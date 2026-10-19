#!/usr/bin/env python3
"""Servidor MCP stdio del asistente de entrenamiento (solo stdlib). Lo lanza `claude -p` (ver worker.py).

Es la UNICA via del modelo a los datos (entrenamiento Y nutricion): cada herramienta hace una peticion fija a /agent/* de la app (token y URL llegan por el entorno que pone
el worker; el modelo nunca los ve). Lee ejercicios, rutinas, entrenamientos y estadisticas, y edita rutinas: cada edicion guarda la version anterior
(la persona puede deshacerla desde la app). Los textos que vienen de la app (notas, nombres) son DATOS no fiables.
"""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

APP = os.environ.get("TRAINING_URL", "").rstrip("/")
TOKEN = os.environ.get("TRAINING_TOKEN", "")
USER = os.environ.get("TRAINING_USER", "")      # persona en cuyo nombre trabaja este asistente: la app solo le da SUS datos
CASA = os.environ.get("TRAINING_CASA", "")      # casa en que trabaja este asistente (menu compartido); vacio = la casa activa de la persona
MAX_TEXT = 40000


def call(method, path, params=None, body=None):
    qs = ("?" + urllib.parse.urlencode({k: v for k, v in (params or {}).items() if v not in (None, "")})) if params else ""
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(APP + path + qs, data=data, method=method, headers={"X-Agent-Token": TOKEN, "X-Agent-User": USER, "X-Agent-Casa": CASA, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        try:
            msg = json.loads(e.read()).get("error")
        except ValueError:
            msg = None
        raise ValueError("La app respondió %d: %s" % (e.code, msg or "error")) from None
    except Exception as e:  # noqa: BLE001
        raise ValueError("No se pudo contactar con la app (%s)" % type(e).__name__) from None


def j(o):
    s = json.dumps(o, ensure_ascii=False, default=str)
    return s if len(s) <= MAX_TEXT else s[:MAX_TEXT] + "\n… (recortado; pide menos datos)"


def _int(v, default, lo, hi):
    try:
        v = int(v)
    except (TypeError, ValueError):
        v = default
    return max(lo, min(hi, v))


# ---------------------------------------------------------------- lectura

def t_exercise_search(a):
    return j(call("GET", "/agent/exercises", {k: a.get(k) for k in ("q", "muscle", "category", "equipment", "level", "tracking")} | {"limit": _int(a.get("limit"), 15, 1, 40)}))


def t_exercise_get(a):
    return j(call("GET", "/agent/exercises/%s" % urllib.parse.quote(str(a.get("id", "")), safe="")))


def t_routine_list(a):
    rs = call("GET", "/agent/routines")
    return j([{"id": r["id"], "name": r["name"], "weekdays": r["weekdays"], "notes": r["notes"], "last_done": r["last_done"], "exercises": [i["name"] for i in r["items"]]} for r in rs])


def t_routine_get(a):
    return j(call("GET", "/agent/routines/%d" % _int(a.get("id"), 0, 0, 10**9)))


def t_sessions_list(a):
    return j(call("GET", "/agent/sessions", {"limit": _int(a.get("limit"), 10, 1, 40), "routine_id": a.get("routine_id")}))


def t_session_get(a):
    s = call("GET", "/agent/sessions/%d" % _int(a.get("id"), 0, 0, 10**9))
    names = {i: (p.get("name_es") or p.get("name")) for i, p in enumerate(s.get("plan") or [])}
    for x in s.get("sets", []):
        x["exercise"] = names.get(x["position"], x["exercise_id"])
    s["plan"] = [{k: p.get(k) for k in ("exercise_id", "name", "name_es", "tracking", "sets", "reps_min", "reps_max", "weight", "duration_s", "rest_s")} for p in s.get("plan") or []]
    return j(s)


def t_stats_get(a):
    return j(call("GET", "/agent/stats", {"weeks": _int(a.get("weeks"), 8, 2, 52)}))


def t_progress_get(a):
    return j(call("GET", "/agent/progress/%s" % urllib.parse.quote(str(a.get("exercise_id", "")), safe="")))


def t_profile_get(a):
    return j(call("GET", "/agent/profile"))


# ---------------------------------------------------------------- escritura (rutinas)


def t_session_update(a):
    sid = _int(a.get("id"), 0, 0, 10**9)
    before = call("GET", "/agent/sessions/%d" % sid)
    out = {"reason": str(a.get("reason") or "")[:300]}
    if len(out["reason"]) < 8:
        raise ValueError("reason (≥ 8 caracteres) es obligatorio")
    body = {k: a[k] for k in ("notes", "rating") if k in a}
    if body:
        call("PATCH", "/agent/sessions/%d" % sid, body=body)
        out["session_before"] = {k: before.get(k) for k in body}
    changes = []
    for ch in a.get("sets") or []:
        if ch.get("delete"):
            old = next((x for x in before.get("sets", []) if x["id"] == ch.get("id")), None)
            call("DELETE", "/agent/sessions/%d/sets/%d" % (sid, _int(ch.get("id"), 0, 0, 10**9)))
            changes.append({"deleted": old})
            continue
        f = {k: ch[k] for k in ("reps", "weight", "duration_s", "distance_m", "rpe", "rest_s") if k in ch}
        if ch.get("id"):
            old = next((x for x in before.get("sets", []) if x["id"] == ch["id"]), None)
            call("PATCH", "/agent/sessions/%d/sets/%d" % (sid, _int(ch["id"], 0, 0, 10**9)), body=f)
            changes.append({"updated": ch["id"], "before": {k: (old or {}).get(k) for k in f}})
        else:
            r = call("POST", "/agent/sessions/%d/sets" % sid, body=dict(f, exercise_id=ch.get("exercise_id"), position=ch.get("position", 0)))
            changes.append({"added": r.get("id")})
    out["sets"] = changes
    return j(out)

ITEM_KEYS = ("exercise_id", "sets", "reps_min", "reps_max", "weight", "duration_s", "distance_m", "rest_s", "rest_ex_s", "notes")


def _items(v):
    if not isinstance(v, list):
        raise ValueError("items debe ser una lista de ejercicios")
    return [{k: it.get(k) for k in ITEM_KEYS if k in it} for it in v if isinstance(it, dict)]


def t_routine_create(a):
    body = {"name": a.get("name"), "notes": a.get("notes") or "", "weekdays": a.get("weekdays") or [], "items": _items(a.get("items") or []), "reason": a.get("reason") or "Creada por el asistente"}
    r = call("POST", "/agent/routines", body=body)
    return "Rutina «%s» creada (id %d) con %d ejercicios." % (r["name"], r["id"], len(r["items"]))


def t_routine_update(a):
    rid = _int(a.get("id"), 0, 0, 10**9)
    body = {"reason": str(a.get("reason") or "")}
    for k in ("name", "notes", "weekdays"):
        if k in a:
            body[k] = a[k]
    if "items" in a:
        body["items"] = _items(a["items"])
    r = call("PUT", "/agent/routines/%d" % rid, body=body)
    return "Rutina «%s» actualizada (%d ejercicios). La versión anterior quedó guardada en su historial." % (r["name"], len(r["items"]))


def t_routine_restore(a):
    r = call("POST", "/agent/routines/%d/restore/%d" % (_int(a.get("id"), 0, 0, 10**9), _int(a.get("revision_id"), 0, 0, 10**9)))
    return "Rutina «%s» restaurada." % r["name"]


def t_routine_archive(a):
    call("DELETE", "/agent/routines/%d" % _int(a.get("id"), 0, 0, 10**9), body={"reason": a.get("reason") or "Archivada por el asistente"})
    return "Rutina archivada (la persona puede recuperarla desde el historial)."


def t_exercise_create(a):
    keys = ("name", "name_es", "tracking", "category", "equipment", "level", "primary", "secondary", "instructions", "video_url", "notes")
    r = call("POST", "/agent/exercises", body={k: a.get(k) for k in keys if k in a})
    return "Ejercicio «%s» creado (id %s). La persona puede añadirle imágenes o vídeos desde Ejercicios." % (r["name"], r["id"])


# ---------------------------------------------------------------- nutricion

def t_nutrition_profile(a):
    return j(call("GET", "/agent/nutrition/profile"))


def t_food_search(a):
    return j(call("GET", "/agent/foods", {"q": a.get("q"), "category": a.get("category"), "limit": _int(a.get("limit"), 15, 1, 40),
                                          "season": "1" if a.get("season") else None, "origin": a.get("origin")}))


def t_food_create(a):
    keys = ("name", "category", "kcal", "protein", "carbs", "fat", "fiber", "serving_g", "notes")
    r = call("POST", "/agent/foods", body={k: a.get(k) for k in keys if k in a})
    return "Alimento «%s» creado (id %s, valores por 100 g)." % (r["name"], r["id"])


def t_recipe_list(a):
    return j(call("GET", "/agent/recipes", {"q": a.get("q"), "season": "1" if a.get("season") else None, "origin": a.get("origin")}))


def t_recipe_get(a):
    return j(call("GET", "/agent/recipes/%d" % _int(a.get("id"), 0, 0, 10**9)))


def t_recipe_save(a):
    body = {k: a[k] for k in ("name", "servings", "steps", "notes", "months") if k in a}
    if "items" in a:
        body["items"] = [{"food_id": i.get("food_id"), "grams": i.get("grams")} for i in a["items"] if isinstance(i, dict)]
    if a.get("id"):
        r = call("PUT", "/agent/recipes/%d" % _int(a.get("id"), 0, 0, 10**9), body=body)
        return "Receta «%s» actualizada (%s kcal por ración)." % (r["name"], r["per_serving"]["kcal"])
    r = call("POST", "/agent/recipes", body=body)
    return "Receta «%s» creada (id %d, %s kcal por ración)." % (r["name"], r["id"], r["per_serving"]["kcal"])


def t_cook_ideas_set(a):
    ideas = []
    for i in (a.get("ideas") or []):
        if isinstance(i, dict):
            ideas.append({k: i.get(k) for k in ("name", "servings", "minutes", "steps", "notes")} | {"ingredients": [{k: x.get(k) for k in ("food_id", "name", "grams", "qty") if k in x} for x in (i.get("ingredients") or []) if isinstance(x, dict)]})
    r = call("PUT", "/agent/cook/ideas", body={"date": a.get("date"), "ideas": ideas})
    return "Guardadas %d ideas de receta para %s. La persona las verá en la sección Cocinar." % (r["saved"], a.get("date"))


def t_plan_get(a):
    r = call("GET", "/agent/plan", {"from": a.get("from"), "to": a.get("to")})
    for d in r["days"].values():
        d["entries"] = [{k: e[k] for k in ("id", "slot", "name", "qty", "kcal", "protein", "carbs", "fat", "done", "notes", "source")} for e in d["entries"]]
    return j(r)


ENTRY_KEYS = ("slot", "kind", "food_id", "recipe_id", "grams", "servings", "label", "kcal", "protein", "carbs", "fat", "notes")


def _entries(v):
    if not isinstance(v, list):
        raise ValueError("entries debe ser una lista")
    return [{k: e.get(k) for k in ENTRY_KEYS if k in e} for e in v if isinstance(e, dict)]


def t_plan_set_days(a):
    days = [{"date": d.get("date"), "entries": _entries(d.get("entries") or [])} for d in (a.get("days") or []) if isinstance(d, dict)]
    r = call("PUT", "/agent/plan/days", body={"days": days, "reason": str(a.get("reason") or "")})
    return "Menú guardado: %d días, %d entradas. El estado anterior quedó en el historial y la persona puede deshacerlo." % (r["days"], r["entries"])


def t_plan_add_entry(a):
    body = {k: a.get(k) for k in ("date",) + ENTRY_KEYS + ("reason",) if k in a}
    r = call("POST", "/agent/plan/entries", body=body)
    return "Añadido a %s (%s): %s %s — %s kcal." % (r["date"], r["slot"], r["name"], r["qty"], r["kcal"])


def t_plan_clear(a):
    r = call("POST", "/agent/plan/clear", body={"from": a.get("from"), "to": a.get("to") or a.get("from"), "reason": a.get("reason") or "Días vaciados por el asistente"})
    return "Se vaciaron %d entradas (recuperables desde el historial)." % r["deleted"]


def t_plan_log(a):
    return j(call("GET", "/agent/plan/log", {"limit": _int(a.get("limit"), 10, 1, 50)}))


def t_plan_restore(a):
    r = call("POST", "/agent/plan/log/%d/restore" % _int(a.get("log_id"), 0, 0, 10**9))
    return "Restaurado el plan de %s a %s." % (r["date_from"], r["date_to"])


S = lambda **p: {"type": "object", "properties": p}  # noqa: E731
STR, INT, NUM = {"type": "string"}, {"type": "integer"}, {"type": "number"}
BOOL = {"type": "boolean"}
ITEM = {"type": "object", "description": "Un ejercicio de la rutina", "properties": {
    "exercise_id": {"type": "string", "description": "id exacto de exercise_search"}, "sets": INT, "reps_min": INT, "reps_max": INT, "weight": {"type": "number", "description": "peso por serie en la unidad del perfil"},
    "duration_s": {"type": "integer", "description": "segundos por serie/bloque (ejercicios por tiempo y cardio)"}, "distance_m": NUM, "rest_s": {"type": "integer", "description": "descanso entre series (s)"},
    "rest_ex_s": {"type": "integer", "description": "descanso al terminar el ejercicio (s)"}, "notes": STR}, "required": ["exercise_id"]}
ITEMS = {"type": "array", "items": ITEM, "description": "Lista COMPLETA y ordenada de ejercicios (sustituye a la actual)"}
TOOLS = {
    "exercise_search": (t_exercise_search, {"description": "Busca en la base de ejercicios (fuerza, cardio, estiramientos…). Filtros: q (nombre en español o inglés), muscle (p. ej. chest, quadriceps, lats), category (strength, cardio, stretching, plyometrics, powerlifting, olympic weightlifting, strongman), equipment (barbell, dumbbell, body only, machine, cable, kettlebells, bands, other, none), level (beginner, intermediate, expert), tracking (reps, time, cardio).", "inputSchema": S(q=STR, muscle=STR, category=STR, equipment=STR, level=STR, tracking=STR, limit=INT)}),
    "exercise_get": (t_exercise_get, {"description": "Detalle de un ejercicio (instrucciones, músculos, material, cómo se registra).", "inputSchema": S(id=STR)}),
    "routine_list": (t_routine_list, {"description": "Lista las rutinas de la persona (id, nombre, días, ejercicios).", "inputSchema": S()}),
    "routine_get": (t_routine_get, {"description": "Rutina completa con cada ejercicio (series, reps, peso, duración, descansos) y sus últimas versiones.", "inputSchema": S(id=INT)}),
    "sessions_list": (t_sessions_list, {"description": "Últimos entrenamientos terminados (fecha, rutina, duración, series, volumen, valoración). Filtra por routine_id.", "inputSchema": S(limit=INT, routine_id=INT)}),
    "session_get": (t_session_get, {"description": "Un entrenamiento con TODAS sus series reales (reps, peso, duración, distancia, RPE, descanso) y el plan que se siguió.", "inputSchema": S(id=INT)}),
    "stats_get": (t_stats_get, {"description": "Estadísticas por semana (sesiones, tiempo, volumen, cardio), músculos trabajados, récords, racha, constancia y ajustes previos del asistente.", "inputSchema": S(weeks=INT)}),
    "progress_get": (t_progress_get, {"description": "Evolución de un ejercicio por día (mejor peso, mejores reps, 1RM estimado, volumen, duración).", "inputSchema": S(exercise_id=STR)}),
    "profile_get": (t_profile_get, {"description": "Perfil de la persona (objetivo, experiencia, días por semana, material, lesiones, notas, unidades, estilo de progresión) y resumen reciente.", "inputSchema": S()}),
    "nutrition_profile": (t_nutrition_profile, {"description": "Perfil nutricional de la persona: objetivos diarios (kcal, proteína, hidratos, grasa), dieta, alergias, alimentos que no le gustan, comidas al día, peso/altura/edad, actividad y objetivo.", "inputSchema": S()}),
    "food_search": (t_food_search, {"description": "Busca alimentos de la base (valores por 100 g: kcal, proteína, hidratos, grasa) por nombre en español. Incluye productos locales de España y Cataluña (origin cat/es) con sus meses de temporada (months; peak=true = de temporada este mes). season=true devuelve solo los frescos de temporada ahora; origin=local|cat|es filtra por producto local. Usa SOLO ids reales para planificar.", "inputSchema": S(season=BOOL, origin=STR, q=STR, category=STR, limit=INT)}),
    "food_create": (t_food_create, {"description": "Crea un alimento propio si no existe (valores por 100 g).", "inputSchema": S(name=STR, category=STR, kcal=NUM, protein=NUM, carbs=NUM, fat=NUM, fiber=NUM, serving_g=NUM)}),
    "recipe_list": (t_recipe_list, {"description": "Lista las recetas guardadas, incluida la biblioteca de recetas tradicionales de España y Cataluña (macros por ración, meses ideales en months, peak=true si son de esta época). season=true: solo las de la época actual y las de todo el año; origin: cat | es | local.", "inputSchema": S(q=STR, season=BOOL, origin=STR)}),
    "recipe_get": (t_recipe_get, {"description": "Receta con ingredientes, pasos y macros por ración.", "inputSchema": S(id=INT)}),
    "recipe_save": (t_recipe_save, {"description": "Crea una receta (sin id) o actualiza una (con id). items = [{food_id, grams}] del total de la receta; servings = raciones que salen.", "inputSchema": S(id=INT, name=STR, servings=NUM, steps=STR, notes=STR, items={"type": "array", "items": {"type": "object", "properties": {"food_id": STR, "grams": NUM}, "required": ["food_id", "grams"]}})}),
    "cook_ideas_set": (t_cook_ideas_set, {"description": "Guarda 1-3 ideas de receta para un día (sustituye las ideas anteriores de ese día que la persona no haya guardado). Cada idea: name, servings, minutes, steps (texto numerado), notes y ingredients [{food_id, grams}] con ids REALES de food_search; para sal, especias o aceite en cantidad libre usa {name, qty} sin food_id.", "inputSchema": S(date=STR, ideas={"type": "array", "items": {"type": "object", "properties": {"name": STR, "servings": NUM, "minutes": INT, "steps": STR, "notes": STR, "ingredients": {"type": "array", "items": {"type": "object", "properties": {"food_id": STR, "name": STR, "grams": NUM, "qty": STR}}}}, "required": ["name", "ingredients"]}})}),
    "plan_get": (t_plan_get, {"description": "Menú entre dos fechas (AAAA-MM-DD, máx. 62 días): entradas por día y momento, totales diarios y objetivos.", "inputSchema": S(**{"from": STR, "to": STR})}),
    "plan_set_days": (t_plan_set_days, {"description": "SUSTITUYE todas las entradas de cada día indicado (no toques días que no quieras cambiar). Cada entrada: slot (breakfast, snack_am, lunch, snack_pm, dinner, other) y food_id+grams, recipe_id+servings, o kind=text con label y macros. reason obligatorio (≥ 8 caracteres). El estado anterior se guarda y se puede deshacer.", "inputSchema": S(days={"type": "array", "items": {"type": "object", "properties": {"date": STR, "entries": {"type": "array", "items": {"type": "object", "properties": {"slot": STR, "kind": STR, "food_id": STR, "recipe_id": INT, "grams": NUM, "servings": NUM, "label": STR, "kcal": NUM, "protein": NUM, "carbs": NUM, "fat": NUM, "notes": STR}, "required": ["slot"]}}}, "required": ["date", "entries"]}}, reason=STR)}),
    "plan_add_entry": (t_plan_add_entry, {"description": "Añade UNA entrada a un día sin tocar el resto.", "inputSchema": S(date=STR, slot=STR, kind=STR, food_id=STR, recipe_id=INT, grams=NUM, servings=NUM, label=STR, kcal=NUM, protein=NUM, carbs=NUM, fat=NUM, notes=STR, reason=STR)}),
    "plan_clear": (t_plan_clear, {"description": "Vacía un rango de días del menú. Pídelo solo si la persona lo ha pedido. Recuperable desde el historial.", "inputSchema": S(**{"from": STR, "to": STR, "reason": STR})}),
    "plan_log": (t_plan_log, {"description": "Historial de cambios del menú (id, fecha, quién, motivo, rango).", "inputSchema": S(limit=INT)}),
    "plan_restore": (t_plan_restore, {"description": "Deshace un cambio del historial (log_id de plan_log).", "inputSchema": S(log_id=INT)}),
    "session_update": (t_session_update, {"description": "Corrige un entrenamiento YA registrado (terminado). notes/rating de la sesión y en sets una lista de cambios: {id, reps, weight, duration_s, distance_m, rpe, rest_s} edita una serie (ids de session_get); {id, delete:true} la borra; {exercise_id, position, reps, weight…} añade una (position = índice del ejercicio en el plan). Úsalo solo si la persona lo pide; reason (≥ 8 caracteres) obligatorio. Devuelve los valores anteriores por si hay que revertir.", "inputSchema": S(id=INT, notes=STR, rating=INT, reason=STR, sets={"type": "array", "items": {"type": "object"}})}),
    "routine_create": (t_routine_create, {"description": "Crea una rutina nueva. Usa ids reales de exercise_search. Indica el motivo en reason.", "inputSchema": S(name=STR, notes=STR, weekdays={"type": "array", "items": INT, "description": "1=lunes … 7=domingo"}, items=ITEMS, reason=STR)}),
    "routine_update": (t_routine_update, {"description": "Edita una rutina. Para cambiar ejercicios/series/pesos envía la lista COMPLETA en items (con los cambios). reason (obligatorio, ≥ 8 caracteres) explica el cambio a la persona. La versión anterior se guarda y se puede restaurar.", "inputSchema": S(id=INT, name=STR, notes=STR, weekdays={"type": "array", "items": INT}, items=ITEMS, reason=STR)}),
    "routine_restore": (t_routine_restore, {"description": "Restaura una versión anterior de la rutina (revision_id sale de routine_get).", "inputSchema": S(id=INT, revision_id=INT)}),
    "routine_archive": (t_routine_archive, {"description": "Archiva una rutina. Pídelo solo si la persona lo ha pedido claramente.", "inputSchema": S(id=INT, reason=STR)}),
    "exercise_create": (t_exercise_create, {"description": "Crea un ejercicio propio si no existe en la base. tracking: reps | time | cardio.", "inputSchema": S(name=STR, name_es=STR, tracking=STR, category=STR, equipment=STR, level=STR, primary={"type": "array", "items": STR}, instructions={"type": "array", "items": STR})}),
}


def send(msg):
    sys.stdout.write(json.dumps(msg, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def handle(m):
    mid, method = m.get("id"), m.get("method")
    if method == "initialize":
        send({"jsonrpc": "2.0", "id": mid, "result": {"protocolVersion": (m.get("params") or {}).get("protocolVersion", "2024-11-05"), "capabilities": {"tools": {}}, "serverInfo": {"name": "training", "version": "1.0"}}})
    elif method == "ping":
        send({"jsonrpc": "2.0", "id": mid, "result": {}})
    elif method == "tools/list":
        send({"jsonrpc": "2.0", "id": mid, "result": {"tools": [dict(name=n, **spec) for n, (_f, spec) in TOOLS.items()]}})
    elif method == "tools/call":
        p = m.get("params") or {}
        entry = TOOLS.get(p.get("name"))
        if not entry:
            send({"jsonrpc": "2.0", "id": mid, "error": {"code": -32602, "message": "tool desconocida"}})
            return
        try:
            text, is_err = entry[0](p.get("arguments") or {}), False
        except ValueError as e:
            text, is_err = "Error: %s" % e, True
        except Exception as e:  # noqa: BLE001
            text, is_err = "Error interno: %s" % type(e).__name__, True
        send({"jsonrpc": "2.0", "id": mid, "result": {"content": [{"type": "text", "text": text}], "isError": is_err}})
    elif mid is not None:
        send({"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": "metodo no soportado"}})


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            handle(json.loads(line))
        except Exception as e:  # noqa: BLE001
            sys.stderr.write("error: %r\n" % e)


if __name__ == "__main__":
    main()
