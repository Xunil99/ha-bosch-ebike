#pragma once

#ifdef USE_ESP32

#include "esphome/core/component.h"
#include "esphome/components/binary_sensor/binary_sensor.h"
#include "esphome/components/sensor/sensor.h"
#include "livedata_decoder.h"
#include <string>
#include <cstdint>

namespace esphome {
namespace bosch_ebike_ldi {

extern const uint8_t LDI_SERVICE_UUID128[16];
extern const uint8_t LDI_LIVE_DATA_CHR_UUID128[16];
static constexpr uint16_t LDI_APPEARANCE_CYCLING = 0x0480;

class BoschEbikeLdi : public Component {
 public:
  void setup() override;
  void loop() override;
  void dump_config() override;
  float get_setup_priority() const override;

  void set_device_name(const std::string &name) { this->device_name_ = name; }

  // ---- Sensor wiring (set from sensor.py / binary_sensor.py codegen) ----
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

  // ---- Called from NimBLE callback context ----
  void on_connect_state_change(bool connected);
  void on_live_data_notify(const uint8_t *data, size_t len);

  void clear_bonding();

 protected:
  std::string device_name_{"HA eBike Bridge"};

  // Connection state plumbing
  bool pending_connected_state_{false};
  bool last_published_connected_{false};
  bool connection_dirty_{false};

  // Last decoded values (held across notifications since fields may be sparse)
  LiveData latest_;
  bool data_dirty_{false};

  // Sensors
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

  void publish_decoded_();
};

}  // namespace bosch_ebike_ldi
}  // namespace esphome

#endif
