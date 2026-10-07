(function () {
  var d = document.documentElement;
  function get(k, def) { try { return localStorage.getItem(k) || def; } catch (e) { return def; } }
  var mq = window.matchMedia ? matchMedia("(prefers-color-scheme: dark)") : null;
  function resolve(pref) { return pref === "auto" ? (mq && mq.matches ? "dark" : "light") : pref; }
  function applyTheme(pref) {
    d.dataset.themePref = pref;
    d.dataset.theme = resolve(pref);
    var m = document.querySelector('meta[name="color-scheme"]');
    if (m) m.content = pref === "auto" ? "light dark" : pref;
  }
  window.__prefs = {
    applyTheme: applyTheme,
    setTheme: function (p) { try { localStorage.setItem("theme", p); } catch (e) {} applyTheme(p); },
    setDensity: function (v) { try { localStorage.setItem("density", v); } catch (e) {} d.dataset.density = v; },
  };
  applyTheme(get("theme", "auto"));
  d.dataset.density = get("density", "comfortable");
  if (mq) {
    var onChange = function () { if (get("theme", "auto") === "auto") applyTheme("auto"); };
    if (mq.addEventListener) mq.addEventListener("change", onChange); else if (mq.addListener) mq.addListener(onChange);
  }
})();
