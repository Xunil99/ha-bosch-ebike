"""Pure two-phase charge-rate estimation.

Charging a Li-ion pack is not linear: it moves fast below roughly 80%, then
tapers off noticeably in the constant-voltage phase above it. This module
learns two separate rates from a bike's own charge history - one for the
0-80% span, one for 80-100% - and projects a remaining-time estimate for
each of the two milestones users actually care about.

Deliberately free of Home Assistant imports, mirroring range_estimate.py,
so the dependency-free suite under tests/ can cover it directly.
"""
from __future__ import annotations

from typing import Any

# The natural break between "fast" and "tapered" charging most Li-ion packs
# show. Also the milestone most riders who charge for battery health target.
PHASE_BOUNDARY_PCT = 80.0

# A phase's rate is only trusted once at least this many historical sessions
# have contributed real minutes to it - mirrors MIN_TOURS in
# range_estimate.py. Below this, the caller should show "not enough data
# yet" rather than a number built on one or two samples.
MIN_SESSIONS_PER_PHASE = 3


def compute_two_phase_rates(sessions: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate minutes-per-percent rates below and above PHASE_BOUNDARY_PCT.

    *sessions* is the bike's charge history, newest or oldest first (order
    does not matter here), each a dict with at least start_soc, end_soc and
    duration_min (the same shape charge_session.py's SUMMARY_KEYS already
    produces). A session spanning the boundary contributes to BOTH phases,
    prorated by its own percentage-point share of its own recorded duration
    (assumes a roughly constant rate within one session's own segment - a
    much safer assumption than across the whole 0-100% range, which is
    exactly what the two-phase split exists to avoid).

    Sessions are aggregated as (sum of minutes) / (sum of percentage
    points) across all contributing sessions, not as a mean of individual
    per-session rates - the same style as wh_per_km in range_estimate.py.

    Returns a dict with rate_below_80/rate_above_80 (minutes per percentage
    point, or None if no session ever contributed to that phase) and
    below_80_sessions/above_80_sessions (contributing-session counts, for
    the MIN_SESSIONS_PER_PHASE gate in estimate_time_to_target).
    """
    below_minutes = 0.0
    below_pct = 0.0
    below_sessions = 0
    above_minutes = 0.0
    above_pct = 0.0
    above_sessions = 0

    for session in sessions:
        try:
            start = float(session.get("start_soc"))
            end = float(session.get("end_soc"))
            duration = float(session.get("duration_min"))
        except (TypeError, ValueError):
            continue
        delta = end - start
        if delta <= 0 or duration <= 0:
            continue

        below_span = max(0.0, min(end, PHASE_BOUNDARY_PCT) - start)
        above_span = max(0.0, end - max(start, PHASE_BOUNDARY_PCT))

        if below_span > 0:
            below_minutes += duration * (below_span / delta)
            below_pct += below_span
            below_sessions += 1
        if above_span > 0:
            above_minutes += duration * (above_span / delta)
            above_pct += above_span
            above_sessions += 1

    return {
        "rate_below_80": (below_minutes / below_pct) if below_pct > 0 else None,
        "rate_above_80": (above_minutes / above_pct) if above_pct > 0 else None,
        "below_80_sessions": below_sessions,
        "above_80_sessions": above_sessions,
    }


def estimate_time_to_target(
    current_soc: float, target_soc: float, rates: dict[str, Any]
) -> float | None:
    """Minutes from current_soc to target_soc (80.0 or 100.0), or None.

    None when: the target is already strictly behind current_soc (nothing
    left to estimate - e.g. asking for time-to-80 at 85%), or a required
    phase's rate does not meet MIN_SESSIONS_PER_PHASE yet (not enough
    history to trust it). Reaching from below 80 to 100 needs BOTH phases'
    minimums met, since the projection sums both rates. current_soc at or
    past target_soc returns 0.0 exactly when they are equal (including
    100-at-100); strictly past returns None.
    """
    if current_soc > target_soc:
        return None
    if current_soc == target_soc:
        return 0.0

    below_ok = rates.get("below_80_sessions", 0) >= MIN_SESSIONS_PER_PHASE
    above_ok = rates.get("above_80_sessions", 0) >= MIN_SESSIONS_PER_PHASE
    rate_below = rates.get("rate_below_80")
    rate_above = rates.get("rate_above_80")

    if target_soc <= PHASE_BOUNDARY_PCT:
        if not below_ok or rate_below is None:
            return None
        return (target_soc - current_soc) * rate_below

    # target is 100: may need one or both phases depending on current_soc.
    if current_soc >= PHASE_BOUNDARY_PCT:
        if not above_ok or rate_above is None:
            return None
        return (target_soc - current_soc) * rate_above

    if not below_ok or not above_ok or rate_below is None or rate_above is None:
        return None
    return (
        (PHASE_BOUNDARY_PCT - current_soc) * rate_below
        + (target_soc - PHASE_BOUNDARY_PCT) * rate_above
    )
