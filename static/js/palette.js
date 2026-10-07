import { t } from "./i18n.js";
import { esc, icon } from "./fmt.js";

let commands = () => [];
let selected = 0;
let shown = [];

const norm = (s) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

export function setCommands(fn) { commands = fn; }

function draw(query) {
  const q = norm(query).split(/\s+/).filter(Boolean);
  const all = commands();
  shown = all.filter((c) => q.every((w) => norm(`${c.label} ${c.group} ${c.keywords || ""}`).includes(w)));
  selected = Math.min(selected, Math.max(0, shown.length - 1));
  const list = document.getElementById("pal-list");
  if (!shown.length) { list.innerHTML = `<li class="pal-empty">${esc(t("palette.none"))}</li>`; return; }
  let group = null;
  list.innerHTML = shown.map((c, i) => {
    const head = c.group !== group ? `<li class="pal-group" role="presentation">${esc(c.group)}</li>` : "";
    group = c.group;
    return `${head}<li role="option" id="pal-${i}" data-i="${i}" aria-selected="${i === selected}" class="pal-item">${icon(c.icon || "command")}<span>${esc(c.label)}</span>${c.hint ? `<kbd>${esc(c.hint)}</kbd>` : ""}</li>`;
  }).join("");
  const cur = document.getElementById(`pal-${selected}`);
  if (cur) cur.scrollIntoView({ block: "nearest" });
  document.getElementById("pal-input").setAttribute("aria-activedescendant", `pal-${selected}`);
}

function run(i) {
  const c = shown[i];
  if (!c) return;
  document.getElementById("palette").close();
  setTimeout(() => c.run(), 30);
}

export function openPalette() {
  const d = document.getElementById("palette");
  if (d.open) return;
  d.innerHTML = `<div class="pal-box">
    <div class="pal-search">${icon("search")}<input id="pal-input" type="text" role="combobox" aria-expanded="true" aria-controls="pal-list" aria-autocomplete="list" autocomplete="off" spellcheck="false" placeholder="${esc(t("palette.placeholder"))}"><kbd>Esc</kbd></div>
    <ul id="pal-list" role="listbox" aria-label="${esc(t("palette.title"))}"></ul>
    <div class="pal-foot"><span><kbd>↑</kbd><kbd>↓</kbd> ${esc(t("palette.navigate"))}</span><span><kbd>↵</kbd> ${esc(t("palette.run"))}</span><span><kbd>?</kbd> ${esc(t("shortcuts.title"))}</span></div>
  </div>`;
  selected = 0;
  const input = d.querySelector("#pal-input");
  draw("");
  input.addEventListener("input", () => { selected = 0; draw(input.value); });
  input.addEventListener("keydown", (e) => {
    if (e.key === "ArrowDown") { selected = Math.min(shown.length - 1, selected + 1); draw(input.value); e.preventDefault(); }
    else if (e.key === "ArrowUp") { selected = Math.max(0, selected - 1); draw(input.value); e.preventDefault(); }
    else if (e.key === "Enter") { run(selected); e.preventDefault(); }
  });
  d.querySelector("#pal-list").addEventListener("click", (e) => {
    const li = e.target.closest("[data-i]");
    if (li) run(Number(li.dataset.i));
  });
  d.addEventListener("click", (e) => { if (e.target === d) d.close(); }, { once: true });
  d.showModal();
  input.focus();
}
