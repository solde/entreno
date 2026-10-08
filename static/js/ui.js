import { t } from "./i18n.js";
import { esc, icon } from "./fmt.js";

const toasts = () => document.getElementById("toasts");

export function toast({ text, kind = "info", undo = null, timeout = 6000 }) {
  const el = document.createElement("div");
  el.className = `toast glass ${kind}`;
  const ic = kind === "ok" ? "ok" : kind === "err" ? "fail" : kind === "warn" ? "warning" : "info";
  el.innerHTML = `${icon(ic)}<span class="toast-text">${esc(text)}</span>`;
  const close = () => {
    el.classList.add("out");
    setTimeout(() => el.remove(), 220);
  };
  if (undo) {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "toast-btn";
    b.innerHTML = `${icon("undo")}${esc(t("common.undo"))}`;
    b.addEventListener("click", () => { close(); undo(); });
    el.append(b);
  }
  const x = document.createElement("button");
  x.type = "button";
  x.className = "icon-btn sm";
  x.setAttribute("aria-label", t("common.close"));
  x.innerHTML = icon("x");
  x.addEventListener("click", close);
  el.append(x);
  toasts().append(el);
  while (toasts().children.length > 4) toasts().firstChild.remove();
  if (timeout) setTimeout(close, timeout);
  return close;
}

export function openDialog(html, { onClose, cls = "" } = {}) {
  const d = document.getElementById("dialog");
  // Un diálogo que sustituye a otro (cerrar + abrir seguidos) recibe el evento "close" del anterior con retraso:
  // solo se atiende un cierre real, es decir, con el diálogo ya cerrado.
  if (d._onClose) { d.removeEventListener("close", d._onClose); d._onClose = null; }
  d.className = `glass dialog ${cls}`;
  d.innerHTML = html;
  const close = () => { if (d.open) d.close(); };
  d.querySelectorAll("[data-close]").forEach((b) => b.addEventListener("click", close));
  d.onclick = (e) => { if (e.target === d) close(); };
  const handler = () => { if (d.open) return; d.removeEventListener("close", handler); d._onClose = null; if (onClose) onClose(); };
  d._onClose = handler;
  d.addEventListener("close", handler);
  if (!d.open) d.showModal();
  return { el: d, close };
}

export function confirmDialog({ title, body, confirm, danger = false }) {
  return new Promise((resolve) => {
    let result = false;
    const { el } = openDialog(
      `<h3>${esc(title)}</h3><p class="muted">${esc(body)}</p>
       <div class="dialog-actions"><button class="btn" data-close type="button">${esc(t("common.cancel"))}</button>
       <button class="btn ${danger ? "danger" : "primary"}" id="dlg-ok" type="button">${esc(confirm)}</button></div>`,
      { onClose: () => resolve(result) },
    );
    el.querySelector("#dlg-ok").addEventListener("click", () => { result = true; el.close(); });
    el.querySelector("#dlg-ok").focus();
  });
}

export function menu(button, panel, onPick) {
  const close = () => { panel.hidden = true; button.setAttribute("aria-expanded", "false"); };
  button.addEventListener("click", (e) => {
    e.stopPropagation();
    const open = panel.hidden;
    document.querySelectorAll(".menu").forEach((m) => (m.hidden = true));
    panel.hidden = !open;
    button.setAttribute("aria-expanded", String(open));
    if (open) (panel.querySelector('[aria-checked="true"]') || panel.querySelector("button")).focus();
  });
  panel.addEventListener("click", (e) => {
    const b = e.target.closest("button");
    if (b) { close(); onPick(b); button.focus(); }
  });
  panel.addEventListener("keydown", (e) => {
    const items = [...panel.querySelectorAll("button")];
    const i = items.indexOf(document.activeElement);
    if (e.key === "ArrowDown") { items[(i + 1) % items.length].focus(); e.preventDefault(); }
    if (e.key === "ArrowUp") { items[(i - 1 + items.length) % items.length].focus(); e.preventDefault(); }
    if (e.key === "Escape") { close(); button.focus(); }
  });
  document.addEventListener("click", close);
}

export function setBusy(btn, busy) {
  btn.disabled = busy;
  btn.classList.toggle("busy", busy);
}

export async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch (e) {
    const ta = document.createElement("textarea");
    ta.value = text; ta.style.position = "fixed"; ta.style.opacity = "0";
    document.body.append(ta); ta.select();
    let ok = false;
    try { ok = document.execCommand("copy"); } catch (err) { /* nada */ }
    ta.remove();
    return ok;
  }
}
