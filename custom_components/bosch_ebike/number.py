"""Number platform for Bosch eBike — configurable battery capacity."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, DEFAULT_BATTERY_CAPACITY_WH
from .coordinator import BoschEBikeCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Bosch eBike number entities."""
    coordinator: BoschEBikeCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([BatteryCapacityNumber(coordinator, entry)])


class BatteryCapacityNumber(NumberEntity):
    """Number entity for battery capacity in Wh."""

    _attr_has_entity_name = True
    _attr_name = "Battery Capacity"
    _attr_icon = "mdi:battery-charging"
    _attr_native_unit_of_measurement = "Wh"
    _attr_native_min_value = 100
    _attr_native_max_value = 1500
    _attr_native_step = 25
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
