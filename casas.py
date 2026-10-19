"""Casas: espacios compartidos de Nutricion. Una casa tiene su propia base (alimentos, recetas, menu, compra y trabajos del asistente; ver db.use_casa) y una o mas
personas asignadas; una persona puede estar en varias casas y elige cual usa. Sin casa activa se trabaja con la base personal de siempre.
Aqui vive el registro (casas, miembros y casa activa de cada persona) en CASAS_DIR/_registro.db; las bases de las casas estan al lado (<slug>.db).
Lo personal (ajustes y objetivos de macros, entrenos, chat) no se comparte nunca."""
import os
import re
import sqlite3
import time
import unicodedata

from flask import Blueprint, abort, jsonify, request

import db
import nutri

bp = Blueprint("casas", __name__)
MAX_CASAS_PER_USER = 12
MAX_MEMBERS = 30
SCHEMA = """
CREATE TABLE IF NOT EXISTS casas(slug TEXT PRIMARY KEY, name TEXT NOT NULL, created INTEGER NOT NULL, created_by TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS members(casa TEXT NOT NULL REFERENCES casas(slug) ON DELETE CASCADE, user TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'member', added INTEGER NOT NULL, PRIMARY KEY(casa, user));
CREATE INDEX IF NOT EXISTS mem_user ON members(user);
CREATE TABLE IF NOT EXISTS active(user TEXT PRIMARY KEY, casa TEXT NOT NULL);
"""


class CasaError(Exception):
    """Mensaje para la persona (422)."""


_schema_ok = set()


def _conn():
    os.makedirs(db.CASAS_DIR, exist_ok=True)
    path = os.path.join(db.CASAS_DIR, "_registro.db")
    c = sqlite3.connect(path, timeout=15, isolation_level=None)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON")
    if path not in _schema_ok:
        c.executescript(SCHEMA)
        _schema_ok.add(path)
    return c


def _q(sql, args=()):
    c = _conn()
    try:
        return [dict(r) for r in c.execute(sql, args).fetchall()]
    finally:
        c.close()


def _x(sql, args=()):
    c = _conn()
    try:
        return c.execute(sql, args)
    finally:
        c.close()


def slugify(name):
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:28].strip("-")
    return s if len(s) >= 2 else "casa"


def clean_name(v):
    n = " ".join(str(v or "").split())[:60]
    if len(n) < 2:
        raise CasaError("Pon un nombre de al menos 2 letras")
    return n


# ---------------------------------------------------------------- consultas

def members(slug):
    return _q("SELECT user, role FROM members WHERE casa=? ORDER BY role DESC, user", (slug,))


def role_of(slug, user):
    r = _q("SELECT role FROM members WHERE casa=? AND user=?", (slug, user)) if db.valid_casa(slug) else []
    return r[0]["role"] if r else None


def mine(user):
    out = []
    for c in _q("SELECT c.slug, c.name, m.role FROM casas c JOIN members m ON m.casa=c.slug WHERE m.user=? ORDER BY lower(c.name)", (user,)):
        out.append({**c, "members": members(c["slug"])})
    return out


def active(user):
    """Casa activa de la persona (None = base personal). Si ya no es miembro, deja de estar activa."""
    r = _q("SELECT casa FROM active WHERE user=?", (user,))
    if r and role_of(r[0]["casa"], user):
        return r[0]["casa"]
    return None


def set_active(user, slug):
    if slug is None:
        _x("DELETE FROM active WHERE user=?", (user,))
        return
    if not role_of(slug, user):
        raise CasaError("No perteneces a esa casa")
    _x("INSERT INTO active(user,casa) VALUES(?,?) ON CONFLICT(user) DO UPDATE SET casa=excluded.casa", (user, slug))


def all_slugs():
    return [r["slug"] for r in _q("SELECT slug FROM casas ORDER BY slug")]


# ---------------------------------------------------------------- cambios

def create(user, name, copy_mine=False):
    name = clean_name(name)
    if len(mine(user)) >= MAX_CASAS_PER_USER:
        raise CasaError("Demasiadas casas")
    base = slugify(name)
    taken = set(all_slugs())
    slug, n = base, 2
    while slug in taken:
        slug = "%s-%d" % (base[:26], n)
        n += 1
    c = _conn()
    try:
        with c:
            c.execute("INSERT INTO casas(slug,name,created,created_by) VALUES(?,?,?,?)", (slug, name, db.now(), user))
            c.execute("INSERT INTO members(casa,user,role,added) VALUES(?,?,'owner',?)", (slug, user, db.now()))
            c.execute("INSERT INTO active(user,casa) VALUES(?,?) ON CONFLICT(user) DO UPDATE SET casa=excluded.casa", (user, slug))
    finally:
        c.close()
    rep = None
    data = nutri.export_part() if copy_mine else None          # (en la base personal: quien llama no ha activado ninguna casa)
    db.use_casa(slug)
    try:
        if data:
            rep = {}
            with db.tx() as t:
                nutri.import_part(t, data, "merge", rep)
    finally:
        db.use_casa(None)
    return slug, rep


def rename(user, slug, name):
    _need_owner(user, slug)
    _x("UPDATE casas SET name=? WHERE slug=?", (clean_name(name), slug))


def _need_owner(user, slug):
    r = role_of(slug, user)
    if not r:
        raise LookupError("casa")
    if r != "owner":
        raise PermissionError("Solo quien administra la casa puede hacerlo")


def add_member(user, slug, who, role="member"):
    _need_owner(user, slug)
    who = str(who or "").strip().lower()
    if not db.valid_user(who):
        raise CasaError("Nombre de usuario no válido")
    if role not in ("member", "owner"):
        raise CasaError("Rol no válido")
    cur = role_of(slug, who)
    if not cur and len(members(slug)) >= MAX_MEMBERS:
        raise CasaError("La casa ya tiene el máximo de personas")
    if not cur and len(mine(who)) >= MAX_CASAS_PER_USER:
        raise CasaError("Esa persona ya está en demasiadas casas")
    if cur == "owner" and role == "member" and _owners(slug) <= 1:
        raise CasaError("Tiene que quedar al menos una persona administrando la casa")
    _x("INSERT INTO members(casa,user,role,added) VALUES(?,?,?,?) ON CONFLICT(casa,user) DO UPDATE SET role=excluded.role", (slug, who, role, db.now()))


def _owners(slug):
    return len([m for m in members(slug) if m["role"] == "owner"])


def remove_member(user, slug, who):
    """Quien administra quita a cualquiera; cualquiera puede salirse. La casa no se queda sin administracion mientras haya mas gente."""
    if who != user:
        _need_owner(user, slug)
    elif not role_of(slug, user):
        raise LookupError("casa")
    r = role_of(slug, who)
    if not r:
        raise LookupError("persona")
    others = [m for m in members(slug) if m["user"] != who]
    if r == "owner" and others and _owners(slug) <= 1:
        raise CasaError("Antes de salir, nombra a otra persona para administrar la casa (o elimina la casa)")
    if not others:
        raise CasaError("Eres la única persona: elimina la casa si ya no la quieres")
    _x("DELETE FROM members WHERE casa=? AND user=?", (slug, who))
    _x("DELETE FROM active WHERE user=? AND casa=?", (who, slug))


def delete(user, slug):
    """Quita la casa del registro y aparta su base (no se borra: queda en _eliminadas/ por si hay que recuperarla)."""
    _need_owner(user, slug)
    _x("DELETE FROM members WHERE casa=?", (slug,))
    _x("DELETE FROM active WHERE casa=?", (slug,))
    _x("DELETE FROM casas WHERE slug=?", (slug,))
    src = db.casa_path(slug)
    if os.path.exists(src):
        os.makedirs(os.path.join(db.CASAS_DIR, "_eliminadas"), exist_ok=True)
        db._ready_casas.discard(slug)
        for ext in ("", "-wal", "-shm"):
            try:
                os.replace(src + ext, os.path.join(db.CASAS_DIR, "_eliminadas", "%s-%d.db%s" % (slug, int(time.time()), ext)))
            except OSError:
                pass


# ---------------------------------------------------------------- rutas (UI)

def _user():
    u = db.user()
    if not u:
        abort(401)
    return u


def _wrap(fn):
    try:
        return fn()
    except CasaError as e:
        return jsonify({"error": str(e)}), 422
    except PermissionError as e:
        return jsonify({"error": str(e)}), 403
    except LookupError as e:
        return jsonify({"error": "%s no encontrada" % e}), 404


def _body():
    d = request.get_json(silent=True)
    if not isinstance(d, dict):
        abort(400, description="JSON esperado")
    return d


def _state(user):
    return {"me": user, "active": active(user), "casas": mine(user), "known_users": [u for u in db.users() if u != user]}


@bp.route("/api/casas", methods=["GET", "POST"])
def api_casas():
    user = _user()
    if request.method == "GET":
        return jsonify(_state(user))
    d = _body()

    def go():
        slug, rep = create(user, d.get("name"), bool(d.get("copy")))
        return jsonify({**_state(user), "created": slug, "copied": rep}), 201
    return _wrap(go)


@bp.route("/api/casas/active", methods=["PUT"])
def api_casa_active():
    user = _user()
    d = _body()

    def go():
        set_active(user, d.get("casa") or None)
        return jsonify(_state(user))
    return _wrap(go)


@bp.route("/api/casas/<slug>", methods=["PATCH", "DELETE"])
def api_casa(slug):
    user = _user()

    def go():
        if request.method == "PATCH":
            rename(user, slug, _body().get("name"))
        else:
            delete(user, slug)
        return jsonify(_state(user))
    return _wrap(go)


@bp.route("/api/casas/<slug>/members", methods=["POST"])
def api_casa_member_add(slug):
    user = _user()
    d = _body()

    def go():
        add_member(user, slug, d.get("user"), d.get("role") or "member")
        return jsonify(_state(user)), 201
    return _wrap(go)


@bp.route("/api/casas/<slug>/members/<who>", methods=["DELETE"])
def api_casa_member_del(slug, who):
    user = _user()

    def go():
        remove_member(user, slug, who)
        return jsonify(_state(user))
    return _wrap(go)


# ---------------------------------------------------------------- la casa que usa cada peticion de Nutricion

@nutri.bp.before_request
def select_casa():
    """Las rutas de nutricion (alimentos, recetas, menu, compra, Cocinar y las del asistente) trabajan en la casa activa de la persona, si tiene una.
    El asistente puede fijarla con X-Agent-Casa (la casa del trabajo que esta haciendo); solo se acepta si la persona es miembro."""
    user = db.user()
    if not user:
        return None
    slug = request.headers.get("X-Agent-Casa", "").strip() if request.path.startswith("/agent/") else ""
    if slug:
        if not role_of(slug, user):
            return jsonify({"error": "casa desconocida para esa persona"}), 400
    else:
        slug = active(user)
    if slug:
        db.use_casa(slug)
    return None
