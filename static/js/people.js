/* Número de personas para escalar cantidades (menú, compra, recetas y Cocinar). Se recuerda en el navegador; las calorías y macros del menú siguen siendo por persona. */
import { num } from "./util.js";
import { esc } from "./fmt.js";

const KEY = "people";
export const getPeople = () => { try { const n = Number(localStorage.getItem(KEY)); return n >= 1 && n <= 50 ? n : 1; } catch (e) { return 1; } };
export const setPeople = (n) => { try { localStorage.setItem(KEY, String(Math.max(1, Math.min(50, Math.round(Number(n)) || 1)))); } catch (e) { /* ignorar */ } };

export const peopleBox = (id = "people") => `<label class="people" title="Escala las cantidades al número de personas"><span>Personas</span><button class="icon-btn sm" type="button" data-people-step="-1" aria-label="Una persona menos">−</button>
  <input class="inp" id="${id}" data-people type="number" min="1" max="50" step="1" inputmode="numeric" value="${getPeople()}" aria-label="Número de personas"><button class="icon-btn sm" type="button" data-people-step="1" aria-label="Una persona más">+</button></label>`;

/* Engancha el control dentro de `root`; `onChange` se llama tras guardar el valor. */
export function bindPeople(root, onChange) {
  root.addEventListener("click", (e) => {
    const b = e.target.closest("[data-people-step]");
    if (!b) return;
    setPeople(getPeople() + Number(b.dataset.peopleStep)); onChange();
  });
  root.addEventListener("change", (e) => { if (e.target.matches("[data-people]")) { setPeople(e.target.value); onChange(); } });
}

/* Cantidad de una entrada del menú para n personas. */
export function scaledQty(e, n) {
  if (n === 1) return e.qty;
  if (e.kind === "food" && e.grams != null) return `${num(e.grams * n)} g`;
  if (e.kind === "recipe" && e.servings != null) { const s = e.servings * n; return `${num(s, 2)} ${s === 1 ? "ración" : "raciones"}`; }
  return e.qty;
}
export const scaleNote = (n) => (n > 1 ? `<p class="muted small scale-note">Cantidades para ${n} personas. Calorías y macros, por persona.</p>` : "");
export { esc };
