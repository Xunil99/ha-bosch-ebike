"""Standalone tests for the Trick Check sensor helpers — run with:
python3 tests/test_trick_sensors.py

sensor.py itself imports Home Assistant, so the three pure helpers
(_trick_entry / _trick_count / _trick_attrs and _bike_has_trick_data) are
extracted from its source and exec'd on their own. That is uglier than an
import, but it keeps the suite dependency-free like every other file here,
and these helpers are exactly the part where a wrong "missing means zero"
assumption would silently ship.
"""
import ast
import importlib.util
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_SENSOR = _ROOT / "custom_components" / "ha_bosch_ebike" / "sensor.py"

_WANTED = {"_trick_entry", "_trick_count", "_trick_attrs", "_bike_has_trick_data"}
_tree = ast.parse(_SENSOR.read_text(encoding="utf-8"))
_picked = [n for n in _tree.body if isinstance(n, ast.FunctionDef) and n.name in _WANTED]
assert {n.name for n in _picked} == _WANTED, (
    f"sensor.py no longer defines {_WANTED - {n.name for n in _picked}} at module "
    "level - update this test alongside the rename"
)

# _bike_has_trick_data calls _activities_for_bike, which is a real (and
# HA-free) helper in the same module; pull it in the same way.
_extra = [
    n for n in _tree.body
    if isinstance(n, ast.FunctionDef) and n.name == "_activities_for_bike"
]
assert _extra, "sensor.py no longer defines _activities_for_bike"

# The annotations on those defs are evaluated at def time (sensor.py has no
# `from __future__ import annotations`), so the names they mention have to
# exist in the namespace we exec into.
_ns: dict = {"Any": __import__("typing").Any, "Callable": __import__("typing").Callable}
exec(  # noqa: S102 - executing our own source, see the module docstring
    compile(ast.Module(body=_picked + _extra, type_ignores=[]), str(_SENSOR), "exec"),
    _ns,
)
_trick_entry = _ns["_trick_entry"]
_trick_count = _ns["_trick_count"]
_trick_attrs = _ns["_trick_attrs"]
_bike_has_trick_data = _ns["_bike_has_trick_data"]

# The real parser, so the fixtures below are the shapes production actually
# produces rather than a hand-written guess at them.
_spec = importlib.util.spec_from_file_location(
    "trick_check", _ROOT / "custom_components" / "ha_bosch_ebike" / "trick_check.py"
)
trick_check = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(trick_check)


def _activity(raw_tricks):
    """Build an activity the way the coordinator's _apply_trick_check does."""
    activity = {"id": "a-1", "tricks": raw_tricks} if raw_tricks is not None else {"id": "a-1"}
    parsed = trick_check.parse_trick_check(activity)
    if parsed is not None:
        activity["_trick_check"] = parsed
    activity["_trick_hint"] = bool(parsed and parsed["has_any"])
    return activity


_REAL_JUMP = {
    "jumps": {"amount": 1, "maxDistance": 2.38, "maxDuration": 250, "maxHeight": 710},
    "manuals": {"amount": 0, "maxAngle": 0, "maxDistance": 0, "maxDuration": 0},
    "stoppies": {"amount": 0, "maxAngle": 0, "maxDistance": 0, "maxDuration": 0},
    "wheelies": {"amount": 0, "maxAngle": 0, "maxDistance": 0, "maxDuration": 0},
}


def test_counts_and_attributes_of_a_real_ride():
    activity = _activity(_REAL_JUMP)
    assert _trick_count("jumps")(activity) == 1
    assert _trick_count("manuals")(activity) == 0
    assert _trick_count("wheelies")(activity) == 0

    # The count is the state, so it must not be repeated as an attribute.
    jump_attrs = _trick_attrs("jumps")(activity)
    assert "amount" not in jump_attrs
    assert jump_attrs == {
        "max_distance_m": 2.4, "max_duration_s": 0.25, "max_height_m": 0.71,
    }
    # Non-jump types report an angle instead of a height.
    assert "max_angle_deg" in _trick_attrs("manuals")(activity)
    assert "max_height_m" not in _trick_attrs("manuals")(activity)


def test_max_jump_height_reads_off_the_jumps_entry():
    activity = _activity(_REAL_JUMP)
    assert (_trick_entry(activity, "jumps") or {}).get("max_height_m") == 0.71
    # And degrades to None, not a crash, when there is no trick data at all.
    assert (_trick_entry(_activity(None), "jumps") or {}).get("max_height_m") is None


def test_no_data_is_none_not_zero():
    # A ride Bosch reports without a tricks block must not claim zero jumps:
    # "the bike does not report this" and "you jumped zero times" are
    # different facts, and only the second one belongs in a statistic.
    for empty in (None, {}, "nonsense", {"jumps": "nonsense"}):
        activity = _activity(empty)
        assert _trick_count("jumps")(activity) is None, empty
        assert _trick_attrs("jumps")(activity) == {}, empty


def test_zero_tricks_is_zero_not_none():
    all_zero = {k: {"amount": 0, "maxAngle": 0, "maxDistance": 0, "maxDuration": 0}
                for k in ("jumps", "manuals", "stoppies", "wheelies")}
    activity = _activity(all_zero)
    assert _trick_count("jumps")(activity) == 0
    assert activity["_trick_hint"] is False


def test_entity_creation_gate():
    data_with = {
        "all_activities": [_activity(None), _activity(_REAL_JUMP)],
        "activity_bike": {},
        "bikes": [{"id": "bike-1"}],
    }
    data_without = {
        "all_activities": [_activity(None), _activity(None)],
        "activity_bike": {},
        "bikes": [{"id": "bike-1"}],
    }
    # Present on ANY ride is enough - the newest ride having no tricks block
    # must not hide sensors from someone whose previous ride did report one.
    assert _bike_has_trick_data(data_with, "bike-1") is True
    assert _bike_has_trick_data(data_without, "bike-1") is False
    assert _bike_has_trick_data({"all_activities": [], "bikes": []}, "bike-1") is False


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("ALL TESTS PASSED")
