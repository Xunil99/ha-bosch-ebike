"""Pure helpers for COBI (SmartphoneHub with the COBI.Bike app).

Bosch's "Activity & Hub API (COBI)" returns two flat lists for the whole
account: the hubs (serialNumber, partNumber, role, activatedAt) and the rides
(id, startTime, endTime, totalDistance, bikeType, elevationGain, avgSpeed,
maxSpeed, durationWithoutStops). There are no bikes, no battery, no odometer
and no track, and the rides carry no hub.

This module maps the rides onto the activity summary shape of the Smart
System, so the existing ride sensors read them unchanged, works out the unit
of durationWithoutStops (the spec does not name it), sums calendar periods and
builds a diagnostics block of field names and counts.

No Home Assistant imports, so tests/test_cobi.py can load it directly. Every
function tolerates missing, None and wrong-typed input and never raises.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from datetime import datetime, timedelta
from typing import Any, Iterable

ROLES = ("OWNER", "GUEST")
BIKE_TYPES = ("BIOBIKE", "ELECTRIC_25", "ELECTRIC_45")
UNITS = ("s", "ms", "min")
UNCLEAR = "unclear"

# A moving time may exceed the wall clock time a little (rounding, clock skew
# between the hub and Bosch), never by more than this.
_WALL_TOLERANCE = 1.05
_TO_SECONDS = {"s": 1.0, "ms": 0.001, "min": 60.0}
# Field names longer than this are not echoed into the diagnostics.
_MAX_FIELD_NAME = 64


def _num(value: Any) -> float | None:
    """A finite int/float, else None (bools and strings are not numbers here)."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return value if math.isfinite(value) else None


def _parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def _wall_seconds(raw: dict[str, Any]) -> float | None:
    start = _parse_time(raw.get("startTime"))
    end = _parse_time(raw.get("endTime"))
    if start is None or end is None:
        return None
    wall = (end - start).total_seconds()
    return wall if wall > 0 else None


def _speed_seconds(raw: dict[str, Any]) -> float | None:
    """The moving time the average speed implies: distance / avgSpeed."""
    distance = _num(raw.get("totalDistance"))
    speed = _num(raw.get("avgSpeed"))
    if not distance or not speed or distance <= 0 or speed <= 0:
        return None
    return distance / 1000 / speed * 3600


def _ride_unit(raw: dict[str, Any]) -> str | None:
    """The unit one ride's durationWithoutStops is most plausibly written in.

    Only candidates that fit into the wall clock time are admissible. Among
    them the one closest (by ratio) to the time the average speed implies
    wins; without a usable speed the wall clock time is the reference.
    Bosch may have averaged the speed over the wall clock time, so the
    reference can be much longer than the moving time; a ratio comparison
    still picks the right candidate then, a fixed tolerance would not.
    Returns None when the ride cannot decide anything.
    """
    duration = _num(raw.get("durationWithoutStops"))
    wall = _wall_seconds(raw)
    if duration is None or duration <= 0 or wall is None:
        return None
    admissible = {
        unit: duration * factor
        for unit, factor in _TO_SECONDS.items()
        if 0 < duration * factor <= wall * _WALL_TOLERANCE
    }
    if not admissible:
        return None
    if len(admissible) == 1:
        return next(iter(admissible))
    reference = _speed_seconds(raw) or wall
    return min(admissible, key=lambda u: abs(math.log(admissible[u] / reference)))


def detect_duration_unit(raw_activities: Any) -> tuple[str | None, dict[str, int]]:
    """Decide the unit of durationWithoutStops once for the whole list.

    Returns (verdict, counts). The verdict is "s", "ms" or "min" when more
    than half of the rides that could decide agree, "unclear" when they do
    not, and None when no ride could decide (every value null, or no usable
    rides at all). counts has one entry per unit plus "undecided" (a value
    that fits no unit, or a ride without a usable wall clock time) and "null".
    """
    counts = {"s": 0, "ms": 0, "min": 0, "undecided": 0, "null": 0}
    if not isinstance(raw_activities, list):
        return None, counts
    for raw in raw_activities:
        if not isinstance(raw, dict):
            continue
        if raw.get("durationWithoutStops") is None:
            if "id" in raw:
                counts["null"] += 1
            continue
        unit = _ride_unit(raw)
        counts[unit or "undecided"] += 1
    decided = sum(counts[u] for u in UNITS)
    if decided == 0:
        return None, counts
    best = max(UNITS, key=lambda u: counts[u])
    if counts[best] * 2 > decided:
        return best, counts
    return UNCLEAR, counts


def normalize_activity(raw: Any, unit: str | None) -> dict[str, Any] | None:
    """One COBI ride in the Smart System summary shape, or None without an id.

    durationWithoutStops comes out in seconds. When the unit is unclear, the
    value is missing, or the converted value does not fit into the ride, the
    wall clock time stands in and the ride is marked
    ``_cobi_duration_estimated``.
    """
    if not isinstance(raw, dict):
        return None
    rid = raw.get("id")
    if rid is None or isinstance(rid, bool) or not str(rid):
        return None

    start = raw.get("startTime") if _parse_time(raw.get("startTime")) else None
    end = raw.get("endTime") if _parse_time(raw.get("endTime")) else None
    wall = _wall_seconds(raw)

    duration = _num(raw.get("durationWithoutStops"))
    seconds: float | None = None
    if duration is not None and unit in _TO_SECONDS:
        candidate = duration * _TO_SECONDS[unit]
        if candidate >= 0 and (wall is None or candidate <= wall * _WALL_TOLERANCE):
            seconds = candidate
    estimated = seconds is None
    if seconds is None and wall is not None:
        seconds = wall

    bike_type = raw.get("bikeType")
    distance = _num(raw.get("totalDistance"))
    return {
        "id": str(rid),
        "startTime": start,
        "endTime": end,
        "distance": distance,
        "durationWithoutStops": round(seconds) if seconds is not None else None,
        "speed": {
            "average": _num(raw.get("avgSpeed")),
            "maximum": _num(raw.get("maxSpeed")),
        },
        "elevation": {"gain": _num(raw.get("elevationGain"))},
        "_cobi_bike_type": bike_type if isinstance(bike_type, str) and bike_type else None,
        "_cobi_duration_estimated": estimated,
    }


def normalize_hub(raw: Any) -> dict[str, Any] | None:
    """One hub, or None without a serial number (nothing to key a device by)."""
    if not isinstance(raw, dict):
        return None
    serial = raw.get("serialNumber")
    if not isinstance(serial, str) or not serial.strip():
        return None
    part = raw.get("partNumber")
    role = raw.get("role")
    activated = raw.get("activatedAt")
    return {
        "serial": serial.strip(),
        "part": part if isinstance(part, str) and part else None,
        "role": role.lower() if role in ROLES else None,
        "activated_at": activated if _parse_time(activated) else None,
    }


def rides_by_bike_type(activities: Iterable[Any] | None) -> dict[str, int]:
    """How many rides each bikeType has; rides without one count as UNKNOWN."""
    counter: Counter[str] = Counter()
    for act in activities or []:
        if isinstance(act, dict):
            counter[act.get("_cobi_bike_type") or "UNKNOWN"] += 1
    return dict(counter)


def period_starts(now_local: datetime) -> dict[str, datetime]:
    """Local midnight on Monday of this ISO week, the 1st of the month, 1 January."""
    tz = now_local.tzinfo
    today = now_local.date()
    monday = today - timedelta(days=today.weekday())
    return {
        "week": datetime(monday.year, monday.month, monday.day, tzinfo=tz),
        "month": datetime(today.year, today.month, 1, tzinfo=tz),
        "year": datetime(today.year, 1, 1, tzinfo=tz),
    }


def period_totals(activities: Iterable[Any] | None, now_local: datetime) -> dict[str, dict[str, Any]]:
    """Distance (km) and ride count of this week, month and year.

    Calendar periods in the local time of now_local (an aware datetime); a
    ride counts for the period it starts in. Rides without a start are left
    out, rides without a distance count as rides with 0 km.
    """
    tz = now_local.tzinfo
    today = now_local.date()
    iso_now = today.isocalendar()
    starts = period_starts(now_local)
    totals = {
        key: {"distance_km": 0.0, "rides": 0, "start": start}
        for key, start in starts.items()
    }
    for act in activities or []:
        if not isinstance(act, dict):
            continue
        start = _parse_time(act.get("startTime"))
        if start is None:
            continue
        local = start.astimezone(tz).date()
        km = (_num(act.get("distance")) or 0.0) / 1000
        matches = {
            "week": local.isocalendar()[:2] == iso_now[:2],
            "month": (local.year, local.month) == (today.year, today.month),
            "year": local.year == today.year,
        }
        for key, hit in matches.items():
            if hit:
                totals[key]["rides"] += 1
                totals[key]["distance_km"] += km
    for value in totals.values():
        value["distance_km"] = round(value["distance_km"], 2)
    return totals


def data_missing(hubs: Iterable[Any] | None, activities: Iterable[Any] | None) -> bool:
    """True when Bosch lists neither a hub nor a ride for the account."""
    return not list(hubs or []) and not list(activities or [])


def _type_name(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "str"
    if isinstance(value, list):
        return "list"
    if isinstance(value, dict):
        return "object"
    return "other"


def _fields(items: list[dict[str, Any]]) -> list[str]:
    return sorted({
        k for item in items for k in item
        if isinstance(k, str) and len(k) <= _MAX_FIELD_NAME
    })


def diagnostics_summary(raw_hubs: Any, raw_activities: Any) -> dict[str, Any]:
    """Field names and counts of what Bosch sent. Never a value.

    Roles and bike types are counted only under their documented enum names
    (anything else is "OTHER"), so no free text from the payload can end up
    in the file; field names are echoed only up to a sane length.
    """
    hubs = [h for h in raw_hubs if isinstance(h, dict)] if isinstance(raw_hubs, list) else []
    acts = (
        [a for a in raw_activities if isinstance(a, dict)]
        if isinstance(raw_activities, list) else []
    )
    roles: Counter[str] = Counter(
        h.get("role") if h.get("role") in ROLES else "OTHER" for h in hubs
    )
    bike_types: Counter[str] = Counter(
        a.get("bikeType") if a.get("bikeType") in BIKE_TYPES
        else ("null" if a.get("bikeType") is None else "OTHER")
        for a in acts
    )
    activity_fields = _fields(acts)
    null_counts = {
        f: sum(1 for a in acts if f in a and a[f] is None) for f in activity_fields
    }
    field_types = {
        f: dict(Counter(_type_name(a[f]) for a in acts if f in a))
        for f in activity_fields
    }
    verdict, unit_counts = detect_duration_unit(acts)
    return {
        "hub_count": len(hubs),
        "hub_roles": dict(roles),
        "hub_fields": _fields(hubs),
        "activity_count": len(acts),
        "activity_fields": activity_fields,
        "null_counts": null_counts,
        "field_types": field_types,
        "bike_type_counts": dict(bike_types),
        "duration_unit": {"verdict": verdict, "counts": unit_counts},
    }


_TIME_RE = re.compile(r"\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:?\d{2})?)?")
_CLOCK_RE = re.compile(r"\d{2}:\d{2}:\d{2}")
_LONG_NUMBER_RE = re.compile(r"\d{6,}")


def scrub_text(text: Any) -> str | None:
    """An error text without dates, times and long numbers (ids, serials).

    Status codes and words stay readable; this is for the diagnostics file,
    which promises no timestamps and no ids.
    """
    if text is None:
        return None
    text = _TIME_RE.sub("<time>", str(text))
    text = _CLOCK_RE.sub("<time>", text)
    return _LONG_NUMBER_RE.sub("<number>", text)


# --- status of the last fetch per endpoint (issue #101) ---------------------

ENDPOINTS = ("hubs", "activities")
# Statuses with which Bosch refuses a request outright. Issue #101: the hub
# list answered 400 (not in Bosch's COBI spec) right after a good sign in.
_REFUSED = (400, 403)
_MAX_REPLY = 300


def _http_status(err: Any) -> int | None:
    status = getattr(err, "status", None)
    if isinstance(status, bool) or not isinstance(status, int):
        return None
    return status


def fetch_result(err: BaseException | Any | None) -> dict[str, Any]:
    """The outcome of one request, for the diagnostics and the repair hint.

    result is "ok", the HTTP status, or the error class name (a timeout, a
    network error). reply is Bosch's own answer (api._get keeps it on the
    exception as .body), scrubbed like every error text of the diagnostics
    and cut to a few hundred characters.
    """
    if err is None:
        return {"result": "ok", "reply": None}
    status = _http_status(err)
    body = " ".join(str(getattr(err, "body", "") or "").split())
    reply = scrub_text(body)[:_MAX_REPLY] if body else None
    return {
        "result": status if status is not None else type(err).__name__,
        "reply": reply,
    }


def refused(result: Any) -> bool:
    """True for a result with which Bosch refused the request (400 or 403)."""
    return not isinstance(result, bool) and result in _REFUSED


def fetch_status_summary(statuses: Any, now: datetime) -> dict[str, Any]:
    """Per endpoint: result, scrubbed reply and whole minutes since the fetch.

    No timestamp: the diagnostics file promises none. None for an endpoint
    that was not fetched yet.
    """
    statuses = statuses if isinstance(statuses, dict) else {}
    summary: dict[str, Any] = {}
    for endpoint in ENDPOINTS:
        status = statuses.get(endpoint)
        if not isinstance(status, dict):
            summary[endpoint] = None
            continue
        at = status.get("at")
        minutes = None
        if isinstance(at, datetime) and at.tzinfo is not None:
            minutes = max(0, int((now - at).total_seconds() // 60))
        summary[endpoint] = {
            "result": status.get("result"),
            "reply": status.get("reply"),
            "minutes_ago": minutes,
        }
    return summary
