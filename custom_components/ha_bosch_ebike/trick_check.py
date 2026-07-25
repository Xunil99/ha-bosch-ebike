"""Parser for Bosch's "Trick Check" activity data (jumps/manuals/stoppies/wheelies).

Introduced in Flow app v1.34 (automatic detection of jumps, wheelies,
manuals and stoppies). As of 2026-07 this was not yet documented in the
official EU Data Act API appendix, so it was first tracked only via
trick_scan.py's generic key-name canary. Confirmed live via a real
Smart System activity summary response (issue #65 follow-up, 2026-07-26):
the API returns a `tricks` object as a direct sibling of `distance`,
`speed`, `elevation` etc. on every activity summary - always present, with
all-zero sub-objects when nothing happened, not just on rides with a trick.

Units cross-verified against the Bosch Flow app's own display for the same
ride ("Jump", 1x, max. 2,4 m / 0.25 s / 0,7 m) against the matching raw
values (maxDistance: 2.38, maxDuration: 250, maxHeight: 710): distance in
metres, duration in milliseconds, height in millimetres. maxAngle
(manuals/stoppies/wheelies only) has not yet been observed non-zero in the
wild, so its unit (assumed degrees) is inferred, not confirmed.
"""
from __future__ import annotations

import math
from typing import Any

# Trick types that report a height instead of an angle.
_HEIGHT_TYPES = {"jumps"}


def _finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(value)


def _num(value: Any, scale: float = 1.0, digits: int = 2) -> float | None:
    if not _finite_number(value):
        return None
    return round(value * scale, digits)


def _parse_trick_type(raw: Any, trick_type: str) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    amount = raw.get("amount")
    if not _finite_number(amount):
        return None
    out: dict[str, Any] = {
        "amount": int(amount),
        "max_distance_m": _num(raw.get("maxDistance"), digits=1),
        "max_duration_s": _num(raw.get("maxDuration"), scale=0.001),
    }
    if trick_type in _HEIGHT_TYPES:
        out["max_height_m"] = _num(raw.get("maxHeight"), scale=0.001, digits=2)
    else:
        out["max_angle_deg"] = _num(raw.get("maxAngle"), digits=1)
    return out


def parse_trick_check(activity: Any) -> dict[str, Any] | None:
    """Extract and normalize the ``tricks`` block from an activity summary.

    Returns ``None`` if the field is absent or malformed (older cached
    data, accounts/systems Bosch hasn't rolled this out to yet, API
    regressions), so callers can safely skip trick display without extra
    guarding. When present, always returns all four trick types (with
    ``amount: 0`` for ones that didn't happen), plus a convenience
    ``has_any`` flag.
    """
    if not isinstance(activity, dict):
        return None
    tricks = activity.get("tricks")
    if not isinstance(tricks, dict):
        return None
    parsed = {
        trick_type: _parse_trick_type(tricks.get(trick_type), trick_type)
        for trick_type in ("jumps", "manuals", "stoppies", "wheelies")
    }
    if all(v is None for v in parsed.values()):
        return None
    result = {k: v for k, v in parsed.items() if v is not None}
    result["has_any"] = any(v.get("amount", 0) > 0 for v in result.values())
    return result
