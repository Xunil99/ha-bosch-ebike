"""Bosch eBike Live Data Interface (LDI) BLE Bridge - ESPHome External Component."""
from esphome import core
import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.const import CONF_ID

try:
    # ESPHome >= 2026.9.0 excludes the ESP-IDF "bt" component from the build
    # by default (compile-time optimization) unless something asks for it
    # back via this call - without it, esp_bt.h is no longer on the include
    # path at all and the build fails with "esp_bt.h: No such file or
    # directory" (issue #81), even though every CONFIG_BT_* sdkconfig option
    # set elsewhere is still correct; sdkconfig options and which component
    # directories get compiled are now two separate mechanisms. Older
    # ESPHome versions never excluded "bt" in the first place, so this
    # import fails there and the call is simply skipped.
    from esphome.components.esp32 import request_bluetooth
except ImportError:
    request_bluetooth = None

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

    # Issue #81: keep the ESP-IDF "bt" component in the build on ESPHome
    # versions that exclude it by default. No-op on older ESPHome.
    if request_bluetooth is not None:
        request_bluetooth()
