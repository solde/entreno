import { get, post, put, patch, del } from "../api.js";
import { esc, icon } from "../fmt.js";
import { toast, openDialog, confirmDialog, setBusy } from "../ui.js";
import { num, parseNum } from "../util.js";
import { getPeople, peopleBox, bindPeople } from "../people.js";

const root = () => document.getElementById("view-foods");
let tab = "foods", foods = { items: [], total: 0, categories: [] }, recipes = [], f = { q: "", category: "", favorite: false, season: false, origin: "" }, rf = { season: false, origin: "" }, timer = null, season = null;
const MN = ["", "ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];
const ORIGIN = { cat: "Cataluña", es: "España" };

/** [11,12,1,2,3] -> «nov–mar»; [] -> «todo el año» (admite el salto de año). */
export function monthsText(ms) {
  if (!ms || !ms.length || ms.length >= 12) return "todo el año";
  const on = new Set(ms), out = [];
  for (let m = 1; m <= 12; m++) {
    if (!on.has(m) || on.has(m === 1 ? 12 : m - 1)) continue;
    let e = m; while (on.has(e === 12 ? 1 : e + 1) && e !== m + 11) e = e === 12 ? 1 : e + 1;
    out.push(e === m ? MN[m] : `${MN[m]}–${MN[e]}`);
  }
  return out.join(", ");
}
const tags = (x) => `${x.peak ? `<span class="chip ok">De temporada</span>` : ""}${x.origin ? `<span class="chip alt">${ORIGIN[x.origin] || "Local"}</span>` : ""}`;

function seasonBanner() {
  if (!season) return "";
  const pick = ["Verduras", "Frutas"].flatMap((c) => (season.foods && season.foods[c]) || []).slice(0, 16);
  return `<section class="glass card season"><h3>${icon("calendar")}${esc(season.label)} · ${esc(season.month_name)}</h3><p class="muted small">${esc(season.tips)}</p>
    ${pick.length ? `<div class="chips">${pick.map((n) => `<span class="chip ok">${esc(n)}</span>`).join("")}</div>` : ""}</section>`;
}
const flt = (on, key, label) => `<button class="chip${on ? " alt" : ""}" type="button" data-flt="${key}" aria-pressed="${on}">${label}</button>`;

/* ------------------------------------------------------------------ selectores (los usa el menú) */

export function pickFood() {
  return new Promise((resolve) => {
    let chosen = null, items = [], total = 0, q = "", cat = "", t = null;
    const { el } = openDialog(`<h3>Elegir alimento</h3><input class="inp" id="pf-q" type="search" placeholder="Buscar alimento…" autocomplete="off"><select class="inp" id="pf-c" aria-label="Categoría"><option value="">Todas las categorías</option></select>
      <ul class="pick-list" id="pf-list"></ul><p id="pf-more"></p><div class="dialog-actions"><button class="btn" data-close type="button">Cancelar</button></div>`, { cls: "wide", id: "dialog2", onClose: () => resolve(chosen) });
    const list = el.querySelector("#pf-list");
    const draw = () => {
      list.innerHTML = items.map((x, i) => `<li><button type="button" class="pick-item" data-i="${i}"><span class="pick-name"><b>${esc(x.name)}</b><small>${num(x.kcal)} kcal · ${num(x.protein, 1)} P · ${num(x.carbs, 1)} C · ${num(x.fat, 1)} G <span class="muted">/ 100 g</span></small></span>${x.favorite ? icon("star-fill") : icon("plus")}</button></li>`).join("") || `<li class="muted small pad">Sin resultados.</li>`;
      el.querySelector("#pf-more").innerHTML = items.length < total ? `<button class="btn" type="button" id="pf-next">Ver más (${total - items.length})</button>` : "";
    };
    const load = async (more) => {
      const r = await get(`/api/foods?limit=40&offset=${more ? items.length : 0}&q=${encodeURIComponent(q)}&category=${encodeURIComponent(cat)}`);
      total = r.total; items = more ? items.concat(r.items) : r.items;
      const sel = el.querySelector("#pf-c");
      if (sel.options.length === 1) sel.insertAdjacentHTML("beforeend", r.categories.map((c) => `<option>${esc(c)}</option>`).join(""));
      draw();
    };
    el.querySelector("#pf-q").addEventListener("input", (e) => { q = e.target.value; clearTimeout(t); t = setTimeout(() => load(false), 200); });
    el.querySelector("#pf-c").addEventListener("change", (e) => { cat = e.target.value; load(false); });
    el.addEventListener("click", (e) => { const b = e.target.closest(".pick-item"); if (b) { chosen = items[Number(b.dataset.i)]; el.close(); } else if (e.target.id === "pf-next") load(true); });
    load(false).then(() => el.querySelector("#pf-q").focus());
  });
}

export async function pickRecipe() {
  const rs = (await get("/api/recipes")).sort((a, b) => Number(b.peak) - Number(a.peak));
  return new Promise((resolve) => {
    let chosen = null;
    const { el } = openDialog(`<h3>Elegir receta</h3>${rs.length ? `<ul class="pick-list">${rs.map((r, i) => `<li><button type="button" class="pick-item" data-i="${i}"><span class="pick-name"><b>${esc(r.name)}</b><small>${num(r.per_serving.kcal)} kcal por ración · ${num(r.per_serving.protein, 1)} P${r.peak ? " · de temporada" : ""}</small></span>${icon("plus")}</button></li>`).join("")}</ul>` : `<p class="muted">Aún no tienes recetas. Créalas en Alimentos → Recetas.</p>`}
      <div class="dialog-actions"><button class="btn" data-close type="button">Cancelar</button></div>`, { id: "dialog2", onClose: () => resolve(chosen) });
    el.addEventListener("click", (e) => { const b = e.target.closest(".pick-item"); if (b) { chosen = rs[Number(b.dataset.i)]; el.close(); } });
  });
}

/* ------------------------------------------------------------------ vista Alimentos / Recetas */

function foodRow(x) {
  return `<article class="glass card food" data-food="${esc(x.id)}" tabindex="0" role="button"><div class="food-main"><b>${esc(x.name)}</b><small class="muted">${esc(x.category)}${x.source === "custom" ? " · tuyo" : ""}${x.months && x.months.length ? " · " + monthsText(x.months) : ""}</small>${tags(x) ? `<div class="chips tight">${tags(x)}</div>` : ""}</div>
    <div class="food-mac"><b>${num(x.kcal)}</b><small>kcal</small></div><div class="food-mac"><b>${num(x.protein, 1)}</b><small>P</small></div><div class="food-mac"><b>${num(x.carbs, 1)}</b><small>C</small></div><div class="food-mac"><b>${num(x.fat, 1)}</b><small>G</small></div>${x.favorite ? `<span class="fav">${icon("star-fill")}</span>` : ""}</article>`;
}

function render() {
  const head = `<header class="view-head"><div><h1 id="h-foods">Alimentos y recetas</h1><p class="muted">Valores orientativos por 100 g. Añade tus propios alimentos y recetas para usarlos en el menú.</p></div>
    <div class="head-actions">${tab === "foods" ? `<button class="btn primary" type="button" data-act="new-food">${icon("plus")}Nuevo alimento</button>` : `<button class="btn primary" type="button" data-act="new-recipe">${icon("plus")}Nueva receta</button>`}</div></header>
    <div class="seg" role="group" aria-label="Sección"><button type="button" data-tab="foods" aria-pressed="${tab === "foods"}">Alimentos</button><button type="button" data-tab="recipes" aria-pressed="${tab === "recipes"}">Recetas</button></div>`;
  if (tab === "foods") {
    root().innerHTML = `${head}${seasonBanner()}<div class="glass card filters"><input class="inp" id="fd-q" type="search" placeholder="Buscar alimento…" value="${esc(f.q)}" autocomplete="off">
      <div class="filter-row"><select class="inp" id="fd-c" aria-label="Categoría"><option value="">Todas las categorías</option>${foods.categories.map((c) => `<option ${f.category === c ? "selected" : ""}>${esc(c)}</option>`).join("")}</select>
      <label class="check"><input type="checkbox" id="fd-f" ${f.favorite ? "checked" : ""}>Solo favoritos</label><span class="muted small">${foods.total} alimentos</span></div>
      <div class="chips">${flt(f.season, "season", "De temporada ahora")}${flt(f.origin === "cat", "cat", "Cataluña")}${flt(f.origin === "es", "es", "España")}</div></div>
      <div class="foods" id="fd-list">${foods.items.map(foodRow).join("") || `<div class="empty">${icon("search")}<p>Sin resultados.</p></div>`}</div>${foods.items.length < foods.total ? `<div class="center"><button class="btn" type="button" data-act="more">Ver más (${foods.total - foods.items.length})</button></div>` : ""}`;
  } else {
    root().innerHTML = `${head}${seasonBanner()}<div class="glass card filters"><div class="chips">${flt(rf.season, "rseason", "De temporada ahora")}${flt(rf.origin === "cat", "rcat", "Cataluña")}${flt(rf.origin === "es", "res", "España")}<span class="muted small">${recipes.length} recetas</span></div></div>
      <div class="routines">${recipes.map((r) => `<article class="glass card routine" data-recipe="${r.id}" tabindex="0" role="button"><h3>${esc(r.name)}</h3><p class="muted small">${num(r.servings)} raciones · ${r.n_items} ingredientes${r.minutes ? ` · ${r.minutes} min` : ""}${r.kind ? ` · ${esc(r.kind)}` : ""}</p>${r.months && r.months.length || r.origin ? `<div class="chips tight">${tags(r)}${r.months && r.months.length ? `<span class="chip">${monthsText(r.months)}</span>` : ""}</div>` : ""}
      <div class="chips"><span class="chip">${num(r.per_serving.kcal)} kcal</span><span class="chip alt">${num(r.per_serving.protein, 1)} P</span><span class="chip">${num(r.per_serving.carbs, 1)} C</span><span class="chip">${num(r.per_serving.fat, 1)} G</span></div><p class="muted small">por ración</p></article>`).join("") || `<div class="empty">${icon("book")}<p>Sin recetas con estos filtros.</p></div>`}</div>`;
  }
}

const loadRecipes = async () => { recipes = await get(`/api/recipes?${rf.season ? "season=1&" : ""}${rf.origin ? "origin=" + rf.origin : ""}`); };
async function loadFoods(more) {
  const r = await get(`/api/foods?limit=60&offset=${more ? foods.items.length : 0}&q=${encodeURIComponent(f.q)}&category=${encodeURIComponent(f.category)}${f.favorite ? "&favorite=1" : ""}${f.season ? "&season=1" : ""}${f.origin ? "&origin=" + f.origin : ""}`);
  foods = { ...r, items: more ? foods.items.concat(r.items) : r.items };
}

function foodDialog(x) {
  const custom = !x || x.source === "custom";
  const fld = (id, l, v, extra = "") => `<div class="fld"><label for="${id}">${l}</label><input class="inp" id="${id}" inputmode="decimal" value="${esc(v ?? "")}" ${extra}></div>`;
  const { el } = openDialog(`<h3>${x ? esc(x.name) : "Nuevo alimento"}</h3>${custom ? `<div class="fld"><label for="fo-name">Nombre</label><input class="inp" id="fo-name" maxlength="100" value="${esc(x ? x.name : "")}"></div>
      <div class="fld"><label for="fo-cat">Categoría</label><input class="inp" id="fo-cat" list="fo-cats" maxlength="40" value="${esc(x ? x.category : "Otros")}"><datalist id="fo-cats">${foods.categories.map((c) => `<option value="${esc(c)}">`).join("")}</datalist></div>
      <p class="muted small">Valores por 100 g</p><div class="two">${fld("fo-kcal", "kcal", x && x.kcal)}${fld("fo-p", "Proteína (g)", x && x.protein)}${fld("fo-c", "Hidratos (g)", x && x.carbs)}${fld("fo-f", "Grasa (g)", x && x.fat)}${fld("fo-fi", "Fibra (g)", x && x.fiber)}${fld("fo-s", "Porción habitual (g)", x ? x.serving_g : 100)}</div>`
      : `<p class="muted small">${esc(x.category)} · valores por 100 g: ${num(x.kcal)} kcal · ${num(x.protein, 1)} P · ${num(x.carbs, 1)} C · ${num(x.fat, 1)} G · porción ${num(x.serving_g)} g</p>`}
    ${x ? `<p class="muted small">${x.months && x.months.length ? `Temporada: ${monthsText(x.months)}` : "Disponible todo el año"}${x.origin ? ` · producto de ${ORIGIN[x.origin]}` : ""}</p>` : ""}
    <div class="fld"><label for="fo-notes">Notas</label><input class="inp" id="fo-notes" maxlength="300" value="${esc(x ? x.notes : "")}"></div>
    ${x ? `<label class="check"><input type="checkbox" id="fo-fav" ${x.favorite ? "checked" : ""}>Favorito</label><label class="check"><input type="checkbox" id="fo-arch" ${x.archived ? "checked" : ""}>Archivado (no sale en las búsquedas)</label>` : ""}
    <div class="dialog-actions">${x && x.source === "custom" ? `<button class="btn danger" type="button" id="fo-del">${icon("trash")}Borrar</button>` : ""}<span class="spacer"></span><button class="btn" data-close type="button">Cancelar</button><button class="btn primary" id="fo-ok" type="button">Guardar</button></div>`, { cls: "wide" });
  const v = (id) => el.querySelector(id) && el.querySelector(id).value;
  el.querySelector("#fo-ok").addEventListener("click", async (ev) => {
    setBusy(ev.currentTarget, true);
    const body = { notes: v("#fo-notes") };
    if (x) { body.favorite = el.querySelector("#fo-fav").checked; body.archived = el.querySelector("#fo-arch").checked; }
    if (custom) Object.assign(body, { name: v("#fo-name"), category: v("#fo-cat"), kcal: parseNum(v("#fo-kcal")), protein: parseNum(v("#fo-p")), carbs: parseNum(v("#fo-c")), fat: parseNum(v("#fo-f")), fiber: parseNum(v("#fo-fi")), serving_g: parseNum(v("#fo-s")) });
    try { x ? await patch(`/api/foods/${encodeURIComponent(x.id)}`, body) : await post("/api/foods", body); el.close(); await loadFoods(); render(); toast({ text: "Guardado", kind: "ok", timeout: 2000 }); }
    catch (e) { toast({ text: e.message, kind: "err" }); setBusy(ev.currentTarget, false); }
  });
  const d = el.querySelector("#fo-del");
  if (d) d.addEventListener("click", async () => { try { await del(`/api/foods/${encodeURIComponent(x.id)}`); el.close(); await loadFoods(); render(); } catch (e) { toast({ text: e.message, kind: "err" }); } });
}

async function recipeDialog(rid) {
  const r = rid ? await get(`/api/recipes/${rid}`) : { name: "", servings: 2, steps: "", notes: "", items: [] };
  const items = r.items.map((i) => ({ ...i }));
  const foodsById = {};
  for (const it of items) foodsById[it.food_id] = await get(`/api/foods/${encodeURIComponent(it.food_id)}`);
  const { el } = openDialog(`<h3>${rid ? "Editar receta" : "Nueva receta"}</h3><div class="fld"><label for="rc-name">Nombre</label><input class="inp" id="rc-name" maxlength="100" value="${esc(r.name)}"></div>
    <div class="fld"><label for="rc-sv">Raciones que salen</label><input class="inp" id="rc-sv" inputmode="decimal" value="${r.servings}"></div>
    <div class="fld"><label>Ingredientes (cantidad total de la receta)</label><div id="rc-items"></div><button class="btn block" type="button" id="rc-add">${icon("plus")}Añadir ingrediente</button></div><p class="muted small" id="rc-prev"></p>
    <div class="fld"><label for="rc-people">Escalar ingredientes</label>${peopleBox("rc-people")}<ul class="plain scaled" id="rc-scaled"></ul></div>
    <div class="fld"><label for="rc-steps">Preparación</label><textarea class="inp area" id="rc-steps" rows="4" maxlength="4000">${esc(r.steps)}</textarea></div>
    <div class="dialog-actions">${rid ? `<button class="btn danger" type="button" id="rc-del">${icon("trash")}Archivar</button>` : ""}<span class="spacer"></span><button class="btn" data-close type="button">Cancelar</button><button class="btn primary" id="rc-ok" type="button">Guardar</button></div>`, { cls: "wide" });
  const list = el.querySelector("#rc-items");
  const preview = () => {
    const sv = parseNum(el.querySelector("#rc-sv").value) || 1, tot = { kcal: 0, protein: 0, carbs: 0, fat: 0 };
    items.forEach((it) => { const fd = foodsById[it.food_id]; if (fd) Object.keys(tot).forEach((k) => { tot[k] += (fd[k] * (parseNum(it.grams) || 0)) / 100; }); });
    scaled(); el.querySelector("#rc-prev").textContent = items.length ? `Por ración: ${num(tot.kcal / sv)} kcal · ${num(tot.protein / sv, 1)} P · ${num(tot.carbs / sv, 1)} C · ${num(tot.fat / sv, 1)} G` : "";
  };
  const scaled = () => {
    const n = getPeople(), sv = parseNum(el.querySelector("#rc-sv").value) || 1, k = n / sv;
    el.querySelector("#rc-scaled").innerHTML = items.length ? `<li class="muted small">Cantidades para ${n} ${n === 1 ? "persona" : "personas"} (la receta da ${num(sv, 2)} raciones):</li>` + items.map((it) => `<li>${esc((foodsById[it.food_id] || {}).name || it.food_id)} <b>${num((parseNum(it.grams) || 0) * k)} g</b></li>`).join("") : "";
  };
  bindPeople(el, scaled);
  const draw = () => { list.innerHTML = items.map((it, i) => `<div class="ing"><span class="grow">${esc((foodsById[it.food_id] || {}).name || it.food_id)}</span><input class="inp" data-g="${i}" inputmode="decimal" value="${it.grams}" aria-label="Gramos"><em>g</em><button class="icon-btn sm danger" type="button" data-rm="${i}" aria-label="Quitar">${icon("trash")}</button></div>`).join(""); preview(); };
  draw();
  el.addEventListener("input", (e) => { if (e.target.dataset.g !== undefined) items[Number(e.target.dataset.g)].grams = e.target.value; preview(); });
  el.addEventListener("click", async (e) => {
    const rm = e.target.closest("[data-rm]");
    if (rm) { items.splice(Number(rm.dataset.rm), 1); draw(); }
    else if (e.target.closest("#rc-add")) { const x = await pickFood(); if (x) { foodsById[x.id] = x; items.push({ food_id: x.id, grams: x.serving_g }); draw(); } }
  });
  el.querySelector("#rc-ok").addEventListener("click", async (ev) => {
    setBusy(ev.currentTarget, true);
    const body = { name: el.querySelector("#rc-name").value, servings: parseNum(el.querySelector("#rc-sv").value), steps: el.querySelector("#rc-steps").value, items: items.map((i) => ({ food_id: i.food_id, grams: parseNum(i.grams) })) };
    try { rid ? await put(`/api/recipes/${rid}`, body) : await post("/api/recipes", body); el.close(); await loadRecipes(); render(); toast({ text: "Receta guardada", kind: "ok", timeout: 2000 }); }
    catch (x) { toast({ text: x.message, kind: "err" }); setBusy(ev.currentTarget, false); }
  });
  const d = el.querySelector("#rc-del");
  if (d) d.addEventListener("click", async () => { if (await confirmDialog({ title: "Archivar receta", body: "Dejará de aparecer; el menú ya planificado se conserva.", confirm: "Archivar", danger: true })) { await del(`/api/recipes/${rid}`); el.close(); await loadRecipes(); render(); } });
}

export function init() {
  const r = root();
  r.addEventListener("input", (e) => { if (e.target.id === "fd-q") { f.q = e.target.value; clearTimeout(timer); timer = setTimeout(async () => { await loadFoods(); const l = document.getElementById("fd-list"); if (l) { render(); const q = document.getElementById("fd-q"); q.focus(); q.setSelectionRange(q.value.length, q.value.length); } }, 250); } });
  r.addEventListener("change", async (e) => {
    if (e.target.id === "fd-c") { f.category = e.target.value; await loadFoods(); render(); }
    else if (e.target.id === "fd-f") { f.favorite = e.target.checked; await loadFoods(); render(); }
  });
  r.addEventListener("click", async (e) => {
    const t = e.target.closest("[data-tab],[data-act],[data-food],[data-recipe],[data-flt]");
    if (!t) return;
    try {
      if (t.dataset.tab) { tab = t.dataset.tab; if (tab === "recipes") await loadRecipes(); else await loadFoods(); render(); }
      else if (t.dataset.flt) {
        const k = t.dataset.flt;
        if (k === "season") f.season = !f.season; else if (k === "cat" || k === "es") f.origin = f.origin === k ? "" : k;
        else if (k === "rseason") rf.season = !rf.season; else { const o = k.slice(1); rf.origin = rf.origin === o ? "" : o; }
        if (k.startsWith("r")) await loadRecipes(); else await loadFoods();
        render();
      }
      else if (t.dataset.act === "new-food") foodDialog(null);
      else if (t.dataset.act === "new-recipe") recipeDialog(null);
      else if (t.dataset.act === "more") { await loadFoods(true); render(); }
      else if (t.dataset.food) foodDialog(await get(`/api/foods/${encodeURIComponent(t.dataset.food)}`));
      else if (t.dataset.recipe) recipeDialog(Number(t.dataset.recipe));
    } catch (x) { toast({ text: x.message, kind: "err" }); }
  });
  r.addEventListener("keydown", (e) => { const c = e.target.closest("[data-food],[data-recipe]"); if (c && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); c.click(); } });
}
export async function show() { try { try { season = await get("/api/season"); } catch (e) { season = null; } if (tab === "recipes") await loadRecipes(); else await loadFoods(); render(); } catch (e) { root().innerHTML = `<div class="empty">${icon("warning")}<p>No se pudieron cargar los alimentos.</p></div>`; } }
