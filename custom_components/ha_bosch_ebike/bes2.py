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
    speed_avg = round(sum(avg_speeds) / len(avg_speeds), 1) if avg_speeds else None
    speed_max = round(max(max_speeds), 1) if max_speeds else None

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

    # Anzeige-Rundung: Trittfrequenz/Leistung/Höhe ganzzahlig, Speed auf 1
    # Nachkommastelle — die BES2-Detailwerte kommen sonst mit vielen Stellen.
    if _num(d.get("avgCadence")):
        cadence["average"] = round(d.get("avgCadence"))
    if _num(d.get("maxCadence")):
        cadence["maximum"] = round(d.get("maxCadence"))
    if _num(d.get("avgRiderPower")):
        rider_power["average"] = round(d.get("avgRiderPower"))
    if _num(d.get("elevationGain")):
        elevation["gain"] = round(d.get("elevationGain"))
    if _num(d.get("elevationLoss")):
        elevation["loss"] = round(d.get("elevationLoss"))

    if speed.get("maximum") is None and _num(d.get("maxSpeed")):
        speed["maximum"] = round(d.get("maxSpeed"), 1)
    if speed.get("average") is None and _num(d.get("avgSpeed")):
        speed["average"] = round(d.get("avgSpeed"), 1)
    if summary.get("caloriesBurned") is None and _num(d.get("caloriesBurned")):
        summary["caloriesBurned"] = d.get("caloriesBurned")

    return summary


# ---------------------------------------------------------------------------
# Track — BES2 parallel per-ride arrays -> flat BES3 activityDetails list
# ---------------------------------------------------------------------------

def _flatten_rides(arr: Any) -> list:
    """Concatenate the inner per-ride lists into one flat list (skip non-lists)."""
    out: list = []
    for ride in (arr if isinstance(arr, list) else []):
        if isinstance(ride, list):
            out.extend(ride)
    return out


def normalize_track(detail: dict) -> dict:
    """Zip the BES2 parallel arrays into a flat activityDetails list.

    ``coordinates`` is a list of rides, each ride a list of {lat,lon}-or-null
    points; ``altitudes``/``speed`` are parallel scalar arrays. Real data shows
    these may be grouped into a DIFFERENT number of rides than ``coordinates``
    (e.g. coordinates as one merged ride while altitudes are split in two), so
    zipping per-ride mis-aligns the tail. We instead walk the coordinate points
    by a single GLOBAL index and look altitude/speed up at the same global index
    in the flattened arrays. The index advances for every coordinate slot
    (including null/invalid points) so the scalar arrays — which carry one slot
    per coordinate point — stay aligned. Guarded so we never IndexError and skip
    points without lat/lon.
    """
    if not isinstance(detail, dict):
        return {"activityDetails": []}
    coords_rides = _get(detail, "coordinates", default=[]) or []
    alts = _flatten_rides(_get(detail, "altitudes", default=[]))
    spds = _flatten_rides(_get(detail, "speed", default=[]))

    points: list[dict] = []
    gi = -1  # global coordinate-point index across all coordinate rides
    for ride in coords_rides:
        if not isinstance(ride, list):
            continue
        for pt in ride:
            gi += 1
            if not isinstance(pt, dict):
                continue
            lat = pt.get("latitude")
            lon = pt.get("longitude")
            if lat is None or lon is None:
                continue
            alt = alts[gi] if 0 <= gi < len(alts) else None
            spd = spds[gi] if 0 <= gi < len(spds) else None
            points.append({
                "latitude": lat,
                "longitude": lon,
                "altitude": alt if _num(alt) else None,
                "speed": spd if _num(spd) else None,
            })
    return {"activityDetails": points}


# ---------------------------------------------------------------------------
# Statistics — BES2 /statistics lifetime totals
# ---------------------------------------------------------------------------

def normalize_statistics(raw: dict) -> dict:
    """Extract lifetime totals from the BES2 ``/statistics`` response.

    ``totalStatistics.distance`` and ``.elevationGain`` are in METRES,
    ``.yearlyDistance`` likewise. Returns only the numeric fields present.
    """
    if not isinstance(raw, dict):
        return {}
    tot = _get(raw, "totalStatistics", default={}) or {}
    out: dict = {}
    if _num(tot.get("distance")):
        out["total_distance_m"] = tot.get("distance")
    if _num(tot.get("elevationGain")):
        out["total_elevation_gain_m"] = tot.get("elevationGain")
    if _num(tot.get("yearlyDistance")):
        out["yearly_distance_m"] = tot.get("yearlyDistance")
    return out
