import io
import json

import pytest

from conftest import AG

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64
MP4 = b"\x00\x00\x00\x18ftypmp42" + b"0" * 64


def ex(me, q, **kw):
    r = me.get("/api/exercises", query_string=dict(q=q, **kw)).get_json()
    assert r["items"], q
    return r["items"][0]["id"]


def test_requires_login_and_agent_token(anon):
    assert anon.get("/api/exercises").status_code == 401
    assert anon.get("/media/x/y.png").status_code == 401
    assert anon.get("/").status_code == 302
    assert anon.get("/agent/routines").status_code == 401
    assert anon.get("/agent/routines", headers=AG).status_code == 200
    assert anon.get("/healthz").status_code == 200


def test_library_seeded_with_media_and_search(me):
    m = me.get("/api/meta").get_json()
    assert m["total"] >= 850
    assert {c["id"] for c in m["categories"]} >= {"strength", "cardio", "stretching"}
    r = me.get("/api/exercises", query_string={"q": "bench press", "limit": 5}).get_json()
    assert r["total"] > 3 and all(e["media"] for e in r["items"])
    chest = me.get("/api/exercises", query_string={"muscle": "chest", "equipment": "dumbbell", "limit": 200}).get_json()
    assert chest["total"] > 10 and all("chest" in e["primary"] + e["secondary"] for e in chest["items"])
    cardio = me.get("/api/exercises", query_string={"category": "cardio", "limit": 200}).get_json()
    assert cardio["total"] >= 50 and all(e["tracking"] == "cardio" for e in cardio["items"])
    assert me.get("/api/exercises", query_string={"q": "carrera"}).get_json()["total"] >= 1   # nombres en español de los de cardio
    full = me.get("/api/exercises/%s" % ex(me, "barbell bench press")).get_json()
    assert full["instructions"] and full["media"][0]["url"].startswith("/static/ex/")


def test_custom_exercise_media_upload_and_serve(me):
    e = me.post("/api/exercises", json={"name": "Remo en anillas", "tracking": "reps", "primary": ["lats"], "equipment": "other"}).get_json()
    assert e["source"] == "custom" and e["media"] == []
    up = me.post("/api/exercises/%s/media" % e["id"], data={"file": [(io.BytesIO(PNG), "foto.png"), (io.BytesIO(MP4), "v.mp4")]}, content_type="multipart/form-data")
    assert up.status_code == 201
    media = up.get_json()["media"]
    assert [m["kind"] for m in media] == ["image", "video"] and all(m["own"] for m in media)
    got = me.get(media[0]["url"])
    assert got.status_code == 200 and got.data == PNG and got.headers["Content-Type"] == "image/png" and "sandbox" in got.headers["Content-Security-Policy"]
    assert me.get(media[1]["url"]).headers["Content-Type"] == "video/mp4"
    bad = me.post("/api/exercises/%s/media" % e["id"], data={"file": (io.BytesIO(b"<script>alert(1)</script>"), "x.png")}, content_type="multipart/form-data")
    assert bad.status_code == 415
    assert me.get("/media/%s/../../etc/passwd" % e["id"]).status_code == 404
    assert me.delete("/api/exercises/%s/media/%s" % (e["id"], media[0]["file"])).status_code == 200
    assert me.get(media[0]["url"]).status_code == 404


def test_library_exercise_can_get_own_images_and_fallback(me):
    eid = ex(me, "running treadmill")
    lib = me.get("/api/exercises/" + eid).get_json()
    assert lib["has_own_media"] is False
    up = me.post("/api/exercises/%s/media" % eid, data={"file": (io.BytesIO(PNG), "mia.png")}, content_type="multipart/form-data").get_json()
    assert up["has_own_media"] and up["media"][0]["own"] and up["media"][0]["url"].startswith("/media/")
    me.delete("/api/exercises/%s/media/%s" % (eid, up["media"][0]["file"]))
    assert me.get("/api/exercises/" + eid).get_json()["has_own_media"] is False
    assert me.patch("/api/exercises/" + eid, json={"name_es": "Carrera en cinta", "video_url": "https://youtu.be/abc123", "favorite": True}).get_json()["name_es"] == "Carrera en cinta"
    assert me.patch("/api/exercises/" + eid, json={"video_url": "javascript:alert(1)"}).status_code == 422
    assert me.patch("/api/exercises/" + eid, json={"name": "hack"}).get_json()["name"] != "hack"   # la biblioteca no se renombra
    assert me.delete("/api/exercises/" + eid).status_code == 409


def make_routine(me):
    bench, squat, run = ex(me, "barbell bench press - medium grip"), ex(me, "barbell squat"), ex(me, "running, treadmill")
    return me.post("/api/routines", json={"name": "Full body", "weekdays": [1, 3, 5], "items": [
        {"exercise_id": bench, "sets": 3, "reps_min": 8, "reps_max": 10, "weight": 60, "rest_s": 90},
        {"exercise_id": squat, "sets": 4, "reps_min": 5, "reps_max": 5, "weight": 80, "rest_s": 120, "rest_ex_s": 150},
        {"exercise_id": run, "sets": 1, "duration_s": 900}]}).get_json(), (bench, squat, run)


def test_routine_crud_revisions_restore(me):
    r, (bench, squat, run) = make_routine(me)
    assert [i["exercise_id"] for i in r["items"]] == [bench, squat, run] and r["weekdays"] == [1, 3, 5]
    assert r["items"][2]["tracking"] == "cardio" and r["items"][2]["duration_s"] == 900
    upd = me.put("/api/routines/%d" % r["id"], json={"items": [dict(r["items"][0], weight=62.5)], "reason": "subo peso"}).get_json()
    assert len(upd["items"]) == 1 and upd["items"][0]["weight"] == 62.5
    revs = me.get("/api/routines/%d/revisions" % r["id"]).get_json()
    assert revs[0]["source"] == "user" and revs[0]["restorable"] and revs[0]["items"] == 3
    back = me.post("/api/routines/%d/restore/%d" % (r["id"], revs[0]["id"])).get_json()
    assert len(back["items"]) == 3 and back["items"][0]["weight"] == 60
    assert me.post("/api/routines", json={"name": "x", "items": [{"exercise_id": "no-existe"}]}).status_code == 422
    assert me.post("/api/routines", json={"name": "", "items": []}).status_code == 422
    dup = me.post("/api/routines/%d/duplicate" % r["id"]).get_json()
    assert dup["name"].endswith("(copia)") and len(dup["items"]) == 3
    assert me.delete("/api/routines/%d" % dup["id"]).status_code == 200
    assert [x["id"] for x in me.get("/api/routines").get_json()] == [r["id"]]


def do_workout(me, rid):
    s = me.post("/api/sessions", json={"routine_id": rid}).get_json()
    assert s["status"] == "active" and len(s["plan"]) == 3
    assert me.post("/api/sessions", json={"routine_id": rid}).status_code == 422          # solo uno en curso
    assert me.get("/api/sessions/active").get_json()["id"] == s["id"]
    p = s["plan"]
    for pos, reps, w in ((0, 10, 60), (0, 9, 60), (0, 8, 60), (1, 5, 80)):
        assert me.post("/api/sessions/%d/sets" % s["id"], json={"position": pos, "exercise_id": p[pos]["exercise_id"], "reps": reps, "weight": w, "rest_s": 90, "rpe": 8}).status_code == 201
    me.post("/api/sessions/%d/sets" % s["id"], json={"position": 2, "exercise_id": p[2]["exercise_id"], "duration_s": 900, "distance_m": 2500})
    assert me.patch("/api/sessions/%d" % s["id"], json={"state": {"idx": 1, "phase": "rest", "since": 123}}).get_json()["state"]["phase"] == "rest"
    return me.post("/api/sessions/%d/finish" % s["id"], json={"notes": "bien", "rating": 4, "total_s": 3000}).get_json()


def test_workout_flow_and_stats(me):
    r, _ = make_routine(me)
    done = do_workout(me, r["id"])
    assert done["status"] == "done" and done["total_s"] == 3000 and done["rating"] == 4 and len(done["sets"]) == 5
    assert me.get("/api/sessions/active").get_json() is None
    lst = me.get("/api/sessions").get_json()
    assert lst[0]["sets_done"] == 5 and lst[0]["volume"] == 60 * 10 + 60 * 9 + 60 * 8 + 80 * 5
    st = me.get("/api/stats").get_json()
    assert st["total_sessions"] == 1 and st["this_week"]["sessions"] == 1 and st["this_week"]["cardio_s"] == 900 and st["this_week"]["distance_m"] == 2500
    assert st["streak_days"] == 1 and st["total_time_s"] == 3000 and len(st["weeks"]) == 12
    assert {p["exercise_id"] for p in st["prs"]} and any(m["muscle"] == "chest" for m in st["muscles"])
    prog = me.get("/api/exercises/%s/progress" % r["items"][0]["exercise_id"]).get_json()
    assert prog[0]["best_weight"] == 60 and prog[0]["sets"] == 3
    assert me.delete("/api/sessions/%d" % done["id"]).status_code == 200
    assert me.get("/api/stats").get_json()["total_sessions"] == 0


def test_free_workout_and_abandon(me):
    s = me.post("/api/sessions", json={}).get_json()
    assert s["plan"] == [] and s["routine_name"]
    out = me.post("/api/sessions/%d/finish" % s["id"], json={"abandon": True}).get_json()
    assert out["status"] == "abandoned"
    assert me.get("/api/stats").get_json()["total_sessions"] == 0
    assert me.post("/api/sessions/%d/sets" % s["id"], json={"exercise_id": "x"}).status_code == 422


def test_settings_and_auto_eval_triggers(me, mod):
    assert me.get("/api/settings").get_json()["auto_adjust"] == "off"
    assert me.put("/api/settings", json={"auto_adjust": "bogus"}).status_code == 422
    assert me.put("/api/settings", json={"auto_adjust": "after", "days_per_week": 4, "goal": "hipertrofia"}).get_json()["days_per_week"] == 4
    r, _ = make_routine(me)
    done = do_workout(me, r["id"])
    assert done["eval_job"]
    jobs = me.get("/api/eval").get_json()["jobs"]
    assert jobs[0]["trigger"] == "auto" and jobs[0]["status"] == "queued"
    c = mod.app.test_client()
    job = c.get("/agent/next?wait=0", headers=AG).get_json()
    assert job["kind"] == "eval" and job["routine_id"] == r["id"]
    assert c.post("/agent/eval/%d/done" % job["job_id"], json={"summary": "Subí el press"}, headers=AG).status_code == 200
    assert me.get("/api/eval").get_json()["jobs"][0]["summary"] == "Subí el press"
    assert me.post("/api/eval", json={"routine_id": r["id"]}).status_code == 202
    assert me.post("/api/eval", json={"routine_id": r["id"]}).get_json()["id"] == me.get("/api/eval").get_json()["jobs"][0]["id"]   # no duplica
    assert me.post("/api/eval", json={"routine_id": 999}).status_code == 404


def test_agent_reads_and_edits_routines(me, mod):
    r, (bench, squat, run) = make_routine(me)
    do_workout(me, r["id"])
    c = mod.app.test_client()
    assert c.get("/agent/routines", headers=AG).get_json()[0]["name"] == "Full body"
    assert c.get("/agent/exercises?q=squat", headers=AG).get_json()["items"]
    assert "instructions" in c.get("/agent/exercises/" + bench, headers=AG).get_json()
    assert c.get("/agent/sessions", headers=AG).get_json()[0]["sets_done"] == 5
    sid = c.get("/agent/sessions", headers=AG).get_json()[0]["id"]
    assert len(c.get("/agent/sessions/%d" % sid, headers=AG).get_json()["sets"]) == 5
    assert c.get("/agent/stats", headers=AG).get_json()["total_sessions"] == 1
    assert "settings" in c.get("/agent/profile", headers=AG).get_json()
    items = c.get("/agent/routines/%d" % r["id"], headers=AG).get_json()["items"]
    items[0]["weight"] = 62.5
    assert c.put("/agent/routines/%d" % r["id"], json={"items": items}, headers=AG).status_code == 400       # exige motivo
    up = c.put("/agent/routines/%d" % r["id"], json={"items": items, "reason": "Completó 3x10 con RPE 8: subo 2,5 kg"}, headers=AG)
    assert up.status_code == 200 and up.get_json()["items"][0]["weight"] == 62.5
    revs = me.get("/api/routines/%d/revisions" % r["id"]).get_json()
    assert revs[0]["source"] == "agent" and "RPE 8" in revs[0]["reason"]
    assert me.get("/api/stats").get_json()["adjustments"][0]["routine"] == "Full body"
    assert c.post("/agent/routines/%d/restore/%d" % (r["id"], revs[0]["id"]), headers=AG).get_json()["items"][0]["weight"] == 60
    new = c.post("/agent/routines", json={"name": "Piernas", "items": [{"exercise_id": squat, "sets": 5, "reps_min": 5}], "reason": "Nueva"}, headers=AG)
    assert new.status_code == 201
    assert c.delete("/agent/routines/%d" % new.get_json()["id"], headers=AG).status_code == 200
    assert c.post("/agent/exercises", json={"name": "Mi ejercicio", "tracking": "time"}, headers=AG).status_code == 201


def test_export_import_roundtrip(me, mod):
    r, _ = make_routine(me)
    do_workout(me, r["id"])
    e = me.post("/api/exercises", json={"name": "Remo en anillas", "tracking": "reps"}).get_json()
    me.post("/api/exercises/%s/media" % e["id"], data={"file": (io.BytesIO(PNG), "f.png")}, content_type="multipart/form-data")
    me.patch("/api/exercises/%s" % ex(me, "barbell squat"), json={"favorite": True, "name_es": "Sentadilla con barra"})
    me.put("/api/settings", json={"goal": "fuerza"})
    exp = me.get("/api/export?media=1")
    assert exp.status_code == 200 and "attachment" in exp.headers["Content-Disposition"]
    data = json.loads(exp.data)
    assert data["app"] == "homelab-training" and len(data["routines"]) == 1 and len(data["sessions"]) == 1 and data["exercises"] and any(x.get("media") for x in data["exercises"])
    csv = me.get("/api/export/sessions.csv")
    assert csv.status_code == 200 and b"Barbell" in csv.data and csv.data.count(b"\n") >= 6
    # sobre una instalacion limpia
    me.post("/api/import?mode=replace", json=data)
    again = me.post("/api/import?mode=merge", json=data).get_json()
    assert again["skipped_sessions"] == 1 and again["routines"] == 1                   # la sesion ya existe; la rutina se actualiza por uid
    assert len(me.get("/api/routines").get_json()) == 1 and len(me.get("/api/sessions").get_json()) == 1
    assert me.get("/api/settings").get_json()["goal"] == "fuerza"
    got = me.get("/api/exercises/%s" % e["id"]).get_json()
    assert got["has_own_media"] and me.get(got["media"][0]["url"]).data == PNG
    assert me.get("/api/exercises/%s" % ex(me, "barbell squat")).get_json()["favorite"] is True
    rep = me.post("/api/import?mode=replace", json=data).get_json()
    assert rep["routines"] == 1 and rep["sessions"] == 1
    assert len(me.get("/api/sessions").get_json()) == 1


def test_import_rejects_garbage(me):
    assert me.post("/api/import", json={"app": "otra"}).status_code == 422
    assert me.post("/api/import?mode=wipe", json={"app": "homelab-training", "version": 1}).status_code == 422
    bad = {"app": "homelab-training", "version": 1, "routines": [{"uid": "u1", "name": "R", "items": [{"exercise_id": "../../etc"}, {"exercise_id": "nope"}]}],
           "exercises": [{"id": "c_evil", "source": "custom", "name": "E", "tracking": "reps", "media": [{"file": "../../x.png", "b64": "aaaa"}, {"file": "ok_file1.png", "b64": "!!!"}]}],
           "sessions": [{"uid": "s1", "status": "done", "started": "no-es-numero", "sets": []}]}
    out = me.post("/api/import", json=bad).get_json()
    assert out["skipped_items"] == 2 and out["skipped_sessions"] == 1
    assert me.get("/api/exercises/c_evil").get_json()["media"] == []


def test_chat_roundtrip(me, mod):
    sid = me.post("/api/chat/sessions").get_json()["id"]
    tid = me.post("/api/chat/sessions/%d/messages" % sid, json={"text": "¿Qué entreno hoy?"}).get_json()["turn_id"]
    c = mod.app.test_client()
    job = c.get("/agent/next?wait=0", headers=AG).get_json()
    assert job["kind"] == "chat" and job["turn_id"] == tid and job["user_message"].startswith("¿Qué")
    c.post("/agent/turns/%d/events" % tid, json={"events": [{"type": "delta", "text": "Hoy"}]}, headers=AG)
    assert me.get("/api/chat/turns/%d" % tid).get_json()["events"][0]["text"] == "Hoy"
    c.post("/agent/turns/%d/done" % tid, json={"text": "Piernas"}, headers=AG)
    assert me.get("/api/chat/sessions/%d" % sid).get_json()["turns"][0]["answer"] == "Piernas"


def test_limits_and_origin(me):
    assert me.post("/api/routines", data=b"x" * (300 * 1024), content_type="application/json").status_code == 413
    assert me.post("/api/routines", json={"name": "a", "items": []}, headers={"Origin": "https://evil.example"}).status_code == 403
    me.csrf = "otro"
    assert me.post("/api/routines", json={"name": "a", "items": []}, headers={"X-CSRF-Token": "mal"}).status_code == 403
