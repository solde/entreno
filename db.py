import os
import sqlite3
import threading
import time

PATH = os.environ.get("DB_PATH", "/data/training.db")
_local = threading.local()

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings(k TEXT PRIMARY KEY, v TEXT NOT NULL);
-- Biblioteca de ejercicios (source='lib': semilla de data/exercises.json; 'custom': creados por la persona o el asistente).
-- user_media: imagenes/videos subidos por la persona (sustituyen a las imagenes de la biblioteca); name_es/video_url/notes/favorite/archived son editables en todos.
CREATE TABLE IF NOT EXISTS exercises(
  id TEXT PRIMARY KEY, name TEXT NOT NULL, name_es TEXT NOT NULL DEFAULT '', category TEXT NOT NULL DEFAULT 'strength',
  level TEXT NOT NULL DEFAULT 'beginner', equipment TEXT NOT NULL DEFAULT 'none', mechanic TEXT NOT NULL DEFAULT '', force TEXT NOT NULL DEFAULT '',
  primary_m TEXT NOT NULL DEFAULT '[]', secondary_m TEXT NOT NULL DEFAULT '[]', instructions TEXT NOT NULL DEFAULT '[]',
  images TEXT NOT NULL DEFAULT '[]', user_media TEXT NOT NULL DEFAULT '[]', video_url TEXT NOT NULL DEFAULT '', notes TEXT NOT NULL DEFAULT '',
  tracking TEXT NOT NULL DEFAULT 'reps', source TEXT NOT NULL DEFAULT 'lib', favorite INTEGER NOT NULL DEFAULT 0, archived INTEGER NOT NULL DEFAULT 0,
  created INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS ex_cat ON exercises(category);
CREATE TABLE IF NOT EXISTS routines(
  id INTEGER PRIMARY KEY, uid TEXT NOT NULL UNIQUE, name TEXT NOT NULL, notes TEXT NOT NULL DEFAULT '', weekdays TEXT NOT NULL DEFAULT '',
  archived INTEGER NOT NULL DEFAULT 0, created INTEGER NOT NULL, updated INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS routine_items(
  id INTEGER PRIMARY KEY, routine_id INTEGER NOT NULL REFERENCES routines(id) ON DELETE CASCADE, position INTEGER NOT NULL,
  exercise_id TEXT NOT NULL, sets INTEGER NOT NULL DEFAULT 3, reps_min INTEGER, reps_max INTEGER, weight REAL NOT NULL DEFAULT 0,
  duration_s INTEGER, distance_m REAL, rest_s INTEGER NOT NULL DEFAULT 90, rest_ex_s INTEGER NOT NULL DEFAULT 120, notes TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS ri_routine ON routine_items(routine_id, position);
-- Version anterior de una rutina antes de cada cambio (persona, asistente o importacion): permite volver atras.
CREATE TABLE IF NOT EXISTS revisions(
  id INTEGER PRIMARY KEY, routine_id INTEGER NOT NULL REFERENCES routines(id) ON DELETE CASCADE, created INTEGER NOT NULL,
  source TEXT NOT NULL, reason TEXT NOT NULL DEFAULT '', snapshot TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS rev_routine ON revisions(routine_id, id);
CREATE TABLE IF NOT EXISTS sessions(
  id INTEGER PRIMARY KEY, uid TEXT NOT NULL UNIQUE, routine_id INTEGER, routine_name TEXT NOT NULL DEFAULT '', started INTEGER NOT NULL,
  finished INTEGER, status TEXT NOT NULL DEFAULT 'active', notes TEXT NOT NULL DEFAULT '', rating INTEGER, plan TEXT NOT NULL DEFAULT '[]',
  state TEXT NOT NULL DEFAULT '{}', total_s INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS se_started ON sessions(started);
CREATE TABLE IF NOT EXISTS session_sets(
  id INTEGER PRIMARY KEY, session_id INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE, position INTEGER NOT NULL, exercise_id TEXT NOT NULL,
  set_no INTEGER NOT NULL, reps INTEGER, weight REAL, duration_s INTEGER, distance_m REAL, rpe REAL, rest_s INTEGER, done_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS ss_session ON session_sets(session_id, position, set_no);
CREATE INDEX IF NOT EXISTS ss_ex ON session_sets(exercise_id);
-- Chat con el asistente (mismo patron que el resto de apps del homelab)
CREATE TABLE IF NOT EXISTS chat_sessions(id INTEGER PRIMARY KEY, title TEXT NOT NULL, claude_uuid TEXT NOT NULL, created INTEGER NOT NULL, updated INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS chat_turns(
  id INTEGER PRIMARY KEY, session_id INTEGER NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
  user_message TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'queued', answer TEXT NOT NULL DEFAULT '', error TEXT,
  cancel INTEGER NOT NULL DEFAULT 0, created INTEGER NOT NULL, started INTEGER, finished INTEGER
);
CREATE INDEX IF NOT EXISTS ct_status ON chat_turns(status, id);
CREATE TABLE IF NOT EXISTS chat_events(id INTEGER PRIMARY KEY, turn_id INTEGER NOT NULL REFERENCES chat_turns(id) ON DELETE CASCADE, type TEXT NOT NULL, payload TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ce_turn ON chat_events(turn_id, id);
-- Evaluaciones del desempeño por el asistente (manuales o automaticas) que pueden ajustar rutinas.
CREATE TABLE IF NOT EXISTS eval_jobs(
  id INTEGER PRIMARY KEY, routine_id INTEGER, trigger TEXT NOT NULL DEFAULT 'manual', status TEXT NOT NULL DEFAULT 'queued',
  created INTEGER NOT NULL, started INTEGER, finished INTEGER, summary TEXT NOT NULL DEFAULT '', error TEXT
);
CREATE INDEX IF NOT EXISTS ev_status ON eval_jobs(status, id);
-- Nutricion: alimentos (valores por 100 g), recetas, plan de comidas por dia y su historial (para deshacer cambios del asistente).
CREATE TABLE IF NOT EXISTS foods(
  id TEXT PRIMARY KEY, name TEXT NOT NULL, category TEXT NOT NULL DEFAULT 'Otros', kcal REAL NOT NULL DEFAULT 0, protein REAL NOT NULL DEFAULT 0,
  carbs REAL NOT NULL DEFAULT 0, fat REAL NOT NULL DEFAULT 0, fiber REAL NOT NULL DEFAULT 0, serving_g REAL NOT NULL DEFAULT 100, notes TEXT NOT NULL DEFAULT '',
  source TEXT NOT NULL DEFAULT 'lib', favorite INTEGER NOT NULL DEFAULT 0, archived INTEGER NOT NULL DEFAULT 0, created INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS recipes(
  id INTEGER PRIMARY KEY, uid TEXT NOT NULL UNIQUE, name TEXT NOT NULL, servings REAL NOT NULL DEFAULT 1, steps TEXT NOT NULL DEFAULT '', notes TEXT NOT NULL DEFAULT '',
  archived INTEGER NOT NULL DEFAULT 0, created INTEGER NOT NULL, updated INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS recipe_items(
  id INTEGER PRIMARY KEY, recipe_id INTEGER NOT NULL REFERENCES recipes(id) ON DELETE CASCADE, position INTEGER NOT NULL,
  food_id TEXT NOT NULL REFERENCES foods(id), grams REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS meal_entries(
  id INTEGER PRIMARY KEY, date TEXT NOT NULL, slot TEXT NOT NULL, position INTEGER NOT NULL DEFAULT 0, kind TEXT NOT NULL DEFAULT 'text',
  food_id TEXT, recipe_id INTEGER, grams REAL, servings REAL, label TEXT NOT NULL DEFAULT '',
  kcal REAL NOT NULL DEFAULT 0, protein REAL NOT NULL DEFAULT 0, carbs REAL NOT NULL DEFAULT 0, fat REAL NOT NULL DEFAULT 0,
  done INTEGER NOT NULL DEFAULT 0, notes TEXT NOT NULL DEFAULT '', source TEXT NOT NULL DEFAULT 'user', created INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS me_date ON meal_entries(date, slot, position);
CREATE TABLE IF NOT EXISTS plan_log(
  id INTEGER PRIMARY KEY, created INTEGER NOT NULL, source TEXT NOT NULL, reason TEXT NOT NULL DEFAULT '', date_from TEXT NOT NULL, date_to TEXT NOT NULL, snapshot TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS plan_jobs(
  id INTEGER PRIMARY KEY, date_from TEXT NOT NULL, date_to TEXT NOT NULL, instructions TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'queued',
  created INTEGER NOT NULL, started INTEGER, finished INTEGER, summary TEXT NOT NULL DEFAULT '', error TEXT
);
CREATE INDEX IF NOT EXISTS pj_status ON plan_jobs(status, id);
"""


def conn():
    c = getattr(_local, "c", None)
    if c is None:
        os.makedirs(os.path.dirname(PATH) or ".", exist_ok=True)
        c = sqlite3.connect(PATH, timeout=15, isolation_level=None)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA foreign_keys=ON")
        c.execute("PRAGMA synchronous=NORMAL")
        _local.c = c
    return c


def init():
    conn().executescript(SCHEMA)


def q(sql, args=()):
    return [dict(r) for r in conn().execute(sql, args).fetchall()]


def one(sql, args=()):
    r = conn().execute(sql, args).fetchone()
    return dict(r) if r else None


def run(sql, args=()):
    return conn().execute(sql, args)


class tx:
    def __enter__(self):
        conn().execute("BEGIN IMMEDIATE")
        return conn()

    def __exit__(self, et, ev, tb):
        conn().execute("ROLLBACK" if et else "COMMIT")
        return False


def setting(key, default=None):
    r = one("SELECT v FROM settings WHERE k=?", (key,))
    return r["v"] if r else default


def set_setting(key, value):
    run("INSERT INTO settings(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v", (key, str(value)))


def now():
    return int(time.time())
