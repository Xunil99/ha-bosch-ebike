"""Standalone tests for writing refreshed tokens back to the entry - run with:
python3 tests/test_token_persistence.py

The API client refreshes an expired access token on its own (api._get on a
401). Bosch may hand out a new refresh token with it, and the old one is then
worthless. The new pair lives only in memory until the coordinator writes it
into the config entry; a restart before that starts from the stale pair and
ends in a reauthentication.

The Smart System poll always did that write. The eBike System 2 poll returned
early from _async_update_data and never reached it, so a BES2 entry kept the
tokens from its last login forever.

coordinator.py imports Home Assistant, so the real methods are extracted from
its source and exec'd against stand-ins (same approach as
test_activity_outage.py).
"""
import __future__
import ast
import asyncio
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
    assert found is not None, f"BoschEBikeCoordinator no longer defines {name}"
    return found


class UpdateFailed(Exception):
    pass


_ns: dict[str, Any] = {
    "Any": Any,
    "SYSTEM_BES2": "ebike_system_2",
    "SYSTEM_COBI": "cobi",
    "UpdateFailed": UpdateFailed,
}
_node = _method("_async_update_data")
exec(  # noqa: S102 - executing our own source
    compile(
        ast.Module(body=[_node], type_ignores=[]),
        str(_COORD),
        "exec",
        flags=__future__.annotations.compiler_flag,
        dont_inherit=True,
    ),
    _ns,
)
_HELPER = "_persist_refreshed_tokens"
_has_helper = any(
    isinstance(n, ast.FunctionDef) and n.name == _HELPER for n in _CLASS.body
)
if _has_helper:
    exec(  # noqa: S102
        compile(
            ast.Module(body=[_method(_HELPER)], type_ignores=[]),
            str(_COORD),
            "exec",
            flags=__future__.annotations.compiler_flag,
            dont_inherit=True,
        ),
        _ns,
    )


class _Entries:
    def __init__(self):
        self.updated = []

    def async_update_entry(self, entry, data):
        self.updated.append(data)
        entry.data = data


class _Hass:
    def __init__(self):
        self.config_entries = _Entries()


class _Entry:
    def __init__(self):
        self.data = {
            "client_id": "cid",
            "system": "ebike_system_2",
            "access_token": "access-old",
            "refresh_token": "refresh-old",
        }


class _Api:
    access_token = "access-old"
    refresh_token = "refresh-old"


class FakeCoordinator:
    _async_update_data = _ns["_async_update_data"]
    if _has_helper:
        _persist_refreshed_tokens = _ns[_HELPER]

    def __init__(self, bes2_behaviour):
        self.api = _Api()
        self.hass = _Hass()
        self.config_entry = _Entry()
        self._system = "ebike_system_2"
        self._bes2_behaviour = bes2_behaviour

    async def _update_bes2(self):
        return await self._bes2_behaviour(self)

    async def _update_cobi(self):
        return await self._bes2_behaviour(self)


async def _refresh_then_succeed(coord):
    # What api._get does on a 401: new access token, rotated refresh token.
    coord.api.access_token = "access-new"
    coord.api.refresh_token = "refresh-new"
    return {"bikes": []}


async def _refresh_then_fail(coord):
    coord.api.access_token = "access-new"
    coord.api.refresh_token = "refresh-new"
    raise UpdateFailed("Error fetching BES2 bikes: 503")


async def _no_refresh(coord):
    return {"bikes": []}


def test_bes2_poll_writes_a_refreshed_token_pair_back():
    coord = FakeCoordinator(_refresh_then_succeed)
    asyncio.run(coord._async_update_data())
    assert coord.hass.config_entries.updated, (
        "the BES2 poll must write the refreshed tokens into the entry"
    )
    data = coord.config_entry.data
    assert data["access_token"] == "access-new"
    assert data["refresh_token"] == "refresh-new"
    assert data["client_id"] == "cid" and data["system"] == "ebike_system_2", (
        "the other entry data stays"
    )


def test_bes2_poll_that_fails_after_the_refresh_still_writes_the_tokens():
    # The refresh succeeded, a later request failed. The old refresh token
    # may already be revoked, so the new one must not wait for a good poll.
    coord = FakeCoordinator(_refresh_then_fail)
    try:
        asyncio.run(coord._async_update_data())
    except UpdateFailed:
        pass
    else:
        raise AssertionError("the poll error must still surface")
    assert coord.config_entry.data["refresh_token"] == "refresh-new"


def test_bes2_poll_without_a_refresh_writes_nothing():
    coord = FakeCoordinator(_no_refresh)
    asyncio.run(coord._async_update_data())
    assert coord.hass.config_entries.updated == [], (
        "no storage write on every poll, only when a token changed"
    )


def test_the_cobi_poll_writes_refreshed_tokens_back_too():
    for behaviour in (_refresh_then_succeed, _refresh_then_fail):
        coord = FakeCoordinator(behaviour)
        coord._system = "cobi"
        try:
            asyncio.run(coord._async_update_data())
        except UpdateFailed:
            pass
        assert coord.config_entry.data["refresh_token"] == "refresh-new", behaviour.__name__


def test_both_paths_use_the_same_helper():
    # The Smart System path must not keep its own inline copy that could drift.
    assert _has_helper, f"coordinator.py defines no {_HELPER}"
    src = ast.unparse(_method("_async_update_data"))
    assert src.count(f"self.{_HELPER}()") >= 2, (
        "_async_update_data calls the helper for BES2 and for the Smart System"
    )
    assert "async_update_entry" not in src, "no inline token write left"


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_")]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"ok   {name}")
        except Exception as err:  # noqa: BLE001
            failed += 1
            print(f"FAIL {name}: {type(err).__name__}: {err}")
    print(f"{len(tests) - failed}/{len(tests)} passed")
    raise SystemExit(1 if failed else 0)
