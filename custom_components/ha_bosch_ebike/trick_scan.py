"""Heuristic scanner for as-yet-undocumented Bosch "Trick Check" data.

Bosch introduced automatic trick detection (jumps, wheelies, manuals,
stoppies - height/distance/duration/angle, longest airtime for jumps) in
Flow app v1.34, shown on the display in real time and later in the Flow
app's own statistics / the paid Flow+ subscription's annual overview. As of
2026-07 this is NOT documented anywhere in the official EU Data Act API
appendix that this integration's endpoints are built against (re-checked
against a fresh download: byte-identical to the last check, still no
"trick"/"jump"/"wheelie"/"stoppie"/"airtime" mentions).

This module is a diagnostic canary, not a real parser: since the actual
field names/shape are unknown, it recursively scans already-fetched
activity JSON for any dict key whose name merely hints at trick data, and
reports what it finds. The point is to capture real field names/values in
the logs the moment Bosch (if ever) starts including this in an activity
response, without having to guess the schema upfront - a proper sensor can
be built once real data has actually been observed this way.
"""
from __future__ import annotations

from typing import Any

# Deliberately excludes bare "manual": it already collides with an
# unrelated, always-present field (the drive unit's automatic-vs-manual
# gear shift configuration), which would make this fire on every single
# activity for any bike not using automatic shifting and defeat the point
# of a canary that should stay quiet until something genuinely new shows up.
TRICK_KEY_HINTS: tuple[str, ...] = (
    "trick",
    "wheelie",
    "stoppie",
    "airtime",
    "air_time",
    "jump",
)

# A jump/wheelie/stoppie plausibly carries its own location and timestamp
# (Bosch would need that to place it on the ride map), so a matched hit's
# VALUE could itself nest genuinely sensitive fields even though the key
# that matched is harmless. This mirrors diagnostics.py's TO_REDACT set
# (kept as an independent copy rather than importing it: diagnostics.py
# already imports from coordinator.py, so importing the other way would be
# circular, and this module is deliberately dependency-free/pure so it can
# be unit-tested without Home Assistant installed, like profile_extra.py).
_SENSITIVE_KEYS = {
    "serialNumber", "serial_number", "partNumber",
    "latitude", "longitude", "lat", "lon", "lng",
    "frameNumber", "frameNumberPosition", "address", "description",
}


def _redact(value: Any) -> Any:
    """Recursively mask known-sensitive keys within a matched hit's value.

    This runs on the VALUE of an already-matched trick-hint key, not on the
    whole activity - it exists purely so that IF Bosch's real trick data
    turns out to nest e.g. a jump's takeoff location under the matched key,
    that nested coordinate never reaches the log line this feeds, while the
    actually-useful trick fields (height, distance, duration, angle, ...)
    stay visible.
    """
    if isinstance(value, dict):
        return {
            k: ("**REDACTED**" if isinstance(k, str) and k in _SENSITIVE_KEYS else _redact(v))
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value


def scan_for_trick_fields(obj: Any, _path: str = "") -> list[dict[str, Any]]:
    """Recursively scan *obj* for dict keys whose name hints at trick data.

    Returns a list of {"path", "key", "value"} dicts, one per matching key,
    in encounter order. Each returned "value" has already been passed
    through _redact() - see its docstring for why. *obj* is expected to be
    already-decoded JSON (dicts/lists/scalars), so no cycle protection is
    needed.
    """
    hits: list[dict[str, Any]] = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            path = f"{_path}.{key}" if _path else str(key)
            if isinstance(key, str) and any(
                hint in key.lower() for hint in TRICK_KEY_HINTS
            ):
                hits.append({"path": path, "key": key, "value": _redact(value)})
            hits.extend(scan_for_trick_fields(value, path))
    elif isinstance(obj, list):
        for idx, item in enumerate(obj):
            hits.extend(scan_for_trick_fields(item, f"{_path}[{idx}]"))
    return hits


def format_hits_for_log(hits: list[dict[str, Any]], max_hits: int = 20, max_value_len: int = 200) -> str:
    """Human-readable, length-capped summary of scan_for_trick_fields() hits.

    Caps both the number of hits shown and each individual value's repr
    length, so a field that happens to contain a large nested structure (or
    an unexpectedly large number of matches) cannot flood the log.
    """
    shown = hits[:max_hits]
    lines = []
    for hit in shown:
        value_repr = repr(hit["value"])
        if len(value_repr) > max_value_len:
            value_repr = value_repr[:max_value_len] + "…"
        lines.append(f"{hit['path']} = {value_repr}")
    text = "; ".join(lines)
    if len(hits) > max_hits:
        text += f" (+{len(hits) - max_hits} more)"
    return text
