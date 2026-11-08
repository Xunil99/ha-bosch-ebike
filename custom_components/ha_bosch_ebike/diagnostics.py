"""Diagnostics support for the Bosch eBike integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .activity_attribution import summarize_attribution
from .const import DOMAIN
from .coordinator import BoschEBikeCoordinator

# Keys that are redacted recursively before the dump leaves the instance.
# Secrets (tokens, client id) plus location/identity data (GPS, serials).
TO_REDACT = {
    "access_token",
    "refresh_token",
    "client_id",
    "serialNumber",
    "serial_number",
    "partNumber",
    "bes2_drive_unit_serial",
    "bes2_drive_unit_part",
    "latitude",
    "longitude",
    "lat",
    "lon",
    "lng",
    "frameNumber",
    "frameNumberPosition",
    "address",
    "description",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry (tokens/PII redacted)."""
    coordinator: BoschEBikeCoordinator | None = hass.data.get(DOMAIN, {}).get(
        entry.entry_id
    )

    diag: dict[str, Any] = {
        "entry": {
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": async_redact_data(dict(entry.options), TO_REDACT),
        }
    }

    if coordinator is None or coordinator.data is None:
        diag["coordinator"] = None
        return diag

    data = coordinator.data
    bikes = data.get("bikes") or []
    all_activities = data.get("all_activities") or []
    consumption = data.get("activity_consumption") or {}
    maintenance = data.get("maintenance") or {}

    # Summarise instead of dumping everything: the full activity list and the
    # GPS track points would be huge and contain location data.
    diag["coordinator"] = {
        "last_update_success": coordinator.last_update_success,
        # Set while Bosch's activity list is failing (issue #95): the other
        # cloud data keeps updating then, so last_update_success alone would
        # look healthy.
        "activities_error": coordinator.activities_error,
        # Which Digital Service Book API version answered ("v2" or "v1") and how
        # many records each bike has: the only way to see on an instance whether
        # the v2 first, v1 fallback logic did what it should.
        "service_book_version": coordinator.api.service_book_version,
        "service_record_counts": {
            bike_id: len((records or {}).get("serviceRecords") or [])
            for bike_id, records in (data.get("service_records") or {}).items()
        },
        "activities_error_since": (
            coordinator.activities_error_since.isoformat()
            if coordinator.activities_error_since
            else None
        ),
        "battery_capacity_wh": data.get("battery_capacity_wh"),
        "bike_count": len(bikes),
        "bikes": async_redact_data(bikes, TO_REDACT),
        "activity_count": len(all_activities),
        "latest_activity": async_redact_data(
            data.get("latest_activity") or {}, TO_REDACT
        ),
        # How far the bikeId Bosch delivers with each ride could be used to
        # pick the bike: with_bike_id / bike_id_known should both equal
        # activities on a normal account. Counts only, no ids.
        "bike_attribution": summarize_attribution(
            bikes,
            all_activities,
            data.get("activity_bike") or {},
            coordinator.manual_activity_bike,
        ),
        "consumption_entries": len(consumption),
        "consumption_sample": dict(list(consumption.items())[:3]),
        "maintenance": maintenance,
        "service_overrides": data.get("service_overrides"),
        "bike_pass": async_redact_data(data.get("bike_pass") or {}, TO_REDACT),
        "service_records": async_redact_data(
            data.get("service_records") or {}, TO_REDACT
        ),
        # Diagnosis Field Data API (capacity-testers/batteries/drive-units).
        # Counts only, not a redacted dump: these dicts are keyed BY the
        # battery/drive-unit serial number itself (not a "serialNumber"
        # field under a value), which TO_REDACT cannot mask since it only
        # redacts values of matching keys, not dict keys.
        "diagnosis_field_data": {
            "capacity_testers_entries": len(data.get("capacity_testers") or {}),
            "battery_field_data_entries": len(data.get("battery_field_data") or {}),
            "drive_unit_field_data_entries": len(
                data.get("drive_unit_field_data") or {}
            ),
        },
    }
    return diag
