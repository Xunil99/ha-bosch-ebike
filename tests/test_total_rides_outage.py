"""Standalone tests for the ride counters during an activity list outage - run with:
python3 tests/test_total_rides_outage.py

sensor.py imports Home Assistant, so BoschEBikeSensor.native_value and the real
value_fn of the Total Rides description are read out of its syntax tree and run
against stand-ins, the way test_trick_sensors.py does for the module level
helpers.

Issue #95 follow-up: when Bosch's activity list fails after a restart, no ride
was ever imported, and the Total Rides counter used to read 0 (len of an empty
list). Total Rides is a total_increasing sensor, so the long term statistics
saw 224 -> 0 -> 224 and added all 224 rides a second time once Bosch answered.
The coordinator now says when the list is "not loaded" rather than "empty"
(activities_unknown, covered in test_activity_outage.py) and the aggregate
sensors read unknown then. The other half of the contract is pinned here: an
account without rides still reads 0, and so does everything once the list has
been loaded.
"""
import __future__
import ast
from pathlib import Path
from types import SimpleNamespace
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
_SENSOR = _ROOT / "custom_components" / "ha_bosch_ebike" / "sensor.py"
_TREE = ast.parse(_SENSOR.read_text(encoding="utf-8"))


def _function(name):
    found = next(
        (n for n in _TREE.body if isinstance(n, ast.FunctionDef) and n.name == name),
        None,
    )
    assert found is not None, f"sensor.py no longer defines {name} at module level"
    return found


def _native_value():
    cls = next(
        n
        for n in _TREE.body
        if isinstance(n, ast.ClassDef) and n.name == "BoschEBikeSensor"
    )
    found = next(
        (n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "native_value"),
        None,
    )
    assert found is not None, "BoschEBikeSensor no longer defines native_value"
    found.decorator_list = []
    return found


def _total_rides_value_fn():
    """The real lambda of the Total Rides description, evaluated on its own."""
    assignment = next(
        n
        for n in _TREE.body
        if isinstance(n, (ast.Assign, ast.AnnAssign))
        and "AGGREGATE_SENSORS" in ast.unparse(n.targets[0] if isinstance(n, ast.Assign) else n.target)
    )
    for call in ast.walk(assignment.value):
        if not isinstance(call, ast.Call):
            continue
        kwargs = {kw.arg: kw.value for kw in call.keywords}
        key = kwargs.get("key")
        if isinstance(key, ast.Constant) and key.value == "total_rides":
            expr = ast.Expression(body=kwargs["value_fn"])
            ast.fix_missing_locations(expr)
            return eval(compile(expr, str(_SENSOR), "eval"), {})  # noqa: S307 - our own source
    raise AssertionError("AGGREGATE_SENSORS no longer has a total_rides description")


_ns: dict[str, Any] = {"Any": Any}
exec(  # noqa: S102 - executing our own source, see the module docstring
    compile(
        ast.Module(body=[_function("_activities_for_bike"), _native_value()], type_ignores=[]),
        str(_SENSOR),
        "exec",
        flags=__future__.annotations.compiler_flag,
        dont_inherit=True,
    ),
    _ns,
)


class Sensor:
    native_value = property(_ns["native_value"])


TOTAL_RIDES = _total_rides_value_fn()


def _sensor(*, unknown, activities, value_fn=TOTAL_RIDES):
    sensor = Sensor()
    sensor.coordinator = SimpleNamespace(
        activities_unknown=unknown,
        data={"all_activities": activities, "activity_bike": {}, "bikes": []},
    )
    sensor._bike_id = "bike-1"
    sensor.entity_description = SimpleNamespace(
        key="total_rides", is_aggregate=True, is_activity=False, value_fn=value_fn
    )
    return sensor


def _rides(count):
    return [{"id": f"a{i}"} for i in range(count)]


def test_the_count_is_unknown_while_the_list_has_never_been_loaded():
    assert _sensor(unknown=True, activities=[]).native_value is None


def test_an_account_without_rides_reads_zero():
    assert _sensor(unknown=False, activities=[]).native_value == 0


def test_the_count_is_the_number_of_rides():
    assert _sensor(unknown=False, activities=_rides(224)).native_value == 224


def test_the_guard_covers_every_aggregate_description():
    # Not only Total Rides: whatever value_fn the description has, an unloaded
    # list must not be turned into a number.
    sensor = _sensor(unknown=True, activities=[], value_fn=lambda activities: 7)
    assert sensor.native_value is None
    sensor = _sensor(unknown=False, activities=[], value_fn=lambda activities: 7)
    assert sensor.native_value == 7


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("ALL TESTS PASSED")
