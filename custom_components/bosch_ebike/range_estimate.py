"""Pure range-estimation math for the Bosch eBike integration.

Deliberately free of Home Assistant imports so it can be unit-tested
standalone (see tests/test_range_estimate.py).
"""

from __future__ import annotations

from typing import Any

# Defaults mirror docs/plans/2026-06-10-range-estimate-design.md
DEFAULT_WINDOW_KM = 500.0
MIN_TOURS = 3
MIN_KM = 30.0
MIN_TOUR_KM = 0.5


def compute_range_estimate(
    activities: list[dict[str, Any]],
    activity_bike: dict[str, str],
    consumption: dict[str, dict[str, Any]],
    bike_id: str,
    window_km: float = DEFAULT_WINDOW_KM,
    fallback_all: bool = False,
) -> dict[str, Any] | None:
    """Distance-weighted average consumption over the last ~window_km.

    Walks activities newest-first, keeps tours that belong to the bike and
    have a valid consumption record, and accumulates until the distance
    window is filled (the tour crossing the threshold is still included).

    Returns ``{wh_per_km, tours_used, window_km, newest_tour_date}`` or
    ``None`` when the data base is too thin (< MIN_TOURS tours or < MIN_KM km).

    ``fallback_all=True`` treats unmapped activities as belonging to the
    bike (single-bike accounts where attribution is empty).
    """
    total_wh = 0.0
    total_km = 0.0
    tours = 0
    newest_date: str | None = None

    for activity in activities:
        aid = activity.get("id")
        if not aid:
            continue
        mapped = activity_bike.get(aid)
        if mapped != bike_id and not (mapped is None and fallback_all):
            continue
        entry = consumption.get(aid)
        if not entry:
            continue
        try:
            wh = float(entry.get("consumed_wh") or 0)
            km = float(activity.get("distance") or 0) / 1000.0
        except (TypeError, ValueError):
            continue
        if wh <= 0 or km <= MIN_TOUR_KM:
            continue

        total_wh += wh
        total_km += km
        tours += 1
        if newest_date is None:
            newest_date = activity.get("startTime")
        if total_km >= window_km:
            break

    if tours < MIN_TOURS or total_km < MIN_KM:
        return None

    return {
        "wh_per_km": round(total_wh / total_km, 2),
        "tours_used": tours,
        "window_km": round(total_km, 1),
        "newest_tour_date": newest_date,
    }
