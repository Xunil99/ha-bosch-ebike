# Routenplaner-Card (BRouter) — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (bzw. subagent-driven-development) to implement this plan task-by-task.

**Goal:** Neue Lovelace-Card `bosch-ebike-routeplanner-card`: Wegpunkte klicken → BRouter-Route mit Distanz/Höhe/Fahrzeit/Verbrauchs-Schätzung + Akku-Check, Höhenprofil-SVG und GPX-Export.

**Architecture:** Backend-WS-Proxy `bosch_ebike/plan_route` (Muster `get_pois`) mit reiner, standalone testbarer URL-Bau-/Validierungsfunktion in neuem Modul `brouter.py`. Frontend: sechste Card im bestehenden Bundle `www/bosch-ebike-map-card.js` (Leaflet, I18N-Objekt, customCards-Registrierung wie die fünf vorhandenen Cards).

**Tech Stack:** HA websocket_api + aiohttp (Backend), Vanilla-JS/Leaflet im bestehenden Single-File-Bundle (Frontend). Tests: Plain-Assert-Python (wie `tests/test_range_estimate.py`), `node --check` fürs Bundle.

**Design-Doc:** `docs/plans/2026-06-10-routeplanner-design.md`
**Repo:** `/tmp/hbcl` — Commits via `git -c user.email="v.hauffe@me.com" -c user.name="Volker Hauffe"`, NIE Co-Author, NICHT pushen (Release erst nach User-Test, Task 8).

---

## Referenz: vorhandene Muster

- **WS-Proxy:** `__init__.py` — `ws_overpass_pois` (`bosch_ebike/get_pois`): voluptuous-Schema-Decorator + `@websocket_api.async_response`; Registrierung in der Liste bei `async_setup` (~Zeile 85-95). Session via `homeassistant.helpers.aiohttp_client.async_get_clientsession` (prüfen, wie ws_overpass_pois sie holt — gleich machen).
- **Cards:** `www/bosch-ebike-map-card.js` (10.8k Zeilen): `I18N`-Objekt (en/de/nl/fr/it/es, Zeile 10-1670, Funktions-Werte erlaubt, z. B. `profile_min_max`), Leaflet-Loader (Promise-basiert, ~Zeile 1780, von `BoschEBikeMapCard` genutzt — Aufrufer suchen und dieselbe Funktion verwenden), Card-Klassen `extends HTMLElement` mit `setConfig`/`set hass`/`getConfigElement`/`getStubConfig`, Editor-Klassen, Registrierung am Dateiende (`customElements.define` ~10769ff + `window.customCards.push` ~10799ff).
- **WS-Aufruf aus der Card:** `this._hass.callWS({ type: "bosch_ebike/get_pois", ... })` (~Zeile 3702).

---

### Task 1: Backend — reine URL-/Validierungslogik (TDD)

**Files:**
- Create: `tests/test_brouter.py`
- Create: `custom_components/bosch_ebike/brouter.py`

**Step 1: Failing Test** (`tests/test_brouter.py`, gleicher importlib-Lade-Stil wie `tests/test_range_estimate.py` — Modul direkt aus Dateipfad laden, KEIN Package-Import):

```python
"""Standalone tests for brouter.py — run with: python3 tests/test_brouter.py"""
import importlib.util
from pathlib import Path

_path = Path(__file__).resolve().parent.parent / "custom_components" / "bosch_ebike" / "brouter.py"
_spec = importlib.util.spec_from_file_location("brouter", _path)
brouter = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(brouter)

build_brouter_url = brouter.build_brouter_url
BRouterRequestError = brouter.BRouterRequestError


def expect_error(fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
    except BRouterRequestError:
        return
    raise AssertionError("expected BRouterRequestError")


def test_happy_path_default_base():
    url = build_brouter_url(None, [[12.35, 48.71], [12.45, 48.75]], "trekking")
    assert url == (
        "https://brouter.de/brouter"
        "?lonlats=12.35,48.71|12.45,48.75"
        "&profile=trekking&alternativeidx=0&format=geojson"
    ), url


def test_custom_base_and_trailing_slash():
    url = build_brouter_url("http://192.168.2.50:17777/", [[1.0, 2.0], [3.0, 4.0]], "mtb")
    assert url.startswith("http://192.168.2.50:17777/brouter?lonlats=1.0,2.0|3.0,4.0&profile=mtb"), url


def test_rejects_bad_profile():
    expect_error(build_brouter_url, None, [[1.0, 2.0], [3.0, 4.0]], "car-eco")


def test_rejects_bad_scheme():
    expect_error(build_brouter_url, "ftp://evil", [[1.0, 2.0], [3.0, 4.0]], "trekking")
    expect_error(build_brouter_url, "file:///etc", [[1.0, 2.0], [3.0, 4.0]], "trekking")


def test_rejects_too_few_or_too_many_points():
    expect_error(build_brouter_url, None, [[1.0, 2.0]], "trekking")
    expect_error(build_brouter_url, None, [[1.0, 2.0]] * 31, "trekking")


def test_rejects_out_of_range_coords():
    expect_error(build_brouter_url, None, [[181.0, 2.0], [3.0, 4.0]], "trekking")
    expect_error(build_brouter_url, None, [[1.0, 91.0], [3.0, 4.0]], "trekking")


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("ALL TESTS PASSED")
```

**Step 2:** `cd /tmp/hbcl && python3 tests/test_brouter.py` → FileNotFoundError/AttributeError (Modul fehlt).

**Step 3: Implementierung** (`custom_components/bosch_ebike/brouter.py`):

```python
"""BRouter request building/validation for the route-planner card.

Pure module (no Home Assistant imports) so it is standalone-testable,
mirroring range_estimate.py. The actual HTTP call lives in __init__.py.
"""

from __future__ import annotations

from urllib.parse import urlsplit

DEFAULT_BASE_URL = "https://brouter.de"
ALLOWED_PROFILES = ("trekking", "fastbike", "mtb", "shortest")
MIN_POINTS = 2
MAX_POINTS = 30


class BRouterRequestError(ValueError):
    """Invalid route request (bad profile, URL or waypoints)."""


def build_brouter_url(
    base_url: str | None,
    lonlats: list[list[float]],
    profile: str,
) -> str:
    """Validate inputs and build the BRouter GeoJSON request URL."""
    if profile not in ALLOWED_PROFILES:
        raise BRouterRequestError(f"unsupported profile: {profile}")

    if not MIN_POINTS <= len(lonlats) <= MAX_POINTS:
        raise BRouterRequestError(
            f"waypoint count must be {MIN_POINTS}-{MAX_POINTS}, got {len(lonlats)}"
        )

    pairs: list[str] = []
    for point in lonlats:
        try:
            lon, lat = float(point[0]), float(point[1])
        except (TypeError, ValueError, IndexError) as err:
            raise BRouterRequestError(f"invalid waypoint: {point!r}") from err
        if not (-180.0 <= lon <= 180.0 and -90.0 <= lat <= 90.0):
            raise BRouterRequestError(f"waypoint out of range: {point!r}")
        pairs.append(f"{lon},{lat}")

    base = (base_url or DEFAULT_BASE_URL).rstrip("/")
    scheme = urlsplit(base).scheme
    if scheme not in ("http", "https"):
        raise BRouterRequestError(f"unsupported BRouter URL scheme: {scheme!r}")

    return (
        f"{base}/brouter?lonlats={'|'.join(pairs)}"
        f"&profile={profile}&alternativeidx=0&format=geojson"
    )
```

**Step 4:** `python3 tests/test_brouter.py` → `ALL TESTS PASSED` (7 Tests).

**Step 5: Commit:** `feat(routeplanner): BRouter-URL-Bau und -Validierung (reines Modul + Tests)`

---

### Task 2: Backend — WS-Befehl `bosch_ebike/plan_route`

**Files:**
- Modify: `custom_components/bosch_ebike/__init__.py`

**Step 1:** Bestehenden `ws_overpass_pois`-Block lesen (Session-Beschaffung, Fehler-Antwortmuster übernehmen). Import ergänzen: `from .brouter import BRouterRequestError, build_brouter_url`.

**Step 2: Handler** (direkt nach `ws_overpass_pois` einfügen, Stil angleichen):

```python
@websocket_api.websocket_command(
    {
        vol.Required("type"): "bosch_ebike/plan_route",
        vol.Required("lonlats"): [[vol.Coerce(float)]],
        vol.Required("profile"): str,
        vol.Optional("brouter_url"): vol.Any(str, None),
    }
)
@websocket_api.async_response
async def ws_plan_route(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Proxy a routing request to BRouter (CORS-safe, like the POI proxy)."""
    try:
        url = build_brouter_url(msg.get("brouter_url"), msg["lonlats"], msg["profile"])
    except BRouterRequestError as err:
        connection.send_error(msg["id"], "invalid_request", str(err))
        return

    session = async_get_clientsession(hass)
    try:
        async with asyncio.timeout(30):
            resp = await session.get(url)
            body = await resp.text()
    except (TimeoutError, aiohttp.ClientError) as err:
        connection.send_error(msg["id"], "server_unreachable", f"BRouter not reachable: {err}")
        return

    # BRouter returns errors as plain text with status 200 *or* non-200 —
    # treat any non-JSON body as a routing failure and pass the text through.
    if resp.status != 200 or not body.lstrip().startswith("{"):
        connection.send_error(msg["id"], "routing_failed", body.strip()[:300] or f"HTTP {resp.status}")
        return

    try:
        geojson = json.loads(body)
    except ValueError:
        connection.send_error(msg["id"], "routing_failed", "invalid response from BRouter")
        return

    connection.send_result(msg["id"], {"geojson": geojson})
```

Vorher prüfen, welche dieser Imports `__init__.py` schon hat (`asyncio`, `json`, `aiohttp`, `async_get_clientsession`, `vol`, `Any`) — nur Fehlendes ergänzen. HA ≥ 2024.1: falls `asyncio.timeout` dort schon anderweitig genutzt wird, übernehmen; sonst `async_timeout.timeout` NICHT einführen — `asyncio.timeout` existiert ab Python 3.11, Repo-Minimum ist HA 2024.1 (Python 3.12) → ok.

**Step 3:** Registrierung in der Befehlsliste: `websocket_api.async_register_command(hass, ws_plan_route)`.

**Step 4:** `python3 -m py_compile custom_components/bosch_ebike/__init__.py && python3 tests/test_brouter.py | tail -1` → OK / ALL TESTS PASSED.

**Step 5: Commit:** `feat(routeplanner): WS-Proxy bosch_ebike/plan_route für BRouter`

---

### Task 3: Frontend — I18N-Schlüssel (6 Sprachen)

**Files:**
- Modify: `custom_components/bosch_ebike/www/bosch-ebike-map-card.js` (I18N-Objekt, alle 6 Sprachblöcke)

In JEDEN Sprachblock (en/de/nl/fr/it/es) folgende Keys einfügen (Texte unten; Funktions-Keys wie bestehendes `profile_min_max`). Englisch als Referenz:

```js
    // Route planner card
    rp_card_name: "Bosch eBike Route Planner",
    rp_card_desc: "Plan bike routes with BRouter: consumption estimate, battery check and GPX export",
    rp_default_title: "Route planner",
    rp_hint_click: "Click the map to set start and destination — more clicks add via points. Drag markers to move, click a marker to remove it.",
    rp_profile_label: "Profile",
    rp_profile_trekking: "Trekking",
    rp_profile_fastbike: "Road bike",
    rp_profile_mtb: "MTB",
    rp_profile_shortest: "Shortest",
    rp_reset: "Reset",
    rp_export_gpx: "Export GPX",
    rp_routing: "Calculating route …",
    rp_stat_distance: "Distance",
    rp_stat_ascent: "Ascent",
    rp_stat_descent: "Descent",
    rp_stat_time: "Ride time",
    rp_stat_energy: "Est. consumption",
    rp_batt_line: (wh, pct, soc) => `Needs ~${wh} Wh ≈ ${pct} % · battery now: ${soc} %`,
    rp_estimate_note: "Estimate based on your average consumption — actual range depends on assist mode, terrain, wind and temperature.",
    rp_hilly_note: "Lots of climbing on this route — the estimate may be too optimistic.",
    rp_err_no_route: "No route found (waypoint off the road network or outside coverage?)",
    rp_err_server: "Routing server not reachable",
    rp_privacy_note: "Waypoints are sent to the configured BRouter server (default: brouter.de).",
```

Deutsch: `rp_card_name: "Bosch eBike Routenplaner"`, `rp_card_desc: "Fahrrad-Routen mit BRouter planen: Verbrauchs-Schätzung, Akku-Check und GPX-Export"`, `rp_default_title: "Routenplaner"`, `rp_hint_click: "Klicke auf die Karte für Start und Ziel — weitere Klicks ergänzen Zwischenpunkte. Marker ziehen = verschieben, Marker anklicken = löschen."`, `rp_profile_label: "Profil"`, `rp_profile_fastbike: "Rennrad"`, `rp_profile_shortest: "Kürzeste"`, `rp_reset: "Zurücksetzen"`, `rp_export_gpx: "GPX exportieren"`, `rp_routing: "Route wird berechnet …"`, `rp_stat_distance: "Distanz"`, `rp_stat_ascent: "Anstieg"`, `rp_stat_descent: "Abstieg"`, `rp_stat_time: "Fahrzeit"`, `rp_stat_energy: "Verbrauch (geschätzt)"`, `rp_batt_line: (wh, pct, soc) => \`Benötigt ~${wh} Wh ≈ ${pct} % · Akku aktuell: ${soc} %\``, `rp_estimate_note: "Schätzung auf Basis deines Durchschnittsverbrauchs — die tatsächliche Reichweite hängt von Unterstützungsmodus, Topografie, Wind und Temperatur ab."`, `rp_hilly_note: "Viele Höhenmeter auf der Route — die Schätzung kann zu optimistisch sein."`, `rp_err_no_route: "Keine Route gefunden (Wegpunkt abseits des Wegenetzes oder außerhalb der Abdeckung?)"`, `rp_err_server: "Routing-Server nicht erreichbar"`, `rp_privacy_note: "Wegpunkte werden an den konfigurierten BRouter-Server gesendet (Standard: brouter.de)."`
NL/FR/IT/ES: sinngemäß idiomatisch übersetzen (Stil der vorhandenen Blöcke; "Trekking"/"MTB" bleiben, fastbike → nl "Racefiets" / fr "Vélo de route" / it "Bici da corsa" / es "Bicicleta de carretera").

Verify: `node --check custom_components/bosch_ebike/www/bosch-ebike-map-card.js` und `node -e 'const s=require("fs").readFileSync("custom_components/bosch_ebike/www/bosch-ebike-map-card.js","utf8"); for (const k of ["rp_default_title","rp_batt_line","rp_export_gpx"]) { const c=(s.match(new RegExp(k,"g"))||[]).length; if (c<6) throw new Error(k+" nur "+c+"x"); } console.log("I18N OK")'`

Commit: `feat(routeplanner): I18N-Texte für die Planer-Card (6 Sprachen)`

---

### Task 4: Frontend — Card-Klasse `BoschEBikeRoutePlannerCard`

**Files:**
- Modify: `custom_components/bosch_ebike/www/bosch-ebike-map-card.js` (neue Klasse nach `BoschEBike3DMapCard`-Block, vor den Editor-Klassen oder am Strukturäquivalent — Lesbarkeit zählt)

Kern-Anforderungen (Methoden vollständig implementieren, vorhandene Card-Klassen als Stilreferenz lesen):

```js
class BoschEBikeRoutePlannerCard extends HTMLElement {
  // setConfig(config): title (default _t("rp_default_title")), height (480),
  //   brouter_url (string|leer), entity (string|leer), soc_entity (string|leer)
  // set hass(hass): erste Zuweisung → _initialize() (einmalig), danach nur speichern
  // getCardSize(), static getConfigElement(), static getStubConfig() → { height: 480 }
}
```

1. **Karte:** denselben Leaflet-Loader verwenden wie `BoschEBikeMapCard` (Aufrufer von „window.L && typeof window.L.map" suchen). OSM-Tile-Layer wie Map-Card. Start-Center: `this._hass.config.latitude/longitude`, Zoom 13.
2. **Wegpunkte:** Karten-Klick → Marker (draggable; Start grün, Ziel rot, Zwischenpunkte blau — Farb-Marker-Helper der Map-Card wiederverwenden, falls vorhanden, sonst `L.circleMarker`). `dragend` → Neuberechnung; Marker-Klick → Punkt entfernen; max. 30 Punkte (MAX wie Backend).
3. **Neuberechnung:** debounced 600 ms; bei < 2 Punkten Route/Stats leeren. WS:
   ```js
   const res = await this._hass.callWS({
     type: "bosch_ebike/plan_route",
     lonlats: this._waypoints.map((m) => { const ll = m.getLatLng(); return [ll.lng, ll.lat]; }),
     profile: this._profile,
     brouter_url: this._config.brouter_url || null,
   });
   ```
   Fehlercodes: `routing_failed` → `rp_err_no_route` (+ Servertext klein), `server_unreachable` → `rp_err_server`. Während des Calls `rp_routing` anzeigen. Antworten verwerfen, wenn inzwischen neue Anfrage läuft (Sequenznummer).
4. **Route rendern:** `features[0].geometry.coordinates` ([lon, lat, ele]) als Polyline (Stil an Map-Card-Track anlehnen), `fitBounds` nur bei erster Route nach Wegpunkt-Änderung.
5. **Stats:** aus `features[0].properties`: `track-length` (m → km, 1 Dezimale), `filtered ascend` (m), `plain-ascend` (negativ = Abstieg; Abstieg = ascend − plain-ascend, als positive Zahl), `total-time` (s → „h:mm"). Verbrauch: `wh_per_km` × km (gerundet Wh) — Quelle Schritt 6.
6. **Range-Datenquelle:** `config.entity` oder Auto-Detect: erster `hass.states`-Key, der auf `_estimated_range_full` endet. Attribute: `wh_per_km`, `battery_capacity_wh`. SoC: `config.soc_entity`-State, sonst Schwester-Entity `…_estimated_range_current` → Attribut `current_soc`. Fehlt `wh_per_km` → Verbrauchs-/Akku-Zeilen ausblenden (Stats bleiben).
7. **Akku-Check:** `needPct = energieWh / capacity × 100`; Ampel: `needPct <= soc*0.7` grün ✅, `<= soc` gelb ⚠️, sonst rot ⛔. Zeile via `rp_batt_line(wh, pct, soc)` + Symbol. Darunter immer klein `rp_estimate_note`; zusätzlich `rp_hilly_note`, wenn `filtered ascend > 800`.
8. **Höhenprofil:** kleines Inline-SVG (volle Breite, ~80 px hoch), Polyline aus (kumulierte Distanz, ele). Haversine-Helper der Datei wiederverwenden, falls vorhanden (suchen!), sonst lokal. Bei fehlenden ele-Werten Profil ausblenden.
9. **GPX-Export:**
   ```js
   _exportGpx() {
     const coords = this._lastRouteCoords; if (!coords || coords.length < 2) return;
     const esc = (s) => String(s).replace(/[<>&]/g, (c) => ({ "<": "&lt;", ">": "&gt;", "&": "&amp;" }[c]));
     const name = esc(`Bosch eBike Route ${new Date().toISOString().slice(0, 10)}`);
     const pts = coords.map((c) => {
       const ele = c.length > 2 && Number.isFinite(c[2]) ? `<ele>${Math.round(c[2])}</ele>` : "";
       return `      <trkpt lat="${c[1].toFixed(6)}" lon="${c[0].toFixed(6)}">${ele}</trkpt>`;
     }).join("\n");
     const gpx = `<?xml version="1.0" encoding="UTF-8"?>\n` +
       `<gpx version="1.1" creator="ha-bosch-ebike" xmlns="http://www.topografix.com/GPX/1/1">\n` +
       `  <trk>\n    <name>${name}</name>\n    <trkseg>\n${pts}\n    </trkseg>\n  </trk>\n</gpx>\n`;
     const blob = new Blob([gpx], { type: "application/gpx+xml" });
     const a = document.createElement("a");
     a.href = URL.createObjectURL(blob);
     a.download = `bosch-ebike-route-${new Date().toISOString().slice(0, 10)}.gpx`;
     a.click();
     setTimeout(() => URL.revokeObjectURL(a.href), 5000);
   }
   ```
   Button deaktiviert, solange keine Route da ist.
10. **Bedienleiste** über der Karte: Profil-`<select>`, Reset-Button, GPX-Button, Hinweiszeile `rp_hint_click` (verschwindet nach erster Route). HA-Theme-Variablen wie die anderen Cards (`var(--primary-color)` etc.).

Verify: `node --check …` → OK. Commit: `feat(routeplanner): Planer-Card mit Wegpunkten, Akku-Check, Höhenprofil und GPX-Export`

---

### Task 5: Frontend — Editor + Registrierung

**Files:**
- Modify: `www/bosch-ebike-map-card.js`

1. `BoschEBikeRoutePlannerCardEditor` — Stil der vorhandenen Editoren (z. B. `BoschEBikeDashboardCardEditor` für Entity-Picker lesen): Felder `title` (Text), `height` (Zahl), `brouter_url` (Text, Placeholder `https://brouter.de`), `entity` (Entity-Picker/Dropdown gefiltert auf `_estimated_range_full`), `soc_entity` (Entity-Picker Sensor). Darunter Hinweistext `rp_privacy_note` (klein, gedimmt).
2. Registrierung am Dateiende analog zu den fünf Cards: `customElements.define("bosch-ebike-routeplanner-card", …)` + Editor + `window.customCards.push({ type: "bosch-ebike-routeplanner-card", name: <rp_card_name engl.>, description: <rp_card_desc engl.>, preview: false })` — exakt das Format der Nachbarn übernehmen.
3. Verify: `node --check` OK; `grep -c "bosch-ebike-routeplanner-card" …` ≥ 4.

Commit: `feat(routeplanner): Card-Editor und Registrierung im Card-Picker`

---

### Task 6: README-Doku (6 Sprachen)

**Files:** `README.md` (DE+EN), `README.nl.md`, `README.fr.md`, `README.it.md`, `README.es.md`

Neuer Abschnitt nach dem Reichweiten-Schätzungs-Abschnitt (alle 6 Stellen, strukturgleich). Deutscher Referenztext:

```markdown
### Routenplaner-Card (BRouter)

Die Card `bosch-ebike-routeplanner-card` plant Fahrrad-Routen direkt im Dashboard
— auf Basis des Open-Source-Routers [BRouter](https://brouter.de):

```yaml
type: custom:bosch-ebike-routeplanner-card
height: 480
```

- **Wegpunkte per Klick** auf die Karte (Start, Ziel, beliebige Zwischenpunkte;
  Marker ziehen = verschieben, anklicken = löschen)
- **Profile:** Trekking, Rennrad, MTB, Kürzeste
- **Ergebnis:** Distanz, Anstieg/Abstieg, Fahrzeit, **geschätzter Verbrauch**
  (dein Ø-Verbrauch aus der Reichweiten-Schätzung × Distanz)
- **Akku-Check:** Ampel-Anzeige, ob die Route mit dem aktuellen Akkustand
  machbar ist (benötigt verknüpften Live-Akkustand-Sensor) — wie die
  Reichweiten-Sensoren eine **Schätzung**, keine Garantie
- **Höhenprofil** als Diagramm unter der Karte
- **GPX-Export** der geplanten Route (importierbar in Garmin Connect,
  Komoot, die Flow-App u. a.)

Optionen: `title`, `height`, `brouter_url` (eigene BRouter-Instanz statt
brouter.de), `entity` (Reichweiten-Sensor), `soc_entity` (Live-Akkustand).

> **Datenschutz:** Die Wegpunkt-Koordinaten werden zur Routenberechnung an den
> konfigurierten BRouter-Server gesendet — standardmäßig der spendenfinanzierte
> öffentliche Server `brouter.de`. Wer das nicht möchte, betreibt BRouter selbst
> (Docker) und trägt die URL unter `brouter_url` ein.
```

EN/NL/FR/IT/ES sinngemäß übersetzen (Stil der jeweiligen Datei). Commit: `docs(routeplanner): Routenplaner-Card in allen sechs READMEs dokumentiert`

---

### Task 7: Verifikation (User-Test, KEIN Push davor)

1. `python3 tests/test_brouter.py` + `python3 tests/test_range_estimate.py` → ALL TESTS PASSED
2. `python3 -m py_compile custom_components/bosch_ebike/*.py` → OK
3. `node --check custom_components/bosch_ebike/www/bosch-ebike-map-card.js` → OK
4. **User-Test:** Card hinzufügen, Route Mengkofen → Dingolfing klicken, Profile durchschalten, GPX exportieren und in Garmin Connect importieren, Akku-Check mit Live-SoC prüfen, `brouter_url`-Fehlerfall (falsche URL) zeigt saubere Meldung.

### Task 8: Release (erst nach User-Freigabe!)

`manifest.json` → nächste Subversion. Push, annotiertes Tag, GitHub-Release dreisprachig (DE/EN/NL), Datenschutz-Hinweis (brouter.de) in den Notes. Kein Co-Author.
