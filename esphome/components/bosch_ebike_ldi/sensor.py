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

from . import BoschEbikeLdi

CONF_BOSCH_EBIKE_LDI_ID = "bosch_ebike_ldi_id"

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
        cv.GenerateID(CONF_BOSCH_EBIKE_LDI_ID): cv.use_id(BoschEbikeLdi),
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
    parent = await cg.get_variable(config[CONF_BOSCH_EBIKE_LDI_ID])
    for key, setter in _SETTERS.items():
        if key in config:
            sens = await sensor.new_sensor(config[key])
            cg.add(getattr(parent, setter)(sens))
