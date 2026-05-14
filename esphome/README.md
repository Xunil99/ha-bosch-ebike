# Bosch eBike Live Data Interface – ESPHome Bridge

ESPHome external component that turns an ESP32 into a Bluetooth bridge for the
**Bosch eBike Live Data Interface (LDI)** - the BLE GATT service introduced with
smart system control unit release **v19** (May 2026).

The bridge advertises itself as a Cycling-class accessory, lets the eBike pair
with it (LE Secure Connections, Just Works), reads the live data characteristic
once for the full snapshot and then receives notifications. All 13 LiveData
fields are exposed as Home Assistant entities through ESPHome's native API.

> **Available languages / Sprachen:** [English](#english) · [Deutsch](#deutsch)

---

## Quick install (no ESPHome required)

If you just want to get the bridge running, the easiest path is the **web installer**: plug an ESP32 into your computer via USB, open the page below in Chrome or Edge and click *Install*. Firmware and WiFi setup happen entirely in the browser, no ESPHome installation needed on your side.

➡️ **https://xunil99.github.io/ha-bosch-ebike/**

The page is bilingual (DE/EN) and walks through the full flow including the Flow App pairing step. Everything below this section is for users who want to customize the YAML themselves or build from source.

---

## English

### What you get

| Entity | Type | Unit |
|---|---|---|
| `sensor.ebike_speed` | numeric | km/h |
| `sensor.ebike_cadence` | numeric | rpm |
| `sensor.ebike_rider_power` | numeric | W |
| `sensor.ebike_ambient_brightness` | numeric | lx |
| `sensor.ebike_battery_soc_live` | numeric | % |
| `sensor.ebike_odometer_live` | numeric | km |
| `binary_sensor.ebike_connected` | bool | connectivity |
| `binary_sensor.ebike_light` | bool | light |
| `binary_sensor.ebike_system_locked` | bool | lock |
| `binary_sensor.ebike_charger_connected` | bool | plug |
| `binary_sensor.ebike_light_reserve` | bool | problem |
| `binary_sensor.ebike_diagnosis_active` | bool | – |
| `binary_sensor.ebike_in_motion` | bool | motion |

### Prerequisites

- **eBike**: Bosch smart system with control unit firmware **v19 or newer**.
  Check via Bosch Flow App → your bike → settings → system info → drive unit
  software version. If you see ≥ 19.x.x, you are good. The Live Data Interface
  is unavailable on older firmware.
- **Range**: BLE only. Park your bike within ~10 m line-of-sight of the bridge.
  Walls and metal cabinets reduce range significantly. A garage / shed where
  you park is the natural location.
- **Hardware**: Any ESP32 dev kit with built-in Bluetooth Low Energy
  (e.g. ESP32-WROOM-32, ESP32-DevKitC). ESP32-S2 is **not** supported (no BT).
  ESP32-C3 / -S3 / -C6 should also work but have not been tested.
- **Software**: Home Assistant with the **ESPHome** add-on or a standalone
  ESPHome installation. Tested with ESPHome 2026.4.5.

### 1. Install ESPHome

If you do not already run ESPHome, install the official add-on from the Home
Assistant add-on store. Open the ESPHome dashboard once so that the
configuration directory `/config/esphome/` exists.

### 2. Drop the YAML in place

Only one file is strictly required: `example-bridge.yaml`. Copy it into your
ESPHome configuration directory and rename it (e.g. `ebike-bridge.yaml`):

```
/config/esphome/
└── ebike-bridge.yaml
```

By default the YAML pulls the bridge component **directly from this GitHub
repository** on every compile via:

```yaml
external_components:
  - source: github://Xunil99/ha-bosch-ebike@main
    components: [bosch_ebike_ldi]
    refresh: 1d
```

That way the bridge updates in lockstep with the HA integration whenever you
recompile - no manual file copies, no version drift. Pin to a tag
(e.g. `@v1.10.0`) instead of `@main` if you want reproducible builds.

#### Offline / air-gapped alternative

If your ESPHome host has no internet during compile, copy the
`esphome/components/bosch_ebike_ldi/` folder from the repo next to your YAML:

```
/config/esphome/
├── ebike-bridge.yaml
└── components/
    └── bosch_ebike_ldi/
        ├── __init__.py
        ├── binary_sensor.py
        ├── sensor.py
        ├── bosch_ebike_ldi.h
        ├── bosch_ebike_ldi.cpp
        ├── livedata_decoder.h
        └── livedata_decoder.cpp
```

…and switch the YAML to the local source variant (the comment block in
`example-bridge.yaml` shows exactly how).

### 3. Adjust the YAML

Open `ebike-bridge.yaml` and change at minimum:

- `name:` and `friendly_name:` - anything you like.
- The list of sensors / binary sensors - you can drop the ones you do not need.

The `wifi:` block uses `!secret wifi_ssid` / `wifi_password`. If you do not yet
have a `secrets.yaml`, create one in `/config/esphome/` with your Wi-Fi
credentials. ESPHome's add-on UI offers a "Secrets" editor for this.

### 4. Compile and flash

In the ESPHome dashboard: pick the bridge entry → "Install".

- **First flash**: choose "Plug into the computer running ESPHome" (USB-C
  cable) - OTA does not work yet because no firmware is on the ESP32.
- **Subsequent flashes**: pick "Wirelessly" - OTA over Wi-Fi.

The first compile takes ~5 minutes (PlatformIO downloads NimBLE and the
toolchain). Later compiles are quick.

### 5. Pair the bridge with the eBike

This is the only step you really have to be careful about - the rest is set
and forget.

1. Power the eBike on, make sure the bridge has booted (you should see it in
   the Bosch Flow App's BLE neighborhood, but you do not need to interact with
   it from there yet).
2. In the **Bosch Flow App**, open your bike, then tap the **gear icon (⚙)
   in the top-right corner** to open the bike settings.
3. Tap **"Komponenten"** ("Components" in English-localized apps).
4. Tap **"Neues Gerät hinzufügen"** ("Add new device" / "Add component").
5. The Flow App now triggers the eBike's "scan-for-accessory" mode. Within
   ~30 seconds the bike should discover **"HA eBike Bridge"** in the list.
6. Confirm the pairing on the bike's display when prompted (Just Works
   pairing - no PIN needed, the bike handles bonding automatically).

That's it - the bridge is now permanently bonded to the eBike. From now on,
the bike will reconnect automatically every time it powers on while in range
of the bridge. The bond is stored in the ESP32's flash and survives reboots
and OTA updates.

### 6. Use the data in Home Assistant

The ESPHome integration auto-discovers the bridge. Each time the bike
connects, the bridge issues an initial GATT read so HA gets a full snapshot
straight away (battery SoC, odometer, light state, …). Then it follows
notifications for changes.

Combined with the
[`ha_bosch_ebike` cloud integration](https://github.com/Xunil99/ha-bosch-ebike)
(in this same repository), you get the best of both worlds: cloud-side tour
history and the live BLE data when the bike is at home.

### Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `ebike connected` never goes on | Out of range, or eBike firmware < v19 | Move bridge closer; verify firmware version in Flow App |
| Pairing fails (encryption status ≠ 0 in log) | Stale bond on the bridge or in the eBike | Press the **eBike Clear Bonding** button in HA, remove the accessory in Flow App, repeat the pairing flow |
| Battery SoC / Speed stay "Unknown" after first connect | Bike firmware regression - initial read returned empty | Disconnect / reconnect (toggle bike power); upgrade to v0.3 of this component if you are on an older snapshot |
| `Advertising started` never appears in the log | NimBLE init failed | Re-flash via USB; check that no other BT-using components (`esp32_ble_tracker`, `bluetooth_proxy`) are in the YAML |
| Compile error `undefined reference to ble_gattc_*` | `CONFIG_BT_NIMBLE_ROLE_CENTRAL: y` missing | Make sure you copied the example YAML verbatim |
| **"API connection issues" in Home Assistant after a successful flash** (firmware compiles and uploads, but HA cannot add the device or the ESPHome API drops) | Board defaults are wrong (typically wrong crystal frequency or partition table). Symptom is flaky WiFi rather than no WiFi. | Add `board: esp32dev` next to `variant: esp32` in the `esp32:` block. The current example YAML already includes both; older copies need updating. |

### Logs to share when filing an issue

Set the component log level to `VERBOSE`:

```yaml
logger:
  level: VERBOSE
  logs:
    bosch_ebike_ldi: VERBOSE
```

…and capture the time window covering one full pairing or reconnect attempt
(boot until first NOTIFY_RX, ideally USB serial so the early NimBLE init is
included).

### Limitations

- The Bosch LDI is read-only: you cannot lock the bike, switch the light, or
  trigger anything from the bridge.
- Only one accessory can connect at a time. If you also use a Bosch sports
  watch / Kiox 500 with LDI, they will compete for the slot.
- The Live Data Interface is marked **experimental** by Bosch in v19. Future
  firmware versions may change behavior.

---

## Deutsch

### Was du bekommst

| Entität | Typ | Einheit |
|---|---|---|
| `sensor.ebike_speed` | Zahl | km/h |
| `sensor.ebike_cadence` | Zahl | rpm |
| `sensor.ebike_rider_power` | Zahl | W |
| `sensor.ebike_ambient_brightness` | Zahl | lx |
| `sensor.ebike_battery_soc_live` | Zahl | % |
| `sensor.ebike_odometer_live` | Zahl | km |
| `binary_sensor.ebike_connected` | bool | connectivity |
| `binary_sensor.ebike_light` | bool | light |
| `binary_sensor.ebike_system_locked` | bool | lock |
| `binary_sensor.ebike_charger_connected` | bool | plug |
| `binary_sensor.ebike_light_reserve` | bool | problem |
| `binary_sensor.ebike_diagnosis_active` | bool | – |
| `binary_sensor.ebike_in_motion` | bool | motion |

### Voraussetzungen

- **eBike**: Bosch smart system mit Steuergerät-Firmware **v19 oder neuer**.
  Prüfen über Bosch Flow App → dein Bike → Einstellungen → Systeminformation
  → Drive-Unit-Software-Version. Steht da ≥ 19.x.x, passt es. Auf älterer
  Firmware existiert das Live Data Interface nicht.
- **Reichweite**: Reines BLE. Das Bike muss in ca. 10 m Luftlinie zur Bridge
  stehen. Wände und Metallschränke verkürzen das deutlich. Eine Garage oder
  ein Gartenhaus, wo das Bike abgestellt ist, ist der typische Aufstellort.
- **Hardware**: Beliebiges ESP32-Devboard mit Bluetooth Low Energy
  (z. B. ESP32-WROOM-32, ESP32-DevKitC). ESP32-S2 funktioniert **nicht** (kein
  BT). ESP32-C3 / -S3 / -C6 sollten gehen, sind aber nicht getestet.
- **Software**: Home Assistant mit dem **ESPHome**-Addon oder eine eigenständige
  ESPHome-Installation. Getestet mit ESPHome 2026.4.5.

### 1. ESPHome installieren

Falls noch nicht vorhanden, das offizielle ESPHome-Addon aus dem Home-Assistant-
Addon-Store installieren. Einmal das ESPHome-Dashboard öffnen, damit das
Konfigurationsverzeichnis `/config/esphome/` angelegt wird.

### 2. YAML einsortieren

Strenggenommen reicht eine einzige Datei: `example-bridge.yaml`. Diese ins
ESPHome-Konfigurationsverzeichnis kopieren und umbenennen
(z. B. `ebike-bridge.yaml`):

```
/config/esphome/
└── ebike-bridge.yaml
```

Standardmäßig zieht die YAML die Bridge-Komponente **direkt aus diesem
GitHub-Repo** bei jedem Compile:

```yaml
external_components:
  - source: github://Xunil99/ha-bosch-ebike@main
    components: [bosch_ebike_ldi]
    refresh: 1d
```

So bewegt sich die Bridge automatisch im Gleichschritt mit der HA-Integration
- kein manuelles Datei-Kopieren, keine Versions-Diskrepanz. Wer reproduzierbare
Builds will, ersetzt `@main` durch ein konkretes Tag (z. B. `@v1.10.0`).

#### Offline-Variante / Air-Gapped

Falls dein ESPHome-Host beim Compile keine Internetverbindung hat, kopiere den
Ordner `esphome/components/bosch_ebike_ldi/` aus dem Repo neben deine YAML:

```
/config/esphome/
├── ebike-bridge.yaml
└── components/
    └── bosch_ebike_ldi/
        ├── __init__.py
        ├── binary_sensor.py
        ├── sensor.py
        ├── bosch_ebike_ldi.h
        ├── bosch_ebike_ldi.cpp
        ├── livedata_decoder.h
        └── livedata_decoder.cpp
```

…und stelle den `external_components:`-Block auf den lokalen Modus um (der
Kommentarblock in `example-bridge.yaml` zeigt genau, wie).

### 3. YAML anpassen

`ebike-bridge.yaml` öffnen und mindestens das hier anpassen:

- `name:` und `friendly_name:` - beliebig.
- Sensor- / Binary-Sensor-Liste - wer einzelne nicht braucht, kann sie
  rauswerfen.

Der `wifi:`-Block verwendet `!secret wifi_ssid` / `wifi_password`. Falls noch
keine `secrets.yaml` existiert, eine in `/config/esphome/` anlegen mit deinen
WLAN-Zugangsdaten. Das ESPHome-Addon hat dafür einen Secrets-Editor.

### 4. Kompilieren und flashen

Im ESPHome-Dashboard: Bridge auswählen → "Install".

- **Erster Flash**: "Plug into the computer running ESPHome" wählen (USB-C-
  Kabel). OTA klappt noch nicht, weil noch keine Firmware auf dem ESP32 ist.
- **Spätere Flashes**: "Wirelessly" - OTA über WLAN.

Der erste Compile dauert ~5 Minuten (PlatformIO lädt NimBLE und die Toolchain).
Folgende sind schnell.

### 5. Bridge mit dem eBike koppeln

Der einzige Schritt, bei dem man kurz aufpassen muss. Danach ist Ruhe.

1. eBike einschalten, Bridge bootet im Hintergrund (sie taucht dann in der
   BLE-Umgebung der Flow App auf, du musst dort aber noch nichts machen).
2. In der **Bosch Flow App** dein Bike öffnen und oben rechts auf das
   **Zahnrad-Symbol (⚙)** tippen, um die Bike-Einstellungen zu öffnen.
3. **„Komponenten"** antippen.
4. **„Neues Gerät hinzufügen"** antippen.
5. Die Flow App löst jetzt am eBike den Such-Modus für neues Zubehör aus.
   Innerhalb von ~30 Sekunden sollte das Bike **„HA eBike Bridge"** in der
   Liste anzeigen.
6. Auf Aufforderung das Pairing am Bike-Display bestätigen (Just-Works-
   Pairing - keine PIN nötig, das Bonding macht das Bike automatisch).

Fertig - die Bridge ist jetzt dauerhaft mit dem eBike gekoppelt. Ab sofort
verbindet sich das Bike bei jedem Einschalten automatisch, sobald es in
Reichweite der Bridge ist. Der Bond liegt im Flash des ESP32 und überlebt
Neustarts und OTA-Updates.

### 6. Daten in Home Assistant nutzen

Die ESPHome-Integration entdeckt die Bridge automatisch. Bei jedem Verbindungs-
aufbau liest die Bridge die Live-Daten-Characteristic einmal aktiv aus, damit
HA sofort einen vollständigen Snapshot bekommt (Akkustand, Tachostand, Licht-
status, …). Danach laufen Notifications für die Deltas.

Zusammen mit der
[`ha_bosch_ebike`-Cloud-Integration](https://github.com/Xunil99/ha-bosch-ebike)
(im selben Repo) hast du das Beste aus beiden Welten: Tour-History aus der
Cloud plus die Live-BLE-Daten, sobald das Bike zu Hause ist.

### Fehlersuche

| Symptom | Wahrscheinliche Ursache | Lösung |
|---|---|---|
| `ebike connected` wird nie aktiv | Außer Reichweite oder Bike-Firmware < v19 | Bridge näher stellen; Firmware in der Flow App prüfen |
| Pairing schlägt fehl (Encryption status ≠ 0 im Log) | Alter Bond auf Bridge oder Bike | In HA den Button **„eBike Clear Bonding"** drücken, in der Flow App das Zubehör entfernen, Pairing neu durchlaufen |
| Akku-SoC / Speed bleiben „Unbekannt" nach erstem Connect | Bike-Firmware-Eigenheit - initialer Read kam leer zurück | Bike aus / einschalten; sicherstellen, dass v0.3 (oder neuer) der Komponente läuft |
| `Advertising started` taucht im Log nie auf | NimBLE-Init fehlgeschlagen | Per USB neu flashen; sicherstellen, dass keine anderen BT-Komponenten (`esp32_ble_tracker`, `bluetooth_proxy`) in der YAML stehen |
| Compile-Fehler `undefined reference to ble_gattc_*` | `CONFIG_BT_NIMBLE_ROLE_CENTRAL: y` fehlt | Prüfen, ob die Beispiel-YAML 1:1 übernommen wurde |
| **„API connection issues" in Home Assistant nach erfolgreichem Flash** (Firmware compilt und uploaded sauber, aber HA kann das Gerät nicht hinzufügen bzw. die ESPHome-API bricht ständig ab) | Falsche Board-Defaults (meist falsche Quarz-Frequenz oder Partitions-Tabelle). Symptom ist instabiles WLAN, nicht „kein WLAN". | `board: esp32dev` neben `variant: esp32` im `esp32:`-Block ergänzen. Die aktuelle Beispiel-YAML enthält beides schon; ältere Kopien müssen aktualisiert werden. |

### Logs für Issues

Komponenten-Loglevel auf `VERBOSE` setzen:

```yaml
logger:
  level: VERBOSE
  logs:
    bosch_ebike_ldi: VERBOSE
```

…und das Zeitfenster eines vollständigen Pairing- oder Reconnect-Versuchs
mitschneiden (vom Bootvorgang bis zum ersten NOTIFY_RX, idealerweise per USB-
Serial damit auch die frühe NimBLE-Init-Phase drin ist).

### Einschränkungen

- Das Bosch-LDI ist nur lesend: Bike abschließen, Licht schalten oder andere
  Aktionen sind über die Bridge nicht möglich.
- Es kann immer nur ein Zubehör gleichzeitig verbunden sein. Wenn du parallel
  eine Bosch-Sports-Watch / einen Kiox 500 mit LDI nutzt, konkurriert das um
  den Slot.
- Bosch markiert das Live Data Interface in v19 als **experimentell**.
  Künftige Firmware-Updates können das Verhalten ändern.

---

## License

Apache-2.0 (matches Bosch's `ebike_live_data.proto` license).
