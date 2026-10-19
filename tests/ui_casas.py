"""Playwright: gestor de casas en Nutricion (crear, asignar, cambiar de casa, menu compartido), sin errores de consola. Uso: python tests/ui_casas.py [carpeta_capturas]"""
import importlib
import os
import sys
import tempfile
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = sys.argv[1] if len(sys.argv) > 1 else tempfile.mkdtemp()
tmp = tempfile.mkdtemp()
os.environ.update(DB_PATH=tmp + "/t.db", MEDIA_DIR=tmp + "/media", AGENT_TOKEN="tok", COOKIE_SECURE="0", SECRET_KEY="k" * 32, URL_PREFIX="", SITE_MODES="127.0.0.1=nutricion")
app_mod = importlib.import_module("app")
from werkzeug.serving import make_server
from flask import Flask
from flask.sessions import SecureCookieSessionInterface
from playwright.sync_api import sync_playwright

PORT = 18096
srv = make_server("0.0.0.0", PORT, app_mod.app, threaded=True)
threading.Thread(target=srv.serve_forever, daemon=True).start()
fl = Flask("x"); fl.config.update(SECRET_KEY="k" * 32, SESSION_COOKIE_NAME="solde_session")
ser = SecureCookieSessionInterface().get_signing_serializer(fl)
cookie = lambda u: ser.dumps({"auth": True, "exp": time.time() + 3600, "csrf": "csrf", "user": u})
errors = []
URL = f"http://127.0.0.1:{PORT}/"


def check(cond, msg):
    if not cond:
        errors.append("FALLO: " + msg)


def open_as(b, user, mobile=False):
    ctx = b.new_context(viewport={"width": 390 if mobile else 1280, "height": 860}, is_mobile=mobile, has_touch=mobile, bypass_csp=True)
    ctx.add_cookies([{"name": "solde_session", "value": cookie(user), "url": URL}])
    page = ctx.new_page()
    page.on("console", lambda m: errors.append(f"[{user}] {m.text}") if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(f"[{user}] {e}"))
    page.on("response", lambda r: errors.append(f"[{user}] {r.status} {r.url}") if r.status >= 400 and "favicon" not in r.url else None)
    page.goto(URL + "#/menu")
    page.wait_for_selector("#casa-btn")
    time.sleep(0.8)
    return ctx, page


with sync_playwright() as p:
    b = p.chromium.launch()
    ctx, pg = open_as(b, "david")
    check(pg.inner_text("#casa-btn").strip() == "Mi menú", "boton sin casa debe decir Mi menú")
    # una entrada de menu personal que se copiara a la casa
    pg.evaluate("""fetch('/api/plan/entries', {method:'POST', headers:{'Content-Type':'application/json','X-CSRF-Token':'csrf'},
        body: JSON.stringify({date: new Date().toISOString().slice(0,10), slot:'lunch', kind:'text', label:'Paella del domingo', kcal: 700})})""")
    pg.click("#casa-btn")
    pg.wait_for_selector("dialog.casa-dlg[open]")
    pg.screenshot(path=OUT + "/casas-vacio.png")
    pg.fill("#casa-new input[name=name]", "Casa de Palleja")
    pg.check("#casa-new input[name=copy]")
    pg.click("#casa-new button[type=submit]")
    pg.wait_for_function("document.querySelector('#casa-btn span').textContent.includes('Palleja')", timeout=8000)
    time.sleep(0.8)
    check("Palleja" in pg.inner_text("#casa-btn"), "tras crear, el boton muestra la casa")
    check("Paella" in pg.inner_text("#view-menu"), "la entrada copiada aparece en el menu de la casa")
    # asignar a ana
    pg.click("#casa-btn")
    pg.wait_for_selector("dialog.casa-dlg[open] .casa[data-slug]")
    pg.fill("form[data-add] input[name=user]", "ana")
    pg.click("form[data-add] button[type=submit]")
    pg.wait_for_selector(".casa-people .chip:has-text('ana')")
    pg.screenshot(path=OUT + "/casas-asignada.png")
    ctx.close()

    # ana (movil): ve la casa, la usa y ve el menu compartido
    ctx2, pa = open_as(b, "ana", mobile=True)
    check("Mi menú" in pa.inner_text("#casa-btn"), "ana empieza en su menu personal")
    check("Paella" not in pa.inner_text("#view-menu"), "ana no ve aun el menu de la casa")
    pa.click("#casa-btn")
    pa.wait_for_selector("dialog.casa-dlg[open] .casa[data-slug]")
    time.sleep(0.6)
    bb = pa.locator("dialog.casa-dlg").bounding_box()
    check(bb and bb["x"] >= 0 and bb["x"] + bb["width"] <= 391 and bb["width"] > 250, f"el dialogo cabe en el movil: {bb}")
    pa.screenshot(path=OUT + "/casas-ana-movil.png")
    check(pa.locator("form[data-add]").count() == 0, "una persona que no administra no ve el formulario de asignar")
    pa.click("[data-use='casa-de-palleja']")
    pa.wait_for_function("document.querySelector('#casa-btn span').textContent.includes('Palleja')", timeout=8000)
    time.sleep(0.8)
    check("Paella" in pa.inner_text("#view-menu"), "ana ve el menu compartido")
    pa.screenshot(path=OUT + "/casas-menu-ana.png")
    ctx2.close()
    b.close()

print("\n".join(errors) or "OK ui_casas")
sys.exit(1 if errors else 0)
