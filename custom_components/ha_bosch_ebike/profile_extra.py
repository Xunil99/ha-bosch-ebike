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


# Bosch returns the assist mode in ``activeAssistModes[].name`` as an internal
# application code (e.g. "A100M00030"), not the name shown on the display.
# Mapping verified against a Bosch DiagnosticTool 3 dealer report
# ("Modes d'assistance", code -> "Désignation complète").
ASSIST_MODE_NAMES: dict[str, str] = {
    "A100M00040": "ECO",
    "A100ECOP37": "ECO+",
    "A100M00030": "TOUR",
    "A100MAAAA0": "TOUR+",
    "A100M00020": "SPORT",
    "A100M00010": "TURBO",
    "A100M0AUTO": "AUTO",
    "A100EAAAB0": "eMTB",
    "A100MSPIC7": "eMTB+",
    "A100MAAAB0": "eMTB-shortcrank",
}


def assist_mode_display_name(code: Any) -> Any:
    """Map a Bosch assist-mode application code to its display name.

    Unknown codes are returned unchanged so a yet-undocumented mode still
    shows something instead of disappearing.
    """
    if isinstance(code, str):
        return ASSIST_MODE_NAMES.get(code, code)
    return code


def reachable_ranges(bike: dict) -> list[dict]:
    """Bosch per-assist-mode reachable range (in API order), km.

    The API delivers ``reachableRange`` already in KILOMETRES (verified
    against real bike data, issue #35) — the OpenAPI example suggesting
    metres is misleading. The value is therefore used as-is, NOT /1000.

    ``activeAssistModes[].name`` is an internal application code; it is
    mapped to the display name (ECO/TOUR/TURBO/eMTB+ ...) via
    :data:`ASSIST_MODE_NAMES`.
    """
    modes = _get(bike, "driveUnit", "activeAssistModes", default=[]) or []
    out: list[dict] = []
    for m in modes:
        name = m.get("name")
        rng = m.get("reachableRange")
        if not name or name == "0" or not isinstance(rng, (int, float)):
            continue
        out.append({"name": assist_mode_display_name(name),
                    "range_km": round(rng, 1)})
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


# ---------------------------------------------------------------------------
# Bike Pass — GET /bike-pass/smart-system/v1/bike-passes
# ---------------------------------------------------------------------------

def theft_status(bike_pass: dict | None) -> dict | None:
    """Theft state from the most recent theftReportLogs entry.

    Returns None when bike_pass is falsy or has no theftReportLogs key
    (unknown / not fetched). Empty list -> not reported. Otherwise reports
    the newest entry (by createdAt) with its location (location optional).
    """
    if not bike_pass or "theftReportLogs" not in bike_pass:
        return None
    logs = [e for e in (bike_pass.get("theftReportLogs") or [])
            if isinstance(e, dict)]
    if not logs:
        return {"reported": False, "since": None, "latitude": None,
                "longitude": None, "address": None, "detected_at": None}
    newest = max(logs, key=lambda e: str(_get(e, "createdAt", default="")))
    loc = newest.get("location")
    loc = loc if isinstance(loc, dict) else {}
    since = newest.get("theftCaseEnteredAt") or newest.get("createdAt")
    return {
        "reported": True,
        "since": str(since) if since is not None else None,
        "latitude": _get(loc, "latitude"),
        "longitude": _get(loc, "longitude"),
        "address": _get(loc, "address"),
        "detected_at": _get(loc, "detectedAt"),
    }


def frame_number(bike_pass: dict | None) -> str | None:
    """First bikePasses[0].frameNumber, else None."""
    passes = _get(bike_pass, "bikePasses", default=[]) or []
    if not passes:
        return None
    return _get(passes[0], "frameNumber")


# ---------------------------------------------------------------------------
# Digital Service Book — GET /service-book/smart-system/v1/service-records
# ---------------------------------------------------------------------------

def _newest_record(service_records: dict | None, record_type: str) -> dict | None:
    """Newest serviceRecords entry of the given type by attributes.createdAt."""
    recs = _get(service_records, "serviceRecords", default=[]) or []
    matching = [r for r in recs if isinstance(r, dict)
                and r.get("type") == record_type]
    if not matching:
        return None
    return max(matching,
               key=lambda r: str(_get(r, "attributes", "createdAt", default="")))


def battery_soh(service_records: dict | None, serial: str) -> dict | None:
    """Newest BATTERY_MEASUREMENT for the given battery serialNumber."""
    recs = _get(service_records, "serviceRecords", default=[]) or []
    matching = [
        r for r in recs
        if isinstance(r, dict) and r.get("type") == "BATTERY_MEASUREMENT"
        and _get(r, "attributes", "details", "batteryMeasurement",
                 "battery", "serialNumber") == serial
    ]
    if not matching:
        return None
    rec = max(matching,
              key=lambda r: str(_get(r, "attributes", "createdAt", default="")))
    meas = _get(rec, "attributes", "details", "batteryMeasurement",
                "measurement", default={}) or {}
    return {
        "soh_pct": meas.get("measuredCapacityPercentage"),
        "measured_wh": meas.get("measuredEnergyCapacity"),
        "nominal_wh": meas.get("nominalEnergyCapacity"),
        "full_charge_cycles": meas.get("fullChargeCycles"),
        "measured_at": _get(rec, "attributes", "createdAt"),
    }


def _newest_customer_components(service_records: dict | None) -> list | None:
    """Components of the newest CUSTOMER_REPORT, or None if no report."""
    rec = _newest_record(service_records, "CUSTOMER_REPORT")
    if rec is None:
        return None
    return _get(rec, "attributes", "details", "customerReport",
                "bike", "components", default=[]) or []


def software_update_available(service_records: dict | None) -> bool | None:
    """True if any component in the newest CUSTOMER_REPORT has an update.

    False if a report exists but no component flags one; None if no report.
    """
    components = _newest_customer_components(service_records)
    if components is None:
        return None
    return any(c.get("softwareUpdateAvailable") is True
               for c in components if isinstance(c, dict))


def special_states(service_records: dict | None) -> list[str]:
    """Distinct highestSpecialState values (!= "NONE") from newest report."""
    components = _newest_customer_components(service_records)
    if not components:
        return []
    out: list[str] = []
    for c in components:
        if not isinstance(c, dict):
            continue
        state = c.get("highestSpecialState")
        if state and state != "NONE" and state not in out:
            out.append(state)
    return out


def next_service_info(service_records: dict | None) -> dict | None:
    """nextServiceInformation from the newest CUSTOMER_REPORT, or None."""
    rec = _newest_record(service_records, "CUSTOMER_REPORT")
    if rec is None:
        return None
    info = _get(rec, "attributes", "details", "customerReport",
                "nextServiceInformation")
    if not info:
        return None
    return {
        "days": info.get("daysNextService"),
        "meters": info.get("metersNextService"),
        "updated_at": info.get("updatedAt"),
    }


# ---------------------------------------------------------------------------
# Tier-3 — assist-mode stats, last service, component inventory, max altitude
# ---------------------------------------------------------------------------

def assist_mode_stats(service_records: dict | None) -> list[dict]:
    """Per-assist-mode distance/energy from the newest CUSTOMER_REPORT chart.

    Reads statistics.chartData[]; returns name/distance_km/energy_wh in order,
    skipping entries without a displayName. [] if no report / no chartData.
    """
    rec = _newest_record(service_records, "CUSTOMER_REPORT")
    if rec is None:
        return []
    chart = _get(rec, "attributes", "details", "customerReport",
                 "statistics", "chartData", default=[]) or []
    out: list[dict] = []
    for entry in chart:
        if not isinstance(entry, dict):
            continue
        name = entry.get("displayName")
        if not name:
            continue
        distance = entry.get("distanceValue")
        distance_km = round(distance / 1000, 1) if isinstance(
            distance, (int, float)) and not isinstance(distance, bool) else None
        out.append({
            "name": name,
            "distance_km": distance_km,
            "energy_wh": entry.get("energyValue"),
        })
    return out


def last_service(service_records: dict | None) -> dict | None:
    """Newest serviceRecords entry (any type) by attributes.createdAt.

    Returns date/dealer/odometer_km, or None if there are no records.
    """
    recs = _get(service_records, "serviceRecords", default=[]) or []
    matching = [r for r in recs if isinstance(r, dict)]
    if not matching:
        return None
    rec = max(matching,
              key=lambda r: str(_get(r, "attributes", "createdAt", default="")))
    odo = _get(rec, "attributes", "odometerValue")
    return {
        "date": _get(rec, "attributes", "createdAt"),
        "dealer": _get(rec, "attributes", "bikeDealer", "name"),
        "odometer_km": round(odo / 1000, 1) if isinstance(odo, (int, float))
        else None,
    }


def component_inventory(bike: dict) -> dict:
    """Component product names + ABS presence from a bike-profile object."""
    abs_systems = bike.get("antiLockBrakeSystems") if isinstance(bike, dict) \
        else None
    return {
        "head_unit": _get(bike, "headUnit", "productName"),
        "remote_control": _get(bike, "remoteControl", "productName"),
        "connect_module": _get(bike, "connectModule", "productName"),
        "has_abs": bool(isinstance(abs_systems, list) and abs_systems),
    }


def max_altitude(details: dict | None) -> float | None:
    """Max numeric altitude (m, 1 decimal) across activity points, or None."""
    if isinstance(details, dict):
        points = details.get("activityDetails") or []
    elif isinstance(details, list):
        points = details
    else:
        return None
    alts = [p.get("altitude") for p in points if isinstance(p, dict)]
    numeric = [a for a in alts if isinstance(a, (int, float))
               and not isinstance(a, bool)]
    if not numeric:
        return None
    return round(max(numeric), 1)
