import json

from conftest import AG


def food(me, q):
    r = me.get("/api/foods", query_string={"q": q}).get_json()
    assert r["items"], q
    return r["items"][0]


def entry(me, date, slot, **kw):
    r = me.post("/api/plan/entries", json={"date": date, "slot": slot, **kw})
    assert r.status_code == 201, r.get_json()
    return r.get_json()


def test_requires_login(anon):
    assert anon.get("/api/foods").status_code == 401
    assert anon.get("/api/plan?from=2026-10-05&to=2026-10-11").status_code == 401
    assert anon.get("/agent/foods").status_code == 401
    assert anon.get("/agent/foods", headers=AG).status_code == 200


def test_foods_catalog_and_custom(me):
    r = me.get("/api/foods", query_string={"limit": 200}).get_json()
    assert r["total"] >= 100 and "Proteínas" in r["categories"]
    pollo = food(me, "pechuga de pollo (cocinada)")
    assert pollo["kcal"] == 165 and pollo["protein"] == 31
    # los valores cuadran con kcal (4/4/9) salvo alcohol
    for f in r["items"]:
        if f["name"] not in ("Cerveza", "Vino tinto", "Vino blanco", "Cava brut", "Vermut", "Sidra", "Pimentón de la Vera", "Vinagre de Jerez"):
            assert abs(f["protein"] * 4 + f["carbs"] * 4 + f["fat"] * 9 - f["kcal"]) <= 0.25 * f["kcal"] + 12, f["name"]
    mine = me.post("/api/foods", json={"name": "Mi barrita", "kcal": 380, "protein": 20, "carbs": 40, "fat": 14, "serving_g": 45, "category": "Otros"})
    assert mine.status_code == 201 and mine.get_json()["source"] == "custom"
    mid = mine.get_json()["id"]
    assert me.post("/api/foods", json={"name": "", "kcal": 1}).status_code == 422
    assert me.post("/api/foods", json={"name": "x", "kcal": "mucho"}).status_code == 422
    assert me.patch("/api/foods/" + mid, json={"kcal": 400, "favorite": True}).get_json()["kcal"] == 400
    assert me.patch("/api/foods/" + pollo["id"], json={"kcal": 1, "favorite": True}).get_json()["kcal"] == 165   # la biblioteca solo admite favorito/notas/archivar
    assert me.delete("/api/foods/" + pollo["id"]).status_code == 409
    assert me.delete("/api/foods/" + mid).status_code == 200


def test_recipes_totals(me):
    arroz, pollo = food(me, "arroz blanco (cocido)"), food(me, "pechuga de pollo (cocinada)")
    r = me.post("/api/recipes", json={"name": "Pollo con arroz", "servings": 2, "items": [{"food_id": arroz["id"], "grams": 360}, {"food_id": pollo["id"], "grams": 240}], "steps": "Cocer y mezclar"})
    assert r.status_code == 201
    rec = r.get_json()
    assert rec["per_serving"]["kcal"] == round((130 * 3.6 + 165 * 2.4) / 2, 1) and rec["n_items"] == 2
    up = me.put("/api/recipes/%d" % rec["id"], json={"servings": 4}).get_json()
    assert up["per_serving"]["kcal"] == round((130 * 3.6 + 165 * 2.4) / 4, 1)
    assert me.post("/api/recipes", json={"name": "mala", "items": [{"food_id": "nope", "grams": 10}]}).status_code == 422
    assert me.delete("/api/recipes/%d" % rec["id"]).status_code == 200 and [r for r in me.get("/api/recipes").get_json() if r["source"] == "user"] == []


def test_plan_entries_day_week_month(me):
    huevo, avena = food(me, "huevo entero"), food(me, "copos de avena")
    me.put("/api/settings", json={"n_kcal": 2200, "n_protein": 140, "n_carbs": 250, "n_fat": 70})
    e1 = entry(me, "2026-10-12", "breakfast", food_id=huevo["id"], grams=110)
    assert e1["kcal"] == round(143 * 1.1, 1) and e1["name"] == "Huevo entero" and e1["qty"] == "110 g" and e1["source"] == "user"
    entry(me, "2026-10-12", "breakfast", food_id=avena["id"], grams=50)
    entry(me, "2026-10-12", "lunch", kind="text", label="Menú del día", kcal=800, protein=40, carbs=90, fat=30)
    entry(me, "2026-10-14", "dinner", kind="text", label="Pizza", kcal=900)
    day = me.get("/api/plan", query_string={"from": "2026-10-12", "to": "2026-10-12"}).get_json()
    d = day["days"]["2026-10-12"]
    assert len(d["entries"]) == 3 and d["totals"]["kcal"] == round(157.3 + 194.5 + 800, 1) and day["targets"]["kcal"] == 2200
    week = me.get("/api/plan", query_string={"from": "2026-10-12", "to": "2026-10-18"}).get_json()
    assert len(week["days"]) == 7 and week["summary"]["planned_days"] == 2 and week["days"]["2026-10-13"]["entries"] == []
    month = me.get("/api/plan", query_string={"from": "2026-10-01", "to": "2026-10-31"}).get_json()
    assert len(month["days"]) == 31 and month["summary"]["avg"]["kcal"] > 0
    # editar cantidad recalcula; marcar hecho
    upd = me.patch("/api/plan/entries/%d" % e1["id"], json={"grams": 220, "done": True}).get_json()
    assert upd["kcal"] == round(143 * 2.2, 1) and upd["done"] is True
    assert me.get("/api/plan", query_string={"from": "2026-10-12", "to": "2026-10-12"}).get_json()["days"]["2026-10-12"]["done"]["kcal"] == upd["kcal"]
    assert me.delete("/api/plan/entries/%d" % e1["id"]).status_code == 200
    # validaciones
    assert me.post("/api/plan/entries", json={"date": "2026-10-12", "slot": "elevenses", "kind": "text", "label": "x"}).status_code == 422
    assert me.post("/api/plan/entries", json={"date": "12/10/2026", "slot": "lunch", "kind": "text", "label": "x"}).status_code == 422
    assert me.post("/api/plan/entries", json={"date": "2026-10-12", "slot": "lunch", "food_id": "nope"}).status_code == 422
    assert me.get("/api/plan", query_string={"from": "2026-01-01", "to": "2026-12-31"}).status_code == 422


def test_copy_clear_and_undo(me):
    pollo = food(me, "pechuga de pollo (cocinada)")
    for day in ("2026-10-12", "2026-10-13"):
        entry(me, day, "lunch", food_id=pollo["id"], grams=150)
    assert me.post("/api/plan/copy", json={"from": "2026-10-12", "to": "2026-10-13", "target": "2026-10-19"}).get_json()["copied"] == 2
    wk2 = me.get("/api/plan", query_string={"from": "2026-10-19", "to": "2026-10-20"}).get_json()
    assert all(len(d["entries"]) == 1 and not d["entries"][0]["done"] for d in wk2["days"].values())
    assert me.post("/api/plan/clear", json={"from": "2026-10-19", "to": "2026-10-20"}).get_json()["deleted"] == 2
    log = me.get("/api/plan/log").get_json()
    assert log[0]["reason"].startswith("Días vaciados") and log[0]["source"] == "user"
    me.post("/api/plan/log/%d/restore" % log[0]["id"])
    assert sum(len(d["entries"]) for d in me.get("/api/plan", query_string={"from": "2026-10-19", "to": "2026-10-20"}).get_json()["days"].values()) == 2


def test_agent_edits_with_history(me, mod):
    c = mod.app.test_client()
    pollo, arroz = food(me, "pechuga de pollo (cocinada)"), food(me, "arroz blanco (cocido)")
    entry(me, "2026-10-12", "lunch", kind="text", label="Lo de siempre", kcal=500)
    days = [{"date": "2026-10-12", "entries": [{"slot": "lunch", "food_id": pollo["id"], "grams": 150}, {"slot": "lunch", "food_id": arroz["id"], "grams": 200}, {"slot": "dinner", "kind": "text", "label": "Crema de verduras", "kcal": 200}]},
            {"date": "2026-10-13", "entries": [{"slot": "breakfast", "kind": "text", "label": "Tostada", "kcal": 250}]}]
    assert c.put("/agent/plan/days", json={"days": days}, headers=AG).status_code == 400                        # exige motivo
    ok = c.put("/agent/plan/days", json={"days": days, "reason": "Menú semanal alto en proteína"}, headers=AG)
    assert ok.status_code == 200 and ok.get_json() == {"days": 2, "entries": 4}
    plan = me.get("/api/plan", query_string={"from": "2026-10-12", "to": "2026-10-13"}).get_json()
    d12 = plan["days"]["2026-10-12"]["entries"]
    assert [e["name"] for e in d12] == ["Pechuga de pollo (cocinada)", "Arroz blanco (cocido)", "Crema de verduras"] and all(e["source"] == "agent" for e in d12)
    bad = c.put("/agent/plan/days", json={"days": [{"date": "2026-10-14", "entries": [{"slot": "lunch", "food_id": "nope", "grams": 5}]}], "reason": "Prueba inválida"}, headers=AG)
    assert bad.status_code == 422 and not me.get("/api/plan", query_string={"from": "2026-10-14", "to": "2026-10-14"}).get_json()["days"]["2026-10-14"]["entries"]
    log = c.get("/agent/plan/log", headers=AG).get_json()
    assert log[0]["source"] == "agent" and "proteína" in log[0]["reason"]
    assert me.post("/api/plan/log/%d/restore" % log[0]["id"]).get_json()["restored"] == 1
    back = me.get("/api/plan", query_string={"from": "2026-10-12", "to": "2026-10-12"}).get_json()["days"]["2026-10-12"]["entries"]
    assert [e["name"] for e in back] == ["Lo de siempre"]
    prof = c.get("/agent/nutrition/profile", headers=AG).get_json()
    assert prof["slots"][0] == "breakfast" and "n_diet" in prof["settings"]


def test_shopping_list(me):
    arroz, pollo = food(me, "arroz blanco (cocido)"), food(me, "pechuga de pollo (cocinada)")
    rec = me.post("/api/recipes", json={"name": "Bol", "servings": 2, "items": [{"food_id": arroz["id"], "grams": 300}, {"food_id": pollo["id"], "grams": 200}]}).get_json()
    entry(me, "2026-10-12", "lunch", kind="recipe", recipe_id=rec["id"], servings=1)
    entry(me, "2026-10-13", "lunch", food_id=pollo["id"], grams=150)
    entry(me, "2026-10-13", "dinner", kind="text", label="Sobras")
    sh = me.get("/api/plan/shopping", query_string={"from": "2026-10-12", "to": "2026-10-18"}).get_json()
    by = {i["name"]: i["grams"] for i in sh["items"]}
    assert by["Arroz blanco (cocido)"] == 150 and by["Pechuga de pollo (cocinada)"] == 100 + 150 and sh["unspecified"] == ["Sobras"]


def test_plan_job_for_agent(me, mod):
    jid = me.post("/api/nutrition/plan", json={"from": "2026-10-12", "to": "2026-10-18", "instructions": "sin gluten"}).get_json()["id"]
    assert me.post("/api/nutrition/plan", json={"from": "2026-10-12", "to": "2026-10-18"}).get_json()["id"] == jid
    assert me.get("/api/nutrition/plan").get_json()["jobs"][0]["status"] == "queued"
    c = mod.app.test_client()
    job = c.get("/agent/next?wait=0", headers=AG).get_json()
    assert job["kind"] == "nplan" and job["date_from"] == "2026-10-12" and job["instructions"] == "sin gluten"
    assert c.post("/agent/nplan/%d/done" % jid, json={"summary": "Menú creado"}, headers=AG).status_code == 200
    assert me.get("/api/nutrition/plan").get_json()["jobs"][0]["summary"] == "Menú creado"
    assert me.post("/api/nutrition/plan", json={"from": "2026-10-18", "to": "2026-10-12"}).status_code == 202   # rango invertido: se normaliza


def test_settings_nutrition_validation(me):
    s = me.put("/api/settings", json={"n_kcal": "2300", "n_sex": "f", "n_activity": "active", "n_goal": "lose", "n_diet": "mediterránea", "n_allergies": "frutos secos"}).get_json()
    assert s["n_kcal"] == "2300.0" and s["n_sex"] == "f"
    assert me.put("/api/settings", json={"n_kcal": 50}).status_code == 422
    assert me.put("/api/settings", json={"n_kcal": "mucho"}).status_code == 422
    assert me.put("/api/settings", json={"n_sex": "x"}).status_code == 422
    assert me.put("/api/settings", json={"n_kcal": ""}).get_json()["n_kcal"] == ""


def test_export_import_nutrition(me):
    pollo = food(me, "pechuga de pollo (cocinada)")
    mine = me.post("/api/foods", json={"name": "Mi barrita", "kcal": 380, "protein": 20, "carbs": 40, "fat": 14, "serving_g": 45}).get_json()
    rec = me.post("/api/recipes", json={"name": "Bol", "servings": 1, "items": [{"food_id": pollo["id"], "grams": 150}, {"food_id": mine["id"], "grams": 45}]}).get_json()
    entry(me, "2026-10-12", "lunch", kind="recipe", recipe_id=rec["id"], servings=1)
    entry(me, "2026-10-12", "snack_pm", food_id=mine["id"], grams=45, notes="antes de entrenar")
    me.patch("/api/foods/" + pollo["id"], json={"favorite": True})
    data = json.loads(me.get("/api/export").data)
    assert len(data["recipes"]) == 1 and len(data["plan"]) == 2 and any(f["id"] == mine["id"] for f in data["foods"])
    assert b"Bol" in me.get("/api/export/plan.csv").data
    me.post("/api/import?mode=replace", json=data)                                   # sobre sí mismo
    again = me.post("/api/import?mode=merge", json=data).get_json()
    assert again["plan_entries"] == 0 and again["recipes"] == 1                       # el plan no se duplica
    day = me.get("/api/plan", query_string={"from": "2026-10-12", "to": "2026-10-12"}).get_json()["days"]["2026-10-12"]
    assert len(day["entries"]) == 2 and day["entries"][0]["name"] == "Bol"
    assert me.get("/api/foods/" + pollo["id"]).get_json()["favorite"] is True
    assert me.get("/api/foods/" + mine["id"]).get_json()["name"] == "Mi barrita"
    bad = {"app": "homelab-training", "version": 1, "foods": [{"id": "../x", "source": "custom", "name": "z"}], "plan": [{"date": "no", "slot": "lunch", "kind": "text", "label": "x"}], "recipes": [{"name": "r", "items": [{"food_id": "nope", "grams": 5}]}]}
    out = me.post("/api/import", json=bad).get_json()
    assert out["plan_entries"] == 0 and out["foods"] == 0


def test_cook_ideas_flow(me, mod):
    day = "2026-10-20"
    assert me.post("/api/cook", json={"date": day}).status_code == 422   # sin menú no hay nada que cocinar
    pollo, arroz = food(me, "pechuga de pollo (cocinada)"), food(me, "arroz blanco (cocido)")
    entry(me, day, "lunch", kind="food", food_id=pollo["id"], grams=150)
    entry(me, day, "dinner", kind="food", food_id=arroz["id"], grams=200)
    d = me.get("/api/cook", query_string={"date": day}).get_json()
    assert {i["food_id"]: i["grams"] for i in d["foods"]["items"]} == {pollo["id"]: 150, arroz["id"]: 200} and d["ideas"] == [] and d["job"] is None
    jid = me.post("/api/cook", json={"date": day, "instructions": "rápido"}).get_json()["id"]
    assert me.post("/api/cook", json={"date": day}).get_json()["id"] == jid
    c = mod.app.test_client()
    job = c.get("/agent/next?wait=0", headers=AG).get_json()
    assert job["kind"] == "cook" and job["date"] == day and job["instructions"] == "rápido"
    ideas = [{"name": "Pollo con arroz", "servings": 2, "minutes": 25, "steps": "1. Cocina\n2. Sirve", "ingredients": [{"food_id": pollo["id"], "grams": 150}, {"food_id": arroz["id"], "grams": 200}, {"name": "Sal", "qty": "una pizca"}]}]
    assert c.put("/agent/cook/ideas", json={"date": day, "ideas": []}, headers=AG).status_code == 422
    assert c.put("/agent/cook/ideas", json={"date": day, "ideas": [{"name": "X", "ingredients": [{"food_id": "nope", "grams": 5}]}]}, headers=AG).status_code == 422
    assert c.put("/agent/cook/ideas", json={"date": day, "ideas": ideas}, headers=AG).status_code == 200
    assert c.post("/agent/cook/%d/done" % jid, json={"summary": "1 receta"}, headers=AG).status_code == 200
    d = me.get("/api/cook", query_string={"date": day}).get_json()
    i = d["ideas"][0]
    assert d["job"]["status"] == "done" and i["name"] == "Pollo con arroz" and i["per_serving"]["kcal"] > 150 and i["saved_recipe_id"] is None
    rec = me.post("/api/cook/ideas/%d/save" % i["id"]).get_json()
    assert rec["name"] == "Pollo con arroz" and len(rec["items"]) == 2 and rec["servings"] == 2     # la sal sin food_id no entra
    assert me.post("/api/cook/ideas/%d/save" % i["id"]).get_json()["id"] == rec["id"]
    # una nueva tanda conserva las ya guardadas y sustituye las demás
    c.put("/agent/cook/ideas", json={"date": day, "ideas": [{"name": "Otra", "ingredients": [{"food_id": pollo["id"], "grams": 100}]}]}, headers=AG)
    assert [x["name"] for x in me.get("/api/cook", query_string={"date": day}).get_json()["ideas"]] == ["Pollo con arroz", "Otra"]
    assert me.delete("/api/cook/ideas/%d" % i["id"]).status_code == 200


def test_season_and_local_products(me, anon):
    import json, os
    from datetime import date
    import nutri
    # biblioteca local: alimentos y recetas con temporada/origen
    cat = me.get("/api/foods", query_string={"origin": "cat", "limit": 200}).get_json()
    assert cat["total"] >= 30 and all(x["origin"] == "cat" for x in cat["items"])
    local = me.get("/api/foods", query_string={"origin": "local"}).get_json()["total"]
    assert local > cat["total"]
    calcot = me.get("/api/foods", query_string={"q": "calçots"}).get_json()["items"][0]
    assert calcot["months"] == [1, 2, 3, 12] and calcot["origin"] == "cat"
    # temporada «ahora»: depende del mes real, pero todo lo devuelto debe tenerlo marcado
    now = me.get("/api/foods", query_string={"season": "1", "limit": 200}).get_json()
    assert now["total"] > 10 and all(date.today().month in x["months"] and x["peak"] for x in now["items"])
    ag = anon.get("/agent/foods", headers=AG, query_string={"season": "1", "origin": "local"}).get_json()
    assert ag["items"] and all(x["peak"] and x["origin"] for x in ag["items"])
    # recetas de la biblioteca: macros calculados, filtros y época
    rs = me.get("/api/recipes").get_json()
    lib = [r for r in rs if r["source"] == "lib"]
    assert len(lib) >= 50 and all(r["per_serving"]["kcal"] > 50 for r in lib)
    assert {r["origin"] for r in lib} == {"cat", "es"}
    seasonal = me.get("/api/recipes", query_string={"season": "1"}).get_json()
    assert seasonal and all((not r["months"]) or date.today().month in r["months"] for r in seasonal)
    assert len(me.get("/api/recipes", query_string={"origin": "cat"}).get_json()) < len(rs)
    # la siembra es idempotente y no duplica ni pisa recetas editadas
    rid = lib[0]["id"]
    me.put("/api/recipes/%d" % rid, json={"name": "Mi versión"})
    import db
    db.use("tester")          # las llamadas directas a nutri.* necesitan base activa (en la app la fija la peticion)
    assert nutri.seed_recipes() == 0
    assert me.get("/api/recipes/%d" % rid).get_json()["name"] == "Mi versión"
    assert len(me.get("/api/recipes").get_json()) == len(rs)
    # temporada: texto para el asistente, endpoints y estación
    assert nutri.season_name(date(2026, 1, 15)) == "invierno" and nutri.season_name(date(2026, 4, 1)) == "primavera"
    assert nutri.season_name(date(2026, 7, 1)) == "verano" and nutri.season_name(date(2026, 10, 13)) == "otoño" and nutri.season_name(date(2026, 12, 21)) == "invierno"
    db.use("tester")
    t = nutri.season_text(date(2026, 1, 20))
    assert "invierno" in t and "Calçots" in t and "Gazpacho" not in t
    assert "Gazpacho andaluz" in nutri.season_text(date(2026, 7, 20))
    s = me.get("/api/season").get_json()
    assert s["season"] and s["foods"] and s["recipes"] and s["tips"]
    a = anon.get("/agent/season", headers=AG).get_json()
    assert a["text"] and anon.get("/agent/season").status_code == 401
    # ids de la biblioteca anterior intactos (los menús ya guardados siguen apuntando al mismo alimento)
    assert me.get("/api/foods/f_001").get_json()["name"] == "Pechuga de pollo (cruda)"
