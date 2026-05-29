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

### Quick start

1. Copy `secrets.yaml.example` to `secrets.yaml` and fill in your values.
2. Create the WireGuard connection on your router and transcribe the values.
3. Enable "Maximize Compatibility" on the iPhone hotspot.
4. Set up the Mosquitto add-on in HA if you have not already.
5. Flash `example-bridge-mobile.yaml`.
6. At home it stays on WiFi with the tunnel off; on the hotspot it brings the
   tunnel up automatically and the data flows.

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

### Schnellstart

1. `secrets.yaml.example` nach `secrets.yaml` kopieren und ausfüllen.
2. WireGuard-Verbindung in der FritzBox anlegen und Werte übertragen.
3. Am iPhone-Hotspot "Kompatibilität maximieren" einschalten.
4. Falls noch nicht vorhanden, das Mosquitto-Add-on in HA einrichten.
5. `example-bridge-mobile.yaml` flashen.
6. Zu Hause bleibt der ESP im WLAN, Tunnel aus; am Hotspot baut er den Tunnel
   automatisch auf und die Daten fließen.
