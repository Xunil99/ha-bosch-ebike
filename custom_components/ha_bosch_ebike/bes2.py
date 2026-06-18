"""Pure normalization for eBike System 2 (BES2) API responses.

Maps BES2 (eBike System 2) bike / activity / track payloads into the SAME
internal shapes the integration already builds for Smart System (BES3), so the
existing sensors and cards consume them unchanged.

Kept dependency-free and side-effect-free (no Home Assistant imports) so it can
be unit-tested without a Home Assistant runtime, mirroring profile_extra.py.
Every function tolerates missing / None / wrong-typed input and never raises.
"""
from __future__ import annotations

from typing import Any


def _get(d: Any, *keys: str, default: Any = None) -> Any:
    cur = d
    for k in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(k)
    return cur if cur is not None else default


def _num(v: Any) -> bool:
    """True if v is a real number (int/float) and not a bool."""
    return isinstance(v, (int, float)) and not isinstance(v, bool)


# ---------------------------------------------------------------------------
# Bike — BES2 driveUnit/headUnits/batteries -> BES3 bike shape
# ---------------------------------------------------------------------------

def normalize_bike(b2: dict) -> dict:
    """Map a BES2 bike object into the BES3 bike dict the sensors read.

    Produces id/driveUnit/batteries/(headUnit), plus _bes2_serial/_bes2_part
    so the coordinator can re-query the BES2 detail endpoints.
    """
    du = _get(b2, "driveUnit", default={}) or {}
    serial = du.get("serialNumber")
    part = du.get("partNumber")
    synthetic = f"{serial or ''}-{part or ''}"
    if synthetic == "-":
        synthetic = "bes2"

    batteries = [
        {
            "productName": x.get("deviceName"),
            "serialNumber": x.get("serialNumber"),
            "partNumber": x.get("partNumber"),
        }
        for x in (_get(b2, "batteries", default=[]) or [])
        if isinstance(x, dict)
    ]

    out: dict = {
        "id": synthetic,
        "driveUnit": {
            "productName": du.get("productLineName") or du.get("deviceName"),
            "serialNumber": serial,
            "partNumber": part,
        },
        "batteries": batteries,
        "_bes2_serial": serial,
        "_bes2_part": part,
    }

    head_units = [h for h in (_get(b2, "headUnits", default=[]) or [])
                  if isinstance(h, dict)]
    if head_units:
        first = head_units[0]
        out["headUnit"] = {
            "productName": first.get("deviceName") or first.get("deviceLineName"),
        }
    return out


# ---------------------------------------------------------------------------
# Activity summary — BES2 TRIP -> BES3 activity summary shape
# ---------------------------------------------------------------------------

def normalize_activity_summary(a2: dict) -> dict:
    """Map a BES2 TRIP summary into the BES3 activity summary dict.

    cadence/riderPower/elevation are returned empty ({}) here and filled in
    later by enrich_summary_from_detail once the detail endpoint is fetched.
    """
    rides = [r for r in (_get(a2, "bikeRides", default=[]) or [])
             if isinstance(r, dict)]

    raw_id = _get(a2, "id")
    activity_id = str(raw_id) if raw_id is not None else None

    distance_raw = _get(a2, "totalDistance")
    distance = round(distance_raw) if _num(distance_raw) else None

    dur_ms = _get(a2, "durationWithoutStops")
    duration = round(dur_ms / 1000) if _num(dur_ms) else None

    avg_speeds = [r.get("avgSpeed") for r in rides if _num(r.get("avgSpeed"))]
    max_speeds = [r.get("maxSpeed") for r in rides if _num(r.get("maxSpeed"))]
    speed_avg = sum(avg_speeds) / len(avg_speeds) if avg_speeds else None
    speed_max = max(max_speeds) if max_speeds else None

    calories = [r.get("caloriesBurned") for r in rides
                if _num(r.get("caloriesBurned"))]
    calories_total = sum(calories) if calories else None

    return {
        "id": activity_id,
        "distance": distance,
        "durationWithoutStops": duration,
        "startTime": _get(a2, "startTime"),
        "endTime": _get(a2, "endTime"),
        "title": _get(a2, "title"),
        "speed": {"average": speed_avg, "maximum": speed_max},
        "cadence": {},
        "riderPower": {},
        "elevation": {},
        "caloriesBurned": calories_total,
    }


def enrich_summary_from_detail(summary: dict, detail: dict) -> dict:
    """Fill cadence/riderPower/elevation (and missing speed/calories) from detail.

    Only sets a value when the detail field is numeric. Tolerates detail being
    None / {} and never raises. Mutates and returns summary.
    """
    if not isinstance(summary, dict):
        return summary
    d = detail if isinstance(detail, dict) else {}

    cadence = summary.setdefault("cadence", {})
    rider_power = summary.setdefault("riderPower", {})
    elevation = summary.setdefault("elevation", {})
    speed = summary.setdefault("speed", {})

    if _num(d.get("avgCadence")):
        cadence["average"] = d.get("avgCadence")
    if _num(d.get("maxCadence")):
        cadence["maximum"] = d.get("maxCadence")
    if _num(d.get("avgRiderPower")):
        rider_power["average"] = d.get("avgRiderPower")
    if _num(d.get("elevationGain")):
        elevation["gain"] = d.get("elevationGain")
    if _num(d.get("elevationLoss")):
        elevation["loss"] = d.get("elevationLoss")

    if speed.get("maximum") is None and _num(d.get("maxSpeed")):
        speed["maximum"] = d.get("maxSpeed")
    if speed.get("average") is None and _num(d.get("avgSpeed")):
        speed["average"] = d.get("avgSpeed")
    if summary.get("caloriesBurned") is None and _num(d.get("caloriesBurned")):
        summary["caloriesBurned"] = d.get("caloriesBurned")

    return summary


# ---------------------------------------------------------------------------
# Track — BES2 parallel per-ride arrays -> flat BES3 activityDetails list
# ---------------------------------------------------------------------------

def normalize_track(detail: dict) -> dict:
    """Zip the BES2 parallel per-ride arrays into a flat activityDetails list.

    coordinates is a list of rides, each ride a list of {lat,lon}-or-null
    points. altitudes/speed are parallel ride-indexed arrays of scalars. Any
    array (or per-ride/per-point index) may be missing or shorter; guard every
    access so we never IndexError and skip points without lat/lon.
    """
    coords = _get(detail, "coordinates", default=[]) or []
    altitudes = _get(detail, "altitudes", default=[]) or []
    speeds = _get(detail, "speed", default=[]) or []

    points: list[dict] = []
    for r, ride in enumerate(coords):
        if not isinstance(ride, list):
            continue
        alt_ride = altitudes[r] if r < len(altitudes) else None
        spd_ride = speeds[r] if r < len(speeds) else None
        alt_ride = alt_ride if isinstance(alt_ride, list) else []
        spd_ride = spd_ride if isinstance(spd_ride, list) else []
        for i, pt in enumerate(ride):
            if not isinstance(pt, dict):
                continue
            lat = pt.get("latitude")
            lon = pt.get("longitude")
            if lat is None or lon is None:
                continue
            alt = alt_ride[i] if i < len(alt_ride) else None
            spd = spd_ride[i] if i < len(spd_ride) else None
            points.append({
                "latitude": lat,
                "longitude": lon,
                "altitude": alt if _num(alt) else None,
                "speed": spd if _num(spd) else None,
            })
    return {"activityDetails": points}


def track_probe(detail: Any) -> dict:
    """PII-safe shape report of a raw BES2 activity detail (for diagnostics).

    Reveals WHETHER the GPS track is present in the JSON ``coordinates`` field
    and HOW it is structured — without leaking any actual coordinate value.
    Reports the detail's top-level keys, the array shapes of
    coordinates/altitudes/speed, the key names of the first point, and the
    point count ``normalize_track`` extracts.
    """
    if not isinstance(detail, dict):
        return {"detail_type": type(detail).__name__}

    def _shape(x: Any) -> Any:
        if x is None:
            return None
        if not isinstance(x, list):
            return {"type": type(x).__name__}
        inner = x[0] if x else None
        if isinstance(inner, list):
            return {"rides": len(x), "first_ride_len": len(inner)}
        return {"len": len(x),
                "first_type": type(inner).__name__ if inner is not None else None}

    coords = detail.get("coordinates")
    probe: dict = {
        "detail_keys": sorted(detail.keys()),
        "coordinates": _shape(coords),
        "altitudes": _shape(detail.get("altitudes")),
        "speed": _shape(detail.get("speed")),
        "elevationGain_numeric": _num(detail.get("elevationGain")),
        "maxAltitude_numeric": _num(detail.get("maxAltitude")),
        "normalized_point_count": len(normalize_track(detail).get("activityDetails", [])),
    }
    # Key names of the first point (latitude/longitude vs lat/lng?) — names only.
    if (isinstance(coords, list) and coords
            and isinstance(coords[0], list) and coords[0]
            and isinstance(coords[0][0], dict)):
        probe["first_point_keys"] = sorted(coords[0][0].keys())
    return probe
