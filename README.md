# Bosch eBike Smart System – Home Assistant Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![HA Version](https://img.shields.io/badge/Home%20Assistant-2024.1%2B-blue.svg)](https://www.home-assistant.io/)

> **Deutsch** | [English](#english)

---

## Deutsch

### Beschreibung

Diese Custom Integration verbindet dein **Bosch eBike Smart System** mit Home Assistant. Sie liest Fahrraddaten (Kilometerstand, Motorstunden, Batterie-Ladezyklen) und Aktivitätsdaten (letzte Fahrt, Geschwindigkeit, Trittfrequenz, Leistung) direkt von der offiziellen Bosch Data Act API aus.

**Unterstützt werden ausschließlich eBikes mit Bosch Smart System** (nicht das Classic Line System).

### Funktionen

- **Bike-Daten:** Kilometerstand, Motorstunden (gesamt & mit Unterstützung), maximale Unterstützungsgeschwindigkeit, aktive Unterstützungsmodi, Schiebehilfe-Geschwindigkeit, nächster Service-Kilometerstand
- **Batterie-Daten:** Gelieferte Wh über Lebensdauer, Ladezyklen (gesamt, am Rad, extern)
- **Letzte Fahrt:** Distanz, Dauer, Durchschnitts-/Maximalgeschwindigkeit, Trittfrequenz (avg/max), Fahrerleistung in Watt (avg/max), Kalorienverbrauch, Höhenmeter (Anstieg/Abstieg), Titel, Datum
- **Gesamtstatistiken:** Anzahl aller Fahrten, Gesamtdistanz, Gesamtfahrzeit, Gesamtkalorien, Gesamthöhenmeter, Durchschnittswerte für Geschwindigkeit/Leistung/Trittfrequenz über alle Fahrten
- **GPS-Track-Export:** Export aller Fahrten als GPX-Dateien (mit Speed, Cadence, Power als Garmin TrackPointExtension)
- **Interaktive Kartendarstellung:** Custom Lovelace Card mit GPS-Tracks, geschwindigkeitsabhängiger Farbcodierung, Date-Picker und Prev/Next-Navigation
- **Automatische Token-Aktualisierung** über Refresh-Token
- **30-Minuten-Polling-Intervall** (beim ersten Start werden alle Fahrten importiert)

### Voraussetzungen

1. Ein eBike mit **Bosch Smart System** (z. B. Performance Line CX, SX, etc.)
2. Ein **Bosch SingleKey ID** Account ([singlekey-id.com](https://singlekey-id.com))
3. Zugang zum **Bosch eBike Flow Portal** ([portal.bosch-ebike.com](https://portal.bosch-ebike.com))

---

### Schritt-für-Schritt-Anleitung

#### 1. Bosch SingleKey ID erstellen (falls noch nicht vorhanden)

1. Gehe zu [singlekey-id.com](https://singlekey-id.com)
2. Klicke auf **Registrieren**
3. Erstelle deinen Account mit deiner E-Mail-Adresse
4. Bestätige deine E-Mail-Adresse

#### 2. eBike mit dem Flow Portal verknüpfen

1. Installiere die **Bosch eBike Flow App** auf deinem Smartphone ([iOS](https://apps.apple.com/app/bosch-ebike-flow/id1504451498) / [Android](https://play.google.com/store/apps/details?id=com.bosch.ebike))
2. Melde dich mit deiner SingleKey ID an
3. Koppele dein eBike über Bluetooth mit der App
4. Dein Bike erscheint nun im Flow Portal unter [portal.bosch-ebike.com](https://portal.bosch-ebike.com)

#### 3. App im Bosch Data Act Portal registrieren

Dies ist der wichtigste Schritt. Du musst eine "App" im Bosch-Portal anlegen, um eine **Client-ID** zu erhalten.

1. Gehe zu [portal.bosch-ebike.com/data-act/app](https://portal.bosch-ebike.com/data-act/app)
2. Melde dich mit deiner SingleKey ID an
3. Klicke auf **"App erstellen"** (oder "Create App")
4. Fülle das Formular aus:
   - **App-Name:** z. B. `Home Assistant`
   - **Login URL:** `https://p9.authz.bosch.com/auth/realms/obc/protocol/openid-connect/auth`
   - **Redirect URI:** `http://localhost:8888/callback`

   > **Wichtig:** Die Login URL muss der Bosch OAuth-Endpunkt sein (siehe oben). Die Redirect-URI muss **exakt** `http://localhost:8888/callback` lauten.

5. Nach dem Erstellen erhältst du eine **Client-ID** (im Format `euda-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`). Kopiere diese — du brauchst sie gleich.

> **Hinweis:** Die App muss von Bosch genehmigt werden. Das kann einige Stunden bis wenige Tage dauern. Du erhältst eine E-Mail, sobald die App freigeschaltet ist. Erst danach funktionieren die nächsten Schritte (Datenfreigabe und Token-Austausch).

#### 4. Datenfreigabe im Flow Portal aktivieren

Ohne Datenfreigabe liefert die API ein leeres Ergebnis!

1. Gehe zu [portal.bosch-ebike.com/data-act](https://portal.bosch-ebike.com/data-act)
2. Suche deine gerade erstellte App (z. B. "Home Assistant")
3. Klicke auf **"Daten freigeben"** (oder "Share data")
4. Wähle aus, welche Daten du freigeben möchtest:
   - **Bike-Profil** (Kilometerstand, Motorstunden, Batterie etc.)
   - **Aktivitäten** (Fahrtdaten, Geschwindigkeit, Trittfrequenz etc.)
5. Bestätige die Freigabe

> **Hinweis:** Wenn du die Datenfreigabe nicht aktivierst, wird die Integration zwar ohne Fehler starten, aber **keine Entities anzeigen** (0 Bikes, keine Aktivitäten).

#### 5. Integration in Home Assistant einrichten

1. Kopiere den Ordner `custom_components/bosch_ebike/` in dein Home Assistant `config/custom_components/`-Verzeichnis
2. Starte Home Assistant neu
3. Gehe zu **Einstellungen → Geräte & Dienste → Integration hinzufügen**
4. Suche nach **"Bosch eBike"**
5. Gib deine **Client-ID** ein (aus Schritt 3)
6. Es erscheint ein Feld für den **Autorisierungscode**. Im Home Assistant Log (Warnung) findest du eine URL:
   ```
   Bosch eBike: Open this URL in your browser to log in: https://p9.authz.bosch.com/auth/realms/obc/...
   ```
7. Öffne diese URL in deinem Browser
8. Melde dich mit deiner **SingleKey ID** an
9. Nach dem Login wirst du zu `http://localhost:8888/callback?code=XXXX...` weitergeleitet
   - Dein Browser wird "Seite nicht erreichbar" anzeigen — **das ist normal!**
   - Kopiere den Wert nach `code=` aus der Adressleiste (alles bis zum `&` oder bis zum Ende der URL)
10. Füge den Code in Home Assistant ein und klicke **Absenden**

Die Integration wird nun deine Bike-Daten abrufen und Sensor-Entities erstellen.

#### 6. Kartenansicht einrichten (optional)

Die Integration enthält eine interaktive Lovelace-Karte zur Anzeige deiner GPS-Tracks.

1. Gehe zu **Einstellungen → Dashboards → Ressourcen → Hinzufügen**
2. URL: `/bosch_ebike/bosch-ebike-map-card.js`
3. Typ: **JavaScript-Modul**
4. Füge die Karte zu deinem Dashboard hinzu:
   ```yaml
   type: custom:bosch-ebike-map-card
   height: 500
   ```

Die Karte zeigt:
- GPS-Track mit geschwindigkeitsabhängiger Farbcodierung (blau → grün → gelb → rot)
- Start-/Endpunkt-Marker
- Fahrtinformationen (Distanz, Dauer, Speed, Höhenmeter, Kalorien)
- Date-Picker und Prev/Next-Buttons zum Durchblättern aller Fahrten

#### HACS-Installation (Alternative)

1. Öffne HACS in Home Assistant
2. Klicke auf **"Benutzerdefinierte Repositories"** (drei Punkte oben rechts)
3. Füge die Repository-URL hinzu: `https://github.com/Xunil99/ha-bosch-ebike`
4. Kategorie: **Integration**
5. Installiere die Integration und starte Home Assistant neu

---

### Fehlerbehebung

| Problem | Lösung |
|---------|--------|
| Keine Entities nach Einrichtung | Datenfreigabe im Flow Portal aktivieren (Schritt 4) |
| "Seite nicht erreichbar" nach Login | Normal! Kopiere den `code=`-Wert aus der Adressleiste |
| Token-Austausch fehlgeschlagen | Prüfe, ob die Redirect-URI exakt `http://localhost:8888/callback` lautet |
| Kilometerstand unrealistisch hoch | Der Odometer wird in Metern geliefert und automatisch in km umgerechnet |
| Aktivitätsdaten fehlen | Prüfe, ob die Aktivitäten-Freigabe im Flow Portal aktiv ist |
| Kein "Daten freigeben"-Button | Die App muss erst von Bosch genehmigt werden (E-Mail abwarten) |
| Token nicht akzeptiert | App noch nicht genehmigt — warte auf die Bestätigungs-E-Mail von Bosch |

---

### Verfügbare Sensoren

#### Bike-Sensoren
| Sensor | Einheit | Beschreibung |
|--------|---------|--------------|
| Odometer | km | Gesamtkilometerstand |
| Motor Total Hours | h | Gesamte Motorlaufzeit |
| Motor Assist Hours | h | Motorlaufzeit mit Unterstützung |
| Max Assist Speed | km/h | Maximale Unterstützungsgeschwindigkeit |
| Active Assist Modes | — | Liste der aktiven Unterstützungsmodi |
| Walk Assist Speed | km/h | Schiebehilfe-Geschwindigkeit |
| Next Service Odometer | km | Nächster Service-Kilometerstand |

#### Batterie-Sensoren (pro Batterie)
| Sensor | Einheit | Beschreibung |
|--------|---------|--------------|
| Wh Lifetime | Wh | Gelieferte Wattstunden über Lebensdauer |
| Charge Cycles | — | Gesamte Ladezyklen |
| Cycles On Bike | — | Ladezyklen am Rad |
| Cycles Off Bike | — | Ladezyklen extern |

#### Aktivitäts-Sensoren (letzte Fahrt)
| Sensor | Einheit | Beschreibung |
|--------|---------|--------------|
| Last Ride Title | — | Name der Fahrt |
| Last Ride Date | — | Datum/Uhrzeit |
| Last Ride Distance | km | Distanz |
| Last Ride Duration | min | Fahrtdauer (ohne Stopps) |
| Last Ride Avg/Max Speed | km/h | Durchschnitts-/Maximalgeschwindigkeit |
| Last Ride Avg/Max Cadence | rpm | Trittfrequenz |
| Last Ride Avg/Max Rider Power | W | Fahrerleistung |
| Last Ride Calories | kcal | Kalorienverbrauch |
| Last Ride Elevation Gain/Loss | m | Höhenmeter (Anstieg/Abstieg) |

#### Gesamtstatistiken (über alle Fahrten)
| Sensor | Einheit | Beschreibung |
|--------|---------|--------------|
| Total Rides | — | Anzahl aller Fahrten |
| Total Distance (Activities) | km | Gesamtdistanz aller Fahrten |
| Total Ride Duration | h | Gesamtfahrzeit |
| Total Calories | kcal | Gesamt-Kalorienverbrauch |
| Total Elevation Gain | m | Gesamt-Höhenmeter |
| Avg Speed (All Rides) | km/h | Durchschnittsgeschwindigkeit über alle Fahrten |
| Avg Rider Power (All Rides) | W | Durchschnittliche Fahrerleistung |
| Avg Cadence (All Rides) | rpm | Durchschnittliche Trittfrequenz |

#### Buttons
| Button | Beschreibung |
|--------|--------------|
| Import All GPS Data | Exportiert GPS-Tracks aller Fahrten als GPX-Dateien |
| Import Latest GPS Data | Exportiert den GPS-Track der letzten Fahrt als GPX |

---

<a id="english"></a>

## English

### Description

This custom integration connects your **Bosch eBike Smart System** to Home Assistant. It reads bike data (odometer, motor hours, battery charge cycles) and activity data (last ride, speed, cadence, rider power) directly from the official Bosch Data Act API.

**Only eBikes with Bosch Smart System are supported** (not the Classic Line system).

### Features

- **Bike data:** Odometer, motor hours (total & with assist), max assist speed, active assist modes, walk assist speed, next service odometer
- **Battery data:** Delivered Wh over lifetime, charge cycles (total, on-bike, off-bike)
- **Last ride:** Distance, duration, avg/max speed, cadence (avg/max), rider power in watts (avg/max), calories burned, elevation gain/loss, title, date
- **Aggregate statistics:** Total rides, total distance, total ride time, total calories, total elevation, averages for speed/power/cadence across all rides
- **GPS track export:** Export all rides as GPX files (with speed, cadence, power as Garmin TrackPointExtension)
- **Interactive map card:** Custom Lovelace card with GPS tracks, speed-based color coding, date picker and prev/next navigation
- **Automatic token refresh** via refresh token
- **30-minute polling interval** (all rides are imported on first startup)

### Prerequisites

1. An eBike with **Bosch Smart System** (e.g., Performance Line CX, SX, etc.)
2. A **Bosch SingleKey ID** account ([singlekey-id.com](https://singlekey-id.com))
3. Access to the **Bosch eBike Flow Portal** ([portal.bosch-ebike.com](https://portal.bosch-ebike.com))

---

### Step-by-Step Setup Guide

#### 1. Create a Bosch SingleKey ID (if you don't have one)

1. Go to [singlekey-id.com](https://singlekey-id.com)
2. Click **Register**
3. Create your account with your email address
4. Confirm your email address

#### 2. Link your eBike to the Flow Portal

1. Install the **Bosch eBike Flow App** on your smartphone ([iOS](https://apps.apple.com/app/bosch-ebike-flow/id1504451498) / [Android](https://play.google.com/store/apps/details?id=com.bosch.ebike))
2. Sign in with your SingleKey ID
3. Pair your eBike via Bluetooth with the app
4. Your bike will now appear in the Flow Portal at [portal.bosch-ebike.com](https://portal.bosch-ebike.com)

#### 3. Register an App in the Bosch Data Act Portal

This is the most important step. You need to create an "App" in the Bosch portal to obtain a **Client-ID**.

1. Go to [portal.bosch-ebike.com/data-act/app](https://portal.bosch-ebike.com/data-act/app)
2. Sign in with your SingleKey ID
3. Click **"Create App"**
4. Fill in the form:
   - **App Name:** e.g., `Home Assistant`
   - **Login URL:** `https://p9.authz.bosch.com/auth/realms/obc/protocol/openid-connect/auth`
   - **Redirect URI:** `http://localhost:8888/callback`

   > **Important:** The Login URL must be the Bosch OAuth endpoint shown above. The redirect URI must be **exactly** `http://localhost:8888/callback`.

5. After creating the app, you will receive a **Client-ID** (format: `euda-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`). Copy it — you'll need it shortly.

> **Note:** The app needs to be approved by Bosch. This can take a few hours to a couple of days. You will receive an email once the app is approved. The following steps (data sharing and token exchange) will only work after approval.

#### 4. Enable Data Sharing in the Flow Portal

Without data sharing enabled, the API will return empty results!

1. Go to [portal.bosch-ebike.com/data-act](https://portal.bosch-ebike.com/data-act)
2. Find your newly created app (e.g., "Home Assistant")
3. Click **"Share data"**
4. Select which data you want to share:
   - **Bike Profile** (odometer, motor hours, battery, etc.)
   - **Activities** (ride data, speed, cadence, etc.)
5. Confirm the sharing

> **Note:** If you don't activate data sharing, the integration will start without errors but will show **no entities** (0 bikes, no activities).

#### 5. Set Up the Integration in Home Assistant

1. Copy the `custom_components/bosch_ebike/` folder into your Home Assistant `config/custom_components/` directory
2. Restart Home Assistant
3. Go to **Settings → Devices & Services → Add Integration**
4. Search for **"Bosch eBike"**
5. Enter your **Client-ID** (from step 3)
6. A field for the **Authorization Code** will appear. In the Home Assistant log (warning level), you'll find a URL:
   ```
   Bosch eBike: Open this URL in your browser to log in: https://p9.authz.bosch.com/auth/realms/obc/...
   ```
7. Open this URL in your browser
8. Sign in with your **SingleKey ID**
9. After login, you'll be redirected to `http://localhost:8888/callback?code=XXXX...`
   - Your browser will show "This site can't be reached" — **this is expected!**
   - Copy the value after `code=` from the address bar (everything up to the `&` or the end of the URL)
10. Paste the code into Home Assistant and click **Submit**

The integration will now fetch your bike data and create sensor entities.

#### 6. Set Up the Map Card (optional)

The integration includes an interactive Lovelace card for displaying your GPS tracks.

1. Go to **Settings → Dashboards → Resources → Add**
2. URL: `/bosch_ebike/bosch-ebike-map-card.js`
3. Type: **JavaScript Module**
4. Add the card to your dashboard:
   ```yaml
   type: custom:bosch-ebike-map-card
   height: 500
   ```

The card shows:
- GPS track with speed-based color coding (blue → green → yellow → red)
- Start/end point markers
- Ride information (distance, duration, speed, elevation, calories)
- Date picker and prev/next buttons for browsing all rides

#### HACS Installation (Alternative)

1. Open HACS in Home Assistant
2. Click **"Custom repositories"** (three dots in the top right)
3. Add the repository URL: `https://github.com/Xunil99/ha-bosch-ebike`
4. Category: **Integration**
5. Install the integration and restart Home Assistant

---

### Troubleshooting

| Problem | Solution |
|---------|----------|
| No entities after setup | Enable data sharing in the Flow Portal (step 4) |
| "This site can't be reached" after login | Expected! Copy the `code=` value from the address bar |
| Token exchange failed | Check that redirect URI is exactly `http://localhost:8888/callback` |
| Odometer unrealistically high | The odometer is delivered in meters and automatically converted to km |
| Activity data missing | Check that activity sharing is enabled in the Flow Portal |
| No "Share data" button visible | The app needs to be approved by Bosch first — wait for the confirmation email |
| Token not accepted | App not yet approved — wait for the approval email from Bosch |

---

### Available Sensors

#### Bike Sensors
| Sensor | Unit | Description |
|--------|------|-------------|
| Odometer | km | Total distance |
| Motor Total Hours | h | Total motor running time |
| Motor Assist Hours | h | Motor running time with assist |
| Max Assist Speed | km/h | Maximum assistance speed |
| Active Assist Modes | — | List of active assist modes |
| Walk Assist Speed | km/h | Walk assist speed |
| Next Service Odometer | km | Next service due at odometer reading |

#### Battery Sensors (per battery)
| Sensor | Unit | Description |
|--------|------|-------------|
| Wh Lifetime | Wh | Delivered watt-hours over lifetime |
| Charge Cycles | — | Total charge cycles |
| Cycles On Bike | — | Charge cycles while on bike |
| Cycles Off Bike | — | Charge cycles off bike |

#### Activity Sensors (last ride)
| Sensor | Unit | Description |
|--------|------|-------------|
| Last Ride Title | — | Ride name |
| Last Ride Date | — | Date/time |
| Last Ride Distance | km | Distance |
| Last Ride Duration | min | Ride duration (without stops) |
| Last Ride Avg/Max Speed | km/h | Average/maximum speed |
| Last Ride Avg/Max Cadence | rpm | Cadence |
| Last Ride Avg/Max Rider Power | W | Rider power |
| Last Ride Calories | kcal | Calories burned |
| Last Ride Elevation Gain/Loss | m | Elevation gain/loss |

#### Aggregate Statistics (all rides)
| Sensor | Unit | Description |
|--------|------|-------------|
| Total Rides | — | Number of all rides |
| Total Distance (Activities) | km | Total distance across all rides |
| Total Ride Duration | h | Total ride time |
| Total Calories | kcal | Total calories burned |
| Total Elevation Gain | m | Total elevation gain |
| Avg Speed (All Rides) | km/h | Average speed across all rides |
| Avg Rider Power (All Rides) | W | Average rider power |
| Avg Cadence (All Rides) | rpm | Average cadence |

#### Buttons
| Button | Description |
|--------|-------------|
| Import All GPS Data | Exports GPS tracks of all rides as GPX files |
| Import Latest GPS Data | Exports the GPS track of the latest ride as GPX |

---

### License

MIT License — see [LICENSE](LICENSE) for details.

### Credits

Built by [Volker Hauffe](https://github.com/Xunil99).

This integration uses the official [Bosch eBike Data Act API](https://portal.bosch-ebike.com/data-act).
