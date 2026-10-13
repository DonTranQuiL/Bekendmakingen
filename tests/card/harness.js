// Browser test harness for the Bekendmakingen card. Runs in headless Chrome
// (see tests/test_card.py) after the card module; writes JSON results to #out.
const results = { errors: [], calls: [], checks: {} };
const origError = console.error;
console.error = (...args) => { results.errors.push(args.map(String).join(" ")); origError(...args); };
window.addEventListener("error", (ev) => results.errors.push(String(ev.message)));
window.addEventListener("unhandledrejection", (ev) => results.errors.push(String(ev.reason)));
customElements.define("ha-form", class extends HTMLElement {});

const DATA = JSON.parse(document.getElementById("states").textContent);
const flush = () => new Promise((r) => setTimeout(r, 0));
const clone = (v) => JSON.parse(JSON.stringify(v));

function makeHass(states, fail = false) {
  return {
    states,
    entities: DATA.entities,
    config: { latitude: DATA.home[0], longitude: DATA.home[1] },
    language: "nl",
    callService: async (domain, service, data) => {
      results.calls.push({ domain, service, data });
      if (fail) throw new Error("boom <b>bold</b>");
    },
  };
}
async function newCard(config, hass) {
  const box = document.createElement("div");
  box.style.width = "760px";
  document.body.appendChild(box);
  const card = document.createElement("bekendmakingen-card");
  card.setConfig(config);
  box.appendChild(card);
  card.hass = hass;
  await flush();
  return card;
}
const $ = (card, s) => card.shadowRoot.querySelector(s);
const $$ = (card, s) => [...card.shadowRoot.querySelectorAll(s)];
const text = (card) => $(card, ".wrap").textContent.replace(/\s+/g, " ");
async function click(card, sel) {
  const el = $(card, sel);
  if (!el) return false;
  el.dispatchEvent(new MouseEvent("click", { bubbles: true, composed: true }));
  await flush();
  return true;
}

(async () => {
  const c = results.checks;
  try {
    localStorage.clear();
    const cfg = { entity: DATA.main, map_style: "radar" };
    const card = await newCard(cfg, makeHass(DATA.states));
    const t = text(card);
    c.title = $(card, ".title").textContent;
    c.status_ok = $(card, ".status").classList.contains("ok");
    c.counters = Object.fromEntries($$(card, ".counter").map((b) => [b.dataset.cat, Number(b.querySelector(".cnum").textContent)]));
    c.groups = $$(card, ".ghead span:first-child").map((e) => e.textContent);
    c.rows = $$(card, ".item").length;
    c.new_rows = $$(card, ".item .new").length;
    c.newbadge = $(card, ".newbadge")?.textContent;
    c.pins = $$(card, ".pin").length;
    c.home = $$(card, ".home").length;
    c.bad_text = ["undefined", "NaN", "null", "[object Object]"].filter((x) => t.includes(x));
    c.deadline_meta = $$(card, ".item .dl").length;

    // Same state objects: no re-render.
    let renders = 0;
    const real = card._render.bind(card);
    card._render = () => { renders += 1; real(); };
    card.hass = makeHass(DATA.states);
    c.renders_same = renders;
    card._render = real;

    // Category filter.
    await click(card, '.counter[data-cat="verkeer"]');
    c.rows_verkeer = $$(card, ".item").length;
    c.verkeer_pressed = $(card, '.counter[data-cat="verkeer"]').getAttribute("aria-pressed");
    await click(card, '.counter[data-cat="verkeer"]');
    // Period filter.
    await click(card, '.seg[data-period="today"]');
    c.rows_today = $$(card, ".item").length;
    c.clear_shown = !!$(card, 'button[data-action="clear"]');
    await click(card, 'button[data-action="clear"]');
    c.rows_after_clear = $$(card, ".item").length;
    // Search keeps focus.
    const search = $(card, "input.search");
    search.focus();
    search.value = "vlugtsingel";
    search.dispatchEvent(new Event("input", { bubbles: true, composed: true }));
    await flush();
    c.rows_search = $$(card, ".item").length;
    c.search_focus = card.shadowRoot.activeElement === $(card, "input.search");
    card.hass = makeHass(clone(DATA.states)); // state update while typing
    await flush();
    c.search_kept = $(card, "input.search")?.value;
    search.value = "";
    $(card, "input.search").value = "";
    $(card, "input.search").dispatchEvent(new Event("input", { bubbles: true, composed: true }));
    await flush();

    // Detail popup.
    await click(card, `.item[data-id="${DATA.detail_id}"]`);
    c.modal = !!$(card, ".modal .sheet");
    c.modal_title = $(card, ".sheet h3")?.textContent;
    c.modal_facts = $$(card, ".fact .k").map((e) => e.textContent);
    c.modal_deadline = $(card, ".fact.soon .v, .fact .v")?.textContent;
    c.modal_links = $$(card, ".actions a").map((a) => a.getAttribute("href").split("?")[0].slice(0, 40));
    c.modal_bullets = $$(card, ".text p.li").length;
    await click(card, 'button[data-action="close"]');
    c.modal_closed = !$(card, ".modal");
    c.new_after_open = $$(card, ".item .new").length;
    await click(card, ".newbadge");
    c.new_after_seen = $$(card, ".item .new").length;
    c.badge_after_seen = !!$(card, ".newbadge");

    // Refresh.
    await click(card, 'button[data-action="refresh"]');
    await flush();
    c.refresh_call = results.calls.at(-1);
    const failing = await newCard(cfg, makeHass(DATA.states, true));
    await click(failing, 'button[data-action="refresh"]');
    await flush(); await flush();
    c.toast = $(failing, ".toast")?.textContent;
    c.toast_markup = $(failing, ".toast")?.children.length;

    // XSS in data.
    const evil = clone(DATA.states);
    const items = evil[DATA.main].attributes.items;
    items[0].title = '<img src=x onerror="window.__xss=1">';
    items[0].link = "javascript:alert(1)";
    const xcard = await newCard(cfg, makeHass(evil));
    c.xss_nodes = $$(xcard, ".item img").length;
    await click(xcard, `.item[data-id="${items[0].id}"]`);
    c.xss_link = $$(xcard, '.actions a[href^="javascript"]').length;
    c.xss_fired = window.__xss || 0;

    // Legacy v2.0 sensor (no items attribute).
    const legacy = clone(DATA.states);
    const la = legacy[DATA.main].attributes;
    la.history = la.items.slice(1).map(({ title, link, date, time, summary }) => ({ title, link, date, time, summary }));
    delete la.items;
    const lcard = await newCard(cfg, makeHass(legacy));
    c.legacy_rows = $$(lcard, ".item").length;
    c.legacy_overig = Number($(lcard, '.counter[data-cat="overig"] .cnum').textContent);

    // Error states.
    const nf = await newCard({ entity: "sensor.nope" }, makeHass(DATA.states));
    c.not_found = text(nf).includes("niet gevonden");
    const none = await newCard({}, makeHass(DATA.states));
    c.no_entity = text(none).includes("Kies een");
    const errStates = clone(DATA.states);
    errStates[DATA.status].state = "Error";
    errStates[DATA.errors].state = "3";
    const ecard = await newCard(cfg, makeHass(errStates));
    c.err_status = $(ecard, ".status").textContent.trim();
    try { card.setConfig(null); c.bad_config = "accepted"; } catch (e) { c.bad_config = "rejected"; }
    try { card.setConfig({ entity: 5 }); c.bad_entity = "accepted"; } catch (e) { c.bad_entity = "rejected"; }
    const compact = await newCard({ ...cfg, compact: true, show_map: false, show_counters: false }, makeHass(DATA.states));
    c.compact = { map: !!$(compact, ".map"), counters: !!$(compact, ".counters"), size: compact.getCardSize() };
    const preset = await newCard({ ...cfg, categories: ["verleend"], max_items: 1 }, makeHass(DATA.states));
    c.preset_rows = $$(preset, ".item").length;

    // Static API.
    const Card = customElements.get("bekendmakingen-card");
    c.stub = Card.getStubConfig(makeHass(DATA.states));
    const editor = Card.getConfigElement();
    editor.setConfig({ entity: DATA.main });
    editor.hass = makeHass(DATA.states);
    const form = editor.querySelector("ha-form");
    c.editor_fields = form.schema.flatMap((s) => (s.schema ? s.schema.map((x) => x.name) : [s.name]));
    c.editor_label = form.computeLabel({ name: "show_map" });
    let changed = null;
    editor.addEventListener("config-changed", (ev) => (changed = ev.detail.config));
    form.dispatchEvent(new CustomEvent("value-changed", { detail: { value: { entity: DATA.main, title: "", compact: true } } }));
    c.editor_config = changed;
    c.registered = (window.customCards || []).filter((x) => x.type === "bekendmakingen-card").length;
  } catch (err) {
    results.errors.push(`harness: ${err && err.stack ? err.stack : err}`);
  }
  document.getElementById("out").textContent = JSON.stringify(results);
})();
