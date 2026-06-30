#ifdef USE_ESP32

#include "bosch_ebike_ldi.h"
#include "esphome/core/log.h"
#include "esphome/core/helpers.h"
#include "esphome/core/application.h"

#include <set>
#include <vector>

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
namespace bosch_ebike_ldi {

static const char *const TAG = "bosch_ebike_ldi";

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
static BoschEbikeLdi *g_instance = nullptr;

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
// One-time diagnostic full-GATT scan (issue #42): enumerate every service and
// characteristic the bike exposes over the LDI accessory link, logged once per
// boot. Read-only; runs after the eb20/eb21 live-data path is already up.
static int on_diag_svc(uint16_t conn_handle, const struct ble_gatt_error *error,
                       const struct ble_gatt_svc *svc, void *arg);
static int on_diag_chr(uint16_t conn_handle, const struct ble_gatt_error *error,
                       const struct ble_gatt_chr *chr, void *arg);
static bool g_diag_scan_done = false;

// One-time read-only raw dump (issue #42): after the scan, read every readable
// characteristic once and subscribe to every notify characteristic, logging the
// raw bytes so the payloads of the undocumented Bosch services (eb10/eb40/ebd0/
// 00000010) become visible. Never writes to a data characteristic; the writable
// 00000012 is left untouched on purpose (a write could change bike state).
static void diag_dump_start();
static void diag_read_next();
static int on_diag_read(uint16_t conn_handle, const struct ble_gatt_error *error,
                        struct ble_gatt_attr *attr, void *arg);
static void diag_subscribe_next();
static int on_diag_sub_dsc(uint16_t conn_handle, const struct ble_gatt_error *error,
                           uint16_t chr_val_handle,
                           const struct ble_gatt_dsc *dsc, void *arg);
static int on_diag_sub_write(uint16_t conn_handle, const struct ble_gatt_error *error,
                             struct ble_gatt_attr *attr, void *arg);

// Raw GATT characteristic property bits (per Bluetooth GATT spec); chr->properties
// from discovery carries exactly these. Local constants avoid depending on which
// NimBLE flag macros happen to be defined in this build.
static constexpr uint8_t CHR_PROP_READ = 0x02;
static constexpr uint8_t CHR_PROP_NOTIFY = 0x10;

// Characteristics collected during the scan; drives the dump above.
struct DiagChar {
  uint16_t def_handle{0};
  uint16_t val_handle{0};
  uint8_t props{0};
  bool redact{false};  // device-unique id char: value logged at DEBUG only
  char uuid[BLE_UUID_STR_LEN]{};
};
struct DiagSvc {
  uint16_t start{0};
  uint16_t end{0};
};
static std::vector<DiagChar> g_diag_chars;
static std::vector<DiagSvc> g_diag_svcs;  // service handle ranges, to bound CCCD scans
static size_t g_diag_idx = 0;
static uint16_t g_diag_pending_cccd = 0;

// ---- Per-connection discovery state -----------------------------------------
struct ConnectionContext {
  uint16_t conn_handle{BLE_HS_CONN_HANDLE_NONE};
  uint16_t live_chr_val_handle{0};
  uint16_t live_chr_end_handle{0};
  uint16_t live_svc_start_handle{0};
  uint16_t live_svc_end_handle{0};
  bool encrypted{false};
};
static ConnectionContext g_conn;

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

// INFO-level hex + ASCII dump for the one-time diagnostic pass, so the raw
// payloads of the non-LDI characteristics are visible at the default log level.
// (The high-frequency LDI hex stays at DEBUG via log_hex above.)
static void diag_log_value(const char *what, const char *uuid, uint16_t handle,
                           const uint8_t *buf, size_t len) {
  char hex[3 * 48 + 1];
  char asc[48 + 1];
  size_t n = len < 48 ? len : 48;
  for (size_t i = 0; i < n; i++) {
    snprintf(&hex[i * 3], 4, "%02x ", buf[i]);
    asc[i] = (buf[i] >= 0x20 && buf[i] < 0x7f) ? (char) buf[i] : '.';
  }
  hex[n > 0 ? (n * 3 - 1) : 0] = '\0';
  asc[n] = '\0';
  ESP_LOGI(TAG, "GATT dump: %s %s handle=0x%04x len=%u: %s%s | \"%s\"",
           what, uuid, handle, (unsigned) len, hex, len > 48 ? " …" : "", asc);
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
extern std::string g_device_name_cache;

// Pairing window. While > 0 and not yet elapsed, advertise discoverable with
// the LDI solicitation (Flow app can add the bridge). Otherwise advertise
// privately so other users' Flow apps never see it. Set by start_pairing()
// and, on first boot without a bond, by on_stack_sync().
static constexpr uint32_t PAIRING_WINDOW_MS = 5 * 60 * 1000;  // 5 minutes
static uint32_t g_pairing_until_ms = 0;

// Master advertising toggle (HA switch). Default on. When off, the bridge only
// advertises inside a pairing window (boot / button); otherwise it stays fully
// silent (no background reconnect). The boot window always overrides this.
static bool g_adv_enabled = true;

// True once the NimBLE host has synced (on_stack_sync ran). Until then NO GAP
// or bond-store call is safe. The 'eBike Advertising' switch restores its
// persisted state during early boot (RESTORE_DEFAULT_ON) and would otherwise
// call ble_gap_*/the bond store before the stack is ready -> boot crash on the
// 2nd boot once the NVS store is populated (Issue #41).
static bool g_ble_synced = false;

static bool pairing_window_open() {
  return g_pairing_until_ms != 0 && (int32_t) (g_pairing_until_ms - millis()) > 0;
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
  if (!pairing && (!g_adv_enabled || bonded_peer_count() == 0)) {
    ESP_LOGI(TAG, "Idle (advertising %s, pairing window closed). Press 'Pairing starten' to add a bike.",
             g_adv_enabled ? "on but no bond" : "disabled");
    return 0;
  }

  uint8_t adv_buf[31];
  size_t adv_len = 0;
  if (build_adv_payload(adv_buf, sizeof(adv_buf), &adv_len, g_device_name_cache, pairing) != 0) {
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
             g_device_name_cache.c_str());
  }
  return rc;
}

// Definition of the cache declared above.
std::string g_device_name_cache;

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
  ble_svc_gap_device_name_set(g_device_name_cache.c_str());
  ble_svc_gap_device_appearance_set(LDI_APPEARANCE_CYCLING);
  // Open the pairing window for ~5 min after EVERY boot (not only when no bond
  // exists). This lets the user (re-)pair or add a bike right after power-up
  // without needing the HA button. When it elapses, loop() switches the bridge
  // to private (non-discoverable, whitelist) advertising so it is no longer
  // visible to other users' Flow apps. A successful connect closes it early.
  g_pairing_until_ms = millis() + PAIRING_WINDOW_MS;
  ESP_LOGI(TAG, "Boot pairing window open for %u min",
           (unsigned) (PAIRING_WINDOW_MS / 60000));
  g_ble_synced = true;  // host is up now; switch/button BLE calls are safe
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
        g_conn.conn_handle = event->connect.conn_handle;
        g_conn.encrypted = false;
        // A bike connected -> pairing succeeded; close the discoverable window
        // so we drop to private advertising on the next disconnect.
        g_pairing_until_ms = 0;
        if (g_instance) g_instance->on_connect_state_change(true);

        // Workaround for LDI-001: bike doesn't initiate DLE. We do.
        ble_gap_set_data_len(event->connect.conn_handle, 251, 2120);
      } else {
        // Connection failed – resume advertising.
        start_advertising();
      }
      return 0;
    }
    case BLE_GAP_EVENT_DISCONNECT: {
      ESP_LOGW(TAG, "GAP DISCONNECT reason=0x%02x",
               event->disconnect.reason);
      g_conn = ConnectionContext{};
      // Abort any in-flight diagnostic dump so its callbacks stop cleanly (the
      // conn_handle is now NONE; the next diag_*_next() early-outs as well).
      g_diag_pending_cccd = 0;
      g_diag_idx = g_diag_chars.size();
      if (g_instance) g_instance->on_connect_state_change(false);
      start_advertising();
      return 0;
    }
    case BLE_GAP_EVENT_ENC_CHANGE: {
      ESP_LOGI(TAG, "Encryption changed status=%d conn_handle=%u",
               event->enc_change.status, event->enc_change.conn_handle);
      if (event->enc_change.status == 0) {
        // IMPORTANT: use the conn_handle from the event itself, NOT
        // g_conn.conn_handle. On bond-resume reconnects NimBLE delivers
        // ENC_CHANGE before BLE_GAP_EVENT_CONNECT to user-space, so our
        // global state may still hold the previous (NONE) handle. The
        // event handle is always valid.
        uint16_t handle = event->enc_change.conn_handle;
        g_conn.conn_handle = handle;
        g_conn.encrypted = true;
        // Workaround for LDI-001/003: initiate MTU ourselves.
        int rc = ble_gattc_exchange_mtu(handle, on_mtu_exchange, nullptr);
        if (rc != 0) {
          ESP_LOGE(TAG, "exchange_mtu start failed: %d (handle=%u)", rc, handle);
        }
      } else {
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
      // The eBike is GATT server – it sends notifications on eb21.
      uint16_t handle = event->notify_rx.attr_handle;
      uint16_t len = OS_MBUF_PKTLEN(event->notify_rx.om);
      uint8_t buf[256];
      uint16_t copy_len = len < sizeof(buf) ? len : sizeof(buf);
      os_mbuf_copydata(event->notify_rx.om, 0, copy_len, buf);
      if (handle == g_conn.live_chr_val_handle) {
        log_hex("NOTIFY_RX raw", buf, copy_len);  // LDI: high frequency -> DEBUG
        ESP_LOGI(TAG, "NOTIFY handle=0x%04x len=%u indication=%d",
                 handle, len, event->notify_rx.indication);
        if (g_instance) g_instance->on_live_data_notify(buf, copy_len);
      } else {
        // A non-LDI characteristic we subscribed to during the diagnostic dump
        // fired. Log the first payload per handle at INFO (with bytes) so it is
        // visible, then drop to DEBUG to avoid spamming. NEVER fed to the LDI
        // decoder, which would misparse it and pollute the sensors.
        static std::set<uint16_t> diag_seen;
        if (diag_seen.insert(handle).second) {
          diag_log_value("notify", "(non-LDI)", handle, buf, copy_len);
        } else {
          log_hex("NOTIFY_RX (non-LDI)", buf, copy_len);
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
  if (error->status == BLE_HS_EDONE) {
    if (g_conn.live_svc_start_handle == 0) {
      ESP_LOGE(TAG, "Service eb20 NOT found on peer. Is the eBike v19+?");
      return 0;
    }
    // Service found – discover its characteristics.
    ble_uuid128_t chr_uuid;
    chr_uuid.u.type = BLE_UUID_TYPE_128;
    memcpy(chr_uuid.value, LDI_LIVE_DATA_CHR_UUID128, 16);
    int rc = ble_gattc_disc_chrs_by_uuid(conn_handle,
                                         g_conn.live_svc_start_handle,
                                         g_conn.live_svc_end_handle,
                                         &chr_uuid.u, on_disc_chr, nullptr);
    if (rc != 0) ESP_LOGE(TAG, "disc_chrs_by_uuid failed: %d", rc);
    return 0;
  }
  if (error->status != 0) {
    ESP_LOGE(TAG, "disc_svc error 0x%x", error->status);
    return 0;
  }
  if (svc != nullptr) {
    g_conn.live_svc_start_handle = svc->start_handle;
    g_conn.live_svc_end_handle = svc->end_handle;
    ESP_LOGI(TAG, "Service eb20 found, handles 0x%04x-0x%04x",
             svc->start_handle, svc->end_handle);
  }
  return 0;
}

static int on_disc_chr(uint16_t conn_handle, const struct ble_gatt_error *error,
                       const struct ble_gatt_chr *chr, void *arg) {
  if (error == nullptr) return 0;
  if (error->status == BLE_HS_EDONE) {
    if (g_conn.live_chr_val_handle == 0) {
      ESP_LOGE(TAG, "Characteristic eb21 NOT found on peer.");
      return 0;
    }
    // Find the CCCD via descriptor discovery.
    int rc = ble_gattc_disc_all_dscs(conn_handle,
                                     g_conn.live_chr_val_handle,
                                     g_conn.live_chr_end_handle,
                                     on_disc_dsc, nullptr);
    if (rc != 0) ESP_LOGE(TAG, "disc_all_dscs failed: %d", rc);
    return 0;
  }
  if (error->status != 0) {
    ESP_LOGE(TAG, "disc_chr error 0x%x", error->status);
    return 0;
  }
  if (chr != nullptr) {
    g_conn.live_chr_val_handle = chr->val_handle;
    g_conn.live_chr_end_handle = g_conn.live_svc_end_handle;
    ESP_LOGI(TAG, "Char eb21 found val_handle=0x%04x props=0x%02x",
             chr->val_handle, chr->properties);
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

  // Per Spec §2.2.3.2 a Read returns the latest values of ALL available
  // LiveData fields. Notifications only carry changed fields, so without
  // this read we'd never see steady-state values like battery_soc or speed=0.
  if (g_conn.live_chr_val_handle != 0) {
    int rc = ble_gattc_read(conn_handle, g_conn.live_chr_val_handle,
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
  if (g_instance) g_instance->on_live_data_notify(buf, copy_len);

  // One-time diagnostic: enumerate ALL GATT services + characteristics so any
  // undocumented surface beyond eb20/eb21 shows up in the log (issue #42). Runs
  // once per boot, here (after the live-data path is up), so it never competes
  // with the connect/discovery/read procedures above. Read-only.
  if (!g_diag_scan_done) {
    ESP_LOGI(TAG, "Running one-time full GATT scan (diagnostic, issue #42)");
    g_diag_chars.clear();
    g_diag_svcs.clear();
    int rc = ble_gattc_disc_all_svcs(conn_handle, on_diag_svc, nullptr);
    if (rc == 0) {
      g_diag_scan_done = true;
    } else {
      ESP_LOGW(TAG, "diag disc_all_svcs start failed: %d (will retry on reconnect)", rc);
    }
  }
  return 0;
}

static int on_diag_svc(uint16_t conn_handle, const struct ble_gatt_error *error,
                       const struct ble_gatt_svc *svc, void *arg) {
  if (error == nullptr) return 0;
  if (error->status == BLE_HS_EDONE) {
    // All services listed; now enumerate every characteristic on the device.
    int rc = ble_gattc_disc_all_chrs(conn_handle, 0x0001, 0xffff, on_diag_chr, nullptr);
    if (rc != 0) ESP_LOGW(TAG, "diag disc_all_chrs start failed: %d", rc);
    return 0;
  }
  if (error->status != 0) {
    ESP_LOGW(TAG, "diag disc_all_svcs error 0x%x", error->status);
    return 0;
  }
  if (svc != nullptr) {
    char buf[BLE_UUID_STR_LEN];
    ble_uuid_to_str(&svc->uuid.u, buf);
    g_diag_svcs.push_back(DiagSvc{svc->start_handle, svc->end_handle});
    ESP_LOGI(TAG, "GATT scan: service %s handles 0x%04x-0x%04x",
             buf, svc->start_handle, svc->end_handle);
  }
  return 0;
}

static int on_diag_chr(uint16_t conn_handle, const struct ble_gatt_error *error,
                       const struct ble_gatt_chr *chr, void *arg) {
  if (error == nullptr) return 0;
  if (error->status == BLE_HS_EDONE) {
    ESP_LOGI(TAG, "GATT scan complete");
    // Now run the read-only raw dump over the characteristics we just collected.
    diag_dump_start();
    return 0;
  }
  if (error->status != 0) {
    ESP_LOGW(TAG, "diag disc_all_chrs error 0x%x", error->status);
    return 0;
  }
  if (chr != nullptr) {
    DiagChar dc;
    dc.def_handle = chr->def_handle;
    dc.val_handle = chr->val_handle;
    dc.props = chr->properties;
    // Redact only device-UNIQUE identifiers (value to DEBUG, not the public INFO
    // log): Serial Number 0x2a25 and System ID 0x2a23 (a MAC-derived EUI). Model
    // number, firmware/software revision and manufacturer stay at INFO - they are
    // per-model diagnostics, not per-bike identifiers.
    dc.redact = (chr->uuid.u.type == BLE_UUID_TYPE_16 &&
                 (chr->uuid.u16.value == 0x2a25 || chr->uuid.u16.value == 0x2a23));
    ble_uuid_to_str(&chr->uuid.u, dc.uuid);
    g_diag_chars.push_back(dc);
    ESP_LOGI(TAG, "GATT scan: characteristic %s def=0x%04x val=0x%04x props=0x%02x",
             dc.uuid, chr->def_handle, chr->val_handle, chr->properties);
  }
  return 0;
}

// ---- One-time read-only raw dump (issue #42) -------------------------------
// NimBLE allows only ONE client procedure per connection at a time, so we walk
// the collected characteristics strictly sequentially: each callback starts the
// next step. Pass 1 reads every readable characteristic once; pass 2 subscribes
// to every notify characteristic (find its CCCD, write 0x0001). The LDI eb21 is
// skipped in both passes (already read + subscribed by the normal path), and the
// write-only 00000012 is never touched (no READ and no NOTIFY bit).
// End handle of the service that owns `handle` (0xffff if unknown). Used to keep
// a CCCD descriptor scan strictly inside the owning service.
static uint16_t diag_service_end_for(uint16_t handle) {
  for (const DiagSvc &s : g_diag_svcs) {
    if (handle >= s.start && handle <= s.end) return s.end;
  }
  return 0xffff;
}

static void diag_dump_start() {
  ESP_LOGI(TAG, "Starting read-only raw dump of %u characteristics (issue #42)",
           (unsigned) g_diag_chars.size());
  g_diag_idx = 0;
  diag_read_next();
}

static void diag_read_next() {
  if (g_conn.conn_handle == BLE_HS_CONN_HANDLE_NONE) return;  // link dropped mid-dump
  while (g_diag_idx < g_diag_chars.size()) {
    const DiagChar &c = g_diag_chars[g_diag_idx];
    if ((c.props & CHR_PROP_READ) && c.val_handle != g_conn.live_chr_val_handle) {
      int rc = ble_gattc_read(g_conn.conn_handle, c.val_handle, on_diag_read, nullptr);
      if (rc == 0) return;  // wait for callback; index NOT advanced yet
      ESP_LOGW(TAG, "GATT dump: read start failed for %s: %d", c.uuid, rc);
    }
    g_diag_idx++;  // not readable, is the LDI char, or read failed to start
  }
  // Reads done -> begin the subscribe pass.
  g_diag_idx = 0;
  diag_subscribe_next();
}

static int on_diag_read(uint16_t conn_handle, const struct ble_gatt_error *error,
                        struct ble_gatt_attr *attr, void *arg) {
  if (g_diag_idx >= g_diag_chars.size()) return 0;  // defensive
  const DiagChar &c = g_diag_chars[g_diag_idx];
  if (error != nullptr && error->status != 0) {
    ESP_LOGW(TAG, "GATT dump: read failed for %s status=0x%x", c.uuid, error->status);
  } else if (attr != nullptr && attr->om != nullptr) {
    uint16_t len = OS_MBUF_PKTLEN(attr->om);
    uint8_t buf[64];
    uint16_t n = len < sizeof(buf) ? len : sizeof(buf);
    os_mbuf_copydata(attr->om, 0, n, buf);
    if (c.redact) {
      // Device-unique identifier (Serial Number / System ID): can identify the
      // bike. Keep it out of the default INFO log (which a user may paste
      // publicly); the value goes to DEBUG only.
      ESP_LOGI(TAG, "GATT dump: read %s handle=0x%04x len=%u (identifying value at DEBUG)",
               c.uuid, attr->handle, len);
      log_hex("  id", buf, n);
    } else {
      diag_log_value("read", c.uuid, attr->handle, buf, n);
    }
  }
  g_diag_idx++;
  diag_read_next();
  return 0;
}

static void diag_subscribe_next() {
  if (g_conn.conn_handle == BLE_HS_CONN_HANDLE_NONE) return;  // link dropped mid-dump
  while (g_diag_idx < g_diag_chars.size()) {
    const DiagChar &c = g_diag_chars[g_diag_idx];
    if ((c.props & CHR_PROP_NOTIFY) && c.val_handle != g_conn.live_chr_val_handle &&
        c.val_handle != 0xffff) {
      // NimBLE's disc_all_dscs scans (start_handle, end_handle] - it begins AFTER
      // start_handle - so we pass the value handle itself as the anchor (exactly
      // like the proven eb21 path in on_disc_dsc). Passing val_handle+1 made the
      // internal request start at val_handle+2 > end -> synchronous EINVAL (3).
      // end is bounded to the owning service (and tightened to the next char) so
      // a CCCD write can never target a descriptor outside this characteristic.
      uint16_t start = c.val_handle;
      uint16_t end = diag_service_end_for(c.def_handle);
      if (g_diag_idx + 1 < g_diag_chars.size()) {
        uint16_t next_def = g_diag_chars[g_diag_idx + 1].def_handle;
        if (next_def > 0 && (uint16_t) (next_def - 1) < end) end = (uint16_t) (next_def - 1);
      }
      g_diag_pending_cccd = 0;
      if (end > c.val_handle) {  // at least one handle after the value -> room for a CCCD
        int rc = ble_gattc_disc_all_dscs(g_conn.conn_handle, start, end,
                                         on_diag_sub_dsc, nullptr);
        if (rc == 0) return;  // wait for descriptor discovery
        ESP_LOGW(TAG, "GATT dump: dsc disc start failed for %s: %d", c.uuid, rc);
      }
    }
    g_diag_idx++;
  }
  ESP_LOGI(TAG, "GATT raw dump complete (read all readable, subscribed all notify)");
}

static int on_diag_sub_dsc(uint16_t conn_handle, const struct ble_gatt_error *error,
                           uint16_t chr_val_handle,
                           const struct ble_gatt_dsc *dsc, void *arg) {
  if (error == nullptr) return 0;
  if (error->status == BLE_HS_EDONE) {
    // Descriptor discovery for this char finished. If we found a CCCD, enable
    // notifications now. (Writing inside the disc callback would collide with the
    // still-active procedure, so the write is deferred to here.)
    if (g_diag_pending_cccd != 0) {
      uint16_t cccd = g_diag_pending_cccd;
      g_diag_pending_cccd = 0;
      uint8_t value[2] = {0x01, 0x00};  // enable notifications
      int rc = ble_gattc_write_flat(conn_handle, cccd, value, sizeof(value),
                                    on_diag_sub_write, nullptr);
      if (rc == 0) return 0;  // wait for write callback
      ESP_LOGW(TAG, "GATT dump: CCCD write start failed: %d", rc);
    }
    g_diag_idx++;
    diag_subscribe_next();
    return 0;
  }
  if (error->status != 0) {
    g_diag_pending_cccd = 0;
    g_diag_idx++;
    diag_subscribe_next();
    return 0;
  }
  if (dsc != nullptr && dsc->uuid.u.type == BLE_UUID_TYPE_16 &&
      dsc->uuid.u16.value == 0x2902) {
    g_diag_pending_cccd = dsc->handle;  // CCCD; write happens on EDONE above
  }
  return 0;
}

static int on_diag_sub_write(uint16_t conn_handle, const struct ble_gatt_error *error,
                             struct ble_gatt_attr *attr, void *arg) {
  if (g_diag_idx < g_diag_chars.size()) {
    const DiagChar &c = g_diag_chars[g_diag_idx];
    if (error != nullptr && error->status != 0) {
      ESP_LOGW(TAG, "GATT dump: subscribe failed for %s status=0x%x", c.uuid, error->status);
    } else {
      ESP_LOGI(TAG, "GATT dump: subscribed to %s (notify); any data appears as 'notify (non-LDI)'",
               c.uuid);
    }
  }
  g_diag_idx++;
  diag_subscribe_next();
  return 0;
}

// ---- ESPHome Component lifecycle -------------------------------------------
void BoschEbikeLdi::setup() {
  g_instance = this;
  g_device_name_cache = this->device_name_;

  ESP_LOGI(TAG, "Initializing Bosch eBike LDI bridge (v0.1)");

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

void BoschEbikeLdi::loop() {
  if (this->connection_dirty_) {
    this->connection_dirty_ = false;
    bool s = this->pending_connected_state_;
    if (s != this->last_published_connected_) {
      this->last_published_connected_ = s;
      if (this->connected_sensor_ != nullptr) {
        this->connected_sensor_->publish_state(s);
      }
      ESP_LOGI(TAG, "Connection state -> %s", s ? "connected" : "disconnected");
    }
  }
  if (this->data_dirty_) {
    this->data_dirty_ = false;
    this->publish_decoded_();
  }

  // Pairing window auto-expiry: once it lapses and we are not connected, drop
  // back to private (non-discoverable, whitelist) advertising so the bridge
  // stops being visible to other users' Flow apps.
  if (g_pairing_until_ms != 0 && (int32_t) (g_pairing_until_ms - millis()) <= 0) {
    g_pairing_until_ms = 0;
    if (!this->last_published_connected_) {
      ESP_LOGI(TAG, "Pairing window expired -> private reconnect advertising");
      ble_gap_adv_stop();
      start_advertising();
    }
  }
}

void BoschEbikeLdi::publish_decoded_() {
  // Convert raw scales into HA-friendly units. Each sensor publishes
  // unconditionally (ESPHome itself dedupes on equal values).
  if (this->latest_.speed_present && this->speed_sensor_) {
    this->speed_sensor_->publish_state(this->latest_.speed_raw / 100.0f);
  }
  if (this->latest_.cadence_present && this->cadence_sensor_) {
    this->cadence_sensor_->publish_state(this->latest_.cadence);
  }
  if (this->latest_.rider_power_present && this->rider_power_sensor_) {
    this->rider_power_sensor_->publish_state(this->latest_.rider_power);
  }
  if (this->latest_.ambient_brightness_present && this->ambient_brightness_sensor_) {
    this->ambient_brightness_sensor_->publish_state(this->latest_.ambient_brightness_raw / 1000.0f);
  }
  if (this->latest_.battery_soc_present && this->battery_soc_sensor_) {
    this->battery_soc_sensor_->publish_state(this->latest_.battery_soc);
  }
  if (this->latest_.odometer_present && this->odometer_sensor_) {
    // publish in km (one decimal will be obvious in HA)
    this->odometer_sensor_->publish_state(this->latest_.odometer / 1000.0f);
  }

  if (this->latest_.bike_light_present && this->light_sensor_) {
    // 1 = OFF, 2 = ON, 0 = INVALID -> treat invalid as off
    this->light_sensor_->publish_state(this->latest_.bike_light == 2);
  }
  if (this->latest_.system_locked_present && this->system_locked_sensor_) {
    // HA device_class=lock: ON=unlocked, OFF=locked. We invert here so
    // the user sees "Abgeschlossen" when the bike is actually locked.
    this->system_locked_sensor_->publish_state(!this->latest_.system_locked);
  }
  if (this->latest_.charger_connected_present && this->charger_connected_sensor_) {
    this->charger_connected_sensor_->publish_state(this->latest_.charger_connected);
  }
  if (this->latest_.light_reserve_present && this->light_reserve_sensor_) {
    this->light_reserve_sensor_->publish_state(this->latest_.light_reserve);
  }
  if (this->latest_.diagnosis_active_present && this->diagnosis_active_sensor_) {
    this->diagnosis_active_sensor_->publish_state(this->latest_.diagnosis_active);
  }
  if (this->latest_.bike_not_driving_present && this->bike_in_motion_sensor_) {
    // Spec field is "bike_not_driving" – we expose the inverse, "in motion"
    this->bike_in_motion_sensor_->publish_state(!this->latest_.bike_not_driving);
  }
}

void BoschEbikeLdi::dump_config() {
  ESP_LOGCONFIG(TAG, "Bosch eBike LDI Bridge:");
  ESP_LOGCONFIG(TAG, "  Device name: %s", this->device_name_.c_str());
  ESP_LOGCONFIG(TAG, "  Service UUID: 0000eb20-eaa2-11e9-81b4-2a2ae2dbcce4");
  ESP_LOGCONFIG(TAG, "  Live Data Char: 0000eb21-eaa2-11e9-81b4-2a2ae2dbcce4");
  ESP_LOGCONFIG(TAG, "  Appearance: 0x0480 (Cycling)");
  ESP_LOGCONFIG(TAG, "  Status: v0.5 – private advertising + manual pairing window (issue #36)");
}

float BoschEbikeLdi::get_setup_priority() const {
  return setup_priority::AFTER_WIFI;
}

void BoschEbikeLdi::on_connect_state_change(bool connected) {
  this->pending_connected_state_ = connected;
  this->connection_dirty_ = true;
  if (!connected) {
    // Reset "present" flags so stale values don't get re-published on reconnect.
    this->latest_ = LiveData{};
  }
}

void BoschEbikeLdi::on_live_data_notify(const uint8_t *data, size_t len) {
  LiveData snapshot;
  if (!decode_live_data(data, len, snapshot)) {
    ESP_LOGW(TAG, "Protobuf decode failed (len=%u)", (unsigned) len);
    return;
  }

  // Merge into latest_: only overwrite fields that were actually present
  // in this notification (per Spec §2.2.4.3).
  if (snapshot.speed_present)              { latest_.speed_present = true;              latest_.speed_raw = snapshot.speed_raw; }
  if (snapshot.cadence_present)            { latest_.cadence_present = true;            latest_.cadence = snapshot.cadence; }
  if (snapshot.rider_power_present)        { latest_.rider_power_present = true;        latest_.rider_power = snapshot.rider_power; }
  if (snapshot.ambient_brightness_present) { latest_.ambient_brightness_present = true; latest_.ambient_brightness_raw = snapshot.ambient_brightness_raw; }
  if (snapshot.battery_soc_present)        { latest_.battery_soc_present = true;        latest_.battery_soc = snapshot.battery_soc; }
  if (snapshot.time_present)               { latest_.time_present = true;               latest_.time = snapshot.time; }
  if (snapshot.odometer_present)           { latest_.odometer_present = true;           latest_.odometer = snapshot.odometer; }
  if (snapshot.bike_light_present)         { latest_.bike_light_present = true;         latest_.bike_light = snapshot.bike_light; }
  if (snapshot.system_locked_present)      { latest_.system_locked_present = true;      latest_.system_locked = snapshot.system_locked; }
  if (snapshot.charger_connected_present)  { latest_.charger_connected_present = true;  latest_.charger_connected = snapshot.charger_connected; }
  if (snapshot.light_reserve_present)      { latest_.light_reserve_present = true;      latest_.light_reserve = snapshot.light_reserve; }
  if (snapshot.diagnosis_active_present)   { latest_.diagnosis_active_present = true;   latest_.diagnosis_active = snapshot.diagnosis_active; }
  if (snapshot.bike_not_driving_present)   { latest_.bike_not_driving_present = true;   latest_.bike_not_driving = snapshot.bike_not_driving; }

  this->data_dirty_ = true;
}

void BoschEbikeLdi::clear_bonding() {
  ESP_LOGW(TAG, "Clearing all bonded peers from NVS");
  ble_store_clear();
}

void BoschEbikeLdi::start_pairing() {
  g_pairing_until_ms = millis() + PAIRING_WINDOW_MS;
  ESP_LOGI(TAG, "Pairing window opened for %u min - discoverable for Flow app",
           (unsigned) (PAIRING_WINDOW_MS / 60000));
  // Re-advertise in pairing mode now (drop any private advertising first).
  // Only touch GAP once the stack is up; before sync on_stack_sync() handles it.
  if (g_ble_synced) {
    ble_gap_adv_stop();
    start_advertising();
  }
}

bool BoschEbikeLdi::is_pairing() { return pairing_window_open(); }

void BoschEbikeLdi::set_advertising_enabled(bool enabled) {
  g_adv_enabled = enabled;
  ESP_LOGI(TAG, "Advertising master switch -> %s", enabled ? "ON" : "OFF");
  // Re-evaluate immediately (no effect while connected; advertising is off
  // during a connection and the new state applies on the next disconnect).
  // Guard on g_ble_synced: the HA switch restores its persisted state during
  // early boot, before the NimBLE stack is up — calling GAP/the bond store then
  // crashes (Issue #41). on_stack_sync() applies the current g_adv_enabled.
  if (g_ble_synced && !this->last_published_connected_) {
    ble_gap_adv_stop();
    start_advertising();
  }
}

bool BoschEbikeLdi::advertising_enabled() { return g_adv_enabled; }

}  // namespace bosch_ebike_ldi
}  // namespace esphome

#endif  // USE_ESP32
