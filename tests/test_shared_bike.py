"""Standalone tests for shared_bike.py — run with: python3 tests/test_shared_bike.py

One bike, shared via Bosch's "Share eBike" between a main user and an invited
rider with their own SingleKey ID: both config entries report the same bike
ID, so every entity of the second entry used to collide on its unique_id
("does not generate unique IDs ... already exists - ignoring") and the second
account's rides never showed up in Home Assistant.

shared_bike.py has no Home Assistant imports; entities and registry entries
are passed in as plain objects, so these tests use small fakes instead of HA.
"""
import importlib.util
from pathlib import Path

_MODULE_PATH = (
    Path(__file__).resolve().parent.parent
    / "custom_components" / "ha_bosch_ebike" / "shared_bike.py"
)
_spec = importlib.util.spec_from_file_location("shared_bike", _MODULE_PATH)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
scope_shared_bike_entities = _mod.scope_shared_bike_entities
unique_ids_of_other_entries = _mod.unique_ids_of_other_entries

DOMAIN = "ha_bosch_ebike"
BIKE = "bike-1"
UID = f"{BIKE}_last_ride_distance"


class FakeEntity:
    def __init__(self, unique_id, identifier, name="Cargo Line"):
        self._attr_unique_id = unique_id
        self._attr_device_info = {"identifiers": {(DOMAIN, identifier)}, "name": name}


class FakeRegistryEntry:
    def __init__(self, unique_id, config_entry_id, platform=DOMAIN):
        self.unique_id = unique_id
        self.config_entry_id = config_entry_id
        self.platform = platform


def _scope(entities, taken, entry_id="entry-b", label="Sam"):
    return scope_shared_bike_entities(
        entities, set(taken), entry_id=entry_id, account_label=label, domain=DOMAIN
    )


def test_bike_nobody_else_registered_is_left_alone():
    entity = FakeEntity(UID, BIKE)
    _scope([entity], taken=[])
    assert entity._attr_unique_id == UID
    assert entity._attr_device_info["identifiers"] == {(DOMAIN, BIKE)}


def test_unique_id_taken_by_another_entry_gets_entry_scoped():
    entity = FakeEntity(UID, BIKE)
    _scope([entity], taken=[UID], entry_id="entry-b")
    assert entity._attr_unique_id == f"entry-b_{UID}"


def test_new_sensor_of_a_bike_held_by_another_entry_is_scoped_too():
    # An update adds a sensor nobody has registered yet. Both entries set up
    # concurrently, so an exact unique_id match would let whichever entry is
    # faster grab the plain ID. The bike as a whole belongs to the entry that
    # already holds its other unique_ids.
    entity = FakeEntity(f"{BIKE}_brand_new_sensor", BIKE)
    _scope([entity], taken=[UID], entry_id="entry-b")
    assert entity._attr_unique_id == f"entry-b_{BIKE}_brand_new_sensor"


def test_scoped_entity_gets_its_own_device():
    entity = FakeEntity(UID, BIKE)
    _scope([entity], taken=[UID], entry_id="entry-b")
    assert entity._attr_device_info["identifiers"] == {(DOMAIN, f"{BIKE}_entry-b")}


def test_own_device_name_carries_the_account_label():
    entity = FakeEntity(UID, BIKE, name="Cargo Line")
    _scope([entity], taken=[UID], label="Sam")
    assert entity._attr_device_info["name"] == "Cargo Line (Sam)"


def test_account_level_entity_of_the_second_entry_is_left_alone():
    # The unassigned-activities sensor hangs off a per-entry account device,
    # not off a bike, so it never collides and must not be touched.
    entity = FakeEntity("entry-b_unassigned_activities", "entry-b", name="Account")
    _scope([entity], taken=[UID], entry_id="entry-b")
    assert entity._attr_unique_id == "entry-b_unassigned_activities"
    assert entity._attr_device_info["name"] == "Account"


def test_entity_with_three_part_device_identifier_does_not_break_setup():
    # Identifiers are not guaranteed to be (domain, id) pairs. Unpacking every
    # identifier as a pair raised "too many values to unpack" and took down
    # every platform of every entry on a real install.
    entity = FakeEntity(UID, BIKE)
    entity._attr_device_info["identifiers"].add(("some_other_domain", "hub", "node-7"))
    _scope([entity], taken=[UID])
    assert entity._attr_unique_id == f"entry-b_{UID}"
    assert (DOMAIN, f"{BIKE}_entry-b") in entity._attr_device_info["identifiers"]


def test_other_entries_unique_ids_exclude_the_entrys_own():
    # The main user's entry must never be re-scoped: that would orphan all of
    # its existing entities and their history. Its own registered unique_ids
    # therefore never count as "taken" for itself.
    registry = [FakeRegistryEntry(UID, "entry-a")]
    assert unique_ids_of_other_entries(registry, entry_id="entry-a", domain=DOMAIN) == set()
    assert unique_ids_of_other_entries(registry, entry_id="entry-b", domain=DOMAIN) == {UID}


def test_other_integrations_entities_do_not_count_as_taken():
    registry = [FakeRegistryEntry(UID, "entry-x", platform="some_other_domain")]
    assert unique_ids_of_other_entries(registry, entry_id="entry-b", domain=DOMAIN) == set()


def test_main_entry_keeps_ids_even_if_the_other_entry_owns_a_same_bike_device():
    # Since Home Assistant 2026.11 a device belongs to exactly one config
    # entry, so both entries can own a device for the same bike. Deciding by
    # device ownership then re-scoped BOTH entries and orphaned the main
    # user's entities. Ownership of the registered unique_ids is what counts.
    registry = [
        FakeRegistryEntry(UID, "entry-a"),
        FakeRegistryEntry(f"entry-b_{UID}", "entry-b"),
    ]
    main = FakeEntity(UID, BIKE)
    second = FakeEntity(UID, BIKE)
    _scope([main], unique_ids_of_other_entries(registry, entry_id="entry-a", domain=DOMAIN), entry_id="entry-a")
    _scope([second], unique_ids_of_other_entries(registry, entry_id="entry-b", domain=DOMAIN), entry_id="entry-b")
    assert main._attr_unique_id == UID
    assert main._attr_device_info["identifiers"] == {(DOMAIN, BIKE)}
    assert second._attr_unique_id == f"entry-b_{UID}"


class UndefinedType:
    """Stand-in for Home Assistant's Undefined sentinel (matched by type name)."""


Undefined = UndefinedType()


class DataclassDeviceInfo:
    """Mimics DeviceInfo from Home Assistant 2026.12: a dataclass whose item
    access is deprecated (stops working in 2027.12) and whose unset fields hold
    the Undefined sentinel (issue #102). Item access fails here so any use of
    it shows up as a test failure."""

    def __init__(self, identifiers, name=Undefined):
        self.identifiers = identifiers
        self.name = name

    def __getitem__(self, key):
        raise AssertionError(f"deprecated DeviceInfo[{key!r}] read")

    def __setitem__(self, key, value):
        raise AssertionError(f"deprecated DeviceInfo[{key!r}] write")

    def get(self, key, default=None):
        raise AssertionError(f"deprecated DeviceInfo.get({key!r})")

    def __contains__(self, key):
        raise AssertionError(f"deprecated {key!r} in DeviceInfo")


def test_dataclass_device_info_is_scoped_through_attributes():
    entity = FakeEntity(UID, BIKE)
    entity._attr_device_info = DataclassDeviceInfo({(DOMAIN, BIKE)}, name="Cargo Line")
    _scope([entity], taken=[UID], entry_id="entry-b", label="Sam")
    assert entity._attr_unique_id == f"entry-b_{UID}"
    assert entity._attr_device_info.identifiers == {(DOMAIN, f"{BIKE}_entry-b")}
    assert entity._attr_device_info.name == "Cargo Line (Sam)"


def test_dataclass_device_info_without_name_keeps_name_unset():
    entity = FakeEntity(UID, BIKE)
    entity._attr_device_info = DataclassDeviceInfo({(DOMAIN, BIKE)})
    _scope([entity], taken=[UID], entry_id="entry-b")
    assert entity._attr_device_info.identifiers == {(DOMAIN, f"{BIKE}_entry-b")}
    assert entity._attr_device_info.name is Undefined


def test_dataclass_device_info_of_unshared_bike_is_left_alone():
    entity = FakeEntity(UID, BIKE)
    entity._attr_device_info = DataclassDeviceInfo({(DOMAIN, BIKE)}, name="Cargo Line")
    _scope([entity], taken=[])
    assert entity._attr_unique_id == UID
    assert entity._attr_device_info.identifiers == {(DOMAIN, BIKE)}
    assert entity._attr_device_info.name == "Cargo Line"


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
