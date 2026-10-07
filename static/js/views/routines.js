import { get, post, put, del } from "../api.js";
import { esc, icon } from "../fmt.js";
import { toast, openDialog, confirmDialog, setBusy } from "../ui.js";
import { thumb } from "../media.js";
import { exName, WEEKDAY, WEEKDAY_LONG } from "../labels.js";
import { human, mmss, parseMmss, parseNum, targetText, estDuration, dateShort } from "../util.js";
import { pickExercise } from "./picker.js";

const root = () => document.getElementById("view-routines");
let list = [], editing = null, settings = { units: "kg" }, jobs = [];

export async function pickRoutine() {
  const rs = await get("/api/routines");
  return new Promise((resolve) => {
    let chosen = null;
    const { el } = openDialog(`<h3>Elegir rutina</h3>${rs.length ? `<ul class="pick-list">${rs.map((r, i) => `<li><button type="button" class="pick-item" data-i="${i}"><span class="pick-name"><b>${esc(r.name)}</b><small>${r.items.length} ejercicios</small></span>${icon("plus")}</button></li>`).join("")}</ul>` : `<p class="muted">Aún no tienes rutinas. Crea una en la sección Rutinas.</p>`}
      <div class="dialog-actions"><button class="btn" data-close type="button">Cancelar</button></div>`, { onClose: () => resolve(chosen) });
    el.addEventListener("click", (e) => { const b = e.target.closest(".pick-item"); if (b) { chosen = rs[Number(b.dataset.i)]; el.close(); } });
  });
}

function days(r) { return r.weekdays.length ? r.weekdays.map((d) => WEEKDAY_LONG[d].slice(0, 3)).join(" · ") : "Sin días fijos"; }

function card(r) {
  const est = estDuration(r.items);
  const today = r.weekdays.includes(((new Date().getDay() + 6) % 7) + 1);
  const job = jobs.find((j) => j.routine_id === r.id && (j.status === "queued" || j.status === "running"));
  return `<article class="glass card routine ${today ? "today" : ""}" data-id="${r.id}">
    <div class="row-between"><div><h3>${esc(r.name)}</h3><p class="muted small">${esc(days(r))}${today ? ' · <b class="accent">hoy</b>' : ""}</p></div>
      <button class="btn primary" type="button" data-act="start" data-id="${r.id}">${icon("play")}Entrenar</button></div>
    <div class="thumbs">${r.items.slice(0, 6).map((i) => thumb(i)).join("")}${r.items.length > 6 ? `<span class="thumb more">+${r.items.length - 6}</span>` : ""}</div>
    <p class="muted small">${r.items.length} ejercicios · ≈ ${est ? human(est) : "—"}${r.last_done ? ` · último: ${dateShort(r.last_done)}` : ""}</p>
    ${r.notes ? `<p class="small">${esc(r.notes)}</p>` : ""}
    <div class="card-actions"><button class="btn" type="button" data-act="edit" data-id="${r.id}">${icon("pencil")}Editar</button>
      <button class="btn" type="button" data-act="eval" data-id="${r.id}" ${job ? "disabled" : ""}>${icon("sparkle")}${job ? "Evaluando…" : "Evaluar y ajustar con IA"}</button>
      <button class="btn" type="button" data-act="hist" data-id="${r.id}">${icon("history")}Historial</button>
      <button class="icon-btn" type="button" data-act="dup" data-id="${r.id}" aria-label="Duplicar" title="Duplicar">${icon("copy")}</button>
      <button class="icon-btn danger" type="button" data-act="del" data-id="${r.id}" aria-label="Archivar" title="Archivar">${icon("archive")}</button></div></article>`;
}

function renderList() {
  const lastJobs = jobs.filter((j) => j.summary).slice(0, 3);
  root().innerHTML = `<header class="view-head"><div><h1 id="h-routines">Rutinas</h1><p class="muted">Diseña tus rutinas con ejercicios, series, repeticiones, peso y descansos. El asistente puede ajustarlas según tu desempeño.</p></div>
      <div class="head-actions"><button class="btn" type="button" data-act="eval" data-id="">${icon("sparkle")}Evaluar todas</button><button class="btn primary" type="button" data-act="new">${icon("plus")}Nueva rutina</button></div></header>
    ${lastJobs.length ? `<div class="glass card"><h3>Últimas evaluaciones del asistente</h3>${lastJobs.map((j) => `<div class="eval"><b>${esc(j.routine || "Todas las rutinas")}</b> <span class="muted small">${dateShort(j.finished || j.created)}${j.trigger !== "manual" ? " · automática" : ""}</span><p class="small">${esc(j.summary)}</p></div>`).join("")}</div>` : ""}
    <div class="routines">${list.map(card).join("") || `<div class="empty">${icon("checks")}<p>Aún no tienes rutinas.</p><button class="btn primary" type="button" data-act="new">${icon("plus")}Crear la primera</button></div>`}</div>`;
}

function itemRow(it, i, n) {
  const reps = it.tracking === "reps";
  return `<article class="glass card item" data-i="${i}">
    <div class="item-head">${thumb(it)}<div class="grow"><b>${esc(exName(it))}</b><small class="muted">${esc(targetText(it, settings.units))}</small></div>
      <div class="item-btns"><button class="icon-btn sm" type="button" data-it="up" data-i="${i}" ${i === 0 ? "disabled" : ""} aria-label="Subir">${icon("up")}</button>
      <button class="icon-btn sm" type="button" data-it="down" data-i="${i}" ${i === n - 1 ? "disabled" : ""} aria-label="Bajar">${icon("down")}</button>
      <button class="icon-btn sm danger" type="button" data-it="rm" data-i="${i}" aria-label="Quitar">${icon("trash")}</button></div></div>
    <div class="item-grid">
      <label>Series<input class="inp" data-f="sets" inputmode="numeric" value="${it.sets ?? ""}"></label>
      ${reps ? `<label>Reps mín.<input class="inp" data-f="reps_min" inputmode="numeric" value="${it.reps_min ?? ""}"></label><label>Reps máx.<input class="inp" data-f="reps_max" inputmode="numeric" value="${it.reps_max ?? ""}"></label>
        <label>Peso (${esc(settings.units)})<input class="inp" data-f="weight" inputmode="decimal" value="${it.weight ?? ""}"></label>`
        : `<label>Duración (mm:ss)<input class="inp" data-f="duration_s" data-t="1" value="${it.duration_s ? mmss(it.duration_s) : ""}"></label>
        ${it.tracking === "cardio" ? `<label>Distancia (km)<input class="inp" data-f="distance_m" data-km="1" inputmode="decimal" value="${it.distance_m ? it.distance_m / 1000 : ""}"></label>` : ""}`}
      <label>Descanso entre series (s)<input class="inp" data-f="rest_s" inputmode="numeric" value="${it.rest_s ?? ""}"></label>
      <label>Descanso al acabar (s)<input class="inp" data-f="rest_ex_s" inputmode="numeric" value="${it.rest_ex_s ?? ""}"></label>
      <label class="wide2">Notas<input class="inp" data-f="notes" maxlength="300" value="${esc(it.notes || "")}"></label></div></article>`;
}

function renderEditor() {
  const r = editing;
  root().innerHTML = `<header class="view-head"><div><h1 id="h-routines">${r.id ? "Editar rutina" : "Nueva rutina"}</h1></div>
      <div class="head-actions"><button class="btn" type="button" data-act="cancel">Cancelar</button><button class="btn primary" type="button" data-act="save">${icon("check")}Guardar</button></div></header>
    <div class="glass card"><div class="fld"><label for="r-name">Nombre</label><input class="inp" id="r-name" maxlength="100" value="${esc(r.name)}" placeholder="Ej.: Empuje (pecho, hombro, tríceps)"></div>
      <div class="fld"><label>Días de la semana</label><div class="wd">${[1, 2, 3, 4, 5, 6, 7].map((d) => `<button type="button" class="wd-b" data-wd="${d}" aria-pressed="${r.weekdays.includes(d)}" title="${WEEKDAY_LONG[d]}">${WEEKDAY[d]}</button>`).join("")}</div><small>El panel te propondrá esta rutina en esos días.</small></div>
      <div class="fld"><label for="r-notes">Notas</label><textarea class="inp area" id="r-notes" rows="2" maxlength="1500" placeholder="Objetivo, calentamiento, técnica…">${esc(r.notes)}</textarea></div></div>
    <p class="muted small" id="r-est">≈ ${estDuration(r.items) ? human(estDuration(r.items)) : "—"} · ${r.items.length} ejercicios</p>
    <div id="r-items">${r.items.map((it, i) => itemRow(it, i, r.items.length)).join("")}</div>
    <button class="btn block" type="button" data-act="add">${icon("plus")}Añadir ejercicio</button>`;
}

function readEditor() {
  const r = editing;
  r.name = document.getElementById("r-name").value;
  r.notes = document.getElementById("r-notes").value;
  document.querySelectorAll("#r-items .item").forEach((card_) => {
    const it = r.items[Number(card_.dataset.i)];
    card_.querySelectorAll("[data-f]").forEach((inp) => {
      const k = inp.dataset.f;
      if (k === "notes") it[k] = inp.value;
      else if (inp.dataset.t) it[k] = parseMmss(inp.value);
      else if (inp.dataset.km) { const n = parseNum(inp.value); it[k] = n == null ? null : Math.round(n * 1000); }
      else it[k] = parseNum(inp.value);
    });
  });
}

async function refresh() {
  [list, settings] = await Promise.all([get("/api/routines"), get("/api/settings")]);
  jobs = (await get("/api/eval")).jobs;
  editing ? renderEditor() : renderList();
}

async function history(id) {
  const revs = await get(`/api/routines/${id}/revisions`);
  const r = list.find((x) => x.id === id);
  const { el } = openDialog(`<h3>Historial · ${esc(r ? r.name : "")}</h3><p class="muted small">Cada cambio guarda la versión anterior. Puedes volver a cualquiera.</p>
    <ul class="revs">${revs.map((v) => `<li><div><b>${v.source === "agent" ? "Asistente" : v.source === "import" ? "Importación" : "Tú"}</b> <span class="muted small">${new Date(v.created * 1000).toLocaleString("es")}</span><p class="small">${esc(v.reason || "Sin motivo")}${v.items != null ? ` · versión anterior con ${v.items} ejercicios` : ""}</p></div>
      ${v.restorable ? `<button class="btn" type="button" data-rest="${v.id}">${icon("rewind")}Volver a esta</button>` : ""}</li>`).join("")}</ul>
    <div class="dialog-actions"><button class="btn" data-close type="button">Cerrar</button></div>`, { cls: "wide" });
  el.addEventListener("click", async (e) => {
    const b = e.target.closest("[data-rest]");
    if (!b || !(await confirmDialog({ title: "Restaurar versión", body: "La rutina volverá a esa versión (la actual también quedará en el historial).", confirm: "Restaurar" }))) return;
    try { await post(`/api/routines/${id}/restore/${b.dataset.rest}`); el.close(); toast({ text: "Rutina restaurada", kind: "ok", timeout: 2500 }); await refresh(); } catch (x) { toast({ text: x.message, kind: "err" }); }
  });
}

export function init() {
  const r = root();
  r.addEventListener("click", async (e) => {
    const t = e.target.closest("[data-act],[data-it],[data-wd]");
    if (!t) return;
    try {
      if (t.dataset.wd) { const d = Number(t.dataset.wd), a = editing.weekdays; a.includes(d) ? a.splice(a.indexOf(d), 1) : a.push(d); t.setAttribute("aria-pressed", String(a.includes(d))); return; }
      if (t.dataset.it) {
        readEditor(); const i = Number(t.dataset.i), a = editing.items;
        if (t.dataset.it === "up" && i > 0) [a[i - 1], a[i]] = [a[i], a[i - 1]];
        else if (t.dataset.it === "down" && i < a.length - 1) [a[i + 1], a[i]] = [a[i], a[i + 1]];
        else if (t.dataset.it === "rm") a.splice(i, 1);
        renderEditor(); return;
      }
      const id = Number(t.dataset.id);
      switch (t.dataset.act) {
        case "new": editing = { name: "", notes: "", weekdays: [], items: [] }; renderEditor(); break;
        case "edit": editing = JSON.parse(JSON.stringify(list.find((x) => x.id === id))); renderEditor(); break;
        case "cancel": editing = null; renderList(); break;
        case "add": {
          readEditor();
          const e = await pickExercise();
          if (e) { editing.items.push({ exercise_id: e.id, name: e.name, name_es: e.name_es, tracking: e.tracking, category: e.category, thumb: (e.media.find((m) => m.kind === "image") || {}).url, sets: e.tracking === "reps" ? 3 : 1, reps_min: 8, reps_max: 12, weight: 0, duration_s: e.tracking === "cardio" ? 900 : e.tracking === "time" ? 30 : null, distance_m: null, rest_s: 90, rest_ex_s: 120, notes: "" }); }
          renderEditor(); break;
        }
        case "save": {
          readEditor(); setBusy(t, true);
          if (!editing.name.trim()) { toast({ text: "Ponle un nombre a la rutina", kind: "warn" }); setBusy(t, false); break; }
          const body = { name: editing.name, notes: editing.notes, weekdays: editing.weekdays, items: editing.items, reason: "Editada a mano" };
          try { editing.id ? await put(`/api/routines/${editing.id}`, body) : await post("/api/routines", body); editing = null; toast({ text: "Rutina guardada", kind: "ok", timeout: 2500 }); await refresh(); }
          catch (x) { toast({ text: x.message, kind: "err" }); setBusy(t, false); }
          break;
        }
        case "start": location.hash = `#/train?routine=${id}`; break;
        case "dup": await post(`/api/routines/${id}/duplicate`); toast({ text: "Rutina duplicada", kind: "ok", timeout: 2500 }); await refresh(); break;
        case "del": if (await confirmDialog({ title: "Archivar rutina", body: "Dejará de aparecer, pero tus entrenamientos pasados se conservan.", confirm: "Archivar", danger: true })) { await del(`/api/routines/${id}`); await refresh(); } break;
        case "hist": await history(id); break;
        case "eval": {
          await post("/api/eval", { routine_id: id || null });
          toast({ text: "Evaluación enviada al asistente. Puede tardar unos minutos; verás el resumen aquí.", kind: "ok", timeout: 5000 });
          await refresh(); pollEval(); break;
        }
        default: break;
      }
    } catch (x) { toast({ text: x.message, kind: "err" }); }
  });
  r.addEventListener("input", (e) => {
    if (!editing || !e.target.closest("#r-items")) return;
    const el = document.getElementById("r-est"); if (!el) return;
    clearTimeout(init.t); init.t = setTimeout(() => { readEditor(); el.textContent = `≈ ${estDuration(editing.items) ? human(estDuration(editing.items)) : "—"} · ${editing.items.length} ejercicios`; }, 300);
  });
}

let evalTimer = null;
function pollEval() {
  clearTimeout(evalTimer);
  evalTimer = setTimeout(async () => {
    if (editing || root().hidden) return;
    jobs = (await get("/api/eval").catch(() => ({ jobs: [] }))).jobs;
    if (jobs.some((j) => j.status === "queued" || j.status === "running")) { renderList(); pollEval(); } else { await refresh(); }
  }, 5000);
}

export async function show() {
  try { editing = null; await refresh(); if (jobs.some((j) => j.status === "queued" || j.status === "running")) pollEval(); }
  catch (e) { root().innerHTML = `<div class="empty">${icon("warning")}<p>No se pudieron cargar las rutinas.</p></div>`; }
}
