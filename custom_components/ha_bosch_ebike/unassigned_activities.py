"""Detect activities the multi-bike odometer attribution could not match."""

from __future__ import annotations

from typing import Any

MAX_RESULTS = 50


def compute_unassigned_activities(
    activities: list[dict[str, Any]],
    attribution: dict[str, str],
    bike_count: int,
) -> list[dict[str, Any]]:
    """Return {id, date, title} for activities missing from *attribution*.

    Only meaningful for multi-bike accounts: attribute_activities_to_bikes()
    trivially attributes every activity for single-bike accounts, so this
    always returns an empty list when bike_count <= 1.
    """
    if bike_count <= 1:
        return []

    result: list[dict[str, Any]] = []
    for activity in activities:
        activity_id = activity.get("id")
        if not activity_id or activity_id in attribution:
            continue
        result.append({
            "id": activity_id,
            "date": activity.get("startTime"),
            "title": activity.get("title"),
        })
        if len(result) >= MAX_RESULTS:
            break
    return result
