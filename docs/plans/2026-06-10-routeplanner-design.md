# Design: Routenplaner-Card auf BRouter-Basis

**Datum:** 2026-06-10
**Status:** Genehmigt (User-Review am 2026-06-10; GPX-Export auf User-Wunsch als eigener Kernpunkt)

## Ziel

Neue Lovelace-Card `bosch-ebike-routeplanner-card`: Fahrrad-Routen direkt im
Dashboard planen (BRouter-Routing, Open Source), mit Verbrauchs-/Akku-Check auf
Basis der Reichweiten-Schätzung (v1.17.2) und **GPX-Export** der geplanten Route.

## Entscheidungen (mit User abgestimmt)

1. **Eigene Planer-Card** (nicht in die bestehende Map-Card integriert,
   kein reiner Backend-Service).
2. **Server:** Default öffentlicher `https://brouter.de`, per Card-Option
   `brouter_url` auf selbst gehostete Instanz umstellbar.
3. **GPX-Export ist Kernfunktion** (Browser-Download, Garmin-tauglich).

## Architektur

- **Backend-Proxy** (Muster wie `bosch_ebike/get_pois`): neuer WS-Befehl
  `bosch_ebike/plan_route` in `__init__.py`.
  - Parameter: `lonlats` (Liste `[lon, lat]`, 2–30 Punkte), `profile`
    (enum: `trekking` | `fastbike` | `mtb` | `shortest`), optional
    `brouter_url` (nur `http(s)://`-URLs, sonst Fehler).
  - Ruft `GET {base}/brouter?lonlats=lon,lat|…&profile=…&alternativeidx=0&format=geojson`
    mit 30-s-Timeout auf, reicht das GeoJSON unverändert durch.
  - Fehlerbilder: BRouter-Fehlertext (z. B. keine Route / Punkt außerhalb
    Abdeckung) → `routing_failed` mit Meldung; Netzfehler/Timeout →
    `server_unreachable`.
- **Frontend:** neue Card im bestehenden Bundle
  `www/bosch-ebike-map-card.js` (gleiche Registrierung wie die fünf
  vorhandenen Cards: `customElements.define` + `window.customCards`).

## Card-Funktionen

1. **Leaflet-Karte** (OSM-Tiles wie Map-Card), Start bei HA-Home-Koordinaten.
2. **Wegpunkte per Klick** setzen (1. Klick = Start, weitere = Ziel/Zwischenpunkte),
   Marker ziehen = verschieben, Klick auf Marker = löschen,
   „Zurücksetzen"-Button. Neuberechnung automatisch, debounced (~600 ms).
3. **Profilwahl-Dropdown:** Trekking (Default), Rennrad (fastbike), MTB, Kürzeste.
4. **Ergebnisleiste:** Distanz (km), Anstieg/Abstieg (m, aus
   `filtered ascend`/`plain-ascend`), Fahrzeit (aus `total-time`),
   **geschätzter Verbrauch** = Distanz × `wh_per_km`
   (Attribut des Sensors `*_estimated_range_full` der gewählten Instanz).
5. **Akku-Check (Ampel):** wenn `wh_per_km`, Kapazität und Live-SoC verfügbar:
   „Benötigt ~210 Wh ≈ 28 % · Akku: 76 % ✅" — grün (< 70 % des verfügbaren
   Akkus), gelb (70–100 %), rot (> 100 %). Klar als **Schätzung**
   gekennzeichnet; Hinweis-Zeile bei > 800 Hm („wh_per_km berücksichtigt
   keine Topografie").
6. **Höhenprofil:** kleines SVG-Diagramm (Höhe über Distanz) aus den
   GeoJSON-Koordinaten (3. Komponente).
7. **GPX-Export-Button:** erzeugt GPX 1.1 (`<trk>` mit `<ele>`, Name =
   „Bosch eBike Route YYYY-MM-DD", Creator-Tag) als Browser-Download —
   importierbar in Garmin Connect/BaseCamp, Komoot, Flow-App etc.

## Card-Konfiguration (+ Editor)

| Option | Default | Bedeutung |
|---|---|---|
| `title` | "Routenplaner" | Header |
| `height` | 480 | Kartenhöhe px |
| `brouter_url` | (leer = brouter.de) | eigene BRouter-Instanz |
| `entity` | (leer) | `sensor.*_estimated_range_full` für Verbrauch/Akku-Check; leer = Auto-Erkennung der ersten Instanz |
| `soc_entity` | (leer) | Live-SoC-Sensor; leer = aus den Range-Sensor-Attributen abgeleitet, sonst kein Akku-Check |

Editor analog zu den bestehenden Card-Editoren (Dropdowns, kein YAML-Zwang).

## Datenschutz / Kennzeichnung

- Hinweis in Editor + README (6 Sprachen): Wegpunkt-Koordinaten gehen an den
  konfigurierten BRouter-Server (Default brouter.de, spendenfinanziert,
  Fair-Use). Kein Layer ist ohne Nutzeraktion aktiv (Planen erfordert Klicks).
- Verbrauchs-/Akku-Werte tragen denselben Schätzungs-Charakter wie die
  Range-Sensoren und werden so beschriftet.

## Bewusst nicht enthalten (YAGNI)

Routen speichern/Favoriten, Turn-by-Turn-Navigation, Rundkurs-Generator,
Senden an Flow-App/Garmin-Gerät, Offline-Routing, alternative Routen
(`alternativeidx>0`), eigene BRouter-Profile.

## Test/Verifikation

- Kein JS-Test-Framework im Repo → Verifikation: `node --check` auf das
  Bundle, py_compile fürs Backend, manuelle Prüfung auf der HA-Instanz des
  Maintainers (Wegpunkte, Profile, GPX-Import in Garmin Connect, Akku-Check
  mit/ohne Live-SoC, Fehlerfall Server unerreichbar).
- Backend-WS-Befehl: Plain-Python-Test der URL-Bau-/Validierungslogik,
  falls als reine Funktion extrahierbar.
