"""Sensor platform for Bosch eBike."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfLength, UnitOfSpeed, UnitOfTime, UnitOfEnergy, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import BoschEBikeCoordinator


def _safe_get(data: dict, *keys: str, default: Any = None) -> Any:
    """Safely traverse nested dicts."""
    for key in keys:
        if not isinstance(data, dict):
            return default
        data = data.get(key)
        if data is None:
            return default
    return data


def _parse_timestamp(value: str | None) -> datetime | None:
    """Parse Bosch API timestamp strings into datetime objects for HA."""
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _format_timestamp(value: str | None, include_time: bool = True) -> str | None:
    """Format Bosch API timestamps for fixed display in Home Assistant."""
    dt = _parse_timestamp(value)
    if dt is None:
        return None
    dt = dt.astimezone()
    return dt.strftime("%d.%m.%Y %H:%M:%S" if include_time else "%d.%m.%Y")


@dataclass(frozen=True, kw_only=True)
class BoschBikeSensorDescription(SensorEntityDescription):
    """Describe a Bosch eBike sensor."""

    value_fn: Callable[[dict], Any]
    is_activity: bool = False
    is_aggregate: bool = False


def _calc_difficulty(activity: dict) -> float | None:
    """Calculate elevation gain per km (difficulty factor)."""
    gain = _safe_get(activity, "elevation", "gain")
    distance = activity.get("distance")
    if not gain or not distance or distance <= 0:
        return None
    distance_km = distance / 1000
    if distance_km <= 0:
        return None
    return round(gain / distance_km, 1)


def _calc_days_since(activity: dict) -> int | None:
    """Calculate days since the last ride."""
    start = _safe_get(activity, "startTime")
    if not start:
        return None
    dt = _parse_timestamp(start)
    if not dt:
        return None
    now = datetime.now(timezone.utc)
    delta = now - dt
    return max(0, delta.days)


def _format_assist_modes(data: dict) -> str | None:
    """Format active assist modes as readable string."""
    modes = _safe_get(data, "driveUnit", "activeAssistModes")
    if not modes:
        return None
    names = [m.get("name", "?") for m in modes if m.get("name") != "0"]
    return ", ".join(names) if names else None


BIKE_SENSORS: tuple[BoschBikeSensorDescription, ...] = (
    BoschBikeSensorDescription(
        key="odometer",
        translation_key="odometer",
        name="Odometer",
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:counter",
        value_fn=lambda d: round(_safe_get(d, "driveUnit", "odometer", default=0) / 1000, 1),
    ),
    BoschBikeSensorDescription(
        key="motor_total_hours",
        translation_key="motor_total_hours",
        name="Motor Total Hours",
        native_unit_of_measurement=UnitOfTime.HOURS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:engine",
        value_fn=lambda d: _safe_get(d, "driveUnit", "powerOnTime", "total"),
    ),
    BoschBikeSensorDescription(
        key="motor_assist_hours",
        translation_key="motor_assist_hours",
        name="Motor Assist Hours",
        native_unit_of_measurement=UnitOfTime.HOURS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:engine",
        value_fn=lambda d: _safe_get(d, "driveUnit", "powerOnTime", "withMotorSupport"),
    ),
    BoschBikeSensorDescription(
        key="max_assist_speed",
        translation_key="max_assist_speed",
        name="Max Assist Speed",
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        icon="mdi:speedometer",
        value_fn=lambda d: _safe_get(d, "driveUnit", "maximumAssistanceSpeed"),
    ),
    BoschBikeSensorDescription(
        key="active_assist_modes",
        translation_key="active_assist_modes",
        name="Active Assist Modes",
        icon="mdi:bike-fast",
        value_fn=_format_assist_modes,
    ),
    BoschBikeSensorDescription(
        key="walk_assist_speed",
        translation_key="walk_assist_speed",
        name="Walk Assist Speed",
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        icon="mdi:walk",
        value_fn=lambda d: _safe_get(d, "driveUnit", "walkAssistConfiguration", "maximumSpeed"),
    ),
    BoschBikeSensorDescription(
        key="next_service_odometer",
        translation_key="next_service_odometer",
        name="Next Service Odometer",
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        icon="mdi:wrench-clock",
        value_fn=lambda d: round(_safe_get(d, "serviceDue", "odometer", default=0) / 1000, 1),
    ),
)

ACTIVITY_SENSORS: tuple[BoschBikeSensorDescription, ...] = (
    BoschBikeSensorDescription(
        key="last_ride_distance",
        translation_key="last_ride_distance",
        name="Last Ride Distance",
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        icon="mdi:map-marker-distance",
        value_fn=lambda d: round(_safe_get(d, "distance", default=0) / 1000, 2),
        is_activity=True,
    ),
    BoschBikeSensorDescription(
        key="last_ride_duration",
        translation_key="last_ride_duration",
        name="Last Ride Duration",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        device_class=SensorDeviceClass.DURATION,
        icon="mdi:timer-outline",
        value_fn=lambda d: round(_safe_get(d, "durationWithoutStops", default=0) / 60, 1),
        is_activity=True,
    ),
    BoschBikeSensorDescription(
        key="last_ride_avg_speed",
        translation_key="last_ride_avg_speed",
        name="Last Ride Avg Speed",
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        icon="mdi:speedometer",
        value_fn=lambda d: _safe_get(d, "speed", "average"),
        is_activity=True,
    ),
    BoschBikeSensorDescription(
        key="last_ride_max_speed",
        translation_key="last_ride_max_speed",
        name="Last Ride Max Speed",
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        icon="mdi:speedometer",
        value_fn=lambda d: _safe_get(d, "speed", "maximum"),
        is_activity=True,
    ),
    BoschBikeSensorDescription(
        key="last_ride_calories",
        translation_key="last_ride_calories",
        name="Last Ride Calories",
        native_unit_of_measurement="kcal",
        icon="mdi:fire",
        value_fn=lambda d: _safe_get(d, "caloriesBurned"),
        is_activity=True,
    ),
    BoschBikeSensorDescription(
        key="last_ride_elevation_gain",
        translation_key="last_ride_elevation_gain",
        name="Last Ride Elevation Gain",
        native_unit_of_measurement=UnitOfLength.METERS,
        icon="mdi:elevation-rise",
        value_fn=lambda d: _safe_get(d, "elevation", "gain"),
        is_activity=True,
    ),
    BoschBikeSensorDescription(
        key="last_ride_date",
        translation_key="last_ride_date",
        name="Last Ride Date",
        icon="mdi:calendar",
        value_fn=lambda d: _format_timestamp(_safe_get(d, "startTime"), include_time=False),
        is_activity=True,
    ),
    BoschBikeSensorDescription(
        key="last_ride_title",
        translation_key="last_ride_title",
        name="Last Ride Title",
        icon="mdi:tag-text",
        value_fn=lambda d: _safe_get(d, "title"),
        is_activity=True,
    ),
    BoschBikeSensorDescription(
        key="last_ride_avg_cadence",
        translation_key="last_ride_avg_cadence",
        name="Last Ride Avg Cadence",
        native_unit_of_measurement="rpm",
        icon="mdi:rotate-right",
        value_fn=lambda d: _safe_get(d, "cadence", "average"),
        is_activity=True,
    ),
    BoschBikeSensorDescription(
        key="last_ride_max_cadence",
        translation_key="last_ride_max_cadence",
        name="Last Ride Max Cadence",
        native_unit_of_measurement="rpm",
        icon="mdi:rotate-right",
        value_fn=lambda d: _safe_get(d, "cadence", "maximum"),
        is_activity=True,
    ),
    BoschBikeSensorDescription(
        key="last_ride_avg_power",
        translation_key="last_ride_avg_power",
        name="Last Ride Avg Rider Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        icon="mdi:lightning-bolt",
        value_fn=lambda d: _safe_get(d, "riderPower", "average"),
        is_activity=True,
    ),
    BoschBikeSensorDescription(
        key="last_ride_max_power",
        translation_key="last_ride_max_power",
        name="Last Ride Max Rider Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        icon="mdi:lightning-bolt",
        value_fn=lambda d: _safe_get(d, "riderPower", "maximum"),
        is_activity=True,
    ),
    BoschBikeSensorDescription(
        key="last_ride_elevation_loss",
        translation_key="last_ride_elevation_loss",
        name="Last Ride Elevation Loss",
        native_unit_of_measurement=UnitOfLength.METERS,
        icon="mdi:elevation-decline",
        value_fn=lambda d: _safe_get(d, "elevation", "loss"),
        is_activity=True,
    ),
    BoschBikeSensorDescription(
        key="last_ride_start_time",
        translation_key="last_ride_start_time",
        name="Last Ride Start Time",
        icon="mdi:calendar-clock",
        value_fn=lambda d: _format_timestamp(_safe_get(d, "startTime")),
        is_activity=True,
    ),
    BoschBikeSensorDescription(
        key="last_ride_end_time",
        translation_key="last_ride_end_time",
        name="Last Ride End Time",
        icon="mdi:calendar-clock",
        value_fn=lambda d: _format_timestamp(_safe_get(d, "endTime")),
        is_activity=True,
    ),
    BoschBikeSensorDescription(
        key="last_ride_difficulty",
        translation_key="last_ride_difficulty",
        name="Last Ride Difficulty",
        native_unit_of_measurement="m/km",
        icon="mdi:terrain",
        value_fn=lambda d: _calc_difficulty(d),
        is_activity=True,
    ),
    BoschBikeSensorDescription(
        key="days_since_last_ride",
        translation_key="days_since_last_ride",
        name="Days Since Last Ride",
        native_unit_of_measurement=UnitOfTime.DAYS,
        icon="mdi:calendar-alert",
        value_fn=lambda d: _calc_days_since(d),
        is_activity=True,
    ),
)

# Battery consumption sensors (Wh delta tracking)
BATTERY_CONSUMPTION_SENSORS: tuple[BoschBikeSensorDescription, ...] = (
    BoschBikeSensorDescription(
        key="last_ride_battery_wh",
        translation_key="last_ride_battery_wh",
        name="Last Ride Battery Consumption",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        icon="mdi:battery-minus",
        value_fn=lambda d: None,
        is_activity=True,
    ),
    BoschBikeSensorDescription(
        key="last_ride_battery_percent",
        translation_key="last_ride_battery_percent",
        name="Last Ride Battery Percent",
        native_unit_of_measurement="%",
        icon="mdi:battery-50",
        value_fn=lambda d: None,
        is_activity=True,
    ),
)


def _sum_activities(activities: list[dict], key: str, *subkeys: str, divisor: float = 1.0) -> float | None:
    """Sum a value across all activities."""
    if not activities:
        return None
    total = 0.0
    for a in activities:
        val = _safe_get(a, key, *subkeys) if subkeys else a.get(key)
        if val is not None:
            total += val
    return round(total / divisor, 2) if divisor != 1.0 else round(total, 2)


def _avg_activities(activities: list[dict], key: str, *subkeys: str) -> float | None:
    """Average a value across all activities."""
    if not activities:
        return None
    values = []
    for a in activities:
        val = _safe_get(a, key, *subkeys) if subkeys else a.get(key)
        if val is not None:
            values.append(val)
    return round(sum(values) / len(values), 2) if values else None


AGGREGATE_SENSORS: tuple[BoschBikeSensorDescription, ...] = (
    BoschBikeSensorDescription(
        key="total_rides",
        name="Total Rides",
        icon="mdi:counter",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda activities: len(activities) if activities else 0,
        is_aggregate=True,
    ),
    BoschBikeSensorDescription(
        key="total_distance_activities",
        name="Total Distance (Activities)",
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:map-marker-distance",
        value_fn=lambda activities: _sum_activities(activities, "distance", divisor=1000),
        is_aggregate=True,
    ),
    BoschBikeSensorDescription(
        key="total_duration",
        name="Total Ride Duration",
        native_unit_of_measurement=UnitOfTime.HOURS,
        device_class=SensorDeviceClass.DURATION,
        icon="mdi:timer-outline",
        value_fn=lambda activities: _sum_activities(activities, "durationWithoutStops", divisor=3600),
        is_aggregate=True,
    ),
    BoschBikeSensorDescription(
        key="total_calories",
        name="Total Calories",
        native_unit_of_measurement="kcal",
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:fire",
        value_fn=lambda activities: _sum_activities(activities, "caloriesBurned"),
        is_aggregate=True,
    ),
    BoschBikeSensorDescription(
        key="total_elevation_gain",
        name="Total Elevation Gain",
        native_unit_of_measurement=UnitOfLength.METERS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:elevation-rise",
        value_fn=lambda activities: _sum_activities(activities, "elevation", "gain"),
        is_aggregate=True,
    ),
    BoschBikeSensorDescription(
        key="avg_speed_all_rides",
        name="Avg Speed (All Rides)",
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        icon="mdi:speedometer-medium",
        value_fn=lambda activities: _avg_activities(activities, "speed", "average"),
        is_aggregate=True,
    ),
    BoschBikeSensorDescription(
        key="avg_power_all_rides",
        name="Avg Rider Power (All Rides)",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        icon="mdi:lightning-bolt",
        value_fn=lambda activities: _avg_activities(activities, "riderPower", "average"),
        is_aggregate=True,
    ),
    BoschBikeSensorDescription(
        key="avg_cadence_all_rides",
        name="Avg Cadence (All Rides)",
        native_unit_of_measurement="rpm",
        icon="mdi:rotate-right",
        value_fn=lambda activities: _avg_activities(activities, "cadence", "average"),
        is_aggregate=True,
    ),
)


GPS_COORDINATE_SENSORS: tuple[BoschBikeSensorDescription, ...] = (
    BoschBikeSensorDescription(
        key="last_ride_start_location",
        translation_key="last_ride_start_location",
        name="Last Ride Start Location",
        icon="mdi:map-marker",
        value_fn=lambda d: None,  # handled in BoschGPSSensor
    ),
    BoschBikeSensorDescription(
        key="last_ride_end_location",
        translation_key="last_ride_end_location",
        name="Last Ride End Location",
        icon="mdi:map-marker-check",
        value_fn=lambda d: None,  # handled in BoschGPSSensor
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Bosch eBike sensors from a config entry."""
    coordinator: BoschEBikeCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[BoschEBikeSensor] = []

    bikes = coordinator.data.get("bikes", [])
    for bike in bikes:
        bike_id = bike.get("id", "unknown")
        drive_name = _safe_get(bike, "driveUnit", "productName") or "eBike"

        # Bike hardware sensors
        for desc in BIKE_SENSORS:
            entities.append(BoschEBikeSensor(coordinator, desc, bike_id, drive_name))

        # Battery sensors (per battery)
        for idx, battery in enumerate(bike.get("batteries", []) or []):
            bat_name = battery.get("productName") or f"Battery {idx + 1}"
            bat_prefix = f"battery_{idx + 1}"
            entities.extend(
                _create_battery_sensors(coordinator, bike_id, drive_name, battery, bat_prefix, bat_name)
            )

        # Activity sensors (attached to first bike)
        for desc in ACTIVITY_SENSORS:
            entities.append(BoschEBikeSensor(coordinator, desc, bike_id, drive_name))

        # Aggregate sensors (statistics across all rides)
        for desc in AGGREGATE_SENSORS:
            entities.append(BoschEBikeSensor(coordinator, desc, bike_id, drive_name))

        # GPS coordinate sensors (start/end location)
        for desc in GPS_COORDINATE_SENSORS:
            entities.append(BoschGPSSensor(coordinator, desc, bike_id, drive_name))

        # Battery consumption sensors (Wh delta tracking)
        for desc in BATTERY_CONSUMPTION_SENSORS:
            entities.append(BoschBatteryConsumptionSensor(coordinator, desc, bike_id, drive_name))

        # Service-due derived sensors (days/km remaining)
        entities.append(BoschServiceDueSensor(coordinator, bike_id, drive_name, kind="days"))
        entities.append(BoschServiceDueSensor(coordinator, bike_id, drive_name, kind="km"))

        # Maintenance overview (count of items due/overdue + full list as attributes)
        entities.append(BoschMaintenanceOverviewSensor(coordinator, bike_id, drive_name))

    async_add_entities(entities)


def _create_battery_sensors(
    coordinator: BoschEBikeCoordinator,
    bike_id: str,
    drive_name: str,
    battery: dict,
    prefix: str,
    bat_name: str,
) -> list[BoschEBikeSensor]:
    """Create sensor entities for a single battery."""
    descs = [
        BoschBikeSensorDescription(
            key=f"{prefix}_wh_lifetime",
            name=f"{bat_name} Wh Lifetime",
            native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL_INCREASING,
            icon="mdi:battery-charging",
            value_fn=lambda d, b=battery: b.get("deliveredWhOverLifetime"),
        ),
        BoschBikeSensorDescription(
            key=f"{prefix}_charge_cycles_total",
            name=f"{bat_name} Charge Cycles",
            icon="mdi:battery-sync",
            state_class=SensorStateClass.TOTAL_INCREASING,
            value_fn=lambda d, b=battery: _safe_get(b, "chargeCycles", "total"),
        ),
        BoschBikeSensorDescription(
            key=f"{prefix}_charge_cycles_on_bike",
            name=f"{bat_name} Cycles On Bike",
            icon="mdi:battery-sync",
            state_class=SensorStateClass.TOTAL_INCREASING,
            value_fn=lambda d, b=battery: _safe_get(b, "chargeCycles", "onBike"),
        ),
        BoschBikeSensorDescription(
            key=f"{prefix}_charge_cycles_off_bike",
            name=f"{bat_name} Cycles Off Bike",
            icon="mdi:battery-sync",
            state_class=SensorStateClass.TOTAL_INCREASING,
            value_fn=lambda d, b=battery: _safe_get(b, "chargeCycles", "offBike"),
        ),
    ]
    return [BoschEBikeSensor(coordinator, desc, bike_id, drive_name) for desc in descs]


class BoschEBikeSensor(CoordinatorEntity[BoschEBikeCoordinator], SensorEntity):
    """Representation of a Bosch eBike sensor."""

    entity_description: BoschBikeSensorDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: BoschEBikeCoordinator,
        description: BoschBikeSensorDescription,
        bike_id: str,
        drive_name: str,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._bike_id = bike_id
        self._attr_unique_id = f"{bike_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, bike_id)},
            name=drive_name,
            manufacturer="Bosch",
            model=drive_name,
        )

    @property
    def native_value(self) -> Any:
        """Return the sensor value."""
        if self.entity_description.is_aggregate:
            all_activities = self.coordinator.data.get("all_activities", [])
            return self.entity_description.value_fn(all_activities)

        if self.entity_description.is_activity:
            activity = self.coordinator.data.get("latest_activity")
            if not activity:
                return None
            return self.entity_description.value_fn(activity)

        # Find this bike in coordinator data
        for bike in self.coordinator.data.get("bikes", []):
            if bike.get("id") == self._bike_id:
                return self.entity_description.value_fn(bike)
        return None


class BoschGPSSensor(CoordinatorEntity[BoschEBikeCoordinator], SensorEntity):
    """Sensor for GPS start/end coordinates from activity details."""

    entity_description: BoschBikeSensorDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: BoschEBikeCoordinator,
        description: BoschBikeSensorDescription,
        bike_id: str,
        drive_name: str,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._bike_id = bike_id
        self._attr_unique_id = f"{bike_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, bike_id)},
            name=drive_name,
            manufacturer="Bosch",
            model=drive_name,
        )

    def _get_coordinate(self, index: int) -> dict[str, float] | None:
        """Get coordinate at given index from activity details."""
        details = self.coordinator.data.get("latest_activity_details")
        if not details:
            return None

        points = details.get("activityDetails", []) if isinstance(details, dict) else details

        # Filter valid coordinates (non-zero)
        valid = [
            p for p in points
            if isinstance(p, dict)
            and p.get("latitude") is not None
            and p.get("longitude") is not None
            and p["latitude"] != 0
            and p["longitude"] != 0
        ]
        if not valid:
            return None
        point = valid[index]
        return {"latitude": point["latitude"], "longitude": point["longitude"]}

    @property
    def native_value(self) -> str | None:
        """Return formatted coordinate string."""
        is_start = "start" in self.entity_description.key
        coord = self._get_coordinate(0 if is_start else -1)
        if not coord:
            return None
        return f"{coord['latitude']:.6f}, {coord['longitude']:.6f}"

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return lat/lon as separate attributes for use in automations."""
        is_start = "start" in self.entity_description.key
        coord = self._get_coordinate(0 if is_start else -1)
        if not coord:
            return None
        return {
            "latitude": coord["latitude"],
            "longitude": coord["longitude"],
        }


class BoschBatteryConsumptionSensor(CoordinatorEntity[BoschEBikeCoordinator], SensorEntity):
    """Sensor for estimated battery consumption per ride (Wh delta tracking)."""

    entity_description: BoschBikeSensorDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: BoschEBikeCoordinator,
        description: BoschBikeSensorDescription,
        bike_id: str,
        drive_name: str,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._bike_id = bike_id
        self._attr_unique_id = f"{bike_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, bike_id)},
            name=drive_name,
            manufacturer="Bosch",
            model=drive_name,
        )

    def _get_consumption(self) -> dict[str, Any] | None:
        """Get consumption data for the latest activity."""
        activity = self.coordinator.data.get("latest_activity")
        if not activity:
            return None
        aid = activity.get("id")
        if not aid:
            return None
        consumption = self.coordinator.data.get("activity_consumption", {})
        return consumption.get(aid)

    @property
    def native_value(self) -> float | None:
        """Return Wh or percentage depending on sensor key."""
        consumption = self._get_consumption()
        if not consumption:
            return None
        if "percent" in self.entity_description.key:
            return consumption.get("percentage")
        return consumption.get("consumed_wh")

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return additional consumption details."""
        consumption = self._get_consumption()
        if not consumption:
            return None
        return {
            "consumed_wh": consumption.get("consumed_wh"),
            "percentage": consumption.get("percentage"),
            "capacity_wh": consumption.get("capacity_wh"),
            "is_exact": consumption.get("is_exact"),
        }


class BoschServiceDueSensor(CoordinatorEntity[BoschEBikeCoordinator], SensorEntity):
    """Days or kilometres remaining until the next Bosch service is due."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: BoschEBikeCoordinator,
        bike_id: str,
        drive_name: str,
        kind: str,
    ) -> None:
        super().__init__(coordinator)
        self._bike_id = bike_id
        self._kind = kind  # "days" or "km"
        if kind == "days":
            self._attr_translation_key = "service_due_in_days"
            self._attr_name = "Service Due In Days"
            self._attr_native_unit_of_measurement = "d"
            self._attr_icon = "mdi:calendar-clock"
        else:
            self._attr_translation_key = "service_due_in_km"
            self._attr_name = "Service Due In Kilometres"
            self._attr_native_unit_of_measurement = "km"
            self._attr_icon = "mdi:road"
        self._attr_unique_id = f"{bike_id}_service_due_in_{kind}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, bike_id)},
            name=drive_name,
            manufacturer="Bosch",
            model=drive_name,
        )

    def _bike(self) -> dict | None:
        for bike in (self.coordinator.data.get("bikes", []) if self.coordinator.data else []):
            if bike.get("id") == self._bike_id:
                return bike
        return None

    @property
    def native_value(self):
        bike = self._bike()
        if not bike:
            return None
        service = bike.get("serviceDue") or {}
        if self._kind == "days":
            from datetime import timezone as _tz
            from homeassistant.util import dt as _dt
            date = service.get("date")
            if not date:
                return None
            try:
                due = _dt.parse_datetime(date) or _dt.parse_datetime(date + "T00:00:00")
            except (TypeError, ValueError):
                return None
            if not due:
                return None
            if due.tzinfo is None:
                due = due.replace(tzinfo=_tz.utc)
            return round((due - _dt.utcnow()).total_seconds() / 86400, 1)
        # km
        service_odo = service.get("odometer")
        if not isinstance(service_odo, (int, float)):
            return None
        current_odo = self.coordinator._bike_current_odometer(bike)
        if current_odo is None:
            return None
        return round((float(service_odo) - current_odo) / 1000, 1)


class BoschMaintenanceOverviewSensor(CoordinatorEntity[BoschEBikeCoordinator], SensorEntity):
    """Aggregated overview of custom maintenance items for one bike.

    State: number of items needing attention (due_soon or overdue).
    Attributes: full list of items with their remaining km / days.
    """

    _attr_has_entity_name = True
    _attr_name = "Maintenance Items Due"
    _attr_translation_key = "maintenance_overview"
    _attr_icon = "mdi:tools"

    def __init__(
        self,
        coordinator: BoschEBikeCoordinator,
        bike_id: str,
        drive_name: str,
    ) -> None:
        super().__init__(coordinator)
        self._bike_id = bike_id
        self._attr_unique_id = f"{bike_id}_maintenance_overview"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, bike_id)},
            name=drive_name,
            manufacturer="Bosch",
            model=drive_name,
        )

    def _items(self) -> list[dict]:
        return (self.coordinator._maintenance.get(self._bike_id) or {}).get("items", [])

    @property
    def native_value(self) -> int:
        from .const import SERVICE_WARN_DAYS, SERVICE_WARN_KM
        count = 0
        for item in self._items():
            rk = item.get("_remaining_km")
            rd = item.get("_remaining_days")
            if (rk is not None and rk <= SERVICE_WARN_KM) or (rd is not None and rd <= SERVICE_WARN_DAYS):
                count += 1
        return count

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "items": [
                {
                    "id": item.get("id"),
                    "name": item.get("name"),
                    "interval_km": item.get("interval_km"),
                    "interval_days": item.get("interval_days"),
                    "remaining_km": item.get("_remaining_km"),
                    "remaining_days": item.get("_remaining_days"),
                    "last_done_at": item.get("last_done_at"),
                }
                for item in self._items()
            ],
            "bike_id": self._bike_id,
        }
