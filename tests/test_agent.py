"""El MCP del asistente contra la app real (servidor local); comprueba lectura, edición con historial y los límites."""
import importlib
import json
import os
import sys
import threading

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "host-agent"))


@pytest.fixture()
def env(mod, anon, monkeypatch):
    from werkzeug.serving import make_server
    srv = make_server("127.0.0.1", 0, mod.app, threaded=True)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    monkeypatch.setenv("TRAINING_URL", "http://127.0.0.1:%d" % srv.server_port)
    monkeypatch.setenv("TRAINING_TOKEN", "tok")
    sys.modules.pop("training_mcp", None)
    mcp = importlib.import_module("training_mcp")
    anon.login()
    yield mcp, anon
    srv.shutdown()


def tool(mcp, tname, /, **args):
    out = {}
    orig = mcp.send
    mcp.send = lambda m: out.update(m)
    try:
        mcp.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": tname, "arguments": args}})
    finally:
        mcp.send = orig
    r = out["result"]
    return r["content"][0]["text"], r["isError"]


def first_ex(mcp, q, **kw):
    text, err = tool(mcp, "exercise_search", q=q, **kw)
    assert not err
    return json.loads(text)["items"][0]["id"]


def test_tools_match_worker_allowlist():
    import worker, training_mcp
    assert {worker.MCP_PREFIX + n for n in training_mcp.TOOLS} == set(worker.ALLOWED)
    assert all(t["inputSchema"]["type"] == "object" for _f, t in training_mcp.TOOLS.values())


def test_read_and_edit_flow(env):
    mcp, me = env
    bench = first_ex(mcp, "barbell bench press - medium grip")
    squat = first_ex(mcp, "barbell squat")
    run = first_ex(mcp, "carrera", category="cardio")
    text, err = tool(mcp, "routine_create", name="Full body", weekdays=[1, 4], reason="Plan inicial", items=[
        {"exercise_id": bench, "sets": 3, "reps_min": 8, "reps_max": 10, "weight": 60, "rest_s": 90},
        {"exercise_id": squat, "sets": 4, "reps_min": 5, "reps_max": 5, "weight": 80},
        {"exercise_id": run, "sets": 1, "duration_s": 1200}])
    assert not err and "creada" in text
    rid = json.loads(tool(mcp, "routine_list")[0])[0]["id"]
    routine = json.loads(tool(mcp, "routine_get", id=rid)[0])
    assert len(routine["items"]) == 3 and routine["revisions"]
    items = routine["items"]
    items[0]["weight"] = 62.5
    text, err = tool(mcp, "routine_update", id=rid, items=items)
    assert err and "motivo" in text.lower()
    text, err = tool(mcp, "routine_update", id=rid, items=items, reason="3x10 con RPE 7: subo 2,5 kg")
    assert not err and "historial" in text
    assert me.get("/api/routines/%d" % rid).get_json()["items"][0]["weight"] == 62.5
    revs = me.get("/api/routines/%d/revisions" % rid).get_json()
    assert revs[0]["source"] == "agent" and "RPE 7" in revs[0]["reason"]
    text, err = tool(mcp, "routine_restore", id=rid, revision_id=revs[0]["id"])
    assert not err and me.get("/api/routines/%d" % rid).get_json()["items"][0]["weight"] == 60
    text, err = tool(mcp, "routine_update", id=rid, reason="Ejercicio inventado", items=[{"exercise_id": "no-existe"}])
    assert err and "no existe" in text
    assert tool(mcp, "exercise_get", id=bench)[1] is False
    assert tool(mcp, "profile_get")[1] is False and tool(mcp, "stats_get", weeks=4)[1] is False
    new = tool(mcp, "exercise_create", name="Remo en anillas", tracking="reps", primary=["lats"])[0]
    assert "creado" in new and me.get("/api/exercises?q=anillas").get_json()["total"] == 1
    assert tool(mcp, "routine_archive", id=rid, reason="Lo pidió la persona")[1] is False
    assert me.get("/api/routines").get_json() == []


def test_session_data_for_evaluation(env):
    mcp, me = env
    bench = first_ex(mcp, "barbell bench press - medium grip")
    r = me.post("/api/routines", json={"name": "Empuje", "items": [{"exercise_id": bench, "sets": 3, "reps_min": 8, "reps_max": 10, "weight": 60}]}).get_json()
    s = me.post("/api/sessions", json={"routine_id": r["id"]}).get_json()
    for reps in (10, 10, 10):
        me.post("/api/sessions/%d/sets" % s["id"], json={"position": 0, "exercise_id": bench, "reps": reps, "weight": 60, "rpe": 7, "rest_s": 100})
    me.post("/api/sessions/%d/finish" % s["id"], json={"total_s": 1800})
    lst = json.loads(tool(mcp, "sessions_list", routine_id=r["id"])[0])
    assert lst[0]["sets_done"] == 3
    full = json.loads(tool(mcp, "session_get", id=lst[0]["id"])[0])
    assert full["sets"][0]["exercise"] and full["sets"][0]["rpe"] == 7 and full["plan"][0]["reps_max"] == 10
    prog = json.loads(tool(mcp, "progress_get", exercise_id=bench)[0])
    assert prog[0]["best_weight"] == 60


def test_errors_are_reported_not_raised(env):
    mcp, _ = env
    text, err = tool(mcp, "routine_get", id=99999)
    assert err and "404" in text
