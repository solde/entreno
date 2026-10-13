import { get, post, del } from "../api.js";
import { esc, icon } from "../fmt.js";
import { toast, openDialog, setBusy } from "../ui.js";
import { num } from "../util.js";
import { getPeople, peopleBox, bindPeople } from "../people.js";
import { iso, parse, addDays, today, fmtLong } from "../cal.js";

const root = () => document.getElementById("view-cook");
let day = today(), data = null, pollT = null;

const busy = () => data && data.job && (data.job.status === "queued" || data.job.status === "running");

function ideaCard(i) {
  const n = getPeople(), k = n / (i.servings || 1);
  const ing = i.ingredients.map((x) => `<li>${esc(x.name)}${x.grams ? ` <span class="muted">· ${num(x.grams * k)} g</span>` : x.qty ? ` <span class="muted">· ${esc(x.qty)}</span>` : ""}</li>`).join("");
  const steps = String(i.steps || "").split(/\n+/).map((s) => s.trim()).filter(Boolean).map((s) => `<li>${esc(s.replace(/^\d+[\.\)]\s*/, ""))}</li>`).join("");
  return `<article class="glass card idea" data-idea="${i.id}"><header><h3>${esc(i.name)}</h3><p class="muted small">${i.minutes ? `${i.minutes} min · ` : ""}${num(i.servings)} ${i.servings === 1 ? "ración" : "raciones"}</p></header>
    <div class="chips"><span class="chip">${num(i.per_serving.kcal)} kcal</span><span class="chip alt">${num(i.per_serving.protein, 1)} P</span><span class="chip">${num(i.per_serving.carbs, 1)} C</span><span class="chip">${num(i.per_serving.fat, 1)} G</span><span class="muted small">por ración</span></div>
    <h4>Ingredientes <small class="muted">para ${n} ${n === 1 ? "persona" : "personas"}</small></h4><ul class="plain">${ing}</ul>${steps ? `<h4>Preparación</h4><ol class="steps">${steps}</ol>` : ""}${i.notes ? `<p class="muted small">${esc(i.notes)}</p>` : ""}
    <div class="dialog-actions">${i.saved_recipe_id ? `<span class="chip ok">${icon("check")}Guardada en Recetas</span>` : `<button class="btn primary" type="button" data-act="save" data-id="${i.id}">${icon("book")}Guardar en mis recetas</button>`}<span class="spacer"></span>
      <button class="icon-btn sm danger" type="button" data-act="drop" data-id="${i.id}" aria-label="Descartar">${icon("trash")}</button></div></article>`;
}

function render() {
  const f = data.foods, j = data.job;
  const banner = busy() ? `<div class="banner info" role="status">${icon("magic")}<span>El asistente está pensando recetas${data.agent_online ? "" : " (esperando a que el agente se conecte)"}…</span></div>`
    : j && j.status === "error" ? `<div class="banner err">${icon("fail")}<span>${esc(j.error || "No se pudo generar")}</span></div>` : "";
  root().innerHTML = `<header class="view-head"><div><h1 id="h-cook">Cocinar</h1><p class="muted">Recetas con los alimentos que tienes en el menú del día.</p></div></header>
    <div class="glass card filters"><div class="filter-row ck-nav"><button class="icon-btn" type="button" data-d="-1" aria-label="Día anterior">${icon("chevron-down", "rot90")}</button><input class="inp" id="ck-d" type="date" value="${day}" aria-label="Día"><button class="icon-btn" type="button" data-d="1" aria-label="Día siguiente">${icon("chevron-down", "rot-90")}</button>
      <button class="chip" type="button" data-d="0">Hoy</button><span class="muted small">${esc(fmtLong(parse(day)))}</span>${peopleBox("ck-people")}</div></div>
    <section class="glass card"><h3>Alimentos del día</h3>${f.items.length || f.unspecified.length ? `<div class="chips">${f.items.map((x) => `<span class="chip">${esc(x.name)} · ${num(x.grams)} g</span>`).join("")}${f.unspecified.map((x) => `<span class="chip alt">${esc(x)}</span>`).join("")}</div>`
      : `<p class="muted">Este día no tiene menú. Añade comidas en la sección Menú.</p>`}
      <div class="fld"><label for="ck-i">Indicaciones (opcional)</label><input class="inp" id="ck-i" maxlength="500" placeholder="p. ej. rápido, sin horno, para llevar al trabajo"></div>
      <button class="btn primary" type="button" data-act="ask" ${f.items.length || f.unspecified.length ? "" : "disabled"} ${busy() ? "disabled" : ""}>${icon("magic")}${data.ideas.length ? "Pedir otras ideas" : "Sugerir recetas"}</button></section>
    ${banner}${data.ideas.length ? `<div class="ideas">${data.ideas.map(ideaCard).join("")}</div>` : busy() ? "" : `<div class="empty">${icon("book")}<p>Aún no hay ideas para este día.</p></div>`}`;
}

async function load() {
  clearTimeout(pollT);
  data = await get(`/api/cook?date=${day}`);
  render();
  if (busy() && !root().hidden) pollT = setTimeout(() => load().catch(() => {}), 5000);
}

export function init() {
  const r = root();
  bindPeople(r, () => { if (data) render(); });
  r.addEventListener("change", (e) => { if (e.target.id === "ck-d" && e.target.value) { day = e.target.value; load().catch((x) => toast({ text: x.message, kind: "err" })); } });
  r.addEventListener("click", async (e) => {
    const t = e.target.closest("[data-d],[data-act]");
    if (!t) return;
    try {
      if (t.dataset.d !== undefined) { day = t.dataset.d === "0" ? today() : iso(addDays(parse(day), Number(t.dataset.d))); await load(); }
      else if (t.dataset.act === "ask") { setBusy(t, true); await post("/api/cook", { date: day, instructions: document.getElementById("ck-i").value }); toast({ text: "Enviado al asistente. Las ideas aparecerán aquí en unos minutos.", kind: "ok", timeout: 4000 }); await load(); }
      else if (t.dataset.act === "save") { setBusy(t, true); await post(`/api/cook/ideas/${t.dataset.id}/save`, {}); toast({ text: "Guardada en Alimentos → Recetas", kind: "ok", timeout: 3000 }); await load(); }
      else if (t.dataset.act === "drop") { await del(`/api/cook/ideas/${t.dataset.id}`); await load(); }
    } catch (x) { toast({ text: x.message, kind: "err" }); await load().catch(() => {}); }
  });
}
export async function show() { try { await load(); } catch (e) { root().innerHTML = `<div class="empty">${icon("warning")}<p>No se pudieron cargar las ideas.</p></div>`; } }
export const stop = () => clearTimeout(pollT);
