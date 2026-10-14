"""Login con usuario y contraseña para una app Flask expuesta a internet (copia identica en cada app: homelab-training, homelab-f1).

`install(app, brand=...)`: ruta /login (formulario sin JavaScript, CSRF de sesion, limite por IP), redireccion a https cuando llega por http detras de Traefik, HSTS,
y `agent_ip_ok()` para que /agent/* solo acepte al worker del host aunque la app este publicada. Las credenciales se comprueban contra el servicio `auth`
(AUTH_URL + AUTH_TOKEN, solo ClusterIP); la app nunca guarda contraseñas. La sesion que se crea es la que ya espera `gate()` de cada app:
session["auth"], session["exp"], session["csrf"] (+ session["user"]).
"""
import hmac
import json
import os
import secrets
import time
import urllib.error
import urllib.request
from html import escape
from urllib.parse import quote

from flask import redirect, request, session

AUTH_URL = os.environ.get("AUTH_URL", "").rstrip("/")
AUTH_TOKEN = os.environ.get("AUTH_TOKEN", "")
IP_FAILS, IP_WINDOW = 10, 600
AGENT_IPS = {x.strip() for x in os.environ.get("AGENT_IPS", "10.42.0.1,192.168.1.224").split(",") if x.strip()}
_fails = {}


def safe_next(n):
    n = n or "/"
    return n if n.startswith("/") and not n.startswith("//") and "\\" not in n and "\n" not in n and "\r" not in n else "/"


def client_ip():
    return request.remote_addr or ""


def agent_ip_ok():
    """True solo si la peticion viene directa del host/ClusterIP (no de Traefik ni de internet)."""
    if request.headers.get("X-Forwarded-For") or request.headers.get("X-Forwarded-Host"):
        return False
    orig = (request.environ.get("werkzeug.proxy_fix.orig") or {}).get("REMOTE_ADDR") or request.environ.get("REMOTE_ADDR") or ""
    return orig in AGENT_IPS


def _limited(ip):
    now = time.time()
    lst = [t for t in _fails.get(ip, []) if now - t < IP_WINDOW]
    _fails[ip] = lst
    if len(_fails) > 5000:
        _fails.clear()
    return len(lst) >= IP_FAILS


def verify(username, password, ip):
    """-> ('ok', usuario) | ('bad', None) | ('locked', None) | ('down', None)"""
    if not AUTH_URL or not AUTH_TOKEN:
        return "down", None
    req = urllib.request.Request(AUTH_URL + "/verify", data=json.dumps({"username": username, "password": password, "ip": ip}).encode(), method="POST",
                                 headers={"X-Auth-Token": AUTH_TOKEN, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            d = json.loads(r.read() or b"{}")
            return ("ok", d.get("user") or username) if d.get("ok") else ("bad", None)
    except urllib.error.HTTPError as e:
        return ("locked", None) if e.code == 429 else (("bad", None) if e.code == 401 else ("down", None))
    except Exception:  # noqa: BLE001
        return "down", None


PAGE = """<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="color-scheme" content="light dark"><meta name="robots" content="noindex, nofollow">
<title>Acceso · {brand}</title><link rel="icon" href="{base}/static/favicon.svg" type="image/svg+xml"><link rel="stylesheet" href="{base}/static/css/app.css">
<style>.lg{{min-height:100dvh;display:grid;place-items:center;padding:20px}}.lg form{{width:min(380px,100%);display:flex;flex-direction:column;gap:12px;padding:26px}}
.lg h1{{font-size:1.5rem;letter-spacing:-.02em}}.lg label{{font-size:.8rem;font-weight:650;color:var(--text-2);display:flex;flex-direction:column;gap:5px}}
.lg input{{min-height:46px;padding:0 14px;border-radius:12px;border:1px solid var(--line);background:var(--fill);color:var(--text);font:inherit}}
.lg input:focus{{outline:2px solid var(--accent)}}.lg button{{min-height:46px;border-radius:99px;border:0;background:var(--accent);color:#fff;font-weight:650;font:inherit;cursor:pointer}}
.err{{color:var(--bad);background:var(--bad-soft);border-radius:10px;padding:8px 12px;font-size:.88rem}}</style>
<script src="{base}/static/js/boot.js"></script></head>
<body><div class="bg" aria-hidden="true"><i></i><i></i><i></i></div>
<main class="lg"><form method="post" action="{base}/login" class="glass" autocomplete="on"><h1>{brand}</h1><p class="muted">Inicia sesión para continuar.</p>{error}
<input type="hidden" name="csrf" value="{csrf}"><input type="hidden" name="next" value="{next}">
<label>Usuario<input name="username" autocomplete="username" autocapitalize="none" spellcheck="false" required autofocus maxlength="64"></label>
<label>Contraseña<input name="password" type="password" autocomplete="current-password" required maxlength="256"></label>
<button type="submit">Entrar</button></form></main></body></html>"""


def render(brand, error="", status=200):
    brand = brand() if callable(brand) else brand
    session["lcsrf"] = session.get("lcsrf") or secrets.token_urlsafe(24)
    html = PAGE.format(brand=escape(brand), base=request.script_root, csrf=session["lcsrf"], next=escape(safe_next(request.values.get("next")), quote=True),
                       error=('<div class="err" role="alert">%s</div>' % escape(error)) if error else "")
    return html, status, {"Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store"}


def install(app, brand, session_hours=168.0):
    def https_redirect():
        if request.headers.get("X-Forwarded-Proto") == "http" and request.path != "/healthz":
            return redirect("https://" + (request.headers.get("X-Forwarded-Host") or request.host) + request.full_path.rstrip("?"), 301)
        return None
    app.before_request_funcs.setdefault(None, []).insert(0, https_redirect)

    @app.after_request
    def hsts(resp):
        if request.headers.get("X-Forwarded-Proto") == "https" or request.is_secure:
            resp.headers["Strict-Transport-Security"] = "max-age=15552000"
        return resp

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "GET":
            return render(brand)
        ip = client_ip()
        want = session.get("lcsrf", "")
        if not want or not hmac.compare_digest(str(request.form.get("csrf", "")), want):
            return render(brand, "La sesión del formulario caducó. Inténtalo de nuevo.", 400)
        if _limited(ip):
            return render(brand, "Demasiados intentos. Espera unos minutos.", 429)
        status, user = verify(request.form.get("username", ""), request.form.get("password", ""), ip)
        if status == "ok":
            nxt = safe_next(request.form.get("next"))
            session.clear()
            session.permanent = True
            session.update(auth=True, user=user, exp=time.time() + session_hours * 3600, csrf=secrets.token_urlsafe(32))
            return redirect(request.script_root + nxt if not nxt.startswith(request.script_root or "\0") else nxt)
        if status == "down":
            return render(brand, "El servicio de usuarios no está disponible. Inténtalo en un momento.", 503)
        _fails.setdefault(ip, []).append(time.time())
        return render(brand, "Demasiados intentos para este usuario. Espera unos minutos." if status == "locked" else "Usuario o contraseña incorrectos.", 429 if status == "locked" else 401)
