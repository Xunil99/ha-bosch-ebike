"""Decide which bike an activity was ridden on (Home Assistant free).

Bosch's activity summaries carry a ``bikeId`` that is the ``id`` of the bike in
the bike profile, so a ride whose ``bikeId`` is one of the account's bikes is
attributed to exactly that bike. Everything else is attributed the way it always
was, by comparing odometers (see :func:`attribute_activities`), because
``bikeId`` is only used when Bosch delivers it and it names a bike we know:

* an activity without a ``bikeId``, or with the id of a bike that is not in the
  bike list (removed from the account, not released for this app), behaves
  exactly as before this module existed;
* the ``bikeId`` only matters when there are two or more bikes to tell apart.
  With one bike (or none) the result is exactly what it was before, so the
  single-bike accounts, which are the large majority, are not touched: an empty
  attribution there means "every ride belongs to the bike" to the sensors, and
  a partial one would make them drop the rides without a ``bikeId``.

Kept out of coordinator.py so the dependency-free test suite can run it.
"""

from __future__ import annotations

from typing import Any

# How far (metres) a bike's odometer may be from a ride's end odometer for the
# ride to count as that bike's.
DEFAULT_TOLERANCE_M = 1500.0


def _known_bike_ids(bikes: list[dict[str, Any]]) -> set[str]:
    return {bike["id"] for bike in bikes if isinstance(bike.get("id"), str) and bike["id"]}


def _bike_id_of(activity: dict[str, Any], known: set[str]) -> str | None:
    """The activity's own ``bikeId`` if it names one of *known*, else None."""
    bike_id = activity.get("bikeId")
    if isinstance(bike_id, str) and bike_id in known:
        return bike_id
    return None


def attribute_activities(
    bikes: list[dict[str, Any]],
    activities: list[dict[str, Any]],
    tolerance_m: float = DEFAULT_TOLERANCE_M,
) -> dict[str, str]:
    """Return ``{activity_id: bike_id}`` for every activity that can be attributed.

    1. With two or more *bikes*, an activity whose ``bikeId`` names one of them
       belongs to that bike.
    2. The rest are attributed by odometer: bikes report their current
       ``driveUnit.odometer`` (metres) and activities expose ``startOdometer``
       and ``distance``. Activities are processed from newest to oldest; each
       goes to the bike whose current odometer is closest to
       ``startOdometer + distance`` (within *tolerance_m*), and that bike's
       odometer is then "unwound" to ``startOdometer`` so the next-older ride
       can be matched. Activities that match no bike are left out.
       Single-bike accounts attribute every remaining activity to that bike.

    An activity attributed by ``bikeId`` unwinds its bike's odometer too (when
    the ride fits that odometer within the tolerance, the same bar the odometer
    matching itself needs), so the rides attributed by odometer further back keep
    seeing the odometer they would have seen if every ride had been matched that
    way.

    Returns an empty dict when no ride carries a known ``bikeId`` and no bike
    reports an odometer.
    """
    known = _known_bike_ids(bikes)
    by_bike_id: dict[str, str] = {}
    # Nothing for the bikeId to decide between with a single bike, and the rest
    # of this function (and the sensors reading its result) rely on the exact
    # old result there, including an empty one.
    if len(known) >= 2:
        for activity in activities:
            bike_id = _bike_id_of(activity, known)
            if activity.get("id") and bike_id is not None:
                by_bike_id[activity["id"]] = bike_id

    bike_odos: dict[str, float] = {}
    for bike in bikes:
        bid = bike.get("id")
        odo = (bike.get("driveUnit") or {}).get("odometer")
        if bid and isinstance(odo, (int, float)):
            bike_odos[bid] = float(odo)
    if not bike_odos:
        return by_bike_id

    # Single bike with an odometer: every activity belongs to it, except the ones
    # Bosch says belong to another bike of the account.
    if len(bike_odos) == 1:
        only_bike = next(iter(bike_odos))
        return {
            **{a["id"]: only_bike for a in activities if a.get("id")},
            **by_bike_id,
        }

    sorted_acts = sorted(
        [a for a in activities if a.get("id") and a.get("startOdometer") is not None],
        key=lambda a: a.get("startTime", ""),
        reverse=True,
    )

    attribution: dict[str, str] = {}
    for act in sorted_acts:
        try:
            start_odo = float(act["startOdometer"])
            distance = float(act.get("distance", 0) or 0)
        except (TypeError, ValueError):
            continue
        end_odo = start_odo + distance

        exact = by_bike_id.get(act["id"])
        if exact is not None:
            # Attributed by Bosch's own bikeId (added below). Unwind only when the
            # ride really fits this bike's odometer: a ride that does not (an
            # odometer reset, a ride recorded without the bike) must not drag the
            # odometer away from the rides still to be matched.
            if exact in bike_odos and abs(bike_odos[exact] - end_odo) <= tolerance_m:
                bike_odos[exact] = start_odo
            continue

        best_bike: str | None = None
        best_diff = float("inf")
        for bid, odo in bike_odos.items():
            diff = abs(odo - end_odo)
            if diff < best_diff:
                best_diff = diff
                best_bike = bid

        if best_bike is None or best_diff > tolerance_m:
            continue

        attribution[act["id"]] = best_bike
        # "Unwind" bike's odometer back to before this activity
        bike_odos[best_bike] = start_odo

    return {**attribution, **by_bike_id}


def summarize_attribution(
    bikes: list[dict[str, Any]],
    activities: list[dict[str, Any]],
    attribution: dict[str, str],
    manual: dict[str, str],
) -> dict[str, int]:
    """Counts for the diagnostics: how far Bosch's bikeId could be used.

    ``with_bike_id`` / ``bike_id_known`` are the numbers that show on a real
    account whether the bikeId is delivered for every ride and names one of the
    account's bikes; ``bike_id_unknown`` counts the rides that name a bike that is
    not in the bike list. The block holds only counts, no ids.
    """
    known = _known_bike_ids(bikes)
    rides = [a for a in activities if a.get("id")]
    with_bike_id = [a for a in rides if isinstance(a.get("bikeId"), str) and a["bikeId"]]
    known_ids = [a for a in with_bike_id if a["bikeId"] in known]
    return {
        "activities": len(rides),
        "with_bike_id": len(with_bike_id),
        "bike_id_known": len(known_ids),
        "bike_id_unknown": len(with_bike_id) - len(known_ids),
        "attributed": sum(1 for a in rides if a["id"] in attribution),
        "manually_assigned": sum(1 for a in rides if a["id"] in manual),
        # A known bikeId that the final attribution does not follow: only a manual
        # assignment can do that.
        "bike_id_overruled": sum(
            1 for a in known_ids if attribution.get(a["id"]) not in (None, a["bikeId"])
        ),
    }
