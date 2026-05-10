#pragma once

#include <cstdint>
#include <cstddef>

namespace esphome {
namespace bosch_ebike_ldi {

// Decoded snapshot from a single LiveData notification.
// Each `*_present` flag tells whether the field was contained in this
// particular notification. Per Spec §2.2.4.3, an unchanged field MAY be
// absent or present – clients shall not infer "stale" from absence.
struct LiveData {
  bool speed_present{false};       uint32_t speed_raw{0};        // 1/100 km/h
  bool cadence_present{false};     int32_t  cadence{0};          // rpm
  bool rider_power_present{false}; uint32_t rider_power{0};      // W
  bool ambient_brightness_present{false}; uint32_t ambient_brightness_raw{0}; // 1/1000 lux
  bool battery_soc_present{false}; uint32_t battery_soc{0};      // %
  bool time_present{false};        int64_t  time{0};             // sec since epoch
  bool odometer_present{false};    uint32_t odometer{0};          // m
  bool bike_light_present{false};  uint32_t bike_light{0};        // 0=invalid 1=off 2=on
  bool system_locked_present{false};       bool system_locked{false};
  bool charger_connected_present{false};   bool charger_connected{false};
  bool light_reserve_present{false};       bool light_reserve{false};
  bool diagnosis_active_present{false};    bool diagnosis_active{false};
  bool bike_not_driving_present{false};    bool bike_not_driving{false};
};

// Decodes one LiveData protobuf message. Returns true on success
// (i.e., wire format was parseable). Unknown fields are skipped per
// proto3 forward-compatibility rules.
bool decode_live_data(const uint8_t *data, size_t len, LiveData &out);

}  // namespace bosch_ebike_ldi
}  // namespace esphome
