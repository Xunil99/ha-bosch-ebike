"""Standalone tests for oauth_error.rejection_reason - run with:
python3 tests/test_oauth_error.py

oauth_error.py imports nothing from Home Assistant or aiohttp, so it is loaded
directly.

Issue #98: a refresh token that Bosch rejects (or a Client-ID Bosch no longer
knows) used to surface as a plain HTTP error, so the setup retried forever and
Home Assistant never asked the user to sign in again. Only a rejection of the
login itself may start the re-authentication. A false alarm is the other half
of the risk: a Bosch hiccup must not send every user to the login page, so
what is NOT a rejection is pinned down here just as firmly.
"""
import ast
import importlib.util
import json
from pathlib import Path

_path = (
    Path(__file__).resolve().parent.parent
    / "custom_components" / "ha_bosch_ebike" / "oauth_error.py"
)
_spec = importlib.util.spec_from_file_location("oauth_error", _path)
oauth_error = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(oauth_error)
rejection_reason = oauth_error.rejection_reason


def _body(error=None, description=None):
    payload = {}
    if error is not None:
        payload["error"] = error
    if description is not None:
        payload["error_description"] = description
    return json.dumps(payload)


# --- what is a rejection ------------------------------------------------------------


def test_an_unknown_client_is_a_rejection():
    # What Bosch's Keycloak answers when the app is gone, 401 as reported.
    body = _body("invalid_client", "Invalid client or Invalid client credentials")
    assert rejection_reason(401, body) == (
        "invalid_client: Invalid client or Invalid client credentials"
    )


def test_a_dead_refresh_token_is_a_rejection():
    body = _body("invalid_grant", "Token is not active")
    assert rejection_reason(400, body) == "invalid_grant: Token is not active"


def test_every_oauth_code_for_an_invalid_grant_or_client_counts_on_a_400():
    for code in ("invalid_grant", "invalid_client", "unauthorized_client"):
        assert rejection_reason(400, _body(code)) == code, code


def test_a_401_is_a_rejection_whatever_the_body_says():
    assert rejection_reason(401, None) == "HTTP 401"
    assert rejection_reason(401, "") == "HTTP 401"
    assert rejection_reason(401, "<html>Unauthorized</html>") == "HTTP 401"
    assert rejection_reason(401, "null") == "HTTP 401"
    assert rejection_reason(401, "[1, 2]") == "HTTP 401"
    assert rejection_reason(401, _body("something_else")) == "something_else"


def test_the_description_is_kept_short_for_the_log():
    reason = rejection_reason(400, _body("invalid_grant", "x" * 500))
    assert reason == "invalid_grant: " + "x" * 120


# --- what is not a rejection ---------------------------------------------------------


def test_a_400_of_another_kind_is_not_a_rejection():
    # A malformed request is our bug or a hiccup, not a reason to ask the user.
    assert rejection_reason(400, _body("invalid_request", "Missing parameter")) is None
    assert rejection_reason(400, _body("invalid_scope")) is None
    assert rejection_reason(400, None) is None
    assert rejection_reason(400, "") is None
    assert rejection_reason(400, "<html>Bad Request</html>") is None
    assert rejection_reason(400, "null") is None


def test_an_error_code_that_is_not_text_is_not_a_rejection():
    assert rejection_reason(400, json.dumps({"error": 5})) is None
    assert rejection_reason(400, json.dumps({"error": ["invalid_grant"]})) is None


def test_failures_that_the_next_poll_may_survive_are_not_rejections():
    for status in (403, 404, 408, 429, 500, 502, 503, 504):
        assert rejection_reason(status, _body("invalid_grant")) is None, status
        assert rejection_reason(status, None) is None, status


def test_a_description_that_is_not_text_is_ignored():
    body = json.dumps({"error": "invalid_grant", "error_description": {"a": 1}})
    assert rejection_reason(400, body) == "invalid_grant"


def test_it_never_raises_on_odd_input():
    for status in (200, 400, 401, 500):
        for body in (None, "", "{", "\x00", "\ud83d", "[]", "123", '"text"', "{}"):
            rejection_reason(status, body)  # must not raise


def test_the_module_imports_nothing_that_needs_installing():
    # That is what lets this dependency-free suite load it.
    tree = ast.parse(_path.read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            imported.add((node.module or "").split(".")[0])
    assert imported <= {"__future__", "json"}, imported


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("ALL TESTS PASSED")
