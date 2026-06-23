"""Numeric sensors for Bosch eBike LDI bridge (v0.2)."""
import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.components import sensor
from esphome.const import (
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_DISTANCE,
    DEVICE_CLASS_ILLUMINANCE,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_SPEED,
    STATE_CLASS_MEASUREMENT,
    STATE_CLASS_TOTAL_INCREASING,
    UNIT_KILOMETER,
    UNIT_LUX,
    UNIT_PERCENT,
    UNIT_WATT,
)

from . import BoschEbikeLdiDual

CONF_BOSCH_EBIKE_LDI_DUAL_ID = "bosch_ebike_ldi_dual_id"

# Which bike this platform block configures: 1 -> slot 0 ("eBike 1"),
# 2 -> slot 1 ("eBike 2"). Two `- platform:` blocks (bike: 1 / bike: 2),
# each with its own distinct `name:`, yield two distinct entity sets.
CONF_BIKE = "bike"

CONF_SPEED = "speed"
CONF_CADENCE = "cadence"
CONF_RIDER_POWER = "rider_power"
CONF_AMBIENT_BRIGHTNESS = "ambient_brightness"
CONF_BATTERY_SOC = "battery_soc"
CONF_ODOMETER = "odometer"

UNIT_KMH = "km/h"
UNIT_RPM = "rpm"

CONFIG_SCHEMA = cv.Schema(
    {
        cv.GenerateID(CONF_BOSCH_EBIKE_LDI_DUAL_ID): cv.use_id(BoschEbikeLdiDual),
        cv.Required(CONF_BIKE): cv.int_range(min=1, max=2),
        cv.Optional(CONF_SPEED): sensor.sensor_schema(
            unit_of_measurement=UNIT_KMH,
            accuracy_decimals=2,
            device_class=DEVICE_CLASS_SPEED,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        cv.Optional(CONF_CADENCE): sensor.sensor_schema(
            unit_of_measurement=UNIT_RPM,
            accuracy_decimals=0,
            state_class=STATE_CLASS_MEASUREMENT,
            icon="mdi:rotate-right",
        ),
        cv.Optional(CONF_RIDER_POWER): sensor.sensor_schema(
            unit_of_measurement=UNIT_WATT,
            accuracy_decimals=0,
            device_class=DEVICE_CLASS_POWER,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        cv.Optional(CONF_AMBIENT_BRIGHTNESS): sensor.sensor_schema(
            unit_of_measurement=UNIT_LUX,
            accuracy_decimals=1,
            device_class=DEVICE_CLASS_ILLUMINANCE,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        cv.Optional(CONF_BATTERY_SOC): sensor.sensor_schema(
            unit_of_measurement=UNIT_PERCENT,
            accuracy_decimals=0,
            device_class=DEVICE_CLASS_BATTERY,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        cv.Optional(CONF_ODOMETER): sensor.sensor_schema(
            unit_of_measurement=UNIT_KILOMETER,
            accuracy_decimals=1,
            device_class=DEVICE_CLASS_DISTANCE,
            state_class=STATE_CLASS_TOTAL_INCREASING,
            icon="mdi:counter",
        ),
    }
)

_SETTERS = {
    CONF_SPEED: "set_speed_sensor",
    CONF_CADENCE: "set_cadence_sensor",
    CONF_RIDER_POWER: "set_rider_power_sensor",
    CONF_AMBIENT_BRIGHTNESS: "set_ambient_brightness_sensor",
    CONF_BATTERY_SOC: "set_battery_soc_sensor",
    CONF_ODOMETER: "set_odometer_sensor",
}


async def to_code(config):
    parent = await cg.get_variable(config[CONF_BOSCH_EBIKE_LDI_DUAL_ID])
    slot = config[CONF_BIKE] - 1
    for key, setter in _SETTERS.items():
        if key in config:
            sens = await sensor.new_sensor(config[key])
            cg.add(getattr(parent, setter)(slot, sens))
