#!/usr/bin/env python3
"""Genera data/exercises.json y static/ex/<id>/N.jpg.
Fuente: https://github.com/yuhonas/free-exercise-db (Unlicense / dominio publico): ~870 ejercicios con 2 imagenes y descripcion.
Las imagenes se redimensionan (max. 480 px, JPEG) para que la imagen del contenedor no pese. Se anaden los ejercicios de cardio propios
de data/extra_exercises.json (sin imagen: la persona las sube desde la app). Requiere internet y Pillow. Idempotente (reutiliza lo descargado).
Uso:  python3 tools/build_exercises.py [--no-images]"""
import io
import json
import os
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RAW = "https://raw.githubusercontent.com/yuhonas/free-exercise-db/main"
OUT_DIR = os.path.join(ROOT, "static", "ex")
MAXW = 480


def get(url, tries=4):
    last = None
    for _ in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "homelab-training-build"}), timeout=30) as r:
                return r.read()
        except Exception as e:  # noqa: BLE001
            last = e
    raise RuntimeError("%s: %s" % (url, last))


def fetch_image(rel):
    dst = os.path.join(OUT_DIR, rel)
    if os.path.exists(dst):
        return True
    from PIL import Image
    try:
        im = Image.open(io.BytesIO(get("%s/exercises/%s" % (RAW, rel)))).convert("RGB")
    except Exception as e:  # noqa: BLE001
        print("sin imagen", rel, e, file=sys.stderr)
        return False
    if im.width > MAXW:
        im = im.resize((MAXW, round(im.height * MAXW / im.width)))
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    im.save(dst, "JPEG", quality=74, optimize=True, progressive=True)
    return True


def tracking(e):
    if e["category"] == "cardio":
        return "cardio"
    if e["category"] == "stretching" or e.get("force") == "static":
        return "time"
    return "reps"


def main():
    with open(os.path.join(HERE, "..", "data", "_source.json"), "wb") as f:
        raw = get(RAW + "/dist/exercises.json")
        f.write(raw)
    src = json.loads(raw)
    out = []
    for e in src:
        out.append({
            "id": e["id"], "name": e["name"], "name_es": "", "category": e["category"], "level": e.get("level") or "beginner",
            "equipment": e.get("equipment") or "none", "mechanic": e.get("mechanic") or "", "force": e.get("force") or "",
            "primary": e.get("primaryMuscles") or [], "secondary": e.get("secondaryMuscles") or [],
            "instructions": e.get("instructions") or [], "images": e.get("images") or [], "tracking": None, "source": "lib",
        })
        out[-1]["tracking"] = tracking(out[-1])
    with open(os.path.join(HERE, "..", "data", "extra_exercises.json"), encoding="utf-8") as f:
        for e in json.load(f):
            out.append({"id": e["id"], "name": e["name"], "name_es": e.get("name_es", ""), "category": "cardio", "level": e.get("level", "beginner"),
                        "equipment": e.get("equipment", "body only"), "mechanic": "", "force": "", "primary": e.get("primary", []),
                        "secondary": e.get("secondary", []), "instructions": e.get("instructions", []), "images": [], "tracking": "cardio", "source": "lib"})
    if "--no-images" not in sys.argv:
        rels = [r for e in out for r in e["images"]]
        with ThreadPoolExecutor(10) as ex:
            ok = list(ex.map(fetch_image, rels))
        good = {r for r, k in zip(rels, ok) if k}
        for e in out:
            e["images"] = [r for r in e["images"] if r in good]
        print("imagenes: %d/%d" % (len(good), len(rels)))
    os.remove(os.path.join(HERE, "..", "data", "_source.json"))
    out.sort(key=lambda e: (e["category"] != "cardio", e["name"].lower()))
    with open(os.path.join(HERE, "..", "data", "exercises.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    print("ejercicios:", len(out), "| sin imagen:", sum(1 for e in out if not e["images"]))


if __name__ == "__main__":
    main()
