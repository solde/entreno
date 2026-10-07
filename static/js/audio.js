let ctx = null;
export function unlock() {
  try { ctx = ctx || new (window.AudioContext || window.webkitAudioContext)(); if (ctx.state === "suspended") ctx.resume(); } catch (e) { /* sin audio */ }
}
export function beep({ freq = 880, ms = 140, vol = 0.18 } = {}) {
  if (!ctx) return;
  try {
    const o = ctx.createOscillator(), g = ctx.createGain();
    o.type = "sine"; o.frequency.value = freq;
    g.gain.setValueAtTime(vol, ctx.currentTime); g.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + ms / 1000);
    o.connect(g).connect(ctx.destination); o.start(); o.stop(ctx.currentTime + ms / 1000 + 0.02);
  } catch (e) { /* ignorar */ }
}
export const vibrate = (p) => { try { navigator.vibrate && navigator.vibrate(p); } catch (e) { /* ignorar */ } };
let lock = null;
export async function wake(on) {
  try {
    if (on && "wakeLock" in navigator && !lock) { lock = await navigator.wakeLock.request("screen"); lock.addEventListener("release", () => { lock = null; }); }
    else if (!on && lock) { await lock.release(); lock = null; }
  } catch (e) { /* no disponible */ }
}
