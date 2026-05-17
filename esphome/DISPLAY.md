# eBike Display (JC4827W543) - Setup Guide

A companion firmware that turns a Guition/Sunton **JC4827W543** smart display
(ESP32-S3, 4.3" IPS QSPI 480x272, GT911 touch) into a dashboard for the
existing Bosch eBike LDI bridge. The display is read-only: it pulls live
sensor values, time, and weather from your Home Assistant instance and
renders them. It does **not** open its own BLE link to the bike, so it
never conflicts with the existing bridge pairing.

Supports **one or two bikes** out of the box. Single-bike users see one
page; two-bike users get a swipeable two-page layout with a small page
indicator at the bottom.

## What you see on the display

- **Header** (top): date and current time
- **Weather strip**: today's high/low + current temperature + icon, plus tomorrow's outlook
- **Bike card**: name, odometer, state of charge with bar, charging status, last-seen timestamp
- **Page indicator** (bottom, only shown when two bikes are configured)

## Hardware

- Guition / Sunton **JC4827W543** ("ESP32-S3 4.3 inch capacitive smart display")
- USB-C power supply, 5 V / 1 A or better
- A spot to put it (it is wall- or stand-mounted, USB only, no battery)

Other JC4827W543-class boards (ESP32-S3 + NV3041A + GT911) may work with
small pin-map tweaks. Verify against your board's schematic before
expecting a clean boot.

## Flashing

1. Open <https://xunil99.github.io/ha-bosch-ebike/> in Chrome or Edge on a
   desktop computer.
2. Connect the JC4827W543 via USB-C.
3. Click **"Install display onto JC4827W543"**.
4. After flashing the device boots into Improv-Serial WiFi setup. Pick
   your network and enter credentials in the browser dialog.
5. The display now shows a setup placeholder. Adopt it in Home Assistant
   under **Settings -> Devices & services**.

## Configuring entities

After adopting the device, edit the YAML in the ESPHome dashboard and
fill in the `substitutions` block to point at your existing HA entities.

```yaml
substitutions:
  weather_entity: weather.home
  weather_temp_entity: sensor.outside_temperature
  weather_today_high_entity: sensor.weather_today_high
  weather_today_low_entity: sensor.weather_today_low
  weather_tomorrow_high_entity: sensor.weather_tomorrow_high
  weather_tomorrow_low_entity: sensor.weather_tomorrow_low
  weather_tomorrow_condition_entity: sensor.weather_tomorrow_condition

  bike_a_name: "Performance Line CX"
  bike_a_soc_entity: sensor.ebike_battery_soc_live
  bike_a_odo_entity: sensor.ebike_odometer_live
  bike_a_charging_entity: binary_sensor.ebike_charger_connected
  bike_a_connected_entity: binary_sensor.ebike_connected
  bike_a_last_seen_entity: sensor.ebike_last_seen

  # Bike B is optional, leave the strings empty for single-bike mode.
  bike_b_name: ""
  bike_b_soc_entity: ""
  bike_b_odo_entity: ""
  bike_b_charging_entity: ""
  bike_b_connected_entity: ""
  bike_b_last_seen_entity: ""
```

Click **Install** in the ESPHome dashboard to OTA the updated config.

## Weather forecast helpers (required)

Home Assistant migrated forecasts to the `weather.get_forecasts` service
in 2024. Direct attribute reads on `weather.*` entities frequently return
empty data. The display therefore reads pre-computed helper sensors that
you create once in HA.

Drop the following into your `configuration.yaml` and adjust the
`weather.home` entity ID:

```yaml
template:
  - trigger:
      - platform: time_pattern
        minutes: "/30"
      - platform: homeassistant
        event: start
    action:
      - service: weather.get_forecasts
        data:
          type: daily
        target:
          entity_id: weather.home
        response_variable: forecast
    sensor:
      - name: "Weather Today High"
        unique_id: weather_today_high
        unit_of_measurement: "°C"
        state: "{{ forecast['weather.home'].forecast[0].temperature }}"
      - name: "Weather Today Low"
        unique_id: weather_today_low
        unit_of_measurement: "°C"
        state: "{{ forecast['weather.home'].forecast[0].templow }}"
      - name: "Weather Tomorrow High"
        unique_id: weather_tomorrow_high
        unit_of_measurement: "°C"
        state: "{{ forecast['weather.home'].forecast[1].temperature }}"
      - name: "Weather Tomorrow Low"
        unique_id: weather_tomorrow_low
        unit_of_measurement: "°C"
        state: "{{ forecast['weather.home'].forecast[1].templow }}"
      - name: "Weather Tomorrow Condition"
        unique_id: weather_tomorrow_condition
        state: "{{ forecast['weather.home'].forecast[1].condition }}"
```

Reload templates (or restart HA) and the five helper entities appear.
Their names must match the `weather_*_entity` substitutions in the
display YAML.

## Backlight behaviour

- Full brightness when the screen has been touched within the last minute
- 30 % after 60 s without touch
- 5 % after 5 minutes without touch

This avoids burn-in on the IPS panel and is easy on the eyes at night.
Tap once anywhere to wake.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Display stays black after flash | Pin map differs on your board revision | Verify `clk_pin`, `data_pins`, `cs_pin`, backlight pin against the schematic and adjust `display-jc4827w543.yaml` |
| Touch coordinates flipped or mirrored | Different panel orientation revision | Toggle `mirror_x` / `mirror_y` under `touchscreen:` |
| "..." stays in date/time | HA not yet connected | Adopt the device in HA so the API link comes up |
| Weather values are "nan" | Helper sensors missing | See "Weather forecast helpers" section above |
| Bike values show "n/v" | Bridge offline or entity IDs wrong | Check `substitutions:` block, check the bridge's ESPHome status in HA |

## Versioning

Display firmware tags use the prefix `display-vX.Y.Z` so the display and
the bridge can be released independently. The bridge keeps the
unprefixed `vX.Y.Z` scheme.

## Out of scope (for now)

- More than two bikes per display
- Sending commands back to the bike from the display
- Battery / mobile operation (the device is USB-C stationary)
- LVGL charts of historical SoC or odometer (planned for v2)
