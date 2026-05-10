"""Bosch eBike Live Data Interface (LDI) BLE Bridge - ESPHome External Component."""
from esphome import core
import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.const import CONF_ID

CODEOWNERS = ["@Xunil99"]
DEPENDENCIES = ["esp32"]
AUTO_LOAD = ["binary_sensor", "sensor"]
MULTI_CONF = False

bosch_ebike_ldi_ns = cg.esphome_ns.namespace("bosch_ebike_ldi")
BoschEbikeLdi = bosch_ebike_ldi_ns.class_("BoschEbikeLdi", cg.Component)

CONF_DEVICE_NAME = "device_name"

CONFIG_SCHEMA = cv.Schema(
    {
        cv.GenerateID(): cv.declare_id(BoschEbikeLdi),
        cv.Optional(CONF_DEVICE_NAME, default="HA eBike Bridge"): cv.string,
    }
).extend(cv.COMPONENT_SCHEMA)


async def to_code(config):
    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)
    cg.add(var.set_device_name(config[CONF_DEVICE_NAME]))

    # ESP-IDF only - NimBLE is the host stack we depend on
    cg.add_build_flag("-DBOSCH_EBIKE_LDI_NIMBLE")
