# Taking the bridge on a ride: MQTT + WireGuard

This describes the optional **mobile / roaming** setup, where the ESP travels
with the bike (for example on a powerbank in the frame bag) and still delivers
its data to your Home Assistant at home. It is an addition to the standard
[`example-bridge.yaml`](example-bridge.yaml) (native API), not a replacement.

Config file: [`example-bridge-mobile.yaml`](example-bridge-mobile.yaml).
Secrets template: [`secrets.yaml.example`](secrets.yaml.example).

---

## English

### The idea

```
eBike --BLE--> ESP --WiFi (phone hotspot)--> Internet --WireGuard--> home router --> Home Assistant (MQTT)
```

The ESP joins your phone's hotspot, opens a WireGuard tunnel to your home
router, and pushes the eBike data to your MQTT broker as if it were sitting at
home.

### You do NOT need a WireGuard app on your phone

This trips people up. The tunnel is built **by the ESP itself**, not by the
phone. The phone only provides the hotspot (plain internet). You do not
install WireGuard, Tailscale or any VPN app on the phone, and you do not
configure anything on the phone beyond the hotspot. The ESP is the WireGuard
client.

### Why MQTT instead of the native API

With the native API, **Home Assistant** opens the connection to the ESP and
must know its IP address. On the road that IP keeps changing (hotspot DHCP,
tunnel IP), so HA can no longer reach the device. With **MQTT the ESP pushes**
its data to the broker, so a changing IP does not matter. That is why this
variant uses MQTT, and why only MQTT reliably gets data through the tunnel.

You need an MQTT broker in HA, for example the **Mosquitto** add-on.

### Heads-up: switching from API to MQTT changes your entities

If you previously ran the bridge with `api:`, moving to `mqtt:` means HA
creates the entities through **MQTT discovery** instead of the ESPHome
integration. Practical consequences:

- The old device appears under the **ESPHome** integration and will go
  **unavailable**. Remove or disable it in *Settings > Devices & services*.
- The new MQTT entities may get **different `entity_id`s** than before.
  Anything that referenced the old ones needs updating: dashboards,
  automations, the Bosch eBike map/dashboard cards, and the integration's
  optional *Live odometer / Live battery SoC* options
  (*Settings > Devices & services > Bosch eBike > Configure*).
- Do not run `api:` and `mqtt:` at the same time, or the device shows up
  twice.

### iPhone: enable "Maximize Compatibility"

On the iPhone go to **Settings > Personal Hotspot > Maximize Compatibility**
and turn it **ON**. This forces the hotspot to 2.4 GHz. The ESP32 has no
5 GHz radio, so without this setting it never sees the hotspot at all.

### Setting up WireGuard on a FritzBox

FRITZ!OS 7.50 and newer have WireGuard built in.

1. In the FritzBox UI go to **Internet > Permit Access > VPN (WireGuard)** and
   click **Add connection**.
2. Choose the option for a **single device / "other application"** (not the
   "share whole network" wizard). Give it a name like `ebike-bridge`.
3. The FritzBox generates a configuration. You will not import it into an app;
   instead you copy its values into `secrets.yaml`. The mapping is:

   | FritzBox config field | secrets.yaml key | Notes |
   |---|---|---|
   | `[Interface] Address` | `wg_address` | The IP the FritzBox assigned to this peer. Use it exactly. |
   | `[Interface] PrivateKey` | `wg_private_key` | The peer's private key (belongs on the ESP). |
   | `[Peer] PublicKey` | `wg_peer_public_key` | The FritzBox's public key. |
   | `[Peer] PresharedKey` | `wg_preshared_key` | |
   | `[Peer] Endpoint` (host part) | `wg_endpoint` | e.g. `yourbox.myfritz.net` |
   | `[Peer] Endpoint` (port part) | `wg_port` | the number after the colon |
   | (your home subnet) | `wg_allowed_subnet` | e.g. `192.168.2.0/24` |

4. In `example-bridge-mobile.yaml` the tunnel uses `netmask: 255.255.255.0`.
   This is what actually routes your home subnet through the tunnel. Do not
   remove it.

> Common mistakes (all already handled in the example):
> - `wg_address` not matching the FritzBox-assigned IP -> data never arrives.
> - Missing `netmask: 255.255.255.0` -> tunnel up but no routing.
> - `require_connection_to_proceed: true` -> reboot loop, because the tunnel
>   is intentionally disabled at home.

### Tunnel only on the hotspot, off at home

The FritzBox assigns the peer an IP inside your home subnet. If the tunnel
were active while the ESP is on your home WiFi, that would conflict with
normal home routing. The example therefore enables the tunnel only when the
connected SSID is your hotspot, and disables it otherwise (a `wifi_info`
text sensor drives `wireguard.enable` / `wireguard.disable`).

### WireGuard troubleshooting

If the tunnel comes up (handshake OK, you can even ping the ESP) but MQTT never
connects (`select() timeout`, `esp-tls error 0x8006`, and nothing from the ESP
on the server's `wg0`), it is almost always one of these:

- **The ESP tunnel IP must be in the same subnet as the MQTT broker.**
  ESPHome's WireGuard (lwIP-based, via `esp_wireguard` / `wireguard-lwip`) does
  NOT do policy routing for `peer_allowed_ips` the way a full OS client does. It
  routes by on-link subnet plus the default route. So the broker only goes
  through the tunnel if it is **on-link** on the WG interface, i.e. the ESP's
  `address` is in the broker's subnet (with `netmask: 255.255.255.0`). A FritzBox
  WireGuard does exactly that automatically (it assigns the peer a home-subnet
  IP), which is why FritzBox setups just work.
  - Own WireGuard server with a **separate** tunnel subnet (e.g. `10.6.0.0/24`)
    while the broker is on `192.168.x.0/24`? Then the broker is off-link, and the
    ESP sends its packets out the WiFi default route, never into the tunnel
    (handshake and ping still work, because those are the reverse path). Fix:
    either give the ESP a free tunnel IP **inside the broker's subnet** (and set
    the server `[Peer] AllowedIPs` to that `/32`), or use full tunnel
    `peer_allowed_ips: 0.0.0.0/0` so the WG interface becomes the default route.

- **OTA rollback can hide your changes.** A freshly flashed firmware is only
  marked valid after it runs ~60 s without a reset (`safe_mode: Successful after:
  60s`). If you reboot or unplug sooner, the bootloader rolls back to the
  PREVIOUS image on the next boot, and you are silently testing the old config.
  After flashing, leave it powered and untouched for ~90 s, then verify the log
  shows your current settings.

- **Do not debug MQTT through MQTT-delivered logs.** ESPHome's `<prefix>/debug`
  log topic only arrives once MQTT works, so it is useless while MQTT is the
  broken part. Use USB serial (`esphome logs ...`). On the server, `wg show`
  (per-peer handshake, transfer, allowed-ips) and `tcpdump -ni wg0` show exactly
  where the packets stop.

### Quick start

1. Copy `secrets.yaml.example` to `secrets.yaml` and fill in your values.
2. Create the WireGuard connection on your router and transcribe the values.
3. Enable "Maximize Compatibility" on the iPhone hotspot.
4. Set up the Mosquitto add-on in HA if you have not already.
5. Flash `example-bridge-mobile.yaml`.
6. At home it stays on WiFi with the tunnel off; on the hotspot it brings the
   tunnel up automatically and the data flows.

Prefer a graphical workflow over the command line? See the next section.

### Using the ESPHome add-on in Home Assistant

You do not need the command line. You can do everything inside the **ESPHome
Device Builder** add-on that most Home Assistant users already have.

1. In Home Assistant go to **Settings > Add-ons**, install and open **ESPHome
   Device Builder**, then **Open Web UI**.
2. Click **New device**, give it a name, pick **ESP32-C3** when asked, then
   **Edit** the device and replace its YAML with the contents of
   [`example-bridge-mobile.yaml`](example-bridge-mobile.yaml).
3. Open the **Secrets** editor (top-right menu of the dashboard) and add the
   keys from [`secrets.yaml.example`](secrets.yaml.example), filled with your
   values. The secrets editor is **shared by all devices** in this add-on, so
   if you already use ESPHome you may have keys like `wifi_ssid` already.
   Reuse those instead of adding them twice.
4. Click **Install > Plug into this computer** for the first flash. Connect the
   ESP by USB to the computer showing the dashboard and use Chrome or Edge
   (Web Serial). After the first flash you can update **Wirelessly** (OTA) over
   WiFi.
5. The first build downloads the toolchain and platform (a few minutes). USB is
   only needed for that first flash.

---

## Deutsch

### Die Idee

```
eBike --BLE--> ESP --WLAN (Handy-Hotspot)--> Internet --WireGuard--> FritzBox --> Home Assistant (MQTT)
```

Der ESP verbindet sich mit dem Hotspot deines Handys, baut einen
WireGuard-Tunnel zu deinem Heim-Router auf und schiebt die eBike-Daten an
deinen MQTT-Broker, als säße er zu Hause.

### Du brauchst KEINE WireGuard-App auf dem Handy

Das ist die häufigste Verwirrung. Der Tunnel wird **vom ESP selbst** aufgebaut,
nicht vom Handy. Das Handy liefert nur den Hotspot (normales Internet). Du
installierst weder WireGuard noch Tailscale noch sonst eine VPN-App auf dem
Handy und konfigurierst dort nichts außer dem Hotspot. Der ESP ist der
WireGuard-Client.

### Warum MQTT statt der nativen API

Bei der nativen API baut **Home Assistant** die Verbindung zum ESP auf und muss
dessen IP kennen. Unterwegs wechselt diese IP ständig (Hotspot-DHCP,
Tunnel-IP), wodurch HA das Gerät nicht mehr erreicht. Bei **MQTT pusht der
ESP** seine Daten an den Broker, die wechselnde IP ist dann egal. Deshalb nutzt
diese Variante MQTT, und nur so kommen die Daten zuverlässig durch den Tunnel.

Du brauchst einen MQTT-Broker in HA, z. B. das **Mosquitto**-Add-on.

### Achtung: der Wechsel von API auf MQTT ändert deine Entitäten

Wenn du die Bridge vorher mit `api:` betrieben hast, legt HA die Entitäten beim
Wechsel auf `mqtt:` über **MQTT-Discovery** an statt über die
ESPHome-Integration. Praktische Folgen:

- Das alte Gerät hängt unter der **ESPHome**-Integration und wird
  **nicht verfügbar**. Entferne oder deaktiviere es unter
  *Einstellungen > Geräte & Dienste*.
- Die neuen MQTT-Entitäten können **andere `entity_id`s** haben als vorher.
  Alles, was die alten verwendet hat, muss angepasst werden: Dashboards,
  Automationen, die Bosch-eBike-Karten und die optionalen Integrations-Optionen
  *Live-Tachostand / Live-Akkustand*
  (*Einstellungen > Geräte & Dienste > Bosch eBike > Konfigurieren*).
- `api:` und `mqtt:` nicht gleichzeitig betreiben, sonst taucht das Gerät
  doppelt auf.

### iPhone: "Kompatibilität maximieren" aktivieren

Am iPhone unter **Einstellungen > Persönlicher Hotspot > Kompatibilität
maximieren** einschalten. Das zwingt den Hotspot auf 2,4 GHz. Der ESP32 hat
kein 5-GHz-Funkteil und würde den Hotspot sonst gar nicht sehen.

### WireGuard in der FritzBox einrichten

FRITZ!OS 7.50 und neuer haben WireGuard eingebaut.

1. In der FritzBox auf **Internet > Freigaben > VPN (WireGuard)** und
   **Verbindung hinzufügen**.
2. Die Option für ein **einzelnes Gerät / "andere Anwendung"** wählen (nicht
   den Assistenten, der das ganze Netz freigibt). Name z. B. `ebike-bridge`.
3. Die FritzBox erzeugt eine Konfiguration. Du importierst sie nicht in eine
   App, sondern überträgst die Werte in `secrets.yaml`. Die Zuordnung:

   | FritzBox-Feld | secrets.yaml-Schlüssel | Hinweis |
   |---|---|---|
   | `[Interface] Address` | `wg_address` | Die IP, die die FritzBox dem Peer zuweist. Exakt übernehmen. |
   | `[Interface] PrivateKey` | `wg_private_key` | Privater Schlüssel des Peers (gehört auf den ESP). |
   | `[Peer] PublicKey` | `wg_peer_public_key` | Öffentlicher Schlüssel der FritzBox. |
   | `[Peer] PresharedKey` | `wg_preshared_key` | |
   | `[Peer] Endpoint` (Host) | `wg_endpoint` | z. B. `deinebox.myfritz.net` |
   | `[Peer] Endpoint` (Port) | `wg_port` | die Zahl nach dem Doppelpunkt |
   | (dein Heim-Subnetz) | `wg_allowed_subnet` | z. B. `192.168.2.0/24` |

4. In `example-bridge-mobile.yaml` nutzt der Tunnel `netmask: 255.255.255.0`.
   Genau das routet dein Heim-Subnetz durch den Tunnel. Nicht entfernen.

> Typische Fehler (im Beispiel bereits gelöst):
> - `wg_address` passt nicht zur von der FritzBox vergebenen IP -> es kommen
>   nie Daten an.
> - Fehlendes `netmask: 255.255.255.0` -> Tunnel steht, aber kein Routing.
> - `require_connection_to_proceed: true` -> Reboot-Schleife, weil der Tunnel
>   zu Hause bewusst deaktiviert wird.

### Tunnel nur am Hotspot, zu Hause aus

Die FritzBox weist dem Peer eine IP im Heim-Subnetz zu. Wäre der Tunnel aktiv,
während der ESP im Heim-WLAN hängt, gäbe das einen Routing-Konflikt. Das
Beispiel aktiviert den Tunnel daher nur, wenn das verbundene WLAN dein Hotspot
ist, und deaktiviert ihn sonst (ein `wifi_info`-Textsensor steuert
`wireguard.enable` / `wireguard.disable`).

### WireGuard-Fehlersuche

Wenn der Tunnel steht (Handshake ok, du kannst den ESP sogar anpingen), MQTT
sich aber nie verbindet (`select() timeout`, `esp-tls error 0x8006`, und auf dem
Server-`wg0` kommt nichts vom ESP an), ist es fast immer eines davon:

- **Die ESP-Tunnel-IP muss im selben Subnetz wie der MQTT-Broker liegen.**
  ESPHomes WireGuard (lwIP-basiert, via `esp_wireguard` / `wireguard-lwip`) macht
  **kein Policy-Routing** über `peer_allowed_ips` wie ein vollwertiger
  OS-Client. Es routet nach On-Link-Subnetz plus Default-Route. Der Broker geht
  also nur durch den Tunnel, wenn er auf dem WG-Interface **on-link** ist - die
  ESP-`address` muss im Broker-Subnetz liegen (mit `netmask: 255.255.255.0`).
  Eine FritzBox-WireGuard macht genau das automatisch (sie vergibt dem Peer eine
  IP aus dem Heim-Subnetz), deshalb funktionieren FritzBox-Setups direkt.
  - Eigener WireGuard-Server mit **separatem** Tunnel-Subnetz (z. B.
    `10.6.0.0/24`), während der Broker in `192.168.x.0/24` liegt? Dann ist der
    Broker off-link, und der ESP schickt seine Pakete über die WLAN-Default-Route
    statt in den Tunnel (Handshake und Ping gehen trotzdem, das ist die
    Rückrichtung). Lösung: dem ESP eine freie Tunnel-IP **im Broker-Subnetz**
    geben (und die Server-`[Peer] AllowedIPs` auf dieses `/32` setzen), oder
    Full-Tunnel `peer_allowed_ips: 0.0.0.0/0`, damit das WG-Interface zur
    Default-Route wird.

- **OTA-Rollback verschleiert deine Änderungen.** Eine frisch geflashte Firmware
  wird erst nach ~60 s ohne Reset als gültig markiert (`safe_mode: Successful
  after: 60s`). Rebootest oder trennst du früher, fällt der Bootloader beim
  nächsten Start auf die **alte** Firmware zurück, und du testest unbemerkt die
  alte Config. Nach dem Flashen also ~90 s unangetastet laufen lassen und im Log
  prüfen, dass deine aktuellen Einstellungen wirklich aktiv sind.

- **MQTT nicht über MQTT-Logs debuggen.** ESPHomes Log-Topic `<prefix>/debug`
  kommt erst an, wenn MQTT funktioniert - es ist also nutzlos, solange genau MQTT
  klemmt. Nimm USB-Serial (`esphome logs ...`). Auf dem Server zeigen `wg show`
  (Handshake, Transfer, allowed-ips je Peer) und `tcpdump -ni wg0` exakt, wo die
  Pakete stehenbleiben.

### Schnellstart

1. `secrets.yaml.example` nach `secrets.yaml` kopieren und ausfüllen.
2. WireGuard-Verbindung in der FritzBox anlegen und Werte übertragen.
3. Am iPhone-Hotspot "Kompatibilität maximieren" einschalten.
4. Falls noch nicht vorhanden, das Mosquitto-Add-on in HA einrichten.
5. `example-bridge-mobile.yaml` flashen.
6. Zu Hause bleibt der ESP im WLAN, Tunnel aus; am Hotspot baut er den Tunnel
   automatisch auf und die Daten fließen.

Lieber grafisch statt Kommandozeile? Siehe nächster Abschnitt.

### Einrichtung im ESPHome-Add-on von Home Assistant

Du brauchst keine Kommandozeile. Alles geht im Add-on **ESPHome Device
Builder**, das die meisten HA-Nutzer schon haben.

1. In Home Assistant unter **Einstellungen > Add-ons** das Add-on **ESPHome
   Device Builder** installieren, öffnen und **Web-UI öffnen**.
2. Auf **New device** klicken, Namen vergeben, bei der Abfrage **ESP32-C3**
   wählen, dann das Gerät **bearbeiten** und seine YAML durch den Inhalt von
   [`example-bridge-mobile.yaml`](example-bridge-mobile.yaml) ersetzen.
3. Den **Secrets**-Editor öffnen (Menü oben rechts im Dashboard) und die
   Schlüssel aus [`secrets.yaml.example`](secrets.yaml.example) mit deinen
   Werten eintragen. Der Secrets-Editor gilt für **alle** Geräte in diesem
   Add-on. Wer ESPHome schon nutzt, hat Schlüssel wie `wifi_ssid` evtl. schon,
   dann vorhandene wiederverwenden statt doppelt anlegen.
4. **Install > Plug into this computer** für den ersten Flash. Den ESP per USB
   an den Rechner stecken, der das Dashboard anzeigt, und Chrome oder Edge
   verwenden (Web Serial). Danach geht **Wirelessly** (OTA) über WLAN.
5. Der erste Build lädt Toolchain und Plattform (einige Minuten). USB ist nur
   für diesen ersten Flash nötig.
