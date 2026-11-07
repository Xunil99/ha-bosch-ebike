"""Standalone tests for a rejected refresh token - run with:
python3 tests/test_refresh_token_rejection.py

api.py imports aiohttp, which this dependency-free suite does not have, so the
real refresh_access_token is extracted from its source and exec'd against
stand-ins, the same AST approach the other API tests use.

Issue #98: when Bosch rejected the refresh token (401, or 400 invalid_grant),
refresh_access_token() raised the ClientResponseError that raise_for_status()
makes of it. The coordinator only turns an AuthError into the request for a new
sign-in, so the setup stayed in "setup error, will retry" forever. The point of
these tests is that exactly the rejection becomes an AuthError and nothing
else does: a server error, a rate limit or a network failure is retried, not
reported to the user as a lost login.
"""
import ast
import asyncio
import importlib.util
import json
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
_API = _ROOT / "custom_components" / "ha_bosch_ebike" / "api.py"
_TREE = ast.parse(_API.read_text(encoding="utf-8"))

_CLASS = next(
    n for n in _TREE.body
    if isinstance(n, ast.ClassDef) and n.name == "BoschEBikeAPI"
)

_spec = importlib.util.spec_from_file_location(
    "oauth_error", _ROOT / "custom_components" / "ha_bosch_ebike" / "oauth_error.py"
)
oauth_error = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(oauth_error)

TOKEN_URL = "https://auth.example/token"


class AuthError(Exception):
    pass


class FakeResponseError(Exception):
    """aiohttp.ClientResponseError as far as refresh_access_token sees it."""

    def __init__(self, status):
        super().__init__(f"{status}, message='x'")
        self.status = status


class FakeResponse:
    def __init__(self, status, body="", payload=None, text_error=None):
        self.status = status
        self._body = body
        self._payload = payload
        self._text_error = text_error

    async def text(self):
        if self._text_error:
            raise self._text_error
        return self._body

    async def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status >= 400:
            raise FakeResponseError(self.status)


class _Post:
    def __init__(self, response, error):
        self._response = response
        self._error = error

    async def __aenter__(self):
        if self._error:
            raise self._error
        return self._response

    async def __aexit__(self, *exc):
        return False


class FakeSession:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.posts = []

    def post(self, url, data=None, timeout=None):
        self.posts.append((url, dict(data or {}), timeout))
        return _Post(self.response, self.error)


_node = next(
    n for n in _CLASS.body
    if isinstance(n, ast.AsyncFunctionDef) and n.name == "refresh_access_token"
)
_ns: dict[str, Any] = {
    "Any": Any,
    "AuthError": AuthError,
    "TOKEN_URL": TOKEN_URL,
    "rejection_reason": oauth_error.rejection_reason,
}
exec(  # noqa: S102 - executing our own source, see the module docstring
    compile(
        ast.Module(body=[_node], type_ignores=[]),
        str(_API),
        "exec",
        flags=__import__("__future__").annotations.compiler_flag,
        dont_inherit=True,
    ),
    _ns,
)


class FakeApi:
    refresh_access_token = _ns["refresh_access_token"]
    _TIMEOUT = "timeout"

    def __init__(self, session, refresh_token="old-refresh"):
        self._session = session
        self._client_id = "euda-test"
        self._access_token = "old-access"
        self._refresh_token = refresh_token


def _refresh(response=None, error=None, refresh_token="old-refresh"):
    session = FakeSession(response, error)
    api = FakeApi(session, refresh_token)
    try:
        result = asyncio.run(api.refresh_access_token())
        return api, session, result, None
    except BaseException as err:  # noqa: BLE001 - the tests inspect what came out
        return api, session, None, err


def _error_of(response=None, error=None):
    return _refresh(response, error)[3]


# --- the rejection starts the re-authentication ---------------------------------------


def test_an_unknown_client_on_a_401_is_an_auth_error():
    err = _error_of(
        FakeResponse(401, json.dumps({"error": "invalid_client", "error_description": "Client not found"}))
    )
    assert isinstance(err, AuthError), repr(err)
    assert "invalid_client" in str(err) and "Client not found" in str(err)


def test_a_401_without_a_readable_body_is_still_an_auth_error():
    err = _error_of(FakeResponse(401, text_error=RuntimeError("connection lost")))
    assert isinstance(err, AuthError), repr(err)
    assert "HTTP 401" in str(err)


def test_a_401_with_an_html_body_is_an_auth_error():
    err = _error_of(FakeResponse(401, "<html>Unauthorized</html>"))
    assert isinstance(err, AuthError), repr(err)


def test_a_dead_refresh_token_on_a_400_is_an_auth_error():
    err = _error_of(
        FakeResponse(400, json.dumps({"error": "invalid_grant", "error_description": "Token is not active"}))
    )
    assert isinstance(err, AuthError), repr(err)
    assert "invalid_grant" in str(err)


# --- everything else is retried, not reported as a lost login ----------------------------


def test_a_400_of_another_kind_stays_a_status_error():
    for body in (json.dumps({"error": "invalid_request"}), "<html>Bad Request</html>", ""):
        err = _error_of(FakeResponse(400, body))
        assert isinstance(err, FakeResponseError) and err.status == 400, (body, repr(err))


def test_rate_limits_and_server_errors_stay_status_errors():
    for status in (403, 404, 429, 500, 502, 503):
        err = _error_of(FakeResponse(status, json.dumps({"error": "invalid_grant"})))
        assert isinstance(err, FakeResponseError) and err.status == status, (status, repr(err))


def test_network_errors_pass_through_unchanged():
    boom = TimeoutError("no answer")
    assert _error_of(error=boom) is boom


# --- the working case and the request itself --------------------------------------------


def test_a_good_answer_replaces_the_access_token_and_a_new_refresh_token():
    api, _, result, err = _refresh(
        FakeResponse(200, payload={"access_token": "new-access", "refresh_token": "new-refresh"})
    )
    assert err is None
    assert api._access_token == "new-access" and api._refresh_token == "new-refresh"
    assert result["access_token"] == "new-access"


def test_a_good_answer_without_a_new_refresh_token_keeps_the_old_one():
    api, _, _, err = _refresh(FakeResponse(200, payload={"access_token": "new-access"}))
    assert err is None
    assert api._access_token == "new-access" and api._refresh_token == "old-refresh"


def test_the_request_is_a_refresh_grant_for_the_client():
    _, session, _, _ = _refresh(FakeResponse(200, payload={"access_token": "a"}))
    assert session.posts == [
        (
            TOKEN_URL,
            {"grant_type": "refresh_token", "client_id": "euda-test", "refresh_token": "old-refresh"},
            "timeout",
        )
    ]


def test_without_a_refresh_token_nothing_is_requested():
    api, session, _, err = _refresh(FakeResponse(200, payload={"access_token": "a"}), refresh_token=None)
    assert isinstance(err, AuthError) and session.posts == []


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("ALL TESTS PASSED")
