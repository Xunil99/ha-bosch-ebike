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
normalize_trip_activities = bes2.normalize_trip_activities
normalize_ride_track = bes2.normalize_ride_track
track_for_activity = bes2.track_for_activity
trip_id_of = bes2.trip_id_of


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


def test_enrich_rounds_noisy_detail_values():
    # BES2-Detailwerte kommen teils mit vielen Nachkommastellen (Issue Habanatz).
    # Anzeige-Rundung: Trittfrequenz/Leistung/Hoehe ganzzahlig, Speed 1 Stelle.
    s = _base_summary()
    detail = {
        "avgCadence": 62.345678, "maxCadence": 109.9,
        "avgRiderPower": 148.6,
        "elevationGain": 123.456789, "elevationLoss": 98.7654,
        "avgSpeed": 22.456, "maxSpeed": 41.249,
    }
    out = enrich_summary_from_detail(s, detail)
    assert out["cadence"] == {"average": 62, "maximum": 110}
    assert out["riderPower"]["average"] == 149
    assert out["elevation"] == {"gain": 123, "loss": 99}
    assert out["speed"] == {"average": 22.5, "maximum": 41.2}


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


# ---------------------------------------------------------------------------
# normalize_activity_summary - trip title (forum report: Joesy/Joachim)
# ---------------------------------------------------------------------------

def test_activity_summary_title_comes_from_first_bike_ride():
    # The real shape, confirmed via diagnostics against Joesy/Joachim's
    # account: the TRIP object itself has no "title" key at all, the name
    # lives on the first bikeRides entry instead.
    a2 = {
        "id": 1,
        "startTime": "2026-01-01T10:00:00Z",
        "bikeRides": [
            {"type": "BIKE_RIDE", "title": "Feierabendrunde", "avgSpeed": 20.0},
        ],
    }
    out = normalize_activity_summary(a2)
    assert out["title"] == "Feierabendrunde"


def test_activity_summary_title_falls_back_to_trip_level_key():
    # Belt and braces: if some other BES2 shape does carry a trip-level
    # title, still use it.
    a2 = {"id": 1, "title": "Trip Level Name", "bikeRides": []}
    out = normalize_activity_summary(a2)
    assert out["title"] == "Trip Level Name"


def test_activity_summary_title_prefers_bike_ride_over_trip_level():
    a2 = {
        "id": 1,
        "title": "Stale Trip Name",
        "bikeRides": [{"type": "BIKE_RIDE", "title": "Actual Ride Name"}],
    }
    out = normalize_activity_summary(a2)
    assert out["title"] == "Actual Ride Name"


def test_activity_summary_title_none_when_nowhere_to_be_found():
    a2 = {"id": 1, "bikeRides": [{"type": "BIKE_RIDE"}]}
    out = normalize_activity_summary(a2)
    assert out["title"] is None


def test_activity_summary_title_ignores_empty_bike_ride_title():
    a2 = {
        "id": 1,
        "title": "Fallback Name",
        "bikeRides": [{"type": "BIKE_RIDE", "title": ""}],
    }
    out = normalize_activity_summary(a2)
    assert out["title"] == "Fallback Name"


def test_activity_summary_title_no_bike_rides_no_raise():
    assert normalize_activity_summary({"id": 1})["title"] is None
    assert normalize_activity_summary({"id": 1, "bikeRides": None})["title"] is None


# ---------------------------------------------------------------------------
# normalize_trip_activities — a BES2 TRIP holds several rides (issue #88)
# ---------------------------------------------------------------------------

TRIP_ID = 17659821156
R1 = "2026-09-23T11:59:48Z"
R2 = "2026-10-04T16:40:10Z"
R3 = "2026-10-05T16:49:29Z"


def _ride(start, dist_m, dur_ms=60000, **extra):
    r = {
        "type": "BIKE_RIDE", "startTime": start, "endTime": start,
        "totalDistance": float(dist_m), "durationWithoutStops": float(dur_ms),
        "avgSpeed": 15.04, "maxSpeed": 25.06, "caloriesBurned": 10.0,
    }
    r.update(extra)
    return r


def _trip(rides, trip_id=TRIP_ID, **extra):
    t = {
        "id": trip_id, "type": "TRIP", "isCompleted": False,
        "startTime": rides[0]["startTime"] if rides else None,
        "endTime": rides[-1]["endTime"] if rides else None,
        "totalDistance": float(sum(r["totalDistance"] for r in rides)),
        "durationWithoutStops": float(sum(r["durationWithoutStops"] for r in rides)),
        "bikeRides": rides,
    }
    t.update(extra)
    return t


def test_trip_with_one_ride_stays_one_unchanged_activity():
    # The common case (closed single-ride trip) must not change at all.
    trip = _trip([_ride(R1, 5000, 900000)])
    out = normalize_trip_activities(trip)
    assert out == [normalize_activity_summary(trip)]
    assert out[0]["id"] == str(TRIP_ID)


def test_trip_without_bike_rides_stays_one_activity():
    for rides in (None, [], "garbage"):
        trip = {"id": 7, "totalDistance": 1234.0, "bikeRides": rides}
        out = normalize_trip_activities(trip)
        assert out == [normalize_activity_summary(trip)]
    assert normalize_trip_activities({"id": 7})[0]["id"] == "7"


def test_trip_with_several_rides_becomes_one_activity_per_ride():
    trip = _trip([
        _ride(R1, 30000, 7_000_000, title="Hausrunde"),
        _ride(R2, 19389, 4_295_000),
        _ride(R3, 406, 113_000, endTime="2026-10-05T16:51:22Z"),
    ], title="Trip Name")
    out = normalize_trip_activities(trip)
    assert [a["id"] for a in out] == [
        str(TRIP_ID),
        f"{TRIP_ID}-20261004164010",
        f"{TRIP_ID}-20261005164929",
    ]
    assert [a["distance"] for a in out] == [30000, 19389, 406]
    assert [a["durationWithoutStops"] for a in out] == [7000, 4295, 113]
    assert sum(a["distance"] for a in out) == 49795  # == the trip total
    assert out[2]["startTime"] == R3 and out[2]["endTime"] == "2026-10-05T16:51:22Z"
    assert out[0]["title"] == "Hausrunde"
    assert out[1]["title"] == "Trip Name"  # ride without its own title -> trip-level
    assert out[2]["speed"] == {"average": 15.0, "maximum": 25.1}
    assert out[2]["caloriesBurned"] == 10.0
    # trip-level aggregates must NOT be passed off as one ride's values
    assert out[2]["cadence"] == {} and out[2]["riderPower"] == {} and out[2]["elevation"] == {}
    for a in out:
        assert a["_bes2_trip_id"] == str(TRIP_ID)
        assert a["_bes2_ride_count"] == 3
    assert [a["_bes2_primary"] for a in out] == [True, False, False]


def test_rides_come_out_oldest_first_even_when_listed_newest_first():
    trip = _trip([_ride(R3, 406), _ride(R2, 19389), _ride(R1, 30000)])
    out = normalize_trip_activities(trip)
    assert [a["startTime"] for a in out] == [R1, R2, R3]
    assert out[0]["id"] == str(TRIP_ID)
    assert [a["_bes2_ride_pos"] for a in out] == [2, 1, 0]  # position in the API array
    assert all(a["_bes2_order_ok"] is False for a in out)


def test_chronological_bike_rides_are_flagged_order_ok():
    out = normalize_trip_activities(_trip([_ride(R1, 1000), _ride(R2, 2000)]))
    assert all(a["_bes2_order_ok"] is True for a in out)
    assert [a["_bes2_ride_pos"] for a in out] == [0, 1]


def test_issue_88_new_ride_in_open_trip_is_a_new_activity():
    # Reporter's numbers: trip totals 49389 m / 11295 s, then +406 m / +113 s.
    r1 = _ride(R1, 30000, 7_000_000)
    r2 = _ride(R2, 19389, 4_295_000, endTime="2026-10-04T16:55:55Z")
    r3 = _ride(R3, 406, 113_000, endTime="2026-10-05T16:51:22Z")
    before = normalize_trip_activities(_trip([r1, r2]))
    after = normalize_trip_activities(_trip([r1, r2, r3]))
    ids_before = {a["id"] for a in before}
    ids_after = {a["id"] for a in after}
    assert ids_before < ids_after
    assert ids_after - ids_before == {f"{TRIP_ID}-20261005164929"}  # exactly one event
    newest = max(after, key=lambda a: a["startTime"])
    assert newest["distance"] == 406 and newest["durationWithoutStops"] == 113
    assert newest["endTime"] == "2026-10-05T16:51:22Z"


def test_single_ride_trip_growing_to_two_rides_keeps_its_first_id():
    one = normalize_trip_activities(_trip([_ride(R1, 5000)]))
    two = normalize_trip_activities(_trip([_ride(R1, 5000), _ride(R2, 800)]))
    assert [a["id"] for a in one] == [str(TRIP_ID)]
    assert {a["id"] for a in two} - {a["id"] for a in one} == {f"{TRIP_ID}-20261004164010"}
    assert str(TRIP_ID) in {a["id"] for a in two}


def test_ride_inserted_in_the_middle_does_not_shift_other_ids():
    # A delayed sync can add an older ride after newer ones. Ids come from the
    # ride's own start time, not its position, so only the new ride is new.
    a, c = _ride(R1, 1000), _ride(R3, 3000)
    b = _ride(R2, 2000)
    before = {x["id"] for x in normalize_trip_activities(_trip([a, c]))}
    after = {x["id"] for x in normalize_trip_activities(_trip([a, b, c]))}
    assert after - before == {f"{TRIP_ID}-20261004164010"}
    assert before < after


def test_split_falls_back_to_the_trip_when_a_ride_lacks_start_or_distance():
    no_start = _trip([_ride(R1, 1000), _ride(R2, 2000)])
    del no_start["bikeRides"][1]["startTime"]
    no_dist = _trip([_ride(R1, 1000), _ride(R2, 2000)])
    no_dist["bikeRides"][0]["totalDistance"] = None
    for trip in (no_start, no_dist):
        assert normalize_trip_activities(trip) == [normalize_activity_summary(trip)]


def test_split_falls_back_when_ride_distances_do_not_add_up_to_the_trip_total():
    # e.g. the ride entries turn out to be in km although documented as metres
    trip = _trip([_ride(R1, 10.0), _ride(R2, 20.0)], totalDistance=30000.0)
    assert normalize_trip_activities(trip) == [normalize_activity_summary(trip)]


def test_rides_sharing_a_start_time_still_get_unique_ids():
    out = normalize_trip_activities(_trip([_ride(R1, 1000), _ride(R2, 1000), _ride(R2, 1000)]))
    ids = [a["id"] for a in out]
    assert len(set(ids)) == 3


def test_trip_activities_never_raise_on_garbage():
    for bad in (None, {}, {"id": 1, "bikeRides": "x"},
                {"id": 1, "bikeRides": [None, 3, "a"]},
                {"id": 1, "bikeRides": [{}, {}]},
                {"id": 1, "bikeRides": [{"startTime": 5, "totalDistance": 1}] * 2}):
        out = normalize_trip_activities(bad)
        assert isinstance(out, list) and len(out) >= 1


def test_trip_id_of():
    assert trip_id_of("17659821156") == "17659821156"
    assert trip_id_of(17659821156) == "17659821156"
    assert trip_id_of("17659821156-20261005164929") == "17659821156"
    assert trip_id_of(None) is None
    assert trip_id_of("") is None


# ---------------------------------------------------------------------------
# Per-ride track slicing
# ---------------------------------------------------------------------------

def _pt(lat):
    return {"latitude": lat, "longitude": lat + 100.0}


def _detail(groups=None, alts=None, speeds=None):
    groups = groups if groups is not None else [[_pt(1), _pt(2), _pt(3)], [_pt(4), _pt(5)]]
    return {
        "coordinates": groups,
        "altitudes": alts if alts is not None else [[10, 11, 12], [20, 21]],
        "speed": speeds if speeds is not None else [[1, 2, 3], [4, 5]],
    }


def test_ride_track_isolates_one_ride():
    first = normalize_ride_track(_detail(), 0, 2)["activityDetails"]
    second = normalize_ride_track(_detail(), 1, 2)["activityDetails"]
    assert [p["latitude"] for p in first] == [1, 2, 3]
    assert [p["latitude"] for p in second] == [4, 5]
    assert [p["altitude"] for p in second] == [20, 21]
    assert [p["speed"] for p in second] == [4, 5]


def test_ride_track_altitude_lookup_survives_different_array_grouping():
    # altitudes merged into one group while coordinates are per ride: the
    # lookup is by global point index, so the second ride still gets 20/21.
    d = _detail(alts=[[10, 11, 12, 20, 21]], speeds=[[1, 2, 3, 4, 5]])
    second = normalize_ride_track(d, 1, 2)["activityDetails"]
    assert [p["altitude"] for p in second] == [20, 21]
    assert [p["speed"] for p in second] == [4, 5]


def test_ride_track_none_when_coordinate_groups_do_not_match_ride_count():
    merged = _detail(groups=[[_pt(1), _pt(2), _pt(3), _pt(4), _pt(5)]])
    assert normalize_ride_track(merged, 0, 2) is None
    assert normalize_ride_track(_detail(groups=[]), 0, 2) is None


def test_ride_track_none_for_unusable_arguments():
    d = _detail()
    assert normalize_ride_track(None, 0, 2) is None
    assert normalize_ride_track(d, 2, 2) is None   # position out of range
    assert normalize_ride_track(d, -1, 2) is None
    assert normalize_ride_track(d, 0, 1) is None   # not a multi-ride trip
    assert normalize_ride_track(d, "0", 2) is None


def test_ride_track_does_not_change_the_whole_trip_normalizer():
    whole = normalize_track(_detail())["activityDetails"]
    assert [p["latitude"] for p in whole] == [1, 2, 3, 4, 5]


def _split_meta(**over):
    meta = {"_bes2_ride_count": 2, "_bes2_ride_pos": 1, "_bes2_order_ok": True}
    meta.update(over)
    return meta


def test_track_for_activity_scope():
    d = _detail()
    track, scope = track_for_activity(d, _split_meta())
    assert scope == "ride"
    assert [p["latitude"] for p in track["activityDetails"]] == [4, 5]
    # unsplit trip, unknown activity -> whole trip
    for act in ({"id": "1"}, None):
        track, scope = track_for_activity(d, act)
        assert scope == "trip"
        assert len(track["activityDetails"]) == 5
    # bikeRides not chronological: the detail's group order cannot be trusted
    track, scope = track_for_activity(d, _split_meta(_bes2_order_ok=False))
    assert scope == "trip" and len(track["activityDetails"]) == 5
    # groups cannot be told apart -> whole trip, never a guessed split
    merged = _detail(groups=[[_pt(1), _pt(2), _pt(3), _pt(4), _pt(5)]])
    track, scope = track_for_activity(merged, _split_meta())
    assert scope == "trip" and len(track["activityDetails"]) == 5


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("ALL TESTS PASSED")
