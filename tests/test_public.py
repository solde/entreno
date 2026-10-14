"""Sitio publico: login con usuario/contraseña (servicio auth falso), separacion entreno/nutricion por dominio y /agent solo desde el host."""
import importlib
import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest


class Fake(BaseHTTPRequestHandler):
    def do_POST(self):
        d = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        ok = self.headers.get("X-Auth-Token") == "tok" and d["username"] == "david" and d["password"] == "clave-correcta-1"
        out = json.dumps({"ok": ok, "user": "david"}).encode()
        self.send_response(200 if ok else 401); self.send_header("Content-Length", str(len(out))); self.end_headers(); self.wfile.write(out)

    def log_message(self, *a):
        pass


@pytest.fixture()
def pub(tmp_path, monkeypatch):
    s = HTTPServer(("127.0.0.1", 0), Fake)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    for k, v in dict(DB_PATH=str(tmp_path / "t.db"), MEDIA_DIR=str(tmp_path / "media"), AGENT_TOKEN="tok", COOKIE_SECURE="0", SECRET_KEY="x" * 32, URL_PREFIX="", AGENT_IPS="127.0.0.1",
                     AUTH_URL="http://127.0.0.1:%d" % s.server_port, AUTH_TOKEN="tok", SITE_MODES="entreno.solde.cat=entreno,nutricion.solde.cat=nutricion").items():
        monkeypatch.setenv(k, v)
    for m in ("db", "core", "nutri", "public_auth", "app"):
        sys.modules.pop(m, None)
    app = importlib.import_module("app")
    app.app.testing = True
    app.db.use("tester")
    app.db.use(None)
    yield app
    s.shutdown()


def login(c, host):
    b = "http://" + host
    c.get("/login", base_url=b)
    with c.session_transaction(base_url=b) as s:
        tok = s["lcsrf"]
    return c.post("/login", data={"csrf": tok, "username": "david", "password": "clave-correcta-1", "next": "/"}, base_url=b)


def test_everything_requires_login(pub):
    c = pub.app.test_client()
    r = c.get("/", base_url="http://entreno.solde.cat")
    assert r.status_code == 302 and r.headers["Location"].startswith("/login?next=")
    assert c.get("/api/stats").status_code == 401
    assert c.get("/static/css/app.css").status_code == 200 and c.get("/login").status_code == 200 and c.get("/healthz").status_code == 200
    assert c.get("/media/x").status_code == 401


def test_login_and_session_cookie(pub):
    c = pub.app.test_client()
    assert login(c, "entreno.solde.cat").status_code == 302
    r = c.get("/", base_url="http://entreno.solde.cat")
    assert r.status_code == 200
    assert c.get_cookie("solde_session", domain="entreno.solde.cat") is not None and c.get_cookie("homelab_session", domain="entreno.solde.cat") is None    # cookie propia, distinta de la del portal
    with c.session_transaction(base_url="http://entreno.solde.cat") as s:
        csrf = s["csrf"]
    assert c.post("/api/logout", base_url="http://entreno.solde.cat", headers={"X-CSRF-Token": csrf, "Origin": "http://entreno.solde.cat"}).status_code == 200
    assert c.get("/", base_url="http://entreno.solde.cat").status_code == 302


def test_domain_modes(pub):
    c = pub.app.test_client()
    login(c, "entreno.solde.cat")
    login(c, "nutricion.solde.cat")
    login(c, "10.43.1.1:8080")
    e = c.get("/", base_url="http://entreno.solde.cat").get_data(as_text=True)
    n = c.get("/", base_url="http://nutricion.solde.cat").get_data(as_text=True)
    other = c.get("/", base_url="http://10.43.1.1:8080").get_data(as_text=True)
    assert 'content="entreno"' in e and 'id="view-routines"' in e and 'id="view-menu"' not in e and "live-banner" in e
    assert 'content="nutricion"' in n and 'id="view-menu"' in n and 'id="view-routines"' not in n and "live-banner" not in n and "Nutrición" in n
    assert 'content="all"' in other and 'id="view-menu"' in other and 'id="view-routines"' in other
    assert 'href="/"' not in e.split('class="sidebar-foot"')[1].split("</div>")[0]                    # sin enlace al portal privado


def test_agent_only_from_host(pub):
    c = pub.app.test_client()
    ok = c.get("/agent/profile", headers={"X-Agent-Token": "tok", "X-Agent-User": "tester"})
    assert ok.status_code == 200                                              # directo (127.0.0.1 = host de prueba)
    assert c.get("/agent/profile", headers={"X-Agent-Token": "tok", "X-Agent-User": "tester", "X-Forwarded-For": "8.8.8.8"}).status_code == 404      # via Traefik/internet: nunca
    assert c.get("/agent/profile", headers={"X-Agent-Token": "tok", "X-Agent-User": "tester"}, environ_overrides={"REMOTE_ADDR": "10.42.7.7"}).status_code == 404
    assert c.get("/agent/profile").status_code in (401, 404)


def test_http_is_redirected_to_https(pub):
    c = pub.app.test_client()
    r = c.get("/", headers={"X-Forwarded-Proto": "http", "X-Forwarded-Host": "entreno.solde.cat"})
    assert r.status_code == 301 and r.headers["Location"] == "https://entreno.solde.cat/"
