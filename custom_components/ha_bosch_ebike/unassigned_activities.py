"""Detect activities the multi-bike odometer attribution could not match."""

from __future__ import annotations

from typing import Any

# How many affected rides the sensor exposes as attributes (HA attribute
# payload size). The sensor's own count (native_value) is NEVER capped by
# this - it must always reflect the true total, or the state would silently
# understate the problem for accounts with more than this many gaps.
ATTRIBUTE_DISPLAY_LIMIT = 50


def compute_unassigned_activities(
    activities: list[dict[str, Any]],
    attribution: dict[str, str],
    bike_count: int,
) -> list[dict[str, Any]]:
    """Return {id, date, title} for every activity missing from *attribution*.

    Only meaningful for multi-bike accounts: attribute_activities_to_bikes()
    trivially attributes every activity for single-bike accounts, so this
    always returns an empty list when bike_count <= 1. Deliberately
    uncapped - callers that need to bound how many entries they display
    (e.g. HA entity attributes) must slice the result themselves, so the
    length of this list can always be trusted as the true count.
    """
    if bike_count <= 1:
        return []

    return [
        {
            "id": activity["id"],
            "date": activity.get("startTime"),
            "title": activity.get("title"),
        }
        for activity in activities
        if activity.get("id") and activity["id"] not in attribution
    ]


def merge_manual_overrides(
    heuristic_attribution: dict[str, str],
    manual_attribution: dict[str, str],
) -> dict[str, str]:
    """Combine odometer-heuristic and manual bike attributions.

    Manual assignments always win, including when the heuristic independently
    (and possibly differently) matches the same activity - once a user has
    corrected an assignment, it must not silently flip back.
    """
    return {**heuristic_attribution, **manual_attribution}
