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
  // Discovery-sequence tracking (issue #61 / #79). The post-encryption setup
  // chain (MTU exchange, service/characteristic discovery, enabling
  // notifications, initial read) has no timeout or retry of its own, so a
  // stall would otherwise sit "connected" forever with no live data.
  //
  // Real two-bike logs (issue #79, round 2 - a tester's precisely timed
  // capture with the round 1 fix already in place) showed the failure is
  // NOT GATT contention: an idle connection that had done zero GATT work,
  // held back by discovery_started deferring below, still got torn down by
  // the link layer's own supervision timeout (reason 0x08) 4-5s after ITS
  // OWN connect - well before this struct's discovery_deadline_ms (8s) can
  // fire, and the SAME failure a single, uncontended link never sees. The
  // real cause is the classic ESP32's single radio not reliably servicing
  // TWO connections' periodic connection events while both are still
  // "young", regardless of what either is doing at the GATT level.
  // BoschEbikeLdiDual::on_connect_state_change() now withholds re-
  // advertising for a second bike until this slot settles (see
  // settle_hold below), which is the layer that actually needed fixing;
  // discovery_started staggering is kept as a harmless second layer of
  // defence, not the primary fix.
  //
  // discovery_started: true once exchange_mtu() has actually been called for
  // this connection (try_start_discovery() may defer it while the OTHER slot
  // is mid-chain, to avoid asking the radio to run two fresh multi-step GATT
  // procedures at once).
  bool discovery_started{false};
  // discovery_deadline_ms: armed (millis() + DISCOVERY_TIMEOUT_MS) the
  // moment this slot connects, covering the whole connect -> encrypt ->
  // discovery -> live-data chain including any time spent deferred waiting
  // for the other slot. Cleared (0) only by on_discovery_complete() - NOT
  // by an ordinary notify, see settle_hold below for why that distinction
  // matters. loop() force-disconnects the slot if this elapses first - the
  // DISCONNECT handler's own re-advertising then gives it a clean, retried
  // attempt. 0 means "not armed". Also doubles as the upper bound on how
  // long settle_hold below may withhold advertising for.
  uint32_t discovery_deadline_ms{0};
  // True while this slot is the only one connected and has not yet reached
  // live data: re-advertising for a second, not-yet-connected bike is
  // withheld until this clears or the slot disconnects (organically via
  // the link layer, or forced by the discovery_deadline_ms watchdog) -
  // either path's own handler resumes advertising. See
  // on_connect_state_change().
  //
  // Cleared ONLY from on_discovery_complete() - the initial-read callback,
  // NOT on_live_data_notify() (an ordinary NOTIFY_RX). A round 2 tester log
  // (issue #79) caught this clearing 0.8s early on a bonded bike's very
  // first notification, which per the BLE spec a server may send from a
  // retained CCC descriptor value the moment it is connected and
  // encrypted, before this bridge has even written its OWN CCCD - so an
  // early notify is not proof this slot's setup chain is actually done.
  bool settle_hold{false};
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
  // Every exposed entity is per-bike, so each setter takes the target slot
  // (0 = "eBike 1", 1 = "eBike 2"). The Python codegen computes the slot from
  // the YAML `bike:` key (1->0, 2->1) so two `- platform:` blocks declare two
  // distinct, separately-named entity sets. The bridge-wide pairing/advertising
  // status is NOT routed here (it is exposed via template/switch/button in YAML).
  void set_speed_sensor(int slot, sensor::Sensor *s)              { speed_sensor_[slot] = s; }
  void set_cadence_sensor(int slot, sensor::Sensor *s)            { cadence_sensor_[slot] = s; }
  void set_rider_power_sensor(int slot, sensor::Sensor *s)        { rider_power_sensor_[slot] = s; }
  void set_ambient_brightness_sensor(int slot, sensor::Sensor *s) { ambient_brightness_sensor_[slot] = s; }
  void set_battery_soc_sensor(int slot, sensor::Sensor *s)        { battery_soc_sensor_[slot] = s; }
  void set_odometer_sensor(int slot, sensor::Sensor *s)           { odometer_sensor_[slot] = s; }

  void set_connected_sensor(int slot, binary_sensor::BinarySensor *s)         { connected_sensor_[slot] = s; }
  void set_light_sensor(int slot, binary_sensor::BinarySensor *s)             { light_sensor_[slot] = s; }
  void set_system_locked_sensor(int slot, binary_sensor::BinarySensor *s)     { system_locked_sensor_[slot] = s; }
  void set_charger_connected_sensor(int slot, binary_sensor::BinarySensor *s) { charger_connected_sensor_[slot] = s; }
  void set_light_reserve_sensor(int slot, binary_sensor::BinarySensor *s)     { light_reserve_sensor_[slot] = s; }
  void set_diagnosis_active_sensor(int slot, binary_sensor::BinarySensor *s)  { diagnosis_active_sensor_[slot] = s; }
  void set_bike_in_motion_sensor(int slot, binary_sensor::BinarySensor *s)    { bike_in_motion_sensor_[slot] = s; }

  // ---- Called from NimBLE callback context (always slot-routed) ----
  // Routing: each callback receives the connecting conn_handle; slot_for_conn()
  // maps it back to the owning slot. Notifies/reads/connect-state are then
  // applied to peer_[slot] / latest_[slot] only.
  void on_connect_state_change(int slot, bool connected);
  void on_live_data_notify(int slot, const uint8_t *data, size_t len);

  // Called ONLY from the initial-read callback (on_chr_read), never from an
  // ordinary NOTIFY_RX - see the long comment on settle_hold below for why
  // that distinction matters (issue #79, round 3). This is the one true
  // signal that this slot's whole setup chain genuinely finished.
  void on_discovery_complete(int slot);

  // Kick off this slot's MTU/discovery chain (exchange_mtu(), which the rest
  // of the chain follows on from its own callback), unless it has already
  // started or the OTHER slot's own chain is still in flight - in which case
  // this is a no-op and loop() retries it on a later tick (issue #61 / #79).
  // Callable from both NimBLE callback context (ENC_CHANGE, for the common
  // uncontended case) and the ESPHome main loop task (loop()'s retry), same
  // as the other direct ble_gap_*/ble_gattc_* callers already in this file.
  void try_start_discovery(int slot);

  // conn_handle -> slot index whose peer_[i].conn_handle matches, else -1.
  int slot_for_conn(uint16_t conn_handle) const;
  // Pick the slot for a (re)connecting peer: the slot whose persisted MAC
  // matches, else the lowest free slot (which is then claimed + persisted),
  // else -1 when both slots are occupied by other bikes.
  int free_or_matching_slot(uint8_t addr_type, const uint8_t *addr);

  // Direct slot accessors for the static C-callbacks (one component instance).
  ConnectionContext &peer(int slot) { return this->peer_[slot]; }

  // True if the slot's persisted MAC already equals this peer address. Used by
  // the ENC_CHANGE handler to detect whether the persisted MAC still needs to
  // converge to the resolved identity address.
  bool slot_mac_equals(int slot, uint8_t addr_type, const uint8_t *addr) const {
    return this->slot_mac_[slot].equals(addr_type, addr);
  }
  // Overwrite a slot's MAC with the resolved identity address and re-persist it,
  // so future reconnects (which match by identity MAC) route to this slot.
  void set_slot_mac(int slot, uint8_t addr_type, const uint8_t *addr) {
    this->slot_mac_[slot].valid = true;
    this->slot_mac_[slot].type = addr_type;
    std::memcpy(this->slot_mac_[slot].addr, addr, 6);
    this->persist_slot_mac_(slot);
  }

  // True if ANY slot currently holds an active connection. Drives advertising
  // decisions: while only one of two bikes is connected we must keep
  // advertising so the second can still be found/reconnect.
  bool any_connected() const;

  void clear_bonding();
  // Per-slot: delete only THIS slot's bond + MAC mapping, disconnect it if live,
  // and refresh advertising. Exposed as a per-bike "Bond löschen" HA button.
  void clear_bonding(int slot);

  // Open the discoverable pairing window (default 5 min). While it is open the
  // bridge advertises with the LDI service solicitation so a Flow app can add
  // it; outside the window the bridge advertises privately (no solicitation,
  // non-discoverable, whitelist) so it is invisible to other users' Flow apps
  // while the bonded bike can still reconnect. Exposed as an HA button.
  // Open a discoverable 5-minute pairing window TARGETING a specific slot. A new
  // (unbonded) bike that connects during the window is bound to this slot, so
  // the user pairs eBike 1 vs eBike 2 deterministically via its own switch.
  void start_pairing(int slot);
  // Close the pairing window if it currently targets this slot.
  void stop_pairing(int slot);
  // True while a pairing window is open AND targets this slot. Drives the
  // per-bike pairing switch so it auto-resets when the window closes/expires.
  bool is_pairing(int slot);

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

  // Per-bike entities, one pointer per slot. slot 0 = "eBike 1", 1 = "eBike 2".
  // publish_decoded_(slot) / the connection publisher only ever touch the
  // pointer at [slot], so bike 1's data can never reach bike 2's entity.
  sensor::Sensor *speed_sensor_[NUM_SLOTS]{nullptr, nullptr};
  sensor::Sensor *cadence_sensor_[NUM_SLOTS]{nullptr, nullptr};
  sensor::Sensor *rider_power_sensor_[NUM_SLOTS]{nullptr, nullptr};
  sensor::Sensor *ambient_brightness_sensor_[NUM_SLOTS]{nullptr, nullptr};
  sensor::Sensor *battery_soc_sensor_[NUM_SLOTS]{nullptr, nullptr};
  sensor::Sensor *odometer_sensor_[NUM_SLOTS]{nullptr, nullptr};

  binary_sensor::BinarySensor *connected_sensor_[NUM_SLOTS]{nullptr, nullptr};
  binary_sensor::BinarySensor *light_sensor_[NUM_SLOTS]{nullptr, nullptr};
  binary_sensor::BinarySensor *system_locked_sensor_[NUM_SLOTS]{nullptr, nullptr};
  binary_sensor::BinarySensor *charger_connected_sensor_[NUM_SLOTS]{nullptr, nullptr};
  binary_sensor::BinarySensor *light_reserve_sensor_[NUM_SLOTS]{nullptr, nullptr};
  binary_sensor::BinarySensor *diagnosis_active_sensor_[NUM_SLOTS]{nullptr, nullptr};
  binary_sensor::BinarySensor *bike_in_motion_sensor_[NUM_SLOTS]{nullptr, nullptr};

  // Load/persist the slot->MAC mapping.
  void load_slot_macs_();
  void persist_slot_mac_(int slot);

  void publish_decoded_(int slot);
};

}  // namespace bosch_ebike_ldi_dual
}  // namespace esphome

#endif
