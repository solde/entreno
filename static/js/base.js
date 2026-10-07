const m = document.querySelector('meta[name="base"]');
export const BASE = m ? m.content.replace(/\/$/, "") : "";
export const u = (p) => (p.startsWith("/") ? BASE + p : p);
export const loginUrl = () => "/login?next=" + encodeURIComponent(BASE + "/");
