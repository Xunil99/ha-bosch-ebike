"""Standalone tests for trick_scan.py — run with: python3 tests/test_trick_scan.py"""
import importlib.util
from pathlib import Path

_path = (
    Path(__file__).resolve().parent.parent
    / "custom_components" / "ha_bosch_ebike" / "trick_scan.py"
)
_spec = importlib.util.spec_from_file_location("trick_scan", _path)
trick_scan = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(trick_scan)

scan_for_trick_fields = trick_scan.scan_for_trick_fields
format_hits_for_log = trick_scan.format_hits_for_log


def test_finds_top_level_trick_key():
    hits = scan_for_trick_fields({"trickCount": 3})
    assert len(hits) == 1
    assert hits[0] == {"path": "trickCount", "key": "trickCount", "value": 3}


def test_finds_nested_keys_with_full_path():
    obj = {"statistics": {"tricks": {"jumps": [{"jumpHeightM": 1.2, "airtimeS": 0.8}]}}}
    hits = scan_for_trick_fields(obj)
    paths = {h["path"] for h in hits}
    assert "statistics.tricks" in paths
    assert "statistics.tricks.jumps" in paths
    assert "statistics.tricks.jumps[0].jumpHeightM" in paths
    assert "statistics.tricks.jumps[0].airtimeS" in paths


def test_case_insensitive_matching():
    hits = scan_for_trick_fields({"WHEELIEDuration": 5, "StoppieAngle": 12})
    keys = {h["key"] for h in hits}
    assert keys == {"WHEELIEDuration", "StoppieAngle"}


def test_bare_manual_is_not_matched():
    """The known false-positive exclusion: bare 'manual' (existing,
    unrelated gear-shift config field) must never be flagged."""
    hits = scan_for_trick_fields({"manual": True, "manualShiftRequired": False})
    assert hits == []


def test_manual_combined_with_trick_word_is_still_matched():
    # e.g. a hypothetical "manualCount" under a tricks section - "manual"
    # is excluded on its own, but this must still match via "trick"/"jump" etc.
    # if those appear elsewhere in the same object.
    hits = scan_for_trick_fields({"tricks": {"manualCount": 2}})
    paths = {h["path"] for h in hits}
    assert "tricks" in paths
    assert "tricks.manualCount" not in paths  # "manual" alone still excluded


def test_redacts_nested_gps_coordinates_within_a_matched_hit():
    # A hypothetical jump event that plausibly carries its own location -
    # the "jumps" key itself matches "jump", so its nested lat/lon must be
    # redacted in the returned hit, while non-sensitive fields survive.
    obj = {
        "jumps": [
            {
                "heightM": 1.2,
                "durationS": 0.8,
                "location": {"latitude": 47.123, "longitude": 11.456},
            }
        ]
    }
    hits = scan_for_trick_fields(obj)
    top_hit = next(h for h in hits if h["path"] == "jumps")
    redacted = top_hit["value"][0]["location"]
    assert redacted == {"latitude": "**REDACTED**", "longitude": "**REDACTED**"}
    assert top_hit["value"][0]["heightM"] == 1.2
    assert top_hit["value"][0]["durationS"] == 0.8


def test_redaction_does_not_alter_non_sensitive_nested_data():
    hits = scan_for_trick_fields({"trickStats": {"count": 3, "types": ["jump", "wheelie"]}})
    assert hits[0]["value"] == {"count": 3, "types": ["jump", "wheelie"]}


def test_no_matches_on_ordinary_activity_data():
    obj = {
        "id": "abc123",
        "title": "Evening ride",
        "distance": 15234,
        "speed": {"average": 18.2, "maximum": 41.0},
        "driveUnit": {"manualShiftRequired": False},
    }
    assert scan_for_trick_fields(obj) == []


def test_non_dict_non_list_input_returns_empty():
    assert scan_for_trick_fields(None) == []
    assert scan_for_trick_fields("trick") == []  # a bare string is not a dict key
    assert scan_for_trick_fields(42) == []


def test_format_hits_for_log_caps_count_and_value_length():
    hits = [{"path": f"a[{i}]", "key": "trick", "value": "x" * 300} for i in range(25)]
    text = format_hits_for_log(hits, max_hits=20, max_value_len=50)
    assert "(+5 more)" in text
    assert text.count("a[") == 20
    # each shown value must be capped well under the full 300 chars
    first_segment = text.split(";")[0]
    assert len(first_segment) < 100


def test_format_hits_for_log_empty():
    assert format_hits_for_log([]) == ""


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("ALL TESTS PASSED")
