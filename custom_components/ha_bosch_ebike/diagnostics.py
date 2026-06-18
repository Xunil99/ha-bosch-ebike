"""Diagnostics support for the Bosch eBike integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

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
        "battery_capacity_wh": data.get("battery_capacity_wh"),
        "bike_count": len(bikes),
        "bikes": async_redact_data(bikes, TO_REDACT),
        "activity_count": len(all_activities),
        "latest_activity": async_redact_data(
            data.get("latest_activity") or {}, TO_REDACT
        ),
        "consumption_entries": len(consumption),
        "consumption_sample": dict(list(consumption.items())[:3]),
        "maintenance": maintenance,
        "service_overrides": data.get("service_overrides"),
        "bike_pass": async_redact_data(data.get("bike_pass") or {}, TO_REDACT),
        "service_records": async_redact_data(
            data.get("service_records") or {}, TO_REDACT
        ),
    }
    return diag
