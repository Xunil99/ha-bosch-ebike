"""Standalone tests for the coordinator's persisted state - run with:
python3 tests/test_persisted_state.py

coordinator.py imports Home Assistant, so it cannot be imported directly in
this dependency-free suite. The loader and the saver are extracted from its
source and exec'd on their own, the same AST approach test_charge_history.py
and test_battery_consumption_topup.py use for the same file.

Why this exists: the coordinator keeps maintenance items, service-due
overrides, the per-bike battery capacity, the odometer floor and the charge
history in one store. The Smart System update path restored it at startup,
the eBike System 2 path did not - so for BES2 the store was written on every
change but never read back. Everything in it was gone after a restart, and
the next save replaced even what was still on disk with the empty in-memory
copy. Both update paths have to load it, and loading has to put back what
saving wrote.
"""
import __future__
import ast
import asyncio
import json
import logging
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
_COORD = _ROOT / "custom_components" / "ha_bosch_ebike" / "coordinator.py"
_TREE = ast.parse(_COORD.read_text(encoding="utf-8"))

_CLASS = next(
    n for n in _TREE.body
    if isinstance(n, ast.ClassDef) and n.name == "BoschEBikeCoordinator"
)


def _method(name):
    found = next(
        (
            n for n in _CLASS.body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name
        ),
        None,
    )
    assert found is not None, (
        f"BoschEBikeCoordinator no longer defines {name} - update this test "
        "alongside the rename/removal"
    )
    return found


def _module_const(name):
    found = next(
        (
            n for n in _TREE.body
            if isinstance(n, ast.Assign)
            and len(n.targets) == 1
            and isinstance(n.targets[0], ast.Name)
            and n.targets[0].id == name
        ),
        None,
    )
    assert found is not None, (
        f"coordinator.py no longer defines {name} at module level - update "
        "this test alongside the rename/removal"
    )
    return found


# --- the real loader and saver, exec'd against a fake store ------------------

_ns: dict[str, Any] = {"Any": Any, "_LOGGER": logging.getLogger("test_persisted_state")}
# coordinator.py uses `from __future__ import annotations`, so its annotations
# are never evaluated; keep that when exec'ing the extracted nodes.
exec(  # noqa: S102 - executing our own source, see the module docstring
    compile(
        ast.Module(
            body=[
                _module_const("CHARGE_HISTORY_MAX_SESSIONS"),
                _method("async_load_persisted_state"),
                _method("_async_save_state"),
            ],
            type_ignores=[],
        ),
        str(_COORD),
        "exec",
        flags=__future__.annotations.compiler_flag,
        dont_inherit=True,
    ),
    _ns,
)
CHARGE_HISTORY_MAX_SESSIONS = _ns["CHARGE_HISTORY_MAX_SESSIONS"]


class FakeStore:
    """Home Assistant's Store reduced to a JSON file shared by key."""

    disk: dict[str, str] = {}

    def __init__(self, key):
        self.key = key
        self.loads = 0

    async def async_load(self):
        self.loads += 1
        raw = FakeStore.disk.get(self.key)
        return None if raw is None else json.loads(raw)

    async def async_save(self, data):
        FakeStore.disk[self.key] = json.dumps(data)


class FakeCoordinator:
    async_load_persisted_state = _ns["async_load_persisted_state"]
    _async_save_state = _ns["_async_save_state"]

    def __init__(self):
        self._store = FakeStore("ha_bosch_ebike_consumption_state")
        self._state_loaded = False
        self._prev_delivered_wh = {}
        self._prev_activity_ids = set()
        self._activity_consumption = {}
        self._activity_bike = {}
        self._manual_activity_bike = {}
        self._maintenance = {}
        self._service_overrides = {}
        self._battery_capacity_wh = {}
        self._odometer_floor_km = {}
        self._charge_history = {}


def _reset():
    FakeStore.disk.clear()


def _run(coro):
    return asyncio.run(coro)


def _populated():
    c = FakeCoordinator()
    c._maintenance = {"bike-1": {"items": [{"id": "chain", "name": "Chain", "interval_km": 500}],
                                 "service_warned": {}}}
    c._service_overrides = {"bike-1": {"date": "2026-12-01", "odometer_km": 3500.0}}
    c._battery_capacity_wh = {"bike-1": 750.0}
    c._odometer_floor_km = {"bike-1": 1234.5}
    c._charge_history = {"bike-1": [{"start_soc": 20.0, "end_soc": 100.0, "duration_min": 170.0}]}
    return c


# --- behaviour of the loader and saver ---------------------------------------

def test_what_is_saved_comes_back_after_a_restart():
    _reset()
    before = _populated()
    _run(before._async_save_state())

    after = FakeCoordinator()
    _run(after.async_load_persisted_state())
    assert after._maintenance == before._maintenance
    assert after._service_overrides == before._service_overrides
    assert after._battery_capacity_wh == before._battery_capacity_wh
    assert after._odometer_floor_km == before._odometer_floor_km
    assert after._charge_history == before._charge_history
    assert after._state_loaded is True


def test_loading_twice_reads_the_store_once_and_keeps_newer_changes():
    _reset()
    _run(_populated()._async_save_state())
    c = FakeCoordinator()
    _run(c.async_load_persisted_state())
    c._battery_capacity_wh["bike-1"] = 625.0        # changed after startup
    _run(c.async_load_persisted_state())            # every poll calls it again
    assert c._store.loads == 1
    assert c._battery_capacity_wh["bike-1"] == 625.0


def test_saving_before_loading_replaces_what_is_stored():
    # This is why every update path has to load first: a save writes the
    # in-memory copy, so a coordinator that never loaded wipes the store.
    _reset()
    _run(_populated()._async_save_state())
    never_loaded = FakeCoordinator()
    never_loaded._battery_capacity_wh = {"bike-1": 500.0}
    _run(never_loaded._async_save_state())

    later = FakeCoordinator()
    _run(later.async_load_persisted_state())
    assert later._maintenance == {}, "the maintenance items were wiped by the save"
    assert later._service_overrides == {}


def test_unusable_files_do_not_break_the_loader():
    for stored in ([], "text", 3, None, {}, {"maintenance": "x", "charge_history": []}):
        _reset()
        if stored is not None:
            FakeStore.disk["ha_bosch_ebike_consumption_state"] = json.dumps(stored)
        c = FakeCoordinator()
        _run(c.async_load_persisted_state())
        assert c._state_loaded is True, stored
        assert c._maintenance == {} and c._charge_history == {}, stored


def test_the_loader_drops_entries_of_the_wrong_shape():
    _reset()
    FakeStore.disk["ha_bosch_ebike_consumption_state"] = json.dumps({
        "battery_capacity_wh": {"a": -5, "b": "x", "c": 700, "d": 0},
        "odometer_floor_km": {"a": -1, "b": 99.5},
        "service_overrides": {"a": "x", "b": {"date": None, "odometer_km": None}},
        "maintenance": {"a": [], "b": {"items": []}},
        "charge_history": {
            "a": [{"start_soc": 20, "end_soc": 80, "duration_min": 60}, {"start_soc": "x"}, 5],
            "b": "not a list",
        },
    })
    c = FakeCoordinator()
    _run(c.async_load_persisted_state())
    assert c._battery_capacity_wh == {"c": 700.0}
    assert c._odometer_floor_km == {"b": 99.5}
    assert c._service_overrides == {"b": {"date": None, "odometer_km": None}}
    assert c._maintenance == {"b": {"items": []}}
    assert c._charge_history == {"a": [{"start_soc": 20, "end_soc": 80, "duration_min": 60}]}


def test_the_charge_history_is_capped_when_loaded():
    _reset()
    entries = [{"start_soc": 10, "end_soc": 90, "duration_min": float(i)}
               for i in range(CHARGE_HISTORY_MAX_SESSIONS + 5)]
    FakeStore.disk["ha_bosch_ebike_consumption_state"] = json.dumps({"charge_history": {"b": entries}})
    c = FakeCoordinator()
    _run(c.async_load_persisted_state())
    kept = c._charge_history["b"]
    assert len(kept) == CHARGE_HISTORY_MAX_SESSIONS
    assert kept[-1]["duration_min"] == float(CHARGE_HISTORY_MAX_SESSIONS + 4), "the newest are kept"


# --- both update paths must load before they use the state --------------------

def _awaits_loader(node):
    """Every `await self.async_load_persisted_state()` below *node*, as line numbers."""
    lines = []
    for sub in ast.walk(node):
        if (
            isinstance(sub, ast.Await)
            and isinstance(sub.value, ast.Call)
            and isinstance(sub.value.func, ast.Attribute)
            and sub.value.func.attr == "async_load_persisted_state"
            and isinstance(sub.value.func.value, ast.Name)
            and sub.value.func.value.id == "self"
        ):
            lines.append(sub.lineno)
    return sorted(lines)


def _first_use_of_persisted_state(node):
    """Line of the first read of a persisted attribute below *node*."""
    persisted = {
        "_maintenance", "_service_overrides", "_battery_capacity_wh",
        "_odometer_floor_km", "_charge_history",
    }
    uses = [
        sub.lineno for sub in ast.walk(node)
        if isinstance(sub, ast.Attribute)
        and sub.attr in persisted
        and isinstance(sub.value, ast.Name) and sub.value.id == "self"
    ]
    return min(uses) if uses else None


def test_the_smart_system_path_loads_the_persisted_state():
    assert _awaits_loader(_method("_async_update_data")), (
        "_async_update_data must await self.async_load_persisted_state()"
    )


def test_the_bes2_path_loads_the_persisted_state_before_using_it():
    # Regression: _update_bes2 returned self._maintenance, self._service_overrides
    # and friends without ever restoring them, so for eBike System 2 they were
    # empty after every restart.
    update_bes2 = _method("_update_bes2")
    loads = _awaits_loader(update_bes2)
    assert loads, "_update_bes2 must await self.async_load_persisted_state()"
    first_use = _first_use_of_persisted_state(update_bes2)
    assert first_use is None or loads[0] < first_use, (
        "the persisted state is read before it was loaded"
    )


def test_the_loader_is_called_from_exactly_these_two_places():
    # A third caller (or a path that silently stops loading) deserves a look.
    callers = sorted(
        n.name for n in _CLASS.body
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and _awaits_loader(n)
    )
    assert callers == ["_async_update_data", "_update_bes2"], callers


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("ALL TESTS PASSED")
