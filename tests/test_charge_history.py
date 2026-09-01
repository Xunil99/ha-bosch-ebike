"""Standalone tests for the coordinator's rolling charge-session history -
run with: python3 tests/test_charge_history.py

coordinator.py imports Home Assistant, so it cannot be imported directly in
this dependency-free suite. record_charge_session and charge_history are
extracted from its source and exec'd on their own, mirroring
test_battery_consumption_topup.py's approach for the same file.

This covers Task 2 of the charge-time-remaining estimate feature: collecting
and persisting a bounded per-bike history of completed charge sessions
({start_soc, end_soc, duration_min} dicts) for charge_rate_estimate.py (Task
1, already built and tested independently) to later consume. The cap itself
(CHARGE_HISTORY_MAX_SESSIONS) is a rolling count, not a time window - see
that constant's docstring in coordinator.py for why - so the main behaviour
worth pinning here is that appending past the cap drops the OLDEST entries
first and always keeps exactly the cap's worth of the most recent ones.
"""
import ast
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_COORD = _ROOT / "custom_components" / "ha_bosch_ebike" / "coordinator.py"
_SRC = _COORD.read_text(encoding="utf-8")
_TREE = ast.parse(_SRC)


def _module_const(name: str) -> ast.Assign:
    node = next(
        (
            n for n in _TREE.body
            if isinstance(n, ast.Assign)
            and len(n.targets) == 1
            and isinstance(n.targets[0], ast.Name)
            and n.targets[0].id == name
        ),
        None,
    )
    assert node is not None, (
        f"coordinator.py no longer defines {name} at module level - update "
        "this test alongside the rename/removal"
    )
    return node


_max_sessions_node = _module_const("CHARGE_HISTORY_MAX_SESSIONS")

_class_node = next(
    n for n in _TREE.body
    if isinstance(n, ast.ClassDef) and n.name == "BoschEBikeCoordinator"
)
_WANTED_METHODS = {"record_charge_session", "charge_history"}
_methods = [
    n for n in _class_node.body
    if isinstance(n, ast.FunctionDef) and n.name in _WANTED_METHODS
]
assert {m.name for m in _methods} == _WANTED_METHODS, (
    f"BoschEBikeCoordinator no longer defines "
    f"{_WANTED_METHODS - {m.name for m in _methods}} - update this test"
)

_ns: dict = {
    "Any": __import__("typing").Any,
}
# The constant first (the method bodies read it as a global), then the
# methods, sharing _ns as their __globals__.
exec(  # noqa: S102 - executing our own source, see the module docstring
    compile(ast.Module(body=[_max_sessions_node], type_ignores=[]), str(_COORD), "exec"),
    _ns,
)
exec(  # noqa: S102
    compile(ast.Module(body=_methods, type_ignores=[]), str(_COORD), "exec"), _ns
)
CHARGE_HISTORY_MAX_SESSIONS = _ns["CHARGE_HISTORY_MAX_SESSIONS"]
_record_charge_session = _ns["record_charge_session"]
_charge_history = _ns["charge_history"]


class _FakeCoordinator:
    """Just enough of BoschEBikeCoordinator's instance state to run the
    extracted methods against."""

    def __init__(self) -> None:
        self._charge_history: dict = {}
        self.saved_count = 0

    class _FakeHass:
        def __init__(self, outer: "_FakeCoordinator") -> None:
            self._outer = outer

        def async_create_task(self, coro) -> None:
            # The real hass would schedule this; here we just count that a
            # save was requested and discard the coroutine (never awaited,
            # never run) to avoid an "unawaited coroutine" warning.
            self._outer.saved_count += 1
            coro.close()

    def __post_init__(self) -> None:
        self.hass = self._FakeHass(self)

    async def _async_save_state(self) -> None:
        # Never actually awaited (async_create_task closes the coroutine
        # object immediately above) - only exists so record_charge_session's
        # call to self._async_save_state() resolves to a real coroutine.
        return None


def _coord() -> _FakeCoordinator:
    c = _FakeCoordinator()
    c.__post_init__()
    return c


def _summary(start_soc: float, end_soc: float, duration_min: float) -> dict:
    # A real ChargeSessionTracker.summary carries more keys (energy_wh,
    # started_at, ...) - record_charge_session must only pick out the three
    # it needs, so exercising it with exactly those three (plus one extra,
    # in test_extra_summary_fields_are_ignored) is the meaningful shape.
    return {"start_soc": start_soc, "end_soc": end_soc, "duration_min": duration_min}


def test_record_appends_and_charge_history_returns_it() -> None:
    coord = _coord()
    _record_charge_session(coord, "bike-1", _summary(20, 80, 120.0))

    history = _charge_history(coord, "bike-1")
    assert history == [{"start_soc": 20, "end_soc": 80, "duration_min": 120.0}]


def test_charge_history_is_empty_for_an_unknown_bike() -> None:
    coord = _coord()
    assert _charge_history(coord, "never-seen") == []


def test_charge_history_returns_a_copy_not_the_live_list() -> None:
    coord = _coord()
    _record_charge_session(coord, "bike-1", _summary(10, 50, 60.0))
    history = _charge_history(coord, "bike-1")
    history.append({"start_soc": 999, "end_soc": 999, "duration_min": 999})

    # Mutating the returned list must not corrupt the coordinator's own
    # stored history.
    assert len(_charge_history(coord, "bike-1")) == 1


def test_record_only_keeps_the_three_fields_it_needs() -> None:
    coord = _coord()
    summary = {
        "start_soc": 15, "end_soc": 95, "soc_delta": 80, "energy_wh": 600.0,
        "duration_min": 200.0, "started_at": 1.0, "ended_at": 2.0,
        "signal_gaps": 0,
    }
    _record_charge_session(coord, "bike-1", summary)

    assert _charge_history(coord, "bike-1") == [
        {"start_soc": 15, "end_soc": 95, "duration_min": 200.0}
    ]


def test_history_caps_at_max_sessions_dropping_oldest() -> None:
    coord = _coord()
    total = CHARGE_HISTORY_MAX_SESSIONS + 5
    for i in range(total):
        # Distinct values per session so we can tell exactly which ones
        # survive: start_soc doubles as a session index.
        _record_charge_session(coord, "bike-1", _summary(i, i + 10, 30.0))

    history = _charge_history(coord, "bike-1")
    assert len(history) == CHARGE_HISTORY_MAX_SESSIONS
    # The earliest 5 appended (indices 0..4) must be gone; the most RECENT
    # CHARGE_HISTORY_MAX_SESSIONS (indices 5..total-1) must remain, in the
    # order they were appended (oldest of what remains first).
    expected_start_socs = list(range(5, total))
    assert [e["start_soc"] for e in history] == expected_start_socs


def test_history_is_kept_separately_per_bike() -> None:
    coord = _coord()
    _record_charge_session(coord, "bike-1", _summary(10, 60, 90.0))
    _record_charge_session(coord, "bike-2", _summary(20, 70, 45.0))
    _record_charge_session(coord, "bike-1", _summary(30, 100, 150.0))

    assert len(_charge_history(coord, "bike-1")) == 2
    assert len(_charge_history(coord, "bike-2")) == 1
    assert _charge_history(coord, "bike-2") == [
        {"start_soc": 20, "end_soc": 70, "duration_min": 45.0}
    ]


def test_record_schedules_a_save() -> None:
    coord = _coord()
    assert coord.saved_count == 0
    _record_charge_session(coord, "bike-1", _summary(10, 60, 90.0))
    assert coord.saved_count == 1
    _record_charge_session(coord, "bike-1", _summary(60, 100, 60.0))
    assert coord.saved_count == 2


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("ALL TESTS PASSED")
