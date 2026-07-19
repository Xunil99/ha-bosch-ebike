"""Standalone tests for diagnosis_field_data.py — run with: python3 tests/test_diagnosis_field_data.py

Loads the module file directly via importlib (like test_profile_extra.py):
importing the package would pull in custom_components/ha_bosch_ebike/__init__.py,
which needs Home Assistant.
"""
import importlib.util
from pathlib import Path

_path = (
    Path(__file__).resolve().parent.parent
    / "custom_components" / "ha_bosch_ebike" / "diagnosis_field_data.py"
)
_spec = importlib.util.spec_from_file_location("diagnosis_field_data", _path)
dfd = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(dfd)

capacity_test_summary = dfd.capacity_test_summary
battery_field_data = dfd.battery_field_data
drive_unit_field_data = dfd.drive_unit_field_data


# -- capacity_test_summary --

def test_capacity_test_summary_picks_newest_by_created_at():
    response = {"capacityTesters": [
        {
            "createdAt": "2025-01-01T10:00:00Z",
            "batteryData": {"measuredCapacity": 600, "nominalCapacity": 750},
        },
        {
            "createdAt": "2026-06-15T10:00:00Z",
            "batteryData": {
                "measuredCapacity": 580, "nominalCapacity": 750,
                "fullChargeCycles": 42.0, "onBikeMeasurement": True,
                "manufacturingDate": "2022-03-01",
            },
        },
    ]}
    out = capacity_test_summary(response)
    assert out["measured_wh"] == 580.0
    assert out["nominal_wh"] == 750.0
    assert out["full_charge_cycles"] == 42.0
    assert out["on_bike_measurement"] is True
    assert out["manufacturing_date"] == "2022-03-01"
    assert out["tested_at"] == "2026-06-15T10:00:00Z"


def test_capacity_test_summary_empty_or_missing_is_none():
    assert capacity_test_summary(None) is None
    assert capacity_test_summary({}) is None
    assert capacity_test_summary({"capacityTesters": []}) is None
    assert capacity_test_summary({"capacityTesters": [1, "x", None]}) is None


def test_capacity_test_summary_missing_battery_data_defaults_gracefully():
    out = capacity_test_summary({"capacityTesters": [{"createdAt": "2026-01-01T00:00:00Z"}]})
    assert out["measured_wh"] is None
    assert out["on_bike_measurement"] is None
    assert out["tested_at"] == "2026-01-01T00:00:00Z"


# -- battery_field_data --

def test_battery_field_data_parses_string_numerics():
    response = {"batteries": [{
        "presentAbacusSoh": "87.5",
        "remainingCapacity": "620",
        "remainingEnergy": "615",
        "packTemperature": "23.4",
        "minPackTemperature": "5.1",
        "maxPackTemperature": "41.2",
        "fetTemperature": "30.0",
        "minFetTemperature": "10.0",
        "maxFetTemperature": "55.5",
        "chargeCycleCountOnBike": "120",
        "chargeCycleCountOffBike": "8",
        "chargeDurationTotal": "9800",
        "manufacturingDate": "2021-11-05",
        "hwVersion": "1.2",
        "swVersion": "3.4.5",
    }]}
    out = battery_field_data(response)
    assert out["present_abacus_soh"] == 87.5
    assert out["remaining_capacity_wh"] == 620.0
    assert out["max_pack_temperature_c"] == 41.2
    assert out["charge_cycle_count_on_bike"] == 120.0
    assert out["charge_duration_total_min"] == 9800.0
    assert out["hw_version"] == "1.2"
    assert out["sw_version"] == "3.4.5"


def test_battery_field_data_unparseable_string_is_none_not_crash():
    response = {"batteries": [{"presentAbacusSoh": "n/a", "remainingCapacity": None}]}
    out = battery_field_data(response)
    assert out["present_abacus_soh"] is None
    assert out["remaining_capacity_wh"] is None


def test_battery_field_data_empty_or_missing_is_none():
    assert battery_field_data(None) is None
    assert battery_field_data({}) is None
    assert battery_field_data({"batteries": []}) is None


# -- drive_unit_field_data --

def test_drive_unit_field_data_parses_first_entry():
    response = {"driveUnits": [{
        "maxMotorTemperature": "68",
        "minMotorTemperature": "12",
        "maxPcbTemperature": "72.5",
        "minPcbTemperature": "15.0",
        "thermalDeratingTime": "340",
        "hwVersion": "2.0",
        "swVersion": "19.22.0",
    }]}
    out = drive_unit_field_data(response)
    assert out["max_motor_temperature_c"] == 68.0
    assert out["min_pcb_temperature_c"] == 15.0
    assert out["thermal_derating_time_raw"] == 340.0
    assert out["sw_version"] == "19.22.0"


def test_drive_unit_field_data_ignores_non_dict_entries():
    assert drive_unit_field_data({"driveUnits": ["oops", None]}) is None


def test_drive_unit_field_data_empty_or_missing_is_none():
    assert drive_unit_field_data(None) is None
    assert drive_unit_field_data({}) is None
    assert drive_unit_field_data({"driveUnits": []}) is None


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("ALL TESTS PASSED")
