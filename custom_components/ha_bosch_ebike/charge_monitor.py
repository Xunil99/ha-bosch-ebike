"""Owns the live-SoC subscription that drives charge session detection.

Deliberately NOT an entity. The charge sensors used to own this: one of them
registered the state listener and fed the tracker, the other only read it.
That made the second sensor silently and permanently stop counting if a user
disabled the first one in the entity registry - a perfectly ordinary thing to
do with an integration that creates dozens of entities, and nothing in the UI
would have hinted that another entity depended on it. A disabled entity never
gets async_added_to_hass called at all, so the subscription simply never
happened.

So the data path lives here, tied to the config entry rather than to any
entity, and the sensors are pure readers that subscribe for notifications.
Disabling either of them now changes nothing except that this particular
entity stops being shown.

A charge that is running when Home Assistant stops is persisted here as well,
in a small store of its own (see async_restore), so that a restart or an
update during an overnight charge loses at most the time Home Assistant was
down instead of the whole session. That is the monitor's job rather than a
sensor's for the same reason as above: it must not depend on which entities
happen to be enabled.

See charge_session.py for the state machine itself, which stays free of Home
Assistant imports so it can be unit-tested.
"""
from __future__ import annotations

from collections.abc import Callable, Coroutine
from datetime import datetime, timezone
import logging
import re
from typing import Any

from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.event import async_call_later, async_track_state_change_event
from homeassistant.helpers.storage import Store

from .charge_session import IDLE_TIMEOUT_S, ChargeSessionTracker
from .const import DOMAIN
from .coordinator import BoschEBikeCoordinator

_LOGGER = logging.getLogger(__name__)

__all__ = ["ChargeSessionMonitor"]

INFLIGHT_STORAGE_VERSION = 1
# How long a changed snapshot of the running session may wait before it is
# written. The file is rewritten at most once per interval however fast the
# SoC climbs, which keeps a charge down to a few dozen writes of a file well
# under a kilobyte. Whatever the interval misses is made up for when Home
# Assistant stops or the entry unloads: a delayed write is flushed then.
INFLIGHT_SAVE_DELAY_S = 60.0


def _storage_slug(bike_id: str) -> str:
    """A bike id as something safe to put in a storage file name."""
    return re.sub(r"[^A-Za-z0-9_-]", "_", str(bike_id))


class ChargeSessionMonitor:
    """Feeds one bike's live SoC into a ChargeSessionTracker."""

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: BoschEBikeCoordinator,
        bike_id: str,
        soc_entity_id: str,
    ) -> None:
        self.hass = hass
        self.coordinator = coordinator
        self.bike_id = bike_id
        self.soc_entity_id = soc_entity_id
        self.tracker = ChargeSessionTracker()
        self._listeners: list[Callable[[], None]] = []
        self._cancel_idle: Callable[[], None] | None = None
        self._unsubs: list[Callable[[], None]] = []
        # One small file per bike rather than a slot in the coordinator's big
        # state file: that one is rewritten whole, and a running charge would
        # otherwise rewrite all of it every time the SoC moves.
        self._store: Store = Store(
            hass,
            INFLIGHT_STORAGE_VERSION,
            f"{DOMAIN}_charge_inflight_{_storage_slug(bike_id)}",
        )
        # The session snapshot the store holds, or has been asked to hold;
        # None means "no open session on disk". What _sync_store compares the
        # tracker against, so nothing is written unless something changed.
        self._stored: dict[str, Any] | None = None
        # A delayed write is queued. While it is, further rises do not queue
        # another: the store pushes a delayed write back every time it is
        # asked again, so a steady stream of rises would otherwise postpone
        # the write for as long as the charge lasts.
        self._write_pending = False
        # The file may hold a session, or a write for it is on its way, so the
        # unload has something to settle. Stays False for a bike that never
        # charges, which therefore never gets a file at all.
        self._touched = False

    @staticmethod
    def _now() -> float:
        return datetime.now(timezone.utc).timestamp()

    async def async_restore(self) -> None:
        """Pick a charge back up that was running when Home Assistant stopped.

        Call before async_start(): this fills the tracker, and start() then
        only seeds the baseline, which cannot disturb a restored session.

        Whatever the stored session turns out to be, the state machine does
        the judging from there (see ChargeSessionTracker.restore_inflight):
        while the last rise is recent it carries on, and the first SoC sample
        after startup raises the peak, closes the session from the stored
        peak if the battery fell, or leaves it to the idle timer. A session
        whose idle window ran out during the downtime is closed from its
        stored peak right here, which is what the idle timer would have done.

        Everything that can go wrong ends the same way: nothing is restored
        and the monitor behaves as it did before this existed. That covers no
        file, an unreadable one, a snapshot that no longer makes sense, and
        one written for a different SoC entity.
        """
        try:
            stored = await self._store.async_load()
        except Exception as err:  # noqa: BLE001 - an unreadable file must never block setup
            _LOGGER.debug(
                "Bosch eBike: could not read the stored charge state for %s: %s",
                self.bike_id,
                err,
            )
            return
        if not isinstance(stored, dict) or stored.get("session") is None:
            return

        snapshot = stored["session"]
        # Remember that the file holds a session, so one that is not resumed
        # below is cleared instead of resurfacing at some later restart.
        self._stored = snapshot if isinstance(snapshot, dict) else {}
        self._touched = True

        now = self._now()
        if stored.get("soc_entity") != self.soc_entity_id:
            _LOGGER.debug(
                "Bosch eBike: dropped a stored charge for %s: it was tracked from "
                "%s, the live SoC now comes from %s",
                self.bike_id,
                stored.get("soc_entity"),
                self.soc_entity_id,
            )
        elif self.tracker.restore_inflight(snapshot, now):
            closed = self.tracker.check_timeout(now)
            if closed and self.tracker.summary:
                _LOGGER.info(
                    "Bosch eBike: the charge of %s that was running at the last "
                    "shutdown ended while Home Assistant was down; booked %s%% to %s%%",
                    self.bike_id,
                    self.tracker.summary.get("start_soc"),
                    self.tracker.summary.get("end_soc"),
                )
                self.coordinator.record_charge_session(self.bike_id, self.tracker.summary)
            elif self.tracker.in_progress:
                _LOGGER.info(
                    "Bosch eBike: resumed the charge of %s that was running at the "
                    "last shutdown",
                    self.bike_id,
                )
                # No sample may arrive to arm the idle timer the usual way
                # (the bridge can be offline for a while after a restart), so
                # arm it for what is left of the window.
                remaining = self.tracker.idle_remaining_s(now) or 0.0
                self._arm_idle_timer(remaining + 1)
        else:
            _LOGGER.debug(
                "Bosch eBike: dropped a stored charge for %s that is too old or "
                "does not describe a plausible session",
                self.bike_id,
            )
        # Writes only if the file no longer matches the tracker: a session that
        # was dropped, closed or found too small is cleared from it.
        self._sync_store()

    def async_start(self) -> Callable[[], Coroutine[Any, Any, None]]:
        """Subscribe and return the callable that tears everything down again.

        The returned callable is a coroutine function: Home Assistant awaits
        what an unload callback returns, and the flush of the running session
        has to be finished before a reload builds the next monitor, which
        reads that same store.
        """
        # Baseline first, so the first genuine rise after a restart is measured
        # against a real value instead of being swallowed as "no previous
        # sample". seed() cannot start a session by itself.
        state = self.hass.states.get(self.soc_entity_id)
        self.tracker.seed(state.state if state is not None else None, self._now())

        self._unsubs.append(
            async_track_state_change_event(
                self.hass, [self.soc_entity_id], self._on_soc_change
            )
        )
        # Safety net on the cloud poll: a session left open because the idle
        # timer never fired (HA suspended, callback lost) is closed on the
        # next poll at the latest, instead of blocking every later charge.
        self._unsubs.append(
            self.coordinator.async_add_listener(self._on_coordinator_update)
        )
        return self.async_stop

    async def async_stop(self) -> None:
        """Tear down the subscriptions and settle the stored session."""
        self._cancel_idle_timer()
        while self._unsubs:
            self._unsubs.pop()()
        self._listeners.clear()
        if not self._touched:
            return
        # Write the newest state now rather than leave it to a delayed write:
        # this is an unload (a reload, or the entry being removed), and the
        # next monitor reads the store as soon as it is set up. async_save
        # takes the store's own write lock, so it also waits for a write that
        # is already under way.
        try:
            await self._store.async_save(self._store_payload())
        except Exception as err:  # noqa: BLE001 - never fail an unload over this
            _LOGGER.debug(
                "Bosch eBike: could not store the charge state of %s on unload: %s",
                self.bike_id,
                err,
            )

    def add_listener(self, update_callback: Callable[[], None]) -> Callable[[], None]:
        """Register a callback for "the tracker changed", returning a remover."""
        self._listeners.append(update_callback)

        def _remove() -> None:
            if update_callback in self._listeners:
                self._listeners.remove(update_callback)

        return _remove

    @callback
    def _notify(self) -> None:
        for update_callback in list(self._listeners):
            update_callback()

    def _cancel_idle_timer(self) -> None:
        if self._cancel_idle is not None:
            self._cancel_idle()
            self._cancel_idle = None

    def _arm_idle_timer(self, delay: float) -> None:
        self._cancel_idle_timer()
        self._cancel_idle = async_call_later(self.hass, delay, self._on_idle_timeout)

    @callback
    def _sync_store(self) -> None:
        """Bring the stored copy of the running session in line with the tracker.

        Called after everything that can change the tracker. It does nothing
        while no charge is running and none is stored, so a bike that is not
        charging never causes a write.

        A session starting or ending is written straight away. An ended one
        in particular must be cleared before the total it fed can reach disk,
        or a restart in between could book the same charge a second time. A
        session that merely moves on (a new peak, another dropout) is
        rewritten at most once per INFLIGHT_SAVE_DELAY_S.
        """
        snapshot = self.tracker.export_inflight()
        if snapshot == self._stored:
            return
        starting_or_ending = snapshot is None or self._stored is None
        self._stored = snapshot
        self._touched = True
        if not starting_or_ending:
            if self._write_pending:
                return
            self._write_pending = True
        self._store.async_delay_save(
            self._store_payload, 0 if starting_or_ending else INFLIGHT_SAVE_DELAY_S
        )

    def _store_payload(self) -> dict[str, Any]:
        """What gets written. The store calls it when the write happens, so
        it is always the newest state rather than the one that queued it."""
        self._write_pending = False
        snapshot = self.tracker.export_inflight()
        self._stored = snapshot
        return {"soc_entity": self.soc_entity_id, "session": snapshot}

    @callback
    def _on_soc_change(self, event: Event) -> None:
        new_state = event.data.get("new_state")
        # The sample's own timestamp, not "now": it is what the duration in
        # the summary is measured with, and the two can differ noticeably when
        # HA is busy or has just started up.
        when = self._now()
        if new_state is not None and new_state.last_updated is not None:
            when = new_state.last_updated.timestamp()

        was_charging = self.tracker.in_progress
        changed = self.tracker.feed(
            new_state.state if new_state is not None else None,
            when,
            self.coordinator.battery_capacity_wh(self.bike_id),
        )
        if changed and self.tracker.summary:
            self.coordinator.record_charge_session(self.bike_id, self.tracker.summary)

        # Rearm regardless of whether this sample moved anything: a charge
        # normally ends by the SoC simply stopping, with no final sample to
        # detect it from, so the timer is what actually closes most sessions.
        if self.tracker.in_progress:
            self._arm_idle_timer(IDLE_TIMEOUT_S + 1)
        else:
            self._cancel_idle_timer()
        self._sync_store()

        # Also notify when a charge merely started or stopped: the summary
        # only changes when a session COMPLETES, but "in progress" is
        # something users watch to see that charging is happening at all.
        if changed or self.tracker.in_progress != was_charging:
            self._notify()

    @callback
    def _on_idle_timeout(self, _now: Any) -> None:
        self._cancel_idle = None
        was_charging = self.tracker.in_progress
        closed = self.tracker.check_timeout(self._now())
        if closed and self.tracker.summary:
            self.coordinator.record_charge_session(self.bike_id, self.tracker.summary)
        self._sync_store()
        # The second case is a session that timed out without producing a
        # summary (too small to publish): nothing about the state changed, but
        # "in progress" went false and has to be shown.
        if closed or self.tracker.in_progress != was_charging:
            self._notify()

    @callback
    def _on_coordinator_update(self) -> None:
        # Same was_charging comparison as _on_idle_timeout, and for the same
        # reason: _close() unconditionally clears in_progress even when the
        # session was too small to publish (check_timeout then returns
        # False). Without this check, a sub-threshold session closed here -
        # exactly the "idle timer was lost" case this safety net exists for -
        # would leave in_progress reporting True forever, with nothing left
        # to ever flip it back.
        was_charging = self.tracker.in_progress
        closed = self.tracker.check_timeout(self._now())
        if closed:
            _LOGGER.debug(
                "Bosch eBike: closed a stale charge session for %s on the poll "
                "safety net; the idle timer had not fired",
                self.bike_id,
            )
            if self.tracker.summary:
                self.coordinator.record_charge_session(self.bike_id, self.tracker.summary)
        self._sync_store()
        if closed or self.tracker.in_progress != was_charging:
            self._notify()
