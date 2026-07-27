"""Sensor description key uniqueness — run with:
python3 tests/test_sensor_keys.py

BoschEBikeSensor builds its unique_id as f"{bike_id}_{description.key}", so
two descriptions that can be created for the same bike must never share a
key: Home Assistant drops the second one with "Platform ha_bosch_ebike does
not generate unique IDs" and the entity silently goes missing. That is
exactly what happened to `total_elevation_gain` on eBike System 2 accounts,
where the AGGREGATE_SENSORS entry (sum over the imported rides) collided
with the BES2_STATISTICS_SENSORS entry (the bike's own lifetime total).

Sharing a key across two tuples is allowed as long as the two can never be
created for the same system - that is the case here, and deliberately so:
BES2 keeps the /statistics figure, Smart System keeps the ride sum, and both
land on the same entity_id. What this test pins down is that the mutual
exclusion is actually in place.

sensor.py imports Home Assistant, so the descriptions are read straight out
of its syntax tree rather than imported - same dependency-free approach the
rest of the suite uses.
"""
import ast
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_SENSOR = _ROOT / "custom_components" / "ha_bosch_ebike" / "sensor.py"
_SRC = _SENSOR.read_text(encoding="utf-8")
_TREE = ast.parse(_SRC)

# Which description tuples are created for which system, mirroring the loops
# in async_setup_entry(). A tuple missing from both sets fails the coverage
# check below, so adding one to sensor.py forces a decision here.
SMART_SYSTEM_TUPLES = {
    "BIKE_SENSORS",
    "ACTIVITY_SENSORS",
    "AGGREGATE_SENSORS",
    "GPS_COORDINATE_SENSORS",
    "TRICK_SENSORS",
    "BATTERY_CONSUMPTION_SENSORS",
}
BES2_TUPLES = {
    "BIKE_SENSORS",
    "ACTIVITY_SENSORS",
    "AGGREGATE_SENSORS",
    "GPS_COORDINATE_SENSORS",
    "TRICK_SENSORS",
    "BES2_STATISTICS_SENSORS",
}


def _description_tuples() -> dict[str, list[dict]]:
    """Every module-level *_SENSORS tuple as {name: [{key, bes2}, ...]}."""
    found: dict[str, list[dict]] = {}
    for node in _TREE.body:
        target = None
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            target = node.target.id
        elif (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
        ):
            target = node.targets[0].id
        if not target or not target.endswith("_SENSORS"):
            continue
        assert isinstance(node.value, ast.Tuple), (
            f"{target} is no longer a tuple literal - update this test"
        )
        descriptions = []
        for element in node.value.elts:
            assert isinstance(element, ast.Call), (
                f"{target} holds something other than a description call"
            )
            fields = {
                kw.arg: kw.value.value
                for kw in element.keywords
                if isinstance(kw.value, ast.Constant)
            }
            assert "key" in fields, f"a description in {target} has no literal key="
            descriptions.append({"key": fields["key"], "bes2": fields.get("bes2", True)})
        found[target] = descriptions
    return found


def _setup_loop_bodies() -> dict[str, str]:
    """Source of each `for desc in *_SENSORS:` loop in async_setup_entry."""
    setup = next(
        n for n in _TREE.body
        if isinstance(n, ast.AsyncFunctionDef) and n.name == "async_setup_entry"
    )
    bodies: dict[str, str] = {}
    for node in ast.walk(setup):
        if not isinstance(node, ast.For) or not isinstance(node.iter, ast.Name):
            continue
        if not node.iter.id.endswith("_SENSORS"):
            continue
        bodies[node.iter.id] = "\n".join(
            ast.get_source_segment(_SRC, stmt) or "" for stmt in node.body
        )
    return bodies


TUPLES = _description_tuples()
LOOPS = _setup_loop_bodies()


def test_every_tuple_is_classified() -> None:
    """A newly added *_SENSORS tuple has to be assigned to a system."""
    classified = SMART_SYSTEM_TUPLES | BES2_TUPLES
    assert classified == set(TUPLES), (
        "sensor.py and this test disagree about which description tuples exist: "
        f"only in sensor.py {set(TUPLES) - classified}, "
        f"only in the test {classified - set(TUPLES)}"
    )


def test_keys_unique_within_each_tuple() -> None:
    for name, descriptions in TUPLES.items():
        keys = [d["key"] for d in descriptions]
        duplicates = {k for k in keys if keys.count(k) > 1}
        assert not duplicates, f"{name} defines {sorted(duplicates)} more than once"


def test_keys_unique_per_system() -> None:
    """The actual unique_id collision: one bike, two entities, one key."""
    for system, names in (("Smart System", SMART_SYSTEM_TUPLES), ("BES2", BES2_TUPLES)):
        seen: dict[str, str] = {}
        for name in sorted(names):
            for description in TUPLES[name]:
                # bes2=False descriptions are skipped for BES2 in setup.
                if system == "BES2" and not description["bes2"]:
                    continue
                key = description["key"]
                assert key not in seen, (
                    f"{system}: {name} and {seen[key]} both create "
                    f"key={key!r}, so both entities claim the unique_id "
                    f"<bike>_{key} and Home Assistant drops one of them"
                )
                seen[key] = name


def test_bes2_flag_is_honoured_by_its_loop() -> None:
    """A bes2=False description only helps if its loop actually checks it."""
    for name, descriptions in TUPLES.items():
        if all(d["bes2"] for d in descriptions):
            continue
        assert name in LOOPS, (
            f"{name} carries bes2=False descriptions but async_setup_entry has "
            "no `for desc in ...` loop for it - check the flag is applied"
        )
        assert "desc.bes2" in LOOPS[name], (
            f"{name} carries bes2=False descriptions but its loop in "
            "async_setup_entry never checks desc.bes2, so they are created for "
            "BES2 anyway"
        )


if __name__ == "__main__":
    for _name, _test in sorted(globals().items()):
        if _name.startswith("test_") and callable(_test):
            _test()
            print(f"ok  {_name}")
    print("all sensor key tests passed")
