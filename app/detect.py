# -*- coding: utf-8 -*-
import base64
import importlib.util
import io
import json
import subprocess

import discret
import sys
import threading
from pathlib import Path

import chemins

BASE = Path(__file__).parent
WORKER = BASE / "detect_worker.py"

_proc = None
_lock = threading.Lock()
_error = None


def available() -> bool:
    try:
        return importlib.util.find_spec("onnxruntime") is not None
    except Exception:
        return False


def _alive() -> bool:
    return _proc is not None and _proc.poll() is None


def status() -> dict:
    return {"installed": available(), "loaded": _alive(), "error": _error}


def _commande_ouvrier(nom: str) -> list:
    import chemins
    if chemins.EMPAQUETEE:
        return [sys.executable, "--ouvrier", nom]
    return [sys.executable, str(WORKER)]


def start() -> bool:
    global _proc, _error
    with _lock:
        if _alive():
            return True
        if not available():
            _error = "onnxruntime absent : ni détecteur, ni relecture japonaise"
            return False
    try:
        flags = discret.drapeaux_processus()
        p = subprocess.Popen(
            _commande_ouvrier("detect"),
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, encoding="utf-8", bufsize=1, creationflags=flags,
            env=discret.env_calcul())
        msg = json.loads(p.stdout.readline() or "{}")
        with _lock:
            if msg.get("ready"):
                _proc, _error = p, None
                return True
            _error = msg.get("fatal") or "démarrage du détecteur impossible"
        try:
            p.kill()
        except Exception:
            pass
        return False
    except Exception as e:
        _error = str(e)
        return False


def stop():
    global _proc
    with _lock:
        if _proc is not None:
            try:
                _proc.stdin.write(json.dumps({"quit": True}) + "\n")
                _proc.stdin.flush()
                _proc.wait(timeout=3)
            except Exception:
                try:
                    _proc.kill()
                except Exception:
                    pass
            _proc = None


def score_boites(img, boites):
    if not boites:
        return []
    if not start():
        return [None] * len(boites)
    try:
        buf = io.BytesIO()
        img.convert("RGB").save(buf, format="BMP")
        req = json.dumps({"img": base64.b64encode(buf.getvalue()).decode(),
                          "boxes": [list(b[:4]) for b in boites]})
        with _lock:
            _proc.stdin.write(req + "\n")
            _proc.stdin.flush()
            rep = json.loads(_proc.stdout.readline() or "{}")
        if rep.get("error"):
            return [None] * len(boites)
        s = rep.get("scores") or []
        return (s + [None] * len(boites))[:len(boites)]
    except Exception:
        return [None] * len(boites)


MODELES = chemins.MODELES


def rec_disponible() -> bool:
    return ((MODELES / "japan_rec.onnx").exists()
            and (MODELES / "japan_dict.txt").exists() and available())


def maison_disponible() -> bool:
    return ((MODELES / "ocr_maison.onnx").exists()
            and (MODELES / "ocr_maison_alphabet.txt").exists() and available())


def juge_complet(img, boites, moteur="rec", maxi=6):
    if not start():
        return [None] * len(boites), []
    try:
        buf = io.BytesIO()
        img.convert("RGB").save(buf, format="BMP")
        req = json.dumps({"mode": "complet",
                          "img": base64.b64encode(buf.getvalue()).decode(),
                          "boxes": [[float(v) for v in b[:4]] for b in boites],
                          "moteur": moteur, "maxi": int(maxi)})
        with _lock:
            _proc.stdin.write(req + "\n")
            _proc.stdin.flush()
            rep = json.loads(_proc.stdout.readline() or "{}")
        if rep.get("error"):
            return [None] * len(boites), []
        notes = rep.get("scores") or []
        return (notes + [None] * len(boites))[:len(boites)], (rep.get("lignes") or [])
    except Exception:
        return [None] * len(boites), []


def lignes_rattrapees(img, deja, moteur="rec", maxi=6):
    if not start():
        return []
    try:
        buf = io.BytesIO()
        img.convert("RGB").save(buf, format="BMP")
        req = json.dumps({"mode": "rattrapees",
                          "img": base64.b64encode(buf.getvalue()).decode(),
                          "boxes": [[float(v) for v in b[:4]] for b in deja],
                          "moteur": moteur, "maxi": int(maxi)})
        with _lock:
            _proc.stdin.write(req + "\n")
            _proc.stdin.flush()
            rep = json.loads(_proc.stdout.readline() or "{}")
        return rep.get("lignes") or []
    except Exception:
        return []


def lire_lignes_maison(img, boites):
    if not boites:
        return []
    if not maison_disponible() or not start():
        return [None] * len(boites)
    try:
        buf = io.BytesIO()
        img.convert("RGB").save(buf, format="BMP")
        req = json.dumps({"mode": "maison",
                          "img": base64.b64encode(buf.getvalue()).decode(),
                          "boxes": [[int(v) for v in b] for b in boites]})
        with _lock:
            _proc.stdin.write(req + "\n")
            _proc.stdin.flush()
            rep = json.loads(_proc.stdout.readline() or "{}")
        if rep.get("error"):
            return [None] * len(boites)
        t = rep.get("textes") or []
        c = rep.get("confiances") or []
        paires = [(t[i] if i < len(t) else None, c[i] if i < len(c) else 0.0)
                  for i in range(len(boites))]
        return paires
    except Exception:
        return [None] * len(boites)


def lire_lignes(img, boites):
    if not boites:
        return []
    if not rec_disponible() or not start():
        return [None] * len(boites)
    try:
        buf = io.BytesIO()
        img.convert("RGB").save(buf, format="BMP")
        req = json.dumps({"mode": "rec",
                          "img": base64.b64encode(buf.getvalue()).decode(),
                          "boxes": [[int(v) for v in b] for b in boites]})
        with _lock:
            _proc.stdin.write(req + "\n")
            _proc.stdin.flush()
            rep = json.loads(_proc.stdout.readline() or "{}")
        if rep.get("error"):
            return [None] * len(boites)
        t = rep.get("textes") or []
        return (t + [None] * len(boites))[:len(boites)]
    except Exception:
        return [None] * len(boites)
