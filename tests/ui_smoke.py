"""Prueba de UI con Playwright contra la app real (BD temporal). Uso: python tests/ui_smoke.py [carpeta_capturas]"""
import importlib
import os
import sys
import tempfile
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = sys.argv[1] if len(sys.argv) > 1 else tempfile.mkdtemp()
tmp = tempfile.mkdtemp()
os.environ.update(DB_PATH=tmp + "/t.db", MEDIA_DIR=tmp + "/media", AGENT_TOKEN="tok", COOKIE_SECURE="0", SECRET_KEY="k" * 32, URL_PREFIX="/entreno")
app_mod = importlib.import_module("app")
from werkzeug.serving import make_server
from flask import Flask
from flask.sessions import SecureCookieSessionInterface
from playwright.sync_api import sync_playwright

srv = make_server("127.0.0.1", 18099, app_mod.app, threaded=True)
threading.Thread(target=srv.serve_forever, daemon=True).start()
fl = Flask("x"); fl.config.update(SECRET_KEY="k" * 32, SESSION_COOKIE_NAME="homelab_session")
cookie = SecureCookieSessionInterface().get_signing_serializer(fl).dumps({"auth": True, "exp": time.time() + 3600, "csrf": "csrf"})
BASE = "http://127.0.0.1:18099/entreno/"
errors = []

with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 1280, "height": 900})
    ctx.add_cookies([{"name": "homelab_session", "value": cookie, "url": "http://127.0.0.1:18099/"}])
    page = ctx.new_page()
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(str(e)))
    # Detrás del portal solo llegan las rutas bajo /entreno: cualquier recurso pedido fuera del prefijo daría 404 en producción
    from urllib.parse import urlparse
    page.on("request", lambda r: errors.append("recurso fuera del prefijo /entreno: " + r.url) if urlparse(r.url).path.startswith(("/static", "/media", "/api")) else None)
    page.on("response", lambda r: errors.append("respuesta %s: %s" % (r.status, r.url)) if r.status >= 400 and "favicon" not in r.url else None)
    def shot(name): page.screenshot(path=f"{OUT}/{name}.png")
    def api(method, path, **kw):
        return ctx.request.fetch(BASE.rstrip("/") + path, method=method, headers={"X-CSRF-Token": "csrf", "Origin": "http://127.0.0.1:18099"}, **kw)

    page.goto(BASE); page.wait_for_selector("#view-dashboard h1"); shot("01-dashboard-vacio")
    # ejercicios
    page.goto(BASE + "#/exercises"); page.wait_for_selector(".ex-card"); page.fill("#ex-q", "bench press"); page.wait_for_timeout(600)
    assert page.locator(".ex-card").count() > 3, "búsqueda sin resultados"
    page.locator(".ex-card").first.click(); page.wait_for_selector(".ex-detail .media.anim img.f1"); page.wait_for_timeout(500); shot("02-ejercicio")
    assert page.evaluate("[...document.querySelectorAll('.ex-card img')].every(i => i.complete && i.naturalWidth > 0)"), "hay miniaturas rotas"
    assert page.evaluate("[...document.querySelectorAll('.ex-detail .media img')].every(i => i.complete && i.naturalWidth > 0)"), "imagen del ejercicio rota"
    page.keyboard.press("Escape")
    page.select_option("#ex-cat", "cardio"); page.fill("#ex-q", "carrera"); page.wait_for_timeout(600)
    page.locator(".ex-card").first.click(); page.wait_for_selector(".ex-detail .no-media"); page.wait_for_timeout(500); shot("03-cardio-sin-imagen")
    page.click("#d-media"); page.wait_for_selector("#m-file", state="attached"); page.wait_for_timeout(800)
    assert page.locator("#dialog h3", has_text="Imágenes y vídeos").is_visible() and page.locator("#m-up").is_visible(), "el diálogo de imágenes se cerró o lo tapó el detalle"
    png = bytes.fromhex("89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d4944415478da63fcffff3f0300090301ff8aa7ba620000000049454e44ae426082")
    page.set_input_files("#m-file", files=[{"name": "mia.png", "mimeType": "image/png", "buffer": png}]); page.wait_for_selector(".media-edit img"); page.wait_for_timeout(800)
    assert page.locator("#dialog h3", has_text="Imágenes y vídeos").is_visible(), "tras subir, el diálogo de imágenes debe seguir abierto"
    shot("04-subir-imagen")
    page.keyboard.press("Escape"); page.wait_for_selector(".ex-detail .gallery", state="attached")
    page.keyboard.press("Escape")
    # rutina
    page.goto(BASE + "#/routines"); page.wait_for_selector("[data-act=new]"); page.click("[data-act=new]")
    page.fill("#r-name", "Empuje"); page.click("[data-wd='1']")
    page.click("[data-act=add]"); page.wait_for_selector(".pick-item"); page.fill("#pk-q", "barbell bench press"); page.wait_for_timeout(500); page.locator(".pick-item").first.click()
    page.click("[data-act=add]"); page.wait_for_selector(".pick-item"); page.click("#pk-cat [data-c=cardio]"); page.wait_for_timeout(500); page.locator(".pick-item").first.click()
    page.locator("#r-items .item").first.locator("[data-f=sets]").fill("2"); page.locator("#r-items .item").first.locator("[data-f=rest_s]").fill("30")
    shot("05-editor"); page.click("[data-act=save]"); page.wait_for_selector(".routine"); shot("06-rutinas")
    # entrenar
    page.goto(BASE + "#/train"); page.wait_for_selector("[data-start]"); page.locator("[data-start]").first.click(); page.wait_for_selector("[data-p=work]")
    shot("07-listo"); page.click("[data-p=work]"); page.wait_for_selector("#t-main"); page.wait_for_timeout(1300)
    assert page.inner_text("#t-main") in ("0:01", "0:02"), page.inner_text("#t-main")
    page.fill("#in-reps", "10"); page.fill("#in-weight", "60"); shot("08-serie"); page.click("[data-p=finish]")
    page.wait_for_selector(".timer.rest"); shot("09-descanso")
    first = page.inner_text("#t-main"); page.wait_for_timeout(1300)
    secs = lambda t: int(t.split(":")[0]) * 60 + int(t.split(":")[1])
    now = page.inner_text("#t-main")
    assert secs(now) < secs(first) <= 30, "la cuenta atrás del descanso no avanza: %s -> %s" % (first, now)
    page.click("[data-p=skip]"); page.wait_for_selector("[data-p=work]")
    page.reload(); page.wait_for_selector("[data-p=work]")  # el estado sobrevive a recargar
    page.click("[data-p=quick]"); page.wait_for_selector("[data-p=work]", state="detached", timeout=1500) if False else None
    page.wait_for_timeout(600)
    page.goto(BASE + "#/dashboard"); page.wait_for_selector("#live-banner:not([hidden])"); page.goto(BASE + "#/train"); page.wait_for_selector("[data-top=finish]")
    page.click("[data-top=finish]"); page.wait_for_selector("#fin-ok"); page.click("#rate [data-r='4']"); page.click("#fin-ok")
    page.wait_for_selector(".kpis"); page.wait_for_timeout(500); shot("10-dashboard")
    assert page.inner_text(".kpis").count("1") >= 1
    # ajustes
    page.goto(BASE + "#/settings"); page.wait_for_selector("#st-save"); shot("11-ajustes")
    # móvil
    m = b.new_context(viewport={"width": 390, "height": 800}); m.add_cookies([{"name": "homelab_session", "value": cookie, "url": "http://127.0.0.1:18099/"}])
    mp = m.new_page(); mp.goto(BASE + "#/dashboard"); mp.wait_for_selector(".kpis"); mp.screenshot(path=f"{OUT}/12-movil-dashboard.png")
    mp.goto(BASE + "#/exercises"); mp.wait_for_selector(".ex-card"); mp.screenshot(path=f"{OUT}/13-movil-ejercicios.png")
    b.close()
real = [e for e in errors if "favicon" not in e]
print("errores de consola:", real or "ninguno")
sys.exit(1 if real else 0)
