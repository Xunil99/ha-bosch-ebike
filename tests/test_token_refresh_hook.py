"""Standalone tests for saving a refreshed token pair at once - run with:
python3 tests/test_token_refresh_hook.py

api._get refreshes an expired access token on its own when Bosch answers 401,
and Bosch may rotate the refresh token with it. The coordinator wrote the new
pair into the config entry only at fixed points of a poll: the Smart System
poll after its first block of requests had all succeeded, BES2 and COBI at the
end of the poll. A refresh followed by a failing request (activity list 404 or
500, a network error), or a refresh during a request outside a poll (GPS
import, CSV export, the track service), left the new pair in memory only. A
restart then logged in with the old refresh token, which Bosch may already
have voided, and ended in a reauthentication.

The client now reports every successful refresh to a listener, and the
coordinator hooks its _persist_refreshed_tokens into it, so the pair is saved
the moment it exists, whatever happens to the request after that.

api.py imports aiohttp and coordinator.py imports Home Assistant, so the real
methods are extracted from their source and exec'd against stand-ins (same
approach as test_refresh_token_rejection.py and test_token_persistence.py).
"""
import __future__
import ast
import asyncio
import importlib.util
import logging
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
_PKG = _ROOT / "custom_components" / "ha_bosch_ebike"
_API = _PKG / "api.py"
_COORD = _PKG / "coordinator.py"
_API_CLASS = next(
    n for n in ast.parse(_API.read_text(encoding="utf-8")).body
    if isinstance(n, ast.ClassDef) and n.name == "BoschEBikeAPI"
)
_COORD_CLASS = next(
    n for n in ast.parse(_COORD.read_text(encoding="utf-8")).body
    if isinstance(n, ast.ClassDef) and n.name == "BoschEBikeCoordinator"
)

_spec = importlib.util.spec_from_file_location("oauth_error", _PKG / "oauth_error.py")
oauth_error = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(oauth_error)


def _method(cls, name):
    found = next(
        (
            n for n in cls.body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name
        ),
        None,
    )
    assert found is not None, f"{cls.name} no longer defines {name}"
    return found


class AuthError(Exception):
    pass


class FakeResponseError(Exception):
    def __init__(self, status):
        super().__init__(f"{status}, message='x'")
        self.status = status


class _Aiohttp:
    ClientResponseError = FakeResponseError


_ns: dict[str, Any] = {
    "Any": Any,
    "AuthError": AuthError,
    "TOKEN_URL": "https://auth.example/token",
    "API_BASE_URL": "https://api.example",
    "aiohttp": _Aiohttp,
    "rejection_reason": oauth_error.rejection_reason,
    "_LOGGER": logging.getLogger("test_token_refresh_hook"),
}
for _name in ("_get", "refresh_access_token"):
    exec(  # noqa: S102 - executing our own source
        compile(
            ast.Module(body=[_method(_API_CLASS, _name)], type_ignores=[]),
            str(_API),
            "exec",
            flags=__future__.annotations.compiler_flag,
            dont_inherit=True,
        ),
        _ns,
    )


class FakeResponse:
    def __init__(self, status, payload=None):
        self.status = status
        self._payload = payload

    async def text(self):
        return ""

    async def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status >= 400:
            raise FakeResponseError(self.status)


class _Ctx:
    def __init__(self, response):
        self._response = response

    async def __aenter__(self):
        if isinstance(self._response, BaseException):
            raise self._response
        return self._response

    async def __aexit__(self, *exc):
        return False


class FakeSession:
    def __init__(self, gets, post):
        self._gets = list(gets)
        self._post = post

    def get(self, url, headers=None, timeout=None):
        return _Ctx(self._gets.pop(0))

    def post(self, url, data=None, timeout=None):
        return _Ctx(self._post)


_ROTATED = FakeResponse(200, {"access_token": "access-new", "refresh_token": "refresh-new"})

# What the real client attribute is called; read from api.py so the test
# follows a rename instead of silently testing a stand-in attribute.
_INIT_SRC = ast.unparse(_method(_API_CLASS, "__init__"))
_HOOK = "token_listener"


class FakeApi:
    _get = _ns["_get"]
    refresh_access_token = _ns["refresh_access_token"]
    _TIMEOUT = "timeout"

    def __init__(self, session):
        self._session = session
        self._client_id = "cid"
        self._access_token = "access-old"
        self._refresh_token = "refresh-old"
        self.seen = []
        setattr(self, _HOOK, lambda: self.seen.append(
            (self._access_token, self._refresh_token)
        ))


def _run(api, path="/activities"):
    try:
        return asyncio.run(api._get(path)), None
    except BaseException as err:  # noqa: BLE001
        return None, err


def test_the_client_starts_without_a_listener():
    assert any(
        line.strip().startswith(f"self.{_HOOK}") and line.rstrip().endswith("= None")
        for line in _INIT_SRC.splitlines()
    ), (
        f"BoschEBikeAPI.__init__ must set {_HOOK} (None until someone hooks in)"
    )


def test_a_refresh_followed_by_a_failing_request_reports_the_new_pair():
    # The Smart System gap: 401, refresh with rotation, then the retried
    # request (the activity list) fails with a 500.
    api = FakeApi(FakeSession([FakeResponse(401), FakeResponse(500)], _ROTATED))
    _, err = _run(api)
    assert isinstance(err, FakeResponseError) and err.status == 500, repr(err)
    assert api.seen == [("access-new", "refresh-new")], api.seen


def test_a_refresh_followed_by_a_network_error_reports_the_new_pair():
    api = FakeApi(FakeSession([FakeResponse(401), TimeoutError("gone")], _ROTATED))
    _, err = _run(api)
    assert isinstance(err, TimeoutError), repr(err)
    assert api.seen == [("access-new", "refresh-new")], api.seen


def test_a_refresh_with_a_good_retry_reports_the_pair_once():
    api = FakeApi(FakeSession([FakeResponse(401), FakeResponse(200, {"ok": 1})], _ROTATED))
    result, err = _run(api)
    assert err is None and result == {"ok": 1}, (result, err)
    assert api.seen == [("access-new", "refresh-new")], api.seen


def test_a_request_without_a_refresh_reports_nothing():
    api = FakeApi(FakeSession([FakeResponse(200, {"ok": 1})], _ROTATED))
    _run(api)
    assert api.seen == []


def test_a_rejected_refresh_reports_nothing():
    api = FakeApi(FakeSession([FakeResponse(401)], FakeResponse(400, None)))
    _, err = _run(api)
    assert err is not None
    assert api.seen == []


def test_a_failing_listener_does_not_fail_the_request():
    api = FakeApi(FakeSession([FakeResponse(401), FakeResponse(200, {"ok": 1})], _ROTATED))

    def boom():
        raise RuntimeError("entry write failed")

    setattr(api, _HOOK, boom)
    result, err = _run(api)
    assert err is None and result == {"ok": 1}, (result, err)
    assert api._refresh_token == "refresh-new"


def test_without_a_listener_the_refresh_still_works():
    api = FakeApi(FakeSession([FakeResponse(401), FakeResponse(200, {"ok": 1})], _ROTATED))
    setattr(api, _HOOK, None)
    result, err = _run(api)
    assert err is None and result == {"ok": 1}, (result, err)


def test_the_coordinator_hooks_its_token_write_into_the_client():
    # Covers every caller of the client at once: the Smart System, BES2 and
    # COBI polls (setup's first refresh included), the GPS/CSV buttons and
    # the track service.
    src = ast.unparse(_method(_COORD_CLASS, "__init__"))
    assert f"self.api.{_HOOK} = self._persist_refreshed_tokens" in src, (
        "the coordinator must hand _persist_refreshed_tokens to the client"
    )


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
