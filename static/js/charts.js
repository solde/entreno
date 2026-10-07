import { esc } from "./fmt.js";
import { dateTime } from "./i18n.js";

const NS = "http://www.w3.org/2000/svg";

function bounds(series, yMax) {
  let max = 0;
  let tMin = Infinity, tMax = -Infinity;
  for (const s of series) {
    for (const [ts, v] of s.data || []) {
      if (v > max) max = v;
      if (ts < tMin) tMin = ts;
      if (ts > tMax) tMax = ts;
    }
  }
  if (yMax != null) max = yMax;
  else max = max > 0 ? max * 1.15 : 1;
  return { max, tMin, tMax };
}

function path(data, x, y) {
  let d = "";
  let gap = true;
  let prevTs = null;
  const step = data.length > 1 ? (data[data.length - 1][0] - data[0][0]) / (data.length - 1) : 0;
  for (const [ts, v] of data) {
    if (prevTs != null && ts - prevTs > step * 3) gap = true;
    d += `${gap ? "M" : "L"}${x(ts).toFixed(1)} ${y(v).toFixed(1)}`;
    gap = false;
    prevTs = ts;
  }
  return d;
}

export function spark(data, { w = 140, h = 40, cls = "" } = {}) {
  if (!data || data.length < 2) return `<svg class="spark ${cls}" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" aria-hidden="true"></svg>`;
  const { max, tMin, tMax } = bounds([{ data }]);
  const x = (ts) => ((ts - tMin) / (tMax - tMin || 1)) * w;
  const y = (v) => h - 2 - (v / max) * (h - 4);
  const line = path(data, x, y);
  const area = `${line}L${w} ${h}L0 ${h}Z`;
  return `<svg class="spark ${cls}" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" aria-hidden="true"><path class="spark-area" d="${area}"/><path class="spark-line" d="${line}"/></svg>`;
}

export function lineChart(el, { series, fmt, yMax = null, height = 150, emptyText = "", fmtAxisT = null, fmtTipT = null }) {
  const render = () => {
    const w = Math.max(240, el.clientWidth || 320);
    const padL = 46, padR = 8, padT = 8, padB = 20;
    const h = height;
    const pw = w - padL - padR, ph = h - padT - padB;
    const { max, tMin, tMax } = bounds(series, yMax);
    const has = series.some((s) => s.data && s.data.length > 1);
    const x = (ts) => padL + ((ts - tMin) / (tMax - tMin || 1)) * pw;
    const y = (v) => padT + ph - (Math.min(v, max) / max) * ph;
    let svg = `<svg viewBox="0 0 ${w} ${h}" width="${w}" height="${h}" role="img" aria-label="${esc(series.map((s) => s.label).join(", "))}">`;
    for (let i = 0; i <= 3; i++) {
      const v = (max * i) / 3, yy = y(v);
      svg += `<line class="grid" x1="${padL}" x2="${w - padR}" y1="${yy}" y2="${yy}"/><text class="axis" x="${padL - 6}" y="${yy + 3.5}" text-anchor="end">${esc(fmt(v))}</text>`;
    }
    if (has) {
      const fmtT = fmtAxisT || ((ts) => dateTime(ts, tMax - tMin > 86400 * 1.5 ? { month: "short", day: "numeric", hour: "2-digit" } : { hour: "2-digit", minute: "2-digit" }));
      svg += `<text class="axis" x="${padL}" y="${h - 4}">${esc(fmtT(tMin))}</text><text class="axis" x="${w - padR}" y="${h - 4}" text-anchor="end">${esc(fmtT(tMax))}</text>`;
      series.forEach((s, i) => {
        if (!s.data || s.data.length < 2) return;
        const line = path(s.data, x, y);
        svg += `<path class="area c${i}" d="${line}L${x(s.data[s.data.length - 1][0])} ${padT + ph}L${x(s.data[0][0])} ${padT + ph}Z"/><path class="line c${i}" d="${line}"/>`;
      });
      svg += `<line class="cursor" x1="0" x2="0" y1="${padT}" y2="${padT + ph}" visibility="hidden"/>`;
    } else {
      svg += `<text class="axis" x="${w / 2}" y="${h / 2}" text-anchor="middle">${esc(emptyText)}</text>`;
    }
    svg += "</svg><div class='tip' hidden></div>";
    el.innerHTML = svg;
    if (!has) return;
    const svgEl = el.querySelector("svg"), cursor = el.querySelector(".cursor"), tip = el.querySelector(".tip");
    const move = (ev) => {
      const r = svgEl.getBoundingClientRect();
      const px = ((ev.clientX - r.left) / r.width) * w;
      const ts = tMin + ((px - padL) / pw) * (tMax - tMin);
      if (ts < tMin || ts > tMax) return leave();
      cursor.setAttribute("x1", px); cursor.setAttribute("x2", px); cursor.setAttribute("visibility", "visible");
      const rows = series.map((s, i) => {
        if (!s.data || !s.data.length) return "";
        let best = s.data[0];
        for (const p of s.data) if (Math.abs(p[0] - ts) < Math.abs(best[0] - ts)) best = p;
        return `<div><i class="dot c${i}"></i>${esc(s.label)}: <b>${esc(fmt(best[1]))}</b></div>`;
      }).join("");
      tip.innerHTML = `<small>${esc(fmtTipT ? fmtTipT(ts) : dateTime(ts, { dateStyle: "short", timeStyle: "medium" }))}</small>${rows}`;
      tip.hidden = false;
      const tw = tip.offsetWidth;
      let left = (px / w) * r.width + 12;
      if (left + tw > r.width) left = (px / w) * r.width - tw - 12;
      tip.style.transform = `translate(${Math.max(0, left)}px, 4px)`;
    };
    const leave = () => { cursor.setAttribute("visibility", "hidden"); tip.hidden = true; };
    svgEl.addEventListener("pointermove", move);
    svgEl.addEventListener("pointerleave", leave);
  };
  render();
  if (el._ro) el._ro.disconnect();
  let lastW = el.clientWidth;
  el._ro = new ResizeObserver(() => { if (Math.abs(el.clientWidth - lastW) > 4) { lastW = el.clientWidth; render(); } });
  el._ro.observe(el);
}

export { NS };
