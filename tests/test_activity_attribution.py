"""Standalone tests for activity_attribution.py - run with:
python3 tests/test_activity_attribution.py

Bosch's activity summaries carry a bikeId that is the id of the bike in the bike
profile (seen on real Smart System accounts, listed as required in the Activity
Records API 1.4.0). With two or more bikes, a ride whose bikeId names one of the
account's bikes is attributed to that bike; everything else is attributed by
odometer, exactly as before. With one bike nothing changes at all. These tests
pin both halves: the bikeId wins where the odometers cannot tell the bikes
apart, and nothing changes where there is no usable bikeId.

The odometer half was also compared against the previous implementation on
thousands of generated accounts when this was written (rides without a bikeId,
with an unknown one, with a known one equal to the odometer's pick, and mixed):
the results were identical. The scenarios below are the hand-checked version of
that, plus the ones an independent review found a wrong implementation could
still pass (which bike is unwound, in which order, and where the tolerance ends).

coordinator.py imports Home Assistant, so what it does with the result is checked
on its syntax tree and on the extracted property.
"""
import ast
import importlib.util
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_INTEGRATION = _ROOT / "custom_components" / "ha_bosch_ebike"
_spec = importlib.util.spec_from_file_location(
    "activity_attribution", _INTEGRATION / "activity_attribution.py"
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
attribute_activities = _mod.attribute_activities
summarize_attribution = _mod.summarize_attribution


def _bike(bike_id, odometer=None):
    bike = {"id": bike_id, "driveUnit": {}}
    if odometer is not None:
        bike["driveUnit"]["odometer"] = odometer
    return bike


def _ride(ride_id, start_odometer, distance, when, bike_id=None):
    ride = {
        "id": ride_id,
        "startOdometer": start_odometer,
        "distance": distance,
        "startTime": f"2026-10-{when:02d}T10:00:00Z",
    }
    if bike_id is not None:
        ride["bikeId"] = bike_id
    return ride


# --- the bikeId decides -------------------------------------------------------


def test_known_bike_id_wins_where_the_odometer_would_pick_the_other_bike():
    bikes = [_bike("A", 100_000.0), _bike("B", 100_100.0)]
    # Ends at 100020: the odometer picks A (20 m away, B is 80 m away).
    assert attribute_activities(bikes, [_ride("r1", 99_000, 1_020, 5)]) == {"r1": "A"}
    # Bosch says the ride was B's.
    assert attribute_activities(bikes, [_ride("r1", 99_000, 1_020, 5, "B")]) == {"r1": "B"}


def test_known_bike_id_attributes_a_ride_the_odometer_cannot_match():
    bikes = [_bike("A", 100_000.0), _bike("B", 900_000.0)]
    far_off = _ride("r1", 500_000, 1_000, 5)  # fits neither bike within the tolerance
    assert attribute_activities(bikes, [far_off]) == {}
    assert attribute_activities(bikes, [{**far_off, "bikeId": "B"}]) == {"r1": "B"}


def test_known_bike_id_attributes_a_ride_without_odometer_data():
    bikes = [_bike("A", 100_000.0), _bike("B", 900_000.0)]
    rides = [
        {"id": "no-odo-with-id", "startTime": "2026-10-05T10:00:00Z", "bikeId": "B"},
        {"id": "no-odo-no-id", "startTime": "2026-10-04T10:00:00Z"},
        {"id": "odo-none", "startOdometer": None, "startTime": "2026-10-03T10:00:00Z", "bikeId": "A"},
        {"id": "odo-garbage", "startOdometer": "garbage", "startTime": "2026-10-02T10:00:00Z", "bikeId": "A"},
    ]
    assert attribute_activities(bikes, rides) == {
        "no-odo-with-id": "B",
        "odo-none": "A",
        "odo-garbage": "A",
    }


def test_known_bike_id_works_when_no_bike_reports_an_odometer():
    """Two bikes to tell apart, no odometer: the rides that name a bike are attributed, the rest stay open."""
    bikes = [_bike("A"), _bike("B")]
    rides = [_ride("r1", 1_000, 100, 5, "B"), _ride("r2", 900, 100, 4)]
    assert attribute_activities(bikes, rides) == {"r1": "B"}
    assert attribute_activities(bikes, [_ride("r2", 900, 100, 4)]) == {}
    assert attribute_activities([], rides) == {}


def test_two_bikes_where_only_one_reports_an_odometer():
    """The odometer logic treats the one bike with an odometer as the only bike."""
    bikes = [_bike("A", 100_000.0), _bike("B")]
    rides = [_ride("r1", 99_000, 1_000, 5), _ride("r2", 5_000, 100, 4, "B")]
    assert attribute_activities(bikes, rides) == {"r1": "A", "r2": "B"}


def test_a_bike_id_naming_a_bike_without_an_odometer_among_bikes_with_one():
    """Three bikes, C reports no odometer: its rides are attributed, nothing raises."""
    bikes = [_bike("A", 10_000.0), _bike("B", 50_000.0), _bike("C")]
    rides = [_ride("c1", 700_000, 1_000, 6, "C"), _ride("a1", 9_000, 1_000, 5)]
    assert attribute_activities(bikes, rides) == {"c1": "C", "a1": "A"}


# --- with one bike nothing changes -------------------------------------------------


def test_with_one_bike_the_bike_id_changes_nothing():
    """Not even for a bike without an odometer: an EMPTY result means "every ride is this bike's"
    to the sensors, a partial one would make them drop the rides that carry no bikeId."""
    rides = [_ride("new", 900, 100, 6, "A"), _ride("mid", 800, 100, 5), _ride("old", 700, 100, 4, "removed-bike")]
    assert attribute_activities([_bike("A")], rides) == {}
    assert attribute_activities([_bike("A")], [{k: v for k, v in r.items() if k != "bikeId"} for r in rides]) == {}
    # with an odometer every ride is the bike's, whatever it names
    assert attribute_activities([_bike("A", 1_000.0)], rides) == {"new": "A", "mid": "A", "old": "A"}


def test_single_bike_account_attributes_everything_to_the_bike():
    bikes = [_bike("A", 10_000.0)]
    rides = [
        _ride("plain", 9_000, 1_000, 6),
        _ride("own", 8_000, 1_000, 5, "A"),
        _ride("foreign", 7_000, 1_000, 4, "removed-bike"),
        {"id": "no-odometer", "startTime": "2026-10-03T10:00:00Z"},
    ]
    assert attribute_activities(bikes, rides) == {
        "plain": "A", "own": "A", "foreign": "A", "no-odometer": "A",
    }


def test_no_bikes_no_result():
    assert attribute_activities([], [_ride("r1", 0, 1, 1)]) == {}
    assert attribute_activities([_bike("A", 1.0)], []) == {}


# --- the odometer keeps deciding everything else -------------------------------


def test_without_a_bike_id_the_odometer_decides_and_unwinds():
    bikes = [_bike("A", 10_000.0), _bike("B", 50_000.0)]
    rides = [
        _ride("a-new", 9_000, 1_000, 6),
        _ride("a-old", 8_000, 1_000, 5),
        _ride("b-new", 49_000, 1_000, 4),
        _ride("b-old", 48_000, 1_000, 3),
        _ride("nobody", 700_000, 1_000, 2),
    ]
    assert attribute_activities(bikes, rides) == {
        "a-new": "A", "a-old": "A", "b-new": "B", "b-old": "B",
    }


def test_unknown_bike_id_is_ignored_and_the_odometer_decides():
    bikes = [_bike("A", 10_000.0), _bike("B", 50_000.0)]
    rides = [_ride("a1", 9_000, 1_000, 6, "removed-bike"), _ride("b1", 49_000, 1_000, 5, "removed-bike")]
    assert attribute_activities(bikes, rides) == {"a1": "A", "b1": "B"}


def test_garbage_bike_id_values_are_ignored():
    bikes = [_bike("A", 10_000.0), _bike("B", 50_000.0)]
    expected = attribute_activities(bikes, [_ride("a1", 9_000, 1_000, 6)])
    assert expected == {"a1": "A"}
    for junk in (None, "", 0, 7, True, ["A"], {"id": "A"}):
        ride = {**_ride("a1", 9_000, 1_000, 6), "bikeId": junk}
        assert attribute_activities(bikes, [ride]) == expected, junk


def test_activity_without_id_is_skipped():
    bikes = [_bike("A", 10_000.0), _bike("B", 50_000.0)]
    assert attribute_activities(bikes, [{"bikeId": "A", "startOdometer": 9_000, "distance": 1_000}]) == {}


# --- how the bikeId rides unwind the odometer ------------------------------------


def test_bike_id_attributed_rides_unwind_the_odometer_for_the_older_rides():
    """The old rides carry no bikeId; they still need the odometer the newer rides left."""
    bikes = [_bike("A", 10_000.0), _bike("B", 50_000.0)]
    rides = [
        _ride("a-new", 5_000, 5_000, 6, "A"),   # A's odometer unwinds from 10000 to 5000
        _ride("a-old", 4_000, 1_000, 5),         # ends at 5000: only matches A once it was unwound
        _ride("b-new", 40_000, 10_000, 4, "B"),
        _ride("b-old", 39_000, 1_000, 3),        # ends at 40000
    ]
    assert attribute_activities(bikes, rides) == {
        "a-new": "A", "a-old": "A", "b-new": "B", "b-old": "B",
    }


def test_the_bike_named_by_the_bike_id_is_unwound_not_the_one_the_odometer_prefers():
    """r1 ends 20 m from B's odometer but Bosch says A: A must be unwound, so r0 (which ends where r1 began) is A's."""
    bikes = [_bike("A", 100_100.0), _bike("B", 100_000.0)]
    rides = [_ride("r1", 99_000, 1_020, 6, "A"), _ride("r0", 98_000, 1_000, 5)]
    assert attribute_activities(bikes, rides) == {"r1": "A", "r0": "A"}


def test_rides_are_processed_newest_first_whatever_carries_a_bike_id():
    """A newer ride without a bikeId must be matched before an older one with a bikeId unwinds the odometer."""
    bikes = [_bike("A", 10_000.0), _bike("B", 50_000.0)]
    rides = [_ride("r-old", 8_000, 1_000, 5, "A"), _ride("r-new", 9_000, 1_000, 6)]
    assert attribute_activities(bikes, rides) == {"r-new": "A", "r-old": "A"}


def test_a_bike_id_ride_that_does_not_fit_the_odometer_does_not_unwind_it():
    bikes = [_bike("A", 10_000.0), _bike("B", 900_000.0)]
    rides = [
        _ride("reset", 500_000, 1_000, 6, "A"),  # an odometer that has nothing to do with bike A's
        _ride("older", 9_000, 500, 5),            # ends at 9500, A's real odometer is 10000
    ]
    assert attribute_activities(bikes, rides) == {"reset": "A", "older": "A"}


def test_the_fit_is_measured_against_the_bike_the_ride_names():
    """r1 names A but ends at B's odometer: it fits neither A nor, by name, B, so nothing is unwound
    and r0 is matched by the odometer to B, whose odometer is still where it was."""
    bikes = [_bike("A", 100_000.0), _bike("B", 900_000.0)]
    rides = [_ride("r1", 899_000, 1_000, 6, "A"), _ride("r0", 898_000, 1_000, 5)]
    assert attribute_activities(bikes, rides) == {"r1": "A", "r0": "B"}


# --- where the tolerance ends --------------------------------------------------------


def test_the_odometer_matches_up_to_and_including_the_tolerance():
    bikes = [_bike("A", 100_000.0), _bike("B", 900_000.0)]
    assert attribute_activities(bikes, [_ride("r", 100_500, 1_000, 5)]) == {"r": "A"}   # ends 1500 m away
    assert attribute_activities(bikes, [_ride("r", 100_501, 1_000, 5)]) == {}           # ends 1501 m away


def test_a_bike_id_ride_unwinds_up_to_and_including_the_tolerance():
    """r1 ends exactly 1500 m from A's odometer, so it still unwinds A to r1's start; r0 ends there and is 2000 m
    from where A's odometer would be without that."""
    bikes = [_bike("A", 100_000.0), _bike("B", 900_000.0)]
    at_the_limit = [_ride("r1", 98_000, 3_500, 6, "A"), _ride("r0", 97_000, 1_000, 5)]    # r1 ends 101500
    assert attribute_activities(bikes, at_the_limit) == {"r1": "A", "r0": "A"}
    over_the_limit = [_ride("r1", 98_000, 3_501, 6, "A"), _ride("r0", 97_000, 1_000, 5)]  # r1 ends 101501
    assert attribute_activities(bikes, over_the_limit) == {"r1": "A"}


def test_the_tolerance_argument_is_used():
    bikes = [_bike("A", 100_000.0), _bike("B", 900_000.0)]
    ride = _ride("r", 99_000, 1_500, 5)  # ends 500 m from A
    assert attribute_activities(bikes, [ride]) == {"r": "A"}
    assert attribute_activities(bikes, [ride], tolerance_m=100) == {}
    assert attribute_activities(bikes, [ride], 100) == {}


# --- the numbers for the diagnostics ---------------------------------------------------


def test_summary_counts_what_the_diagnostics_need():
    bikes = [_bike("A", 10_000.0), _bike("B", 50_000.0)]
    rides = [
        _ride("known-a", 9_000, 1_000, 6, "A"),
        _ride("known-b", 49_000, 1_000, 5, "B"),
        _ride("unknown", 8_000, 1_000, 4, "removed-bike"),
        _ride("none", 7_000, 1_000, 3),
        {"startTime": "2026-10-02T10:00:00Z", "bikeId": "A"},  # no id: not a ride
    ]
    attribution = {"known-a": "A", "known-b": "A", "unknown": "A"}  # known-b was overruled by hand
    summary = summarize_attribution(bikes, rides, attribution, {"known-b": "A"})
    assert summary == {
        "activities": 4,
        "with_bike_id": 3,
        "bike_id_known": 2,
        "bike_id_unknown": 1,
        "attributed": 3,
        "manually_assigned": 1,
        "bike_id_overruled": 1,
    }, summary


def test_summary_counts_only_what_its_keys_say():
    bikes = [_bike("A", 10_000.0), _bike("B", 50_000.0)]
    rides = [
        _ride("known-open", 9_000, 1_000, 6, "A"),   # names a bike but is not attributed at all: not "overruled"
        {**_ride("junk-int", 1, 1, 5), "bikeId": 7},
        {**_ride("junk-empty", 1, 1, 4), "bikeId": ""},
        _ride("plain", 1, 1, 3),
    ]
    summary = summarize_attribution(bikes, rides, {}, {"gone-ride": "A", "plain": "B"})
    assert summary["with_bike_id"] == 1, summary         # 7 and "" are not ids
    assert summary["bike_id_known"] == 1 and summary["bike_id_unknown"] == 0, summary
    assert summary["manually_assigned"] == 1, summary    # only "plain" is among these rides
    assert summary["bike_id_overruled"] == 0, summary
    assert summary["attributed"] == 0, summary


# --- how the coordinator uses it -------------------------------------------------

_COORD_SRC = (_INTEGRATION / "coordinator.py").read_text(encoding="utf-8")
_COORD_TREE = ast.parse(_COORD_SRC)
_COORD_CLASS = next(
    n for n in _COORD_TREE.body
    if isinstance(n, ast.ClassDef) and n.name == "BoschEBikeCoordinator"
)


def _method(name):
    return next(
        n for n in _COORD_CLASS.body
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name
    )


def _calls(node):
    """Every call in *node* as (name, [unparsed arguments])."""
    found = []
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call):
            func = sub.func
            name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else None
            found.append((name, [ast.unparse(a) for a in sub.args] + [f"{k.arg}={ast.unparse(k.value)}" for k in sub.keywords]))
    return found


def test_coordinator_hands_the_attribution_to_the_module():
    calls = _calls(_method("attribute_activities_to_bikes"))
    assert ("attribute_activities", ["bikes", "activities", "tolerance_m"]) in calls, calls
    imported = {
        alias.name
        for n in _COORD_TREE.body
        if isinstance(n, ast.ImportFrom) and n.module == "activity_attribution"
        for alias in n.names
    }
    assert "attribute_activities" in imported, imported


def test_the_poll_never_deletes_battery_figures_when_the_attribution_changes():
    """Only a manual assignment does. The attribution is evaluated again every poll, and a poll whose bike list
    is missing a bike (observed, see the comment at _floored_odometer_km) moves rides for that poll; deleting
    the battery figure then would lose it for good, because it cannot be recomputed."""
    for sub in ast.walk(_method("_async_update_data")):
        if (
            isinstance(sub, ast.Call)
            and isinstance(sub.func, ast.Attribute)
            and sub.func.attr in ("pop", "clear", "update")
            and ast.unparse(sub.func.value) == "self._activity_consumption"
        ):
            raise AssertionError(
                "_async_update_data changes _activity_consumption: " + ast.unparse(sub)
            )


def test_a_manual_assignment_still_drops_the_battery_figure():
    source = ast.unparse(_method("async_assign_activities"))
    assert "self._activity_consumption.pop(" in source
    assert "self._consumption_topup_activity" in source


def test_manual_assignments_are_exposed_as_a_copy():
    method = _method("manual_activity_bike")
    namespace: dict = {}
    exec(compile(ast.Module(body=[method], type_ignores=[]), "coordinator.py", "exec"), namespace)  # noqa: S102

    class Fake:
        _manual_activity_bike = {"r1": "A"}

    # it is a @property, so exec'ing the def leaves a property object behind
    result = namespace["manual_activity_bike"].fget(Fake())
    assert result == {"r1": "A"}
    result["r2"] = "B"
    assert Fake._manual_activity_bike == {"r1": "A"}, "the property hands out the coordinator's own dict"


def test_diagnostics_report_the_attribution_counts():
    """coordinator.data does not carry the manual assignments (only the stored state does), so the diagnostics
    ask the coordinator for them."""
    tree = ast.parse((_INTEGRATION / "diagnostics.py").read_text(encoding="utf-8"))
    calls = [c for c in _calls(tree) if c[0] == "summarize_attribution"]
    assert calls == [(
        "summarize_attribution",
        ["bikes", "all_activities", "data.get('activity_bike') or {}", "coordinator.manual_activity_bike"],
    )], calls
    # and it ends up in the dump under the name the release notes and the testers are told to look for
    keyed = [
        ast.unparse(value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Dict)
        for key, value in zip(node.keys, node.values)
        if isinstance(key, ast.Constant) and key.value == "bike_attribution"
    ]
    assert len(keyed) == 1 and keyed[0].startswith("summarize_attribution("), keyed


if __name__ == "__main__":
    for _name, _test in sorted(globals().items()):
        if _name.startswith("test_") and callable(_test):
            _test()
            print(f"ok  {_name}")
    print("all activity attribution tests passed")
