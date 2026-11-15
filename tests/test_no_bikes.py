"""Standalone tests for no_bikes.py - run with: python3 tests/test_no_bikes.py

Issue #100: with a US account the login worked, but until the data sharing was
activated Bosch answered with 0 bikes and 0 rides and no error at all. It looks
exactly like a region block and nothing in Home Assistant said what was missing.
The integration now raises a repair issue while Bosch names no usable bike (and
for a 403 on the bike list, the other face of the same missing sharing) and
removes it as soon as a bike shows up.

no_bikes.py imports nothing from Home Assistant: the registry calls are passed
in, so these tests use plain fakes.
"""
import ast
import importlib.util
import json
from pathlib import Path

_PACKAGE = (
    Path(__file__).resolve().parent.parent / "custom_components" / "ha_bosch_ebike"
)
_spec = importlib.util.spec_from_file_location("no_bikes", _PACKAGE / "no_bikes.py")
no_bikes = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(no_bikes)


class Recorder:
    def __init__(self, fail=False):
        self.calls = []
        self.fail = fail

    def create(self):
        self.calls.append("create")
        if self.fail:
            raise RuntimeError("registry unavailable")

    def delete(self):
        self.calls.append("delete")
        if self.fail:
            raise RuntimeError("registry unavailable")


def _apply(bikes, fail=False):
    recorder = Recorder(fail)
    no_bikes.apply(bikes, create=recorder.create, delete=recorder.delete)
    return recorder.calls


def test_an_empty_list_raises_the_issue():
    assert _apply([]) == ["create"]


def test_no_answer_at_all_raises_the_issue():
    assert _apply(None) == ["create"]


def test_entries_without_a_usable_id_do_not_count_as_bikes():
    assert _apply([{}, {"id": ""}, {"id": None}, "bike", None, 7]) == ["create"]


def test_a_bike_clears_the_issue():
    assert _apply([{"id": "bike-1"}]) == ["delete"]


def test_one_usable_bike_among_unusable_entries_clears_the_issue():
    assert _apply([{}, {"id": "bike-1"}, None]) == ["delete"]


def test_a_failing_registry_never_breaks_the_poll():
    # Raising here would fail the whole coordinator update over a hint.
    assert _apply([], fail=True) == ["create"]
    assert _apply([{"id": "bike-1"}], fail=True) == ["delete"]


def test_the_issue_id_is_per_config_entry():
    assert no_bikes.issue_id("abc") == "no_bikes_abc"
    assert no_bikes.issue_id("abc") != no_bikes.issue_id("def")
    assert no_bikes.TRANSLATION_KEY == "no_bikes"


def test_every_language_carries_the_issue_text():
    # A repair issue whose translation is missing shows the bare key, so every
    # file needs title and description, and the title names the account.
    for name in ("strings", "translations/en", "translations/de", "translations/nl", "translations/cs"):
        issue = json.loads((_PACKAGE / f"{name}.json").read_text(encoding="utf-8"))["issues"]["no_bikes"]
        assert issue["title"].strip() and issue["description"].strip(), name
        assert "{account}" in issue["title"], name
        assert "{" not in issue["description"].replace("{account}", ""), name


def _method(tree, class_name, name):
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == class_name)
    return next(
        n for n in cls.body
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name
    )


def test_both_update_paths_report_the_bike_list():
    # test_activity_outage.py runs the Smart System poll; the eBike System 2 poll
    # cannot be run in this suite, so its one line is pinned from the source.
    tree = ast.parse((_PACKAGE / "coordinator.py").read_text(encoding="utf-8"))
    for name in ("_async_update_data", "_update_bes2"):
        method = _method(tree, "BoschEBikeCoordinator", name)
        calls = [
            n for n in ast.walk(method)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Attribute)
            and n.func.attr == "_sync_no_bikes_issue"
        ]
        assert calls, f"{name} does not report the bike list to the repair issue"


def test_the_issue_is_cleared_when_the_entry_is_removed():
    tree = ast.parse((_PACKAGE / "__init__.py").read_text(encoding="utf-8"))
    removers = [
        n for n in tree.body
        if isinstance(n, ast.AsyncFunctionDef) and n.name == "async_remove_entry"
    ]
    assert len(removers) == 1, "a deleted entry would leave its repair issue behind"
    source = ast.unparse(removers[0])
    assert "async_delete_issue" in source and "issue_id" in source


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
