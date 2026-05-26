# Tour-Planung mit Höhenprofil und Range-Check — Design + Implementierungsplan

Stand: 2026-05-26
Status: Entwurf, kein Implementierungs-Commitment

## Ziel

Ein Bosch-eBike-User soll im Home-Assistant-Dashboard Touren planen können,
inklusive Strecke auf Karte, Höhenprofil und realistischer
Reichweitenschätzung basierend auf aktuellem Akkustand,
Unterstützungsstufe, Topografie und optional Wetter.

Differenzierungsmerkmal gegenüber generischen Routing-Tools: Wir nutzen
die echten Live-Daten der Bosch-Integration (Akkustand, Bike-Modell,
Sensoren) und liefern eine eBike-spezifische Antwort auf "kommst du an?"
inklusive Stufen-Vergleich ("in Eco schaffst du es, in Sport nicht").

## Nicht-Ziele

- Echtzeit-Navigation während der Fahrt (das macht Komoot/Garmin besser)
- Sprach-Turn-by-Turn-Anweisungen
- Crowdsourced-Streckendaten oder eigene Track-Hosting-Infrastruktur
- Mobile-App-eigene Routenplaner (HA Companion ist ausreichend mobil)

## Übersicht der vier Phasen

| Phase | Dauer | Liefert |
|-------|-------|---------|
| 1     | 3 bis 5 Tage | Browser-only Routenplanung mit brouter.de und Range-Calc |
| 2     | 1 Woche | Backend-Wrapper, Caching, Persistenz, WS-API |
| 3     | 1 bis 2 Wochen | HA-Add-on für Self-Hosted BRouter |
| 4     | 1 Woche | eBike-spezifisches Profil, Range-Refinement, Wetter, GPX-Export |

Gesamt: rund 5 bis 6 Wochen Wochenend-Pace, deutlich schneller bei
Vollzeit oder paralleler Subagent-Bearbeitung.

---

## Phase 1: Browser-only Routenplanung

**Ziel:** User kann auf der Map-Card eine Route planen und sofort sehen,
ob sein aktueller Akkustand ausreicht.

### Architektur

- Modus-Switch in der bestehenden `bosch-ebike-map-card`: "Historie" /
  "Tour planen"
- Direkt-Anfrage an brouter.de aus dem Browser (keine HA-Backend-Änderung)
- Routen leben nur im Editor-Memory der Karte
- Höhenprofil + Range-Calc rein clientseitig

### Tasks

**T1.1: Map-Card Mode-Switch**
- Existing Map-Card um Tab-Bar erweitern: "Touren" und "Route planen"
- State-Variable `_mode = "history" | "planner"`
- Bei Modus-Wechsel altes Layer-Set ausblenden, neues einblenden
- Tests: switching erhält Karten-Zoom und Center

**T1.2: Wegpunkt-Verwaltung**
- Linksklick auf Karte fügt Wegpunkt hinzu (max 8 Wegpunkte)
- Drag verschiebt Wegpunkt, Route wird neu berechnet (debounced 300 ms)
- Rechtsklick auf Wegpunkt löscht ihn
- Spezielle Buttons: "Start = aktuelle Bike-Position" (aus Live-GPS-Sensor),
  "Start = Home Zone", "Ziel = Home Zone"
- Visuelles Marker-Pattern: Start grün, Ziel rot, Wegpunkte gelb

**T1.3: BRouter-Client (Browser)**
- Neue Helper-Klasse `BRouterClient` in der Card
- Methode `route(waypoints, profile, format='geojson')`
- HTTP-GET an `https://brouter.de/brouter?lonlats=...&profile=trekking&format=geojson`
- Error-Handling: Server unerreichbar, kein Pfad gefunden, Timeout (10 s)
- Result-Parsing: GeoJSON-Feature mit `coords[lon, lat, ele]`, Properties
  enthalten `track-length`, `total-time`, `cost-per-km`
- Tests: Mock-Server, valider Track, Edge-Cases

**T1.4: Strecken-Layer auf Leaflet**
- Polyline aus den geparsten Koordinaten
- Farbverlauf nach Range-Status: grün/gelb/rot pro Segment
- Klick auf Strecke zeigt Wegpunkt-Optionen
- Auto-Fit-Bounds nach Routenberechnung

**T1.5: Höhenprofil-Diagramm**
- Pure SVG-Komponente, keine externe Lib (Bundle-Größe!)
- X-Achse: Streckendistanz in km
- Y-Achse links: Höhe in Metern
- Y-Achse rechts: Akkustand-Prognose in Prozent
- Filled Area-Chart für Höhe (hellgrau), Linie für Akku-Verlauf
- Hover zeigt Tooltip mit km-Position, Höhe, Restakku
- Klick auf Diagramm setzt einen Karten-Marker auf entsprechender Position

**T1.6: Range-Calculator (clientseitig)**
- Pure-Function-Modul `_calculateRange(routeStats, bikeState, mode)`
- Eingaben:
  - `routeStats`: total_km, total_climb_m, total_descent_m, avg_grade
  - `bikeState`: battery_wh_available (= soc_percent * nominal_wh / 100)
  - `mode`: "eco" | "tour" | "sport" | "turbo" | "emtb"
  - Optional `temperature_c`, `headwind_kmh` (für Phase 4)
- Konsumtabelle (initial, in Phase 4 verfeinert):
  ```
  base_wh_per_km = {eco: 5, tour: 8, sport: 11, turbo: 16, emtb: 11}
  wh_per_climb_m = {eco: 2.5, tour: 3.5, sport: 5, turbo: 7, emtb: 4}
  ```
- Output: `{required_wh, available_wh, status: "ok"|"tight"|"insufficient",
  km_max, recommended_mode}`
- Bestimmung `recommended_mode`: höchste Stufe, in der die Tour gerade
  noch schaffbar ist mit 10 Prozent Reserve
- Tests: deterministische Fixtures für jeden Modus, Edge-Cases (kein Akku,
  flache Strecke, extreme Steigung)

**T1.7: Range-Ampel UI**
- Prominente Box neben/über dem Höhenprofil
- Ampel-Indikator: grüner/gelber/roter Kreis
- Klartext: "Schaffst du in Tour mit 18 Prozent Reserve" /
  "Sehr knapp in Sport, besser Tour" / "Nicht schaffbar, fehlen 120 Wh"
- Stufen-Vergleichszeile: kleine Pillen "Eco OK / Tour OK / Sport eng /
  Turbo zu wenig"
- Optional: "Was wäre wenn"-Slider für Akku-Stand-Simulation

**T1.8: Bike-Modell-Akkukapazität**
- Mapping `bike_model -> nominal_battery_wh` in `BIKE_BATTERY_MAP`
  in der Card-JS (Bosch-bekannte Werte: 400, 500, 625, 750, 800, 1000 Wh)
- Auto-Detection aus dem Bosch-Bike-Modell, falls verfügbar
- Manueller Override im Card-Setting

**T1.9: i18n für neue Strings**
- 6 Locales (en/de/nl/fr/it/es) erweitern um:
  - `planner_mode_label`, `planner_start_label`, `planner_dest_label`,
    `planner_calculating`, `planner_range_ok`, `planner_range_tight`,
    `planner_range_insufficient`, `planner_recommended_mode`,
    `planner_clear_waypoints`, `planner_no_route_found`, etc.
- Konsistente Bezeichner mit den anderen Translation-Keys

**T1.10: Tests + lokale Verifikation**
- Unit-Tests für Range-Calculator
- Integration-Test gegen brouter.de (CI-Skip-Marker, weil externer Dienst)
- Manueller Bug-Bash:
  - Kurze Stadtroute (sollte trivial OK sein)
  - Steile Bergroute (sollte Akku-Problem zeigen)
  - Wegpunkt-Drag in Echtzeit
  - Browser-Reload während Routenberechnung
  - Switch zwischen Historie und Planner zurück

### Akzeptanzkriterien Phase 1

- User kann Route durch zwei Klicks anlegen
- Höhenprofil erscheint unter der Karte in unter 3 Sekunden
- Range-Ampel zeigt korrekten Status für Test-Fixtures
- Keine Backend-Änderung notwendig
- Bestehende Map-Card-Funktionen (Historie) funktionieren unverändert

---

## Phase 2: Backend-Wrapper + Caching + Persistenz

**Ziel:** Routen werden serverseitig persistiert, gecached, und können
zwischen Devices und Browser-Sessions geteilt werden.

### Architektur-Änderungen

- Neuer Python-Service-Layer `BRouterClient` im Custom-Component
- HA-Storage-Helper für saved routes (analog Maintenance-Items)
- WebSocket-API: `bosch_ebike/routes/list`, `save`, `delete`, `calculate`
- Frontend ruft nicht mehr brouter.de direkt an, sondern HA-Backend
- Server-seitiges Caching: identische Wegpunkte → gleiche Antwort,
  TTL 24 Stunden, max 200 Einträge im Memory

### Tasks

**T2.1: BRouterClient (Python)**
- `custom_components/bosch_ebike/brouter_client.py`
- Async HTTP-Client mit aiohttp (sowieso schon Dependency in HA)
- Methode `async route(waypoints, profile) -> RouteResult`
- Konfigurierbar: `base_url`, `timeout`, `max_retries`
- Strukturierte Errors: `BRouterUnavailableError`, `NoRouteError`
- Tests mit aioresponses-Mock

**T2.2: RouteCache**
- `custom_components/bosch_ebike/route_cache.py`
- LRU-Cache mit TTL (24 h Default)
- Schlüssel: SHA1 über (waypoints_normalized, profile)
- Persistierung im HA-Storage (überlebt Restart)
- Tests für TTL-Ablauf, Eviction-Logik, Schlüssel-Stabilität

**T2.3: RouteStorage (saved routes)**
- `custom_components/bosch_ebike/route_storage.py`
- Pro Account-ID eine Liste von Saved-Routes
- Schema: `{id, name, waypoints, profile, created_at, last_used_at,
  preferred_mode, notes}`
- HA-Storage-API mit Version-Migrations-Stub
- CRUD: list, get, save (create/update), delete
- Tests inkl. Migrations-Skeleton

**T2.4: WebSocket-API**
- `custom_components/bosch_ebike/websocket_routes.py`
- Endpoints:
  - `bosch_ebike/routes/list` → Liste der gespeicherten Routen
  - `bosch_ebike/routes/save` → speichert/aktualisiert
  - `bosch_ebike/routes/delete` → löscht per ID
  - `bosch_ebike/routes/calculate` → berechnet (mit Cache-Lookup) und gibt
    GeoJSON zurück
- Auth-Check über HA-Standard-Mechanismen
- Tests pro Endpoint

**T2.5: Settings für Routing-Provider**
- Config-Flow-Option: Server-URL und Provider-Typ (brouter, ors, custom)
- ORS-Adapter optional in dieser Phase (kann später) oder
  als Folge-Task
- Validation: Test-Anfrage beim Speichern, Fehler verständlich

**T2.6: Frontend-Umstellung auf WS-API**
- BRouterClient im JS wird zu einem `RouteService`-Wrapper, der mit dem
  HA-Backend statt direkt mit brouter.de redet
- Reuse des `_haCall(method, payload)`-Patterns aus existing Cards
- Migration: vorhandene clientseitige Routen aus Phase 1 werden bei
  erstem Öffnen ins Backend gesynct (einmalig, mit "Cleanup local cache")

**T2.7: Saved-Routes-Liste in der Card**
- Neuer Bereich "Meine Routen" in der Map-Card im Planner-Mode
- Aufklappbare Liste der gespeicherten Routen
- Klick → lädt Route auf Karte + recalcuates Range mit aktuellem Akku
- Kontextmenü: umbenennen, löschen, duplizieren, exportieren
- Tests: Speichern, Laden, Löschen

**T2.8: i18n-Erweiterung**
- Neue Keys für Saved-Routes, Cache-Status, Provider-Settings
- Wieder alle 6 Locales

### Akzeptanzkriterien Phase 2

- Routen überleben Browser-Reload und HA-Restart
- Wiederholter Aufruf derselben Route schlägt im Cache und kommt
  in unter 100 ms zurück
- HA-User können in der Integration-Config einen alternativen Routing-Server
  eintragen
- Existierende Phase-1-Funktionalität unverändert nutzbar

---

## Phase 3: HA-Add-on für Self-Hosted BRouter

**Ziel:** One-Click-Installation eines lokalen BRouter-Servers für
HA-OS/Supervised-User. Auto-Discovery in der Integration.

### Architektur

- Separates Repository `Xunil99/ha-bosch-ebike-addons` (HA-Add-on-Konvention:
  Add-ons leben in ihrem eigenen Repo, nicht im Integration-Repo)
- Add-on-Verzeichnis `brouter/` mit Standard-HA-Add-on-Struktur
- Docker-Image basierend auf einem schlanken Java-JRE Alpine-Image
- Optionale Region-Konfiguration (germany, europe, world)
- Persistente Speicherung der RD5-Segmente in `/data`

### Repo-Struktur

```
ha-bosch-ebike-addons/
├── README.md
├── repository.json
└── brouter/
    ├── config.yaml          # HA-Add-on-Metadata
    ├── Dockerfile
    ├── build.yaml           # Multi-Arch-Build-Config
    ├── translations/
    │   ├── en.yaml
    │   └── de.yaml
    ├── rootfs/
    │   ├── etc/
    │   │   └── services.d/brouter/run
    │   └── usr/
    │       └── local/bin/
    │           ├── download-segments.sh
    │           └── start-brouter.sh
    ├── DOCS.md
    └── CHANGELOG.md
```

### Tasks

**T3.1: Add-on-Repo anlegen**
- Neues Repo erstellen mit `repository.json`:
  ```json
  {
    "name": "Bosch eBike Add-ons",
    "url": "https://github.com/Xunil99/ha-bosch-ebike-addons",
    "maintainer": "Volker Hauffe"
  }
  ```
- README mit Installations-Anleitung (Add-on-Store, Custom-Repo-URL hinzufügen)
- LICENSE (MIT, konsistent mit BRouter selbst)

**T3.2: Add-on config.yaml**
- Schema-Definition für User-Config:
  ```yaml
  name: BRouter for Bosch eBike
  version: 0.1.0
  slug: brouter
  description: Local BRouter routing server for the Bosch eBike integration
  arch: [aarch64, amd64, armv7]
  init: false
  startup: services
  ports:
    17777/tcp: 17777
  options:
    region: germany
    java_heap_mb: 512
    download_on_start: true
  schema:
    region: list(germany|europe|world)
    java_heap_mb: int(256, 4096)
    download_on_start: bool
  ```

**T3.3: Dockerfile**
- Basis: `openjdk:17-jre-alpine` (~120 MB)
- BRouter-JAR aus offiziellem Release laden (pinned Version)
- Standard-Profile mitkopieren
- Entrypoint via S6-Overlay (HA-Add-on-Convention)

**T3.4: Segment-Download-Script**
- `download-segments.sh`: holt RD5-Files von `brouter.de/brouter/segments4/`
- Region-spezifische Filter:
  - germany: ca. 18 Tiles, ca. 300 MB
  - europe: ca. 230 Tiles, ca. 3 GB
  - world: alle Tiles, ca. 7 GB
- Skip wenn schon vorhanden und nicht älter als 30 Tage
- Fortschritt in der HA-Add-on-Log-UI sichtbar

**T3.5: Startup-Script**
- `start-brouter.sh`: setzt JVM-Heap aus Config, startet BRouter mit
  Pfad zu den heruntergeladenen Segmenten
- Logs auf STDOUT (für HA-Log-UI)
- Health-Check via HTTP-GET auf `/brouter` (BRouter antwortet mit
  einem Hilfe-Text auf der Root)

**T3.6: Multi-Arch-Build**
- `build.yaml` mit aarch64 (Raspi 4/5), amd64 (NUC/x86), armv7 (Raspi 3)
- GitHub Actions Workflow für Multi-Arch-Docker-Build und Push zur
  GitHub Container Registry (ghcr.io)

**T3.7: Add-on-Doku**
- DOCS.md mit Setup-Schritten, Region-Empfehlung, Troubleshooting
- Hinweis auf Self-Update der Segmente
- Hinweis auf Speicherbedarf

**T3.8: Integration-Auto-Discovery**
- In der `custom_components/bosch_ebike/`: Logik die prüft, ob das Add-on
  installiert und erreichbar ist
- Via Supervisor-API: `GET /addons/info/local_brouter`
- Falls erreichbar: setze `base_url` automatisch auf
  `http://local_brouter:17777`
- Banner im Config-Flow:
  - Add-on nicht installiert: "Möchtest du BRouter lokal hosten?
    [Add-on installieren]"
  - Add-on installiert: "BRouter Add-on erkannt, nutze lokal"

**T3.9: End-to-End-Test**
- Auf HA-OS-Testinstallation: Add-on installieren, starten, Logs prüfen,
  Test-Anfrage senden, Integration verbinden lassen, Test-Route planen
- Auf nicht-Supervised-HA: Fallback auf brouter.de funktioniert

**T3.10: README-Cross-Linking**
- ha-bosch-ebike README erwähnt das Add-on-Repo
- Add-on-Repo README erwähnt die Integration
- HACS-Beschreibung leicht aktualisieren

### Akzeptanzkriterien Phase 3

- Add-on installiert in unter 3 Minuten auf einem Raspi 4
- Erstes Setup mit germany-Region innerhalb von 5 Minuten produktiv
- HA-Integration findet das Add-on automatisch
- Routing-Performance lokal: unter 500 ms für eine 30-km-Strecke
- Speicher: weniger als 700 MB RAM für germany

---

## Phase 4: eBike-Profil + Range-Refinement + Polish

**Ziel:** Routing und Range-Berechnung werden eBike-spezifisch genau,
mit Wetter-Korrektur und Self-Learning-Modus. Plus GPX-Export für
Bike-Computer.

### Tasks

**T4.1: Custom BRouter-Profil `bosch_ebike.brf`**
- Eigene BRF-Profildatei mit eBike-relevanten Cost-Functions:
  - Höhere Toleranz für moderate Steigungen (2 bis 6 Prozent), weil
    eBike-Boost diese fast unsichtbar macht
  - Mittlere Geschwindigkeit auf 25 km/h kalibriert (gesetzliche
    EU-Pedelec-Grenze)
  - Geteerte und chausserte Wege bevorzugt vor losen Schotterwegen
    (eBikes sind 25 bis 28 kg schwer)
  - Hauptstraßen mit hoher Auto-Frequenz vermieden, aber nicht
    verboten (Fahrer-Auswahl)
- Profil in der Integration mitgeliefert, im Add-on automatisch in das
  BRouter-Profil-Verzeichnis kopiert
- Im Card-Setting: Profil-Auswahl mit `bosch_ebike` als Default,
  `trekking` und `fastbike` als Alternativen

**T4.2: Self-Learning-Verbrauchsmodell**
- Nach jeder beendeten Tour (aus Bosch-API-Track-Daten):
  - Berechne `actual_wh_per_km` und `actual_wh_per_climb_m`
  - Aktualisiere User-spezifische Konstanten via gleitender
    Durchschnitt (z.B. Exponential Smoothing mit α = 0.2)
  - Speichere im Bike-Profil
- Range-Calculator nutzt user-spezifische Konstanten, falls vorhanden,
  sonst Defaults
- Optional: Reset-Button im Setting "Verbrauchskalibrierung zurücksetzen"

**T4.3: Wetter-Korrektur**
- Falls eine HA-Weather-Entity konfiguriert (auto-detect via
  config_entry oder explizit gewählt):
  - Hole aktuelle und vorhergesagte Temperatur, Wind, Luftdruck
  - Korrigiere available_battery_wh entsprechend Temperatur
    (linear unter 10 Grad)
  - Korrigiere required_wh entsprechend Gegen-/Rückenwind (basierend
    auf Routen-Richtung vs. Wind-Richtung)
- Anzeige in der Range-Box: "Mit aktuellem Wetter 15 Prozent
  ungünstiger berücksichtigt"

**T4.4: Charging-Stop-Suggestions (optional)**
- Wenn Route den Akku nicht schafft: Suche entlang der Strecke
  Lade-Möglichkeiten
- Datenquelle: OSM-Overpass-API mit `amenity=charging_station`
  + `bicycle=yes` Filter
- Markiere mögliche Stops auf der Karte mit Steckdosen-Icon
- Range-Plan: "Mit einem Stop bei [Cafe Müller, km 22] schaffst du es"

**T4.5: GPX-Export**
- Button "Als GPX exportieren" in der Saved-Route-Liste
- Generiert standard-konformes GPX (waypoints + track)
- Download als File via Browser
- Importierbar in Garmin Connect, Komoot, Strava etc.

**T4.6: Optionaler ORS-Adapter**
- Falls in Phase 2 noch nicht eingebaut: jetzt ORS-Provider-Plugin
- Gleiche Schnittstelle wie BRouterClient, aber mit ORS-API
- Config-Flow zeigt API-Key-Eingabe für ORS
- User können wählen: BRouter (default), ORS, Custom

**T4.7: Companion-App-Optimierung**
- Tests in HA Companion (iOS und Android)
- Touch-Targets prüfen (Wegpunkt-Drag auf Touch-Display)
- Höhenprofil bei kleiner Screen-Breite responsiv
- Performance auf älteren Mobile-Geräten

**T4.8: Dokumentation und Screenshots**
- README-Sektion "Tour-Planung" mit Screenshots
- FAQ: "Warum schätzt das System meine Reichweite zu konservativ?"
  → Self-Learning-Modus, mindestens 10 Touren
- Hinweise zu Provider-Wahl und Self-Hosting

**T4.9: Release v1.18.0**
- Klare Release-Notes
- Migration-Hinweise (keine Breaking Changes erwartet, aber neue
  Settings)
- HACS-Eintrag aktualisieren

### Akzeptanzkriterien Phase 4

- Self-Learning erreicht nach 10 Touren einen Schätzfehler unter 8 Prozent
- Custom-Profil routet messbar anders als Default-trekking-Profil bei
  hügeligen Strecken
- Wetter-Korrektur ist nachvollziehbar (Anzeige der Korrektur-Faktoren)
- GPX-Export validiert sauber in Garmin Connect

---

## Querschnittliche Aspekte

### Tests

- Pro Phase eigener Test-Pass
- Frontend: Vitest oder Jest für Range-Calculator-Logik
- Backend: pytest mit aiohttp-Mocks
- Integration: pytest-homeassistant-custom-component
- E2E: manueller Bug-Bash pro Phase plus Checkliste in PR-Template

### i18n

- Alle 6 Locales (en/de/nl/fr/it/es) durchgängig pflegen
- Neue Strings konsistent benennen: `planner_*`
- Bei jedem Release Translation-Parity-Check (alle Locales haben dieselben
  Keys)

### Backward Compatibility

- Bestehende User dürfen durch das Feature nicht beeinträchtigt werden
- Card-Default ist "Historie", "Planner" muss explizit aktiviert werden
- Saved-Routes-Storage hat Migrations-Stub für künftige Schema-Änderungen
- Add-on ist optional, kein Pflicht-Update

### Performance-Budgets

- Route-Berechnung von 30 km: unter 3 Sekunden bei brouter.de, unter
  500 ms beim Self-Hosted Add-on
- Karten-Layer-Update beim Wegpunkt-Drag: unter 100 ms perceptual
- Höhenprofil-Render: unter 200 ms
- WS-Aufrufe: maximal ein Aufruf pro 300 ms (debounced)

### Risiken

- **brouter.de-Verfügbarkeit:** mitigiert durch ORS-Fallback und Self-Hosting
- **Bosch-API-Bike-Modell-Mapping:** falls Akku-Kapazität nicht erkannt,
  muss User manuell wählen
- **Self-Learning-Bias:** wenn User immer denselben Modus fährt, lernt
  das Modell nur für diesen. Defaults für unbekannte Modi werden nicht
  überschrieben.
- **Add-on-Maintenance:** wir hängen an BRouter-JAR-Releases. Pin auf
  konkrete Version, Test bei Updates.

### Reihenfolge der Releases

- v1.17.0: Phase 1 (Browser-only Planner) — sichtbares Feature für
  alle User
- v1.17.x: Phase 2 (Backend + Persistenz) — User-Quality-of-Life
- v1.18.0: Phase 3 (Add-on) + Phase 4 (Polish) — Premium-Self-Hosters
  bekommen die volle Erfahrung

Phasen 3 und 4 können auch unabhängig voneinander released werden, wenn
einer von beiden länger dauert.

## Beschluss-Status

Aktuell: Entwurf, keine Implementierungsfreigabe. Diese Datei ist die
Grundlage für eine spätere Entscheidung, ob und in welcher Reihenfolge
die Phasen tatsächlich gebaut werden.

Wenn ja, würde ich pro Phase eine eigene `*-implementation.md` mit
Task-Listen analog zur ebike_ble_broadcast-Vorgehensweise anlegen und
dann via Subagent-Driven-Development abarbeiten.
