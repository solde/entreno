"""Casas: menu, alimentos y recetas compartidos entre las personas asignadas; lo personal (objetivos, entrenos) sigue siendo privado."""
import os

import pytest

from conftest import Client

TOKEN = {"X-Agent-Token": "tok"}
D = "2026-10-12"


def agent(user, casa=None):
    return {**TOKEN, "X-Agent-User": user, **({"X-Agent-Casa": casa} if casa else {})}


@pytest.fixture()
def trio(mod):
    out = []
    for u in ("alicia", "benito", "carmen"):
        c = Client(mod.app.test_client())
        c.login(u)
        c.get("/api/meta")                  # crea su base personal
        out.append(c)
    return out[0], out[1], out[2], mod


def entry(c, label="Lentejas de la casa"):
    r = c.post("/api/plan/entries", json={"date": D, "slot": "lunch", "kind": "text", "label": label, "kcal": 500})
    assert r.status_code == 201, r.get_data()
    return r.get_json()


def day(c):
    return c.get("/api/plan", query_string={"from": D, "to": D}).get_json()["days"].get(D, {}).get("entries", [])


def test_create_casa_shares_menu_between_members_only(trio):
    a, b, c, mod = trio
    r = a.post("/api/casas", json={"name": "Casa de Palleja"})
    assert r.status_code == 201
    st = r.get_json()
    slug = st["created"]
    assert st["active"] == slug and st["casas"][0]["name"] == "Casa de Palleja" and st["casas"][0]["role"] == "owner"
    entry(a)
    assert [e["name"] for e in day(a)] == ["Lentejas de la casa"]
    # benito aun no es miembro: ve su menu personal (vacio)
    assert day(b) == [] and b.get("/api/casas").get_json()["casas"] == []
    assert a.post("/api/casas/%s/members" % slug, json={"user": "benito"}).status_code == 201
    # asignado, la casa aparece pero no esta activa hasta que la elige
    st = b.get("/api/casas").get_json()
    assert [x["slug"] for x in st["casas"]] == [slug] and st["active"] is None and day(b) == []
    assert b.put("/api/casas/active", json={"casa": slug}).status_code == 200
    assert [e["name"] for e in day(b)] == ["Lentejas de la casa"]
    entry(b, "Tortilla de Benito")
    assert sorted(e["name"] for e in day(a)) == ["Lentejas de la casa", "Tortilla de Benito"]
    # carmen no puede ni activarla ni tocarla
    assert c.put("/api/casas/active", json={"casa": slug}).status_code == 422
    assert day(c) == []
    # volver a lo personal
    b.put("/api/casas/active", json={"casa": None})
    assert day(b) == []


def test_person_can_be_in_several_casas(trio):
    a, b, c, mod = trio
    s1 = a.post("/api/casas", json={"name": "Casa"}).get_json()["created"]
    entry(a, "Menu casa 1")
    s2 = a.post("/api/casas", json={"name": "Casa"}).get_json()["created"]        # mismo nombre: otro identificador
    assert s1 != s2
    assert day(a) == []                                                          # la nueva casa empieza vacia
    entry(a, "Menu casa 2")
    a.put("/api/casas/active", json={"casa": s1})
    assert [e["name"] for e in day(a)] == ["Menu casa 1"]
    a.put("/api/casas/active", json={"casa": s2})
    assert [e["name"] for e in day(a)] == ["Menu casa 2"]
    assert {x["slug"] for x in a.get("/api/casas").get_json()["casas"]} == {s1, s2}


def test_copy_current_menu_into_new_casa(trio):
    a, b, c, mod = trio
    a.post("/api/foods", json={"name": "Queso de la abuela", "kcal": 300, "protein": 20, "carbs": 1, "fat": 25, "serving_g": 30, "category": "Lácteos"})
    entry(a, "Menu personal previo")
    r = a.post("/api/casas", json={"name": "Casa", "copy": True}).get_json()
    assert r["copied"]["plan_entries"] == 1
    assert [e["name"] for e in day(a)] == ["Menu personal previo"]
    assert a.get("/api/foods", query_string={"q": "abuela"}).get_json()["total"] == 1
    a.put("/api/casas/active", json={"casa": None})                           # lo personal sigue ahi
    assert [e["name"] for e in day(a)] == ["Menu personal previo"]


def test_targets_and_settings_stay_personal(trio):
    a, b, c, mod = trio
    slug = a.post("/api/casas", json={"name": "Casa"}).get_json()["created"]
    a.post("/api/casas/%s/members" % slug, json={"user": "benito"})
    b.put("/api/casas/active", json={"casa": slug})
    a.put("/api/settings", json={"n_kcal": 2750})
    b.put("/api/settings", json={"n_kcal": 1800})
    ca = a.get("/api/plan", query_string={"from": D, "to": D}).get_json()
    cb = b.get("/api/plan", query_string={"from": D, "to": D}).get_json()
    assert ca["targets"]["kcal"] == 2750 and cb["targets"]["kcal"] == 1800
    assert float(a.get("/api/settings").get_json()["n_kcal"]) == 2750
    prof = mod.app.test_client().get("/agent/nutrition/profile", headers=agent("benito")).get_json()
    assert prof["targets"]["kcal"] == 1800 and prof["casa"]["name"] == "Casa" and prof["casa"]["members"] == ["alicia", "benito"]


def test_only_owners_manage_and_membership_rules(trio):
    a, b, c, mod = trio
    slug = a.post("/api/casas", json={"name": "Casa"}).get_json()["created"]
    a.post("/api/casas/%s/members" % slug, json={"user": "benito"})
    # un miembro no administra
    assert b.post("/api/casas/%s/members" % slug, json={"user": "carmen"}).status_code == 403
    assert b.patch("/api/casas/%s" % slug, json={"name": "Robada"}).status_code == 403
    assert b.delete("/api/casas/%s" % slug).status_code == 403
    assert b.delete("/api/casas/%s/members/alicia" % slug).status_code == 403
    # quien no es de la casa ni la ve
    assert c.patch("/api/casas/%s" % slug, json={"name": "x"}).status_code == 404
    assert c.delete("/api/casas/%s/members/alicia" % slug).status_code == 404
    # nombres de usuario no validos
    assert a.post("/api/casas/%s/members" % slug, json={"user": "../etc"}).status_code == 422
    # la administradora unica no puede dejar la casa sin nadie al mando
    assert a.delete("/api/casas/%s/members/alicia" % slug).status_code == 422
    assert a.post("/api/casas/%s/members" % slug, json={"user": "alicia", "role": "member"}).status_code == 422
    # nombra a benito administrador y ya puede salir
    assert a.post("/api/casas/%s/members" % slug, json={"user": "benito", "role": "owner"}).status_code == 201
    assert a.delete("/api/casas/%s/members/alicia" % slug).status_code == 200
    assert a.get("/api/casas").get_json()["casas"] == []
    # quien sale deja de ver el menu y la casa activa
    assert day(a) == []
    # benito (ultimo) no puede salirse: tiene que eliminarla
    assert b.delete("/api/casas/%s/members/benito" % slug).status_code == 422
    assert b.patch("/api/casas/%s" % slug, json={"name": "Casa Nueva"}).status_code == 200
    assert b.get("/api/casas").get_json()["casas"][0]["name"] == "Casa Nueva"


def test_delete_moves_database_aside(trio):
    a, b, c, mod = trio
    import db
    slug = a.post("/api/casas", json={"name": "Casa"}).get_json()["created"]
    entry(a)
    assert os.path.isfile(db.casa_path(slug))
    assert a.delete("/api/casas/%s" % slug).status_code == 200
    assert not os.path.exists(db.casa_path(slug)) and os.listdir(os.path.join(db.CASAS_DIR, "_eliminadas"))
    assert a.get("/api/casas").get_json() == {"me": "alicia", "active": None, "casas": [], "known_users": ["benito", "carmen", "tester"]}
    assert day(a) == []


def test_agent_follows_casa_header_or_active_casa(trio):
    a, b, c, mod = trio
    slug = a.post("/api/casas", json={"name": "Casa"}).get_json()["created"]
    entry(a, "Menu de la casa")
    cl = mod.app.test_client()
    q = {"from": D, "to": D}
    # sin cabecera: la casa activa de la persona
    assert [e["name"] for e in cl.get("/agent/plan", query_string=q, headers=agent("alicia")).get_json()["days"][D]["entries"]] == ["Menu de la casa"]
    # con cabecera de una casa propia
    a.put("/api/casas/active", json={"casa": None})
    assert cl.get("/agent/plan", query_string=q, headers=agent("alicia")).get_json()["days"].get(D, {}).get("entries", []) == []
    assert [e["name"] for e in cl.get("/agent/plan", query_string=q, headers=agent("alicia", slug)).get_json()["days"][D]["entries"]] == ["Menu de la casa"]
    # una casa ajena o inventada se rechaza
    assert cl.get("/agent/plan", query_string=q, headers=agent("benito", slug)).status_code == 400
    assert cl.get("/agent/plan", query_string=q, headers=agent("alicia", "../x")).status_code == 400


def test_casa_jobs_run_as_requester(trio):
    a, b, c, mod = trio
    slug = a.post("/api/casas", json={"name": "Casa"}).get_json()["created"]
    a.post("/api/casas/%s/members" % slug, json={"user": "benito"})
    b.put("/api/casas/active", json={"casa": slug})
    jid = b.post("/api/nutrition/plan", json={"from": D, "to": D, "instructions": "ligero"}).get_json()["id"]
    assert a.get("/api/nutrition/plan").get_json()["jobs"][0]["id"] == jid           # toda la casa ve el trabajo
    cl = mod.app.test_client()
    job = cl.get("/agent/next?wait=0", headers=TOKEN).get_json()
    assert job["kind"] == "nplan" and job["user"] == "benito" and job["casa"] == slug and job["job_id"] == jid
    assert cl.get("/agent/next?wait=0", headers=TOKEN).status_code == 204
    # el asistente escribe en el menu de la casa, no en el personal de benito
    h = agent("benito", slug)
    r = cl.put("/agent/plan/days", headers=h, json={"reason": "menu de prueba para la casa", "days": [{"date": D, "entries": [{"slot": "lunch", "kind": "text", "label": "Arroz", "kcal": 600}]}]})
    assert r.status_code == 200, r.get_data()
    assert cl.post("/agent/nplan/%d/done" % jid, headers=h, json={"summary": "ok"}).status_code == 200
    assert [e["name"] for e in day(a)] == ["Arroz"] and [e["name"] for e in day(b)] == ["Arroz"]
    b.put("/api/casas/active", json={"casa": None})
    assert day(b) == []
    # si quien lo pidio ya no esta en la casa, no se hace en su nombre
    b.put("/api/casas/active", json={"casa": slug})
    jid2 = b.post("/api/nutrition/plan", json={"from": "2026-10-13", "to": "2026-10-13"}).get_json()["id"]
    a.delete("/api/casas/%s/members/benito" % slug)
    assert cl.get("/agent/next?wait=0", headers=TOKEN).status_code == 204
    a.get("/api/casas")
    import db
    db.use(None); db.use_casa(slug)
    try:
        assert db.one("SELECT status FROM plan_jobs WHERE id=?", (jid2,))["status"] == "error"
    finally:
        db.use(None)


def test_chat_job_carries_active_casa(trio):
    a, b, c, mod = trio
    slug = a.post("/api/casas", json={"name": "Casa"}).get_json()["created"]
    sid = a.post("/api/chat/sessions").get_json()["id"]
    a.post("/api/chat/sessions/%d/messages" % sid, json={"text": "Hazme un menu"})
    job = mod.app.test_client().get("/agent/next?wait=0", headers=TOKEN).get_json()
    assert job["kind"] == "chat" and job["user"] == "alicia" and job["casa"] == slug


def test_training_data_is_unaffected_by_casa(trio):
    a, b, c, mod = trio
    a.post("/api/casas", json={"name": "Casa"})
    r = a.post("/api/routines", json={"name": "Mi rutina", "items": []})
    assert r.status_code in (200, 201)
    assert [x["name"] for x in a.get("/api/routines").get_json()] == ["Mi rutina"]
    assert a.get("/api/settings").get_json()["n_kcal"] is not None
