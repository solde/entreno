import { get } from "../api.js";
import { esc, icon } from "../fmt.js";
import { openDialog } from "../ui.js";
import { thumb } from "../media.js";
import { CAT, MUSCLE, lab, exName } from "../labels.js";

/** Selector de ejercicios en un diálogo. Devuelve el ejercicio elegido o null. */
export function pickExercise({ title = "Elegir ejercicio" } = {}) {
  return new Promise((resolve) => {
    let chosen = null, timer = null, items = [], total = 0;
    const f = { q: "", category: "" };
    const { el } = openDialog(`<h3>${esc(title)}</h3>
      <input class="inp" id="pk-q" type="search" placeholder="Buscar (nombre en español o inglés)…" autocomplete="off">
      <div class="seg wrap" id="pk-cat" role="group" aria-label="Categoría"><button type="button" data-c="" aria-pressed="true">Todos</button>${Object.entries(CAT).map(([k, v]) => `<button type="button" data-c="${k}" aria-pressed="false">${v}</button>`).join("")}</div>
      <ul class="pick-list" id="pk-list"></ul><p class="muted small" id="pk-more"></p>
      <div class="dialog-actions"><button class="btn" data-close type="button">Cancelar</button></div>`, { cls: "wide", id: "dialog2", onClose: () => resolve(chosen) });
    const list = el.querySelector("#pk-list"), more = el.querySelector("#pk-more");
    const draw = () => {
      list.innerHTML = items.map((e, i) => `<li><button type="button" class="pick-item" data-i="${i}">${thumb(e)}<span class="pick-name"><b>${esc(exName(e))}</b>${e.name_es ? `<small>${esc(e.name)}</small>` : ""}<small>${esc(lab(CAT, e.category))}${e.primary[0] ? " · " + esc(lab(MUSCLE, e.primary[0])) : ""}</small></span>${icon("plus")}</button></li>`).join("") || `<li class="muted small pad">Sin resultados.</li>`;
      more.innerHTML = items.length < total ? `<button class="btn" type="button" id="pk-next">Ver más (${total - items.length})</button>` : "";
    };
    const load = async (append) => {
      const r = await get(`/api/exercises?limit=40&offset=${append ? items.length : 0}&q=${encodeURIComponent(f.q)}&category=${encodeURIComponent(f.category)}`);
      total = r.total; items = append ? items.concat(r.items) : r.items; draw();
    };
    el.querySelector("#pk-q").addEventListener("input", (e) => { f.q = e.target.value; clearTimeout(timer); timer = setTimeout(() => load(false), 220); });
    el.querySelector("#pk-cat").addEventListener("click", (e) => { const b = e.target.closest("button"); if (!b) return; f.category = b.dataset.c; el.querySelectorAll("#pk-cat button").forEach((x) => x.setAttribute("aria-pressed", String(x === b))); load(false); });
    el.addEventListener("click", (e) => {
      const it = e.target.closest(".pick-item");
      if (it) { chosen = items[Number(it.dataset.i)]; el.close(); }
      else if (e.target.id === "pk-next") load(true);
    });
    load(false).then(() => el.querySelector("#pk-q").focus());
  });
}
