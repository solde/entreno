import { get, post, patch, del } from "../api.js";
import { esc, icon } from "../fmt.js";
import { toast, openDialog, confirmDialog, setBusy } from "../ui.js";
import { SLOT, SLOTS } from "../labels.js";
import { num } from "../util.js";
import { iso, parse, addDays, mondayOf, fmtLong, fmtShort, fmtWeekday, fmtMonth, rangeFor, step, today } from "../cal.js";
import { pickFood, pickRecipe } from "./foods.js";

const root = () => document.getElementById("view-menu");
const store = (k, v) => { try { if (v === undefined) return localStorage.getItem(k); localStorage.setItem(k, v); } catch (e) { return null; } return null; };
let mode = store("menu-mode") || "day", cursor = new Date(), plan = null, jobs = [], log = [], pollT = null;

const kc = (n) => `${num(n)} kcal`;
const TOT = [["kcal", "Calorías", "kcal"], ["protein", "Proteína", "g"], ["carbs", "Hidratos", "g"], ["fat", "Grasa", "g"]];

function status(total, target) {
  if (!target) return "";
  const r = total / target;
  return r < 0.9 ? "low" : r > 1.1 ? "high" : "ok";
}

function totalsBars(t, targets) {
  return `<div class="macros">${TOT.map(([k, l, u]) => {
    const target = targets[k], v = t[k], pct = target ? Math.min(100, Math.round((v / target) * 100)) : 0;
    return `<div class="macro ${status(v, target)}"><div class="macro-top"><span>${l}</span><b>${num(v, k === "kcal" ? 0 : 1)}${target ? `<small> / ${num(target)} ${u}</small>` : `<small> ${u}</small>`}</b></div><div class="mbar"><i style="width:${target ? pct : 0}%"></i></div></div>`;
  }).join("")}</div>`;
}

function entryRow(e) {
  const mac = `${num(e.protein, 0)}P · ${num(e.carbs, 0)}C · ${num(e.fat, 0)}G`;
  return `<li class="entry ${e.done ? "done" : ""}" data-id="${e.id}"><button class="chk" type="button" data-e="done" data-id="${e.id}" aria-pressed="${e.done}" aria-label="Marcar como hecho">${icon(e.done ? "check" : "plus-circle")}</button>
    <button class="e-main" type="button" data-e="edit" data-id="${e.id}"><b>${esc(e.name)}</b><small>${esc(e.qty)}${e.notes ? " · " + esc(e.notes) : ""}</small></button>
    <span class="e-mac"><span><b>${num(e.kcal, 0)}</b> kcal</span><small>${mac}</small></span>${e.source === "agent" ? `<span class="badge info" title="Añadido por el asistente">${icon("sparkle")}</span>` : ""}
    <button class="icon-btn sm danger" type="button" data-e="del" data-id="${e.id}" aria-label="Quitar">${icon("trash")}</button></li>`;
}

function dayView() {
  const k = iso(cursor), d = plan.days[k];
  const slots = SLOTS.filter((s) => s !== "other" || d.entries.some((e) => e.slot === "other"));
  return `${totalsBars(d.totals, plan.targets)}${d.done.kcal ? `<p class="muted small">Marcado como hecho: ${kc(d.done.kcal)}</p>` : ""}
    <div class="slots">${slots.map((s) => {
      const es = d.entries.filter((e) => e.slot === s), sub = es.reduce((a, e) => a + e.kcal, 0);
      return `<section class="glass card slot"><div class="row-between"><h3>${SLOT[s]}${es.length ? ` <small class="muted">${kc(sub)}</small>` : ""}</h3><button class="btn sm" type="button" data-add="${s}" data-date="${k}">${icon("plus")}Añadir</button></div>
        ${es.length ? `<ul class="entries">${es.map(entryRow).join("")}</ul>` : `<p class="muted small">Nada planificado.</p>`}</section>`;
    }).join("")}</div>`;
}

function weekView() {
  const days = Object.keys(plan.days);
  const head = days.map((k) => { const d = parse(k), t = plan.days[k].totals; return `<button type="button" class="wk-h ${k === today() ? "today" : ""} ${status(t.kcal, plan.targets.kcal)}" data-day="${k}"><span>${fmtWeekday(d)}</span><b>${d.getDate()}</b><small>${t.kcal ? num(t.kcal) + " kcal" : "—"}</small></button>`; }).join("");
  const rows = SLOTS.filter((s) => s !== "other" || days.some((k) => plan.days[k].entries.some((e) => e.slot === "other"))).map((s) => `<div class="wk-slot">${SLOT[s]}</div>${days.map((k) => {
    const es = plan.days[k].entries.filter((e) => e.slot === s);
    return `<div class="wk-cell" data-add="${s}" data-date="${k}" tabindex="0" role="button" aria-label="Añadir en ${SLOT[s]} ${k}">${es.map((e) => `<span class="wk-e ${e.done ? "done" : ""} ${e.source === "agent" ? "ai" : ""}" data-e="edit" data-id="${e.id}" title="${esc(e.name)} · ${esc(e.qty)} · ${num(e.kcal, 0)} kcal">${esc(e.name)}</span>`).join("")}</div>`;
  }).join("")}`).join("");
  const foot = days.map((k) => { const t = plan.days[k].totals; return `<div class="wk-t ${status(t.kcal, plan.targets.kcal)}">${t.kcal ? `<b>${num(t.kcal)}</b> kcal<small>${num(t.protein, 0)}P ${num(t.carbs, 0)}C ${num(t.fat, 0)}G</small>` : ""}</div>`; }).join("");
  return `<div class="wk-scroll"><div class="wk"><div class="wk-corner"></div>${head}${rows}<div class="wk-slot tot">Total</div>${foot}</div></div>
    <p class="muted small">Pulsa una celda para añadir, una comida para editarla o un día para abrirlo. ${plan.summary.planned_days ? `Media de ${plan.summary.planned_days} ${plan.summary.planned_days === 1 ? "día planificado" : "días planificados"}: ${kc(plan.summary.avg.kcal)} · ${num(plan.summary.avg.protein, 0)} g de proteína.` : ""}</p>`;
}

function monthView() {
  const days = Object.keys(plan.days), curMonth = cursor.getMonth();
  const head = ["L", "M", "X", "J", "V", "S", "D"].map((x) => `<div class="mo-h">${x}</div>`).join("");
  const cells = days.map((k) => {
    const d = parse(k), p = plan.days[k], t = p.totals;
    const dots = SLOTS.map((s) => `<i class="${p.entries.some((e) => e.slot === s) ? "on" : ""}"></i>`).join("");
    return `<button type="button" class="mo-c ${d.getMonth() !== curMonth ? "out" : ""} ${k === today() ? "today" : ""} ${status(t.kcal, plan.targets.kcal)}" data-day="${k}"><span class="mo-n">${d.getDate()}</span>${t.kcal ? `<b>${num(t.kcal)}</b><small>kcal</small>` : ""}<span class="mo-dots">${dots}</span></button>`;
  }).join("");
  const inMonth = days.filter((k) => parse(k).getMonth() === curMonth && plan.days[k].entries.length);
  const avg = (key) => (inMonth.length ? inMonth.reduce((a, k) => a + plan.days[k].totals[key], 0) / inMonth.length : 0);
  return `<div class="mo">${head}${cells}</div><p class="muted small">${inMonth.length} ${inMonth.length === 1 ? "día" : "días"} con menú este mes${inMonth.length ? ` · media ${kc(avg("kcal"))}, ${num(avg("protein"), 0)} g de proteína` : ""}. Los puntos indican las comidas planificadas de cada día.</p>`;
}

function title() {
  if (mode === "day") return fmtLong(cursor).replace(/^./, (c) => c.toUpperCase());
  if (mode === "week") { const m = mondayOf(cursor); return `Semana del ${fmtShort(m)} al ${fmtShort(addDays(m, 6))}`; }
  return fmtMonth(cursor).replace(/^./, (c) => c.toUpperCase());
}

function agentBanner() {
  const run = jobs.find((j) => j.status === "queued" || j.status === "running");
  const last = jobs.find((j) => j.status === "done" || j.status === "error");
  return run ? `<div class="banner info">${icon("sparkle")}<span>El asistente está planificando el menú del ${esc(run.date_from)} al ${esc(run.date_to)}… puede tardar un par de minutos.</span></div>`
    : last && last.finished && Date.now() / 1000 - last.finished < 3600 && sessionStorage.getItem("nplan-seen") !== String(last.id) ? `<div class="banner ${last.status === "done" ? "ok" : "err"}" id="nplan-note">${icon(last.status === "done" ? "check" : "fail")}<span>${esc(last.status === "done" ? last.summary : last.error || "No se pudo planificar")}</span><button class="icon-btn sm" type="button" data-act="dismiss" data-id="${last.id}" aria-label="Cerrar">${icon("x")}</button></div>` : "";
}

function render() {
  const [a, b] = rangeFor(mode, cursor);
  root().innerHTML = `<header class="view-head"><div><h1 id="h-menu">${esc(title())}</h1><p class="muted">Tu menú, en calendario. El asistente puede planificarlo por ti.</p></div>
      <div class="head-actions"><div class="seg" role="group" aria-label="Vista">${[["day", "Día"], ["week", "Semana"], ["month", "Mes"]].map(([m, l]) => `<button type="button" data-mode="${m}" aria-pressed="${mode === m}">${l}</button>`).join("")}</div></div></header>
    <div class="cal-bar"><div class="cal-nav"><button class="icon-btn" type="button" data-nav="-1" aria-label="Anterior">${icon("chevron-down", "rot90")}</button><button class="btn sm" type="button" data-nav="0">Hoy</button><button class="icon-btn" type="button" data-nav="1" aria-label="Siguiente">${icon("chevron-down", "rot-90")}</button></div>
      <div class="cal-acts"><button class="btn sm" type="button" data-act="ai">${icon("sparkle")}Planificar con IA</button><button class="btn sm" type="button" data-act="shop">${icon("cart")}Compra</button>
        ${mode !== "month" ? `<button class="btn sm" type="button" data-act="copy">${icon("copy")}Copiar</button><button class="btn sm danger" type="button" data-act="clear">${icon("trash")}Vaciar</button>` : ""}</div></div>
    ${agentBanner()}${mode === "day" ? dayView() : mode === "week" ? weekView() : monthView()}
    ${log.length ? `<details class="glass card hist"><summary>${icon("history")}Cambios recientes del menú (${log.length})</summary><ul class="plain">${log.slice(0, 8).map((l) => `<li><span><b>${l.source === "agent" ? "Asistente" : "Tú"}</b> <small class="muted">${new Date(l.created * 1000).toLocaleString("es")} · ${esc(l.date_from)}${l.date_to !== l.date_from ? " → " + esc(l.date_to) : ""}</small><br><span class="small">${esc(l.reason)}</span></span><button class="btn sm" type="button" data-act="restore" data-id="${l.id}">${icon("rewind")}Deshacer</button></li>`).join("")}</ul></details>` : ""}`;
  return [a, b];
}

async function load() {
  const [a, b] = rangeFor(mode, cursor);
  [plan, jobs, log] = await Promise.all([get(`/api/plan?from=${a}&to=${b}`), get("/api/nutrition/plan").then((r) => r.jobs).catch(() => []), get("/api/plan/log?limit=10").catch(() => [])]);
  render();
  clearTimeout(pollT);
  if (jobs.some((j) => j.status === "queued" || j.status === "running") && !root().hidden) pollT = setTimeout(() => load().catch(() => {}), 6000);
}

/* ------------------------------------------------------------------ diálogos */

async function entryDialog({ id = null, date, slot }) {
  let e = null;
  if (id) e = Object.values(plan.days).flatMap((d) => d.entries).find((x) => x.id === id);
  const st = { kind: e ? e.kind : "food", food: null, recipe: null, date: e ? e.date : date, slot: e ? e.slot : slot };
  if (e && e.kind === "food") st.food = await get(`/api/foods/${encodeURIComponent(e.food_id)}`);
  if (e && e.kind === "recipe") st.recipe = (await get("/api/recipes")).find((r) => r.id === e.recipe_id) || null;
  const { el } = openDialog(`<h3>${e ? "Editar" : "Añadir"} · ${SLOT[st.slot]}</h3>
    ${e ? "" : `<div class="seg wrap" id="en-kind" role="group"><button type="button" data-k="food" aria-pressed="${st.kind === "food"}">Alimento</button><button type="button" data-k="recipe" aria-pressed="${st.kind === "recipe"}">Receta</button><button type="button" data-k="text" aria-pressed="${st.kind === "text"}">Libre</button></div>`}
    <div id="en-body"></div>
    <div class="two"><div class="fld"><label for="en-date">Día</label><input class="inp" id="en-date" type="date" value="${st.date}"></div><div class="fld"><label for="en-slot">Momento</label><select class="inp" id="en-slot">${SLOTS.map((s) => `<option value="${s}" ${s === st.slot ? "selected" : ""}>${SLOT[s]}</option>`).join("")}</select></div></div>
    <div class="fld"><label for="en-notes">Notas</label><input class="inp" id="en-notes" maxlength="300" value="${esc(e ? e.notes : "")}"></div>
    <div class="dialog-actions">${e ? `<button class="btn danger" type="button" id="en-del">${icon("trash")}Quitar</button>` : ""}<span class="spacer"></span><button class="btn" data-close type="button">Cancelar</button><button class="btn primary" id="en-ok" type="button">Guardar</button></div>`, { cls: "wide" });
  const body = el.querySelector("#en-body");
  const preview = () => {
    const m = macrosNow();
    const p = el.querySelector("#en-prev");
    if (p) p.textContent = m ? `${num(m.kcal, 0)} kcal · ${num(m.protein, 1)} P · ${num(m.carbs, 1)} C · ${num(m.fat, 1)} G` : "";
  };
  const macrosNow = () => {
    if (st.kind === "food" && st.food) { const g = Number(el.querySelector("#en-g")?.value) || 0; return Object.fromEntries(["kcal", "protein", "carbs", "fat"].map((k) => [k, (st.food[k] * g) / 100])); }
    if (st.kind === "recipe" && st.recipe) { const s = Number(el.querySelector("#en-s")?.value) || 0; return Object.fromEntries(["kcal", "protein", "carbs", "fat"].map((k) => [k, st.recipe.per_serving[k] * s])); }
    if (st.kind === "text") return Object.fromEntries(["kcal", "protein", "carbs", "fat"].map((k) => [k, Number(el.querySelector(`#en-${k}`)?.value) || 0]));
    return null;
  };
  const drawBody = () => {
    if (st.kind === "food") {
      const f = st.food, g = e && e.kind === "food" ? e.grams : f ? f.serving_g : 100;
      body.innerHTML = `<div class="fld"><label>Alimento</label><button class="btn block" type="button" id="en-pick">${f ? esc(f.name) : "Elegir alimento…"}</button></div>
        ${f ? `<div class="fld"><label for="en-g">Cantidad (g)</label><input class="inp" id="en-g" inputmode="decimal" value="${g}"><div class="chips"><button class="chip" type="button" data-g="${f.serving_g}">1 porción (${num(f.serving_g)} g)</button><button class="chip" type="button" data-g="100">100 g</button><button class="chip" type="button" data-g="50">50 g</button></div></div>` : ""}<p class="muted small" id="en-prev"></p>`;
    } else if (st.kind === "recipe") {
      const r = st.recipe, s = e && e.kind === "recipe" ? e.servings : 1;
      body.innerHTML = `<div class="fld"><label>Receta</label><button class="btn block" type="button" id="en-pick">${r ? esc(r.name) : "Elegir receta…"}</button></div>
        ${r ? `<div class="fld"><label for="en-s">Raciones</label><input class="inp" id="en-s" inputmode="decimal" value="${s}"></div>` : ""}<p class="muted small" id="en-prev"></p>`;
    } else {
      body.innerHTML = `<div class="fld"><label for="en-label">Qué comes</label><input class="inp" id="en-label" maxlength="120" value="${esc(e && e.kind === "text" ? e.name : "")}" placeholder="Ej.: Menú del día del bar"></div>
        <div class="two">${[["kcal", "kcal"], ["protein", "Proteína (g)"], ["carbs", "Hidratos (g)"], ["fat", "Grasa (g)"]].map(([k, l]) => `<div class="fld"><label for="en-${k}">${l}</label><input class="inp" id="en-${k}" inputmode="decimal" value="${e && e.kind === "text" ? e[k] : ""}"></div>`).join("")}</div><p class="muted small" id="en-prev"></p>`;
    }
    preview();
  };
  drawBody();
  el.addEventListener("input", preview);
  el.addEventListener("click", async (ev) => {
    const k = ev.target.closest("[data-k]"), g = ev.target.closest("[data-g]");
    if (k) { st.kind = k.dataset.k; el.querySelectorAll("#en-kind button").forEach((b) => b.setAttribute("aria-pressed", String(b === k))); drawBody(); }
    else if (g) { el.querySelector("#en-g").value = g.dataset.g; preview(); }
    else if (ev.target.closest("#en-pick")) {
      const picked = st.kind === "food" ? await pickFood() : await pickRecipe();
      if (picked) { st[st.kind === "food" ? "food" : "recipe"] = picked; drawBody(); }
    }
  });
  const val = (id) => el.querySelector(id).value;
  el.querySelector("#en-ok").addEventListener("click", async (ev) => {
    const body_ = { date: val("#en-date"), slot: val("#en-slot"), kind: st.kind, notes: val("#en-notes") };
    if (st.kind === "food") { if (!st.food) return toast({ text: "Elige un alimento", kind: "warn", timeout: 2500 }); Object.assign(body_, { food_id: st.food.id, grams: Number(val("#en-g").replace(",", ".")) }); }
    else if (st.kind === "recipe") { if (!st.recipe) return toast({ text: "Elige una receta", kind: "warn", timeout: 2500 }); Object.assign(body_, { recipe_id: st.recipe.id, servings: Number(val("#en-s").replace(",", ".")) }); }
    else Object.assign(body_, { label: val("#en-label"), kcal: val("#en-kcal"), protein: val("#en-protein"), carbs: val("#en-carbs"), fat: val("#en-fat") });
    setBusy(ev.currentTarget, true);
    try { e ? await patch(`/api/plan/entries/${e.id}`, body_) : await post("/api/plan/entries", body_); el.close(); await load(); }
    catch (x) { toast({ text: x.message, kind: "err" }); setBusy(ev.currentTarget, false); }
  });
  const d = el.querySelector("#en-del");
  if (d) d.addEventListener("click", async () => { try { await del(`/api/plan/entries/${e.id}`); el.close(); await load(); } catch (x) { toast({ text: x.message, kind: "err" }); } });
}

function aiDialog() {
  const [a, b] = mode === "month" ? [iso(addDays(new Date(), 0)), iso(addDays(new Date(), 6))] : rangeFor(mode, cursor);
  const { el } = openDialog(`<h3>${icon("sparkle")} Planificar con IA</h3><p class="muted small">El asistente creará el menú de los días vacíos del rango según tu perfil (objetivos, dieta, alergias, gustos y entrenos). Los días que ya tengan menú tuyo se respetan, salvo que se lo pidas. Podrás deshacerlo.</p>
    <div class="two"><div class="fld"><label for="ai-a">Desde</label><input class="inp" id="ai-a" type="date" value="${a}"></div><div class="fld"><label for="ai-b">Hasta</label><input class="inp" id="ai-b" type="date" value="${b}"></div></div>
    <div class="fld"><label for="ai-i">Indicaciones (opcional)</label><textarea class="inp area" id="ai-i" rows="3" maxlength="1500" placeholder="Ej.: comidas rápidas entre semana, pescado 2 veces, cena ligera, sin gluten, reutiliza la comida del lunes para la cena…"></textarea></div>
    <div class="dialog-actions"><button class="btn" data-close type="button">Cancelar</button><button class="btn primary" id="ai-ok" type="button">${icon("sparkle")}Planificar</button></div>`, { cls: "wide" });
  el.querySelector("#ai-ok").addEventListener("click", async (ev) => {
    setBusy(ev.currentTarget, true);
    try { await post("/api/nutrition/plan", { from: el.querySelector("#ai-a").value, to: el.querySelector("#ai-b").value, instructions: el.querySelector("#ai-i").value }); el.close(); toast({ text: "Enviado al asistente. Verás el menú aparecer aquí en unos minutos.", kind: "ok", timeout: 5000 }); await load(); }
    catch (x) { toast({ text: x.message, kind: "err" }); setBusy(ev.currentTarget, false); }
  });
}

function copyDialog() {
  const [a, b] = rangeFor(mode, cursor);
  const unit = mode === "day" ? "este día" : "esta semana";
  const next = iso(mode === "day" ? addDays(cursor, 1) : addDays(mondayOf(cursor), 7));
  const { el } = openDialog(`<h3>Copiar ${unit}</h3><p class="muted small">Copia el menú (sin marcar como hecho) a partir de la fecha elegida. Sustituye lo que haya en esos días; se puede deshacer.</p>
    <div class="fld"><label for="cp-t">Copiar a partir del</label><input class="inp" id="cp-t" type="date" value="${next}"></div>
    <div class="dialog-actions"><button class="btn" data-close type="button">Cancelar</button><button class="btn primary" id="cp-ok" type="button">Copiar</button></div>`);
  el.querySelector("#cp-ok").addEventListener("click", async () => {
    try { const r = await post("/api/plan/copy", { from: a, to: b, target: el.querySelector("#cp-t").value }); el.close(); toast({ text: `${r.copied} entradas copiadas`, kind: "ok", timeout: 3000 }); await load(); }
    catch (x) { toast({ text: x.message, kind: "err" }); }
  });
}

export function init() {
  const r = root();
  r.addEventListener("click", async (e) => {
    const t = e.target.closest("[data-mode],[data-nav],[data-day],[data-add],[data-e],[data-act]");
    if (!t) return;
    try {
      if (t.dataset.mode) { mode = t.dataset.mode; store("menu-mode", mode); await load(); }
      else if (t.dataset.nav !== undefined) { cursor = t.dataset.nav === "0" ? new Date() : step(mode, cursor, Number(t.dataset.nav)); await load(); }
      else if (t.dataset.day) { cursor = parse(t.dataset.day); mode = "day"; store("menu-mode", mode); await load(); }
      else if (t.dataset.e === "edit") { e.stopPropagation(); await entryDialog({ id: Number(t.dataset.id) }); }
      else if (t.dataset.e === "done") { const en = Object.values(plan.days).flatMap((d) => d.entries).find((x) => x.id === Number(t.dataset.id)); await patch(`/api/plan/entries/${en.id}`, { done: !en.done }); await load(); }
      else if (t.dataset.e === "del") { await del(`/api/plan/entries/${t.dataset.id}`); await load(); }
      else if (t.dataset.add) await entryDialog({ date: t.dataset.date, slot: t.dataset.add });
      else if (t.dataset.act === "ai") aiDialog();
      else if (t.dataset.act === "copy") copyDialog();
      else if (t.dataset.act === "shop") { const [a, b] = mode === "month" ? [iso(mondayOf(cursor)), iso(addDays(mondayOf(cursor), 6))] : rangeFor(mode, cursor); sessionStorage.setItem("shop-range", JSON.stringify([a, b])); location.hash = "#/shopping"; }
      else if (t.dataset.act === "clear") {
        const [a, b] = rangeFor(mode, cursor);
        if (await confirmDialog({ title: "Vaciar el menú", body: `Se quitará todo el menú de ${mode === "day" ? "este día" : "esta semana"}. Podrás deshacerlo desde «Cambios recientes».`, confirm: "Vaciar", danger: true })) { await post("/api/plan/clear", { from: a, to: b }); await load(); }
      } else if (t.dataset.act === "restore") {
        if (await confirmDialog({ title: "Deshacer cambio", body: "El menú de esos días volverá al estado anterior a ese cambio.", confirm: "Deshacer" })) { await post(`/api/plan/log/${t.dataset.id}/restore`); toast({ text: "Menú restaurado", kind: "ok", timeout: 2500 }); await load(); }
      } else if (t.dataset.act === "dismiss") { sessionStorage.setItem("nplan-seen", t.dataset.id); render(); }
    } catch (x) { toast({ text: x.message, kind: "err" }); }
  });
  r.addEventListener("keydown", (e) => { const c = e.target.closest(".wk-cell"); if (c && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); entryDialog({ date: c.dataset.date, slot: c.dataset.add }); } });
}
export async function show() {
  try { const q = new URLSearchParams(location.hash.split("?")[1] || ""); if (q.get("date")) { cursor = parse(q.get("date")); mode = "day"; history.replaceState(null, "", "#/menu"); } await load(); }
  catch (e) { root().innerHTML = `<div class="empty">${icon("warning")}<p>No se pudo cargar el menú.</p></div>`; }
}
export const stop = () => clearTimeout(pollT);
