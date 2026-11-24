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
import importlib.util
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


class _Optional(_Required):
    pass


class _Vol:
    Required = _Required
    Optional = _Optional

    @staticmethod
    def Schema(mapping):  # noqa: N802 - mirrors voluptuous
        return mapping


# entry_title.py imports nothing from Home Assistant, so the real function is loaded.
_title_spec = importlib.util.spec_from_file_location("entry_title", _PACKAGE / "entry_title.py")
_entry_title = importlib.util.module_from_spec(_title_spec)
_title_spec.loader.exec_module(_entry_title)

# const.py imports nothing either; the auth table and the unique id helper are real.
_const_spec = importlib.util.spec_from_file_location("const", _PACKAGE / "const.py")
const = importlib.util.module_from_spec(_const_spec)
_const_spec.loader.exec_module(const)

_ns: dict[str, Any] = {
    "unique_title": _entry_title.unique_title,
    "authorize_params": const.authorize_params,
    "entry_unique_id": const.entry_unique_id,
    "CONF_KC_IDP_HINT": const.CONF_KC_IDP_HINT,
    "SYSTEM_COBI": const.SYSTEM_COBI,
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
    "async_step_credentials",
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


def entry(entry_id, client_id=None, unique_id=None, title="Bosch eBike", **more):
    data = {"client_id": client_id} if client_id else {}
    data.update(more)
    return SimpleNamespace(entry_id=entry_id, unique_id=unique_id, title=title, data=data)


class FakeFlow:
    async_step_credentials = _ns["async_step_credentials"]
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
        self._kc_idp_hint = None
        self.show_advanced_options = False
        self._entries = entries
        self.unique_id = None
        self.registered = []
        self.forms = []
        self.updates = []
        self.created = []

    def _get_reauth_entry(self):
        return self._reauth_entry

    def _register_impl(self, client_id):
        self.registered.append(client_id)

    async def async_set_unique_id(self, unique_id):
        self.unique_id = unique_id

    def _abort_if_unique_id_configured(self):
        if any(e.unique_id == self.unique_id for e in self._entries):
            raise _Abort("already_configured")

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


class _Abort(Exception):
    pass


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
    # Another account is already set up, so the new one gets the next free title.
    flow, _ = _flow(source="user", client_id="euda-fresh")
    _run(flow.async_oauth_create_entry({"token": {"access_token": "a", "refresh_token": "r"}}))
    assert flow.updates == []
    assert flow.created == [
        {
            "title": "Bosch eBike 2",
            "data": {
                "client_id": "euda-fresh",
                "system": "smart",
                "access_token": "a",
                "refresh_token": "r",
            },
        }
    ]


def test_the_first_account_keeps_the_plain_title_and_a_third_takes_the_next_number():
    # Nothing set up yet: "Bosch eBike". Two set up already: "Bosch eBike 3".
    flow = FakeFlow([], None, source="user", client_id="euda-first")
    _run(flow.async_oauth_create_entry({"token": {"access_token": "a", "refresh_token": "r"}}))
    assert flow.created[0]["title"] == "Bosch eBike"
    others = [entry("a", "c1", "c1"), entry("b", "c2", "c2", title="Bosch eBike 2")]
    flow = FakeFlow(others, None, source="user", client_id="euda-third")
    _run(flow.async_oauth_create_entry({"token": {"access_token": "a", "refresh_token": "r"}}))
    assert flow.created[0]["title"] == "Bosch eBike 3"


def test_a_renamed_account_does_not_use_up_the_default_title():
    flow = FakeFlow([entry("a", "c1", "c1", title="Sam")], None, source="user", client_id="euda-x")
    _run(flow.async_oauth_create_entry({"token": {"access_token": "a", "refresh_token": "r"}}))
    assert flow.created[0]["title"] == "Bosch eBike"


# --- COBI: a third system on the same login -----------------------------------------


def _cobi_flow(entries, **kwargs):
    flow = FakeFlow(entries, None, source="user", **kwargs)
    flow._system = "cobi"
    return flow


def test_cobi_can_be_added_next_to_a_smart_system_entry_with_the_same_client_id():
    # A SingleKey ID user registers one portal app and uses it for both.
    smart = entry("smart", "euda-1", "euda-1", system="smart_system")
    flow = _cobi_flow([smart], client_id=None)
    result = _run(flow.async_step_credentials({"client_id": " euda-1 "}))
    assert flow.unique_id == "cobi:euda-1"
    assert flow.registered == ["euda-1"] and result["type"] == "external"


def test_a_second_cobi_entry_with_the_same_client_id_is_refused():
    other = entry("other", "euda-1", "cobi:euda-1", system="cobi")
    flow = _cobi_flow([other], client_id=None)
    try:
        _run(flow.async_step_credentials({"client_id": "euda-1"}))
    except _Abort as err:
        assert str(err) == "already_configured"
    else:
        raise AssertionError("a duplicate COBI entry must abort")


def test_smart_and_bes2_keep_the_plain_client_id_as_unique_id():
    for system in ("smart_system", "ebike_system_2"):
        flow = FakeFlow([], None, source="user", client_id=None)
        flow._system = system
        _run(flow.async_step_credentials({"client_id": "euda-1"}))
        assert flow.unique_id == "euda-1", system


def test_the_login_hint_field_is_offered_only_for_cobi_in_advanced_mode():
    def fields(system, advanced):
        flow = FakeFlow([], None, source="user", client_id=None)
        flow._system = system
        flow.show_advanced_options = advanced
        result = _run(flow.async_step_credentials())
        return [f.key for f in result["data_schema"]]

    assert fields("cobi", True) == ["client_id", "kc_idp_hint"]
    assert fields("cobi", False) == ["client_id"]
    assert fields("smart_system", True) == ["client_id"]


def test_a_typed_login_hint_is_kept_and_stored_with_the_entry():
    flow = _cobi_flow([], client_id=None)
    flow.show_advanced_options = True
    _run(flow.async_step_credentials({"client_id": "euda-1", "kc_idp_hint": " singlekey "}))
    assert flow._kc_idp_hint == "singlekey"
    _run(flow.async_oauth_create_entry({"token": {"access_token": "a", "refresh_token": "r"}}))
    (created,) = flow.created
    assert created["title"] == "Bosch COBI"
    assert created["data"]["system"] == "cobi"
    assert created["data"]["kc_idp_hint"] == "singlekey"


def test_a_cobi_entry_without_hint_stores_none():
    flow = _cobi_flow([], client_id="euda-1")
    _run(flow.async_oauth_create_entry({"token": {"access_token": "a", "refresh_token": "r"}}))
    assert "kc_idp_hint" not in flow.created[0]["data"]
    flow = FakeFlow([], None, source="user", client_id="euda-1")
    _run(flow.async_oauth_create_entry({"token": {"access_token": "a", "refresh_token": "r"}}))
    assert "kc_idp_hint" not in flow.created[0]["data"], "Smart System entries look as before"


def test_the_reauth_of_a_cobi_entry_does_not_find_itself_or_the_smart_entry():
    own = entry("own", "euda-1", "cobi:euda-1", system="cobi", kc_idp_hint="x")
    smart = entry("smart", "euda-1", "euda-1", system="smart_system")
    flow = FakeFlow([own, smart], own, client_id=None)
    _run(flow.async_step_reauth(dict(own.data)))
    assert flow._system == "cobi" and flow._kc_idp_hint == "x", "the stored hint is used again"
    result = _run(flow.async_step_reauth_confirm({"client_id": "euda-1"}))
    assert result["type"] == "external", result


def test_the_reauth_of_a_cobi_entry_refuses_another_cobi_entrys_client_id():
    own = entry("own", "euda-1", "cobi:euda-1", system="cobi")
    other = entry("other", "euda-2", "cobi:euda-2", system="cobi")
    flow = FakeFlow([own, other], own, client_id=None)
    _run(flow.async_step_reauth(dict(own.data)))
    result = _run(flow.async_step_reauth_confirm({"client_id": "euda-2"}))
    assert result["errors"] == {"base": "already_configured"}


def test_the_reauth_of_a_smart_entry_is_not_blocked_by_a_cobi_entry():
    own = entry("own", "euda-1", "euda-1", system="smart_system")
    cobi_entry = entry("cobi", "euda-2", "cobi:euda-2", system="cobi")
    flow = FakeFlow([own, cobi_entry], own, client_id=None)
    _run(flow.async_step_reauth(dict(own.data)))
    result = _run(flow.async_step_reauth_confirm({"client_id": "euda-2"}))
    assert result["type"] == "external", "a COBI entry does not block the Smart System"


def test_the_finished_cobi_reauth_keeps_the_prefixed_unique_id():
    own = entry("own", "euda-1", "cobi:euda-1", system="cobi")
    flow = FakeFlow([own], own, client_id="euda-9")
    flow._system = "cobi"
    _run(flow.async_oauth_create_entry({"token": {"access_token": "a", "refresh_token": "r"}}))
    ((_, kwargs),) = flow.updates
    assert kwargs["unique_id"] == "cobi:euda-9"


# --- the authorize parameters ------------------------------------------------------------


def test_the_authorize_parameters_per_system():
    assert const.authorize_params("smart_system") == {"scope": "openid"}
    assert const.authorize_params("ebike_system_2") == {"scope": "openid", "kc_idp_hint": "ebike-connect"}
    assert const.authorize_params("cobi") == {"scope": "openid offline_access"}
    assert const.authorize_params("cobi", " my-idp ") == {"scope": "openid offline_access", "kc_idp_hint": "my-idp"}
    assert const.authorize_params("unknown") == {"scope": "openid"}


def test_the_pkce_implementation_reads_the_table():
    src = _FLOW.read_text(encoding="utf-8")
    assert "authorize_params(" in src
    assert "BES2_KC_IDP_HINT if" not in src, "no hint chosen inline any more"


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
