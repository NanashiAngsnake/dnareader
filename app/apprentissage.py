# -*- coding: utf-8 -*-
import json
import math
import sqlite3
import threading
import time
from pathlib import Path

import chemins

DB_PATH = chemins.DB_APPRENTISSAGE
MODELE = chemins.MODELE_APPRENTISSAGE

MIN_EXEMPLES = 40

_lock = threading.Lock()
_con = None
_poids = None

NOMS = ["detecteur", "encre", "dictionnaire", "longueur", "ratio_latin",
        "tout_katakana", "forme_boite", "mots_connus"]


def _db():
    global _con
    if _con is None:
        _con = sqlite3.connect(DB_PATH, check_same_thread=False)
        _con.execute("""CREATE TABLE IF NOT EXISTS exemples (
            id INTEGER PRIMARY KEY,
            texte TEXT NOT NULL,
            trait TEXT NOT NULL,        -- vecteur JSON
            label INTEGER NOT NULL,     -- 1 = vraie lecture, 0 = fausse
            poids REAL DEFAULT 1.0,     -- certitude de l'étiquette
            source TEXT,
            jeu TEXT,
            ajoute REAL,
            UNIQUE(texte, label)
        )""")
        _con.commit()
    return _con


def traits(texte, det, encre, score_dico, box, mots_connus, total_mots):
    from dictionary import is_jp_char
    t = (texte or "").strip()
    n = max(len(t), 1)
    lat = sum(1 for c in t if ("a" <= c.lower() <= "z"))
    jp = sum(1 for c in t if is_jp_char(c))
    kata = sum(1 for c in t if "ァ" <= c <= "ヶ" or c == "ー")
    try:
        bw, bh = float(box[2]), float(box[3])
    except Exception:
        bw = bh = 1.0
    return [
        float(det) if det is not None else 0.5,
        min(float(encre or 0.0) * 4, 1.0),
        float(score_dico or 0.0),
        min(n / 20.0, 1.0),
        lat / float(lat + jp) if (lat + jp) else 0.0,
        1.0 if jp and kata >= jp else 0.0,
        min((bw / bh) / 30.0, 1.0) if bh > 0 else 0.0,
        (mots_connus / float(total_mots)) if total_mots else 0.0,
    ]


def ajoute(texte, vecteur, label, poids=1.0, source="", jeu=""):
    if not texte or not vecteur:
        return False
    with _lock:
        _db().execute(
            "INSERT OR REPLACE INTO exemples "
            "(texte, trait, label, poids, source, jeu, ajoute) VALUES (?,?,?,?,?,?,?)",
            (texte, json.dumps(vecteur), int(label), float(poids), source, jeu, time.time()))
        _db().commit()
    return True


def compte():
    c = _db().execute("SELECT label, COUNT(*) FROM exemples GROUP BY label").fetchall()
    d = {0: 0, 1: 0}
    for lab, n in c:
        d[lab] = n
    return {"faux": d[0], "vrais": d[1], "total": d[0] + d[1]}


def _sigmoide(z):
    if z < -30:
        return 0.0
    if z > 30:
        return 1.0
    return 1.0 / (1.0 + math.exp(-z))


def entraine(iterations=600, pas=0.4, regularisation=0.01):
    global _poids
    lignes = _db().execute("SELECT trait, label, poids FROM exemples").fetchall()
    if len(lignes) < MIN_EXEMPLES:
        return {"ok": False, "error": f"pas assez d'exemples ({len(lignes)}/{MIN_EXEMPLES})"}

    X, y, p = [], [], []
    for trait, lab, poi in lignes:
        try:
            v = json.loads(trait)
        except Exception:
            continue
        if len(v) != len(NOMS):
            continue
        X.append([float(z) for z in v])
        y.append(int(lab))
        p.append(float(poi))
    if len(X) < MIN_EXEMPLES:
        return {"ok": False, "error": "exemples inexploitables"}

    n_pos = max(sum(y), 1)
    n_neg = max(len(y) - n_pos, 1)
    for i in range(len(p)):
        p[i] *= (len(y) / (2.0 * n_pos)) if y[i] == 1 else (len(y) / (2.0 * n_neg))

    d = len(NOMS)
    w = [0.0] * d
    b = 0.0
    for _ in range(iterations):
        gw = [0.0] * d
        gb = 0.0
        for xi, yi, pi in zip(X, y, p):
            pred = _sigmoide(sum(w[j] * xi[j] for j in range(d)) + b)
            err = (pred - yi) * pi
            for j in range(d):
                gw[j] += err * xi[j]
            gb += err
        m = float(len(X))
        for j in range(d):
            w[j] -= pas * (gw[j] / m + regularisation * w[j])
        b -= pas * (gb / m)

    _poids = {"w": w, "b": b, "n": len(X), "noms": NOMS, "date": time.time()}
    MODELE.write_text(json.dumps(_poids, ensure_ascii=False, indent=1), "utf-8")

    bons = sum(1 for xi, yi in zip(X, y)
               if (predit(xi) >= 0.5) == (yi == 1))
    return {"ok": True, "exemples": len(X), "vrais": n_pos, "faux": n_neg,
            "justesse": round(bons / float(len(X)), 3),
            "poids": {k: round(v, 3) for k, v in zip(NOMS, w)}}


def charge():
    global _poids
    if _poids is None and MODELE.exists():
        try:
            _poids = json.loads(MODELE.read_text("utf-8"))
        except Exception:
            _poids = None
    return _poids


def pret() -> bool:
    m = charge()
    return bool(m and m.get("n", 0) >= MIN_EXEMPLES)


def predit(vecteur):
    m = charge()
    if not m:
        return None
    w, b = m["w"], m["b"]
    if len(vecteur) != len(w):
        return None
    return _sigmoide(sum(w[j] * float(vecteur[j]) for j in range(len(w))) + b)


def stats():
    m = charge()
    return {"exemples": compte(), "entraine": bool(m),
            "utilisable": pret(), "min": MIN_EXEMPLES,
            "poids": ({k: round(v, 3) for k, v in zip(m["noms"], m["w"])} if m else None)}
