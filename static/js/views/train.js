import { get, post, patch, del } from "../api.js";
import { esc, icon } from "../fmt.js";
import { toast, openDialog, confirmDialog, setBusy } from "../ui.js";
import { mediaView, thumb } from "../media.js";
import { exName } from "../labels.js";
import { mmss, human, num, parseNum, targetText, dateShort } from "../util.js";
import { beep, vibrate, unlock, wake } from "../audio.js";
import { pickExercise } from "./picker.js";

const root = () => document.getElementById("view-train");
let S = null, ui = null, settings = { units: "kg", sound: "1", vibrate: "1", wake_lock: "1" }, exCache = {}, lastCache = {}, tick = null, saveT = null, beeped = new Set();

const notify = () => window.dispatchEvent(new Event("training:session"));
const item = () => (S && S.plan[ui.idx]) || null;
const logged = (idx = ui.idx) => S.sets.filter((s) => s.position === idx);
const planned = (it) => it.sets || 1;

function saveState() {
  clearTimeout(saveT);
  saveT = setTimeout(() => S && patch(`/api/sessions/${S.id}`, { state: ui }).catch(() => {}), 400);
}
function normState() {
  const st = S.state || {};
  if (typeof st.idx === "number" && st.phase) { ui = { idx: st.idx, phase: st.phase, t0: st.t0 || Date.now(), restTotal: st.restTotal || 0 }; return; }
  let idx = S.plan.findIndex((it, i) => logged(i).length < planned(it));
  if (idx < 0) idx = S.plan.length;
  ui = { idx, phase: "ready", t0: Date.now(), restTotal: 0 };
}

async function exOf(id) { return (exCache[id] = exCache[id] || (await get(`/api/exercises/${encodeURIComponent(id)}`))); }
async function lastOf(id) {
  if (id in lastCache) return lastCache[id];
  const p = await get(`/api/exercises/${encodeURIComponent(id)}/progress`).catch(() => []);
  return (lastCache[id] = p.length ? p[p.length - 1] : null);
}

/* ------------------------------------------------------------------ pantalla de inicio */
async function renderStart() {
  const [rs, recent, st] = await Promise.all([get("/api/routines"), get("/api/sessions?limit=5"), get("/api/stats?weeks=2")]);
  const todayN = ((new Date().getDay() + 6) % 7) + 1;
  rs.sort((a, b) => Number(b.weekdays.includes(todayN)) - Number(a.weekdays.includes(todayN)));
  root().innerHTML = `<header class="view-head"><div><h1 id="h-train">Entrenar</h1><p class="muted">Elige una rutina o entrena libremente. Se cronometran los ejercicios y los descansos.</p></div></header>
    <div class="routines">${rs.map((r) => `<article class="glass card routine ${r.weekdays.includes(todayN) ? "today" : ""}"><div class="row-between"><div><h3>${esc(r.name)}</h3><p class="muted small">${r.items.length} ejercicios${r.weekdays.includes(todayN) ? " · <b class=\"accent\">toca hoy</b>" : ""}</p></div>
      <button class="btn primary" type="button" data-start="${r.id}">${icon("play")}Empezar</button></div><div class="thumbs">${r.items.slice(0, 7).map((i) => thumb(i)).join("")}</div></article>`).join("")}
      <article class="glass card routine"><div class="row-between"><div><h3>Entrenamiento libre</h3><p class="muted small">Añade los ejercicios sobre la marcha</p></div><button class="btn" type="button" data-start="">${icon("play")}Empezar</button></div></article></div>
    ${recent.length ? `<h2 class="sub-h">Últimos entrenamientos</h2><div class="glass card list">${recent.map((s) => `<div class="mrow"><div><b>${esc(s.routine_name || "Libre")}</b><small class="muted"> ${dateShort(s.started)} · ${human(s.total_s)} · ${s.sets_done} series</small></div></div>`).join("")}</div>` : ""}`;
  const q = new URLSearchParams((location.hash.split("?")[1] || ""));
  if (q.get("routine")) { history.replaceState(null, "", "#/train"); start(Number(q.get("routine"))); }
}

async function start(rid) {
  unlock();
  try {
    S = await post("/api/sessions", rid ? { routine_id: rid } : {});
    normState();
    if (!S.plan.length) { await addExercise(true); }
    notify(); await render();
  } catch (x) { toast({ text: x.message, kind: "err" }); }
}

/* ------------------------------------------------------------------ jugador */
function targets(it) {
  const done = logged();
  const last = done[done.length - 1];
  return { reps: last && last.reps != null ? last.reps : it.reps_max || it.reps_min || "", weight: last && last.weight != null ? last.weight : it.weight || "" };
}

async function render() {
  if (!S) return renderStart();
  const it = item();
  const total = S.plan.length;
  if (!it) return renderDone();
  const e = await exOf(it.exercise_id);
  const lt = await lastOf(it.exercise_id);
  const n = logged().length, setNo = Math.min(n + 1, planned(it) + 99);
  const t = targets(it);
  const reps = it.tracking === "reps";
  const u = settings.units;
  const inputs = ui.phase === "rest" ? "" : `<div class="set-inputs">
      ${reps ? `<label>Reps<input class="inp lg" id="in-reps" inputmode="numeric" value="${esc(t.reps)}"></label><label>Peso (${esc(u)})<input class="inp lg" id="in-weight" inputmode="decimal" value="${esc(t.weight)}"></label><label>RPE<input class="inp lg" id="in-rpe" inputmode="decimal" placeholder="1-10"></label>`
        : `<label>Duración (mm:ss)<input class="inp lg" id="in-dur" value="" placeholder="auto"></label>${it.tracking === "cardio" ? `<label>Distancia (km)<input class="inp lg" id="in-dist" inputmode="decimal" placeholder="${it.distance_m ? it.distance_m / 1000 : ""}"></label>` : ""}<label>RPE<input class="inp lg" id="in-rpe" inputmode="decimal" placeholder="1-10"></label>`}</div>`;
  let panel = "";
  if (ui.phase === "ready") panel = `${inputs}<button class="btn primary xl" type="button" data-p="work">${icon("play")}Empezar ${reps ? "serie" : "ejercicio"}</button><button class="btn block" type="button" data-p="quick">Registrar sin cronometrar</button>`;
  else if (ui.phase === "work") panel = `<div class="timer" id="timer"><b id="t-main">0:00</b><small id="t-sub"></small></div>${inputs}<button class="btn primary xl" type="button" data-p="finish">${icon("check")}Terminar ${reps ? "serie" : "ejercicio"}</button>`;
  else {
    const nxt = logged().length >= planned(it) ? S.plan[ui.idx + 0] : it;
    panel = `<div class="timer rest" id="timer"><b id="t-main">0:00</b><small>Descanso</small></div>
      <div class="rest-btns"><button class="btn" type="button" data-p="-15">−15 s</button><button class="btn" type="button" data-p="+15">+15 s</button><button class="btn primary" type="button" data-p="skip">${icon("skip")}Saltar descanso</button></div>
      <p class="muted small center">Siguiente: <b>${esc(exName(S.plan[ui.idx] || it))}</b></p>`;
  }
  const done = logged();
  const planList = S.plan.map((p, i) => { const k = logged(i).length, ok = k >= planned(p); return `<li class="${i === ui.idx ? "on" : ""} ${ok ? "ok" : ""}"><button type="button" data-go="${i}">${ok ? icon("check") : `<span class="num">${i + 1}</span>`}<span class="pn">${esc(exName(p))}</span><small>${k}/${planned(p)}</small></button></li>`; }).join("");
  root().innerHTML = `<header class="view-head"><div><h1 id="h-train">${esc(S.routine_name)}</h1><p class="muted"><span id="clock-total">${mmss(Date.now() / 1000 - S.started)}</span> de entrenamiento · ${S.sets.length} series hechas</p></div>
      <div class="head-actions"><button class="btn" type="button" data-top="add">${icon("plus")}Ejercicio</button><button class="btn primary" type="button" data-top="finish">${icon("check")}Terminar</button><button class="btn danger" type="button" data-top="abandon">Abandonar</button></div></header>
    <div class="player"><section class="glass card now"><div class="now-top"><span class="badge info">Ejercicio ${ui.idx + 1}/${total}</span><span class="badge">${n >= planned(it) ? `Extra · serie ${n + 1}` : `Serie ${setNo}/${planned(it)}`}</span>
      <button class="btn sm" type="button" data-top="extra">+ serie</button><button class="btn sm" type="button" data-top="skipex">Saltar ejercicio</button></div>
      ${mediaView(e, "compact")}<h2>${esc(exName(e))}</h2>
      <p class="target"><b>Objetivo:</b> ${esc(targetText(it, settings.units))}${it.notes ? ` · <span class="muted">${esc(it.notes)}</span>` : ""}</p>
      ${lt ? `<p class="muted small">Última vez: ${lt.best_weight ? `${num(lt.best_weight, 2)} ${esc(u)} × ${lt.best_reps}` : lt.duration_s ? mmss(lt.duration_s) : `${lt.best_reps} reps`} (${lt.date})</p>` : ""}
      ${done.length ? `<div class="chips">${done.map((s) => `<button type="button" class="chip" data-edit="${s.id}" title="Editar serie">${s.weight ? `${num(s.weight, 2)}${esc(u)}×${s.reps}` : s.reps != null ? `${s.reps} reps` : mmss(s.duration_s)}${s.distance_m ? ` · ${num(s.distance_m / 1000, 2)} km` : ""}</button>`).join("")}</div>` : ""}
      <div class="panel">${panel}</div></section>
      <aside class="glass card plan"><h3>Plan</h3><ol class="plan-list">${planList}</ol></aside></div>`;
  runTicker();
}

function renderDone() {
  root().innerHTML = `<header class="view-head"><div><h1 id="h-train">${esc(S.routine_name)}</h1></div></header>
    <div class="glass card center done-card">${icon("trophy", "big")}<h2>¡Rutina completada!</h2><p class="muted">${S.sets.length} series en ${mmss(Date.now() / 1000 - S.started)}. Puedes añadir más ejercicios o terminar ahora.</p>
      <div class="head-actions"><button class="btn" type="button" data-top="add">${icon("plus")}Añadir ejercicio</button><button class="btn primary" type="button" data-top="finish">${icon("check")}Terminar entrenamiento</button></div></div>`;
  clearInterval(tick);
}

function runTicker() {
  clearInterval(tick);
  beeped = new Set();
  const it = item();
  const step = () => {
    const tot = document.getElementById("clock-total");
    if (tot && S) tot.textContent = mmss(Date.now() / 1000 - S.started);
    const main = document.getElementById("t-main");
    if (!main || !it) return;
    const el = (Date.now() - ui.t0) / 1000;
    if (ui.phase === "rest") {
      const left = Math.ceil(ui.restTotal - el);
      main.textContent = mmss(Math.max(0, left));
      if (left <= 3 && left > 0 && !beeped.has(left)) { beeped.add(left); cue(660, 90); }
      if (left <= 0) { cue(990, 280, [200, 80, 200]); endRest(); }
    } else if (ui.phase === "work") {
      const target = it.tracking !== "reps" ? it.duration_s : 0;
      const sub = document.getElementById("t-sub");
      if (target) {
        const left = Math.ceil(target - el);
        main.textContent = left >= 0 ? mmss(left) : "+" + mmss(-left);
        if (sub) sub.textContent = left >= 0 ? `de ${mmss(target)}` : "tiempo extra";
        if (left <= 3 && left > 0 && !beeped.has(left)) { beeped.add(left); cue(660, 90); }
        if (left === 0 && !beeped.has("end")) { beeped.add("end"); cue(990, 280, [200, 80, 200]); }
      } else { main.textContent = mmss(el); if (sub) sub.textContent = it.tracking === "reps" ? "serie en curso" : "cronómetro"; }
    }
  };
  step();
  tick = setInterval(step, 250);
}
function cue(freq, ms, vib) { if (settings.sound === "1") beep({ freq, ms }); if (settings.vibrate === "1" && vib) vibrate(vib); }

async function endRest() {
  clearInterval(tick);
  const last = S.sets[S.sets.length - 1];
  const taken = Math.round(Math.min((Date.now() - ui.t0) / 1000, ui.restTotal + 600));
  if (last && last.rest_s == null) { last.rest_s = taken; patch(`/api/sessions/${S.id}/sets/${last.id}`, { rest_s: taken }).catch(() => {}); }
  ui.phase = "ready"; ui.t0 = Date.now(); saveState(); await render();
}

/* ------------------------------------------------------------------ acciones */
async function logSet(timed) {
  const it = item();
  const el = Math.round((Date.now() - ui.t0) / 1000);
  const g = (id) => { const x = document.getElementById(id); return x ? parseNum(x.value) : null; };
  const durTxt = document.getElementById("in-dur");
  let dur = timed ? el : null;
  if (durTxt && durTxt.value.trim()) { const p = durTxt.value.split(":").map(Number); dur = p.length === 2 ? p[0] * 60 + p[1] : p[0]; }
  const body = { position: ui.idx, exercise_id: it.exercise_id, reps: g("in-reps"), weight: g("in-weight"), duration_s: it.tracking === "reps" ? (timed ? el : null) : dur, distance_m: g("in-dist") != null ? Math.round(g("in-dist") * 1000) : null, rpe: g("in-rpe") };
  if (it.tracking === "reps" && body.reps == null) { toast({ text: "Indica las repeticiones", kind: "warn", timeout: 2500 }); return; }
  const row = await post(`/api/sessions/${S.id}/sets`, body);
  S.sets.push(row);
  delete lastCache[it.exercise_id];
  const k = logged().length;
  const finishedEx = k >= planned(it);
  const nextIdx = finishedEx ? ui.idx + 1 : ui.idx;
  const lastEx = finishedEx && nextIdx >= S.plan.length;
  const rest = lastEx ? 0 : (finishedEx ? it.rest_ex_s : it.rest_s) || 0;
  ui.idx = nextIdx;
  if (rest > 0) { ui.phase = "rest"; ui.restTotal = rest; } else ui.phase = "ready";
  ui.t0 = Date.now(); saveState(); cue(880, 120, [80]);
  await render();
}

async function addExercise(first = false) {
  const e = await pickExercise({ title: first ? "¿Con qué ejercicio empiezas?" : "Añadir ejercicio" });
  if (!e) return;
  const m = (e.media.find((x) => x.kind === "image") || {}).url;
  S.plan.push({ exercise_id: e.id, name: e.name, name_es: e.name_es, tracking: e.tracking, thumb: m || null, sets: e.tracking === "reps" ? 3 : 1, reps_min: 8, reps_max: 12, weight: 0, duration_s: e.tracking === "cardio" ? 900 : e.tracking === "time" ? 30 : null, distance_m: null, rest_s: 90, rest_ex_s: 120, notes: "" });
  await patch(`/api/sessions/${S.id}`, { plan: S.plan });
  if (ui.idx >= S.plan.length - 1 || first) { ui.idx = S.plan.length - 1; ui.phase = "ready"; ui.t0 = Date.now(); saveState(); }
}

async function finishDialog(abandon) {
  if (abandon) {
    if (!(await confirmDialog({ title: "Abandonar entrenamiento", body: "No se guardará en tu historial.", confirm: "Abandonar", danger: true }))) return;
    await post(`/api/sessions/${S.id}/finish`, { abandon: true }); return closeSession();
  }
  const total = Math.round(Date.now() / 1000 - S.started);
  const vol = S.sets.reduce((a, s) => a + (s.weight && s.reps ? s.weight * s.reps : 0), 0);
  const { el } = openDialog(`<h3>Terminar entrenamiento</h3><p class="muted">${S.sets.length} series · ${mmss(total)}${vol ? ` · ${num(vol)} ${esc(settings.units)} de volumen` : ""}</p>
    <div class="fld"><label>¿Cómo ha ido?</label><div class="rating" id="rate">${[1, 2, 3, 4, 5].map((i) => `<button type="button" data-r="${i}" aria-pressed="false">${icon("star")}</button>`).join("")}</div></div>
    <div class="fld"><label for="fin-notes">Notas</label><textarea class="inp area" id="fin-notes" rows="3" maxlength="1500" placeholder="Sensaciones, molestias, qué mejorar…"></textarea></div>
    <div class="dialog-actions"><button class="btn" data-close type="button">Seguir</button><button class="btn primary" id="fin-ok" type="button">Guardar y terminar</button></div>`);
  let rating = null;
  el.querySelector("#rate").addEventListener("click", (e) => { const b = e.target.closest("[data-r]"); if (!b) return; rating = Number(b.dataset.r); el.querySelectorAll("#rate button").forEach((x) => { const on = Number(x.dataset.r) <= rating; x.setAttribute("aria-pressed", String(on)); x.innerHTML = icon(on ? "star-fill" : "star"); }); });
  el.querySelector("#fin-ok").addEventListener("click", async (e) => {
    setBusy(e.currentTarget, true);
    try {
      const r = await post(`/api/sessions/${S.id}/finish`, { total_s: total, rating, notes: el.querySelector("#fin-notes").value });
      el.close(); toast({ text: r.eval_job ? "Entrenamiento guardado. El asistente evaluará tu desempeño y ajustará la rutina." : "Entrenamiento guardado", kind: "ok", timeout: 5000 });
      closeSession(); location.hash = "#/dashboard";
    } catch (x) { toast({ text: x.message, kind: "err" }); setBusy(e.currentTarget, false); }
  });
}

function closeSession() { clearInterval(tick); S = null; ui = null; wake(false); notify(); renderStart(); }

export function init() {
  const r = root();
  r.addEventListener("click", async (e) => {
    const b = e.target.closest("button");
    if (!b) return;
    try {
      if (b.dataset.start !== undefined) return start(b.dataset.start ? Number(b.dataset.start) : null);
      if (!S) return;
      if (b.dataset.p) {
        unlock();
        const p = b.dataset.p;
        if (p === "work") { ui.phase = "work"; ui.t0 = Date.now(); saveState(); await render(); }
        else if (p === "finish") await logSet(true);
        else if (p === "quick") await logSet(false);
        else if (p === "skip") await endRest();
        else if (p === "+15" || p === "-15") { ui.restTotal = Math.max(5, ui.restTotal + Number(p)); saveState(); }
      } else if (b.dataset.top) {
        const a = b.dataset.top;
        if (a === "add") { await addExercise(); await render(); }
        else if (a === "finish") await finishDialog(false);
        else if (a === "abandon") await finishDialog(true);
        else if (a === "extra") { item().sets = planned(item()) + 1; await patch(`/api/sessions/${S.id}`, { plan: S.plan }); if (ui.idx >= S.plan.length) ui.idx = S.plan.length - 1; await render(); }
        else if (a === "skipex") { ui.idx = Math.min(S.plan.length, ui.idx + 1); ui.phase = "ready"; ui.t0 = Date.now(); saveState(); await render(); }
      } else if (b.dataset.go !== undefined) { ui.idx = Number(b.dataset.go); ui.phase = "ready"; ui.t0 = Date.now(); saveState(); await render(); }
      else if (b.dataset.edit) editSet(Number(b.dataset.edit));
    } catch (x) { toast({ text: x.message, kind: "err" }); }
  });
}

function editSet(id) {
  const s = S.sets.find((x) => x.id === id);
  if (!s) return;
  const { el } = openDialog(`<h3>Editar serie</h3><div class="two"><div class="fld"><label>Reps</label><input class="inp" id="es-reps" value="${s.reps ?? ""}" inputmode="numeric"></div><div class="fld"><label>Peso (${esc(settings.units)})</label><input class="inp" id="es-w" value="${s.weight ?? ""}" inputmode="decimal"></div></div>
    <div class="dialog-actions"><button class="btn danger" id="es-del" type="button">${icon("trash")}Borrar</button><span class="spacer"></span><button class="btn" data-close type="button">Cancelar</button><button class="btn primary" id="es-ok" type="button">Guardar</button></div>`);
  el.querySelector("#es-ok").addEventListener("click", async () => {
    const body = { reps: parseNum(el.querySelector("#es-reps").value), weight: parseNum(el.querySelector("#es-w").value) };
    Object.assign(s, await patch(`/api/sessions/${S.id}/sets/${id}`, body)); el.close(); render();
  });
  el.querySelector("#es-del").addEventListener("click", async () => { await del(`/api/sessions/${S.id}/sets/${id}`); S.sets = S.sets.filter((x) => x.id !== id); el.close(); render(); });
}

export async function show() {
  try {
    settings = await get("/api/settings");
    S = await get("/api/sessions/active");
    if (S) { normState(); if (settings.wake_lock === "1") wake(true); await render(); }
    else await renderStart();
  } catch (e) { root().innerHTML = `<div class="empty">${icon("warning")}<p>No se pudo cargar el entrenamiento.</p></div>`; }
}
export const stop = () => clearInterval(tick);
document.addEventListener("visibilitychange", () => { if (!document.hidden && S && settings.wake_lock === "1") wake(true); });
