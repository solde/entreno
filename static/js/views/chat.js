import { get, post, del } from "../api.js";
import { esc, icon } from "../fmt.js";
import { md } from "../md.js";
import { toast, confirmDialog, setBusy } from "../ui.js";

const root = () => document.getElementById("view-chat");
const TOOLS = { exercise_search: "Buscando ejercicios", exercise_get: "Mirando un ejercicio", routine_list: "Revisando tus rutinas", routine_get: "Leyendo una rutina", sessions_list: "Revisando tus entrenamientos", session_get: "Leyendo un entrenamiento",
  stats_get: "Calculando estadísticas", progress_get: "Revisando tu progreso", profile_get: "Leyendo tu perfil", routine_create: "Creando una rutina", routine_update: "Ajustando una rutina", routine_restore: "Restaurando una versión", routine_archive: "Archivando una rutina", exercise_create: "Creando un ejercicio" };
const SUGGEST = [
  "Hazme una rutina de fuerza de 3 días a la semana para ganar masa muscular.",
  "Revisa mis últimos entrenamientos y dime qué debería mejorar.",
  "¿Cómo voy de progresión en press de banca y sentadilla?",
  "Añade a mi rutina de pierna dos ejercicios de glúteo y ajusta los descansos.",
  "Prepárame un plan de cardio suave para correr 5 km en 8 semanas.",
];
let sessions = [], cur = null, run = null, online = true, sideOpen = false;

const scroller = () => document.getElementById("chat-msgs");
function stick() { const s = scroller(); if (s) s.scrollTop = s.scrollHeight; }
function nearBottom() { const s = scroller(); return !s || s.scrollHeight - s.scrollTop - s.clientHeight < 120; }

function bubbleUser(t) { return `<div class="msg user"><div class="bub">${esc(t.user_message).replace(/\n/g, "<br>")}</div></div>`; }
function bubbleBot(t) {
  if (t.status === "error") return `<div class="msg bot"><div class="bub err">${icon("warning")}${esc(t.error === "cancelled" ? "Respuesta cancelada." : t.error || "Error")}</div></div>`;
  return `<div class="msg bot"><div class="bub md">${md(t.answer)}</div></div>`;
}

function thread() {
  if (!cur) return `<div class="chat-empty"><span class="app-icon k-ai">${icon("sparkle")}</span><h2>Asistente de entrenamiento</h2>
    <p class="muted">Conoce tus rutinas, tus entrenamientos y la base de ejercicios. Puede crear y ajustar tus rutinas (queda todo en el historial, con opción de deshacer). No sustituye a un entrenador ni a un médico.</p>
    <div class="suggest">${SUGGEST.map((s) => `<button type="button" class="btn" data-suggest="${esc(s)}">${esc(s)}</button>`).join("")}</div></div>`;
  return cur.turns.map((t) => bubbleUser(t) + (t.status === "queued" || t.status === "running" ? "" : bubbleBot(t))).join("") + (run ? liveBubble() : "");
}
function liveBubble() {
  const tools = run.tools.length ? `<div class="tool-line">${run.tools.map((t) => `<span class="chip ${t.status === "start" ? "pulse" : ""}">${icon(t.status === "start" ? "refresh" : "check")}${esc(TOOLS[t.name] || t.name)}</span>`).join("")}</div>` : "";
  return `<div class="msg bot" id="live"><div class="bub md">${tools}${run.text ? md(run.text) : '<span class="typing"><i></i><i></i><i></i></span>'}</div></div>`;
}

function sideList() {
  return `<button class="btn primary block" type="button" id="ch-new">${icon("plus")}Nueva conversación</button>
    <ul class="sess">${sessions.map((s) => `<li class="${cur && cur.id === s.id ? "on" : ""}"><button type="button" data-open="${s.id}">${esc(s.title)}</button><button class="icon-btn sm" type="button" data-del="${s.id}" aria-label="Borrar conversación" title="Borrar">${icon("trash")}</button></li>`).join("")}</ul>`;
}

function shell() {
  root().innerHTML = `<div class="chat ${sideOpen ? "side-open" : ""}">
    <aside class="glass chat-side" id="chat-side">${sideList()}</aside>
    <section class="glass chat-main">
      <header class="chat-head"><button class="icon-btn only-narrow" type="button" id="ch-toggle" aria-label="Conversaciones">${icon("menu")}</button><h2 id="h-chat">${esc(cur ? cur.title : "Asistente")}</h2>
        <span class="badge ${online ? "ok" : "bad"}" id="ch-status">${online ? "Asistente conectado" : "Asistente desconectado"}</span></header>
      <div class="chat-msgs" id="chat-msgs" aria-live="polite">${thread()}</div>
      <form class="composer" id="ch-form"><textarea class="inp" id="ch-input" rows="1" maxlength="8000" placeholder="Pregunta por tus rutinas, pide cambios, planes, progresión…" aria-label="Mensaje"></textarea>
        ${run ? `<button class="btn danger" type="button" id="ch-stop">${icon("stop")}<span class="hide-narrow">Parar</span></button>` : `<button class="btn primary" type="submit" id="ch-send">${icon("send")}<span class="hide-narrow">Enviar</span></button>`}</form>
      <p class="footnote chat-foot">Puede cometer errores y puede modificar tus rutinas (revisa el historial de cada rutina). Ante dolor o lesión, consulta a un profesional.</p>
    </section></div>`;
  stick();
  const ta = document.getElementById("ch-input");
  const fit = () => { ta.style.height = "auto"; ta.style.height = Math.min(ta.scrollHeight, 180) + "px"; };
  ta.addEventListener("input", fit);
  ta.addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); document.getElementById("ch-form").requestSubmit(); } });
}

function repaint() {
  const m = scroller();
  if (!m) return shell();
  const stickIt = nearBottom();
  m.innerHTML = thread();
  if (stickIt) stick();
}

async function loadSessions() { sessions = await get("/api/chat/sessions"); }
async function status() { try { online = (await get("/api/chat/status")).agent_online; const b = document.getElementById("ch-status"); if (b) { b.className = `badge ${online ? "ok" : "bad"}`; b.textContent = online ? "Asistente conectado" : "Asistente desconectado"; } } catch (e) { /* ignorar */ } }

async function openSession(id) {
  cur = await get(`/api/chat/sessions/${id}`);
  const live = cur.turns.find((t) => t.status === "queued" || t.status === "running");
  run = null;
  sideOpen = false;
  shell();
  if (live) follow(live.id);
}

async function newSession() { const r = await post("/api/chat/sessions"); await loadSessions(); await openSession(r.id); document.getElementById("ch-input").focus(); }

async function send(text) {
  text = text.trim();
  if (!text || run) return;
  if (!cur) { const r = await post("/api/chat/sessions"); cur = { id: r.id, title: "Nueva conversación", turns: [] }; }
  try {
    const r = await post(`/api/chat/sessions/${cur.id}/messages`, { text });
    cur.turns.push({ id: r.turn_id, user_message: text, status: "queued", answer: null, error: null });
    follow(r.turn_id);
    document.getElementById("ch-input") && (document.getElementById("ch-input").value = "");
    loadSessions().then(() => { const s = document.querySelector(".sess"); if (s) document.getElementById("chat-side").innerHTML = sideList(); });
  } catch (x) { toast({ text: x.message, kind: "err" }); }
}

function follow(tid) {
  run = { tid, text: "", tools: [], after: 0, stop: false };
  shell();
  const my = run;
  const tick = async () => {
    if (run !== my) return;
    let r;
    try { r = await get(`/api/chat/turns/${tid}?after=${my.after}`); } catch (e) { setTimeout(tick, 2500); return; }
    for (const ev of r.events) {
      my.after = ev.id;
      if (ev.type === "delta") my.text += ev.text || "";
      else if (ev.type === "tool") { const t = my.tools.find((x) => x.name === ev.name && x.status === "start"); if (ev.status === "end" && t) t.status = "end"; else if (ev.status === "start") my.tools.push({ name: ev.name, status: "start" }); }
    }
    if (r.status === "done" || r.status === "error") {
      run = null;
      const t = cur && cur.turns.find((x) => x.id === tid);
      if (t) { t.status = r.status; t.answer = r.answer; t.error = r.error; }
      repaint(); shellButtons(); loadSessions().then(() => { const s = document.getElementById("chat-side"); if (s) s.innerHTML = sideList(); });
      return;
    }
    const live = document.getElementById("live");
    const stickIt = nearBottom();
    if (live) live.outerHTML = liveBubble(); else repaint();
    if (stickIt) stick();
    setTimeout(tick, 700);
  };
  tick();
}

function shellButtons() { shell(); }

export function init() {
  root().addEventListener("click", async (e) => {
    const b = e.target.closest("button");
    if (!b) return;
    if (b.id === "ch-new") newSession();
    else if (b.id === "ch-toggle") { sideOpen = !sideOpen; document.querySelector(".chat").classList.toggle("side-open", sideOpen); }
    else if (b.dataset.open) openSession(Number(b.dataset.open));
    else if (b.dataset.suggest) send(b.dataset.suggest);
    else if (b.id === "ch-stop" && run) { setBusy(b, true); try { await post(`/api/chat/turns/${run.tid}/cancel`); } catch (x) { /* ignorar */ } }
    else if (b.dataset.del) {
      if (await confirmDialog({ title: "Borrar conversación", body: "Se elimina el historial de esta conversación.", confirm: "Borrar", danger: true })) {
        try { await del(`/api/chat/sessions/${b.dataset.del}`); if (cur && cur.id === Number(b.dataset.del)) { cur = null; run = null; } await loadSessions(); shell(); } catch (x) { toast({ text: x.message, kind: "err" }); }
      }
    }
  });
  root().addEventListener("submit", (e) => { e.preventDefault(); const ta = document.getElementById("ch-input"); const v = ta.value; send(v); });
  setInterval(() => { if (!document.hidden && root() && !root().hidden) status(); }, 15000);
}

export async function show() {
  try { await loadSessions(); await status(); if (!run) { if (cur) { await openSession(cur.id); } else shell(); } else shell(); }
  catch (e) { root().innerHTML = `<div class="empty">${icon("warning")}<p>No se pudo cargar el chat.</p></div>`; }
}
