"""Nutricion: alimentos (valores por 100 g), recetas, plan de comidas por dia (vistas dia/semana/mes), lista de la compra,
historial con deshacer y trabajos de planificacion del asistente. Se registra como Blueprint en app.py."""
import json
import os
import re
import secrets
import uuid
from collections import defaultdict
from datetime import date, datetime, timedelta

from flask import Blueprint, Response, abort, jsonify, request

import core
import db
from core import TrainError, jl

bp = Blueprint("nutri", __name__)
HERE = os.path.dirname(os.path.abspath(__file__))
SLOTS = ["breakfast", "snack_am", "lunch", "snack_pm", "dinner", "other"]
MAX_DAYS = 62
SLOT_ORDER = "CASE slot WHEN 'breakfast' THEN 0 WHEN 'snack_am' THEN 1 WHEN 'lunch' THEN 2 WHEN 'snack_pm' THEN 3 WHEN 'dinner' THEN 4 ELSE 5 END"
FOOD_ID_RE = re.compile(r"^[A-Za-z0-9_\-]{1,40}$")


# ---------------------------------------------------------------- utilidades

def pdate(s):
    try:
        return datetime.strptime(str(s), "%Y-%m-%d").date()
    except ValueError:
        raise TrainError("fecha no válida (AAAA-MM-DD): %r" % (s,)) from None


def drange(a, b):
    d1, d2 = pdate(a), pdate(b)
    if d2 < d1:
        d1, d2 = d2, d1
    if (d2 - d1).days >= MAX_DAYS:
        raise TrainError("el rango admite como máximo %d días" % MAX_DAYS)
    return d1, d2


def num(v, lo, hi, default=None, what="valor"):
    if v in (None, ""):
        return default
    try:
        n = float(v)
    except (TypeError, ValueError):
        raise TrainError("%s no válido: %r" % (what, v)) from None
    return round(max(lo, min(hi, n)), 2)


def r1(x):
    return round(x + 1e-9, 1)


# ---------------------------------------------------------------- alimentos

def seed_foods():
    path = os.path.join(HERE, "data", "foods.json")
    if not os.path.exists(path):
        return 0
    with open(path, encoding="utf-8") as f:
        items = json.load(f)
    n = 0
    with db.tx() as c:
        for e in items:
            if c.execute("SELECT 1 FROM foods WHERE id=?", (e["id"],)).fetchone():
                c.execute("UPDATE foods SET name=?, category=?, kcal=?, protein=?, carbs=?, fat=?, fiber=?, serving_g=? WHERE id=? AND source='lib'",
                          (e["name"], e["category"], e["kcal"], e["protein"], e["carbs"], e["fat"], e["fiber"], e["serving_g"], e["id"]))
            else:
                c.execute("INSERT INTO foods(id,name,category,kcal,protein,carbs,fat,fiber,serving_g,source,created) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                          (e["id"], e["name"], e["category"], e["kcal"], e["protein"], e["carbs"], e["fat"], e["fiber"], e["serving_g"], "lib", db.now()))
                n += 1
    return n


def food_public(r):
    return {"id": r["id"], "name": r["name"], "category": r["category"], "kcal": r["kcal"], "protein": r["protein"], "carbs": r["carbs"], "fat": r["fat"], "fiber": r["fiber"],
            "serving_g": r["serving_g"], "notes": r["notes"], "source": r["source"], "favorite": bool(r["favorite"]), "archived": bool(r["archived"])}


def search_foods(q="", category="", favorite=False, limit=60, offset=0, include_archived=False):
    where, args = [], []
    for w in re.split(r"\s+", (q or "").strip().lower())[:5]:
        if w:
            where.append("lower(name) LIKE ?")
            args.append("%" + w + "%")
    if category:
        where.append("category=?"); args.append(category)
    if favorite:
        where.append("favorite=1")
    if not include_archived:
        where.append("archived=0")
    w = (" WHERE " + " AND ".join(where)) if where else ""
    total = db.one("SELECT COUNT(*) AS n FROM foods" + w, args)["n"]
    rows = db.q("SELECT * FROM foods" + w + " ORDER BY favorite DESC, name COLLATE NOCASE LIMIT ? OFFSET ?", args + [max(1, min(200, limit)), max(0, offset)])
    cats = [r["category"] for r in db.q("SELECT DISTINCT category FROM foods WHERE archived=0 ORDER BY category")]
    return {"total": total, "items": [food_public(r) for r in rows], "categories": cats}


def get_food(fid):
    r = db.one("SELECT * FROM foods WHERE id=?", (fid,))
    return food_public(r) if r else None


def _food_fields(d, partial=False):
    out = {}
    if "name" in d or not partial:
        name = str(d.get("name") or "").strip()[:100]
        if not name:
            raise TrainError("falta el nombre del alimento")
        out["name"] = name
    for k, hi in (("kcal", 1000), ("protein", 100), ("carbs", 100), ("fat", 100), ("fiber", 100)):
        if k in d or not partial:
            out[k] = num(d.get(k), 0, hi, 0, k)
    if "serving_g" in d or not partial:
        out["serving_g"] = num(d.get("serving_g"), 1, 2000, 100, "porción")
    if "category" in d or not partial:
        out["category"] = str(d.get("category") or "Otros").strip()[:40] or "Otros"
    if "notes" in d:
        out["notes"] = str(d["notes"])[:300]
    return out


def create_food(d, source="custom"):
    f = _food_fields(d)
    fid = "c_" + secrets.token_hex(5)
    db.run("INSERT INTO foods(id,name,category,kcal,protein,carbs,fat,fiber,serving_g,notes,source,created) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
           (fid, f["name"], f["category"], f["kcal"], f["protein"], f["carbs"], f["fat"], f["fiber"], f["serving_g"], f.get("notes", ""), source, db.now()))
    return get_food(fid)


def update_food(fid, d):
    r = db.one("SELECT source FROM foods WHERE id=?", (fid,))
    if not r:
        return None
    sets, args = [], []
    if "favorite" in d:
        sets.append("favorite=?"); args.append(1 if d["favorite"] else 0)
    if "archived" in d:
        sets.append("archived=?"); args.append(1 if d["archived"] else 0)
    if "notes" in d:
        sets.append("notes=?"); args.append(str(d["notes"])[:300])
    if r["source"] == "custom":
        for k, v in _food_fields(d, partial=True).items():
            if k != "notes":
                sets.append(k + "=?"); args.append(v)
    if sets:
        db.run("UPDATE foods SET %s WHERE id=?" % ", ".join(sets), args + [fid])
    return get_food(fid)


# ---------------------------------------------------------------- recetas

def _recipe_totals(rid):
    rows = db.q("SELECT ri.food_id, ri.grams, f.name, f.kcal, f.protein, f.carbs, f.fat, f.category FROM recipe_items ri JOIN foods f ON f.id=ri.food_id WHERE ri.recipe_id=? ORDER BY ri.position", (rid,))
    tot = {"kcal": 0.0, "protein": 0.0, "carbs": 0.0, "fat": 0.0}
    for r in rows:
        for k in tot:
            tot[k] += r[k] * r["grams"] / 100.0
    return rows, tot


def recipe_public(r, full=True):
    rows, tot = _recipe_totals(r["id"])
    sv = r["servings"] or 1
    out = {"id": r["id"], "uid": r["uid"], "name": r["name"], "servings": r["servings"], "notes": r["notes"], "archived": bool(r["archived"]),
           "per_serving": {k: r1(v / sv) for k, v in tot.items()}, "n_items": len(rows)}
    if full:
        out["steps"] = r["steps"]
        out["items"] = [{"food_id": x["food_id"], "name": x["name"], "grams": x["grams"]} for x in rows]
    return out


def list_recipes(q="", include_archived=False):
    rows = db.q("SELECT * FROM recipes" + ("" if include_archived else " WHERE archived=0") + " ORDER BY name COLLATE NOCASE")
    if q:
        rows = [r for r in rows if q.lower() in r["name"].lower()]
    return [recipe_public(r, full=False) for r in rows]


def get_recipe(rid):
    r = db.one("SELECT * FROM recipes WHERE id=?", (rid,))
    return recipe_public(r) if r else None


def _recipe_items(items):
    if not isinstance(items, list) or len(items) > 40:
        raise TrainError("una receta admite hasta 40 ingredientes")
    out = []
    for it in items:
        fid = str((it or {}).get("food_id") or "")
        if not db.one("SELECT 1 AS x FROM foods WHERE id=?", (fid,)):
            raise TrainError("el alimento %r no existe (usa food_search)" % fid)
        g = num(it.get("grams"), 1, 5000, None, "gramos")
        if g is None:
            raise TrainError("faltan los gramos de %s" % fid)
        out.append((fid, g))
    return out


def save_recipe(d, rid=None):
    name = str(d.get("name") or "").strip()[:100]
    items = _recipe_items(d["items"]) if "items" in d else None
    sv = num(d.get("servings"), 0.25, 50, None, "raciones") if "servings" in d else None
    now = db.now()
    with db.tx() as c:
        if rid is None:
            if not name:
                raise TrainError("la receta necesita un nombre")
            rid = c.execute("INSERT INTO recipes(uid,name,servings,steps,notes,created,updated) VALUES(?,?,?,?,?,?,?)",
                            (str(uuid.uuid4()), name, sv or 1, str(d.get("steps") or "")[:4000], str(d.get("notes") or "")[:1000], now, now)).lastrowid
        else:
            if not c.execute("SELECT 1 FROM recipes WHERE id=?", (rid,)).fetchone():
                raise TrainError("receta no encontrada")
            if name:
                c.execute("UPDATE recipes SET name=? WHERE id=?", (name, rid))
            if sv:
                c.execute("UPDATE recipes SET servings=? WHERE id=?", (sv, rid))
            for k, lim in (("steps", 4000), ("notes", 1000)):
                if k in d:
                    c.execute("UPDATE recipes SET %s=? WHERE id=?" % k, (str(d[k])[:lim], rid))
            if "archived" in d:
                c.execute("UPDATE recipes SET archived=? WHERE id=?", (1 if d["archived"] else 0, rid))
            c.execute("UPDATE recipes SET updated=? WHERE id=?", (now, rid))
        if items is not None:
            c.execute("DELETE FROM recipe_items WHERE recipe_id=?", (rid,))
            for pos, (fid, g) in enumerate(items):
                c.execute("INSERT INTO recipe_items(recipe_id,position,food_id,grams) VALUES(?,?,?,?)", (rid, pos, fid, g))
    return get_recipe(rid)


# ---------------------------------------------------------------- plan de comidas

def targets():
    s = core.get_settings()
    out = {}
    for k, short in (("n_kcal", "kcal"), ("n_protein", "protein"), ("n_carbs", "carbs"), ("n_fat", "fat")):
        try:
            out[short] = float(s[k]) if str(s[k]).strip() else None
        except ValueError:
            out[short] = None
    return out


def _macros_for(kind, food_id, recipe_id, grams, servings, manual):
    if kind == "food":
        f = db.one("SELECT * FROM foods WHERE id=?", (food_id,))
        if not f:
            raise TrainError("el alimento %r no existe" % food_id)
        g = grams if grams is not None else f["serving_g"]
        return {k: r1(f[k] * g / 100.0) for k in ("kcal", "protein", "carbs", "fat")}, f["name"], g, None
    if kind == "recipe":
        r = db.one("SELECT * FROM recipes WHERE id=?", (recipe_id,))
        if not r:
            raise TrainError("la receta %r no existe" % recipe_id)
        _rows, tot = _recipe_totals(recipe_id)
        sv = servings if servings is not None else 1
        return {k: r1(v / (r["servings"] or 1) * sv) for k, v in tot.items()}, r["name"], None, sv
    return {k: r1(manual.get(k) or 0) for k in ("kcal", "protein", "carbs", "fat")}, None, None, None


def clean_entry(d):
    """Valida un dict de entrada de menu y devuelve las columnas a guardar (macros calculadas)."""
    if not isinstance(d, dict):
        raise TrainError("entrada no válida")
    slot = str(d.get("slot") or "")
    if slot not in SLOTS:
        raise TrainError("momento no válido %r (usa: %s)" % (slot, ", ".join(SLOTS)))
    day = pdate(d.get("date")).isoformat()
    kind = d.get("kind") or ("food" if d.get("food_id") else "recipe" if d.get("recipe_id") else "text")
    if kind not in ("food", "recipe", "text"):
        raise TrainError("tipo de entrada no válido")
    grams = num(d.get("grams"), 1, 5000, None, "gramos")
    servings = num(d.get("servings"), 0.1, 50, None, "raciones")
    manual = {k: num(d.get(k), 0, 5000 if k == "kcal" else 500, 0, k) for k in ("kcal", "protein", "carbs", "fat")}
    label = str(d.get("label") or "").strip()[:120]
    if kind == "text" and not label:
        raise TrainError("una entrada de texto necesita 'label'")
    mac, name, g, sv = _macros_for(kind, d.get("food_id"), d.get("recipe_id"), grams, servings, manual)
    if kind != "text":
        label = label if label and kind == "text" else ""
    return {"date": day, "slot": slot, "kind": kind, "food_id": d.get("food_id") if kind == "food" else None, "recipe_id": d.get("recipe_id") if kind == "recipe" else None,
            "grams": g, "servings": sv, "label": label, **mac, "done": 1 if d.get("done") else 0, "notes": str(d.get("notes") or "")[:300]}


def entry_public(r):
    name = r["label"]
    qty = ""
    if r["kind"] == "food":
        f = db.one("SELECT name, serving_g FROM foods WHERE id=?", (r["food_id"],))
        name = f["name"] if f else "(alimento borrado)"
        qty = "%g g" % r["grams"]
    elif r["kind"] == "recipe":
        rc = db.one("SELECT name FROM recipes WHERE id=?", (r["recipe_id"],))
        name = rc["name"] if rc else "(receta borrada)"
        qty = "%g ración" % r["servings"] if r["servings"] == 1 else "%g raciones" % r["servings"]
    return {"id": r["id"], "date": r["date"], "slot": r["slot"], "position": r["position"], "kind": r["kind"], "food_id": r["food_id"], "recipe_id": r["recipe_id"], "grams": r["grams"],
            "servings": r["servings"], "name": name, "qty": qty, "kcal": r["kcal"], "protein": r["protein"], "carbs": r["carbs"], "fat": r["fat"], "done": bool(r["done"]), "notes": r["notes"], "source": r["source"]}


def _insert_entry(c, e, source, position=None):
    if position is None:
        position = c.execute("SELECT COALESCE(MAX(position),-1)+1 FROM meal_entries WHERE date=? AND slot=?", (e["date"], e["slot"])).fetchone()[0]
    return c.execute("INSERT INTO meal_entries(date,slot,position,kind,food_id,recipe_id,grams,servings,label,kcal,protein,carbs,fat,done,notes,source,created) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                     (e["date"], e["slot"], position, e["kind"], e["food_id"], e["recipe_id"], e["grams"], e["servings"], e["label"], e["kcal"], e["protein"], e["carbs"], e["fat"], e["done"], e["notes"], source, db.now())).lastrowid


def plan_range(a, b):
    d1, d2 = drange(a, b)
    rows = db.q("SELECT * FROM meal_entries WHERE date>=? AND date<=? ORDER BY date, " + SLOT_ORDER + ", position, id", (d1.isoformat(), d2.isoformat()))
    days, d = {}, d1
    while d <= d2:
        days[d.isoformat()] = {"entries": [], "totals": {"kcal": 0.0, "protein": 0.0, "carbs": 0.0, "fat": 0.0}, "done": {"kcal": 0.0}}
        d += timedelta(days=1)
    for r in rows:
        day = days[r["date"]]
        day["entries"].append(entry_public(r))
        for k in day["totals"]:
            day["totals"][k] += r[k]
        if r["done"]:
            day["done"]["kcal"] += r["kcal"]
    planned = [x for x in days.values() if x["entries"]]
    for x in days.values():
        x["totals"] = {k: r1(v) for k, v in x["totals"].items()}
        x["done"]["kcal"] = r1(x["done"]["kcal"])
    n = len(planned)
    summary = {"days": len(days), "planned_days": n, "avg": {k: (r1(sum(x["totals"][k] for x in planned) / n) if n else 0) for k in ("kcal", "protein", "carbs", "fat")}}
    return {"from": d1.isoformat(), "to": d2.isoformat(), "days": days, "targets": targets(), "summary": summary, "slots": SLOTS}


def _snapshot(c, d1, d2):
    rows = [dict(r) for r in c.execute("SELECT * FROM meal_entries WHERE date>=? AND date<=? ORDER BY date, " + SLOT_ORDER + ", position, id", (d1, d2))]
    return json.dumps(rows, ensure_ascii=False)


def _log(c, source, reason, d1, d2, before):
    c.execute("INSERT INTO plan_log(created,source,reason,date_from,date_to,snapshot) VALUES(?,?,?,?,?,?)", (db.now(), source, reason[:300], d1, d2, before))
    c.execute("DELETE FROM plan_log WHERE id NOT IN (SELECT id FROM plan_log ORDER BY id DESC LIMIT 200)")


def add_entry(d, source="user"):
    e = clean_entry(d)
    with db.tx() as c:
        eid = _insert_entry(c, e, source)
        if source == "agent":
            _log(c, "agent", str(d.get("reason") or "Entrada añadida por el asistente"), e["date"], e["date"], "[]")
    return entry_public(db.one("SELECT * FROM meal_entries WHERE id=?", (eid,)))


def update_entry(eid, d):
    cur = db.one("SELECT * FROM meal_entries WHERE id=?", (eid,))
    if not cur:
        return None
    merged = {**{k: cur[k] for k in ("date", "slot", "kind", "food_id", "recipe_id", "grams", "servings", "label", "kcal", "protein", "carbs", "fat", "done", "notes")}, **d}
    e = clean_entry(merged)
    with db.tx() as c:
        c.execute("UPDATE meal_entries SET date=?,slot=?,kind=?,food_id=?,recipe_id=?,grams=?,servings=?,label=?,kcal=?,protein=?,carbs=?,fat=?,done=?,notes=? WHERE id=?",
                  (e["date"], e["slot"], e["kind"], e["food_id"], e["recipe_id"], e["grams"], e["servings"], e["label"], e["kcal"], e["protein"], e["carbs"], e["fat"], e["done"], e["notes"], eid))
    return entry_public(db.one("SELECT * FROM meal_entries WHERE id=?", (eid,)))


def delete_entry(eid):
    db.run("DELETE FROM meal_entries WHERE id=?", (eid,))


def set_days(days, source, reason):
    """Sustituye TODAS las entradas de cada dia indicado. days=[{date, entries:[...]}]. Valida antes de tocar nada y guarda el estado anterior para deshacer."""
    if not isinstance(days, list) or not days or len(days) > MAX_DAYS:
        raise TrainError("days debe ser una lista de 1 a %d días" % MAX_DAYS)
    plan, seen = [], set()
    for dd in days:
        day = pdate((dd or {}).get("date")).isoformat()
        if day in seen:
            raise TrainError("día repetido: %s" % day)
        seen.add(day)
        ents = dd.get("entries") or []
        if len(ents) > 60:
            raise TrainError("demasiadas entradas en %s" % day)
        plan.append((day, [clean_entry({**e, "date": day}) for e in ents]))
    d1, d2 = min(seen), max(seen)
    with db.tx() as c:
        before = _snapshot(c, d1, d2)
        for day, ents in plan:
            c.execute("DELETE FROM meal_entries WHERE date=?", (day,))
            for e in ents:
                _insert_entry(c, e, source)
        _log(c, source, reason, d1, d2, before)
    return {"days": len(plan), "entries": sum(len(e) for _d, e in plan)}


def clear_range(a, b, source="user", reason="Días vaciados"):
    d1, d2 = drange(a, b)
    with db.tx() as c:
        before = _snapshot(c, d1.isoformat(), d2.isoformat())
        n = c.execute("DELETE FROM meal_entries WHERE date>=? AND date<=?", (d1.isoformat(), d2.isoformat())).rowcount
        if n:
            _log(c, source, reason, d1.isoformat(), d2.isoformat(), before)
    return n


def copy_range(src_from, src_to, dst_from, overwrite=True):
    s1, s2 = drange(src_from, src_to)
    dst = pdate(dst_from)
    shift = dst - s1
    d1, d2 = dst, s2 + shift
    with db.tx() as c:
        before = _snapshot(c, d1.isoformat(), d2.isoformat())
        if overwrite:
            c.execute("DELETE FROM meal_entries WHERE date>=? AND date<=?", (d1.isoformat(), d2.isoformat()))
        rows = [dict(r) for r in c.execute("SELECT * FROM meal_entries WHERE date>=? AND date<=? ORDER BY date, " + SLOT_ORDER + ", position, id", (s1.isoformat(), s2.isoformat()))]
        for r in rows:
            e = {k: r[k] for k in ("slot", "kind", "food_id", "recipe_id", "grams", "servings", "label", "kcal", "protein", "carbs", "fat", "notes")}
            e["date"] = (pdate(r["date"]) + shift).isoformat()
            e["done"] = 0
            _insert_entry(c, e, "user", position=r["position"])
        _log(c, "user", "Copiado el plan a %s" % d1.isoformat(), d1.isoformat(), d2.isoformat(), before)
    return len(rows)


def list_log(limit=20):
    rows = db.q("SELECT id, created, source, reason, date_from, date_to FROM plan_log ORDER BY id DESC LIMIT ?", (max(1, min(100, limit)),))
    return rows


def restore_log(log_id, source="user"):
    r = db.one("SELECT * FROM plan_log WHERE id=?", (log_id,))
    if not r:
        raise TrainError("cambio no encontrado")
    old = json.loads(r["snapshot"])
    with db.tx() as c:
        before = _snapshot(c, r["date_from"], r["date_to"])
        c.execute("DELETE FROM meal_entries WHERE date>=? AND date<=?", (r["date_from"], r["date_to"]))
        for e in old:
            c.execute("INSERT INTO meal_entries(date,slot,position,kind,food_id,recipe_id,grams,servings,label,kcal,protein,carbs,fat,done,notes,source,created) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                      (e["date"], e["slot"], e["position"], e["kind"], e["food_id"], e["recipe_id"], e["grams"], e["servings"], e["label"], e["kcal"], e["protein"], e["carbs"], e["fat"], e["done"], e["notes"], e["source"], e["created"]))
        _log(c, source, "Restaurado el estado anterior al cambio #%d" % log_id, r["date_from"], r["date_to"], before)
    return {"restored": len(old), "date_from": r["date_from"], "date_to": r["date_to"]}


def shopping(a, b, only_pending=False):
    d1, d2 = drange(a, b)
    rows = db.q("SELECT * FROM meal_entries WHERE date>=? AND date<=?" + (" AND done=0" if only_pending else ""), (d1.isoformat(), d2.isoformat()))
    grams = defaultdict(float)
    text = []
    for r in rows:
        if r["kind"] == "food":
            grams[r["food_id"]] += r["grams"] or 0
        elif r["kind"] == "recipe":
            rc = db.one("SELECT servings FROM recipes WHERE id=?", (r["recipe_id"],))
            for it in db.q("SELECT food_id, grams FROM recipe_items WHERE recipe_id=?", (r["recipe_id"],)):
                grams[it["food_id"]] += it["grams"] * (r["servings"] or 1) / ((rc or {"servings": 1})["servings"] or 1)
        else:
            text.append(r["label"])
    foods = {f["id"]: f for f in db.q("SELECT id, name, category, serving_g FROM foods WHERE id IN (%s)" % ",".join("?" * len(grams)), list(grams))} if grams else {}
    items = [{"food_id": fid, "name": foods[fid]["name"], "category": foods[fid]["category"], "grams": round(g), "units": round(g / foods[fid]["serving_g"], 1) if foods[fid]["serving_g"] else None, "serving_g": foods[fid]["serving_g"]}
             for fid, g in grams.items() if fid in foods]
    items.sort(key=lambda x: (x["category"], x["name"].lower()))
    return {"from": d1.isoformat(), "to": d2.isoformat(), "items": items, "unspecified": sorted(set(text), key=str.lower)}


# ---------------------------------------------------------------- trabajos del asistente

def enqueue_plan(a, b, instructions):
    d1, d2 = drange(a, b)
    ins = str(instructions or "").strip()[:1500]
    cur = db.one("SELECT id FROM plan_jobs WHERE status IN ('queued','running') AND date_from=? AND date_to=?", (d1.isoformat(), d2.isoformat()))
    if cur:
        return cur["id"]
    return db.run("INSERT INTO plan_jobs(date_from,date_to,instructions,created) VALUES(?,?,?,?)", (d1.isoformat(), d2.isoformat(), ins, db.now())).lastrowid


def fail_stale_jobs():
    now = db.now()
    db.run("UPDATE plan_jobs SET status='error', error='Sin agente conectado', finished=? WHERE status='queued' AND created<?", (now, now - 600))
    db.run("UPDATE plan_jobs SET status='error', error='El agente no respondió a tiempo', finished=? WHERE status='running' AND started<?", (now, now - 1200))


def list_jobs(limit=8):
    fail_stale_jobs()
    return db.q("SELECT id, date_from, date_to, instructions, status, created, finished, summary, error FROM plan_jobs ORDER BY id DESC LIMIT ?", (limit,))


# ---------------------------------------------------------------- exportar / importar (se engancha en core.export_all / import_all)

def export_part():
    foods = [{"id": r["id"], "source": r["source"], "name": r["name"], "category": r["category"], "kcal": r["kcal"], "protein": r["protein"], "carbs": r["carbs"], "fat": r["fat"], "fiber": r["fiber"],
              "serving_g": r["serving_g"], "notes": r["notes"], "favorite": bool(r["favorite"]), "archived": bool(r["archived"])}
             for r in db.q("SELECT * FROM foods WHERE source='custom' OR favorite=1 OR archived=1 OR notes!=''")]
    recipes = []
    for r in db.q("SELECT * FROM recipes ORDER BY id"):
        rows = db.q("SELECT food_id, grams FROM recipe_items WHERE recipe_id=? ORDER BY position", (r["id"],))
        recipes.append({"uid": r["uid"], "name": r["name"], "servings": r["servings"], "steps": r["steps"], "notes": r["notes"], "archived": bool(r["archived"]), "items": rows})
    uid_of = {r["id"]: r["uid"] for r in db.q("SELECT id, uid FROM recipes")}
    plan = [{"date": r["date"], "slot": r["slot"], "position": r["position"], "kind": r["kind"], "food_id": r["food_id"], "recipe_uid": uid_of.get(r["recipe_id"]), "grams": r["grams"], "servings": r["servings"],
             "label": r["label"], "kcal": r["kcal"], "protein": r["protein"], "carbs": r["carbs"], "fat": r["fat"], "done": bool(r["done"]), "notes": r["notes"], "source": r["source"]}
            for r in db.q("SELECT * FROM meal_entries ORDER BY date, " + SLOT_ORDER + ", position, id")]
    return {"foods": foods, "recipes": recipes, "plan": plan}


def import_part(c, data, mode, rep):
    """Dentro de la transaccion de core.import_all."""
    for k in ("foods", "recipes", "plan"):
        if not isinstance(data.get(k, []), list) or len(data.get(k, [])) > 50000:
            raise TrainError("sección %s no válida" % k)
    if mode == "replace":
        c.execute("DELETE FROM meal_entries"); c.execute("DELETE FROM recipes"); c.execute("DELETE FROM foods WHERE source='custom'")
        c.execute("UPDATE foods SET favorite=0, archived=0, notes=''")
    rep.update({"foods": 0, "recipes": 0, "plan_entries": 0})
    for f in data.get("foods", []):
        if not isinstance(f, dict) or not FOOD_ID_RE.match(str(f.get("id", ""))):
            continue
        cur = c.execute("SELECT source FROM foods WHERE id=?", (f["id"],)).fetchone()
        try:
            if cur is None and f.get("source") == "custom":
                v = _food_fields(f)
                c.execute("INSERT INTO foods(id,name,category,kcal,protein,carbs,fat,fiber,serving_g,notes,source,favorite,archived,created) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                          (f["id"], v["name"], v["category"], v["kcal"], v["protein"], v["carbs"], v["fat"], v["fiber"], v["serving_g"], v.get("notes", ""), "custom", 1 if f.get("favorite") else 0, 1 if f.get("archived") else 0, db.now()))
                rep["foods"] += 1
            elif cur is not None:
                c.execute("UPDATE foods SET favorite=?, archived=?, notes=? WHERE id=?", (1 if f.get("favorite") else 0, 1 if f.get("archived") else 0, str(f.get("notes") or "")[:300], f["id"]))
                rep["foods"] += 1
        except TrainError:
            continue
    rid_of = {}
    for r in data.get("recipes", []):
        if not isinstance(r, dict) or not str(r.get("name") or "").strip():
            continue
        uid = str(r.get("uid") or uuid.uuid4())[:64]
        items = [(str(i.get("food_id")), num(i.get("grams"), 1, 5000, None)) for i in (r.get("items") or []) if isinstance(i, dict)]
        items = [(fid, g) for fid, g in items if g and c.execute("SELECT 1 FROM foods WHERE id=?", (fid,)).fetchone()]
        row = c.execute("SELECT id FROM recipes WHERE uid=?", (uid,)).fetchone()
        now = db.now()
        sv = num(r.get("servings"), 0.25, 50, 1)
        if row:
            rid = row["id"]
            c.execute("UPDATE recipes SET name=?, servings=?, steps=?, notes=?, archived=?, updated=? WHERE id=?", (str(r["name"])[:100], sv, str(r.get("steps") or "")[:4000], str(r.get("notes") or "")[:1000], 1 if r.get("archived") else 0, now, rid))
        else:
            rid = c.execute("INSERT INTO recipes(uid,name,servings,steps,notes,archived,created,updated) VALUES(?,?,?,?,?,?,?,?)", (uid, str(r["name"])[:100], sv, str(r.get("steps") or "")[:4000], str(r.get("notes") or "")[:1000], 1 if r.get("archived") else 0, now, now)).lastrowid
        c.execute("DELETE FROM recipe_items WHERE recipe_id=?", (rid,))
        for pos, (fid, g) in enumerate(items):
            c.execute("INSERT INTO recipe_items(recipe_id,position,food_id,grams) VALUES(?,?,?,?)", (rid, pos, fid, g))
        rid_of[uid] = rid
        rep["recipes"] += 1
    for e in data.get("plan", []):
        try:
            if not isinstance(e, dict):
                continue
            rid = rid_of.get(e.get("recipe_uid")) or (c.execute("SELECT id FROM recipes WHERE uid=?", (e.get("recipe_uid"),)).fetchone() or {"id": None})["id"] if e.get("recipe_uid") else None
            dup = c.execute("SELECT 1 FROM meal_entries WHERE date=? AND slot=? AND kind=? AND COALESCE(food_id,'')=? AND COALESCE(recipe_id,0)=? AND COALESCE(grams,0)=? AND label=?",
                            (pdate(e.get("date")).isoformat(), e.get("slot"), e.get("kind"), e.get("food_id") or "", rid or 0, e.get("grams") or 0, str(e.get("label") or ""))).fetchone()
            if dup:
                continue
            ce = clean_entry({"date": e.get("date"), "slot": e.get("slot"), "kind": e.get("kind"), "food_id": e.get("food_id"), "recipe_id": rid, "grams": e.get("grams"), "servings": e.get("servings"),
                              "label": e.get("label"), "kcal": e.get("kcal"), "protein": e.get("protein"), "carbs": e.get("carbs"), "fat": e.get("fat"), "done": e.get("done"), "notes": e.get("notes")})
            _insert_entry(c, ce, e.get("source") if e.get("source") in ("user", "agent") else "user", position=_pos(e.get("position")))
            rep["plan_entries"] += 1
        except TrainError:
            continue


def _pos(v):
    try:
        return max(0, min(200, int(v)))
    except (TypeError, ValueError):
        return 0


def plan_csv(a=None, b=None):
    import csv, io
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["fecha", "momento", "alimento_o_receta", "cantidad", "kcal", "proteina_g", "hidratos_g", "grasa_g", "hecho"])
    where, args = "", []
    if a and b:
        d1, d2 = drange(a, b)
        where, args = " WHERE date>=? AND date<=?", [d1.isoformat(), d2.isoformat()]
    for r in db.q("SELECT * FROM meal_entries" + where + " ORDER BY date, " + SLOT_ORDER + ", position, id", args):
        e = entry_public(r)
        w.writerow([e["date"], e["slot"], e["name"], e["qty"], e["kcal"], e["protein"], e["carbs"], e["fat"], "si" if e["done"] else "no"])
    return out.getvalue()


# ---------------------------------------------------------------- rutas (persona)

def _body():
    d = request.get_json(silent=True)
    if not isinstance(d, dict):
        abort(400, description="JSON esperado")
    return d


def _found(x, what):
    if x is None:
        abort(404, description="%s no encontrado" % what)
    return x


@bp.route("/api/foods", methods=["GET", "POST"])
def api_foods():
    if request.method == "POST":
        return jsonify(create_food(_body())), 201
    return jsonify(search_foods(request.args.get("q", ""), request.args.get("category", ""), request.args.get("favorite") == "1",
                                request.args.get("limit", 60, type=int), request.args.get("offset", 0, type=int)))


@bp.route("/api/foods/<fid>", methods=["GET", "PATCH", "DELETE"])
def api_food(fid):
    if request.method == "PATCH":
        return jsonify(_found(update_food(fid, _body()), "alimento"))
    if request.method == "DELETE":
        r = _found(db.one("SELECT source FROM foods WHERE id=?", (fid,)), "alimento")
        if r["source"] != "custom":
            abort(409, description="los alimentos de la biblioteca no se borran; puedes archivarlos")
        if db.one("SELECT 1 AS x FROM meal_entries WHERE food_id=?", (fid,)) or db.one("SELECT 1 AS x FROM recipe_items WHERE food_id=?", (fid,)):
            abort(409, description="el alimento está en el plan o en una receta; archívalo en su lugar")
        db.run("DELETE FROM foods WHERE id=?", (fid,))
        return jsonify({"ok": True})
    return jsonify(_found(get_food(fid), "alimento"))


@bp.route("/api/recipes", methods=["GET", "POST"])
def api_recipes():
    if request.method == "POST":
        return jsonify(save_recipe(_body())), 201
    return jsonify(list_recipes(request.args.get("q", ""), request.args.get("archived") == "1"))


@bp.route("/api/recipes/<int:rid>", methods=["GET", "PUT", "DELETE"])
def api_recipe(rid):
    _found(db.one("SELECT 1 AS x FROM recipes WHERE id=?", (rid,)), "receta")
    if request.method == "PUT":
        return jsonify(save_recipe(_body(), rid))
    if request.method == "DELETE":
        save_recipe({"archived": True}, rid)
        return jsonify({"ok": True})
    return jsonify(get_recipe(rid))


@bp.route("/api/plan")
def api_plan():
    return jsonify(plan_range(request.args.get("from", ""), request.args.get("to", "")))


@bp.route("/api/plan/entries", methods=["POST"])
def api_plan_add():
    return jsonify(add_entry(_body())), 201


@bp.route("/api/plan/entries/<int:eid>", methods=["PATCH", "DELETE"])
def api_plan_entry(eid):
    if request.method == "DELETE":
        delete_entry(eid)
        return jsonify({"ok": True})
    return jsonify(_found(update_entry(eid, _body()), "entrada"))


@bp.route("/api/plan/copy", methods=["POST"])
def api_plan_copy():
    d = _body()
    return jsonify({"copied": copy_range(d.get("from"), d.get("to") or d.get("from"), d.get("target"), d.get("overwrite", True) is not False)})


@bp.route("/api/plan/clear", methods=["POST"])
def api_plan_clear():
    d = _body()
    return jsonify({"deleted": clear_range(d.get("from"), d.get("to") or d.get("from"))})


@bp.route("/api/plan/log")
def api_plan_log():
    return jsonify(list_log(request.args.get("limit", 20, type=int)))


@bp.route("/api/plan/log/<int:lid>/restore", methods=["POST"])
def api_plan_restore(lid):
    return jsonify(restore_log(lid))


@bp.route("/api/plan/shopping")
def api_shopping():
    return jsonify(shopping(request.args.get("from", ""), request.args.get("to", ""), request.args.get("pending") == "1"))


@bp.route("/api/nutrition/plan", methods=["GET", "POST"])
def api_nplan():
    if request.method == "POST":
        d = _body()
        return jsonify({"id": enqueue_plan(d.get("from"), d.get("to"), d.get("instructions"))}), 202
    import time as _t
    return jsonify({"jobs": list_jobs(), "agent_online": _t.time() - core.AGENT_SEEN["ts"] < 60})


@bp.route("/api/export/plan.csv")
def api_plan_csv():
    return Response("﻿" + plan_csv(request.args.get("from"), request.args.get("to")), mimetype="text/csv; charset=utf-8", headers={"Content-Disposition": 'attachment; filename="menu.csv"'})


# ---------------------------------------------------------------- rutas (agente, solo ClusterIP + token)

@bp.route("/agent/nutrition/profile")
def agent_profile():
    s = core.get_settings()
    keep = ("units", "goal", "experience", "days_per_week", "equipment", "injuries", "notes", "n_kcal", "n_protein", "n_carbs", "n_fat", "n_diet", "n_allergies", "n_dislikes", "n_meals", "n_weight", "n_height", "n_age", "n_sex", "n_activity", "n_goal", "n_notes")
    return jsonify({"settings": {k: s[k] for k in keep}, "targets": targets(), "slots": SLOTS, "today": date.today().isoformat()})


@bp.route("/agent/foods")
def agent_foods():
    r = search_foods(request.args.get("q", ""), request.args.get("category", ""), False, min(40, request.args.get("limit", 15, type=int)))
    return jsonify({"total": r["total"], "items": [{k: f[k] for k in ("id", "name", "category", "kcal", "protein", "carbs", "fat", "serving_g")} for f in r["items"]], "per": "100 g"})


@bp.route("/agent/foods", methods=["POST"])
def agent_food_create():
    return jsonify(create_food(_body())), 201


@bp.route("/agent/recipes")
def agent_recipes():
    return jsonify(list_recipes(request.args.get("q", "")))


@bp.route("/agent/recipes/<int:rid>")
def agent_recipe(rid):
    return jsonify(_found(get_recipe(rid), "receta"))


@bp.route("/agent/recipes", methods=["POST"])
def agent_recipe_create():
    return jsonify(save_recipe(_body())), 201


@bp.route("/agent/recipes/<int:rid>", methods=["PUT"])
def agent_recipe_update(rid):
    _found(db.one("SELECT 1 AS x FROM recipes WHERE id=?", (rid,)), "receta")
    return jsonify(save_recipe(_body(), rid))


@bp.route("/agent/plan")
def agent_plan():
    return jsonify(plan_range(request.args.get("from", ""), request.args.get("to", "")))


@bp.route("/agent/plan/days", methods=["PUT"])
def agent_plan_days():
    d = _body()
    reason = str(d.get("reason") or "").strip()
    if len(reason) < 8:
        abort(400, description="indica el motivo del cambio en 'reason' (para que la persona pueda revisarlo)")
    return jsonify(set_days(d.get("days"), "agent", reason))


@bp.route("/agent/plan/entries", methods=["POST"])
def agent_plan_add():
    return jsonify(add_entry(_body(), "agent")), 201


@bp.route("/agent/plan/clear", methods=["POST"])
def agent_plan_clear():
    d = _body()
    return jsonify({"deleted": clear_range(d.get("from"), d.get("to") or d.get("from"), "agent", str(d.get("reason") or "Días vaciados por el asistente"))})


@bp.route("/agent/plan/log")
def agent_plan_log():
    return jsonify(list_log(request.args.get("limit", 10, type=int)))


@bp.route("/agent/plan/log/<int:lid>/restore", methods=["POST"])
def agent_plan_restore(lid):
    return jsonify(restore_log(lid, "agent"))


@bp.route("/agent/nplan/<int:jid>/done", methods=["POST"])
def agent_nplan_done(jid):
    j = _found(db.one("SELECT status FROM plan_jobs WHERE id=?", (jid,)), "trabajo")
    if j["status"] != "running":
        abort(409, description="trabajo no activo")
    d = _body()
    err = d.get("error")
    db.run("UPDATE plan_jobs SET status=?, summary=?, error=?, finished=? WHERE id=?", ("error" if err else "done", str(d.get("summary") or "")[:4000], str(err)[:500] if err else None, db.now(), jid))
    return jsonify({"ok": True})
