/* Casas de Nutricion: espacios compartidos (alimentos, recetas, menu y compra) entre las personas asignadas. El boton de la barra superior muestra la casa
   activa y abre el gestor: elegir casa, crear, anadir o quitar personas, renombrar y eliminar. Cambiar de casa recarga la pagina (todas las vistas leen de la casa). */
import { get, post, put, patch, del } from "./api.js";
import { esc, icon } from "./fmt.js";
import { openDialog, confirmDialog, toast, setBusy } from "./ui.js";
import { getPeople, setPeople } from "./people.js";

let st = { me: "", active: null, casas: [], known_users: [] };
const btn = () => document.getElementById("casa-btn");
const activeCasa = () => st.casas.find((c) => c.slug === st.active) || null;
const ROLE = { owner: "administra", member: "miembro" };

function paintButton() {
  const b = btn();
  if (!b) return;
  const c = activeCasa();
  b.querySelector("span").textContent = c ? c.name : "Mi menú";
  b.title = c ? `Casa activa: ${c.name} (${c.members.length} ${c.members.length === 1 ? "persona" : "personas"})` : "Menú personal. Pulsa para elegir o crear una casa";
  b.classList.toggle("on", !!c);
}

async function load() { st = await get("/api/casas"); paintButton(); return st; }

function casaRow(c) {
  const mine = c.role === "owner", on = c.slug === st.active;
  const people = c.members.map((m) => `<span class="chip ${m.role === "owner" ? "alt" : ""}" title="${esc(ROLE[m.role] || m.role)}">${esc(m.user)}${mine ? `<button class="casa-x" type="button" data-rm="${esc(c.slug)}" data-u="${esc(m.user)}" aria-label="Quitar a ${esc(m.user)}" title="Quitar">×</button>` : ""}</span>`).join(" ");
  return `<li class="casa ${on ? "on" : ""}" data-slug="${esc(c.slug)}">
    <div class="casa-head"><strong>${esc(c.name)}</strong><span class="badge ${mine ? "info" : ""}">${esc(ROLE[c.role] || c.role)}</span><span class="grow"></span>
      ${on ? `<span class="badge ok">${icon("check")}En uso</span>` : `<button class="btn sm primary" type="button" data-use="${esc(c.slug)}">Usar esta casa</button>`}</div>
    <div class="casa-people">${people}</div>
    ${mine ? `<form class="casa-add" data-add="${esc(c.slug)}"><input class="inp" name="user" list="casa-known" maxlength="32" placeholder="Usuario a asignar" autocomplete="off" autocapitalize="none" spellcheck="false" aria-label="Usuario a asignar a ${esc(c.name)}" required>
      <label class="check"><input type="checkbox" name="owner">Administra</label><button class="btn sm" type="submit">${icon("plus")}Asignar</button></form>
      <div class="casa-acts"><button class="btn sm" type="button" data-rename="${esc(c.slug)}">${icon("pencil")}Renombrar</button><button class="btn sm danger" type="button" data-del="${esc(c.slug)}">${icon("trash")}Eliminar</button></div>`
      : `<div class="casa-acts"><button class="btn sm danger" type="button" data-leave="${esc(c.slug)}">Salir de la casa</button></div>`}
  </li>`;
}

function draw() {
  const { el } = openDialog(`<h3>Casas</h3>
    <p class="muted small">Una casa comparte los alimentos, las recetas, el menú y la lista de la compra entre las personas asignadas. Tus objetivos, tu perfil y tus entrenos siguen siendo solo tuyos. Puedes estar en varias casas.</p>
    <ul class="casa-list"><li class="casa ${st.active ? "" : "on"}"><div class="casa-head"><strong>Mi menú personal</strong><span class="muted small">solo yo</span><span class="grow"></span>
      ${st.active ? `<button class="btn sm primary" type="button" data-use="">Usar el personal</button>` : `<span class="badge ok">${icon("check")}En uso</span>`}</div></li>
      ${st.casas.map(casaRow).join("")}</ul>
    <datalist id="casa-known">${st.known_users.map((u) => `<option value="${esc(u)}"></option>`).join("")}</datalist>
    <form class="casa-new" id="casa-new"><h4>Nueva casa</h4><div class="casa-add"><input class="inp" name="name" maxlength="60" placeholder="Nombre (p. ej. Casa de Palleja)" aria-label="Nombre de la casa" required>
      <button class="btn primary" type="submit">${icon("plus")}Crear</button></div>
      <label class="check"><input type="checkbox" name="copy">Copiar mi menú, recetas y alimentos propios actuales a la casa nueva</label></form>
    <div class="dialog-actions"><button class="btn" data-close type="button">Cerrar</button></div>`, { cls: "wide casa-dlg" });
  el.onsubmit = onSubmit; el.onclick = onClick;
}

async function act(fn, ok) {
  try { st = await fn(); paintButton(); if (ok) toast({ text: ok, kind: "ok", timeout: 2500 }); draw(); }
  catch (x) { toast({ text: x.message, kind: "err" }); }
}

async function onSubmit(e) {
  e.preventDefault();
  const f = e.target, b = f.querySelector("button[type=submit]");
  setBusy(b, true);
  try {
    if (f.id === "casa-new") {
      const r = await post("/api/casas", { name: f.name.value, copy: f.copy.checked });
      toast({ text: r.copied ? `Casa creada con ${r.copied.plan_entries} entradas de menú, ${r.copied.recipes} recetas y ${r.copied.foods} alimentos` : "Casa creada", kind: "ok", timeout: 3500 });
      return location.reload();                                  // pasa a ser la activa
    }
    if (f.dataset.add) { st = await post(`/api/casas/${f.dataset.add}/members`, { user: f.user.value, role: f.owner.checked ? "owner" : "member" }); paintButton(); toast({ text: "Persona asignada", kind: "ok", timeout: 2000 }); draw(); }
  } catch (x) { toast({ text: x.message, kind: "err" }); setBusy(b, false); }
}

async function onClick(e) {
  const t = e.target.closest("button");
  if (!t) return;
  const d = t.dataset;
  if ("use" in d) {
    try { await put("/api/casas/active", { casa: d.use || null }); location.reload(); } catch (x) { toast({ text: x.message, kind: "err" }); }
  } else if (d.rm) {
    const c = st.casas.find((x) => x.slug === d.rm);
    if (await confirmDialog({ title: "Quitar de la casa", body: `${d.u} dejará de ver «${c.name}».`, confirm: "Quitar", danger: true })) await act(() => del(`/api/casas/${d.rm}/members/${d.u}`), "Persona quitada");
    else draw();
  } else if (d.leave) {
    const c = st.casas.find((x) => x.slug === d.leave);
    if (await confirmDialog({ title: "Salir de la casa", body: `Dejarás de ver el menú y las recetas de «${c.name}».`, confirm: "Salir", danger: true })) {
      try { await del(`/api/casas/${d.leave}/members/${st.me}`); location.reload(); } catch (x) { toast({ text: x.message, kind: "err" }); draw(); }
    } else draw();
  } else if (d.rename) {
    const c = st.casas.find((x) => x.slug === d.rename);
    const n = prompt("Nuevo nombre de la casa", c.name);
    if (n && n.trim()) await act(() => patch(`/api/casas/${d.rename}`, { name: n }), "Casa renombrada");
  } else if (d.del) {
    const c = st.casas.find((x) => x.slug === d.del);
    if (await confirmDialog({ title: "Eliminar la casa", body: `Se eliminará «${c.name}» para todas las personas asignadas, con su menú, alimentos y recetas propios. Se guarda una copia aparte por si hay que recuperarla.`, confirm: "Eliminar", danger: true })) {
      try { st = await del(`/api/casas/${d.del}`); location.reload(); } catch (x) { toast({ text: x.message, kind: "err" }); draw(); }
    } else draw();
  }
}

export async function init() {
  const b = btn();
  if (!b) return;
  b.addEventListener("click", async () => { try { await load(); draw(); } catch (x) { toast({ text: x.message, kind: "err" }); } });
  try {
    await load();
    let had = false;
    try { had = localStorage.getItem("people") !== null; } catch (e) { /* ignorar */ }
    const c = activeCasa();
    if (c && !had && c.members.length > 1) setPeople(c.members.length);        // primera vez: tantas personas como la casa
  } catch (e) { /* sin red: el boton queda con "Mi menú" */ }
}
