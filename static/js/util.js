import { numberFmt } from "./i18n.js";

export const mmss = (s) => { s = Math.max(0, Math.round(s || 0)); const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), x = s % 60; return (h ? `${h}:${String(m).padStart(2, "0")}` : String(m)) + `:${String(x).padStart(2, "0")}`; };
export const human = (s) => { s = Math.round(s || 0); if (s < 60) return `${s} s`; const h = Math.floor(s / 3600), m = Math.round((s % 3600) / 60); return h ? `${h} h ${m ? m + " min" : ""}`.trim() : `${m} min`; };
export const num = (n, d = 0) => (n == null || isNaN(n) ? "—" : numberFmt(n, { maximumFractionDigits: d }));
export const km = (m) => (m ? `${numberFmt(m / 1000, { maximumFractionDigits: 2 })} km` : "—");
export const dateShort = (ts) => new Intl.DateTimeFormat("es", { day: "numeric", month: "short" }).format(new Date(ts * 1000));
export const dateLong = (ts) => new Intl.DateTimeFormat("es", { weekday: "long", day: "numeric", month: "long", hour: "2-digit", minute: "2-digit" }).format(new Date(ts * 1000));
export const isoDay = (iso) => { const [y, m, d] = iso.split("-").map(Number); return new Intl.DateTimeFormat("es", { day: "numeric", month: "short" }).format(new Date(y, m - 1, d)); };
export const ytSearch = (name) => `https://www.youtube.com/results?search_query=${encodeURIComponent(name + " ejercicio técnica")}`;
export function parseMmss(v) {
  v = String(v ?? "").trim();
  if (!v) return null;
  if (/^\d+$/.test(v)) return Number(v);
  const p = v.split(":").map(Number);
  if (p.some((x) => isNaN(x))) return null;
  return p.length === 3 ? p[0] * 3600 + p[1] * 60 + p[2] : p[0] * 60 + p[1];
}
export const parseNum = (v) => { const n = Number(String(v ?? "").replace(",", ".")); return v === "" || v == null || isNaN(n) ? null : n; };
export function targetText(it, units = "kg") {
  if (it.tracking === "reps") {
    const reps = it.reps_min && it.reps_max && it.reps_min !== it.reps_max ? `${it.reps_min}–${it.reps_max}` : `${it.reps_max || it.reps_min || "?"}`;
    return `${it.sets} × ${reps}${it.weight ? ` · ${num(it.weight, 2)} ${units}` : ""}`;
  }
  const t = it.duration_s ? mmss(it.duration_s) : "";
  return `${it.sets > 1 ? it.sets + " × " : ""}${t}${it.distance_m ? ` · ${km(it.distance_m)}` : ""}`.trim();
}
export function estDuration(items) {
  let s = 0;
  for (const it of items) {
    if (it.tracking === "reps") s += it.sets * (40 + (it.rest_s || 0)) + (it.rest_ex_s || 0) - (it.rest_s || 0);
    else s += it.sets * (it.duration_s || 0) + (it.sets - 1) * (it.rest_s || 0) + (it.rest_ex_s || 0);
  }
  return s;
}
