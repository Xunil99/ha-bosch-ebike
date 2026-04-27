/**
 * Bosch eBike Map Card for Home Assistant
 * Robust rewrite focused on view switches, iOS WebView quirks, and hidden-container recovery.
 */

const LEAFLET_JS = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js";

const MAP_STYLES = {
  osm: {
    label: "OSM",
    name: "Standard",
    url: "https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png",
    options: { maxZoom: 19, updateWhenIdle: true, keepBuffer: 2, attribution: '&copy; OpenStreetMap contributors &copy; CARTO' }
  },
  topo: {
    label: "Topo",
    name: "Topo",
    url: "https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png",
    options: { maxZoom: 17, updateWhenIdle: true, keepBuffer: 2 }
  },
  sat: {
    label: "Sat",
    name: "Satellit",
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

function ensureLeaflet() {
  if (window.L && typeof window.L.map === "function") return Promise.resolve(window.L);
  if (window.__ebikeLeafletPromise) return window.__ebikeLeafletPromise;

  window.__ebikeLeafletPromise = new Promise((resolve, reject) => {
    const existing = document.querySelector(`script[src="${LEAFLET_JS}"]`);
    if (existing) {
      const finish = () => {
        if (window.L && typeof window.L.map === "function") resolve(window.L);
        else reject(new Error("Leaflet wurde geladen, ist aber nicht verfügbar"));
      };
      existing.addEventListener("load", finish, { once: true });
      existing.addEventListener("error", () => reject(new Error("Leaflet konnte nicht geladen werden")), { once: true });
      if (window.L && typeof window.L.map === "function") finish();
      return;
    }

    const script = document.createElement("script");
    script.src = LEAFLET_JS;
    script.async = true;
    script.onload = () => {
      if (window.L && typeof window.L.map === "function") resolve(window.L);
      else reject(new Error("Leaflet wurde geladen, ist aber nicht verfügbar"));
    };
    script.onerror = () => reject(new Error("Leaflet konnte nicht geladen werden"));
    document.head.appendChild(script);
  });

  return window.__ebikeLeafletPromise;
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
    this._config = { height: config.height || 400, ...config };
  }

  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    if (first) this._boot();
    else if (this._connected) this._scheduleActivation("hass update");
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
    this._destroyFullscreenMap();
    this._destroyMap(false);
  }

  getCardSize() {
    return Math.ceil((this._config.height || 400) / 50) + 4;
  }

  static getConfigElement() { return document.createElement("bosch-ebike-map-card-editor"); }
  static getStubConfig() { return { height: 400 }; }

  async _boot() {
    if (this._booting || this._ready) return;
    this._booting = true;

    if (!this._ready) {
      this._buildDOM();
      this._attachLifecycleHooks();
      this._ready = true;
    }

    try {
      await ensureLeaflet();
      this._leafletReady = true;
      await this._fetchInstances();
      await this._fetchActivities();
      this._scheduleActivation("boot finished");
    } catch (error) {
      console.error("[Bosch eBike Map] boot error", error);
      this._msg("Fehler: " + (error?.message || error));
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
      .eb-title { text-align:center; padding:10px 16px 2px; font-size:16px; font-weight:600; color:var(--primary-text-color,#333); }
      .eb-datelbl { text-align:center; font-size:12px; color:var(--secondary-text-color,#666); padding:0 16px 6px; }
      .eb-stats { display:grid; grid-template-columns:repeat(3,1fr); gap:4px; padding:8px 16px 14px; }
      .eb-stat { text-align:center; }
      .eb-val { font-size:20px; font-weight:700; color:var(--primary-text-color,#212121); }
      .eb-lbl { font-size:11px; color:var(--secondary-text-color,#757575); }

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
      .eb-fullscreen-title { flex:1; min-width:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; font-weight:600; }
      .eb-fullscreen-nav { display:flex; align-items:center; gap:8px; flex-wrap:wrap; }
      .eb-fullscreen-nav input[type="date"] { min-width:170px; padding:6px 10px; border:1px solid rgba(255,255,255,.2); border-radius:8px; background:rgba(255,255,255,.12); color:#fff; }
      .eb-fullscreen-nav .eb-ctr { color:rgba(255,255,255,.8); }
      .eb-fullscreen-map { flex:1; min-height:280px; position:relative; }
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
    wrap.innerHTML = `
      <div class="eb-head">
        <svg viewBox="0 0 24 24" width="22" height="22"><path fill="white" d="M15.5,5.5C16.9,5.5 18,6.6 18,8C18,9.4 16.9,10.5 15.5,10.5C14.1,10.5 13,9.4 13,8C13,6.6 14.1,5.5 15.5,5.5M5,12C2.2,12 0,14.2 0,17C0,19.8 2.2,22 5,22C7.8,22 10,19.8 10,17C10,14.2 7.8,12 5,12M5,20.5C3.1,20.5 1.5,18.9 1.5,17C1.5,15.1 3.1,13.5 5,13.5C6.9,13.5 8.5,15.1 8.5,17C8.5,18.9 6.9,20.5 5,20.5M19,12C16.2,12 14,14.2 14,17C14,19.8 16.2,22 19,22C21.8,22 24,19.8 24,17C24,14.2 21.8,12 19,12M19,20.5C17.1,20.5 15.5,18.9 15.5,17C15.5,15.1 17.1,13.5 19,13.5C20.9,13.5 22.5,15.1 22.5,17C22.5,18.9 20.9,20.5 19,20.5M12.5,11.5L10.1,8.8C10.6,7.8 11.4,7.3 12.3,7.3H14.2L12.9,6H10.3C9.1,6 8,6.7 7.5,7.8L6.1,10.8L5,12.1L7.2,13.5L8.3,11.5H12.5Z"/></svg>
        <span>Bosch eBike Rides</span>
      </div>
      <div class="eb-nav">
        <button id="eb-prev">◀</button>
        <input type="date" id="eb-date">
        <button id="eb-next">▶</button>
        <span id="eb-ctr" class="eb-ctr">–</span>
      </div>
      <div class="eb-sort" id="eb-filter-account-wrap" style="display:none;">
        <span class="eb-sort-lbl">Konto:</span>
        <select id="eb-filter-account">
          <option value="all">Alle Konten</option>
        </select>
      </div>
      <div class="eb-sort" id="eb-filter-bike-wrap" style="display:none;">
        <span class="eb-sort-lbl">Bike:</span>
        <select id="eb-filter-bike">
          <option value="all">Alle Bikes</option>
        </select>
      </div>
      <div class="eb-sort">
        <span class="eb-sort-lbl">Sortierung:</span>
        <select id="eb-sort-key">
          <option value="date">Datum</option>
          <option value="distance">Distanz</option>
          <option value="duration">Dauer</option>
          <option value="avgSpeed">Ø Geschw.</option>
          <option value="maxSpeed">Max Geschw.</option>
          <option value="elevation">Höhenmeter</option>
          <option value="calories">Kalorien</option>
          <option value="difficulty">Schwierigkeit</option>
          <option value="batteryWh">Akku Wh</option>
          <option value="batteryPct">Akku %</option>
        </select>
        <button id="eb-sort-dir" title="Sortierrichtung umkehren">↓</button>
      </div>
      <div class="eb-map-wrap">
        <div id="eb-map" class="eb-map"></div>
        <div class="eb-map-tools">
          <button id="eb-style" class="eb-icon-btn eb-style-btn" title="Kartenstil wechseln" aria-label="Kartenstil wechseln">OSM</button>
          <button id="eb-gpx" class="eb-icon-btn" title="GPX herunterladen" aria-label="GPX herunterladen">GPX</button>
          <button id="eb-fullscreen" class="eb-icon-btn" title="Vollbild" aria-label="Vollbild">
            <svg viewBox="0 0 24 24" width="20" height="20"><path fill="currentColor" d="M7,14H5V19H10V17H7V14M5,10H7V7H10V5H5V10M17,17H14V19H19V14H17V17M14,5V7H17V10H19V5H14Z"/></svg>
          </button>
        </div>
        <div id="eb-overlay-msg" class="eb-overlay-msg"></div>
      </div>
      <div id="eb-title" class="eb-title"></div>
      <div id="eb-date-lbl" class="eb-datelbl"></div>
      <div id="eb-stats" class="eb-stats"></div>
      <div id="eb-fullscreen-overlay" class="eb-fullscreen" aria-hidden="true">
        <div class="eb-fullscreen-card">
          <div class="eb-fullscreen-head">
            <div id="eb-fullscreen-title" class="eb-fullscreen-title">Bosch eBike Ride</div>
            <div class="eb-fullscreen-nav">
              <button id="eb-full-prev" class="eb-icon-btn" title="Vorherige Fahrt" aria-label="Vorherige Fahrt">◀</button>
              <input type="date" id="eb-full-date">
              <button id="eb-full-next" class="eb-icon-btn" title="Nächste Fahrt" aria-label="Nächste Fahrt">▶</button>
              <span id="eb-full-ctr" class="eb-ctr">–</span>
            </div>
            <button id="eb-full-style" class="eb-icon-btn eb-style-btn" title="Kartenstil wechseln" aria-label="Kartenstil wechseln">OSM</button>
            <button id="eb-full-gpx" class="eb-icon-btn" title="GPX herunterladen" aria-label="GPX herunterladen">GPX</button>
            <button id="eb-fit" class="eb-icon-btn" title="Route einpassen" aria-label="Route einpassen">
              <svg viewBox="0 0 24 24" width="20" height="20"><path fill="currentColor" d="M4,4H10V6H6V10H4V4M14,4H20V10H18V6H14V4M4,14H6V18H10V20H4V14M18,14H20V20H14V18H18V14Z"/></svg>
            </button>
            <button id="eb-full-close" class="eb-icon-btn" title="Schließen" aria-label="Schließen">
              <svg viewBox="0 0 24 24" width="20" height="20"><path fill="currentColor" d="M19,6.41L17.59,5L12,10.59L6.41,5L5,6.41L10.59,12L5,17.59L6.41,19L12,13.41L17.59,19L19,17.59L13.41,12L19,6.41Z"/></svg>
            </button>
          </div>
          <div class="eb-fullscreen-tabs" role="tablist" aria-label="Vollbildansicht">
            <button id="eb-tab-map" class="eb-fullscreen-tab active" role="tab" aria-selected="true">Karte</button>
            <button id="eb-tab-elevation" class="eb-fullscreen-tab" role="tab" aria-selected="false">Höhenmeter</button>
          </div>
          <div id="eb-fullscreen-map" class="eb-fullscreen-map"></div>
          <div id="eb-fullscreen-profile" class="eb-profile eb-hidden"></div>
          <div id="eb-fullscreen-meta" class="eb-fullscreen-meta"></div>
        </div>
      </div>
    `;
    while (wrap.firstChild) card.appendChild(wrap.firstChild);

    this._$("eb-prev").addEventListener("click", () => this._go(-1));
    this._$("eb-next").addEventListener("click", () => this._go(1));
    this._$("eb-date").addEventListener("change", (e) => this._jumpDate(e.target.value));
    this._$("eb-style").addEventListener("click", () => this._cycleMapStyle());
    this._$("eb-gpx").addEventListener("click", () => this._downloadCurrentGpx());
    this._$("eb-fullscreen").addEventListener("click", () => this._openFullscreen());
    this._$("eb-full-style").addEventListener("click", () => this._cycleMapStyle());
    this._$("eb-full-gpx").addEventListener("click", () => this._downloadCurrentGpx());
    this._$("eb-full-close").addEventListener("click", () => this._closeFullscreen());
    this._$("eb-tab-map").addEventListener("click", () => this._setFullscreenTab("map"));
    this._$("eb-tab-elevation").addEventListener("click", () => this._setFullscreenTab("elevation"));
    this._$("eb-full-prev").addEventListener("click", () => this._go(-1));
    this._$("eb-full-next").addEventListener("click", () => this._go(1));
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
          this._msg("Keine Fahrten für diesen Filter");
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
          this._msg("Keine Fahrten für diesen Filter");
        }
      });
    }

    this._updateStyleButtons();
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
      this._msg(this._filtersActive() ? "Keine Fahrten für diesen Filter" : "Keine Fahrten gefunden");
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

  /// Build the dropdown options for accounts and bikes based on _instances
  _populateFilterUI() {
    const accountSel = this._$("eb-filter-account");
    const bikeSel = this._$("eb-filter-bike");
    const accountWrap = this._$("eb-filter-account-wrap");
    if (!accountSel || !bikeSel) return;

    // Account dropdown: only show if more than one instance
    if (this._instances.length > 1) {
      const opts = ['<option value="all">Alle Konten</option>'];
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
    const bikeOpts = ['<option value="all">Alle Bikes</option>'];
    for (const b of bikes) {
      bikeOpts.push(`<option value="${b.id}">${this._escapeHtml(b.label)}</option>`);
    }
    bikeSel.innerHTML = bikeOpts.join("");
    // Reset bike filter if currently selected bike isn't in the new list
    if (this._filterBike !== "all" && !bikes.some((b) => b.id === this._filterBike)) {
      this._filterBike = "all";
    }
    bikeSel.value = this._filterBike;

    // Hide bike picker entirely if there's at most one bike total
    const bikeWrap = this._$("eb-filter-bike-wrap");
    if (bikeWrap) bikeWrap.style.display = bikes.length > 1 ? "" : "none";
  }

  _escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
    })[c]);
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
    this._$("eb-title").textContent = activity.title || "Unbenannte Fahrt";

    if (activity.startTime) {
      this._$("eb-date-lbl").textContent = new Date(activity.startTime).toLocaleDateString("de-DE", {
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
      <div class="eb-stat"><div class="eb-val">${dist} km</div><div class="eb-lbl">Distanz</div></div>
      <div class="eb-stat"><div class="eb-val">${dur} min</div><div class="eb-lbl">Dauer</div></div>
      <div class="eb-stat"><div class="eb-val">${avgS}</div><div class="eb-lbl">Ø km/h</div></div>
      <div class="eb-stat"><div class="eb-val">${maxS}</div><div class="eb-lbl">Max km/h</div></div>
      <div class="eb-stat"><div class="eb-val">${ele} m</div><div class="eb-lbl">Höhenmeter ↑</div></div>
      <div class="eb-stat"><div class="eb-val">${cal} kcal</div><div class="eb-lbl">Kalorien</div></div>
      <div class="eb-stat"><div class="eb-val">${difficulty} m/km</div><div class="eb-lbl">Schwierigkeit</div></div>
      <div class="eb-stat"><div class="eb-val">${battWh} Wh</div><div class="eb-lbl">Akku</div></div>
      <div class="eb-stat"><div class="eb-val">${battPct} %</div><div class="eb-lbl">Akku %</div></div>
    `;
    this._$("eb-stats").innerHTML = statsHtml;
    this._$("eb-fullscreen-title").textContent = activity.title || "Unbenannte Fahrt";
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
    this._msg("Lade Route …");

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

      this._destroyMap(true);
      if (this._fullscreenOpen) this._destroyFullscreenMap();

      if (!pts.length) {
        this._msg("Keine GPS-Punkte gefunden");
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
    } catch (error) {
      if (loadSeq < this._loadSeq) return;
      console.error("[Bosch eBike Map] track load error", error);
      this._msg("Fehler beim Laden der Route");
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
      this._msg("Fehler: Leaflet ist nicht verfügbar");
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
      this._msg("Fehler beim Erzeugen der Karte");
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
    this._fullscreenBaseLayer = null;

    const mapEl = this._$("eb-fullscreen-map");
    if (mapEl) mapEl.innerHTML = "";
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

    const Legend = Leaflet.Control.extend({
      options: { position: "bottomright" },
      onAdd() {
        const div = Leaflet.DomUtil.create("div");
        div.style.cssText = "background:rgba(255,255,255,.92);padding:6px 10px;border-radius:6px;font-size:11px;box-shadow:0 1px 5px rgba(0,0,0,.25);line-height:1.6";
        div.innerHTML =
          "<b>Speed</b><br>" +
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
      el.innerHTML = '<div class="eb-profile-title">Höhenprofil</div><div class="eb-profile-range">Keine Höhendaten verfügbar</div>';
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
      "Höhenprofil",
      `Min ${Math.round(minEle)} m · Max ${Math.round(maxEle)} m`,
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
        "Trittfrequenz",
        `Ø ${avgCadence != null ? Math.round(avgCadence) : '–'} rpm · Max ${maxCadence != null ? Math.round(maxCadence) : '–'} rpm`,
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
        "Leistung",
        `Ø ${avgPower != null ? Math.round(avgPower) : '–'} W · Max ${maxPower != null ? Math.round(maxPower) : '–'} W`,
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
        <div class="eb-profile-stat"><div class="eb-pv">${Math.round(ascent)} m</div><div class="eb-pl">Aufstieg</div></div>
        <div class="eb-profile-stat"><div class="eb-pv">${Math.round(descent)} m</div><div class="eb-pl">Abstieg</div></div>
        <div class="eb-profile-stat"><div class="eb-pv">${avgSpeed != null ? avgSpeed.toFixed(1).replace('.', ',') : '–'} km/h</div><div class="eb-pl">Ø Geschwindigkeit</div></div>
        <div class="eb-profile-stat"><div class="eb-pv">${maxSpeed != null ? maxSpeed.toFixed(1).replace('.', ',') : '–'} km/h</div><div class="eb-pl">Max Geschwindigkeit</div></div>
      </div>
    `;
  }


  _setFullscreenTab(tab) {
    const next = tab === "elevation" ? "elevation" : "map";
    this._fullscreenTab = next;
    const isMap = next === "map";
    const mapBtn = this._$("eb-tab-map");
    const eleBtn = this._$("eb-tab-elevation");
    const mapEl = this._$("eb-fullscreen-map");
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
    if (mapEl) mapEl.classList.toggle("eb-hidden", !isMap);
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
      this._msg("Kein GPX für diese Route verfügbar");
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
      this._msg("GPX-Download fehlgeschlagen");
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

class BoschEBikeMapCardEditor extends HTMLElement {
  setConfig(config) {
    this._config = config;
    this._render();
  }

  _render() {
    this.innerHTML = `<div style="padding:16px">
      <label style="display:block;margin-bottom:8px;font-weight:500">Kartenhöhe (px)</label>
      <input type="number" value="${this._config.height || 400}" min="200" max="1000" step="50"
        style="width:100%;padding:8px;border:1px solid #ccc;border-radius:4px" id="h-in">
    </div>`;

    this.querySelector("#h-in").addEventListener("change", (e) => {
      this._config = { ...this._config, height: parseInt(e.target.value, 10) || 400 };
      this.dispatchEvent(new CustomEvent("config-changed", { detail: { config: this._config } }));
    });
  }
}

if (!customElements.get("bosch-ebike-map-card")) {
  customElements.define("bosch-ebike-map-card", BoschEBikeMapCard);
}
if (!customElements.get("bosch-ebike-map-card-editor")) {
  customElements.define("bosch-ebike-map-card-editor", BoschEBikeMapCardEditor);
}

window.customCards = window.customCards || [];
if (!window.customCards.find((c) => c.type === "bosch-ebike-map-card")) {
  window.customCards.push({
    type: "bosch-ebike-map-card",
    name: "Bosch eBike Map",
    description: "Interaktive Karte mit GPS-Tracks deiner Bosch eBike-Fahrten",
    preview: true,
  });
}
