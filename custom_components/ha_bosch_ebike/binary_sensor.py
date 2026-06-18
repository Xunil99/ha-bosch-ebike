"""Binary sensor platform for Bosch eBike.

Two per-bike binary sensors derived from the Data Act endpoints (bike pass
and digital service book). Both consume coordinator data through the pure
parsers in ``profile_extra`` so the parsing logic stays unit-testable without
a Home Assistant runtime.

Like the dynamic per-bike sensors in ``sensor.py`` (reachable range, battery
state-of-health) these use literal names with ``has_entity_name=True`` and no
translation_key.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import BoschEBikeCoordinator
from .profile_extra import software_update_available, theft_status


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create the per-bike Data Act binary sensors from a config entry."""
    coordinator: BoschEBikeCoordinator = hass.data[DOMAIN][entry.entry_id]

    # eBike System 2 has no bike-pass / service-book endpoints, so theft and
    # software-update would always be unknown. Skip the platform entirely.
    if coordinator.is_bes2:
        return

    entities: list[BinarySensorEntity] = []
    for bike in coordinator.data.get("bikes", []):
        bike_id = bike.get("id")
        if not bike_id:
            continue
        drive = bike.get("driveUnit") or {}
        drive_name = drive.get("productName") or "eBike"
        entities.append(BoschTheftReportedBinarySensor(coordinator, bike_id, drive_name))
        entities.append(BoschSoftwareUpdateBinarySensor(coordinator, bike_id, drive_name))

    async_add_entities(entities)


class _BoschBikeBinarySensor(CoordinatorEntity[BoschEBikeCoordinator], BinarySensorEntity):
    """Base for per-bike binary sensors attached to a bike's device."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: BoschEBikeCoordinator,
        bike_id: str,
        drive_name: str,
    ) -> None:
        super().__init__(coordinator)
        self._bike_id = bike_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, bike_id)},
            name=drive_name,
            manufacturer="Bosch",
            model=drive_name,
        )


class BoschTheftReportedBinarySensor(_BoschBikeBinarySensor):
    """Whether the bike is currently reported stolen (from the bike pass).

    ``is_on`` is None (unknown) when there is no bike-pass data — e.g. the
    bike has no Data Act consent or the endpoint has not been fetched. The
    theft location/time is exposed as attributes only when reported.
    """

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_name = "Theft Reported"
    _attr_icon = "mdi:shield-alert"

    def __init__(
        self,
        coordinator: BoschEBikeCoordinator,
        bike_id: str,
        drive_name: str,
    ) -> None:
        super().__init__(coordinator, bike_id, drive_name)
        self._attr_unique_id = f"{bike_id}_theft_reported"

    def _theft(self) -> dict | None:
        """Resolve theft state for this bike, or None when unknown."""
        bike_pass = self.coordinator.data.get("bike_pass", {}).get(self._bike_id)
        return theft_status(bike_pass)

    @property
    def is_on(self) -> bool | None:
        """True if reported stolen, False if not, None if no bike-pass data."""
        ts = self._theft()
        return None if ts is None else ts["reported"]

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Expose theft location/time only when actually reported."""
        ts = self._theft()
        if ts is None or not ts.get("reported"):
            return None
        return {
            "latitude": ts.get("latitude"),
            "longitude": ts.get("longitude"),
            "address": ts.get("address"),
            "detected_at": ts.get("detected_at"),
            "since": ts.get("since"),
        }


class BoschSoftwareUpdateBinarySensor(_BoschBikeBinarySensor):
    """Whether a software update is available for any bike component.

    Driven by the newest CUSTOMER_REPORT in the digital service book.
    ``software_update_available`` already returns True / False / None, so the
    value (including None -> unknown) is passed through directly.
    """

    _attr_device_class = BinarySensorDeviceClass.UPDATE
    _attr_name = "Software Update Available"
    _attr_icon = "mdi:package-up"

    def __init__(
        self,
        coordinator: BoschEBikeCoordinator,
        bike_id: str,
        drive_name: str,
    ) -> None:
        super().__init__(coordinator, bike_id, drive_name)
        self._attr_unique_id = f"{bike_id}_software_update_available"

    @property
    def is_on(self) -> bool | None:
        """True / False / None straight from the parser (None -> unknown)."""
        records = self.coordinator.data.get("service_records", {}).get(self._bike_id)
        return software_update_available(records)
