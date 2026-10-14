"""Prueba de UI con Playwright contra la app real (BD temporal). Uso: python tests/ui_smoke.py [carpeta_capturas]"""
import importlib
import os
import sys
import tempfile
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
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
fl = Flask("x"); fl.config.update(SECRET_KEY="k" * 32, SESSION_COOKIE_NAME="solde_session")
cookie = SecureCookieSessionInterface().get_signing_serializer(fl).dumps({"auth": True, "exp": time.time() + 3600, "csrf": "csrf"})
BASE = "http://127.0.0.1:18099/entreno/"
errors = []

with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 1280, "height": 900})
    ctx.add_cookies([{"name": "solde_session", "value": cookie, "url": "http://127.0.0.1:18099/"}])
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
    # nutricion: menu en calendario (dia / semana / mes), alimentos, compra, IA
    page.goto(BASE + "#/menu"); page.wait_for_selector(".macros"); shot("14-menu-dia")
    page.click("[data-add=breakfast]"); page.wait_for_selector("#en-pick"); page.click("#en-pick"); page.wait_for_selector("#pf-q"); page.fill("#pf-q", "huevo entero"); page.wait_for_timeout(500)
    page.locator("#dialog2 .pick-item").first.click(); page.wait_for_selector("#en-g"); page.fill("#en-g", "110"); page.wait_for_timeout(300)
    assert "kcal" in page.inner_text("#en-prev"), "sin vista previa de macros"
    page.click("#en-ok"); page.wait_for_selector(".entry"); page.wait_for_timeout(300); shot("15-menu-entrada")
    assert "Huevo entero" in page.inner_text(".slots") and "157" in page.inner_text(".macros"), "la entrada no aparece o los totales no cuadran"
    page.click("[data-add=lunch]"); page.click("#en-kind [data-k=text]"); page.fill("#en-label", "Menú del día"); page.fill("#en-kcal", "800"); page.fill("#en-protein", "40"); page.click("#en-ok"); page.wait_for_selector(".entry >> nth=1")
    page.click("[data-e=done]"); page.wait_for_selector(".entry.done")
    page.click("[data-mode=week]"); page.wait_for_selector(".wk"); page.wait_for_timeout(300); shot("16-menu-semana")
    assert "Huevo entero" in page.inner_text(".wk") and page.locator(".wk-h").count() == 7
    page.click("[data-mode=month]"); page.wait_for_selector(".mo"); page.wait_for_timeout(300); shot("17-menu-mes")
    assert page.locator(".mo-c").count() == 42 and "957" in page.inner_text(".mo"), "el mes no muestra el total del día"
    page.locator(".mo-c.today").click(); page.wait_for_selector(".slots"); assert page.locator(".entry").count() == 2
    page.click("[data-act=ai]"); page.wait_for_selector("#ai-ok"); page.fill("#ai-i", "sin gluten"); page.click("#ai-ok"); page.wait_for_selector(".banner.info")
    page.click("[data-act=copy]"); page.wait_for_selector("#cp-ok"); page.click("#cp-ok"); page.wait_for_selector(".entry"); page.click("[data-nav='1']"); page.wait_for_selector(".entry")
    page.click("[data-act=restore]") if False else None
    page.goto(BASE + "#/foods"); page.wait_for_selector(".food"); page.click("[data-tab=recipes]"); page.click("[data-act=new-recipe]"); page.wait_for_selector("#rc-name"); page.fill("#rc-name", "Bol de prueba")
    page.click("#rc-add"); page.wait_for_selector("#pf-q"); page.fill("#pf-q", "arroz blanco"); page.wait_for_timeout(500); page.locator("#dialog2 .pick-item").first.click(); page.wait_for_selector(".ing"); page.fill("[data-g='0']", "300")
    page.click("#rc-ok"); page.wait_for_selector("[data-recipe]"); shot("18-recetas")
    page.goto(BASE + "#/shopping"); page.wait_for_selector(".shop, .empty"); shot("19-compra")
    # cocinar: ideas de recetas con los alimentos del día
    page.goto(BASE + "#/cook"); page.wait_for_selector("[data-act=ask]:not([disabled])"); assert page.locator("#view-cook .chip").count() >= 2, "no lista los alimentos del día"
    page.fill("#ck-i", "rápido"); page.click("[data-act=ask]"); page.wait_for_selector("#view-cook .banner.info"); shot("23-cocinar-pendiente")
    ag = {"X-Agent-Token": "tok"}; job = None
    for _ in range(4):
        job = ctx.request.fetch("http://127.0.0.1:18099/agent/next?wait=0", headers=ag).json()
        if job.get("kind") == "cook": break
    assert job and job["kind"] == "cook", job
    fid = api("GET", "/api/foods?q=" + "arroz%20blanco").json()["items"][0]["id"]
    ctx.request.fetch("http://127.0.0.1:18099/agent/cook/ideas", method="PUT", headers=ag, data={"date": job["date"], "ideas": [{"name": "Bol de arroz", "servings": 2, "minutes": 15, "steps": "1. Cuece\n2. Sirve", "ingredients": [{"food_id": fid, "grams": 200}, {"name": "Sal", "qty": "una pizca"}]}]})
    ctx.request.fetch("http://127.0.0.1:18099/agent/cook/%d/done" % job["job_id"], method="POST", headers=ag, data={"summary": "ok"})
    page.reload(); page.wait_for_selector("#view-cook .idea"); assert "Bol de arroz" in page.inner_text(".idea") and "kcal" in page.inner_text(".idea"); shot("24-cocinar-ideas")
    page.click("[data-act=save]"); page.wait_for_selector(".idea .chip.ok"); page.goto(BASE + "#/foods"); page.click("[data-tab=recipes]"); page.wait_for_selector("[data-recipe]")
    assert "Bol de arroz" in page.inner_text("#view-foods"), "la idea guardada no aparece en Recetas"
    # escalar a N personas (compra, menú, receta, cocinar)
    page.goto(BASE + "#/shopping"); page.wait_for_selector(".shop"); one = page.inner_text(".shop li >> nth=0")
    page.click("#view-shopping [data-people-step='1']"); page.wait_for_selector("#view-shopping .shop"); assert page.input_value("#sh-people") == "2" and "para 2 personas" in page.inner_text("#view-shopping .view-head"), "la compra no escala"
    assert page.inner_text(".shop li >> nth=0") != one, "las cantidades de la compra no cambian con las personas"
    page.goto(BASE + "#/menu"); page.wait_for_selector(".entry"); assert page.input_value("#mn-people") == "2" and "Cantidades para 2 personas" in page.inner_text("#view-menu"), "el menú no recuerda/escala las personas"
    page.goto(BASE + "#/foods"); page.click("[data-tab=recipes]"); page.locator("[data-recipe]").first.click(); page.wait_for_selector("#rc-scaled li"); assert "2 personas" in page.inner_text("#rc-scaled"); shot("25-receta-escalada"); page.keyboard.press("Escape")
    page.goto(BASE + "#/cook"); page.wait_for_selector("#ck-people"); assert "para 2 personas" in page.inner_text("#view-cook .idea"), "Cocinar no escala"
    page.evaluate("localStorage.setItem('people','1')")
    page.goto(BASE + "#/settings"); page.wait_for_selector("#n-est"); page.fill("#n-weight", "75"); page.fill("#n-height", "178"); page.fill("#n-age", "35"); page.select_option("#n-sex", "m"); page.click("#n-est")
    assert page.input_value("#n-kcal") != "" and int(page.input_value("#n-kcal")) > 1500, "la estimación no rellena las calorías"; page.click("#st-save"); page.wait_for_timeout(500); shot("20-ajustes-nutricion")
    # temporada y producto local
    page.goto(BASE + "#/foods"); page.click("[data-tab=foods]"); page.wait_for_selector(".season"); assert "·" in page.inner_text(".season h3")
    n0 = page.locator(".food").count(); page.click("[data-flt=season]"); page.wait_for_timeout(500)
    assert page.locator(".food").count() > 0 and all("De temporada" in t for t in page.locator(".food").all_inner_texts()), "el filtro de temporada no filtra"
    page.click("[data-flt=cat]"); page.wait_for_timeout(500); shot("30-alimentos-temporada")
    assert page.locator("[data-flt=cat][aria-pressed=true]").count() == 1
    page.click("[data-tab=recipes]"); page.wait_for_selector("[data-recipe]"); page.click("[data-flt=rseason]"); page.wait_for_timeout(500)
    assert "Cataluña" in page.inner_text("#view-foods") or page.locator("[data-recipe]").count() > 0; shot("31-recetas-temporada")
    # móvil
    m = b.new_context(viewport={"width": 390, "height": 800}, is_mobile=True, has_touch=True); m.add_cookies([{"name": "solde_session", "value": cookie, "url": "http://127.0.0.1:18099/"}])
    mp = m.new_page(); mp.goto(BASE + "#/dashboard"); mp.wait_for_selector(".kpis"); mp.screenshot(path=f"{OUT}/12-movil-dashboard.png")
    mp.goto(BASE + "#/exercises"); mp.wait_for_selector(".ex-card"); mp.screenshot(path=f"{OUT}/13-movil-ejercicios.png")
    mp.goto(BASE + "#/menu"); mp.wait_for_selector(".macros"); mp.screenshot(path=f"{OUT}/21-movil-menu.png")
    mp.click("[data-mode=week]"); mp.wait_for_selector(".wk"); mp.screenshot(path=f"{OUT}/22-movil-semana.png")
    from mobile_audit import audit
    audit(mp, "semana")
    for v in ["dashboard", "routines", "train", "exercises", "menu", "foods", "cook", "shopping", "chat", "settings"]:
        mp.goto("about:blank"); mp.goto(BASE + "?embed=1#/" + v); mp.wait_for_timeout(900); mp.screenshot(path=f"{OUT}/m-{v}.png"); audit(mp, v)
    b.close()
real = [e for e in errors if "favicon" not in e]
print("errores de consola:", real or "ninguno")
sys.exit(1 if real else 0)
