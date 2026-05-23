# BLE Sensor Broadcast Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a new ESPHome external component `ebike_ble_broadcast` that runs alongside `bosch_ebike_ldi` and exposes the eBike's battery SoC and cadence as standard Bluetooth-SIG GATT services (Battery Service 0x180F, Cycling Speed and Cadence 0x1816), so third-party bike computers like Coros Dura can pair with the bridge and read live data.

**Architecture:** New ESPHome external component sharing the NimBLE host stack with the existing `bosch_ebike_ldi` component (central role). The new component takes peripheral role: registers two GATT services, advertises both UUIDs, and pushes notifications when subscribed ESPHome sensors update. `CONFIG_BT_NIMBLE_MAX_CONNECTIONS` goes from 1 to 2 so central (eBike) and peripheral (Coros) links coexist.

**Tech Stack:** ESPHome 2026.5.0, ESP-IDF framework, NimBLE host stack (Apache NimBLE bundled in ESP-IDF), ESP32-S3-WROOM-1 silicon. Reference design: `docs/plans/2026-05-23-ble-broadcast-design.md`.

**Notes on testing:** Unlike standard application code, BLE peripheral behaviour cannot be unit-tested with `pytest`. "Tests" in this plan are: (a) ESPHome `compile` succeeds with no errors, (b) boot log shows expected NimBLE init messages, (c) verification with a generic BLE scanner app (nRF Connect on phone) before going for the real Coros pairing test. Adapt the TDD discipline: write the smallest possible change that produces a visible boot-log effect or BLE-scanner observation before proceeding.

---

## Phase 1: Component scaffolding (compile-clean empty component)

### Task 1: Create component directory and Python schema

**Files:**
- Create: `esphome/components/ebike_ble_broadcast/__init__.py`

**Step 1: Write the schema file**

```python
"""eBike BLE Broadcast — re-broadcasts eBike data as standard BLE sensor."""
import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.const import CONF_ID
from esphome.components.sensor import Sensor

CODEOWNERS = ["@Xunil99"]
DEPENDENCIES = ["esp32"]
MULTI_CONF = False

ebike_ble_broadcast_ns = cg.esphome_ns.namespace("ebike_ble_broadcast")
EbikeBleBroadcast = ebike_ble_broadcast_ns.class_("EbikeBleBroadcast", cg.Component)

CONF_ADVERTISED_NAME = "advertised_name"
CONF_BATTERY_SOC_ID = "battery_soc_id"
CONF_CADENCE_ID = "cadence_id"

CONFIG_SCHEMA = cv.Schema(
    {
        cv.GenerateID(): cv.declare_id(EbikeBleBroadcast),
        cv.Optional(CONF_ADVERTISED_NAME, default="Bosch eBike Bridge"): cv.string,
        cv.Optional(CONF_BATTERY_SOC_ID): cv.use_id(Sensor),
        cv.Optional(CONF_CADENCE_ID): cv.use_id(Sensor),
    }
).extend(cv.COMPONENT_SCHEMA)


async def to_code(config):
    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)
    cg.add(var.set_advertised_name(config[CONF_ADVERTISED_NAME]))
    if soc_id := config.get(CONF_BATTERY_SOC_ID):
        soc = await cg.get_variable(soc_id)
        cg.add(var.set_battery_soc_sensor(soc))
    if cad_id := config.get(CONF_CADENCE_ID):
        cad = await cg.get_variable(cad_id)
        cg.add(var.set_cadence_sensor(cad))
    cg.add_build_flag("-DEBIKE_BLE_BROADCAST_NIMBLE")
```

**Step 2: Verify with ESPHome config-validation**

Add a minimal block to a test YAML (e.g. `esphome/test-ble-broadcast.yaml`, see Task 4) and run ESPHome's config validator. Header and Python class don't exist yet — expected to fail in C++ codegen, not in Python schema validation.

**Step 3: Commit**

```bash
cd /tmp/ha-bosch-ebike
git add esphome/components/ebike_ble_broadcast/__init__.py
git commit -m "feat(ebike_ble_broadcast): Python schema for new component

Empty scaffold - Python config validator passes, C++ side missing.
Three options exposed: advertised_name (default 'Bosch eBike Bridge'),
battery_soc_id (optional, sensor reference), cadence_id (optional,
sensor reference)."
```

---

### Task 2: Create C++ header (empty class with setters)

**Files:**
- Create: `esphome/components/ebike_ble_broadcast/ebike_ble_broadcast.h`

**Step 1: Write the header**

```cpp
#pragma once

#include "esphome/core/component.h"
#include "esphome/components/sensor/sensor.h"
#include <string>
#include <cstdint>

namespace esphome {
namespace ebike_ble_broadcast {

class EbikeBleBroadcast : public Component {
 public:
  void setup() override;
  void loop() override;
  void dump_config() override;
  float get_setup_priority() const override;

  // Setters called from generated to_code()
  void set_advertised_name(const std::string &name) { advertised_name_ = name; }
  void set_battery_soc_sensor(sensor::Sensor *s) { battery_soc_sensor_ = s; }
  void set_cadence_sensor(sensor::Sensor *s) { cadence_sensor_ = s; }

 protected:
  std::string advertised_name_{"Bosch eBike Bridge"};
  sensor::Sensor *battery_soc_sensor_{nullptr};
  sensor::Sensor *cadence_sensor_{nullptr};

  bool gatt_registered_{false};
  bool advertising_{false};
  uint16_t conn_handle_{0xFFFF};

  // Cadence accumulator state - Task 13
  float cum_crank_revs_{0.0f};
  uint16_t last_crank_event_time_{0};   // 1/1024 s units, wraps every ~64 s
};

}  // namespace ebike_ble_broadcast
}  // namespace esphome
```

**Step 2: No test yet — header is a declaration only.**

**Step 3: Commit**

```bash
git add esphome/components/ebike_ble_broadcast/ebike_ble_broadcast.h
git commit -m "feat(ebike_ble_broadcast): C++ header with empty class skeleton"
```

---

### Task 3: Create C++ implementation file (empty methods)

**Files:**
- Create: `esphome/components/ebike_ble_broadcast/ebike_ble_broadcast.cpp`

**Step 1: Write the empty implementation**

```cpp
#include "ebike_ble_broadcast.h"
#include "esphome/core/log.h"

namespace esphome {
namespace ebike_ble_broadcast {

static const char *const TAG = "ebike_ble_broadcast";

void EbikeBleBroadcast::setup() {
  ESP_LOGI(TAG, "Setup: advertised_name='%s', soc_sensor=%p, cadence_sensor=%p",
           advertised_name_.c_str(),
           static_cast<void *>(battery_soc_sensor_),
           static_cast<void *>(cadence_sensor_));
}

void EbikeBleBroadcast::loop() {}

void EbikeBleBroadcast::dump_config() {
  ESP_LOGCONFIG(TAG, "eBike BLE Broadcast:");
  ESP_LOGCONFIG(TAG, "  Advertised name: %s", advertised_name_.c_str());
  ESP_LOGCONFIG(TAG, "  Battery SoC: %s", battery_soc_sensor_ ? "configured" : "none");
  ESP_LOGCONFIG(TAG, "  Cadence:     %s", cadence_sensor_ ? "configured" : "none");
}

float EbikeBleBroadcast::get_setup_priority() const {
  // Run AFTER bosch_ebike_ldi (which has BLUETOOTH=300) so NimBLE
  // host is up. Same priority as bosch_ebike_ldi but later in
  // registration order, which ESPHome respects on ties.
  return setup_priority::BLUETOOTH - 1.0f;
}

}  // namespace ebike_ble_broadcast
}  // namespace esphome
```

**Step 2: Build via test YAML (Task 4) — expected pass: component compiles, logs init message at boot.**

**Step 3: Commit**

```bash
git add esphome/components/ebike_ble_broadcast/ebike_ble_broadcast.cpp
git commit -m "feat(ebike_ble_broadcast): empty setup/loop/dump_config that logs config

Component now compiles and logs its presence at boot, but does
nothing functional yet. Verifies the scaffold integrates cleanly
with ESPHome's component lifecycle."
```

---

### Task 4: Add to test YAML and verify compile

**Files:**
- Create: `esphome/test-ble-broadcast.yaml`
- Reference: existing `esphome/factory.yaml` for the bridge setup

**Step 1: Create the minimal test YAML**

```yaml
# Test config for ebike_ble_broadcast - extends factory.yaml setup
# with the new component. Flash to a JC4827W543 or any ESP32 with
# the same partition/sdkconfig profile.

esphome:
  name: ble-broadcast-test
  friendly_name: "BLE Broadcast Test"
  min_version: 2025.11.0

esp32:
  board: esp32-s3-devkitc-1
  variant: esp32s3
  flash_size: 4MB
  framework:
    type: esp-idf
    sdkconfig_options:
      CONFIG_ESPTOOLPY_FLASHSIZE_4MB: y
      CONFIG_BT_ENABLED: y
      CONFIG_BT_NIMBLE_ENABLED: y
      CONFIG_BT_BLUEDROID_ENABLED: n
      CONFIG_BT_CONTROLLER_ENABLED: y
      CONFIG_BTDM_CTRL_MODE_BLE_ONLY: y
      CONFIG_BT_NIMBLE_MAX_CONNECTIONS: "2"    # up from 1 - dual role
      CONFIG_BT_NIMBLE_ROLE_PERIPHERAL: y
      CONFIG_BT_NIMBLE_ROLE_BROADCASTER: y
      CONFIG_BT_NIMBLE_ROLE_CENTRAL: y
      CONFIG_BT_NIMBLE_ROLE_OBSERVER: y
      CONFIG_BT_NIMBLE_SM_LEGACY: n
      CONFIG_BT_NIMBLE_SM_SC: y
      CONFIG_BT_NIMBLE_NVS_PERSIST: y
      CONFIG_BT_NIMBLE_ATT_PREFERRED_MTU: "247"

logger:
  hardware_uart: USB_SERIAL_JTAG
  level: DEBUG
  logs:
    ebike_ble_broadcast: DEBUG

wifi:
  ssid: !secret wifi_ssid
  password: !secret wifi_password

api:
ota:
  - platform: esphome

external_components:
  - source:
      type: local
      path: components
    components: [ebike_ble_broadcast]

# Fake sensors so the component has something to talk about during
# bench testing without a real eBike connected.
sensor:
  - platform: template
    name: "Fake Battery SoC"
    id: fake_soc
    lambda: 'return 67.0f;'
    update_interval: 5s
  - platform: template
    name: "Fake Cadence"
    id: fake_cadence
    lambda: 'return 80.0f;'
    update_interval: 1s

ebike_ble_broadcast:
  id: ble_broadcast
  advertised_name: "Bridge BLE Test"
  battery_soc_id: fake_soc
  cadence_id: fake_cadence
```

**Step 2: Compile**

Run ESPHome compile via dashboard or CLI:

```bash
esphome compile esphome/test-ble-broadcast.yaml
```

Expected: clean compile with no errors. Look for `ebike_ble_broadcast` namespace symbols in the link map (`.pioenvs/ble-broadcast-test/firmware.map`).

**Step 3: Flash and check boot log**

Expected log lines:

```
[I][ebike_ble_broadcast:XX]: Setup: advertised_name='Bridge BLE Test', ...
[C][ebike_ble_broadcast:XX]: eBike BLE Broadcast:
[C][ebike_ble_broadcast:XX]:   Advertised name: Bridge BLE Test
[C][ebike_ble_broadcast:XX]:   Battery SoC: configured
[C][ebike_ble_broadcast:XX]:   Cadence:     configured
```

**Step 4: Commit**

```bash
git add esphome/test-ble-broadcast.yaml
git commit -m "test(ebike_ble_broadcast): bench-test YAML with fake sensors

Allows verifying the component compiles and boots without a real
Bosch eBike connected. Fake template sensors provide stable values
for downstream tasks. Local external_components source so any
fork can iterate without pushing to GitHub first."
```

---

## Phase 2: NimBLE GATT server setup

### Task 5: Define GATT service tables

**Files:**
- Modify: `esphome/components/ebike_ble_broadcast/ebike_ble_broadcast.cpp` (top of file)

**Step 1: Add NimBLE includes and GATT service definitions**

After `#include "esphome/core/log.h"`, add:

```cpp
#ifdef EBIKE_BLE_BROADCAST_NIMBLE
#include "host/ble_hs.h"
#include "host/ble_uuid.h"
#include "host/ble_gap.h"
#include "host/ble_gatt.h"
#include "services/gap/ble_svc_gap.h"
#include "services/gatt/ble_svc_gatt.h"
#endif
```

Inside the `esphome::ebike_ble_broadcast` namespace, define service UUIDs and characteristic handles as static members:

```cpp
// Standard Bluetooth-SIG service / characteristic UUIDs (little-endian
// 16-bit, written here in normal byte order for readability).
static const ble_uuid16_t BATTERY_SERVICE_UUID = BLE_UUID16_INIT(0x180F);
static const ble_uuid16_t BATTERY_LEVEL_UUID   = BLE_UUID16_INIT(0x2A19);
static const ble_uuid16_t CSC_SERVICE_UUID     = BLE_UUID16_INIT(0x1816);
static const ble_uuid16_t CSC_MEASUREMENT_UUID = BLE_UUID16_INIT(0x2A5B);

// Forward declarations - filled in Task 6.
static int gatt_battery_level_access(uint16_t conn_handle, uint16_t attr_handle,
                                     struct ble_gatt_access_ctxt *ctxt, void *arg);
static int gatt_csc_measurement_access(uint16_t conn_handle, uint16_t attr_handle,
                                       struct ble_gatt_access_ctxt *ctxt, void *arg);

// Handles populated by NimBLE during service registration.
static uint16_t battery_level_handle = 0;
static uint16_t csc_measurement_handle = 0;

static const struct ble_gatt_svc_def gatt_services[] = {
    {
        .type = BLE_GATT_SVC_TYPE_PRIMARY,
        .uuid = &BATTERY_SERVICE_UUID.u,
        .characteristics = (struct ble_gatt_chr_def[]){
            {
                .uuid = &BATTERY_LEVEL_UUID.u,
                .access_cb = gatt_battery_level_access,
                .flags = BLE_GATT_CHR_F_READ | BLE_GATT_CHR_F_NOTIFY,
                .val_handle = &battery_level_handle,
            },
            { 0 }  // terminator
        },
    },
    {
        .type = BLE_GATT_SVC_TYPE_PRIMARY,
        .uuid = &CSC_SERVICE_UUID.u,
        .characteristics = (struct ble_gatt_chr_def[]){
            {
                .uuid = &CSC_MEASUREMENT_UUID.u,
                .access_cb = gatt_csc_measurement_access,
                .flags = BLE_GATT_CHR_F_NOTIFY,
                .val_handle = &csc_measurement_handle,
            },
            { 0 }
        },
    },
    { 0 }  // terminator
};
```

**Step 2: Add stub access callbacks (return zero data for now)**

```cpp
static int gatt_battery_level_access(uint16_t conn_handle, uint16_t attr_handle,
                                     struct ble_gatt_access_ctxt *ctxt, void *arg) {
  if (ctxt->op == BLE_GATT_ACCESS_OP_READ_CHR) {
    uint8_t level = 0;  // filled in Task 11
    return os_mbuf_append(ctxt->om, &level, sizeof(level)) == 0
               ? 0
               : BLE_ATT_ERR_INSUFFICIENT_RES;
  }
  return BLE_ATT_ERR_UNLIKELY;
}

static int gatt_csc_measurement_access(uint16_t conn_handle, uint16_t attr_handle,
                                       struct ble_gatt_access_ctxt *ctxt, void *arg) {
  // CSC Measurement is notify-only; reads not expected.
  return BLE_ATT_ERR_READ_NOT_PERMITTED;
}
```

**Step 3: Verify compile**

Same compile command as Task 4. Expected: clean compile, no link errors. The unused service table will produce no behaviour at runtime yet (it's not registered).

**Step 4: Commit**

```bash
git add esphome/components/ebike_ble_broadcast/ebike_ble_broadcast.cpp
git commit -m "feat(ebike_ble_broadcast): GATT service table + stub access callbacks

Defines Battery Service (0x180F) and CSC Service (0x1816) with their
characteristics in NimBLE's gatt_services[] format. Access callbacks
return zero/empty data; real values wired in later tasks. Not yet
registered with NimBLE host - only compile-clean for now."
```

---

### Task 6: Register GATT services with NimBLE during setup()

**Files:**
- Modify: `esphome/components/ebike_ble_broadcast/ebike_ble_broadcast.cpp` (the `setup()` method)

**Step 1: Add registration logic**

Replace the body of `setup()`:

```cpp
void EbikeBleBroadcast::setup() {
  ESP_LOGI(TAG, "Setup: advertised_name='%s', soc_sensor=%p, cadence_sensor=%p",
           advertised_name_.c_str(),
           static_cast<void *>(battery_soc_sensor_),
           static_cast<void *>(cadence_sensor_));

#ifdef EBIKE_BLE_BROADCAST_NIMBLE
  // bosch_ebike_ldi (if present) brings up the NimBLE host before our
  // setup runs (higher priority). If bosch_ebike_ldi is not loaded, the
  // component still has to ensure NimBLE is initialised - we rely on
  // ble_hs_is_enabled() and just defer registration to loop() if false.
  if (!ble_hs_is_enabled()) {
    ESP_LOGW(TAG, "NimBLE host not up yet - will retry in loop()");
    return;
  }

  int rc = ble_gatts_count_cfg(gatt_services);
  if (rc != 0) {
    ESP_LOGE(TAG, "ble_gatts_count_cfg failed: %d", rc);
    this->mark_failed();
    return;
  }
  rc = ble_gatts_add_svcs(gatt_services);
  if (rc != 0) {
    ESP_LOGE(TAG, "ble_gatts_add_svcs failed: %d", rc);
    this->mark_failed();
    return;
  }
  gatt_registered_ = true;
  ESP_LOGI(TAG, "GATT services registered (Battery + CSC)");
#endif
}
```

**Step 2: Retry-in-loop fallback**

Modify `loop()`:

```cpp
void EbikeBleBroadcast::loop() {
#ifdef EBIKE_BLE_BROADCAST_NIMBLE
  if (!gatt_registered_ && ble_hs_is_enabled()) {
    // Late init - NimBLE came up after our setup() ran
    ble_gatts_count_cfg(gatt_services);
    if (ble_gatts_add_svcs(gatt_services) == 0) {
      gatt_registered_ = true;
      ESP_LOGI(TAG, "GATT services registered (late init)");
    }
  }
#endif
}
```

**Step 3: Compile + flash + log check**

After flash, expected boot log:

```
[I][ebike_ble_broadcast:XX]: GATT services registered (Battery + CSC)
```

If the message says "late init" or doesn't appear, NimBLE host startup ordering may need adjustment. Test with `setup_priority` tweaks if needed.

**Step 4: Commit**

```bash
git add esphome/components/ebike_ble_broadcast/ebike_ble_broadcast.cpp
git commit -m "feat(ebike_ble_broadcast): register GATT services with NimBLE host

Calls ble_gatts_count_cfg + ble_gatts_add_svcs during setup() (or
loop() as a fallback if NimBLE host comes up later than expected).
Logs success / error code. Services are now visible to any scan if
advertising were running - advertising in next task."
```

---

### Task 7: Implement advertising with service UUIDs

**Files:**
- Modify: `esphome/components/ebike_ble_broadcast/ebike_ble_broadcast.cpp`

**Step 1: Add advertising helper method**

In the header, declare a private method:

```cpp
// Add to the protected: section of EbikeBleBroadcast
void start_advertising_();
```

In the .cpp file, define it:

```cpp
void EbikeBleBroadcast::start_advertising_() {
#ifdef EBIKE_BLE_BROADCAST_NIMBLE
  if (advertising_) return;

  // Build advertising data: flags + complete name + service UUIDs
  struct ble_hs_adv_fields fields{};
  fields.flags = BLE_HS_ADV_F_DISC_GEN | BLE_HS_ADV_F_BREDR_UNSUP;
  fields.name = (uint8_t *)advertised_name_.c_str();
  fields.name_len = advertised_name_.size();
  fields.name_is_complete = 1;

  static ble_uuid16_t adv_uuids[] = {BATTERY_SERVICE_UUID, CSC_SERVICE_UUID};
  fields.uuids16 = adv_uuids;
  fields.num_uuids16 = 2;
  fields.uuids16_is_complete = 1;

  int rc = ble_gap_adv_set_fields(&fields);
  if (rc != 0) {
    ESP_LOGE(TAG, "ble_gap_adv_set_fields failed: %d", rc);
    return;
  }

  struct ble_gap_adv_params adv_params{};
  adv_params.conn_mode = BLE_GAP_CONN_MODE_UND;
  adv_params.disc_mode = BLE_GAP_DISC_MODE_GEN;

  rc = ble_gap_adv_start(BLE_OWN_ADDR_PUBLIC, nullptr, BLE_HS_FOREVER,
                         &adv_params, &EbikeBleBroadcast::gap_event_, this);
  if (rc != 0) {
    ESP_LOGE(TAG, "ble_gap_adv_start failed: %d", rc);
    return;
  }

  advertising_ = true;
  ESP_LOGI(TAG, "Advertising started as '%s'", advertised_name_.c_str());
#endif
}
```

**Step 2: Add GAP event handler (static method)**

In the header, declare:

```cpp
static int gap_event_(struct ble_gap_event *event, void *arg);
```

In .cpp:

```cpp
int EbikeBleBroadcast::gap_event_(struct ble_gap_event *event, void *arg) {
  auto *self = static_cast<EbikeBleBroadcast *>(arg);
  switch (event->type) {
    case BLE_GAP_EVENT_CONNECT:
      if (event->connect.status == 0) {
        self->conn_handle_ = event->connect.conn_handle;
        ESP_LOGI(TAG, "Client connected (handle %u)", self->conn_handle_);
        self->advertising_ = false;
      } else {
        ESP_LOGW(TAG, "Connect failed (status %d) - re-advertising", event->connect.status);
        self->start_advertising_();
      }
      return 0;
    case BLE_GAP_EVENT_DISCONNECT:
      ESP_LOGI(TAG, "Client disconnected (reason %d) - re-advertising",
               event->disconnect.reason);
      self->conn_handle_ = 0xFFFF;
      self->advertising_ = false;
      self->start_advertising_();
      return 0;
    case BLE_GAP_EVENT_SUBSCRIBE:
      ESP_LOGI(TAG, "Subscribe event: handle=%u cur_notify=%d cur_indicate=%d",
               event->subscribe.attr_handle,
               event->subscribe.cur_notify,
               event->subscribe.cur_indicate);
      return 0;
  }
  return 0;
}
```

**Step 3: Wire advertising start into setup() after GATT registration**

Modify the end of `setup()` (after the `gatt_registered_ = true;` line):

```cpp
  start_advertising_();
```

And the late-init branch in `loop()`:

```cpp
  if (!gatt_registered_ && ble_hs_is_enabled()) {
    ble_gatts_count_cfg(gatt_services);
    if (ble_gatts_add_svcs(gatt_services) == 0) {
      gatt_registered_ = true;
      ESP_LOGI(TAG, "GATT services registered (late init)");
      start_advertising_();
    }
  }
```

**Step 4: Flash and verify with nRF Connect app**

Install nRF Connect (Nordic) on phone. Scan. Expected: device with name `"Bridge BLE Test"` (or the configured advertised_name) appears in scan list. Tap it → Connect → expand services. Battery Service and Cycling Speed and Cadence both visible.

Boot log expected:

```
[I][ebike_ble_broadcast:XX]: Advertising started as 'Bridge BLE Test'
```

When you tap "Connect" in the app:

```
[I][ebike_ble_broadcast:XX]: Client connected (handle 0)
```

When you disconnect:

```
[I][ebike_ble_broadcast:XX]: Client disconnected (reason ...) - re-advertising
```

**Step 5: Commit**

```bash
git add esphome/components/ebike_ble_broadcast/ebike_ble_broadcast.h
git add esphome/components/ebike_ble_broadcast/ebike_ble_broadcast.cpp
git commit -m "feat(ebike_ble_broadcast): start NimBLE advertising with services

Advertises both service UUIDs (Battery 0x180F, CSC 0x1816) plus the
configured advertised_name. GAP event handler resumes advertising
after each disconnect so the device is always discoverable when
idle. Verified discoverable from nRF Connect."
```

---

## Phase 3: Wire ESPHome sensors to GATT notifications

### Task 8: Subscribe to battery SoC sensor updates

**Files:**
- Modify: `esphome/components/ebike_ble_broadcast/ebike_ble_broadcast.cpp` (setup method)

**Step 1: Add subscription at end of setup()**

After `start_advertising_();` in setup():

```cpp
  if (battery_soc_sensor_) {
    battery_soc_sensor_->add_on_state_callback([this](float state) {
      this->on_battery_soc_(state);
    });
  }
  if (cadence_sensor_) {
    cadence_sensor_->add_on_state_callback([this](float state) {
      this->on_cadence_(state);
    });
  }
```

**Step 2: Declare and define the on_*_  handlers**

In header (protected):

```cpp
void on_battery_soc_(float soc);
void on_cadence_(float rpm);
uint8_t latest_soc_{0};        // 0-100, cached for GATT read
```

In .cpp:

```cpp
void EbikeBleBroadcast::on_battery_soc_(float soc) {
  if (std::isnan(soc)) return;
  // Clamp + cast to uint8
  if (soc < 0.0f) soc = 0.0f;
  if (soc > 100.0f) soc = 100.0f;
  latest_soc_ = static_cast<uint8_t>(soc + 0.5f);
  ESP_LOGD(TAG, "Battery SoC update: %u %%", latest_soc_);

#ifdef EBIKE_BLE_BROADCAST_NIMBLE
  if (conn_handle_ != 0xFFFF && battery_level_handle != 0) {
    struct os_mbuf *om = ble_hs_mbuf_from_flat(&latest_soc_, sizeof(latest_soc_));
    if (om != nullptr) {
      ble_gatts_notify_custom(conn_handle_, battery_level_handle, om);
    }
  }
#endif
}

void EbikeBleBroadcast::on_cadence_(float rpm) {
  // Implementation in Task 13
  (void) rpm;
}
```

**Step 3: Wire latest_soc_ into the read callback**

Update the access callback for Battery Level (still in same .cpp file, at the top where the static callback lives):

Make `latest_soc_` accessible. Easiest: store a static pointer to the singleton instance after construction. In `setup()`, add at the top:

```cpp
static EbikeBleBroadcast *g_instance = nullptr;
// In setup(), first line:
g_instance = this;
```

Then update the access callback:

```cpp
static int gatt_battery_level_access(uint16_t conn_handle, uint16_t attr_handle,
                                     struct ble_gatt_access_ctxt *ctxt, void *arg) {
  if (ctxt->op == BLE_GATT_ACCESS_OP_READ_CHR) {
    uint8_t level = g_instance ? g_instance->latest_soc_ : 0;
    return os_mbuf_append(ctxt->om, &level, sizeof(level)) == 0
               ? 0
               : BLE_ATT_ERR_INSUFFICIENT_RES;
  }
  return BLE_ATT_ERR_UNLIKELY;
}
```

Note: `latest_soc_` must be public or via friend to access from the static cb. Either move it to `public:` or add `friend int gatt_battery_level_access(...);` to the class.

**Step 4: Flash + test**

In nRF Connect: connect to the device, find Battery Service → Battery Level. Tap "Read". Should return `0x43` (= 67 decimal, the fake SoC value).

Then enable notifications (Notify icon next to Battery Level). After ~5 s the value should appear unchanged at 67 — but the log on ESPHome side should show:

```
[D][ebike_ble_broadcast:XX]: Battery SoC update: 67 %
```

**Step 5: Commit**

```bash
git add esphome/components/ebike_ble_broadcast/
git commit -m "feat(ebike_ble_broadcast): battery SoC GATT read + notify

Subscribes to the configured battery_soc_id sensor's state updates,
caches the latest value as uint8 0-100, exposes via Battery Level
characteristic (read), and pushes a notification to any subscribed
client whenever a new value arrives."
```

---

### Task 9: Implement cadence accumulator and CSC notification

**Files:**
- Modify: `esphome/components/ebike_ble_broadcast/ebike_ble_broadcast.cpp`

**Step 1: Implement on_cadence_()**

```cpp
void EbikeBleBroadcast::on_cadence_(float rpm) {
  if (std::isnan(rpm) || rpm < 0.0f) return;

  // BLE CSC Measurement update model:
  //   delta_revs = rpm / 60 * delta_seconds
  // We're called whenever the sensor publishes (~1 Hz). Assume
  // exactly 1 s between updates - good enough for the spec, and
  // bike computers smooth values themselves anyway.
  cum_crank_revs_ += rpm / 60.0f;
  last_crank_event_time_ += 1024;  // 1 second in 1/1024 s units

  uint16_t revs_u16 = static_cast<uint16_t>(cum_crank_revs_) & 0xFFFF;

  // CSC Measurement frame:
  //   byte 0: flags = 0x02 (crank revs present, wheel data absent)
  //   bytes 1-2: cumulative crank revolutions (LE uint16)
  //   bytes 3-4: last crank event time (LE uint16, 1/1024 s)
  uint8_t payload[5];
  payload[0] = 0x02;
  payload[1] = revs_u16 & 0xFF;
  payload[2] = (revs_u16 >> 8) & 0xFF;
  payload[3] = last_crank_event_time_ & 0xFF;
  payload[4] = (last_crank_event_time_ >> 8) & 0xFF;

  ESP_LOGD(TAG, "CSC notify: rpm=%.1f -> revs=%u, t=%u",
           rpm, revs_u16, last_crank_event_time_);

#ifdef EBIKE_BLE_BROADCAST_NIMBLE
  if (conn_handle_ != 0xFFFF && csc_measurement_handle != 0) {
    struct os_mbuf *om = ble_hs_mbuf_from_flat(payload, sizeof(payload));
    if (om != nullptr) {
      ble_gatts_notify_custom(conn_handle_, csc_measurement_handle, om);
    }
  }
#endif
}
```

**Step 2: Flash + test**

In nRF Connect: connect → Cycling Speed and Cadence → CSC Measurement → enable Notify.

Expected: notifications arrive at ~1 Hz. Each one contains 5 bytes; nRF Connect can decode CSC. Cadence value displayed should hover around 80 RPM (the fake sensor's value).

In a different BLE app or with a script, reconstructing RPM from two consecutive frames must give back ~80.

**Step 3: Commit**

```bash
git add esphome/components/ebike_ble_broadcast/ebike_ble_broadcast.cpp
git commit -m "feat(ebike_ble_broadcast): CSC Measurement notifications from cadence

Accumulates fractional crank revolutions from incoming RPM updates,
packs into the CSC frame layout (flags + cum_revs_LE + event_time_LE),
and notifies subscribed clients. Verified at 1 Hz from nRF Connect:
RPM round-trips correctly from a steady fake cadence sensor."
```

---

## Phase 4: Integration with merged display+bridge firmware

### Task 10: Add the broadcast block to display-bridge-merged.yaml

**Files:**
- Modify: `esphome/display-bridge-merged.yaml`

**Step 1: Add cadence sensor binding to bosch_ebike_ldi**

Find the `bosch_ebike_ldi`-platform sensor block. Add an `id: bike_a_cadence` line under the cadence: entry:

```yaml
  - platform: bosch_ebike_ldi
    bosch_ebike_ldi_id: ebike_bridge
    battery_soc:
      id: bike_a_soc
      name: "eBike Battery SoC (Live)"
    odometer:
      id: bike_a_odo
      name: "eBike Odometer (Live)"
    speed:
      name: "eBike Speed"
    cadence:
      id: bike_a_cadence              # <-- ADD this id for the broadcaster
      name: "eBike Cadence"
    rider_power:
      name: "eBike Rider Power"
    ambient_brightness:
      name: "eBike Ambient Brightness"
```

**Step 2: Add the broadcast block**

After the `bosch_ebike_ldi:` instance config, add:

```yaml
# Optionales BLE-Broadcasting: macht Akku-SoC + Cadence sichtbar fuer
# Bike-Computer (Coros Dura, Garmin) als Standard-BLE-Sensoren.
ebike_ble_broadcast:
  id: ble_broadcast
  advertised_name: "Bosch eBike Bridge"
  battery_soc_id: bike_a_soc
  cadence_id: bike_a_cadence
```

**Step 3: Add external_components entry**

Find the existing `external_components:` block (added when bosch_ebike_ldi was wired). Add the new component:

```yaml
external_components:
  - source:
      type: git
      url: https://github.com/Xunil99/ha-bosch-ebike
      ref: main
    components: [bosch_ebike_ldi, ebike_ble_broadcast]
    refresh: 1d
```

(For LOCAL development before pushing to GitHub: use `type: local, path: components` instead.)

**Step 4: Compile + flash + check both functionalities**

Boot log should now show BOTH:
- `bosch_ebike_ldi` doing BLE central to the eBike
- `ebike_ble_broadcast` advertising as peripheral

**Step 5: Commit**

```bash
git add esphome/display-bridge-merged.yaml
git commit -m "feat(display-bridge): wire ebike_ble_broadcast into merged firmware

The combined display+bridge firmware now also re-broadcasts
SoC + cadence as a BLE peripheral. Standalone-bridge users opt
in by adding the same block to factory.yaml."
```

---

### Task 11: Pair with Coros Dura and verify on-bike

**Step 1: Boot the merged firmware on the JC4827W543 with a live Bosch eBike paired**

Confirm via display + ESPHome logs that:
- The eBike is connected (sensor.bike_a_connected = true)
- Battery SoC + cadence values are flowing (look in HA's developer-tools entity states)

**Step 2: Pair Coros Dura**

On Coros Dura: Settings → Sensors → Add Sensor → Search. The bridge advertises as "Bosch eBike Bridge" with both Cadence and Battery sensor types. Tap to pair.

**Step 3: Verify Live Data**

Pedal the eBike. On the Coros watch:
- Cadence field shows RPM (will match what the eBike's own display shows, ±2 RPM for sample timing)
- Battery field (configurable from sensor list) shows the eBike's SoC %

**Step 4: Persist-across-reboot test**

Power-cycle the ESP32. Coros should automatically reconnect without re-pairing. Validates `CONFIG_BT_NIMBLE_NVS_PERSIST: y` is doing its job.

**Step 5: Commit any tweaks made during testing**

```bash
git add -A
git commit -m "tweak(ebike_ble_broadcast): post-Coros-pairing adjustments

[Describe the specific changes - notification rate tuned, name
shortened to fit Coros UI, etc.]"
```

---

## Phase 5: Documentation and release

### Task 12: Add component README

**Files:**
- Create: `esphome/components/ebike_ble_broadcast/README.md`

**Step 1: Write the README**

```markdown
# ebike_ble_broadcast

ESPHome external component that re-broadcasts eBike data (battery SoC,
cadence) as standard Bluetooth-SIG GATT services so bike computers like
Coros Dura, Garmin Edge, Wahoo Roam can pair with the bridge and see
live readings — no Home Assistant in the path.

Pairs with the existing `bosch_ebike_ldi` component (or any other source
of `sensor::Sensor` values you point it at).

## Quick start

```yaml
external_components:
  - source: github://Xunil99/ha-bosch-ebike@main
    components: [bosch_ebike_ldi, ebike_ble_broadcast]

bosch_ebike_ldi:
  id: ebike_bridge

sensor:
  - platform: bosch_ebike_ldi
    bosch_ebike_ldi_id: ebike_bridge
    battery_soc:
      id: bike_a_soc
    cadence:
      id: bike_a_cadence

ebike_ble_broadcast:
  id: ble_broadcast
  advertised_name: "Bosch eBike Bridge"
  battery_soc_id: bike_a_soc
  cadence_id: bike_a_cadence
```

## Required sdkconfig

```yaml
esp32:
  framework:
    type: esp-idf
    sdkconfig_options:
      CONFIG_BT_NIMBLE_MAX_CONNECTIONS: "2"   # was 1
```

## Pairing

1. Boot the bridge. It will advertise as the configured name.
2. On the bike computer, scan for BLE sensors. Both Cadence and Battery
   sub-types appear.
3. Pair. Bond is persisted across reboots.

## What's broadcast

| Service | UUID | Data |
|---|---|---|
| Battery | 0x180F | Battery Level char (0x2A19), 0-100% |
| Cycling Speed and Cadence | 0x1816 | CSC Measurement char (0x2A5B), cadence only |

Speed is not exposed — bike computers compute their own from GPS.
```

**Step 2: Commit**

```bash
git add esphome/components/ebike_ble_broadcast/README.md
git commit -m "docs(ebike_ble_broadcast): README with quick-start and YAML examples"
```

---

### Task 13: Update top-level project README

**Files:**
- Modify: `README.md` (project root)

**Step 1:** Add a section "Optional: Re-broadcast to bike computers (Coros Dura, Garmin)" linking to the component README. Include a one-line example YAML snippet.

**Step 2: Commit**

```bash
git add README.md
git commit -m "docs: mention ebike_ble_broadcast in project README"
```

---

### Task 14: Tag and release

**Step 1:** Bump component / project version markers if any exist.

**Step 2:** Create a git tag and a GitHub release once the user verifies the firmware works on their bike + Coros:

```bash
git tag ble-broadcast-v0.1.0
git push origin main
git push origin ble-broadcast-v0.1.0
gh release create ble-broadcast-v0.1.0 \
  --title "ebike_ble_broadcast v0.1.0 — MVP" \
  --notes "First release: Battery + Cadence broadcast. Verified with Coros Dura."
```

---

## Open items deferred past MVP

- Cycling Power Service (0x1818) — would add CPS using rider_power sensor
- Speed broadcasting via CSC — currently disabled, would need wheel-circumference YAML option
- Custom HCM / FTMS profile for "drive mode" / "range" — only useful on devices that understand these
- Multi-client support — currently one Coros at a time
- ANT+ E-Bike Profile via external nRF52840 ANT module — separate sub-project

Each becomes its own design doc + plan when prioritised.
