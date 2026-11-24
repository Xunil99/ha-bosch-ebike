"""Standalone tests for the COBI poll - run with: python3 tests/test_cobi_update.py

coordinator.py imports Home Assistant, so the real poll methods are extracted
from its source and exec'd against stand-ins (same approach as
test_activity_outage.py). cobi.py has no Home Assistant imports and is loaded
for real.

What the COBI poll has to get right:
* hubs and rides come from two requests; a failing hub list fails the poll,
  a failing ride list must not (issue #95: keep the last good list, never
  drop the totals to 0, warn once);
* new-ride events only from the second successful fetch on, once per ride;
* refreshed tokens are written back to the entry, also when the poll fails;
* the repair hint for "no COBI data" only while hubs AND rides are empty.
"""
import __future__
import ast
import asyncio
import importlib.util
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
_PKG = _ROOT / "custom_components" / "ha_bosch_ebike"
_COORD = _PKG / "coordinator.py"
_TREE = ast.parse(_COORD.read_text(encoding="utf-8"))
_CLASS = next(
    n for n in _TREE.body
    if isinstance(n, ast.ClassDef) and n.name == "BoschEBikeCoordinator"
)

_spec = importlib.util.spec_from_file_location("cobi", _PKG / "cobi.py")
cobi = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cobi)


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


class AuthError(Exception):
    pass


class ConfigEntryAuthFailed(Exception):
    pass


class UpdateFailed(Exception):
    pass


class _Records(logging.Handler):
    def __init__(self):
        super().__init__(logging.DEBUG)
        self.records = []

    def emit(self, record):
        self.records.append((record.levelno, record.getMessage()))

    def at(self, level):
        return [m for lvl, m in self.records if lvl == level]


_LOG = _Records()
_logger = logging.getLogger("test_cobi_update")
_logger.setLevel(logging.DEBUG)
_logger.propagate = False
_logger.addHandler(_LOG)


class _FakeDtUtil:
    @staticmethod
    def utcnow():
        return datetime(2026, 11, 24, 9, 0, tzinfo=timezone.utc)


_ns: dict[str, Any] = {
    "Any": Any,
    "AuthError": AuthError,
    "ConfigEntryAuthFailed": ConfigEntryAuthFailed,
    "UpdateFailed": UpdateFailed,
    "SYSTEM_BES2": "ebike_system_2",
    "SYSTEM_COBI": "cobi",
    "SYSTEM_SMART": "smart_system",
    "_LOGGER": _logger,
    "dt_util": _FakeDtUtil,
    "cobi": cobi,
}
_NAMES = [
    "_async_update_data",
    "_update_cobi",
    "_fetch_activities_isolated",
    "_describe_fetch_error",
    "_persist_refreshed_tokens",
    "activities_unknown",
    "cobi_account_id",
]
_nodes = [_method(n) for n in _NAMES]
for _node in _nodes:
    _node.decorator_list = []
exec(  # noqa: S102 - executing our own source
    compile(
        ast.Module(body=_nodes, type_ignores=[]),
        str(_COORD),
        "exec",
        flags=__future__.annotations.compiler_flag,
        dont_inherit=True,
    ),
    _ns,
)


# --- synthetic Bosch answers, shaped like the COBI spec ----------------------------------


def raw_ride(rid, start, km=12.0):
    return {
        "id": rid,
        "startTime": start,
        "endTime": start.replace("T10:", "T11:"),
        "totalDistance": int(km * 1000),
        "bikeType": "ELECTRIC_25",
        "elevationGain": 80,
        "avgSpeed": 16.0,
        "maxSpeed": 30.0,
        "durationWithoutStops": 2700,
    }


HUB = {"serialNumber": "24173107182521", "partNumber": "8017", "role": "OWNER",
       "activatedAt": "2021-06-04T10:23:12.000Z"}


class FakeResponseError(Exception):
    def __init__(self, status):
        super().__init__(f"{status}, message='Not Found', url='https://api.bosch-ebike.com/cobi/v1/activities'")
        self.status = status
        self.body = '{"title": "Not Found"}'


class FakeApi:
    access_token_scope = "openid offline_access"

    def __init__(self):
        self.access_token = "access"
        self.refresh_token = "refresh"
        self.hubs = [dict(HUB)]
        self.rides = [
            raw_ride("r1", "2026-11-20T10:00:00.000Z"),
            raw_ride("r2", "2026-11-22T10:00:00.000Z"),
        ]
        self.hubs_error = None
        self.rides_error = None
        self.refresh_on_call = False

    async def get_hubs_cobi(self):
        if self.refresh_on_call:
            self.access_token, self.refresh_token = "access-new", "refresh-new"
        if self.hubs_error:
            raise self.hubs_error
        return [dict(h) for h in self.hubs]

    async def get_activities_cobi(self):
        if self.rides_error:
            raise self.rides_error
        return [dict(r) for r in self.rides]


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
    entry_id = "ENTRY1"

    def __init__(self):
        self.data = {"client_id": "cid", "system": "cobi",
                     "access_token": "access", "refresh_token": "refresh"}


class FakeCoordinator:
    _async_update_data = _ns["_async_update_data"]
    _update_cobi = _ns["_update_cobi"]
    _fetch_activities_isolated = _ns["_fetch_activities_isolated"]
    _describe_fetch_error = staticmethod(_ns["_describe_fetch_error"])
    _persist_refreshed_tokens = _ns["_persist_refreshed_tokens"]
    activities_unknown = property(_ns["activities_unknown"])
    cobi_account_id = property(_ns["cobi_account_id"])

    def __init__(self, api):
        self.api = api
        self.hass = _Hass()
        self.config_entry = _Entry()
        self._system = "cobi"
        self._initial_import_done = False
        self._activities_error = None
        self._activities_error_since = None
        self._all_activities = []
        self._cobi_seen_activity_ids = None
        self._cobi_raw_hubs = []
        self._cobi_raw_activities = None
        self.fired = []
        self.issue_calls = []

    def _fire_new_activity(self, activity, bike_id):
        self.fired.append((activity.get("id"), bike_id))

    def _sync_no_cobi_data_issue(self, missing):
        self.issue_calls.append(missing)


def _setup():
    _LOG.records.clear()
    api = FakeApi()
    return api, FakeCoordinator(api)


def _poll(coord):
    return asyncio.run(coord._async_update_data())


# --- (a) a normal poll --------------------------------------------------------------------


def test_a_normal_poll_delivers_hubs_and_rides_newest_first():
    api, coord = _setup()
    data = _poll(coord)
    assert data["bikes"] == [], "COBI has no bikes; every bike loop stays empty"
    assert [h["serial"] for h in data["cobi_hubs"]] == ["24173107182521"]
    assert [a["id"] for a in data["all_activities"]] == ["r2", "r1"]
    assert data["latest_activity"]["id"] == "r2"
    assert data["all_activities"][0]["durationWithoutStops"] == 2700
    assert data["activity_bike"] == {} and data["activity_consumption"] == {}
    assert coord._initial_import_done and not coord.activities_unknown
    assert coord._cobi_raw_hubs and coord._cobi_raw_activities, "kept for the diagnostics"


# --- (b) + (c) the ride list fails ------------------------------------------------------------


def test_a_failing_ride_list_after_the_import_keeps_the_last_list():
    api, coord = _setup()
    _poll(coord)
    api.rides_error = FakeResponseError(404)
    for _ in range(3):
        data = _poll(coord)
    assert [a["id"] for a in data["all_activities"]] == ["r2", "r1"]
    assert coord.activities_unknown is False, "the totals keep their value"
    assert len(_LOG.at(logging.WARNING)) == 1, "one warning per outage"
    assert "404" in coord._activities_error

    api.rides_error = None
    _poll(coord)
    assert coord._activities_error is None
    assert len([m for m in _LOG.at(logging.INFO) if "available again" in m]) == 1


def test_a_failing_ride_list_on_the_first_poll_makes_the_totals_unknown():
    api, coord = _setup()
    api.rides_error = FakeResponseError(500)
    data = _poll(coord)
    assert data["all_activities"] == []
    assert coord.activities_unknown is True
    assert [h["serial"] for h in data["cobi_hubs"]] == ["24173107182521"], "hubs still load"


# --- (d) the hub list fails / auth -----------------------------------------------------------


def test_a_failing_hub_list_fails_the_poll():
    api, coord = _setup()
    api.hubs_error = FakeResponseError(503)
    try:
        _poll(coord)
    except UpdateFailed as err:
        assert "COBI hubs" in str(err)
        # With wrong consent or scope the hub list is the first request to
        # fail; the log line is then the tester's only evidence.
        assert '{"title": "Not Found"}' in str(err), "Bosch's own reply is kept"
        assert "[access token scope: openid offline_access]" in str(err)
    else:
        raise AssertionError("expected UpdateFailed")


def test_an_auth_error_on_either_list_starts_the_reauth():
    for attr in ("hubs_error", "rides_error"):
        api, coord = _setup()
        setattr(api, attr, AuthError("Bosch rejected the refresh token (invalid_grant)"))
        try:
            _poll(coord)
        except ConfigEntryAuthFailed:
            pass
        else:
            raise AssertionError(f"{attr}: expected ConfigEntryAuthFailed")


# --- (e) new-ride events ------------------------------------------------------------------


def test_the_first_poll_only_seeds_and_a_later_ride_fires_once():
    api, coord = _setup()
    _poll(coord)
    assert coord.fired == [], "no burst of events for the history at setup"
    api.rides.append(raw_ride("r3", "2026-11-24T10:00:00.000Z"))
    _poll(coord)
    assert coord.fired == [("r3", "cobi_ENTRY1")]
    _poll(coord)
    assert coord.fired == [("r3", "cobi_ENTRY1")], "once per ride"


def test_a_failed_first_fetch_does_not_turn_the_history_into_new_rides():
    api, coord = _setup()
    api.rides_error = FakeResponseError(404)
    _poll(coord)
    api.rides_error = None
    _poll(coord)
    assert coord.fired == [], "the first successful fetch only seeds"


# --- (f) tokens ---------------------------------------------------------------------------


def test_a_refreshed_token_pair_is_written_back():
    api, coord = _setup()
    api.refresh_on_call = True
    _poll(coord)
    assert coord.config_entry.data["refresh_token"] == "refresh-new"
    assert coord.config_entry.data["system"] == "cobi"


def test_a_refreshed_token_pair_is_written_back_when_the_poll_fails():
    api, coord = _setup()
    api.refresh_on_call = True
    api.hubs_error = FakeResponseError(503)
    try:
        _poll(coord)
    except UpdateFailed:
        pass
    assert coord.config_entry.data["refresh_token"] == "refresh-new"


# --- (g) the repair hint -----------------------------------------------------------------


def test_the_no_data_hint_follows_hubs_and_rides():
    api, coord = _setup()
    api.hubs, api.rides = [], []
    _poll(coord)
    assert coord.issue_calls == [True]
    api.hubs = [dict(HUB)]
    _poll(coord)
    assert coord.issue_calls == [True, False], "clears itself"


def test_the_no_data_hint_is_not_raised_while_the_rides_cannot_be_fetched():
    api, coord = _setup()
    api.hubs = []
    api.rides_error = FakeResponseError(404)
    _poll(coord)
    assert coord.issue_calls == [], "an outage says nothing about the data sharing"


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"PASS {name}")
        except Exception as err:  # noqa: BLE001
            failed += 1
            print(f"FAIL {name}: {type(err).__name__}: {err}")
    print(f"{len(tests) - failed}/{len(tests)} passed")
    raise SystemExit(1 if failed else 0)
