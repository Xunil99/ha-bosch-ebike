"""Number platform for Bosch eBike — battery capacity & service-due odometer."""

from __future__ import annotations

from typing import Any

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, DEFAULT_BATTERY_CAPACITY_WH
from .coordinator import BoschEBikeCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Bosch eBike number entities."""
    coordinator: BoschEBikeCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[Any] = [BatteryCapacityNumber(coordinator, entry)]

    # Per-bike service-due-km (user-editable)
    bikes = coordinator.data.get("bikes", []) if coordinator.data else []
    for bike in bikes:
        bike_id = bike.get("id")
        if not bike_id:
            continue
        drive = bike.get("driveUnit") or {}
        drive_name = drive.get("productName") or "eBike"
        entities.append(BoschServiceDueKmEntity(coordinator, bike_id, drive_name))

    async_add_entities(entities)


class BatteryCapacityNumber(NumberEntity):
    """Number entity for battery capacity in Wh."""

    _attr_has_entity_name = True
    _attr_name = "Battery Capacity"
    _attr_translation_key = "battery_capacity"
    _attr_icon = "mdi:battery-charging"
    _attr_native_unit_of_measurement = "Wh"
    _attr_native_min_value = 100
    _attr_native_max_value = 1500
    _attr_native_step = 1
    _attr_mode = NumberMode.BOX
    _attr_native_value = DEFAULT_BATTERY_CAPACITY_WH

    def __init__(
        self,
        coordinator: BoschEBikeCoordinator,
        entry: ConfigEntry,
    ) -> None:
        self.coordinator = coordinator
        self._attr_unique_id = f"{entry.entry_id}_battery_capacity"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "Bosch eBike",
            "manufacturer": "Bosch",
        }
        # Restore from config entry if previously saved
        stored = entry.data.get("battery_capacity_wh")
        if stored is not None:
            self._attr_native_value = stored
            coordinator.set_battery_capacity(stored)

    async def async_set_native_value(self, value: float) -> None:
        """Update the battery capacity."""
        self._attr_native_value = value
        self.coordinator.set_battery_capacity(value)
        # Persist to config entry
        self.hass.config_entries.async_update_entry(
            self.coordinator.config_entry,
            data={
                **self.coordinator.config_entry.data,
                "battery_capacity_wh": value,
            },
        )


class BoschServiceDueKmEntity(CoordinatorEntity[BoschEBikeCoordinator], NumberEntity):
    """User-editable next-service odometer (in km) for a single bike."""

    _attr_has_entity_name = True
    _attr_name = "Service Due Odometer"
    _attr_translation_key = "service_due_odometer"
    _attr_icon = "mdi:road-variant"
    _attr_native_unit_of_measurement = "km"
    _attr_native_min_value = 0
    _attr_native_max_value = 200000
    _attr_native_step = 1
    _attr_mode = NumberMode.BOX

    def __init__(
        self,
        coordinator: BoschEBikeCoordinator,
        bike_id: str,
        drive_name: str,
    ) -> None:
        super().__init__(coordinator)
        self._bike_id = bike_id
        self._attr_unique_id = f"{bike_id}_service_due_km"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, bike_id)},
            name=drive_name,
            manufacturer="Bosch",
            model=drive_name,
        )

    @property
    def native_value(self) -> float | None:
        return self.coordinator.get_service_due_km(self._bike_id)

    async def async_set_native_value(self, value: float) -> None:
        # Treat 0 (or below) as "clear override"
        new_value: float | None = float(value) if value > 0 else None
        self.coordinator.set_service_due_km(self._bike_id, new_value)
        self.async_write_ha_state()
