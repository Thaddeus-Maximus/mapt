"use strict";
/* mapt: the place map (pins, side pane, placing and moving pins) and small page helpers. */
const mapt = (() => {
  const $ = (s, el = document) => el.querySelector(s);
  const $$ = (s, el = document) => [...el.querySelectorAll(s)];
  const key = s => (s || "").toLowerCase();
  const clamp01 = v => Math.min(1, Math.max(0, v));
  const typing = e => /^(INPUT|TEXTAREA|SELECT)$/.test(e.target.tagName) || e.target.isContentEditable;

  async function post(url, data) {
    const r = await fetch(url, {method: "POST", body: new URLSearchParams(data)});
    const j = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(j.error || r.statusText);
    return j;
  }

  const PLACE_ICON = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 20V10l8-6 8 6v10z"/><path d="M10 20v-6h4v6"/></svg>';

  function kindOf(p) {
    return p.kind === "thing" ? "thing" : "place";
  }

  function icon(p) {
    const kind = kindOf(p);
    const html = kind === "thing" ? '<span class="dot"></span>'
      : `<span class="dot">${p.things || (p.map ? PLACE_ICON : "")}</span>`;
    const size = kind === "thing" ? 22 : 30;
    return L.divIcon({className: `pin k-${kind}${p.map ? " has-map" : ""}${p.low ? " low" : ""}`, html,
                      iconSize: [size, size], iconAnchor: [size / 2, size / 2]});
  }

  /* The map page. `d`: {id, url, w, h, pins: [{id, kind, x, y, map, things, low, search}],
     sel, pin, readonly}. Positions are fractions of the image from its top-left corner. */
  function placeMap(el, d) {
    const W = 1000, H = 1000 * d.h / d.w;
    const bounds = L.latLngBounds([[-H, 0], [0, W]]);
    const map = L.map(el, {crs: L.CRS.Simple, zoomSnap: 0.25, zoomDelta: 0.5, wheelPxPerZoomLevel: 90,
                           attributionControl: false, minZoom: -8, maxZoom: 8, doubleClickZoom: false,
                           boxZoom: false});
    L.imageOverlay(d.url, bounds, {className: "floorplan"}).addTo(map);
    map.fitBounds(bounds, {padding: [6, 6]});
    const fit = map.getZoom();
    map.setMinZoom(fit - 1);
    map.setMaxZoom(fit + 6);
    map.setMaxBounds(bounds.pad(0.3));
    const toLL = (x, y) => L.latLng(-y * H, x * W);
    const fromLL = ll => [clamp01(ll.lng / W), clamp01(-ll.lat / H)];

    const pane = $("#pane"), peek = $("#peek"), hint = $("#hint"), filter = $("#filter");
    const markers = {};
    let pins = d.pins;
    function drawPins(list) {
      for (const k of Object.keys(markers)) { markers[k].remove(); delete markers[k]; }
      pins = list;
      for (const p of pins) addPin(p);
      near();
      if (filter) applyFilter();
    }
    async function reloadPins() {
      const r = await fetch(`/api/pins/${encodeURIComponent(d.id)}`);
      if (r.ok) drawPins(await r.json());
    }
    function addPin(p) {
      const kind = kindOf(p);
      const m = L.marker(toLL(p.x, p.y), {icon: icon(p), title: p.id, keyboard: true, riseOnHover: true,
                                           autoPan: true});
      const label = document.createElement("span");
      label.textContent = p.id;
      const size = kind === "thing" ? 22 : 30;
      m.bindTooltip(label, {permanent: true, direction: "right", offset: [size / 2 - 4, 0],
                            className: `pin-label k-${kind}`});
      m.on("click", () => { if (!mode) select(p.id); else if (mode.kind !== "move") mapClick({latlng: m.getLatLng()}); });
      m.on("dblclick", () => { if (p.map) location.href = "/m/" + encodeURIComponent(p.id); });
      m.on("dragend", () => savePos(p.id, m.getLatLng()));
      m.addTo(map);
      markers[key(p.id)] = m;
    }
    const near = () => el.classList.toggle("near", pins.length <= 30 || map.getZoom() >= fit + 1);
    map.on("zoomend", near);

    // --- selection and the pane -------------------------------------------
    function highlight(pinId) {
      for (const m of Object.values(markers)) {
        m.getElement()?.classList.remove("sel");
        m.getTooltip()?.getElement()?.classList.remove("sel");
        m.setZIndexOffset(0);
      }
      const m = markers[key(pinId)];
      if (m) {
        m.getElement()?.classList.add("sel");
        m.getTooltip()?.getElement()?.classList.add("sel");
        m.setZIndexOffset(1000);
      }
      return m;
    }

    function peekLabel() {
      const root = pane.firstElementChild;
      const id = root?.dataset.id || d.id;
      $(".label", peek).textContent = key(id) === key(d.id) ? `${d.id} · ${pins.length} on the map` : id;
    }

    function showPane(on) {
      document.body.classList.toggle("pane-open", on);
      if (!on) map.invalidateSize();    // now: the map was hidden, and a click may come right away
    }

    async function select(id, {push = true, pan = false, force = false} = {}) {
      if (!force && !leaveForm()) return;
      ghost(null);
      const r = await fetch(`/pane/${encodeURIComponent(id)}?map=${encodeURIComponent(d.id)}`);
      if (!r.ok) return;
      pane.innerHTML = await r.text();
      pane.scrollTop = 0;
      const root = pane.firstElementChild;
      const pin = root?.dataset.pin;
      const m = highlight(pin && key(pin) !== key(d.id) ? pin : null);
      const url = new URL(location);
      if (key(id) === key(d.id)) url.searchParams.delete("sel"); else url.searchParams.set("sel", id);
      if (url.href !== location.href) history[push ? "pushState" : "replaceState"](null, "", url);
      peekLabel();
      if (pan && m && !map.getBounds().pad(-0.15).contains(m.getLatLng())) map.panTo(m.getLatLng());
    }

    pane.addEventListener("click", e => {
      const a = e.target.closest("a.link[data-id]");
      if (a && !(e.ctrlKey || e.metaKey || e.shiftKey || e.button)) {
        const same = key(a.dataset.id) === key(d.id)
          || (key(a.dataset.map || d.id) === key(d.id) && !("hasmap" in a.dataset));
        if (same) {
          e.preventDefault();
          select(a.dataset.id, {pan: true});
          return;
        }
      }
      const f = e.target.closest("a[data-form]");
      if (f && !(e.ctrlKey || e.metaKey || e.shiftKey || e.button)) {
        e.preventDefault();
        openForm(f.dataset.form);
        return;
      }
      const b = e.target.closest("[data-act]");
      if (!b) return;
      if (b.dataset.act === "pick") setMode({kind: "pick"}, "Click the map where it goes");
      else if (b.dataset.act === "unpick") setSpot(null);
      else if (b.dataset.act === "cancel") {
        const form = b.closest("form");
        if (form?.classList.contains("dirty") && !confirm("Discard your changes?")) return;
        select(b.dataset.id || new URL(location).searchParams.get("sel") || d.id, {push: false, force: true});
      }
      else if (b.dataset.act === "showmap") showPane(false);
      else if (b.dataset.act === "move") startMove(b.dataset.id);
      else if (b.dataset.act === "place") startPlace(b.dataset.id);
    });
    peek.addEventListener("click", () => showPane(true));

    // --- add and edit forms in the pane ------------------------------------
    function leaveForm() {
      return !$("form.dirty", pane) || confirm("Discard your changes?");
    }

    async function openForm(url) {
      if (!leaveForm()) return false;
      const u = new URL(url, location);
      u.searchParams.set("map", d.id);
      const r = await fetch(u);
      if (!r.ok) { alert(`Couldn't open the form (${r.status})`); return false; }
      pane.innerHTML = await r.text();
      pane.scrollTop = 0;
      enhance(pane);
      const where = $("form.itemform input[name=where]", pane);
      where?.addEventListener("input", syncSpot);
      syncSpot();
      peekLabel();
      showPane(true);
      $("input[name=name]", pane)?.focus({preventScroll: true});
      return true;
    }

    pane.addEventListener("input", e => e.target.closest("form.itemform")?.classList.add("dirty"));

    /* The form's "Spot on <map>" row: only while "Where" is this map (otherwise the spot
       would be on the wrong map), and then its marker shows where the pin will go. */
    function syncSpot() {
      const spot = $("form.itemform .spot", pane);
      if (!spot) return;
      const where = $("form.itemform input[name=where]", pane)?.value.trim().replace(/^\[\[|\]\]$/g, "");
      const on = key(where) === key(spot.dataset.map);
      spot.hidden = !on;
      $$("input", spot).forEach(i => { i.disabled = !on; });
      const x = $("input[name=x]", spot).value, y = $("input[name=y]", spot).value;
      ghost(on && "picked" in spot.dataset && x !== "" ? toLL(+x, +y) : null);
    }

    function setSpot(xy) {
      const spot = $("form.itemform .spot", pane);
      if (!spot) return;
      $("input[name=x]", spot).value = xy ? xy[0].toFixed(4) : "";
      $("input[name=y]", spot).value = xy ? xy[1].toFixed(4) : "";
      spot.dataset.picked = "";
      $(".spottext", spot).textContent = xy ? "Marked on the map." : "Not on the map.";
      $("[data-act=pick]", spot).textContent = xy ? "Change" : "Pick on map";
      $("[data-act=unpick]", spot).hidden = !xy;
      spot.closest("form").classList.add("dirty");
      syncSpot();
    }
    pane.addEventListener("submit", async e => {
      if (e.defaultPrevented) return;
      e.preventDefault();
      const f = e.target, buttons = $$("button", f);
      const err = $(".formerror", f) || $(".formerror", pane);
      const body = new FormData(f, e.submitter);   // before disabling: a disabled button isn't sent
      buttons.forEach(b => { b.disabled = true; });
      try {
        const r = await fetch(f.action, {method: "POST", body, headers: {"X-Mapt": "pane"}});
        const j = await r.json().catch(() => ({error: `${r.status} ${r.statusText}`}));
        if (!r.ok || !j.go) throw new Error(j.error || "something went wrong");
        f.classList.remove("dirty");
        ghost(null);
        const url = new URL(j.go, location);
        const m = url.pathname.match(/^\/m\/([^/]+)$/);
        const editedThisMap = key(f.dataset.id) === key(d.id);
        if (m && key(decodeURIComponent(m[1])) === key(d.id) && !editedThisMap) {
          await reloadPins();
          await select(url.searchParams.get("sel") || d.id, {pan: true, force: true});
        } else {
          location.href = url.href;
        }
      } catch (x) {
        if (err) { err.textContent = x.message; err.hidden = false; err.scrollIntoView({block: "nearest"}); }
        else alert(x.message);
      } finally {
        buttons.forEach(b => { b.disabled = false; });
      }
    });

    let ghostPin = null;    // where a new thing will go, while its form is open
    function ghost(latlng) {
      if (ghostPin) map.removeLayer(ghostPin);
      ghostPin = latlng ? L.marker(latlng, {icon: L.divIcon({className: "pin k-ghost", html: '<span class="dot"></span>',
                                                               iconSize: [22, 22], iconAnchor: [11, 11]}),
                                            interactive: false}).addTo(map) : null;
    }
    addEventListener("popstate", () => {
      select(new URL(location).searchParams.get("sel") || d.id, {push: false});
    });

    // --- adding, placing and moving pins ----------------------------------
    let mode = null;     // {kind: "add"} | {kind: "pick"} | {kind: "place", id} | {kind: "move", id}

    function say(html) {
      hint.innerHTML = html;
      hint.hidden = !html;
    }

    function setMode(m, message) {
      const was = mode;
      if (mode && mode.kind === "move") markers[key(mode.id)]?.dragging.disable();
      mode = m;
      el.classList.toggle("adding", !!m && m.kind !== "move");
      $("#addbtn")?.classList.toggle("on", !!m && m.kind === "add");
      say(m ? `${message} <button type="button" class="btn tiny" id="cancelmode">${m.kind === "move" ? "Done" : "Cancel"}</button>` : "");
      $("#cancelmode")?.addEventListener("click", () => setMode(null));
      if (m) showPane(false);
      else if (was?.kind === "pick") showPane(true);     // back to the form
    }

    const esc = s => s.replace(/[&<>"]/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"})[c]);

    function startPlace(id) {
      setMode({kind: "place", id}, `Click the map where <b>${esc(id)}</b> is`);
    }

    function startMove(id) {
      const m = markers[key(id)];
      if (!m) return;
      setMode({kind: "move", id}, `Drag <b>${esc(id)}</b>, or click where it goes`);
      m.dragging.enable();
    }

    async function savePos(id, latlng) {
      const [x, y] = fromLL(latlng);
      try {
        await post("/api/pos", {id, x: x.toFixed(4), y: y.toFixed(4)});
        markers[key(id)]?.setLatLng(toLL(x, y));
      } catch (err) {
        alert(`Couldn't save: ${err.message}`);
      }
    }

    async function mapClick(e) {
      if (!mode) return;
      const [x, y] = fromLL(e.latlng);
      if (mode.kind === "add") {
        const q = new URLSearchParams({place: d.id, x: x.toFixed(4), y: y.toFixed(4)});
        setMode(null);
        await openForm("/form/new?" + q);     // its spot row shows the marker
      } else if (mode.kind === "place") {
        const id = mode.id;
        try {
          await post("/api/pos", {id, x: x.toFixed(4), y: y.toFixed(4)});
          setMode(null);
          await reloadPins();
          await select(id, {force: true});
          showPane(true);
        } catch (err) {
          alert(`Couldn't save: ${err.message}`);
        }
      } else if (mode.kind === "pick") {
        setMode(null);
        setSpot([x, y]);
        showPane(true);
      } else if (mode.kind === "move") {
        const m = markers[key(mode.id)];
        m.setLatLng(e.latlng);
        savePos(mode.id, e.latlng);
      }
    }
    map.on("click", mapClick);
    $("#addbtn")?.addEventListener("click", () =>
      mode && mode.kind === "add" ? setMode(null) : setMode({kind: "add"}, "Click the map where the new thing is"));

    // --- filtering ----------------------------------------------------------
    function applyFilter() {
      const q = filter.value.trim().toLowerCase();
      const hits = [];
      for (const p of pins) {
        const m = markers[key(p.id)];
        const hit = !q || p.search.includes(q);
        if (q && hit) hits.push(p);
        for (const node of [m.getElement(), m.getTooltip()?.getElement()]) {
          node?.classList.toggle("dim", !hit);
          node?.classList.toggle("hit", !!q && hit);
        }
      }
      return hits;
    }
    filter?.addEventListener("input", applyFilter);
    filter?.addEventListener("keydown", e => {
      if (e.key === "Enter") {
        e.preventDefault();
        const q = filter.value.trim();
        const hits = applyFilter();
        if (hits.length === 1) select(hits[0].id, {pan: true});
        else if (!hits.length && q) location.href = "/search?go=1&q=" + encodeURIComponent(q);
      } else if (e.key === "Escape") {
        filter.value = "";
        applyFilter();
        filter.blur();
      }
    });

    addEventListener("keydown", e => {
      if (typing(e)) return;
      if (e.key === "Escape") {
        if (mode) setMode(null); else if (!$("form.itemform", pane)) select(d.id);
      } else if (e.key === "/") {
        e.preventDefault();
        filter?.focus();
      } else if ((e.key === "a" || e.key === "A") && !d.readonly && !e.ctrlKey && !e.metaKey) {
        setMode({kind: "add"}, "Click the map where the new thing is");
      }
    });

    drawPins(pins);
    const first = highlight(d.pin);
    if (first && !map.getBounds().contains(first.getLatLng())) map.panTo(first.getLatLng());
    peekLabel();
    new ResizeObserver(() => map.invalidateSize()).observe(el);
    return map;
  }

  // --- every page -------------------------------------------------------------
  function markNav() {
    const path = location.pathname;
    for (const a of $$("header.top nav a[data-match]")) {
      const on = a.dataset.match.split(" ").some(m => m === "/" ? path === "/" : path.startsWith(m));
      a.classList.toggle("on", on);
    }
  }

  function nameList() {
    const input = $("#q"), list = $("#allnames");
    if (!input || !list) return;
    let loaded = false;
    input.addEventListener("focus", async () => {
      if (loaded) return;
      loaded = true;
      const names = await fetch("/api/names").then(r => r.json()).catch(() => []);
      for (const n of names) {
        const o = document.createElement("option");
        o.value = n.id;
        o.label = n.where || (n.kind === "place" ? "place" : "");
        list.append(o);
      }
    });
  }

  function tableFilter(input) {
    const table = document.getElementById(input.dataset.for);
    input.addEventListener("input", () => {
      const q = input.value.trim().toLowerCase();
      for (const tr of $$("tbody tr", table)) tr.hidden = !!q && !tr.textContent.toLowerCase().includes(q);
    });
  }

  function sortableTable(table) {
    const value = td => {
      const s = td.dataset.sort ?? td.textContent.trim();
      const n = parseFloat(s);
      return s !== "" && !isNaN(n) && /^-?[\d.]/.test(s) ? n : s.toLowerCase();
    };
    $$("thead th", table).forEach((th, i) => th.addEventListener("click", () => {
      const asc = !th.classList.contains("sorted-asc");
      $$("thead th", table).forEach(h => h.classList.remove("sorted-asc", "sorted-desc"));
      th.classList.add(asc ? "sorted-asc" : "sorted-desc");
      const body = table.tBodies[0];
      const rows = [...body.rows].sort((a, b) => {
        const x = value(a.cells[i]), y = value(b.cells[i]);
        if (x === "" && y !== "") return 1;
        if (y === "" && x !== "") return -1;
        return (x < y ? -1 : x > y ? 1 : 0) * (asc ? 1 : -1);
      });
      body.append(...rows);
    }));
  }

  /* Paste, drop or pick a photo: it's saved to attachments/ and embedded as ![[name]]. */
  function photoUploads(ta) {
    async function upload(file) {
      const fd = new FormData();
      fd.append("file", file, file.name || "image.png");
      const r = await fetch("/upload", {method: "POST", body: fd});
      const j = await r.json().catch(() => ({}));
      if (!r.ok) { alert(j.error || "upload failed"); return; }
      const text = `![[${j.name}]]`;
      const at = ta.selectionStart ?? ta.value.length;
      const before = ta.value.slice(0, at), after = ta.value.slice(at);
      const pre = before && !before.endsWith("\n") ? "\n" : "";
      ta.value = before + pre + text + "\n" + after;
      ta.selectionStart = ta.selectionEnd = (before + pre + text + "\n").length;
      ta.focus();
    }
    ta.addEventListener("paste", e => {
      const files = [...(e.clipboardData?.files || [])].filter(f => f.type.startsWith("image/"));
      if (files.length) { e.preventDefault(); files.forEach(upload); }
    });
    ta.addEventListener("dragover", e => e.preventDefault());
    ta.addEventListener("drop", e => {
      const files = [...(e.dataTransfer?.files || [])].filter(f => f.type.startsWith("image/"));
      if (files.length) { e.preventDefault(); files.forEach(upload); }
    });
    for (const input of $$(`input[type=file][data-for="${ta.id}"]`)) {
      input.addEventListener("change", () => { [...input.files].forEach(upload); input.value = ""; });
    }
  }

  function kindSwitch(form) {
    for (const r of $$("input[name=kind]", form)) {
      r.addEventListener("change", () => { form.dataset.kind = r.value; });
    }
  }

  /* Wire up forms in `root` (the page, or a form just loaded into the pane). */
  function enhance(root) {
    $$("textarea.notesedit[id]", root).forEach(photoUploads);
    $$("form.itemform", root).forEach(kindSwitch);
  }

  // Asked before any other submit handler (the pane's included) sees it.
  document.addEventListener("submit", e => {
    const f = e.target.closest("form[data-confirm]");
    if (f && !confirm(f.dataset.confirm)) { e.preventDefault(); e.stopPropagation(); }
  }, true);

  document.addEventListener("DOMContentLoaded", () => {
    markNav();
    nameList();
    $$("input.tablefilter").forEach(tableFilter);
    $$("table.sortable").forEach(sortableTable);
    enhance(document);
  });

  return {placeMap};
})();
