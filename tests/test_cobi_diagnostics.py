"""The diagnostics file of a COBI account - run with:
python3 tests/test_cobi_diagnostics.py

Issue #101 promises the tester that the diagnostics file holds field names and
counts only: no positions, no serial numbers, no timestamps. diagnostics.py
imports Home Assistant, so its function is extracted from the source and
exec'd against stand-ins; cobi.py and token_info.py are loaded for real.

The check scans the whole output, not only for the values of the test data:
generic fields (an error text with Bosch's reply, an "error since") could
carry a time or an id just as well.
"""
import __future__
import ast
import asyncio
import base64
import importlib.util
import json
import re
from pathlib import Path
from types import SimpleNamespace
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
_PKG = _ROOT / "custom_components" / "ha_bosch_ebike"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, _PKG / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


cobi = _load("cobi")
token_info = _load("token_info")
const = _load("const")

_DIAG = _PKG / "diagnostics.py"
_TREE = ast.parse(_DIAG.read_text(encoding="utf-8"))


def _redact(data, to_redact):
    """async_redact_data as far as this test needs it."""
    if isinstance(data, dict):
        return {k: "**REDACTED**" if k in to_redact else _redact(v, to_redact) for k, v in data.items()}
    if isinstance(data, list):
        return [_redact(v, to_redact) for v in data]
    return data


_ns: dict[str, Any] = {
    "Any": Any,
    "async_redact_data": _redact,
    "summarize_attribution": lambda *a: {"activities": 0},
    "DOMAIN": "ha_bosch_ebike",
    "cobi": cobi,
    "token_type": token_info.token_type,
    "authorize_params": const.authorize_params,
    "CONF_KC_IDP_HINT": const.CONF_KC_IDP_HINT,
    "CONF_SYSTEM": const.CONF_SYSTEM,
}
_nodes = [
    n for n in _TREE.body
    if isinstance(n, (ast.Assign, ast.AsyncFunctionDef, ast.FunctionDef))
]
exec(  # noqa: S102 - executing our own source
    compile(
        ast.Module(body=_nodes, type_ignores=[]),
        str(_DIAG),
        "exec",
        flags=__future__.annotations.compiler_flag,
        dont_inherit=True,
    ),
    _ns,
)


def _jwt(claims):
    body = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=")
    return f"eyJhbGciOiJub25lIn0.{body}.sig"


SERIAL = "24173107182521"
RAW_HUBS = [
    {"serialNumber": SERIAL, "partNumber": "8017", "role": "OWNER",
     "activatedAt": "2021-06-04T10:23:12.000Z"},
    {"serialNumber": "11112222333344", "partNumber": "8017", "role": "GUEST",
     "activatedAt": "2022-01-01T08:00:00.000Z"},
]
RAW_ACTS = [
    {"id": "act0000000000001", "startTime": "2026-11-20T10:00:00.000Z",
     "endTime": "2026-11-20T11:00:00.000Z", "totalDistance": 15000,
     "bikeType": "ELECTRIC_25", "elevationGain": 120, "avgSpeed": 18.0,
     "maxSpeed": 31.5, "durationWithoutStops": 3000},
    {"id": "act0000000000002", "startTime": "2026-11-21T10:00:00.000Z",
     "endTime": "2026-11-21T11:00:00.000Z", "totalDistance": 9000,
     "bikeType": "BIOBIKE", "elevationGain": 40, "avgSpeed": 12.0,
     "maxSpeed": 22.0, "durationWithoutStops": None},
]
ERROR = (
    "ClientResponseError: 500, message='Internal Server Error', "
    "url='https://api.bosch-ebike.com/cobi/v1/activities' (Bosch replied: "
    '{"timestamp":"2026-11-24T09:12:33.123Z","traceId":"98765432123456789"})'
)


NOW = __import__("datetime").datetime(2026, 11, 24, 10, 0, tzinfo=__import__("datetime").timezone.utc)
HUB_REPLY = (
    '{"errors":[{"code":400,"title":"BAD_REQUEST","detail":"Error"}],'
    '"timestamp":"2026-11-24T09:12:33.123Z","traceId":"98765432123456789"}'
)
STATUSES = {
    "hubs": cobi.fetch_result(SimpleNamespace(status=400, body=HUB_REPLY)) | {
        "at": NOW - __import__("datetime").timedelta(minutes=12)},
    "activities": cobi.fetch_result(None) | {"at": NOW},
}


def _coordinator(error=ERROR):
    unit, _ = cobi.detect_duration_unit(RAW_ACTS)
    acts = [cobi.normalize_activity(a, unit) for a in RAW_ACTS]
    hubs = [cobi.normalize_hub(h) for h in RAW_HUBS]
    data = {
        "bikes": [], "cobi_hubs": hubs, "all_activities": acts,
        "latest_activity": acts[0], "activity_consumption": {}, "maintenance": {},
    }
    api = SimpleNamespace(
        access_token_scope="openid offline_access",
        refresh_token=_jwt({"typ": "Offline", "exp": 0, "sid": "abc"}),
        service_book_version=None,
    )
    return SimpleNamespace(
        is_cobi=True,
        data=data,
        api=api,
        last_update_success=True,
        activities_error=error,
        activities_error_since=None,
        manual_activity_bike={},
        # The coordinator method merges both; see BoschEBikeCoordinator.cobi_diagnostics.
        cobi_diagnostics=lambda: {
            **cobi.diagnostics_summary(RAW_HUBS, RAW_ACTS),
            "fetch_status": cobi.fetch_status_summary(STATUSES, NOW),
        },
    )


def _diagnostics(coordinator, entry_data=None):
    entry = SimpleNamespace(
        entry_id="ENTRY1",
        data=entry_data or {"client_id": "euda-1", "system": "cobi",
                            "access_token": "a", "refresh_token": "r"},
        options={},
    )
    hass = SimpleNamespace(data={"ha_bosch_ebike": {"ENTRY1": coordinator}})
    return asyncio.run(_ns["async_get_config_entry_diagnostics"](hass, entry))


def test_the_cobi_block_has_the_planned_fields():
    d = _diagnostics(_coordinator())["coordinator"]
    assert d["system"] == "cobi"
    assert d["hub_count"] == 2 and d["hub_roles"] == {"OWNER": 1, "GUEST": 1}
    assert d["activity_count"] == 2
    assert "durationWithoutStops" in d["activity_fields"]
    assert d["null_counts"]["durationWithoutStops"] == 1
    assert d["bike_type_counts"] == {"ELECTRIC_25": 1, "BIOBIKE": 1}
    assert d["duration_unit"]["verdict"] == "s"
    assert d["estimated_durations"] == 1
    assert d["scope_granted"] == "openid offline_access"
    assert d["refresh_token_type"] == "Offline"
    assert d["kc_idp_hint_used"] is None
    assert "500" in d["activities_error"], "the status stays readable"
    assert "bikes" not in d and "latest_activity" not in d, "the generic dump is replaced"
    hubs = d["fetch_status"]["hubs"]
    assert hubs["result"] == 400 and "BAD_REQUEST" in hubs["reply"] and hubs["minutes_ago"] == 12
    assert d["fetch_status"]["activities"] == {"result": "ok", "reply": None, "minutes_ago": 0}


def test_a_stored_hint_is_reported():
    d = _diagnostics(
        _coordinator(),
        {"client_id": "x", "system": "cobi", "kc_idp_hint": "singlekey"},
    )["coordinator"]
    assert d["kc_idp_hint_used"] == "singlekey"


def test_the_file_contains_no_value_serial_id_or_time():
    text = json.dumps(_diagnostics(_coordinator()))
    for value in (SERIAL, "11112222333344", "8017", "act0000000000001", "euda-1"):
        assert value not in text, f"{value!r} leaked"
    assert not re.search(r"\d{4}-\d{2}-\d{2}", text), "no dates or timestamps"
    assert not re.search(r"\d{2}:\d{2}:\d{2}", text), "no times"
    assert not re.search(r"\d{6,}", text), "no long digit strings"
    assert "lat" not in json.loads(text)["coordinator"], "no positions"


def test_the_smart_system_dump_is_unchanged_for_other_systems():
    coordinator = _coordinator()
    coordinator.is_cobi = False
    coordinator.data["bikes"] = [{"id": "b1", "serialNumber": "S"}]
    d = _diagnostics(coordinator)["coordinator"]
    assert d["bike_count"] == 1 and d["bikes"][0]["serialNumber"] == "**REDACTED**"
    assert "system" not in d


def test_redaction_also_covers_the_cobi_keys():
    assert {"serial", "cobi_hubs"} <= _ns["TO_REDACT"]


def test_the_refresh_token_type_is_read_without_trusting_it():
    assert token_info.token_type(_jwt({"typ": "Refresh"})) == "Refresh"
    assert token_info.token_type(_jwt({"typ": "something else"})) == "other"
    assert token_info.token_type("opaque") is None
    assert token_info.token_type(None) is None


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
