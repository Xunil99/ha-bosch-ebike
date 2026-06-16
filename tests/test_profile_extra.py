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
theft_status = profile_extra.theft_status
frame_number = profile_extra.frame_number
battery_soh = profile_extra.battery_soh
software_update_available = profile_extra.software_update_available
special_states = profile_extra.special_states
next_service_info = profile_extra.next_service_info
assist_mode_stats = profile_extra.assist_mode_stats
last_service = profile_extra.last_service
component_inventory = profile_extra.component_inventory
max_altitude = profile_extra.max_altitude

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


# ---------------------------------------------------------------------------
# Bike Pass — theft_status / frame_number
# ---------------------------------------------------------------------------

def test_theft_status_no_logs_key_is_none():
    assert theft_status(None) is None
    assert theft_status({}) is None
    assert theft_status({"bikePasses": []}) is None


def test_theft_status_empty_list_not_reported():
    assert theft_status({"theftReportLogs": []}) == {
        "reported": False, "since": None, "latitude": None,
        "longitude": None, "address": None, "detected_at": None}


def test_theft_status_with_location_reported_with_coords():
    bp = {"theftReportLogs": [{
        "createdAt": "2026-01-01T10:00:00Z",
        "theftCaseEnteredAt": "2026-01-01T09:30:00Z",
        "location": {"latitude": 52.4, "longitude": 13.3,
                     "address": "Berlin", "detectedAt": "2026-01-01T08:00:00Z",
                     "horizontalAccuracy": 15}}]}
    assert theft_status(bp) == {
        "reported": True, "since": "2026-01-01T09:30:00Z",
        "latitude": 52.4, "longitude": 13.3, "address": "Berlin",
        "detected_at": "2026-01-01T08:00:00Z"}


def test_theft_status_picks_most_recent_by_created_at():
    bp = {"theftReportLogs": [
        {"createdAt": "2026-01-01T10:00:00Z",
         "theftCaseEnteredAt": "2026-01-01T10:00:00Z",
         "location": {"latitude": 1.0, "longitude": 1.0}},
        {"createdAt": "2026-03-01T10:00:00Z",
         "theftCaseEnteredAt": "2026-03-01T10:00:00Z",
         "location": {"latitude": 9.0, "longitude": 9.0}},
    ]}
    out = theft_status(bp)
    assert out["reported"] is True
    assert out["since"] == "2026-03-01T10:00:00Z"
    assert out["latitude"] == 9.0


def test_theft_status_log_without_location_reported_but_no_coords():
    bp = {"theftReportLogs": [{
        "createdAt": "2026-01-01T10:00:00Z",
        "theftCaseEnteredAt": "2026-01-01T09:30:00Z"}]}
    assert theft_status(bp) == {
        "reported": True, "since": "2026-01-01T09:30:00Z",
        "latitude": None, "longitude": None,
        "address": None, "detected_at": None}


def test_theft_status_falls_back_to_created_at_when_no_entered_at():
    bp = {"theftReportLogs": [{"createdAt": "2026-01-01T10:00:00Z"}]}
    assert theft_status(bp)["since"] == "2026-01-01T10:00:00Z"


def test_theft_status_non_list_logs_degrades_to_not_reported():
    assert theft_status({"theftReportLogs": {"weird": "dict"}}) == {
        "reported": False, "since": None, "latitude": None,
        "longitude": None, "address": None, "detected_at": None}


def test_theft_status_list_with_non_dict_elements_not_reported():
    assert theft_status({"theftReportLogs": ["not-a-dict", 123]}) == {
        "reported": False, "since": None, "latitude": None,
        "longitude": None, "address": None, "detected_at": None}


def test_theft_status_logs_key_absent_still_none():
    assert theft_status({"bikePasses": [{"frameNumber": "X"}]}) is None


def test_frame_number_present_and_absent():
    assert frame_number({"bikePasses": [{"frameNumber": "WBK123"}]}) == "WBK123"
    assert frame_number({"bikePasses": []}) is None
    assert frame_number({}) is None
    assert frame_number(None) is None


# ---------------------------------------------------------------------------
# Service Book — battery_soh
# ---------------------------------------------------------------------------

def _battery_record(serial, created_at, soh):
    return {"id": serial + created_at, "type": "BATTERY_MEASUREMENT",
            "attributes": {"createdAt": created_at,
                "details": {"batteryMeasurement": {
                    "battery": {"serialNumber": serial, "partNumber": "PN",
                                "productName": "PowerTube"},
                    "measurement": {"fullChargeCycles": 100,
                        "measuredEnergyCapacity": 450,
                        "nominalEnergyCapacity": 500,
                        "measuredCapacityPercentage": soh,
                        "onBikeMeasurement": True}}}}}


def test_battery_soh_matching_serial_returns_fields():
    recs = {"serviceRecords": [_battery_record("ABC", "2026-01-01T00:00:00Z", 90)]}
    assert battery_soh(recs, "ABC") == {
        "soh_pct": 90, "measured_wh": 450, "nominal_wh": 500,
        "full_charge_cycles": 100, "measured_at": "2026-01-01T00:00:00Z"}


def test_battery_soh_non_matching_serial_is_none():
    recs = {"serviceRecords": [_battery_record("ABC", "2026-01-01T00:00:00Z", 90)]}
    assert battery_soh(recs, "XYZ") is None


def test_battery_soh_empty_or_none_is_none():
    assert battery_soh(None, "ABC") is None
    assert battery_soh({}, "ABC") is None
    assert battery_soh({"serviceRecords": []}, "ABC") is None


def test_battery_soh_newest_created_at_wins():
    recs = {"serviceRecords": [
        _battery_record("ABC", "2026-01-01T00:00:00Z", 90),
        _battery_record("ABC", "2026-05-01T00:00:00Z", 80),
    ]}
    assert battery_soh(recs, "ABC")["soh_pct"] == 80


# ---------------------------------------------------------------------------
# Service Book — customer report based functions
# ---------------------------------------------------------------------------

def _customer_record(created_at, components, next_service=None):
    cr = {"bike": {"components": components}}
    if next_service is not None:
        cr["nextServiceInformation"] = next_service
    return {"id": created_at, "type": "CUSTOMER_REPORT",
            "attributes": {"createdAt": created_at,
                "details": {"customerReport": cr}}}


def test_software_update_available_any_true():
    recs = {"serviceRecords": [_customer_record("2026-01-01T00:00:00Z", [
        {"softwareUpdateAvailable": False}, {"softwareUpdateAvailable": True}])]}
    assert software_update_available(recs) is True


def test_software_update_available_none_true_is_false():
    recs = {"serviceRecords": [_customer_record("2026-01-01T00:00:00Z", [
        {"softwareUpdateAvailable": False}, {"softwareUpdateAvailable": False}])]}
    assert software_update_available(recs) is False


def test_software_update_available_no_report_is_none():
    assert software_update_available(None) is None
    assert software_update_available({}) is None
    assert software_update_available({"serviceRecords": []}) is None
    assert software_update_available({"serviceRecords": [
        _battery_record("ABC", "2026-01-01T00:00:00Z", 90)]}) is None


def test_software_update_available_uses_newest_report():
    recs = {"serviceRecords": [
        _customer_record("2026-01-01T00:00:00Z", [{"softwareUpdateAvailable": True}]),
        _customer_record("2026-05-01T00:00:00Z", [{"softwareUpdateAvailable": False}]),
    ]}
    assert software_update_available(recs) is False


def test_special_states_distinct_excluding_none():
    recs = {"serviceRecords": [_customer_record("2026-01-01T00:00:00Z", [
        {"highestSpecialState": "NONE"},
        {"highestSpecialState": "STOLEN"},
        {"highestSpecialState": "LOCKED"},
        {"highestSpecialState": "STOLEN"},
    ])]}
    assert special_states(recs) == ["STOLEN", "LOCKED"]


def test_special_states_no_report_is_empty():
    assert special_states(None) == []
    assert special_states({}) == []
    assert special_states({"serviceRecords": []}) == []
    assert special_states({"serviceRecords": [_customer_record(
        "2026-01-01T00:00:00Z", [{"highestSpecialState": "NONE"}])]}) == []


def test_next_service_info_present():
    recs = {"serviceRecords": [_customer_record("2026-01-01T00:00:00Z", [],
        next_service={"daysNextService": 30, "metersNextService": 500000,
                      "updatedAt": "2026-01-01T00:00:00Z"})]}
    assert next_service_info(recs) == {
        "days": 30, "meters": 500000, "updated_at": "2026-01-01T00:00:00Z"}


def test_next_service_info_absent():
    assert next_service_info(None) is None
    assert next_service_info({}) is None
    assert next_service_info({"serviceRecords": []}) is None
    assert next_service_info({"serviceRecords": [_customer_record(
        "2026-01-01T00:00:00Z", [])]}) is None


# ---------------------------------------------------------------------------
# Tier-3 — assist_mode_stats
# ---------------------------------------------------------------------------

def _customer_report_with_chart(created_at, chart_data):
    return {"id": created_at, "type": "CUSTOMER_REPORT",
            "attributes": {"createdAt": created_at,
                "details": {"customerReport": {
                    "statistics": {"chartData": chart_data}}}}}


def test_assist_mode_stats_two_modes():
    recs = {"serviceRecords": [_customer_report_with_chart(
        "2026-01-01T00:00:00Z", [
            {"distanceValue": 60000, "energyValue": 500, "displayName": "Eco"},
            {"distanceValue": 30000, "energyValue": 800, "displayName": "Turbo"},
        ])]}
    assert assist_mode_stats(recs) == [
        {"name": "Eco", "distance_km": 60.0, "energy_wh": 500},
        {"name": "Turbo", "distance_km": 30.0, "energy_wh": 800},
    ]


def test_assist_mode_stats_skips_missing_display_name_and_non_dict():
    recs = {"serviceRecords": [_customer_report_with_chart(
        "2026-01-01T00:00:00Z", [
            {"distanceValue": 60000, "energyValue": 500, "displayName": "Eco"},
            {"distanceValue": 10000, "energyValue": 100},
            "not-a-dict",
        ])]}
    assert assist_mode_stats(recs) == [
        {"name": "Eco", "distance_km": 60.0, "energy_wh": 500}]


def test_assist_mode_stats_no_report_is_empty():
    assert assist_mode_stats(None) == []
    assert assist_mode_stats({}) == []
    assert assist_mode_stats({"serviceRecords": []}) == []
    assert assist_mode_stats({"serviceRecords": [_customer_report_with_chart(
        "2026-01-01T00:00:00Z", [])]}) == []


def test_assist_mode_stats_non_numeric_distance_is_none():
    recs = {"serviceRecords": [_customer_report_with_chart(
        "2026-01-01T00:00:00Z", [
            {"distanceValue": "oops", "energyValue": 100,
             "displayName": "Eco"},
        ])]}
    assert assist_mode_stats(recs) == [
        {"name": "Eco", "distance_km": None, "energy_wh": 100}]


# ---------------------------------------------------------------------------
# Tier-3 — last_service
# ---------------------------------------------------------------------------

def _service_record(created_at, dealer="Bike Shop", odometer=2000000,
                    rec_type="MAINTENANCE"):
    attrs = {"createdAt": created_at, "bikeDealer": {"name": dealer}}
    if odometer is not None:
        attrs["odometerValue"] = odometer
    return {"id": created_at, "type": rec_type, "attributes": attrs}


def test_last_service_newest_wins_with_fields():
    recs = {"serviceRecords": [
        _service_record("2026-01-01T00:00:00Z", "Old Shop", 1000000),
        _service_record("2026-05-01T00:00:00Z", "New Shop", 2500000,
                        rec_type="CUSTOMER_REPORT"),
    ]}
    assert last_service(recs) == {
        "date": "2026-05-01T00:00:00Z", "dealer": "New Shop",
        "odometer_km": 2500.0}


def test_last_service_missing_odometer_is_none():
    recs = {"serviceRecords": [
        _service_record("2026-01-01T00:00:00Z", "Shop", odometer=None)]}
    assert last_service(recs) == {
        "date": "2026-01-01T00:00:00Z", "dealer": "Shop",
        "odometer_km": None}


def test_last_service_empty_is_none():
    assert last_service(None) is None
    assert last_service({}) is None
    assert last_service({"serviceRecords": []}) is None


# ---------------------------------------------------------------------------
# Tier-3 — component_inventory
# ---------------------------------------------------------------------------

def test_component_inventory_full_bike():
    bike = {
        "headUnit": {"productName": "Kiox 300"},
        "remoteControl": {"productName": "LED Remote"},
        "connectModule": {"productName": "ConnectModule"},
        "antiLockBrakeSystems": [{"productName": "ABS"}],
    }
    assert component_inventory(bike) == {
        "head_unit": "Kiox 300", "remote_control": "LED Remote",
        "connect_module": "ConnectModule", "has_abs": True}


def test_component_inventory_no_abs():
    assert component_inventory({"antiLockBrakeSystems": []}) == {
        "head_unit": None, "remote_control": None,
        "connect_module": None, "has_abs": False}


def test_component_inventory_missing_components():
    assert component_inventory({"headUnit": {"productName": "Kiox"}}) == {
        "head_unit": "Kiox", "remote_control": None,
        "connect_module": None, "has_abs": False}


def test_component_inventory_empty_dict():
    assert component_inventory({}) == {
        "head_unit": None, "remote_control": None,
        "connect_module": None, "has_abs": False}


# ---------------------------------------------------------------------------
# Tier-3 — max_altitude
# ---------------------------------------------------------------------------

def test_max_altitude_list_of_points():
    assert max_altitude([
        {"altitude": 100.2}, {"altitude": 350.7}, {"altitude": 80}]) == 350.7


def test_max_altitude_dict_wrapper():
    assert max_altitude({"activityDetails": [
        {"altitude": 100}, {"altitude": 250.55}]}) == 250.6


def test_max_altitude_skips_non_numeric_and_missing():
    assert max_altitude([
        {"altitude": "high"}, {"foo": "bar"}, {"altitude": 42}]) == 42.0


def test_max_altitude_empty_or_none_is_none():
    assert max_altitude(None) is None
    assert max_altitude([]) is None
    assert max_altitude({"activityDetails": []}) is None
    assert max_altitude([{"altitude": "x"}, {"foo": 1}]) is None


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("ALL TESTS PASSED")
