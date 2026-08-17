"""Card-settings allow-list parity — run with:
python3 tests/test_card_settings_allowlist.py

The shared card-settings store has two independent lists of keys that must
stay in sync: the frontend's SHARED_SETTING_KEYS array (bosch-ebike-map-card.js,
consulted by saveCardSetting()/readCardSetting() before a key is even sent
over the wire) and the backend's `allowed` set inside ws_set_card_settings()
(__init__.py, the actual gate that decides whether a write is persisted).

Adding a new shared setting to the frontend list alone compiles and runs
without any error - the WS call succeeds, callWS() resolves, the optimistic
UI update looks fine - but the backend silently drops the key ("if key not
in allowed: continue") and the value never actually persists. That is
exactly what happened with "show_weather": added to SHARED_SETTING_KEYS when
the weather-overlay feature shipped, but never added to the backend's
`allowed` set, so every attempt to turn the effect off (editor field or the
later on-card toggle chip) silently failed - "on" is just what an absent key
defaults to.

Both files are read as plain text (no Home Assistant import needed, matching
the rest of this dependency-free suite) and the two key sets are extracted
with a small regex - good enough for two literal collections that are never
built dynamically.
"""
import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_JS = _ROOT / "custom_components" / "ha_bosch_ebike" / "www" / "bosch-ebike-map-card.js"
_INIT = _ROOT / "custom_components" / "ha_bosch_ebike" / "__init__.py"


def _extract_string_literals(text: str) -> set[str]:
    """Every "..." string literal in a snippet of source text."""
    return set(re.findall(r'"([^"\\]*(?:\\.[^"\\]*)*)"', text))


def _frontend_shared_keys() -> set[str]:
    src = _JS.read_text(encoding="utf-8")
    m = re.search(r"const SHARED_SETTING_KEYS\s*=\s*\[(.*?)\];", src, re.S)
    assert m, "SHARED_SETTING_KEYS array not found in bosch-ebike-map-card.js"
    return _extract_string_literals(m.group(1))


def _backend_allowed_keys() -> set[str]:
    src = _INIT.read_text(encoding="utf-8")
    m = re.search(r"async def ws_set_card_settings.*?allowed\s*=\s*\{(.*?)\}\s*\n", src, re.S)
    assert m, "`allowed` set not found in ws_set_card_settings()"
    return _extract_string_literals(m.group(1))


def test_every_frontend_shared_key_is_backend_allowed():
    frontend_keys = _frontend_shared_keys()
    backend_keys = _backend_allowed_keys()
    missing = frontend_keys - backend_keys
    assert not missing, (
        "Key(s) in the frontend's SHARED_SETTING_KEYS are missing from the "
        "backend's `allowed` set in ws_set_card_settings() and will silently "
        f"fail to persist: {sorted(missing)}"
    )


if __name__ == "__main__":
    test_every_frontend_shared_key_is_backend_allowed()
    print("OK - card-settings allow-list is in sync")
