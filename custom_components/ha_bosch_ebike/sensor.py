"""Sensor platform for Bosch eBike."""

from __future__ import annotations

import math
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
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfEnergy,
    UnitOfLength,
    UnitOfPower,
    UnitOfSpeed,
    UnitOfTime,
)
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import BoschEBikeCoordinator
from .profile_extra import (
    assist_mode_stats,
    battery_soh,
    component_inventory,
    last_service,
    max_altitude,
    next_service_date,
    reachable_ranges,
)

RANGE_DISCLAIMER = (
    "Estimate based on your past consumption over the last ~500 km. "
    "Actual range depends on assist mode, terrain, wind, temperature "
    "and battery age."
)


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
    # False = Smart-System-only (data BES2 never provides); skipped for BES2.
    bes2: bool = True


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
        bes2=False,
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
        bes2=False,
    ),
    BoschBikeSensorDescription(
        key="max_assist_speed",
        translation_key="max_assist_speed",
        name="Max Assist Speed",
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        icon="mdi:speedometer",
        value_fn=lambda d: _safe_get(d, "driveUnit", "maximumAssistanceSpeed"),
        bes2=False,
    ),
    BoschBikeSensorDescription(
        key="active_assist_modes",
        translation_key="active_assist_modes",
        name="Active Assist Modes",
        icon="mdi:bike-fast",
        value_fn=_format_assist_modes,
        bes2=False,
    ),
    BoschBikeSensorDescription(
        key="walk_assist_speed",
        translation_key="walk_assist_speed",
        name="Walk Assist Speed",
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        icon="mdi:walk",
        value_fn=lambda d: _safe_get(d, "driveUnit", "walkAssistConfiguration", "maximumSpeed"),
        bes2=False,
    ),
    BoschBikeSensorDescription(
        key="next_service_odometer",
        translation_key="next_service_odometer",
        name="Next Service Odometer",
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        icon="mdi:wrench-clock",
        value_fn=lambda d: round(_safe_get(d, "serviceDue", "odometer", default=0) / 1000, 1),
        bes2=False,
    ),
    BoschBikeSensorDescription(
        key="next_service_date",
        translation_key="next_service_date",
        name="Next Service Date",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:wrench-clock",
        value_fn=lambda d: next_service_date(d),
        bes2=False,
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
    BoschBikeSensorDescription(
        key="last_ride_start_odometer",
        translation_key="last_ride_start_odometer",
        name="Last Ride Start Odometer",
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        icon="mdi:counter",
        value_fn=lambda d: _last_ride_start_odometer(d),
        is_activity=True,
    ),
)


def _last_ride_start_odometer(activity: dict) -> float | None:
    """Start odometer of the latest ride in km, or None if absent."""
    raw = _safe_get(activity, "startOdometer")
    if not isinstance(raw, (int, float)) or isinstance(raw, bool):
        return None
    return round(raw / 1000, 1)

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
        translation_key="total_rides",
        name="Total Rides",
        icon="mdi:counter",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda activities: len(activities) if activities else 0,
        is_aggregate=True,
    ),
    BoschBikeSensorDescription(
        key="total_distance_activities",
        translation_key="total_distance_activities",
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
        translation_key="total_duration",
        name="Total Ride Duration",
        native_unit_of_measurement=UnitOfTime.HOURS,
        device_class=SensorDeviceClass.DURATION,
        icon="mdi:timer-outline",
        value_fn=lambda activities: _sum_activities(activities, "durationWithoutStops", divisor=3600),
        is_aggregate=True,
    ),
    BoschBikeSensorDescription(
        key="total_calories",
        translation_key="total_calories",
        name="Total Calories",
        native_unit_of_measurement="kcal",
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:fire",
        value_fn=lambda activities: _sum_activities(activities, "caloriesBurned"),
        is_aggregate=True,
    ),
    BoschBikeSensorDescription(
        key="total_elevation_gain",
        translation_key="total_elevation_gain",
        name="Total Elevation Gain",
        native_unit_of_measurement=UnitOfLength.METERS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:elevation-rise",
        value_fn=lambda activities: _sum_activities(activities, "elevation", "gain"),
        is_aggregate=True,
    ),
    BoschBikeSensorDescription(
        key="avg_speed_all_rides",
        translation_key="avg_speed_all_rides",
        name="Avg Speed (All Rides)",
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        icon="mdi:speedometer-medium",
        value_fn=lambda activities: _avg_activities(activities, "speed", "average"),
        is_aggregate=True,
    ),
    BoschBikeSensorDescription(
        key="avg_power_all_rides",
        translation_key="avg_power_all_rides",
        name="Avg Rider Power (All Rides)",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        icon="mdi:lightning-bolt",
        value_fn=lambda activities: _avg_activities(activities, "riderPower", "average"),
        is_aggregate=True,
    ),
    BoschBikeSensorDescription(
        key="avg_cadence_all_rides",
        translation_key="avg_cadence_all_rides",
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


# Lifetime totals from the BES2 /statistics endpoint. Only created when the
# bike carries `_bes2_statistics` (i.e. eBike System 2); the value resolves
# live from coordinator.data. Smart System bikes never get these.
BES2_STATISTICS_SENSORS: tuple[BoschBikeSensorDescription, ...] = (
    BoschBikeSensorDescription(
        key="total_elevation_gain",
        name="Total Elevation Gain",
        native_unit_of_measurement=UnitOfLength.METERS,
        icon="mdi:elevation-rise",
        value_fn=lambda d: _safe_get(d, "_bes2_statistics", "total_elevation_gain_m"),
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
    # eBike System 2 has no service book / bike pass / per-mode / consumption /
    # range-estimate data; those entities are skipped so BES2 users don't get a
    # row of permanently-unknown sensors. GPS, activities, odometer, totals and
    # maintenance work for both systems.
    is_bes2 = coordinator.is_bes2
    for bike in bikes:
        bike_id = bike.get("id", "unknown")
        drive_name = _safe_get(bike, "driveUnit", "productName") or "eBike"

        # Bike hardware sensors (skip Smart-System-only ones for BES2)
        for desc in BIKE_SENSORS:
            if is_bes2 and not desc.bes2:
                continue
            entities.append(BoschEBikeSensor(coordinator, desc, bike_id, drive_name))

        # BES2 lifetime totals (only when /statistics data is present)
        if bike.get("_bes2_statistics"):
            for desc in BES2_STATISTICS_SENSORS:
                entities.append(BoschEBikeSensor(coordinator, desc, bike_id, drive_name))

        # Battery sensors (per battery). BES2 batteries carry no cloud fields
        # (deliveredWhOverLifetime/chargeCycles) and no service-book SoH, so the
        # whole per-battery block is skipped for BES2.
        for idx, battery in enumerate([] if is_bes2 else (bike.get("batteries", []) or [])):
            bat_name = battery.get("productName") or f"Battery {idx + 1}"
            bat_prefix = f"battery_{idx + 1}"
            entities.extend(
                _create_battery_sensors(coordinator, bike_id, drive_name, battery, bat_prefix, bat_name)
            )

            # State-of-Health sensors from the service book (dealer capacity
            # measurement). serialNumber captured at creation time; values
            # resolve from coordinator.data["service_records"]. Commonly None.
            bat_serial = battery.get("serialNumber")
            entities.append(
                BoschBatterySohSensor(
                    coordinator, bike_id, drive_name, bat_name, bat_prefix, bat_serial,
                    field="soh_pct",
                    name_suffix="State of Health",
                    key_suffix="soh",
                    native_unit_of_measurement=PERCENTAGE,
                    state_class=SensorStateClass.MEASUREMENT,
                    icon="mdi:battery-heart-variant",
                    suggested_display_precision=0,
                )
            )
            entities.append(
                BoschBatterySohSensor(
                    coordinator, bike_id, drive_name, bat_name, bat_prefix, bat_serial,
                    field="measured_wh",
                    name_suffix="Measured Capacity",
                    key_suffix="measured_capacity",
                    native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
                    state_class=SensorStateClass.MEASUREMENT,
                    icon="mdi:battery",
                )
            )

        # Per-assist-mode reachable range sensors (one per active mode, API order)
        for idx, mode in enumerate(reachable_ranges(bike)):
            mode_name = mode.get("name") or f"Mode {idx + 1}"
            entities.append(
                BoschReachableRangeSensor(coordinator, bike_id, drive_name, idx, mode_name)
            )

        # Per-assist-mode lifetime distance/energy stats from the newest customer
        # report (service book). These only exist when a dealer customer report is
        # present, so we create them based on the modes available at setup time.
        # If service_records is empty/absent at setup, none are created for this
        # bike (nice-to-have; acceptable).
        setup_records = coordinator.data.get("service_records", {}).get(bike_id)
        for idx, stat in enumerate(assist_mode_stats(setup_records)):
            mode_name = stat.get("name") or f"Mode {idx + 1}"
            entities.append(
                BoschLifetimeStatSensor(
                    coordinator, bike_id, drive_name, idx, mode_name, kind="distance"
                )
            )
            entities.append(
                BoschLifetimeStatSensor(
                    coordinator, bike_id, drive_name, idx, mode_name, kind="energy"
                )
            )

        # Service history + component inventory come from the service book /
        # bike profile, which BES2 does not provide -> skip for BES2.
        if not is_bes2:
            entities.append(
                BoschLastServiceSensor(coordinator, bike_id, drive_name, kind="date")
            )
            entities.append(
                BoschLastServiceSensor(coordinator, bike_id, drive_name, kind="dealer")
            )
            entities.append(
                BoschLastServiceSensor(coordinator, bike_id, drive_name, kind="odometer")
            )
            entities.append(
                BoschComponentInventorySensor(coordinator, bike_id, drive_name)
            )

        # Last ride max altitude (single instance, derived from activity details)
        entities.append(
            BoschMaxAltitudeSensor(coordinator, bike_id, drive_name)
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

        # Battery consumption (needs deliveredWhOverLifetime deltas) and the
        # range estimate (needs consumption history) have no BES2 data source.
        if not is_bes2:
            # Battery consumption sensors (Wh delta tracking)
            for desc in BATTERY_CONSUMPTION_SENSORS:
                entities.append(BoschBatteryConsumptionSensor(coordinator, desc, bike_id, drive_name))

        # Service-due derived sensors (days/km remaining). Kept for BES2: they
        # work off the user-editable service-due overrides (date/odometer).
        entities.append(BoschServiceDueSensor(coordinator, bike_id, drive_name, kind="days"))
        entities.append(BoschServiceDueSensor(coordinator, bike_id, drive_name, kind="km"))

        # Estimated range (clearly labelled estimate, derived from history)
        if not is_bes2:
            entities.append(BoschRangeEstimateSensor(coordinator, bike_id, drive_name))
            # Per-bike live SoC sensor (issue #44): each bike's own bridge, not
            # a single account-wide entity, so two bikes never share a value.
            soc_entity = coordinator.live_soc_entity(bike_id)
            if soc_entity:
                entities.append(
                    BoschCurrentRangeSensor(coordinator, bike_id, drive_name, soc_entity)
                )

            # Charging energy over rolling 7/30/365-day windows (dashboard
            # card's charging-cost summary). BES2 has no consumption data,
            # same gate as the range estimate above.
            for window_key, translation_key in ENERGY_WINDOW_DEFS:
                entities.append(
                    BoschEnergyWindowSensor(
                        coordinator, bike_id, drive_name, window_key, translation_key
                    )
                )

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


def _activities_for_bike(coordinator_data: dict, bike_id: str) -> list[dict]:
    """Filter all_activities down to the ones attributed to this bike.

    Falls back to the unfiltered (account-wide) list when attribution is
    empty, which covers single-bike accounts and the brief startup window
    before the first attribution pass has run.
    """
    all_activities = coordinator_data.get("all_activities", [])
    activity_bike = coordinator_data.get("activity_bike", {})
    if not activity_bike:
        return all_activities
    return [a for a in all_activities if activity_bike.get(a.get("id")) == bike_id]


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
            activities = _activities_for_bike(self.coordinator.data, self._bike_id)
            return self.entity_description.value_fn(activities)

        if self.entity_description.is_activity:
            activities = _activities_for_bike(self.coordinator.data, self._bike_id)
            activity = activities[0] if activities else None
            if not activity:
                return None
            return self.entity_description.value_fn(activity)

        # Find this bike in coordinator data
        for bike in self.coordinator.data.get("bikes", []):
            if bike.get("id") == self._bike_id:
                return self.entity_description.value_fn(bike)
        return None


class BoschReachableRangeSensor(CoordinatorEntity[BoschEBikeCoordinator], SensorEntity):
    """Bosch per-assist-mode reachable range (one sensor per active mode).

    Uses a literal mode name (like the per-battery sensors), so no
    translation_key is required. Resolves its value from the live bike data
    via profile_extra.reachable_ranges by position in API order.
    """

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.DISTANCE
    _attr_native_unit_of_measurement = UnitOfLength.KILOMETERS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:map-marker-distance"
    _attr_suggested_display_precision = 1

    def __init__(
        self,
        coordinator: BoschEBikeCoordinator,
        bike_id: str,
        drive_name: str,
        index: int,
        mode_name: str,
    ) -> None:
        super().__init__(coordinator)
        self._bike_id = bike_id
        self._index = index
        self._mode_name = mode_name
        self._attr_name = f"Reachable Range {mode_name}"
        self._attr_unique_id = f"{bike_id}_reachable_range_{index}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, bike_id)},
            name=drive_name,
            manufacturer="Bosch",
            model=drive_name,
        )

    @property
    def native_value(self) -> float | None:
        """Return the reachable range (km) for this mode by API position."""
        for bike in self.coordinator.data.get("bikes", []):
            if bike.get("id") == self._bike_id:
                ranges = reachable_ranges(bike)
                if len(ranges) <= self._index:
                    return None
                return ranges[self._index]["range_km"]
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose the assist mode this range belongs to."""
        return {"assist_mode": self._mode_name}


class BoschBatterySohSensor(CoordinatorEntity[BoschEBikeCoordinator], SensorEntity):
    """Per-battery State-of-Health / measured-capacity sensor.

    Reads the dealer capacity measurement from the service book via
    profile_extra.battery_soh(service_records, serial). The serial number is
    captured at creation time and the value is resolved live from
    coordinator.data["service_records"], keyed by bike_id. A measurement only
    exists if a dealer performed a battery capacity test, so in the common case
    battery_soh returns None and the entity reports unavailable / None.

    Uses a literal name (like the other per-battery sensors), so no
    translation_key is required.
    """

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: BoschEBikeCoordinator,
        bike_id: str,
        drive_name: str,
        bat_name: str,
        prefix: str,
        serial: str | None,
        *,
        field: str,
        name_suffix: str,
        key_suffix: str,
        native_unit_of_measurement: str | None = None,
        device_class: SensorDeviceClass | None = None,
        state_class: SensorStateClass | None = None,
        icon: str | None = None,
        suggested_display_precision: int | None = None,
    ) -> None:
        super().__init__(coordinator)
        self._bike_id = bike_id
        self._serial = serial
        self._field = field
        self._attr_name = f"{bat_name} {name_suffix}"
        self._attr_unique_id = f"{bike_id}_{prefix}_{key_suffix}"
        self._attr_native_unit_of_measurement = native_unit_of_measurement
        self._attr_device_class = device_class
        self._attr_state_class = state_class
        if icon is not None:
            self._attr_icon = icon
        if suggested_display_precision is not None:
            self._attr_suggested_display_precision = suggested_display_precision
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, bike_id)},
            name=drive_name,
            manufacturer="Bosch",
            model=drive_name,
        )

    def _soh(self) -> dict | None:
        """Resolve the SoH data dict for this battery, or None."""
        if not self._serial:
            return None
        records = self.coordinator.data.get("service_records", {}).get(self._bike_id)
        return battery_soh(records, self._serial)

    @property
    def native_value(self) -> float | None:
        """Return the requested SoH field, or None if no measurement exists."""
        soh = self._soh()
        if soh is None:
            return None
        return soh.get(self._field)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose the remaining SoH fields so they are not lost."""
        if self._field != "soh_pct":
            return {}
        soh = self._soh()
        if soh is None:
            return {}
        return {
            "nominal_wh": soh.get("nominal_wh"),
            "full_charge_cycles": soh.get("full_charge_cycles"),
            "measured_at": soh.get("measured_at"),
        }


class BoschLifetimeStatSensor(CoordinatorEntity[BoschEBikeCoordinator], SensorEntity):
    """Per-assist-mode lifetime distance/energy from the service book.

    Created one per mode (by API position) at setup time from the newest
    customer report. Resolves its value live from
    coordinator.data["service_records"] via profile_extra.assist_mode_stats,
    index-guarded. Uses a literal name (like the reachable-range / SoH
    sensors), so no translation_key is required.
    """

    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(
        self,
        coordinator: BoschEBikeCoordinator,
        bike_id: str,
        drive_name: str,
        index: int,
        mode_name: str,
        *,
        kind: str,
    ) -> None:
        super().__init__(coordinator)
        self._bike_id = bike_id
        self._index = index
        self._mode_name = mode_name
        self._kind = kind  # "distance" or "energy"
        if kind == "distance":
            self._field = "distance_km"
            self._attr_name = f"Lifetime Distance {mode_name}"
            self._attr_unique_id = f"{bike_id}_lifetime_distance_{index}"
            self._attr_device_class = SensorDeviceClass.DISTANCE
            self._attr_native_unit_of_measurement = UnitOfLength.KILOMETERS
            self._attr_icon = "mdi:map-marker-distance"
        else:
            self._field = "energy_wh"
            self._attr_name = f"Lifetime Energy {mode_name}"
            self._attr_unique_id = f"{bike_id}_lifetime_energy_{index}"
            self._attr_device_class = SensorDeviceClass.ENERGY
            self._attr_native_unit_of_measurement = UnitOfEnergy.WATT_HOUR
            self._attr_icon = "mdi:lightning-bolt"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, bike_id)},
            name=drive_name,
            manufacturer="Bosch",
            model=drive_name,
        )

    @property
    def native_value(self) -> float | None:
        """Return the lifetime value for this mode by API position."""
        records = self.coordinator.data.get("service_records", {}).get(self._bike_id)
        stats = assist_mode_stats(records)
        if len(stats) <= self._index:
            return None
        return stats[self._index].get(self._field)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose the assist mode this stat belongs to."""
        return {"assist_mode": self._mode_name}


class BoschLastServiceSensor(CoordinatorEntity[BoschEBikeCoordinator], SensorEntity):
    """Last service date / dealer / odometer from the service book.

    Always created per bike; resolves live from
    coordinator.data["service_records"] via profile_extra.last_service. Shows
    unknown / None when no service record exists. Uses a literal name (like the
    other service-book sensors), so no translation_key is required.
    """

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: BoschEBikeCoordinator,
        bike_id: str,
        drive_name: str,
        *,
        kind: str,
    ) -> None:
        super().__init__(coordinator)
        self._bike_id = bike_id
        self._kind = kind  # "date" | "dealer" | "odometer"
        if kind == "date":
            self._attr_name = "Last Service Date"
            self._attr_unique_id = f"{bike_id}_last_service_date"
            self._attr_device_class = SensorDeviceClass.TIMESTAMP
            self._attr_icon = "mdi:wrench-clock"
        elif kind == "dealer":
            self._attr_name = "Last Service Dealer"
            self._attr_unique_id = f"{bike_id}_last_service_dealer"
            self._attr_entity_category = EntityCategory.DIAGNOSTIC
            self._attr_icon = "mdi:store"
        else:
            self._attr_name = "Last Service Odometer"
            self._attr_unique_id = f"{bike_id}_last_service_odometer"
            self._attr_device_class = SensorDeviceClass.DISTANCE
            self._attr_native_unit_of_measurement = UnitOfLength.KILOMETERS
            self._attr_icon = "mdi:counter"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, bike_id)},
            name=drive_name,
            manufacturer="Bosch",
            model=drive_name,
        )

    def _service(self) -> dict | None:
        records = self.coordinator.data.get("service_records", {}).get(self._bike_id)
        return last_service(records)

    @property
    def native_value(self) -> Any:
        """Return the requested last-service field, or None."""
        service = self._service()
        if service is None:
            return None
        if self._kind == "date":
            return _parse_timestamp(service.get("date"))
        if self._kind == "dealer":
            return service.get("dealer")
        return service.get("odometer_km")


class BoschComponentInventorySensor(CoordinatorEntity[BoschEBikeCoordinator], SensorEntity):
    """Diagnostic component inventory for one bike.

    State: the head-unit product name (kept short). Attributes: the full
    inventory dict (head_unit, remote_control, connect_module, has_abs).
    Reads the live bike from coordinator.data["bikes"] via
    profile_extra.component_inventory. Uses a literal name, so no
    translation_key is required.
    """

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:format-list-bulleted"

    def __init__(
        self,
        coordinator: BoschEBikeCoordinator,
        bike_id: str,
        drive_name: str,
    ) -> None:
        super().__init__(coordinator)
        self._bike_id = bike_id
        self._attr_name = "Components"
        self._attr_unique_id = f"{bike_id}_components"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, bike_id)},
            name=drive_name,
            manufacturer="Bosch",
            model=drive_name,
        )

    def _inventory(self) -> dict | None:
        for bike in self.coordinator.data.get("bikes", []):
            if bike.get("id") == self._bike_id:
                return component_inventory(bike)
        return None

    @property
    def native_value(self) -> str | None:
        """Return the head-unit product name (kept short)."""
        inv = self._inventory()
        if inv is None:
            return None
        return inv.get("head_unit") or "Unknown"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose the full component inventory."""
        return self._inventory() or {}


class BoschMaxAltitudeSensor(CoordinatorEntity[BoschEBikeCoordinator], SensorEntity):
    """Max altitude of this bike's own latest ride.

    Reads coordinator.data["latest_activity_details_by_bike"][bike_id] and
    returns profile_extra.max_altitude(details) in metres. Uses a literal
    name, so no translation_key is required.
    """

    _attr_has_entity_name = True
    _attr_native_unit_of_measurement = UnitOfLength.METERS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:image-filter-hdr"

    def __init__(
        self,
        coordinator: BoschEBikeCoordinator,
        bike_id: str,
        drive_name: str,
    ) -> None:
        super().__init__(coordinator)
        self._bike_id = bike_id
        self._attr_name = "Last Ride Max Altitude"
        self._attr_unique_id = f"{bike_id}_last_ride_max_altitude"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, bike_id)},
            name=drive_name,
            manufacturer="Bosch",
            model=drive_name,
        )

    @property
    def native_value(self) -> float | None:
        """Return the max altitude (m) of this bike's latest ride, or None."""
        details = self.coordinator.data.get("latest_activity_details_by_bike", {}).get(
            self._bike_id
        )
        return max_altitude(details)


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
        """Get coordinate at given index from this bike's own activity details."""
        details = self.coordinator.data.get("latest_activity_details_by_bike", {}).get(
            self._bike_id
        )
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
        """Get consumption data for this bike's latest activity."""
        activities = _activities_for_bike(self.coordinator.data, self._bike_id)
        activity = activities[0] if activities else None
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


class BoschRangeEstimateSensor(CoordinatorEntity[BoschEBikeCoordinator], SensorEntity):
    """Estimated range at full battery, derived from past consumption.

    Clearly labelled as an estimate: name prefix, disclaimer attribute and
    the underlying numbers (wh_per_km, tours_used, window_km) exposed.
    """

    _attr_has_entity_name = True
    _attr_native_unit_of_measurement = UnitOfLength.KILOMETERS
    _attr_device_class = SensorDeviceClass.DISTANCE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:map-marker-distance"
    _attr_translation_key = "estimated_range_full"

    def __init__(
        self,
        coordinator: BoschEBikeCoordinator,
        bike_id: str,
        drive_name: str,
    ) -> None:
        super().__init__(coordinator)
        self._bike_id = bike_id
        self._attr_unique_id = f"{bike_id}_estimated_range_full"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, bike_id)},
            name=drive_name,
            manufacturer="Bosch",
            model=drive_name,
        )

    def _estimate(self) -> dict[str, Any] | None:
        return (self.coordinator.data.get("range_estimate") or {}).get(self._bike_id)

    @property
    def native_value(self) -> int | None:
        est = self._estimate()
        if not est or not est.get("wh_per_km"):
            return None
        capacity = self.coordinator.battery_capacity_wh(self._bike_id)
        if not capacity:
            return None
        return round(capacity / est["wh_per_km"])

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        est = self._estimate()
        if not est:
            return {"disclaimer": RANGE_DISCLAIMER}
        return {
            "disclaimer": RANGE_DISCLAIMER,
            "wh_per_km": est.get("wh_per_km"),
            "tours_used": est.get("tours_used"),
            "window_km": est.get("window_km"),
            "newest_tour_date": est.get("newest_tour_date"),
            "battery_capacity_wh": self.coordinator.battery_capacity_wh(self._bike_id),
        }


class BoschCurrentRangeSensor(BoschRangeEstimateSensor):
    """Estimated remaining range from live SoC × capacity ÷ avg consumption.

    Only created when the live SoC sensor (ESPHome bridge) is linked in the
    options. Listens to that entity so the value updates immediately, not
    just on the 30-minute poll.
    """

    _attr_translation_key = "estimated_range_current"

    def __init__(
        self,
        coordinator: BoschEBikeCoordinator,
        bike_id: str,
        drive_name: str,
        soc_entity_id: str,
    ) -> None:
        super().__init__(coordinator, bike_id, drive_name)
        self._attr_unique_id = f"{bike_id}_estimated_range_current"
        self._soc_entity_id = soc_entity_id

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(
            async_track_state_change_event(
                self.hass, [self._soc_entity_id], self._on_soc_change
            )
        )

    @callback
    def _on_soc_change(self, event: Event) -> None:
        self.async_write_ha_state()

    def _current_soc(self) -> float | None:
        state = self.hass.states.get(self._soc_entity_id)
        if state is None or state.state in ("unknown", "unavailable"):
            return None
        try:
            soc = float(state.state)
        except ValueError:
            return None
        if not math.isfinite(soc):
            return None
        return max(0.0, min(100.0, soc))

    @property
    def native_value(self) -> int | None:
        full = super().native_value
        if full is None:
            return None
        soc = self._current_soc()
        if soc is None:
            return None
        return round(full * soc / 100.0)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        attrs = dict(super().extra_state_attributes or {})
        attrs["soc_source"] = self._soc_entity_id
        attrs["current_soc"] = self._current_soc()
        return attrs


# (window_key, translation_key, unique_id_suffix)
ENERGY_WINDOW_DEFS: tuple[tuple[str, str], ...] = (
    ("7d", "energy_charged_7d"),
    ("30d", "energy_charged_30d"),
    ("365d", "energy_charged_365d"),
)


class BoschEnergyWindowSensor(CoordinatorEntity[BoschEBikeCoordinator], SensorEntity):
    """Charging energy (Wh) this bike consumed in a rolling time window.

    Feeds the dashboard card's optional charging-cost summary (price is
    applied card-side, same pattern as the existing CO2/fuel-cost
    comparison). Reads coordinator.data["energy_window"][bike_id], computed
    once per poll from data already in memory (see energy_cost.py).
    """

    _attr_has_entity_name = True
    _attr_native_unit_of_measurement = UnitOfEnergy.WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_icon = "mdi:lightning-bolt"
    _attr_suggested_display_precision = 0

    def __init__(
        self,
        coordinator: BoschEBikeCoordinator,
        bike_id: str,
        drive_name: str,
        window_key: str,
        translation_key: str,
    ) -> None:
        super().__init__(coordinator)
        self._bike_id = bike_id
        self._window_key = window_key
        self._attr_translation_key = translation_key
        self._attr_unique_id = f"{bike_id}_{translation_key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, bike_id)},
            name=drive_name,
            manufacturer="Bosch",
            model=drive_name,
        )

    @property
    def native_value(self) -> float | None:
        """Wh charged by this bike within the window, or None if no data."""
        window = (self.coordinator.data.get("energy_window") or {}).get(self._bike_id)
        if not window:
            return None
        return window.get(self._window_key)


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
            self._attr_native_unit_of_measurement = "d"
            self._attr_icon = "mdi:calendar-clock"
        else:
            self._attr_translation_key = "service_due_in_km"
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
        bosch_service = bike.get("serviceDue") or {}
        if self._kind == "days":
            from datetime import timezone as _tz
            from homeassistant.util import dt as _dt
            # Override first, Bosch as fallback
            date = self.coordinator.get_service_due_date(self._bike_id) or bosch_service.get("date")
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
        ov_km = self.coordinator.get_service_due_km(self._bike_id)
        if ov_km is not None:
            service_odo = float(ov_km) * 1000.0
        else:
            service_odo = bosch_service.get("odometer")
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
