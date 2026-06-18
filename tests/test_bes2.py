"""Standalone tests for bes2.py — run with: python3 tests/test_bes2.py

Loads the module file directly via importlib (like test_profile_extra.py /
test_brouter.py): importing the package would pull in
custom_components/ha_bosch_ebike/__init__.py, which needs Home Assistant.
"""
import importlib.util
from pathlib import Path

_path = (
    Path(__file__).resolve().parent.parent
    / "custom_components" / "ha_bosch_ebike" / "bes2.py"
)
_spec = importlib.util.spec_from_file_location("bes2", _path)
bes2 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bes2)

normalize_bike = bes2.normalize_bike
normalize_activity_summary = bes2.normalize_activity_summary
enrich_summary_from_detail = bes2.enrich_summary_from_detail
normalize_track = bes2.normalize_track
normalize_statistics = bes2.normalize_statistics


# ---------------------------------------------------------------------------
# normalize_bike
# ---------------------------------------------------------------------------

def test_normalize_bike_full():
    b2 = {
        "driveUnit": {
            "serialNumber": "SER", "partNumber": "PART",
            "type": "DRIVE_UNIT", "deviceName": "Performance Line CX",
            "productLineName": "Performance CX", "bikeManufacturer": "Cube",
        },
        "headUnits": [
            {"serialNumber": "HU1", "partNumber": "HUP1",
             "deviceName": "Kiox 300", "deviceLineName": "Kiox",
             "mapVersion": "2024"},
        ],
        "batteries": [
            {"serialNumber": "B1", "partNumber": "BP1",
             "type": "BATTERY", "deviceName": "PowerTube 625"},
            {"serialNumber": "B2", "partNumber": "BP2",
             "type": "BATTERY", "deviceName": "PowerTube 500"},
        ],
    }
    out = normalize_bike(b2)
    assert out["id"] == "SER-PART"
    assert out["driveUnit"]["productName"] == "Performance CX"
    assert out["driveUnit"]["serialNumber"] == "SER"
    assert out["driveUnit"]["partNumber"] == "PART"
    assert out["batteries"] == [
        {"productName": "PowerTube 625", "serialNumber": "B1", "partNumber": "BP1"},
        {"productName": "PowerTube 500", "serialNumber": "B2", "partNumber": "BP2"},
    ]
    assert out["headUnit"] == {"productName": "Kiox 300"}
    assert out["_bes2_serial"] == "SER"
    assert out["_bes2_part"] == "PART"


def test_normalize_bike_productname_falls_back_to_devicename():
    b2 = {"driveUnit": {"serialNumber": "S", "partNumber": "P",
                        "deviceName": "Performance Line CX"}}
    out = normalize_bike(b2)
    assert out["driveUnit"]["productName"] == "Performance Line CX"


def test_normalize_bike_headunit_falls_back_to_devicelinename():
    b2 = {"driveUnit": {"serialNumber": "S", "partNumber": "P"},
          "headUnits": [{"deviceLineName": "Kiox"}]}
    assert normalize_bike(b2)["headUnit"] == {"productName": "Kiox"}


def test_normalize_bike_missing_driveunit_safe_id():
    out = normalize_bike({})
    assert out["id"] == "bes2"
    assert out["driveUnit"]["productName"] is None
    assert out["driveUnit"]["serialNumber"] is None
    assert out["batteries"] == []
    assert "headUnit" not in out
    assert out["_bes2_serial"] is None
    assert out["_bes2_part"] is None


def test_normalize_bike_only_serial_id():
    out = normalize_bike({"driveUnit": {"serialNumber": "SER"}})
    assert out["id"] == "SER-"


def test_normalize_bike_no_headunits_absent():
    out = normalize_bike({"driveUnit": {"serialNumber": "S", "partNumber": "P"},
                          "headUnits": []})
    assert "headUnit" not in out


def test_normalize_bike_non_dict_battery_skipped():
    b2 = {"driveUnit": {"serialNumber": "S", "partNumber": "P"},
          "batteries": [{"serialNumber": "B1", "deviceName": "PT"}, "junk", None]}
    out = normalize_bike(b2)
    assert out["batteries"] == [
        {"productName": "PT", "serialNumber": "B1", "partNumber": None}]


def test_normalize_bike_none_input_no_raise():
    out = normalize_bike(None)
    assert out["id"] == "bes2"
    assert out["batteries"] == []


# ---------------------------------------------------------------------------
# normalize_activity_summary
# ---------------------------------------------------------------------------

def test_normalize_activity_summary_full():
    a2 = {
        "id": 1234567890123,
        "type": "TRIP",
        "startTime": "2026-01-01T10:00:00Z",
        "endTime": "2026-01-01T11:00:00Z",
        "durationWithoutStops": 3600000,
        "isCompleted": True,
        "totalDistance": 12345.6,
        "title": "Morning ride",
        "bikeRides": [
            {"type": "BIKE_RIDE", "caloriesBurned": 100.0,
             "avgSpeed": 20.0, "maxSpeed": 30.0},
            {"type": "BIKE_RIDE", "caloriesBurned": 50.0,
             "avgSpeed": 10.0, "maxSpeed": 25.0},
        ],
    }
    out = normalize_activity_summary(a2)
    assert out["id"] == "1234567890123"
    assert out["distance"] == 12346
    assert out["durationWithoutStops"] == 3600
    assert out["startTime"] == "2026-01-01T10:00:00Z"
    assert out["endTime"] == "2026-01-01T11:00:00Z"
    assert out["title"] == "Morning ride"
    assert out["speed"] == {"average": 15.0, "maximum": 30.0}
    assert out["caloriesBurned"] == 150.0
    assert out["cadence"] == {}
    assert out["riderPower"] == {}
    assert out["elevation"] == {}


def test_normalize_activity_summary_no_bikerides_averages_none():
    a2 = {"id": 5, "totalDistance": 100.0, "durationWithoutStops": 1000}
    out = normalize_activity_summary(a2)
    assert out["id"] == "5"
    assert out["distance"] == 100
    assert out["durationWithoutStops"] == 1
    assert out["speed"] == {"average": None, "maximum": None}
    assert out["caloriesBurned"] is None


def test_normalize_activity_summary_empty_safe():
    out = normalize_activity_summary({})
    assert out["id"] is None
    assert out["distance"] is None
    assert out["durationWithoutStops"] is None
    assert out["speed"] == {"average": None, "maximum": None}
    assert out["caloriesBurned"] is None
    assert out["cadence"] == {}
    assert out["riderPower"] == {}
    assert out["elevation"] == {}


def test_normalize_activity_summary_none_input_safe():
    out = normalize_activity_summary(None)
    assert out["id"] is None
    assert out["distance"] is None


def test_normalize_activity_summary_non_numeric_distance_none():
    out = normalize_activity_summary({"totalDistance": "x", "durationWithoutStops": "y"})
    assert out["distance"] is None
    assert out["durationWithoutStops"] is None


def test_normalize_activity_summary_bool_not_numeric():
    out = normalize_activity_summary(
        {"totalDistance": True, "bikeRides": [{"avgSpeed": True, "maxSpeed": True}]})
    assert out["distance"] is None
    assert out["speed"] == {"average": None, "maximum": None}


def test_normalize_activity_summary_partial_speeds():
    # only one ride has avgSpeed
    a2 = {"bikeRides": [{"avgSpeed": 20.0, "maxSpeed": 30.0}, {"caloriesBurned": 5.0}]}
    out = normalize_activity_summary(a2)
    assert out["speed"] == {"average": 20.0, "maximum": 30.0}
    assert out["caloriesBurned"] == 5.0


# ---------------------------------------------------------------------------
# enrich_summary_from_detail
# ---------------------------------------------------------------------------

def _base_summary():
    return {
        "speed": {"average": None, "maximum": None},
        "cadence": {}, "riderPower": {}, "elevation": {},
        "caloriesBurned": None,
    }


def test_enrich_fills_cadence_power_elevation():
    s = _base_summary()
    detail = {"avgCadence": 70, "maxCadence": 110, "avgRiderPower": 150,
              "elevationGain": 200.0, "elevationLoss": 180.0}
    out = enrich_summary_from_detail(s, detail)
    assert out["cadence"] == {"average": 70, "maximum": 110}
    assert out["riderPower"]["average"] == 150
    assert out["elevation"] == {"gain": 200.0, "loss": 180.0}


def test_enrich_fills_speed_and_calories_when_none():
    s = _base_summary()
    detail = {"avgSpeed": 18.0, "maxSpeed": 33.0, "caloriesBurned": 99.0}
    out = enrich_summary_from_detail(s, detail)
    assert out["speed"] == {"average": 18.0, "maximum": 33.0}
    assert out["caloriesBurned"] == 99.0


def test_enrich_leaves_existing_speed_maximum():
    s = _base_summary()
    s["speed"]["maximum"] = 40.0
    s["speed"]["average"] = 22.0
    s["caloriesBurned"] = 150.0
    detail = {"avgSpeed": 18.0, "maxSpeed": 33.0, "caloriesBurned": 99.0}
    out = enrich_summary_from_detail(s, detail)
    assert out["speed"] == {"average": 22.0, "maximum": 40.0}
    assert out["caloriesBurned"] == 150.0


def test_enrich_empty_detail_unchanged():
    s = _base_summary()
    out = enrich_summary_from_detail(s, {})
    assert out["cadence"] == {}
    assert out["riderPower"] == {}
    assert out["elevation"] == {}
    assert out["speed"] == {"average": None, "maximum": None}


def test_enrich_none_detail_unchanged_no_raise():
    s = _base_summary()
    out = enrich_summary_from_detail(s, None)
    assert out["cadence"] == {}


def test_enrich_non_numeric_detail_ignored():
    s = _base_summary()
    detail = {"avgCadence": "x", "maxCadence": True, "avgRiderPower": None,
              "elevationGain": "y"}
    out = enrich_summary_from_detail(s, detail)
    assert out["cadence"] == {}
    assert out["riderPower"] == {}
    assert out["elevation"] == {}


# ---------------------------------------------------------------------------
# normalize_track
# ---------------------------------------------------------------------------

def test_normalize_track_two_rides_zipped():
    detail = {
        "coordinates": [
            [{"latitude": 1.0, "longitude": 2.0}, {"latitude": 1.1, "longitude": 2.1}],
            [{"latitude": 3.0, "longitude": 4.0}, {"latitude": 3.1, "longitude": 4.1}],
        ],
        "altitudes": [[100.0, 110.0], [200.0, 210.0]],
        "speed": [[5.0, 6.0], [7.0, 8.0]],
    }
    out = normalize_track(detail)
    assert out["activityDetails"] == [
        {"latitude": 1.0, "longitude": 2.0, "altitude": 100.0, "speed": 5.0},
        {"latitude": 1.1, "longitude": 2.1, "altitude": 110.0, "speed": 6.0},
        {"latitude": 3.0, "longitude": 4.0, "altitude": 200.0, "speed": 7.0},
        {"latitude": 3.1, "longitude": 4.1, "altitude": 210.0, "speed": 8.0},
    ]


def test_normalize_track_coords_one_ride_alts_two_rides_global_align():
    # Real BES2 shape: coordinates merged into a single ride, altitudes/speed
    # split into two rides. Per-ride zipping would leave the tail without
    # altitude/speed; the global-index walk fills all points.
    detail = {
        "coordinates": [[
            {"latitude": 1.0, "longitude": 2.0},
            {"latitude": 1.1, "longitude": 2.1},
            {"latitude": 1.2, "longitude": 2.2},
        ]],
        "altitudes": [[100.0, 110.0], [120.0]],
        "speed": [[5.0, 6.0], [7.0]],
    }
    out = normalize_track(detail)
    assert out["activityDetails"] == [
        {"latitude": 1.0, "longitude": 2.0, "altitude": 100.0, "speed": 5.0},
        {"latitude": 1.1, "longitude": 2.1, "altitude": 110.0, "speed": 6.0},
        {"latitude": 1.2, "longitude": 2.2, "altitude": 120.0, "speed": 7.0},
    ]


def test_normalize_track_null_point_skipped():
    detail = {
        "coordinates": [[{"latitude": 1.0, "longitude": 2.0}, None,
                         {"latitude": 1.2, "longitude": 2.2}]],
        "altitudes": [[100.0, 110.0, 120.0]],
        "speed": [[5.0, 6.0, 7.0]],
    }
    out = normalize_track(detail)
    assert out["activityDetails"] == [
        {"latitude": 1.0, "longitude": 2.0, "altitude": 100.0, "speed": 5.0},
        {"latitude": 1.2, "longitude": 2.2, "altitude": 120.0, "speed": 7.0},
    ]


def test_normalize_track_point_missing_latlon_skipped():
    detail = {"coordinates": [[{"latitude": 1.0}, {"longitude": 2.0},
                               {"latitude": 1.0, "longitude": 2.0}]]}
    out = normalize_track(detail)
    assert out["activityDetails"] == [
        {"latitude": 1.0, "longitude": 2.0, "altitude": None, "speed": None}]


def test_normalize_track_altitudes_shorter_no_indexerror():
    detail = {
        "coordinates": [[{"latitude": 1.0, "longitude": 2.0},
                         {"latitude": 1.1, "longitude": 2.1}]],
        "altitudes": [[100.0]],
        "speed": [[5.0, 6.0]],
    }
    out = normalize_track(detail)
    assert out["activityDetails"] == [
        {"latitude": 1.0, "longitude": 2.0, "altitude": 100.0, "speed": 5.0},
        {"latitude": 1.1, "longitude": 2.1, "altitude": None, "speed": 6.0},
    ]


def test_normalize_track_missing_speed_array_speed_none():
    detail = {
        "coordinates": [[{"latitude": 1.0, "longitude": 2.0}]],
        "altitudes": [[100.0]],
    }
    out = normalize_track(detail)
    assert out["activityDetails"] == [
        {"latitude": 1.0, "longitude": 2.0, "altitude": 100.0, "speed": None}]


def test_normalize_track_non_numeric_alt_speed_none():
    detail = {
        "coordinates": [[{"latitude": 1.0, "longitude": 2.0}]],
        "altitudes": [["x"]],
        "speed": [[True]],
    }
    out = normalize_track(detail)
    assert out["activityDetails"] == [
        {"latitude": 1.0, "longitude": 2.0, "altitude": None, "speed": None}]


def test_normalize_track_no_coordinates_empty():
    assert normalize_track({}) == {"activityDetails": []}
    assert normalize_track(None) == {"activityDetails": []}
    assert normalize_track({"coordinates": []}) == {"activityDetails": []}


def test_normalize_track_ride_not_list_skipped():
    detail = {"coordinates": ["junk", [{"latitude": 1.0, "longitude": 2.0}]]}
    out = normalize_track(detail)
    assert out["activityDetails"] == [
        {"latitude": 1.0, "longitude": 2.0, "altitude": None, "speed": None}]


def test_normalize_statistics_totals():
    raw = {
        "totalStatistics": {
            "distance": 1234567,
            "elevationGain": 3518,
            "yearlyDistance": 50000.5,
        },
        "bestMonth": 11,
    }
    assert normalize_statistics(raw) == {
        "total_distance_m": 1234567,
        "total_elevation_gain_m": 3518,
        "yearly_distance_m": 50000.5,
    }


def test_normalize_statistics_partial_and_non_numeric():
    raw = {"totalStatistics": {"distance": 1000, "elevationGain": "x"}}
    assert normalize_statistics(raw) == {"total_distance_m": 1000}


def test_normalize_statistics_empty_and_non_dict():
    assert normalize_statistics({}) == {}
    assert normalize_statistics({"totalStatistics": {}}) == {}
    assert normalize_statistics(None) == {}
    assert normalize_statistics([1, 2]) == {}


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("ALL TESTS PASSED")
