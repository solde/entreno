"""Playwright: cada dominio publico muestra solo sus vistas, sin errores de consola. Uso: python tests/ui_modes.py [carpeta_capturas]"""
import importlib
import os
import sys
import tempfile
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = sys.argv[1] if len(sys.argv) > 1 else tempfile.mkdtemp()
tmp = tempfile.mkdtemp()
os.environ.update(DB_PATH=tmp + "/t.db", MEDIA_DIR=tmp + "/media", AGENT_TOKEN="tok", COOKIE_SECURE="0", SECRET_KEY="k" * 32, URL_PREFIX="", SITE_MODES="127.0.0.1=nutricion,localhost=entreno")
app_mod = importlib.import_module("app")
from werkzeug.serving import make_server
from flask import Flask
from flask.sessions import SecureCookieSessionInterface
from playwright.sync_api import sync_playwright

srv = make_server("0.0.0.0", 18097, app_mod.app, threaded=True)
threading.Thread(target=srv.serve_forever, daemon=True).start()
fl = Flask("x"); fl.config.update(SECRET_KEY="k" * 32, SESSION_COOKIE_NAME="solde_session")
cookie = SecureCookieSessionInterface().get_signing_serializer(fl).dumps({"auth": True, "exp": time.time() + 3600, "csrf": "csrf", "user": "david"})
errors = []
with sync_playwright() as p:
    b = p.chromium.launch()
    for host, mode, must, must_not in [("127.0.0.1", "nutricion", ["menu", "foods", "cook", "shopping", "chat"], ["routines", "train", "exercises"]), ("localhost", "entreno", ["dashboard", "routines", "train", "exercises", "chat"], ["menu", "foods", "shopping"])]:
        for mobile in (False, True):
            ctx = b.new_context(viewport={"width": 390 if mobile else 1280, "height": 840}, is_mobile=mobile, has_touch=mobile)
            ctx.add_cookies([{"name": "solde_session", "value": cookie, "url": f"http://{host}:18097/"}])
            page = ctx.new_page()
            page.on("console", lambda m, h=host: errors.append(f"[{h}] {m.text}") if m.type == "error" else None)
            page.on("pageerror", lambda e, h=host: errors.append(f"[{h}] {e}"))
            page.on("response", lambda r, h=host: errors.append(f"[{h}] {r.status} {r.url}") if r.status >= 400 and "favicon" not in r.url else None)
            page.goto(f"http://{host}:18097/")
            time.sleep(1.5)
            assert page.evaluate("document.querySelector('meta[name=mode]').content") == mode
            for v in must:
                assert page.evaluate(f"!!document.getElementById('view-{v}')"), f"{mode}: falta {v}"
                page.goto(f"http://{host}:18097/#/{v}")
                time.sleep(0.6)
                assert page.evaluate(f"!document.getElementById('view-{v}').hidden"), f"{mode}: {v} no se muestra"
            for v in must_not:
                assert not page.evaluate(f"!!document.getElementById('view-{v}')"), f"{mode}: sobra {v}"
            page.goto(f"http://{host}:18097/#/" + must_not[0]); time.sleep(0.6)           # ruta de la otra seccion: cae en la vista por defecto
            assert page.evaluate(f"!document.getElementById('view-{must[0]}').hidden"), f"{mode}: no redirige a la vista por defecto"
            page.screenshot(path=f"{OUT}/{mode}-{'mobile' if mobile else 'desktop'}.png")
            if mobile:
                assert page.evaluate("document.documentElement.scrollWidth - window.innerWidth") <= 1, "desborde horizontal"
            ctx.close()
    b.close()
if errors:
    print("ERRORES:", *errors[:20], sep="\n  "); sys.exit(1)
print("ui_modes OK")
