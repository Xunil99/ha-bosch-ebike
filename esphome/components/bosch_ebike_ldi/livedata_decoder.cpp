#include "livedata_decoder.h"

namespace esphome {
namespace bosch_ebike_ldi {

namespace {

// Reads a base-128 varint at `*pos`, advancing `*pos`. Returns false on truncation.
bool read_varint(const uint8_t *data, size_t len, size_t *pos, uint64_t *out) {
  uint64_t result = 0;
  int shift = 0;
  while (*pos < len) {
    uint8_t b = data[(*pos)++];
    result |= ((uint64_t) (b & 0x7f)) << shift;
    if ((b & 0x80) == 0) {
      *out = result;
      return true;
    }
    shift += 7;
    if (shift >= 64) return false;  // varint too long
  }
  return false;
}

// Skips one field's value of the given wire type, advancing `*pos`.
bool skip_value(const uint8_t *data, size_t len, size_t *pos, uint32_t wire_type) {
  switch (wire_type) {
    case 0: {  // varint
      uint64_t dummy;
      return read_varint(data, len, pos, &dummy);
    }
    case 1: {  // 64-bit
      if (*pos + 8 > len) return false;
      *pos += 8;
      return true;
    }
    case 2: {  // length-delimited
      uint64_t l;
      if (!read_varint(data, len, pos, &l)) return false;
      if (*pos + l > len) return false;
      *pos += (size_t) l;
      return true;
    }
    case 5: {  // 32-bit
      if (*pos + 4 > len) return false;
      *pos += 4;
      return true;
    }
    default:
      return false;
  }
}

// Sign-magnitude decoding for proto int32: protobuf stores negative ints
// as their two's-complement uint64 -> just truncate to int32.
inline int32_t to_int32(uint64_t v) { return (int32_t) v; }

}  // namespace

bool decode_live_data(const uint8_t *data, size_t len, LiveData &out) {
  size_t pos = 0;
  while (pos < len) {
    uint64_t tag;
    if (!read_varint(data, len, &pos, &tag)) return false;
    uint32_t field_no = (uint32_t) (tag >> 3);
    uint32_t wire_type = (uint32_t) (tag & 0x07);

    // All fields we care about are wire_type=0 (varint).
    if (wire_type != 0) {
      if (!skip_value(data, len, &pos, wire_type)) return false;
      continue;
    }

    uint64_t v;
    if (!read_varint(data, len, &pos, &v)) return false;

    switch (field_no) {
      case 1:   out.speed_present = true;              out.speed_raw = (uint32_t) v;             break;
      case 2:   out.cadence_present = true;            out.cadence = to_int32(v);                break;
      case 5:   out.rider_power_present = true;        out.rider_power = (uint32_t) v;           break;
      case 9:   out.ambient_brightness_present = true; out.ambient_brightness_raw = (uint32_t) v; break;
      case 10:  out.battery_soc_present = true;        out.battery_soc = (uint32_t) v;           break;
      case 11:  out.time_present = true;               out.time = (int64_t) v;                   break;
      case 12:  out.odometer_present = true;           out.odometer = (uint32_t) v;              break;
      case 17:  out.bike_light_present = true;         out.bike_light = (uint32_t) v;            break;
      case 21:  out.system_locked_present = true;      out.system_locked = (v != 0);             break;
      case 22:  out.charger_connected_present = true;  out.charger_connected = (v != 0);         break;
      case 23:  out.light_reserve_present = true;      out.light_reserve = (v != 0);             break;
      case 24:  out.diagnosis_active_present = true;   out.diagnosis_active = (v != 0);          break;
      case 25:  out.bike_not_driving_present = true;   out.bike_not_driving = (v != 0);          break;
      default:
        // Unknown field – proto3 says ignore.
        break;
    }
  }
  return true;
}

}  // namespace bosch_ebike_ldi
}  // namespace esphome
