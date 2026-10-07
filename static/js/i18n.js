import { BASE } from "./base.js";

let dict = {};
let lang = document.documentElement.lang || "es";
const listeners = [];
export const LANGS = { es: "Castellano" };

try { dict = JSON.parse(document.getElementById("i18n-data").textContent); } catch (e) { dict = {}; }

export function getLang() { return lang; }
export function onLang(fn) { listeners.push(fn); }

export function t(key, vars) {
  let s = dict[key];
  if (s === undefined) return key;
  if (vars) for (const k in vars) s = s.replaceAll(`{${k}}`, vars[k]);
  return s;
}

export function has(key) { return dict[key] !== undefined; }

export function apply(root = document) {
  root.querySelectorAll("[data-i18n]").forEach((el) => {
    const v = dict[el.dataset.i18n];
    if (v !== undefined) el.textContent = v;
  });
  root.querySelectorAll("[data-i18n-attr]").forEach((el) => {
    el.dataset.i18nAttr.split(";").forEach((pair) => {
      const [attr, key] = pair.split(":");
      if (dict[key] !== undefined) el.setAttribute(attr, dict[key]);
    });
  });
}

export async function setLang(next) {
  if (!(next in LANGS) || next === lang) return;
  const res = await fetch(`${BASE}/static/i18n/${next}.json`, { cache: "no-cache" });
  if (!res.ok) return;
  dict = await res.json();
  lang = next;
  document.documentElement.lang = next;
  document.cookie = `lang=${next}; Path=/; Max-Age=31536000; SameSite=Lax; Secure`;
  apply();
  const code = document.getElementById("lang-code");
  if (code) code.textContent = next.toUpperCase();
  listeners.forEach((fn) => fn(next));
}

export function numberFmt(n, opts) {
  return new Intl.NumberFormat(lang, { useGrouping: "always", ...opts }).format(n);
}

export function dateTime(ts, opts = { dateStyle: "medium", timeStyle: "medium" }) {
  return new Intl.DateTimeFormat(lang, opts).format(new Date(ts * 1000));
}

export function relTime(ts) {
  const diff = ts - Date.now() / 1000;
  const rtf = new Intl.RelativeTimeFormat(lang, { numeric: "auto" });
  const abs = Math.abs(diff);
  if (abs < 60) return rtf.format(Math.round(diff), "second");
  if (abs < 3600) return rtf.format(Math.round(diff / 60), "minute");
  if (abs < 86400) return rtf.format(Math.round(diff / 3600), "hour");
  return rtf.format(Math.round(diff / 86400), "day");
}
