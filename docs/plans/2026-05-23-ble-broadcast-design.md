# BLE Sensor Broadcast for Bosch eBike Bridge — Design

**Status:** approved (brainstorming complete, ready for implementation plan)
**Scope:** MVP — Battery Service + Cycling Speed and Cadence (cadence only)
**Date:** 2026-05-23

## Goal

The existing `bosch_ebike_ldi` component reads live data from a Bosch Smart
System eBike over BLE (central role) and exposes it as ESPHome sensors,
which propagate to Home Assistant. This design adds a second role: the
ESP32-S3 simultaneously acts as a **BLE peripheral**, advertising standard
Bluetooth-SIG cycling sensor services so that third-party bike computers
— Coros Dura, Garmin, Wahoo, anything that speaks BLE bike sensors — can
pair with the bridge and read live data during a ride. No Home Assistant
required between the eBike and the bike computer.

**Out of scope** for MVP:

- ANT+ (impossible on ESP32 silicon without an external module)
- BLE Cycling Power Service (CPS / 0x1818) — deferred to a follow-up
- Speed broadcasting via CSC — Coros has its own GPS speed
- ANT+ E-Bike Profile #0x4F (would require external ANT+ hardware to label
  data as "eBike" on Coros instead of generic sensor)
- Multi-client broadcast — one Coros at a time is enough

## Why a separate component instead of extending `bosch_ebike_ldi`

A new component `ebike_ble_broadcast` (sibling of `bosch_ebike_ldi`)
keeps the two responsibilities cleanly separated. Existing standalone-
bridge users who do not need broadcasting are unaffected — they neither
load the new component nor pay its flash cost. Users who do want it opt
in via a single YAML block. Both components share the same NimBLE host
stack; only the `CONFIG_BT_NIMBLE_MAX_CONNECTIONS` sdkconfig option needs
to go from `1` to `2` so central (eBike) and peripheral (Coros) can hold
simultaneous links.

## Architecture and data flow

```
Bosch eBike --BLE Central--> bosch_ebike_ldi
                                     |
                                     v (existing publish to ESPHome sensors)
                            sensor.battery_soc
                            sensor.cadence
                                     |
                                     v (new component subscribes)
                            ebike_ble_broadcast
                                     |
                                     v (NimBLE GATT notifications)
                            Coros Dura (BLE Central)
```

The new component runs entirely in `loop()` callbacks plus NimBLE event
handlers. No new task is required. Sensor values are read from the
existing ESPHome sensor objects (`bike_a_soc->get_state()` etc.), so the
update cadence matches whatever rate `bosch_ebike_ldi` already produces
(roughly 1 Hz under normal eBike connection).

## BLE services exposed

| Service | UUID | Characteristic | UUID | Format |
|---|---|---|---|---|
| Battery | 0x180F | Battery Level | 0x2A19 | uint8 0-100, Notify |
| Cycling Speed and Cadence | 0x1816 | CSC Measurement | 0x2A5B | flags + payload, Notify |

**CSC Measurement frame**

```
byte 0:  flags = 0x02  (crank revolutions present, wheel data absent)
byte 1-2: cumulative crank revolutions (uint16, little-endian)
byte 3-4: last crank event time (uint16 LE, 1/1024 s units)
```

Cadence (RPM) → CSC representation: each update increments cumulative
revolutions by `rpm / 60` (rounded, accumulated as float internally) and
the event timestamp by `1024` (= 1 s). Bike computers reconstruct
RPM = `delta_revs * 60 * 1024 / delta_time`. With a steady 1 Hz feed this
yields exactly the same value Coros would compute from a hardware sensor.

Advertising name: configurable via YAML, default `"Bosch eBike Bridge"`.
Advertised service UUIDs: 0x180F and 0x1816 in the advertising payload so
that bike computers' "search for sensors" UI surfaces the device with the
right icon.

## YAML configuration

```yaml
ebike_ble_broadcast:
  id: ebike_broadcast
  advertised_name: "Bosch eBike Bridge"
  battery_soc_id: bike_a_soc      # existing sensor id from bosch_ebike_ldi
  cadence_id: bike_a_cadence      # existing sensor id from bosch_ebike_ldi
```

All three fields default-empty disable the corresponding service — a user
who only wants battery broadcast can leave `cadence_id` unset.

## sdkconfig changes

- `CONFIG_BT_NIMBLE_MAX_CONNECTIONS: "2"` (up from `"1"`) so the bridge
  can hold the eBike central link and the Coros peripheral link
  simultaneously.

Everything else (`CONFIG_BT_NIMBLE_ROLE_CENTRAL`, `_PERIPHERAL`,
`_BROADCASTER`, `_OBSERVER`) is already enabled in `factory.yaml` —
NimBLE was already configured for dual-role even though only central
was used.

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| BLE link contention between Bosch central and Coros peripheral | NimBLE schedules slots cooperatively; expected jitter is sub-second and not user-visible at 1 Hz update rate |
| Coros doesn't find the bridge in sensor scan | Advertise both service UUIDs in payload (not just name) so Coros's filter recognises it as a cadence + battery device |
| Re-bonding loops when ESP32 reboots | Store bond info in NVS via `CONFIG_BT_NIMBLE_NVS_PERSIST=y` (already set in factory.yaml) |
| Flash budget on 4 MB display+bridge merged firmware | New component is ~10-15 KB compiled; current 4 MB build has headroom |
| Cadence reconstruction drift over long rides | Use floating-point accumulator internally, cast to uint16 with proper wrap-around (uint16 wraps every ~18 hours of pedalling — fine) |

## Testing approach

1. **Compile** the component in isolation in a test YAML, confirm it links
   against NimBLE peripheral APIs and the existing component without
   symbol collisions.
2. **Boot test:** advertising starts, name is visible in a generic BLE
   scanner app (nRF Connect on phone).
3. **GATT read test:** read Battery Level from the phone's BLE scanner;
   should return current SOC value.
4. **Notification test:** subscribe to CSC Measurement via phone; should
   receive notifications at ~1 Hz with monotonically increasing crank
   revolution counter when pedalling.
5. **Coros pairing:** Coros Dura → Settings → Sensors → Add → confirm
   "Bosch eBike Bridge" appears with Cadence and Battery sub-types →
   pair → confirm bonding persists across ESP32 reboot.
6. **Real ride test:** put ESP32 on a power bank, ride, watch Coros
   display live cadence + eBike battery percentage.

## Open questions deferred to implementation

- Exact `update_interval` for the CSC notifications — pick something
  between 1 Hz (matches Bosch source rate) and 4 Hz (smoother Coros UI
  but extra BLE airtime). Start with 1 Hz.
- How to expose the broadcasting state to Home Assistant — a binary
  sensor "Coros Connected" could be useful but is YAGNI for MVP.
- Naming: `ebike_ble_broadcast` vs `bosch_ebike_broadcast` vs `bike_ble_sensor`.
  Bikeshed at code-review time.

## Next step

Invoke the `writing-plans` skill to break this design into a concrete
step-by-step implementation plan (component scaffolding, NimBLE GATT
setup, sensor subscription, CSC encoding, integration tests).
