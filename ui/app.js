"use strict";

/* POLIZ Kalkulyatori — interfeys mantiqi.
   Hisoblaşning özi Pythonda (poliz.py): bu yerdan /api/<nom> orqali çaqiriladi. */

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

const IS_MAC = /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent);
const MOD = IS_MAC ? "⌘" : "Ctrl+";
const LIVE_DELAY = 160;

const EXAMPLES = [
  ["(5+3)*2", "stek bilan hisoblaş"],
  ["A + B * C", "ustuvorlik"],
  ["(A+B)*(C-D)/E", "murakkab misol"],
  ["x = (a + b) * c;", "qiymat beriş"],
  ["(3 + 4) * 2 - (-5)", "unar minus"],
  ["2 ^ 3 ^ 2", "öngdan assotsiativ"],
  ["(10 + 5) * 2", "infiks → natija"],
];

const ICON = {
  ok: '<svg viewBox="0 0 16 16"><circle cx="8" cy="8" r="7" fill="currentColor" opacity=".16"/><path d="m4.8 8.2 2.2 2.2 4.2-4.6" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>',
  err: '<svg viewBox="0 0 16 16"><path d="M8 1.6 15 14H1z" fill="currentColor" opacity=".16"/><path d="M8 6v3.6" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/><circle cx="8" cy="11.8" r=".9" fill="currentColor"/></svg>',
  back: '<svg viewBox="0 0 20 20"><path d="M7.2 4.5h8.3a1.5 1.5 0 0 1 1.5 1.5v8a1.5 1.5 0 0 1-1.5 1.5H7.2L2.5 10z" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/><path d="m9.5 7.8 4.4 4.4m0-4.4-4.4 4.4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>',
};

const state = {
  result: null,
  values: {},        // özgaruvçi → kiritilgan matn
  varNames: [],     // null — maydonlarni majburan qayta çiziş
  history: [],
  histIndex: null,
  tab: "convert",
  evalMode: "num",
  marks: { err: null, hl: null },
  req: 0,
};

// ------------------------------------------------------------------ server bilan aloqa

async function api(name, ...args) {
  const r = await fetch("/api/" + name, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(args),
  });
  if (!r.ok) throw new Error(`${name}: ${r.status}`);
  return r.json();
}

// ------------------------------------------------------------------ segmentli boşqaruv

function segmented(el, key, onChange) {
  const thumb = $(".thumb", el);
  const buttons = $$("button", el);
  const aria = buttons[0].getAttribute("role") === "tab" ? "aria-selected" : "aria-checked";
  let value = null;

  function move() {
    const b = buttons.find((x) => x.dataset[key] === value);
    if (!b || !b.offsetWidth) return;
    thumb.style.width = b.offsetWidth + "px";
    thumb.style.transform = `translateX(${b.offsetLeft}px)`;
  }
  function set(v, silent) {
    value = v;
    buttons.forEach((b) => {
      const on = b.dataset[key] === v;
      b.setAttribute(aria, String(on));
      b.tabIndex = on ? 0 : -1;
    });
    move();
    if (!silent) onChange(v);
  }
  buttons.forEach((b) => b.addEventListener("click", () => set(b.dataset[key])));
  el.addEventListener("keydown", (e) => {
    const d = { ArrowRight: 1, ArrowLeft: -1 }[e.key];
    if (!d) return;
    const i = buttons.findIndex((b) => b.dataset[key] === value);
    const next = buttons[(i + d + buttons.length) % buttons.length];
    set(next.dataset[key]);
    next.focus();
    e.preventDefault();
  });
  new ResizeObserver(move).observe(el);
  return { set, move, get value() { return value; } };
}

// ------------------------------------------------------------------ mavzu

const darkMq = matchMedia("(prefers-color-scheme: dark)");
let themeMode = "auto";
try { themeMode = localStorage.getItem("poliz-theme") || "auto"; } catch (e) { /* şaxsiy rejim */ }

function applyTheme(mode) {
  themeMode = mode;
  try { localStorage.setItem("poliz-theme", mode); } catch (e) { /* saqlanmasa ham bölaveradi */ }
  const dark = mode === "dark" || (mode === "auto" && darkMq.matches);
  document.documentElement.dataset.theme = dark ? "dark" : "light";
  if (state.result) renderTree(state.result.tree);
}
darkMq.addEventListener("change", () => themeMode === "auto" && applyTheme("auto"));
const themeSeg = segmented($("#themeSeg"), "theme", applyTheme);

// ------------------------------------------------------------------ kiritiş maydoni

const input = $("#expr");
const field = $("#field");
const mirrorBox = $("#mirror");
const mirror = $("#mirror .inner");
const statusEl = $("#status");

function renderMirror() {
  const text = input.value;
  const marks = [state.marks.err && { ...state.marks.err, cls: "err" },
                 state.marks.hl && { ...state.marks.hl, cls: "hl" }]
    .filter(Boolean).sort((a, b) => a.pos - b.pos);
  let html = "";
  let i = 0;
  for (const m of marks) {
    if (m.pos < i) continue;
    html += esc(text.slice(i, m.pos));
    html += `<mark class="${m.cls}">${esc(text.slice(m.pos, m.pos + m.length) || " ")}</mark>`;
    i = m.pos + m.length;
  }
  mirror.innerHTML = html + esc(text.slice(i)) + " ";
  syncMirror();
}
function syncMirror() { mirrorBox.scrollLeft = input.scrollLeft; }
["scroll", "keyup", "select", "click"].forEach((ev) => input.addEventListener(ev, syncMirror));

function setStatus(text, kind = "") {
  statusEl.className = "status " + kind;
  statusEl.innerHTML = (kind === "ok" ? ICON.ok : kind === "err" ? ICON.err : "") + `<span>${esc(text)}</span>`;
}

function hint() {
  setStatus("Ifoda kiriting: sonlar, özgaruvçilar (A, x1), + − * / ^ va qavslar. Enter — hisoblaş");
}

function insertText(text) {
  const { selectionStart: s, selectionEnd: e, value } = input;
  let t = text;
  if (t.startsWith(" ") && (s === 0 || value[s - 1] === " ")) t = t.trimStart();
  input.setRangeText(t, s, e, "end");
  input.dispatchEvent(new Event("input"));
}

function backspace() {
  const { selectionStart: s, selectionEnd: e, value } = input;
  if (s !== e) {
    input.setRangeText("", s, e, "end");
  } else {
    // " + " bitta tugma bilan qöşilgani uçun böşliqlari bilan birga öçadi
    const before = value.slice(0, s).trimEnd();
    let kept = before.slice(0, -1);
    if ("+-*/^".includes(before.slice(-1))) kept = kept.trimEnd();
    input.setRangeText("", kept.length, s, "end");
  }
  input.dispatchEvent(new Event("input"));
}

function loadExpr(expr, run = true) {
  input.value = expr;
  input.focus();
  input.setSelectionRange(expr.length, expr.length);
  state.marks = { err: null, hl: null };
  field.classList.remove("error");
  renderMirror();
  calculate(run);
}

function clearAll() {
  input.value = "";
  state.histIndex = null;
  state.marks = { err: null, hl: null };
  field.classList.remove("error");
  renderMirror();
  state.req++;
  state.result = null;
  renderVars([]);
  renderResult(null);
  hint();
  input.focus();
}

let liveTimer = null;
input.addEventListener("input", () => {
  state.histIndex = null;
  state.marks = { err: null, hl: null };
  field.classList.remove("error");
  renderMirror();
  clearTimeout(liveTimer);
  liveTimer = setTimeout(() => calculate(false), LIVE_DELAY);
});

input.addEventListener("keydown", (e) => {
  if (e.key === "Enter") {
    e.preventDefault();
    calculate(true);
  } else if (e.key === "ArrowUp" || e.key === "ArrowDown") {
    e.preventDefault();
    historyStep(e.key === "ArrowUp" ? -1 : 1);
  }
});

// ------------------------------------------------------------------ hisoblaş

async function calculate(commit) {
  clearTimeout(liveTimer);
  const expr = input.value;
  const id = ++state.req;

  if (!expr.trim()) {
    state.result = null;
    renderVars([]);
    renderResult(null);
    if (commit) showError({ message: "Ifoda kiritilmagan", pos: null });
    else hint();
    return;
  }

  let res;
  try {
    res = await api("calculate", expr, validValues());
  } catch (err) {
    setStatus("Hisoblaş serveri bilan aloqa yöq. Dasturni qayta işga tuşiring.", "err");
    return;
  }
  if (id !== state.req) return; // eskirgan javob

  if (!res.ok) {
    state.result = null;
    renderResult(null);
    if (commit) renderVars([]); // yozib turganda maydonlar "sakramasin", Enterda tozalanadi
    if (commit) showError(res.error);
    else setStatus("Kiritişni davom ettiring…  Enter — tekşiriş");
    return;
  }

  const r = res.result;
  state.result = r;
  renderVars(r.variables);
  renderResult(r);
  if (r.missing.length) {
    setStatus(`POLIZ tayyor. Son natija uçun qiymat kiriting: ${r.missing.join(", ")}`, "ok");
  } else {
    setStatus(commit ? "Hisoblandi" : "Ifoda töğri", "ok");
  }
  if (commit) addHistory(r);
}

function showError(err) {
  state.marks.err = err.pos == null ? null : { pos: err.pos, length: err.length || 1 };
  renderMirror();
  const where = err.pos == null ? "" : `  (${err.pos + 1}-belgi)`;
  setStatus(err.message + where, "err");
  field.classList.add("error");
  field.classList.remove("shake");
  void field.offsetWidth; // animatsiyani qayta boşlaş
  field.classList.add("shake");
  input.focus();
  if (err.pos != null) input.setSelectionRange(err.pos, err.pos);
}

// ------------------------------------------------------------------ özgaruvçilar

function validValues() {
  const out = {};
  for (const [k, v] of Object.entries(state.values)) {
    if (v.trim() && !isNaN(Number(v.trim().replace(",", ".").replace("−", "-")))) out[k] = v;
  }
  return out;
}

function renderVars(names) {
  const box = $("#vars");
  const grid = $("#varsGrid");
  if (state.varNames && names.join("\u0000") === state.varNames.join("\u0000")) return;
  state.varNames = names;
  box.hidden = names.length === 0;
  const focused = document.activeElement && document.activeElement.dataset.var;
  grid.innerHTML = names.map((n) => `
    <label class="var-field"><span>${esc(n)} =</span>
      <input data-var="${esc(n)}" inputmode="decimal" placeholder="?" autocomplete="off"
             spellcheck="false" value="${esc(state.values[n] || "")}" aria-label="${esc(n)} qiymati">
    </label>`).join("");
  $$("input", grid).forEach((inp, i, all) => {
    const check = () => {
      const v = inp.value.trim();
      inp.parentElement.classList.toggle("bad", v !== "" && isNaN(Number(v.replace(",", ".").replace("−", "-"))));
    };
    check();
    inp.addEventListener("input", () => {
      state.values[inp.dataset.var] = inp.value;
      check();
      clearTimeout(liveTimer);
      liveTimer = setTimeout(() => calculate(false), LIVE_DELAY);
    });
    inp.addEventListener("keydown", (e) => {
      if (e.key !== "Enter") return;
      e.preventDefault();
      if (i + 1 < all.length) all[i + 1].focus();
      else calculate(true);
    });
    if (inp.dataset.var === focused) inp.focus();
  });
}

// ------------------------------------------------------------------ natijani çiziş

function renderResult(r) {
  const polizEl = $("#poliz");
  const resEl = $("#result");
  const title = $("#resultTitle");
  state.marks.hl = null;
  renderMirror();

  if (!r) {
    polizEl.innerHTML = '<span class="empty">Ifoda hisoblangaç şu yerda paydo böladi</span>';
    resEl.className = "result placeholder";
    resEl.textContent = "—";
    title.textContent = "Natija";
  } else {
    polizEl.innerHTML = r.poliz.map((t, i) =>
      `<span class="tok ${t.kind}" style="animation-delay:${Math.min(i * 22, 400)}ms">${esc(t.text)}</span>`).join("");
    if (r.value != null) {
      resEl.className = "result";
      resEl.innerHTML = (r.target ? `<span class="eq">${esc(r.target)} = </span>` : "") + esc(r.value);
      title.textContent = "Natija";
    } else {
      resEl.className = "result symbolic";
      resEl.textContent = r.symbolic;
      title.textContent = "Natija (harflarda)";
    }
  }
  renderPanels();
}

function stackCell(items) {
  if (!items.length) return '<span class="none">∅</span>';
  return items.map((s) => `<span>${esc(s)}</span>`).join("");
}

function emptyState(big, text) {
  return `<div class="empty-state"><div class="big">${big}</div><p>${text}</p></div>`;
}

function stepTable(steps, columns) {
  const head = columns.map((c) => `<th>${c}</th>`).join("");
  const rows = steps.map((s, i) => {
    const cls = i === steps.length - 1 ? "final" : "";
    const cells = [
      `<td class="n">${i + 1}</td>`,
      `<td class="t">${esc(s.token)}</td>`,
      `<td class="act">${esc(s.action)}</td>`,
      `<td class="stack">${stackCell(s.stack)}</td>`,
    ];
    if (columns.length === 5) cells.push(`<td class="mono">${esc(s.output.join(" "))}</td>`);
    return `<tr class="${cls}" data-i="${i}" style="animation-delay:${Math.min(i * 18, 360)}ms">${cells.join("")}</tr>`;
  }).join("");
  return `<div class="table-wrap" tabindex="0"><table><thead><tr>${head}</tr></thead><tbody>${rows}</tbody></table></div>`;
}

function bindRows(panel, steps) {
  const wrap = $(".table-wrap", panel);
  if (!wrap) return;
  const rows = $$("tbody tr", wrap);
  const select = (i) => {
    rows.forEach((r) => r.classList.toggle("sel", +r.dataset.i === i));
    const s = steps[i];
    state.marks.hl = s && s.pos != null ? { pos: s.pos, length: s.length } : null;
    renderMirror();
    if (rows[i]) rows[i].scrollIntoView({ block: "nearest" });
    wrap.dataset.sel = i;
  };
  rows.forEach((r) => r.addEventListener("click", () => select(+r.dataset.i)));
  wrap.addEventListener("keydown", (e) => {
    const d = { ArrowDown: 1, ArrowUp: -1 }[e.key];
    if (!d) return;
    e.preventDefault();
    const cur = wrap.dataset.sel == null ? -1 : +wrap.dataset.sel;
    select(Math.max(0, Math.min(rows.length - 1, cur + d)));
  });
}

function renderPanels() {
  const r = state.result;
  const pConv = $('[data-panel="convert"]');
  const pEval = $('[data-panel="eval"]');
  const pTree = $('[data-panel="tree"]');

  const evalSeg = $("#evalMode");
  const hasBoth = r && r.variables.length > 0 && r.value != null;
  evalSeg.hidden = !(hasBoth && state.tab === "eval");
  if (!evalSeg.hidden) evalModeSeg.move();

  if (!r) {
    pConv.innerHTML = emptyState("A B +", "Ifodani kiriting — bu yerda u Deykstra algoritmi bilan POLIZga qanday ötkazilişi qadamma-qadam körsatiladi.");
    pEval.innerHTML = emptyState("[ 5 3 ]", "POLIZ çapdan öngga öqiladi: operand stekka joylanadi, operator kelganda stekdan ikkita operand olinadi.");
    pTree.innerHTML = emptyState("+<br>╱ ╲", "Ifoda daraxti hisoblaşdan keyin çiziladi.");
    return;
  }

  pConv.innerHTML = stepTable(r.convert_steps, ["№", "Token", "Amal", "Stek", "Çiqiş (POLIZ)"]);
  bindRows(pConv, r.convert_steps);

  const symbolic = r.value == null || (hasBoth && state.evalMode === "sym");
  const steps = symbolic ? r.symbolic_steps : r.eval_steps;
  let note = "";
  if (r.value == null) {
    note = `<div class="panel-note">Özgaruvçilarga qiymat berilmagan — hisoblaş <b>harflarda</b> körsatilgan.
            Son natija uçun çapdagi maydonlarga qiymat kiriting.</div>`;
  }
  pEval.innerHTML = note + stepTable(steps, ["№", "Token", "Amal", "Stek"]);
  bindRows(pEval, steps);

  pTree.innerHTML = `<div class="tree-wrap"><div class="caption">Daraxtni pastdan yuqoriga, çapdan öngga aylanib öqisangiz — POLIZ hosil böladi.</div><svg id="treeSvg" role="img" aria-label="Ifoda daraxti"></svg></div>`;
  if (state.tab === "tree") renderTree(r.tree);
}

// ------------------------------------------------------------------ daraxt

function renderTree(tree) {
  const svg = $("#treeSvg");
  if (!svg || !svg.clientWidth) return;
  const nodes = [];
  let leafX = 0;
  const GAP = 18, LEVEL = 74, H = 36;

  (function place(n, depth) {
    const w = Math.max(40, n.label.length * 8.6 + 24);
    let x;
    if (!n.children.length) {
      x = leafX + w / 2;
      leafX += w + GAP;
    } else {
      const xs = n.children.map((c) => place(c, depth + 1));
      x = xs.reduce((a, b) => a + b, 0) / xs.length;
      if (n.children.length === 1) leafX = Math.max(leafX, x + w / 2 + GAP);
    }
    n._x = x; n._y = depth * LEVEL + H / 2; n._w = w;
    nodes.push(n);
    return x;
  })(tree, 0);

  const width = Math.max(leafX - GAP, 40);
  const height = Math.max(...nodes.map((n) => n._y)) + H / 2;
  const pad = 24;
  const scale = Math.min(1.35, (svg.clientWidth - 2 * pad) / width, (svg.clientHeight - 2 * pad) / height);
  const s = Math.max(scale, 0.35);
  const ox = (svg.clientWidth - width * s) / 2;
  const oy = Math.max(pad, (svg.clientHeight - height * s) / 2);

  let edges = "";
  let boxes = "";
  nodes.forEach((n) => {
    n.children.forEach((c) => {
      const y1 = n._y + H / 2, y2 = c._y - H / 2, my = (y1 + y2) / 2;
      edges += `<path class="tree-edge" d="M${n._x},${y1} C${n._x},${my} ${c._x},${my} ${c._x},${y2}"/>`;
    });
  });
  nodes.slice().reverse().forEach((n, i) => {
    boxes += `<g class="tree-node ${n.kind}" style="animation-delay:${i * 30}ms">
      <rect x="${n._x - n._w / 2}" y="${n._y - H / 2}" width="${n._w}" height="${H}" rx="12"/>
      <text x="${n._x}" y="${n._y}">${esc(n.label)}</text></g>`;
  });
  svg.innerHTML = `<g transform="translate(${ox},${oy}) scale(${s})">${edges}${boxes}</g>`;
}

new ResizeObserver(() => {
  if (state.tab === "tree" && state.result) renderTree(state.result.tree);
}).observe($(".col-right"));

// ------------------------------------------------------------------ bölimlar

const tabsSeg = segmented($("#tabs"), "tab", (tab) => {
  state.tab = tab;
  $$(".panel").forEach((p) => { p.hidden = p.dataset.panel !== tab; });
  $("#clearHistory").hidden = tab !== "history" || !state.history.length;
  renderPanels();
});
const evalModeSeg = segmented($("#evalMode"), "mode", (mode) => {
  state.evalMode = mode;
  renderPanels();
});

// ------------------------------------------------------------------ tarix

function renderHistory() {
  const panel = $('[data-panel="history"]');
  const badge = $("#histCount");
  badge.hidden = !state.history.length;
  badge.textContent = state.history.length;
  $("#clearHistory").hidden = state.tab !== "history" || !state.history.length;
  if (!state.history.length) {
    panel.innerHTML = emptyState("↺", "Hisoblangan ifodalar şu yerda saqlanadi. Ularni kiritiş maydonida ↑ / ↓ bilan ham çaqiriş mumkin.");
    return;
  }
  panel.innerHTML = `<div class="table-wrap"><ul class="history-list">${state.history.map((h, i) => `
    <li tabindex="0" data-i="${i}" title="Bosing — qayta yuklaş">
      <span class="e">${esc(h.expr)}</span>
      <span class="v ${h.value == null ? "sym" : ""}">${esc(h.value == null ? h.symbolic : h.value)}</span>
      <span class="p">${esc(h.poliz)}</span>
    </li>`).join("")}</ul></div>`;
  $$("li", panel).forEach((li) => {
    const open = () => {
      const h = state.history[+li.dataset.i];
      Object.assign(state.values, h.values || {});
      state.varNames = null;
      loadExpr(h.expr);
      tabsSeg.set("convert");
    };
    li.addEventListener("click", open);
    li.addEventListener("keydown", (e) => { if (e.key === "Enter") open(); });
  });
}

async function addHistory(r) {
  const values = {};
  r.variables.forEach((v) => { if (state.values[v]) values[v] = state.values[v]; });
  const item = { expr: r.expression.trim(), poliz: r.poliz_text, value: r.value,
                 symbolic: r.symbolic, values };
  try { state.history = await api("add_history", item); } catch (e) { return; }
  renderHistory();
}

function historyStep(delta) {
  if (!state.history.length) return;
  let idx;
  if (state.histIndex == null) {
    if (delta > 0) return;
    idx = 0;
  } else {
    idx = Math.min(state.history.length - 1, state.histIndex - delta);
  }
  if (idx < 0) {
    state.histIndex = null;
    loadExpr("", false);
    hint();
    return;
  }
  state.histIndex = idx;
  const h = state.history[idx];
  Object.assign(state.values, h.values || {});
  state.varNames = null; // maydonlar yangi qiymatlar bilan qayta çizilsin
  loadExpr(h.expr, false);
}

$("#clearHistory").addEventListener("click", async () => {
  try { state.history = await api("clear_history"); } catch (e) { return; }
  renderHistory();
  toast("Tarix tozalandi");
});

// ------------------------------------------------------------------ nusxalaş, toast

let toastTimer = null;
function toast(text) {
  const t = $("#toast");
  t.textContent = text;
  t.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove("show"), 2200);
}

async function copy(what) {
  const r = state.result;
  if (!r) { toast("Avval ifodani hisoblang"); return; }
  const text = what === "poliz" ? r.poliz_text
    : r.value != null ? (r.target ? `${r.target} = ${r.value}` : r.value) : r.symbolic;
  let ok = false;
  try { await navigator.clipboard.writeText(text); ok = true; } catch (e) { /* zaxira yöl pastda */ }
  if (!ok) { try { ok = await api("copy", text); } catch (e) { ok = false; } }
  toast(ok ? `Nusxalandi: ${text}` : "Nusxalab bölmadi");
}
$$("[data-copy]").forEach((b) => b.addEventListener("click", () => copy(b.dataset.copy)));

// ------------------------------------------------------------------ ekran klaviaturasi

const KEYS = [
  ["(", "(", "op"], [")", ")", "op"], ["xʸ", " ^ ", "op", "Darajaga kötariş"], [ICON.back, "BACK", "fn", "Oxirgi belgini öçiriş"],
  ["7", "7"], ["8", "8"], ["9", "9"], ["÷", " / ", "op", "Böliş"],
  ["4", "4"], ["5", "5"], ["6", "6"], ["×", " * ", "op", "Köpaytiriş"],
  ["1", "1"], ["2", "2"], ["3", "3"], ["−", " - ", "op", "Ayiriş"],
  ["0", "0"], [".", "."], ["C", "CLEAR", "fn", "Tozalaş (Esc)"], ["+", " + ", "op", "Qöşiş"],
];
$("#keypad").innerHTML = KEYS.map(([label, val, kind = "", title = ""]) =>
  `<button class="key ${kind}" data-key="${esc(val)}" tabindex="-1" ${title ? `title="${title}" aria-label="${title}"` : ""}>${label}</button>`).join("");
$$("#keypad .key").forEach((k) => {
  k.addEventListener("mousedown", (e) => e.preventDefault()); // kursor maydonda qolsin
  k.addEventListener("click", () => {
    const v = k.dataset.key;
    if (document.activeElement !== input) input.focus();
    if (v === "BACK") backspace();
    else if (v === "CLEAR") clearAll();
    else insertText(v);
  });
});
$("#calcBtn").addEventListener("click", () => calculate(true));

// ------------------------------------------------------------------ namunalar menyusi

const menu = $("#examplesMenu");
const menuBtn = $("#examplesBtn");
menu.innerHTML = '<div class="label">Namunalar (PDF dan)</div>' + EXAMPLES.map(([e, d]) =>
  `<button role="menuitem" data-ex="${esc(e)}">${esc(e)} <small>${esc(d)}</small></button>`).join("");

function openMenu() {
  const r = menuBtn.getBoundingClientRect();
  menu.hidden = false;
  menu.style.top = r.bottom + 6 + "px";
  menu.style.left = Math.max(8, r.right - menu.offsetWidth) + "px";
  menuBtn.setAttribute("aria-expanded", "true");
  $("button", menu).focus();
}
function closeMenu(refocus = true) {
  if (menu.hidden) return;
  menu.hidden = true;
  menuBtn.setAttribute("aria-expanded", "false");
  if (refocus) input.focus();
}
menuBtn.addEventListener("click", () => (menu.hidden ? openMenu() : closeMenu()));
$$("button", menu).forEach((b) => b.addEventListener("click", () => { closeMenu(); loadExpr(b.dataset.ex); }));
menu.addEventListener("keydown", (e) => {
  const items = $$("button", menu);
  const i = items.indexOf(document.activeElement);
  const d = { ArrowDown: 1, ArrowUp: -1 }[e.key];
  if (d) { items[(i + d + items.length) % items.length].focus(); e.preventDefault(); }
});
document.addEventListener("mousedown", (e) => {
  if (!menu.hidden && !menu.contains(e.target) && e.target !== menuBtn) closeMenu(false);
});

// ------------------------------------------------------------------ qöllanma

const help = $("#help");
function openHelp() { help.hidden = false; $("#helpClose").focus(); }
function closeHelp() { help.hidden = true; input.focus(); }
$("#helpBtn").addEventListener("click", openHelp);
$("#helpClose").addEventListener("click", closeHelp);
help.addEventListener("mousedown", (e) => { if (e.target === help) closeHelp(); });
$$("[data-try]", help).forEach((b) => b.addEventListener("click", () => { closeHelp(); loadExpr(b.dataset.try); }));

// ------------------------------------------------------------------ klaviatura yorliqlari

const SHORTCUTS = [
  ["Enter", "hisoblaş"],
  ["Esc", "tozalaş"],
  ["↑ ↓", "tarixdagi ifodalar"],
  [`${MOD}⇧C`.replace("+⇧", "+Shift+"), "natijani nusxalaş"],
  [`${MOD}1–4`, "bölimlar"],
  ["F1", "qöllanma"],
];
$("#footer").innerHTML = SHORTCUTS.map(([k, d]) => `<span><kbd>${k}</kbd> ${d}</span>`).join("");
$("#shortcutTable").innerHTML = SHORTCUTS.map(([k, d]) => `<tr><td><kbd>${k}</kbd></td><td>${d}</td></tr>`).join("");

document.addEventListener("keydown", (e) => {
  const mod = IS_MAC ? e.metaKey : e.ctrlKey;
  if (e.key === "Escape") {
    if (!menu.hidden) closeMenu();
    else if (!help.hidden) closeHelp();
    else clearAll();
    e.preventDefault();
  } else if (e.key === "F1" || (mod && e.key === "/")) {
    help.hidden ? openHelp() : closeHelp();
    e.preventDefault();
  } else if (mod && e.shiftKey && e.key.toLowerCase() === "c") {
    copy("result");
    e.preventDefault();
  } else if (mod && /^[1-4]$/.test(e.key)) {
    tabsSeg.set(["convert", "eval", "tree", "history"][+e.key - 1]);
    e.preventDefault();
  }
});

// ------------------------------------------------------------------ işga tuşiriş

(async function init() {
  themeSeg.set(themeMode, true);
  tabsSeg.set("convert", true);
  evalModeSeg.set("num", true);
  $$(".panel").forEach((p) => { p.hidden = p.dataset.panel !== "convert"; });
  renderResult(null);
  hint();
  try { state.history = await api("history"); } catch (e) { state.history = []; }
  renderHistory();
  input.focus();
})();
