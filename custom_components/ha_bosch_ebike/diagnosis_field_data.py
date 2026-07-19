"""Pure parsers for the Bosch Data Act "Diagnosis Field Data API".

Covers /capacity-testers (Smart System + eBike System 2), /batteries and
/drive-units (eBike System 2 only per the Data Act appendix, no Smart System
variant exists). All three only ever contain data once the eBike System has
been connected to a Bosch DiagnosticTool 3 / Capacity Tester by an
independent bike dealer — in the common case (no dealer visit yet) every
function here returns None, exactly like profile_extra.battery_soh() for the
Digital Service Book.

Every numeric field in the Bosch response is typed as a JSON string (except
capacityTesters[].batteryData, which uses real number/int/bool types) — see
_num() below for the defensive string-to-float parsing this requires.

Kept dependency-free and side-effect-free so it can be unit-tested without a
Home Assistant runtime (mirrors profile_extra.py / range_estimate.py).
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


def _num(v: Any) -> float | None:
    """Best-effort float parse. Bosch ships most of these fields as strings."""
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        try:
            return float(v)
        except ValueError:
            return None
    return None


# ---------------------------------------------------------------------------
# /capacity-testers — Smart System + eBike System 2
# ---------------------------------------------------------------------------

def capacity_test_summary(response: dict | None) -> dict | None:
    """Newest capacityTesters[] entry for this battery, or None.

    response is the raw API payload for ONE battery (queried by
    part+serial), so capacityTesters[] normally holds at most a handful of
    historical measurements; picks the newest by createdAt.
    """
    entries = _get(response, "capacityTesters", default=[]) or []
    matching = [e for e in entries if isinstance(e, dict)]
    if not matching:
        return None
    newest = max(matching, key=lambda e: str(e.get("createdAt") or ""))
    battery_data = _get(newest, "batteryData", default={}) or {}
    return {
        "measured_wh": _num(battery_data.get("measuredCapacity")),
        "nominal_wh": _num(battery_data.get("nominalCapacity")),
        "full_charge_cycles": _num(battery_data.get("fullChargeCycles")),
        "on_bike_measurement": battery_data.get("onBikeMeasurement")
        if isinstance(battery_data.get("onBikeMeasurement"), bool) else None,
        "manufacturing_date": battery_data.get("manufacturingDate"),
        "tested_at": newest.get("createdAt"),
    }


# ---------------------------------------------------------------------------
# /batteries — eBike System 2 only
# ---------------------------------------------------------------------------

def battery_field_data(response: dict | None) -> dict | None:
    """First batteries[] entry for this battery, or None.

    The API has no documented per-entry timestamp for this endpoint (unlike
    capacity-testers' createdAt), so there is no reliable "newest" to pick;
    a part+serial-scoped query is expected to return at most one entry.
    """
    entries = _get(response, "batteries", default=[]) or []
    matching = [e for e in entries if isinstance(e, dict)]
    if not matching:
        return None
    b = matching[0]
    return {
        "present_abacus_soh": _num(b.get("presentAbacusSoh")),
        "remaining_capacity_wh": _num(b.get("remainingCapacity")),
        "remaining_energy_wh": _num(b.get("remainingEnergy")),
        "pack_temperature_c": _num(b.get("packTemperature")),
        "min_pack_temperature_c": _num(b.get("minPackTemperature")),
        "max_pack_temperature_c": _num(b.get("maxPackTemperature")),
        "fet_temperature_c": _num(b.get("fetTemperature")),
        "min_fet_temperature_c": _num(b.get("minFetTemperature")),
        "max_fet_temperature_c": _num(b.get("maxFetTemperature")),
        "charge_cycle_count_on_bike": _num(b.get("chargeCycleCountOnBike")),
        "charge_cycle_count_off_bike": _num(b.get("chargeCycleCountOffBike")),
        "charge_duration_total_min": _num(b.get("chargeDurationTotal")),
        "manufacturing_date": b.get("manufacturingDate"),
        "hw_version": b.get("hwVersion"),
        "sw_version": b.get("swVersion"),
    }


# ---------------------------------------------------------------------------
# /drive-units — eBike System 2 only
# ---------------------------------------------------------------------------

def drive_unit_field_data(response: dict | None) -> dict | None:
    """First driveUnits[] entry for this drive unit, or None.

    Like /batteries, no documented per-entry timestamp; a part+serial-scoped
    query is expected to return at most one entry.

    thermalDeratingTime/totalBikeRidingTime/totalMotorOnTime/totalPowerOnTime
    have no unit stated anywhere in the Data Act appendix (unlike e.g.
    chargeDurationTotal, which is explicitly documented as minutes) — kept as
    raw, unconverted numbers rather than guessing a unit.
    """
    entries = _get(response, "driveUnits", default=[]) or []
    matching = [e for e in entries if isinstance(e, dict)]
    if not matching:
        return None
    d = matching[0]
    return {
        "max_motor_temperature_c": _num(d.get("maxMotorTemperature")),
        "min_motor_temperature_c": _num(d.get("minMotorTemperature")),
        "max_pcb_temperature_c": _num(d.get("maxPcbTemperature")),
        "min_pcb_temperature_c": _num(d.get("minPcbTemperature")),
        "thermal_derating_time_raw": _num(d.get("thermalDeratingTime")),
        "hw_version": d.get("hwVersion"),
        "sw_version": d.get("swVersion"),
    }
