"""Standalone tests for activity_event.py — run with: python3 tests/test_activity_event.py"""
import importlib.util
import json
from pathlib import Path

_path = (
    Path(__file__).resolve().parent.parent
    / "custom_components" / "ha_bosch_ebike" / "activity_event.py"
)
_spec = importlib.util.spec_from_file_location("activity_event", _path)
activity_event = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(activity_event)

build = activity_event.build_new_activity_payload


def test_full_activity():
    # Field names and nesting as the Smart System activity summary returns
    # them; metres and seconds in, km and minutes out.
    payload = build(
        {
            "id": "a-1",
            "title": "Evening Ride",
            "startTime": "2026-07-27T18:04:11Z",
            "distance": 24310.0,
            "durationWithoutStops": 3720,
            "speed": {"average": 23.5, "maximum": 41.2},
            "elevation": {"gain": 312.0, "loss": 298.0},
            "caloriesBurned": 640,
        },
        "bike-abc",
    )
    assert payload["bike_id"] == "bike-abc"
    assert payload["activity_id"] == "a-1"
    assert payload["title"] == "Evening Ride"
    assert payload["start_time"] == "2026-07-27T18:04:11Z"
    assert payload["distance_km"] == 24.31
    assert payload["duration_min"] == 62.0
    assert payload["average_speed"] == 23.5
    assert payload["max_speed"] == 41.2
    assert payload["elevation_gain"] == 312.0
    assert payload["calories"] == 640.0
    assert payload["has_tricks"] is False
    assert payload["tricks"] is None


def test_calories_reads_the_field_bosch_actually_sends():
    # Bosch calls it "caloriesBurned". Reading a plainly-named "calories"
    # key silently yields None for every real ride, and nothing but a
    # fixture built from the real field name catches that.
    assert build({"caloriesBurned": 512}, None)["calories"] == 512.0
    assert build({"calories": 512}, None)["calories"] is None


def test_missing_fields_become_none_not_zero():
    # A ride Bosch reports without elevation must not claim 0 m of climbing.
    payload = build({"id": "a-2"}, None)
    for key in (
        "title", "start_time", "distance_km", "duration_min",
        "average_speed", "max_speed", "elevation_gain", "calories",
    ):
        assert payload[key] is None, key
    assert payload["bike_id"] is None
    assert payload["has_tricks"] is False


def test_unusable_numbers_are_dropped():
    # NaN would compare false against itself in every template that touches
    # it, and a string is what a malformed response actually looks like.
    payload = build(
        {
            "distance": float("nan"),
            "durationWithoutStops": float("inf"),
            "speed": {"average": "fast", "maximum": None},
            "elevation": "not-a-dict",
        },
        "b",
    )
    assert payload["distance_km"] is None
    assert payload["duration_min"] is None
    assert payload["average_speed"] is None
    assert payload["max_speed"] is None
    assert payload["elevation_gain"] is None


def test_trick_data_is_passed_through():
    trick = {"has_any": True, "jumps": {"amount": 2, "max_height_m": 0.71}}
    payload = build({"id": "a-3", "_trick_check": trick, "_trick_hint": True}, "b")
    assert payload["has_tricks"] is True
    assert payload["tricks"] == trick

    # A hint without parsed data (or vice versa) must not crash or invent one.
    assert build({"_trick_hint": True}, "b")["tricks"] is None
    assert build({"_trick_check": "garbage"}, "b")["tricks"] is None
    assert build({"_trick_check": trick}, "b")["has_tricks"] is False


def test_payload_is_json_serializable():
    # HA puts event payloads on the bus and through the websocket API, so
    # anything in here has to survive JSON round-tripping.
    payload = build(
        {"id": "a-4", "distance": 1000, "_trick_check": {"has_any": False}},
        "bike-1",
    )
    assert json.loads(json.dumps(payload)) == payload


def test_non_dict_activity_does_not_crash():
    for junk in (None, [], "ride", 42):
        payload = build(junk, "b")
        assert payload["activity_id"] is None
        assert payload["bike_id"] == "b"


def test_rounding():
    # Two decimals on km, one on minutes: enough precision to be honest,
    # few enough digits to drop straight into a notification.
    assert build({"distance": 1234.5}, None)["distance_km"] == 1.23
    assert build({"distance": 1235.0}, None)["distance_km"] == 1.24
    assert build({"durationWithoutStops": 95}, None)["duration_min"] == 1.6
    assert build({"distance": 0}, None)["distance_km"] == 0
    assert build({"durationWithoutStops": 0}, None)["duration_min"] == 0


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("ALL TESTS PASSED")
