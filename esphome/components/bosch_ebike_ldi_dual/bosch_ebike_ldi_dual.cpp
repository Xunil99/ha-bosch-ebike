#ifdef USE_ESP32

#include "bosch_ebike_ldi_dual.h"
#include "esphome/core/log.h"
#include "esphome/core/helpers.h"
#include "esphome/core/application.h"

extern "C" {
#include "esp_bt.h"
#include "esp_log.h"
#include "nvs_flash.h"
#include "nimble/nimble_port.h"
#include "nimble/nimble_port_freertos.h"
#include "host/ble_hs.h"
#include "host/ble_uuid.h"
#include "host/ble_gap.h"
#include "host/ble_gatt.h"
#include "nimble/hci_common.h"  // BLE_HCI_ADV_FILT_* advertising filter policies
#include "host/util/util.h"
#include "services/gap/ble_svc_gap.h"
#include "services/gatt/ble_svc_gatt.h"
// NVS-backed bond store (provided by NimBLE's ble_store_config helper)
void ble_store_config_init(void);
}

namespace esphome {
namespace bosch_ebike_ldi_dual {

static const char *const TAG = "bosch_ebike_ldi_dual";

// Spec V1.0: 0000xxxx-eaa2-11e9-81b4-2a2ae2dbcce4 with xxxx=eb20/eb21.
// NimBLE expects 128-bit UUIDs in little-endian byte order.
const uint8_t LDI_SERVICE_UUID128[16] = {
    0xe4, 0xcc, 0xdb, 0xe2, 0x2a, 0x2a, 0xb4, 0x81,
    0xe9, 0x11, 0xa2, 0xea, 0x20, 0xeb, 0x00, 0x00,
};
const uint8_t LDI_LIVE_DATA_CHR_UUID128[16] = {
    0xe4, 0xcc, 0xdb, 0xe2, 0x2a, 0x2a, 0xb4, 0x81,
    0xe9, 0x11, 0xa2, 0xea, 0x21, 0xeb, 0x00, 0x00,
};

// AD type for 128-bit Service Solicitation list (BT Core Suppl. Part A §1.10).
static constexpr uint8_t AD_TYPE_SOL_UUIDS128 = 0x15;

// Singleton pointer so static C-callbacks can reach the instance.
static BoschEbikeLdiDual *g_instance_dual = nullptr;

// ---- Forward decls for static callbacks -------------------------------------
static void ble_host_task(void *param);
static void on_stack_reset(int reason);
static void on_stack_sync();
static int gap_event_handler(struct ble_gap_event *event, void *arg);
static int on_disc_svc(uint16_t conn_handle, const struct ble_gatt_error *error,
                       const struct ble_gatt_svc *svc, void *arg);
static int on_disc_chr(uint16_t conn_handle, const struct ble_gatt_error *error,
                       const struct ble_gatt_chr *chr, void *arg);
static int on_disc_dsc(uint16_t conn_handle, const struct ble_gatt_error *error,
                       uint16_t chr_val_handle,
                       const struct ble_gatt_dsc *dsc, void *arg);
static int on_cccd_write(uint16_t conn_handle, const struct ble_gatt_error *error,
                         struct ble_gatt_attr *attr, void *arg);
static int on_chr_read(uint16_t conn_handle, const struct ble_gatt_error *error,
                       struct ble_gatt_attr *attr, void *arg);
static int on_mtu_exchange(uint16_t conn_handle, const struct ble_gatt_error *error,
                           uint16_t mtu, void *arg);

// Per-connection / per-bike state (ConnectionContext, LiveData latest_[]) lives
// on the single component instance (see header). The static C-callbacks below
// reach it through g_instance_dual and always operate on a slot routed from the
// event's conn_handle — never on a single shared struct.

// ---- Helpers ----------------------------------------------------------------
static void log_hex(const char *prefix, const uint8_t *buf, size_t len) {
  // Log up to 64 bytes inline to keep the log readable.
  char hex[3 * 64 + 1];
  size_t to_print = len < 64 ? len : 64;
  for (size_t i = 0; i < to_print; i++) {
    snprintf(&hex[i * 3], 4, "%02x ", buf[i]);
  }
  hex[to_print > 0 ? (to_print * 3 - 1) : 0] = '\0';
  ESP_LOGD(TAG, "%s len=%u: %s%s", prefix, (unsigned) len, hex, len > 64 ? " …" : "");
}

// Build raw advertising payload including Service Solicitation 128-bit (AD 0x15).
// NimBLE's ble_hs_adv_fields struct cannot represent solicitation, so we build
// the byte sequence by hand and pass it to ble_gap_adv_set_data().
static int build_adv_payload(uint8_t *buf, size_t buf_len, size_t *out_len,
                             const std::string &name, bool pairing) {
  size_t pos = 0;
  // 1) Flags. Pairing window: LE General Discoverable + BR/EDR Not Supported
  //    (0x06) so a Flow app can find and add the bridge. Private reconnect
  //    mode: BR/EDR Not Supported only (0x04) -> NOT discoverable, so other
  //    users' Flow apps do not list it.
  if (pos + 3 > buf_len) return -1;
  buf[pos++] = 0x02; buf[pos++] = 0x01; buf[pos++] = (uint8_t) (pairing ? 0x06 : 0x04);

  // 2) Appearance (LE): Cycling generic = 0x0480
  if (pos + 4 > buf_len) return -1;
  buf[pos++] = 0x03; buf[pos++] = 0x19;
  buf[pos++] = (uint8_t) (LDI_APPEARANCE_CYCLING & 0xff);
  buf[pos++] = (uint8_t) ((LDI_APPEARANCE_CYCLING >> 8) & 0xff);

  // 3) Service Solicitation – 128-bit (AD type 0x15), UUID in little-endian.
  //    ONLY in the pairing window: the solicitation is exactly what makes a
  //    Flow app recognise us as a pairable Bosch accessory. In private
  //    reconnect mode we omit it; the bonded bike reconnects by our address.
  if (pairing) {
    if (pos + 2 + 16 > buf_len) return -1;
    buf[pos++] = 1 + 16; buf[pos++] = AD_TYPE_SOL_UUIDS128;
    memcpy(&buf[pos], LDI_SERVICE_UUID128, 16);
    pos += 16;
  }

  // 4) Complete Local Name (truncate if needed; total adv payload max 31 bytes).
  size_t remaining = buf_len - pos;
  size_t name_max = remaining >= 2 ? remaining - 2 : 0;
  size_t name_len = name.size() < name_max ? name.size() : name_max;
  if (name_len > 0) {
    buf[pos++] = (uint8_t) (1 + name_len);
    buf[pos++] = 0x09;  // Complete Local Name
    memcpy(&buf[pos], name.data(), name_len);
    pos += name_len;
  }

  *out_len = pos;
  return 0;
}

// Cache for static use in start_advertising().
extern std::string g_device_name_cache_dual;

// Pairing window. While > 0 and not yet elapsed, advertise discoverable with
// the LDI solicitation (Flow app can add the bridge). Otherwise advertise
// privately so other users' Flow apps never see it. Set by start_pairing()
// and, on first boot without a bond, by on_stack_sync().
static constexpr uint32_t PAIRING_WINDOW_MS = 5 * 60 * 1000;  // 5 minutes
static uint32_t g_pairing_until_ms_dual = 0;

// Master advertising toggle (HA switch). Default on. When off, the bridge only
// advertises inside a pairing window (boot / button); otherwise it stays fully
// silent (no background reconnect). The boot window always overrides this.
static bool g_adv_enabled_dual = true;

// True once the NimBLE host has synced (on_stack_sync ran). Until then NO GAP
// or bond-store call is safe. The 'eBike Advertising' switch restores its
// persisted state during early boot (RESTORE_DEFAULT_ON) and would otherwise
// call ble_gap_*/the bond store before the stack is ready -> boot crash on the
// 2nd boot once the NVS store is populated (Issue #41).
static bool g_ble_synced_dual = false;

static bool pairing_window_open() {
  return g_pairing_until_ms_dual != 0 && (int32_t) (g_pairing_until_ms_dual - millis()) > 0;
}

// Upper bound for reading bonded peers (well above NimBLE's default 3 bonds).
static constexpr int MAX_BOND_PROBE = 8;

// Number of bikes currently bonded in the NVS store.
static int bonded_peer_count() {
  ble_addr_t addrs[MAX_BOND_PROBE];
  int num = 0;
  if (ble_store_util_bonded_peers(addrs, &num, MAX_BOND_PROBE) != 0)
    return 0;
  return num;
}

// Restrict who may scan/connect to the bonded bike(s) only.
static void apply_bond_whitelist() {
  ble_addr_t addrs[MAX_BOND_PROBE];
  int num = 0;
  if (ble_store_util_bonded_peers(addrs, &num, MAX_BOND_PROBE) == 0 && num > 0)
    ble_gap_wl_set(addrs, num);
}

static int start_advertising() {
  const bool pairing = pairing_window_open();

  // Outside a pairing window, advertise only if the master switch is on AND a
  // bike is bonded (private reconnect). Otherwise stay fully silent. A pairing
  // window (boot / button) always advertises, regardless of the switch.
  if (!pairing && (!g_adv_enabled_dual || bonded_peer_count() == 0)) {
    ESP_LOGI(TAG, "Idle (advertising %s, pairing window closed). Press 'Pairing starten' to add a bike.",
             g_adv_enabled_dual ? "on but no bond" : "disabled");
    return 0;
  }

  uint8_t adv_buf[31];
  size_t adv_len = 0;
  if (build_adv_payload(adv_buf, sizeof(adv_buf), &adv_len, g_device_name_cache_dual, pairing) != 0) {
    ESP_LOGE(TAG, "adv payload build failed");
    return -1;
  }

  int rc = ble_gap_adv_set_data(adv_buf, adv_len);
  if (rc != 0) {
    ESP_LOGE(TAG, "ble_gap_adv_set_data failed: %d", rc);
    return rc;
  }

  struct ble_gap_adv_params adv_params = {};
  adv_params.conn_mode = BLE_GAP_CONN_MODE_UND;
  adv_params.itvl_min = 0;  // use default (~1.28 s)
  adv_params.itvl_max = 0;
  if (pairing) {
    adv_params.disc_mode = BLE_GAP_DISC_MODE_GEN;
    adv_params.filter_policy = BLE_HCI_ADV_FILT_NONE;
  } else {
    // Private reconnect: not discoverable, only the bonded bike may connect.
    adv_params.disc_mode = BLE_GAP_DISC_MODE_NON;
    apply_bond_whitelist();
    adv_params.filter_policy = BLE_HCI_ADV_FILT_BOTH;
  }

  rc = ble_gap_adv_start(BLE_OWN_ADDR_PUBLIC, nullptr, BLE_HS_FOREVER,
                         &adv_params, gap_event_handler, nullptr);
  if (rc != 0) {
    ESP_LOGE(TAG, "ble_gap_adv_start failed: %d", rc);
  } else {
    ESP_LOGI(TAG, "Advertising started (%s), name='%s'",
             pairing ? "PAIRING: discoverable + solicitation eb20"
                     : "private reconnect: non-discoverable, whitelist, no solicitation",
             g_device_name_cache_dual.c_str());
  }
  return rc;
}

// Definition of the cache declared above.
std::string g_device_name_cache_dual;

// ---- Stack lifecycle --------------------------------------------------------
static void on_stack_reset(int reason) {
  ESP_LOGW(TAG, "BLE stack reset, reason=%d", reason);
}

static void on_stack_sync() {
  int rc = ble_hs_util_ensure_addr(0);
  if (rc != 0) {
    ESP_LOGE(TAG, "ensure_addr failed: %d", rc);
    return;
  }
  ble_svc_gap_device_name_set(g_device_name_cache_dual.c_str());
  ble_svc_gap_device_appearance_set(LDI_APPEARANCE_CYCLING);
  // Open the pairing window for ~5 min after EVERY boot (not only when no bond
  // exists). This lets the user (re-)pair or add a bike right after power-up
  // without needing the HA button. When it elapses, loop() switches the bridge
  // to private (non-discoverable, whitelist) advertising so it is no longer
  // visible to other users' Flow apps. A successful connect closes it early.
  g_pairing_until_ms_dual = millis() + PAIRING_WINDOW_MS;
  ESP_LOGI(TAG, "Boot pairing window open for %u min",
           (unsigned) (PAIRING_WINDOW_MS / 60000));
  g_ble_synced_dual = true;  // host is up now; switch/button BLE calls are safe
  start_advertising();
}

static void ble_host_task(void *param) {
  nimble_port_run();
  nimble_port_freertos_deinit();
}

// ---- GAP event handler ------------------------------------------------------
static int gap_event_handler(struct ble_gap_event *event, void *arg) {
  switch (event->type) {
    case BLE_GAP_EVENT_CONNECT: {
      ESP_LOGI(TAG, "GAP CONNECT status=%d conn_handle=%u",
               event->connect.status, event->connect.conn_handle);
      if (event->connect.status == 0) {
        uint16_t handle = event->connect.conn_handle;
        int slot = -1;
        if (g_instance_dual) {
          // If ENC_CHANGE already routed this handle (it can arrive before
          // CONNECT on bond-resume), reuse that slot instead of routing again.
          slot = g_instance_dual->slot_for_conn(handle);
          if (slot < 0) {
            // Route this peer to a stable slot by its identity address (matching
            // a persisted MAC, or claiming the next free slot). Falling back to
            // the OTA address keeps us working before identity is resolved.
            struct ble_gap_conn_desc desc;
            if (ble_gap_conn_find(handle, &desc) == 0) {
              const ble_addr_t &id = desc.peer_id_addr;
              const ble_addr_t &ota = desc.peer_ota_addr;
              // An all-zero identity address is NimBLE's canonical "not yet
              // resolved" marker; a (practically nonexistent) legitimately
              // all-zero public address would be misclassified as unresolved.
              const ble_addr_t &use =
                  (id.type == 0 && id.val[0] == 0 && id.val[1] == 0 && id.val[2] == 0 &&
                   id.val[3] == 0 && id.val[4] == 0 && id.val[5] == 0)
                      ? ota
                      : id;
              slot = g_instance_dual->free_or_matching_slot(use.type, use.val);
            } else {
              ESP_LOGW(TAG, "conn_find failed for handle=%u", handle);
            }
          }
        }
        if (slot < 0) {
          ESP_LOGW(TAG, "No free slot for connecting peer (both bikes occupied) – dropping");
          ble_gap_terminate(handle, BLE_ERR_REM_USER_CONN_TERM);
          return 0;
        }

        ConnectionContext &peer = g_instance_dual->peer(slot);
        if (peer.conn_handle != handle) {
          // Newly assigned slot: start discovery from a clean context.
          peer = ConnectionContext{};
          peer.conn_handle = handle;
        }
        peer.encrypted = false;
        ESP_LOGI(TAG, "Peer assigned to slot %d (eBike %d)", slot, slot + 1);
        // A bike connected -> pairing succeeded; close the discoverable window
        // so we drop to private advertising on the next disconnect.
        g_pairing_until_ms_dual = 0;
        g_instance_dual->on_connect_state_change(slot, true);

        // Workaround for LDI-001: bike doesn't initiate DLE. We do.
        ble_gap_set_data_len(handle, 251, 2120);

        // Keep advertising so the OTHER bike can still be found / reconnect.
        // (start_advertising() is a no-op while not applicable.)
        start_advertising();
      } else {
        // Connection failed – resume advertising.
        start_advertising();
      }
      return 0;
    }
    case BLE_GAP_EVENT_DISCONNECT: {
      ESP_LOGW(TAG, "GAP DISCONNECT reason=0x%02x conn_handle=%u",
               event->disconnect.reason, event->disconnect.conn.conn_handle);
      // Clear ONLY the slot owning this conn_handle, never both.
      if (g_instance_dual) {
        int slot = g_instance_dual->slot_for_conn(event->disconnect.conn.conn_handle);
        if (slot >= 0) {
          g_instance_dual->peer(slot) = ConnectionContext{};
          g_instance_dual->on_connect_state_change(slot, false);
        } else {
          ESP_LOGW(TAG, "DISCONNECT for unknown conn_handle=%u (no slot)",
                   event->disconnect.conn.conn_handle);
        }
      }
      start_advertising();
      return 0;
    }
    case BLE_GAP_EVENT_ENC_CHANGE: {
      ESP_LOGI(TAG, "Encryption changed status=%d conn_handle=%u",
               event->enc_change.status, event->enc_change.conn_handle);
      if (event->enc_change.status == 0 && g_instance_dual) {
        // IMPORTANT: use the conn_handle from the event itself. On bond-resume
        // reconnects NimBLE may deliver ENC_CHANGE before BLE_GAP_EVENT_CONNECT
        // to user-space, so the slot may not be assigned yet — resolve it from
        // the peer's identity address in that case (same routing as CONNECT).
        uint16_t handle = event->enc_change.conn_handle;
        // Resolve the peer's identity address now: after a successful pairing
        // the bike has distributed its IRK/identity, so peer_id_addr is the
        // stable address all future reconnects will route by.
        struct ble_gap_conn_desc desc;
        bool have_desc = ble_gap_conn_find(handle, &desc) == 0;
        // An all-zero identity address is NimBLE's canonical "not yet resolved"
        // marker; a (practically nonexistent) legitimately all-zero public
        // address would be misclassified as unresolved.
        bool id_resolved =
            have_desc &&
            !(desc.peer_id_addr.type == 0 && desc.peer_id_addr.val[0] == 0 &&
              desc.peer_id_addr.val[1] == 0 && desc.peer_id_addr.val[2] == 0 &&
              desc.peer_id_addr.val[3] == 0 && desc.peer_id_addr.val[4] == 0 &&
              desc.peer_id_addr.val[5] == 0);

        int slot = g_instance_dual->slot_for_conn(handle);
        if (slot < 0) {
          if (have_desc) {
            const ble_addr_t &use = id_resolved ? desc.peer_id_addr : desc.peer_ota_addr;
            slot = g_instance_dual->free_or_matching_slot(use.type, use.val);
          }
          if (slot >= 0) {
            ConnectionContext &peer = g_instance_dual->peer(slot);
            peer = ConnectionContext{};
            peer.conn_handle = handle;
            g_instance_dual->on_connect_state_change(slot, true);
            ESP_LOGI(TAG, "ENC_CHANGE assigned peer to slot %d (eBike %d)", slot, slot + 1);
          }
        }
        if (slot < 0) {
          ESP_LOGW(TAG, "ENC_CHANGE for unroutable conn_handle=%u – ignoring", handle);
          return 0;
        }
        // First-bond MAC convergence: a brand-new bike is initially claimed/
        // persisted under its OTA/random address (identity not yet resolved at
        // CONNECT time). Now that the identity address is known, overwrite the
        // routed slot's persisted MAC with it and re-persist, so future
        // reconnects — which match by the IDENTITY MAC — route to THIS slot
        // instead of grabbing the other free slot (which would leave the bike
        // occupying both slots over its first bond lifecycle).
        if (id_resolved) {
          const ble_addr_t &id = desc.peer_id_addr;
          if (!g_instance_dual->slot_mac_equals(slot, id.type, id.val)) {
            g_instance_dual->set_slot_mac(slot, id.type, id.val);
            ESP_LOGI(TAG, "Slot %d (eBike %d) MAC converged to identity "
                          "%02x:%02x:%02x:%02x:%02x:%02x (type %u)",
                     slot, slot + 1, id.val[5], id.val[4], id.val[3], id.val[2],
                     id.val[1], id.val[0], id.type);
          }
        }
        g_instance_dual->peer(slot).conn_handle = handle;
        g_instance_dual->peer(slot).encrypted = true;
        // Workaround for LDI-001/003: initiate MTU ourselves.
        int rc = ble_gattc_exchange_mtu(handle, on_mtu_exchange, nullptr);
        if (rc != 0) {
          ESP_LOGE(TAG, "exchange_mtu start failed: %d (handle=%u)", rc, handle);
        }
      } else if (event->enc_change.status != 0) {
        ESP_LOGE(TAG, "Pairing failed; consider clearing bonding on both sides.");
      }
      return 0;
    }
    case BLE_GAP_EVENT_MTU: {
      ESP_LOGI(TAG, "MTU updated channel=%u mtu=%u",
               event->mtu.channel_id, event->mtu.value);
      return 0;
    }
    case BLE_GAP_EVENT_NOTIFY_RX: {
      // The eBike is GATT server – it sends notifications on eb21. Route the
      // payload to the slot that owns this connection so the two bikes' live
      // data never gets merged together.
      uint16_t handle = event->notify_rx.attr_handle;
      uint16_t len = OS_MBUF_PKTLEN(event->notify_rx.om);
      uint8_t buf[256];
      uint16_t copy_len = len < sizeof(buf) ? len : sizeof(buf);
      os_mbuf_copydata(event->notify_rx.om, 0, copy_len, buf);
      log_hex("NOTIFY_RX raw", buf, copy_len);
      ESP_LOGI(TAG, "NOTIFY conn_handle=%u attr=0x%04x len=%u indication=%d",
               event->notify_rx.conn_handle, handle, len, event->notify_rx.indication);
      if (g_instance_dual) {
        int slot = g_instance_dual->slot_for_conn(event->notify_rx.conn_handle);
        if (slot >= 0) {
          g_instance_dual->on_live_data_notify(slot, buf, copy_len);
        } else {
          ESP_LOGW(TAG, "NOTIFY for unknown conn_handle=%u – dropping",
                   event->notify_rx.conn_handle);
        }
      }
      return 0;
    }
    case BLE_GAP_EVENT_REPEAT_PAIRING: {
      // Existing bond – delete and let the bike re-pair.
      struct ble_gap_conn_desc desc;
      if (ble_gap_conn_find(event->repeat_pairing.conn_handle, &desc) == 0) {
        ble_store_util_delete_peer(&desc.peer_id_addr);
      }
      return BLE_GAP_REPEAT_PAIRING_RETRY;
    }
    case BLE_GAP_EVENT_PASSKEY_ACTION: {
      // Just-Works LESC – no passkey expected. Confirm if asked.
      struct ble_sm_io pkey = {};
      if (event->passkey.params.action == BLE_SM_IOACT_NUMCMP) {
        pkey.action = BLE_SM_IOACT_NUMCMP;
        pkey.numcmp_accept = 1;
        ble_sm_inject_io(event->passkey.conn_handle, &pkey);
      }
      return 0;
    }
    case BLE_GAP_EVENT_SUBSCRIBE: {
      ESP_LOGD(TAG, "GAP SUBSCRIBE attr=0x%04x reason=%d notify=%d indicate=%d",
               event->subscribe.attr_handle, event->subscribe.reason,
               event->subscribe.cur_notify, event->subscribe.cur_indicate);
      return 0;
    }
    case BLE_GAP_EVENT_DATA_LEN_CHG: {
      ESP_LOGI(TAG, "DLE updated tx_max=%u rx_max=%u",
               event->data_len_chg.max_tx_octets,
               event->data_len_chg.max_rx_octets);
      return 0;
    }
    default:
      ESP_LOGV(TAG, "GAP event type=%d", event->type);
      return 0;
  }
}

// ---- GATT discovery callbacks ----------------------------------------------
static int on_mtu_exchange(uint16_t conn_handle, const struct ble_gatt_error *error,
                           uint16_t mtu, void *arg) {
  if (error != nullptr && error->status != 0) {
    ESP_LOGE(TAG, "MTU exchange failed status=0x%x", error->status);
    return 0;
  }
  ESP_LOGI(TAG, "MTU exchange complete mtu=%u – starting service discovery", mtu);

  ble_uuid128_t svc_uuid;
  svc_uuid.u.type = BLE_UUID_TYPE_128;
  memcpy(svc_uuid.value, LDI_SERVICE_UUID128, 16);
  int rc = ble_gattc_disc_svc_by_uuid(conn_handle, &svc_uuid.u, on_disc_svc, nullptr);
  if (rc != 0) {
    ESP_LOGE(TAG, "disc_svc_by_uuid failed: %d", rc);
  }
  return 0;
}

static int on_disc_svc(uint16_t conn_handle, const struct ble_gatt_error *error,
                       const struct ble_gatt_svc *svc, void *arg) {
  if (error == nullptr) return 0;
  int slot = g_instance_dual ? g_instance_dual->slot_for_conn(conn_handle) : -1;
  if (slot < 0) {
    ESP_LOGW(TAG, "disc_svc for unknown conn_handle=%u – dropping", conn_handle);
    return 0;
  }
  ConnectionContext &peer = g_instance_dual->peer(slot);
  if (error->status == BLE_HS_EDONE) {
    if (peer.live_svc_start_handle == 0) {
      ESP_LOGE(TAG, "Service eb20 NOT found on peer (slot %d). Is the eBike v19+?", slot);
      return 0;
    }
    // Service found – discover its characteristics.
    ble_uuid128_t chr_uuid;
    chr_uuid.u.type = BLE_UUID_TYPE_128;
    memcpy(chr_uuid.value, LDI_LIVE_DATA_CHR_UUID128, 16);
    int rc = ble_gattc_disc_chrs_by_uuid(conn_handle,
                                         peer.live_svc_start_handle,
                                         peer.live_svc_end_handle,
                                         &chr_uuid.u, on_disc_chr, nullptr);
    if (rc != 0) ESP_LOGE(TAG, "disc_chrs_by_uuid failed: %d", rc);
    return 0;
  }
  if (error->status != 0) {
    ESP_LOGE(TAG, "disc_svc error 0x%x", error->status);
    return 0;
  }
  if (svc != nullptr) {
    peer.live_svc_start_handle = svc->start_handle;
    peer.live_svc_end_handle = svc->end_handle;
    ESP_LOGI(TAG, "Service eb20 found (slot %d), handles 0x%04x-0x%04x",
             slot, svc->start_handle, svc->end_handle);
  }
  return 0;
}

static int on_disc_chr(uint16_t conn_handle, const struct ble_gatt_error *error,
                       const struct ble_gatt_chr *chr, void *arg) {
  if (error == nullptr) return 0;
  int slot = g_instance_dual ? g_instance_dual->slot_for_conn(conn_handle) : -1;
  if (slot < 0) {
    ESP_LOGW(TAG, "disc_chr for unknown conn_handle=%u – dropping", conn_handle);
    return 0;
  }
  ConnectionContext &peer = g_instance_dual->peer(slot);
  if (error->status == BLE_HS_EDONE) {
    if (peer.live_chr_val_handle == 0) {
      ESP_LOGE(TAG, "Characteristic eb21 NOT found on peer (slot %d).", slot);
      return 0;
    }
    // Find the CCCD via descriptor discovery.
    int rc = ble_gattc_disc_all_dscs(conn_handle,
                                     peer.live_chr_val_handle,
                                     peer.live_chr_end_handle,
                                     on_disc_dsc, nullptr);
    if (rc != 0) ESP_LOGE(TAG, "disc_all_dscs failed: %d", rc);
    return 0;
  }
  if (error->status != 0) {
    ESP_LOGE(TAG, "disc_chr error 0x%x", error->status);
    return 0;
  }
  if (chr != nullptr) {
    peer.live_chr_val_handle = chr->val_handle;
    peer.live_chr_end_handle = peer.live_svc_end_handle;
    ESP_LOGI(TAG, "Char eb21 found (slot %d) val_handle=0x%04x props=0x%02x",
             slot, chr->val_handle, chr->properties);
  }
  return 0;
}

static int on_disc_dsc(uint16_t conn_handle, const struct ble_gatt_error *error,
                       uint16_t chr_val_handle,
                       const struct ble_gatt_dsc *dsc, void *arg) {
  if (error == nullptr) return 0;
  if (error->status == BLE_HS_EDONE) return 0;
  if (error->status != 0) {
    ESP_LOGE(TAG, "disc_dsc error 0x%x", error->status);
    return 0;
  }
  // CCCD has UUID 0x2902.
  if (dsc != nullptr && dsc->uuid.u.type == BLE_UUID_TYPE_16 &&
      dsc->uuid.u16.value == 0x2902) {
    ESP_LOGI(TAG, "CCCD at handle 0x%04x – enabling notifications", dsc->handle);
    uint8_t value[2] = {0x01, 0x00};  // notifications
    int rc = ble_gattc_write_flat(conn_handle, dsc->handle, value, sizeof(value),
                                  on_cccd_write, nullptr);
    if (rc != 0) ESP_LOGE(TAG, "CCCD write start failed: %d", rc);
  }
  return 0;
}

static int on_cccd_write(uint16_t conn_handle, const struct ble_gatt_error *error,
                         struct ble_gatt_attr *attr, void *arg) {
  if (error != nullptr && error->status != 0) {
    ESP_LOGE(TAG, "CCCD write failed status=0x%x", error->status);
    return 0;
  }
  ESP_LOGI(TAG, "CCCD written – issuing initial read for full snapshot");

  int slot = g_instance_dual ? g_instance_dual->slot_for_conn(conn_handle) : -1;
  if (slot < 0) {
    ESP_LOGW(TAG, "on_cccd_write for unknown conn_handle=%u – dropping", conn_handle);
    return 0;
  }
  ConnectionContext &peer = g_instance_dual->peer(slot);

  // Per Spec §2.2.3.2 a Read returns the latest values of ALL available
  // LiveData fields. Notifications only carry changed fields, so without
  // this read we'd never see steady-state values like battery_soc or speed=0.
  if (peer.live_chr_val_handle != 0) {
    int rc = ble_gattc_read(conn_handle, peer.live_chr_val_handle,
                            on_chr_read, nullptr);
    if (rc != 0) {
      ESP_LOGE(TAG, "ble_gattc_read failed: %d", rc);
    }
  }
  return 0;
}

static int on_chr_read(uint16_t conn_handle, const struct ble_gatt_error *error,
                       struct ble_gatt_attr *attr, void *arg) {
  if (error != nullptr && error->status != 0) {
    ESP_LOGE(TAG, "Initial read failed status=0x%x", error->status);
    return 0;
  }
  if (attr == nullptr || attr->om == nullptr) {
    ESP_LOGW(TAG, "Initial read returned no payload");
    return 0;
  }
  uint16_t len = OS_MBUF_PKTLEN(attr->om);
  uint8_t buf[256];
  uint16_t copy_len = len < sizeof(buf) ? len : sizeof(buf);
  os_mbuf_copydata(attr->om, 0, copy_len, buf);
  log_hex("INITIAL_READ raw", buf, copy_len);
  ESP_LOGI(TAG, "Initial read got %u bytes – parsing as full snapshot", len);
  if (g_instance_dual) {
    int slot = g_instance_dual->slot_for_conn(conn_handle);
    if (slot >= 0) {
      g_instance_dual->on_live_data_notify(slot, buf, copy_len);
    } else {
      ESP_LOGW(TAG, "Initial read for unknown conn_handle=%u – dropping", conn_handle);
    }
  }
  return 0;
}

// ---- ESPHome Component lifecycle -------------------------------------------
void BoschEbikeLdiDual::setup() {
  g_instance_dual = this;
  g_device_name_cache_dual = this->device_name_;

  // Restore the persisted bike->slot (MAC) assignment so "eBike 1"/"eBike 2"
  // stay stable across reboots.
  this->load_slot_macs_();

  ESP_LOGI(TAG, "Initializing Bosch eBike LDI Dual (2-bike) bridge (dual v0.1)");

  // NVS is already initialized by ESPHome before our setup() runs.
  esp_err_t ret = nimble_port_init();
  if (ret != ESP_OK) {
    ESP_LOGE(TAG, "nimble_port_init failed: %d", ret);
    this->mark_failed();
    return;
  }

  ble_hs_cfg.reset_cb = on_stack_reset;
  ble_hs_cfg.sync_cb = on_stack_sync;
  ble_hs_cfg.sm_io_cap = BLE_HS_IO_NO_INPUT_OUTPUT;
  ble_hs_cfg.sm_bonding = 1;
  ble_hs_cfg.sm_sc = 1;
  ble_hs_cfg.sm_mitm = 0;
  ble_hs_cfg.sm_our_key_dist = BLE_SM_PAIR_KEY_DIST_ENC | BLE_SM_PAIR_KEY_DIST_ID;
  ble_hs_cfg.sm_their_key_dist = BLE_SM_PAIR_KEY_DIST_ENC | BLE_SM_PAIR_KEY_DIST_ID;
  ble_hs_cfg.store_status_cb = ble_store_util_status_rr;

  ble_svc_gap_init();
  ble_svc_gatt_init();
  ble_store_config_init();  // NVS-backed bond store

  nimble_port_freertos_init(ble_host_task);
}

void BoschEbikeLdiDual::loop() {
  // Process both slots' connection-state changes. We track per-slot
  // last_published_connected_ for each bike; the single connected_sensor_ is
  // a Phase-1 "eBike 1" view of slot 0 (per-bike entities come in Phase 2),
  // so only slot 0's transitions drive that sensor.
  for (int s = 0; s < NUM_SLOTS; s++) {
    if (this->connection_dirty_[s]) {
      this->connection_dirty_[s] = false;
      bool connected = this->pending_connected_state_[s];
      if (connected != this->last_published_connected_[s]) {
        this->last_published_connected_[s] = connected;
        if (s == 0 && this->connected_sensor_ != nullptr) {
          this->connected_sensor_->publish_state(connected);
        }
        ESP_LOGI(TAG, "Connection state slot %d (eBike %d) -> %s",
                 s, s + 1, connected ? "connected" : "disconnected");
      }
    }
    if (this->data_dirty_[s]) {
      this->data_dirty_[s] = false;
      this->publish_decoded_(s);
    }
  }

  // Pairing window auto-expiry: once it lapses and NO bike is connected, drop
  // back to private (non-discoverable, whitelist) advertising so the bridge
  // stops being visible to other users' Flow apps. If a bike IS connected we
  // keep the window closed but advertising is governed by the connect/
  // disconnect flow (so a second bike can still be added).
  if (g_pairing_until_ms_dual != 0 && (int32_t) (g_pairing_until_ms_dual - millis()) <= 0) {
    g_pairing_until_ms_dual = 0;
    if (!this->any_connected()) {
      ESP_LOGI(TAG, "Pairing window expired -> private reconnect advertising");
      ble_gap_adv_stop();
      start_advertising();
    }
  }
}

void BoschEbikeLdiDual::publish_decoded_(int slot) {
  const LiveData &latest = this->latest_[slot];

  // Phase 1: only slot 0 ("eBike 1") drives the single entity set. Slot 1's
  // decoded snapshot is kept in latest_[1] (and logged) so the data layer is
  // coherent; per-bike entities for slot 1 arrive in Phase 2.
  if (slot != 0) {
    ESP_LOGD(TAG, "Decoded slot %d (eBike %d) data (no Phase-1 entity yet): "
                  "speed_raw=%u soc=%u",
             slot, slot + 1,
             (unsigned) latest.speed_raw, (unsigned) latest.battery_soc);
    return;
  }

  // Convert raw scales into HA-friendly units. Each sensor publishes
  // unconditionally (ESPHome itself dedupes on equal values).
  if (latest.speed_present && this->speed_sensor_) {
    this->speed_sensor_->publish_state(latest.speed_raw / 100.0f);
  }
  if (latest.cadence_present && this->cadence_sensor_) {
    this->cadence_sensor_->publish_state(latest.cadence);
  }
  if (latest.rider_power_present && this->rider_power_sensor_) {
    this->rider_power_sensor_->publish_state(latest.rider_power);
  }
  if (latest.ambient_brightness_present && this->ambient_brightness_sensor_) {
    this->ambient_brightness_sensor_->publish_state(latest.ambient_brightness_raw / 1000.0f);
  }
  if (latest.battery_soc_present && this->battery_soc_sensor_) {
    this->battery_soc_sensor_->publish_state(latest.battery_soc);
  }
  if (latest.odometer_present && this->odometer_sensor_) {
    // publish in km (one decimal will be obvious in HA)
    this->odometer_sensor_->publish_state(latest.odometer / 1000.0f);
  }

  if (latest.bike_light_present && this->light_sensor_) {
    // 1 = OFF, 2 = ON, 0 = INVALID -> treat invalid as off
    this->light_sensor_->publish_state(latest.bike_light == 2);
  }
  if (latest.system_locked_present && this->system_locked_sensor_) {
    // HA device_class=lock: ON=unlocked, OFF=locked. We invert here so
    // the user sees "Abgeschlossen" when the bike is actually locked.
    this->system_locked_sensor_->publish_state(!latest.system_locked);
  }
  if (latest.charger_connected_present && this->charger_connected_sensor_) {
    this->charger_connected_sensor_->publish_state(latest.charger_connected);
  }
  if (latest.light_reserve_present && this->light_reserve_sensor_) {
    this->light_reserve_sensor_->publish_state(latest.light_reserve);
  }
  if (latest.diagnosis_active_present && this->diagnosis_active_sensor_) {
    this->diagnosis_active_sensor_->publish_state(latest.diagnosis_active);
  }
  if (latest.bike_not_driving_present && this->bike_in_motion_sensor_) {
    // Spec field is "bike_not_driving" – we expose the inverse, "in motion"
    this->bike_in_motion_sensor_->publish_state(!latest.bike_not_driving);
  }
}

void BoschEbikeLdiDual::dump_config() {
  ESP_LOGCONFIG(TAG, "Bosch eBike LDI Dual (2-bike) Bridge:");
  ESP_LOGCONFIG(TAG, "  Device name: %s", this->device_name_.c_str());
  ESP_LOGCONFIG(TAG, "  Slots: 2 (eBike 1 + eBike 2)");
  ESP_LOGCONFIG(TAG, "  Service UUID: 0000eb20-eaa2-11e9-81b4-2a2ae2dbcce4");
  ESP_LOGCONFIG(TAG, "  Live Data Char: 0000eb21-eaa2-11e9-81b4-2a2ae2dbcce4");
  ESP_LOGCONFIG(TAG, "  Appearance: 0x0480 (Cycling)");
  ESP_LOGCONFIG(TAG, "  Status: dual v0.1 – per-peer slot routing + private advertising + manual pairing window");
}

float BoschEbikeLdiDual::get_setup_priority() const {
  return setup_priority::AFTER_WIFI;
}

void BoschEbikeLdiDual::on_connect_state_change(int slot, bool connected) {
  this->pending_connected_state_[slot] = connected;
  this->connection_dirty_[slot] = true;
  if (!connected) {
    // Reset "present" flags so stale values don't get re-published on reconnect.
    this->latest_[slot] = LiveData{};
  }
}

void BoschEbikeLdiDual::on_live_data_notify(int slot, const uint8_t *data, size_t len) {
  LiveData snapshot;
  if (!decode_live_data(data, len, snapshot)) {
    ESP_LOGW(TAG, "Protobuf decode failed (slot %d, len=%u)", slot, (unsigned) len);
    return;
  }

  LiveData &latest = this->latest_[slot];

  // Merge into latest_[slot]: only overwrite fields that were actually present
  // in this notification (per Spec §2.2.4.3).
  if (snapshot.speed_present)              { latest.speed_present = true;              latest.speed_raw = snapshot.speed_raw; }
  if (snapshot.cadence_present)            { latest.cadence_present = true;            latest.cadence = snapshot.cadence; }
  if (snapshot.rider_power_present)        { latest.rider_power_present = true;        latest.rider_power = snapshot.rider_power; }
  if (snapshot.ambient_brightness_present) { latest.ambient_brightness_present = true; latest.ambient_brightness_raw = snapshot.ambient_brightness_raw; }
  if (snapshot.battery_soc_present)        { latest.battery_soc_present = true;        latest.battery_soc = snapshot.battery_soc; }
  if (snapshot.time_present)               { latest.time_present = true;               latest.time = snapshot.time; }
  if (snapshot.odometer_present)           { latest.odometer_present = true;           latest.odometer = snapshot.odometer; }
  if (snapshot.bike_light_present)         { latest.bike_light_present = true;         latest.bike_light = snapshot.bike_light; }
  if (snapshot.system_locked_present)      { latest.system_locked_present = true;      latest.system_locked = snapshot.system_locked; }
  if (snapshot.charger_connected_present)  { latest.charger_connected_present = true;  latest.charger_connected = snapshot.charger_connected; }
  if (snapshot.light_reserve_present)      { latest.light_reserve_present = true;      latest.light_reserve = snapshot.light_reserve; }
  if (snapshot.diagnosis_active_present)   { latest.diagnosis_active_present = true;   latest.diagnosis_active = snapshot.diagnosis_active; }
  if (snapshot.bike_not_driving_present)   { latest.bike_not_driving_present = true;   latest.bike_not_driving = snapshot.bike_not_driving; }

  this->data_dirty_[slot] = true;
}

// ---- Slot routing + bike->slot persistence ---------------------------------
int BoschEbikeLdiDual::slot_for_conn(uint16_t conn_handle) const {
  if (conn_handle == CONN_HANDLE_NONE) return -1;
  for (int i = 0; i < NUM_SLOTS; i++) {
    if (this->peer_[i].conn_handle == conn_handle) return i;
  }
  return -1;
}

bool BoschEbikeLdiDual::any_connected() const {
  for (int i = 0; i < NUM_SLOTS; i++) {
    if (this->peer_[i].conn_handle != CONN_HANDLE_NONE) return true;
  }
  return false;
}

int BoschEbikeLdiDual::free_or_matching_slot(uint8_t addr_type, const uint8_t *addr) {
  // 1) Slot whose persisted MAC matches this peer -> always reuse it. This is
  //    THE stable bike->slot binding; it wins even if the slot still holds a
  //    stale handle (reconnect before the old DISCONNECT was seen), so the same
  //    bike never lands in two slots.
  for (int i = 0; i < NUM_SLOTS; i++) {
    if (this->slot_mac_[i].equals(addr_type, addr)) return i;
  }
  // 2) No persisted match: claim the lowest slot that is neither live nor
  //    already assigned to a different bike, then persist its MAC.
  for (int i = 0; i < NUM_SLOTS; i++) {
    if (this->peer_[i].conn_handle == CONN_HANDLE_NONE && !this->slot_mac_[i].valid) {
      this->slot_mac_[i].valid = true;
      this->slot_mac_[i].type = addr_type;
      std::memcpy(this->slot_mac_[i].addr, addr, 6);
      this->persist_slot_mac_(i);
      ESP_LOGI(TAG, "Claimed slot %d (eBike %d) for new peer "
                    "%02x:%02x:%02x:%02x:%02x:%02x (type %u)",
               i, i + 1, addr[5], addr[4], addr[3], addr[2], addr[1], addr[0], addr_type);
      return i;
    }
  }
  // 3) Both slots are owned by other bikes and not free.
  return -1;
}

void BoschEbikeLdiDual::load_slot_macs_() {
  for (int i = 0; i < NUM_SLOTS; i++) {
    // Stable, distinct preference key per slot.
    uint32_t key = fnv1_hash(std::string("bosch_ebike_ldi_dual_slot_mac_") +
                             std::to_string(i));
    this->slot_mac_pref_[i] = global_preferences->make_preference<PeerMac>(key);
    PeerMac stored;
    if (this->slot_mac_pref_[i].load(&stored)) {
      this->slot_mac_[i] = stored;
      if (stored.valid) {
        ESP_LOGI(TAG, "Restored slot %d (eBike %d) MAC "
                      "%02x:%02x:%02x:%02x:%02x:%02x (type %u)",
                 i, i + 1, stored.addr[5], stored.addr[4], stored.addr[3],
                 stored.addr[2], stored.addr[1], stored.addr[0], stored.type);
      }
    }
  }
}

void BoschEbikeLdiDual::persist_slot_mac_(int slot) {
  if (!this->slot_mac_pref_[slot].save(&this->slot_mac_[slot])) {
    ESP_LOGW(TAG, "Failed to persist slot %d MAC", slot);
  }
}

void BoschEbikeLdiDual::clear_bonding() {
  ESP_LOGW(TAG, "Clearing all bonded peers from NVS and slot->MAC mapping");
  ble_store_clear();
  // Wipe the persisted bike->slot assignment too, so re-pairing starts fresh
  // and a re-added bike can take slot 0 again (otherwise a stale slot_mac_
  // would force it into the previously assigned slot or reject it).
  for (int i = 0; i < NUM_SLOTS; i++) {
    this->slot_mac_[i] = PeerMac{};
    this->persist_slot_mac_(i);
  }
}

void BoschEbikeLdiDual::start_pairing() {
  g_pairing_until_ms_dual = millis() + PAIRING_WINDOW_MS;
  ESP_LOGI(TAG, "Pairing window opened for %u min - discoverable for Flow app",
           (unsigned) (PAIRING_WINDOW_MS / 60000));
  // Re-advertise in pairing mode now (drop any private advertising first).
  // Only touch GAP once the stack is up; before sync on_stack_sync() handles it.
  if (g_ble_synced_dual) {
    ble_gap_adv_stop();
    start_advertising();
  }
}

bool BoschEbikeLdiDual::is_pairing() { return pairing_window_open(); }

void BoschEbikeLdiDual::set_advertising_enabled(bool enabled) {
  g_adv_enabled_dual = enabled;
  ESP_LOGI(TAG, "Advertising master switch -> %s", enabled ? "ON" : "OFF");
  // Re-evaluate immediately (no effect while connected; advertising is off
  // during a connection and the new state applies on the next disconnect).
  // Guard on g_ble_synced_dual: the HA switch restores its persisted state during
  // early boot, before the NimBLE stack is up — calling GAP/the bond store then
  // crashes (Issue #41). on_stack_sync() applies the current g_adv_enabled_dual.
  if (g_ble_synced_dual && !this->any_connected()) {
    ble_gap_adv_stop();
    start_advertising();
  }
}

bool BoschEbikeLdiDual::advertising_enabled() { return g_adv_enabled_dual; }

}  // namespace bosch_ebike_ldi_dual
}  // namespace esphome

#endif  // USE_ESP32
