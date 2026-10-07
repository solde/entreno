import { numberFmt, t } from "./i18n.js";
import { BASE } from "./base.js";

export function bytes(n, digits = 1) {
  if (n == null || isNaN(n)) return "—";
  const units = ["B", "KiB", "MiB", "GiB", "TiB"];
  let i = 0;
  while (Math.abs(n) >= 1024 && i < units.length - 1) { n /= 1024; i++; }
  return `${numberFmt(n, { maximumFractionDigits: i === 0 ? 0 : digits })} ${units[i]}`;
}

export function rate(n) {
  if (n == null || isNaN(n)) return "—";
  return bytes(n) + "/s";
}

export function pct(n, digits = 0) {
  if (n == null || isNaN(n)) return "—";
  return `${numberFmt(n, { maximumFractionDigits: digits })}%`;
}

export function cores(n) {
  if (n == null || isNaN(n)) return "—";
  return n < 0.1 ? `${numberFmt(n * 1000, { maximumFractionDigits: 0 })} m` : `${numberFmt(n, { maximumFractionDigits: 2 })}`;
}

export function duration(sec) {
  if (sec == null || isNaN(sec)) return "—";
  sec = Math.max(0, Math.floor(sec));
  const d = Math.floor(sec / 86400), h = Math.floor((sec % 86400) / 3600), m = Math.floor((sec % 3600) / 60);
  if (d) return `${d} ${t("unit.d")} ${h} ${t("unit.h")}`;
  if (h) return `${h} ${t("unit.h")} ${m} ${t("unit.min")}`;
  return `${m} ${t("unit.min")} ${sec % 60} ${t("unit.s")}`;
}

export function clock(sec) {
  sec = Math.max(0, Math.floor(sec));
  const h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60), s = sec % 60;
  return [h, m, s].map((x) => String(x).padStart(2, "0")).join(":");
}

export function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

export function icon(name, cls = "") {
  return `<svg class="ic ${cls}" aria-hidden="true" focusable="false"><use href="${BASE}/static/icons.svg#i-${name}"/></svg>`;
}

export function last(series) {
  return series && series.length ? series[series.length - 1][1] : null;
}
