#!/usr/bin/env python3
"""Worker del asistente de entrenamiento (solo stdlib). Long-poll a la app y atiende dos tipos de trabajo:
  chat -> `claude -p` SIN herramientas propias (solo el MCP `training`: lee datos y edita rutinas con historial)
  eval -> evaluacion del desempeño (manual o automatica) que ajusta las rutinas con el mismo MCP
Nada de Vault, kubeconfig ni Bash en el entorno del modelo. Ver README.md.
"""
import json
import os
import re
import signal
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.environ.get("TRAINING_URL", "").rstrip("/")
TOKEN_FILE = os.environ.get("TRAINING_TOKEN_FILE", "/etc/training-agent/token")
LOG_DIR = os.environ.get("TRAINING_LOG_DIR", os.path.join(HERE, "logs"))
WORK_DIR = os.environ.get("TRAINING_WORK_DIR", os.path.join(HERE, "work"))
RUN_DIR = os.environ.get("TRAINING_RUN_DIR", os.path.join(HERE, "run"))
CLAUDE = os.environ.get("CLAUDE_BIN", os.path.expanduser("~/.local/bin/claude"))
MODEL = os.environ.get("TRAINING_MODEL", "")
EFFORT = os.environ.get("TRAINING_EFFORT", "")
TIMEOUT = int(os.environ.get("TRAINING_TURN_TIMEOUT", "600"))
EVAL_TIMEOUT = int(os.environ.get("TRAINING_EVAL_TIMEOUT", "900"))
MAX_BUDGET = os.environ.get("TRAINING_MAX_BUDGET_USD", "3")
EVAL_BUDGET = os.environ.get("TRAINING_EVAL_BUDGET_USD", "3")
DEBUG = os.environ.get("TRAINING_DEBUG") == "1"
POLL_WAIT = 25
FLUSH_EVERY = 0.4
MCP_PREFIX = "mcp__training__"
READ_TOOLS = ("exercise_search", "exercise_get", "routine_list", "routine_get", "sessions_list", "session_get", "stats_get", "progress_get", "profile_get")
WRITE_TOOLS = ("routine_create", "routine_update", "routine_restore", "routine_archive", "exercise_create")
ALLOWED = [MCP_PREFIX + t for t in READ_TOOLS + WRITE_TOOLS]
SETTINGS = json.dumps({"permissions": {"allow": ALLOWED}})

_stop = False


def log(msg):
    print("[%s] %s" % (datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), msg), flush=True)


def token():
    with open(TOKEN_FILE) as f:
        return f.read().strip()


def api(method, path, body=None, timeout=15):
    data = json.dumps(body, default=str).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method, headers={
        "X-Agent-Token": token(), "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
        return r.status, (json.loads(raw) if raw else None)


def post_events(turn_id, events):
    """Devuelve True si la app pide cancelar el turno."""
    try:
        _, resp = api("POST", "/agent/turns/%s/events" % turn_id, {"events": events})
        return bool(isinstance(resp, dict) and resp.get("cancel"))
    except Exception as e:  # noqa: BLE001
        log("turno %s: no se pudieron enviar eventos (%s)" % (turn_id, type(e).__name__))
        return False


def post_retry(path, body, what):
    for attempt in range(6):
        try:
            api("POST", path, body, timeout=30)
            return True
        except urllib.error.HTTPError as e:
            if e.code in (404, 409):
                log("%s: rechazado (%d)" % (what, e.code))
                return False
        except Exception:  # noqa: BLE001
            pass
        time.sleep(min(2 ** attempt, 30))
    log("%s: no se pudo enviar" % what)
    return False


def build_system_prompt(name, extra=None):
    with open(os.path.join(HERE, "prompt", name), encoding="utf-8") as f:
        tpl = f.read()
    profile = "(no disponible)"
    try:
        _, ctx = api("GET", "/agent/profile")
        s = ctx.get("settings", {})
        profile = "\n".join("- %s: %s" % (k, v) for k, v in (("Objetivo", s.get("goal")), ("Experiencia", s.get("experience")), ("Días por semana", s.get("days_per_week")), ("Material", s.get("equipment")),
                                                           ("Lesiones/limitaciones", s.get("injuries")), ("Unidad de peso", s.get("units")), ("Estilo de progresión", s.get("adjust_style")), ("Notas", s.get("notes"))) if v)
        today = ctx.get("today") or date.today().isoformat()
    except Exception as e:  # noqa: BLE001
        log("perfil no disponible (%s)" % type(e).__name__)
        today = date.today().isoformat()
    out = tpl.replace("{{TODAY}}", today).replace("{{PROFILE}}", profile)
    for k, v in (extra or {}).items():
        out = out.replace("{{%s}}" % k, v)
    return out


def claude_env():
    env = {k: os.environ[k] for k in ("PATH", "HOME", "USER", "LANG", "LC_ALL", "TZ") if k in os.environ}
    env.setdefault("PATH", "/usr/local/bin:/usr/bin:/bin")
    env["PATH"] = os.path.dirname(CLAUDE) + ":" + env["PATH"]
    env["CLAUDE_CODE_DISABLE_AUTO_MEMORY"] = "1"
    env["DISABLE_AUTOUPDATER"] = "1"
    return env


class Streamer:
    """Traduce el stream-json de claude a eventos para la app y acumula el texto final."""

    def __init__(self, turn_id):
        self.turn_id = turn_id
        self.buf = ""
        self.out = []
        self.last_flush = time.time()
        self.text = ""
        self.tool_names = {}
        self.text_blocks = 0
        self.thinking_sent = False
        self.result = None
        self.cancelled = threading.Event()

    def _delta(self, t):
        self.buf += t
        self.text += t

    def flush(self, force=False):
        if self.turn_id is None:
            self.buf, self.out = "", []
            return
        if not force and time.time() - self.last_flush < FLUSH_EVERY:
            return
        if self.buf:
            self.out.append({"type": "delta", "text": self.buf})
            self.buf = ""
        if self.out:
            if post_events(self.turn_id, self.out):
                self.cancelled.set()
            self.out = []
        self.last_flush = time.time()

    def _tool(self, name, status):
        if self.buf:
            self.out.append({"type": "delta", "text": self.buf})
            self.buf = ""
        self.out.append({"type": "tool", "name": name.replace(MCP_PREFIX, ""), "status": status})
        self.flush(force=True)

    def feed(self, line):
        try:
            d = json.loads(line)
        except ValueError:
            return
        t = d.get("type")
        if t == "stream_event":
            e = d.get("event", {})
            et = e.get("type")
            if et == "content_block_start":
                cb = e.get("content_block", {})
                if cb.get("type") == "text":
                    if self.text_blocks and self.text:
                        self._delta("\n\n")
                    self.text_blocks += 1
                elif cb.get("type") == "tool_use":
                    self.tool_names[cb.get("id")] = cb.get("name", "")
                    self._tool(cb.get("name", ""), "start")
                elif cb.get("type") == "thinking" and not self.thinking_sent:
                    self.thinking_sent = True
                    self.out.append({"type": "status", "text": "thinking"})
            elif et == "content_block_delta":
                dl = e.get("delta", {})
                if dl.get("type") == "text_delta" and dl.get("text"):
                    self._delta(dl["text"])
        elif t == "user":
            msg = d.get("message", {})
            content = msg.get("content") if isinstance(msg, dict) else None
            if isinstance(content, list):
                for c in content:
                    if isinstance(c, dict) and c.get("type") == "tool_result":
                        name = self.tool_names.get(c.get("tool_use_id"), "")
                        if name:
                            self._tool(name, "end")
        elif t == "result":
            self.result = d
        self.flush()


def run_claude(user_message, system_prompt, session_uuid, resume, streamer, timeout, budget, debug_file):
    env = {"TRAINING_URL": BASE, "TRAINING_TOKEN": token()}
    mcp_cfg = {"mcpServers": {"training": {"command": sys.executable, "args": [os.path.join(HERE, "training_mcp.py")], "env": env}}}
    fd, mcp_path = tempfile.mkstemp(prefix="mcp-", suffix=".json", dir=RUN_DIR)  # 0600
    with os.fdopen(fd, "w") as f:
        json.dump(mcp_cfg, f)
    cmd = ["timeout", "-k", "10", str(timeout), CLAUDE, "-p", "--system-prompt", system_prompt, "--system-prompt-snapshot", "off",
           "--mcp-config", mcp_path, "--strict-mcp-config", "--restricted", "--tools", "", "--settings", SETTINGS, "--permission-prompts", "none",
           "--output-format", "stream-json", "--verbose", "--include-partial-messages", "--max-budget-usd", str(budget)]
    cmd += ["--resume", session_uuid] if resume else ["--session-id", session_uuid]
    if MODEL:
        cmd += ["--model", MODEL]
    if EFFORT:
        cmd += ["--effort", EFFORT]
    try:
        p = subprocess.Popen(cmd, cwd=WORK_DIR, env=claude_env(), stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
        err_chunks = []

        def kill():
            try:
                os.killpg(p.pid, signal.SIGTERM)
            except OSError:
                pass

        def watch_cancel():
            while p.poll() is None:
                time.sleep(2)
                if p.poll() is None and (streamer.cancelled.is_set() or (streamer.turn_id is not None and post_events(streamer.turn_id, []))):
                    streamer.cancelled.set()
                    log("cancelado por el usuario")
                    kill()
                    return

        threading.Thread(target=watch_cancel, daemon=True).start()
        threading.Thread(target=lambda: err_chunks.append(p.stderr.read()), daemon=True).start()
        try:
            p.stdin.write(user_message.encode("utf-8"))
            p.stdin.close()
        except BrokenPipeError:
            pass
        for raw in p.stdout:
            line = raw.decode("utf-8", "replace")
            if debug_file:
                debug_file.write(line)
            streamer.feed(line)
            if streamer.cancelled.is_set():
                kill()
        rc = p.wait()
        time.sleep(0.05)
        return rc, (err_chunks[0] if err_chunks else b"").decode("utf-8", "replace")
    finally:
        try:
            os.remove(mcp_path)
        except OSError:
            pass


def run_with_retry(turn_id, user_message, system_prompt, session_uuid, resume, timeout, budget, tag):
    debug_file = open(os.path.join(LOG_DIR, "%s.jsonl" % tag), "w") if DEBUG else None
    streamer = err = rc = None
    try:
        for attempt in (1, 2):
            streamer = Streamer(turn_id)
            rc, err = run_claude(user_message, system_prompt, session_uuid, resume, streamer, timeout, budget, debug_file)
            r = streamer.result or {}
            blob = (err or "") + " " + json.dumps(r.get("errors", "")) + str(r.get("result", ""))
            if streamer.cancelled.is_set():
                break
            if attempt == 1 and not streamer.text and re.search(r"already in use|already exists", blob, re.I) and not resume:
                resume = True
                continue
            if attempt == 1 and not streamer.text and re.search(r"No conversation found", blob, re.I) and resume:
                resume = False
                continue
            break
    except Exception as e:  # noqa: BLE001
        log("%s: excepcion %r" % (tag, e))
        streamer = streamer or Streamer(turn_id)
        rc, err = -1, repr(e)
    finally:
        if debug_file:
            debug_file.close()
    streamer.flush(force=True)
    r = streamer.result or {}
    text = streamer.text.strip() or (r.get("result") or "").strip()
    error = None
    if streamer.cancelled.is_set():
        error, text = "cancelled", streamer.text.strip()
    elif r.get("is_error") or not r:
        error = ("claude terminó con error: " + (str(r.get("result") or "") or (err or "").strip()[-300:] or "código %s" % rc))[:500]
        if rc in (124, 137):
            error = "tiempo máximo superado (%ds)" % timeout
    elif not text:
        error = "claude no devolvió texto"
    return text, error, rc


def process_chat(turn):
    turn_id = turn["turn_id"]
    log("turno %s (sesion %s, resume=%s)" % (turn_id, turn.get("session_id"), turn.get("resume")))
    started = time.time()
    text, error, rc = run_with_retry(turn_id, turn["user_message"], build_system_prompt("system_prompt.md"), turn["claude_session_uuid"], bool(turn.get("resume")), TIMEOUT, MAX_BUDGET, "turn-%s" % turn_id)
    log("turno %s: %s en %.0fs, %d caracteres, rc=%s%s" % (turn_id, "ERROR" if error else "ok", time.time() - started, len(text), rc, " (%s)" % error if error else ""))
    post_retry("/agent/turns/%s/done" % turn_id, {"text": text or "", "error": error}, "turno %s" % turn_id)


def process_eval(job):
    jid = job["job_id"]
    scope = "la rutina «%s» (id %s)" % (job.get("routine_name") or "?", job["routine_id"]) if job.get("routine_id") else "TODAS las rutinas activas"
    log("evaluacion %s (%s, %s)" % (jid, scope, job.get("trigger")))
    started = time.time()
    import uuid
    msg = "Evalúa el desempeño reciente de %s y ajusta lo que proceda. Disparador: %s." % (scope, {"manual": "la persona lo pidió", "auto": "se acaba de terminar un entrenamiento", "weekly": "revisión semanal"}.get(job.get("trigger"), job.get("trigger")))
    text, error, rc = run_with_retry(None, msg, build_system_prompt("eval_prompt.md"), str(uuid.uuid4()), False, EVAL_TIMEOUT, EVAL_BUDGET, "eval-%s" % jid)
    log("evaluacion %s: %s en %.0fs%s" % (jid, "ERROR" if error else "ok", time.time() - started, " (%s)" % error if error else ""))
    post_retry("/agent/eval/%s/done" % jid, {"summary": text[:3500], "error": error}, "evaluacion %s" % jid)


def main():
    global _stop
    if not BASE:
        sys.exit("TRAINING_URL no definido")
    for d in (LOG_DIR, WORK_DIR):
        os.makedirs(d, exist_ok=True)
    os.makedirs(RUN_DIR, mode=0o700, exist_ok=True)
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: globals().__setitem__("_stop", True))
    log("training-agent worker arrancado, app=%s" % BASE)
    backoff = 2
    while not _stop:
        try:
            status, job = api("GET", "/agent/next?wait=%d" % POLL_WAIT, timeout=POLL_WAIT + 15)
            backoff = 2
            if status == 200 and job:
                (process_eval if job.get("kind") == "eval" else process_chat)(job)
        except urllib.error.HTTPError as e:
            log("app respondió %d, reintento en %ds" % (e.code, backoff))
            time.sleep(backoff)
            backoff = min(backoff * 2, 60)
        except Exception as e:  # noqa: BLE001
            log("sin conexión con la app (%s), reintento en %ds" % (type(e).__name__, backoff))
            time.sleep(backoff)
            backoff = min(backoff * 2, 60)
    log("parado")


if __name__ == "__main__":
    main()
