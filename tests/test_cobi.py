"""Standalone tests for cobi.py - run with: python3 tests/test_cobi.py

Loads the module file directly via importlib (like test_bes2.py): importing the
package would pull in __init__.py, which needs Home Assistant.

COBI (SmartphoneHub with the COBI.Bike app) comes from Bosch's "Activity & Hub
API (COBI)": a flat list of hubs and a flat list of rides, no bikes, no
battery, no odometer, no track. cobi.py turns the rides into the summary shape
the Smart System sensors already read, works out the unit of
durationWithoutStops (the spec does not name it), sums calendar periods and
builds the diagnostics block, which must carry field names and counts only.
"""
import importlib.util
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

_ROOT = Path(__file__).resolve().parent.parent
_path = _ROOT / "custom_components" / "ha_bosch_ebike" / "cobi.py"
_spec = importlib.util.spec_from_file_location("cobi", _path)
cobi = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cobi)

BERLIN = ZoneInfo("Europe/Berlin")


def ride(rid="a1", start="2026-11-20T10:00:00.000Z", minutes=60, km=15.0,
         moving_s=3000, avg=None, unit="s", **more):
    """A raw COBI activity. moving_s is the moving time in seconds, written in `unit`."""
    start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
    end_dt = start_dt + timedelta(minutes=minutes)
    if moving_s is None:
        duration = None
    else:
        duration = {"s": moving_s, "ms": moving_s * 1000, "min": round(moving_s / 60)}[unit]
    raw = {
        "id": rid,
        "startTime": start,
        "endTime": end_dt.isoformat().replace("+00:00", "Z"),
        "totalDistance": int(km * 1000),
        "bikeType": "ELECTRIC_25",
        "elevationGain": 120,
        "avgSpeed": avg if avg is not None else (
            round(km / (moving_s / 3600), 1) if moving_s else 18.0
        ),
        "maxSpeed": 31.5,
        "durationWithoutStops": duration,
    }
    raw.update(more)
    return raw


# --- normalize_activity ------------------------------------------------------------


def test_a_full_ride_maps_onto_the_summary_shape_the_sensors_read():
    a = cobi.normalize_activity(ride(), "s")
    assert a["id"] == "a1"
    assert a["startTime"] == "2026-11-20T10:00:00.000Z"
    assert a["endTime"] == "2026-11-20T11:00:00Z"
    assert a["distance"] == 15000
    assert a["durationWithoutStops"] == 3000
    assert a["speed"] == {"average": 18.0, "maximum": 31.5}
    assert a["elevation"] == {"gain": 120}
    assert a["_cobi_bike_type"] == "ELECTRIC_25"
    assert a["_cobi_duration_estimated"] is False


def test_milliseconds_and_minutes_are_converted_to_seconds():
    assert cobi.normalize_activity(ride(unit="ms"), "ms")["durationWithoutStops"] == 3000
    assert cobi.normalize_activity(ride(unit="min"), "min")["durationWithoutStops"] == 3000


def test_an_unclear_unit_or_a_missing_duration_falls_back_to_the_wall_time():
    for raw, unit in ((ride(), "unclear"), (ride(moving_s=None), "s"), (ride(), None)):
        a = cobi.normalize_activity(raw, unit)
        assert a["durationWithoutStops"] == 3600, (raw, unit)
        assert a["_cobi_duration_estimated"] is True


def test_a_converted_duration_longer_than_the_ride_falls_back_too():
    # 3000 read as minutes would be 50 hours of riding in one hour.
    a = cobi.normalize_activity(ride(), "min")
    assert a["durationWithoutStops"] == 3600 and a["_cobi_duration_estimated"] is True


def test_empty_none_and_wrong_types_never_raise():
    assert cobi.normalize_activity(None, "s") is None
    assert cobi.normalize_activity({}, "s") is None, "no id, nothing to key a ride by"
    assert cobi.normalize_activity("x", "s") is None
    a = cobi.normalize_activity(
        {"id": 7, "startTime": 5, "endTime": None, "totalDistance": "12",
         "avgSpeed": True, "maxSpeed": float("nan"), "elevationGain": [],
         "durationWithoutStops": "60", "bikeType": 3},
        "s",
    )
    assert a["id"] == "7"
    assert a["startTime"] is None and a["endTime"] is None
    assert a["distance"] is None
    assert a["speed"] == {"average": None, "maximum": None}
    assert a["elevation"] == {"gain": None}
    assert a["durationWithoutStops"] is None
    assert a["_cobi_bike_type"] is None


# --- detect_duration_unit -----------------------------------------------------------


def test_seconds_are_recognised():
    rides = [ride(f"a{i}", moving_s=3000 + i * 60) for i in range(5)]
    unit, counts = cobi.detect_duration_unit(rides)
    assert unit == "s", counts
    assert counts["s"] == 5


def test_milliseconds_are_recognised():
    rides = [ride(f"a{i}", moving_s=2400 + i * 60, unit="ms") for i in range(5)]
    assert cobi.detect_duration_unit(rides)[0] == "ms"


def test_minutes_are_recognised():
    rides = [ride(f"a{i}", moving_s=2400 + i * 60, unit="min") for i in range(5)]
    assert cobi.detect_duration_unit(rides)[0] == "min"


def test_a_mixed_list_follows_the_majority():
    rides = [ride(f"s{i}") for i in range(3)] + [ride("m1", unit="ms")]
    unit, counts = cobi.detect_duration_unit(rides)
    assert unit == "s" and counts["s"] == 3 and counts["ms"] == 1


def test_no_majority_is_unclear():
    rides = [ride("s1"), ride("s2"), ride("m1", unit="ms"), ride("m2", unit="ms")]
    assert cobi.detect_duration_unit(rides)[0] == "unclear"


def test_seconds_with_long_stops_stay_seconds():
    # Three hours out, one hour moving, and Bosch averaged the speed over the
    # whole three hours: the speed-time then matches the wall time, not the
    # moving time. Seconds must still win; a fixed tolerance would say unclear.
    rides = [
        ride(f"a{i}", minutes=180, km=20.0, moving_s=3600, avg=round(20.0 / 3, 2))
        for i in range(4)
    ]
    unit, counts = cobi.detect_duration_unit(rides)
    assert unit == "s", counts


def test_all_durations_null_gives_no_verdict():
    unit, counts = cobi.detect_duration_unit([ride("a1", moving_s=None), ride("a2", moving_s=None)])
    assert unit is None and counts["null"] == 2


def test_an_empty_or_broken_list_gives_no_verdict():
    assert cobi.detect_duration_unit([])[0] is None
    assert cobi.detect_duration_unit(None)[0] is None
    assert cobi.detect_duration_unit(["x", {"id": "1"}])[0] is None


# --- period_totals ------------------------------------------------------------------


def _norm(rid, start, km=10.0):
    return cobi.normalize_activity(ride(rid, start=start, km=km), "s")


def test_the_week_starts_on_monday_in_local_time():
    # Monday 2026-11-23 00:30 in Berlin is Sunday 23:30 UTC.
    sunday_late = _norm("sun", "2026-11-22T22:59:00Z")  # Sunday 23:59 Berlin
    monday_early = _norm("mon", "2026-11-22T23:00:00Z")  # Monday 00:00 Berlin
    now = datetime(2026, 11, 24, 12, 0, tzinfo=BERLIN)
    totals = cobi.period_totals([sunday_late, monday_early], now)
    assert totals["week"]["rides"] == 1 and totals["week"]["distance_km"] == 10.0
    assert totals["week"]["start"] == datetime(2026, 11, 23, tzinfo=BERLIN)
    assert totals["month"]["rides"] == 2


def test_the_year_turns_at_local_midnight():
    old_year = _norm("old", "2026-12-31T22:59:00Z")  # 23:59 on New Year's Eve in Berlin
    new_year = _norm("new", "2026-12-31T23:00:00Z")  # 00:00 on 1 January in Berlin
    now = datetime(2027, 1, 2, 9, 0, tzinfo=BERLIN)
    totals = cobi.period_totals([old_year, new_year], now)
    assert totals["year"]["rides"] == 1 and totals["month"]["rides"] == 1
    assert totals["year"]["start"] == datetime(2027, 1, 1, tzinfo=BERLIN)


def test_a_dst_change_inside_the_week_does_not_shift_its_start():
    # 2026-10-25 is the end of summer time in Germany (a Sunday).
    now = datetime(2026, 10, 25, 20, 0, tzinfo=BERLIN)
    monday = _norm("mon", "2026-10-18T22:00:00Z")  # Monday 00:00 CEST
    sunday = _norm("sun", "2026-10-18T21:59:00Z")  # Sunday 23:59 CEST, week before
    totals = cobi.period_totals([monday, sunday], now)
    assert totals["week"]["rides"] == 1
    assert totals["week"]["start"].utcoffset() == timedelta(hours=2)


def test_rides_without_a_start_or_distance_are_handled():
    broken = cobi.normalize_activity({"id": "x", "startTime": None}, "s")
    no_distance = cobi.normalize_activity(ride("nd", start="2026-11-24T08:00:00Z", totalDistance=None), "s")
    now = datetime(2026, 11, 24, 12, 0, tzinfo=BERLIN)
    totals = cobi.period_totals([broken, no_distance, None], now)
    assert totals["week"]["rides"] == 1 and totals["week"]["distance_km"] == 0.0


def test_no_rides_is_zero_not_unknown():
    totals = cobi.period_totals([], datetime(2026, 11, 24, tzinfo=BERLIN))
    assert totals["week"] == {"distance_km": 0.0, "rides": 0, "start": datetime(2026, 11, 23, tzinfo=BERLIN)}


# --- bike types ---------------------------------------------------------------------


def test_rides_without_a_motor_count_and_are_listed():
    acts = [
        cobi.normalize_activity(ride("e1"), "s"),
        cobi.normalize_activity(ride("b1", bikeType="BIOBIKE"), "s"),
        cobi.normalize_activity(ride("u1", bikeType=None), "s"),
    ]
    assert cobi.rides_by_bike_type(acts) == {"ELECTRIC_25": 1, "BIOBIKE": 1, "UNKNOWN": 1}
    now = datetime(2026, 11, 24, tzinfo=BERLIN)
    assert cobi.period_totals(acts, now)["month"]["rides"] == 3


# --- hubs ---------------------------------------------------------------------------


def test_a_hub_is_normalized_and_one_without_serial_is_dropped():
    h = cobi.normalize_hub(
        {"serialNumber": "24173107182521", "partNumber": "8017", "role": "GUEST",
         "activatedAt": "2021-06-04T10:23:12.000Z"}
    )
    assert h == {
        "serial": "24173107182521", "part": "8017", "role": "guest",
        "activated_at": "2021-06-04T10:23:12.000Z",
    }
    assert cobi.normalize_hub({"partNumber": "8017"}) is None
    assert cobi.normalize_hub(None) is None
    assert cobi.normalize_hub({"serialNumber": "1", "role": "ADMIN"})["role"] is None


# --- repair issue -------------------------------------------------------------------


def test_the_no_data_issue_needs_both_lists_empty():
    assert cobi.data_missing([], []) is True
    assert cobi.data_missing(None, None) is True
    assert cobi.data_missing([{"serial": "1"}], []) is False
    assert cobi.data_missing([], [{"id": "a"}]) is False


# --- diagnostics --------------------------------------------------------------------

SERIAL = "24173107182521"
PART = "8017"


def _diag():
    hubs = [
        {"serialNumber": SERIAL, "partNumber": PART, "role": "OWNER", "activatedAt": "2021-06-04T10:23:12.000Z"},
        {"serialNumber": "99887766554433", "role": "GUEST", "extraField": "secret-value"},
    ]
    acts = [
        ride("act000000000001", start="2026-11-20T10:00:00.000Z"),
        ride("act000000000002", start="2026-11-21T10:00:00.000Z", moving_s=None, bikeType="BIOBIKE"),
    ]
    return cobi.diagnostics_summary(hubs, acts), hubs, acts


def test_the_diagnostics_carry_field_names_and_counts():
    d, _, _ = _diag()
    assert d["hub_count"] == 2
    assert d["hub_roles"] == {"OWNER": 1, "GUEST": 1}
    assert d["hub_fields"] == ["activatedAt", "extraField", "partNumber", "role", "serialNumber"]
    assert d["activity_count"] == 2
    assert "durationWithoutStops" in d["activity_fields"]
    assert d["null_counts"]["durationWithoutStops"] == 1
    assert d["bike_type_counts"] == {"ELECTRIC_25": 1, "BIOBIKE": 1}
    assert d["duration_unit"]["verdict"] == "s"
    assert d["duration_unit"]["counts"]["null"] == 1
    assert d["field_types"]["durationWithoutStops"] == {"int": 1, "null": 1}


def test_the_diagnostics_contain_no_values():
    d, hubs, acts = _diag()
    text = json.dumps(d)
    for raw in hubs + acts:
        for value in raw.values():
            if isinstance(value, str) and value not in ("OWNER", "GUEST", "BIOBIKE", "ELECTRIC_25"):
                assert value not in text, f"value {value!r} leaked into the diagnostics"
    assert not re.search(r"\d{4}-\d{2}-\d{2}", text), "no dates"
    assert not re.search(r"\d{6,}", text), "no long digit strings (serials, ids)"


def test_the_diagnostics_survive_garbage():
    d = cobi.diagnostics_summary(None, "x")
    assert d["hub_count"] == 0 and d["activity_count"] == 0
    d = cobi.diagnostics_summary([1, None, {"role": 5}], [None, {"id": None}])
    assert d["hub_roles"] == {"OTHER": 1}
    long_key = {"x" * 200: 1, "ok": 2}
    assert cobi.diagnostics_summary([long_key], [])["hub_fields"] == ["ok"], "absurd keys are not echoed"


def test_error_texts_lose_times_and_ids_but_keep_the_status():
    text = cobi.scrub_text(
        "ClientResponseError: 404, message='Not Found' (Bosch replied: "
        '{"timestamp":"2026-11-24T09:12:33.123Z","at":"09:12:33","traceId":"98765432123456789"})'
    )
    assert "404" in text and "Not Found" in text
    assert "2026" not in text and "09:12" not in text and "98765" not in text
    assert cobi.scrub_text(None) is None


# --- texts ----------------------------------------------------------------------------

_TEXT_FILES = ["strings.json"] + [f"translations/{lang}.json" for lang in ("en", "de", "nl", "cs")]
_COBI_SENSOR_KEYS = (
    "distance_week", "distance_month", "distance_year",
    "rides_week", "rides_month", "rides_year",
    "cobi_hub_role", "cobi_hub_activated_at",
)


def _text(name):
    return json.loads((_ROOT / "custom_components" / "ha_bosch_ebike" / name).read_text(encoding="utf-8"))


def test_every_language_has_the_cobi_texts():
    for name in _TEXT_FILES:
        d = _text(name)
        step = d["config"]["step"]
        assert step["user"]["menu_options"]["cobi"].startswith("COBI"), name
        assert "**COBI**" in step["credentials"]["description"], name
        assert "{portal_url}" in step["credentials"]["description"], name
        advanced = step["credentials"]["sections"]["advanced"]
        assert advanced["name"] and advanced["data"]["kc_idp_hint"], name
        assert advanced["data_description"]["kc_idp_hint"], name
        issue = d["issues"]["no_cobi_data"]
        assert "{account}" in issue["title"] and issue["description"], name
        sensors = d["entity"]["sensor"]
        for key in _COBI_SENSOR_KEYS:
            assert sensors[key]["name"], f"{name}: {key}"
        assert set(sensors["cobi_hub_role"]["state"]) == {"owner", "guest"}, name


def test_the_new_texts_have_no_dashes():
    # Public texts: no dashes as punctuation.
    for name in _TEXT_FILES:
        d = _text(name)
        texts = [d["issues"]["no_cobi_data"]["title"], d["issues"]["no_cobi_data"]["description"],
                 d["config"]["step"]["credentials"]["sections"]["advanced"]["data_description"]["kc_idp_hint"]]
        for text in texts:
            assert " - " not in text and "\u2013" not in text and "\u2014" not in text, (name, text)


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"PASS {name}")
        except Exception as err:  # noqa: BLE001
            failed += 1
            print(f"FAIL {name}: {type(err).__name__}: {err}")
    print(f"{len(tests) - failed}/{len(tests)} passed")
    raise SystemExit(1 if failed else 0)
