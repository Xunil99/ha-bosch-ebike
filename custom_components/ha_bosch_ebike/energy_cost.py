"""Pure rolling-window energy aggregation for the charging-cost summary.

Deliberately free of Home Assistant imports so it can be unit-tested
standalone (see tests/test_energy_cost.py).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

WINDOW_DAYS: dict[str, int] = {"7d": 7, "30d": 30, "365d": 365}


def _parse_iso_utc(value: str | None) -> datetime | None:
    """Parse a Bosch-style ISO-8601 timestamp into an aware UTC datetime."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def compute_energy_windows(
    activities: list[dict[str, Any]],
    activity_bike: dict[str, str],
    consumption: dict[str, dict[str, Any]],
    bike_id: str,
    now: datetime,
    fallback_all: bool = False,
) -> dict[str, float]:
    """Wh charged by this bike in the last 7 / 30 / 365 days.

    ``activities`` must be sorted newest-first (the coordinator's existing
    invariant for ``self._all_activities``). ``fallback_all`` mirrors
    ``compute_range_estimate``'s semantics: an unmapped activity counts as
    this bike's own only for single-bike accounts where attribution is
    empty.

    Returns a dict with a subset of the keys "7d"/"30d"/"365d" - a window
    with no matching consumption data in range is simply absent, to
    distinguish "no rides yet in this window" from "rode but the measured
    consumption was exactly 0 Wh".
    """
    totals = {key: 0.0 for key in WINDOW_DAYS}
    found = {key: False for key in WINDOW_DAYS}
    cutoffs = {key: now - timedelta(days=days) for key, days in WINDOW_DAYS.items()}
    oldest_cutoff = min(cutoffs.values())

    for activity in activities:
        aid = activity.get("id")
        if not aid:
            continue
        start = _parse_iso_utc(activity.get("startTime"))
        if start is None:
            continue
        if start < oldest_cutoff:
            break  # newest-first sorted; nothing further can fall in any window
        mapped = activity_bike.get(aid)
        if mapped != bike_id and not (mapped is None and fallback_all):
            continue
        entry = consumption.get(aid)
        if not entry:
            continue
        wh = entry.get("consumed_wh")
        if wh is None:
            continue
        for key, cutoff in cutoffs.items():
            if start >= cutoff:
                totals[key] += float(wh)
                found[key] = True

    return {key: round(totals[key], 2) for key in WINDOW_DAYS if found[key]}
