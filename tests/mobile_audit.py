"""Auditoria de usabilidad movil: desbordes horizontales y zonas tactiles pequenas. audit(page) -> dict."""
JS = """() => {
 const W = document.documentElement.clientWidth, out = {over: [], small: [], scrollW: document.documentElement.scrollWidth, W};
 const scrolls = (e) => { for (let p = e.parentElement; p && p !== document.body; p = p.parentElement) { const o = getComputedStyle(p).overflowX; if (o === 'auto' || o === 'scroll' || o === 'hidden') return true; } return false; };
 document.querySelectorAll('body *').forEach(e => {
  const r = e.getBoundingClientRect(); if (!r.width || !r.height) return;
  const cs = getComputedStyle(e); if (cs.visibility === 'hidden' || cs.display === 'none' || e.closest('[hidden]')) return;
  const tag = e.tagName.toLowerCase();
  const sel = tag + (e.id ? '#' + e.id : '') + (typeof e.className === 'string' && e.className ? '.' + e.className.trim().split(/\\s+/).slice(0, 2).join('.') : '');
  if ((r.right > W + 1 || r.left < -1) && !scrolls(e) && cs.position !== 'fixed') out.over.push([sel, Math.round(r.left), Math.round(r.right)]);
  const interactive = /^(a|button|select|summary)$/.test(tag) || (tag === 'input' && !['checkbox', 'radio', 'hidden', 'file'].includes(e.type)) || tag === 'textarea' || /^(button|tab|switch)$/.test(e.getAttribute('role') || '');
  if (interactive && (r.height < 34 || r.width < 34) && !e.closest('.sr-only')) out.small.push([sel, Math.round(r.width), Math.round(r.height), (e.textContent || e.getAttribute('aria-label') || '').trim().slice(0, 18)]);
 });
 return out; }"""


def audit(page, name=""):
    r = page.evaluate(JS)
    print(f"[movil] {name}: scrollW={r['scrollW']}/{r['W']} desbordes={len(r['over'])} pequenos={len(r['small'])}")
    for x in r["over"][:6]: print("   desborde", x)
    for x in r["small"][:10]: print("   pequeno ", x)
    return r
