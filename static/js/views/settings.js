import { get, put, post, upload } from "../api.js";
import { esc, icon } from "../fmt.js";
import { toast, confirmDialog, setBusy } from "../ui.js";

const root = () => document.getElementById("view-settings");
let s = null;

const sel = (id, cur, opts) => `<select class="inp" id="${id}">${opts.map(([v, l]) => `<option value="${v}" ${String(cur) === String(v) ? "selected" : ""}>${l}</option>`).join("")}</select>`;
const tog = (id, on, label, hint = "") => `<label class="check"><input type="checkbox" id="${id}" ${on ? "checked" : ""}>${label}</label>${hint ? `<small class="muted">${hint}</small>` : ""}`;

function draw() {
  root().innerHTML = `<header class="view-head"><div><h1 id="h-settings">Ajustes</h1></div><div class="head-actions"><button class="btn primary" type="button" id="st-save">${icon("check")}Guardar</button></div></header>
    <div class="glass card"><h3>Mi perfil</h3><p class="muted small">El asistente lo usa para recomendar y ajustar tus rutinas.</p>
      <div class="fld"><label for="p-goal">Objetivo</label><input class="inp" id="p-goal" maxlength="300" value="${esc(s.goal)}" placeholder="Ej.: ganar masa muscular, correr una media maratón…"></div>
      <div class="two"><div class="fld"><label for="p-exp">Experiencia</label>${sel("p-exp", s.experience, [["beginner", "Principiante"], ["intermediate", "Intermedio"], ["advanced", "Avanzado"]])}</div>
      <div class="fld"><label for="p-days">Días de entrenamiento por semana</label>${sel("p-days", s.days_per_week, [1, 2, 3, 4, 5, 6, 7].map((n) => [n, n]))}</div></div>
      <div class="fld"><label for="p-eq">Material disponible</label><input class="inp" id="p-eq" maxlength="300" value="${esc(s.equipment)}" placeholder="Ej.: gimnasio completo / mancuernas y banco / solo peso corporal"></div>
      <div class="fld"><label for="p-inj">Lesiones o limitaciones</label><input class="inp" id="p-inj" maxlength="300" value="${esc(s.injuries)}" placeholder="Ej.: molestia en el hombro derecho"></div>
      <div class="fld"><label for="p-notes">Notas para el asistente</label><textarea class="inp area" id="p-notes" rows="3" maxlength="1500">${esc(s.notes)}</textarea></div>
      <div class="fld"><label for="p-units">Unidad de peso</label>${sel("p-units", s.units, [["kg", "Kilogramos (kg)"], ["lb", "Libras (lb)"]])}<small>Solo cambia la etiqueta: los valores ya guardados no se convierten.</small></div></div>
    <div class="glass card"><h3>Asistente: evaluación y ajuste de rutinas</h3><p class="muted small">El asistente analiza tus entrenamientos (cargas, repeticiones, RPE, descansos y constancia) y modifica las rutinas con progresión gradual. Cada cambio queda en el historial de la rutina y puedes deshacerlo.</p>
      <div class="two"><div class="fld"><label for="a-auto">Ajuste automático</label>${sel("a-auto", s.auto_adjust, [["off", "Desactivado (solo cuando lo pido)"], ["after", "Después de cada entrenamiento"], ["weekly", "Una vez por semana"]])}</div>
      <div class="fld"><label for="a-style">Estilo de progresión</label>${sel("a-style", s.adjust_style, [["conservative", "Conservador"], ["normal", "Normal"], ["aggressive", "Agresivo"]])}</div></div></div>
    <div class="glass card"><h3>Durante el entrenamiento</h3><div class="stack">${tog("w-sound", s.sound === "1", "Sonido al acabar los descansos y las series")}${tog("w-vib", s.vibrate === "1", "Vibración (móvil)")}${tog("w-lock", s.wake_lock === "1", "Mantener la pantalla encendida")}</div></div>
    <div class="glass card"><h3>Copia de seguridad: exportar e importar</h3><p class="muted small">Exporta tus rutinas, entrenamientos, ejercicios propios y ajustes en un archivo JSON, y vuelve a importarlo cuando quieras (en este u otro portal).</p>
      <div class="dialog-actions wrap"><a class="btn" href="/api/export" download>${icon("download")}Exportar todo (JSON)</a><a class="btn" href="/api/export?media=1" download>${icon("download")}Exportar con mis imágenes y vídeos</a><a class="btn" href="/api/export/sessions.csv" download>${icon("download")}Entrenamientos (CSV)</a></div>
      <hr><div class="fld"><label for="im-file">Importar un archivo exportado</label><input class="inp" type="file" id="im-file" accept="application/json,.json"></div>
      <div class="fld"><label for="im-mode">Cómo importar</label>${sel("im-mode", "merge", [["merge", "Combinar (añade y actualiza; no borra nada)"], ["replace", "Reemplazar (borra mis rutinas, entrenamientos y ejercicios propios)"]])}</div>
      <button class="btn" type="button" id="im-go">${icon("upload")}Importar</button></div>
    <div class="glass card"><h3>Créditos</h3><p class="muted small">Ejercicios, descripciones e imágenes de <a href="https://github.com/yuhonas/free-exercise-db" target="_blank" rel="noopener noreferrer">free-exercise-db</a> (dominio público, Unlicense). Los ejercicios de cardio añadidos y su descripción en español son propios; puedes añadir tus imágenes y vídeos a cualquier ejercicio.</p></div>`;
}

const v = (id) => document.getElementById(id);

export function init() {
  root().addEventListener("click", async (e) => {
    const b = e.target.closest("button");
    if (!b) return;
    if (b.id === "st-save") {
      setBusy(b, true);
      try {
        s = await put("/api/settings", { goal: v("p-goal").value, experience: v("p-exp").value, days_per_week: Number(v("p-days").value), equipment: v("p-eq").value, injuries: v("p-inj").value, notes: v("p-notes").value, units: v("p-units").value,
          auto_adjust: v("a-auto").value, adjust_style: v("a-style").value, sound: v("w-sound").checked ? "1" : "0", vibrate: v("w-vib").checked ? "1" : "0", wake_lock: v("w-lock").checked ? "1" : "0" });
        toast({ text: "Ajustes guardados", kind: "ok", timeout: 2500 });
      } catch (x) { toast({ text: x.message, kind: "err" }); }
      setBusy(b, false);
    } else if (b.id === "im-go") {
      const f = v("im-file").files[0], mode = v("im-mode").value;
      if (!f) return toast({ text: "Elige primero un archivo", kind: "warn", timeout: 2500 });
      if (mode === "replace" && !(await confirmDialog({ title: "Reemplazar datos", body: "Se borrarán tus rutinas, entrenamientos y ejercicios propios actuales y se sustituirán por los del archivo.", confirm: "Reemplazar", danger: true }))) return;
      setBusy(b, true);
      try {
        const data = JSON.parse(await f.text());
        const r = await post(`/api/import?mode=${mode}`, data);
        toast({ text: `Importado: ${r.routines} rutinas, ${r.sessions} entrenamientos, ${r.exercises} ejercicios${r.skipped_sessions ? ` (${r.skipped_sessions} entrenamientos ya existían)` : ""}`, kind: "ok", timeout: 7000 });
        s = await get("/api/settings"); draw();
      } catch (x) { toast({ text: x instanceof SyntaxError ? "El archivo no es un JSON válido" : x.message, kind: "err" }); }
      setBusy(b, false);
    }
  });
}
export async function show() { try { s = await get("/api/settings"); draw(); } catch (e) { root().innerHTML = `<div class="empty">${icon("warning")}<p>No se pudieron cargar los ajustes.</p></div>`; } }
