import hmac
import json
import mimetypes
import os
import secrets
import time
import uuid
from urllib.parse import quote, urlparse

from flask import Flask, Response, abort, jsonify, redirect, render_template, request, send_file, session
from werkzeug.middleware.proxy_fix import ProxyFix

import core
import db

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

PREFIX = os.environ.get("URL_PREFIX", "/entreno").rstrip("/")
PORTAL_URL = os.environ.get("PORTAL_URL", "https://portal.solde.cat").rstrip("/")
AGENT_TOKEN = os.environ.get("AGENT_TOKEN", "").strip()
SESSION_HOURS = float(os.environ.get("SESSION_HOURS", "12"))
HERE = os.path.dirname(os.path.abspath(__file__))
ASSET_V = str(int(time.time()))
SMALL_BODY = 256 * 1024
MAX_IMAGE = 8 * 2**20
MAX_VIDEO = 30 * 2**20
MAX_MEDIA = 8
IMPORT_MAX = 40 * 2**20
AGENT_SEEN = {"ts": 0.0}
TURN_STALE = 20 * 60


class PrefixMiddleware:
    """Sirve la app bajo /entreno (SCRIPT_NAME) sin tocar las rutas; sin prefijo (ClusterIP del worker) no hace nada."""

    def __init__(self, wsgi):
        self.wsgi = wsgi

    def __call__(self, environ, start_response):
        path = environ.get("PATH_INFO", "")
        if PREFIX and (path == PREFIX or path.startswith(PREFIX + "/")):
            environ["SCRIPT_NAME"] = environ.get("SCRIPT_NAME", "") + PREFIX
            environ["PATH_INFO"] = path[len(PREFIX):] or "/"
        return self.wsgi(environ, start_response)


app.wsgi_app = PrefixMiddleware(app.wsgi_app)


def _secret_key():
    k = os.environ.get("SECRET_KEY")
    if k:
        return k
    path = os.path.join(os.path.dirname(db.PATH) or ".", "secret.key")
    try:
        with open(path) as f:
            k = f.read().strip()
        if k:
            return k
    except OSError:
        pass
    k = secrets.token_hex(32)
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(k)
    except OSError:
        pass
    return k


app.config.update(
    SECRET_KEY=_secret_key(),
    SESSION_COOKIE_NAME="homelab_session",
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("COOKIE_SECURE", "1") == "1",
    PERMANENT_SESSION_LIFETIME=int(SESSION_HOURS * 3600),
    MAX_CONTENT_LENGTH=IMPORT_MAX + 1024 * 1024,
)
db.init()
core.seed()

# ---------------------------------------------------------------- seguridad (sesion compartida con el portal)

BIG_POSTS = ("/api/import",)


def _same_origin():
    site = request.headers.get("Sec-Fetch-Site")
    if site and site not in ("same-origin", "none"):
        return False
    origin = request.headers.get("Origin")
    return not (origin and urlparse(origin).netloc != request.host)


def _logged():
    return bool(session.get("auth") and session.get("exp", 0) > time.time())


def _to_login():
    return redirect("/login?next=" + quote(request.script_root + "/", safe="/"))


def _is_media_upload(path):
    return request.method == "POST" and path.startswith("/api/exercises/") and path.endswith("/media")


@app.before_request
def gate():
    path = request.path
    if path == "/healthz":
        return None
    if path.startswith("/agent/"):
        if request.script_root:
            abort(404)
        tok = request.headers.get("X-Agent-Token", "")
        if not AGENT_TOKEN or not hmac.compare_digest(tok, AGENT_TOKEN):
            return jsonify({"error": "unauthorized"}), 401
        return None
    if path.startswith("/static/"):
        return None
    big = _is_media_upload(path) or (path in BIG_POSTS and request.method == "POST")
    if request.content_length and request.content_length > (IMPORT_MAX if big else SMALL_BODY):
        return jsonify({"error": "demasiado grande"}), 413
    mutating = request.method in ("POST", "PUT", "PATCH", "DELETE")
    if mutating and not _same_origin():
        return jsonify({"error": "forbidden"}), 403
    if not _logged():
        session.clear()
        if path.startswith(("/api/", "/media/")):
            return jsonify({"error": "unauthorized"}), 401
        return _to_login()
    if mutating:
        sent, want = request.headers.get("X-CSRF-Token", ""), session.get("csrf", "")
        if not want or not hmac.compare_digest(sent, want):
            return jsonify({"error": "csrf"}), 403
    return None


@app.after_request
def headers(resp):
    resp.headers["X-Content-Type-Options"] = "nosniff"
    framed = request.path == "/" and request.args.get("embed") == "1"
    resp.headers["X-Frame-Options"] = "SAMEORIGIN" if framed else "DENY"
    resp.headers["Referrer-Policy"] = "same-origin"
    resp.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(), fullscreen=(self), screen-wake-lock=(self)"
    if request.path.startswith("/media/"):
        resp.headers["Content-Security-Policy"] = "sandbox; default-src 'none'; img-src 'self'; media-src 'self'"
    else:
        resp.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; media-src 'self'; "
            f"connect-src 'self'; font-src 'self'; frame-ancestors {"'self'" if framed else "'none'"}; base-uri 'none'; form-action 'self'")
    if request.path.startswith(("/api/", "/agent/")) or request.path == "/":
        resp.headers["Cache-Control"] = "no-store"
    return resp


# ---------------------------------------------------------------- paginas y utilidades

_i18n = {}


def page(template, **kw):
    if not _i18n:
        with open(os.path.join(HERE, "static", "i18n", "es.json"), encoding="utf-8") as f:
            _i18n.update(json.load(f))
    return render_template(template, lang="es", i18n=_i18n, v=ASSET_V, base=request.script_root, embed=request.args.get("embed") == "1", **kw)


@app.route("/")
def index():
    return page("index.html")


@app.route("/healthz")
def healthz():
    return jsonify({"status": "ok"})


@app.route("/api/session")
def api_session():
    if not session.get("csrf"):
        session["csrf"] = secrets.token_urlsafe(32)
        session.permanent = True
        session.setdefault("exp", time.time() + SESSION_HOURS * 3600)
    return jsonify({"csrf": session["csrf"]})


@app.route("/api/logout", methods=["POST"])
def api_logout():
    session.clear()
    return jsonify({"ok": True})


def body():
    d = request.get_json(silent=True)
    if not isinstance(d, dict):
        abort(400, description="JSON esperado")
    return d


@app.errorhandler(core.TrainError)
def handle_train(err):
    return jsonify({"error": str(err)}), 422


@app.errorhandler(400)
@app.errorhandler(404)
@app.errorhandler(405)
@app.errorhandler(409)
@app.errorhandler(413)
@app.errorhandler(415)
def handle_error(err):
    return jsonify({"error": err.description}), err.code


def found(x, what="elemento"):
    if x is None:
        abort(404, description="%s no encontrado" % what)
    return x


# ---------------------------------------------------------------- ejercicios

@app.route("/api/meta")
def api_meta():
    return jsonify(core.meta())


def _search_args(src):
    return dict(q=src.get("q", ""), muscle=src.get("muscle", ""), equipment=src.get("equipment", ""), category=src.get("category", ""), level=src.get("level", ""),
                favorite=src.get("favorite") == "1", no_media=src.get("no_media") == "1", tracking=src.get("tracking", ""),
                limit=request.args.get("limit", 60, type=int), offset=request.args.get("offset", 0, type=int))


@app.route("/api/exercises", methods=["GET", "POST"])
def api_exercises():
    if request.method == "POST":
        return jsonify(core.create_exercise(body())), 201
    return jsonify(core.search_exercises(**_search_args(request.args)))


@app.route("/api/exercises/<eid>", methods=["GET", "PATCH", "DELETE"])
def api_exercise(eid):
    if request.method == "PATCH":
        return jsonify(found(core.update_exercise(eid, body()), "ejercicio"))
    if request.method == "DELETE":
        r = found(db.one("SELECT source FROM exercises WHERE id=?", (eid,)), "ejercicio")
        if r["source"] != "custom":
            abort(409, description="los ejercicios de la biblioteca no se borran; puedes archivarlos")
        if db.one("SELECT 1 AS x FROM routine_items WHERE exercise_id=?", (eid,)):
            abort(409, description="el ejercicio está en alguna rutina; quítalo primero o archívalo")
        _remove_media_dir(eid)
        db.run("DELETE FROM exercises WHERE id=?", (eid,))
        return jsonify({"ok": True})
    return jsonify(found(core.get_exercise(eid), "ejercicio"))


@app.route("/api/exercises/<eid>/progress")
def api_exercise_progress(eid):
    found(db.one("SELECT 1 AS x FROM exercises WHERE id=?", (eid,)), "ejercicio")
    return jsonify(core.exercise_progress(eid))


def _remove_media_dir(eid):
    d = os.path.join(core.MEDIA_DIR, eid)
    if os.path.isdir(d):
        for f in os.listdir(d):
            try:
                os.remove(os.path.join(d, f))
            except OSError:
                pass
        try:
            os.rmdir(d)
        except OSError:
            pass


@app.route("/api/exercises/<eid>/media", methods=["POST"])
def api_media_upload(eid):
    r = found(db.one("SELECT user_media FROM exercises WHERE id=?", (eid,)), "ejercicio")
    media = core.jl(r["user_media"])
    items = [f for f in request.files.getlist("file") if f and f.filename]
    if not items:
        abort(400, description="no hay archivos")
    if len(media) + len(items) > MAX_MEDIA:
        abort(409, description="máximo %d imágenes/vídeos por ejercicio" % MAX_MEDIA)
    d = os.path.join(core.MEDIA_DIR, eid)
    os.makedirs(d, mode=0o700, exist_ok=True)
    added = []
    for f in items:
        head = f.stream.read(16)
        kind = core.sniff_media(head)
        if not kind:
            abort(415, description="«%s»: formato no admitido (JPG, PNG, WebP, GIF, MP4 o WebM)" % f.filename[:60])
        ext, k = kind
        limit = MAX_VIDEO if k == "video" else MAX_IMAGE
        name = "%s.%s" % (secrets.token_hex(8), ext)
        tmp = os.path.join(d, name + ".part")
        size = len(head)
        try:
            with open(tmp, "wb") as out:
                out.write(head)
                while True:
                    chunk = f.stream.read(65536)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > limit:
                        abort(413, description="«%s» supera el máximo de %d MB" % (f.filename[:60], limit // 2**20))
                    out.write(chunk)
            os.replace(tmp, os.path.join(d, name))
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)
        added.append({"file": name, "kind": k})
    db.run("UPDATE exercises SET user_media=? WHERE id=?", (json.dumps(media + added), eid))
    return jsonify(core.get_exercise(eid)), 201


@app.route("/api/exercises/<eid>/media/<fname>", methods=["DELETE"])
def api_media_delete(eid, fname):
    r = found(db.one("SELECT user_media FROM exercises WHERE id=?", (eid,)), "ejercicio")
    media = core.jl(r["user_media"])
    keep = [m for m in media if m["file"] != fname]
    if len(keep) == len(media):
        abort(404, description="archivo no encontrado")
    try:
        os.remove(os.path.join(core.MEDIA_DIR, eid, fname))
    except OSError:
        pass
    db.run("UPDATE exercises SET user_media=? WHERE id=?", (json.dumps(keep), eid))
    return jsonify(core.get_exercise(eid))


@app.route("/media/<eid>/<fname>")
def media_file(eid, fname):
    r = found(db.one("SELECT user_media FROM exercises WHERE id=?", (eid,)), "archivo")
    if not any(m["file"] == fname for m in core.jl(r["user_media"])):
        abort(404, description="archivo no encontrado")
    p = os.path.realpath(os.path.join(core.MEDIA_DIR, eid, fname))
    if not p.startswith(os.path.realpath(core.MEDIA_DIR) + os.sep) or not os.path.isfile(p):
        abort(404, description="archivo no encontrado")
    resp = send_file(p, mimetype=mimetypes.guess_type(fname)[0] or "application/octet-stream", conditional=True, max_age=3600)
    resp.headers["Cache-Control"] = "private, max-age=3600"
    return resp


# ---------------------------------------------------------------- rutinas

@app.route("/api/routines", methods=["GET", "POST"])
def api_routines():
    if request.method == "POST":
        return jsonify(core.save_routine(body())), 201
    return jsonify(core.list_routines(include_archived=request.args.get("archived") == "1"))


@app.route("/api/routines/<int:rid>", methods=["GET", "PUT", "DELETE"])
def api_routine(rid):
    found(db.one("SELECT 1 AS x FROM routines WHERE id=?", (rid,)), "rutina")
    if request.method == "PUT":
        return jsonify(core.save_routine(body(), rid, "user", str(body().get("reason") or "Editada a mano")[:200]))
    if request.method == "DELETE":
        core.save_routine({"archived": True}, rid, "user", "Archivada")
        return jsonify({"ok": True})
    return jsonify(core.get_routine(rid))


@app.route("/api/routines/<int:rid>/duplicate", methods=["POST"])
def api_routine_dup(rid):
    return jsonify(found(core.duplicate_routine(rid), "rutina")), 201


@app.route("/api/routines/<int:rid>/revisions")
def api_revisions(rid):
    found(db.one("SELECT 1 AS x FROM routines WHERE id=?", (rid,)), "rutina")
    return jsonify(core.list_revisions(rid))


@app.route("/api/routines/<int:rid>/restore/<int:rev>", methods=["POST"])
def api_restore(rid, rev):
    found(db.one("SELECT 1 AS x FROM routines WHERE id=?", (rid,)), "rutina")
    return jsonify(core.restore_revision(rid, rev, "user"))


# ---------------------------------------------------------------- entrenamientos

@app.route("/api/sessions", methods=["GET", "POST"])
def api_sessions():
    if request.method == "POST":
        rid = request.get_json(silent=True) or {}
        return jsonify(core.start_session(rid.get("routine_id") if isinstance(rid, dict) else None)), 201
    return jsonify(core.list_sessions(request.args.get("limit", 30, type=int), request.args.get("routine_id", type=int), request.args.get("before", type=int)))


@app.route("/api/sessions/active")
def api_session_active():
    return jsonify(core.active_session())


@app.route("/api/sessions/<int:sid>", methods=["GET", "PATCH", "DELETE"])
def api_session_item(sid):
    found(db.one("SELECT 1 AS x FROM sessions WHERE id=?", (sid,)), "entrenamiento")
    if request.method == "PATCH":
        return jsonify(core.patch_session(sid, body()))
    if request.method == "DELETE":
        core.delete_session(sid)
        return jsonify({"ok": True})
    return jsonify(core.get_session(sid))


@app.route("/api/sessions/<int:sid>/sets", methods=["POST"])
def api_set_add(sid):
    return jsonify(core.add_set(sid, body())), 201


@app.route("/api/sessions/<int:sid>/sets/<int:set_id>", methods=["PATCH", "DELETE"])
def api_set_item(sid, set_id):
    if request.method == "DELETE":
        db.run("DELETE FROM session_sets WHERE id=? AND session_id=?", (set_id, sid))
        return jsonify({"ok": True})
    return jsonify(found(core.update_set(sid, set_id, body()), "serie"))


@app.route("/api/sessions/<int:sid>/finish", methods=["POST"])
def api_session_finish(sid):
    d = request.get_json(silent=True) or {}
    s = core.finish_session(sid, d, "abandoned" if d.get("abandon") else "done")
    queued = None
    if s["status"] == "done" and s["routine_id"] and core.get_settings()["auto_adjust"] == "after" and s["sets"]:
        queued = enqueue_eval(s["routine_id"], "auto")
    s["eval_job"] = queued
    return jsonify(s)


# ---------------------------------------------------------------- panel, ajustes, evaluacion, datos

@app.route("/api/stats")
def api_stats():
    return jsonify(core.stats(request.args.get("weeks", 12, type=int)))


@app.route("/api/settings", methods=["GET", "PUT"])
def api_settings():
    if request.method == "PUT":
        return jsonify(core.put_settings(body()))
    return jsonify(core.get_settings())


def enqueue_eval(routine_id, trigger):
    q = "SELECT id FROM eval_jobs WHERE status IN ('queued','running') AND " + ("routine_id=?" if routine_id else "routine_id IS NULL")
    cur = db.one(q, (routine_id,) if routine_id else ())
    if cur:
        return cur["id"]
    return db.run("INSERT INTO eval_jobs(routine_id,trigger,created) VALUES(?,?,?)", (routine_id, trigger, db.now())).lastrowid


def _fail_stale_evals():
    now = db.now()
    db.run("UPDATE eval_jobs SET status='error', error='Sin agente conectado', finished=? WHERE status='queued' AND created<?", (now, now - 600))
    db.run("UPDATE eval_jobs SET status='error', error='El agente no respondió a tiempo', finished=? WHERE status='running' AND started<?", (now, now - TURN_STALE))


@app.route("/api/eval", methods=["GET", "POST"])
def api_eval():
    if request.method == "POST":
        d = body()
        rid = d.get("routine_id")
        if rid is not None:
            found(db.one("SELECT 1 AS x FROM routines WHERE id=? AND archived=0", (rid,)), "rutina")
        return jsonify({"id": enqueue_eval(rid, "manual")}), 202
    _fail_stale_evals()
    rows = db.q("SELECT e.id, e.routine_id, r.name AS routine, e.trigger, e.status, e.created, e.finished, e.summary, e.error FROM eval_jobs e LEFT JOIN routines r ON r.id=e.routine_id ORDER BY e.id DESC LIMIT 15")
    return jsonify({"jobs": rows, "agent_online": time.time() - AGENT_SEEN["ts"] < 60})


@app.route("/api/export")
def api_export():
    data = core.export_all(include_media=request.args.get("media") == "1")
    name = "entrenamiento-%s.json" % time.strftime("%Y%m%d")
    return Response(json.dumps(data, ensure_ascii=False, indent=1), mimetype="application/json", headers={"Content-Disposition": 'attachment; filename="%s"' % name})


@app.route("/api/export/sessions.csv")
def api_export_csv():
    return Response("﻿" + core.sessions_csv(), mimetype="text/csv; charset=utf-8", headers={"Content-Disposition": 'attachment; filename="entrenamientos.csv"'})


@app.route("/api/import", methods=["POST"])
def api_import():
    mode = request.args.get("mode", "merge")
    data = body()
    return jsonify(core.import_all(data, mode))


# ---------------------------------------------------------------- chat (UI)

def _fail_stale():
    now = db.now()
    db.run("UPDATE chat_turns SET status='error', error='El agente no respondió a tiempo', finished=? WHERE status='running' AND started<?", (now, now - TURN_STALE))
    db.run("UPDATE chat_turns SET status='error', error='Sin agente conectado', finished=? WHERE status='queued' AND created<?", (now, now - 180))


@app.route("/api/chat/status")
def chat_status():
    return jsonify({"agent_online": time.time() - AGENT_SEEN["ts"] < 60})


@app.route("/api/chat/sessions", methods=["GET", "POST"])
def chat_sessions():
    if request.method == "POST":
        now = db.now()
        cur = db.run("INSERT INTO chat_sessions(title,claude_uuid,created,updated) VALUES(?,?,?,?)", ("Nueva conversación", str(uuid.uuid4()), now, now))
        return jsonify({"id": cur.lastrowid}), 201
    return jsonify(db.q("SELECT id, title, updated FROM chat_sessions ORDER BY updated DESC LIMIT 100"))


@app.route("/api/chat/sessions/<int:sid>", methods=["GET", "DELETE", "PATCH"])
def chat_session(sid):
    s = found(db.one("SELECT * FROM chat_sessions WHERE id=?", (sid,)), "conversación")
    if request.method == "DELETE":
        if db.one("SELECT 1 AS x FROM chat_turns WHERE session_id=? AND status IN ('queued','running')", (sid,)):
            return jsonify({"error": "hay una respuesta en curso"}), 409
        db.run("DELETE FROM chat_sessions WHERE id=?", (sid,))
        return jsonify({"ok": True})
    if request.method == "PATCH":
        t = str(body().get("title", "")).strip()[:80]
        if t:
            db.run("UPDATE chat_sessions SET title=? WHERE id=?", (t, sid))
        return jsonify({"ok": True})
    _fail_stale()
    turns = db.q("SELECT id, user_message, status, answer, error, created FROM chat_turns WHERE session_id=? ORDER BY id", (sid,))
    return jsonify({"id": sid, "title": s["title"], "turns": turns})


@app.route("/api/chat/sessions/<int:sid>/messages", methods=["POST"])
def chat_send(sid):
    found(db.one("SELECT 1 AS x FROM chat_sessions WHERE id=?", (sid,)), "conversación")
    text = str(body().get("text", "")).strip()
    if not text or len(text) > 8000:
        abort(400, description="mensaje vacío o demasiado largo (máx. 8000)")
    _fail_stale()
    if db.one("SELECT 1 AS x FROM chat_turns WHERE session_id=? AND status IN ('queued','running')", (sid,)):
        return jsonify({"error": "hay una respuesta en curso"}), 409
    now = db.now()
    with db.tx() as c:
        cur = c.execute("INSERT INTO chat_turns(session_id,user_message,created) VALUES(?,?,?)", (sid, text, now))
        c.execute("UPDATE chat_sessions SET updated=?, title=CASE WHEN title='Nueva conversación' THEN ? ELSE title END WHERE id=?", (now, text[:60], sid))
    return jsonify({"turn_id": cur.lastrowid}), 201


@app.route("/api/chat/turns/<int:tid>")
def chat_turn(tid):
    after = request.args.get("after", 0, type=int)
    found(db.one("SELECT id FROM chat_turns WHERE id=?", (tid,)), "turno")
    _fail_stale()
    t = db.one("SELECT id, status, answer, error FROM chat_turns WHERE id=?", (tid,))
    ev = db.q("SELECT id, type, payload FROM chat_events WHERE turn_id=? AND id>? ORDER BY id LIMIT 300", (tid, after))
    return jsonify({**t, "events": [{"id": e["id"], "type": e["type"], **json.loads(e["payload"])} for e in ev]})


@app.route("/api/chat/turns/<int:tid>/cancel", methods=["POST"])
def chat_cancel(tid):
    t = found(db.one("SELECT status FROM chat_turns WHERE id=?", (tid,)), "turno")
    if t["status"] == "queued":
        db.run("UPDATE chat_turns SET status='error', error='cancelled', finished=? WHERE id=?", (db.now(), tid))
    elif t["status"] == "running":
        db.run("UPDATE chat_turns SET cancel=1 WHERE id=?", (tid,))
    return jsonify({"ok": True})


# ---------------------------------------------------------------- API del agente (host, solo ClusterIP + token)

def _maybe_weekly():
    s = core.get_settings()
    if s["auto_adjust"] != "weekly":
        return
    last = int(db.setting("last_weekly_eval", "0"))
    if db.now() - last < 7 * 86400:
        return
    if db.one("SELECT 1 AS x FROM sessions WHERE status='done' AND started>?", (db.now() - 7 * 86400,)):
        enqueue_eval(None, "weekly")
    db.set_setting("last_weekly_eval", str(db.now()))


@app.route("/agent/next")
def agent_next():
    wait = max(0, min(30, request.args.get("wait", 25, type=int)))
    end = time.time() + wait
    while True:
        AGENT_SEEN["ts"] = time.time()
        _fail_stale()
        _fail_stale_evals()
        _maybe_weekly()
        job = None
        with db.tx() as c:
            t = c.execute("SELECT t.id, t.session_id, t.user_message, s.claude_uuid FROM chat_turns t JOIN chat_sessions s ON s.id=t.session_id WHERE t.status='queued' ORDER BY t.id LIMIT 1").fetchone()
            if t:
                c.execute("UPDATE chat_turns SET status='running', started=? WHERE id=?", (db.now(), t["id"]))
                resume = c.execute("SELECT 1 FROM chat_turns WHERE session_id=? AND status='done' AND id<?", (t["session_id"], t["id"])).fetchone() is not None
                job = {"kind": "chat", "turn_id": t["id"], "session_id": t["session_id"], "claude_session_uuid": t["claude_uuid"], "resume": resume, "user_message": t["user_message"]}
            else:
                e = c.execute("SELECT e.id, e.routine_id, e.trigger, r.name FROM eval_jobs e LEFT JOIN routines r ON r.id=e.routine_id WHERE e.status='queued' ORDER BY e.id LIMIT 1").fetchone()
                if e:
                    c.execute("UPDATE eval_jobs SET status='running', started=? WHERE id=?", (db.now(), e["id"]))
                    job = {"kind": "eval", "job_id": e["id"], "routine_id": e["routine_id"], "routine_name": e["name"], "trigger": e["trigger"]}
        if job:
            return jsonify(job)
        if time.time() >= end:
            return "", 204
        time.sleep(0.7)


def _turn_for_agent(tid):
    return found(db.one("SELECT id, status, cancel FROM chat_turns WHERE id=?", (tid,)), "turno")


@app.route("/agent/turns/<int:tid>/events", methods=["POST"])
def agent_events(tid):
    t = _turn_for_agent(tid)
    events = (request.get_json(silent=True) or {}).get("events") or []
    if t["status"] == "running":
        with db.tx() as c:
            for e in events[:100]:
                typ = e.get("type")
                if typ not in ("delta", "tool", "status"):
                    continue
                payload = {k: e[k] for k in ("text", "name", "status") if k in e and isinstance(e[k], str)}
                c.execute("INSERT INTO chat_events(turn_id,type,payload) VALUES(?,?,?)", (tid, typ, json.dumps(payload)[:20000]))
    return jsonify({"ok": True, "cancel": bool(t["cancel"])})


@app.route("/agent/turns/<int:tid>/done", methods=["POST"])
def agent_done(tid):
    _turn_for_agent(tid)
    d = request.get_json(silent=True) or {}
    err = d.get("error")
    text = str(d.get("text") or "")[:100000]
    with db.tx() as c:
        c.execute("UPDATE chat_turns SET status=?, answer=?, error=?, finished=? WHERE id=?", ("error" if err else "done", text, str(err)[:500] if err else None, db.now(), tid))
        c.execute("DELETE FROM chat_events WHERE turn_id=?", (tid,))
        c.execute("UPDATE chat_sessions SET updated=? WHERE id=(SELECT session_id FROM chat_turns WHERE id=?)", (db.now(), tid))
    return jsonify({"ok": True})


@app.route("/agent/eval/<int:jid>/done", methods=["POST"])
def agent_eval_done(jid):
    j = found(db.one("SELECT status FROM eval_jobs WHERE id=?", (jid,)), "evaluación")
    if j["status"] != "running":
        abort(409, description="evaluación no activa")
    d = body()
    err = d.get("error")
    db.run("UPDATE eval_jobs SET status=?, summary=?, error=?, finished=? WHERE id=?",
           ("error" if err else "done", str(d.get("summary") or "")[:4000], str(err)[:500] if err else None, db.now(), jid))
    return jsonify({"ok": True})


def _compact_ex(e):
    return {"id": e["id"], "name": e["name"], "name_es": e["name_es"], "category": e["category"], "equipment": e["equipment"], "level": e["level"], "primary": e["primary"], "tracking": e["tracking"]}


@app.route("/agent/profile")
def agent_profile():
    st = core.stats(8)
    return jsonify({"settings": core.get_settings(), "today": core.TZ and __import__("datetime").datetime.now(core.TZ).strftime("%Y-%m-%d %A"),
                    "summary": {k: st[k] for k in ("this_week", "last_week", "streak_days", "total_sessions", "avg_per_week_4", "target_days", "muscles", "prs")}})


@app.route("/agent/exercises")
def agent_exercises():
    a = _search_args(request.args)
    a["limit"] = min(a["limit"], 40)
    r = core.search_exercises(**a)
    return jsonify({"total": r["total"], "items": [_compact_ex(e) for e in r["items"]]})


@app.route("/agent/exercises/<eid>")
def agent_exercise(eid):
    e = found(core.get_exercise(eid), "ejercicio")
    e.pop("media", None)
    return jsonify(e)


@app.route("/agent/exercises", methods=["POST"])
def agent_exercise_create():
    return jsonify(core.create_exercise(body(), source="custom")), 201


@app.route("/agent/routines")
def agent_routines():
    return jsonify(core.list_routines(include_archived=request.args.get("archived") == "1"))


@app.route("/agent/routines/<int:rid>")
def agent_routine(rid):
    r = found(core.get_routine(rid), "rutina")
    r["revisions"] = core.list_revisions(rid, 10)
    return jsonify(r)


@app.route("/agent/routines", methods=["POST"])
def agent_routine_create():
    d = body()
    return jsonify(core.save_routine(d, None, "agent", str(d.get("reason") or "Creada por el asistente")[:300])), 201


@app.route("/agent/routines/<int:rid>", methods=["PUT", "DELETE"])
def agent_routine_update(rid):
    found(db.one("SELECT 1 AS x FROM routines WHERE id=?", (rid,)), "rutina")
    if request.method == "DELETE":
        core.save_routine({"archived": True}, rid, "agent", str((request.get_json(silent=True) or {}).get("reason") or "Archivada por el asistente")[:300])
        return jsonify({"ok": True})
    d = body()
    reason = str(d.get("reason") or "").strip()
    if len(reason) < 8:
        abort(400, description="indica el motivo del cambio en 'reason' (para que la persona pueda revisarlo)")
    return jsonify(core.save_routine(d, rid, "agent", reason[:300]))


@app.route("/agent/routines/<int:rid>/restore/<int:rev>", methods=["POST"])
def agent_restore(rid, rev):
    return jsonify(core.restore_revision(rid, rev, "agent"))


@app.route("/agent/sessions")
def agent_sessions():
    return jsonify(core.list_sessions(request.args.get("limit", 15, type=int), request.args.get("routine_id", type=int)))


@app.route("/agent/sessions/<int:sid>")
def agent_session(sid):
    s = found(core.get_session(sid), "entrenamiento")
    s.pop("state", None)
    return jsonify(s)


@app.route("/agent/stats")
def agent_stats():
    st = core.stats(request.args.get("weeks", 8, type=int))
    st.pop("recent", None)
    return jsonify(st)


@app.route("/agent/progress/<eid>")
def agent_progress(eid):
    return jsonify(core.exercise_progress(eid, 40))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
