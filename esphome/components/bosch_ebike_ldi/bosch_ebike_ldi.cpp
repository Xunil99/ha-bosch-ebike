#ifdef USE_ESP32

#include "bosch_ebike_ldi.h"
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
  hex[to_print * 3 ? (to_print * 3 - 1) : 0] = '\0';
  if (len > 64) {
    ESP_LOGD(TAG, "%s len=%u: %s …", prefix, (unsigned) len, hex);
  } else {
    ESP_LOGD(TAG, "%s len=%u: %s", prefix, (unsigned) len, hex);
  }
}

// Build raw advertising payload including Service Solicitation 128-bit (AD 0x15).
// NimBLE's ble_hs_adv_fields struct cannot represent solicitation, so we build
// the byte sequence by hand and pass it to ble_gap_adv_set_data().
static int build_adv_payload(uint8_t *buf, size_t buf_len, size_t *out_len,
                             const std::string &name) {
  size_t pos = 0;
  // 1) Flags: General Discoverable + BR/EDR Not Supported = 0x06
  if (pos + 3 > buf_len) return -1;
  buf[pos++] = 0x02; buf[pos++] = 0x01; buf[pos++] = 0x06;

  // 2) Appearance (LE): Cycling generic = 0x0480
  if (pos + 4 > buf_len) return -1;
  buf[pos++] = 0x03; buf[pos++] = 0x19;
  buf[pos++] = (uint8_t) (LDI_APPEARANCE_CYCLING & 0xff);
  buf[pos++] = (uint8_t) ((LDI_APPEARANCE_CYCLING >> 8) & 0xff);

  // 3) Service Solicitation – 128-bit (AD type 0x15), UUID in little-endian.
  if (pos + 2 + 16 > buf_len) return -1;
  buf[pos++] = 1 + 16; buf[pos++] = AD_TYPE_SOL_UUIDS128;
  memcpy(&buf[pos], LDI_SERVICE_UUID128, 16);
  pos += 16;

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

static int start_advertising() {
  uint8_t adv_buf[31];
  size_t adv_len = 0;
  if (build_adv_payload(adv_buf, sizeof(adv_buf), &adv_len, g_device_name_cache) != 0) {
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
  adv_params.disc_mode = BLE_GAP_DISC_MODE_GEN;
  adv_params.itvl_min = 0;  // use default (~1.28 s)
  adv_params.itvl_max = 0;

  rc = ble_gap_adv_start(BLE_OWN_ADDR_PUBLIC, nullptr, BLE_HS_FOREVER,
                         &adv_params, gap_event_handler, nullptr);
  if (rc != 0) {
    ESP_LOGE(TAG, "ble_gap_adv_start failed: %d", rc);
  } else {
    ESP_LOGI(TAG, "Advertising started – Solicitation eb20, name='%s'",
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
      log_hex("NOTIFY_RX raw", buf, copy_len);
      ESP_LOGI(TAG, "NOTIFY handle=0x%04x len=%u indication=%d",
               handle, len, event->notify_rx.indication);
      if (g_instance) g_instance->on_live_data_notify(buf, copy_len);
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
  ESP_LOGCONFIG(TAG, "  Status: v0.4 – race-fix for bond-resume reconnects");
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

}  // namespace bosch_ebike_ldi
}  // namespace esphome

#endif  // USE_ESP32
