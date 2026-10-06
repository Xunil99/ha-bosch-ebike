"""Standalone tests for charge_monitor.py - run with:
python3 tests/test_charge_monitor.py

charge_monitor.py imports Home Assistant, so it cannot be imported in this
dependency-free suite. The ChargeSessionMonitor class and its small
module-level helpers are extracted from its source and exec'd against fakes,
the same AST approach test_entry_update_listener.py uses for __init__.py.
The state machine itself is covered in test_charge_session.py.

What this covers is the wiring that carries a running charge across a
restart (issue #89 follow-up): when the stored copy is written, that it is
read back and judged correctly at startup, and that a charge is neither lost
nor booked twice. The fakes keep the one thing about Home Assistant's Store
that matters here: a "disk" shared between Store instances, so a monitor set
up after an unload really reads what the previous one left behind, and
everything written must survive a JSON round trip.
"""
import __future__
import ast
import asyncio
import importlib.util
import inspect
import json
import logging
import re
from collections.abc import Callable, Coroutine
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_COMPONENT = Path(__file__).resolve().parent.parent / "custom_components" / "ha_bosch_ebike"

_spec = importlib.util.spec_from_file_location("charge_session", _COMPONENT / "charge_session.py")
charge_session = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(charge_session)

IDLE_TIMEOUT_S = charge_session.IDLE_TIMEOUT_S
MIN = 60.0

_TREE = ast.parse((_COMPONENT / "charge_monitor.py").read_text(encoding="utf-8"))


def _node(kind, name):
    found = next(
        (
            n for n in _TREE.body
            if isinstance(n, kind) and (
                getattr(n, "name", None) == name
                or (
                    isinstance(n, ast.Assign)
                    and any(isinstance(t, ast.Name) and t.id == name for t in n.targets)
                )
            )
        ),
        None,
    )
    assert found is not None, (
        f"charge_monitor.py no longer defines {name} at module level - update "
        "this test alongside the rename/removal"
    )
    return found


# --- fakes ----------------------------------------------------------------

CLOCK = {"t": 1_000_000.0}
TIMERS: list[dict[str, Any]] = []


def fake_async_call_later(hass, delay, action):
    timer = {"delay": delay, "action": action, "cancelled": False}
    TIMERS.append(timer)

    def _cancel():
        timer["cancelled"] = True

    return _cancel


class FakeStore:
    """Home Assistant's Store, reduced to what the monitor relies on."""

    disk: dict[str, str] = {}

    def __init__(self, hass, version, key):
        self.version = version
        self.key = key
        self.delayed = None
        self.calls: list[tuple] = []
        self.fail_load = False

    async def async_load(self):
        self.calls.append(("load",))
        if self.fail_load:
            raise OSError("disk on fire")
        raw = FakeStore.disk.get(self.key)
        return None if raw is None else json.loads(raw)

    async def async_save(self, data):
        # Like the real one, saving now also cancels a write that was queued.
        self.calls.append(("save",))
        self.delayed = None
        FakeStore.disk[self.key] = json.dumps(data)

    def async_delay_save(self, data_func, delay=0):
        self.calls.append(("delay", delay))
        self.delayed = (data_func, delay)

    def run_delayed(self):
        """Let the queued write happen, as the store does once the delay is up."""
        data_func, _ = self.delayed
        self.delayed = None
        FakeStore.disk[self.key] = json.dumps(data_func())


class FakeCoordinator:
    def __init__(self):
        self.recorded: list[tuple[str, dict]] = []
        self.listeners: list[Callable] = []

    def battery_capacity_wh(self, bike_id):
        return 625.0

    def record_charge_session(self, bike_id, summary):
        self.recorded.append((bike_id, dict(summary)))

    def async_add_listener(self, update_callback):
        self.listeners.append(update_callback)
        return lambda: self.listeners.remove(update_callback)


class FakeStates:
    def __init__(self):
        self.values: dict[str, str] = {}

    def get(self, entity_id):
        value = self.values.get(entity_id)
        return None if value is None else type("State", (), {"state": value})()


class FakeHass:
    def __init__(self):
        self.states = FakeStates()


class _Stamp:
    def __init__(self, ts):
        self._ts = ts

    def timestamp(self):
        return self._ts


class FakeEvent:
    def __init__(self, state, ts):
        new_state = type("NewState", (), {})()
        new_state.state = state
        new_state.last_updated = _Stamp(ts)
        self.data = {"new_state": new_state}


TRACK_UNSUBS: list[dict[str, Any]] = []


def fake_track_state_change_event(hass, entity_ids, action):
    handle = {"entity_ids": entity_ids, "action": action, "removed": False}
    TRACK_UNSUBS.append(handle)

    def _unsub():
        handle["removed"] = True

    return _unsub


_ns: dict[str, Any] = {
    "Callable": Callable,
    "Coroutine": Coroutine,
    "Any": Any,
    "datetime": datetime,
    "timezone": timezone,
    "re": re,
    "callback": lambda func: func,
    "Event": object,
    "HomeAssistant": object,
    "BoschEBikeCoordinator": object,
    "async_call_later": fake_async_call_later,
    "async_track_state_change_event": fake_track_state_change_event,
    "Store": FakeStore,
    "ChargeSessionTracker": charge_session.ChargeSessionTracker,
    "IDLE_TIMEOUT_S": IDLE_TIMEOUT_S,
    "DOMAIN": "ha_bosch_ebike",
    "_LOGGER": logging.getLogger("test_charge_monitor"),
}
# charge_monitor.py uses `from __future__ import annotations`, so its
# annotations (Store, Event, ...) are never evaluated; keep that when exec'ing
# the extracted nodes.
_module = ast.Module(
    body=[
        _node(ast.Assign, "INFLIGHT_STORAGE_VERSION"),
        _node(ast.Assign, "INFLIGHT_SAVE_DELAY_S"),
        _node(ast.FunctionDef, "_storage_slug"),
        _node(ast.ClassDef, "ChargeSessionMonitor"),
    ],
    type_ignores=[],
)
ast.fix_missing_locations(_module)
exec(
    compile(
        _module,
        str(_COMPONENT / "charge_monitor.py"),
        "exec",
        flags=__future__.annotations.compiler_flag,
        dont_inherit=True,
    ),
    _ns,
)
Monitor = _ns["ChargeSessionMonitor"]
_storage_slug = _ns["_storage_slug"]
INFLIGHT_SAVE_DELAY_S = _ns["INFLIGHT_SAVE_DELAY_S"]

SOC = "sensor.bike_soc"


# --- helpers --------------------------------------------------------------

def _reset():
    FakeStore.disk.clear()
    TIMERS.clear()
    TRACK_UNSUBS.clear()
    CLOCK["t"] = 1_000_000.0


def _monitor(soc_entity=SOC, bike_id="bike-1"):
    monitor = Monitor(FakeHass(), FakeCoordinator(), bike_id, soc_entity)
    # An instance attribute shadows the staticmethod, which is all it takes to
    # control time.
    monitor._now = lambda: CLOCK["t"]
    return monitor


def _feed(monitor, soc, at):
    CLOCK["t"] = at
    monitor._on_soc_change(FakeEvent(str(soc), at))


def _charge(monitor, start, stop, t0):
    """Plug in at *start*% and charge to *stop*%, one percent per two minutes.

    Returns the time of the last rise.
    """
    monitor.tracker.seed(start, t0)
    now = t0
    for soc in range(start + 1, stop + 1):
        now += 2 * MIN
        _feed(monitor, soc, now)
    return now


def _disk_session(key="ha_bosch_ebike_charge_inflight_bike-1"):
    return json.loads(FakeStore.disk[key])["session"]


# --- when the stored copy is written --------------------------------------

def test_a_bike_that_is_not_charging_never_touches_the_store():
    _reset()
    m = _monitor()
    m.tracker.seed(60, CLOCK["t"])
    # Nothing here rises by a whole percent, so no session ever starts.
    for i, soc in enumerate([60, 60, "unavailable", 60, 59, 59, 58]):
        _feed(m, soc, CLOCK["t"] + (i + 1) * MIN)
    assert m._store.calls == []
    assert FakeStore.disk == {}
    asyncio.run(m.async_stop())
    assert m._store.calls == [], "an unload with nothing to settle writes nothing"
    assert FakeStore.disk == {}


def test_a_session_start_is_written_at_once_and_a_moving_peak_only_every_so_often():
    _reset()
    m = _monitor()
    t0 = CLOCK["t"]
    m.tracker.seed(20, t0)

    _feed(m, 21, t0 + 2 * MIN)                      # the charge begins
    assert m._store.calls == [("delay", 0)]
    m._store.run_delayed()
    session = _disk_session()
    assert session["start_soc"] == 20 and session["peak_soc"] == 21

    _feed(m, 22, t0 + 4 * MIN)                      # the peak moves: queued, not immediate
    assert m._store.calls[-1] == ("delay", INFLIGHT_SAVE_DELAY_S)
    queued = len(m._store.calls)
    _feed(m, 23, t0 + 6 * MIN)                      # a write is already pending ...
    _feed(m, 24, t0 + 8 * MIN)
    _feed(m, "unavailable", t0 + 9 * MIN)           # ... even a dropout does not re-arm it
    assert len(m._store.calls) == queued, (
        "re-arming a delayed write pushes it back, which would postpone it for "
        "as long as the charge keeps rising"
    )
    m._store.run_delayed()
    session = _disk_session()
    assert session["peak_soc"] == 24, "the write carries the newest state, not the one that queued it"
    assert session["gaps"] == 1

    _feed(m, 25, t0 + 10 * MIN)                     # after the write the next change queues again
    assert m._store.calls[-1] == ("delay", INFLIGHT_SAVE_DELAY_S)
    assert len(m._store.calls) == queued + 1


def test_the_written_data_names_the_soc_entity_and_is_json_safe():
    _reset()
    m = _monitor()
    _charge(m, 20, 30, CLOCK["t"])
    payload = m._store.delayed[0]()
    assert payload["soc_entity"] == SOC
    assert json.loads(json.dumps(payload)) == payload


def test_the_end_of_a_session_clears_the_store_at_once():
    _reset()
    m = _monitor()
    last = _charge(m, 20, 60, CLOCK["t"])
    m._store.run_delayed()
    assert _disk_session()["peak_soc"] == 60

    CLOCK["t"] = last + IDLE_TIMEOUT_S + 1
    m._on_idle_timeout(None)
    assert len(m.coordinator.recorded) == 1
    assert m._store.calls[-1] == ("delay", 0), (
        "a closed session has to leave the store before the total it fed can be "
        "persisted, or a restart in between would book it a second time"
    )
    m._store.run_delayed()
    assert _disk_session() is None


def test_a_session_too_small_to_publish_is_cleared_too():
    _reset()
    m = _monitor()
    last = _charge(m, 20, 22, CLOCK["t"])          # 2%: below MIN_SESSION_PCT
    m._store.run_delayed()
    assert _disk_session() is not None
    CLOCK["t"] = last + IDLE_TIMEOUT_S + 1
    m._on_idle_timeout(None)
    assert m.coordinator.recorded == []
    m._store.run_delayed()
    assert _disk_session() is None


def test_the_poll_safety_net_clears_a_stale_session_from_the_store():
    _reset()
    m = _monitor()
    last = _charge(m, 20, 60, CLOCK["t"])
    m._store.run_delayed()
    CLOCK["t"] = last + IDLE_TIMEOUT_S + 5
    m._on_coordinator_update()
    assert len(m.coordinator.recorded) == 1
    m._store.run_delayed()
    assert _disk_session() is None


def test_every_sample_rearms_the_idle_timer_and_the_end_of_a_session_drops_it():
    _reset()
    m = _monitor()
    t0 = CLOCK["t"]
    m.tracker.seed(20, t0)
    _feed(m, 21, t0 + 2 * MIN)
    _feed(m, 22, t0 + 4 * MIN)
    _feed(m, 22, t0 + 5 * MIN)                      # a sample that moves nothing re-arms it too
    assert [t["delay"] for t in TIMERS] == [IDLE_TIMEOUT_S + 1] * 3
    assert [t["cancelled"] for t in TIMERS] == [True, True, False]
    _feed(m, 18, t0 + 6 * MIN)                      # the bike is ridden again: the session ends
    assert m.tracker.in_progress is False
    assert TIMERS[-1]["cancelled"] is True


# --- unload ---------------------------------------------------------------

def test_unload_writes_the_newest_state_of_a_running_session():
    _reset()
    m = _monitor()
    t0 = CLOCK["t"]
    _charge(m, 20, 40, t0)
    m._store.run_delayed()
    _feed(m, 41, t0 + 60 * MIN)
    _feed(m, 42, t0 + 61 * MIN)                     # a delayed write is queued for this
    assert m._store.delayed is not None
    asyncio.run(m.async_stop())
    assert m._store.delayed is None, "saving now supersedes the queued write"
    assert _disk_session()["peak_soc"] == 42
    assert m._write_pending is False


def test_unload_settles_a_session_that_closed_but_was_not_written_yet():
    # A reload builds the next monitor straight away, and it reads the store.
    # If the clearing write had not happened yet it would find the session that
    # just ended and book it again.
    _reset()
    m = _monitor()
    last = _charge(m, 20, 60, CLOCK["t"])
    m._store.run_delayed()
    CLOCK["t"] = last + IDLE_TIMEOUT_S + 1
    m._on_idle_timeout(None)                        # closed; the clear is only queued
    assert m._store.delayed is not None
    asyncio.run(m.async_stop())
    assert _disk_session() is None


def test_async_start_hands_back_the_coroutine_function_that_stops_it():
    _reset()
    m = _monitor()
    m.hass.states.values[SOC] = "55"
    stop = m.async_start()
    assert stop == m.async_stop and inspect.iscoroutinefunction(stop)
    assert m.tracker.in_progress is False
    assert [h["entity_ids"] for h in TRACK_UNSUBS] == [[SOC]]
    assert len(m.coordinator.listeners) == 1
    asyncio.run(stop())
    assert all(h["removed"] for h in TRACK_UNSUBS)
    assert m.coordinator.listeners == []


def test_a_failing_save_on_unload_does_not_break_the_unload():
    _reset()
    m = _monitor()
    _charge(m, 20, 40, CLOCK["t"])

    async def boom(data):
        raise OSError("read-only file system")

    m._store.async_save = boom
    asyncio.run(m.async_stop())                     # must not raise


# --- restoring at startup -------------------------------------------------

def _interrupted_charge(stop_at=60, soc_entity=SOC):
    """Run a charge up to *stop_at*% on one monitor and unload it cleanly."""
    first = _monitor(soc_entity=soc_entity)
    last = _charge(first, 20, stop_at, CLOCK["t"])
    asyncio.run(first.async_stop())
    # Its timers died with it; what is armed from here on is the next
    # monitor's doing.
    TIMERS.clear()
    return last


def test_nothing_stored_changes_nothing():
    _reset()
    m = _monitor()
    asyncio.run(m.async_restore())
    assert m.tracker.in_progress is False
    assert m._store.calls == [("load",)]
    assert TIMERS == []


def test_a_charge_interrupted_by_a_restart_is_resumed_and_completed():
    # Charge 20% -> 100%, Home Assistant restarts at 60% and is back 3 minutes
    # later. The whole charge is booked, not just the part after the restart.
    _reset()
    last = _interrupted_charge(60)
    CLOCK["t"] = last + 3 * MIN

    m = _monitor()
    asyncio.run(m.async_restore())
    assert m.tracker.in_progress is True
    assert m.coordinator.recorded == []
    assert m._store.calls == [("load",)], "nothing changed, so nothing is rewritten"
    # Armed for what is left of the idle window, since no sample may arrive.
    assert len(TIMERS) == 1 and not TIMERS[0]["cancelled"]
    assert TIMERS[0]["delay"] == IDLE_TIMEOUT_S - 3 * MIN + 1

    m.hass.states.values[SOC] = "62"
    m.async_start()
    now = CLOCK["t"]
    for soc in range(63, 101):
        now += 2 * MIN
        _feed(m, soc, now)
    CLOCK["t"] = now + IDLE_TIMEOUT_S + 1
    m._on_idle_timeout(None)

    assert len(m.coordinator.recorded) == 1
    _, summary = m.coordinator.recorded[0]
    assert summary["start_soc"] == 20 and summary["end_soc"] == 100
    assert summary["energy_wh"] == 500.0
    assert m.tracker.total_energy_wh == 500.0
    m._store.run_delayed()
    assert _disk_session() is None


def test_a_resumed_session_with_a_silent_sensor_is_closed_by_its_timer():
    _reset()
    last = _interrupted_charge(60)
    CLOCK["t"] = last + 3 * MIN
    m = _monitor()
    asyncio.run(m.async_restore())
    assert m.tracker.in_progress is True

    CLOCK["t"] = last + IDLE_TIMEOUT_S + 1
    TIMERS[-1]["action"](None)                      # the timer fires; no sample ever came
    assert m.tracker.in_progress is False
    _, summary = m.coordinator.recorded[0]
    assert summary["end_soc"] == 60 and summary["energy_wh"] == 250.0
    m._store.run_delayed()
    assert _disk_session() is None


def test_a_charge_whose_idle_window_ran_out_while_down_is_closed_from_its_peak():
    _reset()
    last = _interrupted_charge(60)
    CLOCK["t"] = last + 40 * MIN                    # down longer than the idle window

    m = _monitor()
    asyncio.run(m.async_restore())
    assert m.tracker.in_progress is False
    assert len(m.coordinator.recorded) == 1
    _, summary = m.coordinator.recorded[0]
    assert summary["start_soc"] == 20 and summary["end_soc"] == 60
    assert summary["ended_at"] == last, "dated by the last rise that was seen, not by the restart"
    assert m.tracker.summary == summary
    assert m.tracker.total_energy_wh == 250.0
    assert TIMERS == [], "nothing is left running, so nothing is armed"
    assert m._store.calls[-1] == ("delay", 0)
    m._store.run_delayed()
    assert _disk_session() is None


def test_a_charge_is_never_booked_twice_across_restarts():
    _reset()
    last = _interrupted_charge(60)
    CLOCK["t"] = last + 40 * MIN
    second = _monitor()
    asyncio.run(second.async_restore())
    second._store.run_delayed()
    assert len(second.coordinator.recorded) == 1

    third = _monitor()
    asyncio.run(third.async_restore())
    assert third.tracker.in_progress is False
    assert third.coordinator.recorded == []
    assert third.tracker.summary is None


def test_a_charge_that_is_too_old_is_dropped_not_booked_into_today():
    _reset()
    last = _interrupted_charge(60)
    CLOCK["t"] = last + 3 * 86400.0                 # integration was off for days
    m = _monitor()
    asyncio.run(m.async_restore())
    assert m.tracker.in_progress is False
    assert m.coordinator.recorded == []
    m._store.run_delayed()
    assert _disk_session() is None


def test_a_charge_tracked_from_another_soc_entity_is_dropped():
    _reset()
    last = _interrupted_charge(60, soc_entity="sensor.old_bike_soc")
    CLOCK["t"] = last + 3 * MIN
    m = _monitor(soc_entity="sensor.new_bike_soc")
    asyncio.run(m.async_restore())
    assert m.tracker.in_progress is False
    assert m.coordinator.recorded == []
    m._store.run_delayed()
    assert _disk_session() is None


def test_an_unusable_stored_session_is_cleared_and_ignored():
    garbage = [
        {"start_soc": 90.0, "start_ts": 1.0, "peak_soc": 10.0, "peak_ts": 2.0},   # fell
        {"start_soc": "x"},
        "not a session",
        [],
        5,
    ]
    for session in garbage:
        _reset()
        key = "ha_bosch_ebike_charge_inflight_bike-1"
        FakeStore.disk[key] = json.dumps({"soc_entity": SOC, "session": session})
        m = _monitor()
        asyncio.run(m.async_restore())
        assert m.tracker.in_progress is False, session
        assert m.coordinator.recorded == [], session
        m._store.run_delayed()
        assert _disk_session() is None, session


def test_an_unexpected_file_shape_is_ignored_without_failing_setup():
    for stored in ([], "text", 3, {}, {"session": None}, {"soc_entity": SOC}):
        _reset()
        FakeStore.disk["ha_bosch_ebike_charge_inflight_bike-1"] = json.dumps(stored)
        m = _monitor()
        asyncio.run(m.async_restore())
        assert m.tracker.in_progress is False, stored
        assert m.coordinator.recorded == [], stored


def test_an_unreadable_store_does_not_block_setup():
    _reset()
    m = _monitor()
    m._store.fail_load = True
    asyncio.run(m.async_restore())
    assert m.tracker.in_progress is False
    assert m._store.calls == [("load",)]


def test_a_resumed_session_follows_the_samples_after_the_restart():
    # Back after a restart, the battery turns out to have fallen: the session
    # ends from the stored peak, exactly as it would have without the restart.
    _reset()
    last = _interrupted_charge(60)
    CLOCK["t"] = last + 3 * MIN
    m = _monitor()
    asyncio.run(m.async_restore())
    m.hass.states.values[SOC] = "57"
    m.async_start()
    _feed(m, 57, CLOCK["t"] + MIN)
    assert m.tracker.in_progress is False
    _, summary = m.coordinator.recorded[0]
    assert summary["end_soc"] == 60 and summary["soc_delta"] == 40
    assert TIMERS[-1]["cancelled"], "the idle timer is not left behind"
    m._store.run_delayed()
    assert _disk_session() is None


# --- file name ------------------------------------------------------------

def test_the_file_name_is_safe_and_unique_per_bike():
    assert _storage_slug("0b2f5c8e-aaaa-bbbb-cccc-1234567890ab") == "0b2f5c8e-aaaa-bbbb-cccc-1234567890ab"
    assert _storage_slug("a/b c:d..e") == "a_b_c_d__e"
    _reset()
    one, two = _monitor(bike_id="bike-1"), _monitor(bike_id="bike-2")
    assert one._store.key == "ha_bosch_ebike_charge_inflight_bike-1"
    assert one._store.key != two._store.key


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("ALL TESTS PASSED")
