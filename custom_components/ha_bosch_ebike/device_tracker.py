"""Device tracker platform for Bosch eBike.

One per-bike tracker exposing the bike's last known theft location. This is
the only location the Bosch Data Act API provides: it appears solely when a
theft has been reported (with a location) for the bike.

Like the per-bike binary sensors in ``binary_sensor.py`` this consumes the
pure parser ``profile_extra.theft_status`` so the parsing logic stays
unit-testable without a Home Assistant runtime, uses a literal name with
``has_entity_name=True`` and attaches to the bike's device.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.device_tracker import SourceType, TrackerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import BoschEBikeCoordinator
from .profile_extra import theft_status


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create the per-bike last-known-location tracker from a config entry."""
    coordinator: BoschEBikeCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[TrackerEntity] = []
    for bike in coordinator.data.get("bikes", []):
        bike_id = bike.get("id")
        if not bike_id:
            continue
        drive = bike.get("driveUnit") or {}
        drive_name = drive.get("productName") or "eBike"
        entities.append(BoschLastKnownLocationTracker(coordinator, bike_id, drive_name))

    async_add_entities(entities)


class BoschLastKnownLocationTracker(
    CoordinatorEntity[BoschEBikeCoordinator], TrackerEntity
):
    """The bike's last known theft location (from the bike pass).

    Latitude/longitude are present only when a theft with a location has been
    reported; otherwise both are None (the entity has no fix). Every property
    is None-safe: when there is no bike-pass data or no location, nothing is
    raised and the tracker simply reports no coordinates.
    """

    _attr_has_entity_name = True
    _attr_name = "Last Known Location"
    _attr_icon = "mdi:map-marker-alert"

    def __init__(
        self,
        coordinator: BoschEBikeCoordinator,
        bike_id: str,
        drive_name: str,
    ) -> None:
        super().__init__(coordinator)
        self._bike_id = bike_id
        self._attr_unique_id = f"{bike_id}_last_known_location"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, bike_id)},
            name=drive_name,
            manufacturer="Bosch",
            model=drive_name,
        )

    def _theft(self) -> dict | None:
        """Resolve theft state for this bike, or None when unknown."""
        bike_pass = self.coordinator.data.get("bike_pass", {}).get(self._bike_id)
        return theft_status(bike_pass)

    @property
    def source_type(self) -> SourceType:
        """This tracker reports a GPS-style latitude/longitude fix."""
        return SourceType.GPS

    @property
    def latitude(self) -> float | None:
        """Last known theft latitude, or None when no location is known."""
        ts = self._theft()
        return ts["latitude"] if ts and ts.get("latitude") is not None else None

    @property
    def longitude(self) -> float | None:
        """Last known theft longitude, or None when no location is known."""
        ts = self._theft()
        return ts["longitude"] if ts and ts.get("longitude") is not None else None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Expose address/time only when an actual location exists."""
        ts = self._theft()
        if not ts or ts.get("latitude") is None:
            return None
        return {
            "address": ts.get("address"),
            "detected_at": ts.get("detected_at"),
            "since": ts.get("since"),
        }
