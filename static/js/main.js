import { t } from "./i18n.js";
import { session, post, get, onOffline } from "./api.js";
import { loginUrl } from "./base.js";
import { openDialog } from "./ui.js";
import { esc } from "./fmt.js";
import { openPalette, setCommands } from "./palette.js";
import { mmss } from "./util.js";
import * as dashboard from "./views/dashboard.js";
import * as routines from "./views/routines.js";
import * as train from "./views/train.js";
import * as exercises from "./views/exercises.js";
import * as chat from "./views/chat.js";
import * as settings from "./views/settings.js";

const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const VIEWS = { dashboard, routines, train, exercises, chat, settings };
const ORDER = ["dashboard", "routines", "train", "exercises", "chat", "settings"];
const isMac = /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent);
const MOD = isMac ? "⌘" : "Ctrl+";
let current = null, live = null, liveTimer = null;

function openDrawer() { $("#sidebar").classList.add("open"); $("#scrim").hidden = false; }
function closeDrawer() { $("#sidebar").classList.remove("open"); $("#scrim").hidden = true; }

function route() {
  const m = location.hash.match(/^#\/(\w+)/);
  const id = m && VIEWS[m[1]] ? m[1] : "dashboard";
  $$(".view").forEach((v) => (v.hidden = v.dataset.view !== id));
  $$("[data-nav]").forEach((a) => (a.dataset.nav === id ? a.setAttribute("aria-current", "true") : a.removeAttribute("aria-current")));
  document.body.dataset.view = id;
  closeDrawer();
  if (current !== id) { if (current === "train") train.stop(); current = id; window.scrollTo(0, 0); }
  VIEWS[id].show();
  syncLive();
}
const goTo = (id) => { if (location.hash === `#/${id}`) route(); else location.hash = `#/${id}`; };

const THEMES = ["auto", "light", "dark"];
const themePref = () => document.documentElement.dataset.themePref || "auto";
function syncTheme() { $$("#theme-seg button").forEach((b) => b.setAttribute("aria-checked", String(b.dataset.themePref === themePref()))); }
function setTheme(p) { window.__prefs.setTheme(p); syncTheme(); }
function syncDensity() {
  const compact = document.documentElement.dataset.density === "compact";
  $("#btn-density").setAttribute("aria-pressed", String(compact));
  $("#btn-density span").textContent = t(compact ? "density.compact" : "density.comfortable");
}
function toggleDensity() { window.__prefs.setDensity(document.documentElement.dataset.density === "compact" ? "comfortable" : "compact"); syncDensity(); }
async function logout() { try { await post("/api/logout"); } catch (e) { /* ignorar */ } location.href = loginUrl(); }

/* Banner "entrenamiento en curso" visible en todas las pantallas menos en Entrenar */
async function refreshLive() { try { live = await get("/api/sessions/active"); } catch (e) { /* ignorar */ } syncLive(); }
function syncLive() {
  const b = $("#live-banner");
  const show = !!live && current !== "train";
  b.hidden = !show;
  clearInterval(liveTimer);
  if (show) { const tick = () => ($("#live-clock").textContent = mmss(Date.now() / 1000 - live.started)); tick(); liveTimer = setInterval(tick, 1000); }
}

async function refreshAll() { if (current) VIEWS[current].show(); }

function buildCommands() {
  const g = (k) => t(`palette.g_${k}`);
  const icons = { dashboard: "pulse", routines: "checks", train: "barbell", exercises: "search", chat: "chat", settings: "gear" };
  const cmds = ORDER.map((id, i) => ({ group: g("go"), label: t(`nav.${id}`), icon: icons[id], hint: String(i + 1), run: () => goTo(id), keywords: "ir go" }));
  cmds.push({ group: g("actions"), label: "Empezar un entrenamiento", icon: "play", run: () => goTo("train") });
  cmds.push({ group: g("actions"), label: "Nueva rutina", icon: "plus", run: () => { goTo("routines"); setTimeout(() => $('[data-act="new"]')?.click(), 300); } });
  cmds.push({ group: g("actions"), label: "Nueva conversación con el asistente", icon: "chat", run: () => { goTo("chat"); setTimeout(() => $("#ch-new")?.click(), 250); } });
  ["auto", "light", "dark"].forEach((m) => cmds.push({ group: g("appearance"), label: t(`theme.${m}`), icon: { auto: "auto", light: "sun", dark: "moon" }[m], run: () => setTheme(m), keywords: "tema theme" }));
  cmds.push({ group: g("appearance"), label: t("density.toggle"), icon: "density", hint: "D", run: toggleDensity });
  cmds.push({ group: g("system"), label: t("palette.refresh"), icon: "refresh", hint: "R", run: refreshAll });
  cmds.push({ group: g("system"), label: t("shortcuts.title"), icon: "command", hint: "?", run: showShortcuts });
  cmds.push({ group: g("system"), label: t("auth.logout"), icon: "logout", run: logout });
  return cmds;
}

function showShortcuts() {
  const rows = [[`${MOD}K`, t("palette.open")], ["/", t("palette.open")], ["1–6", t("shortcuts.jump")], ["T", t("shortcuts.theme")], ["D", t("density.toggle")], ["R", t("palette.refresh")], ["?", t("shortcuts.title")]];
  openDialog(`<h3>${esc(t("shortcuts.title"))}</h3><dl class="shortcuts">${rows.map(([k, d]) => `<div><dt><kbd>${esc(k)}</kbd></dt><dd>${esc(d)}</dd></div>`).join("")}</dl>
    <div class="dialog-actions"><button class="btn primary" data-close type="button">${esc(t("common.done"))}</button></div>`);
}

function initShortcuts() {
  document.addEventListener("keydown", (e) => {
    const typing = /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement.tagName) || document.activeElement.isContentEditable;
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); openPalette(); return; }
    if (typing || e.metaKey || e.ctrlKey || e.altKey || document.querySelector("dialog[open]")) return;
    const k = e.key;
    if (k === "/") { e.preventDefault(); openPalette(); }
    else if (k === "?") showShortcuts();
    else if (/^[1-6]$/.test(k)) goTo(ORDER[Number(k) - 1]);
    else if (k === "t") setTheme(THEMES[(THEMES.indexOf(themePref()) + 1) % 3]);
    else if (k === "d") toggleDensity();
    else if (k === "r") refreshAll();
  });
}

async function boot() {
  $("#kbd-hint").textContent = `${MOD}K`;
  $("#btn-sidebar").addEventListener("click", openDrawer);
  $("#scrim").addEventListener("click", closeDrawer);
  $("#btn-palette").addEventListener("click", openPalette);
  $("#btn-density").addEventListener("click", () => { toggleDensity(); closeDrawer(); });
  $$("#theme-seg button").forEach((b) => b.addEventListener("click", () => setTheme(b.dataset.themePref)));
  $("#btn-logout").addEventListener("click", logout);
  syncTheme(); syncDensity();
  setCommands(buildCommands);
  initShortcuts();
  onOffline((off) => ($("#banner-offline").hidden = !off));
  await session();
  Object.values(VIEWS).forEach((v) => v.init());
  window.addEventListener("hashchange", route);
  window.addEventListener("training:session", refreshLive);
  await refreshLive();
  route();
  setInterval(() => { if (!document.hidden) refreshLive(); }, 60000);
}

boot().catch((e) => console.error(e));
