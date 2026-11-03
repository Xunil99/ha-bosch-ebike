"""Standalone tests for token_info.token_scope - run with:
python3 tests/test_token_info.py

token_info.py imports nothing from Home Assistant, so it is loaded directly.
It exists for one log line (issue #95): when Bosch refuses a request that used
to work, whether the access token carries the activity scopes is the first
thing to ask. It must never raise, because it runs while an error is already
being reported.
"""
import base64
import importlib.util
import json
from pathlib import Path

_path = (
    Path(__file__).resolve().parent.parent
    / "custom_components" / "ha_bosch_ebike" / "token_info.py"
)
_spec = importlib.util.spec_from_file_location("token_info", _path)
token_info = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(token_info)
token_scope = token_info.token_scope


def _b64(obj) -> str:
    raw = json.dumps(obj).encode() if not isinstance(obj, bytes) else obj
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _jwt(claims) -> str:
    return f"{_b64({'alg': 'RS256'})}.{_b64(claims)}.signature"


def test_the_scope_claim_is_returned():
    scope = "openid activity:summaries:read activity:details:read offline_access"
    assert token_scope(_jwt({"scope": scope, "sub": "x"})) == scope


def test_payloads_of_every_padding_length_decode():
    # base64 without padding comes in three shapes; all of them must work.
    for filler in ("", "a", "ab", "abc", "abcd", "abcde"):
        claims = {"scope": "openid", "x": filler}
        assert token_scope(_jwt(claims)) == "openid", filler


def test_a_token_without_a_scope_claim_gives_none():
    assert token_scope(_jwt({"sub": "x"})) is None


def test_an_empty_or_non_text_scope_gives_none():
    assert token_scope(_jwt({"scope": ""})) is None
    assert token_scope(_jwt({"scope": ["openid"]})) is None
    assert token_scope(_jwt({"scope": 5})) is None


def test_anything_that_is_not_a_jwt_gives_none_and_never_raises():
    for bad in (
        None,
        "",
        "not a token",
        "a.b",
        "a.!!!.c",
        f"a.{_b64(b'not json')}.c",
        f"a.{_b64(['a', 'list'])}.c",
        f"a.{_b64('a string')}.c",
        12345,
    ):
        assert token_scope(bad) is None, bad


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("ALL TESTS PASSED")
