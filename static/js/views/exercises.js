import { get, post, put, patch, del, upload } from "../api.js";
import { esc, icon } from "../fmt.js";
import { toast, openDialog, confirmDialog, setBusy } from "../ui.js";
import { mediaView, thumb } from "../media.js";
import { CAT, MUSCLE, EQUIP, LEVEL, TRACK, lab, exName } from "../labels.js";
import { ytSearch, isoDay, num, mmss } from "../util.js";
import { pickRoutine } from "./routines.js";
import { lineChart } from "../charts.js";

const root = () => document.getElementById("view-exercises");
let meta = null, items = [], total = 0, loading = false, timer = null;
const f = { q: "", category: "", muscle: "", equipment: "", level: "", favorite: false, no_media: false };

const opt = (map, items_, cur, all) => `<option value="">${all}</option>${items_.map((x) => `<option value="${esc(x.id)}" ${cur === x.id ? "selected" : ""}>${esc(lab(map, x.id))} (${x.n})</option>`).join("")}`;

function card(e) {
  return `<article class="glass card ex-card" data-id="${esc(e.id)}" tabindex="0" role="button" aria-label="${esc(exName(e))}">
    ${thumb(e, "lg")}<div class="ex-info"><h3>${esc(exName(e))}</h3>${e.name_es ? `<small class="muted">${esc(e.name)}</small>` : ""}
    <div class="chips"><span class="chip">${esc(lab(CAT, e.category))}</span>${e.primary.slice(0, 2).map((m) => `<span class="chip alt">${esc(lab(MUSCLE, m))}</span>`).join("")}</div></div>
    ${e.favorite ? `<span class="fav">${icon("star-fill")}</span>` : ""}</article>`;
}

function shell() {
  root().innerHTML = `<header class="view-head"><div><h1 id="h-exercises">Ejercicios</h1>
      <p class="muted">${meta ? `${meta.total} ejercicios de fuerza, cardio, estiramientos y más. Cada uno puede tener tus propias imágenes o vídeos.` : ""}</p></div>
      <div class="head-actions"><button class="btn primary" type="button" id="ex-new">${icon("plus")}Nuevo ejercicio</button></div></header>
    <div class="glass card filters">
      <input class="inp" id="ex-q" type="search" placeholder="Buscar ejercicio…" value="${esc(f.q)}" autocomplete="off">
      <div class="filter-row">
        <select class="inp" id="ex-cat" aria-label="Categoría">${opt(CAT, meta.categories, f.category, "Todas las categorías")}</select>
        <select class="inp" id="ex-mus" aria-label="Músculo">${opt(MUSCLE, meta.muscles, f.muscle, "Todos los músculos")}</select>
        <select class="inp" id="ex-eq" aria-label="Material">${opt(EQUIP, meta.equipment, f.equipment, "Todo el material")}</select>
        <select class="inp" id="ex-lv" aria-label="Nivel"><option value="">Todos los niveles</option>${meta.levels.map((l) => `<option value="${l}" ${f.level === l ? "selected" : ""}>${LEVEL[l]}</option>`).join("")}</select>
      </div>
      <div class="filter-row"><label class="check"><input type="checkbox" id="ex-fav" ${f.favorite ? "checked" : ""}>Solo favoritos</label>
        <label class="check"><input type="checkbox" id="ex-nm" ${f.no_media ? "checked" : ""}>Sin imagen ni vídeo (${meta.without_media})</label><span class="muted small" id="ex-count"></span></div></div>
    <div class="ex-grid" id="ex-grid"></div><div class="center" id="ex-more"></div>`;
  fill();
}

function qs(extra = "") {
  const p = new URLSearchParams({ limit: 48, offset: extra ? items.length : 0 });
  Object.entries(f).forEach(([k, v]) => { if (v && v !== true) p.set(k, v); else if (v === true) p.set(k, "1"); });
  return p.toString();
}
async function fill(append = false) {
  if (loading) return;
  loading = true;
  try {
    const r = await get(`/api/exercises?${qs(append ? "more" : "")}`);
    total = r.total; items = append ? items.concat(r.items) : r.items;
    const g = document.getElementById("ex-grid");
    if (!g) return;
    g.innerHTML = items.map(card).join("") || `<div class="empty">${icon("search")}<p>Sin resultados con estos filtros.</p></div>`;
    document.getElementById("ex-count").textContent = `${total} resultados`;
    document.getElementById("ex-more").innerHTML = items.length < total ? `<button class="btn" type="button" id="ex-next">Ver más (${total - items.length})</button>` : "";
  } catch (e) { toast({ text: e.message, kind: "err" }); }
  loading = false;
}

async function detail(id, then) {
  const e = await get(`/api/exercises/${encodeURIComponent(id)}`);
  const prog = await get(`/api/exercises/${encodeURIComponent(id)}/progress`).catch(() => []);
  const vid = e.video_url ? `<a class="btn" href="${esc(e.video_url)}" target="_blank" rel="noopener noreferrer">${icon("video")}Ver vídeo</a>` : "";
  const { el } = openDialog(`<div class="ex-detail">
    <div class="row-between"><div><h3>${esc(exName(e))}</h3>${e.name_es ? `<p class="muted small">${esc(e.name)}</p>` : ""}</div>
      <button class="icon-btn ${e.favorite ? "on" : ""}" type="button" id="d-fav" aria-label="Favorito" aria-pressed="${e.favorite}">${icon(e.favorite ? "star-fill" : "star")}</button></div>
    ${mediaView(e)}
    <div class="chips"><span class="chip">${esc(lab(CAT, e.category))}</span><span class="chip">${esc(lab(LEVEL, e.level))}</span><span class="chip">${esc(lab(EQUIP, e.equipment))}</span><span class="chip">${esc(TRACK[e.tracking])}</span>
      ${e.primary.map((m) => `<span class="chip alt">${esc(lab(MUSCLE, m))}</span>`).join("")}${e.secondary.map((m) => `<span class="chip dim">${esc(lab(MUSCLE, m))}</span>`).join("")}</div>
    ${e.instructions.length ? `<h4>Cómo se hace</h4><ol class="steps">${e.instructions.map((s) => `<li>${esc(s)}</li>`).join("")}</ol>` : ""}
    ${e.notes ? `<h4>Mis notas</h4><p>${esc(e.notes)}</p>` : ""}
    ${prog.length ? `<h4>Mi progreso</h4><div class="chart" id="d-chart"></div>` : ""}
    <div class="dialog-actions wrap">${vid}<a class="btn" href="${esc(ytSearch(e.name))}" target="_blank" rel="noopener noreferrer">${icon("video")}Buscar vídeo</a>
      <button class="btn" type="button" id="d-media">${icon("image")}Imágenes y vídeos</button><button class="btn" type="button" id="d-edit">${icon("pencil")}Editar</button>
      <button class="btn primary" type="button" id="d-add">${icon("plus")}Añadir a una rutina</button><button class="btn" data-close type="button">Cerrar</button></div></div>`, { cls: "wide", onClose: () => then && then() });
  if (prog.length) {
    const pts = prog.map((p) => [Date.parse(p.date) / 1000, e.tracking === "reps" ? (p.e1rm || p.best_weight || p.best_reps) : (p.duration_s || 0)]);
    lineChart(el.querySelector("#d-chart"), { series: [{ label: e.tracking === "reps" ? "1RM estimado / mejor serie" : "Duración (s)", data: pts }], fmt: (v) => (e.tracking === "reps" ? num(v, 1) : mmss(v)), height: 130, emptyText: "Aún sin datos", fmtAxisT: (ts) => isoDay(new Date(ts * 1000).toISOString().slice(0, 10)), fmtTipT: (ts) => isoDay(new Date(ts * 1000).toISOString().slice(0, 10)) });
  }
  el.querySelector("#d-fav").addEventListener("click", async () => { await patch(`/api/exercises/${encodeURIComponent(id)}`, { favorite: !e.favorite }); el.close(); detail(id, then); });
  el.querySelector("#d-edit").addEventListener("click", () => { el.close(); editDialog(e, () => detail(id, then)); });
  el.querySelector("#d-media").addEventListener("click", () => { el.close(); mediaDialog(e, () => detail(id, then)); });
  el.querySelector("#d-add").addEventListener("click", async () => { const r = await pickRoutine(); if (r) { el.close(); await addToRoutine(r, e); } });
}

async function addToRoutine(r, e) {
  const items_ = r.items.map((i) => ({ ...i }));
  const base = { exercise_id: e.id, sets: e.tracking === "reps" ? 3 : 1, reps_min: 8, reps_max: 12, weight: 0, duration_s: e.tracking === "cardio" ? 900 : e.tracking === "time" ? 30 : null, rest_s: 90, rest_ex_s: 120 };
  items_.push(base);
  try { await put(`/api/routines/${r.id}`, { items: items_, reason: `Añadido ${exName(e)}` }); toast({ text: `«${exName(e)}» añadido a «${r.name}»`, kind: "ok", timeout: 3500 }); }
  catch (x) { toast({ text: x.message, kind: "err" }); }
}

function mediaDialog(e, back) {
  const own = (e.media || []).filter((m) => m.own);
  const { el } = openDialog(`<h3>Imágenes y vídeos · ${esc(exName(e))}</h3>
    <p class="muted small">${own.length ? "Se muestran los tuyos en lugar de los de la biblioteca." : e.media.length ? "Ahora se muestran los de la biblioteca. Sube los tuyos para sustituirlos." : "Este ejercicio aún no tiene imagen ni vídeo."} JPG, PNG, WebP, GIF (máx. 8 MB) o MP4/WebM (máx. 30 MB), hasta 8.</p>
    <div class="media-edit">${own.map((m) => `<div class="me">${m.kind === "video" ? `<video src="${esc(m.url)}" controls preload="metadata" playsinline></video>` : `<img src="${esc(m.url)}" alt="">`}<button class="icon-btn sm danger" type="button" data-rm="${esc(m.file)}" aria-label="Quitar">${icon("trash")}</button></div>`).join("") || (e.media.length ? e.media.map((m) => `<div class="me"><img src="${esc(m.url)}" alt=""></div>`).join("") : "")}</div>
    <input type="file" id="m-file" accept="image/jpeg,image/png,image/webp,image/gif,video/mp4,video/webm" multiple hidden>
    <div class="dialog-actions wrap"><button class="btn primary" type="button" id="m-up">${icon("upload")}Subir imágenes o vídeos</button>
      <button class="btn" data-close type="button">Cerrar</button></div><div class="bar" id="m-bar" hidden><i></i></div>`, { cls: "wide", onClose: back });
  const input = el.querySelector("#m-file");
  el.querySelector("#m-up").addEventListener("click", () => input.click());
  input.addEventListener("change", async () => {
    if (!input.files.length) return;
    const form = new FormData();
    [...input.files].forEach((x) => form.append("file", x, x.name));
    const bar = el.querySelector("#m-bar"); bar.hidden = false;
    try { await upload(`/api/exercises/${encodeURIComponent(e.id)}/media`, form, (p) => { bar.firstElementChild.style.width = `${Math.round(p * 100)}%`; }); toast({ text: "Subido", kind: "ok", timeout: 2500 }); const fresh = await get(`/api/exercises/${encodeURIComponent(e.id)}`); el.close(); mediaDialog(fresh, back); }
    catch (x) { toast({ text: x.message, kind: "err" }); bar.hidden = true; }
  });
  el.addEventListener("click", async (ev) => {
    const b = ev.target.closest("[data-rm]");
    if (!b) return;
    try { await del(`/api/exercises/${encodeURIComponent(e.id)}/media/${encodeURIComponent(b.dataset.rm)}`); const fresh = await get(`/api/exercises/${encodeURIComponent(e.id)}`); el.close(); mediaDialog(fresh, back); }
    catch (x) { toast({ text: x.message, kind: "err" }); }
  });
}

function editDialog(e, back) {
  const custom = !e || e.source === "custom";
  const sel = (map, cur) => Object.entries(map).map(([k, v]) => `<option value="${k}" ${cur === k ? "selected" : ""}>${v}</option>`).join("");
  const { el } = openDialog(`<h3>${e ? "Editar" : "Nuevo"} ejercicio</h3>
    ${custom ? `<div class="fld"><label for="e-name">Nombre</label><input class="inp" id="e-name" value="${esc(e ? e.name : "")}" maxlength="120"></div>` : ""}
    <div class="fld"><label for="e-es">Nombre en español</label><input class="inp" id="e-es" value="${esc(e ? e.name_es : "")}" maxlength="120"></div>
    ${custom ? `<div class="two"><div class="fld"><label for="e-track">Se registra como</label><select class="inp" id="e-track">${sel(TRACK, e ? e.tracking : "reps")}</select></div>
      <div class="fld"><label for="e-cat">Categoría</label><select class="inp" id="e-cat">${sel(CAT, e ? e.category : "strength")}</select></div></div>
      <div class="two"><div class="fld"><label for="e-eq">Material</label><select class="inp" id="e-eq">${sel(EQUIP, e ? e.equipment : "none")}</select></div>
      <div class="fld"><label for="e-lv">Nivel</label><select class="inp" id="e-lv">${sel(LEVEL, e ? e.level : "beginner")}</select></div></div>
      <div class="fld"><label for="e-pm">Músculos principales</label><select class="inp" id="e-pm" multiple size="5">${Object.entries(MUSCLE).map(([k, v]) => `<option value="${k}" ${e && e.primary.includes(k) ? "selected" : ""}>${v}</option>`).join("")}</select><small>Ctrl/⌘ para elegir varios</small></div>
      <div class="fld"><label for="e-ins">Instrucciones (una por línea)</label><textarea class="inp area" id="e-ins" rows="4">${esc(e ? e.instructions.join("\n") : "")}</textarea></div>` : ""}
    <div class="fld"><label for="e-vid">Vídeo de referencia (enlace https)</label><input class="inp" id="e-vid" type="url" placeholder="https://…" value="${esc(e ? e.video_url : "")}"></div>
    <div class="fld"><label for="e-notes">Mis notas</label><textarea class="inp area" id="e-notes" rows="2" maxlength="1000">${esc(e ? e.notes : "")}</textarea></div>
    <div class="dialog-actions">${e && custom ? `<button class="btn danger" type="button" id="e-del">${icon("trash")}Borrar</button>` : ""}<span class="spacer"></span><button class="btn" data-close type="button">Cancelar</button><button class="btn primary" id="e-save" type="button">Guardar</button></div>`, { cls: "wide" });
  const v = (id) => el.querySelector(id) && el.querySelector(id).value;
  el.querySelector("#e-save").addEventListener("click", async (ev) => {
    setBusy(ev.currentTarget, true);
    const body = { name_es: v("#e-es"), video_url: v("#e-vid"), notes: v("#e-notes") };
    if (custom) Object.assign(body, { name: v("#e-name"), tracking: v("#e-track"), category: v("#e-cat"), equipment: v("#e-eq"), level: v("#e-lv"), primary: [...el.querySelector("#e-pm").selectedOptions].map((o) => o.value), instructions: v("#e-ins").split("\n") });
    try {
      const saved = e ? await patch(`/api/exercises/${encodeURIComponent(e.id)}`, body) : await post("/api/exercises", body);
      el.close(); toast({ text: "Guardado", kind: "ok", timeout: 2000 });
      if (e) back && back(); else { await load(); detail(saved.id, () => load()); }
    } catch (x) { toast({ text: x.message, kind: "err" }); setBusy(ev.currentTarget, false); }
  });
  const d = el.querySelector("#e-del");
  if (d) d.addEventListener("click", async () => {
    if (!(await confirmDialog({ title: "Borrar ejercicio", body: `Se borrará «${exName(e)}» y sus imágenes.`, confirm: "Borrar", danger: true }))) return;
    try { await del(`/api/exercises/${encodeURIComponent(e.id)}`); el.close(); load(); } catch (x) { toast({ text: x.message, kind: "err" }); }
  });
}

async function load() { meta = await get("/api/meta"); shell(); }

export function init() {
  const r = root();
  r.addEventListener("input", (e) => {
    if (e.target.id === "ex-q") { f.q = e.target.value; clearTimeout(timer); timer = setTimeout(() => fill(), 250); }
  });
  r.addEventListener("change", (e) => {
    const map = { "ex-cat": "category", "ex-mus": "muscle", "ex-eq": "equipment", "ex-lv": "level" };
    if (map[e.target.id]) { f[map[e.target.id]] = e.target.value; fill(); }
    else if (e.target.id === "ex-fav") { f.favorite = e.target.checked; fill(); }
    else if (e.target.id === "ex-nm") { f.no_media = e.target.checked; fill(); }
  });
  r.addEventListener("click", (e) => {
    if (e.target.id === "ex-next") return fill(true);
    if (e.target.closest("#ex-new")) return editDialog(null);
    const c = e.target.closest(".ex-card");
    if (c) detail(c.dataset.id, () => fill());
  });
  r.addEventListener("keydown", (e) => { const c = e.target.closest(".ex-card"); if (c && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); detail(c.dataset.id, () => fill()); } });
}
export async function show() { try { if (!meta) await load(); else { meta = await get("/api/meta"); shell(); } } catch (e) { root().innerHTML = `<div class="empty">${icon("warning")}<p>No se pudieron cargar los ejercicios.</p></div>`; } }
export const openExercise = detail;
