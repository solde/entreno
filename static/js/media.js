import { esc, icon } from "./fmt.js";
import { exName } from "./labels.js";

/** Imagen/vídeo de referencia. Dos fotogramas de la biblioteca se animan (inicio/fin); las imágenes propias forman una galería. */
export function mediaView(ex, { cls = "" } = {}) {
  const m = ex.media || [];
  if (!m.length) return `<div class="media no-media ${cls}">${icon("image")}<span>Sin imagen ni vídeo</span><small>Puedes subir los tuyos desde «Imágenes y vídeos»</small></div>`;
  if (m.length === 1 || m.some((x) => x.own)) {
    const main = m[0];
    const big = main.kind === "video" ? `<video class="g-main" controls playsinline preload="metadata" src="${esc(main.url)}"></video>` : `<img class="g-main" src="${esc(main.url)}" alt="${esc(exName(ex))}" loading="lazy">`;
    const th = m.length > 1 ? `<div class="g-thumbs">${m.map((x, i) => `<button type="button" data-g="${i}" class="${i === 0 ? "on" : ""}" aria-label="Medio ${i + 1}">${x.kind === "video" ? icon("video") : `<img src="${esc(x.url)}" alt="" loading="lazy">`}</button>`).join("")}</div>` : "";
    return `<div class="media gallery ${cls}" data-media='${esc(JSON.stringify(m.map((x) => [x.url, x.kind])))}'>${big}${th}</div>`;
  }
  return `<div class="media anim ${cls}" role="img" aria-label="${esc(exName(ex))}">${m.slice(0, 2).map((x, i) => `<img class="f${i}" src="${esc(x.url)}" alt="" loading="lazy">`).join("")}</div>`;
}

export function thumb(ex, size = "") {
  const m = (ex.media || []).find((x) => x.kind === "image") || null;
  const url = m ? m.url : ex.thumb;
  return `<span class="thumb ${size}">${url ? `<img src="${esc(url)}" alt="" loading="lazy">` : icon(ex.tracking === "cardio" || ex.category === "cardio" ? "heartbeat" : "barbell")}</span>`;
}

document.addEventListener("click", (e) => {
  const b = e.target.closest(".gallery [data-g]");
  if (!b) return;
  const g = b.closest(".gallery");
  const [url, kind] = JSON.parse(g.dataset.media)[Number(b.dataset.g)];
  const old = g.querySelector(".g-main");
  const el = document.createElement(kind === "video" ? "video" : "img");
  el.className = "g-main"; el.src = url;
  if (kind === "video") { el.controls = true; el.playsInline = true; el.preload = "metadata"; } else el.alt = "";
  old.replaceWith(el);
  g.querySelectorAll("[data-g]").forEach((x) => x.classList.toggle("on", x === b));
});
