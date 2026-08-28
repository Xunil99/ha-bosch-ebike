/**
 * Bosch eBike Map Card for Home Assistant
 * Robust rewrite focused on view switches, iOS WebView quirks, and hidden-container recovery.
 */

// Sibling modules are imported with THIS module's own "?v=<version>" query
// appended. A static `import ... from "./x.js"` would resolve to the bare URL
// without the query, and the browser would then happily pair a freshly
// downloaded card with a stale cached sibling after an update - exactly the
// bug the ?v= suffix was added to fix (see _async_register_card_resource in
// __init__.py). cache_headers=False alone does NOT prevent this: it was
// already in effect back when users were still being served stale card JS.
// A dynamic import is required because a static import specifier cannot be
// built at runtime; the resulting top-level await just defers this module's
// evaluation until the sibling has loaded.
const { I18N } = await import(
  "./bosch-ebike-i18n.js" + new URL(import.meta.url).search
);

/**
 * Look up a localized string. `hass` may be null during early init.
 * Falls back to English when the requested key is missing.
 */
function ebT(hass, key, ...args) {
  const lang = ((hass && hass.locale && hass.locale.language) || "en")
    .slice(0, 2).toLowerCase();
  const dict = I18N[lang] || I18N.en;
  const value = dict[key] !== undefined ? dict[key] : I18N.en[key];
  if (value === undefined) return key;
  return typeof value === "function" ? value(...args) : value;
}

const LEAFLET_JS = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js";
const LEAFLET_CSS = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css";

function ensureLeafletCss() {
  if (document.querySelector(`link[href="${LEAFLET_CSS}"]`)) return;
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = LEAFLET_CSS;
  document.head.appendChild(link);
}

const MAP_STYLES = {
  osm: {
    label: "OSM",
    nameKey: "style_standard",
    // Switched from CARTO's basemaps.cartocdn.com (Voyager) to the official
    // OSM tile server: CARTO started watermarking unauthenticated tile
    // requests with "API KEY REQUIRED" (no HTTP error, just baked into the
    // returned PNG), reported by a user as the map suddenly showing that
    // text everywhere. No {r} placeholder here - the official OSM tile
    // server only serves standard-density tiles, no @2x retina variant.
    url: "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
    options: { maxZoom: 19, updateWhenIdle: true, keepBuffer: 2, attribution: '&copy; OpenStreetMap contributors' }
  },
  topo: {
    label: "Topo",
    nameKey: "style_topo",
    url: "https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png",
    options: { maxZoom: 17, updateWhenIdle: true, keepBuffer: 2 }
  },
  sat: {
    label: "Sat",
    nameKey: "style_sat",
    url: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    options: { maxZoom: 19, updateWhenIdle: true, keepBuffer: 2 }
  }
};

const LEAFLET_INLINE_CSS = `
.leaflet-pane, .leaflet-tile, .leaflet-marker-icon, .leaflet-marker-shadow,
.leaflet-tile-container, .leaflet-pane > svg, .leaflet-pane > canvas,
.leaflet-zoom-box, .leaflet-image-layer, .leaflet-layer {
  position: absolute; left: 0; top: 0;
}
.leaflet-container { overflow: hidden; font-family: inherit; font-size: 12px; }
.leaflet-tile, .leaflet-marker-icon, .leaflet-marker-shadow { user-select: none; -webkit-user-select: none; }
.leaflet-tile { filter: inherit; visibility: hidden; }
.leaflet-tile-loaded { visibility: inherit; }
.leaflet-tile-container { pointer-events: none; }
.leaflet-zoom-animated { transform-origin: 0 0; }
.leaflet-tile { image-rendering: auto; width: 256px; height: 256px; }
.leaflet-container { background: #ddd; outline-offset: 1px; }
.leaflet-container a { color: #0078A8; }
.leaflet-zoom-box { border: 2px dotted #38f; background: rgba(255,255,255,0.5); }
.leaflet-pane { z-index: 400; }
.leaflet-tile-pane { z-index: 200; }
.leaflet-overlay-pane { z-index: 400; }
.leaflet-shadow-pane { z-index: 500; }
.leaflet-marker-pane { z-index: 600; }
.leaflet-tooltip-pane { z-index: 650; }
.leaflet-popup-pane { z-index: 700; }
.leaflet-map-pane canvas { z-index: 100; }
.leaflet-map-pane svg { z-index: 200; }
.leaflet-control { position: relative; z-index: 800; pointer-events: visiblePainted; pointer-events: auto; }
.leaflet-top, .leaflet-bottom { position: absolute; z-index: 1000; pointer-events: none; }
.leaflet-top { top: 0; }
.leaflet-right { right: 0; }
.leaflet-bottom { bottom: 0; }
.leaflet-left { left: 0; }
.leaflet-top .leaflet-control, .leaflet-bottom .leaflet-control { margin-top: 10px; }
.leaflet-top .leaflet-control:first-child { margin-top: 0; }
.leaflet-bottom .leaflet-control { margin-bottom: 10px; }
.leaflet-left .leaflet-control { margin-left: 10px; }
.leaflet-right .leaflet-control { margin-right: 10px; }
.leaflet-fade-anim .leaflet-popup { opacity: 1; transition: opacity 0.2s linear; }
.leaflet-fade-anim .leaflet-map-pane .leaflet-popup { opacity: 1; }
.leaflet-zoom-anim .leaflet-zoom-animated { transition: transform 0.25s cubic-bezier(0,0,0.25,1); }
.leaflet-pan-anim .leaflet-tile, .leaflet-zoom-anim .leaflet-zoom-hide { visibility: hidden; }
.leaflet-zoom-anim .leaflet-zoom-animated { will-change: transform; }
.leaflet-control-zoom a { width: 30px; height: 30px; line-height: 30px; display: block; text-align: center; text-decoration: none; color: black; background: white; border-bottom: 1px solid #ccc; }
.leaflet-control-zoom a:hover { background: #f4f4f4; }
.leaflet-control-zoom-in { border-top-left-radius: 4px; border-top-right-radius: 4px; font-size: 18px; }
.leaflet-control-zoom-out { border-bottom-left-radius: 4px; border-bottom-right-radius: 4px; font-size: 20px; }
.leaflet-control-zoom { box-shadow: 0 1px 5px rgba(0,0,0,0.4); border-radius: 5px; }
.leaflet-touch .leaflet-control-zoom a { width: 36px; height: 36px; line-height: 36px; font-size: 20px; }
.leaflet-interactive { cursor: pointer; }
.leaflet-grab { cursor: grab; }
.leaflet-crosshair, .leaflet-crosshair .leaflet-interactive { cursor: crosshair; }
.leaflet-dragging .leaflet-grab, .leaflet-dragging .leaflet-grab .leaflet-interactive,
.leaflet-dragging .leaflet-marker-draggable { cursor: move; cursor: grabbing; }
.leaflet-image-layer, .leaflet-pane > svg path, .leaflet-tile-container { pointer-events: none; }
.leaflet-image-layer.leaflet-interactive, .leaflet-pane > svg path.leaflet-interactive, svg.leaflet-image-layer.leaflet-interactive path { pointer-events: visiblePainted; pointer-events: auto; }
.leaflet-container a.leaflet-active { outline: 2px solid orange; }
.leaflet-tooltip { position: absolute; padding: 4px 8px; background-color: #fff; border: 1px solid #fff; border-radius: 3px; color: #222; white-space: nowrap; pointer-events: none; box-shadow: 0 1px 3px rgba(0,0,0,0.4); }
`;

// ensureLeaflet() runs at module level with no `hass` in scope, so its
// rejections carry a stable, untranslated error CODE rather than natural-
// language text - callers (which always have `this._hass`) translate the
// code via describeBootError() below, right where they already build their
// user-facing error message.
const ERR_LEAFLET_UNAVAILABLE = "leaflet_unavailable";
const ERR_LEAFLET_LOAD_FAILED = "leaflet_load_failed";

// Translates the stable codes ensureLeaflet() rejects with into a
// user-facing message in the current hass locale; any other error's plain
// .message is used as-is (already human-readable, e.g. from a WS call).
function describeBootError(hass, err) {
  if (err?.message === ERR_LEAFLET_UNAVAILABLE) return ebT(hass, "err_leaflet_unavailable");
  if (err?.message === ERR_LEAFLET_LOAD_FAILED) return ebT(hass, "err_leaflet_load");
  return err?.message || String(err);
}

function ensureLeaflet() {
  ensureLeafletCss();
  if (window.L && typeof window.L.map === "function") return Promise.resolve(window.L);
  if (window.__ebikeLeafletPromise) return window.__ebikeLeafletPromise;

  window.__ebikeLeafletPromise = new Promise((resolve, reject) => {
    const existing = document.querySelector(`script[src="${LEAFLET_JS}"]`);
    if (existing) {
      const finish = () => {
        if (window.L && typeof window.L.map === "function") resolve(window.L);
        else {
          // Tag auch hier entfernen: load/error feuern nie wieder,
          // ein Retry an diesem Tag würde sonst ewig hängen.
          existing.remove();
          reject(new Error(ERR_LEAFLET_UNAVAILABLE));
        }
      };
      existing.addEventListener("load", finish, { once: true });
      existing.addEventListener("error", () => {
        // Totes Script-Tag entfernen, damit der nächste Versuch ein
        // frisches injiziert (sonst hinge er ewig an einem Tag, dessen
        // load/error-Events längst gefeuert haben).
        existing.remove();
        reject(new Error(ERR_LEAFLET_LOAD_FAILED));
      }, { once: true });
      if (window.L && typeof window.L.map === "function") finish();
      return;
    }

    const script = document.createElement("script");
    script.src = LEAFLET_JS;
    script.async = true;
    script.onload = () => {
      if (window.L && typeof window.L.map === "function") resolve(window.L);
      else {
        script.remove();
        reject(new Error(ERR_LEAFLET_UNAVAILABLE));
      }
    };
    script.onerror = () => {
      script.remove();
      reject(new Error(ERR_LEAFLET_LOAD_FAILED));
    };
    document.head.appendChild(script);
  }).catch((err) => {
    // Fehlgeschlagenen Ladeversuch NICHT cachen — sonst liefe jeder
    // Retry (z. B. nach kurzem CDN-Ausfall) für immer in dieselbe
    // rejected Promise. Nächster Aufruf startet einen frischen Versuch.
    window.__ebikeLeafletPromise = null;
    throw err;
  });

  return window.__ebikeLeafletPromise;
}

// ===========================================================================
// MapLibre GL + OpenFreeMap helpers for the 3D Map card (lazy-loaded)
// ===========================================================================
// ===========================================================================
// Dashboard-Card: Wartungs-Vorschläge + Fahrzeug-Vergleichswerte
// ---------------------------------------------------------------------------
// Vorschläge fürs Wartungs-Dropdown. Reine Templates; der User kann den
// Text danach beliebig editieren oder einen ganz eigenen eingeben.
// Die Labels werden je nach Sprache aus den i18n-Dicts geholt; die
// englischen Defaults stehen hier inline, damit eine fehlende Locale-
// Datei nicht den Dropdown leert.
const MAINTENANCE_PRESETS = [
  { id: "chain_clean",   label_de: "Kette reinigen und ölen",      label_en: "Clean and oil chain" },
  { id: "chain_wax",     label_de: "Kette wachsen",                 label_en: "Wax chain" },
  { id: "chain_replace", label_de: "Kette wechseln",                label_en: "Replace chain" },
  { id: "brake_check",   label_de: "Bremsen prüfen und einstellen", label_en: "Check and adjust brakes" },
  { id: "brake_pads",    label_de: "Bremsbeläge wechseln",          label_en: "Replace brake pads" },
  { id: "tire_pressure", label_de: "Reifenluftdruck prüfen",         label_en: "Check tire pressure" },
  { id: "tire_replace",  label_de: "Reifen wechseln",                label_en: "Replace tires" },
  { id: "gear_check",    label_de: "Schaltung prüfen / einstellen",  label_en: "Check / adjust gears" },
  { id: "service_large", label_de: "Großer Kundendienst",            label_en: "Major service" },
  { id: "service_small", label_de: "Kleiner Kundendienst",           label_en: "Minor service" },
  { id: "battery_contacts", label_de: "Akku-Kontakte reinigen",      label_en: "Clean battery contacts" },
];

// Fahrzeug-Vergleichswerte für die CO2/Sprit-Berechnung. CO2 in g/km
// als Well-to-Wheel-Schätzung, Verbrauch in l/100km bzw. kWh/100km
// (Elektroauto). Quellen: Umweltbundesamt 2024, ADAC-Mittelwerte.
// fuel_kind unterscheidet Default-Preis und Einheit der Anzeige.
const VEHICLE_PRESETS = {
  none: {
    label_de: "Kein Vergleich",
    label_en: "No comparison",
    co2_g_per_km: 0, consumption: 0, fuel_kind: "none",
  },
  small_petrol: {
    label_de: "Kleinwagen Benzin",
    label_en: "Small car (petrol)",
    co2_g_per_km: 120, consumption: 5.5, fuel_kind: "petrol",
  },
  compact_petrol: {
    label_de: "Mittelklasse Benzin",
    label_en: "Mid-size (petrol)",
    co2_g_per_km: 145, consumption: 7.0, fuel_kind: "petrol",
  },
  suv_petrol: {
    label_de: "SUV / Van Benzin",
    label_en: "SUV / van (petrol)",
    co2_g_per_km: 180, consumption: 9.0, fuel_kind: "petrol",
  },
  small_diesel: {
    label_de: "Kleinwagen Diesel",
    label_en: "Small car (diesel)",
    co2_g_per_km: 105, consumption: 4.5, fuel_kind: "diesel",
  },
  compact_diesel: {
    label_de: "Mittelklasse Diesel",
    label_en: "Mid-size (diesel)",
    co2_g_per_km: 135, consumption: 6.0, fuel_kind: "diesel",
  },
  suv_diesel: {
    label_de: "SUV / Van Diesel",
    label_en: "SUV / van (diesel)",
    co2_g_per_km: 165, consumption: 8.0, fuel_kind: "diesel",
  },
  ev_compact: {
    label_de: "Elektroauto (Ökostrom)",
    label_en: "Electric car (green energy)",
    co2_g_per_km: 50, consumption: 18.0, fuel_kind: "ev",
  },
};

// Default-Preise pro Treibstoff in EUR. Wird vom user-konfigurierten
// fuel_price überschrieben, falls gesetzt.
const FUEL_DEFAULT_PRICE = {
  petrol: 1.85,
  diesel: 1.75,
  ev: 0.35,
  none: 0,
};

// ===========================================================================
// Geteilte Card-Settings (Single Source of Truth in HA-Storage)
// ---------------------------------------------------------------------------
// Beide Cards (2D-Map-Card und 3D-Map-Card) lesen die Playback-/Darstellungs-
// Einstellungen aus EINEM HA-Storage-Slot. Schreiben über die Editor-UI gehen
// per WebSocket zurück in den Store. Cache + EventTarget-Bus auf Modul-Ebene,
// damit beide Card-Instanzen auf derselben Page sich Änderungen mitteilen,
// ohne dass jeder ein eigenes WS-Polling braucht.
//
// Lese-Cascade pro Key:
//   1. Shared Storage  (vom User per Editor gesetzt, gewinnt immer)
//   2. Card-YAML       (Per-Instanz-Override, falls jemand YAML schreibt)
//   3. Hardcoded-Default (vom Aufrufer übergeben)
// ===========================================================================
const SHARED_SETTING_KEYS = [
  "playback_speed", "animate_seconds",
  "default_pitch", "chase_zoom", "chase_lookahead",
  "smooth_window", "track_smooth_window",
  "terrain_exaggeration", "satellite_tile_url", "satellite_max_zoom",
  "north_up",
  // FPV/action-cam chase mode (issue #43)
  "camera_mode", "fpv_height_m", "fpv_distance_m", "fpv_lookahead_m",
  "camera_presets", "active_camera_preset_id",
  "show_date", "show_time", "show_sun",
  "show_speed", "show_distance", "show_elevation",
  "stats_as_chips", "show_weather",
  // Wartungs-Warnschwellen (Dashboard-Card)
  "maint_warn_km", "maint_warn_days",
];

// Defaults, wenn weder Shared-Store noch Card-YAML einen Wert haben.
const MAINT_WARN_KM_DEFAULT = 500;
const MAINT_WARN_DAYS_DEFAULT = 30;

const _cardSettingsCache = { data: null };   // null = noch nicht geladen
const _cardSettingsBus = new EventTarget();

async function ensureCardSettingsLoaded(hass) {
  if (_cardSettingsCache.data != null) return _cardSettingsCache.data;
  if (!hass) return {};
  try {
    const res = await hass.callWS({ type: "bosch_ebike/get_card_settings" });
    _cardSettingsCache.data = (res && res.settings) || {};
  } catch (err) {
    console.warn("[Bosch eBike] get_card_settings failed:", err?.message || err);
    _cardSettingsCache.data = {};
  }
  return _cardSettingsCache.data;
}

async function saveCardSetting(hass, key, value) {
  if (!hass || !SHARED_SETTING_KEYS.includes(key)) return;
  try {
    const res = await hass.callWS({
      type: "bosch_ebike/set_card_settings",
      changes: { [key]: value },
    });
    _cardSettingsCache.data = (res && res.settings) || _cardSettingsCache.data || {};
    _cardSettingsBus.dispatchEvent(new Event("changed"));
  } catch (err) {
    console.warn("[Bosch eBike] set_card_settings failed:", err?.message || err);
  }
}

// Same as saveCardSetting but writes several keys in one WS round trip and
// one "changed" event - used when applying a whole camera preset at once
// (issue #43), so the fields do not visibly update one at a time.
async function saveCardSettings(hass, changes) {
  if (!hass) return;
  const filtered = {};
  for (const [key, value] of Object.entries(changes || {})) {
    if (SHARED_SETTING_KEYS.includes(key)) filtered[key] = value;
  }
  if (!Object.keys(filtered).length) return;
  try {
    const res = await hass.callWS({
      type: "bosch_ebike/set_card_settings",
      changes: filtered,
    });
    _cardSettingsCache.data = (res && res.settings) || _cardSettingsCache.data || {};
    _cardSettingsBus.dispatchEvent(new Event("changed"));
  } catch (err) {
    console.warn("[Bosch eBike] set_card_settings failed:", err?.message || err);
  }
}

// Destination point (issue #43 FPV camera): given a start lat/lon, a
// bearing in degrees and a distance in metres, returns the resulting
// lat/lon. Standard great-circle "destination point given distance and
// bearing" formula (spherical Earth, radius 6371 km - the small error vs.
// an ellipsoid is irrelevant at the few-metre distances used for the
// camera). Verified numerically: distance 0 returns the input point,
// bearing 0/90 only move lat/lon respectively, and a there-and-back trip
// returns to the start within floating point precision.
function destinationPoint(lat, lon, bearingDeg, distanceM) {
  const R = 6371000;
  const brng = bearingDeg * Math.PI / 180;
  const lat1 = lat * Math.PI / 180;
  const lon1 = lon * Math.PI / 180;
  const dR = distanceM / R;
  const lat2 = Math.asin(
    Math.sin(lat1) * Math.cos(dR) + Math.cos(lat1) * Math.sin(dR) * Math.cos(brng)
  );
  const lon2 = lon1 + Math.atan2(
    Math.sin(brng) * Math.sin(dR) * Math.cos(lat1),
    Math.cos(dR) - Math.sin(lat1) * Math.sin(lat2)
  );
  return { lat: lat2 * 180 / Math.PI, lon: ((lon2 * 180 / Math.PI) + 540) % 360 - 180 };
}

// The camera fields a preset captures/restores (issue #43). Kept as one
// list so "capture current values" and "apply a preset" always agree on
// exactly which shared settings are preset-controlled.
const CAMERA_PRESET_FIELDS = [
  "camera_mode", "default_pitch", "chase_zoom", "chase_lookahead",
  "fpv_height_m", "fpv_distance_m", "fpv_lookahead_m",
];

// Factory camera presets (issue #43): sensible starting combinations users
// can apply as-is or duplicate under their own name. "factory" presets are
// never deleted (delete just resets them to these values); ids are stable
// so re-selecting one after an edit always finds the same entry.
const FACTORY_CAMERA_PRESETS = [
  {
    id: "factory_classic", factory: true, name_key: "map3d_preset_classic",
    values: { camera_mode: "chase", default_pitch: 55, chase_zoom: 17, chase_lookahead: 30 },
  },
  {
    id: "factory_cinematic", factory: true, name_key: "map3d_preset_cinematic",
    values: { camera_mode: "chase", default_pitch: 30, chase_zoom: 15, chase_lookahead: 10 },
  },
  {
    id: "factory_action", factory: true, name_key: "map3d_preset_action",
    values: { camera_mode: "fpv", fpv_height_m: 2.5, fpv_distance_m: 4, fpv_lookahead_m: 20 },
  },
  {
    id: "factory_drone_fpv", factory: true, name_key: "map3d_preset_drone_fpv",
    values: { camera_mode: "fpv", fpv_height_m: 1.2, fpv_distance_m: 1.5, fpv_lookahead_m: 12 },
  },
];

// Lookup mit Cascade: shared store > local card config > fallback.
// Wenn der shared store noch nicht geladen ist (data === null), liefert
// der Helfer den Card-Config-Wert bzw. fallback - die Card wird einmal
// neu gerendert, sobald ensureCardSettingsLoaded resolved und der Bus
// fires.
function readCardSetting(localConfig, key, fallback) {
  const shared = _cardSettingsCache.data || {};
  if (shared[key] != null && shared[key] !== "") return shared[key];
  if (localConfig && localConfig[key] != null && localConfig[key] !== "") {
    return localConfig[key];
  }
  return fallback;
}

const MAPLIBRE_JS = "https://unpkg.com/maplibre-gl@5.6.0/dist/maplibre-gl.js";
const MAPLIBRE_CSS = "https://unpkg.com/maplibre-gl@5.6.0/dist/maplibre-gl.css";
const OPENFREEMAP_LIBERTY = "https://tiles.openfreemap.org/styles/liberty";

// AWS Open Data terrain tiles, terrarium-encoded PNG DEM. Free, no key,
// global coverage. Used both for the MapLibre raster-dem source and as
// the URL pattern for the bbox preloader below.
const TERRARIUM_TILE_TEMPLATE =
  "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png";

// Custom protocol schemes that intercept MapLibre tile requests so we
// can serve them from IndexedDB. Tiles get into IDB either via the
// up-front preloader (recommended) or lazily on first map use.
// Same handler logic for DEM and satellite; only the scheme differs
// so MapLibre can distinguish the sources.
const EBIKE_DEM_PROTOCOL = "ebike-dem";
const EBIKE_SAT_PROTOCOL = "ebike-sat";

// Default satellite imagery: Esri World Imagery. Free, no API key,
// global coverage. Slow CDN from EU but our preloader hides that.
// User can override via the satellite_tile_url config option for
// MapTiler / Mapbox keys if they want faster CDNs.
// Note: Esri uses {z}/{y}/{x} order, opposite of OSM-style {z}/{x}/{y}.
// Template placeholders are filled in by _preloadRasterTiles below.
const DEFAULT_SATELLITE_TEMPLATE =
  "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}";

// IndexedDB for tile caching across sessions.
const TILE_DB_NAME = "bosch-ebike-tiles";
const TILE_STORE = "tiles";

let _tileDBPromise = null;
function _tileDBOpen() {
  if (_tileDBPromise) return _tileDBPromise;
  _tileDBPromise = new Promise((resolve, reject) => {
    try {
      const req = indexedDB.open(TILE_DB_NAME, 1);
      req.onupgradeneeded = () => {
        try { req.result.createObjectStore(TILE_STORE); } catch (_) {}
      };
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error);
    } catch (e) {
      reject(e);
    }
  }).catch((e) => {
    // Browser blocked IDB (private mode etc). Fall back to no-op cache.
    console.warn("[Bosch eBike 3D] tile cache disabled:", e?.message || e);
    return null;
  });
  return _tileDBPromise;
}

async function _tileCacheGet(url) {
  try {
    const db = await _tileDBOpen();
    if (!db) return null;
    return await new Promise((resolve) => {
      const tx = db.transaction(TILE_STORE, "readonly");
      const r = tx.objectStore(TILE_STORE).get(url);
      r.onsuccess = () => resolve(r.result || null);
      r.onerror = () => resolve(null);
    });
  } catch (_) { return null; }
}

async function _tileCachePut(url, blob) {
  try {
    const db = await _tileDBOpen();
    if (!db) return;
    await new Promise((resolve) => {
      const tx = db.transaction(TILE_STORE, "readwrite");
      tx.objectStore(TILE_STORE).put(blob, url);
      tx.oncomplete = () => resolve();
      tx.onerror = () => resolve();
    });
  } catch (_) { /* best effort */ }
}

// Slippy-tile math. Converts (lon, lat) to the tile (x, y) containing
// that coordinate at the given zoom. Standard Web-Mercator formula.
function _lonLatToTile(lon, lat, z) {
  const n = Math.pow(2, z);
  const x = Math.floor((lon + 180) / 360 * n);
  const latRad = lat * Math.PI / 180;
  const y = Math.floor(
    (1 - Math.log(Math.tan(latRad) + 1 / Math.cos(latRad)) / Math.PI) / 2 * n,
  );
  const cap = n - 1;
  return { x: Math.max(0, Math.min(cap, x)), y: Math.max(0, Math.min(cap, y)) };
}

// All tiles needed to cover [west,south,east,north] at the given zoom.
function _tilesForBBox(west, south, east, north, zoom) {
  const tl = _lonLatToTile(west, north, zoom);
  const br = _lonLatToTile(east, south, zoom);
  const out = [];
  for (let x = tl.x; x <= br.x; x++) {
    for (let y = tl.y; y <= br.y; y++) {
      out.push({ z: zoom, x, y });
    }
  }
  return out;
}

// Registers the ebike-dem:// and ebike-sat:// MapLibre protocols
// exactly once per page load. Both share the same handler - it checks
// IDB first and only falls back to network on miss, writing through
// to IDB so the next session is served entirely offline.
const _ebikeProtocolsRegistered = new Set();
function registerEbikeProtocols(mlib) {
  if (!mlib || typeof mlib.addProtocol !== "function") return;
  for (const scheme of [EBIKE_DEM_PROTOCOL, EBIKE_SAT_PROTOCOL]) {
    if (_ebikeProtocolsRegistered.has(scheme)) continue;
    mlib.addProtocol(scheme, async (params, abortController) => {
      const url = "https://" + params.url.slice((scheme + "://").length);
      let blob = await _tileCacheGet(url);
      if (!blob) {
        const resp = await fetch(url, {
          mode: "cors",
          signal: abortController?.signal,
        });
        if (!resp.ok) throw new Error(scheme + " tile " + resp.status);
        blob = await resp.blob();
        _tileCachePut(url, blob);   // fire-and-forget
      }
      const buf = await blob.arrayBuffer();
      return { data: buf };
    });
    _ebikeProtocolsRegistered.add(scheme);
  }
}

function ensureMapLibre() {
  if (window.maplibregl) return Promise.resolve(window.maplibregl);
  if (window.__ebikeMapLibrePromise) return window.__ebikeMapLibrePromise;
  window.__ebikeMapLibrePromise = new Promise((resolve, reject) => {
    if (!document.querySelector(`link[href="${MAPLIBRE_CSS}"]`)) {
      const l = document.createElement("link");
      l.rel = "stylesheet";
      l.href = MAPLIBRE_CSS;
      document.head.appendChild(l);
    }
    if (window.maplibregl) return resolve(window.maplibregl);
    const s = document.createElement("script");
    s.src = MAPLIBRE_JS;
    s.onload = () => resolve(window.maplibregl);
    s.onerror = () => reject(new Error("MapLibre GL could not be loaded"));
    document.head.appendChild(s);
  });
  return window.__ebikeMapLibrePromise;
}

// Lightweight NOAA-based sun position. Returns { altitude, azimuth } in radians.
function sunPositionAt(date, lat, lon) {
  const rad = Math.PI / 180;
  const dayMs = 86400000;
  const J1970 = 2440588;
  const J2000 = 2451545;
  const toJulian = (d) => d.valueOf() / dayMs - 0.5 + J1970;
  const toDays = (d) => toJulian(d) - J2000;
  const e = rad * 23.4397;
  const solarMeanAnomaly = (d) => rad * (357.5291 + 0.98560028 * d);
  const eclipticLongitude = (M) => {
    const C = rad * (1.9148 * Math.sin(M) + 0.02 * Math.sin(2 * M) + 0.0003 * Math.sin(3 * M));
    const P = rad * 102.9372;
    return M + C + P + Math.PI;
  };
  const declination = (l) => Math.asin(Math.sin(e) * Math.sin(l));
  const rightAscension = (l) => Math.atan2(Math.sin(l) * Math.cos(e), Math.cos(l));
  const siderealTime = (d, lw) => rad * (280.16 + 360.9856235 * d) - lw;
  const d = toDays(date);
  const M = solarMeanAnomaly(d);
  const L = eclipticLongitude(M);
  const ra = rightAscension(L);
  const dec = declination(L);
  const lw = rad * -lon;
  const phi = rad * lat;
  const H = siderealTime(d, lw) - ra;
  const altitude = Math.asin(Math.sin(phi) * Math.sin(dec) + Math.cos(phi) * Math.cos(dec) * Math.cos(H));
  const azimuth = Math.atan2(Math.sin(H), Math.cos(H) * Math.sin(phi) - Math.tan(dec) * Math.cos(phi));
  return { altitude, azimuth };
}

// Andrew's monotone-chain convex hull. Input: [[x,y], ...]. Output: hull
// vertices in CCW order (NOT closed; caller pushes hull[0] to close).
function convexHull2D(points) {
  if (points.length < 3) return points.slice();
  const sorted = points.slice().sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  const cross = (O, A, B) =>
    (A[0] - O[0]) * (B[1] - O[1]) - (A[1] - O[1]) * (B[0] - O[0]);
  const lower = [];
  for (const p of sorted) {
    while (lower.length >= 2 && cross(lower[lower.length - 2], lower[lower.length - 1], p) <= 0) {
      lower.pop();
    }
    lower.push(p);
  }
  const upper = [];
  for (let i = sorted.length - 1; i >= 0; i--) {
    const p = sorted[i];
    while (upper.length >= 2 && cross(upper[upper.length - 2], upper[upper.length - 1], p) <= 0) {
      upper.pop();
    }
    upper.push(p);
  }
  return lower.concat(upper.slice(1, -1));
}

// Project a building footprint's cast shadow on the ground.
// sunAlt, sunAz: radians (sunAz convention from sunPositionAt: 0 = south,
// +π/2 = west, ±π = north). Returns a closed GeoJSON Polygon ring (last
// vertex equals first) or null if the sun is below the horizon.
function buildingShadowRing(ring, heightM, sunAlt, sunAz, refLat) {
  if (sunAlt <= 0) return null;
  if (!ring || ring.length < 3) return null;
  if (!Number.isFinite(heightM) || heightM <= 0) return null;
  // Shadow compass bearing (from north clockwise) = sun.azimuth + 2π mod 2π
  // (because sun compass = my_az + π, shadow compass = sun_compass + π).
  const shadowCompass = (sunAz + 2 * Math.PI) % (2 * Math.PI);
  const shadowLenM = Math.min(400, heightM / Math.tan(sunAlt));
  // Convert meters to lat/lon offsets
  const dLatPerM = 1 / 111320;
  const cosLat = Math.cos(refLat * Math.PI / 180);
  const dLonPerM = 1 / (111320 * Math.max(0.05, cosLat));
  const dLat = shadowLenM * Math.cos(shadowCompass) * dLatPerM;
  const dLon = shadowLenM * Math.sin(shadowCompass) * dLonPerM;
  // Original ring + projected ring, then convex hull
  const all = [];
  for (const v of ring) {
    if (!Array.isArray(v) || v.length < 2) continue;
    all.push([v[0], v[1]]);
    all.push([v[0] + dLon, v[1] + dLat]);
  }
  if (all.length < 3) return null;
  const hull = convexHull2D(all);
  if (hull.length < 3) return null;
  hull.push(hull[0]); // close the ring
  return hull;
}

// Map a sun altitude (degrees) to a tint that conveys time of day.
function sunMoodFor(altDeg) {
  if (altDeg < -6)  return { fog: "#0c1228", sky: "#0a1530", sun: "#2a3a5a", label: "night" };
  if (altDeg < 0)   return { fog: "#3a2638", sky: "#cf6a3e", sun: "#ff7e3e", label: "twilight" };
  if (altDeg < 10)  return { fog: "#c89c6a", sky: "#ffb777", sun: "#ffa566", label: "golden" };
  if (altDeg < 30)  return { fog: "#d9c8a3", sky: "#bfdcff", sun: "#ffd884", label: "morning" };
  return                { fog: "#cfe2f2", sky: "#a8d2ff", sun: "#ffffff", label: "day" };
}

// "Weather overlay": purely atmospheric cloud/rain/snow/storm effect strengths for a
// past ride, independently written (not ported - Helios, the inspiration, is GPL-3.0
// and this project is MIT; only the general idea - CSS/canvas layers driven by public
// weather data - is reused, not any of its code). WMO weather codes and precipitation
// intensity classes are public meteorological standards, not copyrightable.
const clamp01 = (v) => Math.max(0, Math.min(1, v));

const isSnowCode = (c) => (c >= 71 && c <= 77) || c === 85 || c === 86;
const isStormCode = (c) => c === 95 || c === 96 || c === 99;

// Below these floors, treat a rounding/dew trace as no precipitation to draw.
const RAIN_MIN_MM = 0.1;
const SNOW_MIN_CM = 0.1;

// mm/h (or cm/h) -> particle density [0,1], piecewise-linear through the
// meteorological intensity classes so light/moderate/heavy/violent each read as a
// visibly distinct density instead of saturating early or over-drawing a trace.
function intensityDensity(x, curve) {
  if (x <= curve[0][0]) return curve[0][1];
  for (let i = 1; i < curve.length; i++) {
    const [x1, y1] = curve[i];
    if (x <= x1) {
      const [x0, y0] = curve[i - 1];
      return y0 + (y1 - y0) * (x - x0) / (x1 - x0);
    }
  }
  return curve[curve.length - 1][1];
}
const RAIN_CURVE = [[0.1, 0.05], [2.5, 0.30], [10, 0.60], [50, 1.0]];
const SNOW_CURVE = [[0.1, 0.08], [1, 0.35], [4, 0.70], [10, 1.0]];

// Hard cap on live rain/snow particles per canvas (inline map + fullscreen map
// each have their own canvas/state, so this is a per-overlay ceiling, not global).
const MAX_PARTICLES = 120;

// Map resolved weather (cloud %, precip mm/h, snowfall cm/h, WMO code, sun altitude in
// degrees) to independent overlay strengths. Return fields, all [0,1] unless noted:
//   sun   - warm sun-glow strength (fades under cloud and near/below the horizon)
//   grey  - grey veil opacity, builds in from ~25% cloud cover
//   cloud - drifting cloud-shape opacity, builds in from ~30% cloud cover
//   rain/snow - particle density for the respective canvas layer
//   storm - lightning-flash strength (0, 0.7 or 1)
//   label - condition string for an optional small icon/badge, not required for the effect
function weatherLayers(cloud, precip, snowfall, wmoCode, sunAltitudeDeg) {
  const cloud01 = clamp01((cloud || 0) / 100);
  const snowing = (snowfall || 0) >= SNOW_MIN_CM || isSnowCode(wmoCode);
  const storm = isStormCode(wmoCode) ? (wmoCode === 95 ? 0.7 : 1) : 0;
  const rain = (snowing || (precip || 0) < RAIN_MIN_MM) ? 0 : intensityDensity(precip, RAIN_CURVE);
  const snow = (snowing && (snowfall || 0) >= SNOW_MIN_CM) ? intensityDensity(snowfall, SNOW_CURVE) : 0;
  const dayFactor = clamp01((sunAltitudeDeg || 0) / 18);
  return {
    sun: dayFactor * clamp01(1 - cloud01 / 0.85),
    grey: clamp01((cloud01 - 0.25) / 0.60),
    cloud: clamp01((cloud01 - 0.30) / 0.55),
    rain, snow, storm,
    label:
      storm > 0 ? "storm" :
      snow > 0.5 ? "snow" : snow > 0 ? "light_snow" :
      rain > 0.5 ? "rain" : rain > 0 ? "light_rain" :
      cloud01 > 0.75 ? "overcast" : cloud01 > 0.40 ? "cloudy" :
      cloud01 > 0.15 ? "partly_cloudy" : "clear",
  };
}

// Linear interpolation between the two hourly samples bracketing targetDate.
// hourly = { time: string[] (ISO hours), cloud: number[], precip: number[], snow: number[], code: number[] }
// hourly.timesMs (number[], optional) - epoch-ms parse of hourly.time, precomputed
// once by a caller that will call this repeatedly against the same series (the 3D
// card's per-scrub-tick usage - see _loadTourWeather). Falls back to parsing
// hourly.time on the fly when absent, so the 2D card's one-shot call (which has no
// reason to precompute anything) keeps working unchanged.
function interpolateWeatherAt(hourly, targetDate) {
  if (!hourly || !Array.isArray(hourly.time) || !hourly.time.length) return null;
  const t = targetDate.getTime();
  const times = hourly.timesMs || hourly.time.map((s) => new Date(s).getTime());
  if (t <= times[0]) return { cloud: hourly.cloud[0], precip: hourly.precip[0], snow: hourly.snow[0], code: hourly.code[0] };
  const last = times.length - 1;
  if (t >= times[last]) return { cloud: hourly.cloud[last], precip: hourly.precip[last], snow: hourly.snow[last], code: hourly.code[last] };
  for (let i = 1; i <= last; i++) {
    if (t <= times[i]) {
      const f = (t - times[i - 1]) / (times[i] - times[i - 1]);
      const lerp = (a) => a[i - 1] + (a[i] - a[i - 1]) * f;
      return { cloud: lerp(hourly.cloud), precip: lerp(hourly.precip), snow: lerp(hourly.snow), code: hourly.code[i - 1] };
    }
  }
  return null; // unreachable
}

// Fetches hourly weather for [startISO, endISO] at (lat, lon). Archive API has ~5 day
// lag (ERA5 reanalysis), so recent rides fall back to the Forecast API (which also
// serves recent past hours via past_days) - both share the same hourly param names.
// Throws on a failed/empty response (unlike the Wikipedia/POI fetchers elsewhere in
// this file, which swallow errors and return [] /null) - callers must catch this.
async function fetchHistoricalWeather(lat, lon, startISO, endISO) {
  const startDate = startISO.substring(0, 10);
  const endDate = endISO.substring(0, 10);
  const params = "cloud_cover_low,cloud_cover_mid,cloud_cover_high,precipitation,snowfall,weather_code";
  const fiveDaysAgo = new Date(Date.now() - 5 * 86400000).toISOString().substring(0, 10);
  const useForecast = endDate >= fiveDaysAgo;
  const url = useForecast
    ? `https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lon}&hourly=${params}&past_days=7&forecast_days=1&timezone=UTC`
    : `https://archive-api.open-meteo.com/v1/archive?latitude=${lat}&longitude=${lon}&start_date=${startDate}&end_date=${endDate}&hourly=${params}&timezone=UTC`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`weather fetch failed: ${res.status}`);
  const data = await res.json();
  const h = data.hourly;
  if (!h || !Array.isArray(h.time)) throw new Error("weather fetch: no hourly data");
  const cover = h.time.map((_, i) => {
    const low = h.cloud_cover_low?.[i] ?? 0, mid = h.cloud_cover_mid?.[i] ?? 0, high = h.cloud_cover_high?.[i] ?? 0;
    return Math.min(100, low + 0.6 * mid + 0.2 * high); // same collapse formula Helios documents using
  });
  return {
    time: h.time,
    cloud: cover,
    precip: h.precipitation || h.time.map(() => 0),
    snow: h.snowfall || h.time.map(() => 0),
    code: h.weather_code || h.time.map(() => 0),
  };
}

// Trick Check trick types (see trick_check.py). Names are deliberately left
// untranslated across all languages - the Bosch Flow app itself shows them
// as "Jump" even in its German UI (confirmed via a real screenshot, issue
// #65 follow-up), so a translation would likely just be wrong/unfamiliar.
const TRICK_TYPE_DEFS = [
  { key: "jumps", nameKey: "trick_jump", hasHeight: true },
  { key: "manuals", nameKey: "trick_manual", hasHeight: false },
  { key: "stoppies", nameKey: "trick_stoppie", hasHeight: false },
  { key: "wheelies", nameKey: "trick_wheelie", hasHeight: false },
];

// -- Weather overlay particle/flash renderer --
// Module-level (not class methods) since none of this needs `this`: state is
// stashed directly on the canvas/flash DOM nodes so the inline overlay
// (#eb-wx-overlay) and the fullscreen overlay (#eb-full-wx-overlay) each own
// an independent rAF loop / timer chain and can never cancel one another.

// CSS for the .eb-wx-overlay/.eb-wx-veil/.eb-wx-canvas/.eb-wx-flash DOM used
// by _applyWeatherLayers() (Task 3). Shared as a module-level string - NOT
// because CSS "isn't scoped" (it very much is: each card here builds its own
// <style> tag inside its own light DOM, and neither card ever calls
// attachShadow() itself, so whichever shadow root a card instance happens to
// land in - its own hui-card wrapper in normal dashboard use, or none at all
// in the document.body chase-cam portal (see _openChaseCam()) - is the only
// scope that <style> ever reaches. A style tag built by BoschEBikeMapCard's
// own _buildDOM() never reaches a separately-mounted BoschEBike3DMapCard;
// verified empirically, mirrors why _ensureChaseCamStyles() already had to
// inject its own flex-chain CSS rather than assume reuse). Every class that
// renders one of these overlays must interpolate this into its OWN <style>
// text so the rules land in that instance's own scope; this constant just
// keeps the rule text itself single-sourced instead of copy-pasted twice.
const WX_OVERLAY_CSS = `/* Opt-in weather overlay (Task 3), full-area on top of the map tiles.
         z-index:1050 sits below .eb-map-tools/.eb-batt-badge's 1100 so the
         toolbar and battery badge stay visually on top; pointer-events:none
         so the map stays interactive underneath. */
      .eb-wx-overlay { position:absolute; inset:0; z-index:1050; pointer-events:none; overflow:hidden; }
      .eb-wx-veil { position:absolute; inset:0; background:#3a4552; opacity:0; transition:opacity 1.5s; }
      .eb-wx-canvas { position:absolute; inset:0; width:100%; height:100%; }
      .eb-wx-flash { position:absolute; inset:0; background:#fff; opacity:0; }`;

function _wxDominantKind(rain, snow) {
  if (rain === 0 && snow === 0) return null;
  return snow > rain ? "snow" : "rain";
}

function _wxSpawnParticle(kind, w, h) {
  if (kind === "rain") {
    return {
      x: Math.random() * w,
      y: Math.random() * h,
      len: 10 + Math.random() * 12,
      speed: 400 + Math.random() * 300,  // px/s, downward
      drift: -40 + Math.random() * 20,   // px/s, slight sideways lean
    };
  }
  // snow
  return {
    x: Math.random() * w,
    y: Math.random() * h,
    r: 1 + Math.random() * 2.2,
    speed: 25 + Math.random() * 35,
    drift: -15 + Math.random() * 30,
    phase: Math.random() * Math.PI * 2, // gentle horizontal sway
  };
}

function _wxStopCanvas(canvas) {
  if (!canvas) return;
  const st = canvas._wxState;
  if (st && st.raf) cancelAnimationFrame(st.raf);
  canvas._wxState = null;
}

function _wxTick(canvas, ts) {
  const st = canvas._wxState;
  if (!st) return; // stopped/torn down since this frame was scheduled

  // Visibility gate: an ancestor (e.g. a closed .eb-fullscreen modal) with
  // display:none yields offsetParent === null for this element too, so this
  // single check covers both "overlay itself hidden" and "hidden ancestor".
  const overlayEl = st.overlayEl;
  if (!overlayEl || overlayEl.offsetParent === null) {
    st.raf = null;
    return; // do not reschedule - stop burning cycles while not visible
  }

  let dt = st.lastTs ? (ts - st.lastTs) / 1000 : 0;
  if (dt > 0.05) dt = 0.05; // clamp so a throttled/backgrounded tab can't blow up physics on resume
  st.lastTs = ts;

  // Reconcile the backing store from live layout size every tick, so a
  // dashboard resize or the fullscreen modal opening/closing can't leave the
  // canvas stale-sized or 0x0. A 0-sized canvas just skips drawing this tick.
  const w = canvas.clientWidth, h = canvas.clientHeight;
  if (w > 0 && h > 0) {
    if (canvas.width !== w || canvas.height !== h) {
      canvas.width = w;
      canvas.height = h;
    }
    const ctx = canvas.getContext("2d");
    ctx.clearRect(0, 0, w, h);

    // Only spawn new particles as density grows; shrink is a cheap length
    // truncation. Never reallocate the whole array every frame.
    const targetCount = Math.round(MAX_PARTICLES * st.density);
    while (st.particles.length < targetCount) st.particles.push(_wxSpawnParticle(st.kind, w, h));
    if (st.particles.length > targetCount) st.particles.length = targetCount;

    // All particles share `st.kind` at any given moment (enforced by the
    // kind-flip reset below), so style is set once per frame, not per-particle,
    // and every particle is batched into a single path + one draw call.
    if (st.kind === "rain") {
      ctx.strokeStyle = "rgba(190,210,235,0.55)";
      ctx.lineWidth = 1.4;
      ctx.beginPath();
      for (const p of st.particles) {
        p.y += p.speed * dt;
        p.x += p.drift * dt;
        if (p.y > h) { p.y = -p.len; p.x = Math.random() * w; }
        if (p.x < -10) p.x += w; else if (p.x > w + 10) p.x -= w;
        ctx.moveTo(p.x, p.y);
        ctx.lineTo(p.x + p.drift * 0.03, p.y + p.len);
      }
      ctx.stroke();
    } else if (st.kind === "snow") {
      ctx.fillStyle = "rgba(255,255,255,0.85)";
      ctx.beginPath();
      for (const p of st.particles) {
        p.phase += dt * 1.6;
        p.y += p.speed * dt;
        p.x += Math.sin(p.phase) * 10 * dt + p.drift * dt * 0.15;
        if (p.y > h) { p.y = -p.r * 2; p.x = Math.random() * w; }
        if (p.x < -5) p.x += w; else if (p.x > w + 5) p.x -= w;
        // explicit moveTo before each arc() so circles are separate
        // disconnected subpaths, not joined into one connected shape
        ctx.moveTo(p.x + p.r, p.y);
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
      }
      ctx.fill();
    }
  }

  if (st.rain === 0 && st.snow === 0) {
    st.raf = null;
    canvas._wxState = null; // idle/clear - stop the loop entirely, nothing left to animate
    return;
  }
  st.raf = requestAnimationFrame((ts2) => _wxTick(canvas, ts2));
}

// Starts/updates the per-canvas particle loop for one overlay from the
// current rain/snow densities. Safe to call every time layers are applied,
// whether or not a loop is already running.
function _wxStartOrUpdateCanvas(overlayEl, canvas, rain, snow) {
  const kind = _wxDominantKind(rain, snow);
  let st = canvas._wxState;
  if (!kind) {
    _wxStopCanvas(canvas);
    return;
  }
  const density = kind === "snow" ? snow : rain;
  if (!st) {
    st = canvas._wxState = { raf: null, particles: [], kind, lastTs: 0, density, rain, snow, overlayEl };
  } else {
    if (st.kind !== kind) {
      st.kind = kind;
      st.particles = []; // dominant kind flipped - drop stale-kind particles
    }
    st.density = density;
    st.rain = rain;
    st.snow = snow;
    st.overlayEl = overlayEl;
  }
  if (!st.raf) {
    if (overlayEl.offsetParent === null) return; // stay stopped while not visible
    st.raf = requestAnimationFrame((ts) => _wxTick(canvas, ts));
  }
}

function _wxStopFlash(flashEl) {
  if (!flashEl) return;
  const st = flashEl._wxFlashState;
  if (st && st.timer) clearTimeout(st.timer);
  flashEl._wxFlashState = null;
  flashEl.style.opacity = "0";
}

// Schedules the next brief lightning pulse. Deliberately simple: if `storm`
// changes mid-wait, the already-scheduled pulse still fires at the old
// storm-derived cadence rather than instantly retiming - the *next*
// scheduled pulse picks up the new cadence. Acceptable for a purely
// atmospheric effect, not worth the extra bookkeeping to fix.
function _wxScheduleFlash(flashEl) {
  const st = flashEl._wxFlashState;
  if (!st || !st.storm) return;

  // Self-healing visibility/attachment gate, mirroring _wxTick's check above:
  // an ancestor going display:none (e.g. a closed chase-cam/fullscreen modal)
  // yields offsetParent === null here too, and isConnected catches full
  // removal from the DOM (e.g. an innerHTML wipe). Either means this flash
  // node is orphaned - stop rescheduling and fully tear down via
  // _wxStopFlash() so a later _wxUpdateFlash() call (driven by the next
  // _applyWeatherLayers() pass, once the node is visible/attached again)
  // sees a fresh `!st` and re-arms the chain, instead of every current and
  // future teardown path needing to remember to call _wxStopFlash() itself.
  if (flashEl.offsetParent === null || !flashEl.isConnected) {
    _wxStopFlash(flashEl);
    return;
  }

  const gap = (2500 + Math.random() * 4500) / (0.4 + st.storm); // higher storm -> shorter avg gap
  st.timer = setTimeout(() => {
    const cur = flashEl._wxFlashState;
    if (!cur || !cur.storm) return;
    flashEl.style.transition = "opacity 80ms ease-out";
    flashEl.style.opacity = String(0.5 + Math.random() * 0.35 * cur.storm);
    setTimeout(() => {
      const still = flashEl._wxFlashState;
      if (!still) return; // torn down mid-pulse
      flashEl.style.transition = "opacity 250ms ease-in";
      flashEl.style.opacity = "0";
    }, 90 + Math.random() * 60);
    _wxScheduleFlash(flashEl);
  }, gap);
}

function _wxUpdateFlash(flashEl, storm) {
  const st = flashEl._wxFlashState;
  if (storm <= 0) {
    _wxStopFlash(flashEl);
    return;
  }
  if (!st) {
    flashEl._wxFlashState = { timer: null, storm };
    _wxScheduleFlash(flashEl);
  } else {
    st.storm = storm;
  }
}

// Applies one resolved weatherLayers() result to one overlay's DOM (e.g.
// BoschEBikeMapCard's inline #eb-wx-overlay / fullscreen #eb-full-wx-overlay,
// or BoschEBike3DMapCard's #m3d-wx-overlay). Pure rendering - takes layers as
// given, does not fetch or interpolate weather itself. Module-level (not a
// class method) like the rest of this block: the body never touches `this`,
// and both map-card classes call it against their own overlay element.
function _applyWeatherLayers(overlayEl, layers) {
  if (!overlayEl) return;
  const veil = overlayEl.querySelector(".eb-wx-veil");
  const canvas = overlayEl.querySelector(".eb-wx-canvas");
  const flash = overlayEl.querySelector(".eb-wx-flash");

  const grey = layers.grey || 0, rain = layers.rain || 0, snow = layers.snow || 0, storm = layers.storm || 0;
  // An entirely clear day shows nothing at all.
  overlayEl.style.display = (grey > 0 || rain > 0 || snow > 0 || storm > 0) ? "" : "none";

  if (veil) veil.style.opacity = String(grey * 0.55); // capped max darkening

  if (canvas) _wxStartOrUpdateCanvas(overlayEl, canvas, rain, snow);
  if (flash) _wxUpdateFlash(flash, storm);
}

class BoschEBikeMapCard extends HTMLElement {
  constructor() {
    super();
    this._hass = null;
    this._config = {};
    this._allActivities = [];   // unfiltered, all accounts/bikes
    this._activities = [];      // filtered view
    this._instances = [];        // [{config_entry_id, label, bikes:[{id,label}]}]
    this._filterAccount = "all"; // "all" | config_entry_id
    this._filterBike = "all";    // "all" | bike_id
    this._idx = 0;
    this._currentTrack = [];
    this._currentTrackActivityId = null;
    // Wikipedia overlay
    this._wikiEnabled = (typeof localStorage !== "undefined" && localStorage.getItem("eb-wiki-enabled") === "1");
    this._wikiArticles = new Map();   // activityId → [{pageId, title, lat, lon, lang}]
    this._wikiLoading = new Set();    // activity IDs currently being fetched
    this._wikiSummaries = new Map();  // pageId → {extract, thumbnail}
    this._wikiGroup = null;
    this._fullscreenWikiGroup = null;
    // Which activityId is currently rendered on each map (avoid re-rendering and killing open popups)
    this._wikiRenderedInline = null;
    this._wikiRenderedFullscreen = null;
    // POI overlay (Overpass)
    this._poiEnabled = (typeof localStorage !== "undefined" && localStorage.getItem("eb-poi-enabled") === "1");
    this._poiData = new Map();        // activityId → [{lat, lon, name, category, tags}]
    this._poiLoading = new Set();
    this._poiGroup = null;
    this._fullscreenPoiGroup = null;
    this._poiRenderedInline = null;
    this._poiRenderedFullscreen = null;
    // Weather overlay (opt-in, mirrors _wikiEnabled/_poiEnabled exactly)
    this._weatherEnabled = (typeof localStorage !== "undefined" && localStorage.getItem("eb-weather-enabled") === "1");
    this._weatherData = new Map();    // activityId -> {cloud,precip,snow,code} at ride start
    this._weatherLoading = new Set();

    this._map = null;
    this._trackGroup = null;
    this._inlineBaseLayer = null;
    this._legend = null;
    this._fullscreenMap = null;
    this._fullscreenTrackGroup = null;
    this._fullscreenBaseLayer = null;
    this._fullscreenLegend = null;
    this._resizeObserver = null;
    this._intersectionObserver = null;
    this._timers = new Set();

    this._fullscreenOpen = false;
    this._mapStyle = "osm";
    this._fullscreenTab = "map";
    this._sortKey = "date";
    this._sortAsc = false;
    this._inlineBaseLayer = null;
    this._fullscreenBaseLayer = null;

    this._ready = false;
    this._booting = false;
    this._connected = false;
    this._busy = false;
    this._leafletReady = false;
    this._mapVisible = false;
    this._pendingRender = false;
    this._loadSeq = 0;
    this._appliedLoadSeq = 0;

    this._boundVisibility = this._onVisibilityChange.bind(this);
    this._boundFocus = this._onFocus.bind(this);
    this._boundPageShow = this._onPageShow.bind(this);
    this._boundKeydown = this._onKeydown.bind(this);
  }

  setConfig(config) {
    const prevRadius = this._wikiRadius;
    this._config = { height: config.height || 400, ...config };
    // Allow pinning the card to a specific account / bike via Lovelace config.
    // When set, the corresponding dropdown is hidden and the filter is locked.
    if (config.account_id) {
      this._filterAccount = config.account_id;
      this._lockedAccount = true;
    } else {
      this._lockedAccount = false;
    }
    if (config.bike_id) {
      this._filterBike = config.bike_id;
      this._lockedBike = true;
    } else {
      this._lockedBike = false;
    }
    // Wikipedia search radius (m). Default 1000. Allowed: 500, 1000, 2000, 5000, 10000.
    const allowed = [500, 1000, 2000, 5000, 10000];
    const requested = parseInt(config.wiki_radius_m, 10);
    this._wikiRadius = allowed.includes(requested) ? requested : 1000;
    // POI proximity radius (m) — how far from the route a POI may be. Default 1000.
    const prevPoiRadius = this._poiRadius;
    const poiAllowed = [500, 1000, 2000, 5000, 10000];
    const poiRequested = parseInt(config.poi_radius_m, 10);
    this._poiRadius = poiAllowed.includes(poiRequested) ? poiRequested : 1000;

    // If the card was already built once (re-config without re-creation),
    // refresh UI and re-render
    if (this._ready) {
      this._applyConfigTitle();
      this._applyVisibilityConfig();
      this._populateFilterUI();
      this._applyFilter();
      // Wikipedia radius changed → invalidate cached articles, re-fetch if layer active
      if (prevRadius !== undefined && prevRadius !== this._wikiRadius) {
        this._wikiArticles.clear();
        this._wikiRenderedInline = null;
        this._wikiRenderedFullscreen = null;
        if (this._wikiGroup) try { this._wikiGroup.clearLayers(); } catch (_) {}
        if (this._fullscreenWikiGroup) try { this._fullscreenWikiGroup.clearLayers(); } catch (_) {}
        if (this._wikiEnabled && this._currentTrackActivityId) this._loadAndRenderWiki();
      }
      // POI radius changed → invalidate cached POIs, re-fetch if layer active
      if (prevPoiRadius !== undefined && prevPoiRadius !== this._poiRadius) {
        this._poiData.clear();
        this._poiRenderedInline = null;
        this._poiRenderedFullscreen = null;
        if (this._poiGroup) try { this._poiGroup.clearLayers(); } catch (_) {}
        if (this._fullscreenPoiGroup) try { this._fullscreenPoiGroup.clearLayers(); } catch (_) {}
        if (this._poiEnabled && this._currentTrackActivityId) this._loadAndRenderPoi();
      }
      if (this._activities.length) this._show(0, true);
      this._updateBatteryBadge();
    }
  }

  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    if (first) this._boot();
    else if (this._connected) this._scheduleActivation("hass update");
    this._updateBatteryBadge();
  }

  // Opt-in live battery SoC overlay (top-left) on the inline map, the
  // fullscreen view and the chase-cam overlay. Shows only when the user set
  // a live battery entity AND enabled "battery_live_show". Hidden otherwise
  // or when the entity is unavailable.
  _updateBatteryBadge() {
    if (!this._ready) return;
    const cfg = this._config || {};
    const entId = cfg.battery_live_entity;
    const enabled = !!cfg.battery_live_show && !!entId;
    const st = enabled && this._hass ? this._hass.states[entId] : null;
    const raw = st ? Number(st.state) : NaN;
    const ok = !!(enabled && st && st.state !== "unavailable" &&
                  st.state !== "unknown" && Number.isFinite(raw));
    const pct = ok ? Math.round(raw) : null;
    const html = ok
      ? `<svg viewBox="0 0 24 24"><path fill="currentColor" d="M16.67,4H15V2H9V4H7.33A1.33,1.33 0 0,0 6,5.33V20.67C6,21.4 6.6,22 7.33,22H16.67A1.33,1.33 0 0,0 18,20.67V5.33C18,4.6 17.4,4 16.67,4Z"/></svg><span>${pct}%</span>`
      : "";
    const low = ok && pct <= 20;
    const apply = (el) => {
      if (!el) return;
      el.style.display = ok ? "inline-flex" : "none";
      el.classList.toggle("eb-batt-low", low);
      if (ok) el.innerHTML = html;
    };
    apply(this.querySelector("#eb-batt-inline"));
    apply(this.querySelector("#eb-batt-full"));
    apply(this._chaseBattEl);   // chase overlay lives in document.body
  }

  connectedCallback() {
    this._connected = true;
    if (this._ready) {
      this._attachLifecycleHooks();
      this._scheduleActivation("connected");
    }
  }

  disconnectedCallback() {
    this._connected = false;
    this._detachLifecycleHooks();
    this._clearTimers();
    this._clearWeatherOverlay();
    this._destroyFullscreenMap();
    this._destroyMap(false);
  }

  getCardSize() {
    const cfg = this._config || {};
    // The "+4" base covers the surrounding chrome (header, nav, sort,
    // title/stats). Header/nav/sort are each roughly one row and can be
    // hidden independently via show_header/show_nav/show_sort, so shrink
    // the estimate accordingly (title/stats always render, hence the
    // floor of 1).
    let chrome = 4;
    if (cfg.show_header === false) chrome -= 1;
    if (cfg.show_nav === false) chrome -= 1;
    if (cfg.show_sort === false) chrome -= 1;
    return Math.ceil((cfg.height || 400) / 50) + Math.max(chrome, 1);
  }

  static getConfigElement() { return document.createElement("bosch-ebike-map-card-editor"); }
  static getStubConfig() { return { height: 400, show_sort: true, show_header: true, show_nav: true }; }

  async _boot() {
    if (this._booting || this._ready) return;
    this._booting = true;

    if (!this._ready) {
      this._buildDOM();
      this._attachLifecycleHooks();
      this._ready = true;
      this._updateBatteryBadge();
    }

    try {
      await ensureLeaflet();
      this._leafletReady = true;
      this._applyConfigTitle();
      await this._fetchInstances();
      await this._fetchActivities();
      this._scheduleActivation("boot finished");
    } catch (error) {
      console.error("[Bosch eBike Map] boot error", error);
      this._msg(this._t("msg_error_prefix") + describeBootError(this._hass, error));
    } finally {
      this._booting = false;
    }
  }

  _buildDOM() {
    const h = this._config.height || 400;
    this.innerHTML = "";

    const card = document.createElement("ha-card");
    this.appendChild(card);

    const style = document.createElement("style");
    style.textContent = LEAFLET_INLINE_CSS + `
      .eb-head {
        display:flex; align-items:center; gap:8px; padding:12px 16px;
        background:var(--primary-color,#03a9f4); color:#fff; font-size:16px; font-weight:500;
      }
      .eb-head svg { flex-shrink:0; }
      /* Opt-in live battery overlay, top-left on the map / fullscreen / chase. */
      .eb-batt-badge {
        position:absolute; left:12px; top:12px; z-index:1100;
        display:none; align-items:center; gap:6px;
        padding:5px 11px; border-radius:999px;
        background:rgba(33,33,33,.72); backdrop-filter:blur(4px);
        color:#fff; font-size:15px; font-weight:600; white-space:nowrap;
        box-shadow:0 2px 8px rgba(0,0,0,.25); pointer-events:none;
      }
      .eb-batt-badge.eb-batt-low { color:#ff5252; }
      .eb-batt-badge svg { width:18px; height:18px; }
      ${WX_OVERLAY_CSS}
      .eb-nav {
        display:flex; align-items:center; gap:8px; padding:8px 12px;
        background:var(--secondary-background-color,#f5f5f5);
        border-bottom:1px solid var(--divider-color,#e0e0e0);
      }
      .eb-nav button, .eb-icon-btn {
        width:36px; height:36px; flex-shrink:0;
        background:var(--primary-color,#03a9f4); color:#fff;
        border:none; border-radius:8px; cursor:pointer; font-size:16px;
        display:flex; align-items:center; justify-content:center;
      }
      .eb-nav button:disabled, .eb-icon-btn:disabled { opacity:.35; cursor:not-allowed; }
      .eb-nav input[type="date"] {
        flex:1; min-width:0; padding:6px 10px;
        border:1px solid var(--divider-color,#ccc); border-radius:6px; font-size:14px;
        background:var(--card-background-color,#fff); color:var(--primary-text-color,#333);
      }
      .eb-ctr { font-size:13px; color:var(--secondary-text-color,#666); white-space:nowrap; flex-shrink:0; }
      .eb-sort {
        display:flex; align-items:center; gap:8px; padding:6px 12px;
        background:var(--secondary-background-color,#f5f5f5);
        border-bottom:1px solid var(--divider-color,#e0e0e0);
      }
      .eb-sort select {
        flex:1; min-width:0; padding:5px 8px;
        border:1px solid var(--divider-color,#ccc); border-radius:6px; font-size:13px;
        background:var(--card-background-color,#fff); color:var(--primary-text-color,#333);
      }
      .eb-sort button {
        width:36px; height:36px; flex-shrink:0;
        background:var(--primary-color,#03a9f4); color:#fff;
        border:none; border-radius:8px; cursor:pointer; font-size:16px;
        display:flex; align-items:center; justify-content:center;
      }
      .eb-sort-lbl { font-size:12px; color:var(--secondary-text-color,#666); white-space:nowrap; flex-shrink:0; }
      .eb-icon-btn.eb-active {
        background:rgba(11,132,199,.95) !important;
        outline:2px solid rgba(255,255,255,.6);
      }
      .eb-icon-btn.eb-loading {
        opacity:.6;
        animation:eb-pulse 1.2s ease-in-out infinite;
      }
      @keyframes eb-pulse {
        0%,100% { opacity:.55; }
        50%     { opacity:.95; }
      }
      .eb-wiki-marker {
        background:rgba(255,255,255,.95);
        border:1.5px solid #0b84c7;
        border-radius:50%;
        width:14px !important; height:14px !important;
        display:flex; align-items:center; justify-content:center;
        font-family:Georgia,serif; font-style:italic; font-weight:700;
        color:#0b84c7; font-size:10px; line-height:1;
        box-shadow:0 1px 3px rgba(0,0,0,.3);
        cursor:pointer;
      }
      .eb-wiki-popup { font-family:inherit; max-width:280px; }
      .eb-wiki-popup .eb-wiki-title { font-size:15px; font-weight:600; margin-bottom:6px; color:#222; }
      .eb-wiki-popup .eb-wiki-thumb {
        max-width:100%; max-height:140px; border-radius:6px; margin-bottom:6px; display:block;
      }
      .eb-wiki-popup .eb-wiki-extract { font-size:12px; color:#444; line-height:1.35; margin-bottom:8px; }
      .eb-wiki-popup .eb-wiki-link {
        display:inline-block; padding:4px 10px;
        background:#0b84c7; color:#fff; border-radius:6px;
        text-decoration:none; font-size:12px; font-weight:500;
      }
      .eb-wiki-popup .eb-wiki-link:hover { background:#096ba3; }
      .eb-wiki-popup .eb-wiki-loading { font-size:12px; color:#888; }
      .eb-poi-marker {
        background:rgba(255,255,255,.95);
        border-radius:50%;
        width:18px !important; height:18px !important;
        display:flex; align-items:center; justify-content:center;
        font-size:12px; line-height:1;
        box-shadow:0 1px 3px rgba(0,0,0,.3);
        cursor:pointer;
      }
      .eb-poi-marker.eb-poi-charging { border:1.5px solid #2e7d32; }
      .eb-poi-marker.eb-poi-bicycle  { border:1.5px solid #c62828; }
      .eb-poi-marker.eb-poi-water    { border:1.5px solid #1565c0; }
      .eb-poi-marker.eb-poi-toilet   { border:1.5px solid #6a1b9a; }
      .eb-poi-marker.eb-poi-food       { border:1.5px solid #e65100; }
      .eb-poi-marker.eb-poi-cafe       { border:1.5px solid #5d4037; }
      .eb-poi-marker.eb-poi-biergarten { border:1.5px solid #f9a825; }
      .eb-poi-popup { font-family:inherit; max-width:240px; font-size:13px; }
      .eb-poi-popup .eb-poi-title { font-weight:600; margin-bottom:4px; }
      .eb-poi-popup .eb-poi-cat { font-size:11px; color:#666; margin-bottom:6px; }
      .eb-poi-popup .eb-poi-link {
        display:inline-block; padding:3px 8px;
        background:#0b84c7; color:#fff; border-radius:6px;
        text-decoration:none; font-size:11px; font-weight:500;
      }
      .eb-map-wrap { position:relative; }
      .eb-map { width:100% !important; height:${h}px !important; min-height:${h}px; z-index:0; position:relative; }
      .eb-overlay-msg {
        position:absolute; inset:0; display:flex; align-items:center; justify-content:center;
        color:var(--secondary-text-color,#999); font-size:14px; background:transparent; pointer-events:none;
      }
      .eb-map-tools {
        position:absolute; right:12px; top:12px; z-index:1100;
        display:flex; gap:8px;
      }
      .eb-map-tools .eb-icon-btn {
        width:40px; height:40px;
        background:rgba(33,33,33,.72); backdrop-filter:blur(4px);
        box-shadow:0 2px 8px rgba(0,0,0,.25);
      }
      /* flex-wrap so a long title + the date can share one row when there's
         room, and gracefully drop to two lines instead of overflowing when
         there isn't (issue #71: combine title and date to save space). */
      .eb-title {
        display:flex; flex-wrap:wrap; justify-content:center; align-items:center;
        column-gap:8px; row-gap:2px; padding:10px 16px 6px;
        font-size:16px; font-weight:600; color:var(--primary-text-color,#333);
      }
      .eb-bike-badge {
        display:none; flex-shrink:0; max-width:42%;
        align-items:center; margin-right:6px; opacity:0.72; font-weight:500;
      }
      /* Truncation lives on the inner text span, never on the badge itself,
         so a long bike name cannot clip the caret next to it. */
      .eb-bike-badge-text { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; min-width:0; }
      .eb-bike-caret { flex-shrink:0; margin-left:3px; font-size:9px; line-height:1; opacity:0.8; }
      /* Resting-state affordance: without it the name is indistinguishable
         from plain text, so nobody discovers it is clickable - and on touch
         devices there is no hover to reveal it either (issue #65). */
      .eb-bike-badge.eb-editable {
        cursor:pointer; opacity:0.9; padding:1px 6px; margin-right:8px;
        border:1px solid var(--divider-color,#d0d0d0); border-radius:999px;
        background:var(--secondary-background-color,rgba(127,127,127,.10));
      }
      .eb-bike-badge.eb-editable:hover,
      .eb-bike-badge.eb-editable:focus-visible {
        opacity:1; border-color:var(--primary-color,#03a9f4); outline:none;
      }
      .eb-bike-select {
        display:none; flex-shrink:0; max-width:52%; margin-right:6px;
        font-size:13px; font-weight:500; padding:1px 4px; border-radius:6px;
        border:1px solid var(--divider-color,#bbb);
        background:var(--card-background-color,#fff);
        color:var(--primary-text-color,#333);
      }
      .eb-trick-dot {
        display: none; flex-shrink: 0; width: 9px; height: 9px; margin-left: 7px;
        border-radius: 50%; background: #43a047; vertical-align: middle;
        box-shadow: 0 0 0 2px rgba(67,160,71,0.25);
      }
      /* Now an inline flex child of .eb-title (issue #71), not its own row.
         The separator only appears once there is actual date text, so an
         activity without a startTime renders no dangling "· ". */
      .eb-datelbl { font-size:12px; font-weight:400; color:var(--secondary-text-color,#666); }
      .eb-datelbl:not(:empty)::before { content:"· "; }
      .eb-stats { display:grid; grid-template-columns:repeat(3,1fr); gap:4px; padding:8px 16px 14px; }
      .eb-stat { text-align:center; }
      .eb-val { font-size:20px; font-weight:700; color:var(--primary-text-color,#212121); }
      .eb-lbl { font-size:11px; color:var(--secondary-text-color,#757575); }
      /* Compact fallback navigator shown only when show_nav hides the main
         prev/next bar (issue #71), so switching rides stays possible. */
      .eb-stats-nav { display:flex; align-items:center; justify-content:center; gap:10px; padding:2px 16px 6px; }
      .eb-stats-nav button {
        width:28px; height:28px; flex-shrink:0;
        background:var(--primary-color,#03a9f4); color:#fff;
        border:none; border-radius:6px; cursor:pointer; font-size:13px;
        display:flex; align-items:center; justify-content:center;
      }
      .eb-stats-nav button:disabled { opacity:.35; cursor:not-allowed; }
      .eb-stats-nav .eb-ctr { font-size:12px; color:var(--secondary-text-color,#666); white-space:nowrap; }

      .eb-fullscreen {
        position:fixed; inset:0; z-index:99999;
        display:none; align-items:stretch; justify-content:stretch;
        background:rgba(0,0,0,.72);
      }
      .eb-fullscreen.open { display:flex; }
      .eb-fullscreen-card {
        width:min(1400px, 100vw); height:100vh; margin:auto;
        background:var(--card-background-color,#111);
        display:flex; flex-direction:column;
        overflow-y:auto;
        -webkit-overflow-scrolling:touch;
      }
      .eb-fullscreen-head {
        display:flex; align-items:center; gap:8px;
        padding:10px 12px; color:#fff;
        background:rgba(0,0,0,.35);
        border-bottom:1px solid rgba(255,255,255,.12);
      }
      .eb-fullscreen-title { flex:1; min-width:0; display:flex; align-items:center; font-weight:600; }
      .eb-fullscreen-title-text { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; min-width:0; }
      .eb-fullscreen-nav { display:flex; align-items:center; gap:8px; flex-wrap:wrap; }
      .eb-fullscreen-nav input[type="date"] { min-width:170px; padding:6px 10px; border:1px solid rgba(255,255,255,.2); border-radius:8px; background:rgba(255,255,255,.12); color:#fff; }
      .eb-fullscreen-nav .eb-ctr { color:rgba(255,255,255,.8); }
      /* Wrapper owns the fullscreen map's flex sizing/positioning (mirrors
         .eb-map-wrap in the inline case). #eb-fullscreen-map itself must
         stay a plain, un-sized child: Leaflet mounts directly onto it and
         _syncFullscreenMap()/_destroyFullscreenMap() do
         mapEl.innerHTML = "" on it, which would wipe #eb-full-wx-overlay
         if the overlay lived inside it instead of as a wrapper sibling. */
      .eb-fullscreen-map-wrap { flex:1; min-height:280px; position:relative; }
      .eb-fullscreen-map { width:100%; height:100%; position:relative; }
      .eb-profile { background:var(--card-background-color,#fff); border-top:1px solid var(--divider-color,#ddd); padding:12px 14px 8px; overflow:visible; }
      .eb-profile-head { display:flex; align-items:baseline; justify-content:space-between; gap:12px; margin-bottom:8px; }
      .eb-profile-title { font-size:16px; font-weight:600; color:var(--primary-text-color,#222); }
      .eb-profile-range { font-size:12px; color:var(--secondary-text-color,#666); }
      .eb-profile-chart { width:100%; height:180px; display:block; }
      .eb-profile-axis { display:flex; justify-content:space-between; font-size:11px; color:var(--secondary-text-color,#777); margin-top:4px; }
      .eb-profile-stats { display:grid; grid-template-columns:repeat(4,1fr); gap:10px; margin-top:10px; }
      .eb-profile-stat { background:var(--secondary-background-color,#f5f5f5); border-radius:10px; padding:10px 8px; text-align:center; }
      .eb-profile-stat .eb-pv { font-size:16px; font-weight:700; color:var(--primary-text-color,#212121); }
      .eb-profile-stat .eb-pl { font-size:11px; color:var(--secondary-text-color,#757575); margin-top:2px; }
      .eb-fullscreen-meta {
        padding:8px 12px; display:grid; grid-template-columns:repeat(4,1fr); gap:8px;
        background:var(--card-background-color,#fff);
        border-top:1px solid var(--divider-color,#ddd);
      }
      .eb-fullscreen-meta .eb-stat { background:var(--secondary-background-color,#f5f5f5); border-radius:10px; padding:8px 4px; }
      .eb-fullscreen-tabs {
        display:flex; gap:8px; padding:10px 12px 0;
        background:#fff !important;
        border-bottom:1px solid var(--divider-color,#ddd);
      }
      .eb-fullscreen-tabs .eb-fullscreen-tab {
        appearance:none; border:none; background:transparent !important; color:#222 !important;
        opacity:1 !important; visibility:visible !important;
        padding:10px 2px 12px; margin:0 10px 0 0; font-size:14px; font-weight:600; cursor:pointer;
        border-bottom:2px solid transparent;
      }
      .eb-fullscreen-tabs .eb-fullscreen-tab.active {
        color:#111 !important; border-bottom-color:var(--primary-color,#03a9f4);
      }
      .eb-hidden { display:none !important; }
      @media (max-width: 700px) {
        .eb-stats { grid-template-columns:repeat(2,1fr); }
        .eb-profile-stats { grid-template-columns:repeat(2,1fr); }
        .eb-fullscreen-meta { grid-template-columns:repeat(2,1fr); }
        .eb-fullscreen-head { flex-wrap:wrap; }
        .eb-fullscreen-title { width:100%; }
        .eb-fullscreen-nav { width:100%; }
        .eb-fullscreen-nav input[type="date"] { flex:1; min-width:0; }
        .eb-fullscreen-card { overflow-y:auto; -webkit-overflow-scrolling:touch; }
      }
    `;
    card.appendChild(style);

    const wrap = document.createElement("div");
    const t = (k) => this._t(k);
    wrap.innerHTML = `
      <div class="eb-head">
        <svg viewBox="0 0 24 24" width="22" height="22"><path fill="white" d="M15.5,5.5C16.9,5.5 18,6.6 18,8C18,9.4 16.9,10.5 15.5,10.5C14.1,10.5 13,9.4 13,8C13,6.6 14.1,5.5 15.5,5.5M5,12C2.2,12 0,14.2 0,17C0,19.8 2.2,22 5,22C7.8,22 10,19.8 10,17C10,14.2 7.8,12 5,12M5,20.5C3.1,20.5 1.5,18.9 1.5,17C1.5,15.1 3.1,13.5 5,13.5C6.9,13.5 8.5,15.1 8.5,17C8.5,18.9 6.9,20.5 5,20.5M19,12C16.2,12 14,14.2 14,17C14,19.8 16.2,22 19,22C21.8,22 24,19.8 24,17C24,14.2 21.8,12 19,12M19,20.5C17.1,20.5 15.5,18.9 15.5,17C15.5,15.1 17.1,13.5 19,13.5C20.9,13.5 22.5,15.1 22.5,17C22.5,18.9 20.9,20.5 19,20.5M12.5,11.5L10.1,8.8C10.6,7.8 11.4,7.3 12.3,7.3H14.2L12.9,6H10.3C9.1,6 8,6.7 7.5,7.8L6.1,10.8L5,12.1L7.2,13.5L8.3,11.5H12.5Z"/></svg>
        <span>${t("rides_title")}</span>
      </div>
      <div class="eb-nav">
        <button id="eb-prev">◀</button>
        <input type="date" id="eb-date">
        <button id="eb-next">▶</button>
        <span id="eb-ctr" class="eb-ctr">–</span>
      </div>
      <div class="eb-sort" id="eb-filter-account-wrap" style="display:none;">
        <span class="eb-sort-lbl">${t("account_label")}</span>
        <select id="eb-filter-account">
          <option value="all">${t("all_accounts")}</option>
        </select>
      </div>
      <div class="eb-sort" id="eb-filter-bike-wrap" style="display:none;">
        <span class="eb-sort-lbl">${t("bike_label")}</span>
        <select id="eb-filter-bike">
          <option value="all">${t("all_bikes")}</option>
        </select>
      </div>
      <div class="eb-sort" id="eb-sort-wrap">
        <span class="eb-sort-lbl">${t("sort_label")}</span>
        <select id="eb-sort-key">
          <option value="date">${t("sort_date")}</option>
          <option value="distance">${t("sort_distance")}</option>
          <option value="duration">${t("sort_duration")}</option>
          <option value="avgSpeed">${t("sort_avg_speed")}</option>
          <option value="maxSpeed">${t("sort_max_speed")}</option>
          <option value="elevation">${t("sort_elevation")}</option>
          <option value="calories">${t("sort_calories")}</option>
          <option value="difficulty">${t("sort_difficulty")}</option>
          <option value="batteryWh">${t("sort_battery_wh")}</option>
          <option value="batteryPct">${t("sort_battery_pct")}</option>
        </select>
        <button id="eb-sort-dir" title="${t("sort_dir_title")}">↓</button>
      </div>
      <div class="eb-map-wrap">
        <div id="eb-map" class="eb-map"></div>
        <div id="eb-wx-overlay" class="eb-wx-overlay" style="display:none;">
          <div class="eb-wx-veil"></div>
          <canvas class="eb-wx-canvas"></canvas>
          <div class="eb-wx-flash"></div>
        </div>
        <div class="eb-map-tools">
          <button id="eb-style" class="eb-icon-btn eb-style-btn" title="${t("btn_change_style")}" aria-label="${t("btn_change_style")}">OSM</button>
          <button id="eb-wiki" class="eb-icon-btn" title="${t("btn_wiki")}" aria-label="${t("btn_wiki")}">📚</button>
          <button id="eb-poi" class="eb-icon-btn" title="${t("btn_poi")}" aria-label="${t("btn_poi")}">📍</button>
          <button id="eb-weather" class="eb-icon-btn" title="${t("btn_weather")}" aria-label="${t("btn_weather")}">🌦️</button>
          <button id="eb-gpx" class="eb-icon-btn" title="${t("btn_gpx")}" aria-label="${t("btn_gpx")}">GPX</button>
          <button id="eb-chase" class="eb-icon-btn" title="${t("btn_chase")}" aria-label="${t("btn_chase")}">
            <svg viewBox="0 0 24 24" width="20" height="20"><path fill="currentColor" d="M8 5v14l11-7z"/></svg>
          </button>
          <button id="eb-fullscreen" class="eb-icon-btn" title="${t("btn_fullscreen")}" aria-label="${t("btn_fullscreen")}">
            <svg viewBox="0 0 24 24" width="20" height="20"><path fill="currentColor" d="M7,14H5V19H10V17H7V14M5,10H7V7H10V5H5V10M17,17H14V19H19V14H17V17M14,5V7H17V10H19V5H14Z"/></svg>
          </button>
        </div>
        <div id="eb-overlay-msg" class="eb-overlay-msg"></div>
        <div id="eb-batt-inline" class="eb-batt-badge"></div>
      </div>
      <div id="eb-title" class="eb-title"><span id="eb-bike-badge" class="eb-bike-badge"></span><select id="eb-bike-select" class="eb-bike-select"></select><span id="eb-title-text"></span><span id="eb-trick-dot" class="eb-trick-dot" style="display:none" title="${t("trick_hint_tooltip")}"></span><span id="eb-date-lbl" class="eb-datelbl"></span></div>
      <div id="eb-stats-nav" class="eb-stats-nav" style="display:none;">
        <button id="eb-stats-prev" title="${t("btn_prev")}" aria-label="${t("btn_prev")}">◀</button>
        <span id="eb-stats-ctr" class="eb-ctr">–</span>
        <button id="eb-stats-next" title="${t("btn_next")}" aria-label="${t("btn_next")}">▶</button>
      </div>
      <div id="eb-stats" class="eb-stats"></div>
      <div id="eb-fullscreen-overlay" class="eb-fullscreen" aria-hidden="true">
        <div class="eb-fullscreen-card">
          <div class="eb-fullscreen-head">
            <div id="eb-fullscreen-title" class="eb-fullscreen-title"><span id="eb-fullscreen-bike-badge" class="eb-bike-badge"></span><select id="eb-fullscreen-bike-select" class="eb-bike-select"></select><span id="eb-fullscreen-title-text">${t("rides_title")}</span><span id="eb-fullscreen-trick-dot" class="eb-trick-dot" style="display:none" title="${t("trick_hint_tooltip")}"></span></div>
            <div class="eb-fullscreen-nav">
              <button id="eb-full-prev" class="eb-icon-btn" title="${t("btn_prev")}" aria-label="${t("btn_prev")}">◀</button>
              <input type="date" id="eb-full-date">
              <button id="eb-full-next" class="eb-icon-btn" title="${t("btn_next")}" aria-label="${t("btn_next")}">▶</button>
              <span id="eb-full-ctr" class="eb-ctr">–</span>
            </div>
            <button id="eb-full-style" class="eb-icon-btn eb-style-btn" title="${t("btn_change_style")}" aria-label="${t("btn_change_style")}">OSM</button>
            <button id="eb-full-wiki" class="eb-icon-btn" title="${t("btn_wiki")}" aria-label="${t("btn_wiki")}">📚</button>
            <button id="eb-full-poi" class="eb-icon-btn" title="${t("btn_poi")}" aria-label="${t("btn_poi")}">📍</button>
            <button id="eb-full-weather" class="eb-icon-btn" title="${t("btn_weather")}" aria-label="${t("btn_weather")}">🌦️</button>
            <button id="eb-full-gpx" class="eb-icon-btn" title="${t("btn_gpx")}" aria-label="${t("btn_gpx")}">GPX</button>
            <button id="eb-full-chase" class="eb-icon-btn" title="${t("btn_chase")}" aria-label="${t("btn_chase")}">
              <svg viewBox="0 0 24 24" width="20" height="20"><path fill="currentColor" d="M8 5v14l11-7z"/></svg>
            </button>
            <button id="eb-fit" class="eb-icon-btn" title="${t("btn_fit")}" aria-label="${t("btn_fit")}">
              <svg viewBox="0 0 24 24" width="20" height="20"><path fill="currentColor" d="M4,4H10V6H6V10H4V4M14,4H20V10H18V6H14V4M4,14H6V18H10V20H4V14M18,14H20V20H14V18H18V14Z"/></svg>
            </button>
            <button id="eb-full-close" class="eb-icon-btn" title="${t("btn_close")}" aria-label="${t("btn_close")}">
              <svg viewBox="0 0 24 24" width="20" height="20"><path fill="currentColor" d="M19,6.41L17.59,5L12,10.59L6.41,5L5,6.41L10.59,12L5,17.59L6.41,19L12,13.41L17.59,19L19,17.59L13.41,12L19,6.41Z"/></svg>
            </button>
          </div>
          <div class="eb-fullscreen-tabs" role="tablist" aria-label="${t("btn_view_label")}">
            <button id="eb-tab-map" class="eb-fullscreen-tab active" role="tab" aria-selected="true">${t("tab_map")}</button>
            <button id="eb-tab-elevation" class="eb-fullscreen-tab" role="tab" aria-selected="false">${t("tab_elevation")}</button>
          </div>
          <div id="eb-fullscreen-map-wrap" class="eb-fullscreen-map-wrap">
            <div id="eb-fullscreen-map" class="eb-fullscreen-map">
              <div id="eb-batt-full" class="eb-batt-badge"></div>
            </div>
            <div id="eb-full-wx-overlay" class="eb-wx-overlay" style="display:none;">
              <div class="eb-wx-veil"></div>
              <canvas class="eb-wx-canvas"></canvas>
              <div class="eb-wx-flash"></div>
            </div>
          </div>
          <div id="eb-fullscreen-profile" class="eb-profile eb-hidden"></div>
          <div id="eb-fullscreen-stats-nav" class="eb-stats-nav" style="display:none;">
            <button id="eb-fullscreen-stats-prev" title="${t("btn_prev")}" aria-label="${t("btn_prev")}">◀</button>
            <span id="eb-fullscreen-stats-ctr" class="eb-ctr">–</span>
            <button id="eb-fullscreen-stats-next" title="${t("btn_next")}" aria-label="${t("btn_next")}">▶</button>
          </div>
          <div id="eb-fullscreen-meta" class="eb-fullscreen-meta"></div>
        </div>
      </div>
    `;
    while (wrap.firstChild) card.appendChild(wrap.firstChild);

    this._$("eb-prev").addEventListener("click", () => this._go(-1));
    this._$("eb-next").addEventListener("click", () => this._go(1));
    this._$("eb-date").addEventListener("change", (e) => this._jumpDate(e.target.value));
    // Compact fallback navigator in the stats area, only shown when
    // show_nav hides the main prev/next bar (issue #71).
    this._$("eb-stats-prev").addEventListener("click", () => this._go(-1));
    this._$("eb-stats-next").addEventListener("click", () => this._go(1));
    this._$("eb-style").addEventListener("click", () => this._cycleMapStyle());
    this._$("eb-gpx").addEventListener("click", () => this._downloadCurrentGpx());
    this._$("eb-fullscreen").addEventListener("click", () => this._openFullscreen());
    this._$("eb-chase").addEventListener("click", () => this._openChaseCam());
    this._$("eb-full-style").addEventListener("click", () => this._cycleMapStyle());
    this._$("eb-full-gpx").addEventListener("click", () => this._downloadCurrentGpx());
    const fullChase = this._$("eb-full-chase");
    if (fullChase) fullChase.addEventListener("click", () => this._openChaseCam());
    this._$("eb-full-close").addEventListener("click", () => this._closeFullscreen());
    this._$("eb-wiki").addEventListener("click", () => this._toggleWikipedia());
    const fullWiki = this._$("eb-full-wiki");
    if (fullWiki) fullWiki.addEventListener("click", () => this._toggleWikipedia());
    this._$("eb-poi").addEventListener("click", () => this._togglePoi());
    const fullPoi = this._$("eb-full-poi");
    if (fullPoi) fullPoi.addEventListener("click", () => this._togglePoi());
    this._$("eb-weather").addEventListener("click", () => this._toggleWeather());
    const fullWeather = this._$("eb-full-weather");
    if (fullWeather) fullWeather.addEventListener("click", () => this._toggleWeather());
    this._$("eb-tab-map").addEventListener("click", () => this._setFullscreenTab("map"));
    this._$("eb-tab-elevation").addEventListener("click", () => this._setFullscreenTab("elevation"));
    this._$("eb-full-prev").addEventListener("click", () => this._go(-1));
    this._$("eb-full-next").addEventListener("click", () => this._go(1));
    this._$("eb-fullscreen-stats-prev").addEventListener("click", () => this._go(-1));
    this._$("eb-fullscreen-stats-next").addEventListener("click", () => this._go(1));
    this._$("eb-full-date").addEventListener("change", (e) => this._jumpDate(e.target.value));
    this._$("eb-fit").addEventListener("click", () => {
      this._fullscreenUserAdjustedView = false;
      this._needsFullscreenFit = false;
      this._fitMapToTrack(this._fullscreenMap, this._currentTrack, [60, 60]);
    });
    this._$("eb-fullscreen-overlay").addEventListener("click", (e) => {
      if (e.target === this._$("eb-fullscreen-overlay")) this._closeFullscreen();
    });

    this._$("eb-sort-key").addEventListener("change", (e) => {
      this._sortKey = e.target.value;
      this._applySort();
    });
    this._$("eb-sort-dir").addEventListener("click", () => {
      this._sortAsc = !this._sortAsc;
      this._$("eb-sort-dir").textContent = this._sortAsc ? "↑" : "↓";
      this._applySort();
    });

    const accountSel = this._$("eb-filter-account");
    if (accountSel) {
      accountSel.addEventListener("change", (e) => {
        this._filterAccount = e.target.value;
        this._populateFilterUI(); // refresh bike dropdown to match account
        this._applyFilter();
        if (this._activities.length) {
          this._show(0, true);
        } else {
          this._msg(this._t("msg_no_filter_match"));
        }
      });
    }
    const bikeSel = this._$("eb-filter-bike");
    if (bikeSel) {
      bikeSel.addEventListener("change", (e) => {
        this._filterBike = e.target.value;
        this._applyFilter();
        if (this._activities.length) {
          this._show(0, true);
        } else {
          this._msg(this._t("msg_no_filter_match"));
        }
      });
    }

    this._updateStyleButtons();
    this._updateWikiButtons();
    this._updatePoiButtons();
    this._updateWeatherButtons();
    this._applyVisibilityConfig();
  }

  _attachLifecycleHooks() {
    const mapEl = this._$("eb-map");
    if (!mapEl) return;

    if (window.ResizeObserver && !this._resizeObserver) {
      this._resizeObserver = new ResizeObserver(() => {
        this._scheduleActivation("resize");
      });
      this._resizeObserver.observe(mapEl);
    }

    if (window.IntersectionObserver && !this._intersectionObserver) {
      this._intersectionObserver = new IntersectionObserver((entries) => {
        const entry = entries[0];
        this._mapVisible = !!entry && (entry.isIntersecting || entry.intersectionRatio > 0);
        if (this._mapVisible) this._scheduleActivation("intersection");
      }, { threshold: [0, 0.01, 0.1, 0.25] });
      this._intersectionObserver.observe(mapEl);
    }

    document.addEventListener("visibilitychange", this._boundVisibility);
    window.addEventListener("focus", this._boundFocus);
    window.addEventListener("pageshow", this._boundPageShow);
    window.addEventListener("keydown", this._boundKeydown);
  }

  _detachLifecycleHooks() {
    if (this._resizeObserver) {
      this._resizeObserver.disconnect();
      this._resizeObserver = null;
    }
    if (this._intersectionObserver) {
      this._intersectionObserver.disconnect();
      this._intersectionObserver = null;
    }
    document.removeEventListener("visibilitychange", this._boundVisibility);
    window.removeEventListener("focus", this._boundFocus);
    window.removeEventListener("pageshow", this._boundPageShow);
    window.removeEventListener("keydown", this._boundKeydown);
  }

  _onVisibilityChange() {
    if (!document.hidden) this._scheduleActivation("visibilitychange");
  }

  _onFocus() {
    this._scheduleActivation("focus");
  }

  _onPageShow() {
    this._scheduleActivation("pageshow");
    if (this._fullscreenOpen) this._scheduleFullscreenSync("pageshow");
  }

  _onKeydown(ev) {
    if (ev.key === "Escape" && this._fullscreenOpen) this._closeFullscreen();
  }

  _$(id) {
    return this.querySelector("#" + id);
  }

  _msg(text) {
    const overlay = this._$("eb-overlay-msg");
    if (overlay) overlay.textContent = text || "";
  }

  _clearTimers() {
    for (const id of this._timers) window.clearTimeout(id);
    this._timers.clear();
  }

  _setTimer(fn, delay) {
    const id = window.setTimeout(() => {
      this._timers.delete(id);
      fn();
    }, delay);
    this._timers.add(id);
    return id;
  }

  _scheduleActivation(reason = "") {
    if (!this._connected || !this._leafletReady || !this._activities.length) return;
    if (this._pendingRender) return;
    this._pendingRender = true;

    const steps = [0, 120, 350, 900];
    steps.forEach((delay) => {
      this._setTimer(() => this._activateMap(reason), delay);
    });
    this._setTimer(() => {
      if (this._fullscreenOpen) this._scheduleFullscreenSync(reason || "activation");
      this._pendingRender = false;
    this._loadSeq = 0;
    this._appliedLoadSeq = 0;
    }, Math.max(...steps) + 50);
  }

  _scheduleFullscreenSync(reason = "") {
    if (!this._fullscreenOpen) return;
    [0, 120, 350].forEach((delay) => {
      this._setTimer(() => this._syncFullscreenMap(reason), delay);
    });
  }

  _isContainerUsable() {
    const mapEl = this._$("eb-map");
    if (!mapEl || !this.isConnected) return false;
    const rect = mapEl.getBoundingClientRect();
    return rect.width > 40 && rect.height > 40;
  }

  async _fetchInstances() {
    try {
      const res = await this._hass.callWS({ type: "bosch_ebike/list_instances" });
      this._instances = res.instances || [];
    } catch (e) {
      this._instances = [];
    }
    this._populateFilterUI();
  }

  async _fetchActivities() {
    const res = await this._hass.callWS({ type: "bosch_ebike/list_activities" });
    this._allActivities = (res.activities || []).sort((a, b) => new Date(b.startTime) - new Date(a.startTime));
    this._applyFilter();

    if (!this._activities.length) {
      this._msg(this._filtersActive() ? this._t("msg_no_filter_match") : this._t("msg_no_rides"));
      return;
    }

    await this._show(0, false);
  }

  _filtersActive() {
    return this._filterAccount !== "all" || this._filterBike !== "all";
  }

  /// Apply current account/bike filter to _allActivities → _activities
  _applyFilter() {
    let list = [...this._allActivities];
    if (this._filterAccount !== "all") {
      list = list.filter((a) => a.accountId === this._filterAccount);
    }
    if (this._filterBike !== "all") {
      list = list.filter((a) => a.bikeId === this._filterBike);
    }
    this._activities = list;
  }

  /// Build the dropdown options for accounts and bikes based on _instances.
  /// When `account_id`/`bike_id` is set in card config, the corresponding
  /// dropdown is hidden entirely (the filter is locked to the configured value).
  _populateFilterUI() {
    const accountSel = this._$("eb-filter-account");
    const bikeSel = this._$("eb-filter-bike");
    const accountWrap = this._$("eb-filter-account-wrap");
    const bikeWrap = this._$("eb-filter-bike-wrap");
    if (!accountSel || !bikeSel) return;

    // Account dropdown: hidden if locked via config OR if only one instance
    if (this._lockedAccount) {
      if (accountWrap) accountWrap.style.display = "none";
    } else if (this._instances.length > 1) {
      const opts = [`<option value="all">${this._t("all_accounts")}</option>`];
      for (const inst of this._instances) {
        opts.push(`<option value="${inst.config_entry_id}">${this._escapeHtml(inst.label)}</option>`);
      }
      accountSel.innerHTML = opts.join("");
      accountSel.value = this._filterAccount;
      if (accountWrap) accountWrap.style.display = "";
    } else {
      if (accountWrap) accountWrap.style.display = "none";
    }

    // Bike dropdown: union of all bikes (or filtered to selected account)
    const bikes = [];
    for (const inst of this._instances) {
      if (this._filterAccount !== "all" && inst.config_entry_id !== this._filterAccount) continue;
      for (const b of (inst.bikes || [])) {
        const label = this._instances.length > 1 ? `${inst.label} — ${b.label}` : b.label;
        bikes.push({ id: b.id, label });
      }
    }
    // Reused by _show() to prefix the ride title with its bike name when
    // the "All Bikes" filter can't otherwise disambiguate (issue #65).
    this._bikeLabelById = new Map(bikes.map((b) => [b.id, b.label]));
    // Per-account bike lists for the in-card reassignment dropdown (issue
    // #65 follow-up). Deliberately built from ALL instances, ignoring the
    // account filter above: the reassignment options for a ride depend on
    // which account the RIDE belongs to, not on what the user is currently
    // filtering by. A ride can only ever move between bikes of its own
    // account (the backend rejects anything else), so each account's list
    // stays separate rather than being flattened like `bikes` above.
    this._bikesByAccount = new Map();
    for (const inst of this._instances) {
      this._bikesByAccount.set(
        inst.config_entry_id,
        (inst.bikes || []).map((b) => ({ id: b.id, label: b.label })),
      );
    }

    // Bike dropdown: hidden if locked via config OR <=1 bike total
    if (this._lockedBike) {
      if (bikeWrap) bikeWrap.style.display = "none";
    } else {
      const bikeOpts = [`<option value="all">${this._t("all_bikes")}</option>`];
      for (const b of bikes) {
        bikeOpts.push(`<option value="${b.id}">${this._escapeHtml(b.label)}</option>`);
      }
      bikeSel.innerHTML = bikeOpts.join("");
      // Reset bike filter if currently selected bike isn't in the new list
      if (this._filterBike !== "all" && !bikes.some((b) => b.id === this._filterBike)) {
        this._filterBike = "all";
      }
      bikeSel.value = this._filterBike;
      if (bikeWrap) bikeWrap.style.display = bikes.length > 1 ? "" : "none";
    }
  }

  /// Apply config.title to the card header if present
  _applyConfigTitle() {
    const head = this.querySelector(".eb-head span");
    if (head && this._config && this._config.title) {
      head.textContent = this._config.title;
    }
  }

  /// Show/hide the sort dropdown, header and date navigator (incl. the
  /// fullscreen nav twin) per config. All three default to visible
  /// (opt-out via show_sort/show_header/show_nav === false), matching the
  /// stats-card convention. show_nav governs both the inline and the
  /// fullscreen navigator so behavior stays consistent between views.
  _applyVisibilityConfig() {
    const cfg = this._config || {};
    const set = (selector, visible) => {
      const el = this.querySelector(selector);
      if (el) el.style.display = visible ? "" : "none";
    };
    set(".eb-head", cfg.show_header !== false);
    set(".eb-nav", cfg.show_nav !== false);
    set(".eb-fullscreen-nav", cfg.show_nav !== false);
    set("#eb-sort-wrap", cfg.show_sort !== false);
    // Inverted: the compact stats-area fallback navigator only appears
    // once the main nav is hidden, so switching rides stays possible
    // without duplicating both navigators at once (issue #71).
    set("#eb-stats-nav", cfg.show_nav === false);
    set("#eb-fullscreen-stats-nav", cfg.show_nav === false);
  }

  _escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
    })[c]);
  }

  _t(key, ...args) {
    return ebT(this._hass, key, ...args);
  }

  _getSortValue(activity, key) {
    switch (key) {
      case "date": return new Date(activity.startTime || 0).getTime();
      case "distance": return activity.distance || 0;
      case "duration": return activity.durationWithoutStops || 0;
      case "avgSpeed": return activity.speed?.average ?? 0;
      case "maxSpeed": return activity.speed?.maximum ?? 0;
      case "elevation": return activity.elevation?.gain ?? 0;
      case "calories": return activity.caloriesBurned ?? 0;
      case "difficulty": {
        const d = activity.distance ? activity.distance / 1000 : 0;
        return d > 0 ? (activity.elevation?.gain ?? 0) / d : 0;
      }
      case "batteryWh": return activity.consumption?.consumed_wh ?? 0;
      case "batteryPct": return activity.consumption?.percentage ?? 0;
      default: return 0;
    }
  }

  _applySort() {
    const key = this._sortKey;
    const asc = this._sortAsc;
    this._activities.sort((a, b) => {
      const va = this._getSortValue(a, key);
      const vb = this._getSortValue(b, key);
      return asc ? va - vb : vb - va;
    });
    this._show(0, true);
  }

  /// Short "1x Jump, 2x Wheelie" summary for the trick-dot's tooltip.
  _trickSummary(trick) {
    if (!trick) return "";
    const parts = [];
    for (const { key, nameKey } of TRICK_TYPE_DEFS) {
      const t = trick[key];
      if (t && t.amount) parts.push(`${t.amount}× ${this._t(nameKey)}`);
    }
    return parts.join(", ");
  }

  /// One extra .eb-stat tile per trick type that actually happened, with
  /// the full max distance/duration/height-or-angle breakdown as a hover
  /// tooltip (see trick_check.py for the parsed field shapes).
  _trickStatsHtml(trick) {
    if (!trick || !trick.has_any) return "";
    const fmt = (v, digits) => (v == null ? "–" : v.toFixed(digits));
    return TRICK_TYPE_DEFS.map(({ key, nameKey, hasHeight }) => {
      const t = trick[key];
      if (!t || !t.amount) return "";
      const dist = fmt(t.max_distance_m, 1);
      const dur = fmt(t.max_duration_s, 2);
      const detail = hasHeight
        ? this._t("trick_detail_height", dist, dur, fmt(t.max_height_m, 2))
        : this._t("trick_detail_angle", dist, dur, fmt(t.max_angle_deg, 1));
      return `<div class="eb-stat" title="${this._escapeHtml(detail)}"><div class="eb-val">${t.amount}×</div><div class="eb-lbl">${this._escapeHtml(this._t(nameKey))}</div></div>`;
    }).join("");
  }

  /// Bikes a ride may be reassigned to: those of its OWN account only.
  /// The backend rejects anything else, since the attribution override it
  /// writes is per-account state (see ws_assign_activity in __init__.py).
  _reassignOptionsFor(activity) {
    if (!activity || !activity.accountId) return [];
    return (this._bikesByAccount && this._bikesByAccount.get(activity.accountId)) || [];
  }

  /// Render the bike badge, and make it a click-to-reassign control when
  /// this ride's account actually has more than one bike to choose from
  /// (issue #65: the odometer heuristic sometimes attributes a ride to the
  /// wrong bike, and until now only the options-flow wizard could fix
  /// that - and only for rides it failed to attribute at all).
  _updateBikeBadge(badgeId, selectId, activity, bikeLabel) {
    const badge = this._$(badgeId);
    const select = this._$(selectId);
    if (!badge) return;
    // Built from element nodes rather than innerHTML: bikeLabel is a
    // backend-supplied device name, and textContent needs no escaping.
    badge.textContent = "";
    if (bikeLabel) {
      const text = document.createElement("span");
      text.className = "eb-bike-badge-text";
      text.textContent = `${bikeLabel} —`;
      badge.appendChild(text);
    }
    badge.style.display = bikeLabel ? "inline-flex" : "none";
    if (select) select.style.display = "none";

    if (select && !badge.dataset.reassignWired) {
      badge.dataset.reassignWired = "1";
      badge.addEventListener("click", () => this._openBikeEditor(badgeId, selectId));
      badge.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          this._openBikeEditor(badgeId, selectId);
        }
      });
      select.addEventListener("change", () =>
        this._commitBikeAssignment(select.value, badgeId, selectId));
      select.addEventListener("blur", () => this._closeBikeEditor(badgeId, selectId));
      select.addEventListener("keydown", (e) => {
        if (e.key === "Escape") {
          // Must not bubble: the window-level handler in _onKeydown closes
          // the whole fullscreen overlay on Escape, so without this,
          // aborting the dropdown would also tear down fullscreen.
          e.stopPropagation();
          this._closeBikeEditor(badgeId, selectId);
        }
      });
    }

    const editable = Boolean(bikeLabel) && this._reassignOptionsFor(activity).length > 1;
    badge.classList.toggle("eb-editable", editable);
    badge.title = editable ? this._t("bike_reassign_hint") : "";
    if (editable) {
      const caret = document.createElement("span");
      caret.className = "eb-bike-caret";
      caret.textContent = "▼";
      badge.appendChild(caret);
      badge.setAttribute("role", "button");
      badge.setAttribute("tabindex", "0");
    } else {
      badge.removeAttribute("role");
      badge.removeAttribute("tabindex");
    }
  }

  _closeBikeEditor(badgeId, selectId) {
    const badge = this._$(badgeId);
    const select = this._$(selectId);
    if (select) select.style.display = "none";
    // Must match _updateBikeBadge's inline-flex: the ellipsis truncation
    // lives on the inner text span, and a span only picks it up while the
    // badge is a flex container. Restoring inline-block here would let a
    // long bike name spill over the ride title until the next _show().
    if (badge && badge.textContent) badge.style.display = "inline-flex";
  }

  _openBikeEditor(badgeId, selectId) {
    const activity = this._activities[this._idx];
    const badge = this._$(badgeId);
    const select = this._$(selectId);
    if (!activity || !badge || !select) return;
    const options = this._reassignOptionsFor(activity);
    if (options.length < 2) return;
    // When the ride's current bike is unknown, lead with a selected
    // placeholder so the first real bike is not silently shown as if it
    // were the current assignment. Its empty value is treated as "no
    // change" by _commitBikeAssignment.
    const known = options.some((b) => b.id === activity.bikeId);
    const opts = known ? [] : [`<option value="" selected>${this._escapeHtml(this._t("bike_unassigned"))}</option>`];
    for (const b of options) {
      opts.push(`<option value="${this._escapeHtml(b.id)}"${b.id === activity.bikeId ? " selected" : ""}>${this._escapeHtml(b.label)}</option>`);
    }
    select.innerHTML = opts.join("");
    badge.style.display = "none";
    select.style.display = "inline-block";
    select.focus();
  }

  async _commitBikeAssignment(bikeId, badgeId, selectId) {
    const activity = this._activities[this._idx];
    if (!activity || !bikeId || bikeId === activity.bikeId || !this._hass) {
      this._closeBikeEditor(badgeId, selectId);
      return;
    }
    try {
      await this._hass.callWS({
        type: "bosch_ebike/assign_activity",
        activity_id: activity.id,
        bike_id: bikeId,
        config_entry_id: activity.accountId,
      });
      // A manual assignment always beats the odometer heuristic backend
      // side (see merge_manual_overrides), so this optimistic local update
      // is guaranteed to match what the next poll reports. Updating in
      // place rather than refetching keeps the user on the ride they are
      // looking at. _activities holds the same objects as _allActivities
      // (_applyFilter only copies the array), so one write covers both.
      activity.bikeId = bikeId;
      this._show(this._idx, false);
    } catch (err) {
      console.warn("[Bosch eBike Map] assign_activity failed:", err?.message || err);
      this._closeBikeEditor(badgeId, selectId);
      alert(this._t("bike_reassign_failed", err?.message || err));
    }
  }

  async _show(index, forceTrackReload = true) {
    if (index < 0 || index >= this._activities.length) return;
    this._idx = index;
    const activity = this._activities[index];

    if (activity.startTime) {
      const dateValue = activity.startTime.substring(0, 10);
      this._$("eb-date").value = dateValue;
      const fullDate = this._$("eb-full-date");
      if (fullDate) fullDate.value = dateValue;
    }
    this._$("eb-ctr").textContent = `${index + 1} / ${this._activities.length}`;
    const fullCtr = this._$("eb-full-ctr");
    if (fullCtr) fullCtr.textContent = `${index + 1} / ${this._activities.length}`;
    this._$("eb-prev").disabled = index <= 0;
    this._$("eb-next").disabled = index >= this._activities.length - 1;
    const fullPrev = this._$("eb-full-prev");
    const fullNext = this._$("eb-full-next");
    if (fullPrev) fullPrev.disabled = index <= 0;
    if (fullNext) fullNext.disabled = index >= this._activities.length - 1;
    // Compact stats-area fallback navigator (issue #71): kept in sync the
    // same way as the main nav, even while hidden, so it is correct the
    // moment show_nav flips it visible.
    const statsCtr = this._$("eb-stats-ctr");
    if (statsCtr) statsCtr.textContent = `${index + 1} / ${this._activities.length}`;
    const statsPrev = this._$("eb-stats-prev");
    const statsNext = this._$("eb-stats-next");
    if (statsPrev) statsPrev.disabled = index <= 0;
    if (statsNext) statsNext.disabled = index >= this._activities.length - 1;
    const fsStatsCtr = this._$("eb-fullscreen-stats-ctr");
    if (fsStatsCtr) fsStatsCtr.textContent = `${index + 1} / ${this._activities.length}`;
    const fsStatsPrev = this._$("eb-fullscreen-stats-prev");
    const fsStatsNext = this._$("eb-fullscreen-stats-next");
    if (fsStatsPrev) fsStatsPrev.disabled = index <= 0;
    if (fsStatsNext) fsStatsNext.disabled = index >= this._activities.length - 1;
    const baseTitle = activity.title || this._t("msg_unnamed_ride");
    // Bosch's own ride titles are often generic (e.g. "Bike Fahrt"), so when
    // "All Bikes" is selected and there's more than one bike to tell apart,
    // show the specific bike's name as its own badge next to the title
    // (a separate element, not concatenated text, so a long bike name can't
    // push the actual ride title past the fullscreen title's own ellipsis
    // truncation - issue #65).
    // A ride whose bikeId is missing (heuristic never attributed it) or no
    // longer resolvable (assigned to a bike since removed from the account)
    // still gets a badge, labelled as unassigned. Otherwise it would render
    // no badge at all, which used to make it uneditable and therefore
    // permanently stuck on a wrong/dead bike - the exact dead end this
    // reassignment feature exists to remove.
    const showBikeLabel = this._filterBike === "all" && (this._bikeLabelById?.size || 0) > 1;
    const bikeLabel = showBikeLabel
      ? (this._bikeLabelById.get(activity.bikeId) || this._t("bike_unassigned"))
      : null;
    this._$("eb-title-text").textContent = baseTitle;
    this._updateBikeBadge("eb-bike-badge", "eb-bike-select", activity, bikeLabel);
    const trickDot = this._$("eb-trick-dot");
    trickDot.style.display = activity.trickHint ? "inline-block" : "none";
    trickDot.title = this._trickSummary(activity.trickCheck) || this._t("trick_hint_tooltip");

    if (activity.startTime) {
      this._$("eb-date-lbl").textContent = new Date(activity.startTime).toLocaleDateString(this._hassLocale(), {
        weekday: "long", year: "numeric", month: "long", day: "numeric", hour: "2-digit", minute: "2-digit"
      });
    } else {
      this._$("eb-date-lbl").textContent = "";
    }

    const dist = activity.distance ? (activity.distance / 1000).toFixed(1) : "–";
    const dur = activity.durationWithoutStops ? Math.round(activity.durationWithoutStops / 60) : "–";
    const avgS = activity.speed?.average != null ? activity.speed.average.toFixed(1) : "–";
    const maxS = activity.speed?.maximum != null ? activity.speed.maximum.toFixed(1) : "–";
    const ele = activity.elevation?.gain != null ? Math.round(activity.elevation.gain) : "–";
    const cal = activity.caloriesBurned != null ? Math.round(activity.caloriesBurned) : "–";

    // Difficulty: elevation gain per km
    const distKm = activity.distance ? activity.distance / 1000 : 0;
    const eleGain = activity.elevation?.gain ?? 0;
    const difficulty = distKm > 0 ? (eleGain / distKm).toFixed(1) : "–";

    // Battery consumption
    const cons = activity.consumption;
    const battWh = cons?.consumed_wh != null ? cons.consumed_wh.toFixed(1) : "–";
    const battPct = cons?.percentage != null ? cons.percentage.toFixed(1) : "–";

    const statsHtml = `
      <div class="eb-stat"><div class="eb-val">${dist} km</div><div class="eb-lbl">${this._t("stat_distance")}</div></div>
      <div class="eb-stat"><div class="eb-val">${dur} min</div><div class="eb-lbl">${this._t("stat_duration")}</div></div>
      <div class="eb-stat"><div class="eb-val">${avgS}</div><div class="eb-lbl">${this._t("stat_avg_kmh")}</div></div>
      <div class="eb-stat"><div class="eb-val">${maxS}</div><div class="eb-lbl">${this._t("stat_max_kmh")}</div></div>
      <div class="eb-stat"><div class="eb-val">${ele} m</div><div class="eb-lbl">${this._t("stat_elevation_up")}</div></div>
      <div class="eb-stat"><div class="eb-val">${cal} kcal</div><div class="eb-lbl">${this._t("stat_calories")}</div></div>
      <div class="eb-stat"><div class="eb-val">${difficulty} m/km</div><div class="eb-lbl">${this._t("stat_difficulty")}</div></div>
      <div class="eb-stat"><div class="eb-val">${battWh} Wh</div><div class="eb-lbl">${this._t("stat_battery")}</div></div>
      <div class="eb-stat"><div class="eb-val">${battPct} %</div><div class="eb-lbl">${this._t("stat_battery_pct")}</div></div>
      ${this._trickStatsHtml(activity.trickCheck)}
    `;
    this._$("eb-stats").innerHTML = statsHtml;
    this._$("eb-fullscreen-title-text").textContent = baseTitle;
    this._updateBikeBadge(
      "eb-fullscreen-bike-badge", "eb-fullscreen-bike-select", activity, bikeLabel);
    const fsTrickDot = this._$("eb-fullscreen-trick-dot");
    fsTrickDot.style.display = activity.trickHint ? "inline-block" : "none";
    fsTrickDot.title = trickDot.title;
    this._$("eb-fullscreen-meta").innerHTML = statsHtml;
    this._renderFullscreenProfile();

    if (forceTrackReload || this._currentTrackActivityId !== activity.id || !this._currentTrack.length) {
      this._destroyMap(true);
      if (this._fullscreenOpen) this._destroyFullscreenMap();
      await this._loadTrack(activity.id, activity.accountId);
    } else {
      this._scheduleActivation("show cached track");
    }
  }

  async _loadTrack(activityId, accountId) {
    const loadSeq = ++this._loadSeq;
    this._msg(this._t("msg_loading_route"));

    try {
      const params = { type: "bosch_ebike/get_track", activity_id: activityId };
      if (accountId) params.config_entry_id = accountId;
      const res = await this._hass.callWS(params);
      if (loadSeq < this._loadSeq) return;

      const pts = Array.isArray(res.track) ? res.track.filter((p) => Number.isFinite(p.lat) && Number.isFinite(p.lon)) : [];
      this._currentTrack = pts;
      this._currentTrackActivityId = activityId;
      this._appliedLoadSeq = loadSeq;
      this._inlineUserAdjustedView = false;
      this._fullscreenUserAdjustedView = false;
      this._needsInlineFit = true;
      this._needsFullscreenFit = true;

      // Switching rides (or reloading this one) always starts a fresh weather
      // fetch below when enabled - clear whatever the PREVIOUS ride left on
      // screen right away, before that fetch even starts, so a rainy ride's
      // veil/particles/flash never lingers over the new ride's map. Must run
      // before the `!pts.length` early-return below too, since that path
      // (and a missing startTime, a failed fetch, etc.) never reaches
      // _loadAndRenderWeather()/_applyWeatherLayers() at all.
      if (this._weatherEnabled) this._clearWeatherOverlay();

      this._destroyMap(true);
      if (this._fullscreenOpen) this._destroyFullscreenMap();

      if (!pts.length) {
        this._msg(this._t("msg_no_gps"));
        this._clearTrackLayers();
        this._renderFullscreenProfile();
        return;
      }

      this._renderFullscreenProfile();
      this._msg("");
      [0, 80, 220, 500].forEach((delay) => {
        this._setTimer(() => this._activateMap("track loaded"), delay);
      });
      if (this._fullscreenOpen) this._scheduleFullscreenSync("track loaded");
      if (this._wikiEnabled) {
        // Slight delay so the map is initialized before placing markers
        this._setTimer(() => this._loadAndRenderWiki(), 600);
      }
      if (this._poiEnabled) {
        this._setTimer(() => this._loadAndRenderPoi(), 700);
      }
      if (this._weatherEnabled) {
        this._setTimer(() => this._loadAndRenderWeather(), 800);
      }
    } catch (error) {
      if (loadSeq < this._loadSeq) return;
      console.error("[Bosch eBike Map] track load error", error);
      this._msg(this._t("msg_error_prefix") + (error?.message || error));
    }
  }

  _activateMap(reason = "") {
    if (!this._connected || !this._leafletReady || !this._currentTrack.length) return;
    if (!this._isContainerUsable()) return;

    const mapEl = this._$("eb-map");
    if (!mapEl) return;

    if (!this._map) {
      this._createMap();
    } else if (this._map.getContainer() !== mapEl || !mapEl.querySelector(".leaflet-pane")) {
      this._destroyMap(true);
      this._createMap();
    }

    if (!this._map) return;

    this._renderCurrentTrack();
    this._safeInvalidate();
    if (this._fullscreenOpen) this._scheduleFullscreenSync(reason || "activate");
  }

  _createMap() {
    const mapEl = this._$("eb-map");
    const Leaflet = window.L;
    if (!mapEl || !Leaflet || typeof Leaflet.map !== "function") {
      this._msg(this._t("msg_error_prefix") + this._t("err_leaflet_load"));
      return;
    }

    mapEl.innerHTML = "";

    try {
      this._map = Leaflet.map(mapEl, {
        zoomControl: true,
        attributionControl: false,
        preferCanvas: true,
        zoomAnimation: true,
        fadeAnimation: true,
        markerZoomAnimation: true,
      }).setView([48.7, 12.4], 10);

      this._applyBaseLayer(this._map, "inline", true);

      this._trackGroup = Leaflet.layerGroup().addTo(this._map);
      this._bindMapInteractionState(this._map, "inline");
    } catch (error) {
      console.error("[Bosch eBike Map] map create error", error);
      this._destroyMap(true);
      this._msg(this._t("err_create_map"));
    }
  }


  _styleDef(styleKey = this._mapStyle) {
    return MAP_STYLES[styleKey] || MAP_STYLES.osm;
  }

  _updateStyleButtons() {
    const label = this._styleDef().label;
    const inlineBtn = this._$("eb-style");
    const fullBtn = this._$("eb-full-style");
    if (inlineBtn) inlineBtn.textContent = label;
    if (fullBtn) fullBtn.textContent = label;
  }

  _makeBaseLayer(Leaflet, styleKey = this._mapStyle) {
    const def = this._styleDef(styleKey);
    return Leaflet.tileLayer(def.url, def.options);
  }

  _applyBaseLayer(targetMap, kind = "inline", force = false) {
    const Leaflet = window.L;
    if (!Leaflet || !targetMap) return;

    const prop = kind === "fullscreen" ? "_fullscreenBaseLayer" : "_inlineBaseLayer";
    const current = this[prop];
    if (current && !force) return;

    if (current) {
      try { targetMap.removeLayer(current); } catch (_) {}
      this[prop] = null;
    }

    const layer = this._makeBaseLayer(Leaflet, this._mapStyle);
    layer.addTo(targetMap);
    this[prop] = layer;
  }

  _cycleMapStyle() {
    const keys = Object.keys(MAP_STYLES);
    const index = keys.indexOf(this._mapStyle);
    const next = keys[(index + 1) % keys.length];
    this._setMapStyle(next);
  }

  _setMapStyle(styleKey) {
    if (!MAP_STYLES[styleKey] || this._mapStyle === styleKey) return;
    this._mapStyle = styleKey;
    this._updateStyleButtons();

    if (this._map) this._applyBaseLayer(this._map, "inline", true);
    if (this._fullscreenMap) this._applyBaseLayer(this._fullscreenMap, "fullscreen", true);

    this._setTimer(() => this._safeInvalidate(), 0);
    if (this._fullscreenOpen) this._scheduleFullscreenSync("style change");
  }


  _bindMapInteractionState(map, kind = "inline") {
    if (!map || map._boschInteractionBound) return;

    const markAdjusted = () => {
      if (kind === "fullscreen") {
        this._fullscreenUserAdjustedView = true;
        this._needsFullscreenFit = false;
      } else {
        this._inlineUserAdjustedView = true;
        this._needsInlineFit = false;
      }
    };

    map.on("zoomstart", markAdjusted);
    map.on("dragstart", markAdjusted);
    map.on("movestart", (ev) => {
      if (ev?.originalEvent) markAdjusted();
    });
    map._boschInteractionBound = true;
  }

  _destroyMap(keepContainer = true) {
    try {
      if (this._legend && this._map) {
        this._map.removeControl(this._legend);
      }
    } catch (_) {}
    this._legend = null;

    try {
      if (this._map) {
        this._map.remove();
      }
    } catch (_) {}

    this._map = null;
    this._trackGroup = null;
    this._wikiGroup = null;
    this._wikiRenderedInline = null;
    this._poiGroup = null;
    this._poiRenderedInline = null;
    this._inlineBaseLayer = null;

    const mapEl = this._$("eb-map");
    if (!keepContainer && mapEl) mapEl.innerHTML = "";
  }

  _destroyFullscreenMap() {
    try {
      if (this._fullscreenLegend && this._fullscreenMap) {
        this._fullscreenMap.removeControl(this._fullscreenLegend);
      }
    } catch (_) {}
    this._fullscreenLegend = null;

    try {
      if (this._fullscreenMap) {
        this._fullscreenMap.remove();
      }
    } catch (_) {}

    this._fullscreenMap = null;
    this._fullscreenTrackGroup = null;
    this._fullscreenWikiGroup = null;
    this._wikiRenderedFullscreen = null;
    this._fullscreenPoiGroup = null;
    this._poiRenderedFullscreen = null;
    this._fullscreenBaseLayer = null;

    const mapEl = this._$("eb-fullscreen-map");
    if (mapEl) mapEl.innerHTML = "";
  }

  // -- Wikipedia overlay --

  _updateWikiButtons() {
    const inlineBtn = this._$("eb-wiki");
    const fullBtn = this._$("eb-full-wiki");
    if (inlineBtn) inlineBtn.classList.toggle("eb-active", this._wikiEnabled);
    if (fullBtn) fullBtn.classList.toggle("eb-active", this._wikiEnabled);
  }

  _toggleWikipedia() {
    this._wikiEnabled = !this._wikiEnabled;
    try { localStorage.setItem("eb-wiki-enabled", this._wikiEnabled ? "1" : "0"); } catch (_) {}
    this._updateWikiButtons();

    if (this._wikiEnabled) {
      this._loadAndRenderWiki();
    } else {
      this._clearWikiLayers();
    }
  }

  _clearWikiLayers() {
    if (this._wikiGroup) {
      try { this._wikiGroup.clearLayers(); } catch (_) {}
    }
    if (this._fullscreenWikiGroup) {
      try { this._fullscreenWikiGroup.clearLayers(); } catch (_) {}
    }
    this._wikiRenderedInline = null;
    this._wikiRenderedFullscreen = null;
  }

  /// Wikipedia language code based on HA locale, fallback en
  _wikiLanguage() {
    const locale = (this._hass && this._hass.locale && this._hass.locale.language) || "en";
    return String(locale).slice(0, 2).toLowerCase() || "en";
  }

  /// BCP-47 locale tag for Intl/toLocale* date formatting. Try to honor
  /// HA's configured locale; fall back to browser default. Mirrors the
  /// same _hassLocale() pattern already used by the Calendar and Trick
  /// List cards, so date formatting is consistent across all cards.
  _hassLocale() {
    if (this._hass && this._hass.locale && this._hass.locale.language) {
      return this._hass.locale.language;
    }
    return (this._hass && this._hass.language) || navigator.language || "en-GB";
  }

  /// Subsample the route every ~2 km along the actual driven distance.
  _wikiSamplePoints(track) {
    if (!Array.isArray(track) || track.length < 2) return [];
    const pts = [];
    let lastSampleDist = -Infinity;
    let cumKm = 0;
    pts.push({ lat: track[0].lat, lon: track[0].lon });
    lastSampleDist = 0;
    for (let i = 1; i < track.length; i += 1) {
      cumKm += this._distanceMeters(track[i - 1], track[i]) / 1000;
      if (cumKm - lastSampleDist >= 2) {
        pts.push({ lat: track[i].lat, lon: track[i].lon });
        lastSampleDist = cumKm;
      }
    }
    // Always include the last point as well
    const last = track[track.length - 1];
    pts.push({ lat: last.lat, lon: last.lon });
    return pts;
  }

  async _loadAndRenderWiki() {
    if (!this._currentTrackActivityId || !this._currentTrack.length) return;
    const aid = this._currentTrackActivityId;
    // Cache is keyed by activity AND radius so different radii don't collide
    const cacheKey = `eb-wiki-${aid}-${this._wikiRadius}`;

    // From cache? Empty arrays from older versions or transient failures are
    // ignored so navigating between tours always re-tries when nothing was
    // found before — matches the POI handling in _loadAndRenderPoi.
    let articles = this._wikiArticles.get(aid);
    if (!articles || articles.length === 0) {
      try {
        const cached = localStorage.getItem(cacheKey);
        if (cached) {
          const parsed = JSON.parse(cached);
          if (Array.isArray(parsed) && parsed.length > 0) {
            articles = parsed;
            this._wikiArticles.set(aid, parsed);
          }
        }
      } catch (_) {}
    }

    if (!articles || articles.length === 0) {
      if (this._wikiLoading.has(aid)) return;
      this._wikiLoading.add(aid);
      try {
        articles = await this._fetchWikiArticles(this._currentTrack);
        this._wikiArticles.set(aid, articles);
        if (articles.length > 0) {
          try { localStorage.setItem(cacheKey, JSON.stringify(articles)); } catch (_) {}
        }
      } catch (err) {
        console.warn("[Bosch eBike Wiki] fetch failed", err);
        articles = [];
      } finally {
        this._wikiLoading.delete(aid);
      }
    }

    this._renderWikiMarkers(articles);
  }

  async _fetchWikiArticles(track) {
    const samples = this._wikiSamplePoints(track);
    if (!samples.length) return [];
    const lang = this._wikiLanguage();
    const seen = new Map(); // pageId → article

    // Process in batches of 5 with a small pause between batches
    const BATCH_SIZE = 5;
    for (let i = 0; i < samples.length; i += BATCH_SIZE) {
      const batch = samples.slice(i, i + BATCH_SIZE);
      const results = await Promise.all(
        batch.map((p) => this._geosearchOnce(lang, p.lat, p.lon))
      );
      for (const list of results) {
        for (const art of list) {
          if (!seen.has(art.pageId)) seen.set(art.pageId, art);
        }
      }
      if (i + BATCH_SIZE < samples.length) {
        await new Promise((r) => setTimeout(r, 100));
      }
    }

    let arr = Array.from(seen.values());
    // Cap at 30 markers — keep the closest to any sample point
    if (arr.length > 30) {
      arr.sort((a, b) => (a.dist || 0) - (b.dist || 0));
      arr = arr.slice(0, 30);
    }
    return arr;
  }

  async _geosearchOnce(lang, lat, lon) {
    const url = new URL(`https://${lang}.wikipedia.org/w/api.php`);
    url.searchParams.set("action", "query");
    url.searchParams.set("list", "geosearch");
    url.searchParams.set("gscoord", `${lat}|${lon}`);
    url.searchParams.set("gsradius", String(this._wikiRadius || 1000));
    url.searchParams.set("gslimit", "10");
    url.searchParams.set("format", "json");
    url.searchParams.set("origin", "*");
    try {
      const resp = await fetch(url.toString());
      if (!resp.ok) return [];
      const data = await resp.json();
      const list = (data && data.query && data.query.geosearch) || [];
      return list.map((a) => ({
        pageId: a.pageid,
        title: a.title,
        lat: a.lat,
        lon: a.lon,
        dist: a.dist,
        lang,
      }));
    } catch (_) {
      return [];
    }
  }

  async _fetchWikiSummary(pageId, title, lang) {
    if (this._wikiSummaries.has(pageId)) return this._wikiSummaries.get(pageId);
    const url = `https://${lang}.wikipedia.org/api/rest_v1/page/summary/${encodeURIComponent(title)}?redirect=true`;
    try {
      const resp = await fetch(url, { headers: { Accept: "application/json" } });
      if (!resp.ok) return null;
      const data = await resp.json();
      const summary = {
        extract: data.extract || "",
        thumbnail: data.thumbnail && data.thumbnail.source ? data.thumbnail.source : null,
        link: (data.content_urls && data.content_urls.desktop && data.content_urls.desktop.page)
          || `https://${lang}.wikipedia.org/wiki/${encodeURIComponent(title)}`,
      };
      this._wikiSummaries.set(pageId, summary);
      return summary;
    } catch (_) {
      return null;
    }
  }

  _renderWikiMarkers(articles) {
    if (!this._wikiEnabled) return;
    const Leaflet = window.L;
    if (!Leaflet) return;
    const aid = this._currentTrackActivityId;

    const popupOpts = {
      maxWidth: 300,
      closeOnClick: false,  // don't close when clicking on the map
      autoClose: false,     // don't close when another popup opens
    };

    const renderTo = (map, groupRefName, renderedRefName) => {
      if (!map) return;
      // Already rendered for this activity → keep markers (and any open popup) alive
      if (this[renderedRefName] === aid && this[groupRefName]) return;

      let group = this[groupRefName];
      if (!group) {
        group = Leaflet.layerGroup().addTo(map);
        this[groupRefName] = group;
      }
      group.clearLayers();
      for (const art of articles) {
        if (!Number.isFinite(art.lat) || !Number.isFinite(art.lon)) continue;
        const icon = Leaflet.divIcon({
          className: "",
          html: '<div class="eb-wiki-marker">i</div>',
          iconSize: [14, 14],
          iconAnchor: [7, 7],
        });
        const marker = Leaflet.marker([art.lat, art.lon], { icon, title: art.title });
        marker.bindPopup(this._wikiPopupHtml(art, true), popupOpts);
        marker.on("popupopen", async () => {
          const summary = await this._fetchWikiSummary(art.pageId, art.title, art.lang);
          marker.setPopupContent(this._wikiPopupHtml(art, false, summary));
        });
        marker.addTo(group);
      }
      this[renderedRefName] = aid;
    };

    renderTo(this._map, "_wikiGroup", "_wikiRenderedInline");
    renderTo(this._fullscreenMap, "_fullscreenWikiGroup", "_wikiRenderedFullscreen");
  }

  // -- POI overlay (Overpass) --

  _updatePoiButtons() {
    const inlineBtn = this._$("eb-poi");
    const fullBtn = this._$("eb-full-poi");
    if (inlineBtn) inlineBtn.classList.toggle("eb-active", this._poiEnabled);
    if (fullBtn) fullBtn.classList.toggle("eb-active", this._poiEnabled);
  }

  _togglePoi() {
    this._poiEnabled = !this._poiEnabled;
    try { localStorage.setItem("eb-poi-enabled", this._poiEnabled ? "1" : "0"); } catch (_) {}
    this._updatePoiButtons();
    if (this._poiEnabled) {
      this._loadAndRenderPoi();
    } else {
      this._clearPoiLayers();
    }
  }

  // -- Weather overlay (opt-in, mirrors the Wiki/POI toggle pattern) --

  _updateWeatherButtons() {
    const inlineBtn = this._$("eb-weather");
    const fullBtn = this._$("eb-full-weather");
    if (inlineBtn) inlineBtn.classList.toggle("eb-active", this._weatherEnabled);
    if (fullBtn) fullBtn.classList.toggle("eb-active", this._weatherEnabled);
  }

  _toggleWeather() {
    this._weatherEnabled = !this._weatherEnabled;
    try { localStorage.setItem("eb-weather-enabled", this._weatherEnabled ? "1" : "0"); } catch (_) {}
    this._updateWeatherButtons();
    if (this._weatherEnabled) {
      this._loadAndRenderWeather();
    } else {
      this._clearWeatherOverlay();
    }
  }

  // Fetches (or reuses cached) weather for the ride's start time/location,
  // interpolates the sample at startTime, and applies the resolved layers to
  // both overlays. Mirrors _loadAndRenderWiki()'s in-memory → localStorage →
  // network cache cascade exactly.
  async _loadAndRenderWeather() {
    if (!this._currentTrackActivityId || !this._currentTrack.length) return;
    const aid = this._currentTrackActivityId;
    const activity = this._activities.find((a) => a.id === aid);
    if (!activity?.startTime) return;
    // Captured once, up front - a forced reload of this same activity's track
    // while its weather fetch is still in flight could otherwise leave
    // this._currentTrack[0] undefined by the time we read it again below.
    const startPoint = this._currentTrack[0];

    let weather = this._weatherData.get(aid);
    if (!weather) {
      const cacheKey = `eb-weather-${aid}`;
      try {
        const cached = localStorage.getItem(cacheKey);
        if (cached) weather = JSON.parse(cached);
      } catch (_) {}
    }
    if (!weather) {
      if (this._weatherLoading.has(aid)) return;
      this._weatherLoading.add(aid);
      try {
        const hourly = await fetchHistoricalWeather(startPoint.lat, startPoint.lon, activity.startTime, activity.startTime);
        const sample = interpolateWeatherAt(hourly, new Date(activity.startTime));
        if (!sample) return;
        weather = sample;
        this._weatherData.set(aid, weather);
        try { localStorage.setItem(`eb-weather-${aid}`, JSON.stringify(weather)); } catch (_) {}
      } catch (err) {
        console.warn("[Bosch eBike Map] weather fetch failed", err);
        return; // fail open - no overlay, no error surfaced to the user
      } finally {
        this._weatherLoading.delete(aid);
      }
    }
    // user navigated away while fetching, or toggled weather off before this resolved
    if (this._currentTrackActivityId !== aid || !this._weatherEnabled) return;
    const alt = sunPositionAt(new Date(activity.startTime), startPoint.lat, startPoint.lon).altitude * 180 / Math.PI;
    const layers = weatherLayers(weather.cloud, weather.precip, weather.snow, weather.code, alt);
    _applyWeatherLayers(this._$("eb-wx-overlay"), layers);
    const fullOverlay = this._$("eb-full-wx-overlay");
    if (fullOverlay) _applyWeatherLayers(fullOverlay, layers);
  }

  // Hides both weather overlays and stops any running particle/flash loops -
  // called on toggle-off and from disconnectedCallback().
  _clearWeatherOverlay() {
    const overlays = [this._$("eb-wx-overlay"), this._$("eb-full-wx-overlay")];
    for (const overlayEl of overlays) {
      if (!overlayEl) continue;
      overlayEl.style.display = "none";
      _wxStopCanvas(overlayEl.querySelector(".eb-wx-canvas"));
      _wxStopFlash(overlayEl.querySelector(".eb-wx-flash"));
    }
  }

  _clearPoiLayers() {
    if (this._poiGroup) {
      try { this._poiGroup.clearLayers(); } catch (_) {}
    }
    if (this._fullscreenPoiGroup) {
      try { this._fullscreenPoiGroup.clearLayers(); } catch (_) {}
    }
    this._poiRenderedInline = null;
    this._poiRenderedFullscreen = null;
  }

  /// Bounding box around the route; clamped to a sensible buffer.
  _routeBoundingBox(track) {
    let minLat = Infinity, maxLat = -Infinity, minLon = Infinity, maxLon = -Infinity;
    for (const p of track) {
      if (!Number.isFinite(p.lat) || !Number.isFinite(p.lon)) continue;
      if (p.lat < minLat) minLat = p.lat;
      if (p.lat > maxLat) maxLat = p.lat;
      if (p.lon < minLon) minLon = p.lon;
      if (p.lon > maxLon) maxLon = p.lon;
    }
    if (!Number.isFinite(minLat)) return null;
    return { minLat, maxLat, minLon, maxLon };
  }

  _setPoiLoadingUI(loading) {
    for (const id of ["eb-poi", "eb-full-poi"]) {
      const btn = this._$(id);
      if (btn) {
        btn.classList.toggle("eb-loading", !!loading);
        btn.disabled = !!loading;
      }
    }
  }

  async _loadAndRenderPoi() {
    if (!this._currentTrackActivityId || !this._currentTrack.length) return;
    const aid = this._currentTrackActivityId;
    // Cache key includes the radius so different radii don't collide, and
    // the category list so adding a category invalidates stale cached results
    // (pre-gastronomy caches would otherwise hide the new POIs).
    const cacheKey = `eb-poi-${aid}-${this._poiRadius || 1000}-${RP_POI_CATEGORIES.join(",")}`;

    let pois = this._poiData.get(aid);
    if (!pois || pois.length === 0) {
      // In-memory cache empty → check localStorage but only honour non-empty cached results
      try {
        const cached = localStorage.getItem(cacheKey);
        if (cached) {
          const parsed = JSON.parse(cached);
          if (Array.isArray(parsed) && parsed.length > 0) {
            pois = parsed;
            this._poiData.set(aid, parsed);
          }
        }
      } catch (_) {}
    }

    if (!pois || pois.length === 0) {
      if (this._poiLoading.has(aid)) return;
      this._poiLoading.add(aid);
      this._setPoiLoadingUI(true);
      try {
        pois = await this._fetchPois(this._currentTrack);
        this._poiData.set(aid, pois);
        // Only persist NON-EMPTY results — otherwise a transient Overpass
        // error would poison the cache and hide POIs forever.
        if (pois.length > 0) {
          try { localStorage.setItem(cacheKey, JSON.stringify(pois)); } catch (_) {}
        }
      } catch (err) {
        console.warn("[Bosch eBike POI] fetch failed", err);
        pois = [];
      } finally {
        this._poiLoading.delete(aid);
        this._setPoiLoadingUI(false);
      }
    }

    this._renderPoiMarkers(pois);
  }

  async _fetchPois(track) {
    const bbox = this._routeBoundingBox(track);
    if (!bbox) return [];
    // Bbox padding scales with the configured proximity radius (in degrees, ~111 km/°)
    const radiusM = this._poiRadius || 1000;
    const pad = radiusM / 111000 + 0.001;
    const south = bbox.minLat - pad;
    const north = bbox.maxLat + pad;
    const west = bbox.minLon - pad;
    const east = bbox.maxLon + pad;

    // Route the Overpass query through the HA backend (avoids CORS issues
    // that overpass-api.de's tightened policy causes for browser requests).
    let elements = [];
    try {
      const res = await this._hass.callWS({
        type: "bosch_ebike/get_pois",
        south, west, north, east,
        categories: RP_POI_CATEGORIES,
      });
      elements = (res && Array.isArray(res.elements)) ? res.elements : [];
    } catch (err) {
      console.warn("[Bosch eBike POI] backend Overpass call failed:", err);
      return [];
    }

    if (!elements.length) {
      console.info("[Bosch eBike POI] Overpass returned no POIs in route bbox", bbox);
    }
    // Sample track points every ~radius/2 so the proximity filter has no gaps
    const MAX_DIST_M = radiusM;
    const sampled = this._poiSamplePoints(track, MAX_DIST_M / 2);

    const out = [];
    for (const el of elements) {
      if (typeof el.lat !== "number" || typeof el.lon !== "number") continue;
      // Only keep POIs within MAX_DIST_M of any sampled track point
      let near = false;
      for (const sp of sampled) {
        if (this._haversineMeters(el.lat, el.lon, sp.lat, sp.lon) <= MAX_DIST_M) {
          near = true; break;
        }
      }
      if (!near) continue;
      const tags = el.tags || {};
      const cat = this._poiCategory(tags);
      if (!cat) continue;
      out.push({
        lat: el.lat,
        lon: el.lon,
        category: cat.key,
        catLabel: cat.label,
        catIcon: cat.icon,
        name: tags.name || cat.label,
        osmId: el.id,
        tags,
      });
    }
    // Cap at 100 markers to avoid clutter
    return out.slice(0, 100);
  }

  _poiCategory(tags) {
    if (tags.amenity === "charging_station") {
      return { key: "charging", label: this._t("poi_charging"), icon: "🔌" };
    }
    if (tags.shop === "bicycle") {
      return { key: "bicycle", label: this._t("poi_bicycle_shop"), icon: "🛠️" };
    }
    if (tags.amenity === "bicycle_repair_station") {
      return { key: "bicycle", label: this._t("poi_repair"), icon: "🛠️" };
    }
    if (tags.amenity === "drinking_water") {
      return { key: "water", label: this._t("poi_water"), icon: "💧" };
    }
    if (tags.amenity === "toilets") {
      return { key: "toilet", label: this._t("poi_toilet"), icon: "🚻" };
    }
    if (tags.amenity === "restaurant" || tags.amenity === "fast_food") {
      return { key: "food", label: this._t("poi_food"), icon: "🍽️" };
    }
    if (tags.amenity === "cafe") {
      return { key: "cafe", label: this._t("poi_cafe"), icon: "☕" };
    }
    if (tags.amenity === "biergarten") {
      return { key: "biergarten", label: this._t("poi_biergarten"), icon: "🍺" };
    }
    return null;
  }

  /// Sample points every `intervalM` metres along the actual driven distance.
  /// Default 250 m; caller passes radius/2 so the proximity filter has no gaps
  /// even when the route makes sharp turns.
  _poiSamplePoints(track, intervalM = 250) {
    if (!Array.isArray(track) || track.length < 2) return [];
    const intervalKm = Math.max(0.05, intervalM / 1000);
    const pts = [];
    pts.push({ lat: track[0].lat, lon: track[0].lon });
    let cumKm = 0;
    let lastSampled = 0;
    for (let i = 1; i < track.length; i += 1) {
      cumKm += this._distanceMeters(track[i - 1], track[i]) / 1000;
      if (cumKm - lastSampled >= intervalKm) {
        pts.push({ lat: track[i].lat, lon: track[i].lon });
        lastSampled = cumKm;
      }
    }
    const last = track[track.length - 1];
    pts.push({ lat: last.lat, lon: last.lon });
    return pts;
  }

  _haversineMeters(lat1, lon1, lat2, lon2) {
    const R = 6371000;
    const toRad = (d) => d * Math.PI / 180;
    const dLat = toRad(lat2 - lat1);
    const dLon = toRad(lon2 - lon1);
    const a = Math.sin(dLat / 2) ** 2
      + Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon / 2) ** 2;
    return 2 * R * Math.asin(Math.sqrt(a));
  }

  _renderPoiMarkers(pois) {
    if (!this._poiEnabled) return;
    const Leaflet = window.L;
    if (!Leaflet) return;
    const aid = this._currentTrackActivityId;

    const popupOpts = { maxWidth: 260, closeOnClick: false, autoClose: false };

    const renderTo = (map, groupRefName, renderedRefName) => {
      if (!map) return;
      if (this[renderedRefName] === aid && this[groupRefName]) return;
      let group = this[groupRefName];
      if (!group) {
        group = Leaflet.layerGroup().addTo(map);
        this[groupRefName] = group;
      }
      group.clearLayers();
      for (const poi of pois) {
        const icon = Leaflet.divIcon({
          className: "",
          html: `<div class="eb-poi-marker eb-poi-${poi.category}">${poi.catIcon}</div>`,
          iconSize: [18, 18],
          iconAnchor: [9, 9],
        });
        const marker = Leaflet.marker([poi.lat, poi.lon], { icon, title: `${poi.catIcon} ${poi.name}` });
        marker.bindPopup(this._poiPopupHtml(poi), popupOpts);
        marker.addTo(group);
      }
      this[renderedRefName] = aid;
    };

    renderTo(this._map, "_poiGroup", "_poiRenderedInline");
    renderTo(this._fullscreenMap, "_fullscreenPoiGroup", "_poiRenderedFullscreen");
  }

  _poiPopupHtml(poi) {
    const safeName = this._escapeHtml(poi.name);
    const osmUrl = `https://www.openstreetmap.org/node/${poi.osmId}`;
    let extra = "";
    if (poi.tags.opening_hours) {
      extra += `<div>🕒 ${this._escapeHtml(poi.tags.opening_hours)}</div>`;
    }
    if (poi.tags["addr:street"]) {
      const addr = [poi.tags["addr:street"], poi.tags["addr:housenumber"]].filter(Boolean).join(" ");
      extra += `<div>📍 ${this._escapeHtml(addr)}</div>`;
    }
    if (poi.tags.website) {
      const url = poi.tags.website.startsWith("http") ? poi.tags.website : "https://" + poi.tags.website;
      extra += `<div>🌐 <a href="${this._escapeHtml(url)}" target="_blank" rel="noopener">${this._t("poi_website_link")}</a></div>`;
    }
    return `<div class="eb-poi-popup">
      <div class="eb-poi-title">${poi.catIcon} ${safeName}</div>
      <div class="eb-poi-cat">${this._escapeHtml(poi.catLabel)}</div>
      ${extra}
      <a class="eb-poi-link" href="${osmUrl}" target="_blank" rel="noopener noreferrer">${this._t("poi_open_osm")}</a>
    </div>`;
  }

  _wikiPopupHtml(article, loading, summary = null) {
    const safeTitle = this._escapeHtml(article.title);
    if (loading) {
      return `<div class="eb-wiki-popup">
        <div class="eb-wiki-title">${safeTitle}</div>
        <div class="eb-wiki-loading">${this._t("wiki_loading_preview")}</div>
      </div>`;
    }
    if (!summary) {
      const fallbackUrl = `https://${article.lang}.wikipedia.org/wiki/${encodeURIComponent(article.title)}`;
      return `<div class="eb-wiki-popup">
        <div class="eb-wiki-title">${safeTitle}</div>
        <div class="eb-wiki-extract">${this._t("wiki_no_preview")}</div>
        <a class="eb-wiki-link" href="${fallbackUrl}" target="_blank" rel="noopener noreferrer">${this._t("wiki_open_link")}</a>
      </div>`;
    }
    const thumb = summary.thumbnail
      ? `<img class="eb-wiki-thumb" src="${summary.thumbnail}" alt="">` : "";
    const extract = this._escapeHtml(summary.extract || "");
    return `<div class="eb-wiki-popup">
      <div class="eb-wiki-title">${safeTitle}</div>
      ${thumb}
      <div class="eb-wiki-extract">${extract}</div>
      <a class="eb-wiki-link" href="${summary.link}" target="_blank" rel="noopener noreferrer">${this._t("wiki_open_link")}</a>
    </div>`;
  }

  _clearTrackLayers() {
    if (this._trackGroup) this._trackGroup.clearLayers();
    if (this._legend && this._map) {
      try { this._map.removeControl(this._legend); } catch (_) {}
    }
    this._legend = null;
  }

  _renderCurrentTrack() {
    if (!this._map || !this._trackGroup || !this._currentTrack.length) return;
    this._renderTrackToMap(this._map, this._trackGroup, {
      padding: [40, 40],
      legend: "inline",
      fit: this._needsInlineFit && !this._inlineUserAdjustedView,
    });
    this._needsInlineFit = false;
    this._msg("");

    // Restore Wikipedia markers from cache if active
    if (this._wikiEnabled) {
      const cached = this._wikiArticles.get(this._currentTrackActivityId);
      if (cached) this._renderWikiMarkers(cached);
    }
    // Restore POI markers from cache if active
    if (this._poiEnabled) {
      const cached = this._poiData.get(this._currentTrackActivityId);
      if (cached) this._renderPoiMarkers(cached);
    }
  }

  _renderTrackToMap(targetMap, targetGroup, { padding = [40, 40], legend = "inline", fit = false } = {}) {
    const Leaflet = window.L;
    if (!targetMap || !targetGroup || !Leaflet || !this._currentTrack.length) return;

    targetGroup.clearLayers();
    const pts = this._currentTrack;

    for (let i = 0; i < pts.length - 1; i += 1) {
      const speed = pts[i].speed || 0;
      Leaflet.polyline(
        [[pts[i].lat, pts[i].lon], [pts[i + 1].lat, pts[i + 1].lon]],
        { color: this._color(speed), weight: 5, opacity: 0.9, lineCap: "round" }
      ).addTo(targetGroup);
    }

    Leaflet.circleMarker([pts[0].lat, pts[0].lon], {
      radius: 8, fillColor: "#4CAF50", color: "#fff", weight: 3, fillOpacity: 1,
    }).bindTooltip("Start").addTo(targetGroup);

    const last = pts[pts.length - 1];
    Leaflet.circleMarker([last.lat, last.lon], {
      radius: 8, fillColor: "#f44336", color: "#fff", weight: 3, fillOpacity: 1,
    }).bindTooltip("Ziel").addTo(targetGroup);

    if (fit) this._fitMapToTrack(targetMap, pts, padding);
    this._addLegend(targetMap, legend);
  }

  _fitMapToTrack(targetMap, pts = this._currentTrack, padding = [40, 40]) {
    const Leaflet = window.L;
    if (!targetMap || !Leaflet || !pts?.length) return;
    const bounds = Leaflet.latLngBounds(pts.map((p) => [p.lat, p.lon]));
    try {
      targetMap.fitBounds(bounds, { padding, animate: false });
    } catch (_) {}
  }

  _safeInvalidate() {
    if (!this._map || !this._isContainerUsable()) return;
    try {
      this._map.invalidateSize({ pan: false, animate: false });
    } catch (_) {}
  }

  _color(kmh) {
    if (kmh <= 5) return "#2196F3";
    if (kmh <= 12) return "#4CAF50";
    if (kmh <= 20) return "#8BC34A";
    if (kmh <= 27) return "#FFC107";
    if (kmh <= 33) return "#FF9800";
    return "#f44336";
  }

  _addLegend(targetMap = this._map, kind = "inline") {
    const Leaflet = window.L;
    if (!targetMap || !Leaflet) return;

    if (kind === "fullscreen") {
      if (this._fullscreenLegend) {
        try { this._fullscreenMap.removeControl(this._fullscreenLegend); } catch (_) {}
      }
    } else if (this._legend) {
      try { this._map.removeControl(this._legend); } catch (_) {}
    }

    const speedLabel = this._t("speed_legend");
    const Legend = Leaflet.Control.extend({
      options: { position: "bottomright" },
      onAdd() {
        const div = Leaflet.DomUtil.create("div");
        div.style.cssText = "background:rgba(255,255,255,.92);padding:6px 10px;border-radius:6px;font-size:11px;box-shadow:0 1px 5px rgba(0,0,0,.25);line-height:1.6";
        div.innerHTML =
          `<b>${speedLabel}</b><br>` +
          '<i style="background:#2196F3;width:14px;height:3px;display:inline-block;border-radius:2px;vertical-align:middle"></i> 0 ' +
          '<i style="background:#4CAF50;width:14px;height:3px;display:inline-block;border-radius:2px;vertical-align:middle"></i> 12 ' +
          '<i style="background:#FFC107;width:14px;height:3px;display:inline-block;border-radius:2px;vertical-align:middle"></i> 25 ' +
          '<i style="background:#f44336;width:14px;height:3px;display:inline-block;border-radius:2px;vertical-align:middle"></i> 35+ km/h';
        return div;
      }
    });

    const legend = new Legend();
    targetMap.addControl(legend);
    if (kind === "fullscreen") this._fullscreenLegend = legend;
    else this._legend = legend;
  }



  _pointElevation(point) {
    const v = Number.isFinite(point?.ele) ? point.ele
      : Number.isFinite(point?.alt) ? point.alt
      : Number.isFinite(point?.altitude) ? point.altitude
      : null;
    return Number.isFinite(v) ? v : null;
  }

  _distanceMeters(a, b) {
    if (!a || !b) return 0;
    const R = 6371000;
    const toRad = (deg) => (deg * Math.PI) / 180;
    const dLat = toRad((b.lat || 0) - (a.lat || 0));
    const dLon = toRad((b.lon || 0) - (a.lon || 0));
    const lat1 = toRad(a.lat || 0);
    const lat2 = toRad(b.lat || 0);
    const sinLat = Math.sin(dLat / 2);
    const sinLon = Math.sin(dLon / 2);
    const x = sinLat * sinLat + Math.cos(lat1) * Math.cos(lat2) * sinLon * sinLon;
    return 2 * R * Math.atan2(Math.sqrt(x), Math.sqrt(1 - x));
  }

  _buildElevationProfileData() {
    const pts = Array.isArray(this._currentTrack) ? this._currentTrack : [];
    if (pts.length < 2) return null;

    const pointDistancesKm = [];
    const rawElevations = [];
    const rawCadences = [];
    const rawPowers = [];
    let cumulative = 0;

    for (let i = 0; i < pts.length; i += 1) {
      if (i > 0) cumulative += this._distanceMeters(pts[i - 1], pts[i]);
      pointDistancesKm.push(cumulative / 1000);
      rawElevations.push(this._pointElevation(pts[i]));
      const c = pts[i].cadence;
      rawCadences.push(Number.isFinite(c) ? c : null);
      const p = pts[i].power;
      rawPowers.push(Number.isFinite(p) ? p : null);
    }

    const validEntries = rawElevations
      .map((ele, idx) => ({ ele, idx }))
      .filter(({ ele }) => Number.isFinite(ele));

    if (!validEntries.length) return null;

    const firstPositiveEntry = validEntries.find(({ ele }) => ele > 0);
    const startIdx = firstPositiveEntry ? firstPositiveEntry.idx : validEntries[0].idx;

    const trimmedDistancesKm = pointDistancesKm.slice(startIdx);
    const trimmedElevations = rawElevations.slice(startIdx);
    const trimmedCadences = rawCadences.slice(startIdx);
    const trimmedPowers = rawPowers.slice(startIdx);
    if (trimmedDistancesKm.length < 2 || trimmedElevations.length < 2) return null;

    const distanceOffsetKm = trimmedDistancesKm[0] || 0;
    const normalizedDistancesKm = trimmedDistancesKm.map((d) => Math.max(0, d - distanceOffsetKm));

    const validTrimmedElevations = trimmedElevations.filter((v) => Number.isFinite(v));
    if (!validTrimmedElevations.length) return null;

    const fallbackEle = validTrimmedElevations[0];
    const sanitizedElevations = trimmedElevations.map((ele) => Number.isFinite(ele) ? ele : fallbackEle);

    let minEle = Infinity;
    let maxEle = -Infinity;
    let ascent = 0;
    let descent = 0;
    let lastEle = null;

    for (const ele of sanitizedElevations) {
      minEle = Math.min(minEle, ele);
      maxEle = Math.max(maxEle, ele);
      if (lastEle != null) {
        const delta = ele - lastEle;
        if (delta > 0) ascent += delta;
        else descent += Math.abs(delta);
      }
      lastEle = ele;
    }

    if (!Number.isFinite(minEle) || !Number.isFinite(maxEle)) return null;

    const samples = 180;
    const totalKm = normalizedDistancesKm[normalizedDistancesKm.length - 1] || 0;
    const sampleDistances = [];
    const sampleElevations = [];
    const sampleCadences = [];
    const samplePowers = [];

    // Bucket boundaries (by index in the trimmed arrays)
    const n = normalizedDistancesKm.length;
    for (let i = 0; i < samples; i += 1) {
      const targetKm = totalKm * (i / Math.max(1, samples - 1));
      let idx = normalizedDistancesKm.findIndex((d) => d >= targetKm);
      if (idx === -1) idx = n - 1;
      idx = Math.max(0, Math.min(sanitizedElevations.length - 1, idx));
      sampleDistances.push(targetKm);
      sampleElevations.push(sanitizedElevations[idx]);

      // Bucket average for cadence / power (smooths noise, shows pauses correctly)
      const bucketStart = Math.floor((i / Math.max(1, samples)) * n);
      const bucketEnd = Math.max(bucketStart + 1, Math.floor(((i + 1) / Math.max(1, samples)) * n));
      let cSum = 0, cCount = 0, pSum = 0, pCount = 0;
      for (let j = bucketStart; j < bucketEnd && j < n; j += 1) {
        if (trimmedCadences[j] != null) { cSum += trimmedCadences[j]; cCount += 1; }
        if (trimmedPowers[j] != null) { pSum += trimmedPowers[j]; pCount += 1; }
      }
      sampleCadences.push(cCount > 0 ? cSum / cCount : null);
      samplePowers.push(pCount > 0 ? pSum / pCount : null);
    }

    // Stats for cadence / power (only over non-null moving values)
    const cadencesValid = trimmedCadences.filter((v) => v != null && v > 0);
    const powersValid = trimmedPowers.filter((v) => v != null);
    const avgCadence = cadencesValid.length ? cadencesValid.reduce((a, b) => a + b, 0) / cadencesValid.length : null;
    const maxCadence = cadencesValid.length ? Math.max(...cadencesValid) : null;
    const avgPower = powersValid.length ? powersValid.reduce((a, b) => a + b, 0) / powersValid.length : null;
    const maxPower = powersValid.length ? Math.max(...powersValid) : null;

    const hasCadence = sampleCadences.some((v) => v != null);
    const hasPower = samplePowers.some((v) => v != null);

    const activity = this._activities[this._idx] || {};
    const avgSpeed = activity.speed?.average;
    const maxSpeed = activity.speed?.maximum;

    return {
      minEle,
      maxEle,
      ascent,
      descent,
      totalKm,
      sampleDistances,
      sampleElevations,
      sampleCadences,
      samplePowers,
      hasCadence,
      hasPower,
      avgCadence,
      maxCadence,
      avgPower,
      maxPower,
      avgSpeed: Number.isFinite(avgSpeed) ? avgSpeed : null,
      maxSpeed: Number.isFinite(maxSpeed) ? maxSpeed : null,
    };
  }

  _renderMiniChart(title, rangeText, samples, unit, color, fillColor, minValue, maxValue, showAxis) {
    const width = 1000;
    const height = 160;
    const padL = 46;
    const padR = 8;
    const padT = 18;
    const padB = showAxis ? 24 : 8;
    const chartW = width - padL - padR;
    const chartH = height - padT - padB;
    const span = Math.max(1, maxValue - minValue);

    // Build polyline with null-handling: break line where no data
    const segments = [];
    let current = [];
    samples.forEach((v, i) => {
      if (v == null) {
        if (current.length) { segments.push(current); current = []; }
      } else {
        const x = padL + (chartW * i) / Math.max(1, samples.length - 1);
        const y = padT + chartH - (((v - minValue) / span) * chartH);
        current.push(`${x.toFixed(1)},${y.toFixed(1)}`);
      }
    });
    if (current.length) segments.push(current);

    const linesSvg = segments.map((seg) =>
      `<polyline points="${seg.join(' ')}" fill="none" stroke="${color}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"></polyline>`
    ).join('');

    // Fill (only useful for elevation — keep optional)
    let fillSvg = '';
    if (fillColor && segments.length === 1) {
      const seg = segments[0];
      const firstX = seg[0].split(',')[0];
      const lastX = seg[seg.length - 1].split(',')[0];
      fillSvg = `<polyline points="${firstX},${height - padB} ${seg.join(' ')} ${lastX},${height - padB}" fill="${fillColor}" stroke="none"></polyline>`;
    }

    const gridTicks = [0, 0.5, 1].map((t) => {
      const y = padT + chartH - (chartH * t);
      const label = Math.round(minValue + span * t);
      return `<line x1="${padL}" y1="${y.toFixed(1)}" x2="${width - padR}" y2="${y.toFixed(1)}" stroke="rgba(0,0,0,.08)" stroke-dasharray="3 4" />
              <text x="0" y="${(y + 4).toFixed(1)}" font-size="11" fill="rgba(0,0,0,.55)">${label}</text>`;
    }).join('');

    return `
      <div class="eb-profile-head">
        <div class="eb-profile-title">${title}</div>
        <div class="eb-profile-range">${rangeText}</div>
      </div>
      <svg class="eb-profile-chart" viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" aria-label="${title}">
        ${gridTicks}
        ${fillSvg}
        ${linesSvg}
        <text x="${padL - 4}" y="${padT - 4}" font-size="10" fill="rgba(0,0,0,.55)" text-anchor="end">${unit}</text>
      </svg>
    `;
  }

  _renderFullscreenProfile() {
    const el = this._$("eb-fullscreen-profile");
    if (!el) return;

    const profile = this._buildElevationProfileData();
    if (!profile) {
      el.innerHTML = `<div class="eb-profile-title">${this._t("profile_title")}</div><div class="eb-profile-range">${this._t("profile_no_data")}</div>`;
      return;
    }

    const {
      minEle, maxEle, ascent, descent, totalKm,
      sampleElevations, sampleCadences, samplePowers,
      hasCadence, hasPower,
      avgCadence, maxCadence, avgPower, maxPower,
      avgSpeed, maxSpeed,
    } = profile;

    const fmtKm = (v) => `${v.toFixed(v >= 10 ? 1 : 2).replace('.', ',')} km`;
    const axisLabels = [0, 0.25, 0.5, 0.75, 1].map((t) => fmtKm(totalKm * t));

    // Höhe
    const eleChart = this._renderMiniChart(
      this._t("profile_title"),
      this._t("profile_min_max", Math.round(minEle), Math.round(maxEle)),
      sampleElevations,
      "m",
      "#89b52b",
      "rgba(139,195,74,.20)",
      minEle, maxEle,
      false
    );

    // Kadenz
    let cadChart = '';
    if (hasCadence) {
      const cadMin = 0;
      const cadMax = Math.max(20, Math.ceil((maxCadence || 0) / 10) * 10);
      cadChart = this._renderMiniChart(
        this._t("profile_cadence"),
        this._t("profile_avg_max_rpm",
          avgCadence != null ? Math.round(avgCadence) : '–',
          maxCadence != null ? Math.round(maxCadence) : '–'),
        sampleCadences,
        "rpm",
        "#f39c12",
        null,
        cadMin, cadMax,
        false
      );
    }

    // Leistung
    let powChart = '';
    if (hasPower) {
      const powMin = 0;
      const powMax = Math.max(50, Math.ceil((maxPower || 0) / 50) * 50);
      powChart = this._renderMiniChart(
        this._t("profile_power"),
        this._t("profile_avg_max_w",
          avgPower != null ? Math.round(avgPower) : '–',
          maxPower != null ? Math.round(maxPower) : '–'),
        samplePowers,
        "W",
        "#e74c3c",
        null,
        powMin, powMax,
        true
      );
    }

    el.innerHTML = `
      ${eleChart}
      ${cadChart}
      ${powChart}
      <div class="eb-profile-axis">
        ${axisLabels.map((label) => `<span>${label}</span>`).join('')}
      </div>
      <div class="eb-profile-stats">
        <div class="eb-profile-stat"><div class="eb-pv">${Math.round(ascent)} m</div><div class="eb-pl">${this._t("profile_ascent")}</div></div>
        <div class="eb-profile-stat"><div class="eb-pv">${Math.round(descent)} m</div><div class="eb-pl">${this._t("profile_descent")}</div></div>
        <div class="eb-profile-stat"><div class="eb-pv">${avgSpeed != null ? avgSpeed.toFixed(1).replace('.', ',') : '–'} km/h</div><div class="eb-pl">${this._t("profile_avg_speed")}</div></div>
        <div class="eb-profile-stat"><div class="eb-pv">${maxSpeed != null ? maxSpeed.toFixed(1).replace('.', ',') : '–'} km/h</div><div class="eb-pl">${this._t("profile_max_speed")}</div></div>
      </div>
    `;
  }


  _setFullscreenTab(tab) {
    const next = tab === "elevation" ? "elevation" : "map";
    this._fullscreenTab = next;
    const isMap = next === "map";
    const mapBtn = this._$("eb-tab-map");
    const eleBtn = this._$("eb-tab-elevation");
    // Toggle the wrapper, not #eb-fullscreen-map itself: the weather
    // overlay now lives as a wrapper sibling (see _buildDOM), so hiding
    // just the inner map div would leave it visible over the elevation
    // profile. Hiding the wrapper hides map + overlay together, same as
    // when the overlay used to be a child of #eb-fullscreen-map.
    const mapWrapEl = this._$("eb-fullscreen-map-wrap");
    const profileEl = this._$("eb-fullscreen-profile");
    const fitBtn = this._$("eb-fit");
    if (mapBtn) {
      mapBtn.classList.toggle("active", isMap);
      mapBtn.setAttribute("aria-selected", isMap ? "true" : "false");
    }
    if (eleBtn) {
      eleBtn.classList.toggle("active", !isMap);
      eleBtn.setAttribute("aria-selected", !isMap ? "true" : "false");
    }
    if (mapWrapEl) mapWrapEl.classList.toggle("eb-hidden", !isMap);
    if (profileEl) profileEl.classList.toggle("eb-hidden", isMap);
    if (fitBtn) fitBtn.classList.toggle("eb-hidden", !isMap);
    if (isMap) {
      this._scheduleFullscreenSync("tab map");
    } else {
      this._renderFullscreenProfile();
    }
  }

  _slugify(text) {
    return String(text || "ride")
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "")
      .slice(0, 60) || "ride";
  }

  _escapeXml(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&apos;");
  }

  _trackPointTime(point, index) {
    const candidates = [point?.time, point?.timestamp, point?.ts, point?.dateTime, point?.recordedAt];
    for (const candidate of candidates) {
      if (!candidate) continue;
      const date = new Date(candidate);
      if (!Number.isNaN(date.getTime())) return date.toISOString();
    }

    const activity = this._activities[this._idx];
    const base = activity?.startTime ? new Date(activity.startTime) : null;
    if (base && !Number.isNaN(base.getTime())) {
      const offsetSeconds = Math.max(0, index);
      return new Date(base.getTime() + offsetSeconds * 1000).toISOString();
    }

    return null;
  }

  _buildCurrentGpx() {
    if (!Array.isArray(this._currentTrack) || !this._currentTrack.length) return null;

    const activity = this._activities[this._idx] || {};
    const title = activity.title || "Bosch eBike Ride";
    const type = activity.type || "Ride";

    const trackPoints = this._currentTrack.map((point, index) => {
      const ele = Number.isFinite(point?.ele) ? point.ele
        : Number.isFinite(point?.alt) ? point.alt
        : Number.isFinite(point?.altitude) ? point.altitude
        : null;
      const time = this._trackPointTime(point, index);
      return `    <trkpt lat="${point.lat}" lon="${point.lon}">` +
        (ele != null ? `\n      <ele>${ele}</ele>` : "") +
        (time ? `\n      <time>${time}</time>` : "") +
        `\n    </trkpt>`;
    }).join("\n");

    const metaTime = activity.startTime ? new Date(activity.startTime) : null;
    const metaTimeXml = metaTime && !Number.isNaN(metaTime.getTime())
      ? `\n    <time>${metaTime.toISOString()}</time>` : "";

    return `<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="Home Assistant Bosch eBike Map Card" xmlns="http://www.topografix.com/GPX/1/1">
  <metadata>
    <name>${this._escapeXml(title)}</name>${metaTimeXml}
  </metadata>
  <trk>
    <name>${this._escapeXml(title)}</name>
    <type>${this._escapeXml(type)}</type>
    <trkseg>
${trackPoints}
    </trkseg>
  </trk>
</gpx>`;
  }

  _currentGpxFilename() {
    const activity = this._activities[this._idx] || {};
    const date = activity.startTime ? new Date(activity.startTime) : null;
    const datePart = date && !Number.isNaN(date.getTime()) ? date.toISOString().slice(0, 10) : "ride";
    const titlePart = this._slugify(activity.title || "bosch-ebike-ride");
    return `${datePart}-${titlePart}.gpx`;
  }

  _downloadCurrentGpx() {
    const gpx = this._buildCurrentGpx();
    if (!gpx) {
      this._msg(this._t("msg_gpx_unavailable"));
      this._setTimer(() => this._msg(""), 2200);
      return;
    }

    try {
      const blob = new Blob([gpx], { type: "application/gpx+xml;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = this._currentGpxFilename();
      link.rel = "noopener";
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      this._setTimer(() => URL.revokeObjectURL(url), 2000);
    } catch (error) {
      console.error("[Bosch eBike Map] GPX download error", error);
      this._msg(this._t("msg_gpx_download_failed"));
      this._setTimer(() => this._msg(""), 2200);
    }
  }


  _openFullscreen() {
    this._fullscreenOpen = true;
    const overlay = this._$("eb-fullscreen-overlay");
    if (!overlay) return;
    overlay.classList.add("open");
    overlay.setAttribute("aria-hidden", "false");
    document.body.style.overflow = "hidden";
    this._setFullscreenTab(this._fullscreenTab || "map");
    this._scheduleFullscreenSync("open");
  }

  // Öffnet die aktuell selektierte Tour als Chase-Cam-Wiedergabe in
  // einem Vollbild-Overlay. Erzeugt eine bosch-ebike-3d-map-card-
  // Instanz, gibt ihr das passende Bike/Account-Filter mit (damit der
  // Back-Button die richtige Liste zeigt) und ruft openActivity() -
  // die Card skipt damit ihre List-View und geht direkt in den Detail-
  // (Playback-)Modus.
  //
  // Layout-Fix: die 3D-Card ist intern als Lovelace-Card gebaut und
  // begrenzt ihr Canvas auf var(--m3d-h, 540px). Damit das Overlay
  // auf jedem Bildschirmrand sauber ausfüllt (Map oben, Play-Leiste
  // unten am Rand), injecten wir scoped CSS-Regeln, die dieselbe
  // Flex-Chain wie der :fullscreen-Pfad anwenden - jedoch
  // unkonditional, sobald die Card in einem .eb-chase-overlay sitzt.
  // Dadurch funktioniert die Anzeige sowohl im Browser-Fullscreen als
  // auch im non-FS-Overlay-Zustand.
  _openChaseCam() {
    const activity = this._activities && this._activities[this._idx];
    if (!activity || !activity.id) return;

    this._closeChaseCam();
    this._ensureChaseCamStyles();

    const overlay = document.createElement("div");
    overlay.className = "eb-chase-overlay";
    overlay.style.cssText =
      "position:fixed;inset:0;z-index:10000;background:#000;" +
      "display:flex;flex-direction:column;";

    const closeBtn = document.createElement("button");
    closeBtn.type = "button";
    closeBtn.setAttribute("aria-label", this._t("btn_close"));
    closeBtn.style.cssText =
      "position:absolute;top:calc(env(safe-area-inset-top,0px) + 8px);" +
      "right:8px;z-index:10001;width:36px;height:36px;border:0;border-radius:50%;" +
      "background:rgba(20,24,32,.85);color:#fff;cursor:pointer;" +
      "display:inline-flex;align-items:center;justify-content:center;" +
      "box-shadow:0 2px 8px rgba(0,0,0,.5);";
    closeBtn.innerHTML =
      '<svg viewBox="0 0 24 24" width="20" height="20">' +
      '<path fill="currentColor" d="M19,6.41L17.59,5L12,10.59L6.41,5L5,6.41L10.59,12L5,17.59L6.41,19L12,13.41L17.59,19L19,17.59L13.41,12L19,6.41Z"/>' +
      '</svg>';
    closeBtn.addEventListener("click", () => this._closeChaseCam());
    overlay.appendChild(closeBtn);

    // Live battery overlay (top-left), same opt-in logic as the 2D map.
    const battEl = document.createElement("div");
    battEl.className = "eb-batt-badge";
    battEl.style.cssText =
      "position:absolute;left:12px;top:calc(env(safe-area-inset-top,0px) + 8px);z-index:10001;";
    overlay.appendChild(battEl);
    this._chaseBattEl = battEl;
    this._updateBatteryBadge();

    const card = document.createElement("bosch-ebike-3d-map-card");
    // Playback- und Darstellungs-Settings aus einer auf der Seite
    // existierenden bosch-ebike-3d-map-card übernehmen. Sonst würde
    // der Overlay-Klon mit Default-Werten laufen (playback_speed: 60
    // etc.) und die Chase-Cam-Geschwindigkeit wäre nicht konsistent
    // mit dem, was der User auf seinem Dashboard eingestellt hat.
    const inherited = this._inherit3DMapCardConfig();
    const cfg = { ...inherited, height: 540 };
    if (this._filterAccount && this._filterAccount !== "all") cfg.account_id = this._filterAccount;
    if (this._filterBike && this._filterBike !== "all") cfg.bike_id = this._filterBike;
    card.setConfig(cfg);

    // Overlay zuerst in den DOM, dann die Card. Reihenfolge wichtig,
    // damit die Card im connectedCallback schon ihre DOM-Position
    // kennt.
    document.body.appendChild(overlay);
    document.body.style.overflow = "hidden";
    overlay.appendChild(card);

    card.hass = this._hass;
    // GANZES Activity-Objekt durchreichen, nicht nur { id, accountId }:
    // das 3D-Card liest später a.startTime, a.endTime, a.title etc.
    // Ohne diese Felder fällt _applyIndex auf `new Date()` (aktueller
    // Zeitpunkt) zurück und die Datum-/Uhrzeit-Chips zeigen jetzt
    // statt der echten Tour-Zeit.
    card.openActivity(activity);

    // MapLibre misst seine Canvas-Größe direkt nach dem Mounting.
    // Da die Flex-Chain dann gerade erst greift, kommt der erste
    // resize() noch mit der alten Höhe. Zwei RAFs später hat sich
    // das Layout settled - dann explizit map.resize() triggern.
    requestAnimationFrame(() => requestAnimationFrame(() => {
      try { card._map && card._map.resize(); } catch (_) {}
    }));

    // Falls der User später manuell den Browser-Fullscreen verlässt,
    // soll Escape NICHT direkt das Overlay zumachen - zweiter Escape
    // schließt es.
    this._chaseFsExitedAt = 0;
    this._chaseFsChangeHandler = () => {
      const inFs = document.fullscreenElement === card
        || document.webkitFullscreenElement === card;
      if (!inFs) this._chaseFsExitedAt = Date.now();
    };
    document.addEventListener("fullscreenchange", this._chaseFsChangeHandler);
    document.addEventListener("webkitfullscreenchange", this._chaseFsChangeHandler);

    this._chaseEscHandler = (ev) => {
      if (ev.key !== "Escape") return;
      const inFs = document.fullscreenElement || document.webkitFullscreenElement;
      if (inFs) return;
      if (Date.now() - this._chaseFsExitedAt < 400) return;
      this._closeChaseCam();
    };
    document.addEventListener("keydown", this._chaseEscHandler);

    this._chaseOverlay = overlay;
    this._chaseCard = card;
  }

  // Sucht im DOM nach einer vom User konfigurierten
  // bosch-ebike-3d-map-card und übernimmt deren Playback- und
  // Darstellungs-relevante Konfigurations-Keys. Geht durch Shadow-
  // Roots, weil HA Lovelace-Cards in eigenen Shadow-DOMs einkapselt
  // und document.querySelector sonst nichts finden würde. Bei
  // mehreren Cards gewinnt die erste gefundene. Wenn keine vorhanden:
  // leeres Objekt -> die Overlay-Card nutzt ihre internen Defaults.
  _inherit3DMapCardConfig() {
    const PLAYBACK_KEYS = [
      "playback_speed", "animate_seconds",
      "default_pitch", "chase_zoom", "chase_lookahead",
      "smooth_window", "track_smooth_window",
      "terrain_exaggeration", "satellite_tile_url", "satellite_max_zoom",
      "north_up",
      "show_date", "show_time", "show_sun",
      "show_speed", "show_distance", "show_elevation",
      "stats_as_chips",
    ];
    const found = this._findCardsAcrossShadow("bosch-ebike-3d-map-card");
    for (const c of found) {
      if (c === this._chaseCard) continue;   // niemals von uns selbst klonen
      const src = c._config;
      if (!src) continue;
      const out = {};
      for (const k of PLAYBACK_KEYS) {
        if (src[k] != null && src[k] !== "") out[k] = src[k];
      }
      // Wenn die gefundene Card wenigstens EINEN playback-relevanten
      // Wert hatte, nehmen wir sie. Sonst weiter suchen.
      if (Object.keys(out).length > 0) return out;
    }
    return {};
  }

  // BFS durch document.* + shadowRoots, gibt alle Custom-Elements mit
  // dem angegebenen Tag-Namen zurück. Notwendig weil HA Lovelace
  // Cards in geschachtelten Shadow-DOMs hostet (hui-view, hui-card,
  // ha-card etc.) und ein flaches document.querySelectorAll die nicht
  // findet.
  _findCardsAcrossShadow(tagName) {
    const out = [];
    const tag = tagName.toLowerCase();
    const visited = new WeakSet();
    const queue = [document];
    while (queue.length) {
      const root = queue.shift();
      if (!root || visited.has(root)) continue;
      visited.add(root);
      let nodes = [];
      try { nodes = root.querySelectorAll("*"); } catch (_) { continue; }
      for (const n of nodes) {
        if (n.tagName && n.tagName.toLowerCase() === tag) out.push(n);
        if (n.shadowRoot && !visited.has(n.shadowRoot)) queue.push(n.shadowRoot);
      }
    }
    return out;
  }

  // Injectet einmalig ein <style>-Element in document.head, das die
  // Flex-Chain für die 3D-Card im Chase-Cam-Overlay aktiviert.
  // Idempotent über die ID.
  _ensureChaseCamStyles() {
    if (document.getElementById("eb-chase-style")) return;
    const ss = document.createElement("style");
    ss.id = "eb-chase-style";
    ss.textContent = `
      .eb-chase-overlay bosch-ebike-3d-map-card {
        flex: 1; min-height: 0;
        display: flex; flex-direction: column;
        width: 100%; height: 100%;
      }
      .eb-chase-overlay bosch-ebike-3d-map-card ha-card {
        flex: 1; min-height: 0; height: auto; max-height: none;
        border-radius: 0;
        display: flex; flex-direction: column;
      }
      .eb-chase-overlay bosch-ebike-3d-map-card .map3d-root {
        flex: 1; min-height: 0;
        display: flex; flex-direction: column;
      }
      .eb-chase-overlay bosch-ebike-3d-map-card .map3d-detail {
        flex: 1; min-height: 0;
      }
      .eb-chase-overlay bosch-ebike-3d-map-card .map3d-canvas {
        height: 100% !important; max-height: none !important;
      }
    `;
    document.head.appendChild(ss);
  }

  _closeChaseCam() {
    if (this._chaseEscHandler) {
      document.removeEventListener("keydown", this._chaseEscHandler);
      this._chaseEscHandler = null;
    }
    if (this._chaseFsChangeHandler) {
      document.removeEventListener("fullscreenchange", this._chaseFsChangeHandler);
      document.removeEventListener("webkitfullscreenchange", this._chaseFsChangeHandler);
      this._chaseFsChangeHandler = null;
    }
    // Falls die Card gerade noch im Browser-Fullscreen ist, zuerst
    // ordentlich rausgehen - sonst meckert Chrome beim sofortigen
    // DOM-Detach mit "fullscreen element removed".
    try {
      if (this._chaseCard && (
        document.fullscreenElement === this._chaseCard
        || document.webkitFullscreenElement === this._chaseCard
      )) {
        const exit = document.exitFullscreen || document.webkitExitFullscreen;
        if (exit) exit.call(document);
      }
    } catch (_) { /* ignore */ }
    if (this._chaseOverlay) {
      try { this._chaseOverlay.remove(); } catch (_) {}
      this._chaseOverlay = null;
    }
    this._chaseCard = null;
    document.body.style.overflow = "";
  }

  _closeFullscreen() {
    this._fullscreenOpen = false;
    const overlay = this._$("eb-fullscreen-overlay");
    if (overlay) {
      overlay.classList.remove("open");
      overlay.setAttribute("aria-hidden", "true");
    }
    document.body.style.overflow = "";
    this._destroyFullscreenMap();
    this._rebuildInlineMapAfterFullscreen();
  }

  _rebuildInlineMapAfterFullscreen() {
    if (!this._connected || !this._currentTrack.length) return;
    this._destroyMap(true);
    this._needsInlineFit = true;
    this._inlineUserAdjustedView = false;

    [0, 100, 280, 700].forEach((delay) => {
      this._setTimer(() => {
        this._activateMap("fullscreen closed");
      }, delay);
    });
  }

  _syncFullscreenMap(reason = "") {
    if (!this._fullscreenOpen || !this._currentTrack.length) return;
    const Leaflet = window.L;
    const mapEl = this._$("eb-fullscreen-map");
    if (!Leaflet || !mapEl) return;

    const rect = mapEl.getBoundingClientRect();
    if (rect.width < 100 || rect.height < 100) return;

    if (!this._fullscreenMap) {
      try {
        mapEl.innerHTML = "";
        this._fullscreenMap = Leaflet.map(mapEl, {
          zoomControl: true,
          attributionControl: false,
          preferCanvas: true,
          zoomAnimation: true,
          fadeAnimation: true,
          markerZoomAnimation: true,
        }).setView([48.7, 12.4], 10);

        this._applyBaseLayer(this._fullscreenMap, "fullscreen", true);

        this._fullscreenTrackGroup = Leaflet.layerGroup().addTo(this._fullscreenMap);
      } catch (error) {
        console.error("[Bosch eBike Map] fullscreen map create error", error);
        this._destroyFullscreenMap();
        return;
      }
    }

    try {
      this._fullscreenMap.invalidateSize({ pan: false, animate: false });
    } catch (_) {}

    this._renderTrackToMap(this._fullscreenMap, this._fullscreenTrackGroup, {
      padding: [60, 60],
      legend: "fullscreen",
      fit: this._needsFullscreenFit && !this._fullscreenUserAdjustedView,
    });
    this._needsFullscreenFit = false;

    // Re-render Wikipedia markers if enabled (covers cached articles instantly)
    if (this._wikiEnabled) {
      const cached = this._wikiArticles.get(this._currentTrackActivityId);
      if (cached) {
        this._renderWikiMarkers(cached);
      } else {
        this._loadAndRenderWiki();
      }
    }
    // Re-render POI markers
    if (this._poiEnabled) {
      const cached = this._poiData.get(this._currentTrackActivityId);
      if (cached) {
        this._renderPoiMarkers(cached);
      } else {
        this._loadAndRenderPoi();
      }
    }
    // Re-apply the weather overlay if enabled. _loadAndRenderWeather() checks
    // its own in-memory/localStorage cache first, so this is a cheap re-apply
    // to the fullscreen overlay DOM when already cached, not a re-fetch.
    if (this._weatherEnabled) this._loadAndRenderWeather();

    this._setTimer(() => {
      try { this._fullscreenMap?.invalidateSize({ pan: false, animate: false }); } catch (_) {}
    }, 150);
  }

  _go(dir) {
    const next = this._idx + dir;
    if (next >= 0 && next < this._activities.length) this._show(next, true);
  }

  _jumpDate(str) {
    if (!str) return;
    const target = new Date(str).getTime();
    let best = 0;
    let bestDiff = Infinity;

    this._activities.forEach((activity, index) => {
      const diff = Math.abs(new Date(activity.startTime).getTime() - target);
      if (diff < bestDiff) {
        bestDiff = diff;
        best = index;
      }
    });

    this._show(best, true);
  }
}

// ============================================================================
// Heatmap card — overlays all rides on one map
// ============================================================================

class BoschEBikeHeatmapCard extends HTMLElement {
  constructor() {
    super();
    this._hass = null;
    this._config = {};
    this._tracks = [];
    this._instances = [];
    this._filterAccount = "all";
    this._filterBike = "all";
    this._filterRange = "365"; // days; "all" for everything, "custom" for date_from/date_to
    this._filterDateFrom = "";   // YYYY-MM-DD, used when _filterRange === "custom"
    this._filterDateTo = "";
    this._map = null;
    this._tracksGroup = null;
    this._baseLayer = null;
    this._mapStyle = "osm";
    this._ready = false;
    this._booting = false;
    this._loaded = false;
  }

  setConfig(config) {
    this._config = {
      height: config.height || 500,
      ...config,
    };
    if (config.account_id) {
      this._filterAccount = config.account_id;
      this._lockedAccount = true;
    } else {
      this._lockedAccount = false;
    }
    if (config.bike_id) {
      this._filterBike = config.bike_id;
      this._lockedBike = true;
    } else {
      this._lockedBike = false;
    }
    if (this._ready) {
      this._applyHeatTitle();
      this._populateFilters();
      this._renderTracks();
    }
  }

  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    if (first) this._boot();
  }

  static getConfigElement() {
    return document.createElement("bosch-ebike-heatmap-card-editor");
  }

  static getStubConfig() {
    return { height: 500 };
  }

  getCardSize() {
    return Math.ceil((this._config.height || 500) / 50) + 2;
  }

  _applyHeatTitle() {
    const head = this.querySelector(".heat-head span");
    if (head && this._config && this._config.title) {
      head.textContent = this._config.title;
    }
  }

  async _boot() {
    if (this._booting || this._ready) return;
    this._booting = true;
    try {
      this._buildDOM();
      this._ready = true;
      this._applyHeatTitle();
      await ensureLeaflet();
      await this._fetchInstances();
      this._populateFilters();
      this._createMap();
      await this._loadTracks();
      this._renderTracks();
    } catch (err) {
      console.error("[Bosch eBike Heatmap] boot error", err);
      const msg = this.querySelector("#heat-msg");
      if (msg) msg.textContent = ebT(this._hass, "msg_error_prefix") + describeBootError(this._hass, err);
    } finally {
      this._booting = false;
    }
  }

  _buildDOM() {
    const h = this._config.height || 500;
    this.innerHTML = "";
    const card = document.createElement("ha-card");
    this.appendChild(card);
    const style = document.createElement("style");
    style.textContent = LEAFLET_INLINE_CSS + `
      .heat-head {
        display:flex; align-items:center; gap:8px; padding:12px 16px;
        background:var(--primary-color,#03a9f4); color:#fff; font-size:16px; font-weight:500;
      }
      .heat-filters {
        display:flex; flex-wrap:wrap; gap:8px; padding:8px 12px;
        background:var(--secondary-background-color,#f5f5f5);
        border-bottom:1px solid var(--divider-color,#e0e0e0);
      }
      .heat-filters select, .heat-filters input[type="date"] {
        padding:5px 8px; border:1px solid var(--divider-color,#ccc);
        border-radius:6px; font-size:13px;
        background:var(--card-background-color,#fff); color:var(--primary-text-color,#333);
      }
      .heat-filter-lbl { font-size:12px; color:var(--secondary-text-color,#666); align-self:center; }
      .heat-map-wrap { position:relative; }
      .heat-map { width:100% !important; height:${h}px !important; min-height:${h}px; z-index:0; position:relative; }
      .heat-overlay {
        position:absolute; inset:0; display:flex; align-items:center; justify-content:center;
        color:var(--secondary-text-color,#999); font-size:14px; pointer-events:none;
      }
      .heat-stats { padding:8px 16px 12px; font-size:13px; color:var(--secondary-text-color,#666); display:flex; gap:16px; flex-wrap:wrap; }
      .heat-stats b { color:var(--primary-text-color,#333); }
      .heat-head .heat-fs-btn {
        margin-left:auto; background:rgba(255,255,255,.15); color:#fff; border:0;
        width:28px; height:28px; border-radius:50%; cursor:pointer;
        display:inline-flex; align-items:center; justify-content:center;
      }
      .heat-head .heat-fs-btn:hover { background:rgba(255,255,255,.28); }
      .heat-head .heat-fs-btn ha-icon { --mdc-icon-size:18px; color:#fff; }
      /* Same flex chain as the 3D card. Pseudo-classes split into
         separate rules to survive CSS-list parsing in Firefox - see
         the long comment in the 3D card style block above. */
      bosch-ebike-heatmap-card:fullscreen {
        display:flex; flex-direction:column;
        width:100%; height:100%;
        background: var(--card-background-color, #fff);
      }
      bosch-ebike-heatmap-card:-webkit-full-screen {
        display:flex; flex-direction:column;
        width:100%; height:100%;
        background: var(--card-background-color, #fff);
      }
      bosch-ebike-heatmap-card:fullscreen ha-card {
        flex:1; min-height:0; height:auto; max-height:none;
        border-radius:0; display:flex; flex-direction:column;
      }
      bosch-ebike-heatmap-card:-webkit-full-screen ha-card {
        flex:1; min-height:0; height:auto; max-height:none;
        border-radius:0; display:flex; flex-direction:column;
      }
      /* Firefox / Opera honor :fullscreen and the flex chain, but
         percentage heights on a flex child whose parent has
         min-height:0 don't always resolve there (Chromium is more
         lenient). Result: .heat-map kept its baseline ${h}px height
         and a big white area appeared below. Fix: in fullscreen we
         pin .heat-map absolutely inside the already-relative
         wrapper - inset:0 needs no resolved parent height. */
      bosch-ebike-heatmap-card:fullscreen .heat-map-wrap {
        flex:1; min-height:0; position:relative;
      }
      bosch-ebike-heatmap-card:-webkit-full-screen .heat-map-wrap {
        flex:1; min-height:0; position:relative;
      }
      bosch-ebike-heatmap-card:fullscreen .heat-map {
        position:absolute !important; inset:0 !important;
        width:auto !important; height:auto !important;
        min-height:0 !important;
      }
      bosch-ebike-heatmap-card:-webkit-full-screen .heat-map {
        position:absolute !important; inset:0 !important;
        width:auto !important; height:auto !important;
        min-height:0 !important;
      }
      /* iOS / WKWebView fallback: requestFullscreen rejects there, so
         we pin the host with position:fixed. Same flex chain as the
         native rules. */
      bosch-ebike-heatmap-card.heat-pseudo-fs {
        position:fixed !important; inset:0 !important;
        z-index:9999 !important;
        width:100vw !important; height:100vh !important;
        max-width:100vw !important; max-height:100vh !important;
        display:flex !important; flex-direction:column !important;
        background: var(--card-background-color, #fff);
      }
      bosch-ebike-heatmap-card.heat-pseudo-fs ha-card {
        flex:1; min-height:0; height:auto; max-height:none;
        border-radius:0;
        display:flex; flex-direction:column;
      }
      bosch-ebike-heatmap-card.heat-pseudo-fs .heat-map-wrap {
        flex:1; min-height:0; position:relative;
      }
      bosch-ebike-heatmap-card.heat-pseudo-fs .heat-map {
        position:absolute !important; inset:0 !important;
        width:auto !important; height:auto !important;
        min-height:0 !important;
      }
    `;
    card.appendChild(style);

    const t = (k, ...a) => ebT(this._hass, k, ...a);
    const wrap = document.createElement("div");
    wrap.innerHTML = `
      <div class="heat-head">
        <svg viewBox="0 0 24 24" width="22" height="22"><path fill="white" d="M3,3H21V5H3V3M3,7H21V9H3V7M3,11H21V13H3V11M3,15H21V17H3V15M3,19H21V21H3V19Z"/></svg>
        <span>${t("heatmap_title")}</span>
        <button id="heat-fs-btn" class="heat-fs-btn" type="button" title="${t("btn_fullscreen")}" aria-label="${t("btn_fullscreen")}">
          <ha-icon icon="mdi:fullscreen" id="heat-fs-ico"></ha-icon>
        </button>
      </div>
      <div class="heat-filters">
        <span class="heat-filter-lbl">${t("heat_range_label")}</span>
        <select id="heat-range">
          <option value="30">${t("heat_range_30")}</option>
          <option value="90">${t("heat_range_90")}</option>
          <option value="365" selected>${t("heat_range_365")}</option>
          <option value="all">${t("heat_range_all")}</option>
          <option value="custom">${t("heat_range_custom")}</option>
        </select>
        <span class="heat-filter-lbl" id="heat-from-lbl" style="display:none;">${t("heat_date_from")}</span>
        <input type="date" id="heat-from" style="display:none;">
        <span class="heat-filter-lbl" id="heat-to-lbl" style="display:none;">${t("heat_date_to")}</span>
        <input type="date" id="heat-to" style="display:none;">
        <span class="heat-filter-lbl" id="heat-acc-lbl" style="display:none;">${t("heat_account_label")}</span>
        <select id="heat-account" style="display:none;">
          <option value="all">${t("all_accounts")}</option>
        </select>
        <span class="heat-filter-lbl" id="heat-bike-lbl" style="display:none;">${t("heat_bike_label")}</span>
        <select id="heat-bike" style="display:none;">
          <option value="all">${t("all_bikes")}</option>
        </select>
      </div>
      <div class="heat-map-wrap">
        <div id="heat-map" class="heat-map"></div>
        <div class="heat-overlay" id="heat-msg">${t("heat_loading")}</div>
      </div>
      <div class="heat-stats" id="heat-stats"></div>
    `;
    while (wrap.firstChild) card.appendChild(wrap.firstChild);

    this.querySelector("#heat-range").addEventListener("change", async (e) => {
      this._filterRange = e.target.value;
      this._updateCustomRangeUI();
      // Skip the load when switching to "custom" without dates picked
      // yet - the inputs need a value first or the backend would
      // return everything, which is misleading.
      if (this._filterRange === "custom" && !this._filterDateFrom && !this._filterDateTo) {
        return;
      }
      await this._loadTracks();
      this._renderTracks();
    });

    const fromInp = this.querySelector("#heat-from");
    const toInp = this.querySelector("#heat-to");
    const onDateChange = async () => {
      this._filterDateFrom = fromInp.value || "";
      this._filterDateTo = toInp.value || "";
      if (this._filterRange === "custom") {
        await this._loadTracks();
        this._renderTracks();
      }
    };
    fromInp.addEventListener("change", onDateChange);
    toInp.addEventListener("change", onDateChange);
    // Initialise the custom-range visibility based on the current
    // _filterRange (which is "365" on first render, so inputs hidden).
    this._updateCustomRangeUI();
    this.querySelector("#heat-account").addEventListener("change", (e) => {
      this._filterAccount = e.target.value;
      this._populateBikeFilter();
      this._renderTracks();
    });
    this.querySelector("#heat-bike").addEventListener("change", (e) => {
      this._filterBike = e.target.value;
      this._renderTracks();
    });

    const fsBtn = this.querySelector("#heat-fs-btn");
    if (fsBtn) fsBtn.addEventListener("click", () => this._toggleFullscreen());
    this._ensureFullscreenListener();
  }

  // Native Fullscreen API with a CSS-pseudo-fullscreen fallback for
  // iOS Safari / the HA Companion app's WKWebView, where the native
  // API rejects silently or is missing entirely.
  _toggleFullscreen() {
    const target = this;
    const nativeOn = document.fullscreenElement === target || document.webkitFullscreenElement === target;
    const pseudoOn = !!this._heatPseudoFs;
    if (nativeOn || pseudoOn) {
      if (pseudoOn) this._exitHeatPseudoFullscreen();
      else (document.exitFullscreen || document.webkitExitFullscreen)?.call(document);
      return;
    }
    try {
      const req = target.requestFullscreen || target.webkitRequestFullscreen;
      if (!req) { this._enterHeatPseudoFullscreen(); return; }
      const result = req.call(target);
      if (result && typeof result.then === "function") {
        result.catch((e) => {
          console.warn("[Bosch eBike Heatmap] native fullscreen rejected, using fallback", e);
          this._enterHeatPseudoFullscreen();
        });
      }
    } catch (e) {
      console.warn("[Bosch eBike Heatmap] native fullscreen threw, using fallback", e);
      this._enterHeatPseudoFullscreen();
    }
  }

  _enterHeatPseudoFullscreen() {
    if (this._heatPseudoFs) return;
    this._heatPseudoFs = true;
    this.classList.add("heat-pseudo-fs");
    document.body.style.overflow = "hidden";
    const ico = this.querySelector("#heat-fs-ico");
    if (ico) ico.setAttribute("icon", "mdi:fullscreen-exit");
    if (!this._heatPseudoEscHandler) {
      this._heatPseudoEscHandler = (ev) => {
        if (ev.key === "Escape" && this._heatPseudoFs) this._exitHeatPseudoFullscreen();
      };
      document.addEventListener("keydown", this._heatPseudoEscHandler);
    }
    this._refreshHeatmapSize("enter pseudo fullscreen");
    setTimeout(() => { try { this._renderTracks(); } catch (_) {} }, 350);
  }

  _exitHeatPseudoFullscreen() {
    if (!this._heatPseudoFs) return;
    this._heatPseudoFs = false;
    this.classList.remove("heat-pseudo-fs");
    document.body.style.overflow = "";
    const ico = this.querySelector("#heat-fs-ico");
    if (ico) ico.setAttribute("icon", "mdi:fullscreen");
    if (this._heatPseudoEscHandler) {
      document.removeEventListener("keydown", this._heatPseudoEscHandler);
      this._heatPseudoEscHandler = null;
    }
    this._refreshHeatmapSize("exit pseudo fullscreen");
    setTimeout(() => { try { this._renderTracks(); } catch (_) {} }, 350);
  }

  _ensureFullscreenListener() {
    if (this._heatFsChangeHandler) return;
    this._heatFsChangeHandler = () => {
      const fsEl = document.fullscreenElement || document.webkitFullscreenElement;
      const on = fsEl === this;
      const ico = this.querySelector("#heat-fs-ico");
      if (ico) ico.setAttribute("icon", on ? "mdi:fullscreen-exit" : "mdi:fullscreen");
      this._refreshHeatmapSize("native fullscreen change");
      setTimeout(() => { try { this._renderTracks(); } catch (_) {} }, 350);
    };
    document.addEventListener("fullscreenchange", this._heatFsChangeHandler);
    document.addEventListener("webkitfullscreenchange", this._heatFsChangeHandler);
  }

  disconnectedCallback() {
    if (this._heatFsChangeHandler) {
      document.removeEventListener("fullscreenchange", this._heatFsChangeHandler);
      document.removeEventListener("webkitfullscreenchange", this._heatFsChangeHandler);
      this._heatFsChangeHandler = null;
    }
    if (this._heatPseudoEscHandler) {
      document.removeEventListener("keydown", this._heatPseudoEscHandler);
      this._heatPseudoEscHandler = null;
    }
    if (this._heatPseudoFs) {
      this._heatPseudoFs = false;
      this.classList.remove("heat-pseudo-fs");
      document.body.style.overflow = "";
    }
    if (this._heatResizeObserver) {
      try { this._heatResizeObserver.disconnect(); } catch (_) {}
      this._heatResizeObserver = null;
    }
  }

  async _fetchInstances() {
    try {
      const res = await this._hass.callWS({ type: "bosch_ebike/list_instances" });
      this._instances = res.instances || [];
    } catch (_) {
      this._instances = [];
    }
  }

  _populateFilters() {
    const accountSel = this.querySelector("#heat-account");
    const accLbl = this.querySelector("#heat-acc-lbl");
    if (this._lockedAccount) {
      if (accountSel) accountSel.style.display = "none";
      if (accLbl) accLbl.style.display = "none";
    } else if (this._instances.length > 1) {
      const opts = [`<option value="all">${ebT(this._hass, "all_accounts")}</option>`];
      for (const inst of this._instances) {
        opts.push(`<option value="${inst.config_entry_id}">${this._escapeHtml(inst.label)}</option>`);
      }
      accountSel.innerHTML = opts.join("");
      accountSel.value = this._filterAccount;
      accountSel.style.display = "";
      accLbl.style.display = "";
    }
    this._populateBikeFilter();
  }

  _populateBikeFilter() {
    const bikeSel = this.querySelector("#heat-bike");
    const lbl = this.querySelector("#heat-bike-lbl");
    if (this._lockedBike) {
      if (bikeSel) bikeSel.style.display = "none";
      if (lbl) lbl.style.display = "none";
      return;
    }
    const bikes = [];
    for (const inst of this._instances) {
      if (this._filterAccount !== "all" && inst.config_entry_id !== this._filterAccount) continue;
      for (const b of (inst.bikes || [])) {
        const label = this._instances.length > 1 ? `${inst.label} — ${b.label}` : b.label;
        bikes.push({ id: b.id, label });
      }
    }
    if (bikes.length > 1) {
      const opts = [`<option value="all">${ebT(this._hass, "all_bikes")}</option>`];
      for (const b of bikes) {
        opts.push(`<option value="${b.id}">${this._escapeHtml(b.label)}</option>`);
      }
      bikeSel.innerHTML = opts.join("");
      if (this._filterBike !== "all" && !bikes.some((x) => x.id === this._filterBike)) {
        this._filterBike = "all";
      }
      bikeSel.value = this._filterBike;
      bikeSel.style.display = "";
      lbl.style.display = "";
    } else {
      bikeSel.style.display = "none";
      lbl.style.display = "none";
    }
  }

  _escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
    })[c]);
  }

  _createMap() {
    const Leaflet = window.L;
    const mapEl = this.querySelector("#heat-map");
    if (!Leaflet || !mapEl) return;
    this._map = Leaflet.map(mapEl, {
      zoomControl: true,
      attributionControl: false,
      preferCanvas: true,
    }).setView([48.7, 12.4], 6);
    const def = MAP_STYLES.osm;
    this._baseLayer = Leaflet.tileLayer(def.url, def.options).addTo(this._map);
    this._tracksGroup = Leaflet.layerGroup().addTo(this._map);

    // ResizeObserver auf den Wrapper: faengt jede spaetere Aenderung der
    // verfuegbaren Hoehe ab (Sidebar-Toggle, Rotation, Vollbild-Layout
    // stabilisiert sich verzoegert in Firefox/Companion-App). Wir
    // rufen hier NUR invalidateSize - nicht _refreshHeatmapSize - damit
    // die Wrapper-Hoehen-Mutation aus dem Refresh nicht den Observer
    // erneut feuert (Endlosschleife). Die Hoehen-Mutation passiert nur
    // ueber explizite _refreshHeatmapSize-Aufrufe bei Vollbild-Toggle.
    if (!this._heatResizeObserver && typeof ResizeObserver !== "undefined") {
      this._heatResizeObserver = new ResizeObserver(() => {
        try { this._map?.invalidateSize({ animate: false, pan: false }); } catch (_) {}
      });
      const wrap = this.querySelector(".heat-map-wrap");
      if (wrap) this._heatResizeObserver.observe(wrap);
    }
  }

  // Vollbild-/Layoutwechsel sind in HA + Firefox/Opera/Companion-App
  // oft erst nach 100-600 ms stabil. Statt einmalig nach zwei rAF-Ticks
  // pumpen wir invalidateSize in einer kurzen Staffel durch - und
  // setzen im Vollbild zusaetzlich eine explizite Pixelhoehe auf den
  // Wrapper, falls die Flex-Kette durch ha-cards Shadow-DOM oder
  // browserspezifisches Verhalten doch nicht greift. Die .heat-map
  // selbst folgt automatisch via 'position:absolute; inset:0' aus dem
  // CSS - wir muessen sie hier nicht direkt anfassen.
  _refreshHeatmapSize(reason = "") {
    if (!this._map) return;
    const apply = () => {
      try {
        const wrap = this.querySelector(".heat-map-wrap");
        const fsOn =
          document.fullscreenElement === this ||
          document.webkitFullscreenElement === this ||
          this._heatPseudoFs;
        if (wrap) {
          if (fsOn) {
            const head = this.querySelector(".heat-head");
            const filters = this.querySelector(".heat-filters");
            const stats = this.querySelector(".heat-stats");
            const used =
              (head?.offsetHeight || 0) +
              (filters?.offsetHeight || 0) +
              (stats?.offsetHeight || 0);
            const h = Math.max(200, window.innerHeight - used);
            wrap.style.height = `${h}px`;
          } else {
            wrap.style.height = "";
          }
        }
        this._map.invalidateSize({ animate: false, pan: false });
      } catch (e) {
        console.warn("[Bosch eBike Heatmap] resize refresh failed", reason, e);
      }
    };
    // Vier Wellen: sofort nach dem naechsten Doppel-rAF (Standard-Layout-
    // Tick), plus drei spaetere setTimeouts fuer langsam stabilisierende
    // Browser-Fullscreen-Wechsel. Mehr setTimeouts (wie ChatGPT 5x)
    // bringen erfahrungsgemaess nichts ueber 700 ms hinaus.
    requestAnimationFrame(() => requestAnimationFrame(apply));
    setTimeout(apply, 100);
    setTimeout(apply, 350);
    setTimeout(apply, 700);
  }

  // Toggle the From/To inputs depending on whether the dropdown is on
  // "custom". Kept as one helper so the change-listener and the
  // initial _buildDOM call share exactly the same logic.
  _updateCustomRangeUI() {
    const isCustom = this._filterRange === "custom";
    const ids = ["#heat-from-lbl", "#heat-from", "#heat-to-lbl", "#heat-to"];
    for (const sel of ids) {
      const el = this.querySelector(sel);
      if (el) el.style.display = isCustom ? "" : "none";
    }
    // Pre-fill sensible defaults the first time the user switches
    // to custom: last 30 days. They can adjust freely after that.
    if (isCustom && !this._filterDateFrom && !this._filterDateTo) {
      const today = new Date();
      const monthAgo = new Date(today.getTime() - 30 * 86400000);
      const iso = (d) => d.toISOString().slice(0, 10);
      this._filterDateFrom = iso(monthAgo);
      this._filterDateTo = iso(today);
      const fromInp = this.querySelector("#heat-from");
      const toInp = this.querySelector("#heat-to");
      if (fromInp) fromInp.value = this._filterDateFrom;
      if (toInp) toInp.value = this._filterDateTo;
    }
  }

  async _loadTracks() {
    const msg = this.querySelector("#heat-msg");
    if (msg) { msg.textContent = ebT(this._hass, "heat_loading"); msg.style.display = ""; }
    const params = { type: "bosch_ebike/get_all_tracks" };
    if (this._filterRange === "custom") {
      // Send only the half-bounds that are actually set, so users can
      // do "everything from X onwards" by leaving the To field empty.
      if (this._filterDateFrom) params.date_from = this._filterDateFrom;
      if (this._filterDateTo) params.date_to = this._filterDateTo;
    } else if (this._filterRange !== "all") {
      params.max_age_days = parseInt(this._filterRange, 10);
    }
    try {
      const res = await this._hass.callWS(params);
      this._tracks = res.tracks || [];
      this._loaded = true;
    } catch (err) {
      console.error("[Bosch eBike Heatmap] load failed", err);
      this._tracks = [];
      if (msg) msg.textContent = ebT(this._hass, "heat_load_failed");
      return;
    }
    if (msg) msg.style.display = "none";
  }

  _renderTracks() {
    if (!this._map || !this._tracksGroup) return;
    const Leaflet = window.L;
    this._tracksGroup.clearLayers();

    const filtered = this._tracks.filter((t) => {
      if (this._filterAccount !== "all" && t.account_id !== this._filterAccount) return false;
      if (this._filterBike !== "all" && t.bike_id !== this._filterBike) return false;
      return true;
    });

    let totalDist = 0;
    let allLatLngs = [];
    for (const t of filtered) {
      if (!t.points || t.points.length < 2) continue;
      const latlngs = t.points.map((p) => [p.lat, p.lon]);
      Leaflet.polyline(latlngs, {
        color: "#d32f2f",
        weight: 2.5,
        opacity: 0.35,
        smoothFactor: 1.5,
      }).addTo(this._tracksGroup);
      allLatLngs = allLatLngs.concat(latlngs);
      totalDist += t.distance || 0;
    }

    if (allLatLngs.length) {
      try {
        const bounds = Leaflet.latLngBounds(allLatLngs);
        this._map.fitBounds(bounds, { padding: [40, 40], animate: false });
      } catch (_) {}
    }

    const stats = this.querySelector("#heat-stats");
    if (stats) {
      stats.innerHTML = `
        <div>${ebT(this._hass, "heat_stat_rides")}: <b>${filtered.length}</b></div>
        <div>${ebT(this._hass, "heat_stat_distance")}: <b>${(totalDist / 1000).toFixed(0)} km</b></div>
      `;
    }
    const msg = this.querySelector("#heat-msg");
    if (msg) {
      if (!filtered.length) {
        msg.textContent = ebT(this._hass, "heat_no_match");
        msg.style.display = "";
      } else {
        msg.style.display = "none";
      }
    }
  }
}

class BoschEBikeMapCardEditor extends HTMLElement {
  setConfig(config) {
    this._config = config;
    this._render();
  }

  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    if (first) this._loadInstances();
  }

  async _loadInstances() {
    if (!this._hass) return;
    try {
      const res = await this._hass.callWS({ type: "bosch_ebike/list_instances" });
      this._instances = res.instances || [];
    } catch (_) {
      this._instances = [];
    }
    this._render();
  }

  _escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
    })[c]);
  }

  _emit() {
    this.dispatchEvent(new CustomEvent("config-changed", { detail: { config: this._config } }));
  }

  _bikeOptionsForAccount(accountId) {
    const out = [];
    for (const inst of (this._instances || [])) {
      if (accountId && accountId !== "all" && inst.config_entry_id !== accountId) continue;
      for (const b of (inst.bikes || [])) {
        const hasMultiInst = (this._instances || []).length > 1;
        const label = hasMultiInst && !accountId ? `${inst.label} — ${b.label}` : b.label;
        out.push({ id: b.id, label });
      }
    }
    return out;
  }

  _render() {
    if (!this._config) return;
    const cfg = this._config;
    const inputStyle = "width:100%;padding:8px;border:1px solid #ccc;border-radius:4px;background:var(--card-background-color,#fff);color:var(--primary-text-color,#222);";
    const labelStyle = "display:block;margin-top:14px;margin-bottom:6px;font-weight:500";
    const hintStyle = "display:block;margin-top:4px;font-size:12px;color:var(--secondary-text-color,#777)";

    let accountOpts = `<option value="">${ebT(this._hass, "editor_select_all")}</option>`;
    for (const inst of (this._instances || [])) {
      const selected = cfg.account_id === inst.config_entry_id ? " selected" : "";
      accountOpts += `<option value="${this._escapeHtml(inst.config_entry_id)}"${selected}>${this._escapeHtml(inst.label)}</option>`;
    }

    let bikeOpts = `<option value="">${ebT(this._hass, "editor_select_all")}</option>`;
    for (const b of this._bikeOptionsForAccount(cfg.account_id)) {
      const selected = cfg.bike_id === b.id ? " selected" : "";
      bikeOpts += `<option value="${this._escapeHtml(b.id)}"${selected}>${this._escapeHtml(b.label)}</option>`;
    }

    const radii = [
      { v: 500, l: "500 m" },
      { v: 1000, l: "1 km" },
      { v: 2000, l: "2 km" },
      { v: 5000, l: "5 km" },
      { v: 10000, l: "10 km" },
    ];
    const t = (k, ...a) => ebT(this._hass, k, ...a);
    const defaultSuffix = " " + t("radius_default_suffix");
    const selectedWikiRadius = parseInt(cfg.wiki_radius_m, 10) || 1000;
    const wikiRadiusOpts = radii.map((r) => {
      const sel = r.v === selectedWikiRadius ? " selected" : "";
      const label = r.v === 1000 ? `${r.l}${defaultSuffix}` : r.l;
      return `<option value="${r.v}"${sel}>${label}</option>`;
    }).join("");

    const selectedPoiRadius = parseInt(cfg.poi_radius_m, 10) || 1000;
    const poiRadiusOpts = radii.map((r) => {
      const sel = r.v === selectedPoiRadius ? " selected" : "";
      const label = r.v === 1000 ? `${r.l}${defaultSuffix}` : r.l;
      return `<option value="${r.v}"${sel}>${label}</option>`;
    }).join("");

    this.innerHTML = `<div style="padding:16px">
      <label style="${labelStyle.replace('margin-top:14px;', '')}">${t("editor_height")}</label>
      <input type="number" value="${cfg.height || 400}" min="200" max="1000" step="50" style="${inputStyle}" id="h-in">

      <label style="${labelStyle}">${t("editor_title")}</label>
      <input type="text" value="${this._escapeHtml(cfg.title || '')}" placeholder="${t("rides_title")}" style="${inputStyle}" id="title-in">
      <span style="${hintStyle}">${t("editor_title_hint")}</span>

      <label style="${labelStyle}">${t("editor_account_label")}</label>
      <select id="acc-in" style="${inputStyle}">${accountOpts}</select>
      <span style="${hintStyle}">${t("editor_account_hint")}</span>

      <label style="${labelStyle}">${t("editor_bike_label")}</label>
      <select id="bike-in" style="${inputStyle}">${bikeOpts}</select>
      <span style="${hintStyle}">${t("editor_bike_hint")}</span>

      <label style="${labelStyle}">${t("map_editor_battery_live")}</label>
      <div id="batt-live-in"></div>
      <span style="${hintStyle}">${t("map_editor_battery_live_hint")}</span>

      <label style="${labelStyle}">
        <input type="checkbox" id="batt-live-show-in"${cfg.battery_live_show ? " checked" : ""} style="margin-right:8px;vertical-align:middle;">${t("map_editor_battery_live_show")}
      </label>

      <label style="${labelStyle}">${t("editor_wiki_radius")}</label>
      <select id="wiki-radius-in" style="${inputStyle}">${wikiRadiusOpts}</select>
      <span style="${hintStyle}">${t("editor_wiki_radius_hint")}</span>

      <label style="${labelStyle}">${t("editor_poi_radius")}</label>
      <select id="poi-radius-in" style="${inputStyle}">${poiRadiusOpts}</select>
      <span style="${hintStyle}">${t("editor_poi_radius_hint")}</span>

      <label style="${labelStyle}">${t("map_editor_visibility")}</label>
      <div>
        <input type="checkbox" id="show-header-in"${cfg.show_header !== false ? " checked" : ""} style="margin-right:8px;vertical-align:middle;">${t("map_editor_show_header")}<br>
        <input type="checkbox" id="show-nav-in"${cfg.show_nav !== false ? " checked" : ""} style="margin-right:8px;vertical-align:middle;">${t("map_editor_show_nav")}<br>
        <input type="checkbox" id="show-sort-in"${cfg.show_sort !== false ? " checked" : ""} style="margin-right:8px;vertical-align:middle;">${t("map_editor_show_sort")}
      </div>
      <span style="${hintStyle}">${t("map_editor_visibility_hint")}</span>

      <div style="margin-top:18px;padding-top:14px;border-top:1px solid var(--divider-color);">
        <div style="font-weight:600;color:var(--primary-text-color);font-size:13px;">
          ${t("editor_chase_section")}
        </div>
        <div style="font-size:11px;color:var(--secondary-text-color);margin-top:2px;line-height:1.4;">
          ${t("editor_chase_section_hint")}
        </div>
      </div>

      ${this._renderPresetControls(labelStyle, hintStyle, inputStyle)}

      ${this._renderSharedSelectField("camera_mode", "map3d_editor_camera_mode", "map3d_editor_camera_mode_hint", [
        ["chase", "map3d_camera_mode_chase"],
        ["fpv", "map3d_camera_mode_fpv"],
      ], inputStyle, labelStyle, hintStyle)}
      ${this._renderSharedField("playback_speed", "map3d_editor_playback_speed", "map3d_editor_playback_speed_hint", "number", inputStyle, labelStyle, hintStyle)}
      ${this._renderSharedField("animate_seconds", "map3d_editor_animate_seconds", "map3d_editor_animate_seconds_override_hint", "number", inputStyle, labelStyle, hintStyle)}
      ${this._renderSharedField("default_pitch", "map3d_editor_default_pitch", "map3d_editor_default_pitch_hint", "number", inputStyle, labelStyle, hintStyle)}
      ${this._renderSharedField("chase_zoom", "map3d_editor_chase_zoom", "map3d_editor_chase_zoom_hint", "number", inputStyle, labelStyle, hintStyle)}
      ${this._renderSharedField("chase_lookahead", "map3d_editor_chase_lookahead", "map3d_editor_chase_lookahead_hint", "number", inputStyle, labelStyle, hintStyle)}
      ${this._renderSharedField("fpv_height_m", "map3d_editor_fpv_height", "map3d_editor_fpv_height_hint", "number", inputStyle, labelStyle, hintStyle)}
      ${this._renderSharedField("fpv_distance_m", "map3d_editor_fpv_distance", "map3d_editor_fpv_distance_hint", "number", inputStyle, labelStyle, hintStyle)}
      ${this._renderSharedField("fpv_lookahead_m", "map3d_editor_fpv_lookahead", "map3d_editor_fpv_lookahead_hint", "number", inputStyle, labelStyle, hintStyle)}
      ${this._renderSharedField("smooth_window", "map3d_editor_smooth_window", "map3d_editor_smooth_window_hint", "number", inputStyle, labelStyle, hintStyle)}
      ${this._renderSharedField("track_smooth_window", "map3d_editor_track_smooth", "map3d_editor_track_smooth_hint", "number", inputStyle, labelStyle, hintStyle)}
      ${this._renderSharedField("terrain_exaggeration", "map3d_editor_terrain_exag", "map3d_editor_terrain_exag_hint", "number", inputStyle, labelStyle, hintStyle)}
      ${this._renderSharedField("satellite_max_zoom", "map3d_editor_sat_maxzoom", "map3d_editor_sat_maxzoom_hint", "number", inputStyle, labelStyle, hintStyle)}
      ${this._renderSharedField("satellite_tile_url", "map3d_editor_sat_url", "map3d_editor_sat_url_hint", "text", inputStyle, labelStyle, hintStyle)}
      ${this._renderSharedField("north_up", "map3d_editor_north_up", "map3d_editor_north_up_hint", "number", inputStyle, labelStyle, hintStyle)}
    </div>`;

    this.querySelector("#h-in").addEventListener("change", (e) => {
      this._config = { ...this._config, height: parseInt(e.target.value, 10) || 400 };
      this._emit();
    });
    this.querySelector("#title-in").addEventListener("change", (e) => {
      const v = e.target.value.trim();
      this._config = { ...this._config };
      if (v) this._config.title = v;
      else delete this._config.title;
      this._emit();
    });
    this.querySelector("#acc-in").addEventListener("change", (e) => {
      const v = e.target.value;
      this._config = { ...this._config };
      if (v) this._config.account_id = v;
      else delete this._config.account_id;
      // Reset bike when account changes
      delete this._config.bike_id;
      this._emit();
      this._render();
    });
    this.querySelector("#bike-in").addEventListener("change", (e) => {
      const v = e.target.value;
      this._config = { ...this._config };
      if (v) this._config.bike_id = v;
      else delete this._config.bike_id;
      this._emit();
    });
    // Native searchable HA entity picker (issue #45), built here instead of
    // as a template string since its filtering/hass properties can only be
    // set on the actual element, not expressed as static HTML.
    const battLivePicker = document.createElement("ha-entity-picker");
    battLivePicker.hass = this._hass;
    battLivePicker.includeDomains = ["sensor"];
    battLivePicker.allowCustomEntity = true;
    battLivePicker.value = cfg.battery_live_entity || "";
    battLivePicker.style.width = "100%";
    battLivePicker.addEventListener("value-changed", (ev) => {
      const v = ev.detail.value;
      this._config = { ...this._config };
      if (v) this._config.battery_live_entity = v;
      else delete this._config.battery_live_entity;
      this._emit();
    });
    this.querySelector("#batt-live-in").appendChild(battLivePicker);
    this.querySelector("#batt-live-show-in").addEventListener("change", (e) => {
      this._config = { ...this._config };
      if (e.target.checked) this._config.battery_live_show = true;
      else delete this._config.battery_live_show;
      this._emit();
    });
    this.querySelector("#wiki-radius-in").addEventListener("change", (e) => {
      const v = parseInt(e.target.value, 10);
      this._config = { ...this._config };
      if (v && v !== 1000) this._config.wiki_radius_m = v;
      else delete this._config.wiki_radius_m;
      this._emit();
    });
    this.querySelector("#poi-radius-in").addEventListener("change", (e) => {
      const v = parseInt(e.target.value, 10);
      this._config = { ...this._config };
      if (v && v !== 1000) this._config.poi_radius_m = v;
      else delete this._config.poi_radius_m;
      this._emit();
    });
    for (const [id, key] of [
      ["show-header-in", "show_header"],
      ["show-nav-in", "show_nav"],
      ["show-sort-in", "show_sort"],
    ]) {
      this.querySelector(`#${id}`).addEventListener("change", (e) => {
        this._config = { ...this._config, [key]: e.target.checked };
        this._emit();
      });
    }

    // Shared playback fields: einmal hass-Settings nachladen, dann
    // Werte in die Inputs schreiben + Listener mit Debounce-Save.
    this._wireSharedFields();
    this._wirePresetControls();
    if (!this._sharedSettingsHandler) {
      this._sharedSettingsHandler = () => {
        this._syncSharedFields();
        this._syncPresetSelect();
      };
      _cardSettingsBus.addEventListener("changed", this._sharedSettingsHandler);
    }
    ensureCardSettingsLoaded(this._hass).then(() => {
      this._syncSharedFields();
      this._syncPresetSelect();
    }).catch(() => {});
  }

  disconnectedCallback() {
    if (this._sharedSettingsHandler) {
      _cardSettingsBus.removeEventListener("changed", this._sharedSettingsHandler);
      this._sharedSettingsHandler = null;
    }
    if (this._sharedSaveTimers) {
      for (const t of this._sharedSaveTimers.values()) clearTimeout(t);
      this._sharedSaveTimers.clear();
    }
  }

  // Baut einen Block <label> + <input> für ein Shared-Setting. Wird im
  // _render-Template per Tag-Literal aufgerufen, daher reicht Markup
  // ohne Listener-Binding - das passiert nach dem innerHTML in
  // _wireSharedFields.
  _renderSharedField(key, labelKey, hintKey, type, inputStyle, labelStyle, hintStyle) {
    const t = (k) => ebT(this._hass, k);
    const id = `cs-${key}`;
    const hintHtml = hintKey ? `<span style="${hintStyle}">${this._escapeHtml(t(hintKey))}</span>` : "";
    const step = type === "number" ? ' step="any"' : "";
    return `
      <label style="${labelStyle}">${this._escapeHtml(t(labelKey))}</label>
      <input type="${type}"${step} id="${id}" data-shared-key="${key}" data-shared-type="${type}" style="${inputStyle}">
      ${hintHtml}
    `;
  }

  // Same shared-key/shared-type wiring as _renderSharedField, but a
  // <select> instead of an <input> (e.g. camera_mode). "input" events also
  // fire on <select> value changes in current browsers, so it is picked up
  // by the exact same _wireSharedFields/_syncSharedFields loop below
  // without any changes there - matched purely by the [data-shared-key]
  // attribute, not by tag name.
  _renderSharedSelectField(key, labelKey, hintKey, options, inputStyle, labelStyle, hintStyle) {
    const t = (k) => ebT(this._hass, k);
    const id = `cs-${key}`;
    const hintHtml = hintKey ? `<span style="${hintStyle}">${this._escapeHtml(t(hintKey))}</span>` : "";
    const optionsHtml = options
      .map(([value, labelKeyForOption]) => `<option value="${this._escapeHtml(value)}">${this._escapeHtml(t(labelKeyForOption))}</option>`)
      .join("");
    return `
      <label style="${labelStyle}">${this._escapeHtml(t(labelKey))}</label>
      <select id="${id}" data-shared-key="${key}" data-shared-type="text" style="${inputStyle}">${optionsHtml}</select>
      ${hintHtml}
    `;
  }

  _wireSharedFields() {
    if (!this._sharedSaveTimers) this._sharedSaveTimers = new Map();
    const inputs = this.querySelectorAll("[data-shared-key]");
    for (const input of inputs) {
      const key = input.dataset.sharedKey;
      const type = input.dataset.sharedType;
      input.addEventListener("input", () => {
        const v = input.value;
        if (this._sharedSaveTimers.has(key)) clearTimeout(this._sharedSaveTimers.get(key));
        this._sharedSaveTimers.set(key, setTimeout(() => {
          this._sharedSaveTimers.delete(key);
          const value = v === "" || v == null ? null
            : (type === "number" ? Number(v) : v);
          saveCardSetting(this._hass, key, value);
        }, 400));
      });
    }
    this._syncSharedFields();
  }

  // Werte aus dem Storage in die Shared-Inputs schreiben, ohne
  // fokussierte Felder anzufassen (sonst springt der Cursor). Wird
  // sowohl beim Initial-Load gerufen als auch vom Bus, wenn ein
  // anderes Card-Setting-UI etwas geändert hat.
  _syncSharedFields() {
    const inputs = this.querySelectorAll("[data-shared-key]");
    for (const input of inputs) {
      if (document.activeElement === input) continue;
      const key = input.dataset.sharedKey;
      const v = readCardSetting(this._config, key, "");
      input.value = v !== "" && v != null ? String(v) : "";
    }
  }

  // -- Camera presets (issue #43) -------------------------------------
  // Custom presets are user data stored under the "camera_presets" shared
  // key; factory ones are the FACTORY_CAMERA_PRESETS constant above and
  // are never written to storage, so they cannot be corrupted or lost.

  _customCameraPresets() {
    const raw = readCardSetting(this._config, "camera_presets", []);
    return Array.isArray(raw) ? raw : [];
  }

  _allCameraPresets() {
    return [...FACTORY_CAMERA_PRESETS, ...this._customCameraPresets()];
  }

  _currentCameraValues() {
    const values = {};
    for (const key of CAMERA_PRESET_FIELDS) {
      const v = readCardSetting(this._config, key, undefined);
      if (v !== undefined && v !== "") values[key] = v;
    }
    return values;
  }

  _renderPresetControls(labelStyle, hintStyle, inputStyle) {
    const t = (k) => ebT(this._hass, k);
    const btnStyle = "padding:6px 10px;border:1px solid var(--divider-color);border-radius:4px;background:var(--card-background-color,#fff);color:var(--primary-text-color,#222);cursor:pointer;font-size:12px;";
    return `
      <label style="${labelStyle}">${t("map3d_editor_preset_label")}</label>
      <select id="cam-preset-select" style="${inputStyle}"></select>
      <div style="display:flex;gap:6px;margin-top:8px;flex-wrap:wrap;">
        <button type="button" id="cam-preset-save" style="${btnStyle}">${t("map3d_preset_btn_save")}</button>
        <button type="button" id="cam-preset-update" style="${btnStyle}">${t("map3d_preset_btn_update")}</button>
        <button type="button" id="cam-preset-rename" style="${btnStyle}">${t("map3d_preset_btn_rename")}</button>
        <button type="button" id="cam-preset-delete" style="${btnStyle}">${t("map3d_preset_btn_delete")}</button>
      </div>
      <span style="${hintStyle}">${t("map3d_editor_preset_hint")}</span>
    `;
  }

  // Rebuilds the <option> list (factory presets first, translated, then
  // custom ones by name) and selects whichever is active_camera_preset_id,
  // or the blank "not from a preset" option if none/unknown.
  _syncPresetSelect() {
    const select = this.querySelector("#cam-preset-select");
    if (!select || document.activeElement === select) return;
    const t = (k) => ebT(this._hass, k);
    const activeId = readCardSetting(this._config, "active_camera_preset_id", "");
    let html = `<option value="">${this._escapeHtml(t("map3d_preset_custom"))}</option>`;
    for (const preset of this._allCameraPresets()) {
      const label = preset.factory ? t(preset.name_key) : preset.name;
      const selected = preset.id === activeId ? " selected" : "";
      html += `<option value="${this._escapeHtml(preset.id)}"${selected}>${this._escapeHtml(label)}</option>`;
    }
    select.innerHTML = html;
    if (!activeId) select.value = "";
  }

  _wirePresetControls() {
    this._syncPresetSelect();
    const select = this.querySelector("#cam-preset-select");
    if (select && !select.dataset.wired) {
      select.dataset.wired = "1";
      select.addEventListener("change", () => {
        const id = select.value;
        if (!id) { saveCardSetting(this._hass, "active_camera_preset_id", null); return; }
        const preset = this._allCameraPresets().find((p) => p.id === id);
        if (!preset) return;
        saveCardSettings(this._hass, { ...preset.values, active_camera_preset_id: id });
      });
    }

    const saveBtn = this.querySelector("#cam-preset-save");
    if (saveBtn && !saveBtn.dataset.wired) {
      saveBtn.dataset.wired = "1";
      saveBtn.addEventListener("click", () => {
        const name = (window.prompt(ebT(this._hass, "map3d_preset_prompt_name")) || "").trim();
        if (!name) return;
        const id = `custom_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`;
        const list = this._customCameraPresets();
        list.push({ id, name, factory: false, values: this._currentCameraValues() });
        saveCardSettings(this._hass, { camera_presets: list, active_camera_preset_id: id });
      });
    }

    const updateBtn = this.querySelector("#cam-preset-update");
    if (updateBtn && !updateBtn.dataset.wired) {
      updateBtn.dataset.wired = "1";
      updateBtn.addEventListener("click", () => {
        const activeId = readCardSetting(this._config, "active_camera_preset_id", "");
        const list = this._customCameraPresets();
        const entry = list.find((p) => p.id === activeId);
        if (!entry) { window.alert(ebT(this._hass, "map3d_preset_pick_custom_first")); return; }
        entry.values = this._currentCameraValues();
        saveCardSettings(this._hass, { camera_presets: list });
      });
    }

    const renameBtn = this.querySelector("#cam-preset-rename");
    if (renameBtn && !renameBtn.dataset.wired) {
      renameBtn.dataset.wired = "1";
      renameBtn.addEventListener("click", () => {
        const activeId = readCardSetting(this._config, "active_camera_preset_id", "");
        const list = this._customCameraPresets();
        const entry = list.find((p) => p.id === activeId);
        if (!entry) { window.alert(ebT(this._hass, "map3d_preset_pick_custom_first")); return; }
        const name = (window.prompt(ebT(this._hass, "map3d_preset_prompt_name"), entry.name) || "").trim();
        if (!name) return;
        entry.name = name;
        saveCardSettings(this._hass, { camera_presets: list });
      });
    }

    const deleteBtn = this.querySelector("#cam-preset-delete");
    if (deleteBtn && !deleteBtn.dataset.wired) {
      deleteBtn.dataset.wired = "1";
      deleteBtn.addEventListener("click", () => {
        const activeId = readCardSetting(this._config, "active_camera_preset_id", "");
        const list = this._customCameraPresets();
        const idx = list.findIndex((p) => p.id === activeId);
        if (idx < 0) { window.alert(ebT(this._hass, "map3d_preset_pick_custom_first")); return; }
        if (!window.confirm(ebT(this._hass, "map3d_preset_confirm_delete"))) return;
        list.splice(idx, 1);
        saveCardSettings(this._hass, { camera_presets: list, active_camera_preset_id: null });
      });
    }
  }
}

// Heatmap card editor — same UX as the map card editor minus title customisation
class BoschEBikeHeatmapCardEditor extends BoschEBikeMapCardEditor {
  _render() {
    if (!this._config) return;
    const cfg = this._config;
    const inputStyle = "width:100%;padding:8px;border:1px solid #ccc;border-radius:4px;background:var(--card-background-color,#fff);color:var(--primary-text-color,#222);";
    const labelStyle = "display:block;margin-top:14px;margin-bottom:6px;font-weight:500";
    const hintStyle = "display:block;margin-top:4px;font-size:12px;color:var(--secondary-text-color,#777)";

    let accountOpts = `<option value="">${ebT(this._hass, "editor_select_all")}</option>`;
    for (const inst of (this._instances || [])) {
      const selected = cfg.account_id === inst.config_entry_id ? " selected" : "";
      accountOpts += `<option value="${this._escapeHtml(inst.config_entry_id)}"${selected}>${this._escapeHtml(inst.label)}</option>`;
    }

    let bikeOpts = `<option value="">${ebT(this._hass, "editor_select_all")}</option>`;
    for (const b of this._bikeOptionsForAccount(cfg.account_id)) {
      const selected = cfg.bike_id === b.id ? " selected" : "";
      bikeOpts += `<option value="${this._escapeHtml(b.id)}"${selected}>${this._escapeHtml(b.label)}</option>`;
    }

    const t = (k, ...a) => ebT(this._hass, k, ...a);
    this.innerHTML = `<div style="padding:16px">
      <label style="${labelStyle.replace('margin-top:14px;', '')}">${t("editor_height")}</label>
      <input type="number" value="${cfg.height || 500}" min="200" max="1500" step="50" style="${inputStyle}" id="h-in">

      <label style="${labelStyle}">${t("editor_title")}</label>
      <input type="text" value="${this._escapeHtml(cfg.title || '')}" placeholder="${t("heatmap_title")}" style="${inputStyle}" id="title-in">

      <label style="${labelStyle}">${t("editor_account_label")}</label>
      <select id="acc-in" style="${inputStyle}">${accountOpts}</select>
      <span style="${hintStyle}">${t("editor_account_hint")}</span>

      <label style="${labelStyle}">${t("editor_bike_label")}</label>
      <select id="bike-in" style="${inputStyle}">${bikeOpts}</select>
      <span style="${hintStyle}">${t("editor_bike_hint")}</span>
    </div>`;

    this.querySelector("#h-in").addEventListener("change", (e) => {
      this._config = { ...this._config, height: parseInt(e.target.value, 10) || 500 };
      this._emit();
    });
    this.querySelector("#title-in").addEventListener("change", (e) => {
      const v = e.target.value.trim();
      this._config = { ...this._config };
      if (v) this._config.title = v;
      else delete this._config.title;
      this._emit();
    });
    this.querySelector("#acc-in").addEventListener("change", (e) => {
      const v = e.target.value;
      this._config = { ...this._config };
      if (v) this._config.account_id = v;
      else delete this._config.account_id;
      delete this._config.bike_id;
      this._emit();
      this._render();
    });
    this.querySelector("#bike-in").addEventListener("change", (e) => {
      const v = e.target.value;
      this._config = { ...this._config };
      if (v) this._config.bike_id = v;
      else delete this._config.bike_id;
      this._emit();
    });
  }
}

/* ===========================================================================
 * Calendar Card - GitHub-contributions-style per-day distance heatmap
 * ===========================================================================
 *
 * Reads all activities from the existing bosch_ebike/list_activities WS,
 * aggregates them per local-time day, and renders a 7-row grid of weeks.
 * Each cell is colored by total km on that day. Hover shows a tooltip.
 *
 * Lockable to a single account / bike (same pattern as the other cards).
 * No backend changes required.
 */

class BoschEBikeCalendarCard extends HTMLElement {
  constructor() {
    super();
    this._hass = null;
    this._config = {};
    this._activities = [];
    this._instances = [];
    this._filterAccount = "all";
    this._filterBike = "all";
    this._filterRange = "365";   // days, or "all"
    this._lockedAccount = false;
    this._lockedBike = false;
    this._ready = false;
    this._booting = false;
  }

  setConfig(config) {
    this._config = { ...config };
    if (config.account_id) { this._filterAccount = config.account_id; this._lockedAccount = true; }
    else { this._lockedAccount = false; }
    if (config.bike_id) { this._filterBike = config.bike_id; this._lockedBike = true; }
    else { this._lockedBike = false; }
    if (this._ready) {
      this._applyTitle();
      this._populateFilters();
      this._render();
    }
  }

  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    if (first) this._boot();
  }

  static getConfigElement() { return document.createElement("bosch-ebike-calendar-card-editor"); }
  static getStubConfig() { return {}; }
  getCardSize() { return 5; }

  async _boot() {
    if (this._booting || this._ready) return;
    this._booting = true;
    try {
      this._buildDOM();
      this._ready = true;
      this._applyTitle();
      await this._fetchInstances();
      this._populateFilters();
      await this._loadActivities();
      this._render();
    } catch (err) {
      console.error("[Bosch eBike Calendar] boot error", err);
      const msg = this.querySelector("#cal-msg");
      if (msg) msg.textContent = ebT(this._hass, "msg_error_prefix") + (err?.message || err);
    } finally {
      this._booting = false;
    }
  }

  _applyTitle() {
    const head = this.querySelector(".cal-head span");
    if (head && this._config && this._config.title) head.textContent = this._config.title;
  }

  _buildDOM() {
    this.innerHTML = "";
    const card = document.createElement("ha-card");
    this.appendChild(card);
    const style = document.createElement("style");
    style.textContent = `
      .cal-head {
        display:flex; align-items:center; gap:8px; padding:12px 16px;
        background:var(--primary-color,#03a9f4); color:#fff; font-size:16px; font-weight:500;
      }
      .cal-filters {
        display:flex; flex-wrap:wrap; gap:8px; padding:8px 12px;
        background:var(--secondary-background-color,#f5f5f5);
        border-bottom:1px solid var(--divider-color,#e0e0e0);
      }
      .cal-filters select {
        padding:5px 8px; border:1px solid var(--divider-color,#ccc);
        border-radius:6px; font-size:13px;
        background:var(--card-background-color,#fff); color:var(--primary-text-color,#333);
      }
      .cal-filter-lbl { font-size:12px; color:var(--secondary-text-color,#666); align-self:center; }
      .cal-body { padding:14px 16px; overflow-x:auto; }
      .cal-grid {
        display:inline-grid;
        grid-template-rows: 14px repeat(7, 12px);
        gap:3px;
        font-size:10px;
      }
      .cal-month-label {
        font-size:10px; color:var(--secondary-text-color,#666);
        white-space:nowrap;
        text-align:left;
      }
      .cal-cell {
        width:12px; height:12px; border-radius:2px;
        background:var(--cal-bucket-0,#ebedf0);
        cursor:default;
      }
      .cal-cell.b1 { background:var(--cal-bucket-1,#9be9a8); }
      .cal-cell.b2 { background:var(--cal-bucket-2,#40c463); }
      .cal-cell.b3 { background:var(--cal-bucket-3,#30a14e); }
      .cal-cell.b4 { background:var(--cal-bucket-4,#216e39); }
      .cal-cell.spacer { background:transparent; pointer-events:none; }
      .cal-legend { display:flex; align-items:center; gap:6px; padding:0 16px 8px; font-size:11px; color:var(--secondary-text-color,#666); }
      .cal-legend .cal-cell { width:10px; height:10px; }
      .cal-stats { padding:8px 16px 14px; font-size:13px; color:var(--secondary-text-color,#666); display:flex; gap:18px; flex-wrap:wrap; }
      .cal-stats b { color:var(--primary-text-color,#333); }
      .cal-overlay {
        padding:18px 16px; color:var(--secondary-text-color,#999); font-size:13px; text-align:center;
      }
      @media (prefers-color-scheme: dark) {
        .cal-cell { background:var(--cal-bucket-0-dark,#1b1f23); }
        .cal-cell.b1 { background:var(--cal-bucket-1-dark,#0e4429); }
        .cal-cell.b2 { background:var(--cal-bucket-2-dark,#006d32); }
        .cal-cell.b3 { background:var(--cal-bucket-3-dark,#26a641); }
        .cal-cell.b4 { background:var(--cal-bucket-4-dark,#39d353); }
      }
    `;
    card.appendChild(style);

    const t = (k, ...a) => ebT(this._hass, k, ...a);
    const wrap = document.createElement("div");
    wrap.innerHTML = `
      <div class="cal-head">
        <svg viewBox="0 0 24 24" width="22" height="22"><path fill="white" d="M19,3H18V1H16V3H8V1H6V3H5C3.89,3 3,3.9 3,5V19A2,2 0 0,0 5,21H19A2,2 0 0,0 21,19V5C21,3.9 20.1,3 19,3M19,19H5V8H19V19M7,10H12V15H7V10Z"/></svg>
        <span>${t("calendar_title")}</span>
      </div>
      <div class="cal-filters">
        <span class="cal-filter-lbl">${t("cal_range_label")}</span>
        <select id="cal-range">
          <option value="365" selected>${t("cal_range_1y")}</option>
          <option value="730">${t("cal_range_2y")}</option>
          <option value="1825">${t("cal_range_5y")}</option>
          <option value="all">${t("cal_range_all")}</option>
        </select>
        <span class="cal-filter-lbl" id="cal-acc-lbl" style="display:none;">${t("cal_account_label")}</span>
        <select id="cal-account" style="display:none;">
          <option value="all">${t("cal_account_label")}</option>
        </select>
        <span class="cal-filter-lbl" id="cal-bike-lbl" style="display:none;">${t("cal_bike_label")}</span>
        <select id="cal-bike" style="display:none;">
          <option value="all">${t("cal_bike_label")}</option>
        </select>
      </div>
      <div class="cal-body" id="cal-body">
        <div class="cal-overlay" id="cal-msg">${t("cal_loading")}</div>
      </div>
      <div class="cal-legend" id="cal-legend"></div>
      <div class="cal-stats" id="cal-stats"></div>
    `;
    while (wrap.firstChild) card.appendChild(wrap.firstChild);

    this.querySelector("#cal-range").addEventListener("change", (e) => {
      this._filterRange = e.target.value;
      this._render();
    });
    this.querySelector("#cal-account").addEventListener("change", (e) => {
      this._filterAccount = e.target.value;
      if (!this._lockedBike) this._filterBike = "all";
      this._populateBikeFilter();
      this._render();
    });
    this.querySelector("#cal-bike").addEventListener("change", (e) => {
      this._filterBike = e.target.value;
      this._render();
    });
  }

  async _fetchInstances() {
    try {
      const res = await this._hass.callWS({ type: "bosch_ebike/list_instances" });
      this._instances = res.instances || [];
    } catch (_) { this._instances = []; }
  }

  async _loadActivities() {
    try {
      const res = await this._hass.callWS({ type: "bosch_ebike/list_activities" });
      this._activities = res.activities || [];
    } catch (err) {
      console.error("[Bosch eBike Calendar] load_activities failed", err);
      this._activities = [];
    }
  }

  _populateFilters() {
    const accSel = this.querySelector("#cal-account");
    const accLbl = this.querySelector("#cal-acc-lbl");
    if (this._lockedAccount) {
      if (accSel) accSel.style.display = "none";
      if (accLbl) accLbl.style.display = "none";
    } else if (this._instances.length > 1) {
      const t = (k) => ebT(this._hass, k);
      const opts = [`<option value="all">${t("cal_account_label").replace(":", "")}</option>`];
      for (const inst of this._instances) {
        opts.push(`<option value="${this._escapeHtml(inst.config_entry_id)}">${this._escapeHtml(inst.label)}</option>`);
      }
      accSel.innerHTML = opts.join("");
      accSel.value = this._filterAccount;
      accSel.style.display = "";
      accLbl.style.display = "";
    }
    this._populateBikeFilter();
  }

  _populateBikeFilter() {
    const bikeSel = this.querySelector("#cal-bike");
    const bikeLbl = this.querySelector("#cal-bike-lbl");
    if (this._lockedBike) {
      if (bikeSel) bikeSel.style.display = "none";
      if (bikeLbl) bikeLbl.style.display = "none";
      return;
    }
    const bikes = [];
    for (const inst of this._instances) {
      if (this._filterAccount !== "all" && inst.config_entry_id !== this._filterAccount) continue;
      for (const b of (inst.bikes || [])) bikes.push(b);
    }
    if (bikes.length <= 1) {
      bikeSel.style.display = "none";
      bikeLbl.style.display = "none";
      return;
    }
    const t = (k) => ebT(this._hass, k);
    const opts = [`<option value="all">${t("cal_bike_label").replace(":", "")}</option>`];
    for (const b of bikes) {
      opts.push(`<option value="${this._escapeHtml(b.id)}">${this._escapeHtml(b.label)}</option>`);
    }
    bikeSel.innerHTML = opts.join("");
    bikeSel.value = this._filterBike;
    bikeSel.style.display = "";
    bikeLbl.style.display = "";
  }

  _escapeHtml(s) {
    return String(s || "").replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    })[c]);
  }

  _filteredActivities() {
    return (this._activities || []).filter((a) => {
      if (this._filterAccount !== "all" && a.accountId !== this._filterAccount) return false;
      if (this._filterBike !== "all" && a.bikeId !== this._filterBike) return false;
      return true;
    });
  }

  _aggregateByDay(acts) {
    // Returns Map<YYYY-MM-DD, { rides, distanceMeters }>
    const byDay = new Map();
    for (const a of acts) {
      const ts = a.startTime;
      if (!ts) continue;
      let d;
      try { d = new Date(ts); } catch (_) { continue; }
      if (isNaN(d.getTime())) continue;
      const key = this._localDateKey(d);
      const entry = byDay.get(key) || { rides: 0, distanceMeters: 0 };
      entry.rides += 1;
      entry.distanceMeters += a.distance || 0;
      byDay.set(key, entry);
    }
    return byDay;
  }

  _localDateKey(d) {
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, "0");
    const dd = String(d.getDate()).padStart(2, "0");
    return `${y}-${m}-${dd}`;
  }

  _bucketForKm(km) {
    if (km <= 0) return 0;
    if (km < 10) return 1;
    if (km < 25) return 2;
    if (km < 50) return 3;
    return 4;
  }

  _render() {
    if (!this._ready) return;
    const body = this.querySelector("#cal-body");
    const stats = this.querySelector("#cal-stats");
    const legend = this.querySelector("#cal-legend");
    if (!body) return;

    const acts = this._filteredActivities();
    const byDay = this._aggregateByDay(acts);

    // Range: pick start/end
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    let startDate;
    if (this._filterRange === "all") {
      if (acts.length === 0) {
        body.innerHTML = `<div class="cal-overlay">${ebT(this._hass, "cal_no_match")}</div>`;
        stats.innerHTML = "";
        legend.innerHTML = "";
        return;
      }
      let earliest = Infinity;
      for (const a of acts) {
        const t = Date.parse(a.startTime);
        if (!isNaN(t) && t < earliest) earliest = t;
      }
      startDate = new Date(earliest);
      startDate.setHours(0, 0, 0, 0);
    } else {
      const days = parseInt(this._filterRange, 10);
      startDate = new Date(today.getTime() - (days - 1) * 86400000);
    }

    // Align start to Monday (so the column-based grid is week-aligned).
    // Monday = 1, Sunday = 0 in JS; we want column 0 to be Monday.
    const dow = (startDate.getDay() + 6) % 7; // Mon=0, Sun=6
    const gridStart = new Date(startDate.getTime() - dow * 86400000);
    const totalDays = Math.floor((today.getTime() - gridStart.getTime()) / 86400000) + 1;
    const totalWeeks = Math.ceil(totalDays / 7);

    // Build grid: row 0 = month labels, rows 1..7 = day cells
    const cells = [];
    let activeDays = 0;
    let totalRides = 0;
    let totalDistance = 0;
    let lastMonthLabel = -1;
    const monthFmt = new Intl.DateTimeFormat(this._hassLocale(), { month: "short" });
    const dateFmt = new Intl.DateTimeFormat(this._hassLocale(), { year: "numeric", month: "short", day: "numeric" });

    // Row 0: month labels (one per week column at row 0).
    for (let w = 0; w < totalWeeks; w++) {
      const firstDayOfWeek = new Date(gridStart.getTime() + w * 7 * 86400000);
      const m = firstDayOfWeek.getMonth();
      let label = "";
      if (m !== lastMonthLabel && firstDayOfWeek.getDate() <= 14) {
        label = monthFmt.format(firstDayOfWeek);
        lastMonthLabel = m;
      }
      cells.push({ row: 1, col: w + 1, type: "month", text: label });
    }

    // Rows 1..7 (Mon..Sun) for each week column
    for (let w = 0; w < totalWeeks; w++) {
      for (let d = 0; d < 7; d++) {
        const day = new Date(gridStart.getTime() + (w * 7 + d) * 86400000);
        if (day > today) {
          cells.push({ row: d + 2, col: w + 1, type: "spacer" });
          continue;
        }
        if (day < startDate) {
          cells.push({ row: d + 2, col: w + 1, type: "spacer" });
          continue;
        }
        const key = this._localDateKey(day);
        const info = byDay.get(key);
        const rides = info ? info.rides : 0;
        const km = info ? info.distanceMeters / 1000 : 0;
        if (rides > 0) {
          activeDays += 1;
          totalRides += rides;
          totalDistance += info.distanceMeters;
        }
        const bucket = this._bucketForKm(km);
        const dateStr = dateFmt.format(day);
        let title;
        if (rides > 0) {
          title = ebT(this._hass, "cal_day_summary", dateStr, rides, km);
        } else {
          title = ebT(this._hass, "cal_no_rides_day", dateStr);
        }
        cells.push({ row: d + 2, col: w + 1, type: "cell", bucket, title });
      }
    }

    // Build the DOM
    body.innerHTML = "";
    const grid = document.createElement("div");
    grid.className = "cal-grid";
    grid.style.gridTemplateColumns = `repeat(${totalWeeks}, 12px)`;
    for (const c of cells) {
      const el = document.createElement("div");
      el.style.gridRow = String(c.row);
      el.style.gridColumn = String(c.col);
      if (c.type === "month") {
        el.className = "cal-month-label";
        el.textContent = c.text || "";
      } else if (c.type === "spacer") {
        el.className = "cal-cell spacer";
      } else {
        el.className = "cal-cell" + (c.bucket > 0 ? " b" + c.bucket : "");
        el.title = c.title;
      }
      grid.appendChild(el);
    }
    body.appendChild(grid);

    // Stats row
    const t = (k) => ebT(this._hass, k);
    stats.innerHTML = `
      <div>${t("cal_stat_active_days")}: <b>${activeDays}</b></div>
      <div>${t("cal_stat_rides")}: <b>${totalRides}</b></div>
      <div>${t("cal_stat_distance")}: <b>${(totalDistance / 1000).toFixed(0)} km</b></div>
    `;

    // Legend row
    legend.innerHTML = `
      <span>${t("cal_legend_less")}</span>
      <div class="cal-cell"></div>
      <div class="cal-cell b1"></div>
      <div class="cal-cell b2"></div>
      <div class="cal-cell b3"></div>
      <div class="cal-cell b4"></div>
      <span>${t("cal_legend_more")}</span>
    `;
  }

  _hassLocale() {
    // Try to honor HA's configured locale; fall back to browser default.
    if (this._hass && this._hass.locale && this._hass.locale.language) {
      return this._hass.locale.language;
    }
    return (this._hass && this._hass.language) || navigator.language || "en-GB";
  }
}

// Calendar card editor - reuses the heatmap editor pattern (same fields).
class BoschEBikeCalendarCardEditor extends BoschEBikeMapCardEditor {
  _render() {
    if (!this._config) return;
    const cfg = this._config;
    const inputStyle = "width:100%;padding:8px;border:1px solid #ccc;border-radius:4px;background:var(--card-background-color,#fff);color:var(--primary-text-color,#222);";
    const labelStyle = "display:block;margin-top:14px;margin-bottom:6px;font-weight:500";
    const hintStyle = "display:block;margin-top:4px;font-size:12px;color:var(--secondary-text-color,#777)";

    let accountOpts = `<option value="">${ebT(this._hass, "editor_select_all")}</option>`;
    for (const inst of (this._instances || [])) {
      const selected = cfg.account_id === inst.config_entry_id ? " selected" : "";
      accountOpts += `<option value="${this._escapeHtml(inst.config_entry_id)}"${selected}>${this._escapeHtml(inst.label)}</option>`;
    }

    let bikeOpts = `<option value="">${ebT(this._hass, "editor_select_all")}</option>`;
    for (const b of this._bikeOptionsForAccount(cfg.account_id)) {
      const selected = cfg.bike_id === b.id ? " selected" : "";
      bikeOpts += `<option value="${this._escapeHtml(b.id)}"${selected}>${this._escapeHtml(b.label)}</option>`;
    }

    const t = (k, ...a) => ebT(this._hass, k, ...a);
    this.innerHTML = `<div style="padding:16px">
      <label style="${labelStyle.replace('margin-top:14px;', '')}">${t("editor_title")}</label>
      <input type="text" value="${this._escapeHtml(cfg.title || '')}" placeholder="${t("calendar_title")}" style="${inputStyle}" id="title-in">

      <label style="${labelStyle}">${t("editor_account_label")}</label>
      <select id="acc-in" style="${inputStyle}">${accountOpts}</select>
      <span style="${hintStyle}">${t("editor_account_hint")}</span>

      <label style="${labelStyle}">${t("editor_bike_label")}</label>
      <select id="bike-in" style="${inputStyle}">${bikeOpts}</select>
      <span style="${hintStyle}">${t("editor_bike_hint")}</span>
    </div>`;

    this.querySelector("#title-in").addEventListener("change", (e) => {
      const v = e.target.value.trim();
      this._config = { ...this._config };
      if (v) this._config.title = v; else delete this._config.title;
      this._emit();
    });
    this.querySelector("#acc-in").addEventListener("change", (e) => {
      const v = e.target.value;
      this._config = { ...this._config };
      if (v) this._config.account_id = v; else delete this._config.account_id;
      delete this._config.bike_id;
      this._emit();
      this._render();
    });
    this.querySelector("#bike-in").addEventListener("change", (e) => {
      const v = e.target.value;
      this._config = { ...this._config };
      if (v) this._config.bike_id = v; else delete this._config.bike_id;
      this._emit();
    });
  }
}

// ===========================================================================
// Statistics card: bar charts (distance/elevation/avg speed/ride count) over
// the last 12 weeks or months, issue #51.
// ===========================================================================

// Fixed-size bucket boundaries [{start, end, label}], oldest first, ending at
// "now" - weeks are 7-day windows, months are calendar months. `now` is
// injected so this stays testable. Verified standalone (see this session's
// scratchpad sim_stats_card_bucketing.js) before being pasted here.
function statsComputeBuckets(mode, now) {
  const buckets = [];
  if (mode === "weeks") {
    let end = new Date(now);
    for (let i = 0; i < 12; i++) {
      const start = new Date(end.getTime() - 7 * 86400000);
      buckets.unshift({ start, end, label: null });
      end = start;
    }
  } else {
    let end = new Date(now);
    let cursor = new Date(now.getFullYear(), now.getMonth(), 1);
    for (let i = 0; i < 12; i++) {
      const start = cursor;
      buckets.unshift({ start, end, label: null });
      end = start;
      cursor = new Date(start.getFullYear(), start.getMonth() - 1, 1);
    }
  }
  for (const b of buckets) {
    b.label = mode === "weeks"
      ? `${b.start.getMonth() + 1}/${b.start.getDate()}`
      : b.start.toLocaleString(undefined, { month: "short" });
  }
  return buckets;
}

// Finds the bucket index for an activity's startTime (ISO string), or -1 if
// it falls outside all 12 buckets. A ride's own startTime decides its
// bucket - it is never split across a boundary.
function statsBucketIndexFor(startTimeIso, buckets) {
  const t = Date.parse(startTimeIso);
  if (isNaN(t)) return -1;
  for (let i = 0; i < buckets.length; i++) {
    if (t >= buckets[i].start.getTime() && t < buckets[i].end.getTime()) return i;
  }
  return -1;
}

// Best-available tour duration in seconds, mirroring BoschEBike3DMapCard's
// _tourDurationSec(): durationWithoutStops (preferred), then legacy
// duration, then endTime - startTime, else 0. Needed because the backend
// can legitimately omit durationWithoutStops (e.g. BES2 activities) while
// still reporting a real distance - falling back to `|| 0` there would
// silently skew the distance-weighted average speed below.
function statsTourDurationSec(a) {
  if (!a) return 0;
  if (Number.isFinite(a.durationWithoutStops) && a.durationWithoutStops > 0) {
    return a.durationWithoutStops;
  }
  if (Number.isFinite(a.duration) && a.duration > 0) {
    return a.duration;
  }
  if (a.startTime && a.endTime) {
    const d = (new Date(a.endTime).getTime() - new Date(a.startTime).getTime()) / 1000;
    if (Number.isFinite(d) && d > 0) return d;
  }
  return 0;
}

// Aggregates filtered activities into per-bucket totals, parallel to
// `buckets`. Average speed is NOT stored directly - it is derived at render
// time as distanceM / durationS (distance-weighted), never as a mean of
// per-ride speed.average values, so multi-bike/multi-ride buckets stay
// statistically correct.
function statsAggregateIntoBuckets(activities, buckets) {
  const totals = buckets.map(() => ({ distanceM: 0, elevationM: 0, rides: 0, durationS: 0 }));
  for (const a of activities) {
    const idx = statsBucketIndexFor(a.startTime, buckets);
    if (idx === -1) continue;
    const t = totals[idx];
    t.distanceM += a.distance || 0;
    t.elevationM += a.elevation?.gain || 0; // missing -> contributes 0, ride still counted
    t.durationS += statsTourDurationSec(a);
    t.rides += 1;
  }
  return totals;
}

function statsAvgSpeedKmh(bucketTotal) {
  if (bucketTotal.durationS <= 0) return null;
  return (bucketTotal.distanceM / 1000) / (bucketTotal.durationS / 3600);
}

const STATS_METRICS = [
  { key: "show_distance", labelKey: "stats_metric_distance", unitKey: "stats_unit_km",
    value: (t) => t.distanceM / 1000, digits: 1 },
  { key: "show_elevation", labelKey: "stats_metric_elevation", unitKey: "stats_unit_m",
    value: (t) => t.elevationM, digits: 0 },
  { key: "show_avg_speed", labelKey: "stats_metric_avg_speed", unitKey: "stats_unit_kmh",
    value: (t) => statsAvgSpeedKmh(t) ?? 0, digits: 1 },
  { key: "show_ride_count", labelKey: "stats_metric_ride_count", unitKey: "stats_unit_rides",
    value: (t) => t.rides, digits: 0 },
];

// "Nice round number" tick helper for a 3-gridline Y-axis (0 / mid / max).
// Returns { niceMax, ticks: [0, mid, niceMax] } where niceMax is always >=
// the input max, rounded up to a clean 1/2/5-times-a-power-of-ten step, so
// axis labels read as "0/25/50" instead of "0/24.7/49.3". Bars are scaled
// against niceMax (not the raw max) so bars and gridlines always agree.
function statsNiceTicks(max) {
  if (!(max > 0)) return { niceMax: 0, ticks: [0, 0, 0] };
  const rawStep = max / 2;
  const magnitude = Math.pow(10, Math.floor(Math.log10(rawStep)));
  const normalized = rawStep / magnitude;
  let niceStep;
  if (normalized <= 1) niceStep = 1 * magnitude;
  else if (normalized <= 2) niceStep = 2 * magnitude;
  else if (normalized <= 5) niceStep = 5 * magnitude;
  else niceStep = 10 * magnitude;
  const niceMax = niceStep * 2;
  return { niceMax, ticks: [0, niceStep, niceMax] };
}

// Fixed palette for per-bike bars/legend when "All Bikes" is selected with
// 2+ bikes in scope. Matches the vivid Bosch-Flow-style hex values already
// used for assist-mode colors elsewhere in this file (BOSCH_MODE_COLORS),
// copied by value rather than referenced (that object is declared later in
// this file, and a top-level reference here would hit the temporal dead
// zone before the script finishes its first pass). Cycles via modulo if
// more than 8 bikes are in scope.
const STATS_BIKE_COLORS = [
  "#1E9FE0", "#F39200", "#5FB733", "#8A4FD3",
  "#E2231A", "#00B3C8", "#E5006D", "#8C9196",
];

// Fixed, non-cycling color for activities the backend couldn't attribute to
// a specific bike (odometer-based matching failed - see the integration's
// "Unassigned Activities" diagnostic sensor). Kept separate from
// STATS_BIKE_COLORS so it never collides with a real bike's cycled color.
const STATS_UNASSIGNED_COLOR = "#8C9196";

class BoschEBikeStatsCard extends HTMLElement {
  constructor() {
    super();
    this._hass = null;
    this._config = {};
    this._activities = [];
    this._instances = [];
    this._filterAccount = "all";
    this._filterBike = "all";
    this._timeframe = "weeks"; // "weeks" | "months"
    this._lockedAccount = false;
    this._lockedBike = false;
    this._ready = false;
    this._booting = false;
  }

  setConfig(config) {
    this._config = { ...config };
    if (config.account_id) { this._filterAccount = config.account_id; this._lockedAccount = true; }
    else { this._lockedAccount = false; }
    if (config.bike_id) { this._filterBike = config.bike_id; this._lockedBike = true; }
    else { this._lockedBike = false; }
    this._timeframe = config.default_timeframe === "months" ? "months" : "weeks";
    if (this._ready) {
      this._applyTitle();
      this._populateFilters();
      this._render();
    }
  }

  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    if (first) this._boot();
  }

  static getConfigElement() { return document.createElement("bosch-ebike-stats-card-editor"); }
  static getStubConfig() {
    return { show_distance: true, show_elevation: true, show_avg_speed: true, show_ride_count: true };
  }
  getCardSize() { return 6; }

  async _boot() {
    if (this._booting || this._ready) return;
    this._booting = true;
    try {
      this._buildDOM();
      this._ready = true;
      this._applyTitle();
      await this._fetchInstances();
      this._populateFilters();
      await this._loadActivities();
      this._render();
    } catch (err) {
      console.error("[Bosch eBike Stats] boot error", err);
      const msg = this.querySelector("#stats-msg");
      if (msg) msg.textContent = ebT(this._hass, "msg_error_prefix") + (err?.message || err);
    } finally {
      this._booting = false;
    }
  }

  _applyTitle() {
    const head = this.querySelector(".stats-head span");
    if (head && this._config && this._config.title) head.textContent = this._config.title;
  }

  _buildDOM() {
    this.innerHTML = "";
    const card = document.createElement("ha-card");
    this.appendChild(card);
    const style = document.createElement("style");
    style.textContent = `
      .stats-head {
        display:flex; align-items:center; gap:8px; padding:12px 16px;
        background:var(--primary-color,#03a9f4); color:#fff; font-size:16px; font-weight:500;
      }
      .stats-filters {
        display:flex; flex-wrap:wrap; gap:8px; padding:8px 12px;
        background:var(--secondary-background-color,#f5f5f5);
        border-bottom:1px solid var(--divider-color,#e0e0e0);
      }
      .stats-filters select {
        padding:5px 8px; border:1px solid var(--divider-color,#ccc);
        border-radius:6px; font-size:13px;
        background:var(--card-background-color,#fff); color:var(--primary-text-color,#333);
      }
      .stats-filter-lbl { font-size:12px; color:var(--secondary-text-color,#666); align-self:center; }
      .stats-body { padding:14px 16px; }
      .stats-legend { display:flex; flex-wrap:wrap; gap:10px; margin-bottom:12px; }
      .stats-legend-item { display:flex; align-items:center; gap:5px; font-size:11px; color:var(--secondary-text-color,#666); }
      .stats-legend-swatch { width:9px; height:9px; border-radius:2px; flex:none; }
      .stats-chart { margin-bottom:18px; }
      .stats-chart:last-child { margin-bottom:0; }
      .stats-chart-title { font-size:13px; font-weight:500; color:var(--primary-text-color,#333); margin-bottom:6px; }
      .stats-chart-unit { font-weight:400; color:var(--secondary-text-color,#888); }
      .stats-chart-body { display:flex; gap:6px; height:90px; }
      .stats-axis { position:relative; width:28px; flex:none; }
      .stats-axis-tick {
        position:absolute; left:0; right:0; transform:translateY(50%);
        font-size:9px; color:var(--secondary-text-color,#888); text-align:right;
      }
      .stats-bars { position:relative; flex:1; display:flex; align-items:flex-end; gap:3px; height:100%; }
      .stats-gridline {
        position:absolute; left:0; right:0; height:1px;
        background:var(--divider-color,#e0e0e0); transform:translateY(50%); z-index:0;
      }
      .stats-bar-wrap { position:relative; z-index:1; flex:1; display:flex; flex-direction:column; align-items:center; height:100%; justify-content:flex-end; }
      .stats-bar { width:100%; background:var(--primary-color,#03a9f4); border-radius:2px 2px 0 0; min-height:1px; }
      .stats-bar-group { width:100%; height:100%; display:flex; align-items:flex-end; gap:1px; }
      .stats-bar-sub { flex:1; border-radius:2px 2px 0 0; min-height:1px; }
      .stats-bar-label { font-size:9px; color:var(--secondary-text-color,#888); margin-top:3px; white-space:nowrap; }
      .stats-overlay { padding:18px 16px; color:var(--secondary-text-color,#999); font-size:13px; text-align:center; }
    `;
    card.appendChild(style);

    const t = (k, ...a) => ebT(this._hass, k, ...a);
    const wrap = document.createElement("div");
    wrap.innerHTML = `
      <div class="stats-head">
        <svg viewBox="0 0 24 24" width="22" height="22"><path fill="white" d="M22,21H2V3H4V19H6V10H10V19H12V6H16V19H18V14H22V21Z"/></svg>
        <span>${t("stats_title")}</span>
      </div>
      <div class="stats-filters">
        <span class="stats-filter-lbl" id="stats-acc-lbl" style="display:none;">${t("cal_account_label")}</span>
        <select id="stats-account" style="display:none;">
          <option value="all">${t("cal_account_label")}</option>
        </select>
        <span class="stats-filter-lbl" id="stats-bike-lbl" style="display:none;">${t("cal_bike_label")}</span>
        <select id="stats-bike" style="display:none;">
          <option value="all">${t("cal_bike_label")}</option>
        </select>
        <select id="stats-timeframe">
          <option value="weeks">${t("stats_weeks")}</option>
          <option value="months">${t("stats_months")}</option>
        </select>
      </div>
      <div class="stats-body" id="stats-body">
        <div class="stats-overlay" id="stats-msg">${t("cal_loading")}</div>
      </div>
    `;
    while (wrap.firstChild) card.appendChild(wrap.firstChild);

    this.querySelector("#stats-account").addEventListener("change", (e) => {
      this._filterAccount = e.target.value;
      if (!this._lockedBike) this._filterBike = "all";
      this._populateBikeFilter();
      this._render();
    });
    this.querySelector("#stats-bike").addEventListener("change", (e) => {
      this._filterBike = e.target.value;
      this._render();
    });
    const tfSel = this.querySelector("#stats-timeframe");
    tfSel.value = this._timeframe;
    tfSel.addEventListener("change", (e) => {
      this._timeframe = e.target.value;
      this._render();
    });
  }

  async _fetchInstances() {
    try {
      const res = await this._hass.callWS({ type: "bosch_ebike/list_instances" });
      this._instances = res.instances || [];
    } catch (_) { this._instances = []; }
  }

  async _loadActivities() {
    try {
      const res = await this._hass.callWS({ type: "bosch_ebike/list_activities" });
      this._activities = res.activities || [];
    } catch (err) {
      console.error("[Bosch eBike Stats] load_activities failed", err);
      this._activities = [];
    }
  }

  _populateFilters() {
    const accSel = this.querySelector("#stats-account");
    const accLbl = this.querySelector("#stats-acc-lbl");
    if (this._lockedAccount) {
      if (accSel) accSel.style.display = "none";
      if (accLbl) accLbl.style.display = "none";
    } else if (this._instances.length > 1) {
      const t = (k) => ebT(this._hass, k);
      const opts = [`<option value="all">${t("cal_account_label").replace(":", "")}</option>`];
      for (const inst of this._instances) {
        opts.push(`<option value="${this._escapeHtml(inst.config_entry_id)}">${this._escapeHtml(inst.label)}</option>`);
      }
      accSel.innerHTML = opts.join("");
      accSel.value = this._filterAccount;
      accSel.style.display = "";
      accLbl.style.display = "";
    }
    this._populateBikeFilter();
  }

  // Bikes visible under the current account filter, in stable order. Shared
  // by the bike-filter <select> and the per-bike chart breakdown so both
  // always agree on which bikes exist and in what order.
  _bikesInScope() {
    const bikes = [];
    for (const inst of this._instances) {
      if (this._filterAccount !== "all" && inst.config_entry_id !== this._filterAccount) continue;
      for (const b of (inst.bikes || [])) bikes.push(b);
    }
    return bikes;
  }

  _populateBikeFilter() {
    const bikeSel = this.querySelector("#stats-bike");
    const bikeLbl = this.querySelector("#stats-bike-lbl");
    if (this._lockedBike) {
      if (bikeSel) bikeSel.style.display = "none";
      if (bikeLbl) bikeLbl.style.display = "none";
      return;
    }
    const bikes = this._bikesInScope();
    if (bikes.length <= 1) {
      bikeSel.style.display = "none";
      bikeLbl.style.display = "none";
      return;
    }
    const t = (k) => ebT(this._hass, k);
    const opts = [`<option value="all">${t("cal_bike_label").replace(":", "")}</option>`];
    for (const b of bikes) {
      opts.push(`<option value="${this._escapeHtml(b.id)}">${this._escapeHtml(b.label)}</option>`);
    }
    bikeSel.innerHTML = opts.join("");
    bikeSel.value = this._filterBike;
    bikeSel.style.display = "";
    bikeLbl.style.display = "";
  }

  _escapeHtml(s) {
    return String(s || "").replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    })[c]);
  }

  _filteredActivities() {
    return (this._activities || []).filter((a) => {
      if (this._filterAccount !== "all" && a.accountId !== this._filterAccount) return false;
      if (this._filterBike !== "all" && a.bikeId !== this._filterBike) return false;
      return true;
    });
  }

  _render() {
    if (!this._ready) return;
    const body = this.querySelector("#stats-body");
    if (!body) return;
    const t = (k, ...a) => ebT(this._hass, k, ...a);

    const acts = this._filteredActivities();
    const buckets = statsComputeBuckets(this._timeframe, new Date());
    const totals = statsAggregateIntoBuckets(acts, buckets);

    const anyRides = totals.some((tt) => tt.rides > 0);
    if (!anyRides) {
      body.innerHTML = `<div class="stats-overlay">${t("stats_no_match")}</div>`;
      return;
    }

    const scopedBikes = this._filterBike === "all" ? this._bikesInScope() : [];
    const multiBike = scopedBikes.length >= 2;
    let perBike = [];
    if (multiBike) {
      const scopedIds = new Set(scopedBikes.map((b) => b.id));
      const groups = scopedBikes.map((b, i) => ({
        label: b.label,
        color: STATS_BIKE_COLORS[i % STATS_BIKE_COLORS.length],
        acts: acts.filter((a) => a.bikeId === b.id),
      }));
      // Activities the backend couldn't attribute to a specific bike (see
      // the "Unassigned Activities" diagnostic sensor) still count toward
      // the household totals/axis above - give them their own bar/legend
      // entry instead of silently dropping them from every bike's bar.
      const unassignedActs = acts.filter((a) => !scopedIds.has(a.bikeId));
      if (unassignedActs.length) {
        groups.push({ label: t("stats_bike_unassigned"), color: STATS_UNASSIGNED_COLOR, acts: unassignedActs });
      }
      perBike = groups.map((g) => ({ bike: g, totals: statsAggregateIntoBuckets(g.acts, buckets) }));
    }

    const legend = multiBike
      ? `<div class="stats-legend">${perBike.map((pb) => `
          <span class="stats-legend-item">
            <span class="stats-legend-swatch" style="background:${pb.bike.color}"></span>
            ${this._escapeHtml(pb.bike.label)}
          </span>`).join("")}</div>`
      : "";

    const cfg = this._config || {};
    const charts = [];
    for (const metric of STATS_METRICS) {
      if (cfg[metric.key] === false) continue; // absent key -> enabled by default
      const values = totals.map((tt) => metric.value(tt));
      const perBikeValues = perBike.map((pb) => pb.totals.map((tt) => metric.value(tt)));
      const rawMax = Math.max(...values, ...perBikeValues.flat(), 0);
      const { niceMax, ticks } = statsNiceTicks(rawMax);
      const scale = niceMax > 0 ? niceMax : 1;

      const bars = buckets.map((bucket, i) => {
        let barsHtml;
        if (multiBike) {
          barsHtml = perBike.map((pb, bi) => {
            const v = perBikeValues[bi][i];
            const pct = Math.max((v / scale) * 100, v > 0 ? 2 : 0);
            const title = `${this._escapeHtml(pb.bike.label)} - ${bucket.label}: ${v.toFixed(metric.digits)} ${t(metric.unitKey)}`;
            return `<div class="stats-bar-sub" style="height:${pct}%; background:${pb.bike.color}" title="${title}"></div>`;
          }).join("");
          barsHtml = `<div class="stats-bar-group">${barsHtml}</div>`;
        } else {
          const v = values[i];
          const pct = Math.max((v / scale) * 100, v > 0 ? 2 : 0);
          const title = `${bucket.label}: ${v.toFixed(metric.digits)} ${t(metric.unitKey)}`;
          barsHtml = `<div class="stats-bar" style="height:${pct}%" title="${this._escapeHtml(title)}"></div>`;
        }
        return `<div class="stats-bar-wrap">${barsHtml}<div class="stats-bar-label">${this._escapeHtml(bucket.label)}</div></div>`;
      }).join("");

      const zeroLabel = (0).toFixed(metric.digits);
      const topLabel = ticks[2].toFixed(metric.digits);
      const midLabel = ticks[1].toFixed(metric.digits);
      // A top label that rounds to zero (e.g. "0.0" for a few meters of
      // distance) is actively misleading, not just imprecise - omit the
      // numbers rather than show a fake-looking all-zero scale. A mid
      // label identical to the top label (e.g. both "1" for ticks 0.5/1
      // with an integer metric) is redundant, so it's dropped too.
      const showAxisLabels = niceMax > 0 && topLabel !== zeroLabel;
      const axis = showAxisLabels
        ? `<div class="stats-axis">
            <span class="stats-axis-tick" style="bottom:100%">${topLabel}</span>
            ${midLabel !== topLabel ? `<span class="stats-axis-tick" style="bottom:50%">${midLabel}</span>` : ""}
            <span class="stats-axis-tick" style="bottom:0%">0</span>
          </div>`
        : "";
      const gridlines = niceMax > 0
        ? `<div class="stats-gridline" style="bottom:100%"></div>
           <div class="stats-gridline" style="bottom:50%"></div>
           <div class="stats-gridline" style="bottom:0%"></div>`
        : "";

      charts.push(`<div class="stats-chart">
        <div class="stats-chart-title">${t(metric.labelKey)} <span class="stats-chart-unit">(${t(metric.unitKey)})</span></div>
        <div class="stats-chart-body">
          ${axis}
          <div class="stats-bars">${gridlines}${bars}</div>
        </div>
      </div>`);
    }
    body.innerHTML = charts.length
      ? legend + charts.join("")
      : `<div class="stats-overlay">${t("stats_no_match")}</div>`;
  }
}

class BoschEBikeStatsCardEditor extends BoschEBikeMapCardEditor {
  _render() {
    if (!this._config) return;
    const cfg = this._config;
    const inputStyle = "width:100%;padding:8px;border:1px solid #ccc;border-radius:4px;background:var(--card-background-color,#fff);color:var(--primary-text-color,#222);";
    const labelStyle = "display:block;margin-top:14px;margin-bottom:6px;font-weight:500";
    const hintStyle = "display:block;margin-top:4px;font-size:12px;color:var(--secondary-text-color,#777)";
    const t = (k, ...a) => ebT(this._hass, k, ...a);

    let accountOpts = `<option value="">${ebT(this._hass, "editor_select_all")}</option>`;
    for (const inst of (this._instances || [])) {
      const selected = cfg.account_id === inst.config_entry_id ? " selected" : "";
      accountOpts += `<option value="${this._escapeHtml(inst.config_entry_id)}"${selected}>${this._escapeHtml(inst.label)}</option>`;
    }

    let bikeOpts = `<option value="">${ebT(this._hass, "editor_select_all")}</option>`;
    for (const b of this._bikeOptionsForAccount(cfg.account_id)) {
      const selected = cfg.bike_id === b.id ? " selected" : "";
      bikeOpts += `<option value="${this._escapeHtml(b.id)}"${selected}>${this._escapeHtml(b.label)}</option>`;
    }

    this.innerHTML = `<div style="padding:16px">
      <label style="${labelStyle.replace('margin-top:14px;', '')}">${t("editor_title")}</label>
      <input type="text" value="${this._escapeHtml(cfg.title || '')}" placeholder="${t("stats_title")}" style="${inputStyle}" id="title-in">

      <label style="${labelStyle}">${t("editor_account_label")}</label>
      <select id="acc-in" style="${inputStyle}">${accountOpts}</select>
      <span style="${hintStyle}">${t("editor_account_hint")}</span>

      <label style="${labelStyle}">${t("editor_bike_label")}</label>
      <select id="bike-in" style="${inputStyle}">${bikeOpts}</select>
      <span style="${hintStyle}">${t("editor_bike_hint")}</span>

      <label style="${labelStyle}">${t("stats_editor_timeframe")}</label>
      <select id="timeframe-in" style="${inputStyle}">
        <option value="weeks"${cfg.default_timeframe !== "months" ? " selected" : ""}>${t("stats_weeks")}</option>
        <option value="months"${cfg.default_timeframe === "months" ? " selected" : ""}>${t("stats_months")}</option>
      </select>

      <label style="${labelStyle}">${t("stats_editor_metrics")}</label>
      <div>
        <input type="checkbox" id="show-distance-in"${cfg.show_distance !== false ? " checked" : ""} style="margin-right:8px;vertical-align:middle;">${t("stats_metric_distance")}<br>
        <input type="checkbox" id="show-elevation-in"${cfg.show_elevation !== false ? " checked" : ""} style="margin-right:8px;vertical-align:middle;">${t("stats_metric_elevation")}<br>
        <input type="checkbox" id="show-avg-speed-in"${cfg.show_avg_speed !== false ? " checked" : ""} style="margin-right:8px;vertical-align:middle;">${t("stats_metric_avg_speed")}<br>
        <input type="checkbox" id="show-ride-count-in"${cfg.show_ride_count !== false ? " checked" : ""} style="margin-right:8px;vertical-align:middle;">${t("stats_metric_ride_count")}
      </div>
    </div>`;

    this.querySelector("#title-in").addEventListener("change", (e) => {
      const v = e.target.value.trim();
      this._config = { ...this._config };
      if (v) this._config.title = v; else delete this._config.title;
      this._emit();
    });
    this.querySelector("#acc-in").addEventListener("change", (e) => {
      const v = e.target.value;
      this._config = { ...this._config };
      if (v) this._config.account_id = v; else delete this._config.account_id;
      delete this._config.bike_id;
      this._emit();
      this._render();
    });
    this.querySelector("#bike-in").addEventListener("change", (e) => {
      const v = e.target.value;
      this._config = { ...this._config };
      if (v) this._config.bike_id = v; else delete this._config.bike_id;
      this._emit();
    });
    this.querySelector("#timeframe-in").addEventListener("change", (e) => {
      this._config = { ...this._config, default_timeframe: e.target.value };
      this._emit();
    });
    for (const [id, key] of [
      ["show-distance-in", "show_distance"],
      ["show-elevation-in", "show_elevation"],
      ["show-avg-speed-in", "show_avg_speed"],
      ["show-ride-count-in", "show_ride_count"],
    ]) {
      this.querySelector(`#${id}`).addEventListener("change", (e) => {
        this._config = { ...this._config, [key]: e.target.checked };
        this._emit();
      });
    }
  }
}

// ===========================================================================
// Dashboard card: user-uploaded image + live ESPHome data + smart-plug control
// ===========================================================================
// Bosch internal assist-mode application codes -> display name. Mirrors the
// integration's profile_extra mapping; used as a frontend fallback so that
// older integration builds (whose reachable-range entity_id still carries the
// raw code, e.g. "…_reachable_range_a100m0auto") still show a clean label and
// match the default colours.
const BOSCH_ASSIST_MODE_NAMES = {
  A100M00040: "ECO",
  A100ECOP37: "ECO+",
  A100M00030: "TOUR",
  A100MAAAA0: "TOUR+",
  A100M00020: "SPORT",
  A100M00010: "TURBO",
  A100M0AUTO: "AUTO",
  A100EAAAB0: "eMTB",
  A100MSPIC7: "eMTB+",
  A100MAAAB0: "eMTB-shortcrank",
};

// --- Bosch assist-mode colours (range pills) --------------------------------
// Vivid, Bosch-Flow-typical palette. Keys are stable config tokens; the hex
// values approximate the colours the Flow app offers for custom ride modes.
const BOSCH_MODE_COLORS = {
  red: "#E2231A",
  orange: "#F39200",
  yellow: "#FFC107",
  green: "#5FB733",
  turquoise: "#00B3C8",
  blue: "#1E9FE0",
  purple: "#8A4FD3",
  magenta: "#E5006D",
  grey: "#8C9196",
};
const BOSCH_MODE_COLOR_ORDER = [
  "red", "orange", "yellow", "green", "turquoise", "blue", "purple", "magenta", "grey",
];
// Default mode-name -> colour key, matching the Flow app look out of the box.
// Keyed by the display name the integration emits (see profile_extra).
const BOSCH_MODE_DEFAULT_COLOR = {
  TURBO: "red",
  SPRINT: "purple",
  SPORT: "orange",
  "eMTB+": "purple",
  eMTB: "purple",
  "eMTB-shortcrank": "purple",
  AUTO: "blue",
  TOUR: "green",
  "TOUR+": "turquoise",
  ECO: "yellow",
  "ECO+": "yellow",
};
// Default display order of the range pills, by assist level — matches the order
// shown on the bike (ECO, TOUR, eMTB/SPORT, TURBO). Used when the user has not
// defined an explicit order via `mode_order`. Unknown modes sort last.
const BOSCH_MODE_DEFAULT_ORDER = {
  ECO: 1, "ECO+": 2,
  TOUR: 3, "TOUR+": 4,
  SPORT: 5, eMTB: 6, "eMTB+": 7, "eMTB-shortcrank": 8,
  SPRINT: 9,
  TURBO: 10,
  AUTO: 11,
};

// Black/white text for a given background hex via the YIQ contrast rule.
function boschContrastColor(hex) {
  const m = /^#?([0-9a-fA-F]{6})$/.exec(hex || "");
  if (!m) return "#ffffff";
  const n = parseInt(m[1], 16);
  const r = (n >> 16) & 255, g = (n >> 8) & 255, b = n & 255;
  const yiq = (r * 299 + g * 587 + b * 114) / 1000;
  return yiq >= 150 ? "#1c1c1c" : "#ffffff";
}

// Resolve a mode name to a hex colour: explicit config wins, else the Bosch
// default for that mode, else null (render as a neutral pill).
function boschModeColorHex(modeName, modeColorsCfg) {
  const cfg = modeColorsCfg || {};
  const key = cfg[modeName] || BOSCH_MODE_DEFAULT_COLOR[modeName];
  return (key && BOSCH_MODE_COLORS[key]) ? BOSCH_MODE_COLORS[key] : null;
}

// Derive the assist-mode label of a reachable-range entity. Prefers the clean
// `assist_mode` attribute (e.g. "AUTO"); falls back to the friendly name
// ("… Reachable Range AUTO") and finally the entity_id suffix, so the card
// still works on older integration builds that predate the attribute.
function boschModeLabel(eid, attrs) {
  const a = attrs || {};
  let label = null;
  if (a.assist_mode != null && String(a.assist_mode).trim()) {
    label = String(a.assist_mode).trim();
  } else {
    const fn = a.friendly_name ? String(a.friendly_name) : "";
    const m = /reachable\s*range\s+(.+)$/i.exec(fn);
    if (m && m[1].trim()) {
      label = m[1].trim();
    } else {
      const m2 = /reachable_range_(.+)$/.exec(eid);
      if (m2 && m2[1]) label = m2[1].toUpperCase();
    }
  }
  if (!label) return null;
  // Normalise a raw Bosch code to its display name (no-op for clean labels).
  return BOSCH_ASSIST_MODE_NAMES[label.toUpperCase()] || label;
}

// Auto-detect the per-mode reachable-range sensors of one bike. They are the
// entities with `reachable_range` in the id (state = km); the mode label comes
// from boschModeLabel (attribute or name). Detection does NOT require the
// `assist_mode` attribute, so it works across integration versions. When an
// anchor entity (battery/odometer) is set, results are PREFERRED on that bike's
// device, but if nothing matches that device (e.g. the range sensors live on a
// separate "drive unit" device) we fall back to all matches instead of showing
// none. Sorted by entity_id so the order matches the integration sensor order.
function boschReachableRanges(hass, anchorEntityId, bikeId, modeOrder) {
  if (!hass || !hass.states) return [];
  const reg = hass.entities || null;

  // Resolve the device whose pills we want. A configured bike_id is
  // authoritative (issue #39: a card pinned to one bike must NOT show other
  // bikes' ranges): find the integration device with identifier
  // (ha_bosch_ebike, bike_id) and filter STRICTLY to it. The anchor entity
  // (odometer/battery) is only a fallback for the auto-discover case (no
  // bike_id resolvable), where range sensors may sit on a separate device.
  let targetDevice = null;
  let strict = false;
  if (bikeId && hass.devices) {
    for (const [devId, dev] of Object.entries(hass.devices)) {
      const ids = (dev && dev.identifiers) || [];
      if (ids.some((t) => Array.isArray(t)
          && t[0] === "ha_bosch_ebike" && t[1] === bikeId)) {
        targetDevice = devId;
        strict = true;
        break;
      }
    }
  }
  if (!targetDevice && anchorEntityId && reg && reg[anchorEntityId]) {
    targetDevice = reg[anchorEntityId].device_id || null;
  }

  const all = [];
  for (const [eid, st] of Object.entries(hass.states)) {
    if (!/reachable_range/.test(eid)) continue;
    const a = (st && st.attributes) || {};
    const mode = boschModeLabel(eid, a);
    if (!mode) continue;
    const km = Number(st.state);
    const dev = (reg && reg[eid]) ? (reg[eid].device_id || null) : null;
    all.push({
      entity_id: eid,
      mode,
      km: Number.isFinite(km) ? km : null,
      device_id: dev,
    });
  }
  // Order: explicit user order (mode_order) first and in that order, then the
  // default order by assist level (ECO, TOUR, eMTB/SPORT, TURBO — like on the
  // bike), then entity_id as a stable tiebreaker.
  const userIdx = (m) => {
    if (Array.isArray(modeOrder)) {
      const i = modeOrder.indexOf(m);
      if (i >= 0) return i;
    }
    return -1;
  };
  all.sort((x, y) => {
    const ux = userIdx(x.mode), uy = userIdx(y.mode);
    if (ux !== uy) {
      if (ux === -1) return 1;
      if (uy === -1) return -1;
      return ux - uy;
    }
    const rx = BOSCH_MODE_DEFAULT_ORDER[x.mode] ?? 99;
    const ry = BOSCH_MODE_DEFAULT_ORDER[y.mode] ?? 99;
    if (rx !== ry) return rx - ry;
    return x.entity_id.localeCompare(y.entity_id);
  });
  let chosen = all;
  if (targetDevice) {
    const same = all.filter((r) => r.device_id === targetDevice);
    // strict (bike_id pinned): only that bike, even if that means none.
    // non-strict (anchor only): prefer the anchor's device, but fall back to
    // all when nothing matches (range sensors on a separate drive-unit device).
    if (same.length || strict) chosen = same;
  }
  return chosen.map(({ device_id, ...r }) => r);
}

// ===========================================================================
// Trick List card: sortable table of every recorded jump/manual/stoppie/
// wheelie (issue #65 follow-up). Bosch's `tricks` API field is a per-RIDE
// aggregate per trick type (amount + max distance/duration/height-or-angle
// for that ride, see trick_check.py's docstring - confirmed via a real
// diagnostics dump, no per-event GPS or timestamp exists to list instead),
// so "one row per trick" is approximated as one row per (ride, trick type)
// that actually happened - a ride with both a jump and two wheelies becomes
// two rows, each carrying that type's own full stat set.
// ===========================================================================

const TRICKLIST_TYPES = ["jumps", "manuals", "stoppies", "wheelies"];

// {type -> i18n key} for the already-existing per-type labels (see the
// trick tooltip on the map card) - reused as-is rather than duplicated.
const TRICKLIST_TYPE_LABEL_KEY = {
  jumps: "trick_jump",
  manuals: "trick_manual",
  stoppies: "trick_stoppie",
  wheelies: "trick_wheelie",
};

// Flattens activities into one row per (ride, trick type) with amount > 0.
// Pure and DOM-free so it can be verified standalone (see this session's
// scratchpad verify_trick_list.mjs) before being pasted here.
function trickListBuildRows(activities) {
  const rows = [];
  for (const a of (activities || [])) {
    const tc = a && a.trickCheck;
    if (!tc || !tc.has_any) continue;
    for (const type of TRICKLIST_TYPES) {
      const t = tc[type];
      if (!t || !(t.amount > 0)) continue;
      rows.push({
        activityId: a.id,
        startTime: a.startTime,
        title: a.title || "",
        bikeId: a.bikeId,
        type,
        amount: t.amount,
        maxDistanceM: Number.isFinite(t.max_distance_m) ? t.max_distance_m : null,
        maxDurationS: Number.isFinite(t.max_duration_s) ? t.max_duration_s : null,
        maxHeightM: Number.isFinite(t.max_height_m) ? t.max_height_m : null,
        maxAngleDeg: Number.isFinite(t.max_angle_deg) ? t.max_angle_deg : null,
      });
    }
  }
  return rows;
}

// Column definitions: `value` extracts the sort key (a locale-aware string
// resolver is passed in separately for the two label columns, since their
// display text depends on ebT()/bike-label lookups the pure row itself
// doesn't carry). `numeric` marks columns whose N/A cells (null) must
// always sort last regardless of direction - a "-" is neither the smallest
// nor the largest real value for that stat, so it must never interleave
// with actual numbers at either end of a numeric sort.
const TRICKLIST_COLUMNS = [
  {
    key: "startTime", labelKey: "tricklist_col_date", numeric: false,
    // A missing/invalid startTime must resolve to null, not epoch 0 - only
    // null gets trickListSort's "always sorts to the end, either direction"
    // treatment (see its own comment and README's documented promise for
    // this table); epoch 0 sorts as a real, extremely old timestamp and
    // would pin such a row at the very top the moment the date column is
    // sorted ascending, contradicting the "-" placeholder its own render
    // cell already shows for the exact same row.
    value: (r) => {
      const t = Date.parse(r.startTime);
      return Number.isNaN(t) ? null : t;
    },
  },
  { key: "title", labelKey: "tricklist_col_ride", numeric: false, value: (r) => (r.title || "").toLowerCase() },
  { key: "bike", labelKey: "tricklist_col_bike", numeric: false, value: (r, ctx) => (ctx.bikeLabel(r.bikeId) || "").toLowerCase() },
  { key: "type", labelKey: "tricklist_col_trick", numeric: false, value: (r, ctx) => (ctx.typeLabel(r.type) || "").toLowerCase() },
  { key: "amount", labelKey: "tricklist_col_amount", numeric: true, value: (r) => r.amount },
  { key: "maxDistanceM", labelKey: "tricklist_col_distance", numeric: true, value: (r) => r.maxDistanceM },
  { key: "maxDurationS", labelKey: "tricklist_col_duration", numeric: true, value: (r) => r.maxDurationS },
  { key: "maxHeightM", labelKey: "tricklist_col_height", numeric: true, value: (r) => r.maxHeightM },
  { key: "maxAngleDeg", labelKey: "tricklist_col_angle", numeric: true, value: (r) => r.maxAngleDeg },
];

// Sorts `rows` in place by the given column (see TRICKLIST_COLUMNS) and
// direction ("asc" | "desc"). `ctx` supplies the two label resolvers the
// bike/type columns need. Null values (a stat that doesn't apply to this
// row's trick type, e.g. maxHeightM on a wheelie) always sort to the very
// end, independent of `dir` - see TRICKLIST_COLUMNS' comment for why.
function trickListSort(rows, columnKey, dir, ctx) {
  const col = TRICKLIST_COLUMNS.find((c) => c.key === columnKey) || TRICKLIST_COLUMNS[0];
  const sign = dir === "asc" ? 1 : -1;
  rows.sort((a, b) => {
    const av = col.value(a, ctx);
    const bv = col.value(b, ctx);
    const aNull = av === null || av === undefined;
    const bNull = bv === null || bv === undefined;
    if (aNull && bNull) return 0;
    if (aNull) return 1;
    if (bNull) return -1;
    if (av < bv) return -1 * sign;
    if (av > bv) return 1 * sign;
    return 0;
  });
  return rows;
}

class BoschEBikeTrickListCard extends HTMLElement {
  constructor() {
    super();
    this._hass = null;
    this._config = {};
    this._activities = [];
    this._instances = [];
    this._filterAccount = "all";
    this._filterBike = "all";
    this._sortColumn = "startTime";
    this._sortDir = "desc";
    this._lockedAccount = false;
    this._lockedBike = false;
    this._ready = false;
    this._booting = false;
  }

  setConfig(config) {
    this._config = { ...config };
    if (config.account_id) { this._filterAccount = config.account_id; this._lockedAccount = true; }
    else { this._lockedAccount = false; }
    if (config.bike_id) { this._filterBike = config.bike_id; this._lockedBike = true; }
    else { this._lockedBike = false; }
    if (this._ready) {
      this._applyTitle();
      this._populateFilters();
      this._render();
    }
  }

  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    if (first) this._boot();
  }

  static getConfigElement() { return document.createElement("bosch-ebike-trick-list-card-editor"); }
  static getStubConfig() { return {}; }
  getCardSize() { return 6; }

  async _boot() {
    if (this._booting || this._ready) return;
    this._booting = true;
    try {
      this._buildDOM();
      this._ready = true;
      this._applyTitle();
      await this._fetchInstances();
      this._populateFilters();
      await this._loadActivities();
      this._render();
    } catch (err) {
      console.error("[Bosch eBike Trick List] boot error", err);
      const msg = this.querySelector("#trklist-msg");
      if (msg) msg.textContent = ebT(this._hass, "msg_error_prefix") + (err?.message || err);
    } finally {
      this._booting = false;
    }
  }

  _applyTitle() {
    const head = this.querySelector(".trklist-head span");
    if (head && this._config && this._config.title) head.textContent = this._config.title;
  }

  _buildDOM() {
    this.innerHTML = "";
    const card = document.createElement("ha-card");
    this.appendChild(card);
    const style = document.createElement("style");
    style.textContent = `
      .trklist-head {
        display:flex; align-items:center; gap:8px; padding:12px 16px;
        background:var(--primary-color,#03a9f4); color:#fff; font-size:16px; font-weight:500;
      }
      .trklist-filters {
        display:flex; flex-wrap:wrap; gap:8px; padding:8px 12px;
        background:var(--secondary-background-color,#f5f5f5);
        border-bottom:1px solid var(--divider-color,#e0e0e0);
      }
      .trklist-filters select {
        padding:5px 8px; border:1px solid var(--divider-color,#ccc);
        border-radius:6px; font-size:13px;
        background:var(--card-background-color,#fff); color:var(--primary-text-color,#333);
      }
      .trklist-filter-lbl { font-size:12px; color:var(--secondary-text-color,#666); align-self:center; }
      .trklist-summary { padding:8px 16px 0; font-size:12px; color:var(--secondary-text-color,#666); }
      .trklist-scroll { overflow-x:auto; padding:10px 16px 16px; }
      .trklist-table { border-collapse:collapse; width:100%; font-size:13px; white-space:nowrap; }
      .trklist-table th, .trklist-table td { padding:6px 10px; text-align:left; }
      .trklist-table th {
        cursor:pointer; user-select:none; font-weight:500;
        color:var(--secondary-text-color,#666); border-bottom:2px solid var(--divider-color,#e0e0e0);
      }
      .trklist-table th.num, .trklist-table td.num { text-align:right; font-variant-numeric:tabular-nums; }
      .trklist-table th.active { color:var(--primary-text-color,#222); }
      .trklist-table td { border-bottom:1px solid var(--divider-color,#eee); }
      .trklist-table tbody tr:hover { background:var(--secondary-background-color,#f5f5f5); }
      .trklist-table td.title-cell { max-width:220px; overflow:hidden; text-overflow:ellipsis; }
      .trklist-overlay { padding:18px 16px; color:var(--secondary-text-color,#999); font-size:13px; text-align:center; }
      @media (prefers-color-scheme: dark) {
        .trklist-table tbody tr:hover { background:rgba(255,255,255,0.06); }
      }
    `;
    card.appendChild(style);

    const t = (k, ...a) => ebT(this._hass, k, ...a);
    const wrap = document.createElement("div");
    wrap.innerHTML = `
      <div class="trklist-head">
        <svg viewBox="0 0 24 24" width="22" height="22"><path fill="white" d="M13.13,22.19L11.5,18.36C13.07,17.78 14.54,17 15.9,16.09L13.13,22.19M5.64,12.5L1.81,10.87L7.91,8.1C7,9.46 6.22,10.93 5.64,12.5M21.61,2.39C21.61,2.39 16.66,0.269 11.61,5.319C9.6,7.329 8.54,9.36 7.5,10.36C6.65,11.21 5.35,11.5 5.35,11.5L2.5,14.35C1.5,15.35 2.5,17.5 3.5,18.5C4.5,19.5 6.65,20.5 7.65,19.5L10.5,16.65C10.5,16.65 10.79,15.35 11.64,14.5C12.64,13.46 14.67,12.4 16.68,10.39C21.73,5.34 21.61,2.39 21.61,2.39Z"/></svg>
        <span>${t("tricklist_title")}</span>
      </div>
      <div class="trklist-filters">
        <span class="trklist-filter-lbl" id="trklist-acc-lbl" style="display:none;">${t("cal_account_label")}</span>
        <select id="trklist-account" style="display:none;">
          <option value="all">${t("cal_account_label")}</option>
        </select>
        <span class="trklist-filter-lbl" id="trklist-bike-lbl" style="display:none;">${t("cal_bike_label")}</span>
        <select id="trklist-bike" style="display:none;">
          <option value="all">${t("cal_bike_label")}</option>
        </select>
      </div>
      <div class="trklist-summary" id="trklist-summary"></div>
      <div class="trklist-scroll" id="trklist-body">
        <div class="trklist-overlay" id="trklist-msg">${t("cal_loading")}</div>
      </div>
    `;
    while (wrap.firstChild) card.appendChild(wrap.firstChild);

    this.querySelector("#trklist-account").addEventListener("change", (e) => {
      this._filterAccount = e.target.value;
      if (!this._lockedBike) this._filterBike = "all";
      this._populateBikeFilter();
      this._render();
    });
    this.querySelector("#trklist-bike").addEventListener("change", (e) => {
      this._filterBike = e.target.value;
      this._render();
    });
  }

  async _fetchInstances() {
    try {
      const res = await this._hass.callWS({ type: "bosch_ebike/list_instances" });
      this._instances = res.instances || [];
    } catch (_) { this._instances = []; }
  }

  async _loadActivities() {
    try {
      const res = await this._hass.callWS({ type: "bosch_ebike/list_activities" });
      this._activities = res.activities || [];
    } catch (err) {
      console.error("[Bosch eBike Trick List] load_activities failed", err);
      this._activities = [];
    }
  }

  _populateFilters() {
    const accSel = this.querySelector("#trklist-account");
    const accLbl = this.querySelector("#trklist-acc-lbl");
    if (this._lockedAccount) {
      if (accSel) accSel.style.display = "none";
      if (accLbl) accLbl.style.display = "none";
    } else if (this._instances.length > 1) {
      const t = (k) => ebT(this._hass, k);
      const opts = [`<option value="all">${t("cal_account_label").replace(":", "")}</option>`];
      for (const inst of this._instances) {
        opts.push(`<option value="${this._escapeHtml(inst.config_entry_id)}">${this._escapeHtml(inst.label)}</option>`);
      }
      accSel.innerHTML = opts.join("");
      accSel.value = this._filterAccount;
      accSel.style.display = "";
      accLbl.style.display = "";
    }
    this._populateBikeFilter();
  }

  // Bikes visible under the current account filter, in stable order - also
  // used to resolve a row's bikeId into a display label (see _bikeLabel()).
  _bikesInScope() {
    const bikes = [];
    for (const inst of this._instances) {
      if (this._filterAccount !== "all" && inst.config_entry_id !== this._filterAccount) continue;
      for (const b of (inst.bikes || [])) bikes.push(b);
    }
    return bikes;
  }

  _populateBikeFilter() {
    const bikeSel = this.querySelector("#trklist-bike");
    const bikeLbl = this.querySelector("#trklist-bike-lbl");
    if (this._lockedBike) {
      if (bikeSel) bikeSel.style.display = "none";
      if (bikeLbl) bikeLbl.style.display = "none";
      return;
    }
    const bikes = this._bikesInScope();
    if (bikes.length <= 1) {
      bikeSel.style.display = "none";
      bikeLbl.style.display = "none";
      return;
    }
    const t = (k) => ebT(this._hass, k);
    const opts = [`<option value="all">${t("cal_bike_label").replace(":", "")}</option>`];
    for (const b of bikes) {
      opts.push(`<option value="${this._escapeHtml(b.id)}">${this._escapeHtml(b.label)}</option>`);
    }
    bikeSel.innerHTML = opts.join("");
    bikeSel.value = this._filterBike;
    bikeSel.style.display = "";
    bikeLbl.style.display = "";
  }

  _escapeHtml(s) {
    return String(s || "").replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    })[c]);
  }

  _filteredActivities() {
    return (this._activities || []).filter((a) => {
      if (this._filterAccount !== "all" && a.accountId !== this._filterAccount) return false;
      if (this._filterBike !== "all" && a.bikeId !== this._filterBike) return false;
      return true;
    });
  }

  // bikeId -> display label, "" for an unattributed ride (the "Bike" column
  // then simply shows blank rather than a raw uuid or a misleading guess).
  _bikeLabel(bikeId) {
    if (!bikeId) return "";
    const found = this._bikesInScope().find((b) => b.id === bikeId);
    return found ? found.label : "";
  }

  _typeLabel(type) {
    return ebT(this._hass, TRICKLIST_TYPE_LABEL_KEY[type] || type);
  }

  _render() {
    if (!this._ready) return;
    const body = this.querySelector("#trklist-body");
    const summary = this.querySelector("#trklist-summary");
    if (!body) return;
    const t = (k, ...a) => ebT(this._hass, k, ...a);

    const rows = trickListBuildRows(this._filteredActivities());
    if (!rows.length) {
      body.innerHTML = `<div class="trklist-overlay">${t("tricklist_no_match")}</div>`;
      summary.innerHTML = "";
      return;
    }

    const ctx = { bikeLabel: (id) => this._bikeLabel(id), typeLabel: (ty) => this._typeLabel(ty) };
    trickListSort(rows, this._sortColumn, this._sortDir, ctx);

    summary.textContent = t("tricklist_summary_count", rows.length);

    // Hide once the table itself is already narrowed to one bike (dropdown
    // pick or a config-locked bike_id) - showing a column that repeats the
    // same name on every row is dead weight. Mirrors the exact same
    // "_filterBike === 'all'" gate BoschEBikeStatsCard and BoschEBikeMapCard
    // already use for the analogous decision.
    const showBikeCol = this._filterBike === "all" && this._bikesInScope().length > 1;
    const dateFmt = new Intl.DateTimeFormat(this._hassLocale(), {
      year: "numeric", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
    });
    const na = "–"; // en dash, matches the existing "-" placeholder convention elsewhere in this card

    const columns = TRICKLIST_COLUMNS.filter((c) => c.key !== "bike" || showBikeCol);
    const headHtml = columns.map((c) => {
      const active = c.key === this._sortColumn;
      const arrow = active ? (this._sortDir === "asc" ? " ▲" : " ▼") : "";
      return `<th class="${c.numeric ? "num " : ""}${active ? "active" : ""}" data-col="${c.key}">${t(c.labelKey)}${arrow}</th>`;
    }).join("");

    const bodyRows = rows.map((r) => {
      const cells = [];
      for (const c of columns) {
        let text;
        switch (c.key) {
          case "startTime": {
            // A missing/malformed startTime must degrade to "-", not throw
            // and blank the whole table - Intl.DateTimeFormat.format()
            // throws on an Invalid Date, and new Date(undefined) is exactly
            // that (same guard shape as BoschEBikeCalendarCard's
            // _aggregateByDay for the same field).
            const parsed = r.startTime ? new Date(r.startTime) : null;
            text = parsed && !isNaN(parsed.getTime())
              ? this._escapeHtml(dateFmt.format(parsed))
              : na;
            break;
          }
          case "title": text = `<span title="${this._escapeHtml(r.title)}">${this._escapeHtml(r.title || na)}</span>`; break;
          case "bike": text = this._escapeHtml(this._bikeLabel(r.bikeId) || na); break;
          case "type": text = this._escapeHtml(this._typeLabel(r.type)); break;
          case "amount": text = String(r.amount); break;
          case "maxDistanceM": text = r.maxDistanceM != null ? r.maxDistanceM.toFixed(1) : na; break;
          case "maxDurationS": text = r.maxDurationS != null ? r.maxDurationS.toFixed(2) : na; break;
          case "maxHeightM": text = r.maxHeightM != null ? r.maxHeightM.toFixed(2) : na; break;
          case "maxAngleDeg": text = r.maxAngleDeg != null ? r.maxAngleDeg.toFixed(1) : na; break;
          default: text = na;
        }
        const cls = [c.numeric ? "num" : "", c.key === "title" ? "title-cell" : ""].filter(Boolean).join(" ");
        cells.push(`<td${cls ? ` class="${cls}"` : ""}>${text}</td>`);
      }
      return `<tr>${cells.join("")}</tr>`;
    }).join("");

    body.innerHTML = `
      <table class="trklist-table">
        <thead><tr>${headHtml}</tr></thead>
        <tbody>${bodyRows}</tbody>
      </table>
    `;

    for (const th of body.querySelectorAll("th[data-col]")) {
      th.addEventListener("click", () => {
        const col = th.getAttribute("data-col");
        if (this._sortColumn === col) {
          this._sortDir = this._sortDir === "asc" ? "desc" : "asc";
        } else {
          this._sortColumn = col;
          // A fresh column starts in its most useful direction: newest-
          // first for the date column, biggest-first for every numeric
          // stat (nobody opens a personal-bests table wanting the smallest
          // jump on top), alphabetical for the two label columns.
          const startCol = TRICKLIST_COLUMNS.find((c) => c.key === col);
          this._sortDir = (col === "startTime" || (startCol && startCol.numeric)) ? "desc" : "asc";
        }
        this._render();
      });
    }
  }

  _hassLocale() {
    if (this._hass && this._hass.locale && this._hass.locale.language) {
      return this._hass.locale.language;
    }
    return (this._hass && this._hass.language) || navigator.language || "en-GB";
  }
}

class BoschEBikeTrickListCardEditor extends BoschEBikeMapCardEditor {
  _render() {
    if (!this._config) return;
    const cfg = this._config;
    const inputStyle = "width:100%;padding:8px;border:1px solid #ccc;border-radius:4px;background:var(--card-background-color,#fff);color:var(--primary-text-color,#222);";
    const labelStyle = "display:block;margin-top:14px;margin-bottom:6px;font-weight:500";
    const hintStyle = "display:block;margin-top:4px;font-size:12px;color:var(--secondary-text-color,#777)";
    const t = (k, ...a) => ebT(this._hass, k, ...a);

    let accountOpts = `<option value="">${ebT(this._hass, "editor_select_all")}</option>`;
    for (const inst of (this._instances || [])) {
      const selected = cfg.account_id === inst.config_entry_id ? " selected" : "";
      accountOpts += `<option value="${this._escapeHtml(inst.config_entry_id)}"${selected}>${this._escapeHtml(inst.label)}</option>`;
    }

    let bikeOpts = `<option value="">${ebT(this._hass, "editor_select_all")}</option>`;
    for (const b of this._bikeOptionsForAccount(cfg.account_id)) {
      const selected = cfg.bike_id === b.id ? " selected" : "";
      bikeOpts += `<option value="${this._escapeHtml(b.id)}"${selected}>${this._escapeHtml(b.label)}</option>`;
    }

    this.innerHTML = `<div style="padding:16px">
      <label style="${labelStyle.replace('margin-top:14px;', '')}">${t("editor_title")}</label>
      <input type="text" value="${this._escapeHtml(cfg.title || '')}" placeholder="${t("tricklist_title")}" style="${inputStyle}" id="title-in">

      <label style="${labelStyle}">${t("editor_account_label")}</label>
      <select id="acc-in" style="${inputStyle}">${accountOpts}</select>
      <span style="${hintStyle}">${t("editor_account_hint")}</span>

      <label style="${labelStyle}">${t("editor_bike_label")}</label>
      <select id="bike-in" style="${inputStyle}">${bikeOpts}</select>
      <span style="${hintStyle}">${t("editor_bike_hint")}</span>
    </div>`;

    this.querySelector("#title-in").addEventListener("change", (e) => {
      const v = e.target.value.trim();
      this._config = { ...this._config };
      if (v) this._config.title = v; else delete this._config.title;
      this._emit();
    });
    this.querySelector("#acc-in").addEventListener("change", (e) => {
      const v = e.target.value;
      this._config = { ...this._config };
      if (v) this._config.account_id = v; else delete this._config.account_id;
      delete this._config.bike_id;
      this._emit();
      this._render();
    });
    this.querySelector("#bike-in").addEventListener("change", (e) => {
      const v = e.target.value;
      this._config = { ...this._config };
      if (v) this._config.bike_id = v; else delete this._config.bike_id;
      this._emit();
    });
  }
}

class BoschEBikeDashboardCard extends HTMLElement {
  constructor() {
    super();
    this._hass = null;
    this._config = {};
    this._built = false;
    this._pendingStop = false;
    this._pendingStopTimer = null;
    // Maintenance items live in HA storage now (was localStorage +
    // card-config in v1.16.5). Backend is the source of truth, this
    // is a local cache to avoid a WebSocket roundtrip on every
    // _render(). Invalidated by mutations and reloaded on demand.
    this._maintItems = null;
    this._maintLoadedFor = null;
    this._maintLoading = false;
    this._maintMigrated = false;
  }

  setConfig(config) {
    if (!config) throw new Error("Invalid configuration");
    this._config = { ...config };
    if (this._built) { this._applyStatic(); this._render(); }
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._built) this._build();
    if (!this._maintBusHandler) {
      // Wartungs-Änderungen aus einem offenen Editor (oder einer
      // zweiten Dashboard-Card) bekommen wir per _cardSettingsBus
      // mit. Wir invalidieren den lokalen Cache und ziehen die
      // aktuelle Liste vom Backend. Ohne diese Subscription blieben
      // hinzugefügte / geänderte Items unsichtbar bis zum nächsten
      // Bike-Wechsel oder Page-Reload.
      this._maintBusHandler = () => {
        this._maintLoadedFor = null;
        // Reload auch im Auto-Discover-Fall (keine bike_id konfiguriert)
        // - _loadMaintenance entscheidet selbst, ob es matched oder
        // automatisch das einzige Bike mit Items nimmt.
        this._loadMaintenance(this._config.bike_id || null);
        // Re-Render der "fällige Wartung"-Sektion: die Warnschwellen
        // koennen sich geaendert haben, auch wenn die Items selbst
        // gleich blieben.
        this._render();
      };
      _cardSettingsBus.addEventListener("changed", this._maintBusHandler);
    }
    // Shared-Card-Settings einmalig nachladen. Enthaelt u.a. die
    // Warnschwellen maint_warn_km / maint_warn_days. Ohne diesen
    // Call laefe _maintStatus nach jedem Browser-Reload auf die
    // Defaults 500/30 zurueck - der Bus feuert nur bei Writes von
    // anderen Cards/Editoren, nicht beim initialen Mount.
    if (!this._sharedSettingsRequested) {
      this._sharedSettingsRequested = true;
      ensureCardSettingsLoaded(hass).then(() => this._render()).catch(() => {});
    }
    this._render();
  }

  disconnectedCallback() {
    if (this._maintBusHandler) {
      _cardSettingsBus.removeEventListener("changed", this._maintBusHandler);
      this._maintBusHandler = null;
    }
  }

  static getConfigElement() { return document.createElement("bosch-ebike-dashboard-card-editor"); }
  static getStubConfig() {
    return {
      bike_image: "",
      odometer_entity: "",
      battery_entity: "",
      charging_entity: "",
    };
  }
  getCardSize() { return 6; }

  _t(key, ...args) {
    const lang = (this._hass && this._hass.language) ? this._hass.language.split("-")[0] : "en";
    const dict = (I18N && I18N[lang]) || I18N.en;
    const v = dict[key] != null ? dict[key] : I18N.en[key];
    return typeof v === "function" ? v(...args) : v;
  }

  _build() {
    this.innerHTML = "";
    const card = document.createElement("ha-card");
    this.appendChild(card);

    const style = document.createElement("style");
    style.textContent = `
      .dash-wrap { padding: 16px; box-sizing: border-box; }
      .dash-title {
        text-align: center; font-size: 20px; font-weight: 600;
        margin: 0 0 8px 0; color: var(--primary-text-color);
      }
      .dash-image-wrap {
        width: 100%; aspect-ratio: 16/10;
        display: flex; align-items: center; justify-content: center;
        background: var(--secondary-background-color, #f5f5f5);
        border-radius: 12px; overflow: hidden; margin-bottom: 14px;
      }
      .dash-image-wrap img { max-width: 100%; max-height: 100%; object-fit: contain; }
      .dash-no-image {
        text-align: center; padding: 16px; color: var(--secondary-text-color);
        font-size: 13px; line-height: 1.4;
      }
      .dash-no-image .ico {
        display: block; margin: 0 auto 8px; opacity: .5;
      }
      .dash-row {
        display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
        gap: 12px; margin-bottom: 12px;
      }
      .dash-tile {
        display: flex; flex-direction: column; align-items: center;
        gap: 4px; padding: 6px 4px;
      }
      .dash-tile ha-icon { --mdc-icon-size: 24px; color: var(--secondary-text-color); }
      .dash-tile ha-icon.accent { color: var(--primary-color, #03a9f4); }
      .dash-tile .val { font-size: 14px; font-weight: 500; color: var(--primary-text-color); }
      .dash-tile .lbl { font-size: 11px; color: var(--secondary-text-color); text-transform: uppercase; letter-spacing: .04em; }
      .dash-pills {
        display: flex; flex-wrap: wrap; gap: 10px; justify-content: center;
        margin: 6px 0 14px;
      }
      .dash-pill {
        display: inline-flex; align-items: center; gap: 6px;
        padding: 6px 12px; border-radius: 999px;
        background: var(--secondary-background-color, #f0f0f0);
        font-size: 13px; color: var(--primary-text-color);
      }
      .dash-pill ha-icon { --mdc-icon-size: 18px; }
      .dash-pill.charging { background: rgba(76,175,80,.18); color: #2e7d32; }
      .dash-pill.charging ha-icon { color: #2e7d32; }
      /* Remembered, no-longer-live SoC: dimmed and italic so it reads as an
         old reading at a glance, not as a current one (issue #65). */
      .dash-pill.stale { opacity: 0.6; font-style: italic; }
      /* Per-mode reachable-range pills (colour set inline per mode). */
      .dash-pill.range { gap: 8px; font-weight: 600; }
      .dash-pill.range .mode { letter-spacing: .02em; }
      .dash-pill.range .km { font-weight: 500; opacity: .92; font-variant-numeric: tabular-nums; }
      .dash-controls {
        display: flex; gap: 10px; margin: 14px 0 12px; flex-wrap: wrap;
      }
      .dash-btn {
        flex: 1 1 140px;
        display: inline-flex; align-items: center; justify-content: center; gap: 6px;
        padding: 10px 14px; border-radius: 10px; border: 0; cursor: pointer;
        font-size: 14px; font-weight: 500;
        background: var(--primary-color, #03a9f4); color: var(--text-primary-color, #fff);
        transition: filter .15s ease;
      }
      .dash-btn:hover { filter: brightness(1.08); }
      .dash-btn.stop { background: #e53935; }
      /* Issue #68: a barely-darker red plus a text change from "Stop
         charging" to "Sure?" was too easy to miss (a user reported that
         pressing Stop "did nothing", which turned out to be an unnoticed
         first click landing in this state, not a second click ever
         happening). Amber + a pulse make the "needs one more press" state
         impossible to miss even at a glance. */
      .dash-btn.stop.confirm { background: #f57c00; animation: dash-stop-confirm-pulse 1s ease-in-out infinite; }
      @keyframes dash-stop-confirm-pulse {
        0%,100% { opacity: 1; }
        50%     { opacity: .65; }
      }
      .dash-btn:disabled { opacity: .4; cursor: not-allowed; }
      .dash-slider-row {
        display: flex; align-items: center; gap: 10px; margin: 10px 0 14px;
      }
      .dash-slider-row .lbl { flex: 0 0 auto; font-size: 13px; color: var(--secondary-text-color); }
      .dash-slider-row input[type=range] { flex: 1; }
      .dash-slider-row .val {
        flex: 0 0 auto; min-width: 38px; text-align: right;
        font-size: 14px; font-weight: 600; color: var(--primary-text-color);
      }
      .dash-slider-warn {
        display: flex; align-items: center; gap: 6px;
        font-size: 12px; color: var(--warning-color, #ff9800);
        margin: 10px 0 14px;
      }
      .dash-batbar-wrap {
        margin-top: 6px;
        background: var(--secondary-background-color, #eee);
        border-radius: 999px; overflow: hidden; height: 22px; position: relative;
      }
      .dash-batbar {
        height: 100%; background: linear-gradient(90deg,#66bb6a,#43a047);
        transition: width .4s ease;
      }
      .dash-batbar.low { background: linear-gradient(90deg,#ffb74d,#fb8c00); }
      .dash-batbar.crit { background: linear-gradient(90deg,#ef5350,#e53935); }
      .dash-batbar-label {
        position: absolute; right: 12px; top: 0; bottom: 0; display: flex;
        align-items: center; font-size: 13px; font-weight: 600;
        color: var(--primary-text-color);
      }
      /* --- Wartung + CO2-Sektion --- */
      .dash-section-head {
        font-size: 13px; font-weight: 600; letter-spacing: .02em;
        color: var(--secondary-text-color);
        margin: 16px 0 8px 2px; text-transform: uppercase;
      }
      .dash-maint-list {
        display: flex; flex-direction: column; gap: 8px;
      }
      .dash-maint-row {
        display: flex; align-items: center; gap: 10px;
        padding: 10px 12px; border-radius: 10px;
        background: var(--secondary-background-color, #f4f6f8);
        border-left: 4px solid var(--primary-color, #03a9f4);
      }
      .dash-maint-row.overdue {
        background: rgba(229,57,53,.10);
        border-left-color: #e53935;
      }
      .dash-maint-row.due-soon {
        background: rgba(255,167,38,.12);
        border-left-color: #fb8c00;
      }
      .dash-maint-row ha-icon { --mdc-icon-size: 22px; color: var(--secondary-text-color); flex-shrink: 0; }
      .dash-maint-row.overdue ha-icon { color: #e53935; }
      .dash-maint-row.due-soon ha-icon { color: #fb8c00; }
      .dash-maint-row .name { flex: 1; font-size: 14px; color: var(--primary-text-color); }
      .dash-maint-row .when {
        font-size: 12px; font-weight: 600;
        color: var(--secondary-text-color);
        font-variant-numeric: tabular-nums;
      }
      .dash-maint-row.overdue .when { color: #e53935; }
      .dash-maint-row.due-soon .when { color: #fb8c00; }
      .dash-maint-done {
        background: #2e7d32; color: #fff; border: 0;
        width: 32px; height: 32px; border-radius: 50%;
        display: inline-flex; align-items: center; justify-content: center;
        cursor: pointer; flex-shrink: 0;
        box-shadow: 0 1px 4px rgba(0,0,0,.2);
        transition: filter .15s ease, transform .15s ease;
      }
      .dash-maint-done:hover { filter: brightness(1.1); }
      .dash-maint-done:active { transform: scale(0.92); }
      .dash-maint-done ha-icon { --mdc-icon-size: 18px; color: #fff; }
      .dash-maint-empty {
        padding: 10px 12px; font-size: 13px;
        color: var(--secondary-text-color); font-style: italic;
        text-align: center;
      }
      .dash-co2-grid {
        display: grid; grid-template-columns: 1fr 1fr; gap: 10px;
      }
      .dash-co2-card {
        padding: 12px; border-radius: 10px;
        background: var(--secondary-background-color, #f4f6f8);
        display: flex; flex-direction: column; gap: 4px;
      }
      .dash-co2-card .lbl {
        font-size: 11px; color: var(--secondary-text-color);
        text-transform: uppercase; letter-spacing: .04em;
      }
      .dash-co2-card .v1 { font-size: 16px; font-weight: 600; color: var(--primary-text-color); }
      .dash-co2-card .v2 { font-size: 13px; color: var(--secondary-text-color); }
      .dash-co2-compared {
        font-size: 11px; color: var(--secondary-text-color);
        margin-top: 4px; text-align: center; font-style: italic;
      }
      .dash-energy-grid {
        display: grid; grid-template-columns: repeat(auto-fit, minmax(90px, 1fr));
        gap: 10px;
      }
      .dash-energy-card {
        padding: 12px; border-radius: 10px;
        background: var(--secondary-background-color, #f4f6f8);
        display: flex; flex-direction: column; gap: 4px;
        border-left: 3px solid var(--primary-color, #03a9f4);
      }
      .dash-energy-card .lbl {
        font-size: 11px; color: var(--secondary-text-color);
        text-transform: uppercase; letter-spacing: .04em;
      }
      .dash-energy-card .v1 {
        font-size: 18px; font-weight: 700; color: var(--primary-text-color);
        font-variant-numeric: tabular-nums;
      }
      .dash-energy-card .v2 {
        font-size: 12px; color: var(--secondary-text-color);
        font-variant-numeric: tabular-nums;
      }
      /* Editor: Wartungs-Liste */
      .dash-ed-maint-row {
        display: grid;
        grid-template-columns: 1fr auto auto auto auto;
        gap: 8px; align-items: end;
        padding: 8px; border-radius: 8px;
        background: var(--secondary-background-color, #f4f6f8);
        margin-bottom: 6px;
      }
      .dash-ed-maint-row > div { display: flex; flex-direction: column; gap: 2px; }
      .dash-ed-maint-row label {
        font-size: 10px; color: var(--secondary-text-color);
        text-transform: uppercase; letter-spacing: .04em;
      }
      .dash-ed-maint-row input, .dash-ed-maint-row select {
        padding: 6px 8px; border-radius: 4px;
        border: 1px solid var(--divider-color);
        background: var(--card-background-color);
        color: var(--primary-text-color); font-size: 13px;
      }
      .dash-ed-maint-row .interval { width: 90px; }
      .dash-ed-maint-row .lastat { width: 130px; }
      .dash-ed-maint-row button.remove {
        background: transparent; border: 0; color: #e53935;
        cursor: pointer; padding: 6px; align-self: end;
      }
      .dash-ed-add {
        background: var(--primary-color, #03a9f4); color: #fff; border: 0;
        padding: 8px 12px; border-radius: 6px; cursor: pointer;
        font-size: 13px; align-self: flex-start;
      }
      @media (max-width: 600px) {
        .dash-ed-maint-row { grid-template-columns: 1fr; }
      }
    `;
    card.appendChild(style);

    const wrap = document.createElement("div");
    wrap.className = "dash-wrap";
    card.appendChild(wrap);

    wrap.innerHTML = `
      <div class="dash-title" id="dash-title"></div>
      <div class="dash-image-wrap" id="dash-image-wrap"></div>
      <div class="dash-row" id="dash-row-stats"></div>
      <div class="dash-pills" id="dash-pills"></div>
      <div class="dash-slider-row" id="dash-slider-row" style="display:none">
        <span class="lbl" id="dash-slider-lbl"></span>
        <input type="range" id="dash-slider" min="20" max="100" step="5" value="80" />
        <span class="val" id="dash-slider-val">80%</span>
      </div>
      <div class="dash-slider-warn" id="dash-slider-warn" style="display:none">
        <ha-icon icon="mdi:alert-outline"></ha-icon>
        <span id="dash-slider-warn-text"></span>
      </div>
      <div class="dash-controls" id="dash-controls" style="display:none"></div>
      <div class="dash-batbar-wrap" id="dash-batbar-wrap">
        <div class="dash-batbar" id="dash-batbar" style="width:0%"></div>
        <div class="dash-batbar-label" id="dash-batbar-label">--%</div>
      </div>
      <div id="dash-maint-section" style="display:none">
        <div class="dash-section-head" id="dash-maint-head"></div>
        <div class="dash-maint-list" id="dash-maint-list"></div>
      </div>
      <div id="dash-co2-section" style="display:none">
        <div class="dash-section-head" id="dash-co2-head"></div>
        <div class="dash-co2-grid" id="dash-co2-grid"></div>
        <div class="dash-co2-compared" id="dash-co2-compared"></div>
      </div>
      <div id="dash-energy-section" style="display:none">
        <div class="dash-section-head" id="dash-energy-head"></div>
        <div class="dash-energy-grid" id="dash-energy-grid"></div>
      </div>
    `;

    // Slider live preview + commit on change
    const slider = wrap.querySelector("#dash-slider");
    const sliderVal = wrap.querySelector("#dash-slider-val");
    slider.addEventListener("input", () => { sliderVal.textContent = slider.value + "%"; });
    slider.addEventListener("change", () => {
      const target = this._config.target_soc_entity;
      if (!target || !this._hass) return;
      // Domain-aware, like _callSwitch(): target_soc_entity is documented as
      // an input_number helper, but the Charge Limiter firmware this project
      // ships its own ESPHome "Charge Limit" number entity, i.e. a plain
      // `number.*` entity, not an `input_number.*` one. Hardcoding the
      // input_number domain here made the slider visibly move and then
      // silently snap back for exactly that setup (issue #68): the service
      // call targeted a domain the configured entity does not belong to, so
      // it matched nothing, and the next render reasserted the unchanged
      // real state. Both domains name the service identically ("set_value"),
      // so deriving it from the entity_id is enough for either.
      const [domain] = target.split(".");
      this._hass.callService(domain, "set_value", {
        entity_id: target, value: Number(slider.value),
      }).catch((err) => console.error("[Bosch eBike Dashboard] set_value failed", err));
    });

    this._built = true;
    this._applyStatic();
  }

  _applyStatic() {
    const title = this.querySelector("#dash-title");
    if (title) {
      title.textContent =
        this._config.bike_name || this._config.title || "eBike";
    }
  }

  _state(entityId) {
    if (!entityId || !this._hass) return null;
    return this._hass.states[entityId] || null;
  }

  _num(entityId, fallback = null) {
    const s = this._state(entityId);
    if (!s) return fallback;
    const v = Number(s.state);
    return Number.isFinite(v) ? v : fallback;
  }

  _onOff(entityId) {
    const s = this._state(entityId);
    if (!s) return null;
    return s.state === "on" || s.state === "true" || s.state === "charging";
  }

  /// Remember the newest real SoC so the pill can still show something once
  /// the bike sleeps and its sensors go unavailable (issue #65). Kept in
  /// localStorage, keyed by the configured entities, so it also survives a
  /// dashboard reload - which is exactly when the value is needed, since a
  /// sleeping bike will not produce a fresh reading to re-seed it.
  _rememberBattery(cfg, freshValue) {
    const key = "bosch_ebike_last_soc:"
      + (cfg.battery_live_entity || "") + "|" + (cfg.battery_entity || "");
    // Drop the memo when the configured entities change: HA reuses the same
    // element across a card-editor change, so without this a previously
    // remembered SoC would be shown under the newly picked bike's name.
    if (this._lastSocKey !== key) {
      this._lastSoc = null;
      this._lastSocKey = key;
    }
    if (freshValue != null) {
      // set hass -> _render runs on every state change anywhere in HA, so
      // only touch localStorage when the value actually moved (or the stamp
      // aged past the tooltip's own one-minute granularity). A synchronous
      // write per render on a high-frequency *_live sensor is exactly the
      // kind of main-thread work that froze this card before (issue #19).
      if (this._lastSoc && this._lastSoc.value === freshValue
          && Date.now() - this._lastSoc.ts < 60000) {
        return this._lastSoc;
      }
      const entry = { value: freshValue, ts: Date.now() };
      this._lastSoc = entry;
      try { localStorage.setItem(key, JSON.stringify(entry)); } catch (_) { /* quota/private mode */ }
      return entry;
    }
    if (this._lastSoc) return this._lastSoc;
    try {
      const raw = localStorage.getItem(key);
      const parsed = raw ? JSON.parse(raw) : null;
      if (parsed && Number.isFinite(parsed.value)) {
        this._lastSoc = parsed;
        return parsed;
      }
    } catch (_) { /* corrupt or unavailable */ }
    return { value: null, ts: null };
  }

  /// "2 h ago" style age for the stale-SoC tooltip.
  _socAgeText(ts) {
    if (!ts) return "";
    // Floor at 1 so a value cached seconds ago never reads as "0 min ago".
    const mins = Math.max(1, Math.round((Date.now() - ts) / 60000));
    if (mins < 60) return this._t("dash_soc_stale_min", mins);
    const hours = Math.round(mins / 60);
    if (hours < 48) return this._t("dash_soc_stale_hour", hours);
    return this._t("dash_soc_stale_day", Math.round(hours / 24));
  }

  _formatKm(v) {
    if (v == null || !Number.isFinite(v)) return this._t("dash_state_unknown");
    return v.toLocaleString(undefined, { maximumFractionDigits: 1 }) + " km";
  }
  _formatW(v) {
    if (v == null || !Number.isFinite(v)) return this._t("dash_state_unknown");
    return v.toLocaleString(undefined, { maximumFractionDigits: 0 }) + " W";
  }
  _formatPct(v) {
    if (v == null || !Number.isFinite(v)) return this._t("dash_state_unknown");
    return v.toLocaleString(undefined, { maximumFractionDigits: 0 }) + " %";
  }

  // Geschätzte Restreichweite in km: explizit konfigurierter Sensor
  // (range_entity) oder Auto-Erkennung des Integrations-Sensors
  // "Estimated Range (Current)". null = keine Kachel anzeigen.
  _estimatedRangeKm(cfg) {
    const states = this._hass && this._hass.states ? this._hass.states : null;
    if (!states) return null;
    let ent = cfg.range_entity;
    if (!ent) {
      // Treffer cachen; bei "nicht gefunden" weiter suchen, damit ein erst
      // später angelegter Sensor ohne Card-Neuaufbau erscheint.
      if (!this._rangeAutoEntity || !states[this._rangeAutoEntity]) {
        this._rangeAutoEntity =
          boschRangeEntityIds(this._hass, "estimated_range_current")[0] || null;
      }
      ent = this._rangeAutoEntity;
    }
    const st = ent ? states[ent] : null;
    if (!st) return null;
    const v = Number(st.state);
    return Number.isFinite(v) && v >= 0 ? Math.round(v) : null;
  }

  _render() {
    if (!this._built || !this._hass) return;

    const cfg = this._config;

    // ---------- Image ----------
    // WICHTIG: NICHT bei jedem _render() das <img> neu erzeugen.
    // Jedes neue <img> triggert einen frischen HTTP-Request – bei
    // hochfrequenten State-Updates (z.B. *_live-Sensoren) entstand
    // damit eine sub-sekündliche Fetch-Schleife auf
    // /api/image/serve/<id>/original, die das UI zum Flackern oder
    // Einfrieren brachte (Issue #19). Wir aktualisieren stattdessen
    // nur src/alt, wenn sich die Werte tatsächlich geändert haben.
    const imgWrap = this.querySelector("#dash-image-wrap");
    if (imgWrap) {
      // Issue #45 follow-up: the whole image area (photo or the "no image
      // configured" placeholder) is optional, default on for existing
      // configs. display:none collapses the aspect-ratio box AND its
      // margin-bottom entirely, so turning it off actually reclaims the
      // space instead of leaving an empty gap.
      const showImage = cfg.show_bike_image !== false;
      imgWrap.style.display = showImage ? "" : "none";

      if (showImage) {
        let img = imgWrap.querySelector("img");
        let placeholder = imgWrap.querySelector(".dash-no-image");
        const wantedAlt = cfg.bike_name || "eBike";

        if (cfg.bike_image) {
          if (placeholder) { placeholder.remove(); placeholder = null; }
          if (!img) {
            img = document.createElement("img");
            img.src = cfg.bike_image;
            img.alt = wantedAlt;
            imgWrap.appendChild(img);
          } else {
            // src nur überschreiben, wenn sich der URL-String wirklich
            // ändert – sonst (je nach Browser und Cache-Header) erneuter
            // Netzwerk-Roundtrip trotz identischer URL.
            if (img.getAttribute("src") !== cfg.bike_image) {
              img.src = cfg.bike_image;
            }
            if (img.alt !== wantedAlt) img.alt = wantedAlt;
          }
        } else {
          if (img) { img.remove(); img = null; }
          if (!placeholder) {
            placeholder = document.createElement("div");
            placeholder.className = "dash-no-image";
            placeholder.innerHTML = `
              <ha-icon class="ico" icon="mdi:bicycle-electric" style="--mdc-icon-size:48px"></ha-icon>
              <div>${this._t("dash_no_image")}</div>
              <div style="opacity:.6;margin-top:4px">${this._t("dash_no_image_hint")}</div>
            `;
            imgWrap.appendChild(placeholder);
          }
        }
      }
    }

    // ---------- Stat tiles ----------
    const odo = this._num(cfg.odometer_entity);
    const lastTour = this._num(cfg.last_tour_distance_entity);
    const power = this._num(cfg.charge_power_entity);
    const batteryLive = cfg.battery_live_entity ? this._num(cfg.battery_live_entity) : null;
    const batteryCloud = this._num(cfg.battery_entity);
    // Prefer the real-time value from the local LDI bridge when it is
    // available; otherwise fall back to the second configured SoC entity.
    const batteryFresh = (batteryLive != null) ? batteryLive : batteryCloud;
    const batteryIsLive = (batteryLive != null);
    // Both sources gone: the bike sleeps and the BLE bridge disconnects, so
    // every SoC entity goes unavailable at once (issue #65). Bosch's cloud
    // API exposes no state of charge at all, so there is nothing else to read
    // - show the last value we saw instead of "n/a", clearly marked as stale
    // so a days-old reading is never mistaken for a current one.
    const batteryRemembered = this._rememberBattery(cfg, batteryFresh);
    const battery = (batteryFresh != null) ? batteryFresh : batteryRemembered.value;
    const batteryIsStale = (batteryFresh == null) && (batteryRemembered.value != null);
    const isCharging = this._onOff(cfg.charging_entity);

    const row = this.querySelector("#dash-row-stats");
    if (row) {
      row.innerHTML = "";
      const tiles = [
        { icon: "mdi:counter", label: this._t("dash_label_odo"), val: this._formatKm(odo) },
      ];
      if (cfg.last_tour_distance_entity) {
        tiles.push({ icon: "mdi:map-marker-distance", label: this._t("dash_label_last_tour"), val: this._formatKm(lastTour) });
      }
      // Geschätzte Restreichweite (Sensor "Estimated Range (Current)" der
      // Integration). Explizit via range_entity, sonst Auto-Erkennung; ohne
      // Wert keine Kachel. "≈" markiert den Schätzungs-Charakter.
      const rangeKm = this._estimatedRangeKm(cfg);
      if (rangeKm != null) {
        tiles.push({
          icon: "mdi:road-variant",
          label: this._t("dash_label_range"),
          val: `≈ ${rangeKm} km`,
        });
      }
      if (cfg.charge_power_entity) {
        tiles.push({
          icon: "mdi:flash",
          label: this._t("dash_label_charge_power"),
          val: this._formatW(power),
          accent: !!(isCharging && power && power > 0),
        });
      }
      for (const t of tiles) {
        const el = document.createElement("div");
        el.className = "dash-tile";
        el.innerHTML = `
          <ha-icon class="${t.accent ? "accent" : ""}" icon="${t.icon}"></ha-icon>
          <div class="val">${t.val}</div>
          <div class="lbl">${t.label}</div>
        `;
        row.appendChild(el);
      }
    }

    // ---------- Status pills ----------
    const pills = this.querySelector("#dash-pills");
    if (pills) {
      pills.innerHTML = "";

      // Reichweite je Fahrmodus als farbige Piles (vor Lade-/Akku-Pille).
      // Farben pro Modus aus der Karten-Konfig (mode_colors) bzw. Bosch-Default.
      // Schalter ist nur ein Opt-out; Default (Schlüssel fehlt) = anzeigen.
      if (cfg.show_range_pills !== false) {
        // Prefer anchors that live on the integration's bike device
        // (odometer/range) over the battery/charging entities, which are often
        // BLE-bridge sensors on a different device. bike_id (when set) is the
        // authoritative filter inside boschReachableRanges (issue #39).
        const anchor = cfg.odometer_entity || cfg.range_entity
          || cfg.battery_entity || cfg.charging_entity;
        for (const r of boschReachableRanges(this._hass, anchor, cfg.bike_id, cfg.mode_order)) {
          if (r.km == null) continue;
          const hex = boschModeColorHex(r.mode, cfg.mode_colors);
          const rp = document.createElement("span");
          rp.className = "dash-pill range";
          if (hex) { rp.style.background = hex; rp.style.color = boschContrastColor(hex); }
          const m = document.createElement("span");
          m.className = "mode";
          m.textContent = r.mode;
          const km = document.createElement("span");
          km.className = "km";
          km.textContent = this._formatKm(r.km);
          rp.appendChild(m);
          rp.appendChild(km);
          pills.appendChild(rp);
        }
      }

      const stateLabel = isCharging == null
        ? this._t("dash_state_unknown")
        : isCharging ? this._t("dash_state_charging") : this._t("dash_state_not_charging");
      const stateIcon = isCharging ? "mdi:battery-charging" : "mdi:power-plug-off";
      const pill = document.createElement("span");
      pill.className = "dash-pill" + (isCharging ? " charging" : "");
      pill.innerHTML = `<ha-icon icon="${stateIcon}"></ha-icon><span>${stateLabel}</span>`;
      pills.appendChild(pill);

      if (cfg.battery_entity || cfg.battery_live_entity) {
        const bp = document.createElement("span");
        bp.className = "dash-pill" + (batteryIsStale ? " stale" : "");
        const battIcon = batteryIsLive
          ? "mdi:battery-sync"
          : (batteryIsStale ? "mdi:battery-clock" : "mdi:battery");
        // A remembered reading is prefixed with "~" and dimmed, and names its
        // age in the tooltip, so it can never pass for a live value.
        const battText = (batteryIsStale ? "~ " : "") + this._formatPct(battery);
        bp.innerHTML = `<ha-icon icon="${battIcon}"></ha-icon><span>${battText}</span>`;
        if (batteryIsStale) {
          bp.title = this._t("dash_soc_stale_hint", this._socAgeText(batteryRemembered.ts));
        }
        pills.appendChild(bp);
      }
    }

    // ---------- Slider ----------
    const sliderRow = this.querySelector("#dash-slider-row");
    const slider = this.querySelector("#dash-slider");
    const sliderVal = this.querySelector("#dash-slider-val");
    const sliderLbl = this.querySelector("#dash-slider-lbl");
    const sliderWarn = this.querySelector("#dash-slider-warn");
    const sliderWarnText = this.querySelector("#dash-slider-warn-text");
    if (cfg.target_soc_entity) {
      const targetState = this._state(cfg.target_soc_entity);
      if (targetState) {
        sliderRow.style.display = "flex";
        sliderWarn.style.display = "none";
        sliderLbl.textContent = this._t("dash_label_target_soc");
        const a = targetState.attributes || {};
        if (a.min != null) slider.min = a.min;
        if (a.max != null) slider.max = a.max;
        if (a.step != null) slider.step = a.step;
        const v = Number(targetState.state);
        if (Number.isFinite(v) && document.activeElement !== slider) {
          slider.value = v;
          sliderVal.textContent = v + "%";
        }
      } else {
        // Configured entity_id does not exist (issue #62): showing a live
        // slider here would silently fail on every change (input_number.set_value
        // has nowhere to write to), so surface the fix instead of a
        // seemingly-working but non-functional control.
        sliderRow.style.display = "none";
        sliderWarn.style.display = "flex";
        sliderWarnText.textContent = `${this._t("dash_target_soc_missing")} (${cfg.target_soc_entity})`;
      }
    } else {
      sliderRow.style.display = "none";
      sliderWarn.style.display = "none";
    }

    // ---------- Buttons ----------
    const controls = this.querySelector("#dash-controls");
    if (controls) {
      controls.innerHTML = "";
      if (cfg.charge_switch_entity) {
        controls.style.display = "flex";
        const sw = this._state(cfg.charge_switch_entity);
        const swOn = sw && sw.state === "on";
        const startBtn = document.createElement("button");
        startBtn.className = "dash-btn";
        startBtn.innerHTML = `<ha-icon icon="mdi:play"></ha-icon><span>${this._t("dash_btn_start")}</span>`;
        startBtn.disabled = swOn === true;
        startBtn.addEventListener("click", () => this._callSwitch("turn_on"));
        controls.appendChild(startBtn);

        const stopBtn = document.createElement("button");
        stopBtn.className = "dash-btn stop" + (this._pendingStop ? " confirm" : "");
        stopBtn.innerHTML = `<ha-icon icon="mdi:stop"></ha-icon><span>${this._pendingStop ? this._t("dash_btn_confirm") : this._t("dash_btn_stop")}</span>`;
        stopBtn.disabled = swOn === false;
        stopBtn.addEventListener("click", () => this._handleStop());
        controls.appendChild(stopBtn);
      } else {
        controls.style.display = "none";
      }
    }

    // ---------- Battery bar ----------
    const bar = this.querySelector("#dash-batbar");
    const barLbl = this.querySelector("#dash-batbar-label");
    if (bar && barLbl) {
      const pct = battery != null && Number.isFinite(battery) ? Math.max(0, Math.min(100, battery)) : 0;
      bar.style.width = pct + "%";
      bar.classList.remove("low", "crit");
      if (pct < 15) bar.classList.add("crit");
      else if (pct < 35) bar.classList.add("low");
      barLbl.textContent = battery != null && Number.isFinite(battery)
        ? Math.round(battery) + " %" : "--%";
    }

    // ---------- Wartung + CO2 ----------
    this._renderMaintenance();
    this._renderCO2(odo, lastTour);
    this._renderEnergyCost();
  }

  // ===========================================================================
  // Wartung - liest Items aus HA-Storage (per-bike), nicht mehr aus der
  // Card-Config oder localStorage. Backend liefert remaining_km +
  // remaining_days bereits ausgerechnet. Anzeige zeigt nur Items, die
  // in den nächsten 500 km oder 30 Tagen fällig sind; überfällig rot,
  // bald fällig gelb, sortiert nach Dringlichkeit.
  // ===========================================================================
  _renderMaintenance() {
    const sec = this.querySelector("#dash-maint-section");
    const head = this.querySelector("#dash-maint-head");
    const list = this.querySelector("#dash-maint-list");
    if (!sec || !head || !list) return;

    const bikeId = this._config.bike_id || null;

    // Async-Loader anstossen, falls wir noch keine Items haben oder
    // sich der Bike-Scope (oder das "auto"-Flag) geändert hat. Beim
    // erfolgreichen Laden ruft dieser Pfad _render() erneut auf.
    const scopeKey = bikeId || "__auto__";
    if (this._maintItems == null || this._maintLoadedFor !== scopeKey) {
      this._loadMaintenance(bikeId);
      sec.style.display = "none";
      return;
    }

    if (!this._maintItems.length) { sec.style.display = "none"; return; }

    head.textContent = this._t("dash_section_maint");
    sec.style.display = "";
    list.innerHTML = "";

    const due = [];
    for (const m of this._maintItems) {
      const status = this._maintStatus(m);
      if (!status) continue;
      if (status.show) due.push({ m, status });
    }
    if (!due.length) {
      const p = document.createElement("div");
      p.className = "dash-maint-empty";
      p.textContent = this._t("dash_maint_none", this._maintWarnDays(), this._maintWarnKm());
      list.appendChild(p);
      return;
    }
    due.sort((a, b) => {
      const aPri = a.status.overdue ? -1 : 1;
      const bPri = b.status.overdue ? -1 : 1;
      if (aPri !== bPri) return aPri - bPri;
      return a.status.sortKey - b.status.sortKey;
    });
    for (const { m, status } of due) {
      const row = document.createElement("div");
      row.className = "dash-maint-row " + (status.overdue ? "overdue" : "due-soon");
      const icon = status.kind === "km" ? "mdi:wrench-cog" : "mdi:calendar-clock";
      row.innerHTML = `
        <ha-icon icon="${icon}"></ha-icon>
        <div class="name">${this._escapeHtml(m.name || "")}</div>
        <div class="when">${this._escapeHtml(status.label)}</div>
      `;
      const doneBtn = document.createElement("button");
      doneBtn.type = "button";
      doneBtn.className = "dash-maint-done";
      doneBtn.title = this._t("dash_maint_done_btn");
      doneBtn.setAttribute("aria-label", this._t("dash_maint_done_btn"));
      doneBtn.innerHTML = `<ha-icon icon="mdi:check"></ha-icon>`;
      doneBtn.addEventListener("click", () => this._maintMarkDone(m));
      row.appendChild(doneBtn);
      list.appendChild(row);
    }
  }

  // Status aus dem vom Backend gelieferten remaining_km / remaining_days.
  // Reine Anzeige-Logik; die eigentliche Restberechnung passiert in
  // coordinator.py:_evaluate_maintenance_item.
  //
  // Wichtig: Number(null) === 0 und Number.isFinite(0) === true. Wir
  // MÜSSEN daher explizit auf != null prüfen, sonst wird für ein
  // Datums-Item mit remaining_km: null fälschlich der km-Pfad gewählt
  // und der User sieht "Überfällig: 0 km" statt "in X Tagen".
  // Außerdem nehmen wir bevorzugt den vorhandenen Interval-Typ:
  // wenn das Item interval_days hat (also datumsbasiert ist), zeigen
  // wir Tage - auch wenn ein verirrtes remaining_km mitkommen sollte.
  _maintStatus(m) {
    if (!m || !m.name) return null;
    const hasKmInterval = m.interval_km != null && Number.isFinite(Number(m.interval_km));
    const hasDayInterval = m.interval_days != null && Number.isFinite(Number(m.interval_days));
    const remKm = m.remaining_km;
    const remDays = m.remaining_days;
    const useKm = hasKmInterval && remKm != null && Number.isFinite(Number(remKm));
    const useDays = hasDayInterval && remDays != null && Number.isFinite(Number(remDays));
    const warnKm = this._maintWarnKm();
    const warnDays = this._maintWarnDays();
    if (useKm && !useDays) {
      const remaining = Math.round(Number(remKm));
      return {
        kind: "km",
        show: remaining <= warnKm,
        overdue: remaining <= 0,
        sortKey: remaining,
        label: this._t("dash_maint_due_km", remaining),
      };
    }
    if (useDays) {
      const days = Math.round(Number(remDays));
      return {
        kind: "date",
        show: days <= warnDays,
        overdue: days <= 0,
        sortKey: days,
        label: this._t("dash_maint_due_days", days),
      };
    }
    return null;
  }

  // Warnschwellen in einem Helper kapseln, damit alle Stellen (Status-
  // Eval, "keine Wartung fällig"-Text) garantiert denselben Wert sehen.
  // Cascade: Shared-Store > Card-YAML > Hardcoded-Default. Werte aus
  // dem Store kommen als Number oder String je nach Browser; coerce
  // hier einmal und klemme auf einen vernuenftigen Bereich.
  _maintWarnKm() {
    const raw = readCardSetting(this._config, "maint_warn_km", MAINT_WARN_KM_DEFAULT);
    const n = Number(raw);
    if (!Number.isFinite(n) || n < 0) return MAINT_WARN_KM_DEFAULT;
    return Math.max(0, Math.min(100000, Math.round(n)));
  }
  _maintWarnDays() {
    const raw = readCardSetting(this._config, "maint_warn_days", MAINT_WARN_DAYS_DEFAULT);
    const n = Number(raw);
    if (!Number.isFinite(n) || n < 0) return MAINT_WARN_DAYS_DEFAULT;
    return Math.max(0, Math.min(3650, Math.round(n)));
  }

  // Lädt die Wartungs-Items vom Backend (ws_list_maintenance). Wird
  // einmal beim ersten Render gerufen sowie nach jeder Mutation
  // (mark-done, etc.) zum Refresh. Cleanup-Migration aus localStorage
  // ist hier eingebaut: alte v1.16.5-Keys werden bei jedem Load
  // gelöscht, sobald der Backend-Pfad einmal funktioniert hat.
  async _loadMaintenance(bikeId) {
    if (this._maintLoading) return;
    if (!this._hass) return;
    this._maintLoading = true;
    try {
      const res = await this._hass.callWS({ type: "bosch_ebike/list_maintenance" });
      const bikes = res?.bikes || [];
      let resolvedBikeId = bikeId;
      let items = null;
      if (bikeId) {
        const myBike = bikes.find((b) => b.bike_id === bikeId);
        items = myBike?.items || null;
      }
      // Auto-Discover: bei fehlender oder nicht-matchender bike_id
      // nimm das Bike, das überhaupt Items hat. Häufiger Fall:
      // Single-Bike-Setup, und der User hat in den Editor-Settings
      // nichts explizit gewählt.
      if (items == null) {
        const bikesWithItems = bikes.filter((b) => (b.items || []).length > 0);
        if (bikesWithItems.length === 1) {
          items = bikesWithItems[0].items;
          resolvedBikeId = bikesWithItems[0].bike_id;
        } else {
          items = [];
        }
      }
      // bike_id pro Item annotieren, damit der Done-Button die
      // richtige Bike-Zuordnung hat - auch im Auto-Discover-Fall,
      // wo this._config.bike_id leer ist.
      this._maintItems = items.map((i) => ({ ...i, bike_id: resolvedBikeId }));
      this._maintLoadedFor = bikeId || "__auto__";
      this._cleanupLegacyLocalStorage();
      this._tryConfigMaintenanceMigration(resolvedBikeId).catch(() => {});
      this._render();
    } catch (err) {
      console.warn("[Bosch eBike Dashboard] list_maintenance failed:", err?.message || err);
      this._maintItems = [];
      this._maintLoadedFor = bikeId || "__auto__";
    } finally {
      this._maintLoading = false;
    }
  }

  _cleanupLegacyLocalStorage() {
    try {
      const keys = [];
      for (let i = 0; i < localStorage.length; i++) {
        const k = localStorage.key(i);
        if (k && k.startsWith("bosch-ebike-maint-")) keys.push(k);
      }
      for (const k of keys) localStorage.removeItem(k);
    } catch (_) { /* private mode etc. */ }
  }

  // Verschiebt Items aus card.config.maintenance einmalig ins Backend.
  // Wir machen das beim Card-Render, weil im YAML-Mode der User den
  // Editor evtl. gar nicht öffnet. Idempotent: läuft maximal einmal
  // pro Card-Instanz und nur wenn beim ersten Pull noch keine Items
  // im Backend lagen (sonst würden wir Duplikate erzeugen).
  async _tryConfigMaintenanceMigration(bikeId) {
    if (this._maintMigrated) return;
    const legacy = Array.isArray(this._config.maintenance) ? this._config.maintenance : [];
    if (!legacy.length) { this._maintMigrated = true; return; }
    // Schutz vor Duplikat-Import: nur wenn das Backend für dieses Bike
    // noch keine Items hat. Sonst lassen wir die alte Liste in der
    // Card-Config liegen - der User muss dann einmalig im Editor
    // entscheiden, was bleiben soll.
    if ((this._maintItems || []).length > 0) { this._maintMigrated = true; return; }
    this._maintMigrated = true;
    for (const m of legacy) {
      const payload = {
        type: "bosch_ebike/add_maintenance",
        bike_id: bikeId,
        name: m.name || "",
      };
      if (m.type === "km" && Number.isFinite(Number(m.intervalKm))) {
        payload.interval_km = Number(m.intervalKm);
      } else if (m.type === "date" && Number.isFinite(Number(m.intervalDays))) {
        payload.interval_days = Number(m.intervalDays);
      } else {
        continue;
      }
      if (!payload.name) continue;
      try { await this._hass.callWS(payload); } catch (_) { /* skip */ }
    }
    // Card-Config patchen: maintenance-Feld leeren, damit es bei
    // späterem Re-Migration-Check nicht wieder triggert. Das funktio-
    // niert nur, wenn die Lovelace-Config im UI-Mode ist; im YAML-Mode
    // bleibt das Feld stehen, aber die Migration läuft trotzdem nur
    // einmal pro Sitzung (siehe _maintMigrated-Flag oben).
    if (this._config.maintenance) {
      delete this._config.maintenance;
    }
    // Items neu laden, damit die Anzeige stimmt.
    this._maintLoadedFor = null;
    await this._loadMaintenance(bikeId);
  }

  // "Erledigt"-Klick: ruft ws_complete_maintenance. Backend setzt
  // last_done_at + last_done_odometer aus dem Bosch-API-Odometer und
  // speichert in HA-Storage. Nach Erfolg neu vom Backend laden.
  //
  // Fehler-Sichtbarkeit: alte Version war stillschweigend (`console.warn`),
  // der User dachte der Button reagiere nicht. Jetzt zeigen wir ein
  // sichtbares Flash + bei Fehler ein alert(), damit man weiß woran man
  // ist.
  async _maintMarkDone(item) {
    if (!item || !item.id) return;
    // Bike-ID-Auflösung in dieser Reihenfolge: das Item selbst (das
    // wir in _loadMaintenance mit bike_id annotieren) -> Card-Config
    // -> der zuletzt geladene Scope. So funktioniert "erledigt" auch
    // im Auto-Discover-Fall, wo this._config.bike_id leer ist.
    const bikeId = item.bike_id || this._config.bike_id
      || (this._maintLoadedFor !== "__auto__" ? this._maintLoadedFor : null);
    if (!bikeId) {
      alert(this._t("msg_no_bike_selected"));
      return;
    }
    if (!this._hass) return;
    try {
      await this._hass.callWS({
        type: "bosch_ebike/complete_maintenance",
        bike_id: bikeId,
        item_id: item.id,
      });
      // Kurzes visuelles Feedback
      const flash = document.createElement("div");
      flash.textContent = "✓";
      flash.style.cssText =
        "position:fixed;top:20px;left:50%;transform:translateX(-50%);" +
        "background:#2e7d32;color:#fff;padding:8px 24px;border-radius:999px;" +
        "font-size:22px;z-index:99999;box-shadow:0 2px 12px rgba(0,0,0,.3);" +
        "pointer-events:none;";
      document.body.appendChild(flash);
      setTimeout(() => flash.remove(), 800);
      this._maintLoadedFor = null;
      this._loadMaintenance(this._config.bike_id || null);
    } catch (err) {
      console.warn("[Bosch eBike Dashboard] complete_maintenance failed:", err?.message || err);
      alert(this._t("err_complete_maintenance_failed", err?.message || err));
    }
  }

  _escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    })[c]);
  }

  // ===========================================================================
  // CO2 + Sprit-Equivalent
  // ---------------------------------------------------------------------------
  // Berechnet Gesamt- und Letzte-Tour-Werte basierend auf dem
  // konfigurierten Fahrzeug-Preset. Wenn keine Vehicle ausgewählt ist,
  // oder Odometer/letzte-Tour fehlen, wird die Sektion ausgeblendet.
  _renderCO2(currentOdo, lastTourKm) {
    const sec = this.querySelector("#dash-co2-section");
    const head = this.querySelector("#dash-co2-head");
    const grid = this.querySelector("#dash-co2-grid");
    const cmp = this.querySelector("#dash-co2-compared");
    if (!sec || !head || !grid || !cmp) return;
    const vid = this._config.vehicle_comparison;
    if (!vid || vid === "none") { sec.style.display = "none"; return; }
    const preset = VEHICLE_PRESETS[vid];
    if (!preset) { sec.style.display = "none"; return; }
    sec.style.display = "";
    head.textContent = this._t("dash_section_co2");

    const fuelPrice = Number.isFinite(Number(this._config.fuel_price))
      ? Number(this._config.fuel_price)
      : FUEL_DEFAULT_PRICE[preset.fuel_kind] || 0;
    const calc = (km) => {
      if (!Number.isFinite(km) || km <= 0) return null;
      const co2Kg = (km * preset.co2_g_per_km) / 1000;
      // consumption ist l/100km (oder kWh/100km bei EV)
      const eur = km * (preset.consumption / 100) * fuelPrice;
      return { co2Kg, eur };
    };
    const total = calc(currentOdo);
    const last = calc(lastTourKm);

    grid.innerHTML = "";
    const card = (label, vals) => {
      const el = document.createElement("div");
      el.className = "dash-co2-card";
      if (!vals) {
        el.innerHTML = `<div class="lbl">${label}</div><div class="v1">–</div>`;
      } else {
        const co2 = vals.co2Kg.toLocaleString(undefined, { maximumFractionDigits: vals.co2Kg < 10 ? 1 : 0 });
        const eur = vals.eur.toLocaleString(undefined, { maximumFractionDigits: 2 });
        el.innerHTML = `
          <div class="lbl">${label}</div>
          <div class="v1">${co2}${this._t("dash_co2_grams")}</div>
          <div class="v2">${eur}${this._t("dash_co2_eur")}</div>
        `;
      }
      grid.appendChild(el);
    };
    card(this._t("dash_co2_total"), total);
    card(this._t("dash_co2_last"), last);

    const lang = (this._hass && this._hass.language) ? this._hass.language.split("-")[0] : "en";
    const vehLabel = preset["label_" + lang] || preset.label_en;
    cmp.textContent = this._t("dash_co2_compared") + ": " + vehLabel;
  }

  // Charging-cost summary over rolling 7/30/365-day windows. The energy
  // (Wh) figures come from the integration's own backend sensors (stored
  // in Home Assistant, not recomputed from cached rides in the browser);
  // this method only applies a price - fixed or from a referenced entity -
  // same "raw entity + card-side math" split as _renderCO2 above.
  _renderEnergyCost() {
    const sec = this.querySelector("#dash-energy-section");
    const head = this.querySelector("#dash-energy-head");
    const grid = this.querySelector("#dash-energy-grid");
    if (!sec || !head || !grid) return;
    if (this._config.show_energy_cost === false) { sec.style.display = "none"; return; }

    const priceMode = this._config.energy_price_mode === "entity" ? "entity" : "fixed";
    let price = null;
    if (priceMode === "entity") {
      const v = this._config.energy_price_entity ? this._num(this._config.energy_price_entity) : null;
      price = v;
    } else {
      const fixed = Number(this._config.energy_price_fixed);
      price = Number.isFinite(fixed) ? fixed : 0.23;
    }

    const periods = [
      { entityKey: "energy_week_entity", showKey: "show_cost_week", label: this._t("dash_energy_week") },
      { entityKey: "energy_month_entity", showKey: "show_cost_month", label: this._t("dash_energy_month") },
      { entityKey: "energy_year_entity", showKey: "show_cost_year", label: this._t("dash_energy_year") },
    ];
    const rows = periods.filter((p) => this._config[p.showKey] !== false && this._config[p.entityKey]);
    if (!rows.length) { sec.style.display = "none"; return; }

    sec.style.display = "";
    head.textContent = this._t("dash_section_energy");
    grid.innerHTML = "";

    for (const p of rows) {
      const wh = this._num(this._config[p.entityKey]);
      const el = document.createElement("div");
      el.className = "dash-energy-card";
      if (wh == null || price == null) {
        el.innerHTML = `<div class="lbl">${p.label}</div><div class="v1">–</div>`;
      } else {
        const kwh = wh / 1000;
        const cost = kwh * price;
        const costStr = cost.toLocaleString(undefined, { maximumFractionDigits: 2 });
        const kwhStr = kwh.toLocaleString(undefined, { maximumFractionDigits: kwh < 10 ? 2 : 1 });
        el.innerHTML = `
          <div class="lbl">${p.label}</div>
          <div class="v1">${costStr}${this._t("dash_co2_eur")}</div>
          <div class="v2">${kwhStr}${this._t("dash_energy_kwh")}</div>
        `;
      }
      grid.appendChild(el);
    }
  }

  _handleStop() {
    if (!this._pendingStop) {
      this._pendingStop = true;
      this._render();
      this._pendingStopTimer = setTimeout(() => {
        this._pendingStop = false;
        this._render();
      }, 3000);
      return;
    }
    clearTimeout(this._pendingStopTimer);
    this._pendingStop = false;
    this._callSwitch("turn_off");
  }

  _callSwitch(action) {
    const entityId = this._config.charge_switch_entity;
    if (!entityId || !this._hass) return;
    const [domain] = entityId.split(".");
    this._hass.callService(domain, action, { entity_id: entityId })
      .catch((err) => console.error("[Bosch eBike Dashboard] switch call failed", err));
  }
}

// Editor for Dashboard card
class BoschEBikeDashboardCardEditor extends HTMLElement {
  constructor() {
    super();
    this._hass = null;
    this._config = {};
    this._built = false;
  }

  setConfig(config) {
    this._config = { ...config };
    if (this._built) this._sync();
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._built) {
      this._build();
    } else if (this._fields) {
      // _build() only ever runs once (see setConfig), so the ha-entity-
      // picker fields created there would otherwise keep the .hass from
      // that first tick forever and never see newly added entities.
      for (const input of Object.values(this._fields)) {
        if (input && input.tagName === "HA-ENTITY-PICKER") input.hass = hass;
      }
    }
    // Shared-Settings einmalig laden + Bus abonnieren. Sonst zeigt der
    // Editor nach Browser-Reload die hartcodierten Defaults statt der
    // im Backend gespeicherten Werte - und ein nachfolgendes Tippen
    // wuerde den Backend-Wert mit dem versehentlichen Default ueber-
    // schreiben.
    if (!this._sharedSettingsRequested) {
      this._sharedSettingsRequested = true;
      ensureCardSettingsLoaded(hass).then(() => this._syncSharedFields()).catch(() => {});
    }
    if (!this._sharedSettingsHandler) {
      this._sharedSettingsHandler = () => this._syncSharedFields();
      _cardSettingsBus.addEventListener("changed", this._sharedSettingsHandler);
    }
    // Rebuild the per-mode colour rows only when the detected mode set
    // actually changes (e.g. the range sensors load after the editor opened).
    // Guarded so an open dropdown is not reset on every hass tick.
    if (this._modeColorsWrap) {
      const anchor = this._config.odometer_entity || this._config.range_entity
        || this._config.battery_entity || this._config.charging_entity;
      const key = boschReachableRanges(hass, anchor, this._config.bike_id, this._config.mode_order)
        .map((r) => r.mode).join("|");
      if (key !== this._modeColorsKey) {
        this._modeColorsKey = key;
        this._renderModeColorRows();
      }
    }
  }

  disconnectedCallback() {
    if (this._sharedSettingsHandler) {
      _cardSettingsBus.removeEventListener("changed", this._sharedSettingsHandler);
      this._sharedSettingsHandler = null;
    }
  }

  // Ueberschreibt die Werte der Warn-Inputs aus dem gerade geladenen
  // Shared-Store. NICHT aufrufen, waehrend der User tippt - sonst
  // wuerde unser eigener Save-Debounce sich selbst stoeren. Wir
  // ueberspringen Inputs, deren _saveTimer gerade laeuft.
  _syncSharedFields() {
    if (!this._warnInputs) return;
    for (const { key, input, defaultVal } of this._warnInputs) {
      if (this._sharedSaveTimers && this._sharedSaveTimers.has(key)) continue;
      const raw = readCardSetting(this._config, key, defaultVal);
      const n = Number(raw);
      const value = Number.isFinite(n) && n >= 0 ? String(Math.round(n)) : String(defaultVal);
      if (input.value !== value) input.value = value;
    }
    if (typeof this._refreshMaintHint === "function") this._refreshMaintHint();
  }

  _t(key) {
    const lang = (this._hass && this._hass.language) ? this._hass.language.split("-")[0] : "en";
    const dict = (I18N && I18N[lang]) || I18N.en;
    return dict[key] != null ? dict[key] : I18N.en[key];
  }

  _emit() {
    // Emit a fresh snapshot so HA always stores the current state (a shared
    // mutable reference could be missed for boolean / removed keys).
    this.dispatchEvent(new CustomEvent("config-changed", {
      detail: { config: { ...this._config } },
      bubbles: true,
      composed: true,
    }));
  }

  // Build one "mode -> colour" row per detected reachable-range mode.
  _renderModeColorRows() {
    const cont = this._modeColorsWrap;
    if (!cont) return;
    cont.innerHTML = "";
    const anchor = this._config.odometer_entity || this._config.range_entity
      || this._config.battery_entity || this._config.charging_entity;
    const modes = boschReachableRanges(this._hass, anchor, this._config.bike_id, this._config.mode_order);
    if (!modes.length) {
      const none = document.createElement("small");
      none.textContent = this._t("dash_editor_modes_none");
      none.style.cssText = "color:var(--secondary-text-color);font-size:11px;";
      cont.appendChild(none);
      return;
    }

    // Eindeutige Modus-Namen in aktueller Anzeige-Reihenfolge. Treibt sowohl die
    // Zeilen als auch die per Auf/Ab persistierte Reihenfolge (mode_order).
    const ordered = [];
    for (const r of modes) if (!ordered.includes(r.mode)) ordered.push(r.mode);

    // Reihenfolge speichern (immutable Update wie beim Farb-Select) + neu rendern.
    const saveOrder = (next) => {
      this._config = { ...this._config, mode_order: next };
      this._emit();
      this._renderModeColorRows();
    };

    ordered.forEach((mode, i) => {
      const row = document.createElement("div");
      row.style.cssText = "display:flex;align-items:center;gap:10px;";

      // Auf/Ab-Pfeile zum Umsortieren (funktioniert auch auf Touch).
      const arrows = document.createElement("div");
      arrows.style.cssText = "display:flex;flex-direction:column;line-height:1;flex:0 0 auto;";
      const mkArrow = (sym, disabled, onClick) => {
        const b = document.createElement("button");
        b.type = "button";
        b.textContent = sym;
        b.disabled = disabled;
        b.style.cssText = "border:none;background:none;padding:0 3px;font-size:12px;"
          + "cursor:" + (disabled ? "default" : "pointer") + ";"
          + "color:" + (disabled ? "var(--disabled-text-color)" : "var(--primary-text-color)") + ";";
        if (!disabled) b.addEventListener("click", onClick);
        return b;
      };
      arrows.appendChild(mkArrow("▲", i === 0, () => {
        const next = ordered.slice();
        [next[i - 1], next[i]] = [next[i], next[i - 1]];
        saveOrder(next);
      }));
      arrows.appendChild(mkArrow("▼", i === ordered.length - 1, () => {
        const next = ordered.slice();
        [next[i + 1], next[i]] = [next[i], next[i + 1]];
        saveOrder(next);
      }));

      const swatch = document.createElement("span");
      swatch.style.cssText = "width:16px;height:16px;border-radius:4px;flex:0 0 auto;border:1px solid var(--divider-color);";

      const name = document.createElement("span");
      name.textContent = mode;
      name.style.cssText = "flex:1;font-size:13px;font-weight:600;";

      const sel = document.createElement("select");
      sel.style.cssText = "padding:6px;border-radius:4px;border:1px solid var(--divider-color);background:var(--card-background-color);color:var(--primary-text-color);";
      const optAuto = document.createElement("option");
      optAuto.value = "";
      optAuto.textContent = this._t("dash_editor_color_auto");
      sel.appendChild(optAuto);
      for (const key of BOSCH_MODE_COLOR_ORDER) {
        const o = document.createElement("option");
        o.value = key;
        o.textContent = this._t("color_" + key);
        sel.appendChild(o);
      }
      sel.dataset.mode = mode;
      sel.value = (this._config.mode_colors && this._config.mode_colors[mode]) || "";

      const applySwatch = () => {
        const hex = boschModeColorHex(mode, sel.value ? { [mode]: sel.value } : {});
        swatch.style.background = hex || "var(--secondary-background-color)";
      };
      applySwatch();

      sel.addEventListener("change", () => {
        // Rebuild mode_colors from the CURRENT state of every row, so the saved
        // config always mirrors the UI exactly: reverting a mode to "Auto"
        // (empty value) reliably drops its entry, and modes no longer present
        // are pruned. Incrementally deleting a single key could leave a stale
        // entry behind on revert-to-default (issue #37).
        const mc = {};
        cont.querySelectorAll("select[data-mode]").forEach((s) => {
          if (s.value) mc[s.dataset.mode] = s.value;
        });
        const next = { ...this._config };
        if (Object.keys(mc).length) next.mode_colors = mc;
        else delete next.mode_colors;
        this._config = next;
        applySwatch();
        this._emit();
      });

      row.appendChild(arrows);
      row.appendChild(swatch);
      row.appendChild(name);
      row.appendChild(sel);
      cont.appendChild(row);
    });
  }

  _build() {
    this.innerHTML = "";
    const wrap = document.createElement("div");
    wrap.style.cssText = "display:flex;flex-direction:column;gap:12px;padding:12px;";
    this.appendChild(wrap);

    const mk = (label, hint, makeInput) => {
      const block = document.createElement("div");
      block.style.cssText = "display:flex;flex-direction:column;gap:4px;";
      const lbl = document.createElement("label");
      lbl.textContent = label;
      lbl.style.fontWeight = "500";
      block.appendChild(lbl);
      const input = makeInput();
      block.appendChild(input);
      if (hint) {
        const h = document.createElement("small");
        h.textContent = hint;
        h.style.cssText = "color:var(--secondary-text-color);font-size:11px;";
        block.appendChild(h);
      }
      wrap.appendChild(block);
      return input;
    };

    const mkText = (key, labelKey, hintKey) => {
      const input = mk(this._t(labelKey), hintKey ? this._t(hintKey) : null, () => {
        const i = document.createElement("input");
        i.type = "text";
        i.style.cssText = "padding:8px;border-radius:4px;border:1px solid var(--divider-color);background:var(--card-background-color);color:var(--primary-text-color);";
        return i;
      });
      input.value = this._config[key] || "";
      input.addEventListener("input", () => {
        if (input.value) this._config[key] = input.value;
        else delete this._config[key];
        this._emit();
      });
      return input;
    };

    // Native searchable/filterable HA entity picker (issue #45) instead of a
    // plain <select> listing every matching entity as a flat option list -
    // unusable once an install has thousands of entities. ha-entity-picker
    // is bundled with HA's own frontend (used by core integrations'
    // Lovelace editors), so it is always available here with no import;
    // verified against the actual frontend source for the .hass property,
    // .includeDomains, .value and the "value-changed" event (stable as of
    // HA frontend 20260527.x - a newer, context-based rewrite exists
    // upstream that drops the settable .hass property, so re-verify this if
    // pickers ever stop reacting to hass updates on a future HA version).
    const mkEntity = (key, labelKey, hintKey, includeDomains) => {
      const input = mk(this._t(labelKey), hintKey ? this._t(hintKey) : null, () => {
        const picker = document.createElement("ha-entity-picker");
        picker.hass = this._hass;
        picker.includeDomains = includeDomains;
        picker.allowCustomEntity = true;
        picker.style.width = "100%";
        return picker;
      });
      input.value = this._config[key] || "";
      input.addEventListener("value-changed", (ev) => {
        const v = ev.detail.value;
        if (v) this._config[key] = v;
        else delete this._config[key];
        this._emit();
      });
      return input;
    };

    const mkImage = (key, labelKey, hintKey) => {
      // Composite widget: text input + Upload button + preview + Clear button.
      // Uses HA's built-in /api/image/upload endpoint (image_upload integration,
      // active in HA core since 2023.4). Files persist under /config/image/
      // and survive HACS updates.
      const block = document.createElement("div");
      block.style.cssText = "display:flex;flex-direction:column;gap:6px;";

      const lbl = document.createElement("label");
      lbl.textContent = this._t(labelKey);
      lbl.style.fontWeight = "500";
      block.appendChild(lbl);

      const row = document.createElement("div");
      row.style.cssText = "display:flex;gap:6px;align-items:center;flex-wrap:wrap;";
      block.appendChild(row);

      const text = document.createElement("input");
      text.type = "text";
      text.placeholder = "/local/bike.webp";
      text.style.cssText = "flex:1 1 220px;min-width:160px;padding:8px;border-radius:4px;border:1px solid var(--divider-color);background:var(--card-background-color);color:var(--primary-text-color);";
      row.appendChild(text);

      const file = document.createElement("input");
      file.type = "file";
      file.accept = "image/*";
      file.style.display = "none";
      row.appendChild(file);

      const uploadBtn = document.createElement("button");
      uploadBtn.type = "button";
      uploadBtn.textContent = this._t("dash_editor_image_upload");
      uploadBtn.style.cssText = "padding:8px 12px;border-radius:4px;border:0;background:var(--primary-color,#03a9f4);color:var(--text-primary-color,#fff);cursor:pointer;font-weight:500;";
      uploadBtn.addEventListener("click", () => file.click());
      row.appendChild(uploadBtn);

      const clearBtn = document.createElement("button");
      clearBtn.type = "button";
      clearBtn.textContent = this._t("dash_editor_image_clear");
      clearBtn.style.cssText = "padding:8px 12px;border-radius:4px;border:1px solid var(--divider-color);background:transparent;color:var(--primary-text-color);cursor:pointer;";
      clearBtn.addEventListener("click", () => {
        text.value = "";
        delete this._config[key];
        this._refreshPreview(preview, "");
        this._emit();
      });
      row.appendChild(clearBtn);

      const status = document.createElement("div");
      status.style.cssText = "font-size:12px;color:var(--secondary-text-color);min-height:16px;";
      block.appendChild(status);

      const preview = document.createElement("div");
      preview.style.cssText = "margin-top:4px;max-width:260px;aspect-ratio:16/10;background:var(--secondary-background-color,#f5f5f5);border-radius:8px;overflow:hidden;display:flex;align-items:center;justify-content:center;";
      block.appendChild(preview);

      if (hintKey) {
        const h = document.createElement("small");
        h.textContent = this._t(hintKey);
        h.style.cssText = "color:var(--secondary-text-color);font-size:11px;";
        block.appendChild(h);
      }

      text.value = this._config[key] || "";
      this._refreshPreview(preview, text.value);

      text.addEventListener("input", () => {
        if (text.value) this._config[key] = text.value;
        else delete this._config[key];
        this._refreshPreview(preview, text.value);
        this._emit();
      });

      file.addEventListener("change", async () => {
        if (!file.files || !file.files[0]) return;
        const picked = file.files[0];
        status.textContent = this._t("dash_editor_image_uploading");
        uploadBtn.disabled = true;
        try {
          const url = await this._uploadImage(picked);
          text.value = url;
          this._config[key] = url;
          this._refreshPreview(preview, url);
          status.textContent = "";
          this._emit();
        } catch (err) {
          console.error("[Bosch eBike Dashboard] image upload failed", err);
          status.textContent = this._t("dash_editor_image_upload_failed") + (err?.message || err);
        } finally {
          uploadBtn.disabled = false;
          file.value = "";
        }
      });

      wrap.appendChild(block);
      return text;  // return text input so _sync() can still set its value
    };

    const titleField = mkText("title", "dash_editor_title");
    const bikeImageField = mkImage("bike_image", "dash_editor_image", "dash_editor_image_hint");

    // Issue #45 follow-up: the bike image (photo or its placeholder) takes
    // up a fixed 16:10 block on the card - make it optional, right next to
    // the field that sets it. Same immutable-update pattern as
    // show_range_pills below: an explicit boolean, never deleted, since a
    // missing key was not reliably picked up through HA's config-changed
    // round-trip for this control.
    const showImageWrap = document.createElement("label");
    showImageWrap.style.cssText = "display:flex;align-items:center;gap:8px;font-size:13px;cursor:pointer;margin-top:-4px;";
    const showImageToggle = document.createElement("input");
    showImageToggle.type = "checkbox";
    showImageToggle.checked = this._config.show_bike_image !== false;
    showImageToggle.addEventListener("change", () => {
      this._config = { ...this._config, show_bike_image: showImageToggle.checked };
      this._emit();
    });
    showImageWrap.appendChild(showImageToggle);
    const showImageLbl = document.createElement("span");
    showImageLbl.textContent = this._t("dash_editor_show_bike_image");
    showImageWrap.appendChild(showImageLbl);
    wrap.appendChild(showImageWrap);

    const bikeNameField = mkText("bike_name", "dash_editor_bike_name", "dash_editor_bike_name_hint");

    this._fields = {
      title: titleField,
      bike_image: bikeImageField,
      bike_name: bikeNameField,
      odometer_entity: mkEntity("odometer_entity", "dash_editor_odo", null,
        ["sensor"]),
      battery_entity: mkEntity("battery_entity", "dash_editor_battery", null,
        ["sensor"]),
      battery_live_entity: mkEntity("battery_live_entity", "dash_editor_battery_live", "dash_editor_battery_live_hint",
        ["sensor"]),
      charging_entity: mkEntity("charging_entity", "dash_editor_charging", null,
        ["binary_sensor", "sensor"]),
      last_tour_distance_entity: mkEntity("last_tour_distance_entity", "dash_editor_last_tour", null,
        ["sensor"]),
      range_entity: mkEntity("range_entity", "dash_editor_range", "dash_editor_range_hint",
        ["sensor"]),
      charge_power_entity: mkEntity("charge_power_entity", "dash_editor_charge_power", null,
        ["sensor"]),
      charge_switch_entity: mkEntity("charge_switch_entity", "dash_editor_charge_switch", null,
        ["switch"]),
      // Both domains work identically here (see the slider's change handler
      // for why): an input_number helper the user created, or the Charge
      // Limiter firmware's own native ESPHome "Charge Limit" number entity.
      target_soc_entity: mkEntity("target_soc_entity", "dash_editor_target_soc", "dash_editor_target_soc_hint",
        ["input_number", "number"]),
    };

    // --- Reichweite je Fahrmodus (Piles) -------------------------------------
    const rangeHead = document.createElement("div");
    rangeHead.textContent = this._t("dash_editor_section_modes");
    rangeHead.style.cssText =
      "margin-top:14px;padding-top:10px;border-top:1px solid var(--divider-color);" +
      "color:var(--secondary-text-color);font-size:12px;line-height:1.4;font-weight:600;";
    wrap.appendChild(rangeHead);

    const rangeToggleWrap = document.createElement("label");
    rangeToggleWrap.style.cssText = "display:flex;align-items:center;gap:8px;font-size:13px;cursor:pointer;";
    const rangeToggle = document.createElement("input");
    rangeToggle.type = "checkbox";
    rangeToggle.checked = this._config.show_range_pills !== false;
    rangeToggle.addEventListener("change", () => {
      // Immutable update: replace _config with a NEW object carrying an
      // explicit boolean. HA's edit dialog tracks the config by identity /
      // value; mutating in place was not reliably picked up for this control,
      // and an explicit boolean (never delete) survives HA's config merge.
      this._config = { ...this._config, show_range_pills: rangeToggle.checked };
      this._emit();
    });
    rangeToggleWrap.appendChild(rangeToggle);
    const rangeToggleLbl = document.createElement("span");
    rangeToggleLbl.textContent = this._t("dash_editor_show_range_pills");
    rangeToggleWrap.appendChild(rangeToggleLbl);
    wrap.appendChild(rangeToggleWrap);

    const modeHint = document.createElement("small");
    modeHint.textContent = this._t("dash_editor_mode_colors_hint");
    modeHint.style.cssText = "color:var(--secondary-text-color);font-size:11px;";
    wrap.appendChild(modeHint);

    this._modeColorsWrap = document.createElement("div");
    this._modeColorsWrap.style.cssText = "display:flex;flex-direction:column;gap:8px;margin-top:4px;";
    wrap.appendChild(this._modeColorsWrap);
    this._renderModeColorRows();

    // --- CO2 / Fahrzeug-Vergleich --------------------------------------------
    const co2Head = document.createElement("div");
    co2Head.textContent = this._t("dash_editor_section_co2");
    co2Head.style.cssText =
      "margin-top:14px;padding-top:10px;border-top:1px solid var(--divider-color);" +
      "color:var(--secondary-text-color);font-size:12px;line-height:1.4;font-weight:600;";
    wrap.appendChild(co2Head);

    const co2Hint = document.createElement("small");
    co2Hint.textContent = this._t("dash_editor_co2_hint");
    co2Hint.style.cssText = "color:var(--secondary-text-color);font-size:11px;";
    wrap.appendChild(co2Hint);

    // Vehicle dropdown
    const lang = (this._hass && this._hass.language) ? this._hass.language.split("-")[0] : "en";
    const vehicleSelect = mk(this._t("dash_editor_vehicle_type"), null, () => {
      const sel = document.createElement("select");
      sel.style.cssText = "padding:8px;border-radius:4px;border:1px solid var(--divider-color);background:var(--card-background-color);color:var(--primary-text-color);";
      for (const [id, preset] of Object.entries(VEHICLE_PRESETS)) {
        const o = document.createElement("option");
        o.value = id;
        o.textContent = preset["label_" + lang] || preset.label_en;
        sel.appendChild(o);
      }
      return sel;
    });
    vehicleSelect.value = this._config.vehicle_comparison || "none";
    vehicleSelect.addEventListener("change", () => {
      if (vehicleSelect.value && vehicleSelect.value !== "none") {
        this._config.vehicle_comparison = vehicleSelect.value;
      } else {
        delete this._config.vehicle_comparison;
      }
      this._emit();
    });
    this._fields.vehicle_comparison = vehicleSelect;

    // Fuel price override
    const fuelPriceInput = mk(this._t("dash_editor_fuel_price"), this._t("dash_editor_fuel_price_hint"), () => {
      const i = document.createElement("input");
      i.type = "number"; i.step = "0.01"; i.min = "0";
      i.style.cssText = "padding:8px;border-radius:4px;border:1px solid var(--divider-color);background:var(--card-background-color);color:var(--primary-text-color);";
      return i;
    });
    fuelPriceInput.value = this._config.fuel_price != null ? String(this._config.fuel_price) : "";
    fuelPriceInput.addEventListener("input", () => {
      const v = fuelPriceInput.value.trim();
      if (v === "") delete this._config.fuel_price;
      else if (Number.isFinite(Number(v))) this._config.fuel_price = Number(v);
      this._emit();
    });
    this._fields.fuel_price = fuelPriceInput;

    // --- Ladekosten-Zusammenfassung -------------------------------------------
    const energyHead = document.createElement("div");
    energyHead.textContent = this._t("dash_editor_section_energy");
    energyHead.style.cssText =
      "margin-top:14px;padding-top:10px;border-top:1px solid var(--divider-color);" +
      "color:var(--secondary-text-color);font-size:12px;line-height:1.4;font-weight:600;";
    wrap.appendChild(energyHead);

    const energyHint = document.createElement("small");
    energyHint.textContent = this._t("dash_editor_energy_hint");
    energyHint.style.cssText = "color:var(--secondary-text-color);font-size:11px;";
    wrap.appendChild(energyHint);

    const energyToggleWrap = document.createElement("label");
    energyToggleWrap.style.cssText = "display:flex;align-items:center;gap:8px;font-size:13px;cursor:pointer;margin-top:6px;";
    const energyToggle = document.createElement("input");
    energyToggle.type = "checkbox";
    energyToggle.checked = this._config.show_energy_cost !== false;
    energyToggle.addEventListener("change", () => {
      this._config = { ...this._config, show_energy_cost: energyToggle.checked };
      this._emit();
    });
    energyToggleWrap.appendChild(energyToggle);
    const energyToggleLbl = document.createElement("span");
    energyToggleLbl.textContent = this._t("dash_editor_show_energy_cost");
    energyToggleWrap.appendChild(energyToggleLbl);
    wrap.appendChild(energyToggleWrap);

    // Price source: fixed value or a referenced entity. Both fields stay
    // visible (same simplicity as the fuel-price field above); energy_price_mode
    // decides which one _renderEnergyCost() actually reads.
    const priceModeSelect = mk(this._t("dash_editor_energy_price_mode"), null, () => {
      const sel = document.createElement("select");
      sel.style.cssText = "padding:8px;border-radius:4px;border:1px solid var(--divider-color);background:var(--card-background-color);color:var(--primary-text-color);";
      for (const [id, labelKey] of [["fixed", "dash_editor_energy_price_mode_fixed"], ["entity", "dash_editor_energy_price_mode_entity"]]) {
        const o = document.createElement("option");
        o.value = id;
        o.textContent = this._t(labelKey);
        sel.appendChild(o);
      }
      return sel;
    });
    priceModeSelect.value = this._config.energy_price_mode === "entity" ? "entity" : "fixed";
    priceModeSelect.addEventListener("change", () => {
      this._config = { ...this._config, energy_price_mode: priceModeSelect.value };
      this._emit();
    });
    this._fields.energy_price_mode = priceModeSelect;

    const energyPriceFixedInput = mk(this._t("dash_editor_energy_price_fixed"), this._t("dash_editor_energy_price_fixed_hint"), () => {
      const i = document.createElement("input");
      i.type = "number"; i.step = "0.01"; i.min = "0";
      i.style.cssText = "padding:8px;border-radius:4px;border:1px solid var(--divider-color);background:var(--card-background-color);color:var(--primary-text-color);";
      return i;
    });
    energyPriceFixedInput.value = this._config.energy_price_fixed != null ? String(this._config.energy_price_fixed) : "0.23";
    energyPriceFixedInput.addEventListener("input", () => {
      const v = energyPriceFixedInput.value.trim();
      if (v === "") delete this._config.energy_price_fixed;
      else if (Number.isFinite(Number(v))) this._config.energy_price_fixed = Number(v);
      this._emit();
    });
    this._fields.energy_price_fixed = energyPriceFixedInput;

    this._fields.energy_price_entity = mkEntity(
      "energy_price_entity", "dash_editor_energy_price_entity", "dash_editor_energy_price_entity_hint", ["sensor", "input_number"]
    );

    const energyEntitiesHint = document.createElement("small");
    energyEntitiesHint.textContent = this._t("dash_editor_energy_entities_hint");
    energyEntitiesHint.style.cssText = "color:var(--secondary-text-color);font-size:11px;";
    wrap.appendChild(energyEntitiesHint);

    this._fields.energy_week_entity = mkEntity("energy_week_entity", "dash_editor_energy_week_entity", null, ["sensor"]);
    this._fields.energy_month_entity = mkEntity("energy_month_entity", "dash_editor_energy_month_entity", null, ["sensor"]);
    this._fields.energy_year_entity = mkEntity("energy_year_entity", "dash_editor_energy_year_entity", null, ["sensor"]);

    const mkPeriodToggle = (configKey, labelKey) => {
      const toggleWrap = document.createElement("label");
      toggleWrap.style.cssText = "display:flex;align-items:center;gap:8px;font-size:13px;cursor:pointer;";
      const toggle = document.createElement("input");
      toggle.type = "checkbox";
      toggle.checked = this._config[configKey] !== false;
      toggle.addEventListener("change", () => {
        this._config = { ...this._config, [configKey]: toggle.checked };
        this._emit();
      });
      toggleWrap.appendChild(toggle);
      const toggleLbl = document.createElement("span");
      toggleLbl.textContent = this._t(labelKey);
      toggleWrap.appendChild(toggleLbl);
      wrap.appendChild(toggleWrap);
      return toggle;
    };
    this._fields.show_cost_week = mkPeriodToggle("show_cost_week", "dash_editor_show_cost_week");
    this._fields.show_cost_month = mkPeriodToggle("show_cost_month", "dash_editor_show_cost_month");
    this._fields.show_cost_year = mkPeriodToggle("show_cost_year", "dash_editor_show_cost_year");

    // --- Bike-Picker (für Wartung) -------------------------------------------
    // Wartung lebt jetzt in HA-Storage und ist per Bike gescopt. Wenn
    // hier kein Bike gewählt ist, blendet die Card die Wartungs-Sektion
    // aus. Wir laden die Bike-Liste asynchron - der Picker bleibt
    // sichtbar (mit nur "—" als Option), bis list_instances kommt.
    const bikeHead = document.createElement("div");
    bikeHead.textContent = this._t("dash_editor_section_maint");
    bikeHead.style.cssText =
      "margin-top:14px;padding-top:10px;border-top:1px solid var(--divider-color);" +
      "color:var(--secondary-text-color);font-size:12px;line-height:1.4;font-weight:600;";
    wrap.appendChild(bikeHead);

    // Hilfsfunktionen: lesen die aktuell wirksamen Warnschwellen aus
    // dem Shared-Store (mit Cascade). Werden auch fuer den live-aktuali-
    // sierten Hint-Text und die Initialwerte der beiden Inputs genutzt.
    const readWarnKm = () => {
      const raw = readCardSetting(this._config, "maint_warn_km", MAINT_WARN_KM_DEFAULT);
      const n = Number(raw);
      return Number.isFinite(n) && n >= 0 ? Math.round(n) : MAINT_WARN_KM_DEFAULT;
    };
    const readWarnDays = () => {
      const raw = readCardSetting(this._config, "maint_warn_days", MAINT_WARN_DAYS_DEFAULT);
      const n = Number(raw);
      return Number.isFinite(n) && n >= 0 ? Math.round(n) : MAINT_WARN_DAYS_DEFAULT;
    };

    const maintHint = document.createElement("small");
    this._refreshMaintHint = () => {
      maintHint.textContent = this._t("dash_editor_maint_hint", readWarnDays(), readWarnKm());
    };
    this._refreshMaintHint();
    maintHint.style.cssText = "color:var(--secondary-text-color);font-size:11px;display:block;margin-bottom:8px;";
    wrap.appendChild(maintHint);

    // Warnschwellen (km / Tage). Number-Inputs, debouncetes Schreiben
    // in den Shared-Store - selbe Pattern wie der 3D-Card-Editor. Beim
    // Aendern wird der maintHint sofort lokal aktualisiert, der Bus
    // benachrichtigt parallel andere offene Dashboards. Refs werden in
    // this._warnInputs gesammelt, damit _syncSharedFields() sie nach
    // dem asynchronen Cache-Load nachziehen kann.
    if (!this._sharedSaveTimers) this._sharedSaveTimers = new Map();
    this._warnInputs = [];
    const mkWarnInput = (key, labelKey, hintKey, defaultVal, min, max) => {
      const input = mk(this._t(labelKey), this._t(hintKey), () => {
        const i = document.createElement("input");
        i.type = "number"; i.step = "1";
        i.min = String(min); i.max = String(max);
        i.style.cssText = "padding:8px;border-radius:4px;border:1px solid var(--divider-color);background:var(--card-background-color);color:var(--primary-text-color);";
        return i;
      });
      const current = readCardSetting(this._config, key, defaultVal);
      input.value = current != null && current !== "" ? String(current) : String(defaultVal);
      input.addEventListener("input", () => {
        const v = input.value;
        if (this._sharedSaveTimers.has(key)) clearTimeout(this._sharedSaveTimers.get(key));
        this._sharedSaveTimers.set(key, setTimeout(() => {
          this._sharedSaveTimers.delete(key);
          // Leer / unsinnig -> Default wiederherstellen (null im Store)
          const num = v === "" ? null : Number(v);
          const safe = num == null || !Number.isFinite(num) || num < 0
            ? null
            : Math.max(min, Math.min(max, Math.round(num)));
          // Card-YAML-Override entfernen, damit der Shared-Wert gewinnt
          if (this._config[key] != null) {
            delete this._config[key];
            this._emit();
          }
          saveCardSetting(this._hass, key, safe);
          this._refreshMaintHint();
        }, 400));
      });
      this._warnInputs.push({ key, input, defaultVal });
      return input;
    };
    mkWarnInput("maint_warn_km", "dash_editor_maint_warn_km", "dash_editor_maint_warn_km_hint", MAINT_WARN_KM_DEFAULT, 0, 100000);
    mkWarnInput("maint_warn_days", "dash_editor_maint_warn_days", "dash_editor_maint_warn_days_hint", MAINT_WARN_DAYS_DEFAULT, 0, 3650);

    const bikeSelect = mk(this._t("dash_editor_bike_id"), null, () => {
      const sel = document.createElement("select");
      sel.style.cssText = "padding:8px;border-radius:4px;border:1px solid var(--divider-color);background:var(--card-background-color);color:var(--primary-text-color);";
      const opt0 = document.createElement("option");
      opt0.value = ""; opt0.textContent = "—";
      sel.appendChild(opt0);
      return sel;
    });
    this._bikeSelect = bikeSelect;
    this._fields.bike_id = bikeSelect;
    bikeSelect.value = this._config.bike_id || "";
    bikeSelect.addEventListener("change", () => {
      if (bikeSelect.value) this._config.bike_id = bikeSelect.value;
      else delete this._config.bike_id;
      this._emit();
      // Bei Bike-Wechsel: Liste komplett neu laden
      this._maintItemsCache = null;
      this._maintListLoadedFor = null;
      this._reloadMaintList();
    });
    // Asynchron Bike-Liste reinstreuen, sobald hass verfügbar.
    this._populateBikeSelect();

    // Liste der Wartungen + Add-Button
    this._maintListWrap = document.createElement("div");
    this._maintListWrap.id = "dash-ed-maint-list";
    wrap.appendChild(this._maintListWrap);

    const addBtn = document.createElement("button");
    addBtn.type = "button";
    addBtn.className = "dash-ed-add";
    addBtn.textContent = this._t("dash_editor_maint_add");
    addBtn.addEventListener("click", () => this._handleAddMaintenance());
    this._maintAddBtn = addBtn;
    wrap.appendChild(addBtn);

    // Inline-style fürs Editor-Wartungs-Layout. Editor läuft im Lovelace-
    // Editor-DOM und hat keinen eigenen <style>-Block; deshalb in den
    // document head injecten (idempotent über die ID).
    if (!document.getElementById("dash-ed-maint-styles")) {
      const ss = document.createElement("style");
      ss.id = "dash-ed-maint-styles";
      ss.textContent = `
        .dash-ed-maint-row {
          display: grid;
          grid-template-columns: minmax(140px,1fr) 100px 90px 140px auto auto;
          gap: 8px; align-items: end;
          padding: 8px; border-radius: 8px;
          background: var(--secondary-background-color, #f4f6f8);
          margin-bottom: 6px;
        }
        .dash-ed-maint-row > div { display: flex; flex-direction: column; gap: 2px; }
        .dash-ed-maint-row label {
          font-size: 10px; color: var(--secondary-text-color);
          text-transform: uppercase; letter-spacing: .04em;
        }
        .dash-ed-maint-row input, .dash-ed-maint-row select {
          padding: 6px 8px; border-radius: 4px;
          border: 1px solid var(--divider-color);
          background: var(--card-background-color);
          color: var(--primary-text-color); font-size: 13px;
          width: 100%; box-sizing: border-box;
        }
        .dash-ed-maint-row button.remove {
          background: transparent; border: 0; color: #e53935;
          cursor: pointer; padding: 6px; font-size: 18px;
          align-self: end;
        }
        .dash-ed-maint-empty {
          padding: 10px 12px; font-size: 12px;
          color: var(--secondary-text-color); font-style: italic;
        }
        @media (max-width: 600px) {
          .dash-ed-maint-row { grid-template-columns: 1fr; }
        }
      `;
      document.head.appendChild(ss);
    }
    this._reloadMaintList();

    this._built = true;
  }

  // Bike-Dropdown asynchron mit list_instances befüllen. Wartet via
  // setInterval auf hass, falls dieses später ankommt - der Editor
  // wird manchmal vor dem set hass() vom Lovelace-Editor gemounted.
  _populateBikeSelect() {
    if (!this._bikeSelect) return;
    if (!this._hass) { setTimeout(() => this._populateBikeSelect(), 200); return; }
    this._hass.callWS({ type: "bosch_ebike/list_instances" })
      .then((res) => {
        const sel = this._bikeSelect;
        if (!sel) return;
        // Bestehende non-"—" Optionen entfernen, damit ein erneutes
        // Befüllen (z. B. nach Reconnect) keine Duplikate erzeugt.
        for (let i = sel.options.length - 1; i >= 1; i--) sel.remove(i);
        for (const inst of (res?.instances || [])) {
          for (const bike of (inst.bikes || [])) {
            const o = document.createElement("option");
            o.value = bike.id;
            const accLabel = inst.label && res.instances.length > 1 ? `${inst.label} — ` : "";
            o.textContent = `${accLabel}${bike.label || bike.id}`;
            sel.appendChild(o);
          }
        }
        sel.value = this._config.bike_id || "";
      })
      .catch(() => { /* ignore - selector bleibt mit "—" */ });
  }

  // Lädt ALLE Wartungen aller Bikes für den Editor. Macht die Liste
  // unabhängig vom Bike-Picker oben - der wird nur noch für "Add"
  // gebraucht. So kann der User Wartungen bearbeiten/löschen/erledigen
  // auch ohne die Card-Config umzukonfigurieren.
  async _reloadMaintList() {
    if (!this._maintListWrap) return;
    if (this._maintAddBtn) this._maintAddBtn.disabled = !this._hass;
    if (!this._hass) return;
    try {
      const res = await this._hass.callWS({ type: "bosch_ebike/list_maintenance" });
      const bikes = res?.bikes || [];
      // Flach mit bike_id + bike_label pro Item, damit Mutationen die
      // richtige Bike-Zuordnung haben.
      this._maintItemsCache = bikes.flatMap((b) =>
        (b.items || []).map((i) => ({
          ...i,
          bike_id: b.bike_id,
          bike_label: b.bike_label || b.bike_id,
        }))
      );
      this._allBikes = bikes;
      this._renderMaintRowsFromCache();
    } catch (err) {
      console.warn("[Bosch eBike Dashboard-Editor] list_maintenance failed:", err?.message || err);
    }
  }

  // Renders alle Rows aus this._maintItemsCache neu. Wird gerufen
  // nach Bike-Wechsel oder Type-Switch innerhalb einer Row; NICHT bei
  // jedem Keystroke (das würde die alten Inputs wegwerfen und den
  // Fokus killen - exakt der Bug aus v1.16.5).
  _renderMaintRowsFromCache() {
    if (!this._maintListWrap) return;
    this._maintListWrap.innerHTML = "";
    const items = Array.isArray(this._maintItemsCache) ? this._maintItemsCache : [];
    if (!items.length) {
      const p = document.createElement("div");
      p.className = "dash-ed-maint-empty";
      p.textContent = this._t("dash_editor_maint_none_yet");
      this._maintListWrap.appendChild(p);
      return;
    }
    for (const item of items) this._maintListWrap.appendChild(this._buildMaintRow(item));
  }

  // Erstellt EINE Row für ein Item. Inputs binden direkt an
  // debouncedUpdate (KEIN this._emit()) - das ist der Hauptgrund,
  // warum der Fokus jetzt erhalten bleibt: keine Lovelace-Roundtrips
  // bei Maintenance-Edits.
  _buildMaintRow(item) {
    const lang = (this._hass && this._hass.language) ? this._hass.language.split("-")[0] : "en";
    const presetLabel = (p) => p["label_" + lang] || p.label_en;
    const row = document.createElement("div");
    row.className = "dash-ed-maint-row";
    row.dataset.itemId = item.id;
    row.dataset.bikeId = item.bike_id || "";

    // Bike-Label, falls mehr als ein Bike konfiguriert ist - hilft
    // dem User, Wartungen verschiedener Bikes auseinanderzuhalten.
    const multipleBikes = Array.isArray(this._allBikes) && this._allBikes.length > 1;
    if (multipleBikes && item.bike_label) {
      const bikeBadge = document.createElement("div");
      bikeBadge.style.cssText =
        "grid-column: 1 / -1; font-size: 11px; color: var(--secondary-text-color);" +
        "font-weight: 500; text-transform: uppercase; letter-spacing: .04em;";
      bikeBadge.textContent = item.bike_label;
      row.appendChild(bikeBadge);
    }

    // Bestimmt den Typ aus den vorhandenen Intervallen. Das Backend
    // erlaubt beide gleichzeitig, der Editor zeigt aber nur einen.
    // Wichtig: Number(null) ist 0 und Number.isFinite(0) ist true,
    // daher MUSS hier explizit auf != null geprüft werden.
    const hasKm = item.interval_km != null && Number.isFinite(Number(item.interval_km));
    const hasDays = item.interval_days != null && Number.isFinite(Number(item.interval_days));
    // Self-Repair: wenn beide Intervalle gesetzt sind, ist das ein
    // inkonsistenter Zustand. Frühere Bugs (Debouncer-Races beim
    // Typ-Switch) konnten dazu führen, dass der "alte" Wert nach dem
    // Wechsel wieder ins Backend lief. Auflösung: beim Render die
    // Datumsseite bevorzugen (typisch für 'Kundendienst alle X Tage')
    // und silently einen Patch senden, der interval_km löscht. Das
    // ist non-destruktiv: der User kann jederzeit per Typ-Dropdown
    // zurück auf km wechseln; das setzt dann einen frischen Default.
    if (hasKm && hasDays) {
      this._sendUpdateMaint(item, { interval_km: null });
      item.interval_km = null;
    }
    const cleanHasKm = item.interval_km != null && Number.isFinite(Number(item.interval_km));
    const cleanHasDays = item.interval_days != null && Number.isFinite(Number(item.interval_days));
    const initialType = cleanHasKm ? "km" : (cleanHasDays ? "date" : "km");
    let currentType = initialType;

    // -- Name (Dropdown + freier Text) --
    const nameWrap = document.createElement("div");
    nameWrap.innerHTML = `<label>${this._t("dash_editor_maint_name")}</label>`;
    const nameSel = document.createElement("select");
    const customOpt = document.createElement("option");
    customOpt.value = "__custom__";
    customOpt.textContent = this._t("dash_editor_maint_name_custom");
    nameSel.appendChild(customOpt);
    for (const preset of MAINTENANCE_PRESETS) {
      const o = document.createElement("option");
      o.value = preset["label_" + lang] || preset.label_en;
      o.textContent = o.value;
      nameSel.appendChild(o);
    }
    const matchingPreset = MAINTENANCE_PRESETS.find(p => presetLabel(p) === item.name);
    nameSel.value = matchingPreset ? item.name : "__custom__";
    const nameInput = document.createElement("input");
    nameInput.type = "text";
    nameInput.value = item.name || "";
    nameInput.placeholder = this._t("dash_editor_maint_name");
    nameInput.style.marginTop = "4px";
    nameInput.style.display = matchingPreset ? "none" : "";
    nameSel.addEventListener("change", () => {
      if (nameSel.value === "__custom__") {
        nameInput.style.display = "";
        nameInput.focus();
      } else {
        nameInput.value = nameSel.value;
        nameInput.style.display = "none";
        this._debouncedUpdateMaint(item, { name: nameSel.value });
      }
    });
    nameInput.addEventListener("input", () => {
      this._debouncedUpdateMaint(item, { name: nameInput.value });
    });
    nameWrap.appendChild(nameSel);
    nameWrap.appendChild(nameInput);
    row.appendChild(nameWrap);

    // -- Typ --
    const typeWrap = document.createElement("div");
    typeWrap.innerHTML = `<label>${this._t("dash_editor_maint_type")}</label>`;
    const typeSel = document.createElement("select");
    const optKm = document.createElement("option");
    optKm.value = "km"; optKm.textContent = this._t("dash_editor_maint_type_km");
    typeSel.appendChild(optKm);
    const optDate = document.createElement("option");
    optDate.value = "date"; optDate.textContent = this._t("dash_editor_maint_type_date");
    typeSel.appendChild(optDate);
    typeSel.value = initialType;
    typeSel.addEventListener("change", () => {
      currentType = typeSel.value;
      // Beim Typ-Wechsel: Interval umstellen (eines clearen, anderes
      // mit Default belegen). Wir senden das in einem Call.
      const patch = {};
      if (currentType === "km") {
        patch.interval_km = Number.isFinite(Number(item.interval_km)) ? Number(item.interval_km) : 500;
        patch.interval_days = null;
      } else {
        patch.interval_days = Number.isFinite(Number(item.interval_days)) ? Number(item.interval_days) : 30;
        patch.interval_km = null;
      }
      this._sendUpdateMaint(item, patch);
      // Update lokales Item + die Interval-Row neu rendern (nur diese
      // Zeile, nicht die ganze Liste -> kein Fokus-Verlust bei den
      // anderen Reihen).
      Object.assign(item, patch);
      const newRow = this._buildMaintRow(item);
      row.replaceWith(newRow);
    });
    typeWrap.appendChild(typeSel);
    row.appendChild(typeWrap);

    // -- Interval --
    const intWrap = document.createElement("div");
    const intLabel = currentType === "date"
      ? this._t("dash_editor_maint_interval_days")
      : this._t("dash_editor_maint_interval_km");
    intWrap.innerHTML = `<label>${intLabel}</label>`;
    const intInput = document.createElement("input");
    intInput.type = "number"; intInput.min = "1";
    intInput.value = currentType === "date"
      ? (item.interval_days != null ? String(item.interval_days) : "")
      : (item.interval_km != null ? String(item.interval_km) : "");
    intInput.addEventListener("input", () => {
      const v = Number(intInput.value);
      if (!Number.isFinite(v) || v <= 0) return;
      if (currentType === "date") this._debouncedUpdateMaint(item, { interval_days: v });
      else this._debouncedUpdateMaint(item, { interval_km: v });
    });
    intWrap.appendChild(intInput);
    row.appendChild(intWrap);

    // -- Last done (km bzw. Datum, je nach Typ) ---------------------------
    // Beim Add ist der Wert vom Backend bereits auf "jetzt" gesetzt
    // (km = current_odo, date = now). Der User kann hier eintragen,
    // dass die Wartung in der Vergangenheit gemacht wurde.
    const lastWrap = document.createElement("div");
    const lastLabel = currentType === "date"
      ? this._t("dash_editor_maint_last_date")
      : this._t("dash_editor_maint_last_km");
    lastWrap.innerHTML = `<label>${lastLabel}</label>`;
    const lastInput = document.createElement("input");
    if (currentType === "date") {
      lastInput.type = "date";
      const v = item.last_done_at;
      lastInput.value = v ? String(v).slice(0, 10) : "";
      lastInput.addEventListener("change", () => {
        if (!lastInput.value) return;
        // YYYY-MM-DD -> ISO mit T00:00:00Z, damit das Backend einen
        // sauberen, zeitzonenstabilen Stempel speichert.
        const iso = new Date(lastInput.value + "T00:00:00Z").toISOString();
        this._debouncedUpdateMaint(item, { last_done_at: iso });
      });
    } else {
      lastInput.type = "number"; lastInput.min = "0"; lastInput.step = "0.1";
      // Backend speichert Meter, UI zeigt km. Umrechnung nur in eine
      // Richtung; Anzeige rundet auf eine Nachkommastelle wenn nötig.
      const m = item.last_done_odometer;
      lastInput.value = (m != null && Number.isFinite(Number(m))) ? String(Number(m) / 1000) : "";
      lastInput.addEventListener("input", () => {
        const km = Number(lastInput.value);
        if (!Number.isFinite(km) || km < 0) return;
        this._debouncedUpdateMaint(item, { last_done_odometer: km * 1000 });
      });
    }
    lastWrap.appendChild(lastInput);
    row.appendChild(lastWrap);

    // -- Done --
    const doneBtn = document.createElement("button");
    doneBtn.type = "button";
    doneBtn.className = "ed-maint-done";
    doneBtn.title = this._t("dash_maint_done_btn");
    doneBtn.setAttribute("aria-label", this._t("dash_maint_done_btn"));
    doneBtn.innerHTML =
      '<svg viewBox="0 0 24 24" width="18" height="18">' +
      '<path fill="currentColor" d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/>' +
      "</svg>";
    doneBtn.style.cssText =
      "background:#2e7d32;color:#fff;border:0;width:30px;height:30px;" +
      "border-radius:50%;cursor:pointer;display:inline-flex;" +
      "align-items:center;justify-content:center;align-self:end;" +
      "box-shadow:0 1px 4px rgba(0,0,0,.2);";
    doneBtn.addEventListener("click", () => this._handleCompleteMaintenance(item));
    row.appendChild(doneBtn);

    // -- Remove --
    const rmBtn = document.createElement("button");
    rmBtn.type = "button";
    rmBtn.className = "remove";
    rmBtn.title = this._t("dash_editor_maint_remove");
    rmBtn.innerHTML = "&times;";
    rmBtn.addEventListener("click", () => this._handleRemoveMaintenance(item, row));
    row.appendChild(rmBtn);

    return row;
  }

  // Anlegen via WS + DOM appendOnly (kein Re-Render). Item-Defaults:
  // leerer Name, km-Trigger, 500 km Intervall. Der Backend gibt uns
  // die neue ID zurück.
  // Findet die Bike-ID für eine neue Wartung. Bevorzugt das im Editor
  // gewählte Bike. Wenn das leer ist und genau ein Bike existiert,
  // nimmt automatisch das. Sonst null - Caller zeigt eine kurze
  // Fehlermeldung an, damit der User den Picker setzt.
  _resolveAddBikeId() {
    if (this._config.bike_id) return this._config.bike_id;
    const bikes = Array.isArray(this._allBikes) ? this._allBikes : [];
    if (bikes.length === 1 && bikes[0].bike_id) return bikes[0].bike_id;
    return null;
  }

  async _handleAddMaintenance() {
    const bikeId = this._resolveAddBikeId();
    if (!bikeId) {
      alert(this._t("dash_editor_maint_pick_bike"));
      return;
    }
    if (!this._hass) return;
    try {
      const res = await this._hass.callWS({
        type: "bosch_ebike/add_maintenance",
        bike_id: bikeId,
        name: "",
        interval_km: 500,
      });
      const bikeLabel = (this._allBikes || []).find((b) => b.bike_id === bikeId)?.bike_label
        || bikeId;
      const newItem = {
        id: res.id, name: "", interval_km: 500, interval_days: null,
        bike_id: bikeId, bike_label: bikeLabel,
      };
      if (!Array.isArray(this._maintItemsCache)) this._maintItemsCache = [];
      this._maintItemsCache.push(newItem);
      const placeholder = this._maintListWrap.querySelector(".dash-ed-maint-empty");
      if (placeholder) placeholder.remove();
      this._maintListWrap.appendChild(this._buildMaintRow(newItem));
      _cardSettingsBus.dispatchEvent(new Event("changed"));
    } catch (err) {
      console.warn("[Bosch eBike Dashboard-Editor] add_maintenance failed:", err?.message || err);
      alert(ebT(this._hass, "err_add_maintenance_failed", err?.message || err));
    }
  }

  async _handleRemoveMaintenance(item, rowEl) {
    if (!item || !item.bike_id || !this._hass) return;
    try {
      await this._hass.callWS({
        type: "bosch_ebike/remove_maintenance",
        bike_id: item.bike_id,
        item_id: item.id,
      });
      this._maintItemsCache = (this._maintItemsCache || []).filter((i) => i.id !== item.id);
      rowEl.remove();
      if (!this._maintItemsCache.length) this._renderMaintRowsFromCache();
      _cardSettingsBus.dispatchEvent(new Event("changed"));
    } catch (err) {
      console.warn("[Bosch eBike Dashboard-Editor] remove_maintenance failed:", err?.message || err);
      alert(ebT(this._hass, "err_remove_maintenance_failed", err?.message || err));
    }
  }

  // "Erledigt"-Knopf im Editor: setzt last_done_at/odometer für das
  // Item. Der Backend liest current_odo automatisch aus dem Coordinator;
  // wir müssen nur bike_id + item_id schicken.
  async _handleCompleteMaintenance(item) {
    if (!item || !item.bike_id || !this._hass) return;
    try {
      await this._hass.callWS({
        type: "bosch_ebike/complete_maintenance",
        bike_id: item.bike_id,
        item_id: item.id,
      });
      // Visuelles Feedback - Bus-Echo lädt die Liste, aber der Klick
      // soll sich sofort bestätigt anfühlen.
      const flash = document.createElement("div");
      flash.textContent = "✓";
      flash.style.cssText =
        "position:fixed;top:20px;left:50%;transform:translateX(-50%);" +
        "background:#2e7d32;color:#fff;padding:8px 24px;border-radius:999px;" +
        "font-size:22px;z-index:99999;box-shadow:0 2px 12px rgba(0,0,0,.3);" +
        "pointer-events:none;";
      document.body.appendChild(flash);
      setTimeout(() => flash.remove(), 800);
      // Neuladen, damit die Werte (last_done_*, remaining_*) frisch
      // angezeigt werden. Bus-Echo benachrichtigt die Dashboard-Card,
      // sofern sie auf der gleichen Page lebt.
      this._reloadMaintList();
      _cardSettingsBus.dispatchEvent(new Event("changed"));
    } catch (err) {
      console.warn("[Bosch eBike Dashboard-Editor] complete_maintenance failed:", err?.message || err);
      alert(ebT(this._hass, "err_complete_maintenance_failed", err?.message || err));
    }
  }

  // Debouncer pro Item, damit jeder Keystroke nicht direkt einen
  // WebSocket-Call auslöst.
  _debouncedUpdateMaint(item, patch) {
    if (!this._maintDebounceTimers) this._maintDebounceTimers = new Map();
    if (!this._maintDebouncePending) this._maintDebouncePending = new Map();
    const key = item.id;
    const merged = Object.assign(this._maintDebouncePending.get(key) || {}, patch);
    this._maintDebouncePending.set(key, merged);
    if (this._maintDebounceTimers.has(key)) {
      clearTimeout(this._maintDebounceTimers.get(key));
    }
    this._maintDebounceTimers.set(key, setTimeout(() => {
      const finalPatch = this._maintDebouncePending.get(key) || {};
      this._maintDebouncePending.delete(key);
      this._maintDebounceTimers.delete(key);
      this._sendUpdateMaint(item, finalPatch);
    }, 400));
  }

  async _sendUpdateMaint(item, patch) {
    if (!item || !item.bike_id || !this._hass) return;
    try {
      await this._hass.callWS({
        type: "bosch_ebike/update_maintenance",
        bike_id: item.bike_id,
        item_id: item.id,
        ...patch,
      });
      const cached = (this._maintItemsCache || []).find((i) => i.id === item.id);
      if (cached) Object.assign(cached, patch);
      // Bus-Echo, damit eine offene Dashboard-Card (oder eine zweite
      // Editor-Instanz) ihre Items frisch nachlaedt.
      _cardSettingsBus.dispatchEvent(new Event("changed"));
    } catch (err) {
      console.warn("[Bosch eBike Dashboard-Editor] update_maintenance failed:", err?.message || err);
      alert(ebT(this._hass, "err_update_maintenance_failed", err?.message || err));
    }
  }

  _sync() {
    if (!this._fields) return;
    for (const [key, input] of Object.entries(this._fields)) {
      // vehicle_comparison/fuel_price/energy_price_mode/energy_price_fixed
      // brauchen Sonderfälle (Select-Default bzw. ein tatsächlich wirksamer
      // Default statt leerem Feld bei fehlendem Override).
      if (key === "vehicle_comparison") {
        input.value = this._config.vehicle_comparison || "none";
      } else if (key === "fuel_price") {
        input.value = this._config.fuel_price != null ? String(this._config.fuel_price) : "";
      } else if (key === "energy_price_mode") {
        input.value = this._config.energy_price_mode === "entity" ? "entity" : "fixed";
      } else if (key === "energy_price_fixed") {
        input.value = this._config.energy_price_fixed != null ? String(this._config.energy_price_fixed) : "0.23";
      } else {
        input.value = this._config[key] || "";
      }
    }
    // Maintenance-Liste NICHT mehr hier rendern - sie lebt im Backend,
    // nicht in der card config, und ein Re-Render nach jedem
    // config-changed-Roundtrip (siehe v1.16.5-Bug) hat den Eingabe-
    // Fokus weggeschossen. Beim Bike-Wechsel via Picker triggern wir
    // _reloadMaintList explizit dort.
  }

  _refreshPreview(container, url) {
    if (!container) return;
    container.innerHTML = "";
    if (!url) {
      const ph = document.createElement("ha-icon");
      ph.setAttribute("icon", "mdi:image-outline");
      ph.style.cssText = "--mdc-icon-size:36px;color:var(--secondary-text-color);";
      container.appendChild(ph);
      return;
    }
    const img = document.createElement("img");
    img.src = url;
    img.alt = "preview";
    img.style.cssText = "max-width:100%;max-height:100%;object-fit:contain;";
    img.addEventListener("error", () => {
      container.innerHTML = "";
      const broken = document.createElement("ha-icon");
      broken.setAttribute("icon", "mdi:image-broken-variant");
      broken.style.cssText = "--mdc-icon-size:36px;color:#e53935;";
      container.appendChild(broken);
    });
    container.appendChild(img);
  }

  async _uploadImage(file) {
    if (!this._hass) throw new Error("Home Assistant connection not available");
    const token = this._hass.auth && this._hass.auth.data && this._hass.auth.data.access_token;
    if (!token) throw new Error("No access token available");

    // HA's image_upload endpoint imposes a 10 MB ceiling and rejects formats
    // PIL cannot decode. Surface that upfront so the user does not chase a
    // network error when the file is simply too big.
    const MAX_BYTES = 10 * 1024 * 1024;
    if (file.size > MAX_BYTES) {
      throw new Error(`File too large (${(file.size / 1024 / 1024).toFixed(1)} MB, max 10 MB)`);
    }

    const fd = new FormData();
    fd.append("file", file, file.name || "bike.webp");
    const resp = await fetch("/api/image/upload", {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      body: fd,
    });
    if (!resp.ok) {
      // Try JSON first, fall back to plain text so the user sees the server's
      // own message (e.g. "Unable to decode image") in the editor.
      let detail = "";
      const ctype = resp.headers.get("content-type") || "";
      try {
        if (ctype.includes("application/json")) {
          const j = await resp.json();
          detail = j?.message || j?.error || JSON.stringify(j);
        } else {
          detail = (await resp.text()).slice(0, 200);
        }
      } catch (_) { /* ignore */ }
      throw new Error(`HTTP ${resp.status}${detail ? " - " + detail : ""}`);
    }
    const data = await resp.json();
    if (!data || !data.id) throw new Error("Upload response missing id");
    return `/api/image/serve/${data.id}/original`;
  }
}

// ===========================================================================
// 3D Map card: MapLibre + OpenFreeMap, opens individual tours in 3D with
// a time slider, animated marker and sun-mood lighting.
//
// Architecture:
// - Initial view: scrollable list of recent tours matching the configured
//   filters (account_id / bike_id, locked via card YAML).
// - Detail view: click a tour, swap to 3D map. Track polyline, animated
//   marker, time slider, play/pause, info chips, back-button.
// - MapLibre is lazy-loaded from CDN the first time the card mounts.
// ===========================================================================
class BoschEBike3DMapCard extends HTMLElement {
  constructor() {
    super();
    this._hass = null;
    this._config = {};
    this._instances = [];
    this._activities = [];
    this._allActivities = [];
    this._filterAccount = "all";
    this._filterBike = "all";
    this._lockedAccount = false;
    this._lockedBike = false;
    this._ready = false;
    this._booting = false;
    this._mode = "list";          // "list" or "detail"
    this._currentActivity = null;
    this._currentTrack = null;
    this._weatherSeries = null;   // hourly series for the open tour (Task 7), or null when off/unfetched
    this._map = null;
    this._marker = null;
    this._fitDone = false;
    this._animRAF = null;
    this._animStartTs = 0;
    this._animStartIndex = 0;
    this._isPlaying = false;
    this._cumDist = null;
    this._totalDistM = 0;
    this._mapInitEpoch = 0;
    this._configStr = null;
  }

  setConfig(config) {
    // HA tends to call setConfig multiple times during a dashboard load.
    // If the config is byte-for-byte identical to the one we already
    // have, skip the work: re-rendering the detail view would tear down
    // the live MapLibre map and recreate it, which both flashes and
    // wipes the markers/track that the user is looking at.
    const newStr = JSON.stringify(config || {});
    if (this._configStr === newStr) return;
    this._configStr = newStr;

    this._config = { ...config };
    if (config.account_id) { this._filterAccount = config.account_id; this._lockedAccount = true; }
    if (config.bike_id) { this._filterBike = config.bike_id; this._lockedBike = true; }
    if (this._ready) {
      this._applyHeight();
      this._renderRoot();
    }
  }

  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    if (first) this._boot();
  }

  // Detach global listeners + release the scroll lock if the host is
  // removed from the DOM while still in pseudo-fullscreen.
  disconnectedCallback() {
    if (this._fsChangeHandler) {
      document.removeEventListener("fullscreenchange", this._fsChangeHandler);
      document.removeEventListener("webkitfullscreenchange", this._fsChangeHandler);
      this._fsChangeHandler = null;
    }
    if (this._pseudoEscHandler) {
      document.removeEventListener("keydown", this._pseudoEscHandler);
      this._pseudoEscHandler = null;
    }
    if (this._pseudoFullscreen) {
      this._pseudoFullscreen = false;
      this.classList.remove("map3d-pseudo-fs");
      document.body.style.overflow = "";
    }
    if (this._cardSettingsHandler) {
      _cardSettingsBus.removeEventListener("changed", this._cardSettingsHandler);
      this._cardSettingsHandler = null;
    }
    this._teardownIdleFade();
  }

  static getConfigElement() { return document.createElement("bosch-ebike-3d-map-card-editor"); }
  static getStubConfig() {
    return {
      height: 540, default_pitch: 55, chase_zoom: 17, chase_lookahead: 30,
      smooth_window: 15, track_smooth_window: 3, playback_speed: 60,
      terrain_exaggeration: 1.5,
      satellite_tile_url: "", satellite_max_zoom: 14,
      north_up: 0,
      show_date: 1, show_time: 1, show_sun: 1,
      show_speed: 1, show_distance: 1, show_elevation: 1,
      stats_as_chips: 0, show_weather: 1,
      auto_hide_ui: 0,
    };
  }
  getCardSize() { return 7; }

  _t(key, ...args) {
    const lang = (this._hass && this._hass.language) ? this._hass.language.split("-")[0] : "en";
    const dict = (I18N && I18N[lang]) || I18N.en;
    const v = dict[key] != null ? dict[key] : I18N.en[key];
    return typeof v === "function" ? v(...args) : v;
  }

  async _boot() {
    if (this._booting || this._ready) return;
    this._booting = true;
    try {
      this._buildShell();
      this._ready = true;
      this._applyHeight();
      this._showMessage(this._t("map3d_loading"));
      // Shared Card-Settings laden, BEVOR irgendwas gerendert wird -
      // sonst kommt der erste Render mit YAML-Defaults und die Shared-
      // Werte werden erst beim nächsten Bus-Event übernommen. Subscribe
      // läuft so lange, wie die Card im DOM hängt.
      try { await ensureCardSettingsLoaded(this._hass); } catch (_) {}
      this._cardSettingsHandler = () => {
        try { this._applyHeight(); } catch (_) {}
        try { this._renderRoot(); } catch (_) {}
      };
      _cardSettingsBus.addEventListener("changed", this._cardSettingsHandler);
      try {
        const res = await this._hass.callWS({ type: "bosch_ebike/list_instances" });
        this._instances = res.instances || [];
      } catch (e) { /* ignore */ }
      const res = await this._hass.callWS({ type: "bosch_ebike/list_activities" });
      this._allActivities = (res.activities || []).sort(
        (a, b) => new Date(b.startTime) - new Date(a.startTime)
      );
      this._applyFilter();
      // External callers (z. B. die 2D-Card via Chase-Cam-Button) können
      // openActivity() schon vor dem Boot rufen. Die Aktivität wird
      // gepuffert und sobald die Liste steht hier eingespielt - skipt
      // das List-View komplett.
      if (this._pendingOpenActivity) {
        const a = this._pendingOpenActivity;
        this._pendingOpenActivity = null;
        this._openTour(a);
      } else {
        this._renderRoot();
      }
    } catch (err) {
      console.error("[Bosch eBike 3D] boot error", err);
      this._showMessage(this._t("msg_error_prefix") + (err?.message || err));
    } finally {
      this._booting = false;
    }
  }

  // Public entry: vom 2D-Card-Toolbar-Button gerufen. Öffnet direkt die
  // Detail-Wiedergabe einer Tour, ohne die List-View dazwischen. Wenn
  // die Card noch nicht gebootet ist, wird die Aktivität in
  // _pendingOpenActivity zwischengespeichert und am Ende von _boot()
  // automatisch aufgerufen. Erwartet { id, accountId } analog zu den
  // List-View-Activity-Objekten.
  openActivity(activity) {
    if (!activity || !activity.id) return;
    if (this._ready) {
      this._openTour(activity);
    } else {
      this._pendingOpenActivity = activity;
    }
  }

  _applyFilter() {
    let list = [...this._allActivities];
    if (this._filterAccount !== "all") list = list.filter((a) => a.accountId === this._filterAccount);
    if (this._filterBike !== "all") list = list.filter((a) => a.bikeId === this._filterBike);
    this._activities = list;
  }

  _buildShell() {
    this.innerHTML = "";
    const card = document.createElement("ha-card");
    this.appendChild(card);

    const style = document.createElement("style");
    style.textContent = `
      .map3d-root { position: relative; padding: 0; overflow: hidden; }
      .map3d-head {
        display: flex; align-items: center; gap: 8px; padding: 12px 16px;
        background: var(--primary-color, #03a9f4); color: #fff;
        font-size: 16px; font-weight: 500;
      }
      .map3d-head .title { flex: 1; }
      .map3d-back-btn {
        background: rgba(255,255,255,.15); border: 0; color: #fff;
        padding: 4px 10px; border-radius: 6px; cursor: pointer;
        font-size: 13px; display: inline-flex; align-items: center; gap: 4px;
      }
      .map3d-back-btn:hover { background: rgba(255,255,255,.25); }
      .map3d-list {
        max-height: var(--m3d-h, 540px); overflow-y: auto;
        background: var(--card-background-color);
      }
      .map3d-tour {
        display: flex; align-items: center; gap: 12px;
        padding: 10px 16px; cursor: pointer;
        border-bottom: 1px solid var(--divider-color, #e3e3e5);
        transition: background-color .12s ease;
      }
      .map3d-tour:hover { background: var(--secondary-background-color); }
      .map3d-tour .date { flex: 0 0 110px; font-size: 13px; color: var(--secondary-text-color); }
      .map3d-tour .meta { flex: 1; font-size: 14px; color: var(--primary-text-color); }
      .map3d-tour .right { font-size: 13px; color: var(--secondary-text-color); }
      .map3d-tour .right b { color: var(--primary-text-color); font-weight: 600; }
      .map3d-tour ha-icon { color: var(--primary-color); --mdc-icon-size: 20px; }
      .map3d-msg { padding: 24px; text-align: center; color: var(--secondary-text-color); }
      .map3d-detail { position: relative; }
      .map3d-canvas { width: 100%; height: var(--m3d-h, 540px); position: relative; }
      /* Kiosk / auto-hide-UI (auto_hide_ui option): fades the informational
         chips, mode switch, north-up button and playback controls after a
         few seconds without interaction, for wall-mounted displays watching
         a passive playback - inspired by comparing against Helios's kiosk
         mode. Only applied when .map3d-ui-idle is toggled on .map3d-detail
         by _setupIdleFade(); the canvas itself never fades.
         Deliberately NOT fading .map3d-overlay as a whole (and so NOT
         .map3d-close-btn/.map3d-fs-btn, its other children): a parent's
         opacity:0 collapses its entire rendered subtree as one compositing
         group, so a child's own opacity/pointer-events cannot "win" it back
         - the close/fullscreen buttons are the only way out of (pseudo-)
         fullscreen on a touch-only kiosk tablet with no ESC key, and must
         stay visible and reachable at all times, idle or not. */
      .map3d-chip, .map3d-mode-switch, .map3d-terrain-progress, .map3d-nu-btn, .map3d-controls {
        transition: opacity .4s ease;
      }
      .map3d-detail.map3d-ui-idle .map3d-chip,
      .map3d-detail.map3d-ui-idle .map3d-mode-switch,
      .map3d-detail.map3d-ui-idle .map3d-terrain-progress,
      .map3d-detail.map3d-ui-idle .map3d-nu-btn,
      .map3d-detail.map3d-ui-idle .map3d-controls {
        opacity: 0;
        pointer-events: none;
      }
      .map3d-overlay {
        position: absolute; top: 8px; left: 8px; right: 8px;
        display: flex; flex-wrap: wrap; gap: 6px; pointer-events: none;
        z-index: 1100;
      }
      /* Shared weather-overlay CSS (WX_OVERLAY_CSS, declared above
         BoschEBikeMapCard) - same light-DOM-per-instance constant used by
         the 2D Map Card, since a <style> tag never crosses a shadow/light
         DOM boundary between separate card instances (see
         _ensureChaseCamStyles() for the same problem solved differently). */
      ${WX_OVERLAY_CSS}
      .map3d-chip {
        background: rgba(20,24,32,.78); color: #fff; backdrop-filter: blur(6px);
        padding: 4px 10px; border-radius: 999px; font-size: 12px;
        display: inline-flex; align-items: center; gap: 5px;
        pointer-events: auto;
      }
      .map3d-chip ha-icon { --mdc-icon-size: 14px; }
      /* Stable widths for the playback stat chips. Even with a fixed
         decimal place, '9,5 km/h' and '11,5 km/h' have different
         character counts and would otherwise push neighbouring chips
         sideways every frame. tabular-nums aligns digit widths,
         min-width pins the chip so it cannot shrink/grow with the
         value. Min-width values are picked empirically to fit the
         widest realistic content (e.g. '99,9 km/h'). */
      #m3d-speed-chip, #m3d-stat-speed-wrap {
        min-width: 92px;
        font-variant-numeric: tabular-nums;
      }
      #m3d-dist-chip, #m3d-stat-dist-wrap {
        min-width: 84px;
        font-variant-numeric: tabular-nums;
      }
      #m3d-ele-chip, #m3d-stat-ele-wrap {
        min-width: 72px;
        font-variant-numeric: tabular-nums;
      }
      #m3d-stat-speed, #m3d-stat-dist, #m3d-stat-ele {
        font-variant-numeric: tabular-nums;
      }
      .map3d-controls {
        position: absolute; left: 8px; right: 8px; bottom: 8px;
        background: rgba(20,24,32,.78); color: #fff; backdrop-filter: blur(8px);
        border-radius: 12px; padding: 10px 12px;
        display: flex; flex-direction: column; gap: 8px;
        z-index: 1100;
      }
      .map3d-controls .row1 {
        display: flex; align-items: center; gap: 10px;
      }
      .map3d-play-btn {
        background: var(--primary-color, #03a9f4); color: #fff; border: 0;
        width: 36px; height: 36px; border-radius: 50%;
        display: inline-flex; align-items: center; justify-content: center;
        cursor: pointer;
      }
      .map3d-play-btn ha-icon { --mdc-icon-size: 22px; }
      .map3d-rec-btn {
        background: rgba(255,255,255,.18); color: #fff; border: 0;
        width: 32px; height: 32px; border-radius: 50%;
        display: inline-flex; align-items: center; justify-content: center;
        cursor: pointer; flex: 0 0 32px;
      }
      .map3d-rec-btn:hover { background: rgba(255,255,255,.32); }
      .map3d-rec-btn.active { background: #e53935; color: #fff; }
      .map3d-rec-btn:disabled { opacity: .35; cursor: not-allowed; }
      .map3d-rec-btn ha-icon { --mdc-icon-size: 20px; }
      .map3d-rec-badge { background: rgba(229,57,53,.85); color: #fff; }
      .map3d-rec-badge ha-icon { color: #fff; animation: ebike-rec-blink 1s ease-in-out infinite; }
      .map3d-download-chip {
        background: #2e7d32; color: #fff; text-decoration: none;
        cursor: pointer; box-shadow: 0 2px 8px rgba(0,0,0,.4);
      }
      .map3d-download-chip:hover { filter: brightness(1.1); }
      .map3d-download-chip ha-icon { color: #fff; }
      .map3d-mode-switch {
        display: inline-flex; align-items: center; gap: 0;
        background: rgba(20,24,32,.78); backdrop-filter: blur(6px);
        border: 1px solid rgba(255,255,255,.18); border-radius: 999px;
        padding: 2px; pointer-events: auto;
      }
      .map3d-mode-pill {
        background: transparent; color: #fff; border: 0;
        padding: 3px 11px; border-radius: 999px; font-size: 12px;
        font-weight: 600; cursor: pointer; user-select: none;
        display: inline-flex; align-items: center; gap: 4px;
        transition: background-color .12s ease;
      }
      .map3d-mode-pill:hover:not(.active):not(:disabled) {
        background: rgba(255,255,255,.10);
      }
      .map3d-mode-pill.active {
        background: #1f6feb;
        box-shadow: 0 1px 6px rgba(31,111,235,.45);
      }
      .map3d-mode-pill:disabled { opacity: .45; cursor: progress; }
      .map3d-mode-pill ha-icon { --mdc-icon-size: 13px; }
      .map3d-terrain-progress {
        background: rgba(20,24,32,.78); color: #fff; backdrop-filter: blur(6px);
        padding: 4px 10px; border-radius: 999px; font-size: 12px;
        font-variant-numeric: tabular-nums; pointer-events: auto;
      }
      .map3d-fs-btn {
        background: rgba(20,24,32,.78); color: #fff;
        backdrop-filter: blur(6px); border: 1px solid rgba(255,255,255,.18);
        width: 26px; height: 26px; border-radius: 50%;
        display: inline-flex; align-items: center; justify-content: center;
        cursor: pointer; pointer-events: auto;
      }
      .map3d-fs-btn:hover { background: rgba(20,24,32,.92); }
      .map3d-fs-btn ha-icon { --mdc-icon-size: 16px; }
      /* Compass toggle: same chip shape as the fullscreen button.
         Highlighted blue while north-up mode is active. */
      .map3d-nu-btn {
        background: rgba(20,24,32,.78); color: #fff;
        backdrop-filter: blur(6px); border: 1px solid rgba(255,255,255,.18);
        width: 26px; height: 26px; border-radius: 50%;
        display: inline-flex; align-items: center; justify-content: center;
        cursor: pointer; pointer-events: auto;
      }
      .map3d-nu-btn:hover { background: rgba(20,24,32,.92); }
      .map3d-nu-btn.active {
        background: #1f6feb; border-color: #1f6feb;
        box-shadow: 0 1px 6px rgba(31,111,235,.45);
      }
      .map3d-nu-btn ha-icon { --mdc-icon-size: 16px; }
      /* Weather-toggle chip: additional on-card control for the same
         show_weather shared setting the editor's number field already
         exposes (not a replacement for it). Sibling of the daylight
         chip; base pill shape/padding/border-radius come from the
         .map3d-chip rule above. Rendered as a real <button> (for
         correct native keyboard activation semantics, matching the
         other overlay controls) rather than a span, so border:0 resets
         the browser's default button border - the base .map3d-chip
         rule doesn't set one - mirroring the same reset .map3d-back-btn
         already needs for the same reason. cursor:pointer is kept
         explicit for clarity even though buttons default to it.
         Active-state accent mirrors .map3d-nu-btn.active's exact
         colors, adapted to the pill shape (no border, since the base
         chip has none). Scoped to this one chip's class rather than a
         bare .map3d-chip.active so no other chip accidentally inherits
         this look if it ever gains an "active" class of its own. */
      .map3d-wx-toggle-chip { cursor: pointer; border: 0; }
      .map3d-wx-toggle-chip.active {
        background: #1f6feb;
        box-shadow: 0 1px 6px rgba(31,111,235,.45);
      }
      /* Close button: bigger hit area so it works well on tablets,
         which have no ESC key to exit fullscreen / chase-cam mode.
         Slight red tint so it stands out from the neutral chip row. */
      .map3d-close-btn {
        background: rgba(180,32,40,.82); color: #fff;
        backdrop-filter: blur(6px); border: 1px solid rgba(255,255,255,.22);
        width: 34px; height: 34px; border-radius: 50%;
        display: inline-flex; align-items: center; justify-content: center;
        cursor: pointer; pointer-events: auto;
      }
      .map3d-close-btn:hover { background: rgba(200,40,48,.95); }
      .map3d-close-btn ha-icon { --mdc-icon-size: 20px; }
      /* Browser fullscreen: turn the whole chain
         host -> ha-card -> map3d-root -> map3d-detail -> canvas
         into a column flex stack so the height cascades and the
         WebGL canvas gets a real viewport size.

         IMPORTANT: each pseudo-class lives in its OWN rule. CSS
         drops an entire selector list if ANY selector in it is
         invalid for the browser, and :-webkit-full-screen is
         invalid in Firefox (and vice versa for :-moz-full-screen
         in Chromium). Combining them was breaking the layout on
         Firefox completely - the rule was discarded and the
         canvas kept its 540px height while the rest of the
         viewport stayed black. */
      bosch-ebike-3d-map-card:fullscreen {
        display: flex; flex-direction: column;
        width: 100%; height: 100%;
        background: var(--card-background-color, #000);
      }
      bosch-ebike-3d-map-card:-webkit-full-screen {
        display: flex; flex-direction: column;
        width: 100%; height: 100%;
        background: var(--card-background-color, #000);
      }
      bosch-ebike-3d-map-card:fullscreen ha-card {
        flex: 1; min-height: 0; height: auto; max-height: none;
        border-radius: 0; display: flex; flex-direction: column;
      }
      bosch-ebike-3d-map-card:-webkit-full-screen ha-card {
        flex: 1; min-height: 0; height: auto; max-height: none;
        border-radius: 0; display: flex; flex-direction: column;
      }
      bosch-ebike-3d-map-card:fullscreen .map3d-root {
        flex: 1; min-height: 0; display: flex; flex-direction: column;
      }
      bosch-ebike-3d-map-card:-webkit-full-screen .map3d-root {
        flex: 1; min-height: 0; display: flex; flex-direction: column;
      }
      bosch-ebike-3d-map-card:fullscreen .map3d-detail {
        flex: 1; min-height: 0;
      }
      bosch-ebike-3d-map-card:-webkit-full-screen .map3d-detail {
        flex: 1; min-height: 0;
      }
      bosch-ebike-3d-map-card:fullscreen .map3d-canvas {
        height: 100% !important; max-height: none !important;
      }
      bosch-ebike-3d-map-card:-webkit-full-screen .map3d-canvas {
        height: 100% !important; max-height: none !important;
      }
      /* CSS-pseudo-fullscreen fallback for iOS Safari + the HA mobile
         app's WKWebView, where requestFullscreen() either rejects or
         is missing entirely. Same flex chain as the native rules, just
         pinned to the viewport via position:fixed. */
      bosch-ebike-3d-map-card.map3d-pseudo-fs {
        position: fixed !important; inset: 0 !important;
        z-index: 9999 !important;
        width: 100vw !important; height: 100vh !important;
        max-width: 100vw !important; max-height: 100vh !important;
        display: flex !important; flex-direction: column !important;
        background: var(--card-background-color, #000);
      }
      bosch-ebike-3d-map-card.map3d-pseudo-fs ha-card {
        flex: 1; min-height: 0; height: auto; max-height: none;
        border-radius: 0;
        display: flex; flex-direction: column;
      }
      bosch-ebike-3d-map-card.map3d-pseudo-fs .map3d-root {
        flex: 1; min-height: 0;
        display: flex; flex-direction: column;
      }
      bosch-ebike-3d-map-card.map3d-pseudo-fs .map3d-detail {
        flex: 1; min-height: 0;
      }
      bosch-ebike-3d-map-card.map3d-pseudo-fs .map3d-canvas {
        height: 100% !important; max-height: none !important;
      }
      @keyframes ebike-rec-blink {
        0%, 49% { opacity: 1; }
        50%, 100% { opacity: 0.25; }
      }
      .map3d-time { font-variant-numeric: tabular-nums; font-size: 13px; }
      .map3d-slider { flex: 1; }
      .map3d-stats {
        display: flex; gap: 14px; font-size: 12px; opacity: .85;
      }
      .map3d-stats .v { font-weight: 600; }
      .maplibregl-canvas:focus { outline: none; }
      .ebike-3d-marker {
        /* MapLibre's stylesheet sets position:absolute + top:0 + left:0
           on .maplibregl-marker, but that stylesheet lives in document
           <head> and does NOT penetrate HA's shadow DOM boundary. With
           the shadow tree, markers default to position:static and the
           transform translate(x, y) is applied relative to DOM flow
           instead of the map container origin - so all markers stack
           at the bottom of the flow, invisible. Explicitly setting
           absolute + top:0 + left:0 here works inside any shadow tree. */
        position: absolute; top: 0; left: 0;
        width: 18px; height: 18px; border-radius: 50%;
        background: #42c76a; border: 5px solid #fff;
        box-shadow:
          0 0 0 6px rgba(66,199,106,0.35),
          0 4px 18px rgba(0,0,0,.65);
        z-index: 100;
      }
      .ebike-3d-marker::before {
        content: ""; position: absolute;
        inset: -8px; border-radius: 50%;
        border: 5px solid #42c76a; opacity: 0.7;
        animation: ebike-3d-pulse 1.6s ease-out infinite;
        z-index: 99;
      }
      @keyframes ebike-3d-pulse {
        0%   { transform: scale(0.55); opacity: 0.9; }
        100% { transform: scale(2.0); opacity: 0; }
      }
      /* Force the MapLibre marker wrappers above any 3D building or
         shadow visuals. Two selector forms because :has() is not
         everywhere. */
      .maplibregl-marker { z-index: 100 !important; }
      .maplibregl-marker:has(.ebike-3d-marker) { z-index: 101 !important; }
    `;
    card.appendChild(style);

    this._root = document.createElement("div");
    this._root.className = "map3d-root";
    card.appendChild(this._root);
  }

  _applyHeight() {
    const h = Number.isFinite(Number(this._config.height)) ? Number(this._config.height) : 540;
    this._root.style.setProperty("--m3d-h", h + "px");
  }

  _showMessage(text) {
    if (!this._root) return;
    this._root.innerHTML = `
      <div class="map3d-head"><div class="title">${this._config.title || this._t("map3d_title")}</div></div>
      <div class="map3d-msg">${text}</div>
    `;
  }

  _renderRoot() {
    if (!this._root) return;
    if (this._mode === "detail" && this._currentActivity) {
      this._renderDetail();
    } else {
      this._renderList();
    }
  }

  _renderList() {
    this._destroyMap();
    if (!this._activities.length) {
      this._showMessage(this._t("map3d_no_rides"));
      return;
    }
    const lang = (this._hass && this._hass.locale && this._hass.locale.language)
      || (this._hass && this._hass.language) || navigator.language || "en-GB";
    const fmtDate = (iso) => {
      try { return new Date(iso).toLocaleDateString(lang, { day: "2-digit", month: "short", year: "numeric" }); }
      catch { return iso; }
    };
    const fmtKm = (m) => (m != null && Number.isFinite(m)) ? (m / 1000).toFixed(1) + " km" : "–";
    const fmtDur = (s) => {
      if (!Number.isFinite(s) || s <= 0) return "–";
      const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60);
      return h > 0 ? `${h}h ${m}min` : `${m} min`;
    };
    const rows = this._activities.slice(0, 50).map((a, i) => {
      const km = fmtKm(a.distance);
      const dur = fmtDur(this._tourDurationSec(a));
      const title = a.title || this._t("msg_unnamed_ride");
      return `
        <div class="map3d-tour" data-idx="${i}">
          <div class="date">${fmtDate(a.startTime)}</div>
          <div class="meta">${this._escapeHtml(title)}</div>
          <div class="right"><b>${km}</b> · ${dur}</div>
          <ha-icon icon="mdi:chevron-right"></ha-icon>
        </div>
      `;
    }).join("");
    this._root.innerHTML = `
      <div class="map3d-head"><div class="title">${this._config.title || this._t("map3d_title")}</div></div>
      <div class="map3d-list">${rows}</div>
    `;
    this._root.querySelectorAll(".map3d-tour").forEach((el) => {
      el.addEventListener("click", () => {
        const idx = Number(el.getAttribute("data-idx"));
        const act = this._activities[idx];
        if (act) this._openTour(act);
      });
    });
  }

  _escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }

  async _openTour(activity) {
    this._mode = "detail";
    this._currentActivity = activity;
    this._currentTrack = null;
    // Reset per-tour weather so a ride opened with show_weather off (or
    // whose fetch fails) never keeps rendering the PREVIOUS tour's overlay.
    // Re-populated below, only when the flag is on, once the new track has
    // loaded and a start point is available.
    this._weatherSeries = null;
    this._shadowDiagLogged = false;
    this._showMessage(this._t("map3d_loading_track"));
    try {
      const params = { type: "bosch_ebike/get_track", activity_id: activity.id };
      if (activity.accountId) params.config_entry_id = activity.accountId;
      const res = await this._hass.callWS(params);
      const pts = Array.isArray(res.track)
        ? res.track.filter((p) => Number.isFinite(p.lat) && Number.isFinite(p.lon))
        : [];
      if (!pts.length) {
        this._showMessage(this._t("map3d_no_gps"));
        return;
      }
      // Keep the raw GPS samples for the visible polyline so the track
      // on the map matches what was actually recorded. The chase cam,
      // marker, bearings and distance counter use a smoothed copy to
      // damp GPS jitter and avoid motion sickness during playback.
      this._rawTrack = pts;
      const wRaw = readCardSetting(this._config, "track_smooth_window", undefined);
      const w = Number.isFinite(Number(wRaw)) && wRaw !== "" && wRaw !== null
        ? Math.max(0, Math.min(15, Number(wRaw))) : 3;
      this._currentTrack = this._smoothTrackPositions(pts, w);
      this._buildCumulativeDistances();
      this._precomputeBearings();
      // Fire-and-forget: the full-ride weather series is only needed by
      // _applyIndex() on each scrub tick, so it must not delay the track
      // render above. this._weatherSeries stays null (already reset)
      // until/unless the fetch resolves for THIS still-open tour.
      if (this._showFlag("show_weather")) {
        this._loadTourWeather(activity);
      }
      this._renderDetail();
    } catch (err) {
      console.error("[Bosch eBike 3D] track load failed", err);
      this._showMessage(this._t("msg_error_prefix") + (err?.message || err));
    }
  }

  // Fetches the full-ride hourly weather series (ride start → ride end) once
  // for the whole open tour, so _applyIndex() can interpolate a per-scrub
  // sample on every tick without a network call per frame. Uses this
  // class's own smoothed _currentTrack (not the 2D card's _currentTrack,
  // which is the raw/unsmoothed array on that class - see _openTour) for
  // the start coordinate, since that is the same array _applyIndex() reads
  // from during playback. Mirrors _loadAndRenderWeather()'s (Task 4, 2D
  // card) fail-open convention: any failure is swallowed after a
  // console.warn, leaving this._weatherSeries unset so the overlay simply
  // never activates rather than throwing during playback.
  async _loadTourWeather(activity) {
    const startPoint = this._currentTrack && this._currentTrack[0];
    if (!startPoint || !activity?.startTime) return;
    try {
      const startISO = activity.startTime;
      const endISO = new Date(
        new Date(activity.startTime).getTime() + this._tourDurationSec(activity) * 1000
      ).toISOString();
      const series = await fetchHistoricalWeather(startPoint.lat, startPoint.lon, startISO, endISO);
      // The user may have opened a different tour while this was in
      // flight - do not let a late resolve overwrite that tour's state.
      if (this._currentActivity !== activity) return;
      // Precompute epoch-ms once here rather than letting interpolateWeatherAt()
      // re-parse the whole (up to ~192-entry) series on every _applyIndex() tick
      // during autoplay/scrubbing (~60/s).
      series.timesMs = series.time.map((s) => new Date(s).getTime());
      // The Forecast API branch of fetchHistoricalWeather() has no
      // start_date bound - it always returns a fixed [now-7days, now+1day]
      // window regardless of the ride's real start. For an unusually long
      // multi-day tour whose END falls within the last 5 days but whose
      // START predates that fixed window, the series would start LATER than
      // the ride actually did; interpolateWeatherAt() can't detect this on
      // its own since it just clamps out-of-range lookups to the first
      // sample. Rather than silently show wrong-day weather for the early
      // part of such a tour, treat too-short coverage the same as a failed
      // fetch (fail open, matching this feature's convention elsewhere):
      // leave this._weatherSeries unset so the overlay never activates for
      // this tour. ~1h tolerance for the hourly sample bucketing itself.
      const rideStartMs = new Date(activity.startTime).getTime();
      if (rideStartMs < series.timesMs[0] - 3600000) return;
      this._weatherSeries = series;
    } catch (err) {
      console.warn("[Bosch eBike 3D] weather fetch failed", err);
      // fail open - no overlay, no error surfaced to the user
    }
  }

  // Gaussian-weighted smoothing of lat/lon. Used to give the chase cam
  // and live marker a calm path that does not surface raw GPS wobble.
  // Returns a NEW array so the raw points stay available for the
  // visible polyline. Gauss instead of uniform mean: better high-freq
  // attenuation at the same window size and noticeably less corner
  // cutting, because the center sample keeps the highest weight.
  _smoothTrackPositions(pts, window) {
    if (!pts || pts.length < 3 || window <= 0) {
      return pts ? pts.slice() : [];
    }
    const W = Math.floor(window);
    const sigma = Math.max(0.5, W / 2);
    const twoSigSq = 2 * sigma * sigma;
    // Precompute kernel for offsets -W..+W. The 2W+1 weights are reused
    // for every sample; only the boundary slice changes near the ends.
    const kernel = new Array(2 * W + 1);
    for (let k = -W; k <= W; k++) {
      kernel[k + W] = Math.exp(-(k * k) / twoSigSq);
    }
    const N = pts.length;
    const out = new Array(N);
    for (let i = 0; i < N; i++) {
      const lo = Math.max(0, i - W);
      const hi = Math.min(N - 1, i + W);
      let sLat = 0, sLon = 0, wSum = 0;
      for (let j = lo; j <= hi; j++) {
        const w = kernel[j - i + W];
        sLat += pts[j].lat * w;
        sLon += pts[j].lon * w;
        wSum += w;
      }
      out[i] = {
        ...pts[i],
        lat: sLat / wSum,
        lon: sLon / wSum,
      };
    }
    return out;
  }

  // ===========================================================================
  // Map mode switch: vector | terrain | satellite
  // ---------------------------------------------------------------------------
  // Modes are mutually exclusive. The currently applied one lives in
  // this._mapMode; the persisted preference in localStorage survives
  // reloads. A small migration step also picks up the legacy
  // bosch-ebike-3d-terrain="1" flag from v1.16.0 builds.
  _loadMapModePref() {
    try {
      const v = localStorage.getItem("bosch-ebike-3d-mode");
      if (v === "vector" || v === "terrain" || v === "satellite") return v;
      // Migration: earlier builds only had a terrain on/off flag.
      if (localStorage.getItem("bosch-ebike-3d-terrain") === "1") return "terrain";
    } catch (_) { /* ignore */ }
    return "vector";
  }
  _saveMapModePref(mode) {
    try {
      localStorage.setItem("bosch-ebike-3d-mode", mode);
      // Clean up the legacy key so re-migrating cannot resurrect an
      // old preference if the user has since switched modes.
      localStorage.removeItem("bosch-ebike-3d-terrain");
    } catch (_) { /* private mode, ignore */ }
  }

  _updateModeUI() {
    const sw = this._root?.querySelector("#m3d-mode-switch");
    if (!sw) return;
    for (const btn of sw.querySelectorAll(".map3d-mode-pill")) {
      btn.classList.toggle("active", btn.dataset.mode === this._mapMode);
    }
  }

  _setTilesProgress(msg) {
    const el = this._root?.querySelector("#m3d-terrain-progress");
    if (!el) return;
    if (!msg) { el.style.display = "none"; el.textContent = ""; return; }
    el.style.display = ""; el.textContent = msg;
  }

  _setSwitchDisabled(disabled) {
    const sw = this._root?.querySelector("#m3d-mode-switch");
    if (!sw) return;
    for (const btn of sw.querySelectorAll(".map3d-mode-pill")) btn.disabled = !!disabled;
  }

  // ===========================================================================
  // Fullscreen toggle
  // ---------------------------------------------------------------------------
  // Two-track implementation: native Fullscreen API where available
  // (desktop browsers, Android Chrome) and a CSS-pseudo-fullscreen
  // fallback for environments where the native API rejects or is
  // missing entirely (iOS Safari, the iOS HA Companion app's
  // WKWebView). The fallback flips a host class that the stylesheet
  // pins to position:fixed, with the same flex-chain layout fix that
  // the native :fullscreen rules use so the canvas still fills the
  // viewport.
  _toggleFullscreen() {
    const target = this;
    const nativeOn = document.fullscreenElement === target || document.webkitFullscreenElement === target;
    const pseudoOn = !!this._pseudoFullscreen;
    if (nativeOn || pseudoOn) {
      if (pseudoOn) this._exitPseudoFullscreen();
      else (document.exitFullscreen || document.webkitExitFullscreen)?.call(document);
      return;
    }
    try {
      const req = target.requestFullscreen || target.webkitRequestFullscreen;
      if (!req) { this._enterPseudoFullscreen(); return; }
      const result = req.call(target);
      if (result && typeof result.then === "function") {
        result.catch((e) => {
          console.warn("[Bosch eBike 3D] native fullscreen rejected, using fallback", e);
          this._enterPseudoFullscreen();
        });
      }
    } catch (e) {
      console.warn("[Bosch eBike 3D] native fullscreen threw, using fallback", e);
      this._enterPseudoFullscreen();
    }
  }

  // CSS-fallback path. Pins the host with position:fixed and listens
  // for Escape so the user has a way out (the native API handles
  // Escape automatically; here we own it).
  _enterPseudoFullscreen() {
    if (this._pseudoFullscreen) return;
    this._pseudoFullscreen = true;
    this.classList.add("map3d-pseudo-fs");
    document.body.style.overflow = "hidden";
    const ico = this._root?.querySelector("#m3d-fs-ico");
    if (ico) ico.setAttribute("icon", "mdi:fullscreen-exit");
    if (!this._pseudoEscHandler) {
      this._pseudoEscHandler = (ev) => {
        if (ev.key === "Escape" && this._pseudoFullscreen) this._exitPseudoFullscreen();
      };
      document.addEventListener("keydown", this._pseudoEscHandler);
    }
    requestAnimationFrame(() => requestAnimationFrame(() => {
      try { this._map?.resize(); } catch (_) {}
    }));
  }

  _exitPseudoFullscreen() {
    if (!this._pseudoFullscreen) return;
    this._pseudoFullscreen = false;
    this.classList.remove("map3d-pseudo-fs");
    document.body.style.overflow = "";
    const ico = this._root?.querySelector("#m3d-fs-ico");
    if (ico) ico.setAttribute("icon", "mdi:fullscreen");
    if (this._pseudoEscHandler) {
      document.removeEventListener("keydown", this._pseudoEscHandler);
      this._pseudoEscHandler = null;
    }
    requestAnimationFrame(() => requestAnimationFrame(() => {
      try { this._map?.resize(); } catch (_) {}
    }));
  }

  // Document-level fullscreen state change for the native API path.
  // Updates the icon and forces a MapLibre resize at the new size.
  _ensureFullscreenListener() {
    if (this._fsChangeHandler) return;
    this._fsChangeHandler = () => {
      const fsEl = document.fullscreenElement || document.webkitFullscreenElement;
      const on = fsEl === this;
      this._isFullscreen = on;
      const ico = this._root?.querySelector("#m3d-fs-ico");
      if (ico) ico.setAttribute("icon", on ? "mdi:fullscreen-exit" : "mdi:fullscreen");
      requestAnimationFrame(() => requestAnimationFrame(() => {
        try { this._map?.resize(); } catch (_) {}
      }));
    };
    document.addEventListener("fullscreenchange", this._fsChangeHandler);
    document.addEventListener("webkitfullscreenchange", this._fsChangeHandler);
  }

  // ===========================================================================
  // North-up toggle (compass button on the map)
  // ---------------------------------------------------------------------------
  // The editor option `north_up` provides the initial default per card
  // config. A runtime click on the compass button overrides that
  // default and persists in localStorage so the choice survives
  // reloads. Cleared by switching back to the same state as the
  // config option (so the editor change can still take effect).
  _loadNorthUpPref() {
    try {
      const v = localStorage.getItem("bosch-ebike-3d-north-up");
      if (v === "1") return true;
      if (v === "0") return false;
    } catch (_) { /* ignore */ }
    return null;   // sentinel: use config default
  }
  _saveNorthUpPref(on) {
    try { localStorage.setItem("bosch-ebike-3d-north-up", on ? "1" : "0"); }
    catch (_) { /* private mode */ }
  }

  // Chase-cam pitch/zoom: config (default_pitch/chase_zoom) sets the
  // starting value, same as north-up above. A live manual adjustment via
  // the map's own drag/scroll/pitch controls (detected through
  // pitchend/zoomend's originalEvent - absent on our own programmatic
  // jumpTo/easeTo calls, see _initMap) overrides it and persists across
  // reloads, so a user's preferred viewing angle sticks instead of
  // resetting to the YAML default every time (inspired by comparing
  // against Helios's persisted camera pose).
  _loadChasePitchPref() {
    try {
      // getItem returns null when unset - Number(null) is 0, NOT NaN, so
      // the raw string must be checked for absence before conversion.
      // Getting this wrong would force every fresh install's pitch to 0
      // (straight down) instead of falling through to the config default.
      const raw = localStorage.getItem("bosch-ebike-3d-chase-pitch");
      if (raw == null) return null;
      const v = Number(raw);
      if (Number.isFinite(v)) return v;
    } catch (_) { /* ignore */ }
    return null;   // sentinel: use config default
  }
  _saveChasePitchPref(pitch) {
    try { localStorage.setItem("bosch-ebike-3d-chase-pitch", String(pitch)); }
    catch (_) { /* private mode */ }
  }
  _loadChaseZoomPref() {
    try {
      // Same null-vs-0 pitfall as _loadChasePitchPref above.
      const raw = localStorage.getItem("bosch-ebike-3d-chase-zoom");
      if (raw == null) return null;
      const v = Number(raw);
      if (Number.isFinite(v)) return v;
    } catch (_) { /* ignore */ }
    return null;   // sentinel: use config default
  }
  _saveChaseZoomPref(zoom) {
    try { localStorage.setItem("bosch-ebike-3d-chase-zoom", String(zoom)); }
    catch (_) { /* private mode */ }
  }

  // Kiosk / auto-hide-UI: fades the overlay chips and playback controls
  // after IDLE_MS without interaction, brings them back on the next touch
  // or pointer movement within the detail view. Off by default (auto_hide_ui
  // config option), for wall-mounted/kiosk dashboards showing a passive
  // playback. Must be torn down before every re-render and on disconnect -
  // see the call sites in _renderDetail/exitDetail/disconnectedCallback -
  // otherwise repeated renders would stack duplicate listeners.
  _teardownIdleFade() {
    if (this._idleTimer) { clearTimeout(this._idleTimer); this._idleTimer = null; }
    if (this._idleFadeTarget && this._idleFadeHandler) {
      for (const ev of ["pointerdown", "pointermove", "touchstart", "keydown"]) {
        this._idleFadeTarget.removeEventListener(ev, this._idleFadeHandler);
      }
    }
    if (this._idleFadeTarget) this._idleFadeTarget.classList.remove("map3d-ui-idle");
    this._idleFadeTarget = null;
    this._idleFadeHandler = null;
  }
  _setupIdleFade(detailEl) {
    if (!detailEl || !this._optionOn("auto_hide_ui", false)) return;
    const IDLE_MS = 5000;
    const wake = () => {
      detailEl.classList.remove("map3d-ui-idle");
      if (this._idleTimer) clearTimeout(this._idleTimer);
      this._idleTimer = setTimeout(() => detailEl.classList.add("map3d-ui-idle"), IDLE_MS);
    };
    this._idleFadeTarget = detailEl;
    this._idleFadeHandler = wake;
    for (const ev of ["pointerdown", "pointermove", "touchstart", "keydown"]) {
      detailEl.addEventListener(ev, wake);
    }
    wake();
  }
  _currentNorthUp() {
    const pref = this._loadNorthUpPref();
    if (pref !== null) return pref;
    return this._optionOn("north_up", false);
  }

  _updateNorthUpButton() {
    const btn = this._root?.querySelector("#m3d-nu-btn");
    if (!btn) return;
    btn.classList.toggle("active", this._currentNorthUp());
  }

  _toggleNorthUp() {
    const next = !this._currentNorthUp();
    this._saveNorthUpPref(next);
    this._updateNorthUpButton();
    // Re-apply the current frame so the camera rotation and marker
    // arrow update immediately, without waiting for the next anim
    // tick. _currentFracIndex is the precise position the playback
    // is on right now.
    if (this._currentFracIndex != null) {
      try { this._applyIndex(this._currentFracIndex, true); } catch (_) {}
    }
  }

  // Compute the geographic bounding box of the loaded track, padded by
  // ~0.5 km so terrain extends slightly beyond the track edges and the
  // chase-cam never looks at a flat strip when panning sideways.
  _bboxOfTrack(pts) {
    let w = Infinity, e = -Infinity, s = Infinity, n = -Infinity;
    for (const p of pts) {
      if (p.lon < w) w = p.lon;
      if (p.lon > e) e = p.lon;
      if (p.lat < s) s = p.lat;
      if (p.lat > n) n = p.lat;
    }
    const padLat = 0.005;   // ~550 m
    const padLon = 0.005 / Math.max(0.1, Math.cos((s + n) / 2 * Math.PI / 180));
    return {
      west: w - padLon, east: e + padLon,
      south: s - padLat, north: n + padLat,
    };
  }

  // Tile set for the DEM preloader. Three zooms (10/11/12) cover every
  // realistic chase-cam state for a typical day tour - ~30-90 tiles.
  _collectTerrainTiles(bbox) {
    const out = [];
    for (const z of [10, 11, 12]) {
      out.push(..._tilesForBBox(bbox.west, bbox.south, bbox.east, bbox.north, z));
    }
    return out;
  }

  // Tile set for the satellite preloader. Goes 12..maxZ to keep total
  // size sane: z=12 alone ~14 MB, z=12+13 ~40 MB, z=12..14 ~110 MB
  // for a typical day tour. The 'satellite_max_zoom' config caps the
  // top end.
  _collectSatelliteTiles(bbox, maxZ) {
    const out = [];
    for (let z = 12; z <= maxZ; z++) {
      out.push(..._tilesForBBox(bbox.west, bbox.south, bbox.east, bbox.north, z));
    }
    return out;
  }

  // Generic parallel preloader. Same logic for DEM and satellite, only
  // the URL template differs. Concurrency 8 saturates home connections
  // without making AWS S3 / Esri throttle. Failures are silently
  // skipped - one missing tile means one flat patch, not a broken map,
  // and the runtime fetcher will retry on demand.
  async _preloadRasterTiles(tiles, urlTemplate, onProgress) {
    const total = tiles.length;
    let done = 0;
    const concurrency = 8;
    const queue = tiles.slice();
    const worker = async () => {
      while (queue.length) {
        const t = queue.shift();
        const url = urlTemplate
          .replace("{z}", t.z).replace("{x}", t.x).replace("{y}", t.y);
        try {
          const cached = await _tileCacheGet(url);
          if (!cached) {
            const resp = await fetch(url, { mode: "cors" });
            if (resp.ok) await _tileCachePut(url, await resp.blob());
          }
        } catch (_) { /* skip, runtime will retry */ }
        done++;
        try { onProgress?.(done, total); } catch (_) {}
      }
    };
    await Promise.all(Array.from({ length: concurrency }, worker));
  }

  _satelliteTemplate() {
    const cfg = String(readCardSetting(this._config, "satellite_tile_url", "") || "").trim();
    return cfg || DEFAULT_SATELLITE_TEMPLATE;
  }

  _satelliteMaxZoom() {
    const raw = Number(readCardSetting(this._config, "satellite_max_zoom", undefined));
    if (!Number.isFinite(raw)) return 14;
    return Math.max(12, Math.min(15, Math.floor(raw)));
  }

  // ===========================================================================
  // Mode switch core
  // ---------------------------------------------------------------------------
  // Transition from this._mapMode to the requested mode. All three
  // mode-changes are funneled through one entry point so the tear-down
  // of the previous mode (removing sources / layers, restoring base
  // visibility) is always paired with the build-up of the new one.
  async _setMapMode(mode, opts = {}) {
    const map = this._map;
    if (!map) return;
    if (mode !== "vector" && mode !== "terrain" && mode !== "satellite") return;
    if (mode === this._mapMode) return;
    this._setSwitchDisabled(true);
    try {
      // 1) Tear down the currently active non-vector mode.
      if (this._mapMode === "terrain") this._teardownTerrain();
      else if (this._mapMode === "satellite") this._teardownSatellite();

      // 2) Apply the new mode (vector is the bare baseline).
      if (mode === "terrain") {
        await this._buildTerrain(map);
        if (this._map !== map) return;   // user navigated away mid-load
      } else if (mode === "satellite") {
        await this._buildSatellite(map);
        if (this._map !== map) return;
      }
      this._mapMode = mode;
      if (!opts.silent) this._saveMapModePref(mode);
    } catch (e) {
      console.warn("[Bosch eBike 3D] mode switch failed", e);
      const kind = this._t(mode === "satellite" ? "map3d_kind_satellite" : "map3d_kind_terrain");
      this._setTilesProgress(this._t("map3d_tiles_failed", kind));
      setTimeout(() => this._setTilesProgress(null), 3000);
    } finally {
      this._setSwitchDisabled(false);
      this._setTilesProgress(null);
      this._updateModeUI();
    }
  }

  // --- Terrain build / teardown -----------------------------------------------
  async _buildTerrain(map) {
    const pts = this._currentTrack;
    if (!pts || !pts.length) return;
    const bbox = this._bboxOfTrack(pts);
    const tiles = this._collectTerrainTiles(bbox);
    const kind = this._t("map3d_kind_terrain");
    this._setTilesProgress(this._t("map3d_tiles_loading", kind, 0, tiles.length));
    await this._preloadRasterTiles(tiles, TERRARIUM_TILE_TEMPLATE, (d, t) => {
      this._setTilesProgress(this._t("map3d_tiles_loading", kind, d, t));
    });
    if (this._map !== map) return;

    if (!map.getSource("ebike-dem")) {
      // maxzoom: 12 caps the DEM tile pyramid so MapLibre never
      // overzooms higher levels - the mesh is coarser but with
      // exaggeration 1.5 the visible relief looks essentially the
      // same and playback stays smooth.
      map.addSource("ebike-dem", {
        type: "raster-dem",
        tiles: [EBIKE_DEM_PROTOCOL + "://" + TERRARIUM_TILE_TEMPLATE.replace(/^https?:\/\//, "")],
        encoding: "terrarium",
        tileSize: 256, minzoom: 0, maxzoom: 12,
      });
    }
    const exag = Math.max(1.0, Math.min(3.0, Number(readCardSetting(this._config, "terrain_exaggeration", undefined)) || 1.5));
    map.setTerrain({ source: "ebike-dem", exaggeration: exag });
    this._hideBuildingsAndShadows();
  }

  _teardownTerrain() {
    const map = this._map;
    if (!map) return;
    try { map.setTerrain(null); } catch (_) {}
    try { if (map.getSource("ebike-dem")) map.removeSource("ebike-dem"); } catch (_) {}
    this._restoreBuildingsAndShadows();
  }

  // --- Satellite build / teardown ---------------------------------------------
  async _buildSatellite(map) {
    const pts = this._currentTrack;
    if (!pts || !pts.length) return;
    const bbox = this._bboxOfTrack(pts);
    const maxZ = this._satelliteMaxZoom();
    const template = this._satelliteTemplate();
    const tiles = this._collectSatelliteTiles(bbox, maxZ);
    const kind = this._t("map3d_kind_satellite");
    this._setTilesProgress(this._t("map3d_tiles_loading", kind, 0, tiles.length));
    await this._preloadRasterTiles(tiles, template, (d, t) => {
      this._setTilesProgress(this._t("map3d_tiles_loading", kind, d, t));
    });
    if (this._map !== map) return;

    if (!map.getSource("ebike-sat")) {
      // Tile URL for MapLibre goes through the ebike-sat:// protocol
      // so the runtime fetcher hits IDB on every request. minzoom 0
      // keeps coarse overview tiles available even at far-out zoom.
      const tileUrl = EBIKE_SAT_PROTOCOL + "://" + template.replace(/^https?:\/\//, "");
      map.addSource("ebike-sat", {
        type: "raster",
        tiles: [tileUrl],
        tileSize: 256, minzoom: 0, maxzoom: maxZ,
      });
    }
    if (!map.getLayer("ebike-sat-layer")) {
      // Insert satellite ABOVE every existing fill / fill-extrusion /
      // background layer of the OpenFreeMap style so the imagery
      // shows through, but BELOW symbol layers (labels) so road
      // names + POI icons stay visible. _firstSymbolLayer finds the
      // first symbol id; if none, the layer goes on top.
      const beforeId = this._firstSymbolLayer();
      map.addLayer({
        id: "ebike-sat-layer",
        type: "raster",
        source: "ebike-sat",
        paint: { "raster-opacity": 1, "raster-fade-duration": 200 },
      }, beforeId);
    }
    // Buildings + shadows hidden for the same reason as in terrain
    // mode: 3D extrusions over satellite raster looks terrible at
    // pitch 55 and the queryRenderedFeatures cost during playback is
    // wasted. Labels and roads remain on top of the satellite.
    this._hideBuildingsAndShadows();
  }

  _teardownSatellite() {
    const map = this._map;
    if (!map) return;
    try { if (map.getLayer("ebike-sat-layer")) map.removeLayer("ebike-sat-layer"); } catch (_) {}
    try { if (map.getSource("ebike-sat")) map.removeSource("ebike-sat"); } catch (_) {}
    this._restoreBuildingsAndShadows();
  }

  // --- shared visibility helpers ----------------------------------------------
  _hideBuildingsAndShadows() {
    for (const id of this._findBuildingLayers()) this._setLayerVisibility(id, false);
    this._setLayerVisibility("ebike-buildings-3d", false);
    this._setLayerVisibility("ebike-shadows", false);
  }
  _restoreBuildingsAndShadows() {
    for (const id of this._findBuildingLayers()) this._setLayerVisibility(id, true);
    this._setLayerVisibility("ebike-buildings-3d", true);
    this._setLayerVisibility("ebike-shadows", true);
    // Refresh once now that footprints are visible again. Tiny delay
    // gives MapLibre time to re-publish 'building' query results.
    setTimeout(() => this._updateShadows(), 100);
  }

  // Returns the id of the first symbol layer in the current style or
  // undefined. Used to insert satellite raster below labels while
  // keeping it above all the opaque base fills.
  _firstSymbolLayer() {
    if (!this._map || !this._map.getStyle) return undefined;
    const style = this._map.getStyle();
    if (!style || !style.layers) return undefined;
    const sym = style.layers.find((l) => l.type === "symbol");
    return sym ? sym.id : undefined;
  }

  // Helper used by terrain toggle to flip 'visibility' on a layer
  // without crashing if the layer was never added (e.g. style without
  // buildings, or shadow layer not yet initialised).
  _setLayerVisibility(layerId, visible) {
    if (!this._map) return;
    try {
      if (this._map.getLayer(layerId)) {
        this._map.setLayoutProperty(layerId, "visibility", visible ? "visible" : "none");
      }
    } catch (_) { /* ignore */ }
  }

  _buildCumulativeDistances() {
    const pts = this._currentTrack;
    const cum = [0];
    let total = 0;
    for (let i = 1; i < pts.length; i++) {
      total += this._haversine(pts[i - 1], pts[i]);
      cum.push(total);
    }
    this._cumDist = cum;
    this._totalDistM = total;
  }

  _haversine(a, b) {
    const R = 6371000;
    const rad = Math.PI / 180;
    const dLat = (b.lat - a.lat) * rad;
    const dLon = (b.lon - a.lon) * rad;
    const lat1 = a.lat * rad, lat2 = b.lat * rad;
    const h = Math.sin(dLat / 2) ** 2 + Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLon / 2) ** 2;
    return 2 * R * Math.asin(Math.sqrt(h));
  }

  // Best-available tour duration in seconds. The backend exposes
  // `durationWithoutStops` (preferred) and `endTime`; legacy callers may
  // also pass a `duration` field. We try them in that order and fall
  // back to 0 if nothing usable is present.
  _tourDurationSec(a) {
    if (!a) return 0;
    if (Number.isFinite(a.durationWithoutStops) && a.durationWithoutStops > 0) {
      return a.durationWithoutStops;
    }
    if (Number.isFinite(a.duration) && a.duration > 0) {
      return a.duration;
    }
    if (a.startTime && a.endTime) {
      const d = (new Date(a.endTime).getTime() - new Date(a.startTime).getTime()) / 1000;
      if (Number.isFinite(d) && d > 0) return d;
    }
    return 0;
  }

  // Resolve an overlay-visibility flag. Cascade: shared HA-Storage >
  // card YAML > "default on". Truthy by default; only an explicit 0 /
  // "0" / false / "false" / "off" disables.
  _showFlag(key) {
    const v = readCardSetting(this._config, key, undefined);
    if (v === undefined || v === null || v === "") return true;
    return !(v === 0 || v === "0" || v === false || v === "false" || v === "off");
  }

  // Like _showFlag but with an explicit default (used for options that
  // should be OFF unless the user opts in).
  _optionOn(key, defaultOn) {
    const v = readCardSetting(this._config, key, undefined);
    if (v === undefined || v === null || v === "") return !!defaultOn;
    return !(v === 0 || v === "0" || v === false || v === "false" || v === "off");
  }

  // Weather-toggle chip (chase-cam overlay, sibling of the daylight
  // chip): a more discoverable ADDITIONAL control for the same
  // show_weather shared setting the editor's number field already
  // exposes - single source of truth, no localStorage override layer
  // like north-up's. Reads the current value via the same _showFlag()
  // accessor _applyIndex() already uses to gate the weather overlay
  // itself, so this stays consistent with the rest of the class. The
  // chip's own class is updated optimistically right away so the click
  // feels responsive (mirroring _toggleNorthUp -> _updateNorthUpButton),
  // then the value is persisted via saveCardSetting() fire-and-forget -
  // same async-write-no-block, fail-soft-on-error convention every
  // other shared-setting write in this file already follows (e.g.
  // mkWarnInput's number inputs). On success, saveCardSetting() dispatches
  // _cardSettingsBus's "changed" event, which triggers a full
  // _renderDetail() (via _cardSettingsHandler/_renderRoot) that rebuilds
  // this chip's class inline from _showFlag() again anyway - so the
  // optimistic update here only needs to bridge the gap until that
  // round trip resolves. That rebuild tears down and recreates the
  // MapLibre instance (see _renderDetail()'s "Tear down any previous
  // MapLibre instance" comment just below) - _renderDetail() and
  // _initMap() capture and restore the chase-cam's scrub position and
  // play/pause state across it (resumeFrac/resumePlaying), so clicking
  // this chip mid-playback does not stop the animation or snap the
  // scrubber back to the start of the track.
  _toggleWeatherChip() {
    const chip = this._root?.querySelector("#m3d-wx-toggle-chip");
    // Derive `next` from the chip's own current DOM state, not from
    // _showFlag()/_cardSettingsCache - that cache only reflects a prior
    // saveCardSetting() call once its WS round-trip resolves and the
    // "changed" event fires. Two clicks inside that window would
    // otherwise both read the same pre-click cached value and compute
    // the same `next`, silently swallowing the second click's
    // toggle-back intent (both writes persist the same value, and the
    // classList.toggle below becomes a no-op on the second click).
    // Reading the DOM keeps this path immune to that race, the same
    // way _toggleNorthUp() is immune via its synchronous
    // localStorage-backed persistence.
    const next = !chip?.classList.contains("active");
    if (chip) chip.classList.toggle("active", next);
    saveCardSetting(this._hass, "show_weather", next ? 1 : 0);
  }

  _renderDetail() {
    const a = this._currentActivity;
    if (!a) return;
    // Snapshot playback state BEFORE _destroyMap() below wipes it
    // (_destroyMap -> _stopAnim() sets _isPlaying=false; _initMap()
    // unconditionally re-applies index 0). _renderDetail() is not only
    // called once when a tour is opened - it is also re-invoked on every
    // _cardSettingsBus "changed" event (_cardSettingsHandler/_renderRoot),
    // i.e. whenever ANY open card - this one or another instance on a
    // different dashboard - changes a shared setting (show_date,
    // show_time, show_sun, stats_as_chips, the show_weather editor field,
    // or the weather-toggle chip added alongside this comment). Without
    // preserving state here, a mid-playback settings change from
    // elsewhere would silently snap this card's chase-cam back to frame 0
    // and stop the animation - the exact "jarring interruption" outcome
    // that must not happen. `this._map` is only truthy if a PREVIOUS
    // _renderDetail() call already built one for this same tour - the
    // first render after _openTour() has none yet, so both stay
    // undefined/false there and _initMap() falls back to its normal
    // start-at-0-paused behaviour.
    const resumeFrac = this._map ? this._currentFracIndex : undefined;
    const resumePlaying = this._map ? this._isPlaying : false;
    // Tear down any previous MapLibre instance + markers before we
    // wipe the DOM with innerHTML. Without this, a re-render leaves
    // an orphaned map object whose markers are gone from the DOM,
    // and the new map+markers race against the orphan's leftover
    // event handlers.
    this._destroyMap();
    this._teardownIdleFade();
    const title = a.title || this._t("msg_unnamed_ride");
    const hide = (key) => this._showFlag(key) ? "" : "display:none;";
    const statsAsChips = this._optionOn("stats_as_chips", false);
    this._root.innerHTML = `
      <div class="map3d-head">
        <button class="map3d-back-btn" type="button">
          <ha-icon icon="mdi:arrow-left"></ha-icon><span>${this._t("map3d_back")}</span>
        </button>
        <div class="title">${this._escapeHtml(title)}</div>
      </div>
      <div class="map3d-detail">
        <div class="map3d-canvas" id="m3d-canvas"></div>
        <div class="map3d-overlay">
          <span class="map3d-chip" id="m3d-date-chip" style="${hide("show_date")}">
            <ha-icon icon="mdi:calendar-blank"></ha-icon><span id="m3d-date-text">--</span>
          </span>
          <span class="map3d-chip" id="m3d-time-chip" style="${hide("show_time")}">
            <ha-icon icon="mdi:clock-outline"></ha-icon><span id="m3d-time-text">--:--</span>
          </span>
          <span class="map3d-chip" id="m3d-sun-chip" style="${hide("show_sun")}">
            <ha-icon icon="mdi:white-balance-sunny" id="m3d-sun-ico"></ha-icon><span id="m3d-sun-text">--</span>
          </span>
          <button class="map3d-chip map3d-wx-toggle-chip${this._showFlag("show_weather") ? " active" : ""}" id="m3d-wx-toggle-chip" type="button" title="${this._t("btn_weather")}" aria-label="${this._t("btn_weather")}">
            <ha-icon icon="mdi:weather-partly-cloudy"></ha-icon><span>${this._t("btn_weather")}</span>
          </button>
          ${statsAsChips ? `
          <span class="map3d-chip" id="m3d-dist-chip" style="${hide("show_distance")}">
            <ha-icon icon="mdi:map-marker-distance"></ha-icon><span id="m3d-stat-dist">–</span>
          </span>
          <span class="map3d-chip" id="m3d-speed-chip" style="${hide("show_speed")}">
            <ha-icon icon="mdi:speedometer"></ha-icon><span id="m3d-stat-speed">–</span>
          </span>
          <span class="map3d-chip" id="m3d-ele-chip" style="${hide("show_elevation")}">
            <ha-icon icon="mdi:elevation-rise"></ha-icon><span id="m3d-stat-ele">–</span>
          </span>
          ` : ""}
          <span class="map3d-chip map3d-rec-badge" id="m3d-rec-badge" style="display:none">
            <ha-icon icon="mdi:record"></ha-icon><span>${this._t("map3d_record_active")}</span>
          </span>
          <span class="map3d-mode-switch" id="m3d-mode-switch">
            <button class="map3d-mode-pill" data-mode="vector" type="button">
              <ha-icon icon="mdi:map-outline"></ha-icon>${this._t("map3d_mode_vector")}
            </button>
            <button class="map3d-mode-pill" data-mode="terrain" type="button">
              <ha-icon icon="mdi:terrain"></ha-icon>${this._t("map3d_mode_terrain")}
            </button>
            <button class="map3d-mode-pill" data-mode="satellite" type="button">
              <ha-icon icon="mdi:earth"></ha-icon>${this._t("map3d_mode_satellite")}
            </button>
          </span>
          <span class="map3d-terrain-progress" id="m3d-terrain-progress" style="display:none">…</span>
          <button class="map3d-nu-btn" id="m3d-nu-btn" type="button" title="${this._t("map3d_btn_north_up")}" aria-label="${this._t("map3d_btn_north_up")}">
            <ha-icon icon="mdi:compass-outline"></ha-icon>
          </button>
          <button class="map3d-fs-btn" id="m3d-fs-btn" type="button" title="${this._t("btn_fullscreen")}" aria-label="${this._t("btn_fullscreen")}">
            <ha-icon icon="mdi:fullscreen" id="m3d-fs-ico"></ha-icon>
          </button>
          <button class="map3d-close-btn" id="m3d-close-btn" type="button" title="${this._t("btn_close")}" aria-label="${this._t("btn_close")}">
            <ha-icon icon="mdi:close"></ha-icon>
          </button>
        </div>
        <div id="m3d-wx-overlay" class="eb-wx-overlay" style="${hide("show_weather")}">
          <div class="eb-wx-veil"></div>
          <canvas class="eb-wx-canvas"></canvas>
          <div class="eb-wx-flash"></div>
        </div>
        <div class="map3d-controls">
          <div class="row1">
            <button class="map3d-play-btn" type="button" id="m3d-play">
              <ha-icon icon="mdi:play" id="m3d-play-ico"></ha-icon>
            </button>
            <span class="map3d-time" id="m3d-t-start">--:--</span>
            <input type="range" class="map3d-slider" id="m3d-slider" min="0" max="100" step="0.01" value="0">
            <span class="map3d-time" id="m3d-t-end">--:--</span>
            <button class="map3d-rec-btn" type="button" id="m3d-rec" title="${this._t("map3d_record_start")}">
              <ha-icon icon="mdi:record-circle-outline" id="m3d-rec-ico"></ha-icon>
            </button>
          </div>
          ${statsAsChips ? "" : `
          <div class="map3d-stats">
            <span id="m3d-stat-dist-wrap" style="${hide("show_distance")}"><span>${this._t("map3d_distance_label")}: </span><span class="v" id="m3d-stat-dist">–</span></span>
            <span id="m3d-stat-speed-wrap" style="${hide("show_speed")}"><span>${this._t("map3d_speed_label")}: </span><span class="v" id="m3d-stat-speed">–</span></span>
            <span id="m3d-stat-ele-wrap" style="${hide("show_elevation")}"><span>${this._t("map3d_elevation_label")}: </span><span class="v" id="m3d-stat-ele">–</span></span>
          </div>
          `}
        </div>
      </div>
    `;

    const exitDetail = () => {
      if (document.fullscreenElement === this || document.webkitFullscreenElement === this) {
        (document.exitFullscreen || document.webkitExitFullscreen)?.call(document);
      }
      // CSS pseudo-fullscreen fallback (iOS WKWebView, etc.)
      this.classList.remove("map3d-pseudo-fs");
      this._stopAnim();
      this._destroyMap();
      this._teardownIdleFade();
      this._mode = "list";
      this._currentActivity = null;
      this._currentTrack = null;
      this._renderRoot();
    };
    this._root.querySelector(".map3d-back-btn").addEventListener("click", exitDetail);
    const closeBtn = this._root.querySelector("#m3d-close-btn");
    if (closeBtn) closeBtn.addEventListener("click", exitDetail);

    const slider = this._root.querySelector("#m3d-slider");
    slider.max = String(this._currentTrack.length - 1);
    slider.addEventListener("input", () => {
      this._stopAnim();
      this._applyIndex(Number(slider.value));
    });
    slider.addEventListener("change", () => {
      // Refresh shadows once the user releases the slider (sun has moved)
      this._updateShadows();
    });

    const playBtn = this._root.querySelector("#m3d-play");
    playBtn.addEventListener("click", () => this._togglePlay());

    const recBtn = this._root.querySelector("#m3d-rec");
    if (recBtn) {
      if (typeof MediaRecorder === "undefined" ||
          typeof HTMLCanvasElement.prototype.captureStream !== "function") {
        recBtn.disabled = true;
        recBtn.title = this._t("map3d_record_unsupported");
      } else {
        recBtn.addEventListener("click", () => this._toggleRecording());
      }
    }

    const fsBtn = this._root.querySelector("#m3d-fs-btn");
    if (fsBtn) {
      fsBtn.addEventListener("click", () => this._toggleFullscreen());
    }
    this._ensureFullscreenListener();

    const nuBtn = this._root.querySelector("#m3d-nu-btn");
    if (nuBtn) {
      nuBtn.addEventListener("click", () => this._toggleNorthUp());
    }
    this._updateNorthUpButton();

    const wxToggleChip = this._root.querySelector("#m3d-wx-toggle-chip");
    if (wxToggleChip) {
      // Real <button> (see markup above): click already fires correctly
      // for both mouse and keyboard activation (Enter/Space), including
      // native single-fire-per-press key-repeat handling, so no manual
      // keydown listener is needed here.
      wxToggleChip.addEventListener("click", () => this._toggleWeatherChip());
    }

    const switchEl = this._root.querySelector("#m3d-mode-switch");
    if (switchEl) {
      switchEl.addEventListener("click", (ev) => {
        const btn = ev.target.closest(".map3d-mode-pill");
        if (!btn) return;
        const mode = btn.dataset.mode;
        if (mode && mode !== this._mapMode) this._setMapMode(mode);
      });
    }
    // _mapMode is the currently APPLIED mode on the map. Initial state
    // is always 'vector' here; the actual activation of a persisted
    // terrain/satellite preference happens after the map's 'load'
    // event in _initMap, so MapLibre has a stable style first.
    this._mapMode = "vector";
    this._updateModeUI();

    this._setupIdleFade(this._root.querySelector(".map3d-detail"));

    this._initMap(resumeFrac, resumePlaying);
  }

  // resumeFrac/resumePlaying: scrub position + play state captured by
  // _renderDetail() just before it tore down the previous map (undefined/
  // false on a freshly opened tour - see the comment there). Used below to
  // put the chase-cam back where it was instead of always starting at
  // frame 0, so a settings-change re-render does not interrupt playback.
  async _initMap(resumeFrac, resumePlaying) {
    // Epoch token: if _initMap is called again before this one finishes
    // (async race during ensureMapLibre), the older call bails out so
    // only the newest init creates a Map and adds markers.
    const myEpoch = ++this._mapInitEpoch;
    let mlib;
    try {
      mlib = await ensureMapLibre();
    } catch (e) {
      this._showMessage(this._t("map3d_err_maplibre"));
      return;
    }
    // Register the IDB-backed DEM protocol exactly once. Safe to call on
    // every init; the function is idempotent after the first call.
    try { registerEbikeProtocols(mlib); } catch (_) {}
    if (myEpoch !== this._mapInitEpoch) {
      console.log("[Bosch eBike 3D] init skipped (newer epoch already running)");
      return;
    }
    const a = this._currentActivity;
    const pts = this._currentTrack;
    const startTime = a.startTime ? new Date(a.startTime) : new Date();
    const meanLat = pts.reduce((s, p) => s + p.lat, 0) / pts.length;
    const meanLon = pts.reduce((s, p) => s + p.lon, 0) / pts.length;

    const sun = sunPositionAt(startTime, meanLat, meanLon);
    const altDeg = sun.altitude * 180 / Math.PI;
    const azDeg = ((sun.azimuth * 180 / Math.PI) + 180 + 360) % 360;
    const mood = sunMoodFor(altDeg);

    const canvas = this._root.querySelector("#m3d-canvas");
    // Chase-cam: pitch ~55° (looking forward over the bike) and zoom ~17
    // (about 100 m of road visible ahead). User can override via config.
    // Upper bound raised from 65 to 80 (issue #43): MapLibre's own default
    // maxPitch is 60, so anything above that was already being silently
    // clamped by the map itself regardless of this setting - see the
    // matching maxPitch: 80 on the Map constructor below, which is what
    // actually lets values in the new 65-80 range take effect.
    const chasePitch = Math.max(20, Math.min(80, Number(readCardSetting(this._config, "default_pitch", undefined)) || 55));
    const chaseZoom = Math.max(14, Math.min(19, Number(readCardSetting(this._config, "chase_zoom", undefined)) || 17));

    // FPV/action-cam mode (issue #43): an alternative camera driven by real
    // metre distances instead of pitch/zoom, computed per frame in
    // _applyIndex via calculateCameraOptionsFromTo. "chase" (default)
    // leaves ALL existing behavior above unchanged. Computed BEFORE the
    // pitch/zoom preference below so that a stored CHASE-mode override
    // (see pitchend/zoomend further down) can never leak into an FPV
    // card's initial camera frame - the two camera modes share this._map's
    // constructor call, and localStorage is not per-card-instance scoped.
    const cameraModeRaw = readCardSetting(this._config, "camera_mode", "chase");
    this._cameraMode = cameraModeRaw === "fpv" ? "fpv" : "chase";

    // A live manual pitch/zoom adjustment (see the pitchend/zoomend
    // listeners below) overrides the config default and persists across
    // reloads, same idea as the north-up preference above. Chase mode only:
    // FPV never reads this._chasePitch/this._chaseZoom (its own camera is
    // computed fresh every frame via calculateCameraOptionsFromTo), and the
    // save-side listeners already skip FPV cards - this is the matching
    // gate on the load/apply side.
    const pitchPref = this._cameraMode === "fpv" ? null : this._loadChasePitchPref();
    const zoomPref = this._cameraMode === "fpv" ? null : this._loadChaseZoomPref();
    this._chasePitch = pitchPref != null ? Math.max(20, Math.min(80, pitchPref)) : chasePitch;
    this._chaseZoom = zoomPref != null ? Math.max(14, Math.min(19, zoomPref)) : chaseZoom;
    this._fpvHeight = Math.max(0.3, Math.min(10, Number(readCardSetting(this._config, "fpv_height_m", undefined)) || 2));
    this._fpvDistance = Math.max(0, Math.min(30, Number(readCardSetting(this._config, "fpv_distance_m", undefined)) || 4));
    this._fpvLookahead = Math.max(3, Math.min(80, Number(readCardSetting(this._config, "fpv_lookahead_m", undefined)) || 20));

    // Wait for layout to settle so the canvas has a real height. Without
    // this, MapLibre boots with a 0x0 WebGL viewport.
    await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
    void canvas.offsetHeight;

    // Initial pose: chase-cam look-target ~60 m AHEAD of the bike along
    // the smoothed bearing. That places the bike behind the camera focus,
    // so the rendered bike sits in the lower part of the screen and the
    // upcoming road fills the rest.
    const initialBearing = this._bearingAt(0);
    // chase_lookahead is now interpreted as a PIXEL offset that pushes
    // the rendered centre down on screen, so the bike (which is the
    // map centre) appears in the lower part of the canvas. Larger
    // value -> bike sits lower, more sky/road ahead visible. Range
    // kept compatible with the previous metre-based config to avoid
    // breaking existing user setups; 30 still works as a good default.
    const lookAheadPx = Math.max(0, Math.min(200, Number(readCardSetting(this._config, "chase_lookahead", undefined)) || 30));
    this._chaseLookAhead = lookAheadPx;
    // Resume position (see the resumeFrac/resumePlaying comment on the
    // caller side, _renderDetail()): defaults to the very start of the
    // track when there is nothing to resume. Seeded here already (ahead
    // of the map's 'load' event further below) purely so a stray
    // _updateShadows() call during camera setup has a plausible
    // integer-anchored index instead of always claiming frame 0.
    const startFrac = (resumeFrac != null && Number.isFinite(resumeFrac)) ? resumeFrac : 0;
    this._currentIndex = Math.floor(startFrac);
    // Local capture: 'myMap' is THIS init's map. Use it instead of
    // this._map inside async callbacks, so a later re-init that
    // overwrites this._map cannot pollute or hijack the wrong map.
    // Initial centre is the bike's start position; the pixel offset
    // is applied via the first _applyIndex(startFrac, true) easeTo, which
    // animates from no-offset to offset over 900 ms.
    const myMap = new mlib.Map({
      container: canvas,
      style: OPENFREEMAP_LIBERTY,
      center: [pts[0].lon, pts[0].lat],
      zoom: this._chaseZoom,
      pitch: this._chasePitch,
      bearing: initialBearing,
      attributionControl: false,
      maxTileCacheSize: 200,
      preserveDrawingBuffer: true,
      // Default maxPitch is 60 (issue #43): raised so the extended
      // 65-80° chase-cam range and the FPV camera's own steep pitch
      // (derived from height/distance, can exceed 60 at close range)
      // are not silently clamped back down by the map itself.
      maxPitch: 80,
    });
    this._map = myMap;
    myMap.addControl(new mlib.AttributionControl({ compact: true }), "bottom-right");
    myMap.addControl(new mlib.NavigationControl({ visualizePitch: true }), "top-right");

    if (typeof ResizeObserver !== "undefined") {
      this._resizeObs = new ResizeObserver(() => {
        if (this._map === myMap) { try { myMap.resize(); } catch (_) {} }
      });
      this._resizeObs.observe(canvas);
    }

    myMap.on("error", (e) => {
      console.warn("[Bosch eBike 3D] map error", e && e.error);
    });

    // Capture a manual pitch/zoom adjustment and persist it. e.originalEvent
    // is only set by MapLibre's own interaction handlers (drag/scroll/pinch),
    // never by our own programmatic jumpTo/easeTo calls in _applyIndex below
    // (verified against the bundled MapLibre source - interaction handlers
    // pass {originalEvent: e} as eventData, our calls never do) - so this
    // only fires for something the user actually did with their hands, not
    // every per-frame chase-cam camera update. Chase mode only: FPV's camera
    // is computed fresh every frame from real metre distances and has no
    // comparable persisted pitch/zoom concept.
    myMap.on("pitchend", (e) => {
      if (this._map !== myMap || this._cameraMode === "fpv" || !e || !e.originalEvent) return;
      const p = myMap.getPitch();
      this._chasePitch = p;
      this._saveChasePitchPref(p);
    });
    myMap.on("zoomend", (e) => {
      if (this._map !== myMap || this._cameraMode === "fpv" || !e || !e.originalEvent) return;
      const z = myMap.getZoom();
      this._chaseZoom = z;
      this._saveChaseZoomPref(z);
    });

    myMap.on("load", () => {
      // If a newer init has overwritten this._map already, do not touch
      // it — that map has its own load handler that will run.
      if (this._map !== myMap) return;

      // Lighting & sky from sun mood
      try {
        myMap.setLight({
          anchor: "viewport",
          color: mood.sun,
          intensity: altDeg > 0 ? 0.6 : 0.15,
          position: [1.15, azDeg, Math.max(5, 90 - altDeg)],
        });
      } catch (_) { /* older MapLibre versions */ }

      this._addTrackLayers(this._rawTrack || pts);
      this._addBuildingsIfNeeded();
      this._initShadowLayer();

      myMap.on("moveend", () => {
        if (this._map === myMap) this._updateShadows();
      });
      setTimeout(() => { if (this._map === myMap) this._updateShadows(); }, 400);
      setTimeout(() => { if (this._map === myMap) this._updateShadows(); }, 1500);

      // Markers — attach explicitly to myMap, the local capture. If
      // this._map has been swapped to a different instance, those
      // markers would land on a destroyed map and never reach the DOM.
      this._addPointMarker(pts[0], "#ff9800", "S", myMap);
      this._addPointMarker(pts[pts.length - 1], "#e53935", "Z", myMap);

      // Bike marker as a MapLibre Marker bound to (lat, lon). With the
      // camera now centred ON the bike and an offset moving the screen
      // origin down, the bike's projected pixel position is identical
      // every frame regardless of terrain elevation under it. So the
      // marker never drifts off the track, and MapLibre's render lag
      // (if any) affects marker and world tiles equally - they stay
      // visually locked. A child arrow rotates in north-up mode to
      // indicate travel direction; in bearing-follow mode the arrow
      // stays at 0 (pointing screen-up = forward).
      const el = document.createElement("div");
      el.className = "ebike-3d-marker";
      el.style.cssText =
        "position:absolute;top:0;left:0;" +
        "width:18px;height:18px;border-radius:50%;" +
        "background:#42c76a;border:5px solid #fff;" +
        "box-shadow:0 0 0 6px rgba(66,199,106,.35),0 4px 18px rgba(0,0,0,.65);" +
        "z-index:100;";
      const arrow = document.createElement("div");
      arrow.className = "ebike-3d-marker-arrow";
      // White triangular pointer centred in the marker. transform-
      // origin = centre so the arrow rotates around the bike's
      // projected position, not its tip. translate(-50%,-58%) nudges
      // the visual centre of mass up a hair so the tip lands on the
      // green border, matching the bike's heading visually.
      arrow.style.cssText =
        "position:absolute;left:50%;top:50%;" +
        "width:10px;height:10px;" +
        "background:#fff;" +
        "clip-path:polygon(50% 0%, 100% 100%, 50% 70%, 0% 100%);" +
        "transform:translate(-50%,-58%) rotate(0deg);" +
        "transform-origin:center;" +
        "pointer-events:none;";
      el.appendChild(arrow);
      this._markerArrowEl = arrow;
      this._marker = new mlib.Marker({ element: el, anchor: "center" })
        .setLngLat([pts[0].lon, pts[0].lat])
        .addTo(myMap);

      // Diagnostic: verify marker placement and DOM visibility shortly
      // after creation. If the marker is in DOM but reports a
      // projected pixel position outside the canvas, the camera has
      // moved away from it. If it is not in DOM at all, something is
      // removing it.

      // Resize once after layers are added, then apply the chase-cam at
      // startFrac (0 for a freshly opened tour, or the preserved scrub
      // position when this init is resuming after a settings-driven
      // rebuild - see the resumeFrac/resumePlaying comments above).
      // _applyIndex jumps the camera to the bike's position, bearing-
      // aligned with the direction of travel.
      try { this._map.resize(); } catch (_) {}

      this._applyIndex(startFrac, true);
      // _applyIndex() above already called _updateTimeChips() with the
      // date/time/sun correctly interpolated for startFrac. This second
      // call only adds value for the true tour-start case (startFrac===0,
      // where the two happen to agree) - for a resumed position it would
      // wrongly stomp the just-set chips back to the tour's absolute
      // start time, so it is skipped there.
      if (startFrac === 0) {
        this._updateTimeChips(0, startTime, altDeg, mood);
      }
      this._updateRangeLabels();

      // Restore persisted map mode (vector / terrain / satellite). Done
      // here, AFTER the base style finished loading, so the source +
      // layer additions attach to a stable map. Failure (no internet,
      // IDB blocked) silently falls back to plain vector - we never
      // block the map from rendering.
      const wantMode = this._loadMapModePref();
      if (wantMode && wantMode !== "vector") {
        this._setMapMode(wantMode, { silent: true }).catch((e) => {
          console.warn("[Bosch eBike 3D] mode auto-restore failed", e);
        });
      }

      // Resume playback (see _renderDetail()'s resumeFrac/resumePlaying
      // comment): only reached when a settings-change re-render tore
      // down and rebuilt the map WHILE the chase-cam was mid-animation.
      // _startAnim() reads the slider's current value for its start
      // point, which _applyIndex() above already set to startFrac.
      if (resumePlaying) {
        try { this._startAnim(); } catch (_) {}
      }
    });
  }

  // Pre-compute a smoothed bearing for every track point. The chase-cam
  // then looks up the value instead of recomputing on every frame, which
  // both eliminates jitter and removes per-frame cost.
  //
  // Smoothing uses a sliding window of W points on each side and
  // averages bearings as unit vectors (cos, sin) so that the 0°/360°
  // wrap-around is handled correctly (averaging 350° and 10° yields 0°,
  // not 180°).
  _precomputeBearings() {
    const pts = this._currentTrack;
    if (!pts || pts.length < 2) {
      this._smoothedBearings = null;
      return;
    }
    // Raw bearings between consecutive points
    const raw = new Array(pts.length);
    for (let i = 0; i < pts.length - 1; i++) {
      raw[i] = this._calcBearing(pts[i], pts[i + 1]);
    }
    raw[pts.length - 1] = raw[pts.length - 2] != null ? raw[pts.length - 2] : 0;

    // Wider window = smoother camera but corners are taken wider.
    const W = Math.max(1, Math.min(60, Number(readCardSetting(this._config, "smooth_window", undefined)) || 15));
    const smoothed = new Array(raw.length);
    const rad = Math.PI / 180;
    for (let i = 0; i < raw.length; i++) {
      const lo = Math.max(0, i - W);
      const hi = Math.min(raw.length - 1, i + W);
      let sx = 0, sy = 0;
      for (let j = lo; j <= hi; j++) {
        const a = raw[j] * rad;
        sx += Math.cos(a);
        sy += Math.sin(a);
      }
      smoothed[i] = (Math.atan2(sy, sx) * 180 / Math.PI + 360) % 360;
    }
    this._smoothedBearings = smoothed;
  }

  _bearingAt(i) {
    if (this._smoothedBearings) {
      const idx = Math.max(0, Math.min(this._smoothedBearings.length - 1, Math.round(i)));
      return this._smoothedBearings[idx];
    }
    return 0;
  }

  _calcBearing(a, b) {
    const rad = Math.PI / 180;
    const lat1 = a.lat * rad, lat2 = b.lat * rad;
    const dLon = (b.lon - a.lon) * rad;
    const y = Math.sin(dLon) * Math.cos(lat2);
    const x = Math.cos(lat1) * Math.sin(lat2) - Math.sin(lat1) * Math.cos(lat2) * Math.cos(dLon);
    const brng = Math.atan2(y, x) * 180 / Math.PI;
    return (brng + 360) % 360;
  }

  // Coordinate `distanceMeters` ahead of `p` along compass `bearingDeg`.
  // Equirectangular approximation, accurate enough for chase-cam offsets
  // of a few dozen metres.
  _lookAheadCoord(p, bearingDeg, distanceMeters) {
    const bRad = bearingDeg * Math.PI / 180;
    const metersPerDegLat = 111320;
    const metersPerDegLon = 111320 * Math.cos(p.lat * Math.PI / 180);
    const dLat = (distanceMeters * Math.cos(bRad)) / metersPerDegLat;
    const dLon = (distanceMeters * Math.sin(bRad)) / Math.max(1, metersPerDegLon);
    return [p.lon + dLon, p.lat + dLat];
  }


  _addPointMarker(p, color, _label, mapOverride) {
    const target = mapOverride || this._map;
    if (!target || !window.maplibregl) return;
    const el = document.createElement("div");
    // Explicit position:absolute + top/left:0 because MapLibre's
    // own CSS (which sets these on .maplibregl-marker) is in the
    // document <head> and does not penetrate HA's shadow DOM.
    el.style.cssText =
      "position:absolute;top:0;left:0;" +
      `width:14px;height:14px;border-radius:50%;background:${color};` +
      "border:2px solid #fff;box-shadow:0 1px 3px rgba(0,0,0,.4);";
    new window.maplibregl.Marker({ element: el }).setLngLat([p.lon, p.lat]).addTo(target);
  }

  // Track polyline (glow + main stroke). Idempotent: removes existing
  // ebike layers/sources first so it can be safely called after a
  // style.setStyle() swap. Always uses the RAW GPS samples (not the
  // smoothed camera-path copy) so the line on the map matches what was
  // actually recorded.
  _addTrackLayers(pts) {
    if (!this._map) return;
    pts = pts || this._rawTrack || this._currentTrack;
    if (!pts || !pts.length) return;
    const coords = pts.map((p) => [p.lon, p.lat]);
    try { if (this._map.getLayer("ebike-track")) this._map.removeLayer("ebike-track"); } catch (_) {}
    try { if (this._map.getLayer("ebike-track-glow")) this._map.removeLayer("ebike-track-glow"); } catch (_) {}
    try { if (this._map.getSource("ebike-track")) this._map.removeSource("ebike-track"); } catch (_) {}
    this._map.addSource("ebike-track", {
      type: "geojson",
      data: { type: "Feature", geometry: { type: "LineString", coordinates: coords }, properties: {} },
    });
    this._map.addLayer({
      id: "ebike-track-glow",
      type: "line",
      source: "ebike-track",
      layout: { "line-cap": "round", "line-join": "round" },
      paint: { "line-color": "#03a9f4", "line-width": 9, "line-opacity": 0.25, "line-blur": 3 },
    });
    this._map.addLayer({
      id: "ebike-track",
      type: "line",
      source: "ebike-track",
      layout: { "line-cap": "round", "line-join": "round" },
      paint: { "line-color": "#03a9f4", "line-width": 4.5, "line-opacity": 0.95 },
    });
  }

  // Discover all style layers that visualise buildings, regardless of
  // the exact id used by the upstream OpenFreeMap / OpenMapTiles
  // variant. Used both to find the layer to insert shadows before, and
  // to know which layers to query for building features.
  _findBuildingLayers() {
    if (!this._map || !this._map.getStyle) return [];
    const style = this._map.getStyle();
    if (!style || !style.layers) return [];
    return style.layers
      .filter((l) =>
        (l["source-layer"] === "building") ||
        (typeof l.id === "string" &&
         (l.id === "building" || l.id.startsWith("building-") || l.id.includes("buildings"))))
      .map((l) => l.id);
  }

  // Empty shadow source + layer, populated by _updateShadows() once the
  // map has settled. Placed BEFORE the first building-related layer so
  // building extrusions render on top of their own shadows.
  _initShadowLayer() {
    if (!this._map) return;
    try {
      if (this._map.getSource("ebike-shadows")) return;
      this._map.addSource("ebike-shadows", {
        type: "geojson",
        data: { type: "FeatureCollection", features: [] },
      });
      const buildingLayers = this._findBuildingLayers();
      const beforeId = buildingLayers[0]; // may be undefined; that is fine
      this._map.addLayer({
        id: "ebike-shadows",
        type: "fill",
        source: "ebike-shadows",
        minzoom: 13,
        paint: {
          "fill-color": "#0a1018",
          "fill-opacity": 0.55,
          "fill-antialias": true,
        },
      }, beforeId);
      console.log("[Bosch eBike 3D] shadow layer ready. beforeId =", beforeId, "buildingLayers =", buildingLayers);
    } catch (e) {
      console.warn("[Bosch eBike 3D] shadow layer init failed", e);
    }
  }

  // Re-project all visible building footprints into ground-level cast
  // shadows for the sun position at the current slider index. Throttled
  // so a busy chase cam does not hammer it every frame.
  _updateShadows() {
    if (!this._map || !this._map.loaded()) return;
    // Shadows are computed by querying every visible building feature
    // and projecting their footprints onto the ground. Combined with a
    // 3D terrain mesh or satellite imagery this is the dominant
    // per-move cost during playback. Skipped while we are NOT in plain
    // vector mode; the layer itself is hidden by the mode switch so
    // old shadows do not linger.
    if (this._mapMode && this._mapMode !== "vector") return;
    const now = performance.now();
    if (this._shadowsThrottleUntil && now < this._shadowsThrottleUntil) {
      if (!this._shadowsPending) {
        this._shadowsPending = true;
        setTimeout(() => {
          this._shadowsPending = false;
          this._updateShadows();
        }, this._shadowsThrottleUntil - now);
      }
      return;
    }
    this._shadowsThrottleUntil = now + 500;

    const pts = this._currentTrack;
    if (!pts || !pts.length) return;
    const i = this._currentIndex != null ? this._currentIndex : 0;
    const p = pts[i];

    // Sun position at the slider's interpolated time
    const a = this._currentActivity;
    const dur = this._tourDurationSec(a);
    const startTime = a?.startTime ? new Date(a.startTime) : new Date();
    const t = new Date(startTime.getTime() + (i / Math.max(1, pts.length - 1)) * dur * 1000);
    const sun = sunPositionAt(t, p.lat, p.lon);

    const src = this._map.getSource("ebike-shadows");
    if (!src) return;
    if (sun.altitude <= 0) {
      // Below horizon: clear shadows
      src.setData({ type: "FeatureCollection", features: [] });
      return;
    }

    const layerIds = this._findBuildingLayers().filter((id) => this._map.getLayer(id));
    if (!layerIds.length) {
      console.warn("[Bosch eBike 3D] no building layers found in the active style; shadows skipped");
      src.setData({ type: "FeatureCollection", features: [] });
      return;
    }

    let buildings = [];
    try {
      buildings = this._map.queryRenderedFeatures(undefined, { layers: layerIds });
    } catch (e) {
      console.warn("[Bosch eBike 3D] queryRenderedFeatures failed", e);
    }

    const features = [];
    const seen = new Set();
    let skippedHeight = 0;
    let skippedGeom = 0;
    for (const b of buildings) {
      // Dedupe across tile boundaries
      const key = b.id != null ? `i:${b.id}` :
        `g:${b.geometry?.coordinates?.[0]?.[0]?.join(",")}`;
      if (seen.has(key)) continue;
      seen.add(key);

      const props = b.properties || {};
      // OpenMapTiles uses 'render_height'; some vector schemas use 'height',
      // 'min_height' is the building base. Fall back to a 6 m default so
      // small buildings without an explicit height still cast a shadow.
      let h = Number(props.render_height);
      if (!Number.isFinite(h) || h <= 0) h = Number(props.height);
      if (!Number.isFinite(h) || h <= 0) {
        const levels = Number(props["building:levels"] || props.levels);
        if (Number.isFinite(levels) && levels > 0) h = levels * 3;
      }
      if (!Number.isFinite(h) || h <= 0) h = 6;
      if (h < 1) { skippedHeight++; continue; }

      const rings = b.geometry?.type === "Polygon"
        ? [b.geometry.coordinates[0]]
        : b.geometry?.type === "MultiPolygon"
          ? b.geometry.coordinates.map((poly) => poly[0])
          : null;
      if (!rings) { skippedGeom++; continue; }

      for (const ring of rings) {
        const shadow = buildingShadowRing(ring, h, sun.altitude, sun.azimuth, p.lat);
        if (shadow) {
          features.push({
            type: "Feature",
            geometry: { type: "Polygon", coordinates: [shadow] },
            properties: {},
          });
        }
      }
    }
    if (!this._shadowDiagLogged) {
      this._shadowDiagLogged = true;
      console.log("[Bosch eBike 3D] shadow diagnostic:", {
        layerIds,
        rawBuildings: buildings.length,
        uniqueBuildings: seen.size,
        skippedHeight,
        skippedGeom,
        shadowFeatures: features.length,
        sunAltDeg: (sun.altitude * 180 / Math.PI).toFixed(1),
        sampleProps: buildings[0]?.properties,
        sampleGeomType: buildings[0]?.geometry?.type,
      });
    }
    src.setData({ type: "FeatureCollection", features });
  }

  // Add a 3D building-extrusion fallback layer if the active style does
  // not already provide one. Most Liberty style variants ship a building
  // layer, but a few revisions disable it; this guarantees extrusion.
  _addBuildingsIfNeeded() {
    if (!this._map) return;
    if (this._map.getLayer("building-3d") || this._map.getLayer("building") || this._map.getLayer("ebike-buildings-3d")) {
      return;
    }
    try {
      this._map.addLayer({
        id: "ebike-buildings-3d",
        type: "fill-extrusion",
        source: "openmaptiles",
        "source-layer": "building",
        minzoom: 14,
        paint: {
          "fill-extrusion-color": ["case", ["has", "colour"], ["get", "colour"], "#c9c4be"],
          "fill-extrusion-height": ["coalesce", ["get", "render_height"], ["get", "height"], 6],
          "fill-extrusion-base": ["coalesce", ["get", "render_min_height"], 0],
          "fill-extrusion-opacity": 0.85,
        },
      });
    } catch (_) { /* style without openmaptiles source */ }
  }


  // Linearly interpolate two values, treating non-finite operands gracefully.
  _lerpFinite(a, b, f) {
    const af = Number.isFinite(a), bf = Number.isFinite(b);
    if (af && bf) return a + (b - a) * f;
    if (af) return a;
    if (bf) return b;
    return NaN;
  }

  // Shortest-arc circular interpolation of two compass bearings in degrees.
  _lerpBearing(a, b, f) {
    const diff = (((b - a + 540) % 360) - 180);
    return ((a + diff * f) + 360) % 360;
  }

  // Elevation `aheadMeters` further along the track than the current
  // interpolated position, via the precomputed cumulative-distance array.
  // Used as the FPV look-ahead target's altitude fallback while its own
  // DEM tile has not loaded yet - closer to the truth than freezing the
  // target at the bike's current elevation, since the road can climb or
  // descend meaningfully within the (3-80 m) look-ahead distance.
  _elevationAlongTrackAhead(i0, currentDist, aheadMeters) {
    const cum = this._cumDist;
    const pts = this._currentTrack;
    if (!cum || !pts || !pts.length || !Number.isFinite(currentDist)) return NaN;
    const targetDist = currentDist + aheadMeters;
    const N = pts.length - 1;
    let j = Math.max(0, Math.min(N, i0));
    while (j < N && cum[j + 1] < targetDist) j++;
    if (j >= N) return Number.isFinite(pts[N].ele) ? pts[N].ele : NaN;
    const segStart = cum[j], segEnd = cum[j + 1];
    const segF = segEnd > segStart ? (targetDist - segStart) / (segEnd - segStart) : 0;
    return this._lerpFinite(pts[j].ele, pts[j + 1].ele, segF);
  }

  // Fractional version of _bearingAt: looks up two adjacent smoothed
  // bearings and shortest-arc-interpolates between them. The chase cam
  // then turns smoothly across the gap between two GPS samples instead
  // of snapping at each integer index.
  _bearingAtFractional(idx) {
    const arr = this._smoothedBearings;
    if (!arr || !arr.length) return 0;
    const N = arr.length - 1;
    const c = Math.max(0, Math.min(N, idx));
    const i0 = Math.floor(c);
    const i1 = Math.min(N, i0 + 1);
    const f = c - i0;
    return this._lerpBearing(arr[i0], arr[i1], f);
  }

  _applyIndex(idx, isInitial) {
    const pts = this._currentTrack;
    if (!pts || !pts.length) return;
    const clamped = Math.max(0, Math.min(pts.length - 1, idx));
    const i0 = Math.floor(clamped);
    const i1 = Math.min(pts.length - 1, i0 + 1);
    const f = clamped - i0;
    const a0 = pts[i0];
    const a1 = pts[i1];
    // Interpolated current bike state. All downstream visual updates
    // (marker, camera, stats, sun) use this fractional position so the
    // chase cam glides between GPS samples instead of jumping every
    // time the rounded index increments.
    const p = {
      lat: a0.lat + (a1.lat - a0.lat) * f,
      lon: a0.lon + (a1.lon - a0.lon) * f,
      ele: this._lerpFinite(a0.ele, a1.ele, f),
      speed: this._lerpFinite(a0.speed, a1.speed, f),
    };
    this._currentIndex = i0;       // for shadow snapping (integer-anchored)
    this._currentFracIndex = clamped;

    // Second-stage temporal smoothing on the bike position. Both the
    // MapLibre marker and the chase-cam centre use the same EMA
    // output, so they remain perfectly co-located in pixel space
    // while small GPS residuals are damped. Lag ~90 ms at 60 fps is
    // imperceptible during smooth motion.
    const ALPHA = 0.18;
    if (isInitial || this._dispLat == null || this._dispLon == null) {
      this._dispLat = p.lat;
      this._dispLon = p.lon;
    } else {
      this._dispLat += ALPHA * (p.lat - this._dispLat);
      this._dispLon += ALPHA * (p.lon - this._dispLon);
    }

    if (this._marker) this._marker.setLngLat([this._dispLon, this._dispLat]);

    // Chase-cam: camera centred on the bike's smoothed position, with
    // a pixel offset that pushes the rendered centre DOWN by
    // chase_lookahead pixels. Net effect: bike sits in the lower part
    // of the canvas (third-person feel) while the bike's lat/lon
    // projects to the SAME pixel every frame - so the green marker
    // stays glued to the rendered track, regardless of terrain
    // elevation changes as DEM tiles refine.
    if (this._map && this._map.loaded()) {
      try {
        const travelBearing = this._bearingAtFractional(clamped);
        // North-up mode: lock the map bearing to 0 (north stays up)
        // and rotate the marker's arrow child to indicate travel
        // direction instead. The relative arrow rotation = travel
        // bearing minus map bearing, which collapses to 0 in the
        // default mode and to the travel bearing in north-up mode.
        const northUp = this._currentNorthUp();
        let camera;
        if (this._cameraMode === "fpv") {
          // FPV/action-cam (issue #43): camera positioned real metres
          // behind + above the bike, aimed at a point ahead along the
          // travel bearing. MapLibre GL JS has no free/quaternion camera
          // (verified against the actual bundled source - no
          // FreeCameraOptions), so this uses calculateCameraOptionsFromTo,
          // the supported helper that turns two 3D points (lng/lat +
          // altitude in real metres) into the classic center/zoom/pitch/
          // bearing this map already understands.
          const camPoint = destinationPoint(
            this._dispLat, this._dispLon, (travelBearing + 180) % 360, this._fpvDistance
          );
          const lookPoint = destinationPoint(
            this._dispLat, this._dispLon, travelBearing, this._fpvLookahead
          );
          const groundEle = this._map.queryTerrainElevation([camPoint.lon, camPoint.lat]);
          const lookGroundEle = this._map.queryTerrainElevation([lookPoint.lon, lookPoint.lat]);
          const bikeEle = Number.isFinite(p.ele) ? p.ele : 0;
          // Number.isFinite (not just != null) so a NaN from an
          // unloaded DEM tile also falls back to the GPS elevation,
          // instead of poisoning the camera altitude.
          const camAltitude = (Number.isFinite(groundEle) ? groundEle : bikeEle) + this._fpvHeight;
          // calculateCameraOptionsFromTo's target-altitude arg defaults to
          // literally 0 when omitted (verified against the actual MapLibre
          // bundle - it does NOT auto-query terrain at the target). Passing
          // the DEM's own ground elevation ahead keeps camera and target on
          // the same real-world altitude scale; without this, on any route
          // with meaningful elevation above sea level the calculated pitch
          // collapses toward a straight-down top view once the DEM tile
          // finishes loading (the camera altitude jumps to the real terrain
          // height while the target stays pinned at 0).
          // If the DEM tile at lookPoint itself has not loaded yet, prefer
          // the track's OWN elevation ~fpvLookahead metres ahead (via the
          // precomputed cumulative-distance array) over freezing the target
          // at the bike's current elevation - a route can climb or descend
          // meaningfully within the 3-80 m look-ahead distance, and reusing
          // the current elevation would reintroduce a smaller version of the
          // same altitude-mismatch artefact this fix addresses.
          const cumDistHere = this._cumDist
            ? this._lerpFinite(this._cumDist[i0], this._cumDist[i1], f)
            : NaN;
          const trackLookEle = this._elevationAlongTrackAhead(i0, cumDistHere, this._fpvLookahead);
          const lookAltitude = Number.isFinite(lookGroundEle)
            ? lookGroundEle
            : (Number.isFinite(trackLookEle) ? trackLookEle : bikeEle);
          camera = this._map.calculateCameraOptionsFromTo(
            [camPoint.lon, camPoint.lat], camAltitude,
            [lookPoint.lon, lookPoint.lat], lookAltitude
          );
          if (northUp) camera.bearing = 0;
          // The pixel-offset framing trick below is a chase-cam-only hack;
          // the FPV camera's own 3D placement already frames the bike.
          camera.offset = [0, 0];
        } else {
          const mapBearing = northUp ? 0 : travelBearing;
          const offY = this._chaseLookAhead != null ? this._chaseLookAhead : 30;
          camera = {
            center: [this._dispLon, this._dispLat],
            zoom: this._chaseZoom != null ? this._chaseZoom : 17,
            pitch: this._chasePitch != null ? this._chasePitch : 55,
            bearing: mapBearing,
            offset: [0, offY],
          };
        }
        if (isInitial) {
          this._map.easeTo({ ...camera, duration: 900 });
        } else {
          this._map.jumpTo(camera);
        }
        if (this._markerArrowEl) {
          const mapBearingForArrow = camera.bearing != null ? camera.bearing : travelBearing;
          const rel = ((travelBearing - mapBearingForArrow) % 360 + 360) % 360;
          this._markerArrowEl.style.transform = `translate(-50%,-58%) rotate(${rel}deg)`;
        }
      } catch (e) { console.warn("[Bosch eBike 3D] chase-cam update failed", e); }
    }

    // Per-frame interpolated tour time
    const a = this._currentActivity;
    const dur = this._tourDurationSec(a);
    const startTime = a?.startTime ? new Date(a.startTime) : new Date();
    const t = new Date(startTime.getTime() + (clamped / Math.max(1, pts.length - 1)) * dur * 1000);
    const sun = sunPositionAt(t, p.lat, p.lon);
    const altDeg = sun.altitude * 180 / Math.PI;

    // Weather overlay (Task 7): only once the full-ride series has arrived
    // (this._weatherSeries stays null while unfetched/disabled/failed - the
    // common case right after _openTour() starts, before its fetch could
    // possibly have resolved). Reuses altDeg/t computed just above instead
    // of calling sunPositionAt() a second time.
    // Also re-check the live show_weather flag on every tick: toggling it
    // off mid-playback must stop re-showing the overlay, since this block
    // re-runs continuously during autoplay/scrubbing (see code-review notes
    // on commit 047d694). We don't force-hide here - render()'s hide() call
    // already set display:none - we just stop undoing it.
    if (this._weatherSeries && this._showFlag("show_weather")) {
      try {
        const wxSample = interpolateWeatherAt(this._weatherSeries, t);
        if (wxSample) {
          const layers = weatherLayers(wxSample.cloud, wxSample.precip, wxSample.snow, wxSample.code, altDeg);
          _applyWeatherLayers(this._root.querySelector("#m3d-wx-overlay"), layers);
        }
      } catch (e) { console.warn("[Bosch eBike 3D] weather overlay update failed", e); }
    }

    const mood = sunMoodFor(altDeg);
    this._updateTimeChips(clamped, t, altDeg, mood);

    if (this._map && this._map.loaded()) {
      try {
        const azDeg = ((sun.azimuth * 180 / Math.PI) + 180 + 360) % 360;
        this._map.setLight({
          anchor: "viewport",
          color: mood.sun,
          intensity: altDeg > 0 ? 0.6 : 0.15,
          position: [1.15, azDeg, Math.max(5, 90 - altDeg)],
        });
      } catch (_) { /* ignore */ }
    }

    // Stats: also interpolated. Distance uses the cumulative array.
    const cum = this._cumDist;
    const dist = cum ? this._lerpFinite(cum[i0], cum[i1], f) : 0;
    const distLbl = Number.isFinite(dist)
      ? (dist / 1000).toLocaleString(undefined, { maximumFractionDigits: 1 }) + " km"
      : "–";
    const distEl = this._root.querySelector("#m3d-stat-dist");
    if (distEl) distEl.textContent = distLbl;
    const sp = Number.isFinite(p.speed) ? p.speed : null;
    const speedEl = this._root.querySelector("#m3d-stat-speed");
    // Always one decimal so the chip width stays constant across
    // whole and fractional values (27 km/h vs 27,3 km/h was visibly
    // jumping the neighbouring chips around).
    if (speedEl) speedEl.textContent =
      sp != null
        ? sp.toLocaleString(undefined, { minimumFractionDigits: 1, maximumFractionDigits: 1 }) + " km/h"
        : "–";
    const ele = Number.isFinite(p.ele) ? p.ele : null;
    const eleEl = this._root.querySelector("#m3d-stat-ele");
    if (eleEl) eleEl.textContent = ele != null ? Math.round(ele) + " m" : "–";

    const slider = this._root.querySelector("#m3d-slider");
    if (slider && document.activeElement !== slider) {
      slider.value = String(clamped);
    }
  }

  _updateTimeChips(_i, time, altDeg, mood) {
    const fmtHm = (d) => `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
    const tt = this._root.querySelector("#m3d-time-text");
    if (tt) tt.textContent = fmtHm(time);
    const dt = this._root.querySelector("#m3d-date-text");
    if (dt) {
      const lang = (this._hass && this._hass.locale && this._hass.locale.language)
        || (this._hass && this._hass.language) || navigator.language || "en-GB";
      try {
        dt.textContent = time.toLocaleDateString(lang, {
          weekday: "short", day: "2-digit", month: "short"
        });
      } catch (_) {
        dt.textContent = time.toISOString().slice(0, 10);
      }
    }
    const st = this._root.querySelector("#m3d-sun-text");
    if (st) {
      // Word label, not a degree value: degree symbol on a sun-themed chip
      // was being mistaken for a temperature reading.
      const key = "map3d_sun_" + (mood?.label || "day");
      st.textContent = this._t(key);
    }
    const sico = this._root.querySelector("#m3d-sun-ico");
    if (sico) {
      sico.setAttribute("icon",
        altDeg < -6 ? "mdi:weather-night" :
        altDeg < 0  ? "mdi:weather-sunset" :
        altDeg < 10 ? "mdi:weather-sunset-up" :
                      "mdi:white-balance-sunny");
      sico.style.color = mood.sun;
    }
  }

  _updateRangeLabels() {
    const a = this._currentActivity;
    const dur = this._tourDurationSec(a);
    const start = a?.startTime ? new Date(a.startTime) : new Date();
    const end = new Date(start.getTime() + dur * 1000);
    const fmt = (d) => `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
    const s = this._root.querySelector("#m3d-t-start");
    const e = this._root.querySelector("#m3d-t-end");
    if (s) s.textContent = fmt(start);
    if (e) e.textContent = fmt(end);
  }

  _togglePlay() {
    if (this._isPlaying) this._stopAnim();
    else this._startAnim();
  }

  // Total playback duration in milliseconds. Two modes:
  //   1. If the user set `animate_seconds` explicitly, that wins and the
  //      whole tour plays in that fixed duration regardless of length.
  //   2. Otherwise the tour plays at `playback_speed` × real-time. 60×
  //      means 1 h of riding becomes 1 min of playback. Clamped to
  //      [2 s, 10 min] so absurd configs do not produce unusable values.
  _playbackDurationMs() {
    const animSec = readCardSetting(this._config, "animate_seconds", undefined);
    if (animSec != null && animSec !== "" && Number.isFinite(Number(animSec))) {
      const fixed = Math.max(2, Number(animSec));
      return fixed * 1000;
    }
    const factor = Math.max(1, Number(readCardSetting(this._config, "playback_speed", undefined)) || 60);
    const tourSec = this._tourDurationSec(this._currentActivity);
    const ms = tourSec > 0 ? (tourSec * 1000) / factor : 25000;
    return Math.max(2000, Math.min(600000, ms));
  }

  _startAnim() {
    if (!this._currentTrack || !this._currentTrack.length) return;
    this._isPlaying = true;
    const icon = this._root.querySelector("#m3d-play-ico");
    if (icon) icon.setAttribute("icon", "mdi:pause");
    // moveend does not fire during continuous chase-cam playback, so we
    // also refresh shadows on a slow interval. 800 ms is fast enough to
    // catch sun-angle changes during a play-through, slow enough not to
    // hurt frame rate.
    if (this._shadowPlayInterval) clearInterval(this._shadowPlayInterval);
    this._shadowPlayInterval = setInterval(() => this._updateShadows(), 800);
    const slider = this._root.querySelector("#m3d-slider");
    const startIdx = Number(slider.value) || 0;
    const totalIdx = this._currentTrack.length - 1;
    const wrapAt = startIdx >= totalIdx ? 0 : startIdx;
    this._animStartIndex = wrapAt;
    this._animStartTs = performance.now();
    const fullDurMs = this._playbackDurationMs();
    // If the user pressed Play partway through, only the remaining
    // fraction should be replayed in proportion to that.
    const remainingFrac = totalIdx > 0 ? (totalIdx - wrapAt) / totalIdx : 1;
    const dur = Math.max(500, fullDurMs * remainingFrac);
    const step = (ts) => {
      if (!this._isPlaying) return;
      const elapsed = ts - this._animStartTs;
      const frac = Math.min(1, elapsed / dur);
      const idx = wrapAt + (totalIdx - wrapAt) * frac;
      this._applyIndex(idx);
      if (frac >= 1) { this._stopAnim(); return; }
      this._animRAF = requestAnimationFrame(step);
    };
    this._animRAF = requestAnimationFrame(step);
  }

  _stopAnim() {
    this._isPlaying = false;
    if (this._animRAF) cancelAnimationFrame(this._animRAF);
    this._animRAF = null;
    if (this._shadowPlayInterval) {
      clearInterval(this._shadowPlayInterval);
      this._shadowPlayInterval = null;
    }
    const icon = this._root.querySelector("#m3d-play-ico");
    if (icon) icon.setAttribute("icon", "mdi:play");
    // One final shadow refresh now that the bike has stopped
    this._updateShadows();
    // If a recording session was tied to this play-through, finish it
    if (this._isRecording) this._stopRecording();
  }

  // Toggle recording. The exported file is a WebM video of exactly the
  // canvas content during a single play-through, no audio. Renders in
  // the user's browser via MediaRecorder + canvas.captureStream(); HA
  // server is not involved.
  _toggleRecording() {
    if (this._isRecording) this._stopRecording();
    else this._startRecording();
  }

  _startRecording() {
    if (this._isRecording) return;
    if (!this._map) return;
    const sourceCanvas = this._map.getCanvas();
    if (!sourceCanvas) return;
    // Detect a usable captureStream path. We will capture from a 2D
    // mirror canvas anyway (see below for the reason), so we only need
    // 2D captureStream to be present.
    const probe = document.createElement("canvas");
    if (typeof probe.captureStream !== "function") {
      console.warn("[Bosch eBike 3D] canvas.captureStream not available");
      return;
    }

    // Pick the best mime type the browser actually supports.
    //
    // Important Safari caveat: WebKit reports isTypeSupported = true for
    // 'video/mp4;codecs=avc1.*' but the underlying encoder silently
    // produces empty containers when fed a canvas.captureStream() with
    // no audio track. This has been confirmed on Safari 17 and 18.
    // So in Safari we prefer WebM (which works since macOS 14.4 / iOS
    // 14.5) and only fall back to MP4 if no WebM variant is supported.
    //
    // In Chromium and Firefox there is no such defect, so MP4 stays
    // preferred there for better cross-app playback.
    const isSafari = (() => {
      const ua = navigator.userAgent;
      return /^((?!chrome|android|crios|fxios|edg).)*safari/i.test(ua);
    })();
    const mp4Mimes = [
      "video/mp4;codecs=avc1.42E01E",
      "video/mp4;codecs=avc1",
      "video/mp4",
    ];
    const webmMimes = [
      "video/webm;codecs=vp9",
      "video/webm;codecs=vp8",
      "video/webm",
    ];
    const mimeCandidates = isSafari
      ? [...webmMimes, ...mp4Mimes]
      : [...mp4Mimes, ...webmMimes];
    let mimeType = "";
    for (const m of mimeCandidates) {
      if (MediaRecorder.isTypeSupported(m)) { mimeType = m; break; }
    }
    console.log("[Bosch eBike 3D] recording mime selected:", mimeType || "(browser default)", "(safari =", isSafari + ")");

    // Each browser needs a different capture pipeline; testing two
    // rounds confirmed that one approach breaks the other.
    //
    //   Safari: captureStream() on a WebGL canvas yields zero frames
    //           (long-standing WebKit bug, drawing-buffer not exposed).
    //           Workaround: mirror the WebGL canvas into a 2D canvas
    //           inside MapLibre's 'render' event so drawImage runs on
    //           a freshly flushed backbuffer, then capture from the 2D
    //           mirror via captureStream(0) + track.requestFrame().
    //   Chromium / Firefox: drawImage(webglCanvas, ...) into a 2D
    //           mirror produces black pixels for these users
    //           (preserveDrawingBuffer is not reliably honoured in the
    //           drawImage path). But captureStream DIRECTLY on the
    //           WebGL canvas works fine here. So we just use that.
    //
    // Branch decision based on the existing isSafari flag.
    const w = sourceCanvas.width || sourceCanvas.clientWidth || 640;
    const h = sourceCanvas.height || sourceCanvas.clientHeight || 360;
    console.log("[Bosch eBike 3D] capture source size:", w, "x", h, "(safari =", isSafari + ")");

    let stream;
    if (isSafari) {
      // -------- Safari path: 2D mirror + render hook --------
      const mirror = document.createElement("canvas");
      mirror.width = w;
      mirror.height = h;
      // Off-screen, real pixel CSS size (a CSS-shrunken canvas can be
      // captured as 1x1 by the compositor).
      mirror.style.cssText =
        "position:fixed;left:-" + (w + 100) + "px;top:0;" +
        "width:" + w + "px;height:" + h + "px;pointer-events:none;opacity:0;";
      document.body.appendChild(mirror);
      this._recMirror = mirror;

      const mirrorCtx = mirror.getContext("2d");
      if (!mirrorCtx) {
        try { mirror.remove(); } catch (_) {}
        this._recMirror = null;
        console.warn("[Bosch eBike 3D] 2D context unavailable on mirror canvas");
        return;
      }

      try { stream = mirror.captureStream(0); }
      catch (e) {
        console.warn("[Bosch eBike 3D] mirror captureStream(0) failed, trying (30)", e);
        try { stream = mirror.captureStream(30); }
        catch (e2) {
          console.warn("[Bosch eBike 3D] mirror captureStream(30) also failed", e2);
          try { mirror.remove(); } catch (_) {}
          this._recMirror = null;
          return;
        }
      }
      const streamTrack = stream.getVideoTracks()[0];
      const supportsRequestFrame =
        streamTrack && typeof streamTrack.requestFrame === "function";

      this._recDiag = { renders: 0, draws: 0, drawErrors: 0, firstPixelLogged: false };
      const diag = this._recDiag;

      const renderHandler = () => {
        diag.renders++;
        if (!this._isRecording) return;
        try {
          mirrorCtx.drawImage(sourceCanvas, 0, 0, w, h);
          diag.draws++;
        } catch (e) {
          diag.drawErrors++;
          if (diag.drawErrors === 1) {
            console.warn("[Bosch eBike 3D] drawImage to mirror threw:", e);
          }
        }
        if (supportsRequestFrame) {
          try { streamTrack.requestFrame(); } catch (_) {}
        }
        if (!diag.firstPixelLogged && diag.draws >= 3) {
          diag.firstPixelLogged = true;
          try {
            const px = mirrorCtx.getImageData(Math.floor(w / 2), Math.floor(h / 2), 1, 1).data;
            console.log("[Bosch eBike 3D] mirror centre pixel after " + diag.draws +
              " draws: rgba(" + px[0] + "," + px[1] + "," + px[2] + "," + px[3] + ")");
          } catch (e) {
            console.warn("[Bosch eBike 3D] getImageData failed:", e);
          }
        }
      };
      this._map.on("render", renderHandler);
      this._renderHandlerForRec = renderHandler;

      // First frame so the encoder does not start blank
      try { this._map.triggerRepaint(); } catch (_) {}
      try { mirrorCtx.drawImage(sourceCanvas, 0, 0, w, h); } catch (_) {}
      console.log("[Bosch eBike 3D] capture path: Safari mirror + render-hook; requestFrame:", supportsRequestFrame);
    } else {
      // -------- Chromium / Firefox path: direct WebGL captureStream --------
      try {
        stream = sourceCanvas.captureStream(30);
      } catch (e) {
        console.warn("[Bosch eBike 3D] direct captureStream failed", e);
        return;
      }
      // Keep MapLibre repainting at ~60fps so the WebGL backbuffer is
      // refreshed even if no map movement is happening. (Normally the
      // chase cam moves the camera each frame so renders are constant;
      // this is just belt-and-braces.)
      const ensureRender = () => {
        if (!this._isRecording) return;
        try { this._map.triggerRepaint(); } catch (_) {}
        this._recCopyRAF = requestAnimationFrame(ensureRender);
      };
      this._recCopyRAF = requestAnimationFrame(ensureRender);
      console.log("[Bosch eBike 3D] capture path: direct WebGL captureStream");
    }

    this._recChunks = [];
    try {
      this._mediaRecorder = mimeType
        ? new MediaRecorder(stream, { mimeType, videoBitsPerSecond: 4_000_000 })
        : new MediaRecorder(stream);
    } catch (e) {
      console.warn("[Bosch eBike 3D] MediaRecorder construction failed", e);
      return;
    }

    this._mediaRecorder.ondataavailable = (ev) => {
      if (ev.data && ev.data.size > 0) this._recChunks.push(ev.data);
    };
    this._mediaRecorder.onstop = () => this._finalizeRecording(mimeType);
    this._mediaRecorder.onerror = (e) => {
      console.warn("[Bosch eBike 3D] MediaRecorder error", e);
    };

    // CRITICAL ordering: stop any in-flight playback FIRST, while
    // _isRecording is still false, so the bail-out at the end of
    // _stopAnim does not call _stopRecording on us mid-setup.
    this._stopAnim();

    // Reset slider and lay down the first frame so the mirror is not
    // black on the very first capture tick.
    const slider = this._root.querySelector("#m3d-slider");
    if (slider) slider.value = "0";
    this._applyIndex(0);
    try { mirrorCtx.drawImage(sourceCanvas, 0, 0, w, h); } catch (_) {}

    // Set state, then start the encoder and the per-frame copy loop.
    this._isRecording = true;
    this._updateRecordUI(true);

    try {
      this._mediaRecorder.start(1000);  // chunk every 1 s
    } catch (e) {
      console.warn("[Bosch eBike 3D] MediaRecorder start failed", e);
      this._mediaRecorder = null;
      this._isRecording = false;
      this._updateRecordUI(false);
      try { mirror.remove(); } catch (_) {}
      this._recMirror = null;
      return;
    }
    // The render-event hook is already attached; nothing more to start.

    // Now drive the chase-cam playback. When the animation ends,
    // _stopAnim's tail will see _isRecording === true and call
    // _stopRecording, finalising the file.
    this._startAnim();
  }

  _stopRecording() {
    if (!this._isRecording) return;
    this._isRecording = false;
    this._updateRecordUI(false);
    // Safari path: detach the MapLibre render-event copy hook
    if (this._renderHandlerForRec && this._map) {
      try { this._map.off("render", this._renderHandlerForRec); } catch (_) {}
    }
    this._renderHandlerForRec = null;
    // Chromium/Firefox path: cancel the ensure-render RAF
    if (this._recCopyRAF) {
      cancelAnimationFrame(this._recCopyRAF);
      this._recCopyRAF = null;
    }
    if (this._recDiag) {
      console.log("[Bosch eBike 3D] recording stopped; counters:", this._recDiag);
    }
    try {
      if (this._mediaRecorder && this._mediaRecorder.state !== "inactive") {
        this._mediaRecorder.stop();
      }
    } catch (e) {
      console.warn("[Bosch eBike 3D] MediaRecorder stop failed", e);
    }
  }

  _finalizeRecording(mimeType) {
    const chunks = this._recChunks || [];
    this._recChunks = null;
    this._mediaRecorder = null;
    // Remove the hidden mirror canvas now that the encoder is done.
    if (this._recMirror) {
      try { this._recMirror.remove(); } catch (_) {}
      this._recMirror = null;
    }

    const totalBytes = chunks.reduce((n, c) => n + (c.size || 0), 0);
    console.log("[Bosch eBike 3D] recording finalised:", {
      chunks: chunks.length,
      totalBytes,
      mimeType: mimeType || "(default)",
    });

    if (!chunks.length || totalBytes === 0) {
      console.warn("[Bosch eBike 3D] recording produced no data; nothing to download");
      this._showDownloadStatus(this._t("map3d_record_empty") || "Recording produced no data");
      return;
    }

    const blobType = mimeType || "video/webm";
    const blob = new Blob(chunks, { type: blobType });

    // File extension from the actual mime
    const ext = blobType.startsWith("video/mp4") ? "mp4"
              : blobType.startsWith("video/x-matroska") ? "mkv"
              : "webm";

    const a = this._currentActivity || {};
    const dateStr = a.startTime
      ? new Date(a.startTime).toISOString().slice(0, 19).replace(/[:T]/g, "-")
      : "tour";
    const safeTitle = (a.title || "ebike-tour")
      .toLowerCase().replace(/[^a-z0-9-]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 40);
    const filename = `${safeTitle || "ebike-tour"}-${dateStr}.${ext}`;

    const url = URL.createObjectURL(blob);

    // Try a programmatic auto-download first. Many desktop Chromium
    // builds honour this even without an explicit user gesture, so it
    // is a nice convenience when it works.
    try {
      const tmp = document.createElement("a");
      tmp.href = url;
      tmp.download = filename;
      tmp.style.display = "none";
      document.body.appendChild(tmp);
      tmp.click();
      document.body.removeChild(tmp);
    } catch (e) {
      console.warn("[Bosch eBike 3D] auto-download click was rejected", e);
    }

    // ALWAYS also show a visible chip with a real anchor element. If
    // the auto-click was blocked (Safari, newer Chrome under stricter
    // user-gesture policy), the user can click this manually as a real
    // user gesture and the browser will accept the download.
    this._showDownloadChip(url, filename, blob.size);
  }

  _showDownloadChip(url, filename, sizeBytes) {
    const overlay = this._root.querySelector(".map3d-overlay");
    if (!overlay) return;

    // Revoke any previous chip URL so we don't leak Blob URLs
    if (this._downloadChipEl) {
      const prevUrl = this._downloadChipEl.getAttribute("href");
      if (prevUrl && prevUrl.startsWith("blob:")) {
        try { URL.revokeObjectURL(prevUrl); } catch (_) { /* ignore */ }
      }
      try { this._downloadChipEl.remove(); } catch (_) { /* ignore */ }
      this._downloadChipEl = null;
    }
    if (this._downloadChipTimer) {
      clearTimeout(this._downloadChipTimer);
      this._downloadChipTimer = null;
    }

    const chip = document.createElement("a");
    chip.className = "map3d-chip map3d-download-chip";
    chip.href = url;
    chip.download = filename;
    chip.target = "_self";
    chip.rel = "noopener";
    const sizeMB = (sizeBytes / 1024 / 1024).toFixed(1);
    chip.innerHTML = `<ha-icon icon="mdi:download"></ha-icon><span>${this._t("map3d_record_download")} (${sizeMB} MB)</span>`;
    chip.title = filename;
    overlay.appendChild(chip);
    this._downloadChipEl = chip;

    // Auto-hide and revoke after 2 minutes to free memory
    this._downloadChipTimer = setTimeout(() => {
      try { URL.revokeObjectURL(url); } catch (_) { /* ignore */ }
      try { chip.remove(); } catch (_) { /* ignore */ }
      this._downloadChipEl = null;
      this._downloadChipTimer = null;
    }, 120000);
  }

  _showDownloadStatus(text) {
    const overlay = this._root.querySelector(".map3d-overlay");
    if (!overlay) return;
    const old = overlay.querySelector(".map3d-rec-status");
    if (old) old.remove();
    const chip = document.createElement("span");
    chip.className = "map3d-chip map3d-rec-status";
    chip.style.background = "rgba(229,57,53,.85)";
    chip.innerHTML = `<ha-icon icon="mdi:alert"></ha-icon><span>${text}</span>`;
    overlay.appendChild(chip);
    setTimeout(() => { try { chip.remove(); } catch (_) {} }, 6000);
  }

  _updateRecordUI(active) {
    const btn = this._root.querySelector("#m3d-rec");
    const ico = this._root.querySelector("#m3d-rec-ico");
    const badge = this._root.querySelector("#m3d-rec-badge");
    if (btn) btn.classList.toggle("active", active);
    if (ico) ico.setAttribute("icon", active ? "mdi:stop" : "mdi:record-circle-outline");
    if (btn) btn.title = active ? this._t("map3d_record_stop") : this._t("map3d_record_start");
    if (badge) badge.style.display = active ? "inline-flex" : "none";
  }

  _destroyMap() {
    // Invalidate any in-flight _initMap waiting on ensureMapLibre
    this._mapInitEpoch = (this._mapInitEpoch || 0) + 1;
    this._stopAnim();
    if (this._isRecording) this._stopRecording();
    if (this._renderHandlerForRec && this._map) {
      try { this._map.off("render", this._renderHandlerForRec); } catch (_) {}
      this._renderHandlerForRec = null;
    }
    if (this._recCopyRAF) { cancelAnimationFrame(this._recCopyRAF); this._recCopyRAF = null; }
    if (this._recMirror) { try { this._recMirror.remove(); } catch (_) {} this._recMirror = null; }
    if (this._downloadChipTimer) { clearTimeout(this._downloadChipTimer); this._downloadChipTimer = null; }
    if (this._downloadChipEl) {
      const u = this._downloadChipEl.getAttribute("href");
      if (u && u.startsWith("blob:")) { try { URL.revokeObjectURL(u); } catch (_) {} }
      try { this._downloadChipEl.remove(); } catch (_) {}
      this._downloadChipEl = null;
    }
    if (this._resizeObs) { try { this._resizeObs.disconnect(); } catch (_) {} this._resizeObs = null; }
    if (this._marker) { try { this._marker.remove(); } catch (_) {} this._marker = null; }
    if (this._map) { try { this._map.remove(); } catch (_) {} this._map = null; }
    // Reset displayed-position EMA so the next playback starts cleanly
    // on the new track's first sample instead of easing in from the old
    // track's last marker position.
    this._dispLat = null;
    this._dispLon = null;
  }
}

class BoschEBike3DMapCardEditor extends HTMLElement {
  constructor() {
    super();
    this._hass = null;
    this._config = {};
    this._built = false;
    // Debouncer-Timer pro Shared-Setting-Key, damit jeder Keystroke
    // im Number-/Text-Field nicht direkt einen WebSocket-Call auslöst.
    this._sharedSaveTimers = new Map();
  }
  setConfig(config) { this._config = { ...config }; if (this._built) this._sync(); }
  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    if (!this._built) this._build();
    if (first) {
      // Shared Settings nachladen, sobald hass da ist - dann Inputs
      // mit den richtigen Werten überschreiben.
      ensureCardSettingsLoaded(hass).then(() => this._sync()).catch(() => {});
    }
    if (!this._sharedSettingsHandler) {
      this._sharedSettingsHandler = () => this._sync();
      _cardSettingsBus.addEventListener("changed", this._sharedSettingsHandler);
    }
  }

  disconnectedCallback() {
    if (this._sharedSettingsHandler) {
      _cardSettingsBus.removeEventListener("changed", this._sharedSettingsHandler);
      this._sharedSettingsHandler = null;
    }
    for (const t of this._sharedSaveTimers.values()) clearTimeout(t);
    this._sharedSaveTimers.clear();
  }
  _t(key) {
    const lang = (this._hass && this._hass.language) ? this._hass.language.split("-")[0] : "en";
    const dict = (I18N && I18N[lang]) || I18N.en;
    return dict[key] != null ? dict[key] : I18N.en[key];
  }
  _emit() { this.dispatchEvent(new CustomEvent("config-changed", { detail: { config: this._config } })); }
  _build() {
    this.innerHTML = "";
    const wrap = document.createElement("div");
    wrap.style.cssText = "display:flex;flex-direction:column;gap:12px;padding:12px;";
    this.appendChild(wrap);

    const mkLabeled = (labelKey, hintKey, makeInput) => {
      const block = document.createElement("div");
      block.style.cssText = "display:flex;flex-direction:column;gap:4px;";
      const lbl = document.createElement("label");
      lbl.textContent = this._t(labelKey);
      lbl.style.fontWeight = "500";
      block.appendChild(lbl);
      const input = makeInput();
      block.appendChild(input);
      if (hintKey) {
        const h = document.createElement("small");
        h.textContent = this._t(hintKey);
        h.style.cssText = "color:var(--secondary-text-color);font-size:11px;";
        block.appendChild(h);
      }
      wrap.appendChild(block);
      return input;
    };

    // Shared-Keys schreiben ins HA-Storage statt in die Card-YAML,
    // damit Änderungen in der 3D-Card-UI auch in der 2D-Card-Chase-Cam
    // sichtbar werden. Non-Shared-Keys (title, height, account_id,
    // bike_id) gehen wie gehabt per config-changed-Event an Lovelace.
    const isShared = (k) => SHARED_SETTING_KEYS.includes(k);

    const mkText = (key, labelKey, hintKey, type) => {
      const i = mkLabeled(labelKey, hintKey, () => {
        const el = document.createElement("input");
        el.type = type || "text";
        el.style.cssText = "padding:8px;border-radius:4px;border:1px solid var(--divider-color);background:var(--card-background-color);color:var(--primary-text-color);";
        return el;
      });
      const initial = isShared(key)
        ? readCardSetting(this._config, key, "")
        : (this._config[key] != null ? this._config[key] : "");
      i.value = initial !== "" && initial != null ? String(initial) : "";
      i.addEventListener("input", () => {
        const v = i.value;
        if (isShared(key)) {
          // Debounced WS-Save. 400 ms ist konsistent mit dem Maintenance-
          // Editor; verhindert dass jeder Tastendruck ein WS-Roundtrip
          // ist und gleichzeitig dass die UI träge wirkt.
          if (this._sharedSaveTimers.has(key)) clearTimeout(this._sharedSaveTimers.get(key));
          this._sharedSaveTimers.set(key, setTimeout(() => {
            this._sharedSaveTimers.delete(key);
            const value = v === "" || v == null ? null
              : (type === "number" ? Number(v) : v);
            // Zusätzlich aus der Card-YAML entfernen, damit das Lovelace-
            // Editor nicht weiter die alten Werte als "Override" hält und
            // keine Drift zwischen Storage und YAML entsteht.
            if (this._config[key] != null) {
              delete this._config[key];
              this._emit();
            }
            saveCardSetting(this._hass, key, value);
          }, 400));
        } else {
          if (v === "" || v == null) delete this._config[key];
          else if (type === "number") this._config[key] = Number(v);
          else this._config[key] = v;
          this._emit();
        }
      });
      return i;
    };

    this._fields = {
      title: mkText("title", "map3d_editor_title", null, "text"),
      height: mkText("height", "map3d_editor_height", null, "number"),
      default_pitch: mkText("default_pitch", "map3d_editor_default_pitch", "map3d_editor_default_pitch_hint", "number"),
      chase_zoom: mkText("chase_zoom", "map3d_editor_chase_zoom", "map3d_editor_chase_zoom_hint", "number"),
      chase_lookahead: mkText("chase_lookahead", "map3d_editor_chase_lookahead", "map3d_editor_chase_lookahead_hint", "number"),
      smooth_window: mkText("smooth_window", "map3d_editor_smooth_window", "map3d_editor_smooth_window_hint", "number"),
      track_smooth_window: mkText("track_smooth_window", "map3d_editor_track_smooth", "map3d_editor_track_smooth_hint", "number"),
      playback_speed: mkText("playback_speed", "map3d_editor_playback_speed", "map3d_editor_playback_speed_hint", "number"),
      terrain_exaggeration: mkText("terrain_exaggeration", "map3d_editor_terrain_exag", "map3d_editor_terrain_exag_hint", "number"),
      satellite_tile_url: mkText("satellite_tile_url", "map3d_editor_sat_url", "map3d_editor_sat_url_hint", "text"),
      satellite_max_zoom: mkText("satellite_max_zoom", "map3d_editor_sat_maxzoom", "map3d_editor_sat_maxzoom_hint", "number"),
      north_up: mkText("north_up", "map3d_editor_north_up", "map3d_editor_north_up_hint", "number"),
      animate_seconds: mkText("animate_seconds", "map3d_editor_animate_seconds", "map3d_editor_animate_seconds_override_hint", "number"),
      account_id: mkText("account_id", "map3d_editor_account", null, "text"),
      bike_id: mkText("bike_id", "map3d_editor_bike", null, "text"),
    };

    // Overlay-visibility section: small heading followed by the six toggles
    const sectionHead = document.createElement("div");
    sectionHead.textContent = this._t("map3d_editor_overlay_section");
    sectionHead.style.cssText =
      "margin-top:14px;padding-top:10px;border-top:1px solid var(--divider-color);" +
      "color:var(--secondary-text-color);font-size:12px;line-height:1.4;";
    wrap.appendChild(sectionHead);

    Object.assign(this._fields, {
      show_date: mkText("show_date", "map3d_editor_show_date", null, "number"),
      show_time: mkText("show_time", "map3d_editor_show_time", null, "number"),
      show_sun: mkText("show_sun", "map3d_editor_show_sun", null, "number"),
      show_speed: mkText("show_speed", "map3d_editor_show_speed", null, "number"),
      show_distance: mkText("show_distance", "map3d_editor_show_distance", null, "number"),
      show_elevation: mkText("show_elevation", "map3d_editor_show_elevation", null, "number"),
      stats_as_chips: mkText("stats_as_chips", "map3d_editor_stats_as_chips", "map3d_editor_stats_as_chips_hint", "number"),
      show_weather: mkText("show_weather", "map3d_editor_show_weather", "map3d_editor_show_weather_hint", "number"),
    });

    // Auto-hide-UI (kiosk mode): a real checkbox rather than the 0/1
    // number-input pattern used above, so it is not registered in
    // this._fields - _sync()'s generic loop only ever assigns .value,
    // which is a documented no-op on a checkbox and would not reflect
    // .checked anyway. Not a shared setting: it is a 3D-card-only display
    // preference, not a chase-cam rendering parameter used by the 2D card too.
    const autoHideWrap = document.createElement("label");
    autoHideWrap.style.cssText = "display:flex;align-items:center;gap:8px;font-size:13px;cursor:pointer;margin-top:8px;";
    const autoHideCb = document.createElement("input");
    autoHideCb.type = "checkbox";
    autoHideCb.checked = this._config.auto_hide_ui === 1 || this._config.auto_hide_ui === "1" || this._config.auto_hide_ui === true;
    autoHideCb.addEventListener("change", () => {
      if (autoHideCb.checked) this._config.auto_hide_ui = 1;
      else delete this._config.auto_hide_ui;
      this._emit();
    });
    autoHideWrap.appendChild(autoHideCb);
    const autoHideLbl = document.createElement("span");
    autoHideLbl.textContent = this._t("map3d_editor_auto_hide_ui");
    autoHideWrap.appendChild(autoHideLbl);
    wrap.appendChild(autoHideWrap);

    const autoHideHint = document.createElement("small");
    autoHideHint.textContent = this._t("map3d_editor_auto_hide_ui_hint");
    autoHideHint.style.cssText = "color:var(--secondary-text-color);font-size:11px;";
    wrap.appendChild(autoHideHint);

    this._built = true;
  }
  _sync() {
    if (!this._fields) return;
    for (const [k, el] of Object.entries(this._fields)) {
      // Fokussierte Eingaben nicht überschreiben - der User tippt
      // gerade und der Bus-Echo würde den Cursor wegspringen lassen.
      if (document.activeElement === el) continue;
      const v = SHARED_SETTING_KEYS.includes(k)
        ? readCardSetting(this._config, k, "")
        : (this._config[k] != null ? this._config[k] : "");
      el.value = v !== "" && v != null ? String(v) : "";
    }
  }
}

// ===========================================================================
// Route-Planner-Card — Wegpunkte klicken, Routing via Backend-Proxy
// (bosch_ebike/plan_route → BRouter), Verbrauchs-Schätzung + Akku-Check,
// Höhenprofil-SVG und GPX-Export. Editor + Registrierung folgen in Task 5.
// ===========================================================================
const RP_MAX_WAYPOINTS = 30; // muss zum Backend-Limit in brouter.py passen
const RP_PROFILES = ["trekking", "fastbike", "mtb", "shortest"];
// POI-Kategorien für den Routenplaner: wie die Map-Card plus Gastronomie
// (muss zur Whitelist POI_CATEGORY_SELECTORS im Backend passen).
const RP_POI_CATEGORIES = ["charging", "bicycle", "water", "toilets", "food"];
const RP_POI_RADIUS_M = 500; // POIs max. 500 m neben der Route

// Sprachunabhängige Erkennung der Reichweiten-Sensoren. Entity-IDs werden
// aus dem ÜBERSETZTEN Namen erzeugt (deutsche Instanz →
// sensor.…_geschatzte_reichweite_aktuell), ein englischer Suffix-Match
// reicht daher nicht. Primär über die Frontend-Entity-Registry
// (platform + translation_key), Fallback: englisches ID-Suffix.
function boschRangeEntityIds(hass, translationKey) {
  const ids = [];
  const reg = hass && hass.entities ? hass.entities : null;
  if (reg) {
    for (const id in reg) {
      const e = reg[id];
      if (e && e.platform === "ha_bosch_ebike" && e.translation_key === translationKey) {
        ids.push(id);
      }
    }
  }
  if (!ids.length && hass && hass.states) {
    for (const id in hass.states) {
      if (id.startsWith("sensor.") && id.endsWith("_" + translationKey)) ids.push(id);
    }
  }
  return ids;
}

class BoschEBikeRoutePlannerCard extends HTMLElement {
  constructor() {
    super();
    this._hass = null;
    this._config = {};
    this._map = null;
    this._baseLayer = null;
    this._routeGroup = null;
    this._waypoints = [];          // L.marker[], in Klick-Reihenfolge
    this._profile = "trekking";
    this._routeSeq = 0;            // verwirft veraltete plan_route-Antworten
    this._debounceTimer = null;
    this._lastRouteCoords = null;  // [[lon, lat, ele], …] der letzten Route
    this._lastRouteProps = null;   // properties der letzten Route (für Re-Render)
    this._lastRangeSig = "";       // zuletzt gerenderte Verbrauchs-/SoC-Daten
    this._fitPending = false;      // fitBounds einmalig nach Wegpunkt-Änderung
    this._ready = false;           // Boot komplett (Leaflet geladen, Map steht)
    this._domBuilt = false;
    this._booting = false;
    this._bootErrorShown = false; // Boot-Fehler nur einmal loggen/anzeigen
    // POI-Overlay entlang der Route (eigener localStorage-Key, unabhängig
    // vom 📍-Toggle der Map-Card)
    this._poiEnabled = (typeof localStorage !== "undefined" && localStorage.getItem("eb-rp-poi-enabled") === "1");
    this._poiGroup = null;         // L.layerGroup mit den POI-Markern
    this._poiCache = new Map();    // bbox+Kategorien → rohe Overpass-Elemente
    this._poiSeq = 0;              // verwirft veraltete get_pois-Antworten
    // Gespeicherte Routen (HA-Storage): id + Name der aktuell geladenen
    // Route — einfache Felder, überleben Map-Rebuilds (das DOM bleibt
    // bei disconnect/reconnect stehen, nur die Leaflet-Map wird neu gebaut).
    this._loadedRouteId = null;
    this._loadedRouteName = null;
  }

  setConfig(config) {
    this._config = { height: config.height || 480, ...config };
    if (this._domBuilt) this._applyTitle();
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._ready) {
      // Erst-Boot bzw. neuer Versuch nach fehlgeschlagenem Boot
      // (z. B. Leaflet-CDN kurz nicht erreichbar).
      if (!this._booting) this._boot();
      return;
    }
    // Live-SoC: ändert sich der Akkustand (oder Ø-Verbrauch/Kapazität),
    // während eine Route angezeigt wird, Akku-Zeile + Verbrauch auffrischen.
    if (this._lastRouteProps) {
      const r = this._rangeData();
      const sig = r ? `${r.whPerKm}|${r.capacityWh}|${r.soc}` : "";
      if (sig !== this._lastRangeSig) this._renderStats(this._lastRouteProps);
    }
  }

  getCardSize() {
    return Math.ceil((parseInt(this._config.height, 10) || 480) / 50) + 3;
  }

  static getConfigElement() {
    return document.createElement("bosch-ebike-routeplanner-card-editor");
  }

  static getStubConfig() {
    return { height: 480 };
  }

  _t(key, ...args) {
    return ebT(this._hass, key, ...args);
  }

  async _boot() {
    if (this._booting || this._ready) return;
    this._booting = true;
    try {
      if (!this._domBuilt) {
        this._buildDOM();
        this._domBuilt = true;
      }
      this._applyTitle();
      await ensureLeaflet();
      this._createMap();
      // Erst nach erfolgreichem Map-Aufbau "fertig" — schlägt der Boot
      // fehl, bleibt _ready false und die nächste hass-Zuweisung (bzw.
      // connectedCallback) startet einen neuen Versuch.
      this._ready = !!this._map;
      if (this._ready) {
        this._setStatus(null);
        this._bootErrorShown = false;
      }
    } catch (err) {
      // Jede hass-Zuweisung stößt bei !_ready einen neuen Boot-Versuch an —
      // ohne Drossel würde ein anhaltender CDN-Ausfall die Konsole fluten.
      if (!this._bootErrorShown) {
        this._bootErrorShown = true;
        console.error("[Bosch eBike Routeplanner] boot error", err);
        this._setStatus(this._t("msg_error_prefix") + describeBootError(this._hass, err), "");
      }
    } finally {
      this._booting = false;
    }
  }

  connectedCallback() {
    if (!this._ready) {
      // Boot lief noch nicht oder ist fehlgeschlagen — neuer Versuch,
      // sobald hass schon da ist (sonst stößt set hass den Boot an).
      if (this._hass && !this._booting) this._boot();
      return;
    }
    if (!this._map) {
      this._rebuildMap();
    } else {
      setTimeout(() => {
        try { this._map?.invalidateSize({ animate: false, pan: false }); } catch (_) {}
      }, 50);
    }
  }

  disconnectedCallback() {
    if (this._debounceTimer) {
      clearTimeout(this._debounceTimer);
      this._debounceTimer = null;
    }
    this._routeSeq += 1; // laufende plan_route-Antwort verwerfen
    this._poiSeq += 1;   // laufende get_pois-Antwort verwerfen
    // Leaflet-Map sauber abbauen (Listener/Memory-Leak bei Lovelace-
    // Edit-Zyklen) — Muster wie _destroyMap() der Map-/3D-Card.
    if (this._map) {
      try { this._map.remove(); } catch (_) {}
      this._map = null;
      this._baseLayer = null;
      this._routeGroup = null;
      this._poiGroup = null;
    }
    if (this._rpResizeObserver) {
      try { this._rpResizeObserver.disconnect(); } catch (_) {}
      this._rpResizeObserver = null;
    }
  }

  // Nach disconnect/reconnect (z. B. Lovelace-Editor): Map neu aufbauen,
  // Wegpunkt-Marker wieder anhängen (Marker überleben map.remove() samt
  // ihrer Listener) und bei ≥ 2 Punkten die Route neu berechnen — das
  // deckt auch eine beim Disconnect verloren gegangene, noch ausstehende
  // Neuberechnung ab. Stats/Höhenprofil bleiben stehen (DOM bleibt).
  _rebuildMap() {
    this._createMap();
    if (!this._map) return;
    for (const m of this._waypoints) {
      try { m.addTo(this._map); } catch (_) {}
    }
    // Gecachte Route nur neu ZEICHNEN — kein erneuter BRouter-Request bei
    // jedem View-Wechsel (Fair-Use gegenüber brouter.de). Neu gerechnet
    // wird nur, wenn noch keine Route vorliegt (z. B. Recalc beim
    // Disconnect verloren gegangen).
    if (this._lastRouteCoords && this._lastRouteCoords.length >= 2) {
      const Leaflet = window.L;
      const latlngs = this._lastRouteCoords.map((c) => [c[1], c[0]]);
      try {
        this._routeGroup.clearLayers();
        Leaflet.polyline(latlngs, {
          color: "#0b84c7", weight: 5, opacity: 0.9, lineCap: "round",
        }).addTo(this._routeGroup);
        this._map.fitBounds(Leaflet.latLngBounds(latlngs), { padding: [40, 40], animate: false });
      } catch (_) {}
      // POI-Marker aus dem In-Memory-Cache neu zeichnen (kein Re-Query)
      if (this._poiEnabled) this._loadAndRenderPois();
    } else if (this._waypoints.length >= 2) {
      this._fitPending = true;
      this._scheduleRoute();
    }
  }

  _applyTitle() {
    const head = this.querySelector(".rp-head span");
    if (head) head.textContent = this._config.title || this._t("rp_default_title");
  }

  _buildDOM() {
    // parseInt: height kann aus YAML als String kommen — niemals
    // un-koerziert in den <style>-Text interpolieren.
    const h = parseInt(this._config.height, 10) || 480;
    this.innerHTML = "";
    const card = document.createElement("ha-card");
    this.appendChild(card);
    const style = document.createElement("style");
    style.textContent = LEAFLET_INLINE_CSS + `
      .rp-head {
        display:flex; align-items:center; gap:8px; padding:12px 16px;
        background:var(--primary-color,#03a9f4); color:#fff; font-size:16px; font-weight:500;
      }
      .rp-toolbar {
        display:flex; flex-wrap:wrap; align-items:center; gap:8px; padding:8px 12px;
        background:var(--secondary-background-color,#f5f5f5);
        border-bottom:1px solid var(--divider-color,#e0e0e0);
      }
      .rp-toolbar select {
        padding:5px 8px; border:1px solid var(--divider-color,#ccc);
        border-radius:6px; font-size:13px;
        background:var(--card-background-color,#fff); color:var(--primary-text-color,#333);
      }
      .rp-toolbar button {
        padding:6px 12px; flex-shrink:0;
        background:var(--primary-color,#03a9f4); color:#fff;
        border:none; border-radius:8px; cursor:pointer; font-size:13px;
      }
      .rp-toolbar button:disabled { opacity:.35; cursor:not-allowed; }
      .rp-toolbar button.eb-active {
        background:rgba(11,132,199,.95);
        outline:2px solid rgba(255,255,255,.6);
      }
      .rp-toolbar button.eb-loading {
        opacity:.6;
        animation:rp-poi-pulse 1.2s ease-in-out infinite;
      }
      @keyframes rp-poi-pulse {
        0%,100% { opacity:.55; }
        50%     { opacity:.95; }
      }
      .rp-lbl { font-size:12px; color:var(--secondary-text-color,#666); }
      .rp-namerow input {
        flex:1; min-width:120px; padding:5px 8px;
        border:1px solid var(--divider-color,#ccc); border-radius:6px; font-size:13px;
        background:var(--card-background-color,#fff); color:var(--primary-text-color,#333);
      }
      .rp-routes {
        padding:4px 12px 8px; max-height:220px; overflow-y:auto;
        background:var(--secondary-background-color,#f5f5f5);
        border-bottom:1px solid var(--divider-color,#e0e0e0);
      }
      .rp-route-row {
        display:flex; align-items:center; gap:8px; padding:6px 4px;
        border-bottom:1px solid var(--divider-color,#e0e0e0);
      }
      .rp-route-row:last-child { border-bottom:none; }
      .rp-route-info { flex:1; min-width:0; cursor:pointer; }
      .rp-route-name {
        font-size:13px; font-weight:500; color:var(--primary-text-color,#333);
        overflow:hidden; text-overflow:ellipsis; white-space:nowrap;
      }
      .rp-route-meta { font-size:11px; color:var(--secondary-text-color,#757575); }
      .rp-route-del {
        padding:4px 9px; flex-shrink:0; cursor:pointer; font-size:12px;
        background:none; border:1px solid var(--divider-color,#ccc);
        border-radius:6px; color:var(--secondary-text-color,#666);
      }
      .rp-route-del.confirm { background:#c62828; border-color:#c62828; color:#fff; }
      .rp-routes-empty { font-size:12px; color:var(--secondary-text-color,#757575); padding:6px 4px; }
      .rp-hint {
        padding:6px 12px; font-size:12px; color:var(--secondary-text-color,#666);
        border-bottom:1px solid var(--divider-color,#e0e0e0);
      }
      .rp-map-wrap { position:relative; }
      .rp-map { width:100% !important; height:${h}px !important; min-height:${h}px; z-index:0; position:relative; }
      .rp-status {
        position:absolute; left:50%; top:12px; transform:translateX(-50%); z-index:1100;
        max-width:90%; padding:6px 12px; border-radius:8px; text-align:center;
        background:rgba(33,33,33,.78); backdrop-filter:blur(4px); color:#fff;
        font-size:13px; pointer-events:none;
      }
      .rp-status small { display:block; font-size:11px; opacity:.8; margin-top:2px; }
      .rp-wp {
        width:18px; height:18px; border-radius:50%; box-sizing:border-box;
        border:3px solid #fff; box-shadow:0 1px 4px rgba(0,0,0,.4);
      }
      .eb-poi-marker {
        background:rgba(255,255,255,.95);
        border-radius:50%;
        width:18px !important; height:18px !important;
        display:flex; align-items:center; justify-content:center;
        font-size:12px; line-height:1;
        box-shadow:0 1px 3px rgba(0,0,0,.3);
        cursor:pointer;
      }
      .eb-poi-marker.eb-poi-charging   { border:1.5px solid #2e7d32; }
      .eb-poi-marker.eb-poi-bicycle    { border:1.5px solid #c62828; }
      .eb-poi-marker.eb-poi-water      { border:1.5px solid #1565c0; }
      .eb-poi-marker.eb-poi-toilet     { border:1.5px solid #6a1b9a; }
      .eb-poi-marker.eb-poi-food       { border:1.5px solid #e65100; }
      .eb-poi-marker.eb-poi-cafe       { border:1.5px solid #5d4037; }
      .eb-poi-marker.eb-poi-biergarten { border:1.5px solid #f9a825; }
      .eb-poi-popup { font-family:inherit; max-width:240px; font-size:13px; }
      .eb-poi-popup .eb-poi-title { font-weight:600; margin-bottom:4px; }
      .eb-poi-popup .eb-poi-cat { font-size:11px; color:#666; margin-bottom:6px; }
      .eb-poi-popup .eb-poi-link {
        display:inline-block; padding:3px 8px;
        background:#0b84c7; color:#fff; border-radius:6px;
        text-decoration:none; font-size:11px; font-weight:500;
      }
      .rp-stats { display:grid; grid-template-columns:repeat(auto-fit,minmax(90px,1fr)); gap:4px; padding:10px 16px 4px; }
      .rp-stat { text-align:center; }
      .rp-val { font-size:18px; font-weight:700; color:var(--primary-text-color,#212121); }
      .rp-stat .rp-lbl { font-size:11px; color:var(--secondary-text-color,#757575); }
      .rp-batt { padding:4px 16px 8px; }
      .rp-batt-line { font-size:14px; color:var(--primary-text-color,#333); margin-bottom:4px; }
      .rp-note { font-size:11px; color:var(--secondary-text-color,#757575); line-height:1.35; }
      .rp-elev { padding:0 16px 12px; }
      .rp-elev svg { width:100%; height:80px; display:block; }
      .rp-elev-range { font-size:11px; color:var(--secondary-text-color,#777); margin-top:2px; }
    `;
    card.appendChild(style);

    const t = (k, ...a) => ebT(this._hass, k, ...a);
    const wrap = document.createElement("div");
    wrap.innerHTML = `
      <div class="rp-head">
        <svg viewBox="0 0 24 24" width="22" height="22"><path fill="white" d="M6.5,8.11C5.61,8.11 4.89,7.39 4.89,6.5A1.61,1.61 0 0,1 6.5,4.89C7.39,4.89 8.11,5.61 8.11,6.5A1.61,1.61 0 0,1 6.5,8.11M6.5,2C4,2 2,4 2,6.5C2,9.87 6.5,14.86 6.5,14.86C6.5,14.86 11,9.87 11,6.5C11,4 9,2 6.5,2M17.5,8.11A1.61,1.61 0 0,1 15.89,6.5C15.89,5.61 16.61,4.89 17.5,4.89C18.39,4.89 19.11,5.61 19.11,6.5A1.61,1.61 0 0,1 17.5,8.11M17.5,2C15,2 13,4 13,6.5C13,9.87 17.5,14.86 17.5,14.86C17.5,14.86 22,9.87 22,6.5C22,4 20,2 17.5,2M17.5,16C16.23,16 15.1,16.8 14.68,18H9.32C8.77,16.44 7.05,15.62 5.5,16.17C3.93,16.72 3.11,18.44 3.66,20C4.22,21.56 5.93,22.38 7.5,21.83C8.35,21.53 9,20.85 9.32,20H14.68C15.23,21.56 16.95,22.38 18.5,21.83C20.07,21.28 20.89,19.56 20.34,18C19.92,16.8 18.78,16 17.5,16M17.5,20.5A1.5,1.5 0 0,1 16,19A1.5,1.5 0 0,1 17.5,17.5A1.5,1.5 0 0,1 19,19A1.5,1.5 0 0,1 17.5,20.5Z"/></svg>
        <span>${t("rp_default_title")}</span>
      </div>
      <div class="rp-toolbar">
        <span class="rp-lbl">${t("rp_profile_label")}</span>
        <select id="rp-profile">
          <option value="trekking" selected>${t("rp_profile_trekking")}</option>
          <option value="fastbike">${t("rp_profile_fastbike")}</option>
          <option value="mtb">${t("rp_profile_mtb")}</option>
          <option value="shortest">${t("rp_profile_shortest")}</option>
        </select>
        <button id="rp-reset" type="button">${t("rp_reset")}</button>
        <button id="rp-gpx" type="button" disabled>${t("rp_export_gpx")}</button>
        <button id="rp-poi" type="button" class="${this._poiEnabled ? "eb-active" : ""}" title="${t("rp_poi_btn")}" aria-label="${t("rp_poi_btn")}">📍</button>
        <button id="rp-save" type="button" disabled title="${t("rp_save_btn")}" aria-label="${t("rp_save_btn")}">💾</button>
        <button id="rp-routes" type="button" title="${t("rp_routes_btn")}" aria-label="${t("rp_routes_btn")}">📁</button>
      </div>
      <div class="rp-toolbar rp-namerow" id="rp-name-row" style="display:none;">
        <input type="text" id="rp-name-in" maxlength="60" placeholder="${t("rp_name_placeholder")}">
        <button id="rp-name-ok" type="button">OK</button>
        <button id="rp-name-cancel" type="button">${t("rp_save_cancel")}</button>
      </div>
      <div id="rp-routes-panel" class="rp-routes" style="display:none;"></div>
      <div class="rp-hint" id="rp-hint">${t("rp_hint_click")}</div>
      <div class="rp-map-wrap">
        <div id="rp-map" class="rp-map"></div>
        <div class="rp-status" id="rp-status" style="display:none;">
          <span id="rp-status-main"></span><small id="rp-status-sub" style="display:none;"></small>
        </div>
      </div>
      <div class="rp-stats" id="rp-stats" style="display:none;">
        <div class="rp-stat"><div class="rp-val" id="rp-dist">–</div><div class="rp-lbl">${t("rp_stat_distance")}</div></div>
        <div class="rp-stat"><div class="rp-val" id="rp-asc">–</div><div class="rp-lbl">${t("rp_stat_ascent")}</div></div>
        <div class="rp-stat"><div class="rp-val" id="rp-desc">–</div><div class="rp-lbl">${t("rp_stat_descent")}</div></div>
        <div class="rp-stat"><div class="rp-val" id="rp-time">–</div><div class="rp-lbl">${t("rp_stat_time")}</div></div>
        <div class="rp-stat" id="rp-stat-energy" style="display:none;"><div class="rp-val" id="rp-energy">–</div><div class="rp-lbl">${t("rp_stat_energy")}</div></div>
      </div>
      <div class="rp-batt" id="rp-batt" style="display:none;">
        <div class="rp-batt-line" id="rp-batt-line" style="display:none;"></div>
        <div class="rp-note" id="rp-note-est"></div>
        <div class="rp-note" id="rp-note-hilly" style="display:none;"></div>
      </div>
      <div class="rp-elev" id="rp-elev" style="display:none;">
        <svg id="rp-elev-svg" viewBox="0 0 600 80" preserveAspectRatio="none" xmlns="http://www.w3.org/2000/svg"></svg>
        <div class="rp-elev-range" id="rp-elev-range"></div>
      </div>
    `;
    while (wrap.firstChild) card.appendChild(wrap.firstChild);

    this.querySelector("#rp-profile").addEventListener("change", (e) => {
      const v = e.target.value;
      this._profile = RP_PROFILES.includes(v) ? v : "trekking";
      this._scheduleRoute();
    });
    this.querySelector("#rp-reset").addEventListener("click", () => this._reset());
    this.querySelector("#rp-gpx").addEventListener("click", () => this._exportGpx());
    this.querySelector("#rp-poi").addEventListener("click", () => this._togglePoi());
    this.querySelector("#rp-save").addEventListener("click", () => this._toggleSaveRow());
    this.querySelector("#rp-routes").addEventListener("click", () => this._toggleRoutesPanel());
    this.querySelector("#rp-name-ok").addEventListener("click", () => this._saveRoute());
    this.querySelector("#rp-name-cancel").addEventListener("click", () => this._toggleSaveRow(false));
    this.querySelector("#rp-name-in").addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        this._saveRoute();
      } else if (e.key === "Escape") {
        this._toggleSaveRow(false);
      }
    });
  }

  _createMap() {
    const Leaflet = window.L;
    const mapEl = this.querySelector("#rp-map");
    if (!Leaflet || !mapEl) {
      this._setStatus(this._t("err_leaflet_load"), "");
      return;
    }
    const cfg = this._hass && this._hass.config;
    const lat = Number(cfg && cfg.latitude);
    const lon = Number(cfg && cfg.longitude);
    this._map = Leaflet.map(mapEl, {
      zoomControl: true,
      attributionControl: false,
      preferCanvas: true,
    }).setView([Number.isFinite(lat) ? lat : 48.7, Number.isFinite(lon) ? lon : 12.4], 13);
    const def = MAP_STYLES.osm;
    this._baseLayer = Leaflet.tileLayer(def.url, def.options).addTo(this._map);
    this._routeGroup = Leaflet.layerGroup().addTo(this._map);
    this._poiGroup = Leaflet.layerGroup().addTo(this._map);
    this._map.on("click", (e) => this._onMapClick(e));

    // Leaflet friert die beim Erstellen gemessene Container-Größe ein.
    // Wird die Karte initialisiert, bevor das HA-Layout fertig ist
    // (Panel-Ansicht, Masonry, langsame Browser), rendern Kacheln nur in
    // einer Teilfläche. Gegenmittel wie bei der Heatmap-Card:
    // (a) ResizeObserver fängt jede spätere Größenänderung ab,
    // (b) eine kurze invalidateSize-Staffel deckt das Einschwingen
    //     direkt nach dem Erstellen ab.
    if (!this._rpResizeObserver && typeof ResizeObserver !== "undefined") {
      this._rpResizeObserver = new ResizeObserver(() => {
        try { this._map?.invalidateSize({ animate: false, pan: false }); } catch (_) {}
      });
      this._rpResizeObserver.observe(mapEl);
    }
    const settle = () => {
      try { this._map?.invalidateSize({ animate: false, pan: false }); } catch (_) {}
    };
    requestAnimationFrame(() => requestAnimationFrame(settle));
    setTimeout(settle, 150);
    setTimeout(settle, 400);
    setTimeout(settle, 700);
  }

  // -------------------------------------------------------------------------
  // Wegpunkte
  // -------------------------------------------------------------------------

  _wpIcon(color) {
    return window.L.divIcon({
      className: "",
      html: `<div class="rp-wp" style="background:${color}"></div>`,
      iconSize: [18, 18],
      iconAnchor: [9, 9],
    });
  }

  // Gemeinsamer Marker-Bau für Karten-Klick UND das Laden gespeicherter
  // Routen — Farben, Drag- und Klick-Handler bleiben so garantiert identisch.
  _addWaypoint(latlng) {
    const Leaflet = window.L;
    if (!Leaflet || !this._map || this._waypoints.length >= RP_MAX_WAYPOINTS) return null;
    const marker = Leaflet.marker(latlng, {
      draggable: true,
      icon: this._wpIcon("#2196F3"),
    });
    marker.on("click", () => this._removeWaypoint(marker));
    marker.on("dragend", () => {
      this._fitPending = true;
      this._scheduleRoute();
    });
    marker.addTo(this._map);
    this._waypoints.push(marker);
    return marker;
  }

  _onMapClick(e) {
    if (!this._addWaypoint(e.latlng)) return;
    this._refreshWaypointStyles();
    this._fitPending = true;
    this._scheduleRoute();
  }

  _removeWaypoint(marker) {
    const idx = this._waypoints.indexOf(marker);
    if (idx === -1) return;
    this._waypoints.splice(idx, 1);
    try { this._map.removeLayer(marker); } catch (_) {}
    this._refreshWaypointStyles();
    this._fitPending = true;
    this._scheduleRoute();
  }

  // Start grün, Ziel rot, Zwischenpunkte blau (Farben wie Start/Ziel der Map-Card).
  _refreshWaypointStyles() {
    const n = this._waypoints.length;
    this._waypoints.forEach((m, i) => {
      const color = i === 0 ? "#4CAF50" : i === n - 1 ? "#f44336" : "#2196F3";
      m.setIcon(this._wpIcon(color));
    });
  }

  // Wegpunkte + Route entfernen — gemeinsamer Kern von _reset (Toolbar-
  // Button) und _loadSavedRoute (Karte leeren, bevor die geladene Route
  // ihre eigenen Marker setzt).
  _clearWaypoints() {
    this._routeSeq += 1; // laufende Anfrage verwerfen
    if (this._debounceTimer) {
      clearTimeout(this._debounceTimer);
      this._debounceTimer = null;
    }
    for (const m of this._waypoints) {
      try { this._map.removeLayer(m); } catch (_) {}
    }
    this._waypoints = [];
    this._clearRoute();
    this._setStatus(null);
  }

  _reset() {
    this._clearWaypoints();
    this._loadedRouteId = null;
    this._loadedRouteName = null;
    this._toggleSaveRow(false);
    const hint = this.querySelector("#rp-hint");
    if (hint) hint.style.display = "";
  }

  // -------------------------------------------------------------------------
  // Routing
  // -------------------------------------------------------------------------

  _scheduleRoute() {
    if (this._debounceTimer) clearTimeout(this._debounceTimer);
    this._debounceTimer = setTimeout(() => {
      this._debounceTimer = null;
      this._calcRoute();
    }, 600);
  }

  async _calcRoute() {
    if (this._waypoints.length < 2) {
      this._routeSeq += 1;
      this._clearRoute();
      this._setStatus(null);
      return;
    }
    const seq = ++this._routeSeq;
    this._setStatus(this._t("rp_routing"));
    let res;
    try {
      res = await this._hass.callWS({
        type: "bosch_ebike/plan_route",
        lonlats: this._waypoints.map((m) => { const ll = m.getLatLng(); return [ll.lng, ll.lat]; }),
        profile: this._profile,
        brouter_url: this._config.brouter_url || null,
      });
    } catch (err) {
      if (seq !== this._routeSeq) return;
      const main = err && err.code === "server_unreachable"
        ? this._t("rp_err_server")
        : this._t("rp_err_no_route");
      this._setStatus(main, (err && err.message) || "");
      return;
    }
    if (seq !== this._routeSeq) return;
    this._setStatus(null);
    this._renderRoute(res && res.geojson);
  }

  _clearRoute() {
    if (this._routeGroup) this._routeGroup.clearLayers();
    this._poiSeq += 1; // laufende get_pois-Antwort verwerfen
    if (this._poiGroup) {
      try { this._poiGroup.clearLayers(); } catch (_) {}
    }
    this._lastRouteCoords = null;
    this._lastRouteProps = null;
    const gpxBtn = this.querySelector("#rp-gpx");
    if (gpxBtn) gpxBtn.disabled = true;
    const saveBtn = this.querySelector("#rp-save");
    if (saveBtn) saveBtn.disabled = true;
    for (const id of ["rp-stats", "rp-batt", "rp-elev"]) {
      const el = this.querySelector(`#${id}`);
      if (el) el.style.display = "none";
    }
  }

  _renderRoute(geojson) {
    const Leaflet = window.L;
    const feat = geojson && Array.isArray(geojson.features) ? geojson.features[0] : null;
    const coords = feat && feat.geometry && Array.isArray(feat.geometry.coordinates)
      ? feat.geometry.coordinates : null;
    if (!Leaflet || !this._map || !coords || coords.length < 2) {
      this._clearRoute();
      this._setStatus(this._t("rp_err_no_route"), "");
      return;
    }

    this._lastRouteCoords = coords;
    this._lastRouteProps = feat.properties || {};
    this._routeGroup.clearLayers();
    const latlngs = coords.map((c) => [c[1], c[0]]);
    Leaflet.polyline(latlngs, {
      color: "#0b84c7", weight: 5, opacity: 0.9, lineCap: "round",
    }).addTo(this._routeGroup);

    if (this._fitPending) {
      this._fitPending = false;
      try {
        this._map.fitBounds(Leaflet.latLngBounds(latlngs), { padding: [40, 40], animate: false });
      } catch (_) {}
    }

    const hint = this.querySelector("#rp-hint");
    if (hint) hint.style.display = "none";
    const gpxBtn = this.querySelector("#rp-gpx");
    if (gpxBtn) gpxBtn.disabled = false;
    const saveBtn = this.querySelector("#rp-save");
    if (saveBtn) saveBtn.disabled = false;

    this._renderStats(this._lastRouteProps);
    this._renderElevation(coords);
    if (this._poiEnabled) this._loadAndRenderPois();
  }

  // -------------------------------------------------------------------------
  // Stats, Verbrauch + Akku-Check
  // -------------------------------------------------------------------------

  _renderStats(props) {
    const km = (parseFloat(props["track-length"]) || 0) / 1000;
    const ascent = Math.max(0, Math.round(parseFloat(props["filtered ascend"]) || 0));
    const plain = parseFloat(props["plain-ascend"]) || 0;
    const descent = Math.max(0, Math.round((parseFloat(props["filtered ascend"]) || 0) - plain));
    const totalS = parseFloat(props["total-time"]) || 0;
    let hh = Math.floor(totalS / 3600);
    let mm = Math.round((totalS % 3600) / 60);
    if (mm === 60) { hh += 1; mm = 0; }

    this.querySelector("#rp-dist").textContent = `${km.toFixed(1)} km`;
    this.querySelector("#rp-asc").textContent = `${ascent} m`;
    this.querySelector("#rp-desc").textContent = `${descent} m`;
    this.querySelector("#rp-time").textContent = `${hh}:${String(mm).padStart(2, "0")} h`;
    this.querySelector("#rp-stats").style.display = "";

    const energyStat = this.querySelector("#rp-stat-energy");
    const battBox = this.querySelector("#rp-batt");
    const range = this._rangeData();
    // Signatur merken, damit set hass nur bei tatsächlich geänderten
    // Verbrauchs-/SoC-Werten neu rendert (Live-SoC-Refresh).
    this._lastRangeSig = range ? `${range.whPerKm}|${range.capacityWh}|${range.soc}` : "";
    if (!range || !range.whPerKm) {
      // Ohne Ø-Verbrauch keine Verbrauchs-/Akku-Zeilen — die Basis-Stats bleiben.
      energyStat.style.display = "none";
      battBox.style.display = "none";
      return;
    }

    const wh = Math.round(range.whPerKm * km);
    this.querySelector("#rp-energy").textContent = `${wh} Wh`;
    energyStat.style.display = "";

    const battLine = this.querySelector("#rp-batt-line");
    if (range.capacityWh && range.soc != null) {
      const needPct = (wh / range.capacityWh) * 100;
      const soc = range.soc;
      const icon = needPct <= soc * 0.7 ? "✅" : needPct <= soc ? "⚠️" : "⛔";
      battLine.textContent = `${icon} ${this._t("rp_batt_line", wh, Math.round(needPct), Math.round(soc))}`;
      battLine.style.display = "";
    } else {
      battLine.style.display = "none";
    }
    this.querySelector("#rp-note-est").textContent = this._t("rp_estimate_note");
    const hilly = this.querySelector("#rp-note-hilly");
    hilly.textContent = this._t("rp_hilly_note");
    hilly.style.display = ascent > 800 ? "" : "none";
    battBox.style.display = "";
  }

  // Reichweiten-Datenquelle: config.entity oder sprachunabhängige
  // Auto-Erkennung (Registry). SoC aus config.soc_entity oder dem
  // Schwester-Sensor "estimated_range_current" (Attribut current_soc).
  _rangeData() {
    const states = this._hass && this._hass.states;
    if (!states) return null;
    let entId = this._config.entity;
    if (!entId || !states[entId]) {
      entId = boschRangeEntityIds(this._hass, "estimated_range_full")[0] || null;
    }
    const st = entId ? states[entId] : null;
    if (!st) return null;
    const attrs = st.attributes || {};
    const whPerKm = Number(attrs.wh_per_km);
    const capacityWh = Number(attrs.battery_capacity_wh);
    let soc = NaN;
    if (this._config.soc_entity && states[this._config.soc_entity]) {
      soc = Number(states[this._config.soc_entity].state);
    } else {
      // Schwester-Sensor bevorzugt vom selben Gerät (Registry); Fallback:
      // englisches ID-Suffix bzw. erster Treffer.
      const reg = (this._hass && this._hass.entities) || {};
      const dev = reg[entId] && reg[entId].device_id;
      const candidates = boschRangeEntityIds(this._hass, "estimated_range_current");
      let sibId = dev
        ? candidates.find((id) => reg[id] && reg[id].device_id === dev)
        : null;
      if (!sibId) {
        const guess = entId.replace(/_estimated_range_full$/, "_estimated_range_current");
        sibId = (guess !== entId && states[guess]) ? guess : candidates[0];
      }
      const sibling = sibId ? states[sibId] : null;
      if (sibling && sibling.attributes) soc = Number(sibling.attributes.current_soc);
    }
    return {
      whPerKm: Number.isFinite(whPerKm) && whPerKm > 0 ? whPerKm : null,
      capacityWh: Number.isFinite(capacityWh) && capacityWh > 0 ? capacityWh : null,
      soc: Number.isFinite(soc) ? soc : null,
    };
  }

  // -------------------------------------------------------------------------
  // Höhenprofil
  // -------------------------------------------------------------------------

  _haversineMeters(lat1, lon1, lat2, lon2) {
    const R = 6371000;
    const toRad = (d) => d * Math.PI / 180;
    const dLat = toRad(lat2 - lat1);
    const dLon = toRad(lon2 - lon1);
    const a = Math.sin(dLat / 2) ** 2
      + Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon / 2) ** 2;
    return 2 * R * Math.asin(Math.sqrt(a));
  }

  _renderElevation(coords) {
    const box = this.querySelector("#rp-elev");
    const svg = this.querySelector("#rp-elev-svg");
    if (!box || !svg) return;

    const pts = []; // [kumulierte Distanz m, Höhe m]
    let dist = 0;
    let prev = null;
    for (const c of coords) {
      if (prev) dist += this._haversineMeters(prev[1], prev[0], c[1], c[0]);
      prev = c;
      if (c.length > 2 && Number.isFinite(c[2])) pts.push([dist, c[2]]);
    }
    if (pts.length < 2) {
      box.style.display = "none";
      return;
    }

    const W = 600, H = 80, PAD = 4;
    const maxD = pts[pts.length - 1][0] || 1;
    let minE = Infinity, maxE = -Infinity;
    for (const p of pts) {
      if (p[1] < minE) minE = p[1];
      if (p[1] > maxE) maxE = p[1];
    }
    const span = Math.max(maxE - minE, 10);
    const x = (d) => PAD + (d / maxD) * (W - 2 * PAD);
    const y = (e) => H - PAD - ((e - minE) / span) * (H - 2 * PAD);
    const line = pts.map((p) => `${x(p[0]).toFixed(1)},${y(p[1]).toFixed(1)}`).join(" ");
    svg.innerHTML =
      `<polygon points="${PAD},${H - PAD} ${line} ${W - PAD},${H - PAD}" fill="var(--primary-color,#03a9f4)" fill-opacity="0.15"></polygon>` +
      `<polyline points="${line}" fill="none" stroke="var(--primary-color,#03a9f4)" stroke-width="2"></polyline>`;
    const range = this.querySelector("#rp-elev-range");
    if (range) range.textContent = this._t("profile_min_max", Math.round(minE), Math.round(maxE));
    box.style.display = "";
  }

  // -------------------------------------------------------------------------
  // GPX-Export
  // -------------------------------------------------------------------------

  _exportGpx() {
    const coords = this._lastRouteCoords; if (!coords || coords.length < 2) return;
    const esc = (s) => String(s).replace(/[<>&]/g, (c) => ({ "<": "&lt;", ">": "&gt;", "&": "&amp;" }[c]));
    const name = esc(`Bosch eBike Route ${new Date().toISOString().slice(0, 10)}`);
    const pts = coords.map((c) => {
      const lon = Number(c[0]);
      const lat = Number(c[1]);
      if (!Number.isFinite(lon) || !Number.isFinite(lat)) return null;
      const ele = c.length > 2 && Number.isFinite(c[2]) ? `<ele>${Math.round(c[2])}</ele>` : "";
      return `      <trkpt lat="${lat.toFixed(6)}" lon="${lon.toFixed(6)}">${ele}</trkpt>`;
    }).filter(Boolean).join("\n");
    if (!pts) return;
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

  // -------------------------------------------------------------------------
  // Gespeicherte Routen (HA-Storage via list_routes/save_route/delete_route)
  // -------------------------------------------------------------------------

  _toggleSaveRow(show) {
    const row = this.querySelector("#rp-name-row");
    if (!row) return;
    const visible = row.style.display !== "none";
    const next = show != null ? !!show : !visible;
    row.style.display = next ? "" : "none";
    if (next) {
      const input = this.querySelector("#rp-name-in");
      if (input) {
        // Vorbelegung: Name der aktuell geladenen Route (Re-Save), sonst leer.
        input.value = this._loadedRouteName || "";
        input.focus();
        input.select();
      }
    }
  }

  async _saveRoute() {
    const input = this.querySelector("#rp-name-in");
    const name = ((input && input.value) || "").trim();
    if (!name || this._waypoints.length < 2) return;
    const lonlats = this._waypoints.map((m) => {
      const ll = m.getLatLng();
      return [ll.lng, ll.lat];
    });
    const meters = parseFloat(this._lastRouteProps && this._lastRouteProps["track-length"]);
    const msg = {
      type: "bosch_ebike/save_route",
      name,
      profile: this._profile,
      lonlats,
      distance_km: Number.isFinite(meters) ? Math.round(meters / 100) / 10 : null,
    };
    // Unveränderter Name der geladenen Route → Update per id. Ein NEUER
    // Name lässt die id bewusst weg: das Backend überschreibt dann einen
    // namensgleichen Eintrag oder legt neu an ("Speichern unter").
    if (
      this._loadedRouteId
      && this._loadedRouteName
      && name.toLowerCase() === this._loadedRouteName.trim().toLowerCase()
    ) {
      msg.route_id = this._loadedRouteId;
    }
    let res;
    try {
      res = await this._hass.callWS(msg);
    } catch (err) {
      // Servermeldung (Limit erreicht, ungültiger Name, …) klein dazu.
      this._setStatus(this._t("msg_error_prefix") + (err && err.message || err), "");
      return;
    }
    this._loadedRouteId = (res && res.saved_id) || null;
    this._loadedRouteName = name;
    this._toggleSaveRow(false);
    // Kurz-Bestätigung, blendet sich selbst aus (Muster wie rp_poi_error).
    const okMsg = this._t("rp_save_ok");
    this._setStatus(okMsg, "");
    setTimeout(() => {
      const mainEl = this.querySelector("#rp-status-main");
      if (mainEl && mainEl.textContent === okMsg) this._setStatus(null);
    }, 3000);
    // Offenes Listen-Panel direkt mit der Antwort auffrischen (kein Re-Fetch).
    this._refreshRoutesPanel(res && Array.isArray(res.routes) ? res.routes : null);
  }

  async _toggleRoutesPanel() {
    const panel = this.querySelector("#rp-routes-panel");
    if (!panel) return;
    const open = panel.style.display === "none";
    panel.style.display = open ? "" : "none";
    const btn = this.querySelector("#rp-routes");
    if (btn) btn.classList.toggle("eb-active", open);
    if (open) await this._refreshRoutesPanel();
  }

  // Listen-Panel neu rendern; ohne übergebene Liste wird sie frisch vom
  // Backend geholt. Tut nichts, solange das Panel geschlossen ist.
  async _refreshRoutesPanel(routes = null) {
    const panel = this.querySelector("#rp-routes-panel");
    if (!panel || panel.style.display === "none") return;
    if (!routes) {
      try {
        const res = await this._hass.callWS({ type: "bosch_ebike/list_routes" });
        routes = res && Array.isArray(res.routes) ? res.routes : [];
      } catch (err) {
        console.warn("[Bosch eBike Routeplanner] list_routes failed", err);
        panel.innerHTML = "";
        const fail = document.createElement("div");
        fail.className = "rp-routes-empty";
        fail.textContent = this._t("rp_load_failed");
        panel.appendChild(fail);
        return;
      }
    }
    this._renderRoutesList(routes);
  }

  // Routennamen sind Nutzereingaben → konsequent über textContent setzen
  // (kein innerHTML), damit kein HTML aus dem Namen gerendert wird.
  _renderRoutesList(routes) {
    const panel = this.querySelector("#rp-routes-panel");
    if (!panel) return;
    panel.innerHTML = "";
    if (!routes.length) {
      const empty = document.createElement("div");
      empty.className = "rp-routes-empty";
      empty.textContent = this._t("rp_no_saved");
      panel.appendChild(empty);
      return;
    }
    for (const route of routes) {
      const row = document.createElement("div");
      row.className = "rp-route-row";

      const info = document.createElement("div");
      info.className = "rp-route-info";
      const nameEl = document.createElement("div");
      nameEl.className = "rp-route-name";
      nameEl.textContent = route.name || "";
      const meta = document.createElement("div");
      meta.className = "rp-route-meta";
      const parts = [];
      if (RP_PROFILES.includes(route.profile)) {
        parts.push(this._t("rp_profile_" + route.profile));
      }
      const km = Number(route.distance_km);
      if (Number.isFinite(km)) {
        parts.push(`${km.toLocaleString(undefined, { minimumFractionDigits: 1, maximumFractionDigits: 1 })} km`);
      }
      if (route.updated) {
        const d = new Date(route.updated);
        if (!Number.isNaN(d.getTime())) parts.push(d.toLocaleDateString());
      }
      meta.textContent = parts.join(" · ");
      info.appendChild(nameEl);
      info.appendChild(meta);
      info.addEventListener("click", () => this._loadSavedRoute(route));

      const del = document.createElement("button");
      del.type = "button";
      del.className = "rp-route-del";
      del.textContent = "✕";
      del.addEventListener("click", (ev) => {
        ev.stopPropagation();
        this._deleteSavedRoute(route, del);
      });

      row.appendChild(info);
      row.appendChild(del);
      panel.appendChild(row);
    }
  }

  _loadSavedRoute(route) {
    const Leaflet = window.L;
    if (!Leaflet || !this._map) return;
    // Karte leeren wie _reset, aber Panel + Hinweiszeile unangetastet lassen.
    this._clearWaypoints();
    for (const pair of (Array.isArray(route.lonlats) ? route.lonlats : [])) {
      const lon = Number(pair && pair[0]);
      const lat = Number(pair && pair[1]);
      if (!Number.isFinite(lat) || !Number.isFinite(lon)) continue;
      this._addWaypoint(Leaflet.latLng(lat, lon));
    }
    this._refreshWaypointStyles();
    if (RP_PROFILES.includes(route.profile)) {
      this._profile = route.profile;
      const sel = this.querySelector("#rp-profile");
      if (sel) sel.value = route.profile;
    }
    this._loadedRouteId = route.id || null;
    this._loadedRouteName = route.name || null;
    this._fitPending = true;
    this._scheduleRoute();
  }

  async _deleteSavedRoute(route, btn) {
    // Zwei-Klick-Bestätigung wie der Stop-Button der Dashboard-Card:
    // erster Klick schaltet 3 s lang in den "Sicher?"-Zustand.
    if (btn.dataset.confirm !== "1") {
      btn.dataset.confirm = "1";
      btn.classList.add("confirm");
      btn.textContent = this._t("dash_btn_confirm");
      setTimeout(() => {
        if (btn.dataset.confirm === "1") {
          btn.dataset.confirm = "";
          btn.classList.remove("confirm");
          btn.textContent = "✕";
        }
      }, 3000);
      return;
    }
    let res;
    try {
      res = await this._hass.callWS({
        type: "bosch_ebike/delete_route",
        route_id: route.id,
      });
    } catch (err) {
      this._setStatus(this._t("msg_error_prefix") + (err && err.message || err), "");
      return;
    }
    // Geladene Route gelöscht? Verknüpfung lösen — die Marker bleiben,
    // ein erneutes 💾 legt die Route bei Bedarf wieder neu an.
    if (this._loadedRouteId && this._loadedRouteId === route.id) {
      this._loadedRouteId = null;
      this._loadedRouteName = null;
    }
    this._renderRoutesList(res && Array.isArray(res.routes) ? res.routes : []);
  }

  // -------------------------------------------------------------------------
  // POI-Overlay entlang der Route (Overpass via Backend-Proxy) — Mechanik wie
  // in der Map-Card, zusätzlich mit Gastronomie-Kategorien
  // -------------------------------------------------------------------------

  _togglePoi() {
    this._poiEnabled = !this._poiEnabled;
    try { localStorage.setItem("eb-rp-poi-enabled", this._poiEnabled ? "1" : "0"); } catch (_) {}
    const btn = this.querySelector("#rp-poi");
    if (btn) btn.classList.toggle("eb-active", this._poiEnabled);
    if (this._poiEnabled) {
      // Ohne Route passiert nichts — POIs kommen, sobald eine Route da ist.
      this._loadAndRenderPois();
    } else {
      this._poiSeq += 1; // laufende Antwort verwerfen
      if (this._poiGroup) {
        try { this._poiGroup.clearLayers(); } catch (_) {}
      }
    }
  }

  _setPoiLoadingUI(loading) {
    const btn = this.querySelector("#rp-poi");
    if (btn) {
      btn.classList.toggle("eb-loading", !!loading);
      btn.disabled = !!loading;
    }
  }

  async _loadAndRenderPois() {
    if (!this._poiEnabled || !this._map) return;
    const coords = this._lastRouteCoords;
    if (!coords || coords.length < 2) return;
    const track = coords
      .map((c) => ({ lat: Number(c[1]), lon: Number(c[0]) }))
      .filter((p) => Number.isFinite(p.lat) && Number.isFinite(p.lon));
    if (track.length < 2) return;

    // Bbox der Route + Puffer (wie _fetchPois der Map-Card, Radius 500 m)
    let minLat = Infinity, maxLat = -Infinity, minLon = Infinity, maxLon = -Infinity;
    for (const p of track) {
      if (p.lat < minLat) minLat = p.lat;
      if (p.lat > maxLat) maxLat = p.lat;
      if (p.lon < minLon) minLon = p.lon;
      if (p.lon > maxLon) maxLon = p.lon;
    }
    const pad = RP_POI_RADIUS_M / 111000 + 0.001;
    const south = minLat - pad;
    const north = maxLat + pad;
    const west = minLon - pad;
    const east = maxLon + pad;

    // In-Memory-Cache: gerundete Bbox + Kategorien — Toggle/Rebuild auf
    // derselben Route fragt Overpass nicht erneut ab.
    const cacheKey = [south, west, north, east].map((v) => v.toFixed(4)).join(",")
      + "|" + RP_POI_CATEGORIES.join(",");
    const seq = ++this._poiSeq;
    let elements = this._poiCache.get(cacheKey);

    if (!elements) {
      this._setPoiLoadingUI(true);
      try {
        const res = await this._hass.callWS({
          type: "bosch_ebike/get_pois",
          south, west, north, east,
          categories: RP_POI_CATEGORIES,
        });
        elements = (res && Array.isArray(res.elements)) ? res.elements : [];
        if (this._poiCache.size > 20) this._poiCache.clear();
        this._poiCache.set(cacheKey, elements);
      } catch (err) {
        console.warn("[Bosch eBike Routeplanner] POI fetch failed", err);
        if (seq === this._poiSeq) {
          // Marker der VORHERIGEN Route nicht neben der neuen stehen lassen.
          if (this._poiGroup) {
            try { this._poiGroup.clearLayers(); } catch (_) {}
          }
          const msg = this._t("rp_poi_error");
          this._setStatus(msg, "");
          // Hinweis nach kurzer Zeit ausblenden — die Route bleibt nutzbar.
          setTimeout(() => {
            const mainEl = this.querySelector("#rp-status-main");
            if (mainEl && mainEl.textContent === msg) this._setStatus(null);
          }, 5000);
        }
        return;
      } finally {
        // Nur die eigene (aktuelle) Anfrage darf den Lade-Puls beenden —
        // sonst stoppt eine überholte Antwort die Anzeige der laufenden.
        if (seq === this._poiSeq) this._setPoiLoadingUI(false);
      }
    }

    // Veraltet (neue Route/Toggle aus/Reset während des Fetches)? Verwerfen.
    if (seq !== this._poiSeq || !this._poiEnabled || this._lastRouteCoords !== coords) return;
    this._renderPoiMarkers(this._filterPois(elements, track));
  }

  // Elemente parsen, auf Routen-Nähe filtern und auf 100 Marker kappen
  // (Spiegel von _fetchPois der Map-Card, fester Radius 500 m).
  _filterPois(elements, track) {
    const MAX_DIST_M = RP_POI_RADIUS_M;
    const sampled = this._poiSamplePoints(track, MAX_DIST_M / 2);
    const out = [];
    for (const el of elements) {
      if (typeof el.lat !== "number" || typeof el.lon !== "number") continue;
      let near = false;
      for (const sp of sampled) {
        if (this._haversineMeters(el.lat, el.lon, sp.lat, sp.lon) <= MAX_DIST_M) {
          near = true; break;
        }
      }
      if (!near) continue;
      const tags = el.tags || {};
      const cat = this._poiCategory(tags);
      if (!cat) continue;
      out.push({
        lat: el.lat,
        lon: el.lon,
        category: cat.key,
        catLabel: cat.label,
        catIcon: cat.icon,
        name: tags.name || cat.label,
        osmId: el.id,
        tags,
      });
    }
    // Maximal 100 Marker, sonst wird die Karte unübersichtlich
    return out.slice(0, 100);
  }

  // Kategorien wie in der Map-Card, zusätzlich Gastronomie
  _poiCategory(tags) {
    if (tags.amenity === "charging_station") {
      return { key: "charging", label: this._t("poi_charging"), icon: "🔌" };
    }
    if (tags.shop === "bicycle") {
      return { key: "bicycle", label: this._t("poi_bicycle_shop"), icon: "🛠️" };
    }
    if (tags.amenity === "bicycle_repair_station") {
      return { key: "bicycle", label: this._t("poi_repair"), icon: "🛠️" };
    }
    if (tags.amenity === "drinking_water") {
      return { key: "water", label: this._t("poi_water"), icon: "💧" };
    }
    if (tags.amenity === "toilets") {
      return { key: "toilet", label: this._t("poi_toilet"), icon: "🚻" };
    }
    if (tags.amenity === "restaurant" || tags.amenity === "fast_food") {
      return { key: "food", label: this._t("poi_food"), icon: "🍽️" };
    }
    if (tags.amenity === "cafe") {
      return { key: "cafe", label: this._t("poi_cafe"), icon: "☕" };
    }
    if (tags.amenity === "biergarten") {
      return { key: "biergarten", label: this._t("poi_biergarten"), icon: "🍺" };
    }
    return null;
  }

  /// Punkte alle `intervalM` Meter entlang der Route (Dublette der Map-Card,
  /// wie beim _haversineMeters-Präzedenzfall).
  _poiSamplePoints(track, intervalM = 250) {
    if (!Array.isArray(track) || track.length < 2) return [];
    const intervalKm = Math.max(0.05, intervalM / 1000);
    const pts = [];
    pts.push({ lat: track[0].lat, lon: track[0].lon });
    let cumKm = 0;
    let lastSampled = 0;
    for (let i = 1; i < track.length; i += 1) {
      cumKm += this._haversineMeters(track[i - 1].lat, track[i - 1].lon, track[i].lat, track[i].lon) / 1000;
      if (cumKm - lastSampled >= intervalKm) {
        pts.push({ lat: track[i].lat, lon: track[i].lon });
        lastSampled = cumKm;
      }
    }
    const last = track[track.length - 1];
    pts.push({ lat: last.lat, lon: last.lon });
    return pts;
  }

  _renderPoiMarkers(pois) {
    if (!this._poiEnabled) return;
    const Leaflet = window.L;
    if (!Leaflet || !this._map) return;
    if (!this._poiGroup) this._poiGroup = Leaflet.layerGroup().addTo(this._map);
    this._poiGroup.clearLayers();
    const popupOpts = { maxWidth: 260, closeOnClick: false, autoClose: false };
    for (const poi of pois) {
      const icon = Leaflet.divIcon({
        className: "",
        html: `<div class="eb-poi-marker eb-poi-${poi.category}">${poi.catIcon}</div>`,
        iconSize: [18, 18],
        iconAnchor: [9, 9],
      });
      const marker = Leaflet.marker([poi.lat, poi.lon], { icon, title: `${poi.catIcon} ${poi.name}` });
      marker.bindPopup(this._poiPopupHtml(poi), popupOpts);
      marker.addTo(this._poiGroup);
    }
  }

  // Dublette der Map-Card-Methode — OSM-Tag-Werte (Name, Öffnungszeiten,
  // Adresse, Website) sind Fremddaten und werden durchgängig escaped.
  _poiPopupHtml(poi) {
    const safeName = this._escapeHtml(poi.name);
    const osmUrl = `https://www.openstreetmap.org/node/${poi.osmId}`;
    let extra = "";
    if (poi.tags.opening_hours) {
      extra += `<div>🕒 ${this._escapeHtml(poi.tags.opening_hours)}</div>`;
    }
    if (poi.tags["addr:street"]) {
      const addr = [poi.tags["addr:street"], poi.tags["addr:housenumber"]].filter(Boolean).join(" ");
      extra += `<div>📍 ${this._escapeHtml(addr)}</div>`;
    }
    if (poi.tags.website) {
      const url = poi.tags.website.startsWith("http") ? poi.tags.website : "https://" + poi.tags.website;
      extra += `<div>🌐 <a href="${this._escapeHtml(url)}" target="_blank" rel="noopener">${this._t("poi_website_link")}</a></div>`;
    }
    return `<div class="eb-poi-popup">
      <div class="eb-poi-title">${poi.catIcon} ${safeName}</div>
      <div class="eb-poi-cat">${this._escapeHtml(poi.catLabel)}</div>
      ${extra}
      <a class="eb-poi-link" href="${osmUrl}" target="_blank" rel="noopener noreferrer">${this._t("poi_open_osm")}</a>
    </div>`;
  }

  _escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
    })[c]);
  }

  // -------------------------------------------------------------------------
  // Status-Chip auf der Karte (Routing läuft / Fehler + Servertext klein)
  // -------------------------------------------------------------------------

  _setStatus(main, sub = "") {
    const box = this.querySelector("#rp-status");
    if (!box) return;
    if (!main) {
      box.style.display = "none";
      return;
    }
    this.querySelector("#rp-status-main").textContent = main;
    const subEl = this.querySelector("#rp-status-sub");
    subEl.textContent = sub || "";
    subEl.style.display = sub ? "" : "none";
    box.style.display = "";
  }
}

class BoschEBikeRoutePlannerCardEditor extends HTMLElement {
  constructor() {
    super();
    this._hass = null;
    this._config = null;
    this._built = false;
  }

  // DOM nur EINMAL bauen (Muster wie BoschEBike3DMapCardEditor): ein
  // innerHTML-Re-Render nach jedem config-changed-Roundtrip würde nach
  // jedem Feld-Commit den Eingabe-Fokus wegschießen (v1.16.5-Bug-Klasse).
  // Danach synct setConfig nur noch die Feld-Werte.
  setConfig(config) {
    this._config = config;
    if (!this._built) {
      // Lazy: erst rendern, wenn hass da ist — die Entity-Dropdowns
      // brauchen hass.states und die Labels die hass-Sprache.
      if (this._hass) this._render();
    } else {
      this._sync();
    }
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._built && this._config) {
      this._render();
    } else if (this._built) {
      // _render() only ever runs once (see setConfig), so the entity
      // pickers created there would otherwise keep the .hass from that
      // first tick forever and never see newly added entities.
      const entityIn = this.querySelector("#rp-entity-in");
      const socIn = this.querySelector("#rp-soc-in");
      if (entityIn) entityIn.hass = hass;
      if (socIn) socIn.hass = hass;
    }
  }

  _escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
    })[c]);
  }

  _emit() {
    this.dispatchEvent(new CustomEvent("config-changed", { detail: { config: this._config } }));
  }

  // Wird nach dem einmaligen _render() bei jedem setConfig aufgerufen:
  // aktualisiert nur die Feld-Werte, ohne das DOM neu zu bauen.
  _sync() {
    const cfg = this._config || {};
    const set = (id, v) => {
      const el = this.querySelector(id);
      if (el && el.value !== v) el.value = v;
    };
    set("#rp-h-in", String(parseInt(cfg.height, 10) || 480));
    set("#rp-title-in", cfg.title || "");
    set("#rp-brouter-in", cfg.brouter_url || "");
    set("#rp-entity-in", cfg.entity || "");
    set("#rp-soc-in", cfg.soc_entity || "");
  }

  _render() {
    if (!this._config) return;
    const cfg = this._config;
    const t = (k, ...a) => ebT(this._hass, k, ...a);
    const inputStyle = "width:100%;padding:8px;border:1px solid #ccc;border-radius:4px;background:var(--card-background-color,#fff);color:var(--primary-text-color,#222);";
    const labelStyle = "display:block;margin-top:14px;margin-bottom:6px;font-weight:500";
    const hintStyle = "display:block;margin-top:4px;font-size:12px;color:var(--secondary-text-color,#777)";

    this.innerHTML = `<div style="padding:16px">
      <label style="${labelStyle.replace('margin-top:14px;', '')}">${t("editor_height")}</label>
      <input type="number" value="${parseInt(cfg.height, 10) || 480}" min="200" max="1000" step="20" style="${inputStyle}" id="rp-h-in">

      <label style="${labelStyle}">${t("editor_title")}</label>
      <input type="text" value="${this._escapeHtml(cfg.title || '')}" placeholder="${t("rp_default_title")}" style="${inputStyle}" id="rp-title-in">
      <span style="${hintStyle}">${t("editor_title_hint")}</span>

      <label style="${labelStyle}">${t("rp_editor_brouter_url")}</label>
      <input type="text" value="${this._escapeHtml(cfg.brouter_url || '')}" placeholder="https://brouter.de" style="${inputStyle}" id="rp-brouter-in">

      <label style="${labelStyle}">${t("rp_editor_entity")}</label>
      <div id="rp-entity-in-holder"></div>
      <span style="${hintStyle}">${t("rp_editor_entity_hint")}</span>

      <label style="${labelStyle}">${t("rp_editor_soc")}</label>
      <div id="rp-soc-in-holder"></div>
      <span style="${hintStyle}">${t("rp_editor_soc_hint")}</span>

      <span style="${hintStyle};margin-top:14px;">${t("rp_privacy_note")}</span>
    </div>`;

    this.querySelector("#rp-h-in").addEventListener("change", (e) => {
      this._config = { ...this._config, height: parseInt(e.target.value, 10) || 480 };
      this._emit();
    });
    this.querySelector("#rp-title-in").addEventListener("change", (e) => {
      const v = e.target.value.trim();
      this._config = { ...this._config };
      if (v) this._config.title = v;
      else delete this._config.title;
      this._emit();
    });
    this.querySelector("#rp-brouter-in").addEventListener("change", (e) => {
      const v = e.target.value.trim();
      this._config = { ...this._config };
      if (v) this._config.brouter_url = v;
      else delete this._config.brouter_url;
      this._emit();
    });
    // Native searchable HA entity pickers (issue #45) instead of a <select>
    // listing every matching entity - built here rather than as template
    // strings since filtering/hass can only be set on the actual element.
    const rangeIds = new Set(boschRangeEntityIds(this._hass, "estimated_range_full"));
    const entityPicker = document.createElement("ha-entity-picker");
    entityPicker.id = "rp-entity-in";
    entityPicker.hass = this._hass;
    entityPicker.entityFilter = (stateObj) =>
      rangeIds.has(stateObj.entity_id) || stateObj.entity_id.endsWith("_estimated_range_full");
    entityPicker.allowCustomEntity = true;
    entityPicker.value = cfg.entity || "";
    entityPicker.style.width = "100%";
    entityPicker.addEventListener("value-changed", (ev) => {
      const v = ev.detail.value;
      this._config = { ...this._config };
      if (v) this._config.entity = v;
      else delete this._config.entity;
      this._emit();
    });
    this.querySelector("#rp-entity-in-holder").appendChild(entityPicker);

    const socPicker = document.createElement("ha-entity-picker");
    socPicker.id = "rp-soc-in";
    socPicker.hass = this._hass;
    socPicker.includeDomains = ["sensor"];
    socPicker.allowCustomEntity = true;
    socPicker.value = cfg.soc_entity || "";
    socPicker.style.width = "100%";
    socPicker.addEventListener("value-changed", (ev) => {
      const v = ev.detail.value;
      this._config = { ...this._config };
      if (v) this._config.soc_entity = v;
      else delete this._config.soc_entity;
      this._emit();
    });
    this.querySelector("#rp-soc-in-holder").appendChild(socPicker);

    this._built = true;
  }
}

if (!customElements.get("bosch-ebike-map-card")) {
  customElements.define("bosch-ebike-map-card", BoschEBikeMapCard);
}
if (!customElements.get("bosch-ebike-map-card-editor")) {
  customElements.define("bosch-ebike-map-card-editor", BoschEBikeMapCardEditor);
}
if (!customElements.get("bosch-ebike-heatmap-card")) {
  customElements.define("bosch-ebike-heatmap-card", BoschEBikeHeatmapCard);
}
if (!customElements.get("bosch-ebike-heatmap-card-editor")) {
  customElements.define("bosch-ebike-heatmap-card-editor", BoschEBikeHeatmapCardEditor);
}
if (!customElements.get("bosch-ebike-calendar-card")) {
  customElements.define("bosch-ebike-calendar-card", BoschEBikeCalendarCard);
}
if (!customElements.get("bosch-ebike-calendar-card-editor")) {
  customElements.define("bosch-ebike-calendar-card-editor", BoschEBikeCalendarCardEditor);
}
if (!customElements.get("bosch-ebike-dashboard-card")) {
  customElements.define("bosch-ebike-dashboard-card", BoschEBikeDashboardCard);
}
if (!customElements.get("bosch-ebike-dashboard-card-editor")) {
  customElements.define("bosch-ebike-dashboard-card-editor", BoschEBikeDashboardCardEditor);
}
if (!customElements.get("bosch-ebike-3d-map-card")) {
  customElements.define("bosch-ebike-3d-map-card", BoschEBike3DMapCard);
}
if (!customElements.get("bosch-ebike-3d-map-card-editor")) {
  customElements.define("bosch-ebike-3d-map-card-editor", BoschEBike3DMapCardEditor);
}
if (!customElements.get("bosch-ebike-routeplanner-card")) {
  customElements.define("bosch-ebike-routeplanner-card", BoschEBikeRoutePlannerCard);
}
if (!customElements.get("bosch-ebike-routeplanner-card-editor")) {
  customElements.define("bosch-ebike-routeplanner-card-editor", BoschEBikeRoutePlannerCardEditor);
}
if (!customElements.get("bosch-ebike-stats-card")) {
  customElements.define("bosch-ebike-stats-card", BoschEBikeStatsCard);
}
if (!customElements.get("bosch-ebike-stats-card-editor")) {
  customElements.define("bosch-ebike-stats-card-editor", BoschEBikeStatsCardEditor);
}
if (!customElements.get("bosch-ebike-trick-list-card")) {
  customElements.define("bosch-ebike-trick-list-card", BoschEBikeTrickListCard);
}
if (!customElements.get("bosch-ebike-trick-list-card-editor")) {
  customElements.define("bosch-ebike-trick-list-card-editor", BoschEBikeTrickListCardEditor);
}

// window.customCards descriptions run at module load time, before any card
// instance (and its hass) exists - ebT() falls back to English when passed
// a falsy hass, so proxy the browser's language here instead (the closest
// approximation of the user's HA language available this early).
function ebTStatic(key) {
  return ebT({ locale: { language: navigator.language } }, key);
}

window.customCards = window.customCards || [];
if (!window.customCards.find((c) => c.type === "bosch-ebike-map-card")) {
  window.customCards.push({
    type: "bosch-ebike-map-card",
    name: "Bosch eBike Map",
    description: ebTStatic("map_card_desc"),
    preview: true,
  });
}
if (!window.customCards.find((c) => c.type === "bosch-ebike-heatmap-card")) {
  window.customCards.push({
    type: "bosch-ebike-heatmap-card",
    name: "Bosch eBike Heatmap",
    description: ebTStatic("heatmap_card_desc"),
    preview: false,
  });
}
if (!window.customCards.find((c) => c.type === "bosch-ebike-calendar-card")) {
  window.customCards.push({
    type: "bosch-ebike-calendar-card",
    name: "Bosch eBike Calendar",
    description: ebTStatic("calendar_card_desc"),
    preview: false,
  });
}
if (!window.customCards.find((c) => c.type === "bosch-ebike-dashboard-card")) {
  window.customCards.push({
    type: "bosch-ebike-dashboard-card",
    name: "Bosch eBike Dashboard",
    description: ebTStatic("dashboard_card_desc"),
    preview: false,
  });
}
if (!window.customCards.find((c) => c.type === "bosch-ebike-3d-map-card")) {
  window.customCards.push({
    type: "bosch-ebike-3d-map-card",
    name: "Bosch eBike 3D-Karte",
    description: ebTStatic("map3d_card_desc"),
    preview: false,
  });
}
if (!window.customCards.find((c) => c.type === "bosch-ebike-routeplanner-card")) {
  window.customCards.push({
    type: "bosch-ebike-routeplanner-card",
    name: "Bosch eBike Route Planner",
    description: ebTStatic("rp_card_desc"),
    preview: false,
  });
}
if (!window.customCards.find((c) => c.type === "bosch-ebike-stats-card")) {
  window.customCards.push({
    type: "bosch-ebike-stats-card",
    name: "Bosch eBike Statistics",
    description: ebTStatic("stats_card_desc"),
    preview: false,
  });
}
if (!window.customCards.find((c) => c.type === "bosch-ebike-trick-list-card")) {
  window.customCards.push({
    type: "bosch-ebike-trick-list-card",
    name: "Bosch eBike Trick List",
    description: ebTStatic("tricklist_card_desc"),
    preview: false,
  });
}
