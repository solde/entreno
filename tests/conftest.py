import importlib
import os
import sys
import time

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
AG = {"X-Agent-Token": "tok"}


@pytest.fixture()
def mod(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setenv("MEDIA_DIR", str(tmp_path / "media"))
    monkeypatch.setenv("AGENT_TOKEN", "tok")
    monkeypatch.setenv("COOKIE_SECURE", "0")
    monkeypatch.setenv("SECRET_KEY", "x" * 32)
    monkeypatch.setenv("URL_PREFIX", "/entreno")
    monkeypatch.setenv("AGENT_IPS", "127.0.0.1")
    for m in ("db", "core", "nutri", "public_auth", "app"):
        sys.modules.pop(m, None)
    app = importlib.import_module("app")
    app.app.testing = True
    return app


class Client:
    def __init__(self, c):
        self.c = c
        self.csrf = "csrf-token"

    def login(self):
        with self.c.session_transaction() as s:
            s.update(auth=True, exp=time.time() + 3600, csrf=self.csrf)

    def req(self, method, url, **kw):
        h = kw.pop("headers", {})
        h.setdefault("X-CSRF-Token", self.csrf)
        return self.c.open(url, method=method, headers=h, **kw)

    def get(self, url, **kw): return self.req("GET", url, **kw)
    def post(self, url, **kw): return self.req("POST", url, **kw)
    def put(self, url, **kw): return self.req("PUT", url, **kw)
    def patch(self, url, **kw): return self.req("PATCH", url, **kw)
    def delete(self, url, **kw): return self.req("DELETE", url, **kw)


@pytest.fixture()
def anon(mod):
    return Client(mod.app.test_client())


@pytest.fixture()
def me(anon):
    anon.login()
    return anon
