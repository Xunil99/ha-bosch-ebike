/**
 * Bosch eBike Map Card for Home Assistant
 * Displays GPS tracks from Bosch eBike activities on an interactive map.
 */

const LEAFLET_CSS = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css";
const LEAFLET_JS = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js";

// Global Leaflet loader (singleton)
if (!window.__ebikeLeaflet) {
  window.__ebikeLeaflet = null;
}

function ensureLeaflet() {
  if (window.L) return Promise.resolve();
  if (window.__ebikeLeaflet) return window.__ebikeLeaflet;

  window.__ebikeLeaflet = new Promise((resolve, reject) => {
    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = LEAFLET_CSS;
    document.head.appendChild(link);

    const script = document.createElement("script");
    script.src = LEAFLET_JS;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error("Leaflet load failed"));
    document.head.appendChild(script);
  });
  return window.__ebikeLeaflet;
}

class BoschEBikeMapCard extends HTMLElement {
  constructor() {
    super();
    this._hass = null;
    this._config = {};
    this._activities = [];
    this._idx = 0;
    this._map = null;
    this._trackGroup = null;
    this._legend = null;
    this._busy = false;
    this._ready = false;
  }

  /* ── HA hooks ─────────────────────────────────────── */

  setConfig(config) {
    this._config = { height: config.height || 400, ...config };
  }

  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    if (first) this._boot();
  }

  getCardSize() {
    return Math.ceil((this._config.height || 400) / 50) + 4;
  }

  static getConfigElement() {
    return document.createElement("bosch-ebike-map-card-editor");
  }

  static getStubConfig() {
    return { height: 400 };
  }

  /* ── Bootstrap ────────────────────────────────────── */

  async _boot() {
    if (this._ready) return;
    this._ready = true;
    this._buildDOM();
    try {
      await ensureLeaflet();
      await this._fetchActivities();
    } catch (e) {
      console.error("[eBike Map] boot error:", e);
      this._showMsg("Fehler: " + e.message);
    }
  }

  /* ── DOM ──────────────────────────────────────────── */

  _buildDOM() {
    const h = this._config.height || 400;
    this.innerHTML = "";

    const card = document.createElement("ha-card");
    card.innerHTML = `
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
      <div id="eb-map" style="width:100%;height:${h}px;background:#eee"></div>
      <div id="eb-title" class="eb-title"></div>
      <div id="eb-date-lbl" class="eb-datelbl"></div>
      <div id="eb-stats" class="eb-stats"></div>
    `;
    this.appendChild(card);

    // Inject scoped styles
    const style = document.createElement("style");
    style.textContent = `
      ha-card { overflow: hidden; }
      .eb-head {
        display:flex; align-items:center; gap:8px;
        padding:12px 16px;
        background:var(--primary-color,#03a9f4);
        color:white; font-size:16px; font-weight:500;
      }
      .eb-nav {
        display:flex; align-items:center; gap:8px;
        padding:8px 12px;
        background:var(--secondary-background-color,#f5f5f5);
        border-bottom:1px solid var(--divider-color,#e0e0e0);
      }
      .eb-nav button {
        width:36px; height:36px; flex-shrink:0;
        background:var(--primary-color,#03a9f4); color:white;
        border:none; border-radius:6px; cursor:pointer; font-size:16px;
      }
      .eb-nav button:disabled { opacity:0.35; cursor:not-allowed; }
      .eb-nav input[type="date"] {
        flex:1; min-width:0; padding:6px 10px;
        border:1px solid var(--divider-color,#ccc);
        border-radius:6px; font-size:14px;
        background:var(--card-background-color,white);
        color:var(--primary-text-color,#333);
      }
      .eb-ctr { font-size:13px; color:var(--secondary-text-color,#666); white-space:nowrap; flex-shrink:0; }
      #eb-map { z-index:0; }
      .eb-title { text-align:center; padding:10px 16px 2px; font-size:16px; font-weight:600; color:var(--primary-text-color,#333); }
      .eb-datelbl { text-align:center; font-size:12px; color:var(--secondary-text-color,#666); padding:0 16px 6px; }
      .eb-stats {
        display:grid; grid-template-columns:repeat(3,1fr);
        gap:4px; padding:8px 16px 14px;
      }
      .eb-stat { text-align:center; }
      .eb-val { font-size:20px; font-weight:700; color:var(--primary-text-color,#212121); }
      .eb-lbl { font-size:11px; color:var(--secondary-text-color,#757575); }
      .eb-msg { display:flex; align-items:center; justify-content:center; height:100%; color:var(--secondary-text-color,#999); font-size:14px; }
    `;
    card.prepend(style);

    // Events
    card.querySelector("#eb-prev").addEventListener("click", () => this._go(-1));
    card.querySelector("#eb-next").addEventListener("click", () => this._go(1));
    card.querySelector("#eb-date").addEventListener("change", (e) => this._jumpDate(e.target.value));
  }

  _el(id) { return this.querySelector("#" + id); }

  _showMsg(text) {
    const m = this._el("eb-map");
    if (m) m.innerHTML = `<div class="eb-msg">${text}</div>`;
  }

  /* ── Data loading ─────────────────────────────────── */

  async _fetchActivities() {
    const res = await this._hass.callWS({ type: "bosch_ebike/list_activities" });
    this._activities = (res.activities || []).sort(
      (a, b) => new Date(b.startTime) - new Date(a.startTime)
    );

    console.log("[eBike Map] Loaded", this._activities.length, "activities");

    if (!this._activities.length) {
      this._showMsg("Keine Fahrten gefunden");
      return;
    }

    this._initMap();
    this._show(0);
  }

  /* ── Map ──────────────────────────────────────────── */

  _initMap() {
    const el = this._el("eb-map");
    if (!el || this._map) return;

    this._map = L.map(el, { zoomControl: true, attributionControl: false })
      .setView([48.7, 12.4], 10);

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
    }).addTo(this._map);

    this._trackGroup = L.layerGroup().addTo(this._map);

    // Ensure correct sizing
    requestAnimationFrame(() => this._map.invalidateSize());
    setTimeout(() => this._map.invalidateSize(), 300);
    setTimeout(() => this._map.invalidateSize(), 1000);

    // Resize observer for dynamic layout changes
    if (window.ResizeObserver) {
      new ResizeObserver(() => {
        if (this._map) this._map.invalidateSize();
      }).observe(el);
    }
  }

  async _show(index) {
    if (index < 0 || index >= this._activities.length) return;
    this._idx = index;
    const act = this._activities[index];

    // Nav
    const dp = this._el("eb-date");
    if (act.startTime) dp.value = act.startTime.substring(0, 10);
    this._el("eb-ctr").textContent = `${index + 1} / ${this._activities.length}`;
    this._el("eb-prev").disabled = index <= 0;
    this._el("eb-next").disabled = index >= this._activities.length - 1;

    // Info
    this._el("eb-title").textContent = act.title || "Unbenannte Fahrt";
    if (act.startTime) {
      this._el("eb-date-lbl").textContent = new Date(act.startTime).toLocaleDateString("de-DE", {
        weekday: "long", year: "numeric", month: "long", day: "numeric",
        hour: "2-digit", minute: "2-digit",
      });
    }

    // Stats — speed values from activity summary are already in km/h
    const dist = act.distance ? (act.distance / 1000).toFixed(1) : "–";
    const dur = act.durationWithoutStops ? Math.round(act.durationWithoutStops / 60) : "–";
    const avgSpd = act.speed?.average != null ? act.speed.average.toFixed(1) : "–";
    const maxSpd = act.speed?.maximum != null ? act.speed.maximum.toFixed(1) : "–";
    const ele = act.elevation?.gain != null ? Math.round(act.elevation.gain) : "–";
    const cal = act.caloriesBurned != null ? Math.round(act.caloriesBurned) : "–";

    this._el("eb-stats").innerHTML = `
      <div class="eb-stat"><div class="eb-val">${dist} km</div><div class="eb-lbl">Distanz</div></div>
      <div class="eb-stat"><div class="eb-val">${dur} min</div><div class="eb-lbl">Dauer</div></div>
      <div class="eb-stat"><div class="eb-val">${avgSpd}</div><div class="eb-lbl">Ø km/h</div></div>
      <div class="eb-stat"><div class="eb-val">${maxSpd}</div><div class="eb-lbl">Max km/h</div></div>
      <div class="eb-stat"><div class="eb-val">${ele} m</div><div class="eb-lbl">Höhenmeter ↑</div></div>
      <div class="eb-stat"><div class="eb-val">${cal} kcal</div><div class="eb-lbl">Kalorien</div></div>
    `;

    // Track
    await this._loadTrack(act.id);
  }

  async _loadTrack(activityId) {
    if (!this._map || this._busy) return;
    this._busy = true;

    try {
      console.log("[eBike Map] Loading track for", activityId);
      const res = await this._hass.callWS({
        type: "bosch_ebike/get_track",
        activity_id: activityId,
      });

      const pts = res.track || [];
      console.log("[eBike Map] Got", pts.length, "track points");

      this._trackGroup.clearLayers();
      if (this._legend) { this._map.removeControl(this._legend); this._legend = null; }

      if (!pts.length) {
        console.warn("[eBike Map] No GPS points for this activity");
        return;
      }

      // Draw speed-colored segments
      // Speed from track detail points is in m/s → convert to km/h
      for (let i = 0; i < pts.length - 1; i++) {
        const rawSpeed = pts[i].speed || 0;
        // Track detail points: speed is in m/s
        const kmh = rawSpeed * 3.6;
        const color = this._color(kmh);
        L.polyline(
          [[pts[i].lat, pts[i].lon], [pts[i + 1].lat, pts[i + 1].lon]],
          { color, weight: 5, opacity: 0.9 }
        ).addTo(this._trackGroup);
      }

      // Start marker
      L.circleMarker([pts[0].lat, pts[0].lon], {
        radius: 8, fillColor: "#4CAF50", color: "#fff", weight: 3, fillOpacity: 1,
      }).bindTooltip("Start").addTo(this._trackGroup);

      // End marker
      const last = pts[pts.length - 1];
      L.circleMarker([last.lat, last.lon], {
        radius: 8, fillColor: "#f44336", color: "#fff", weight: 3, fillOpacity: 1,
      }).bindTooltip("Ziel").addTo(this._trackGroup);

      // Zoom to track
      const bounds = L.latLngBounds(pts.map(p => [p.lat, p.lon]));
      this._map.fitBounds(bounds, { padding: [40, 40] });

      // Legend
      this._addLegend();

      console.log("[eBike Map] Track rendered successfully");
    } catch (err) {
      console.error("[eBike Map] Track load error:", err);
    } finally {
      this._busy = false;
    }
  }

  _color(kmh) {
    if (kmh <= 5)  return "#2196F3";
    if (kmh <= 12) return "#4CAF50";
    if (kmh <= 20) return "#8BC34A";
    if (kmh <= 27) return "#FFC107";
    if (kmh <= 33) return "#FF9800";
    return "#f44336";
  }

  _addLegend() {
    const Ctrl = L.Control.extend({
      options: { position: "bottomright" },
      onAdd() {
        const d = L.DomUtil.create("div");
        d.style.cssText = "background:rgba(255,255,255,.92);padding:6px 10px;border-radius:6px;font-size:11px;box-shadow:0 1px 5px rgba(0,0,0,.25);line-height:1.6";
        d.innerHTML =
          "<b>Speed</b><br>" +
          '<i style="background:#2196F3;width:14px;height:3px;display:inline-block;border-radius:2px;vertical-align:middle"></i> 0 ' +
          '<i style="background:#4CAF50;width:14px;height:3px;display:inline-block;border-radius:2px;vertical-align:middle"></i> 12 ' +
          '<i style="background:#FFC107;width:14px;height:3px;display:inline-block;border-radius:2px;vertical-align:middle"></i> 25 ' +
          '<i style="background:#f44336;width:14px;height:3px;display:inline-block;border-radius:2px;vertical-align:middle"></i> 35+ km/h';
        return d;
      },
    });
    this._legend = new Ctrl();
    this._map.addControl(this._legend);
  }

  /* ── Navigation ───────────────────────────────────── */

  _go(dir) {
    const n = this._idx + dir;
    if (n >= 0 && n < this._activities.length) this._show(n);
  }

  _jumpDate(str) {
    if (!str) return;
    const t = new Date(str).getTime();
    let best = 0, bestD = Infinity;
    this._activities.forEach((a, i) => {
      const d = Math.abs(new Date(a.startTime).getTime() - t);
      if (d < bestD) { bestD = d; best = i; }
    });
    this._show(best);
  }
}

/* ── Editor ─────────────────────────────────────────── */

class BoschEBikeMapCardEditor extends HTMLElement {
  setConfig(config) { this._config = config; this._render(); }
  _render() {
    this.innerHTML = `<div style="padding:16px">
      <label style="display:block;margin-bottom:8px;font-weight:500">Kartenhöhe (px)</label>
      <input type="number" value="${this._config.height || 400}" min="200" max="1000" step="50"
        style="width:100%;padding:8px;border:1px solid #ccc;border-radius:4px" id="h-in">
    </div>`;
    this.querySelector("#h-in").addEventListener("change", (e) => {
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
