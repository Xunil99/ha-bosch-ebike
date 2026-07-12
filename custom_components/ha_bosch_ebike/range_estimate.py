"""Pure range-estimation math for the Bosch eBike integration.

Deliberately free of Home Assistant imports so it can be unit-tested
standalone (see tests/test_range_estimate.py).
"""

from __future__ import annotations

import math
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


def track_distance_m(details: dict[str, Any]) -> float | None:
    """Total distance in metres covered by an activity's GPS track.

    Prefers Bosch's own cumulative per-point ``distance`` field (largest
    value wins — robust against a missing tail). Falls back to a haversine
    sum over the coordinates when no point carries a distance. Returns
    ``None`` when the track is unusable.
    """
    if not isinstance(details, dict):
        return None
    points = details.get("activityDetails") or []
    if not isinstance(points, list):
        return None
    best = 0.0
    coords: list[tuple[float, float]] = []
    for p in points:
        d = p.get("distance")
        if isinstance(d, (int, float)) and d > best:
            best = float(d)
        lat, lon = p.get("latitude"), p.get("longitude")
        if (
            isinstance(lat, (int, float))
            and isinstance(lon, (int, float))
            and not (lat == 0 and lon == 0)
            and -90.0 <= lat <= 90.0
            and -180.0 <= lon <= 180.0
        ):
            coords.append((float(lat), float(lon)))
    if best > 0:
        return best
    if len(coords) < 2:
        return None
    total = 0.0
    for (lat1, lon1), (lat2, lon2) in zip(coords, coords[1:]):
        p1 = math.radians(lat1)
        p2 = math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlmb = math.radians(lon2 - lon1)
        a = (
            math.sin(dphi / 2) ** 2
            + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
        )
        total += 2 * 6371000.0 * math.asin(math.sqrt(a))
    return total if total > 0 else None


def corrected_track_distance(
    summary_m: float,
    track_m: float | None,
    min_ratio: float = 1.05,
    min_absolute_m: float = 200.0,
) -> float | None:
    """GPS-track distance to use, or None to keep the summary (issue #31).

    Corrects the existing distance UPWARDS only — a partial/uploading track
    must never shrink a value — past small noise (default >5 % and >200 m),
    with an absolute sanity cap (500 km) against unit surprises or haversine
    outliers. There is deliberately NO relative cap: an unfinished ride
    reports only a partial summary, so the full track can be many times
    longer (the case that the old "max 2x summary" guard wrongly blocked).

    *min_ratio*/*min_absolute_m* can be raised by callers correcting a value
    that is normally MORE precise than a GPS track (e.g. a BLE-odometer-
    derived "ble_live" distance), so ordinary GPS noise (cold-start jitter,
    urban-canyon multipath) cannot override it — only a genuinely wrong value,
    clearly outside that noise band, should.
    """
    if track_m is None:
        return None
    if (
        track_m > summary_m * min_ratio
        and track_m - summary_m > min_absolute_m
        and track_m <= 500_000.0
    ):
        return round(track_m, 1)
    return None
