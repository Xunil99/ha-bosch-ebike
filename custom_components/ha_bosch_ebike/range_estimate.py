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

# Impossible (issue #78): no real e-bike ride uses this little energy for this
# much distance. This is the gate coordinator.py's _track_battery_consumption
# applies before it PERSISTS a split of the cloud's energy counter across a
# batch of newly seen rides. It has to stay this loose. The counter reaches
# the cloud late and in pieces, so a ride's first credit is routinely a
# fraction of its true energy, and the top-up window (issue #67) exists to
# complete it. A stricter write gate would refuse exactly those first
# credits, and with them the top-up that fixes them.
MIN_PLAUSIBLE_WH_PER_KM = 1.0

# Too good to be true for an AVERAGE (issue #78 follow-up): the estimate
# ignores a tour recorded below this. The per-tour figure still comes from
# that late, partial counter, or from a live SoC sample that can be stale, so
# a ride that ended up with too little energy is stored without anything
# being wrong at the time. It then pulls the average down and the range up,
# which is the unsafe direction (the route planner's battery check reads the
# same average). One real example: a ride of over 30 km with hundreds of
# metres of climbing stored with 41 Wh, 1.33 Wh/km, which cleared the 1.0
# floor above and by itself pushed the full battery range of that bike up by
# about 14 percent. The rides counted properly on that same bike sat between
# 7 and 14 Wh/km, so 2.5 is far below anything an assisted ride produces. A
# ride that really is this efficient (the motor mostly off) falls away too,
# which only errs towards a smaller range.
# Applied when the estimate is read, so it also cleans up entries that are
# already stored, whatever put them there.
MIN_REALISTIC_WH_PER_KM = 2.5

# How many of the ignored tours are listed (newest first) in the result, the
# sensor attributes and the log line. Enough to see whether they share one
# rate (a batch artefact) or are scattered (lag), small enough to stay an
# attribute and not a table.
MAX_IGNORED_SAMPLE = 5


def compute_range_estimate(
    activities: list[dict[str, Any]],
    activity_bike: dict[str, str],
    consumption: dict[str, dict[str, Any]],
    bike_id: str,
    window_km: float = DEFAULT_WINDOW_KM,
    fallback_all: bool = False,
) -> dict[str, Any]:
    """Distance-weighted average consumption over the last ~window_km.

    Walks activities newest-first, keeps tours that belong to the bike and
    have a usable consumption record, and accumulates until the distance
    window is filled (the tour crossing the threshold is still included).
    A tour with 0 Wh or below ``MIN_REALISTIC_WH_PER_KM`` is not used but
    counted, so it shows up in the diagnostics instead of vanishing.

    Always returns a dict: ``wh_per_km``, ``tours_used``, ``window_km``,
    ``newest_tour_date``, ``wh_per_km_min`` / ``wh_per_km_max`` (per-tour rates
    of the tours used), ``tours_used_by_source``, ``tours_ignored`` and
    ``tours_ignored_sample``. The source says where a tour's energy came from:
    ``ble_live`` (live SoC of the bridge) or ``cloud`` (the cloud's energy
    counter). They fail differently, and which one produced the tours that
    were ignored, or that still feed the average, is the first thing to know
    when an estimate looks wrong.
    ``wh_per_km`` is ``None`` when the data base is too thin (fewer than
    MIN_TOURS tours or MIN_KM km), but the rest still describes what was found,
    so a sensor without a value can say why. That matters most exactly then:
    when every tour got ignored there is no estimate left to look at.

    ``fallback_all=True`` treats unmapped activities as belonging to the
    bike (single-bike accounts where attribution is empty).
    """
    total_wh = 0.0
    total_km = 0.0
    tours = 0
    newest_date: str | None = None
    rate_min: float | None = None
    rate_max: float | None = None
    used_by_source: dict[str, int] = {}
    ignored = 0
    ignored_sample: list[dict[str, Any]] = []

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
        if km <= MIN_TOUR_KM:
            continue
        # Only the live-SoC path stamps a source on its entries; everything
        # else is a split of the cloud's energy counter.
        source = entry.get("source") or "cloud"
        # 0 Wh (and anything negative) falls under the floor as well.
        if wh / km < MIN_REALISTIC_WH_PER_KM:
            ignored += 1
            if len(ignored_sample) < MAX_IGNORED_SAMPLE:
                ignored_sample.append(
                    {
                        "date": str(activity.get("startTime") or "")[:10] or None,
                        "km": round(km, 1),
                        "wh": round(max(wh, 0.0), 1),
                        "source": source,
                    }
                )
            continue

        used_by_source[source] = used_by_source.get(source, 0) + 1
        rate = wh / km
        rate_min = rate if rate_min is None else min(rate_min, rate)
        rate_max = rate if rate_max is None else max(rate_max, rate)
        total_wh += wh
        total_km += km
        tours += 1
        if newest_date is None:
            newest_date = activity.get("startTime")
        if total_km >= window_km:
            break

    enough = tours >= MIN_TOURS and total_km >= MIN_KM
    return {
        "wh_per_km": round(total_wh / total_km, 2) if enough else None,
        "tours_used": tours,
        "window_km": round(total_km, 1),
        "newest_tour_date": newest_date,
        "wh_per_km_min": round(rate_min, 2) if rate_min is not None else None,
        "wh_per_km_max": round(rate_max, 2) if rate_max is not None else None,
        "tours_used_by_source": used_by_source,
        "tours_ignored": ignored,
        "tours_ignored_sample": ignored_sample,
    }


def range_estimate_attributes(est: dict[str, Any] | None) -> dict[str, Any]:
    """The calculation basis the range sensors expose as attributes.

    Empty before the first estimate exists (first poll, eBike System 2).
    Present with ``wh_per_km`` ``None`` when the data base is too thin, which
    is when these numbers are the only way to see why the sensor is empty.
    """
    if not est:
        return {}
    return {
        "wh_per_km": est.get("wh_per_km"),
        "tours_used": est.get("tours_used"),
        "window_km": est.get("window_km"),
        "newest_tour_date": est.get("newest_tour_date"),
        "wh_per_km_min": est.get("wh_per_km_min"),
        "wh_per_km_max": est.get("wh_per_km_max"),
        "tours_used_by_source": est.get("tours_used_by_source"),
        "tours_ignored": est.get("tours_ignored"),
        "tours_ignored_sample": est.get("tours_ignored_sample"),
    }


def range_estimate_log_key(est: dict[str, Any]) -> tuple[Any, ...]:
    """What makes a new log line worth writing: the value and what fed it.

    The estimate is recomputed every poll; logging it each time would bury
    everything else. A changed average, a different number of tours used or a
    different number left out is news, an unchanged one is not.
    """
    return (est.get("wh_per_km"), est.get("tours_used"), est.get("tours_ignored"))


def describe_range_estimate(est: dict[str, Any]) -> str:
    """One line for the INFO log: the estimate and the tours left out of it."""
    used = est.get("tours_used") or 0
    km = est.get("window_km") or 0.0
    wh_per_km = est.get("wh_per_km")
    by_source = est.get("tours_used_by_source") or {}
    sources = (
        " (" + ", ".join(f"{name} {n}" for name, n in sorted(by_source.items())) + ")"
        if by_source
        else ""
    )
    if wh_per_km is None:
        text = (
            f"no estimate yet, {used} usable tours{sources} over {km:.1f} km "
            f"(needs {MIN_TOURS} tours and {MIN_KM:.0f} km)"
        )
    else:
        lo = est.get("wh_per_km_min")
        hi = est.get("wh_per_km_max")
        spread = f", per tour {lo:.2f} to {hi:.2f}" if lo is not None and hi is not None else ""
        text = f"{wh_per_km:.2f} Wh/km from {used} tours{sources} over {km:.1f} km{spread}"
    ignored = est.get("tours_ignored") or 0
    if not ignored:
        return text
    sample = est.get("tours_ignored_sample") or []
    listed = ", ".join(
        f"{t['date']} {t['km']} km {t['wh']} Wh {t.get('source', 'cloud')}"
        for t in sample
    )
    more = ignored - len(sample)
    text += (
        f"; {ignored} tours ignored (0 Wh or below {MIN_REALISTIC_WH_PER_KM} Wh/km)"
    )
    if listed:
        text += f": {listed}"
    if more > 0:
        text += f" and {more} more"
    return text


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


def ble_distance_implausible(
    ble_m: float,
    track_m: float | None,
    cloud_m: float | None = None,
    min_ratio: float = 1.5,
    min_absolute_m: float = 500.0,
) -> bool:
    """True if a ble_live-derived distance disagrees with the ride's own
    GPS track by more than ordinary noise (issue #31/#54).

    A live-odometer sample can have a genuinely fresh timestamp while its
    VALUE still reflects an earlier, unrelated ride (a bike reconnecting
    right before departure, sampling an odometer that has not yet caught
    up with the prior ride) - a ride's own track, once fetched, is a
    physically-grounded, independent check for exactly that.

    The two directions are NOT symmetric, though. A track LARGER than the
    BLE value is always trustworthy evidence the BLE value is too low
    (tracks do not grow beyond the true distance - the same reasoning
    corrected_track_distance() above already relies on for a raw cloud
    summary). A track SMALLER than the BLE value is ambiguous on its own:
    the track can itself still be partially uploaded and legitimately
    under-report right after a ride ends, so that direction only counts
    when corroborated by *cloud_m* (the activity's own cloud-reported
    distance) closely agreeing with the smaller track - a genuinely
    partial track is very unlikely to also happen to closely match an
    independently computed cloud summary purely by coincidence. Without
    *cloud_m*, a smaller track alone is never treated as conclusive.
    """
    if track_m is None or track_m <= 0 or ble_m <= 0:
        return False
    lo, hi = sorted((ble_m, track_m))
    if not (hi > lo * min_ratio and hi - lo > min_absolute_m):
        return False
    if ble_m <= track_m:
        return True
    if cloud_m is None or cloud_m <= 0:
        return False
    return abs(track_m - cloud_m) <= max(cloud_m * 0.1, 200.0)
