"""Helpers for enriching Bosch tour data with live BLE values.

When the user has wired up the optional ``live_odometer_entity`` and/or
``live_soc_entity`` in the integration's options, the coordinator queries the
HA recorder for the value of those sensors at the exact start and end of each
tour. The deltas give us:

* exact tour distance (odometer end minus start), and
* exact battery consumption (SoC delta times capacity).

Both are far more accurate than the cloud-derived numbers, which are
distance-aggregated estimations and Wh-snapshots with reporting latency.
"""

from __future__ import annotations

from datetime import datetime, timedelta
import logging

from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.history import state_changes_during_period
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

# How far apart a recorder sample may be from the target time to still be
# considered representative of "the bike at that moment". Outside this window
# the sample is treated as stale (e.g. last value before BLE went out of range)
# and we transparently fall back to the cloud-based estimate.
LIVE_SAMPLE_TOLERANCE = timedelta(minutes=5)


async def get_state_at(
    hass: HomeAssistant,
    entity_id: str | None,
    target_time: datetime,
    tolerance: timedelta = LIVE_SAMPLE_TOLERANCE,
) -> float | None:
    """Return the recorder state of *entity_id* closest to *target_time*.

    Only returns a value if a fresh sample exists within *tolerance* of the
    target. Returns None if the entity is not configured, the recorder has no
    matching data, or the closest sample is too far away in time.
    """
    if not entity_id:
        return None

    start = target_time - tolerance
    end = target_time + tolerance

    def _query():
        return state_changes_during_period(
            hass,
            start,
            end,
            entity_id,
            include_start_time_state=True,
            no_attributes=True,
        )

    try:
        history = await get_instance(hass).async_add_executor_job(_query)
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug("Recorder query for %s failed: %s", entity_id, err)
        return None

    states = history.get(entity_id, []) if history else []
    if not states:
        return None

    closest = None
    closest_delta: float | None = None
    for s in states:
        if s.state in ("unknown", "unavailable", None, ""):
            continue
        delta = abs((s.last_updated - target_time).total_seconds())
        if closest is None or delta < closest_delta:
            closest = s
            closest_delta = delta

    if closest is None or closest_delta is None:
        return None
    if closest_delta > tolerance.total_seconds():
        return None

    try:
        return float(closest.state)
    except (ValueError, TypeError):
        return None


def parse_iso_utc(value: str | None) -> datetime | None:
    """Parse a Bosch-style ISO-8601 timestamp into an aware UTC datetime."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
