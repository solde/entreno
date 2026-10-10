import { get } from "../api.js";
import { esc, icon } from "../fmt.js";
import { toast } from "../ui.js";
import { copyText } from "../ui.js";
import { num } from "../util.js";
import { iso, parse, addDays, mondayOf, fmtShort } from "../cal.js";

const root = () => document.getElementById("view-shopping");
let range = null, data = null, pending = false;
const key = () => `shop-${range[0]}-${range[1]}`;
const ticks = () => { try { return new Set(JSON.parse(localStorage.getItem(key()) || "[]")); } catch (e) { return new Set(); } };
const saveTicks = (s) => { try { localStorage.setItem(key(), JSON.stringify([...s])); } catch (e) { /* ignorar */ } };

function render() {
  const t = ticks();
  const by = {};
  data.items.forEach((i) => { (by[i.category] = by[i.category] || []).push(i); });
  root().innerHTML = `<header class="view-head"><div><h1 id="h-shopping">Lista de la compra</h1><p class="muted">Ingredientes del menú del ${esc(fmtShort(parse(range[0])))} al ${esc(fmtShort(parse(range[1])))}, sumados.</p></div>
      <div class="head-actions"><button class="btn" type="button" data-act="copy">${icon("copy")}Copiar lista</button></div></header>
    <div class="glass card filters"><div class="filter-row"><label class="fld">Desde<input class="inp" id="sh-a" type="date" value="${range[0]}"></label><label class="fld">Hasta<input class="inp" id="sh-b" type="date" value="${range[1]}"></label></div>
      <div class="chips"><button class="chip" type="button" data-r="this">Esta semana</button><button class="chip" type="button" data-r="next">Próxima semana</button><button class="chip" type="button" data-r="14">Dos semanas</button><label class="check"><input type="checkbox" id="sh-p" ${pending ? "checked" : ""}>Solo lo que aún no he marcado como hecho</label></div></div>
    ${data.items.length || data.unspecified.length ? Object.entries(by).map(([c, items]) => `<section class="glass card"><h3>${esc(c)}</h3><ul class="shop">${items.map((i) => `<li class="${t.has(i.food_id) ? "got" : ""}"><label><input type="checkbox" data-t="${esc(i.food_id)}" ${t.has(i.food_id) ? "checked" : ""}><span class="grow"><b>${esc(i.name)}</b></span><span>${num(i.grams)} g${i.units && i.serving_g && i.serving_g < 400 && i.units >= 1.5 ? ` <small class="muted">(≈ ${num(i.units, 1)} uds.)</small>` : ""}</span></label></li>`).join("")}</ul></section>`).join("")
      + (data.unspecified.length ? `<section class="glass card"><h3>Sin desglosar</h3><p class="muted small">Entradas libres del menú, sin ingredientes:</p><ul class="plain">${data.unspecified.map((x) => `<li>${esc(x)}</li>`).join("")}</ul></section>` : "")
      : `<div class="empty">${icon("cart")}<p>No hay alimentos en el menú de estas fechas. Planifica el menú primero.</p></div>`}`;
}

async function load() { data = await get(`/api/plan/shopping?from=${range[0]}&to=${range[1]}${pending ? "&pending=1" : ""}`); render(); }

function setRange(kind) {
  const m = mondayOf(new Date());
  range = kind === "this" ? [iso(m), iso(addDays(m, 6))] : kind === "next" ? [iso(addDays(m, 7)), iso(addDays(m, 13))] : [iso(m), iso(addDays(m, 13))];
  return load();
}

export function init() {
  const r = root();
  r.addEventListener("change", async (e) => {
    try {
      if (e.target.dataset.t) { const s = ticks(); e.target.checked ? s.add(e.target.dataset.t) : s.delete(e.target.dataset.t); saveTicks(s); e.target.closest("li").classList.toggle("got", e.target.checked); }
      else if (e.target.id === "sh-a" || e.target.id === "sh-b") { range = [document.getElementById("sh-a").value, document.getElementById("sh-b").value]; await load(); }
      else if (e.target.id === "sh-p") { pending = e.target.checked; await load(); }
    } catch (x) { toast({ text: x.message, kind: "err" }); }
  });
  r.addEventListener("click", async (e) => {
    const t = e.target.closest("[data-r],[data-act]");
    if (!t) return;
    try {
      if (t.dataset.r) await setRange(t.dataset.r);
      else if (t.dataset.act === "copy") {
        const lines = data.items.map((i) => `- ${i.name}: ${Math.round(i.grams)} g`).concat(data.unspecified.map((x) => `- ${x}`));
        toast({ text: (await copyText(lines.join("\n"))) ? "Lista copiada" : "No se pudo copiar", kind: "ok", timeout: 2500 });
      }
    } catch (x) { toast({ text: x.message, kind: "err" }); }
  });
}
export async function show() {
  try {
    const saved = sessionStorage.getItem("shop-range");
    if (saved) { range = JSON.parse(saved); sessionStorage.removeItem("shop-range"); await load(); }
    else if (range) await load();
    else await setRange("this");
  } catch (e) { root().innerHTML = `<div class="empty">${icon("warning")}<p>No se pudo cargar la lista.</p></div>`; }
}
