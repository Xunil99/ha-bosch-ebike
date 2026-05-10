"""Binary sensors for Bosch eBike LDI bridge (v0.2)."""
import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.components import binary_sensor
from esphome.const import (
    DEVICE_CLASS_CONNECTIVITY,
    DEVICE_CLASS_LIGHT,
    DEVICE_CLASS_LOCK,
    DEVICE_CLASS_MOTION,
    DEVICE_CLASS_PLUG,
    DEVICE_CLASS_PROBLEM,
)

from . import BoschEbikeLdi

CONF_BOSCH_EBIKE_LDI_ID = "bosch_ebike_ldi_id"

CONF_CONNECTED = "connected"
CONF_LIGHT = "light"
CONF_SYSTEM_LOCKED = "system_locked"
CONF_CHARGER_CONNECTED = "charger_connected"
CONF_LIGHT_RESERVE = "light_reserve"
CONF_DIAGNOSIS_ACTIVE = "diagnosis_active"
CONF_IN_MOTION = "in_motion"

CONFIG_SCHEMA = cv.Schema(
    {
        cv.GenerateID(CONF_BOSCH_EBIKE_LDI_ID): cv.use_id(BoschEbikeLdi),
        cv.Optional(CONF_CONNECTED): binary_sensor.binary_sensor_schema(
            device_class=DEVICE_CLASS_CONNECTIVITY,
        ),
        cv.Optional(CONF_LIGHT): binary_sensor.binary_sensor_schema(
            device_class=DEVICE_CLASS_LIGHT,
        ),
        cv.Optional(CONF_SYSTEM_LOCKED): binary_sensor.binary_sensor_schema(
            device_class=DEVICE_CLASS_LOCK,
        ),
        cv.Optional(CONF_CHARGER_CONNECTED): binary_sensor.binary_sensor_schema(
            device_class=DEVICE_CLASS_PLUG,
        ),
        cv.Optional(CONF_LIGHT_RESERVE): binary_sensor.binary_sensor_schema(
            device_class=DEVICE_CLASS_PROBLEM,
            icon="mdi:car-light-dimmed",
        ),
        cv.Optional(CONF_DIAGNOSIS_ACTIVE): binary_sensor.binary_sensor_schema(
            icon="mdi:wrench",
        ),
        cv.Optional(CONF_IN_MOTION): binary_sensor.binary_sensor_schema(
            device_class=DEVICE_CLASS_MOTION,
        ),
    }
)

_SETTERS = {
    CONF_CONNECTED: "set_connected_sensor",
    CONF_LIGHT: "set_light_sensor",
    CONF_SYSTEM_LOCKED: "set_system_locked_sensor",
    CONF_CHARGER_CONNECTED: "set_charger_connected_sensor",
    CONF_LIGHT_RESERVE: "set_light_reserve_sensor",
    CONF_DIAGNOSIS_ACTIVE: "set_diagnosis_active_sensor",
    CONF_IN_MOTION: "set_bike_in_motion_sensor",
}


async def to_code(config):
    parent = await cg.get_variable(config[CONF_BOSCH_EBIKE_LDI_ID])
    for key, setter in _SETTERS.items():
        if key in config:
            sens = await binary_sensor.new_binary_sensor(config[key])
            cg.add(getattr(parent, setter)(sens))
