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

    # Confirmed via diagnostics against real BES2 payloads (forum report,
    # Joesy/Joachim): the TRIP object itself never carries a "title" key at
    # all. The rider-given name lives one level down, on the first ride
    # segment (bikeRides[0].title) - a trip is apparently modelled as one or
    # more constituent rides, and the name belongs to the ride, not the
    # trip. Falls back to the old trip-level lookup too, harmlessly, in case
    # some other BES2 payload shape does carry it there.
    title = (rides[0].get("title") if rides else None) or _get(a2, "title")

    return {
        "id": activity_id,
        "distance": distance,
        "durationWithoutStops": duration,
        "startTime": _get(a2, "startTime"),
        "endTime": _get(a2, "endTime"),
        "title": title,
        "speed": {"average": speed_avg, "maximum": speed_max},
        "cadence": {},
        "riderPower": {},
        "elevation": {},
        "caloriesBurned": calories_total,
    }


# Per-ride distances may differ from the trip total by this much before the
# per-ride data is distrusted. A unit mix-up (km vs m) would be off by 1000x,
# so a generous bound still catches it.
_RIDE_SUM_TOLERANCE_M = 1000.0
_RIDE_SUM_TOLERANCE_RATIO = 0.15


def trip_id_of(activity_id: Any) -> str | None:
    """Trip id behind an activity id.

    Activities split out of a multi-ride trip carry ``"<trip_id>-<token>"``
    (see normalize_trip_activities); every other activity id already is the
    trip id. Trip ids are plain integers, so the first "-" separates safely.
    """
    if activity_id is None:
        return None
    head = str(activity_id).split("-", 1)[0].strip()
    return head or None


def trip_split_blocker(a2: dict) -> str | None:
    """Why a trip is NOT split into per-ride activities, or None if it is.

    The one place that decides this, shared by normalize_trip_activities and
    the coordinator's debug log, so "why did my trip stay one activity" can be
    answered from the log alone (the per-ride fields are documented, but a
    live payload can differ from the documentation).
    """
    if _get(a2, "id") is None:
        return "trip has no id"
    rides = [r for r in (_get(a2, "bikeRides", default=[]) or [])
             if isinstance(r, dict)]
    if len(rides) < 2:
        return f"fewer than two rides ({len(rides)})"

    dist_sum = 0.0
    for i, r in enumerate(rides):
        start = r.get("startTime")
        if not isinstance(start, str) or not start.strip():
            return f"ride {i} has no startTime"
        if not _num(r.get("totalDistance")):
            return f"ride {i} has no numeric totalDistance"
        dist_sum += r["totalDistance"]

    trip_total = _get(a2, "totalDistance")
    if _num(trip_total):
        allowed = max(_RIDE_SUM_TOLERANCE_M,
                      _RIDE_SUM_TOLERANCE_RATIO * abs(trip_total))
        if abs(dist_sum - trip_total) > allowed:
            return (f"ride distances add up to {dist_sum:.0f} m but the "
                    f"trip total is {trip_total:.0f} m")
    return None


def normalize_trip_activities(a2: dict) -> list[dict]:
    """Expand a BES2 TRIP into one activity per bike ride.

    Bosch's BES2 API calls a TRIP an "activity", but a trip is a container of
    one or more bike rides, and it stays open (``isCompleted`` false) so new
    rides keep being appended to it. Mapping the whole trip to one activity
    meant an open trip never produced a new activity id, so no new-ride event
    fired and every "last ride" value showed the trip's running totals
    (issue #88).

    A trip with two or more rides becomes one activity per ride, oldest
    first. The oldest ride keeps the plain trip id, so a trip that grows from
    one ride to two keeps its first id and adds exactly one new one. The
    other rides get ``"<trip_id>-<digits of their start time>"``: derived
    from the ride itself rather than its position, so a ride that Bosch
    inserts later (a delayed sync) does not shift the ids of the others.
    Each ride dict carries ``_bes2_*`` keys that map it back to the trip and
    to its place in the API's ``bikeRides`` array (needed to find its track).

    Falls back to the single trip-level activity - exactly the pre-#88
    behaviour - when the trip has fewer than two rides, when any ride lacks a
    start time or distance, or when the per-ride distances do not add up to
    the trip total (the documented schema could be out of date). Never
    raises.
    """
    trip = normalize_activity_summary(a2)
    if trip_split_blocker(a2) is not None:
        return [trip]
    rides = [r for r in (_get(a2, "bikeRides", default=[]) or [])
             if isinstance(r, dict)]
    trip_id = trip["id"]

    n = len(rides)
    order = sorted(range(n), key=lambda i: (rides[i]["startTime"], i))
    order_ok = order == list(range(n))
    trip_title = _get(a2, "title")
    if not isinstance(trip_title, str) or not trip_title:
        trip_title = None

    out: list[dict] = []
    used_ids: set[str] = {trip_id}
    for chrono, pos in enumerate(order):
        r = rides[pos]
        if chrono == 0:
            rid = trip_id
        else:
            token = "".join(ch for ch in r["startTime"] if ch.isdigit())
            rid = f"{trip_id}-{token or chrono}"
            while rid in used_ids:
                rid += "x"
            used_ids.add(rid)

        dur_ms = r.get("durationWithoutStops")
        avg, mx = r.get("avgSpeed"), r.get("maxSpeed")
        cal = r.get("caloriesBurned")
        end = r.get("endTime")
        title = r.get("title")
        out.append({
            "id": rid,
            "distance": round(r["totalDistance"]),
            "durationWithoutStops": round(dur_ms / 1000) if _num(dur_ms) else None,
            "startTime": r["startTime"],
            "endTime": end if isinstance(end, str) and end else None,
            "title": title if isinstance(title, str) and title else trip_title,
            "speed": {
                "average": round(avg, 1) if _num(avg) else None,
                "maximum": round(mx, 1) if _num(mx) else None,
            },
            "cadence": {},
            "riderPower": {},
            "elevation": {},
            "caloriesBurned": cal if _num(cal) else None,
            "_bes2_trip_id": trip_id,
            "_bes2_ride_pos": pos,
            "_bes2_ride_count": n,
            "_bes2_order_ok": order_ok,
            "_bes2_primary": chrono == 0,
        })
    return out


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
    return {"activityDetails": _track_points(coords_rides, alts, spds)}


def _track_points(coords_rides: Any, alts: list, spds: list,
                  only_group: int | None = None) -> list[dict]:
    """Walk the coordinate groups by one GLOBAL point index (see normalize_track).

    ``only_group`` restricts the output to a single coordinate group while the
    index still advances over every group before it, so the altitude/speed
    lookup stays aligned.
    """
    points: list[dict] = []
    gi = -1  # global coordinate-point index across all coordinate rides
    for group, ride in enumerate(coords_rides):
        if not isinstance(ride, list):
            continue
        for pt in ride:
            gi += 1
            if only_group is not None and group != only_group:
                continue
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
    return points


def normalize_ride_track(detail: dict, ride_pos: int, ride_count: int) -> dict | None:
    """Track of ONE ride out of a multi-ride trip detail, or None.

    The trip detail holds every ride's points in ``coordinates``, one group
    per ride. A ride can only be told apart when there is exactly one group
    per ride; real payloads sometimes merge them (one group for a trip of two
    rides), and then guessing a split would attach the wrong route to a ride.
    None means "cannot isolate it", and the caller falls back to the whole
    trip. ``ride_pos`` is the ride's position in the API's own ``bikeRides``
    array, the order the detail groups are assumed to follow.
    """
    if not isinstance(detail, dict):
        return None
    if not isinstance(ride_pos, int) or not isinstance(ride_count, int):
        return None
    if ride_count < 2 or not 0 <= ride_pos < ride_count:
        return None
    coords_rides = _get(detail, "coordinates", default=[]) or []
    if not isinstance(coords_rides, list) or len(coords_rides) != ride_count:
        return None
    alts = _flatten_rides(_get(detail, "altitudes", default=[]))
    spds = _flatten_rides(_get(detail, "speed", default=[]))
    return {"activityDetails": _track_points(coords_rides, alts, spds,
                                             only_group=ride_pos)}


def track_for_activity(detail: dict, activity: dict | None) -> tuple[dict, str]:
    """Return ``(track, scope)`` for one activity out of a trip detail.

    ``scope`` is ``"ride"`` when the track is isolated to the activity's own
    ride, ``"trip"`` when it is the whole trip's route: an unsplit trip, an
    unknown activity, a trip whose ``bikeRides`` order is not chronological
    (the detail's group order cannot then be trusted to match), or one whose
    track groups cannot be told apart per ride.
    """
    if isinstance(activity, dict):
        count = activity.get("_bes2_ride_count")
        if (isinstance(count, int) and count >= 2
                and activity.get("_bes2_order_ok") is True):
            ride = normalize_ride_track(detail, activity.get("_bes2_ride_pos"), count)
            if ride is not None:
                return ride, "ride"
    return normalize_track(detail), "trip"


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
