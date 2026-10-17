"""Standalone tests for range_estimate.py — run with: python3 tests/test_range_estimate.py"""
import importlib.util
from pathlib import Path

# Load the module file directly: importing the package would pull in
# custom_components/ha_bosch_ebike/__init__.py, which needs Home Assistant.
_MODULE_PATH = (
    Path(__file__).resolve().parent.parent
    / "custom_components" / "ha_bosch_ebike" / "range_estimate.py"
)
_spec = importlib.util.spec_from_file_location("range_estimate", _MODULE_PATH)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
compute_range_estimate = _mod.compute_range_estimate
corrected_track_distance = _mod.corrected_track_distance
describe_range_estimate = _mod.describe_range_estimate
range_estimate_attributes = _mod.range_estimate_attributes
range_estimate_log_key = _mod.range_estimate_log_key
MIN_REALISTIC_WH_PER_KM = _mod.MIN_REALISTIC_WH_PER_KM
MIN_PLAUSIBLE_WH_PER_KM = _mod.MIN_PLAUSIBLE_WH_PER_KM
MAX_IGNORED_SAMPLE = _mod.MAX_IGNORED_SAMPLE
MIN_ESTIMATE_TOUR_KM = _mod.MIN_ESTIMATE_TOUR_KM
MIN_TOUR_KM = _mod.MIN_TOUR_KM


def test_corrected_track_distance_partial_summary():
    # Issue #31 matscheck case: summary reports a partial 1.2 km, the full GPS
    # track is 5.4 km -> correct upwards to the track distance.
    assert corrected_track_distance(1200.0, 5400.0) == 5400.0


def test_corrected_track_distance_keeps_when_track_not_longer():
    # Track shorter/equal (still uploading) -> keep the summary (never shrink).
    assert corrected_track_distance(5400.0, 1200.0) is None
    assert corrected_track_distance(5400.0, 5400.0) is None


def test_corrected_track_distance_ignores_noise():
    # Within the 5 % / 200 m noise band -> no correction.
    assert corrected_track_distance(5000.0, 5100.0) is None   # +2 %
    assert corrected_track_distance(10000.0, 10150.0) is None  # +150 m


def test_corrected_track_distance_absolute_cap():
    # Absurd track (unit surprise / GPS outliers) above 500 km -> reject.
    assert corrected_track_distance(1000.0, 600_000.0) is None


def test_corrected_track_distance_none_track():
    assert corrected_track_distance(1200.0, None) is None


def act(aid, km, start="2026-06-01T10:00:00Z"):
    return {"id": aid, "distance": km * 1000, "startTime": start}


def test_happy_path():
    # 5 Touren à 20 km à 100 Wh -> 5 Wh/km
    activities = [act(f"a{i}", 20) for i in range(5)]
    bike_map = {f"a{i}": "bike1" for i in range(5)}
    cons = {f"a{i}": {"consumed_wh": 100.0} for i in range(5)}
    r = compute_range_estimate(activities, bike_map, cons, "bike1")
    assert r is not None
    assert abs(r["wh_per_km"] - 5.0) < 0.001, r
    assert r["tours_used"] == 5
    assert abs(r["window_km"] - 100.0) < 0.001
    assert r["newest_tour_date"] == "2026-06-01T10:00:00Z"


def test_distance_weighted():
    # 100 km à 5 Wh/km (als 2 Touren, MIN_TOURS=3) + 10 km à 16.5 Wh/km
    # -> (500+165)/110 Wh/km, auf 2 Nachkommastellen gerundet
    activities = [act("a1", 50), act("a1b", 50), act("a2", 10)]
    bike_map = {"a1": "bike1", "a1b": "bike1", "a2": "bike1"}
    cons = {
        "a1": {"consumed_wh": 250.0},
        "a1b": {"consumed_wh": 250.0},
        "a2": {"consumed_wh": 165.0},
    }
    r = compute_range_estimate(activities, bike_map, cons, "bike1")
    assert abs(r["wh_per_km"] - round(665.0 / 110.0, 2)) < 0.001


def test_window_stops_at_500km():
    # 12 Touren à 50 km: nach 10 Touren sind 500 km erreicht -> Tour 11/12 ignoriert
    activities = [act(f"a{i}", 50) for i in range(12)]
    bike_map = {f"a{i}": "bike1" for i in range(12)}
    cons = {f"a{i}": {"consumed_wh": 250.0} for i in range(12)}
    r = compute_range_estimate(activities, bike_map, cons, "bike1")
    assert r["tours_used"] == 10
    assert abs(r["window_km"] - 500.0) < 0.001


def test_window_overshoot_includes_crossing_tour():
    # 9 Touren à 60 km: Tour 9 überschreitet die 500-km-Grenze (480 -> 540 km)
    # und wird laut Doku trotzdem noch mitgenommen
    activities = [act(f"a{i}", 60) for i in range(9)]
    bike_map = {f"a{i}": "bike1" for i in range(9)}
    cons = {f"a{i}": {"consumed_wh": 300.0} for i in range(9)}
    r = compute_range_estimate(activities, bike_map, cons, "bike1")
    assert r["tours_used"] == 9
    assert abs(r["window_km"] - 540.0) < 0.001


def test_min_data_thresholds():
    # nur 2 Touren -> kein Wert; 3 Touren aber < 30 km -> kein Wert. Das
    # Ergebnis bleibt ein dict, damit die Sensoren trotzdem zeigen, wie viel
    # Datenbasis da ist (und was ignoriert wurde).
    activities = [act("a1", 20), act("a2", 20)]
    bike_map = {"a1": "bike1", "a2": "bike1"}
    cons = {"a1": {"consumed_wh": 100.0}, "a2": {"consumed_wh": 100.0}}
    r = compute_range_estimate(activities, bike_map, cons, "bike1")
    assert r["wh_per_km"] is None
    assert r["tours_used"] == 2
    assert abs(r["window_km"] - 40.0) < 0.001

    activities = [act(f"a{i}", 5) for i in range(3)]
    bike_map = {f"a{i}": "bike1" for i in range(3)}
    cons = {f"a{i}": {"consumed_wh": 25.0} for i in range(3)}
    r = compute_range_estimate(activities, bike_map, cons, "bike1")
    assert r["wh_per_km"] is None
    assert r["tours_used"] == 3
    assert abs(r["window_km"] - 15.0) < 0.001

    # Kein einziges Bike-Match: leeres, aber vollständiges Ergebnis.
    r = compute_range_estimate([], {}, {}, "bike1")
    assert r["wh_per_km"] is None
    assert r["tours_used"] == 0 and r["tours_ignored"] == 0
    assert r["wh_per_km_min"] is None and r["wh_per_km_max"] is None
    assert r["newest_tour_date"] is None and r["tours_ignored_sample"] == []
    assert r["tours_used_by_source"] == {}
    assert r["tours_too_short"] == 0


def test_skips_invalid_tours():
    # Touren ohne Verbrauch, mit 0 Wh oder Mini-Distanz (<0.5 km) überspringen,
    # fremde Bikes ignorieren
    activities = [
        act("ok1", 20), act("nocons", 30), act("zero", 25),
        act("tiny", 0.3), act("other", 40), act("ok2", 20), act("ok3", 20),
    ]
    bike_map = {a["id"]: "bike1" for a in activities}
    bike_map["other"] = "bike2"
    cons = {
        "ok1": {"consumed_wh": 100.0}, "zero": {"consumed_wh": 0.0},
        "tiny": {"consumed_wh": 10.0}, "other": {"consumed_wh": 999.0},
        "ok2": {"consumed_wh": 100.0}, "ok3": {"consumed_wh": 100.0},
    }
    r = compute_range_estimate(activities, bike_map, cons, "bike1")
    assert r["tours_used"] == 3
    assert abs(r["wh_per_km"] - 5.0) < 0.001


def test_skips_implausible_wh_per_km_stale_entry():
    # Issue #78 follow-up: a consumption entry persisted before the write-time
    # guard existed (or any other already-stored implausible value) must not
    # poison the average just because it is still sitting in storage - a
    # single entry with a 75000 km-range-implying ratio (0.01 Wh/km) mixed
    # among otherwise-normal tours.
    activities = [
        act("ok1", 20), act("ok2", 20), act("ok3", 20), act("stale", 500),
    ]
    bike_map = {a["id"]: "bike1" for a in activities}
    cons = {
        "ok1": {"consumed_wh": 100.0}, "ok2": {"consumed_wh": 100.0},
        "ok3": {"consumed_wh": 100.0}, "stale": {"consumed_wh": 5.0},
    }
    r = compute_range_estimate(activities, bike_map, cons, "bike1")
    assert r["tours_used"] == 3
    assert abs(r["wh_per_km"] - 5.0) < 0.001


def _bike_inputs(activities, wh_by_id):
    """bike_map/consumption for tests where every tour belongs to bike1."""
    bike_map = {a["id"]: "bike1" for a in activities}
    cons = {aid: {"consumed_wh": wh} for aid, wh in wh_by_id.items()}
    return bike_map, cons


def test_write_gate_stays_looser_than_the_read_filter():
    # coordinator.py refuses to persist a split below MIN_PLAUSIBLE_WH_PER_KM
    # and opens the top-up window (issue #67) only for splits it accepted.
    # The cloud counter reaches the cloud late and in pieces, so a ride's
    # FIRST credit is routinely a fraction of its true energy. Tightening the
    # write gate up to the read filter's level would refuse exactly those
    # credits and leave the top-up nothing to complete.
    assert MIN_PLAUSIBLE_WH_PER_KM < MIN_REALISTIC_WH_PER_KM


def test_ignores_tour_below_realistic_floor():
    # Issue #78 follow-up: a ride whose energy was only partly counted (a
    # 30 km ride stored with 40 Wh, i.e. 1.33 Wh/km) clears the old 1.0 Wh/km
    # floor but is far too good to be true. Left in, it would drag the average
    # from 5.0 down to 3.78 Wh/km and push the range up by a third.
    activities = [
        act("ok1", 20, "2026-06-04T10:00:00Z"),
        act("lag", 30, "2026-06-03T10:00:00Z"),
        act("ok2", 20, "2026-06-02T10:00:00Z"),
        act("ok3", 20, "2026-06-01T10:00:00Z"),
    ]
    bike_map, cons = _bike_inputs(
        activities, {"ok1": 100.0, "lag": 40.0, "ok2": 100.0, "ok3": 100.0}
    )
    r = compute_range_estimate(activities, bike_map, cons, "bike1")
    assert r["tours_used"] == 3
    assert abs(r["wh_per_km"] - 5.0) < 0.001
    assert r["tours_ignored"] == 1
    assert r["tours_ignored_sample"] == [
        {"date": "2026-06-03", "km": 30.0, "wh": 40.0, "source": "cloud"}
    ]


def test_floor_is_inclusive():
    km = 20.0
    on_the_floor = MIN_REALISTIC_WH_PER_KM * km
    activities = [act(f"a{i}", km) for i in range(3)] + [act("edge", km), act("below", km)]
    bike_map, cons = _bike_inputs(
        activities,
        {"a0": 100.0, "a1": 100.0, "a2": 100.0,
         "edge": on_the_floor, "below": on_the_floor - 0.1},
    )
    r = compute_range_estimate(activities, bike_map, cons, "bike1")
    assert r["tours_used"] == 4
    assert r["tours_ignored"] == 1
    assert r["wh_per_km_min"] == MIN_REALISTIC_WH_PER_KM


def test_zero_wh_tour_counts_as_ignored_but_a_tiny_tour_does_not():
    # A real distance with 0 Wh is a measurement hole and counts as ignored.
    # A tour under MIN_TOUR_KM is not a ride worth judging at all and stays
    # out of the count, so the number means "rides that were left out".
    activities = [act("ok1", 20), act("ok2", 20), act("ok3", 20), act("zero", 25), act("tiny", 0.3)]
    bike_map, cons = _bike_inputs(
        activities,
        {"ok1": 100.0, "ok2": 100.0, "ok3": 100.0, "zero": 0.0, "tiny": 10.0},
    )
    r = compute_range_estimate(activities, bike_map, cons, "bike1")
    assert r["tours_used"] == 3
    assert r["tours_ignored"] == 1
    assert r["tours_too_short"] == 0   # 0.3 km is not a ride at all


def test_ignored_tours_do_not_fill_the_window():
    # Ignored tours add no kilometres, so the walk reaches back further to
    # fill the 500 km. Tours beyond the window are never looked at, so they
    # are not counted as ignored either.
    activities = (
        [act(f"bad{i}", 200) for i in range(3)]
        + [act(f"ok{i}", 50) for i in range(12)]
        + [act(f"old{i}", 50) for i in range(2)]
    )
    wh = {f"bad{i}": 100.0 for i in range(3)}
    wh.update({f"ok{i}": 250.0 for i in range(12)})
    wh.update({f"old{i}": 100.0 for i in range(2)})
    bike_map, cons = _bike_inputs(activities, wh)
    r = compute_range_estimate(activities, bike_map, cons, "bike1")
    assert r["tours_used"] == 10
    assert abs(r["window_km"] - 500.0) < 0.001
    assert r["tours_ignored"] == 3


def test_min_and_max_rate_over_the_used_tours():
    # 4, 5, 6 and 12 Wh/km over 20 km each
    activities = [act(f"a{i}", 20) for i in range(4)]
    bike_map, cons = _bike_inputs(
        activities, {"a0": 80.0, "a1": 100.0, "a2": 120.0, "a3": 240.0}
    )
    r = compute_range_estimate(activities, bike_map, cons, "bike1")
    assert r["tours_used"] == 4
    assert abs(r["wh_per_km"] - 6.75) < 0.001
    assert r["wh_per_km_min"] == 4.0
    assert r["wh_per_km_max"] == 12.0


def _all_tours_ignored():
    # The fresh-install artefact from issue #78: every tour of one batch
    # carries the same too-low rate (here 1.9 Wh/km), newest first.
    activities = [
        act(f"a{i}", 25, f"2026-06-{10 - i:02d}T10:00:00Z") for i in range(6)
    ]
    bike_map, cons = _bike_inputs(activities, {a["id"]: 47.5 for a in activities})
    return compute_range_estimate(activities, bike_map, cons, "bike1")


def test_all_tours_ignored_keeps_the_diagnostics():
    r = _all_tours_ignored()
    assert r["wh_per_km"] is None
    assert r["tours_used"] == 0
    assert r["tours_ignored"] == 6
    assert r["wh_per_km_min"] is None and r["wh_per_km_max"] is None
    # the sample is capped and newest first
    assert len(r["tours_ignored_sample"]) == MAX_IGNORED_SAMPLE
    assert r["tours_ignored_sample"][0] == {
        "date": "2026-06-10", "km": 25.0, "wh": 47.5, "source": "cloud"
    }
    assert r["tours_ignored_sample"][1]["date"] == "2026-06-09"


def test_source_tells_the_live_soc_path_from_the_cloud_split():
    # The two fail differently (a stale SoC sample vs. a late, partial energy
    # counter), so a report has to say which one produced which tour. Only the
    # live-SoC path stamps a source on its entries, everything else is a
    # split of the cloud counter.
    activities = [act(f"a{i}", 20, f"2026-06-{10 - i:02d}T10:00:00Z") for i in range(6)]
    bike_map = {a["id"]: "bike1" for a in activities}
    cons = {
        "a0": {"consumed_wh": 30.0, "source": "ble_live"},   # 1.5 Wh/km, ignored
        "a1": {"consumed_wh": 30.0},                          # 1.5 Wh/km, ignored
        "a2": {"consumed_wh": 100.0, "source": "ble_live"},
        "a3": {"consumed_wh": 100.0, "source": "ble_live"},
        "a4": {"consumed_wh": 100.0},
        "a5": {"consumed_wh": 100.0},
    }
    r = compute_range_estimate(activities, bike_map, cons, "bike1")
    assert r["tours_used_by_source"] == {"ble_live": 2, "cloud": 2}
    assert [t["source"] for t in r["tours_ignored_sample"]] == ["ble_live", "cloud"]
    text = describe_range_estimate(r)
    assert "4 tours (ble_live 2, cloud 2)" in text   # sorted by name, stable
    assert "30.0 Wh ble_live" in text and "30.0 Wh cloud" in text


def test_the_minimum_length_is_a_real_ride_not_an_errand():
    # A ride this short says little about how far a battery goes, and its
    # energy is the hardest to capture precisely, so it stays out of the
    # estimate no matter how plausible its own figure looks.
    assert MIN_ESTIMATE_TOUR_KM > MIN_TOUR_KM


def test_tours_under_the_minimum_length_are_not_used():
    short = MIN_ESTIMATE_TOUR_KM - 0.01
    activities = [act(f"a{i}", 20) for i in range(3)] + [act("s1", short), act("s2", 2.0)]
    bike_map, cons = _bike_inputs(
        activities,
        {"a0": 100.0, "a1": 100.0, "a2": 100.0, "s1": short * 20.0, "s2": 2.0 * 20.0},
    )
    r = compute_range_estimate(activities, bike_map, cons, "bike1")
    assert r["tours_used"] == 3
    assert r["tours_too_short"] == 2
    assert abs(r["wh_per_km"] - 5.0) < 0.001   # the 20 Wh/km short ones did not move it


def test_the_minimum_length_is_inclusive():
    activities = [act(f"a{i}", 20) for i in range(3)] + [act("edge", MIN_ESTIMATE_TOUR_KM)]
    bike_map, cons = _bike_inputs(
        activities,
        {"a0": 100.0, "a1": 100.0, "a2": 100.0, "edge": MIN_ESTIMATE_TOUR_KM * 5.0},
    )
    r = compute_range_estimate(activities, bike_map, cons, "bike1")
    assert r["tours_used"] == 4
    assert r["tours_too_short"] == 0


def test_a_short_tour_is_counted_as_short_not_as_unrealistic():
    # Length is judged first. A short tour with 0 Wh is "too short", it must
    # not also show up in the list of tours ignored for their energy.
    activities = [act(f"a{i}", 20) for i in range(3)] + [act("short0", 3.0)]
    bike_map, cons = _bike_inputs(
        activities, {"a0": 100.0, "a1": 100.0, "a2": 100.0, "short0": 0.0}
    )
    r = compute_range_estimate(activities, bike_map, cons, "bike1")
    assert r["tours_too_short"] == 1
    assert r["tours_ignored"] == 0 and r["tours_ignored_sample"] == []


def test_a_rider_with_only_short_rides_gets_no_value_and_sees_why():
    # Issue #78 (a real report): 35 tours over 93 km, 2.7 km each, averaging
    # 3.9 Wh/km while Bosch's own forecast for that bike implies 5 to 10. All
    # the estimate can say about such a rider is how far errands go.
    activities = [act(f"a{i}", 3.0, f"2026-06-{(i % 28) + 1:02d}T10:00:00Z") for i in range(40)]
    bike_map, cons = _bike_inputs(activities, {a["id"]: 9.0 for a in activities})
    r = compute_range_estimate(activities, bike_map, cons, "bike1")
    assert r["wh_per_km"] is None
    assert r["tours_used"] == 0
    assert r["tours_too_short"] == 40
    assert r["tours_ignored"] == 0


def test_short_tours_are_reported_in_attributes_and_log_line():
    activities = [act(f"a{i}", 20) for i in range(3)] + [act("s1", 2.0), act("s2", 3.0)]
    bike_map, cons = _bike_inputs(
        activities, {"a0": 100.0, "a1": 100.0, "a2": 100.0, "s1": 18.0, "s2": 27.0}
    )
    r = compute_range_estimate(activities, bike_map, cons, "bike1")
    assert range_estimate_attributes(r)["tours_too_short"] == 2
    text = describe_range_estimate(r)
    assert "2 tours under 5 km not used" in text
    # nothing short -> nothing said
    clean = compute_range_estimate(activities[:3], bike_map, cons, "bike1")
    assert "under" not in describe_range_estimate(clean)


def test_attributes_expose_the_diagnostics_even_without_a_value():
    a = range_estimate_attributes(_all_tours_ignored())
    assert a["wh_per_km"] is None
    assert a["tours_used"] == 0
    assert a["tours_ignored"] == 6
    assert len(a["tours_ignored_sample"]) == MAX_IGNORED_SAMPLE
    for key in ("wh_per_km", "tours_used", "window_km", "newest_tour_date",
                "tours_ignored", "tours_ignored_sample", "wh_per_km_min",
                "wh_per_km_max", "tours_used_by_source", "tours_too_short"):
        assert key in a, key
    # No estimate computed yet (first poll, eBike System 2): nothing to show.
    assert range_estimate_attributes(None) == {}


def test_describe_with_a_value():
    activities = [act(f"a{i}", 20) for i in range(4)]
    bike_map, cons = _bike_inputs(
        activities, {"a0": 80.0, "a1": 100.0, "a2": 120.0, "a3": 240.0}
    )
    text = describe_range_estimate(compute_range_estimate(activities, bike_map, cons, "bike1"))
    assert "6.75 Wh/km" in text
    assert "4 tours (cloud 4)" in text
    assert "80.0 km" in text
    assert "4.00 to 12.00" in text
    assert "ignored" not in text


def test_describe_lists_the_ignored_tours():
    text = describe_range_estimate(_all_tours_ignored())
    assert text.startswith("no estimate yet")
    assert "6 tours ignored" in text
    assert str(MIN_REALISTIC_WH_PER_KM) in text
    assert "2026-06-10 25.0 km 47.5 Wh cloud" in text
    assert "and 1 more" in text


def test_log_key_follows_the_numbers_that_matter():
    activities = [act(f"a{i}", 20) for i in range(4)]
    bike_map, cons = _bike_inputs(
        activities, {"a0": 80.0, "a1": 100.0, "a2": 120.0, "a3": 240.0}
    )
    a = compute_range_estimate(activities, bike_map, cons, "bike1")
    b = compute_range_estimate(activities, bike_map, cons, "bike1")
    assert range_estimate_log_key(a) == range_estimate_log_key(b)

    # one more tour left out -> a new line is worth writing
    extra = activities + [act("lag", 25)]
    bike_map2, cons2 = _bike_inputs(
        extra, {"a0": 80.0, "a1": 100.0, "a2": 120.0, "a3": 240.0, "lag": 20.0}
    )
    c = compute_range_estimate(extra, bike_map2, cons2, "bike1")
    assert range_estimate_log_key(a) != range_estimate_log_key(c)


def test_unmapped_activities_count_for_single_bike_fallback():
    # leere bike_map + fallback_all=True (Single-Bike-Konto, Attribution leer)
    activities = [act(f"a{i}", 20) for i in range(3)]
    cons = {f"a{i}": {"consumed_wh": 100.0} for i in range(3)}
    r = compute_range_estimate(activities, {}, cons, "bike1", fallback_all=True)
    assert r is not None and r["tours_used"] == 3



track_distance_m = _mod.track_distance_m


def test_track_distance_prefers_cumulative_field():
    # Größter kumulativer Bosch-Wert gewinnt (robust gegen fehlendes Track-Ende)
    d = {"activityDetails": [
        {"distance": 0}, {"distance": 5200.0}, {"distance": 12340.5}, {"distance": None},
    ]}
    assert track_distance_m(d) == 12340.5


def test_track_distance_haversine_fallback():
    # Ohne distance-Feld: Haversine — 1 Breitengrad ≈ 111 km
    d = {"activityDetails": [
        {"latitude": 48.0, "longitude": 12.0},
        {"latitude": 49.0, "longitude": 12.0},
    ]}
    v = track_distance_m(d)
    assert v is not None and 110000 < v < 112500, v


def test_track_distance_filters_bad_points():
    # (0,0) und Out-of-Range-Koordinaten werden ignoriert -> < 2 Punkte -> None
    d = {"activityDetails": [
        {"latitude": 0, "longitude": 0},
        {"latitude": 91.0, "longitude": 12.0},
        {"latitude": 48.0, "longitude": 181.0},
        {"latitude": 48.0, "longitude": 12.0},
    ]}
    assert track_distance_m(d) is None


def test_track_distance_unusable_input():
    assert track_distance_m({"activityDetails": []}) is None
    assert track_distance_m({}) is None
    assert track_distance_m(None) is None
    assert track_distance_m([1, 2, 3]) is None
    assert track_distance_m({"activityDetails": "kaputt"}) is None


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("ALL TESTS PASSED")
