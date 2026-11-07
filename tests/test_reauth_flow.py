"""Standalone tests for the re-authentication flow - run with:
python3 tests/test_reauth_flow.py

config_flow.py imports Home Assistant, which this dependency-free suite does
not have, so the real reauth methods of BoschEBikeConfigFlow are extracted from
its source and exec'd against stand-ins, the same AST approach the other tests
use for coordinator.py and api.py.

Issue #98: the Client-ID registered in the Data Act portal stopped existing at
Bosch ("Client not found"), and the re-authentication could not help because
its form had no field: it always logged in with the stored Client-ID again.
The flow now shows the Client-ID, lets the user replace it, refuses one that
another entry already uses, and updates the entry in place. The entry's other
data and its unique id have to come out right: data= alone would have thrown
away everything else stored in the entry, and the unique id is the Client-ID.
"""
import __future__
import ast
import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
_PACKAGE = _ROOT / "custom_components" / "ha_bosch_ebike"
_FLOW = _PACKAGE / "config_flow.py"
_TREE = ast.parse(_FLOW.read_text(encoding="utf-8"))

_CLASS = next(
    n for n in _TREE.body
    if isinstance(n, ast.ClassDef) and n.name == "BoschEBikeConfigFlow"
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
        f"BoschEBikeConfigFlow no longer defines {name} - update this test "
        "alongside the rename/removal"
    )
    return found


# --- stand-ins for what config_flow.py imports --------------------------------------


class _Required:
    def __init__(self, key, description=None):
        self.key = key
        self.description = description


class _Vol:
    Required = _Required

    @staticmethod
    def Schema(mapping):  # noqa: N802 - mirrors voluptuous
        return mapping


_ns: dict[str, Any] = {
    "Any": Any,
    "vol": _Vol,
    "CONF_CLIENT_ID": "client_id",
    "CONF_SYSTEM": "system",
    "DOMAIN": "ha_bosch_ebike",
    "SOURCE_REAUTH": "reauth",
    "SYSTEM_SMART": "smart",
    "ConfigFlowResult": dict,
}
_names = [
    "async_step_reauth",
    "async_step_reauth_confirm",
    "_used_by_another_entry",
    "async_oauth_create_entry",
]
exec(  # noqa: S102 - executing our own source, see the module docstring
    compile(
        ast.Module(body=[_method(n) for n in _names], type_ignores=[]),
        str(_FLOW),
        "exec",
        flags=__future__.annotations.compiler_flag,
        dont_inherit=True,
    ),
    _ns,
)


def entry(entry_id, client_id=None, unique_id=None, **more):
    data = {"client_id": client_id} if client_id else {}
    data.update(more)
    return SimpleNamespace(entry_id=entry_id, unique_id=unique_id, data=data)


class FakeFlow:
    async_step_reauth = _ns["async_step_reauth"]
    async_step_reauth_confirm = _ns["async_step_reauth_confirm"]
    _used_by_another_entry = _ns["_used_by_another_entry"]
    async_oauth_create_entry = _ns["async_oauth_create_entry"]

    _portal_url = "https://portal.example/app"

    def __init__(self, entries, reauth_entry, source="reauth", client_id="euda-old"):
        self.hass = SimpleNamespace(
            config_entries=SimpleNamespace(async_entries=lambda domain: list(entries))
        )
        self._reauth_entry = reauth_entry
        self.source = source
        self._client_id = client_id
        self._system = "smart"
        self.registered = []
        self.forms = []
        self.updates = []
        self.created = []

    def _get_reauth_entry(self):
        return self._reauth_entry

    def _register_impl(self, client_id):
        self.registered.append(client_id)

    async def async_step_pick_implementation(self):
        return {"type": "external", "client_id": self._client_id}

    def async_show_form(self, **kwargs):
        self.forms.append(kwargs)
        return {"type": "form", **kwargs}

    def async_update_reload_and_abort(self, target, **kwargs):
        self.updates.append((target, kwargs))
        return {"type": "abort", "reason": "reauth_successful"}

    def async_create_entry(self, **kwargs):
        self.created.append(kwargs)
        return {"type": "create_entry", **kwargs}


def _flow(entries=None, **kwargs):
    own = entry("own", "euda-old", "euda-old", access_token="old", battery_capacity_wh={"b1": 750})
    entries = [own] if entries is None else [own, *entries]
    return FakeFlow(entries, own, **kwargs), own


def _run(coro):
    return asyncio.run(coro)


# --- the form ---------------------------------------------------------------------------


def test_the_form_offers_the_stored_client_id():
    flow, _ = _flow()
    result = _run(flow.async_step_reauth_confirm())
    assert result["type"] == "form" and result["step_id"] == "reauth_confirm"
    (field,) = result["data_schema"].keys()
    assert field.key == "client_id"
    assert field.description == {"suggested_value": "euda-old"}
    assert result["errors"] == {}
    assert result["description_placeholders"] == {"portal_url": "https://portal.example/app"}


def test_reauth_starts_from_the_stored_client_id_and_system():
    flow, _ = _flow(client_id=None)
    result = _run(flow.async_step_reauth({"client_id": "euda-x", "system": "bes2"}))
    assert flow._client_id == "euda-x" and flow._system == "bes2"
    assert result["type"] == "form" and result["data_schema"]
    (field,) = result["data_schema"].keys()
    assert field.description == {"suggested_value": "euda-x"}


# --- submitting it -----------------------------------------------------------------------


def test_submitting_the_stored_client_id_continues_with_it():
    flow, _ = _flow()
    result = _run(flow.async_step_reauth_confirm({"client_id": "euda-old"}))
    assert flow.registered == ["euda-old"]
    assert result == {"type": "external", "client_id": "euda-old"}


def test_a_new_client_id_replaces_the_stored_one():
    flow, _ = _flow()
    result = _run(flow.async_step_reauth_confirm({"client_id": "  euda-new  "}))
    assert flow.registered == ["euda-new"], "stripped, and the login uses the new one"
    assert flow._client_id == "euda-new"
    assert result["client_id"] == "euda-new"


def test_a_blank_field_falls_back_to_the_stored_client_id():
    flow, _ = _flow()
    _run(flow.async_step_reauth_confirm({"client_id": "   "}))
    assert flow.registered == ["euda-old"]


def test_a_client_id_of_another_entry_is_refused():
    other = entry("other", "euda-other", "euda-other")
    flow, _ = _flow([other])
    result = _run(flow.async_step_reauth_confirm({"client_id": "euda-other"}))
    assert result["type"] == "form" and result["errors"] == {"base": "already_configured"}
    assert flow.registered == [] and flow._client_id == "euda-old"
    (field,) = result["data_schema"].keys()
    assert field.description == {"suggested_value": "euda-other"}, "what was typed stays in the field"


def test_an_older_entry_without_unique_id_still_counts():
    # Entries from the first manual flow keep the Client-ID in their data only.
    older = entry("older", "euda-other", None)
    flow, _ = _flow([older])
    result = _run(flow.async_step_reauth_confirm({"client_id": "euda-other"}))
    assert result["errors"] == {"base": "already_configured"}


def test_an_entry_known_only_by_its_unique_id_still_counts():
    older = entry("older", None, "euda-other")
    flow, _ = _flow([older])
    result = _run(flow.async_step_reauth_confirm({"client_id": "euda-other"}))
    assert result["errors"] == {"base": "already_configured"}


def test_the_entry_being_repaired_never_conflicts_with_itself():
    flow, _ = _flow()
    result = _run(flow.async_step_reauth_confirm({"client_id": "euda-old"}))
    assert result["type"] == "external"


# --- finishing the login -------------------------------------------------------------------


def test_the_finished_login_updates_the_entry_in_place_and_keeps_its_other_data():
    flow, own = _flow(client_id="euda-new")
    result = _run(
        flow.async_oauth_create_entry({"token": {"access_token": "a2", "refresh_token": "r2"}})
    )
    assert result["reason"] == "reauth_successful"
    ((target, kwargs),) = flow.updates
    assert target is own
    assert kwargs["unique_id"] == "euda-new", "the unique id is the Client-ID"
    assert kwargs["data"] == {
        "client_id": "euda-new",
        "system": "smart",
        "access_token": "a2",
        "refresh_token": "r2",
        "battery_capacity_wh": {"b1": 750},
    }
    assert flow.created == []


def test_the_old_data_object_is_not_modified():
    flow, own = _flow(client_id="euda-new")
    before = dict(own.data)
    _run(flow.async_oauth_create_entry({"token": {"access_token": "a2", "refresh_token": "r2"}}))
    assert own.data == before


def test_a_new_entry_is_still_created_as_before():
    flow, _ = _flow(source="user", client_id="euda-fresh")
    _run(flow.async_oauth_create_entry({"token": {"access_token": "a", "refresh_token": "r"}}))
    assert flow.updates == []
    assert flow.created == [
        {
            "title": "Bosch eBike",
            "data": {
                "client_id": "euda-fresh",
                "system": "smart",
                "access_token": "a",
                "refresh_token": "r",
            },
        }
    ]


# --- the texts ---------------------------------------------------------------------------------

_TEXT_FILES = ["strings.json"] + [f"translations/{lang}.json" for lang in ("en", "de", "nl", "cs")]


def _config(name):
    return json.loads((_PACKAGE / name).read_text(encoding="utf-8"))["config"]


def test_every_language_has_the_client_id_field_and_the_duplicate_error():
    for name in _TEXT_FILES:
        config = _config(name)
        step = config["step"]["reauth_confirm"]
        assert step["data"] == {"client_id": config["step"]["credentials"]["data"]["client_id"]}, name
        assert config["error"]["already_configured"].strip(), name


def test_every_reauth_description_keeps_the_portal_link_and_names_the_bosch_message():
    for name in _TEXT_FILES:
        description = _config(name)["step"]["reauth_confirm"]["description"]
        assert "{portal_url}" in description, name
        assert "Client not found" in description, f"{name}: the message Bosch shows is not translated"


def test_the_translations_have_the_same_reauth_keys_as_strings_json():
    reference = _config("strings.json")
    for name in _TEXT_FILES[1:]:
        config = _config(name)
        assert set(config["step"]["reauth_confirm"]) == set(reference["step"]["reauth_confirm"]), name
        assert set(config["error"]) == set(reference["error"]), name


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("ALL TESTS PASSED")
