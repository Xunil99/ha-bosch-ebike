"""Payload builder for the ``ha_bosch_ebike_new_activity`` event.

Kept out of coordinator.py and free of Home Assistant imports so the
dependency-free suite under tests/ can cover it. The coordinator decides
*when* a ride is new (that part is genuinely stateful and differs between
the Smart System and BES2 poll paths); this module only decides what the
resulting event looks like.

The payload is deliberately flat and pre-converted to the units the sensors
use: an automation should be able to drop a value straight into a
notification without any Jinja arithmetic and without knowing Bosch's
nested response shape. Every field is optional in the API responses, so
every value may be None - templates have to cope with that either way, and
None is far easier to test for than a silently substituted 0.
"""
from __future__ import annotations

import math
from typing import Any

__all__ = ["build_new_activity_payload"]


def _num(activity: dict[str, Any], *path: str) -> float | None:
    """Return a nested numeric field as a float, or None if unusable."""
    node: Any = activity
    for key in path:
        if not isinstance(node, dict):
            return None
        node = node.get(key)
    try:
        value = float(node)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    # A NaN would go onto the event bus and then compare false against
    # itself in every template that touches it; an infinity would render as
    # "inf". Both are better reported as "no value".
    return value if math.isfinite(value) else None


def build_new_activity_payload(
    activity: dict[str, Any], bike_id: str | None
) -> dict[str, Any]:
    """Build the event payload for one freshly appeared ride.

    ``bike_id`` is passed in rather than read off the activity: the activity
    dicts never carry one, attribution lives in the coordinator's separate
    activity->bike mapping.
    """
    if not isinstance(activity, dict):
        activity = {}

    distance_m = _num(activity, "distance")
    duration_s = _num(activity, "durationWithoutStops")
    trick = activity.get("_trick_check")
    return {
        "bike_id": bike_id,
        "activity_id": activity.get("id"),
        "title": activity.get("title"),
        "start_time": activity.get("startTime"),
        "distance_km": round(distance_m / 1000, 2) if distance_m is not None else None,
        "duration_min": round(duration_s / 60, 1) if duration_s is not None else None,
        "average_speed": _num(activity, "speed", "average"),
        "max_speed": _num(activity, "speed", "maximum"),
        "elevation_gain": _num(activity, "elevation", "gain"),
        # Bosch calls this "caloriesBurned", not "calories" - same key the
        # last_ride_calories sensor reads.
        "calories": _num(activity, "caloriesBurned"),
        # Lets a "nice ride!" automation single out the rides that actually
        # have Trick Check data without re-deriving it from the nested dict.
        "has_tricks": bool(activity.get("_trick_hint")),
        "tricks": trick if isinstance(trick, dict) else None,
    }
