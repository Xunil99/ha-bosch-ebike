#pragma once

#ifdef USE_ESP32

#include "esphome/core/component.h"
#include "esphome/core/preferences.h"
#include "esphome/components/binary_sensor/binary_sensor.h"
#include "esphome/components/sensor/sensor.h"
#include "livedata_decoder.h"
#include <string>
#include <cstdint>
#include <cstring>

namespace esphome {
namespace bosch_ebike_ldi_dual {

extern const uint8_t LDI_SERVICE_UUID128[16];
extern const uint8_t LDI_LIVE_DATA_CHR_UUID128[16];
static constexpr uint16_t LDI_APPEARANCE_CYCLING = 0x0480;

// This bridge talks to up to TWO bikes simultaneously. Each bike occupies a
// fixed "slot" (0 = "eBike 1", 1 = "eBike 2"). The slot a bike gets is decided
// by bond order / MAC the first time it connects and is then persisted, so it
// stays stable across reboots. ALL per-connection and per-bike live state is
// indexed by slot; nothing about an individual bike's connection or data may be
// kept in shared (non-slot) state, or the two bikes would clobber each other.
static constexpr int NUM_SLOTS = 2;
// Sentinel for "no connection" – mirrors NimBLE's BLE_HS_CONN_HANDLE_NONE
// without pulling the NimBLE host headers into this codegen-facing header.
static constexpr uint16_t CONN_HANDLE_NONE = 0xFFFF;

// ---- Per-connection / per-bike discovery + transport state ------------------
// One instance per slot. On DISCONNECT only the affected slot is reset to a
// default-constructed ConnectionContext{}, never both.
struct ConnectionContext {
  uint16_t conn_handle{CONN_HANDLE_NONE};
  uint16_t live_chr_val_handle{0};
  uint16_t live_chr_end_handle{0};
  uint16_t live_svc_start_handle{0};
  uint16_t live_svc_end_handle{0};
  bool encrypted{false};
};

// ---- Persisted slot->MAC mapping (stable bike->slot assignment) -------------
// POD copy of a NimBLE ble_addr_t (type + 6-byte address). Kept NimBLE-free so
// the header stays usable by the Python codegen layer; the .cpp converts to/from
// ble_addr_t. Stored verbatim in ESPHome preferences (one blob per slot).
struct PeerMac {
  bool valid{false};
  uint8_t type{0};
  uint8_t addr[6]{0, 0, 0, 0, 0, 0};

  bool equals(uint8_t other_type, const uint8_t *other_addr) const {
    return this->valid && this->type == other_type &&
           std::memcmp(this->addr, other_addr, 6) == 0;
  }
};

class BoschEbikeLdiDual : public Component {
 public:
  void setup() override;
  void loop() override;
  void dump_config() override;
  float get_setup_priority() const override;

  void set_device_name(const std::string &name) { this->device_name_ = name; }

  // ---- Sensor wiring (set from sensor.py / binary_sensor.py codegen) ----
  // NOTE: the public setter API is intentionally left single-bike for now.
  // Distinct entities per bike (and thus slot-indexed setters) arrive in
  // Phase 2; until then these target the "eBike 1" view of slot 0 so the
  // existing single-bike YAML keeps compiling and publishing.
  void set_speed_sensor(sensor::Sensor *s)              { speed_sensor_ = s; }
  void set_cadence_sensor(sensor::Sensor *s)            { cadence_sensor_ = s; }
  void set_rider_power_sensor(sensor::Sensor *s)        { rider_power_sensor_ = s; }
  void set_ambient_brightness_sensor(sensor::Sensor *s) { ambient_brightness_sensor_ = s; }
  void set_battery_soc_sensor(sensor::Sensor *s)        { battery_soc_sensor_ = s; }
  void set_odometer_sensor(sensor::Sensor *s)           { odometer_sensor_ = s; }

  void set_connected_sensor(binary_sensor::BinarySensor *s)         { connected_sensor_ = s; }
  void set_light_sensor(binary_sensor::BinarySensor *s)             { light_sensor_ = s; }
  void set_system_locked_sensor(binary_sensor::BinarySensor *s)     { system_locked_sensor_ = s; }
  void set_charger_connected_sensor(binary_sensor::BinarySensor *s) { charger_connected_sensor_ = s; }
  void set_light_reserve_sensor(binary_sensor::BinarySensor *s)     { light_reserve_sensor_ = s; }
  void set_diagnosis_active_sensor(binary_sensor::BinarySensor *s)  { diagnosis_active_sensor_ = s; }
  void set_bike_in_motion_sensor(binary_sensor::BinarySensor *s)    { bike_in_motion_sensor_ = s; }

  // ---- Called from NimBLE callback context (always slot-routed) ----
  // Routing: each callback receives the connecting conn_handle; slot_for_conn()
  // maps it back to the owning slot. Notifies/reads/connect-state are then
  // applied to peer_[slot] / latest_[slot] only.
  void on_connect_state_change(int slot, bool connected);
  void on_live_data_notify(int slot, const uint8_t *data, size_t len);

  // conn_handle -> slot index whose peer_[i].conn_handle matches, else -1.
  int slot_for_conn(uint16_t conn_handle) const;
  // Pick the slot for a (re)connecting peer: the slot whose persisted MAC
  // matches, else the lowest free slot (which is then claimed + persisted),
  // else -1 when both slots are occupied by other bikes.
  int free_or_matching_slot(uint8_t addr_type, const uint8_t *addr);

  // Direct slot accessors for the static C-callbacks (one component instance).
  ConnectionContext &peer(int slot) { return this->peer_[slot]; }

  // True if ANY slot currently holds an active connection. Drives advertising
  // decisions: while only one of two bikes is connected we must keep
  // advertising so the second can still be found/reconnect.
  bool any_connected() const;

  void clear_bonding();

  // Open the discoverable pairing window (default 5 min). While it is open the
  // bridge advertises with the LDI service solicitation so a Flow app can add
  // it; outside the window the bridge advertises privately (no solicitation,
  // non-discoverable, whitelist) so it is invisible to other users' Flow apps
  // while the bonded bike can still reconnect. Exposed as an HA button.
  void start_pairing();
  // True while the pairing window is open (for an HA status binary_sensor).
  bool is_pairing();

  // Master advertising toggle (HA switch, default ON). When OFF the bridge
  // only advertises during a pairing window (boot 5 min / button) and is
  // otherwise fully silent; when ON it additionally does private reconnect
  // advertising to the bonded bike. The 5-minute boot window runs regardless.
  void set_advertising_enabled(bool enabled);
  bool advertising_enabled();

 protected:
  std::string device_name_{"HA eBike Bridge"};

  // ---- Per-slot connection + data state -------------------------------------
  // Two BLE peers, two LiveData snapshots, two sets of publish plumbing. There
  // is exactly one component instance, so these live as members (not globals).
  ConnectionContext peer_[NUM_SLOTS];

  // Connection-state publish plumbing, per slot.
  bool pending_connected_state_[NUM_SLOTS]{false, false};
  bool last_published_connected_[NUM_SLOTS]{false, false};
  bool connection_dirty_[NUM_SLOTS]{false, false};

  // Last decoded values per slot (held across notifications since fields may
  // be sparse).
  LiveData latest_[NUM_SLOTS];
  bool data_dirty_[NUM_SLOTS]{false, false};

  // Persisted bike->slot assignment (stable across reboots).
  PeerMac slot_mac_[NUM_SLOTS];
  ESPPreferenceObject slot_mac_pref_[NUM_SLOTS];

  // Sensors (single-bike view, see note on the setters above).
  sensor::Sensor *speed_sensor_{nullptr};
  sensor::Sensor *cadence_sensor_{nullptr};
  sensor::Sensor *rider_power_sensor_{nullptr};
  sensor::Sensor *ambient_brightness_sensor_{nullptr};
  sensor::Sensor *battery_soc_sensor_{nullptr};
  sensor::Sensor *odometer_sensor_{nullptr};

  binary_sensor::BinarySensor *connected_sensor_{nullptr};
  binary_sensor::BinarySensor *light_sensor_{nullptr};
  binary_sensor::BinarySensor *system_locked_sensor_{nullptr};
  binary_sensor::BinarySensor *charger_connected_sensor_{nullptr};
  binary_sensor::BinarySensor *light_reserve_sensor_{nullptr};
  binary_sensor::BinarySensor *diagnosis_active_sensor_{nullptr};
  binary_sensor::BinarySensor *bike_in_motion_sensor_{nullptr};

  // Load/persist the slot->MAC mapping.
  void load_slot_macs_();
  void persist_slot_mac_(int slot);

  void publish_decoded_(int slot);
};

}  // namespace bosch_ebike_ldi_dual
}  // namespace esphome

#endif
