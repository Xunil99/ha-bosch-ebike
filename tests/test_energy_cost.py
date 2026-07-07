"""Standalone tests for energy_cost.py — run with: python3 tests/test_energy_cost.py"""
import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path

_MODULE_PATH = (
    Path(__file__).resolve().parent.parent
    / "custom_components" / "ha_bosch_ebike" / "energy_cost.py"
)
_spec = importlib.util.spec_from_file_location("energy_cost", _MODULE_PATH)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
compute_energy_windows = _mod.compute_energy_windows

NOW = datetime(2026, 7, 7, 12, 0, 0, tzinfo=timezone.utc)


def _iso(days_ago):
    return (NOW - timedelta(days=days_ago)).isoformat().replace("+00:00", "Z")


def test_single_ride_within_all_windows():
    activities = [{"id": "a1", "startTime": _iso(2)}]
    activity_bike = {"a1": "bike_a"}
    consumption = {"a1": {"consumed_wh": 150.0}}
    result = compute_energy_windows(activities, activity_bike, consumption, "bike_a", NOW)
    assert result == {"7d": 150.0, "30d": 150.0, "365d": 150.0}, result


def test_ride_outside_week_but_inside_month():
    activities = [{"id": "a1", "startTime": _iso(10)}]
    activity_bike = {"a1": "bike_a"}
    consumption = {"a1": {"consumed_wh": 200.0}}
    result = compute_energy_windows(activities, activity_bike, consumption, "bike_a", NOW)
    assert "7d" not in result, result
    assert result["30d"] == 200.0
    assert result["365d"] == 200.0


def test_ride_outside_all_windows_produces_empty_dict():
    activities = [{"id": "a1", "startTime": _iso(400)}]
    activity_bike = {"a1": "bike_a"}
    consumption = {"a1": {"consumed_wh": 200.0}}
    result = compute_energy_windows(activities, activity_bike, consumption, "bike_a", NOW)
    assert result == {}, result


def test_multiple_rides_sum_within_window():
    activities = [
        {"id": "a1", "startTime": _iso(1)},
        {"id": "a2", "startTime": _iso(5)},
        {"id": "a3", "startTime": _iso(20)},
    ]
    activity_bike = {"a1": "bike_a", "a2": "bike_a", "a3": "bike_a"}
    consumption = {
        "a1": {"consumed_wh": 100.0},
        "a2": {"consumed_wh": 50.0},
        "a3": {"consumed_wh": 300.0},
    }
    result = compute_energy_windows(activities, activity_bike, consumption, "bike_a", NOW)
    assert result["7d"] == 150.0, result   # a1 + a2
    assert result["30d"] == 450.0, result  # a1 + a2 + a3
    assert result["365d"] == 450.0, result


def test_multi_bike_isolation_matches_issue_47_fix():
    # Same shape as the issue #47 regression: bike A's newer ride must not
    # leak into bike B's energy totals.
    activities = [
        {"id": "act_a2", "startTime": _iso(1)},
        {"id": "act_b1", "startTime": _iso(2)},
    ]
    activity_bike = {"act_a2": "bike_a", "act_b1": "bike_b"}
    consumption = {
        "act_a2": {"consumed_wh": 111.0},
        "act_b1": {"consumed_wh": 55.0},
    }
    result_a = compute_energy_windows(activities, activity_bike, consumption, "bike_a", NOW)
    result_b = compute_energy_windows(activities, activity_bike, consumption, "bike_b", NOW)
    assert result_a["7d"] == 111.0, result_a
    assert result_b["7d"] == 55.0, result_b


def test_single_bike_fallback_when_attribution_empty():
    activities = [{"id": "s1", "startTime": _iso(3)}]
    consumption = {"s1": {"consumed_wh": 80.0}}
    result = compute_energy_windows(activities, {}, consumption, "only_bike", NOW, fallback_all=True)
    assert result["7d"] == 80.0, result

    # Without fallback_all, an empty attribution matches nothing.
    result_no_fallback = compute_energy_windows(activities, {}, consumption, "only_bike", NOW, fallback_all=False)
    assert result_no_fallback == {}, result_no_fallback


def test_ride_with_no_consumption_entry_is_skipped():
    activities = [{"id": "a1", "startTime": _iso(1)}]
    activity_bike = {"a1": "bike_a"}
    result = compute_energy_windows(activities, activity_bike, {}, "bike_a", NOW)
    assert result == {}, result


def test_ride_missing_start_time_is_skipped_not_fatal():
    activities = [
        {"id": "a1"},  # no startTime at all
        {"id": "a2", "startTime": _iso(1)},
    ]
    activity_bike = {"a1": "bike_a", "a2": "bike_a"}
    consumption = {
        "a1": {"consumed_wh": 999.0},
        "a2": {"consumed_wh": 42.0},
    }
    result = compute_energy_windows(activities, activity_bike, consumption, "bike_a", NOW)
    assert result["7d"] == 42.0, result


def test_no_activities_returns_empty_dict():
    assert compute_energy_windows([], {}, {}, "bike_a", NOW) == {}


def test_bike_with_zero_matching_activities_among_others():
    activities = [{"id": "a1", "startTime": _iso(1)}]
    activity_bike = {"a1": "bike_a"}
    consumption = {"a1": {"consumed_wh": 100.0}}
    result = compute_energy_windows(activities, activity_bike, consumption, "bike_c_no_rides", NOW)
    assert result == {}, result


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("ALL TESTS PASSED")
