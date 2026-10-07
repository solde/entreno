import { get, post } from "../api.js";
import { esc, icon } from "../fmt.js";
import { toast, openDialog } from "../ui.js";
import { MUSCLE, lab, exName } from "../labels.js";
import { human, mmss, num, km, dateShort, dateLong, isoDay } from "../util.js";

const root = () => document.getElementById("view-dashboard");
let st = null, mode = "sessions";

function bars(weeks, key, fmt) {
  const max = Math.max(1, ...weeks.map((w) => w[key]));
  return `<div class="bars" role="img" aria-label="Por semana">${weeks.map((w, i) => `<div class="bar-col ${i === weeks.length - 1 ? "cur" : ""}" title="${isoDay(w.week)}: ${esc(fmt(w[key]))}"><i style="height:${Math.max(2, (w[key] / max) * 100)}%"></i><small>${i % 2 === (weeks.length - 1) % 2 ? isoDay(w.week).replace(/\s.*/, "") : ""}</small></div>`).join("")}</div>`;
}

function kpi(label, value, sub, ic) { return `<div class="glass tile kpi"><div class="tile-head">${icon(ic)}<span>${esc(label)}</span></div><div class="tile-value">${value}</div><div class="tile-sub">${sub}</div></div>`; }

function render() {
  const u = st.units, tw = st.this_week, lw = st.last_week;
  const delta = (a, b) => (b ? `${a >= b ? "▲" : "▼"} ${Math.abs(Math.round(((a - b) / b) * 100))} % vs. semana pasada` : "");
  const modes = { sessions: ["Sesiones", (v) => `${v}`], time_s: ["Tiempo", (v) => human(v)], volume: [`Volumen (${u})`, (v) => num(v)], cardio_s: ["Cardio", (v) => human(v)] };
  const maxMus = Math.max(1, ...st.muscles.map((m) => m.sets));
  const t = st.today;
  root().innerHTML = `<header class="view-head"><div><h1 id="h-dashboard">Panel de entrenamiento</h1><p class="muted">Tu actividad, progreso y los ajustes del asistente.</p></div>
      <div class="head-actions"><button class="btn" type="button" data-act="eval">${icon("sparkle")}Evaluar y ajustar con IA</button><a class="btn primary" href="#/train">${icon("play")}Entrenar</a></div></header>
    ${t ? `<div class="glass card today-card"><div><span class="badge info">Hoy toca</span><h2>${esc(t.name)}</h2><p class="muted small">${t.items} ejercicios${t.done_today ? " · ya has entrenado hoy" : ""}</p></div><a class="btn primary" href="#/train?routine=${t.id}">${icon("play")}Empezar</a></div>` : ""}
    <div class="tiles kpis">${kpi("Esta semana", `${tw.sessions}<small> / ${st.target_days}</small>`, delta(tw.sessions, lw.sessions) || "sesiones", "calendar")}
      ${kpi("Tiempo semanal", human(tw.time_s), delta(tw.time_s, lw.time_s) || "entrenando", "timer")}
      ${kpi("Volumen semanal", `${num(tw.volume)}<small> ${esc(u)}</small>`, delta(tw.volume, lw.volume) || "peso × repeticiones", "barbell")}
      ${kpi("Racha", `${st.streak_days}<small> ${st.streak_days === 1 ? "día" : "días"}</small>`, `${st.total_sessions} entrenamientos en total · ${human(st.total_time_s)}`, "fire")}</div>
    <div class="dash-grid"><section class="glass card"><div class="row-between"><h3>Últimas 12 semanas</h3><div class="seg" role="group">${Object.entries(modes).map(([k, [l]]) => `<button type="button" data-mode="${k}" aria-pressed="${mode === k}">${l}</button>`).join("")}</div></div>
        ${bars(st.weeks, mode, modes[mode][1])}<p class="muted small">Media últimas 4 semanas: ${st.avg_per_week_4} sesiones/semana (objetivo ${st.target_days}). ${tw.distance_m ? `Cardio esta semana: ${km(tw.distance_m)}.` : ""}</p></section>
      <section class="glass card"><h3>Músculos trabajados <small class="muted">(series, 4 semanas)</small></h3>${st.muscles.length ? st.muscles.slice(0, 10).map((m) => `<div class="hbar"><span>${esc(lab(MUSCLE, m.muscle))}</span><div><i style="width:${(m.sets / maxMus) * 100}%"></i></div><b>${num(m.sets, 1)}</b></div>`).join("") : `<p class="muted">Aún sin datos.</p>`}</section>
      <section class="glass card"><h3>Récords personales</h3>${st.prs.length ? `<ul class="plain">${st.prs.map((p) => `<li><b>${esc(p.name)}</b><span>${num(p.weight, 2)} ${esc(u)} × ${p.reps} <small class="muted">· 1RM ≈ ${num(p.e1rm, 1)} · ${isoDay(p.date)}</small></span></li>`).join("")}</ul>` : `<p class="muted">Registra series con peso para ver tus marcas.</p>`}</section>
      <section class="glass card"><h3>Entrenamientos recientes</h3>${st.recent.length ? `<ul class="plain">${st.recent.map((s) => `<li><button class="link" type="button" data-sess="${s.id}"><b>${esc(s.routine_name || "Libre")}</b><span>${dateShort(s.started)} · ${human(s.total_s)} · ${s.sets_done} series${s.rating ? ` · ${"★".repeat(s.rating)}` : ""}</span></button></li>`).join("")}</ul>` : `<p class="muted">Todavía no hay entrenamientos.</p>`}</section>
      <section class="glass card wide"><h3>Ajustes del asistente a tus rutinas</h3>${st.adjustments.length ? `<ul class="plain">${st.adjustments.map((a) => `<li><span><b>${esc(a.routine)}</b> <small class="muted">${new Date(a.created * 1000).toLocaleDateString("es")}</small><br><span class="small">${esc(a.reason)}</span></span><a class="btn sm" href="#/routines">Historial</a></li>`).join("")}</ul>` : `<p class="muted">El asistente aún no ha modificado ninguna rutina. Activa el ajuste automático en Ajustes o pulsa «Evaluar y ajustar con IA».</p>`}</section></div>`;
}

async function sessionDialog(id) {
  const s = await get(`/api/sessions/${id}`);
  const by = {};
  s.sets.forEach((x) => { (by[x.position] = by[x.position] || []).push(x); });
  const names = (p) => { const it = s.plan[p]; return it ? exName(it) : "Ejercicio"; };
  openDialog(`<h3>${esc(s.routine_name || "Entrenamiento libre")}</h3><p class="muted small">${esc(dateLong(s.started))} · ${human(s.total_s)}${s.rating ? ` · ${"★".repeat(s.rating)}` : ""}</p>${s.notes ? `<p>${esc(s.notes)}</p>` : ""}
    ${Object.entries(by).map(([p, sets]) => `<h4>${esc(names(Number(p)))}</h4><div class="chips">${sets.map((x) => `<span class="chip">${x.weight ? `${num(x.weight, 2)}×${x.reps}` : x.reps != null ? `${x.reps} reps` : mmss(x.duration_s)}${x.distance_m ? ` · ${km(x.distance_m)}` : ""}${x.rpe ? ` · RPE ${x.rpe}` : ""}${x.rest_s != null ? ` · desc. ${x.rest_s}s` : ""}</span>`).join("")}</div>`).join("") || `<p class="muted">Sin series registradas.</p>`}
    <div class="dialog-actions"><button class="btn danger" type="button" id="sd-del">${icon("trash")}Borrar</button><span class="spacer"></span><button class="btn" data-close type="button">Cerrar</button></div>`, { cls: "wide" }).el
    .querySelector("#sd-del").addEventListener("click", async () => { const { del } = await import("../api.js"); await del(`/api/sessions/${id}`); document.getElementById("dialog").close(); show(); });
}

export function init() {
  root().addEventListener("click", async (e) => {
    const b = e.target.closest("[data-mode],[data-sess],[data-act]");
    if (!b) return;
    if (b.dataset.mode) { mode = b.dataset.mode; render(); }
    else if (b.dataset.sess) sessionDialog(Number(b.dataset.sess));
    else if (b.dataset.act === "eval") { try { await post("/api/eval", { routine_id: null }); toast({ text: "Evaluación enviada. El asistente revisará tus últimos entrenamientos y ajustará las rutinas.", kind: "ok", timeout: 5000 }); } catch (x) { toast({ text: x.message, kind: "err" }); } }
  });
}
export async function show() {
  try { st = await get("/api/stats?weeks=12"); render(); }
  catch (e) { root().innerHTML = `<div class="empty">${icon("warning")}<p>No se pudo cargar el panel.</p></div>`; }
}
