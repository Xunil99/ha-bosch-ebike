"""Standalone tests for profile_extra.py — run with: python3 tests/test_profile_extra.py

Loads the module file directly via importlib (like test_range_estimate.py /
test_brouter.py): importing the package would pull in
custom_components/ha_bosch_ebike/__init__.py, which needs Home Assistant.
"""
import importlib.util
from pathlib import Path

_path = (
    Path(__file__).resolve().parent.parent
    / "custom_components" / "ha_bosch_ebike" / "profile_extra.py"
)
_spec = importlib.util.spec_from_file_location("profile_extra", _path)
profile_extra = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(profile_extra)

reachable_ranges = profile_extra.reachable_ranges
next_service_date = profile_extra.next_service_date

BIKE = {
    "serviceDue": {"date": "2026-09-30T14:15:22Z", "odometer": 2000000},
    "driveUnit": {"activeAssistModes": [
        {"name": "Eco", "reachableRange": 60000},
        {"name": "Tour", "reachableRange": 50000},
        {"name": "eMTB", "reachableRange": 40000},
        {"name": "Turbo", "reachableRange": 30000},
    ]},
}


def test_reachable_ranges_returns_name_and_km_in_order():
    out = reachable_ranges(BIKE)
    assert out == [
        {"name": "Eco", "range_km": 60.0},
        {"name": "Tour", "range_km": 50.0},
        {"name": "eMTB", "range_km": 40.0},
        {"name": "Turbo", "range_km": 30.0},
    ]


def test_reachable_ranges_skips_placeholder_and_missing():
    assert reachable_ranges({"driveUnit": {"activeAssistModes": [
        {"name": "0", "reachableRange": 1}, {"name": "Eco"}]}}) == []
    assert reachable_ranges({}) == []


def test_reachable_ranges_skips_non_numeric_range():
    assert reachable_ranges({"driveUnit": {"activeAssistModes": [
        {"name": "Eco", "reachableRange": "abc"}]}}) == []


def test_reachable_ranges_keeps_zero_range():
    assert reachable_ranges({"driveUnit": {"activeAssistModes": [
        {"name": "Eco", "reachableRange": 0}]}}) == [
            {"name": "Eco", "range_km": 0.0}]


def test_next_service_date_parses_iso():
    assert next_service_date(BIKE).year == 2026
    assert next_service_date({}) is None
    assert next_service_date({"serviceDue": {"date": "bogus"}}) is None


def test_next_service_date_parses_date_only():
    assert next_service_date({"serviceDue": {"date": "2026-09-15"}}).month == 9


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("ALL TESTS PASSED")
