#!/usr/bin/env python3
"""Servidor MCP stdio del asistente de entrenamiento (solo stdlib). Lo lanza `claude -p` (ver worker.py).

Es la UNICA via del modelo a los datos: cada herramienta hace una peticion fija a /agent/* de la app (token y URL llegan por el entorno que pone
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
MAX_TEXT = 40000


def call(method, path, params=None, body=None):
    qs = ("?" + urllib.parse.urlencode({k: v for k, v in (params or {}).items() if v not in (None, "")})) if params else ""
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(APP + path + qs, data=data, method=method, headers={"X-Agent-Token": TOKEN, "Content-Type": "application/json"})
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


S = lambda **p: {"type": "object", "properties": p}  # noqa: E731
STR, INT, NUM = {"type": "string"}, {"type": "integer"}, {"type": "number"}
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
