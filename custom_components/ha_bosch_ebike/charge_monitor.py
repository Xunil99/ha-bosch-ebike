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

See charge_session.py for the state machine itself, which stays free of Home
Assistant imports so it can be unit-tested.
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
import logging
from typing import Any

from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.event import async_call_later, async_track_state_change_event

from .charge_session import IDLE_TIMEOUT_S, ChargeSessionTracker
from .coordinator import BoschEBikeCoordinator

_LOGGER = logging.getLogger(__name__)

__all__ = ["ChargeSessionMonitor"]


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

    @staticmethod
    def _now() -> float:
        return datetime.now(timezone.utc).timestamp()

    def async_start(self) -> Callable[[], None]:
        """Subscribe and return a callable that tears everything down again."""
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

    @callback
    def async_stop(self) -> None:
        self._cancel_idle_timer()
        while self._unsubs:
            self._unsubs.pop()()
        self._listeners.clear()

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

        # Rearm regardless of whether this sample moved anything: a charge
        # normally ends by the SoC simply stopping, with no final sample to
        # detect it from, so the timer is what actually closes most sessions.
        self._cancel_idle_timer()
        if self.tracker.in_progress:
            self._cancel_idle = async_call_later(
                self.hass, IDLE_TIMEOUT_S + 1, self._on_idle_timeout
            )

        # Also notify when a charge merely started or stopped: the summary
        # only changes when a session COMPLETES, but "in progress" is
        # something users watch to see that charging is happening at all.
        if changed or self.tracker.in_progress != was_charging:
            self._notify()

    @callback
    def _on_idle_timeout(self, _now: Any) -> None:
        self._cancel_idle = None
        was_charging = self.tracker.in_progress
        # The second case is a session that timed out without producing a
        # summary (too small to publish): nothing about the state changed, but
        # "in progress" went false and has to be shown.
        if self.tracker.check_timeout(self._now()) or (
            self.tracker.in_progress != was_charging
        ):
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
        if closed or self.tracker.in_progress != was_charging:
            self._notify()
