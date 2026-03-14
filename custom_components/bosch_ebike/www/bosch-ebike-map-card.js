/**
 * Bosch eBike Map Card for Home Assistant
 * Displays GPS tracks from Bosch eBike activities on an interactive map.
 */

const LEAFLET_VERSION = "1.9.4";
const LEAFLET_CSS = `https://unpkg.com/leaflet@${LEAFLET_VERSION}/dist/leaflet.css`;
const LEAFLET_JS = `https://unpkg.com/leaflet@${LEAFLET_VERSION}/dist/leaflet.js`;

// Load Leaflet globally (once)
function loadLeaflet() {
  if (window.__leafletLoading) return window.__leafletLoading;
  if (window.L) return Promise.resolve();

  window.__leafletLoading = new Promise((resolve, reject) => {
    // CSS
    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = LEAFLET_CSS;
    document.head.appendChild(link);

    // JS
    const script = document.createElement("script");
    script.src = LEAFLET_JS;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error("Failed to load Leaflet"));
    document.head.appendChild(script);
  });

  return window.__leafletLoading;
}

class BoschEBikeMapCard extends HTMLElement {
  constructor() {
    super();
    this._hass = null;
    this._config = {};
    this._activities = [];
    this._currentIndex = 0;
    this._map = null;
    this._trackLayer = null;
    this._legendControl = null;
    this._loading = false;
    this._initialized = false;
  }

  setConfig(config) {
    this._config = {
      height: config.height || 400,
      ...config,
    };
    if (this._initialized) {
      const mapEl = this.querySelector("#ebike-map");
      if (mapEl) mapEl.style.height = `${this._config.height}px`;
    }
  }

  set hass(hass) {
    const firstSet = !this._hass;
    this._hass = hass;
    if (firstSet) {
      this._initialize();
    }
  }

  async _initialize() {
    if (this._initialized) return;
    this._initialized = true;
    this._buildHTML();
    await loadLeaflet();
    await this._loadActivities();
  }

  _buildHTML() {
    const h = this._config.height || 400;

    this.innerHTML = `
      <ha-card>
        <style>
          .ebike-header {
            display: flex;
            align-items: center;
            padding: 12px 16px;
            background: var(--primary-color, #03a9f4);
            color: white;
            font-size: 16px;
            font-weight: 500;
            gap: 8px;
          }
          .ebike-header svg { width: 22px; height: 22px; fill: white; }
          .ebike-nav {
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 8px 12px;
            background: var(--secondary-background-color, #f5f5f5);
            border-bottom: 1px solid var(--divider-color, #e0e0e0);
          }
          .ebike-nav button {
            background: var(--primary-color, #03a9f4);
            color: white;
            border: none;
            border-radius: 6px;
            width: 36px; height: 36px;
            cursor: pointer;
            font-size: 16px;
            display: flex;
            align-items: center;
            justify-content: center;
            flex-shrink: 0;
          }
          .ebike-nav button:hover { opacity: 0.85; }
          .ebike-nav button:disabled { opacity: 0.35; cursor: not-allowed; }
          .ebike-nav input[type="date"] {
            flex: 1;
            min-width: 0;
            padding: 6px 10px;
            border: 1px solid var(--divider-color, #ccc);
            border-radius: 6px;
            font-size: 14px;
            background: var(--card-background-color, white);
            color: var(--primary-text-color, #333);
          }
          .ebike-nav .counter {
            font-size: 13px;
            color: var(--secondary-text-color, #666);
            white-space: nowrap;
            flex-shrink: 0;
          }
          #ebike-map {
            width: 100%;
            height: ${h}px;
            z-index: 0;
          }
          .ebike-ride-title {
            text-align: center;
            padding: 10px 16px 2px;
            font-size: 16px;
            font-weight: 600;
            color: var(--primary-text-color, #333);
          }
          .ebike-ride-date {
            text-align: center;
            font-size: 12px;
            color: var(--secondary-text-color, #666);
            padding: 0 16px 6px;
          }
          .ebike-stats {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 4px;
            padding: 8px 16px 14px;
          }
          .ebike-stat {
            text-align: center;
          }
          .ebike-stat .val {
            font-size: 20px;
            font-weight: 700;
            color: var(--primary-text-color, #212121);
          }
          .ebike-stat .lbl {
            font-size: 11px;
            color: var(--secondary-text-color, #757575);
            margin-top: 1px;
          }
          .ebike-loading, .ebike-nodata {
            display: flex;
            align-items: center;
            justify-content: center;
            height: ${h}px;
            color: var(--secondary-text-color, #999);
            font-size: 14px;
          }
          .ebike-spinner {
            width: 24px; height: 24px;
            border: 3px solid var(--divider-color, #ddd);
            border-top-color: var(--primary-color, #03a9f4);
            border-radius: 50%;
            animation: ebike-spin 0.8s linear infinite;
            margin-right: 10px;
          }
          @keyframes ebike-spin { to { transform: rotate(360deg); } }
        </style>

        <div class="ebike-header">
          <svg viewBox="0 0 24 24"><path d="M15.5,5.5C16.9,5.5 18,6.6 18,8C18,9.4 16.9,10.5 15.5,10.5C14.1,10.5 13,9.4 13,8C13,6.6 14.1,5.5 15.5,5.5M5,12C2.2,12 0,14.2 0,17C0,19.8 2.2,22 5,22C7.8,22 10,19.8 10,17C10,14.2 7.8,12 5,12M5,20.5C3.1,20.5 1.5,18.9 1.5,17C1.5,15.1 3.1,13.5 5,13.5C6.9,13.5 8.5,15.1 8.5,17C8.5,18.9 6.9,20.5 5,20.5M19,12C16.2,12 14,14.2 14,17C14,19.8 16.2,22 19,22C21.8,22 24,19.8 24,17C24,14.2 21.8,12 19,12M19,20.5C17.1,20.5 15.5,18.9 15.5,17C15.5,15.1 17.1,13.5 19,13.5C20.9,13.5 22.5,15.1 22.5,17C22.5,18.9 20.9,20.5 19,20.5M12.5,11.5L10.1,8.8L10.2,8.6C10.6,7.8 11.4,7.3 12.3,7.3H14.2L12.9,6H10.3C9.1,6 8,6.7 7.5,7.8L6.1,10.8L5,12.1L7.2,13.5L8.3,11.5H12.5Z"/></svg>
          Bosch eBike Rides
        </div>

        <div class="ebike-nav">
          <button id="ebike-prev" title="Vorherige Fahrt">◀</button>
          <input type="date" id="ebike-date" />
          <button id="ebike-next" title="Nächste Fahrt">▶</button>
          <span class="counter" id="ebike-counter">–</span>
        </div>

        <div id="ebike-map-wrap">
          <div class="ebike-loading" id="ebike-loading">
            <div class="ebike-spinner"></div>
            Lade Fahrten...
          </div>
        </div>

        <div class="ebike-ride-title" id="ebike-title"></div>
        <div class="ebike-ride-date" id="ebike-date-label"></div>
        <div class="ebike-stats" id="ebike-stats"></div>
      </ha-card>
    `;

    this.querySelector("#ebike-prev").addEventListener("click", () => this._navigate(-1));
    this.querySelector("#ebike-next").addEventListener("click", () => this._navigate(1));
    this.querySelector("#ebike-date").addEventListener("change", (e) => this._jumpToDate(e.target.value));
  }

  async _loadActivities() {
    if (!this._hass) return;

    try {
      const result = await this._hass.callWS({ type: "bosch_ebike/list_activities" });
      this._activities = (result.activities || []).sort(
        (a, b) => new Date(b.startTime) - new Date(a.startTime)
      );

      const wrap = this.querySelector("#ebike-map-wrap");
      if (this._activities.length === 0) {
        wrap.innerHTML = '<div class="ebike-nodata">Keine Fahrten gefunden</div>';
        return;
      }

      // Replace loading with map
      wrap.innerHTML = `<div id="ebike-map" style="width:100%;height:${this._config.height || 400}px"></div>`;

      // Small delay so DOM can settle
      await new Promise((r) => setTimeout(r, 50));

      this._initMap();
      this._currentIndex = 0;
      this._showActivity(0);
    } catch (err) {
      console.error("eBike Map: Failed to load activities:", err);
      const wrap = this.querySelector("#ebike-map-wrap");
      if (wrap) wrap.innerHTML = `<div class="ebike-nodata">Fehler: ${err.message || err}</div>`;
    }
  }

  _initMap() {
    const mapEl = this.querySelector("#ebike-map");
    if (!mapEl || this._map) return;

    this._map = L.map(mapEl, {
      zoomControl: true,
      attributionControl: false,
    }).setView([48.7, 12.4], 10);

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: '© <a href="https://openstreetmap.org">OSM</a>',
      maxZoom: 19,
    }).addTo(this._map);

    this._trackLayer = L.layerGroup().addTo(this._map);

    // Force correct sizing
    setTimeout(() => this._map.invalidateSize(), 200);
    setTimeout(() => this._map.invalidateSize(), 600);
  }

  async _showActivity(index) {
    if (index < 0 || index >= this._activities.length) return;
    this._currentIndex = index;
    const activity = this._activities[index];

    this._updateNav(activity);
    this._updateInfo(activity);
    await this._loadTrack(activity.id);
  }

  _updateNav(activity) {
    const dp = this.querySelector("#ebike-date");
    const ctr = this.querySelector("#ebike-counter");
    const prev = this.querySelector("#ebike-prev");
    const next = this.querySelector("#ebike-next");

    if (activity.startTime) dp.value = activity.startTime.substring(0, 10);
    ctr.textContent = `${this._currentIndex + 1} / ${this._activities.length}`;
    prev.disabled = this._currentIndex <= 0;
    next.disabled = this._currentIndex >= this._activities.length - 1;
  }

  _updateInfo(activity) {
    const titleEl = this.querySelector("#ebike-title");
    const dateEl = this.querySelector("#ebike-date-label");
    const statsEl = this.querySelector("#ebike-stats");

    titleEl.textContent = activity.title || "Unbenannte Fahrt";

    if (activity.startTime) {
      const d = new Date(activity.startTime);
      dateEl.textContent = d.toLocaleDateString("de-DE", {
        weekday: "long", year: "numeric", month: "long", day: "numeric",
        hour: "2-digit", minute: "2-digit",
      });
    }

    const dist = activity.distance ? (activity.distance / 1000).toFixed(1) : "–";
    const dur = activity.durationWithoutStops ? Math.round(activity.durationWithoutStops / 60) : "–";
    const avgSpd = activity.speed?.average ? (activity.speed.average * 3.6).toFixed(1) : "–";
    const maxSpd = activity.speed?.maximum ? (activity.speed.maximum * 3.6).toFixed(1) : "–";
    const eleGain = activity.elevation?.gain != null ? Math.round(activity.elevation.gain) : "–";
    const cal = activity.caloriesBurned ? Math.round(activity.caloriesBurned) : "–";

    statsEl.innerHTML = `
      <div class="ebike-stat"><div class="val">${dist} km</div><div class="lbl">Distanz</div></div>
      <div class="ebike-stat"><div class="val">${dur} min</div><div class="lbl">Dauer</div></div>
      <div class="ebike-stat"><div class="val">${avgSpd}</div><div class="lbl">Ø km/h</div></div>
      <div class="ebike-stat"><div class="val">${maxSpd}</div><div class="lbl">Max km/h</div></div>
      <div class="ebike-stat"><div class="val">${eleGain} m</div><div class="lbl">Höhenmeter ↑</div></div>
      <div class="ebike-stat"><div class="val">${cal} kcal</div><div class="lbl">Kalorien</div></div>
    `;
  }

  async _loadTrack(activityId) {
    if (!this._hass || !this._map || this._loading) return;
    this._loading = true;

    try {
      const result = await this._hass.callWS({
        type: "bosch_ebike/get_track",
        activity_id: activityId,
      });

      const track = result.track || [];
      this._trackLayer.clearLayers();

      // Remove old legend
      if (this._legendControl) {
        this._map.removeControl(this._legendControl);
        this._legendControl = null;
      }

      if (track.length === 0) {
        this._map.setView([48.7, 12.4], 8);
        return;
      }

      // Speed is in m/s from API — convert to km/h for coloring
      for (let i = 0; i < track.length - 1; i++) {
        const speedMs = track[i].speed || 0;
        const speedKmh = speedMs * 3.6;
        const color = this._speedColor(speedKmh);
        const seg = L.polyline(
          [[track[i].lat, track[i].lon], [track[i + 1].lat, track[i + 1].lon]],
          { color, weight: 5, opacity: 0.9 }
        );
        this._trackLayer.addLayer(seg);
      }

      // Start marker (green)
      const startIcon = L.divIcon({
        className: "ebike-marker",
        html: '<div style="width:16px;height:16px;background:#4CAF50;border:3px solid white;border-radius:50%;box-shadow:0 2px 6px rgba(0,0,0,0.4)"></div>',
        iconSize: [16, 16],
        iconAnchor: [8, 8],
      });
      L.marker([track[0].lat, track[0].lon], { icon: startIcon, title: "Start" })
        .addTo(this._trackLayer);

      // End marker (red)
      const last = track[track.length - 1];
      const endIcon = L.divIcon({
        className: "ebike-marker",
        html: '<div style="width:16px;height:16px;background:#f44336;border:3px solid white;border-radius:50%;box-shadow:0 2px 6px rgba(0,0,0,0.4)"></div>',
        iconSize: [16, 16],
        iconAnchor: [8, 8],
      });
      L.marker([last.lat, last.lon], { icon: endIcon, title: "Ziel" })
        .addTo(this._trackLayer);

      // Fit bounds
      const coords = track.map((p) => [p.lat, p.lon]);
      this._map.fitBounds(L.latLngBounds(coords), { padding: [40, 40] });

      // Speed legend as Leaflet control
      this._addLegend();

    } catch (err) {
      console.error("eBike Map: Failed to load track:", err);
    } finally {
      this._loading = false;
    }
  }

  _speedColor(kmh) {
    if (kmh <= 5) return "#2196F3";      // blue - slow / stopped
    if (kmh <= 12) return "#4CAF50";     // green
    if (kmh <= 20) return "#8BC34A";     // light green
    if (kmh <= 27) return "#FFC107";     // yellow
    if (kmh <= 33) return "#FF9800";     // orange
    return "#f44336";                     // red - fast
  }

  _addLegend() {
    const LegendControl = L.Control.extend({
      options: { position: "bottomright" },
      onAdd: function () {
        const div = L.DomUtil.create("div", "ebike-legend");
        div.style.cssText =
          "background:rgba(255,255,255,0.92);padding:6px 10px;border-radius:6px;" +
          "font-size:11px;box-shadow:0 1px 5px rgba(0,0,0,0.25);line-height:1.5;" +
          "font-family:var(--paper-font-body1_-_font-family,Roboto,sans-serif)";
        div.innerHTML =
          '<b>Speed</b><br>' +
          '<span style="background:#2196F3;display:inline-block;width:14px;height:3px;border-radius:2px;vertical-align:middle"></span> 0 ' +
          '<span style="background:#4CAF50;display:inline-block;width:14px;height:3px;border-radius:2px;vertical-align:middle"></span> 12 ' +
          '<span style="background:#FFC107;display:inline-block;width:14px;height:3px;border-radius:2px;vertical-align:middle"></span> 25 ' +
          '<span style="background:#f44336;display:inline-block;width:14px;height:3px;border-radius:2px;vertical-align:middle"></span> 35+ km/h';
        return div;
      },
    });
    this._legendControl = new LegendControl();
    this._map.addControl(this._legendControl);
  }

  _navigate(direction) {
    const idx = this._currentIndex + direction;
    if (idx >= 0 && idx < this._activities.length) {
      this._showActivity(idx);
    }
  }

  _jumpToDate(dateStr) {
    if (!dateStr) return;
    let bestIdx = 0;
    let bestDiff = Infinity;
    const target = new Date(dateStr).getTime();
    this._activities.forEach((a, i) => {
      const diff = Math.abs(new Date(a.startTime).getTime() - target);
      if (diff < bestDiff) { bestDiff = diff; bestIdx = i; }
    });
    this._showActivity(bestIdx);
  }

  getCardSize() {
    return Math.ceil((this._config.height || 400) / 50) + 3;
  }

  static getConfigElement() {
    return document.createElement("bosch-ebike-map-card-editor");
  }

  static getStubConfig() {
    return { height: 400 };
  }
}

// Simple editor
class BoschEBikeMapCardEditor extends HTMLElement {
  setConfig(config) {
    this._config = config;
    this._render();
  }

  _render() {
    this.innerHTML = `
      <div style="padding:16px">
        <label style="display:block;margin-bottom:8px;font-weight:500">Kartenhöhe (px)</label>
        <input type="number" value="${this._config.height || 400}" min="200" max="1000" step="50"
          style="width:100%;padding:8px;border:1px solid #ccc;border-radius:4px" id="h-input" />
      </div>
    `;
    this.querySelector("#h-input").addEventListener("change", (e) => {
      this._config = { ...this._config, height: parseInt(e.target.value) || 400 };
      this.dispatchEvent(new CustomEvent("config-changed", { detail: { config: this._config } }));
    });
  }
}

customElements.define("bosch-ebike-map-card", BoschEBikeMapCard);
customElements.define("bosch-ebike-map-card-editor", BoschEBikeMapCardEditor);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "bosch-ebike-map-card",
  name: "Bosch eBike Map",
  description: "Interaktive Karte mit GPS-Tracks deiner Bosch eBike-Fahrten",
  preview: true,
});
