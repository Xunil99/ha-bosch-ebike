"""Translation keys that other projects find sensors by - run with:
python3 tests/test_sensor_translation_keys.py

Cards and scripts outside this repository (the ebike-cards project, for one)
look a bike's sensors up through the translation_key in Home Assistant's entity
registry instead of through the entity ID, because the entity ID is whatever the
name was when the entity was created and users rename it. That makes the keys
below part of the interface of this integration: a rename or a removal breaks
those cards without any error on our side. This test pins them.

It also pins the two decisions that keep a key from changing anything visible:

* The names stay literal. The battery sensors carry the battery's product name
  ("PowerTube 750 Wh Lifetime"), which a translated name could not.
* There is no entry for these keys in strings.json or translations/*.json.
  With has_entity_name Home Assistant prefers a translated name over the literal
  one, so adding an entry would rename the entities (and give new installs
  different entity IDs than existing ones have).

sensor.py imports Home Assistant, so everything is read out of its syntax tree
rather than imported - same dependency-free approach the rest of the suite uses.
"""
import ast
import json
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_INTEGRATION = _ROOT / "custom_components" / "ha_bosch_ebike"
_SRC = (_INTEGRATION / "sensor.py").read_text(encoding="utf-8")
_TREE = ast.parse(_SRC)

# The end of each battery description's key (the part after the battery prefix)
# and the translation key it must carry.
BATTERY_KEYS = {
    "_wh_lifetime": "battery_wh_lifetime",
    "_charge_cycles_total": "battery_charge_cycles",
    "_charge_cycles_on_bike": "battery_cycles_on_bike",
    "_charge_cycles_off_bike": "battery_cycles_off_bike",
}
MAX_ALTITUDE_KEY = "last_ride_max_altitude"
ALL_PINNED = set(BATTERY_KEYS.values()) | {MAX_ALTITUDE_KEY}


def _battery_descriptions() -> list[dict]:
    """The descriptions built in _create_battery_sensors, as plain dicts."""
    function = next(
        n for n in _TREE.body
        if isinstance(n, ast.FunctionDef) and n.name == "_create_battery_sensors"
    )
    found = []
    for node in ast.walk(function):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "BoschBikeSensorDescription"
        ):
            continue
        kwargs = {kw.arg: kw.value for kw in node.keywords if kw.arg}
        key = kwargs["key"]
        assert isinstance(key, ast.JoinedStr) and isinstance(key.values[-1], ast.Constant), (
            "a battery description's key is no longer f'{prefix}<suffix>' - update this test"
        )
        translation_key = kwargs.get("translation_key")
        found.append({
            "suffix": key.values[-1].value,
            "translation_key": (
                translation_key.value if isinstance(translation_key, ast.Constant) else None
            ),
            "name": ast.unparse(kwargs["name"]),
        })
    return found


def _class_attributes(class_name: str) -> dict[str, ast.AST]:
    cls = next(
        n for n in _TREE.body
        if isinstance(n, ast.ClassDef) and n.name == class_name
    )
    attributes = {}
    for node in cls.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    attributes[target.id] = node.value
    return attributes


def test_battery_sensors_carry_their_keys() -> None:
    descriptions = _battery_descriptions()
    assert {d["suffix"] for d in descriptions} == set(BATTERY_KEYS), (
        "the battery sensors in _create_battery_sensors changed - "
        f"found {sorted(d['suffix'] for d in descriptions)}; decide the keys "
        "for any new one and add it to this test"
    )
    for description in descriptions:
        expected = BATTERY_KEYS[description["suffix"]]
        assert description["translation_key"] == expected, (
            f"the battery sensor ending in {description['suffix']!r} has "
            f"translation_key={description['translation_key']!r}, expected "
            f"{expected!r} - cards look it up by that key"
        )


def test_battery_names_keep_the_product_name() -> None:
    for description in _battery_descriptions():
        assert "{bat_name}" in description["name"], (
            f"the name of the battery sensor ending in {description['suffix']!r} "
            "no longer contains the battery's product name; with two batteries "
            "on a bike both sensors would carry the same name"
        )


def test_max_altitude_sensor_carries_its_key() -> None:
    attributes = _class_attributes("BoschMaxAltitudeSensor")
    key = attributes.get("_attr_translation_key")
    assert isinstance(key, ast.Constant) and key.value == MAX_ALTITUDE_KEY, (
        f"BoschMaxAltitudeSensor must set _attr_translation_key = {MAX_ALTITUDE_KEY!r}"
    )


def test_max_altitude_name_stays_literal() -> None:
    """The class sets its name in __init__, so look for it there."""
    cls = next(
        n for n in _TREE.body
        if isinstance(n, ast.ClassDef) and n.name == "BoschMaxAltitudeSensor"
    )
    names = [
        node.value.value
        for node in ast.walk(cls)
        if isinstance(node, ast.Assign)
        and any(
            isinstance(t, ast.Attribute) and t.attr == "_attr_name"
            for t in node.targets
        )
        and isinstance(node.value, ast.Constant)
    ]
    assert names == ["Last Ride Max Altitude"], (
        f"BoschMaxAltitudeSensor's name changed to {names} - "
        "existing installs show it as 'Last Ride Max Altitude'"
    )


def test_each_pinned_key_is_used_exactly_once() -> None:
    """A second user of a key would make cards find two different sensors."""
    for key in sorted(ALL_PINNED):
        uses = _SRC.count(f'"{key}"')
        assert uses == 1, (
            f"translation key {key!r} appears {uses} times in sensor.py - "
            "every entity type needs its own key"
        )


def test_no_translated_name_exists_for_the_pinned_keys() -> None:
    files = [_INTEGRATION / "strings.json", *sorted((_INTEGRATION / "translations").glob("*.json"))]
    assert len(files) > 1, "no translation files found - the glob is wrong"
    for path in files:
        sensors = json.loads(path.read_text(encoding="utf-8")).get("entity", {}).get("sensor", {})
        clash = ALL_PINNED & set(sensors)
        assert not clash, (
            f"{path.name} has entity names for {sorted(clash)}: Home Assistant "
            "would show those instead of the literal names, which carry the "
            "battery's product name, and new installs would get different "
            "entity IDs than existing ones"
        )


if __name__ == "__main__":
    for _name, _test in sorted(globals().items()):
        if _name.startswith("test_") and callable(_test):
            _test()
            print(f"ok  {_name}")
    print("all sensor translation key tests passed")
