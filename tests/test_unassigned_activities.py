"""Standalone tests for unassigned_activities.py — run with: python3 tests/test_unassigned_activities.py"""
import importlib.util
from pathlib import Path

_MODULE_PATH = (
    Path(__file__).resolve().parent.parent
    / "custom_components" / "ha_bosch_ebike" / "unassigned_activities.py"
)
_spec = importlib.util.spec_from_file_location("unassigned_activities", _MODULE_PATH)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
compute_unassigned_activities = _mod.compute_unassigned_activities


def test_all_attributed_returns_empty():
    activities = [{"id": "a1", "startTime": "2026-01-01T10:00:00Z", "title": "Ride 1"}]
    attribution = {"a1": "bike_a"}
    result = compute_unassigned_activities(activities, attribution, bike_count=2)
    assert result == [], result


def test_missing_attribution_entry_is_reported():
    activities = [
        {"id": "a1", "startTime": "2026-01-01T10:00:00Z", "title": "Ride 1"},
        {"id": "a2", "startTime": "2026-01-02T10:00:00Z", "title": "Ride 2"},
    ]
    attribution = {"a1": "bike_a"}
    result = compute_unassigned_activities(activities, attribution, bike_count=2)
    assert result == [{"id": "a2", "date": "2026-01-02T10:00:00Z", "title": "Ride 2"}], result


def test_single_bike_account_always_empty_even_if_unattributed():
    activities = [{"id": "a1", "startTime": "2026-01-01T10:00:00Z", "title": "Ride 1"}]
    result = compute_unassigned_activities(activities, {}, bike_count=1)
    assert result == [], result


def test_zero_bike_account_also_empty():
    activities = [{"id": "a1", "startTime": "2026-01-01T10:00:00Z", "title": "Ride 1"}]
    result = compute_unassigned_activities(activities, {}, bike_count=0)
    assert result == [], result


def test_activity_without_id_is_skipped():
    activities = [{"startTime": "2026-01-01T10:00:00Z", "title": "No ID"}]
    result = compute_unassigned_activities(activities, {}, bike_count=2)
    assert result == [], result


def test_missing_date_and_title_still_included_with_none():
    activities = [{"id": "a1"}]
    result = compute_unassigned_activities(activities, {}, bike_count=2)
    assert result == [{"id": "a1", "date": None, "title": None}], result


def test_result_capped_at_max_results():
    activities = [
        {"id": f"a{i}", "startTime": f"2026-01-{(i % 28) + 1:02d}T10:00:00Z", "title": f"Ride {i}"}
        for i in range(80)
    ]
    result = compute_unassigned_activities(activities, {}, bike_count=2)
    assert len(result) == _mod.MAX_RESULTS, len(result)


def test_no_activities_returns_empty():
    assert compute_unassigned_activities([], {}, bike_count=2) == []


def test_multi_bike_isolation_matches_issue_47_shape():
    # Same account shape as the issue #47 regression: bike A's and bike B's
    # own rides are both correctly attributed, only the genuinely stray
    # historical ride shows up as unassigned.
    activities = [
        {"id": "act_a2", "startTime": "2026-01-03T10:00:00Z", "title": "Bike A ride"},
        {"id": "act_b1", "startTime": "2026-01-02T10:00:00Z", "title": "Bike B ride"},
        {"id": "act_old", "startTime": "2024-06-01T10:00:00Z", "title": "Ancient ride"},
    ]
    attribution = {"act_a2": "bike_a", "act_b1": "bike_b"}
    result = compute_unassigned_activities(activities, attribution, bike_count=2)
    assert result == [{"id": "act_old", "date": "2024-06-01T10:00:00Z", "title": "Ancient ride"}], result


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("ALL TESTS PASSED")
