"""Date platform for Bosch eBike — user-editable next-service date per bike."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from homeassistant.components.date import DateEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import BoschEBikeCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create one ServiceDueDate entity per bike."""
    coordinator: BoschEBikeCoordinator = hass.data[DOMAIN][entry.entry_id]
    bikes = coordinator.data.get("bikes", []) if coordinator.data else []
    entities: list[Any] = []
    for bike in bikes:
        bike_id = bike.get("id")
        if not bike_id:
            continue
        drive = bike.get("driveUnit") or {}
        drive_name = drive.get("productName") or "eBike"
        entities.append(BoschServiceDueDateEntity(coordinator, bike_id, drive_name))
    async_add_entities(entities)


class BoschServiceDueDateEntity(CoordinatorEntity[BoschEBikeCoordinator], DateEntity):
    """User-editable next-service date for a single bike."""

    _attr_has_entity_name = True
    _attr_name = "Service Due Date"
    _attr_translation_key = "service_due_date"
    _attr_icon = "mdi:calendar-wrench"

    def __init__(
        self,
        coordinator: BoschEBikeCoordinator,
        bike_id: str,
        drive_name: str,
    ) -> None:
        super().__init__(coordinator)
        self._bike_id = bike_id
        self._attr_unique_id = f"{bike_id}_service_due_date"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, bike_id)},
            name=drive_name,
            manufacturer="Bosch",
            model=drive_name,
        )

    def _bosch_service_date(self) -> str | None:
        """This bike's own serviceDue.date from the Bosch API, if any."""
        bikes = self.coordinator.data.get("bikes", []) if self.coordinator.data else []
        for bike in bikes:
            if bike.get("id") == self._bike_id:
                return (bike.get("serviceDue") or {}).get("date")
        return None

    @property
    def native_value(self) -> date | None:
        # User override first, Bosch's own value as the fallback - the same
        # order every other consumer of this override already uses (see
        # sensor.py's service_due_in_days). Doing it here at read time,
        # rather than by pre-filling the override, is what lets the override
        # be cleared again and lets a later Bosch-side change come through
        # (issue #66).
        raw = self.coordinator.get_service_due_date(self._bike_id) or self._bosch_service_date()
        if not raw:
            return None
        raw = str(raw)
        try:
            # raw is "YYYY-MM-DD" or full ISO string; date.fromisoformat handles both 10-char and full-date forms
            if "T" in raw:
                return datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
            return date.fromisoformat(raw[:10])
        except (TypeError, ValueError):
            return None

    async def async_set_value(self, value: date) -> None:
        self.coordinator.set_service_due_date(self._bike_id, value.isoformat())
        self.async_write_ha_state()
