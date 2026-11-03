"""Standalone tests for device_lookup.device_for_identifier - run with:
python3 tests/test_device_lookup.py

device_lookup.py imports nothing from Home Assistant, so it is loaded
directly. The registries below stand in for the two shapes the real
DeviceRegistry has had.

Issue #96: Home Assistant 2026.10 reports DeviceRegistry.async_get_device as
deprecated (it stops working in 2027.8.0), because device identifiers are only
unique per config entry now. Issue #80 had converted one of the three lookups
in the integration and left the other two, so besides the helper itself this
file pins down that no direct call is left anywhere in the package.
"""
import ast
import importlib.util
from pathlib import Path

_PACKAGE = (
    Path(__file__).resolve().parent.parent / "custom_components" / "ha_bosch_ebike"
)
_spec = importlib.util.spec_from_file_location(
    "device_lookup", _PACKAGE / "device_lookup.py"
)
device_lookup = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(device_lookup)
device_for_identifier = device_lookup.device_for_identifier

DOMAIN = "ha_bosch_ebike"
BIKE = (DOMAIN, "bike-1")


class OwnershipRegistry:
    """Home Assistant 2026.8 and later: identifiers are unique per config entry."""

    def __init__(self, devices):
        self.devices = devices  # {(identifier, config_entry_id): device}
        self.lookups = []

    # Keyword only on purpose: the helper must name its arguments, so a change
    # of the parameter order in Home Assistant cannot swap them silently.
    def async_get_device_by_identifier(self, *, identifier, config_entry_id):
        self.lookups.append((identifier, config_entry_id))
        return self.devices.get((identifier, config_entry_id))

    def async_get_device(self, identifiers=None, connections=None):
        raise AssertionError(
            "the deprecated async_get_device was used on a registry that has "
            "the replacement"
        )


class LegacyRegistry:
    """Before 2026.8: one device per identifier, no config entry in the lookup."""

    def __init__(self, devices):
        self.devices = devices  # {identifier: device}
        self.lookups = []

    def async_get_device(self, identifiers=None, connections=None):
        self.lookups.append(identifiers)
        for identifier in identifiers or ():
            if identifier in self.devices:
                return self.devices[identifier]
        return None


def test_the_replacement_is_used_with_the_config_entry():
    registry = OwnershipRegistry({(BIKE, "entry-a"): "device-a"})
    assert device_for_identifier(registry, BIKE, "entry-a") == "device-a"
    assert registry.lookups == [(BIKE, "entry-a")]


def test_the_lookup_is_scoped_to_the_config_entry():
    # Two accounts that both know the identifier: each one gets its own device.
    registry = OwnershipRegistry(
        {(BIKE, "entry-a"): "device-a", (BIKE, "entry-b"): "device-b"}
    )
    assert device_for_identifier(registry, BIKE, "entry-a") == "device-a"
    assert device_for_identifier(registry, BIKE, "entry-b") == "device-b"
    assert device_for_identifier(registry, BIKE, "entry-c") is None


def test_an_unregistered_identifier_gives_none_on_both_kinds_of_registry():
    assert device_for_identifier(OwnershipRegistry({}), BIKE, "entry-a") is None
    assert device_for_identifier(LegacyRegistry({}), BIKE, "entry-a") is None


def test_the_old_call_is_the_fallback_when_there_is_no_replacement():
    registry = LegacyRegistry({BIKE: "device-a"})
    assert not hasattr(registry, "async_get_device_by_identifier")
    assert device_for_identifier(registry, BIKE, "entry-a") == "device-a"
    assert registry.lookups == [{BIKE}], "the identifier goes in as a set, as before"


def test_the_identifier_of_another_bike_is_not_found():
    other = (DOMAIN, "bike-2")
    assert device_for_identifier(LegacyRegistry({other: "d"}), BIKE, "e") is None
    assert (
        device_for_identifier(OwnershipRegistry({(other, "e"): "d"}), BIKE, "e")
        is None
    )


# --- structure pins ---------------------------------------------------------------


def _package_files():
    return sorted(_PACKAGE.rglob("*.py"))


def test_no_direct_async_get_device_is_left_in_the_package():
    offenders = []
    for path in _package_files():
        if path.name == "device_lookup.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr == "async_get_device":
                offenders.append(f"{path.name}:{node.lineno}")
    assert not offenders, (
        "DeviceRegistry.async_get_device is deprecated (issue #96), go through "
        f"device_lookup.device_for_identifier instead: {offenders}"
    )


def _calls_to_helper(filename):
    tree = ast.parse((_PACKAGE / filename).read_text(encoding="utf-8"))
    imported = any(
        isinstance(n, ast.ImportFrom)
        and n.module == "device_lookup"
        and any(a.name == "device_for_identifier" for a in n.names)
        for n in ast.walk(tree)
    )
    calls = [
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Name)
        and n.func.id == "device_for_identifier"
    ]
    return imported, calls


def test_the_three_lookups_use_the_helper():
    imported, calls = _calls_to_helper("__init__.py")
    assert imported and len(calls) >= 2, "ghost device cleanup and the instance list"
    imported, calls = _calls_to_helper("config_flow.py")
    assert imported and len(calls) >= 1, "bike name in the options dialog"


def test_every_lookup_names_the_config_entry_it_belongs_to():
    # The third argument is what scopes the lookup. Whatever expression a call
    # site uses for it has to be an entry id, not the bike or anything else.
    for filename in ("__init__.py", "config_flow.py"):
        _, calls = _calls_to_helper(filename)
        for call in calls:
            assert len(call.args) == 3, f"{filename}:{call.lineno} needs three arguments"
            entry = ast.unparse(call.args[2])
            assert entry.split(".")[-1] == "entry_id", (
                f"{filename}:{call.lineno} scopes the lookup with {entry}"
            )


def test_the_helper_imports_nothing_from_home_assistant():
    # That is what lets this dependency-free suite load it.
    tree = ast.parse((_PACKAGE / "device_lookup.py").read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            imported.add((node.module or "").split(".")[0])
    assert imported <= {"__future__", "typing"}, imported


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("ALL TESTS PASSED")
