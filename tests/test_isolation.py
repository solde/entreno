"""Cada persona solo ve y toca SUS datos: una base SQLite y una carpeta de media por usuario; el asistente trabaja en nombre de una persona concreta."""
import io
import os
import time

import pytest

from conftest import Client

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64
TOKEN = {"X-Agent-Token": "tok"}


def agent(user):
    return {**TOKEN, "X-Agent-User": user}


@pytest.fixture()
def duo(mod):
    """Dos personas con sesion en el mismo servidor."""
    out = []
    for u in ("alicia", "benito"):
        c = Client(mod.app.test_client())
        c.login(u)
        out.append(c)
    return out[0], out[1], mod


def first_ex(c, q):
    return c.get("/api/exercises", query_string={"q": q}).get_json()["items"][0]["id"]


def test_each_person_has_their_own_database_file(duo):
    a, b, mod = duo
    a.get("/api/meta"), b.get("/api/meta")
    import db
    assert db.users() == ["alicia", "benito", "tester"] and os.path.isfile(db.path_of("alicia")) and db.path_of("alicia") != db.path_of("benito")


def test_routines_exercises_and_settings_are_private(duo):
    a, b, mod = duo
    bench = first_ex(a, "barbell bench press")
    r = a.post("/api/routines", json={"name": "Rutina secreta de Alicia", "items": [{"exercise_id": bench, "sets": 3, "reps_min": 8, "reps_max": 10, "weight": 60}]}).get_json()
    assert [x["name"] for x in a.get("/api/routines").get_json()] == ["Rutina secreta de Alicia"]
    assert b.get("/api/routines").get_json() == []
    rid = r["id"]
    assert b.get("/api/routines/%d" % rid).status_code == 404
    assert b.put("/api/routines/%d" % rid, json={"name": "robada"}).status_code == 404
    assert b.delete("/api/routines/%d" % rid).status_code == 404
    assert a.get("/api/routines/%d" % rid).get_json()["name"] == "Rutina secreta de Alicia"          # sigue intacta
    mine = a.post("/api/exercises", json={"name": "Ejercicio privado de Alicia", "tracking": "reps", "primary": ["lats"], "equipment": "other"}).get_json()
    assert a.get("/api/exercises", query_string={"q": "privado de Alicia"}).get_json()["total"] == 1
    assert b.get("/api/exercises", query_string={"q": "privado de Alicia"}).get_json()["total"] == 0
    assert b.get("/api/exercises/%s" % mine["id"]).status_code == 404
    a.put("/api/settings", json={"n_kcal": 2750, "goal": "hipertrofia"})
    assert b.get("/api/settings").get_json()["n_kcal"] != 2750 and b.get("/api/settings").get_json()["goal"] != "hipertrofia"


def test_nutrition_data_is_private(duo):
    a, b, mod = duo
    a.post("/api/foods", json={"name": "Barrita secreta de Alicia", "kcal": 380, "protein": 20, "carbs": 40, "fat": 14, "serving_g": 45, "category": "Otros"})
    assert a.get("/api/foods", query_string={"q": "secreta de Alicia"}).get_json()["total"] == 1
    assert b.get("/api/foods", query_string={"q": "secreta de Alicia"}).get_json()["total"] == 0


def test_uploaded_media_is_private(duo):
    a, b, mod = duo
    e = a.post("/api/exercises", json={"name": "Remo de Alicia", "tracking": "reps", "primary": ["lats"], "equipment": "other"}).get_json()
    up = a.post("/api/exercises/%s/media" % e["id"], data={"file": (io.BytesIO(PNG), "foto.png")}, content_type="multipart/form-data")
    url = up.get_json()["media"][0]["url"]
    assert a.get(url).data == PNG
    assert b.get(url).status_code == 404
    assert b.post("/api/exercises/%s/media" % e["id"], data={"file": (io.BytesIO(PNG), "x.png")}, content_type="multipart/form-data").status_code == 404
    import db
    assert os.path.isdir(db.media_dir("alicia")) and not os.path.exists(db.media_dir("benito") + "/" + e["id"])


def test_chat_is_private(duo):
    a, b, mod = duo
    sid = a.post("/api/chat/sessions").get_json()["id"]
    tid = a.post("/api/chat/sessions/%d/messages" % sid, json={"text": "Mi lesión secreta"}).get_json()["turn_id"]
    assert b.get("/api/chat/sessions").get_json() == []
    assert b.get("/api/chat/sessions/%d" % sid).status_code == 404
    assert b.get("/api/chat/turns/%d" % tid).status_code == 404
    assert b.post("/api/chat/sessions/%d/messages" % sid, json={"text": "hola"}).status_code == 404
    assert b.delete("/api/chat/sessions/%d" % sid).status_code == 404


def test_agent_works_for_one_person_at_a_time(duo):
    a, b, mod = duo
    c = mod.app.test_client()
    # sin persona o con una desconocida, el asistente no recibe nada
    assert c.get("/agent/profile", headers=TOKEN).status_code == 400
    assert c.get("/agent/profile", headers=agent("fantasma")).status_code == 400
    assert c.get("/agent/profile", headers=agent("../../etc")).status_code == 400
    bench = first_ex(a, "barbell bench press")
    b.get("/api/meta")                                                  # su base se crea al entrar por primera vez
    a.post("/api/routines", json={"name": "Rutina de Alicia", "items": [{"exercise_id": bench, "sets": 3, "reps_min": 8, "reps_max": 10, "weight": 60}]})
    assert [r["name"] for r in c.get("/agent/routines", headers=agent("alicia")).get_json()] == ["Rutina de Alicia"]
    assert c.get("/agent/routines", headers=agent("benito")).get_json() == []
    # el trabajo en cola se entrega con el nombre de su dueña, y solo con su cabecera se puede cerrar
    sid = a.post("/api/chat/sessions").get_json()["id"]
    tid = a.post("/api/chat/sessions/%d/messages" % sid, json={"text": "Hola"}).get_json()["turn_id"]
    job = c.get("/agent/next?wait=0", headers=TOKEN).get_json()
    assert job["kind"] == "chat" and job["turn_id"] == tid and job["user"] == "alicia"
    assert c.post("/agent/turns/%d/done" % tid, headers=agent("benito"), json={"text": "x"}).status_code == 404
    assert c.post("/agent/turns/%d/done" % tid, headers=agent("alicia"), json={"text": "Hecho"}).status_code == 200
    assert a.get("/api/chat/turns/%d" % tid).get_json()["answer"] == "Hecho"
    assert c.get("/agent/next?wait=0", headers=TOKEN).status_code == 204


def test_session_without_user_is_rejected(mod):
    c = mod.app.test_client()
    with c.session_transaction() as s:
        s.update(auth=True, exp=time.time() + 3600, csrf="x")      # cookie anterior a las cuentas: sin usuario
    assert c.get("/api/meta").status_code in (401, 302)
    with c.session_transaction() as s:
        s.update(user="../x")
    assert c.get("/api/meta").status_code in (401, 302)


def test_legacy_database_goes_only_to_its_owner(tmp_path, monkeypatch):
    """La base anterior a las cuentas (y su media) pasa a la persona indicada en LEGACY_OWNER; nadie mas la ve."""
    import importlib
    import sqlite3
    import sys
    monkeypatch.setenv("DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setenv("MEDIA_DIR", str(tmp_path / "media"))
    monkeypatch.setenv("LEGACY_OWNER", "dueno")
    for k, v in dict(AGENT_TOKEN="tok", COOKIE_SECURE="0", SECRET_KEY="x" * 32, URL_PREFIX="/entreno", AGENT_IPS="127.0.0.1").items():
        monkeypatch.setenv(k, v)
    for m in ("db", "core", "nutri", "casas", "public_auth", "app"):
        sys.modules.pop(m, None)
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    # base antigua con un dato reconocible y una imagen propia
    old = importlib.import_module("db")
    old.PATH = str(tmp_path / "t.db")
    c = sqlite3.connect(old.PATH)
    c.executescript(old.SCHEMA)
    c.execute("INSERT INTO routines(id,uid,name,created,updated) VALUES(1,'u1','Rutina de antes',1,1)")
    c.commit()
    c.close()
    os.makedirs(tmp_path / "media" / "ex1")
    (tmp_path / "media" / "ex1" / "a.png").write_bytes(PNG)
    for m in ("db", "core", "nutri", "casas", "public_auth", "app"):
        sys.modules.pop(m, None)
    mod = importlib.import_module("app")
    mod.app.testing = True
    import db
    other = Client(mod.app.test_client())
    other.login("intruso")
    other.get("/api/meta")
    assert os.path.exists(db.PATH)                                      # otra persona no se lleva la base antigua
    owner = Client(mod.app.test_client())
    owner.login("dueno")
    owner.get("/api/meta")
    assert not os.path.exists(db.PATH) and os.path.isfile(db.path_of("dueno"))
    assert os.path.isfile(os.path.join(db.media_dir("dueno"), "ex1", "a.png")) and not os.path.exists(os.path.join(tmp_path, "media", "ex1"))
    chk = sqlite3.connect(db.path_of("dueno"))
    assert chk.execute("SELECT COUNT(*) FROM routines WHERE name='Rutina de antes'").fetchone()[0] == 1
    assert owner.get("/api/routines").get_json()[0]["name"] == "Rutina de antes" and other.get("/api/routines").get_json() == []


def test_agent_can_correct_registered_workout(duo):
    a, b, mod = duo
    c = mod.app.test_client()
    bench = first_ex(a, "barbell bench press")
    sid = a.post("/api/sessions", json={}).get_json()["id"]
    sset = a.post("/api/sessions/%d/sets" % sid, json={"exercise_id": bench, "position": 0, "reps": 8, "weight": 50}).get_json()
    a.post("/api/sessions/%d/finish" % sid, json={})
    H = agent("alicia")
    r = c.patch("/agent/sessions/%d/sets/%d" % (sid, sset["id"]), headers=H, json={"reps": 10, "weight": 55})
    assert r.status_code == 200 and r.get_json()["reps"] == 10
    n = c.post("/agent/sessions/%d/sets" % sid, headers=H, json={"exercise_id": bench, "position": 0, "reps": 6, "weight": 60}).get_json()
    assert n["set_no"] == 2
    assert c.patch("/agent/sessions/%d" % sid, headers=H, json={"notes": "ok", "rating": 4}).get_json()["rating"] == 4
    assert c.delete("/agent/sessions/%d/sets/%d" % (sid, n["id"]), headers=H).status_code == 200
    b.get("/api/meta")
    # otra persona no ve ni toca esa sesión
    assert c.patch("/agent/sessions/%d/sets/%d" % (sid, sset["id"]), headers=agent("benito"), json={"reps": 1}).status_code == 404
