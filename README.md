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

#### Voraussetzungen

1. Ein **Bosch SingleKey ID** Account — falls noch nicht vorhanden, erstelle einen unter [singlekey-id.com](https://singlekey-id.com)
2. Dein eBike muss mit der **Bosch eBike Flow App** ([iOS](https://apps.apple.com/app/bosch-ebike-flow/id1504451498) / [Android](https://play.google.com/store/apps/details?id=com.bosch.ebike)) verknüpft sein

---

#### Schritt 1: App im Bosch Data Act Portal registrieren (zuerst machen!)

Dies ist der wichtigste Schritt. Du musst eine "App" im Bosch-Portal anlegen, um eine **Client-ID** zu erhalten.

1. Gehe zu [portal.bosch-ebike.com/data-act/app](https://portal.bosch-ebike.com/data-act/app)
2. Melde dich mit deiner SingleKey ID an
3. Klicke auf **"App erstellen"** (oder "Create App")
4. Fülle das Formular aus:
   - **App-Name:** z. B. `Home Assistant`
   - **Login URL:** `https://p9.authz.bosch.com/auth/realms/obc/protocol/openid-connect/auth`
   - **Redirect URI:** `http://localhost:8888/callback`

   > **Wichtig:** Die Login URL muss der Bosch OAuth-Endpunkt sein (siehe oben). Die Redirect-URI muss **exakt** `http://localhost:8888/callback` lauten.

5. Nach dem Erstellen erhältst du eine **Client-ID** (im Format `euda-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`).

#### Schritt 2: Client-ID sichern

Kopiere die gerade erstellte **Client-ID** in ein Text-File oder einen Notizzettel — du brauchst sie später zum Einfügen per Copy & Paste.

---

#### Schritt 3: Integration in Home Assistant einrichten

> **Wichtig:** Am besten solltest du in deinem Browser **noch NICHT bei Bosch angemeldet** sein, bevor du diesen Schritt startest!

1. Kopiere den Ordner `custom_components/bosch_ebike/` in dein Home Assistant `config/custom_components/`-Verzeichnis
2. Starte Home Assistant neu
3. Gehe zu **Einstellungen → Geräte & Dienste → Integration hinzufügen**
4. Suche nach **"Bosch eBike"**
5. Gib deine **Client-ID** ein (aus Schritt 2)
6. Es erscheint ein Feld für den **Autorisierungscode**. Im Home Assistant Log (Warnung) findest du eine URL:
   ```
   Bosch eBike: Open this URL in your browser to log in: https://p9.authz.bosch.com/auth/realms/obc/...
   ```
7. Kopiere diese URL und öffne sie **in einem neuen Browser-Tab**
8. Melde dich mit deiner **SingleKey ID** an
9. Nach dem Login wirst du zu `http://localhost:8888/callback?code=XXXX...` weitergeleitet
   - Dein Browser wird "Seite nicht erreichbar" anzeigen — **das ist normal!**
   - Kopiere den Wert nach `code=` aus der Adressleiste (alles bis zum `&` oder bis zum Ende der URL)
   - ⏱️ **Wichtig: Dies ist zeitkritisch!** Der Code ist nur ca. 45–60 Sekunden gültig — kopiere und füge ihn schnell ein!
10. Füge den Code in Home Assistant ein und klicke **Absenden** — ebenfalls innerhalb von 45–60 Sekunden!

#### Schritt 4: Ergebnis prüfen

Die Integration sollte jetzt eingerichtet sein — aber **noch ohne Entities!** Das ist normal. Weiter mit Schritt 5.

---

#### Schritt 5: Datenfreigabe aktivieren

Ohne Datenfreigabe liefert die API ein leeres Ergebnis!

1. Gehe zu **[flow.bosch-ebike.com](https://flow.bosch-ebike.com)**
2. Melde dich mit deiner **SingleKey ID** an
3. Wähle oben im Menü **"Data Act"** aus
4. Suche den Eintrag **"Home Assistant"** und **aktiviere** ihn

Jetzt solltest du auf der passenden Bosch-API Seite die Option sehen, die Client-ID zu aktivieren!

#### Schritt 6: Integration neu laden

Nachdem du die Client-ID im Flow Portal aktiviert hast:

1. Gehe zurück zu **Home Assistant → Einstellungen → Geräte & Dienste**
2. Suche die **Bosch eBike** Integration
3. Klicke auf **⋮ (drei Punkte)** → **Neu laden**

Die Integration sollte sich nun mit **allen verfügbaren Entities** aktualisieren (Bike-Daten, Batterie, letzte Fahrt, Gesamtstatistiken).

#### 6. Kartenansicht einrichten (optional)

Die Integration enthält eine interaktive Lovelace-Karte zur Anzeige deiner GPS-Tracks.

**Schritt A: Ressource registrieren**

1. Gehe zu **Einstellungen → Dashboards**
2. Klicke oben rechts auf das **⋮ Drei-Punkte-Menü** → **Ressourcen**
3. Klicke auf **+ Ressource hinzufügen** (unten rechts)
4. Gib folgende Daten ein:
   - **URL:** `/ha_bosch_ebike/bosch-ebike-map-card.js`
   - **Ressourcentyp:** JavaScript-Modul
5. Klicke auf **Erstellen**

**Schritt B: Karte zum Dashboard hinzufügen**

1. Öffne dein gewünschtes Dashboard
2. Klicke oben rechts auf den **Stift ✏️** (Bearbeiten-Modus)
3. Klicke auf **+ Karte hinzufügen**
4. Scrolle ganz nach unten und wähle **Manuell** (YAML-Eingabe)
5. Füge folgenden Code ein:
   ```yaml
   type: custom:bosch-ebike-map-card
   height: 400
   ```
6. Klicke auf **Speichern**

> **Tipp:** Die Höhe (height) kannst du anpassen (200–1000 Pixel). Empfehlung: 400 für Smartphones, 500 für Desktops.

**Die Karte zeigt:**
- GPS-Track mit geschwindigkeitsabhängiger Farbcodierung (blau → grün → gelb → rot)
- Start-Marker (grün) und Ziel-Marker (rot)
- Fahrtinformationen (Distanz, Dauer, Ø/Max Speed, Höhenmeter, Kalorien)
- **◀ Prev / Next ▶** Buttons und **Date-Picker** zum Durchblättern aller Fahrten

> **Hinweis:** Wenn die Karte nach einem Update nicht korrekt angezeigt wird, leere den Browser-Cache mit `Ctrl+Shift+R` (Hard Reload).

#### HACS-Installation (Alternative)

1. Öffne HACS in Home Assistant
2. Klicke auf **"Benutzerdefinierte Repositories"** (drei Punkte oben rechts)
3. Füge die Repository-URL hinzu: `https://github.com/Xunil99/ha-bosch-ebike`
4. Kategorie: **Integration**
5. Installiere die Integration und starte Home Assistant neu

---

### Mehrere Bikes oder Konten

Die Integration unterstützt sowohl mehrere Konten als auch mehrere Bikes pro Konto.

**Mehrere Bosch-Konten** (z. B. ein Bike pro Familienmitglied mit eigener SingleKey ID):
1. Erstelle für jedes Konto im Bosch Data Act Portal eine eigene App-Registrierung mit eigener Client-ID
2. Füge die Integration mehrfach hinzu (**Einstellungen → Geräte & Dienste → + Integration hinzufügen → Bosch eBike**) und gib dabei jeweils die andere Client-ID ein
3. Jede Instanz hat ihre eigenen Sensoren und Touren

**Mehrere Bikes unter einem Konto** (z. B. zwei Bikes mit derselben SingleKey ID):
- Die Integration legt automatisch eigene Sensoren pro Bike an (Drive Unit, Akku, Service usw.).
- Touren werden über eine Heuristik (Abgleich des bike-spezifischen `odometer`-Stands mit `startOdometer + distance` der jeweiligen Tour) automatisch dem richtigen Bike zugeordnet.

**Filter in der Karte:** Sobald mehr als ein Konto und/oder mehr als ein Bike vorhanden ist, blendet die Lovelace-Karte automatisch zwei Auswahlfelder über der Liste ein:
- **Konto** (nur sichtbar bei mehreren Konten)
- **Bike** (nur sichtbar bei mehreren Bikes)

Die Auswahl filtert die angezeigten Touren live; das Sortieren funktioniert wie gewohnt innerhalb des gefilterten Ergebnisses.

### POIs entlang der Route

Auf der Karte gibt es einen 📍-Toggle in den Steuerelementen. Aktiviert er, wird im Hintergrund eine Overpass-API-Abfrage gestartet, die folgende Punkte entlang der Route findet (max. ~500 m vom befahrenen Pfad entfernt):

- 🔌 **Ladestationen** (`amenity=charging_station`)
- 🛠️ **Fahrradgeschäfte** und Reparaturstationen (`shop=bicycle`, `amenity=bicycle_repair_station`)
- 💧 **Trinkwasser** (`amenity=drinking_water`)
- 🚻 **Toiletten** (`amenity=toilets`)

Klick auf einen Marker → Popup mit Name, Öffnungszeiten/Adresse/Website (sofern bei OSM hinterlegt) und Link zu OpenStreetMap. Pro Tour werden bis zu 100 Marker dargestellt; Ergebnisse werden im Browser-localStorage gecacht.

### Wartungs-Erinnerungen

#### Service-Termin selbst setzen

Pro Bike gibt es zwei editierbare Entitäten:

- **`date.<bike>_service_due_date`** — Datum, an dem der nächste Kundendienst fällig ist
- **`number.<bike>_service_due_odometer`** — Kilometerstand, bei dem der nächste Kundendienst fällig ist

Beim ersten Datenabruf werden diese Werte automatisch aus der Bosch-API vorbelegt (sofern dort hinterlegt). Änderungen an den Entitäten überschreiben die Bosch-Werte und werden für die Service-Erinnerungen herangezogen. Setzt Du den Kilometerstand auf `0`, fällt die Anzeige auf den Bosch-Wert zurück.

#### Eigene Wartungsposten

Neben dem von Bosch gelieferten Service-Termin (`Next Service Date`/`Next Service Odometer`) kannst Du beliebige eigene Wartungsposten anlegen — z. B. Kettenwechsel alle 3000 km, Inspektion alle 365 Tage. Pro Bike wird ein Sensor `Maintenance Items Due` angelegt; sein Wert ist die Anzahl bald fälliger oder überfälliger Posten, das Attribut `items` listet alle Details (Restkilometer, Resttage).

**Posten anlegen:** **Entwicklerwerkzeuge → Dienste**, Dienst `bosch_ebike.add_maintenance` aufrufen mit:
- `bike_id` (aus dem Sensor-Attribut)
- `name` (z. B. "Kettenwechsel")
- `interval_km` und/oder `interval_days`

**Posten als erledigt markieren:** Dienst `bosch_ebike.complete_maintenance` mit `bike_id` und `item_id` (aus dem Sensor-Attribut). Setzt Datum und Kilometerstand auf jetzt zurück.

**Posten löschen:** Dienst `bosch_ebike.remove_maintenance`.

**Events für Automationen:** Bei Erreichen der Schwelle (Standard: 30 Tage / 200 km vor Fälligkeit) werden HA-Events ausgelöst:
- `ha_bosch_ebike_service_due_soon` / `ha_bosch_ebike_service_overdue` (für den Bosch-Service)
- `ha_bosch_ebike_maintenance_due_soon` / `ha_bosch_ebike_maintenance_overdue` (für eigene Posten)

Damit kann man z. B. eine Push-Mitteilung oder eine Beleuchtungs-Erinnerung bauen.

### Heatmap-Card — alle Touren auf einer Karte

Eine zweite Card-Variante `bosch-ebike-heatmap-card` legt alle Touren einer Auswahl als halbtransparente Linien übereinander. Filter-Dropdowns für Zeitraum (30 Tage / 3 Monate / 12 Monate / Alle), Konto und Bike. Darunter eine Statuszeile mit Tour- und Kilometeranzahl der Auswahl.

```yaml
type: custom:bosch-ebike-heatmap-card
height: 600
```

Die erste Anzeige kann etwas dauern — bei jeder bisher nicht abgerufenen Tour wird ein zusätzlicher API-Call gemacht (mit Concurrency-Limit). Die Tracks werden serverseitig im Speicher gecacht, weitere Aufrufe sind sofort.

### Wikipedia-Artikel entlang der Route

Auf der Lovelace-Karte gibt es einen 📚-Toggle in den Karten-Steuerelementen. Ist er aktiviert, sucht die Karte entlang der gefahrenen Route alle 2 km nach nahegelegenen Wikipedia-Artikeln und zeigt sie als (i)-Marker an. Ein Klick öffnet ein kleines Popup mit Titel, Vorschaubild, Kurzbeschreibung und einem Link auf den vollständigen Artikel.

- **Sprache** richtet sich nach der HA-Spracheinstellung; bei leerem Treffer wird auf Englisch zurückgefallen
- **Maximal 30 Marker** pro Tour, dichte Bereiche werden gebündelt
- **Toggle-Status und Ergebnisse** werden im Browser gecacht (`localStorage`), beim Tour-Wechsel werden frische Daten geholt
- **Datenschutz-Hinweis**: Beim Aktivieren des Layers werden Stützstellen-Koordinaten der Route an die Wikipedia-API gesendet; der Layer ist standardmäßig aus

### Fehlerbehebung

| Problem | Lösung |
|---------|--------|
| Keine Entities nach Einrichtung | Datenfreigabe im Flow Portal aktivieren (Schritt 4) |
| "Seite nicht erreichbar" nach Login | Normal! Kopiere den `code=`-Wert aus der Adressleiste |
| Token-Austausch fehlgeschlagen | Prüfe, ob die Redirect-URI exakt `http://localhost:8888/callback` lautet |
| Kilometerstand unrealistisch hoch | Der Odometer wird in Metern geliefert und automatisch in km umgerechnet |
| Aktivitätsdaten fehlen | Prüfe, ob die Aktivitäten-Freigabe im Flow Portal aktiv ist |
| Token nicht akzeptiert | Prüfe, ob die Client-ID korrekt eingegeben wurde |

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

> **Speicherort:** Die exportierten GPX-Dateien werden lokal im Home-Assistant-Config-Verzeichnis gespeichert unter:
> ```
> /config/bosch_ebike_gps/
> ```

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

#### Prerequisites

1. A **Bosch SingleKey ID** account — if you don't have one, create it at [singlekey-id.com](https://singlekey-id.com)
2. Your eBike must be linked to the **Bosch eBike Flow App** ([iOS](https://apps.apple.com/app/bosch-ebike-flow/id1504451498) / [Android](https://play.google.com/store/apps/details?id=com.bosch.ebike))

---

#### Step 1: Register an App in the Bosch Data Act Portal (do this first!)

This is the most important step. You need to create an "App" in the Bosch portal to obtain a **Client-ID**.

1. Go to [portal.bosch-ebike.com/data-act/app](https://portal.bosch-ebike.com/data-act/app)
2. Sign in with your SingleKey ID
3. Click **"Create App"**
4. Fill in the form:
   - **App Name:** e.g., `Home Assistant`
   - **Login URL:** `https://p9.authz.bosch.com/auth/realms/obc/protocol/openid-connect/auth`
   - **Redirect URI:** `http://localhost:8888/callback`

   > **Important:** The Login URL must be the Bosch OAuth endpoint shown above. The redirect URI must be **exactly** `http://localhost:8888/callback`.

5. After creating the app, you will receive a **Client-ID** (format: `euda-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`).

#### Step 2: Save your Client-ID

Copy the **Client-ID** you just created into a text file or note — you will need it later for copy & paste.

---

#### Step 3: Set Up the Integration in Home Assistant

> **Important:** It's best if you are **NOT already logged into Bosch** in your browser before starting this step!

1. Copy the `custom_components/bosch_ebike/` folder into your Home Assistant `config/custom_components/` directory
2. Restart Home Assistant
3. Go to **Settings → Devices & Services → Add Integration**
4. Search for **"Bosch eBike"**
5. Enter your **Client-ID** (from step 2)
6. A field for the **Authorization Code** will appear. In the Home Assistant log (warning level), you'll find a URL:
   ```
   Bosch eBike: Open this URL in your browser to log in: https://p9.authz.bosch.com/auth/realms/obc/...
   ```
7. Copy this URL and open it **in a new browser tab**
8. Sign in with your **SingleKey ID**
9. After login, you'll be redirected to `http://localhost:8888/callback?code=XXXX...`
   - Your browser will show "This site can't be reached" — **this is expected!**
   - Copy the value after `code=` from the address bar (everything up to the `&` or the end of the URL)
   - ⏱️ **Important: This is time-critical!** The code is only valid for about 45–60 seconds — copy and paste it quickly!
10. Paste the code into Home Assistant and click **Submit** — also within 45–60 seconds!

#### Step 4: Check the result

The integration should now be set up — but **still without entities!** This is normal. Continue with step 5.

---

#### Step 5: Enable Data Sharing

Without data sharing enabled, the API will return empty results!

1. Go to **[flow.bosch-ebike.com](https://flow.bosch-ebike.com)**
2. Sign in with your **SingleKey ID**
3. Select **"Data Act"** from the top menu
4. Find the entry **"Home Assistant"** and **activate** it

You should now see the option to activate the Client-ID on the Bosch API page!

#### Step 6: Reload the Integration

After activating the Client-ID in the Flow Portal:

1. Go back to **Home Assistant → Settings → Devices & Services**
2. Find the **Bosch eBike** integration
3. Click **⋮ (three dots)** → **Reload**

The integration should now update with **all available entities** (bike data, battery, last ride, aggregate statistics).

#### 6. Set Up the Map Card (optional)

The integration includes an interactive Lovelace card for displaying your GPS tracks.

**Step A: Register the Resource**

1. Go to **Settings → Dashboards**
2. Click the **⋮ three-dot menu** in the top right → **Resources**
3. Click **+ Add Resource** (bottom right)
4. Enter the following:
   - **URL:** `/ha_bosch_ebike/bosch-ebike-map-card.js`
   - **Resource Type:** JavaScript Module
5. Click **Create**

**Step B: Add the Card to Your Dashboard**

1. Open the dashboard where you want the map
2. Click the **pencil ✏️** icon (top right) to enter edit mode
3. Click **+ Add Card**
4. Scroll to the bottom and select **Manual** (YAML editor)
5. Paste the following code:
   ```yaml
   type: custom:bosch-ebike-map-card
   height: 400
   ```
6. Click **Save**

> **Tip:** You can adjust the height (200–1000 pixels). Recommendation: 400 for mobile, 500 for desktop.

**The card shows:**
- GPS track with speed-based color coding (blue → green → yellow → red)
- Start marker (green) and end marker (red)
- Ride information (distance, duration, avg/max speed, elevation, calories)
- **◀ Prev / Next ▶** buttons and **date picker** for browsing all rides

> **Note:** If the card doesn't display correctly after an update, clear your browser cache with `Ctrl+Shift+R` (hard reload).

#### HACS Installation (Alternative)

1. Open HACS in Home Assistant
2. Click **"Custom repositories"** (three dots in the top right)
3. Add the repository URL: `https://github.com/Xunil99/ha-bosch-ebike`
4. Category: **Integration**
5. Install the integration and restart Home Assistant

---

### Multiple bikes or accounts

The integration supports both multiple accounts and multiple bikes per account.

**Multiple Bosch accounts** (e.g. one bike per family member with their own SingleKey ID):
1. Create a separate app registration with its own Client-ID for each account in the Bosch Data Act Portal
2. Add the integration multiple times (**Settings → Devices & Services → + Add Integration → Bosch eBike**) using a different Client-ID each time
3. Each instance has its own sensors and rides.

**Multiple bikes under one account** (e.g. two bikes sharing the same SingleKey ID):
- The integration automatically creates per-bike sensors (drive unit, battery, service, etc.).
- Rides are attributed to the correct bike via a heuristic (matching each bike's reported `odometer` against the activity's `startOdometer + distance`).

**Card filter:** Once more than one account and/or more than one bike is present, the Lovelace card automatically shows two extra dropdowns above the activity list:
- **Account** (visible only with multiple accounts)
- **Bike** (visible only with multiple bikes)

The selection filters the displayed activities live; sorting works as usual within the filtered result.

### POIs along the route

Click the 📍 toggle in the map controls to overlay points of interest sourced live from OpenStreetMap (Overpass API), filtered to within ~500 m of the route:

- 🔌 **Charging stations** (`amenity=charging_station`)
- 🛠️ **Bike shops** and repair stations (`shop=bicycle`, `amenity=bicycle_repair_station`)
- 💧 **Drinking water** (`amenity=drinking_water`)
- 🚻 **Toilets** (`amenity=toilets`)

Clicking a marker opens a popup with name, opening hours / address / website (if tagged in OSM) and a link to the OpenStreetMap node. Up to 100 markers per ride; results are cached in the browser's localStorage.

### Maintenance reminders

#### Override the next service appointment

Each bike exposes two user-editable entities:

- **`date.<bike>_service_due_date`** — date the next service is due
- **`number.<bike>_service_due_odometer`** — odometer reading at which the next service is due

On first data fetch these are seeded from the Bosch API (when present). Changes you make take precedence over Bosch's values and feed into the service-due sensors and events. Setting the odometer to `0` clears the override and falls back to the Bosch value.

#### Custom maintenance items

Beyond the official Bosch service info (`Next Service Date` / `Next Service Odometer`) you can add arbitrary maintenance items per bike — e.g. chain swap every 3000 km, inspection every 365 days. Each bike gets a `Maintenance Items Due` sensor whose state is the count of items currently due-soon or overdue, with the full list available as the `items` attribute (remaining km, remaining days).

**Add an item:** **Developer tools → Services**, call `bosch_ebike.add_maintenance` with:
- `bike_id` (from the sensor attribute)
- `name` (e.g. "Chain swap")
- `interval_km` and/or `interval_days`

**Mark as done:** Call `bosch_ebike.complete_maintenance` with `bike_id` and `item_id` (from the sensor attribute). Resets date and odometer to "now".

**Delete:** Call `bosch_ebike.remove_maintenance`.

**Events for automations:** When a threshold is crossed (default: 30 days / 200 km before due), HA events fire:
- `ha_bosch_ebike_service_due_soon` / `ha_bosch_ebike_service_overdue` (Bosch service)
- `ha_bosch_ebike_maintenance_due_soon` / `ha_bosch_ebike_maintenance_overdue` (custom items)

You can wire these up to push notifications, light reminders, etc.

### Heatmap card — all rides overlaid

A second card type, `bosch-ebike-heatmap-card`, draws all rides in a selection as semi-transparent overlays on a single map. Filter dropdowns for time range (30 days / 3 months / 12 months / All), account and bike. A status line below shows ride count and total distance for the current selection.

```yaml
type: custom:bosch-ebike-heatmap-card
height: 600
```

First render can take a moment — every ride whose detail hasn't been fetched yet triggers an API call (rate-limited via concurrency limit). Tracks are then cached server-side in memory; subsequent renders are instant.

### Wikipedia articles along the route

The Lovelace card has a 📚 toggle in the map controls. When enabled, the card samples the ridden route every 2 km and queries Wikipedia for nearby articles, showing each one as a small (i) marker. Clicking a marker opens a popup with title, thumbnail, short summary and a link to the full article.

- **Language** follows the Home Assistant locale; falls back to English if no results
- **Up to 30 markers** per ride; dense areas are clustered
- **Toggle state and results** are cached in the browser (`localStorage`); fresh queries run when switching rides
- **Privacy note**: Enabling the layer sends sample coordinates of the route to the Wikipedia API. The layer is off by default

### Troubleshooting

| Problem | Solution |
|---------|----------|
| No entities after setup | Enable data sharing in the Flow Portal (step 4) |
| "This site can't be reached" after login | Expected! Copy the `code=` value from the address bar |
| Token exchange failed | Check that redirect URI is exactly `http://localhost:8888/callback` |
| Odometer unrealistically high | The odometer is delivered in meters and automatically converted to km |
| Activity data missing | Check that activity sharing is enabled in the Flow Portal |
| Token not accepted | Check that the Client-ID was entered correctly |

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

> **Storage location:** The exported GPX files are stored locally in the Home Assistant config directory at:
> ```
> /config/bosch_ebike_gps/
> ```

---

### License

MIT License — see [LICENSE](LICENSE) for details.

### Credits

Built by [Volker Hauffe](https://github.com/Xunil99).

This integration uses the official [Bosch eBike Data Act API](https://portal.bosch-ebike.com/data-act).
