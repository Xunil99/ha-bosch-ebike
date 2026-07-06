"""Number platform for Bosch eBike — battery capacity & service-due odometer."""

from __future__ import annotations

from typing import Any

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
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
    """Set up Bosch eBike number entities."""
    coordinator: BoschEBikeCoordinator = hass.data[DOMAIN][entry.entry_id]
    bikes = coordinator.data.get("bikes", []) if coordinator.data else []
    valid_bikes = [b for b in bikes if b.get("id")]

    # One-time registry migration (issue #44 follow-up): Battery Capacity
    # used to be a single account-wide entity with unique_id
    # f"{entry.entry_id}_battery_capacity". Renaming that registry entry to
    # the first bike's new per-bike unique_id preserves its entity_id and
    # history instead of orphaning it. This must NOT depend on how many
    # bikes currently exist - deliberately unlike an earlier version of this
    # fix, which branched entity creation on len(valid_bikes) and therefore
    # silently reassigned unique_ids (breaking history again) the moment a
    # bike was added to or removed from the account. Every bike's unique_id
    # is now a pure function of its own bike_id, so it stays stable across
    # any future bike-count change. This block is a no-op after the first
    # run, once the legacy unique_id no longer exists in the registry.
    if valid_bikes:
        registry = er.async_get(hass)
        legacy_unique_id = f"{entry.entry_id}_battery_capacity"
        legacy_entity_id = registry.async_get_entity_id(
            "number", DOMAIN, legacy_unique_id
        )
        if legacy_entity_id is not None:
            registry.async_update_entity(
                legacy_entity_id,
                new_unique_id=f"{valid_bikes[0]['id']}_battery_capacity",
            )

    entities: list[Any] = []

    # Battery Capacity, one per bike: a single global value could not be
    # right for two bikes with different battery sizes, and it used to live
    # on its own account-level "ghost device" instead of a bike device (see
    # the registry migration above for how an existing single-bike entity's
    # history is preserved across this change).
    for bike in valid_bikes:
        drive_name = (bike.get("driveUnit") or {}).get("productName") or "eBike"
        entities.append(BatteryCapacityNumber(coordinator, bike["id"], drive_name))

    # Per-bike service-due-km (user-editable)
    for bike in valid_bikes:
        drive_name = (bike.get("driveUnit") or {}).get("productName") or "eBike"
        entities.append(BoschServiceDueKmEntity(coordinator, bike["id"], drive_name))

    async_add_entities(entities)


class BatteryCapacityNumber(NumberEntity):
    """Number entity for a single bike's battery capacity in Wh.

    One entity per bike (issue #44 follow-up): the capacity feeds the range
    estimate and live-SoC consumption calculations for that bike, and two
    bikes on the same account can have different battery sizes, so a single
    account-wide value (the pre-fix behaviour) was wrong for at least one of
    them. It also used to be attached to its own account-level device
    instead of a bike device, which is the "ghost device" reported alongside
    this issue.
    """

    _attr_has_entity_name = True
    _attr_name = "Battery Capacity"
    _attr_translation_key = "battery_capacity"
    _attr_icon = "mdi:battery-charging"
    _attr_native_unit_of_measurement = "Wh"
    _attr_native_min_value = 100
    _attr_native_max_value = 1500
    _attr_native_step = 1
    _attr_mode = NumberMode.BOX

    def __init__(
        self,
        coordinator: BoschEBikeCoordinator,
        bike_id: str,
        drive_name: str,
    ) -> None:
        self.coordinator = coordinator
        self._bike_id = bike_id
        # A pure function of bike_id, never of how many bikes currently
        # exist - see the registry migration in async_setup_entry for why.
        self._attr_unique_id = f"{bike_id}_battery_capacity"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, bike_id)},
            name=drive_name,
            manufacturer="Bosch",
            model=drive_name,
        )
        self._attr_native_value = coordinator.battery_capacity_wh(bike_id)

    async def async_set_native_value(self, value: float) -> None:
        """Update this bike's battery capacity."""
        self._attr_native_value = value
        self.coordinator.set_battery_capacity(self._bike_id, value)
        self.async_write_ha_state()


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
