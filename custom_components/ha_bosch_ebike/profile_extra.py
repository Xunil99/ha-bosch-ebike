"""Pure parsers for additional Bosch Data Act / Smart System fields.

Kept dependency-free and side-effect-free so they can be unit-tested
without a Home Assistant runtime (mirrors range_estimate.py).
"""
from __future__ import annotations

from datetime import datetime
from typing import Any


def _get(d: Any, *keys: str, default: Any = None) -> Any:
    cur = d
    for k in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(k)
    return cur if cur is not None else default


def reachable_ranges(bike: dict) -> list[dict]:
    """Bosch per-assist-mode reachable range (in API order), km."""
    modes = _get(bike, "driveUnit", "activeAssistModes", default=[]) or []
    out: list[dict] = []
    for m in modes:
        name = m.get("name")
        rng = m.get("reachableRange")
        if not name or name == "0" or not isinstance(rng, (int, float)):
            continue
        out.append({"name": name, "range_km": round(rng / 1000, 1)})
    return out


def next_service_date(bike: dict) -> datetime | None:
    """Parse serviceDue.date (handles trailing Z); None if missing/unparseable."""
    raw = _get(bike, "serviceDue", "date")
    if not raw:
        return None
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
