"""Standalone tests for trick_check.py — run with: python3 tests/test_trick_check.py"""
import importlib.util
from pathlib import Path

_path = (
    Path(__file__).resolve().parent.parent
    / "custom_components" / "ha_bosch_ebike" / "trick_check.py"
)
_spec = importlib.util.spec_from_file_location("trick_check", _path)
trick_check = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(trick_check)

parse_trick_check = trick_check.parse_trick_check


def test_parses_real_jump_example():
    # Real Smart System activity summary field values (forum report,
    # issue #65 follow-up): 1 jump, max 2.38m / 250ms / 710mm, cross
    # verified against the Flow app's own display for the same ride
    # ("1x", "2,4 m", "0.25 s", "0,7 m").
    activity = {
        "tricks": {
            "jumps": {"amount": 1, "maxDistance": 2.3799999999999999, "maxDuration": 250, "maxHeight": 710},
            "manuals": {"amount": 0, "maxAngle": 0, "maxDistance": 0, "maxDuration": 0},
            "stoppies": {"amount": 0, "maxAngle": 0, "maxDistance": 0, "maxDuration": 0},
            "wheelies": {"amount": 0, "maxAngle": 0, "maxDistance": 0, "maxDuration": 0},
        }
    }
    result = parse_trick_check(activity)
    assert result["has_any"] is True
    assert result["jumps"] == {
        "amount": 1, "max_distance_m": 2.4, "max_duration_s": 0.25, "max_height_m": 0.71,
    }
    assert result["manuals"]["amount"] == 0
    assert result["stoppies"]["amount"] == 0
    assert result["wheelies"]["amount"] == 0
    # Non-jump types report an angle, not a height.
    assert "max_angle_deg" in result["manuals"]
    assert "max_height_m" not in result["manuals"]


def test_parses_real_all_zero_example():
    # Real Smart System activity summary with no tricks on that ride
    # (forum report, issue #65 follow-up) - the field is always present,
    # not only on rides with an actual trick.
    activity = {
        "tricks": {
            "jumps": {"amount": 0, "maxDistance": 0, "maxDuration": 0, "maxHeight": 0},
            "manuals": {"amount": 0, "maxAngle": 0, "maxDistance": 0, "maxDuration": 0},
            "stoppies": {"amount": 0, "maxAngle": 0, "maxDistance": 0, "maxDuration": 0},
            "wheelies": {"amount": 0, "maxAngle": 0, "maxDistance": 0, "maxDuration": 0},
        }
    }
    result = parse_trick_check(activity)
    assert result["has_any"] is False
    assert result["jumps"]["amount"] == 0


def test_no_tricks_key_returns_none():
    assert parse_trick_check({"id": "abc", "distance": 5000}) is None


def test_non_dict_tricks_value_returns_none():
    assert parse_trick_check({"tricks": "not-a-dict"}) is None


def test_non_dict_activity_returns_none():
    assert parse_trick_check(None) is None
    assert parse_trick_check("tricks") is None
    assert parse_trick_check(42) is None


def test_malformed_trick_type_is_skipped_not_fatal():
    activity = {
        "tricks": {
            "jumps": {"amount": 2, "maxDistance": 5.0, "maxDuration": 400, "maxHeight": 900},
            "manuals": "unexpected-string",
            "stoppies": {"amount": 0, "maxAngle": 0, "maxDistance": 0, "maxDuration": 0},
            "wheelies": None,
        }
    }
    result = parse_trick_check(activity)
    assert result["has_any"] is True
    assert result["jumps"]["amount"] == 2
    assert "manuals" not in result
    assert "wheelies" not in result
    assert result["stoppies"]["amount"] == 0


def test_all_trick_types_malformed_returns_none():
    activity = {"tricks": {"jumps": None, "manuals": None, "stoppies": None, "wheelies": None}}
    assert parse_trick_check(activity) is None


def test_missing_amount_field_is_malformed():
    activity = {"tricks": {"jumps": {"maxDistance": 1.0, "maxDuration": 100, "maxHeight": 200}}}
    assert parse_trick_check(activity) is None


def test_non_numeric_metric_fields_degrade_to_none_not_crash():
    activity = {
        "tricks": {
            "jumps": {"amount": 1, "maxDistance": "n/a", "maxDuration": None, "maxHeight": 710},
        }
    }
    result = parse_trick_check(activity)
    assert result["jumps"]["amount"] == 1
    assert result["jumps"]["max_distance_m"] is None
    assert result["jumps"]["max_duration_s"] is None
    assert result["jumps"]["max_height_m"] == 0.71


def test_nan_or_infinite_amount_is_malformed_not_a_crash():
    # A literal NaN/Infinity JSON token in amount must not blow up int()
    # and take down the whole coordinator poll.
    activity = {
        "tricks": {
            "jumps": {"amount": float("nan"), "maxDistance": 1.0, "maxDuration": 100, "maxHeight": 200},
            "manuals": {"amount": float("inf"), "maxAngle": 0, "maxDistance": 0, "maxDuration": 0},
        }
    }
    assert parse_trick_check(activity) is None


def test_nan_or_infinite_metric_fields_degrade_to_none_not_crash():
    activity = {
        "tricks": {
            "jumps": {
                "amount": 1,
                "maxDistance": float("nan"),
                "maxDuration": float("inf"),
                "maxHeight": 710,
            },
        }
    }
    result = parse_trick_check(activity)
    assert result["jumps"]["amount"] == 1
    assert result["jumps"]["max_distance_m"] is None
    assert result["jumps"]["max_duration_s"] is None
    assert result["jumps"]["max_height_m"] == 0.71


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("ALL TESTS PASSED")
