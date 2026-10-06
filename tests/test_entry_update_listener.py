"""Standalone tests for the config-entry update listener - run with:
python3 tests/test_entry_update_listener.py

__init__.py imports Home Assistant, so it cannot be imported in this
dependency-free suite. The listener factory and the heatmap cache tag are
extracted from its source and exec'd on their own, the same AST approach
test_battery_consumption_topup.py uses for coordinator.py.

Covers issue #89: Home Assistant fires every update listener for ANY change
to a config entry, and the coordinator writes refreshed tokens back into
entry.data about once an hour. The old listener reloaded unconditionally, so
each token refresh tore the whole entry down: all entities went unavailable,
a charge in progress was dropped, and the full activity history was imported
again. The listener must reload for a real change (options, or any data key
other than the two tokens) and for nothing else.
"""
import __future__
import ast
import asyncio
import copy
from pathlib import Path
from types import MappingProxyType

_INIT = (
    Path(__file__).resolve().parent.parent
    / "custom_components" / "ha_bosch_ebike" / "__init__.py"
)
_TREE = ast.parse(_INIT.read_text(encoding="utf-8"))


def _node(kind, name):
    found = next(
        (
            n for n in _TREE.body
            if isinstance(n, kind) and (
                getattr(n, "name", None) == name
                or (
                    isinstance(n, ast.Assign)
                    and any(isinstance(t, ast.Name) and t.id == name for t in n.targets)
                )
            )
        ),
        None,
    )
    assert found is not None, (
        f"__init__.py no longer defines {name} at module level - update this "
        "test alongside the rename/removal"
    )
    return found


_nodes = [
    _node(ast.Assign, "_TOKEN_KEYS"),
    _node(ast.FunctionDef, "_reload_relevant_state"),
    _node(ast.FunctionDef, "_make_update_listener"),
    _node(ast.FunctionDef, "_track_cache_tag"),
]
_ns = {"copy": copy}
# __init__.py uses `from __future__ import annotations`, so its annotations
# (ConfigEntry, HomeAssistant) are never evaluated; keep that when exec'ing
# the extracted nodes, which cannot resolve those names here.
exec(  # noqa: S102 - executing our own source, see the module docstring
    compile(
        ast.Module(body=_nodes, type_ignores=[]),
        str(_INIT), "exec",
        flags=__future__.annotations.compiler_flag, dont_inherit=True,
    ),
    _ns,
)
_make_update_listener = _ns["_make_update_listener"]
_track_cache_tag = _ns["_track_cache_tag"]


class FakeEntry:
    def __init__(self, options=None, data=None, title="Bosch eBike"):
        self.entry_id = "entry1"
        self.options = MappingProxyType(options if options is not None else {})
        self.data = MappingProxyType(data if data is not None else {})
        self.title = title


class FakeConfigEntries:
    def __init__(self):
        self.reloaded = []

    async def async_reload(self, entry_id):
        self.reloaded.append(entry_id)


class FakeHass:
    def __init__(self):
        self.config_entries = FakeConfigEntries()


def _options():
    return {"bikes": {"bike1": {"live_odometer_entity": "sensor.odo"}}}


def _data():
    return {
        "client_id": "abc", "system": "smart_system",
        "access_token": "tok-1", "refresh_token": "ref-1",
    }


def _fire(listener, entry):
    hass = FakeHass()
    asyncio.run(listener(hass, entry))
    return hass.config_entries.reloaded


def test_token_refresh_alone_does_not_reload():
    entry = FakeEntry(_options(), _data())
    listener = _make_update_listener(entry)
    # what coordinator.py writes after a refresh: same keys, new token values
    entry.data = MappingProxyType({**_data(), "access_token": "tok-2", "refresh_token": "ref-2"})
    assert _fire(listener, entry) == []


def test_only_one_token_changing_does_not_reload_either():
    entry = FakeEntry(_options(), _data())
    listener = _make_update_listener(entry)
    entry.data = MappingProxyType({**_data(), "access_token": "tok-2"})
    assert _fire(listener, entry) == []


def test_option_change_reloads():
    entry = FakeEntry(_options(), _data())
    listener = _make_update_listener(entry)
    opts = _options()
    opts["bikes"]["bike1"]["live_soc_entity"] = "sensor.soc"
    entry.options = MappingProxyType(opts)
    assert _fire(listener, entry) == ["entry1"]


def test_nested_option_changed_in_place_still_reloads():
    # The snapshot is a deep copy: mutating a nested option on the live entry
    # must not silently change what it is compared against.
    shared = _options()
    entry = FakeEntry(shared, _data())
    listener = _make_update_listener(entry)
    shared["bikes"]["bike1"]["live_odometer_entity"] = "sensor.other_odo"
    assert _fire(listener, entry) == ["entry1"]


def test_other_data_key_change_reloads():
    entry = FakeEntry(_options(), _data())
    listener = _make_update_listener(entry)
    entry.data = MappingProxyType({**_data(), "client_id": "different"})
    assert _fire(listener, entry) == ["entry1"]
    entry2 = FakeEntry(_options(), _data())
    listener2 = _make_update_listener(entry2)
    entry2.data = MappingProxyType({**_data(), "new_key": 1})
    assert _fire(listener2, entry2) == ["entry1"]


def test_title_change_does_not_reload():
    entry = FakeEntry(_options(), _data())
    listener = _make_update_listener(entry)
    entry.title = "My renamed bike"
    assert _fire(listener, entry) == []


def test_option_change_together_with_a_token_refresh_reloads():
    entry = FakeEntry(_options(), _data())
    listener = _make_update_listener(entry)
    opts = _options()
    opts["x"] = 1
    entry.options = MappingProxyType(opts)
    entry.data = MappingProxyType({**_data(), "access_token": "tok-3"})
    assert _fire(listener, entry) == ["entry1"]


def test_a_new_setup_compares_against_the_options_then_in_force():
    # After an options-triggered reload async_setup_entry builds a NEW
    # listener from the changed entry; token refreshes after that must not
    # reload again, and must not be compared against the stale options.
    entry = FakeEntry(_options(), _data())
    opts = _options()
    opts["x"] = 1
    entry.options = MappingProxyType(opts)
    listener_after_reload = _make_update_listener(entry)
    entry.data = MappingProxyType({**_data(), "access_token": "tok-9"})
    assert _fire(listener_after_reload, entry) == []
    assert _fire(listener_after_reload, entry) == []


def test_no_change_at_all_does_not_reload():
    entry = FakeEntry(_options(), _data())
    assert _fire(_make_update_listener(entry), entry) == []


# ---------------------------------------------------------------------------
# Heatmap track cache tag
# ---------------------------------------------------------------------------

def test_track_cache_tag_is_stable_for_an_unchanged_activity():
    a = {"id": "1", "distance": 5400, "startTime": "2026-10-01T10:00:00Z"}
    assert _track_cache_tag(a) == _track_cache_tag(dict(a))


def test_track_cache_tag_changes_when_the_distance_is_corrected():
    # issue #31: a ride whose track was still uploading gets its distance
    # corrected upward once the full track is there - the cached partial
    # track must then be refetched.
    partial = {"id": "1", "distance": 1200}
    full = {"id": "1", "distance": 5400}
    assert _track_cache_tag(partial) != _track_cache_tag(full)


def test_track_cache_tag_changes_when_a_bes2_trip_gains_a_ride():
    two = {"id": "1-x", "distance": 800, "_bes2_ride_count": 2}
    three = {"id": "1-x", "distance": 800, "_bes2_ride_count": 3}
    assert _track_cache_tag(two) != _track_cache_tag(three)


def test_track_cache_tag_handles_activities_without_either_field():
    assert _track_cache_tag({}) == (None, None)


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("ALL TESTS PASSED")
