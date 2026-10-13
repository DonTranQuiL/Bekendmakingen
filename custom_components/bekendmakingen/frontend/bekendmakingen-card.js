/*
 * Bekendmakingen card for Home Assistant.
 * Shipped with the Bekendmakingen integration and registered automatically.
 *   type: custom:bekendmakingen-card
 *   entity: sensor.bekendmakingen_utrecht
 */
const CARD_VERSION = "2.1.0";

const CATS = {
  aanvragen: { label: "Aanvragen", color: "#3b82f6", icon: "M6 2h9l5 5v15H6zM14 3v5h5M9 13h8M9 17h6" },
  verleend: { label: "Verleend", color: "#22a565", icon: "M4 12.5l5 5L20 6.5" },
  geweigerd: { label: "Geweigerd", color: "#e5484d", icon: "M6 6l12 12M18 6L6 18" },
  verkeer: { label: "Verkeer", color: "#f59e0b", icon: "M12 3l9 17H3zM12 10v4M12 17v.5" },
  meldingen: { label: "Meldingen", color: "#8b5cf6", icon: "M6 17V11a6 6 0 0112 0v6l2 2H4zM10 21h4" },
  overig: { label: "Overig", color: "#64748b", icon: "M5 12h.5M12 12h.5M19 12h.5" },
};
const CAT_KEYS = Object.keys(CATS);
const PERIODS = [
  ["all", "Alles"],
  ["today", "Vandaag"],
  ["week", "7 dagen"],
  ["month", "30 dagen"],
];
const DAY = 86400000;
const SEEN_KEY = "bekendmakingen-card-seen";

const esc = (v) =>
  String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const safeUrl = (u) => (typeof u === "string" && /^https:\/\//i.test(u) ? u : "");
const svg = (path, size = 16) =>
  `<svg viewBox="0 0 24 24" width="${size}" height="${size}" aria-hidden="true"><path d="${path}" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
const ICON_REFRESH = "M20 11a8 8 0 10-2.3 5.7M20 4v7h-7";
const ICON_PIN = "M12 21s-7-6.2-7-11.5A7 7 0 0119 9.5C19 14.8 12 21 12 21zM12 12a2.5 2.5 0 100-5 2.5 2.5 0 000 5z";
const ICON_SEARCH = "M11 18a7 7 0 100-14 7 7 0 000 14zM20 20l-4-4";
const ICON_CLOCK = "M12 21a9 9 0 100-18 9 9 0 000 18zM12 7v5l3 2";
const ICON_EXT = "M14 4h6v6M20 4l-9 9M18 14v6H4V6h6";
const ICON_FILE = "M6 2h9l5 5v15H6zM14 3v5h5";

function startOfDay(d) {
  const x = new Date(d);
  x.setHours(0, 0, 0, 0);
  return x;
}
function itemDate(item) {
  const raw = item.published || (item.date && item.date !== "Onbekend" ? `${item.date}T${item.time || "00:00"}` : null);
  const d = raw ? new Date(raw) : null;
  return d && !isNaN(d) ? d : null;
}
function fmtDate(d) {
  return d ? d.toLocaleDateString("nl-NL", { weekday: "short", day: "numeric", month: "short" }) : "Onbekend";
}
function daysUntil(iso, now) {
  if (!iso) return null;
  const d = new Date(`${iso}T23:59:59`);
  if (isNaN(d)) return null;
  return Math.ceil((startOfDay(d) - startOfDay(now)) / DAY);
}
function fmtKm(km) {
  if (km === null || km === undefined || isNaN(km)) return "";
  return km < 1 ? `${Math.round(km * 1000)} m` : `${km.toLocaleString("nl-NL", { maximumFractionDigits: 1 })} km`;
}
function relAgo(d, now) {
  if (!d) return "";
  const mins = Math.round((now - d) / 60000);
  if (mins < 1) return "zojuist";
  if (mins < 60) return `${mins} min geleden`;
  const h = Math.round(mins / 60);
  if (h < 24) return `${h} uur geleden`;
  const days = Math.round(h / 24);
  return days === 1 ? "gisteren" : `${days} dagen geleden`;
}

class BekendmakingenCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._filters = { cats: new Set(), period: "all", q: "" };
    this._open = null;
    this._seen = this._loadSeen();
    this._busy = false;
  }

  static getConfigElement() {
    return document.createElement("bekendmakingen-card-editor");
  }

  static getStubConfig(hass) {
    const states = hass?.states || {};
    const entity =
      Object.keys(states).find((id) => id.startsWith("sensor.") && Array.isArray(states[id].attributes?.items)) ||
      Object.keys(states).find((id) => id.startsWith("sensor.bekendmakingen") && "history" in (states[id].attributes || {})) ||
      "";
    return { entity };
  }

  setConfig(config) {
    if (!config || typeof config !== "object") throw new Error("Ongeldige configuratie");
    if (config.entity !== undefined && typeof config.entity !== "string") throw new Error("entity moet een tekst zijn");
    this._config = {
      show_map: true,
      show_counters: true,
      show_search: true,
      max_items: 25,
      new_hours: 24,
      max_distance_km: 0,
      compact: false,
      ...config,
    };
    if (Array.isArray(config.categories)) this._filters.cats = new Set(config.categories.filter((c) => CATS[c]));
    this._stateObj = undefined;
    if (this._hass) this._render();
  }

  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    const id = this._config?.entity;
    const st = id ? hass.states[id] : undefined;
    const diag = this._diagIds().map((d) => hass.states[d]);
    const same = st === this._stateObj && diag.every((s, i) => s === this._diag?.[i]);
    if (!first && same) return;
    this._stateObj = st;
    this._diag = diag;
    this._render();
  }

  getCardSize() {
    return this._config?.compact ? 5 : 9;
  }

  // ---------------------------------------------------------------- data
  _diagIds() {
    const id = this._config?.entity;
    if (!id || !this._hass) return [];
    const reg = this._hass.entities || {};
    const dev = reg[id]?.device_id;
    const ids = dev ? Object.keys(reg).filter((e) => reg[e].device_id === dev) : [];
    const pick = (suffix) => ids.find((e) => e.endsWith(suffix)) || `${id}_${suffix.replace(/^_/, "")}`;
    return [pick("_last_update_status"), pick("_last_update_time"), pick("_consecutive_errors")];
  }

  _items() {
    const st = this._stateObj;
    if (!st || !st.attributes) return [];
    const a = st.attributes;
    let items = Array.isArray(a.items) ? a.items : null;
    if (!items) {
      if (!a.link && !(a.history || []).length) return [];
      items = [{ title: st.state, date: a.date, time: a.time, link: a.link, summary: a.summary, detailed_description: a.detailed_description }, ...(a.history || [])];
    }
    return items
      .filter((i) => i && typeof i === "object")
      .map((i, n) => ({
        ...i,
        id: i.id || i.link || `item-${n}`,
        category: CATS[i.category] ? i.category : "overig",
        _date: itemDate(i),
      }));
  }

  _isNew(item, now) {
    const hours = Number(this._config.new_hours) || 24;
    return !!item._date && now - item._date < hours * 3600000 && !this._seen.has(item.id);
  }

  _filtered(items, now) {
    const f = this._filters;
    const today = startOfDay(now);
    const limit = { today: 0, week: 6, month: 29 }[f.period];
    const q = f.q.trim().toLowerCase();
    const maxKm = Number(this._config.max_distance_km) || 0;
    return items.filter((i) => {
      if (f.cats.size && !f.cats.has(i.category)) return false;
      if (limit !== undefined && (!i._date || startOfDay(i._date) < today - limit * DAY)) return false;
      if (maxKm > 0 && typeof i.distance_km === "number" && i.distance_km > maxKm) return false;
      if (q) {
        const hay = `${i.title} ${i.address || ""} ${i.postcode || ""} ${i.summary || ""} ${i.case_number || ""}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
  }

  _loadSeen() {
    try {
      return new Set(JSON.parse(localStorage.getItem(SEEN_KEY) || "[]"));
    } catch (e) {
      return new Set();
    }
  }
  _saveSeen() {
    try {
      localStorage.setItem(SEEN_KEY, JSON.stringify([...this._seen].slice(-500)));
    } catch (e) {
      /* private mode */
    }
  }

  // -------------------------------------------------------------- render
  _render() {
    if (!this._config || !this._hass) return;
    const root = this.shadowRoot;
    if (!root.querySelector(".wrap")) {
      root.innerHTML = `<style>${STYLE}</style><ha-card><div class="wrap"></div></ha-card>`;
      root.addEventListener("click", (ev) => this._onClick(ev));
      root.addEventListener("input", (ev) => {
        if (ev.target.matches("input.search")) {
          this._filters.q = ev.target.value;
          this._renderResults();
          this._syncClear();
        }
      });
      root.addEventListener("keydown", (ev) => {
        if (ev.key === "Escape" && this._open) this._closeDetail();
        const row = ev.target.closest?.(".item");
        if (row && (ev.key === "Enter" || ev.key === " ")) {
          ev.preventDefault();
          this._openDetail(row.dataset.id);
        }
      });
    }
    const wrap = root.querySelector(".wrap");
    wrap.classList.toggle("compact", !!this._config.compact);
    const id = this._config.entity;
    if (!id) {
      wrap.innerHTML = `<div class="empty big">Kies een Bekendmakingen-sensor in de kaart-editor.</div>`;
      return;
    }
    if (!this._stateObj) {
      wrap.innerHTML = `<div class="empty big warn">Entiteit niet gevonden: ${esc(id)}</div>`;
      return;
    }
    const focusSearch = root.activeElement?.matches?.("input.search");
    wrap.innerHTML = `${this._header()}<div class="body"></div><div class="modal-host"></div>`;
    this._renderBody();
    if (this._open) this._renderDetail();
    if (focusSearch) {
      const s = root.querySelector("input.search");
      s?.focus();
      s?.setSelectionRange(s.value.length, s.value.length);
    }
  }

  _header() {
    const now = new Date();
    const st = this._stateObj;
    const [status, time, errors] = this._diag || [];
    const items = this._items();
    const newCount = items.filter((i) => this._isNew(i, now)).length;
    let muni = st.attributes.municipality || (st.attributes.friendly_name || "").replace(/^Bekendmakingen\s*\(?|\)?$/g, "");
    if (muni && muni === muni.toLowerCase()) muni = muni.charAt(0).toUpperCase() + muni.slice(1);
    const title = this._config.title || `Bekendmakingen${muni ? ` ${muni}` : ""}`;
    const err = Number(errors?.state) || 0;
    const ok = status ? status.state === "OK" && err === 0 : true;
    const updated = time && time.state && !["unknown", "unavailable"].includes(time.state) ? new Date(time.state) : null;
    const statusText = !ok
      ? err > 1
        ? `${err}× mislukt`
        : "Bijwerken mislukt"
      : updated && !isNaN(updated)
        ? `Bijgewerkt ${relAgo(updated, now)}`
        : "Gemeenteblad";
    return `
      <header class="head">
        <div class="logo">${svg(ICON_FILE, 22)}</div>
        <div class="titles">
          <div class="title">${esc(title)}</div>
          <div class="status ${ok ? "ok" : "bad"}"><span class="dot"></span>${esc(statusText)}</div>
        </div>
        ${newCount ? `<button class="newbadge" data-action="seen" title="Markeer alles als gelezen">${newCount} nieuw</button>` : ""}
        <button class="icon-btn ${this._busy ? "spin" : ""}" data-action="refresh" title="Nu verversen" aria-label="Nu verversen">${svg(ICON_REFRESH, 18)}</button>
      </header>`;
  }

  _renderBody() {
    const body = this.shadowRoot.querySelector(".body");
    if (!body) return;
    const all = this._items();
    body.innerHTML = `${this._config.show_counters ? this._counters(all) : ""}${this._toolbar()}<div class="results"></div>`;
    this._renderResults();
  }

  _renderResults() {
    const box = this.shadowRoot.querySelector(".results");
    if (!box) return;
    const now = new Date();
    const all = this._items();
    const shown = this._filtered(all, now);
    const max = Math.max(1, Number(this._config.max_items) || 25);
    box.innerHTML = `${this._config.show_map ? this._map(shown) : ""}${this._timeline(shown.slice(0, max), now, all.length)}`;
    if (this._config.show_map) this._mountHaMap(shown);
  }

  _syncClear() {
    const bar = this.shadowRoot.querySelector(".toolbar");
    if (!bar) return;
    const f = this._filters;
    const want = !!(f.cats.size || f.q || f.period !== "all");
    const btn = bar.querySelector('[data-action="clear"]');
    if (want && !btn) bar.insertAdjacentHTML("beforeend", `<button class="link" data-action="clear">Wis filters</button>`);
    if (!want && btn) btn.remove();
  }

  _counters(all) {
    const counts = Object.fromEntries(CAT_KEYS.map((k) => [k, 0]));
    all.forEach((i) => (counts[i.category] += 1));
    const chips = CAT_KEYS.map((k) => {
      const on = this._filters.cats.has(k);
      const off = this._filters.cats.size && !on;
      return `<button class="counter ${on ? "on" : ""} ${off ? "dim" : ""} ${counts[k] ? "" : "zero"}" data-action="cat" data-cat="${k}" style="--c:${CATS[k].color}" aria-pressed="${on}">
        <span class="cicon">${svg(CATS[k].icon, 15)}</span><span class="cnum">${counts[k]}</span><span class="clabel">${CATS[k].label}</span></button>`;
    }).join("");
    return `<div class="counters">${chips}</div>`;
  }

  _toolbar() {
    const f = this._filters;
    const periods = PERIODS.map(
      ([k, l]) => `<button class="seg ${f.period === k ? "on" : ""}" data-action="period" data-period="${k}">${l}</button>`,
    ).join("");
    const search = this._config.show_search
      ? `<label class="searchbox">${svg(ICON_SEARCH, 15)}<input class="search" type="search" placeholder="Zoek op straat, postcode, kenmerk…" value="${esc(f.q)}" aria-label="Zoeken"></label>`
      : "";
    const clear = f.cats.size || f.q || f.period !== "all" ? `<button class="link" data-action="clear">Wis filters</button>` : "";
    return `<div class="toolbar"><div class="segs">${periods}</div>${search}${clear}</div>`;
  }

  _map(items) {
    const pts = items.filter((i) => typeof i.latitude === "number" && typeof i.longitude === "number");
    if (!pts.length) return "";
    const useHa = !!customElements.get("ha-map") && this._config.map_style !== "radar";
    if (useHa) return `<div class="map ha"><div class="map-slot"></div><div class="map-legend">${pts.length} op de kaart</div></div>`;
    return this._radar(pts);
  }

  _radar(pts) {
    const home = {
      lat: this._hass.config?.latitude,
      lon: this._hass.config?.longitude,
    };
    const lats = pts.map((p) => p.latitude);
    const lons = pts.map((p) => p.longitude);
    const hasHome = typeof home.lat === "number" && typeof home.lon === "number";
    const cLat = hasHome ? home.lat : (Math.min(...lats) + Math.max(...lats)) / 2;
    const cLon = hasHome ? home.lon : (Math.min(...lons) + Math.max(...lons)) / 2;
    const k = Math.cos((cLat * Math.PI) / 180);
    const dist = (p) => Math.hypot((p.latitude - cLat) * 111.32, (p.longitude - cLon) * 111.32 * k);
    const maxD = Math.max(0.5, ...pts.map(dist));
    const W = 600, H = 220, R = 100;
    const ring = [0.33, 0.66, 1].map((f) => `<ellipse cx="${W / 2}" cy="${H / 2}" rx="${R * f * 2.4}" ry="${R * f}" class="ring"/>`).join("");
    const labels = [0.33, 0.66, 1]
      .map((f) => `<text x="${W / 2}" y="${H / 2 - R * f + 12}" class="ringlabel" text-anchor="middle">${esc(fmtKm(maxD * f))}</text>`)
      .join("");
    const dots = pts
      .map((p) => {
        const x = W / 2 + (((p.longitude - cLon) * 111.32 * k) / maxD) * R * 2.4;
        const y = H / 2 - (((p.latitude - cLat) * 111.32) / maxD) * R;
        return `<g class="pin" data-action="open" data-id="${esc(p.id)}" style="--c:${CATS[p.category].color}" tabindex="0"><title>${esc(p.title)}</title><circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="9" class="halo"/><circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="5" class="core"/></g>`;
      })
      .join("");
    const homeMark = hasHome ? `<g class="home"><circle cx="${W / 2}" cy="${H / 2}" r="6"/><text x="${W / 2}" y="${H / 2 + 22}" text-anchor="middle">Thuis</text></g>` : "";
    return `<div class="map radar"><svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="xMidYMid meet" role="img" aria-label="Kaart met ${pts.length} bekendmakingen">${ring}${labels}${homeMark}${dots}</svg><div class="map-legend">${pts.length} op de kaart</div></div>`;
  }

  _mountHaMap(items) {
    const slot = this.shadowRoot.querySelector(".map-slot");
    if (!slot) return;
    const pts = items.filter((i) => typeof i.latitude === "number");
    const map = document.createElement("ha-map");
    map.hass = this._hass;
    map.zoom = 13;
    map.autoFit = true;
    map.fitZones = false;
    map.darkMode = !!this._hass.themes?.darkMode;
    slot.appendChild(map);
    let tries = 0;
    const place = () => {
      const L = map.Leaflet;
      const lmap = map.leafletMap;
      if (!L || !lmap) {
        if (tries++ < 40) setTimeout(place, 150);
        return;
      }
      const group = L.featureGroup();
      pts.forEach((p) => {
        const m = L.circleMarker([p.latitude, p.longitude], {
          radius: 8,
          color: "#fff",
          weight: 2,
          fillColor: CATS[p.category].color,
          fillOpacity: 0.95,
        });
        m.bindTooltip(esc(p.title));
        m.on("click", () => this._openDetail(p.id));
        group.addLayer(m);
      });
      group.addTo(lmap);
      if (pts.length) lmap.fitBounds(group.getBounds().pad(0.2), { maxZoom: 16 });
    };
    place();
  }

  _timeline(items, now, total) {
    if (!total) return `<div class="empty">Nog geen bekendmakingen. Ze verschijnen na de eerste update.</div>`;
    if (!items.length) return `<div class="empty">Geen bekendmakingen voor deze filters.</div>`;
    const today = startOfDay(now).getTime();
    const groups = [
      ["Vandaag", (t) => t >= today],
      ["Gisteren", (t) => t >= today - DAY],
      ["Deze week", (t) => t >= today - 6 * DAY],
      ["Eerder", () => true],
    ];
    const buckets = groups.map(() => []);
    items.forEach((i) => {
      const t = i._date ? startOfDay(i._date).getTime() : -Infinity;
      buckets[groups.findIndex(([, test]) => test(t))].push(i);
    });
    return `<div class="timeline">${groups
      .map(([label], n) =>
        buckets[n].length
          ? `<div class="group"><div class="ghead"><span>${label}</span><span class="gcount">${buckets[n].length}</span></div>${buckets[n]
              .map((i) => this._row(i, now))
              .join("")}</div>`
          : "",
      )
      .join("")}</div>`;
  }

  _row(i, now) {
    const c = CATS[i.category];
    const left = daysUntil(i.deadline, now);
    const meta = [
      i.address ? `<span class="m">${svg(ICON_PIN, 13)}${esc(i.address)}</span>` : "",
      typeof i.distance_km === "number" ? `<span class="m dist">${esc(fmtKm(i.distance_km))}</span>` : "",
      left !== null && left >= 0 ? `<span class="m dl ${left <= 7 ? "soon" : ""}">${svg(ICON_CLOCK, 13)}nog ${left} ${left === 1 ? "dag" : "dagen"}</span>` : "",
    ].join("");
    return `<div class="item" role="button" tabindex="0" data-action="open" data-id="${esc(i.id)}" style="--c:${c.color}">
      <div class="rail"><span class="node">${svg(c.icon, 14)}</span></div>
      <div class="content">
        <div class="row1"><span class="cat">${c.label}</span><span class="date">${esc(fmtDate(i._date))}</span>${this._isNew(i, now) ? `<span class="new">NIEUW</span>` : ""}</div>
        <div class="ititle">${esc(i.title)}</div>
        ${meta ? `<div class="meta">${meta}</div>` : ""}
      </div></div>`;
  }

  // -------------------------------------------------------------- detail
  _openDetail(id) {
    this._open = id;
    if (!this._seen.has(id)) {
      this._seen.add(id);
      this._saveSeen();
    }
    this._renderDetail();
  }
  _closeDetail() {
    this._open = null;
    const host = this.shadowRoot.querySelector(".modal-host");
    if (host) host.innerHTML = "";
    this._renderBody();
    this._refreshHeader();
  }
  _refreshHeader() {
    const head = this.shadowRoot.querySelector("header.head");
    if (head) head.outerHTML = this._header();
  }

  _renderDetail() {
    const host = this.shadowRoot.querySelector(".modal-host");
    const item = this._items().find((i) => i.id === this._open);
    if (!host) return;
    if (!item) {
      host.innerHTML = "";
      return;
    }
    const c = CATS[item.category];
    const now = new Date();
    const left = daysUntil(item.deadline, now);
    const deadline = item.deadline
      ? `<div class="fact ${left !== null && left < 0 ? "past" : left <= 7 ? "soon" : ""}"><span class="k">Reageren / bezwaar tot</span><span class="v">${esc(
          new Date(`${item.deadline}T12:00:00`).toLocaleDateString("nl-NL", { day: "numeric", month: "long", year: "numeric" }),
        )}${left !== null ? ` · ${left < 0 ? "verlopen" : left === 0 ? "vandaag" : `nog ${left} ${left === 1 ? "dag" : "dagen"}`}` : ""}</span></div>`
      : "";
    const facts = [
      ["Gepubliceerd", fmtDate(item._date)],
      ["Adres", [item.address, item.postcode].filter(Boolean).join(", ")],
      ["Afstand", typeof item.distance_km === "number" ? fmtKm(item.distance_km) : ""],
      ["Kenmerk", item.case_number],
      ["Rubriek", item.rubriek],
    ]
      .filter(([, v]) => v)
      .map(([k, v]) => `<div class="fact"><span class="k">${k}</span><span class="v">${esc(v)}</span></div>`)
      .join("");
    const text = String(item.detailed_description || item.summary || "")
      .split("\n")
      .filter(Boolean)
      .map((l) => `<p class="${l.startsWith("• ") ? "li" : ""}">${esc(l)}</p>`)
      .join("");
    const link = safeUrl(item.link);
    const inzage = safeUrl(item.inzage_url);
    host.innerHTML = `<div class="modal" data-action="backdrop"><div class="sheet" role="dialog" aria-modal="true" aria-label="${esc(item.title)}" style="--c:${c.color}">
      <div class="sheet-head"><span class="cat big">${svg(c.icon, 14)} ${c.label}</span><button class="icon-btn close" data-action="close" aria-label="Sluiten">${svg(CATS.geweigerd.icon, 18)}</button></div>
      <h3>${esc(item.title)}</h3>
      <div class="facts">${deadline}${facts}</div>
      <div class="text">${text || "<p>Geen extra details beschikbaar.</p>"}</div>
      <div class="actions">
        ${link ? `<a class="btn primary" href="${esc(link)}" target="_blank" rel="noopener noreferrer">${svg(ICON_EXT, 15)} Open op overheid.nl</a>` : ""}
        ${inzage ? `<a class="btn" href="${esc(inzage)}" target="_blank" rel="noopener noreferrer">${svg(ICON_FILE, 15)} Stukken inzien</a>` : ""}
        ${typeof item.latitude === "number" ? `<a class="btn" href="https://www.openstreetmap.org/?mlat=${item.latitude}&mlon=${item.longitude}#map=17/${item.latitude}/${item.longitude}" target="_blank" rel="noopener noreferrer">${svg(ICON_PIN, 15)} Kaart</a>` : ""}
      </div></div></div>`;
    host.querySelector(".close")?.focus();
  }

  // -------------------------------------------------------------- actions
  _onClick(ev) {
    const el = ev.target.closest("[data-action]");
    if (!el) return;
    const a = el.dataset.action;
    if (a === "backdrop" && ev.target !== el) return;
    switch (a) {
      case "cat": {
        const k = el.dataset.cat;
        this._filters.cats.has(k) ? this._filters.cats.delete(k) : this._filters.cats.add(k);
        this._renderBody();
        break;
      }
      case "period":
        this._filters.period = el.dataset.period;
        this._renderBody();
        break;
      case "clear":
        this._filters = { cats: new Set(), period: "all", q: "" };
        this._renderBody();
        break;
      case "open":
        this._openDetail(el.dataset.id);
        break;
      case "close":
      case "backdrop":
        this._closeDetail();
        break;
      case "seen":
        this._items().forEach((i) => this._seen.add(i.id));
        this._saveSeen();
        this._refreshHeader();
        this._renderBody();
        break;
      case "refresh":
        this._refresh();
        break;
      default:
        break;
    }
  }

  async _refresh() {
    if (this._busy) return;
    this._busy = true;
    this._refreshHeader();
    try {
      await this._hass.callService("bekendmakingen", "refresh", {});
    } catch (err) {
      this._toast(`Verversen mislukt: ${err?.message || err}`);
    } finally {
      this._busy = false;
      this._refreshHeader();
    }
  }

  _toast(msg) {
    const wrap = this.shadowRoot.querySelector(".wrap");
    if (!wrap) return;
    wrap.querySelector(".toast")?.remove();
    const t = document.createElement("div");
    t.className = "toast";
    t.textContent = msg;
    wrap.appendChild(t);
    setTimeout(() => t.remove(), 5000);
  }
}

const STYLE = `
:host { display: block; }
ha-card { overflow: hidden; }
.wrap { position: relative; padding: 16px; color: var(--primary-text-color); font-family: var(--paper-font-body1_-_font-family, inherit); }
.head { display: flex; align-items: center; gap: 12px; margin-bottom: 14px; }
.logo { width: 42px; height: 42px; border-radius: 12px; display: grid; place-items: center; color: #fff;
  background: linear-gradient(135deg, #f97316, #e11d48); box-shadow: 0 6px 16px -6px rgba(225,29,72,.6); flex: none; }
.titles { flex: 1; min-width: 0; }
.title { font-size: 1.15em; font-weight: 700; letter-spacing: .1px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.status { display: flex; align-items: center; gap: 6px; font-size: .82em; color: var(--secondary-text-color); margin-top: 2px; }
.status .dot { width: 8px; height: 8px; border-radius: 50%; background: var(--success-color, #22a565); box-shadow: 0 0 0 3px color-mix(in srgb, var(--success-color, #22a565) 25%, transparent); }
.status.bad .dot { background: var(--error-color, #e5484d); box-shadow: 0 0 0 3px color-mix(in srgb, var(--error-color, #e5484d) 25%, transparent); }
.status.bad { color: var(--error-color, #e5484d); }
.newbadge { border: 0; cursor: pointer; font: inherit; font-size: .78em; font-weight: 700; color: #fff; padding: 5px 11px; border-radius: 999px;
  background: linear-gradient(135deg, #e11d48, #f97316); animation: pulse 2.4s ease-in-out infinite; }
@keyframes pulse { 0%,100% { box-shadow: 0 0 0 0 rgba(225,29,72,.45); } 50% { box-shadow: 0 0 0 6px rgba(225,29,72,0); } }
.icon-btn { border: 1px solid var(--divider-color, rgba(127,127,127,.25)); background: transparent; color: var(--primary-text-color);
  width: 36px; height: 36px; border-radius: 10px; display: grid; place-items: center; cursor: pointer; flex: none; }
.icon-btn:hover { background: color-mix(in srgb, var(--primary-color, #03a9f4) 10%, transparent); }
.icon-btn.spin svg { animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.counters { display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 8px; margin-bottom: 12px; }
.counter { --c: #888; border: 1px solid color-mix(in srgb, var(--c) 30%, transparent); background: color-mix(in srgb, var(--c) 9%, var(--card-background-color, transparent));
  border-radius: 12px; padding: 8px 6px 7px; cursor: pointer; font: inherit; color: var(--primary-text-color); display: grid; justify-items: center; gap: 2px; transition: transform .12s, opacity .12s, background .12s; }
.counter:hover { transform: translateY(-1px); }
.counter .cicon { color: var(--c); display: grid; }
.counter .cnum { font-size: 1.35em; font-weight: 800; line-height: 1.1; }
.counter .clabel { font-size: .72em; color: var(--secondary-text-color); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 100%; }
.counter.on { background: var(--c); border-color: var(--c); color: #fff; }
.counter.on .cicon, .counter.on .clabel { color: #fff; }
.counter.dim { opacity: .45; }
.counter.zero .cnum { opacity: .45; }
.toolbar { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin-bottom: 12px; }
.segs { display: inline-flex; background: color-mix(in srgb, var(--primary-text-color) 6%, transparent); border-radius: 10px; padding: 3px; }
.seg { border: 0; background: transparent; color: var(--secondary-text-color); font: inherit; font-size: .82em; padding: 5px 10px; border-radius: 8px; cursor: pointer; }
.seg.on { background: var(--card-background-color, #fff); color: var(--primary-text-color); font-weight: 600; box-shadow: 0 1px 3px rgba(0,0,0,.15); }
.searchbox { flex: 1; min-width: 160px; display: flex; align-items: center; gap: 6px; padding: 0 10px; height: 34px; border-radius: 10px;
  border: 1px solid var(--divider-color, rgba(127,127,127,.25)); color: var(--secondary-text-color); }
.searchbox:focus-within { border-color: var(--primary-color, #03a9f4); }
.search { flex: 1; min-width: 0; border: 0; outline: 0; background: transparent; color: var(--primary-text-color); font: inherit; font-size: .9em; }
.link { border: 0; background: none; color: var(--primary-color, #03a9f4); cursor: pointer; font: inherit; font-size: .82em; }
.map { position: relative; border-radius: 14px; overflow: hidden; margin-bottom: 14px; border: 1px solid var(--divider-color, rgba(127,127,127,.2)); }
.map.ha .map-slot, .map.ha ha-map { display: block; height: 240px; }
.map.radar { background: radial-gradient(ellipse at center, color-mix(in srgb, var(--primary-color, #03a9f4) 14%, transparent), transparent 70%),
  color-mix(in srgb, var(--primary-text-color) 3%, var(--card-background-color, transparent)); }
.map.radar svg { display: block; width: 100%; height: 220px; }
.ring { fill: none; stroke: var(--divider-color, rgba(127,127,127,.35)); stroke-dasharray: 3 5; }
.ringlabel { fill: var(--secondary-text-color); font-size: 10px; }
.home circle { fill: var(--primary-color, #03a9f4); stroke: #fff; stroke-width: 2.5; }
.home text { fill: var(--secondary-text-color); font-size: 10px; font-weight: 600; }
.pin { cursor: pointer; }
.pin .halo { fill: var(--c); opacity: .22; transition: r .15s; }
.pin .core { fill: var(--c); stroke: #fff; stroke-width: 1.8; }
.pin:hover .halo { r: 13; opacity: .35; }
.map-legend { position: absolute; right: 8px; bottom: 8px; font-size: .72em; padding: 3px 8px; border-radius: 999px;
  background: color-mix(in srgb, var(--card-background-color, #fff) 85%, transparent); color: var(--secondary-text-color); backdrop-filter: blur(4px); z-index: 500; }
.timeline .group + .group { margin-top: 6px; }
.ghead { display: flex; justify-content: space-between; align-items: center; font-size: .74em; font-weight: 700; letter-spacing: .08em;
  text-transform: uppercase; color: var(--secondary-text-color); padding: 6px 2px; position: sticky; top: 0; }
.gcount { font-weight: 600; opacity: .7; }
.item { --c: #888; display: flex; gap: 12px; padding: 4px 6px 4px 2px; border-radius: 12px; cursor: pointer; outline: none; transition: background .12s; }
.item:hover, .item:focus-visible { background: color-mix(in srgb, var(--c) 8%, transparent); }
.rail { position: relative; width: 30px; flex: none; display: flex; justify-content: center; }
.rail::before { content: ""; position: absolute; top: 0; bottom: 0; width: 2px; background: var(--divider-color, rgba(127,127,127,.25)); }
.group .item:first-of-type .rail::before { top: 12px; }
.group .item:last-of-type .rail::before { bottom: calc(100% - 26px); }
.node { position: relative; margin-top: 8px; width: 26px; height: 26px; border-radius: 50%; display: grid; place-items: center; color: #fff;
  background: var(--c); box-shadow: 0 0 0 3px var(--card-background-color, #fff); }
.content { flex: 1; min-width: 0; padding: 7px 0 9px; border-bottom: 1px solid color-mix(in srgb, var(--divider-color, rgba(127,127,127,.2)) 70%, transparent); }
.group .item:last-of-type .content { border-bottom: 0; }
.row1 { display: flex; align-items: center; gap: 8px; font-size: .74em; }
.cat { color: var(--c); font-weight: 700; text-transform: uppercase; letter-spacing: .06em; display: inline-flex; align-items: center; gap: 5px; }
.date { color: var(--secondary-text-color); }
.new { margin-left: auto; font-weight: 800; font-size: .92em; letter-spacing: .06em; color: #fff; background: linear-gradient(135deg, #e11d48, #f97316); padding: 2px 7px; border-radius: 6px; }
.ititle { font-weight: 600; font-size: .95em; line-height: 1.35; margin-top: 3px; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.meta { display: flex; flex-wrap: wrap; gap: 4px 12px; margin-top: 5px; font-size: .78em; color: var(--secondary-text-color); }
.m { display: inline-flex; align-items: center; gap: 4px; }
.dist { font-weight: 600; }
.dl { color: var(--secondary-text-color); }
.dl.soon { color: var(--warning-color, #f59e0b); font-weight: 600; }
.compact .meta, .compact .map { display: none; }
.compact .ititle { -webkit-line-clamp: 1; }
.empty { padding: 26px 12px; text-align: center; color: var(--secondary-text-color); font-size: .9em; }
.empty.big { padding: 30px 12px; }
.empty.warn { color: var(--error-color, #e5484d); }
.modal { position: fixed; inset: 0; z-index: 1000; background: rgba(0,0,0,.45); display: flex; align-items: center; justify-content: center; padding: 16px; animation: fade .15s ease-out; }
@keyframes fade { from { opacity: 0; } }
.sheet { --c: #888; width: min(620px, 100%); max-height: min(86vh, 900px); overflow: auto; border-radius: 18px; padding: 18px 20px 20px;
  background: var(--card-background-color, var(--ha-card-background, #fff)); color: var(--primary-text-color); box-shadow: 0 24px 60px -12px rgba(0,0,0,.5);
  border-top: 5px solid var(--c); animation: rise .18s ease-out; }
@keyframes rise { from { transform: translateY(14px); opacity: 0; } }
.sheet-head { display: flex; justify-content: space-between; align-items: center; }
.cat.big { font-size: .78em; background: color-mix(in srgb, var(--c) 14%, transparent); padding: 4px 10px; border-radius: 999px; }
.sheet h3 { margin: 12px 0 14px; font-size: 1.15em; line-height: 1.35; }
.facts { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 8px; margin-bottom: 14px; }
.fact { background: color-mix(in srgb, var(--primary-text-color) 5%, transparent); border-radius: 10px; padding: 8px 10px; display: grid; gap: 2px; }
.fact .k { font-size: .7em; text-transform: uppercase; letter-spacing: .06em; color: var(--secondary-text-color); font-weight: 600; }
.fact .v { font-size: .9em; font-weight: 600; word-break: break-word; }
.fact.soon { background: color-mix(in srgb, var(--warning-color, #f59e0b) 16%, transparent); }
.fact.past { opacity: .6; }
.text { font-size: .9em; line-height: 1.55; color: var(--primary-text-color); }
.text p { margin: 0 0 8px; }
.text p.li { padding-left: 10px; }
.actions { display: flex; flex-wrap: wrap; gap: 8px; margin: 16px -20px -20px; padding: 12px 20px 18px; position: sticky; bottom: -20px;
  background: var(--card-background-color, var(--ha-card-background, #fff)); border-top: 1px solid var(--divider-color, rgba(127,127,127,.2)); }
.btn { display: inline-flex; align-items: center; gap: 6px; text-decoration: none; font-weight: 600; font-size: .88em; padding: 9px 14px; border-radius: 10px;
  color: var(--primary-text-color); border: 1px solid var(--divider-color, rgba(127,127,127,.3)); }
.btn.primary { background: var(--c); border-color: var(--c); color: #fff; }
.toast { position: absolute; left: 16px; right: 16px; bottom: 12px; padding: 10px 14px; border-radius: 10px; background: var(--error-color, #e5484d); color: #fff; font-size: .85em; }
@media (max-width: 520px) {
  .counters { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .facts { grid-template-columns: 1fr; }
}
`;

const EDITOR_SCHEMA = [
  { name: "entity", required: true, selector: { entity: { domain: "sensor", integration: "bekendmakingen" } } },
  { name: "title", selector: { text: {} } },
  {
    type: "grid",
    name: "",
    schema: [
      { name: "show_map", selector: { boolean: {} } },
      { name: "show_counters", selector: { boolean: {} } },
      { name: "show_search", selector: { boolean: {} } },
      { name: "compact", selector: { boolean: {} } },
    ],
  },
  { name: "categories", selector: { select: { multiple: true, options: CAT_KEYS.map((k) => ({ value: k, label: CATS[k].label })) } } },
  { name: "max_items", selector: { number: { min: 5, max: 50, step: 5, mode: "slider" } } },
  { name: "new_hours", selector: { number: { min: 1, max: 168, step: 1, mode: "box", unit_of_measurement: "uur" } } },
  { name: "max_distance_km", selector: { number: { min: 0, max: 50, step: 0.5, mode: "box", unit_of_measurement: "km" } } },
];
const EDITOR_LABELS = {
  entity: "Bekendmakingen-sensor",
  title: "Titel (optioneel)",
  show_map: "Kaart tonen",
  show_counters: "Tellers per categorie",
  show_search: "Zoekveld",
  compact: "Compacte weergave",
  categories: "Standaard categorie-filter",
  max_items: "Maximaal aantal in de lijst",
  new_hours: "‘Nieuw’ gedurende",
  max_distance_km: "Maximale afstand (0 = alles)",
};

class BekendmakingenCardEditor extends HTMLElement {
  setConfig(config) {
    this._config = { ...config };
    this._render();
  }
  set hass(hass) {
    this._hass = hass;
    if (this._form) this._form.hass = hass;
    else this._render();
  }
  _render() {
    if (!this._config) return;
    if (!this._form) {
      this._form = document.createElement("ha-form");
      this._form.computeLabel = (s) => EDITOR_LABELS[s.name] || s.name;
      this._form.addEventListener("value-changed", (ev) => {
        const config = { ...ev.detail.value };
        Object.keys(config).forEach((k) => (config[k] === "" || config[k] === undefined) && delete config[k]);
        this._config = config;
        this.dispatchEvent(new CustomEvent("config-changed", { detail: { config }, bubbles: true, composed: true }));
      });
      this.appendChild(this._form);
    }
    this._form.hass = this._hass;
    this._form.schema = EDITOR_SCHEMA;
    this._form.data = { show_map: true, show_counters: true, show_search: true, compact: false, max_items: 25, new_hours: 24, ...this._config };
  }
}

if (!customElements.get("bekendmakingen-card")) customElements.define("bekendmakingen-card", BekendmakingenCard);
if (!customElements.get("bekendmakingen-card-editor")) customElements.define("bekendmakingen-card-editor", BekendmakingenCardEditor);
window.customCards = window.customCards || [];
if (!window.customCards.some((c) => c.type === "bekendmakingen-card")) {
  window.customCards.push({
    type: "bekendmakingen-card",
    name: "Bekendmakingen",
    description: "Officiële gemeentelijke bekendmakingen: tijdlijn, kaart, filters en details.",
    preview: true,
    documentationURL: "https://github.com/DonTranQuiL/Bekendmakingen",
  });
}
console.info(`%c BEKENDMAKINGEN-CARD %c ${CARD_VERSION} `, "background:#e11d48;color:#fff;font-weight:700", "background:#f97316;color:#fff");
