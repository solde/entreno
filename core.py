"""Logica de entrenamiento: biblioteca de ejercicios, rutinas (con versiones), sesiones, estadisticas, exportar/importar."""
import base64
import json
import os
import re
import secrets
import uuid
from collections import defaultdict
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import db

HERE = os.path.dirname(os.path.abspath(__file__))
TZ = ZoneInfo(os.environ.get("TRAINING_TZ", "Europe/Madrid"))
EX_ID_RE = re.compile(r"^[A-Za-z0-9_().\-]{1,90}$")
MAX_ITEMS = 40
CATEGORIES = ["strength", "cardio", "stretching", "plyometrics", "powerlifting", "olympic weightlifting", "strongman"]
TRACKING = ("reps", "time", "cardio")
LEVELS = ("beginner", "intermediate", "expert")


AGENT_SEEN = {"ts": 0.0}


class TrainError(ValueError):
    pass


def jl(s, default=None):
    try:
        return json.loads(s)
    except (TypeError, ValueError):
        return [] if default is None else default


# ---------------------------------------------------------------- ajustes

DEFAULTS = {
    "units": "kg", "goal": "", "experience": "intermediate", "days_per_week": 3, "equipment": "", "injuries": "", "notes": "",
    "auto_adjust": "off",          # off | after (tras cada entrenamiento) | weekly
    "adjust_style": "normal",      # conservative | normal | aggressive
    "sound": "1", "vibrate": "1", "wake_lock": "1",
    # nutricion
    "n_kcal": "", "n_protein": "", "n_carbs": "", "n_fat": "", "n_diet": "", "n_allergies": "", "n_dislikes": "", "n_meals": "4",
    "n_weight": "", "n_height": "", "n_age": "", "n_sex": "", "n_activity": "moderate", "n_goal": "maintain", "n_notes": "",
}
NUM_SETTINGS = {"n_kcal": (500, 10000), "n_protein": (0, 600), "n_carbs": (0, 1500), "n_fat": (0, 600), "n_weight": (20, 400), "n_height": (80, 260), "n_age": (10, 110)}
CHOICES = {"units": ("kg", "lb"), "experience": ("beginner", "intermediate", "advanced"), "auto_adjust": ("off", "after", "weekly"),
           "adjust_style": ("conservative", "normal", "aggressive"), "sound": ("0", "1"), "vibrate": ("0", "1"), "wake_lock": ("0", "1"),
           "n_sex": ("", "m", "f"), "n_activity": ("sedentary", "light", "moderate", "active", "very_active"), "n_goal": ("lose", "maintain", "gain"), "n_meals": ("3", "4", "5", "6")}


def get_settings():
    out = {k: db.setting("s_" + k, v) for k, v in DEFAULTS.items()}
    out["days_per_week"] = int(out["days_per_week"])
    return out


def put_settings(d):
    for k, v in d.items():
        if k not in DEFAULTS:
            continue
        if k == "days_per_week":
            v = max(1, min(7, int(v)))
        elif k in CHOICES and str(v) not in CHOICES[k]:
            raise TrainError("valor no válido para %s" % k)
        elif k in NUM_SETTINGS:
            if str(v).strip() == "":
                v = ""
            else:
                try:
                    n = float(str(v).replace(",", "."))
                except ValueError:
                    raise TrainError("%s debe ser un número" % k) from None
                lo, hi = NUM_SETTINGS[k]
                if not lo <= n <= hi:
                    raise TrainError("%s fuera de rango (%s-%s)" % (k, lo, hi))
                v = round(n, 1)
        db.set_setting("s_" + k, str(v)[:1500])
    return get_settings()


# ---------------------------------------------------------------- ejercicios

def seed():
    path = os.path.join(HERE, "data", "exercises.json")
    if not os.path.exists(path):
        return 0
    with open(path, encoding="utf-8") as f:
        items = json.load(f)
    n = 0
    now = db.now()
    with db.tx() as c:
        for e in items:
            row = c.execute("SELECT 1 FROM exercises WHERE id=?", (e["id"],)).fetchone()
            if row:  # lo de la biblioteca se refresca; lo editado por la persona (name_es, media propia, favoritos…) no se toca
                c.execute("UPDATE exercises SET name=?, category=?, level=?, equipment=?, mechanic=?, force=?, primary_m=?, secondary_m=?, instructions=?, images=?, tracking=? "
                          "WHERE id=? AND source='lib'", (e["name"], e["category"], e["level"], e["equipment"], e["mechanic"], e["force"], json.dumps(e["primary"]),
                                                          json.dumps(e["secondary"]), json.dumps(e["instructions"], ensure_ascii=False), json.dumps(e["images"]), e["tracking"], e["id"]))
                continue
            c.execute("INSERT INTO exercises(id,name,name_es,category,level,equipment,mechanic,force,primary_m,secondary_m,instructions,images,tracking,source,created) "
                      "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                      (e["id"], e["name"], e.get("name_es", ""), e["category"], e["level"], e["equipment"], e["mechanic"], e["force"], json.dumps(e["primary"]),
                       json.dumps(e["secondary"]), json.dumps(e["instructions"], ensure_ascii=False), json.dumps(e["images"]), e["tracking"], "lib", now))
            n += 1
    return n


def media_of(r):
    """Lista de medios a mostrar: los de la persona si hay; si no, los de la biblioteca. Cada uno {url, kind, own}."""
    own = jl(r["user_media"])
    if own:
        return [{"url": "/media/%s/%s" % (r["id"], m["file"]), "kind": m.get("kind", "image"), "own": True, "file": m["file"]} for m in own]
    return [{"url": "/static/ex/" + rel, "kind": "image", "own": False} for rel in jl(r["images"])]


def ex_public(r, full=False):
    out = {"id": r["id"], "name": r["name"], "name_es": r["name_es"], "category": r["category"], "level": r["level"], "equipment": r["equipment"],
           "primary": jl(r["primary_m"]), "secondary": jl(r["secondary_m"]), "tracking": r["tracking"], "source": r["source"],
           "favorite": bool(r["favorite"]), "archived": bool(r["archived"]), "video_url": r["video_url"], "media": media_of(r)}
    if full:
        out.update({"instructions": jl(r["instructions"]), "mechanic": r["mechanic"], "force": r["force"], "notes": r["notes"], "has_own_media": bool(jl(r["user_media"]))})
    return out


def search_exercises(q="", muscle="", equipment="", category="", level="", favorite=False, no_media=False, tracking="", limit=60, offset=0, include_archived=False):
    where, args = [], []
    if q:
        for w in re.split(r"\s+", q.strip().lower())[:5]:
            where.append("(lower(name) LIKE ? OR lower(name_es) LIKE ?)")
            args += ["%" + w + "%"] * 2
    if muscle:
        where.append("(primary_m LIKE ? OR secondary_m LIKE ?)")
        args += ['%"' + muscle + '"%'] * 2
    for col, val in (("equipment", equipment), ("category", category), ("level", level), ("tracking", tracking)):
        if val:
            where.append(col + "=?")
            args.append(val)
    if favorite:
        where.append("favorite=1")
    if not include_archived:
        where.append("archived=0")
    if no_media:
        where.append("user_media='[]' AND images='[]'")
    w = (" WHERE " + " AND ".join(where)) if where else ""
    total = db.one("SELECT COUNT(*) AS n FROM exercises" + w, args)["n"]
    rows = db.q("SELECT * FROM exercises" + w + " ORDER BY favorite DESC, name COLLATE NOCASE LIMIT ? OFFSET ?", args + [max(1, min(200, limit)), max(0, offset)])
    return {"total": total, "items": [ex_public(r) for r in rows]}


def get_exercise(eid):
    r = db.one("SELECT * FROM exercises WHERE id=?", (eid,))
    return ex_public(r, full=True) if r else None


def meta():
    rows = db.q("SELECT category, equipment, level, primary_m FROM exercises WHERE archived=0")
    muscles, equip, cats = defaultdict(int), defaultdict(int), defaultdict(int)
    for r in rows:
        cats[r["category"]] += 1
        equip[r["equipment"]] += 1
        for m in jl(r["primary_m"]):
            muscles[m] += 1
    srt = lambda d: [{"id": k, "n": n} for k, n in sorted(d.items(), key=lambda kv: -kv[1])]
    return {"categories": srt(cats), "equipment": srt(equip), "muscles": srt(muscles), "levels": list(LEVELS), "total": len(rows),
            "without_media": db.one("SELECT COUNT(*) AS n FROM exercises WHERE user_media='[]' AND images='[]' AND archived=0")["n"]}


def _list_field(v, maxn=12):
    if isinstance(v, str):
        v = [x.strip() for x in v.split(",")]
    return [str(x).strip().lower()[:40] for x in (v or []) if str(x).strip()][:maxn]


def create_exercise(d, source="custom"):
    name = str(d.get("name") or "").strip()[:120]
    if not name:
        raise TrainError("falta el nombre del ejercicio")
    tracking = d.get("tracking", "reps")
    cat = str(d.get("category") or ("cardio" if tracking == "cardio" else "strength"))
    if tracking not in TRACKING:
        raise TrainError("tracking no válido (reps, time, cardio)")
    eid = "c_" + secrets.token_hex(6)
    ins = [str(x).strip()[:600] for x in (d.get("instructions") or []) if str(x).strip()][:20]
    db.run("INSERT INTO exercises(id,name,name_es,category,level,equipment,primary_m,secondary_m,instructions,video_url,notes,tracking,source,created) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
           (eid, name, str(d.get("name_es") or "")[:120], cat[:40], d.get("level") if d.get("level") in LEVELS else "beginner", str(d.get("equipment") or "none")[:40],
            json.dumps(_list_field(d.get("primary"))), json.dumps(_list_field(d.get("secondary"))), json.dumps(ins, ensure_ascii=False),
            _video_url(d.get("video_url")), str(d.get("notes") or "")[:1000], tracking, source, db.now()))
    return get_exercise(eid)


def _video_url(v):
    v = str(v or "").strip()
    if v and not re.match(r"^https://[^\s]{4,300}$", v):
        raise TrainError("la URL del vídeo debe empezar por https://")
    return v


def update_exercise(eid, d):
    r = db.one("SELECT * FROM exercises WHERE id=?", (eid,))
    if not r:
        return None
    sets, args = [], []
    editable = ["name_es", "video_url", "notes", "favorite", "archived"]
    if r["source"] == "custom":
        editable += ["name", "category", "level", "equipment", "tracking", "primary", "secondary", "instructions"]
    for k in editable:
        if k not in d:
            continue
        v = d[k]
        if k == "video_url":
            v = _video_url(v)
        elif k in ("favorite", "archived"):
            v = 1 if v else 0
        elif k == "tracking":
            if v not in TRACKING:
                raise TrainError("tracking no válido")
        elif k == "level":
            if v not in LEVELS:
                raise TrainError("nivel no válido")
        elif k in ("primary", "secondary"):
            k, v = k + "_m", json.dumps(_list_field(v))
        elif k == "instructions":
            v = json.dumps([str(x).strip()[:600] for x in v if str(x).strip()][:20], ensure_ascii=False)
        elif k == "name" and not str(v).strip():
            raise TrainError("el nombre no puede estar vacío")
        else:
            v = str(v)[:1000 if k == "notes" else 120]
        sets.append(k + "=?")
        args.append(v)
    if sets:
        db.run("UPDATE exercises SET %s WHERE id=?" % ", ".join(sets), args + [eid])
    return get_exercise(eid)


# ---------------------------------------------------------------- rutinas

def _int(v, lo, hi, default=None):
    if v in (None, ""):
        return default
    try:
        n = int(float(v))
    except (TypeError, ValueError):
        raise TrainError("número no válido: %r" % (v,)) from None
    return max(lo, min(hi, n))


def _flt(v, lo, hi, default=None):
    if v in (None, ""):
        return default
    try:
        n = float(v)
    except (TypeError, ValueError):
        raise TrainError("número no válido: %r" % (v,)) from None
    return round(max(lo, min(hi, n)), 2)


def clean_items(items):
    if not isinstance(items, list) or len(items) > MAX_ITEMS:
        raise TrainError("la rutina admite hasta %d ejercicios" % MAX_ITEMS)
    out = []
    for i, it in enumerate(items):
        if not isinstance(it, dict):
            raise TrainError("ejercicio %d no válido" % (i + 1))
        eid = str(it.get("exercise_id") or "")
        ex = db.one("SELECT id, tracking FROM exercises WHERE id=?", (eid,))
        if not ex:
            raise TrainError("el ejercicio %r no existe (usa la búsqueda de ejercicios)" % eid)
        rmin, rmax = _int(it.get("reps_min"), 1, 200), _int(it.get("reps_max"), 1, 200)
        if rmin and rmax and rmax < rmin:
            rmin, rmax = rmax, rmin
        row = {"exercise_id": eid, "sets": _int(it.get("sets"), 1, 30, 3), "reps_min": rmin, "reps_max": rmax or rmin,
               "weight": _flt(it.get("weight"), 0, 2000, 0), "duration_s": _int(it.get("duration_s"), 0, 14400), "distance_m": _flt(it.get("distance_m"), 0, 1000000),
               "rest_s": _int(it.get("rest_s"), 0, 1800, 90), "rest_ex_s": _int(it.get("rest_ex_s"), 0, 1800, None), "notes": str(it.get("notes") or "")[:300]}
        if row["rest_ex_s"] is None:
            row["rest_ex_s"] = max(row["rest_s"], 90) if ex["tracking"] == "reps" else row["rest_s"]
        if ex["tracking"] == "reps" and not row["reps_min"]:
            row["reps_min"] = row["reps_max"] = 10
        if ex["tracking"] != "reps" and not row["duration_s"]:
            row["duration_s"] = 600 if ex["tracking"] == "cardio" else 30
        out.append(row)
    return out


def _weekdays(v):
    if isinstance(v, str):
        v = [x for x in v.split(",") if x.strip()]
    days = sorted({int(x) for x in (v or []) if str(x).strip().isdigit() and 1 <= int(x) <= 7})
    return ",".join(str(d) for d in days)


def routine_items(rid):
    rows = db.q("SELECT ri.*, e.name, e.name_es, e.category, e.tracking, e.images, e.user_media, e.id AS eid FROM routine_items ri JOIN exercises e ON e.id=ri.exercise_id "
                "WHERE ri.routine_id=? ORDER BY ri.position", (rid,))
    out = []
    for r in rows:
        media = media_of({"id": r["eid"], "user_media": r["user_media"], "images": r["images"]})
        out.append({"id": r["id"], "position": r["position"], "exercise_id": r["exercise_id"], "name": r["name"], "name_es": r["name_es"], "category": r["category"],
                    "tracking": r["tracking"], "thumb": media[0]["url"] if media and media[0]["kind"] == "image" else None, "sets": r["sets"], "reps_min": r["reps_min"],
                    "reps_max": r["reps_max"], "weight": r["weight"], "duration_s": r["duration_s"], "distance_m": r["distance_m"], "rest_s": r["rest_s"],
                    "rest_ex_s": r["rest_ex_s"], "notes": r["notes"]})
    return out


def get_routine(rid):
    r = db.one("SELECT * FROM routines WHERE id=?", (rid,))
    if not r:
        return None
    last = db.one("SELECT MAX(started) AS t FROM sessions WHERE routine_id=? AND status='done'", (rid,))
    return {"id": r["id"], "uid": r["uid"], "name": r["name"], "notes": r["notes"], "weekdays": [int(x) for x in r["weekdays"].split(",") if x], "archived": bool(r["archived"]),
            "created": r["created"], "updated": r["updated"], "last_done": last["t"] if last else None, "items": routine_items(rid)}


def list_routines(include_archived=False):
    rows = db.q("SELECT id FROM routines" + ("" if include_archived else " WHERE archived=0") + " ORDER BY name COLLATE NOCASE")
    return [get_routine(r["id"]) for r in rows]


def _snapshot(rid):
    r = get_routine(rid)
    return json.dumps({"name": r["name"], "notes": r["notes"], "weekdays": r["weekdays"],
                       "items": [{k: i[k] for k in ("exercise_id", "sets", "reps_min", "reps_max", "weight", "duration_s", "distance_m", "rest_s", "rest_ex_s", "notes")} for i in r["items"]]},
                      ensure_ascii=False)


def _write_items(c, rid, items):
    c.execute("DELETE FROM routine_items WHERE routine_id=?", (rid,))
    for pos, it in enumerate(items):
        c.execute("INSERT INTO routine_items(routine_id,position,exercise_id,sets,reps_min,reps_max,weight,duration_s,distance_m,rest_s,rest_ex_s,notes) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                  (rid, pos, it["exercise_id"], it["sets"], it["reps_min"], it["reps_max"], it["weight"], it["duration_s"], it["distance_m"], it["rest_s"], it["rest_ex_s"], it["notes"]))


def save_routine(d, rid=None, source="user", reason=""):
    """Crea o actualiza una rutina. En actualizacion guarda antes la version anterior (revisions). Con 'items' omitido no toca los ejercicios."""
    now = db.now()
    name = str(d.get("name") or "").strip()[:100]
    items = clean_items(d["items"]) if "items" in d else None
    with db.tx() as c:
        if rid is None:
            if not name:
                raise TrainError("la rutina necesita un nombre")
            cur = c.execute("INSERT INTO routines(uid,name,notes,weekdays,created,updated) VALUES(?,?,?,?,?,?)",
                            (str(uuid.uuid4()), name, str(d.get("notes") or "")[:1500], _weekdays(d.get("weekdays")), now, now))
            rid = cur.lastrowid
            _write_items(c, rid, items or [])
            c.execute("INSERT INTO revisions(routine_id,created,source,reason,snapshot) VALUES(?,?,?,?,?)", (rid, now, source, reason or "Creada", "{}"))
        else:
            if not c.execute("SELECT 1 FROM routines WHERE id=?", (rid,)).fetchone():
                raise TrainError("rutina no encontrada")
            c.execute("INSERT INTO revisions(routine_id,created,source,reason,snapshot) VALUES(?,?,?,?,?)", (rid, now, source, reason, _snapshot_in(c, rid)))
            if name:
                c.execute("UPDATE routines SET name=? WHERE id=?", (name, rid))
            if "notes" in d:
                c.execute("UPDATE routines SET notes=? WHERE id=?", (str(d["notes"])[:1500], rid))
            if "weekdays" in d:
                c.execute("UPDATE routines SET weekdays=? WHERE id=?", (_weekdays(d["weekdays"]), rid))
            if "archived" in d:
                c.execute("UPDATE routines SET archived=? WHERE id=?", (1 if d["archived"] else 0, rid))
            if items is not None:
                _write_items(c, rid, items)
            c.execute("UPDATE routines SET updated=? WHERE id=?", (now, rid))
            c.execute("DELETE FROM revisions WHERE routine_id=? AND id NOT IN (SELECT id FROM revisions WHERE routine_id=? ORDER BY id DESC LIMIT 60)", (rid, rid))
    return get_routine(rid)


def _snapshot_in(c, rid):
    # misma foto que _snapshot pero dentro de la transaccion abierta
    r = c.execute("SELECT name, notes, weekdays FROM routines WHERE id=?", (rid,)).fetchone()
    items = [dict(x) for x in c.execute("SELECT exercise_id,sets,reps_min,reps_max,weight,duration_s,distance_m,rest_s,rest_ex_s,notes FROM routine_items WHERE routine_id=? ORDER BY position", (rid,))]
    return json.dumps({"name": r["name"], "notes": r["notes"], "weekdays": [int(x) for x in r["weekdays"].split(",") if x], "items": items}, ensure_ascii=False)


def list_revisions(rid, limit=30):
    rows = db.q("SELECT id, created, source, reason, snapshot FROM revisions WHERE routine_id=? ORDER BY id DESC LIMIT ?", (rid, limit))
    out = []
    for r in rows:
        snap = jl(r["snapshot"], {})
        out.append({"id": r["id"], "created": r["created"], "source": r["source"], "reason": r["reason"], "restorable": bool(snap), "items": len(snap.get("items", [])) if snap else None})
    return out


def restore_revision(rid, rev_id, source="user"):
    r = db.one("SELECT snapshot, created FROM revisions WHERE id=? AND routine_id=?", (rev_id, rid))
    snap = jl(r["snapshot"], {}) if r else {}
    if not snap:
        raise TrainError("esa versión no se puede restaurar")
    items = [i for i in snap.get("items", []) if db.one("SELECT 1 AS x FROM exercises WHERE id=?", (i["exercise_id"],))]
    return save_routine({"name": snap["name"], "notes": snap.get("notes", ""), "weekdays": snap.get("weekdays", []), "items": items}, rid, source, "Versión anterior restaurada")


def duplicate_routine(rid):
    r = get_routine(rid)
    if not r:
        return None
    return save_routine({"name": (r["name"] + " (copia)")[:100], "notes": r["notes"], "weekdays": [], "items": r["items"]}, None, "user", "Duplicada")


# ---------------------------------------------------------------- sesiones

def _plan_from(rid):
    r = get_routine(rid)
    plan = []
    for it in r["items"]:
        plan.append({k: it[k] for k in ("exercise_id", "name", "name_es", "tracking", "thumb", "sets", "reps_min", "reps_max", "weight", "duration_s", "distance_m", "rest_s", "rest_ex_s", "notes")})
    return r, plan


def active_session():
    r = db.one("SELECT id FROM sessions WHERE status='active' ORDER BY id DESC LIMIT 1")
    return get_session(r["id"]) if r else None


def start_session(routine_id=None):
    if active_session():
        raise TrainError("ya hay un entrenamiento en curso")
    name, plan = "Entrenamiento libre", []
    if routine_id:
        r, plan = _plan_from(routine_id) if db.one("SELECT 1 AS x FROM routines WHERE id=?", (routine_id,)) else (None, None)
        if r is None:
            raise TrainError("rutina no encontrada")
        name = r["name"]
    cur = db.run("INSERT INTO sessions(uid,routine_id,routine_name,started,plan,state) VALUES(?,?,?,?,?,?)",
                 (str(uuid.uuid4()), routine_id, name, db.now(), json.dumps(plan, ensure_ascii=False), "{}"))
    return get_session(cur.lastrowid)


def session_sets(sid):
    return db.q("SELECT id, position, exercise_id, set_no, reps, weight, duration_s, distance_m, rpe, rest_s, done_at FROM session_sets WHERE session_id=? ORDER BY done_at, id", (sid,))


def get_session(sid, with_sets=True):
    r = db.one("SELECT * FROM sessions WHERE id=?", (sid,))
    if not r:
        return None
    out = {"id": r["id"], "uid": r["uid"], "routine_id": r["routine_id"], "routine_name": r["routine_name"], "started": r["started"], "finished": r["finished"], "status": r["status"],
           "notes": r["notes"], "rating": r["rating"], "total_s": r["total_s"], "plan": jl(r["plan"]), "state": jl(r["state"], {})}
    if with_sets:
        out["sets"] = session_sets(sid)
    return out


def _check_session_active(sid):
    s = db.one("SELECT status FROM sessions WHERE id=?", (sid,))
    if not s:
        raise TrainError("entrenamiento no encontrado")
    if s["status"] != "active":
        raise TrainError("el entrenamiento ya terminó")


def add_set(sid, d):
    _check_session_active(sid)
    eid = str(d.get("exercise_id") or "")
    if not db.one("SELECT 1 AS x FROM exercises WHERE id=?", (eid,)):
        raise TrainError("ejercicio no válido")
    pos = _int(d.get("position"), 0, 200, 0)
    n = db.one("SELECT COALESCE(MAX(set_no),0)+1 AS n FROM session_sets WHERE session_id=? AND position=?", (sid, pos))["n"]
    cur = db.run("INSERT INTO session_sets(session_id,position,exercise_id,set_no,reps,weight,duration_s,distance_m,rpe,rest_s,done_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                 (sid, pos, eid, n, _int(d.get("reps"), 0, 1000), _flt(d.get("weight"), 0, 2000), _int(d.get("duration_s"), 0, 86400), _flt(d.get("distance_m"), 0, 1000000),
                  _flt(d.get("rpe"), 1, 10), _int(d.get("rest_s"), 0, 7200), db.now()))
    return db.one("SELECT * FROM session_sets WHERE id=?", (cur.lastrowid,))


def update_set(sid, set_id, d):
    sets, args = [], []
    for k, fn in (("reps", lambda v: _int(v, 0, 1000)), ("weight", lambda v: _flt(v, 0, 2000)), ("duration_s", lambda v: _int(v, 0, 86400)),
                  ("distance_m", lambda v: _flt(v, 0, 1000000)), ("rpe", lambda v: _flt(v, 1, 10)), ("rest_s", lambda v: _int(v, 0, 7200))):
        if k in d:
            sets.append(k + "=?")
            args.append(fn(d[k]))
    if sets:
        db.run("UPDATE session_sets SET %s WHERE id=? AND session_id=?" % ", ".join(sets), args + [set_id, sid])
    return db.one("SELECT * FROM session_sets WHERE id=? AND session_id=?", (set_id, sid))


def patch_session(sid, d):
    s = db.one("SELECT * FROM sessions WHERE id=?", (sid,))
    if not s:
        raise TrainError("entrenamiento no encontrado")
    if "state" in d and s["status"] == "active" and isinstance(d["state"], dict):
        db.run("UPDATE sessions SET state=? WHERE id=?", (json.dumps(d["state"])[:4000], sid))
    if "notes" in d:
        db.run("UPDATE sessions SET notes=? WHERE id=?", (str(d["notes"])[:1500], sid))
    if "rating" in d:
        db.run("UPDATE sessions SET rating=? WHERE id=?", (_int(d["rating"], 1, 5), sid))
    if "plan" in d and s["status"] == "active" and isinstance(d["plan"], list) and len(d["plan"]) <= MAX_ITEMS:
        plan = []
        for it in d["plan"]:
            if isinstance(it, dict) and db.one("SELECT 1 AS x FROM exercises WHERE id=?", (str(it.get("exercise_id")),)):
                plan.append({k: it.get(k) for k in ("exercise_id", "name", "name_es", "tracking", "thumb", "sets", "reps_min", "reps_max", "weight", "duration_s", "distance_m", "rest_s", "rest_ex_s", "notes")})
        db.run("UPDATE sessions SET plan=? WHERE id=?", (json.dumps(plan, ensure_ascii=False), sid))
    return get_session(sid)


def finish_session(sid, d, status="done"):
    _check_session_active(sid)
    now = db.now()
    s = db.one("SELECT started FROM sessions WHERE id=?", (sid,))
    total = _int(d.get("total_s"), 0, 86400, None)
    if total is None:
        total = max(0, now - s["started"])
    db.run("UPDATE sessions SET status=?, finished=?, total_s=?, notes=COALESCE(?,notes), rating=COALESCE(?,rating), state='{}' WHERE id=?",
           (status, now, total, str(d["notes"])[:1500] if "notes" in d else None, _int(d.get("rating"), 1, 5, None), sid))
    return get_session(sid)


def delete_session(sid):
    db.run("DELETE FROM sessions WHERE id=?", (sid,))


def list_sessions(limit=30, routine_id=None, before=None):
    where, args = ["status!='active'"], []
    if routine_id:
        where.append("routine_id=?"); args.append(routine_id)
    if before:
        where.append("started<?"); args.append(before)
    rows = db.q("SELECT id FROM sessions WHERE " + " AND ".join(where) + " ORDER BY started DESC LIMIT ?", args + [max(1, min(100, limit))])
    out = []
    for r in rows:
        s = get_session(r["id"], with_sets=False)
        agg = db.one("SELECT COUNT(*) AS sets, COALESCE(SUM(CASE WHEN weight>0 THEN weight*reps ELSE 0 END),0) AS volume FROM session_sets WHERE session_id=?", (r["id"],))
        s["sets_done"], s["volume"] = agg["sets"], round(agg["volume"], 1)
        s.pop("plan", None); s.pop("state", None)
        out.append(s)
    return out


# ---------------------------------------------------------------- estadisticas

def _day(ts):
    return datetime.fromtimestamp(ts, TZ).date()


def _week_start(d):
    return d - timedelta(days=d.weekday())


def est_1rm(w, r):
    return round(w * (1 + r / 30.0), 1) if w and r and 0 < r <= 12 else None


def stats(weeks=12):
    weeks = max(2, min(52, weeks))
    today = datetime.now(TZ).date()
    first_week = _week_start(today) - timedelta(weeks=weeks - 1)
    since = int(datetime.combine(first_week, datetime.min.time(), TZ).timestamp())
    sess = db.q("SELECT id, started, finished, total_s, routine_name, rating FROM sessions WHERE status='done' AND started>=? ORDER BY started", (since,))
    sets = db.q("SELECT s.started, ss.session_id, ss.exercise_id, ss.reps, ss.weight, ss.duration_s, ss.distance_m, e.category, e.tracking, e.name, e.name_es, e.primary_m, e.secondary_m "
                "FROM session_sets ss JOIN sessions s ON s.id=ss.session_id JOIN exercises e ON e.id=ss.exercise_id WHERE s.status='done' AND s.started>=?", (since,))
    wk = {first_week + timedelta(weeks=i): {"week": (first_week + timedelta(weeks=i)).isoformat(), "sessions": 0, "volume": 0.0, "time_s": 0, "sets": 0, "cardio_s": 0, "distance_m": 0.0} for i in range(weeks)}
    for s in sess:
        w = wk.get(_week_start(_day(s["started"])))
        if w:
            w["sessions"] += 1
            w["time_s"] += s["total_s"] or 0
    muscles = defaultdict(float)
    cutoff = int((datetime.now(TZ) - timedelta(days=28)).timestamp())
    for r in sets:
        w = wk.get(_week_start(_day(r["started"])))
        if not w:
            continue
        w["sets"] += 1
        if r["tracking"] == "cardio":
            w["cardio_s"] += r["duration_s"] or 0
            w["distance_m"] += r["distance_m"] or 0
        elif r["weight"] and r["reps"]:
            w["volume"] += r["weight"] * r["reps"]
        if r["started"] >= cutoff:
            for m in jl(r["primary_m"]):
                muscles[m] += 1
            for m in jl(r["secondary_m"]):
                muscles[m] += 0.5
    best = {}
    for r in db.q("SELECT s.started, ss.exercise_id, ss.reps, ss.weight, e.name, e.name_es FROM session_sets ss JOIN sessions s ON s.id=ss.session_id JOIN exercises e ON e.id=ss.exercise_id "
                  "WHERE s.status='done' AND ss.weight>0 AND ss.reps>0 AND e.tracking='reps'"):
        k = r["exercise_id"]
        e1 = est_1rm(r["weight"], r["reps"]) or r["weight"]
        if k not in best or e1 > best[k]["e1rm"]:
            best[k] = {"exercise_id": k, "name": r["name_es"] or r["name"], "weight": r["weight"], "reps": r["reps"], "e1rm": e1, "date": _day(r["started"]).isoformat(), "ts": r["started"]}
    prs = sorted(best.values(), key=lambda x: -x["ts"])[:8]
    # racha: dias consecutivos con entrenamiento (hoy puede faltar)
    days = {_day(r["started"]) for r in db.q("SELECT started FROM sessions WHERE status='done'")}
    streak, d = 0, today if today in days else today - timedelta(days=1)
    while d in days:
        streak, d = streak + 1, d - timedelta(days=1)
    week_list = [wk[k] for k in sorted(wk)]
    for w in week_list:
        w["volume"], w["distance_m"] = round(w["volume"]), round(w["distance_m"])
    total = db.one("SELECT COUNT(*) AS n, COALESCE(SUM(total_s),0) AS t FROM sessions WHERE status='done'")
    this_w, last_w = week_list[-1], week_list[-2]
    done_today = today in days
    settings = get_settings()
    nxt = None
    for r in list_routines():
        if r["weekdays"] and (today.isoweekday() in r["weekdays"]):
            nxt = {"id": r["id"], "name": r["name"], "items": len(r["items"]), "done_today": done_today}
            break
    adjustments = db.q("SELECT r.id, r.routine_id, r.created, r.reason, ro.name AS routine FROM revisions r JOIN routines ro ON ro.id=r.routine_id WHERE r.source='agent' ORDER BY r.id DESC LIMIT 8")
    return {"weeks": week_list, "this_week": this_w, "last_week": last_w, "streak_days": streak, "total_sessions": total["n"], "total_time_s": total["t"],
            "muscles": [{"muscle": m, "sets": round(v, 1)} for m, v in sorted(muscles.items(), key=lambda kv: -kv[1])], "prs": prs,
            "recent": list_sessions(8), "today": nxt, "target_days": settings["days_per_week"], "adjustments": adjustments, "units": settings["units"],
            "avg_per_week_4": round(sum(w["sessions"] for w in week_list[-4:]) / 4, 1)}


def exercise_progress(eid, limit=60):
    rows = db.q("SELECT s.started, ss.reps, ss.weight, ss.duration_s, ss.distance_m FROM session_sets ss JOIN sessions s ON s.id=ss.session_id WHERE s.status='done' AND ss.exercise_id=? ORDER BY s.started", (eid,))
    by = defaultdict(lambda: {"best_weight": 0, "best_reps": 0, "e1rm": 0, "volume": 0, "sets": 0, "duration_s": 0, "distance_m": 0})
    for r in rows:
        d = by[_day(r["started"]).isoformat()]
        d["sets"] += 1
        d["duration_s"] += r["duration_s"] or 0
        d["distance_m"] += r["distance_m"] or 0
        if r["weight"]:
            d["best_weight"] = max(d["best_weight"], r["weight"])
            d["volume"] += r["weight"] * (r["reps"] or 0)
            d["e1rm"] = max(d["e1rm"], est_1rm(r["weight"], r["reps"]) or 0)
        d["best_reps"] = max(d["best_reps"], r["reps"] or 0)
    return [dict(date=k, **{kk: (round(vv, 1) if isinstance(vv, float) else vv) for kk, vv in v.items()}) for k, v in sorted(by.items())][-limit:]


# ---------------------------------------------------------------- exportar / importar

def export_all(include_media=False):
    ex = []
    for r in db.q("SELECT * FROM exercises WHERE source='custom' OR name_es!='' OR video_url!='' OR notes!='' OR favorite=1 OR archived=1 OR user_media!='[]'"):
        item = {"id": r["id"], "source": r["source"], "name": r["name"], "name_es": r["name_es"], "category": r["category"], "level": r["level"], "equipment": r["equipment"],
                "primary": jl(r["primary_m"]), "secondary": jl(r["secondary_m"]), "instructions": jl(r["instructions"]), "tracking": r["tracking"], "video_url": r["video_url"],
                "notes": r["notes"], "favorite": bool(r["favorite"]), "archived": bool(r["archived"])}
        if include_media:
            media = []
            for m in jl(r["user_media"]):
                p = os.path.join(db.media_dir(), r["id"], m["file"])
                if os.path.isfile(p) and os.path.getsize(p) <= 8 * 2**20:
                    with open(p, "rb") as f:
                        media.append({"file": m["file"], "kind": m.get("kind", "image"), "b64": base64.b64encode(f.read()).decode()})
            item["media"] = media
        ex.append(item)
    routines = []
    for r in list_routines(include_archived=True):
        routines.append({"uid": r["uid"], "name": r["name"], "notes": r["notes"], "weekdays": r["weekdays"], "archived": r["archived"],
                         "items": [{k: i[k] for k in ("exercise_id", "sets", "reps_min", "reps_max", "weight", "duration_s", "distance_m", "rest_s", "rest_ex_s", "notes")} for i in r["items"]]})
    sessions = []
    for s in db.q("SELECT id FROM sessions WHERE status!='active' ORDER BY started"):
        full = get_session(s["id"])
        ruid = db.one("SELECT uid FROM routines WHERE id=?", (full["routine_id"],)) if full["routine_id"] else None
        sessions.append({"uid": full["uid"], "routine_uid": ruid["uid"] if ruid else None, "routine_name": full["routine_name"], "started": full["started"], "finished": full["finished"],
                         "status": full["status"], "notes": full["notes"], "rating": full["rating"], "total_s": full["total_s"], "plan": full["plan"],
                         "sets": [{k: x[k] for k in ("position", "exercise_id", "set_no", "reps", "weight", "duration_s", "distance_m", "rpe", "rest_s", "done_at")} for x in full["sets"]]})
    import nutri
    return {"app": "homelab-training", "version": 1, "exported": db.now(), "settings": get_settings(), "exercises": ex, "routines": routines, "sessions": sessions, **nutri.export_part()}


def sessions_csv():
    import csv, io
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["fecha", "rutina", "ejercicio", "serie", "reps", "peso", "duracion_s", "distancia_m", "rpe", "descanso_s"])
    for r in db.q("SELECT s.started, s.routine_name, e.name, ss.set_no, ss.reps, ss.weight, ss.duration_s, ss.distance_m, ss.rpe, ss.rest_s FROM session_sets ss JOIN sessions s ON s.id=ss.session_id "
                  "JOIN exercises e ON e.id=ss.exercise_id WHERE s.status!='active' ORDER BY s.started, ss.id"):
        w.writerow([datetime.fromtimestamp(r["started"], TZ).strftime("%Y-%m-%d %H:%M"), r["routine_name"], r["name"], r["set_no"], r["reps"], r["weight"], r["duration_s"], r["distance_m"], r["rpe"], r["rest_s"]])
    return out.getvalue()


def _sane_media_file(name):
    return bool(re.match(r"^[A-Za-z0-9_-]{6,40}\.(jpg|png|gif|webp|mp4|webm)$", str(name)))


def import_all(data, mode="merge"):
    """Valida y aplica un export. mode: merge (anade/actualiza por uid, no borra) | replace (borra rutinas, sesiones y ejercicios propios antes)."""
    if not isinstance(data, dict) or data.get("app") != "homelab-training" or data.get("version") != 1:
        raise TrainError("el archivo no es una exportación de homelab-training (versión 1)")
    if mode not in ("merge", "replace"):
        raise TrainError("modo no válido")
    rep = {"exercises": 0, "routines": 0, "sessions": 0, "skipped_items": 0, "skipped_sessions": 0}
    for key in ("exercises", "routines", "sessions"):
        if not isinstance(data.get(key, []), list) or len(data.get(key, [])) > 20000:
            raise TrainError("sección %s no válida" % key)
    with db.tx() as c:
        if mode == "replace":
            c.execute("DELETE FROM sessions"); c.execute("DELETE FROM routines"); c.execute("DELETE FROM exercises WHERE source='custom'")
            c.execute("UPDATE exercises SET video_url='', notes='', favorite=0, archived=0")
        for e in data.get("exercises", []):
            if not isinstance(e, dict) or not EX_ID_RE.match(str(e.get("id", ""))):
                continue
            eid = e["id"]
            cur = c.execute("SELECT source FROM exercises WHERE id=?", (eid,)).fetchone()
            vurl = str(e.get("video_url") or "")
            vurl = vurl if re.match(r"^https://[^\s]{4,300}$", vurl) else ""
            if cur is None and e.get("source") == "custom" and str(e.get("name") or "").strip() and e.get("tracking") in TRACKING:
                c.execute("INSERT INTO exercises(id,name,name_es,category,level,equipment,primary_m,secondary_m,instructions,video_url,notes,tracking,source,favorite,archived,created) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                          (eid, str(e["name"])[:120], str(e.get("name_es") or "")[:120], str(e.get("category") or "strength")[:40], e.get("level") if e.get("level") in LEVELS else "beginner",
                           str(e.get("equipment") or "none")[:40], json.dumps(_list_field(e.get("primary"))), json.dumps(_list_field(e.get("secondary"))),
                           json.dumps([str(x)[:600] for x in (e.get("instructions") or [])][:20], ensure_ascii=False), vurl, str(e.get("notes") or "")[:1000], e["tracking"], "custom",
                           1 if e.get("favorite") else 0, 1 if e.get("archived") else 0, db.now()))
                rep["exercises"] += 1
            elif cur is not None:
                c.execute("UPDATE exercises SET name_es=?, video_url=?, notes=?, favorite=?, archived=? WHERE id=?",
                          (str(e.get("name_es") or "")[:120], vurl, str(e.get("notes") or "")[:1000], 1 if e.get("favorite") else 0, 1 if e.get("archived") else 0, eid))
                rep["exercises"] += 1
            else:
                continue
            media = []
            for m in e.get("media") or []:
                if not isinstance(m, dict) or not _sane_media_file(m.get("file")):
                    continue
                try:
                    raw = base64.b64decode(m.get("b64", ""), validate=True)
                except ValueError:
                    continue
                if len(raw) > 8 * 2**20 or not sniff_media(raw):
                    continue
                os.makedirs(os.path.join(db.media_dir(), eid), mode=0o700, exist_ok=True)
                with open(os.path.join(db.media_dir(), eid, m["file"]), "wb") as f:
                    f.write(raw)
                media.append({"file": m["file"], "kind": sniff_media(raw)[1]})
            if media:
                c.execute("UPDATE exercises SET user_media=? WHERE id=?", (json.dumps(media), eid))
        by_uid = {}
        for r in data.get("routines", []):
            if not isinstance(r, dict) or not str(r.get("name") or "").strip():
                continue
            items = []
            for it in r.get("items") or []:
                if isinstance(it, dict) and EX_ID_RE.match(str(it.get("exercise_id", ""))) and c.execute("SELECT 1 FROM exercises WHERE id=?", (it["exercise_id"],)).fetchone():
                    items.append(it)
                else:
                    rep["skipped_items"] += 1
            uid = str(r.get("uid") or uuid.uuid4())[:64]
            try:
                items = clean_items(items)
            except TrainError:
                rep["skipped_items"] += len(items)
                items = []
            row = c.execute("SELECT id FROM routines WHERE uid=?", (uid,)).fetchone()
            now = db.now()
            if row:
                rid = row["id"]
                c.execute("UPDATE routines SET name=?, notes=?, weekdays=?, archived=?, updated=? WHERE id=?",
                          (str(r["name"])[:100], str(r.get("notes") or "")[:1500], _weekdays(r.get("weekdays")), 1 if r.get("archived") else 0, now, rid))
            else:
                rid = c.execute("INSERT INTO routines(uid,name,notes,weekdays,archived,created,updated) VALUES(?,?,?,?,?,?,?)",
                                (uid, str(r["name"])[:100], str(r.get("notes") or "")[:1500], _weekdays(r.get("weekdays")), 1 if r.get("archived") else 0, now, now)).lastrowid
            _write_items(c, rid, items)
            by_uid[uid] = rid
            rep["routines"] += 1
        for s in data.get("sessions", []):
            try:
                uid = str(s.get("uid") or "")[:64]
                if not uid or c.execute("SELECT 1 FROM sessions WHERE uid=?", (uid,)).fetchone() or s.get("status") not in ("done", "abandoned"):
                    rep["skipped_sessions"] += 1
                    continue
                rid = by_uid.get(s.get("routine_uid")) or (c.execute("SELECT id FROM routines WHERE uid=?", (s.get("routine_uid"),)).fetchone() or {"id": None})["id"] if s.get("routine_uid") else None
                sid = c.execute("INSERT INTO sessions(uid,routine_id,routine_name,started,finished,status,notes,rating,plan,total_s) VALUES(?,?,?,?,?,?,?,?,?,?)",
                                (uid, rid, str(s.get("routine_name") or "")[:100], int(s["started"]), int(s["finished"]) if s.get("finished") else None, s["status"],
                                 str(s.get("notes") or "")[:1500], _int(s.get("rating"), 1, 5), json.dumps(s.get("plan") or [])[:200000], _int(s.get("total_s"), 0, 86400, 0))).lastrowid
                for x in s.get("sets") or []:
                    if EX_ID_RE.match(str(x.get("exercise_id", ""))) and c.execute("SELECT 1 FROM exercises WHERE id=?", (x["exercise_id"],)).fetchone():
                        c.execute("INSERT INTO session_sets(session_id,position,exercise_id,set_no,reps,weight,duration_s,distance_m,rpe,rest_s,done_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                                  (sid, _int(x.get("position"), 0, 200, 0), x["exercise_id"], _int(x.get("set_no"), 1, 500, 1), _int(x.get("reps"), 0, 1000), _flt(x.get("weight"), 0, 2000),
                                   _int(x.get("duration_s"), 0, 86400), _flt(x.get("distance_m"), 0, 1000000), _flt(x.get("rpe"), 1, 10), _int(x.get("rest_s"), 0, 7200), _int(x.get("done_at"), 0, 4102444800, int(s["started"]))))
                rep["sessions"] += 1
            except (TypeError, ValueError, KeyError, TrainError):
                rep["skipped_sessions"] += 1
        import nutri
        nutri.import_part(c, data, mode, rep)
        if isinstance(data.get("settings"), dict):
            put_settings({k: v for k, v in data["settings"].items() if k in DEFAULTS})
    return rep


def sniff_media(raw):
    """(ext, kind) segun los primeros bytes, o None. Solo se aceptan imagenes y videos conocidos."""
    h = raw[:16]
    if h.startswith(b"\xff\xd8\xff"):
        return "jpg", "image"
    if h.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png", "image"
    if h[:4] == b"GIF8":
        return "gif", "image"
    if h[:4] == b"RIFF" and h[8:12] == b"WEBP":
        return "webp", "image"
    if h[4:8] == b"ftyp":
        return "mp4", "video"
    if h[:4] == b"\x1aE\xdf\xa3":
        return "webm", "video"
    return None
