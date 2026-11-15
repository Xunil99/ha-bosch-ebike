"""Standalone tests for entry_title.unique_title - run with:
python3 tests/test_entry_title.py

Every config entry used to be created with the title "Bosch eBike". With two
accounts on one bike (pull request #99) the second account's device is named
after its entry, so both read "Cargo Line (Bosch eBike)", and the card's
account picker shows two identical names. A new entry now takes the first free
title: "Bosch eBike", "Bosch eBike 2", "Bosch eBike 3". The title is only a
default; the user can rename the entry in Home Assistant.

entry_title.py imports nothing from Home Assistant, so it is loaded directly.
"""
import ast
import importlib.util
from pathlib import Path

_PACKAGE = (
    Path(__file__).resolve().parent.parent / "custom_components" / "ha_bosch_ebike"
)
_spec = importlib.util.spec_from_file_location("entry_title", _PACKAGE / "entry_title.py")
entry_title = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(entry_title)
unique_title = entry_title.unique_title

BASE = "Bosch eBike"


def test_the_first_entry_keeps_the_plain_title():
    assert unique_title(BASE, []) == BASE


def test_the_second_entry_gets_a_number():
    assert unique_title(BASE, [BASE]) == "Bosch eBike 2"


def test_the_next_free_number_is_taken():
    assert unique_title(BASE, [BASE, "Bosch eBike 2"]) == "Bosch eBike 3"


def test_a_gap_is_filled_before_the_count_moves_on():
    # The first entry was deleted again: its title is free, and 2 must not be
    # handed out twice (counting the entries would give "Bosch eBike 2" here).
    assert unique_title(BASE, ["Bosch eBike 2"]) == BASE
    assert unique_title(BASE, [BASE, "Bosch eBike 3"]) == "Bosch eBike 2"


def test_a_renamed_entry_does_not_use_up_the_default():
    assert unique_title(BASE, ["Sam"]) == BASE
    assert unique_title(BASE, ["Sam", BASE]) == "Bosch eBike 2"


def test_empty_titles_are_ignored():
    assert unique_title(BASE, ["", None]) == BASE


def test_the_config_flow_creates_the_entry_with_the_unique_title():
    # config_flow.py imports Home Assistant, so this is pinned from the source;
    # tests/test_reauth_flow.py runs the real method and checks the titles.
    tree = ast.parse((_PACKAGE / "config_flow.py").read_text(encoding="utf-8"))
    flow = next(n for n in ast.walk(tree) if isinstance(n, ast.AsyncFunctionDef) and n.name == "async_oauth_create_entry")
    creates = [
        n for n in ast.walk(flow)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "async_create_entry"
    ]
    assert creates, "async_oauth_create_entry no longer creates the entry"
    for call in creates:
        title = next((k.value for k in call.keywords if k.arg == "title"), None)
        assert title is not None and not isinstance(title, ast.Constant), "the new entry's title is a fixed string again"
    assert any(
        isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "unique_title"
        for n in ast.walk(flow)
    ), "the title is not taken from unique_title"


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
