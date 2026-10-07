import { u, loginUrl } from "./base.js";

let csrf = null;

export class ApiError extends Error {
  constructor(status, body) {
    super((body && body.error) || `HTTP ${status}`);
    this.status = status;
    this.body = body || {};
  }
}

export const state = { offline: false };
const offlineListeners = [];
export function onOffline(fn) { offlineListeners.push(fn); }

export async function session() {
  const res = await fetch(u("/api/session"), { credentials: "same-origin" });
  if (res.status === 401) { location.href = loginUrl(); throw new ApiError(401); }
  const data = await res.json();
  csrf = data.csrf;
  return data;
}

export async function request(method, url, body, retry = true) {
  const opts = { method, credentials: "same-origin", headers: { Accept: "application/json" } };
  if (method !== "GET") {
    if (!csrf) await session();
    opts.headers["X-CSRF-Token"] = csrf;
  }
  if (body !== undefined) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  let res;
  try {
    res = await fetch(u(url), opts);
  } catch (e) {
    setOffline(true);
    throw new ApiError(0, { error: "network" });
  }
  setOffline(false);
  if (res.status === 401) { location.href = loginUrl(); throw new ApiError(401); }
  let data = null;
  try { data = await res.json(); } catch (e) { /* sin cuerpo */ }
  if (res.status === 403 && data && data.error === "csrf" && retry) {
    csrf = null;
    await session();
    return request(method, url, body, false);
  }
  if (!res.ok) throw new ApiError(res.status, data);
  return data;
}

function setOffline(v) {
  if (state.offline !== v) { state.offline = v; offlineListeners.forEach((f) => f(v)); }
}

export async function upload(url, form, onProgress) {
  if (!csrf) await session();
  return new Promise((resolve, reject) => {
    const x = new XMLHttpRequest();
    x.open("POST", u(url));
    x.withCredentials = true;
    x.setRequestHeader("X-CSRF-Token", csrf);
    x.setRequestHeader("Accept", "application/json");
    if (onProgress) x.upload.onprogress = (e) => e.lengthComputable && onProgress(e.loaded / e.total);
    x.onload = () => {
      let data = null;
      try { data = JSON.parse(x.responseText); } catch (e) { /* sin cuerpo */ }
      if (x.status === 401) { location.href = loginUrl(); return reject(new ApiError(401)); }
      x.status >= 200 && x.status < 300 ? resolve(data) : reject(new ApiError(x.status, data));
    };
    x.onerror = () => reject(new ApiError(0, { error: "network" }));
    x.send(form);
  });
}

export const get = (u) => request("GET", u);
export const post = (u, b) => request("POST", u, b ?? {});
export const del = (u) => request("DELETE", u);
export const patch = (u, b) => request("PATCH", u, b ?? {});
export const put = (u, b) => request("PUT", u, b ?? {});
