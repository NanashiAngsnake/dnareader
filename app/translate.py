# -*- coding: utf-8 -*-
import json
import sqlite3
import subprocess

import discret
import sys
import threading
import time
from pathlib import Path

import chemins

BASE = Path(__file__).parent
WORKER = BASE / "translate_worker.py"
DB_PATH = chemins.DB_TRADUCTIONS

_proc = None
_lock = threading.Lock()
_error = None
_con = None
_loading = False


def _db():
    global _con
    if _con is None:
        _con = sqlite3.connect(DB_PATH, check_same_thread=False)
        _con.execute("""CREATE TABLE IF NOT EXISTS tr (
            src TEXT PRIMARY KEY, dst TEXT NOT NULL, added REAL)""")
        _con.commit()
    return _con


def cached(text: str):
    row = _db().execute("SELECT dst FROM tr WHERE src = ?", (text,)).fetchone()
    return row[0] if row else None


def _remember(pairs):
    if not pairs:
        return
    now = time.time()
    _db().executemany("INSERT OR REPLACE INTO tr (src, dst, added) VALUES (?,?,?)",
                      [(s, d, now) for s, d in pairs])
    _db().commit()


def cache_count() -> int:
    return _db().execute("SELECT COUNT(*) FROM tr").fetchone()[0]


def available() -> bool:
    try:
        import importlib.util
        return importlib.util.find_spec("transformers") is not None
    except Exception:
        return False


def _alive() -> bool:
    return _proc is not None and _proc.poll() is None


def status() -> dict:
    return {"installed": available(), "loaded": _alive(), "loading": _loading,
            "error": _error, "cached": cache_count() if DB_PATH.exists() else 0}


def _commande_ouvrier(nom: str) -> list:
    import chemins
    if chemins.EMPAQUETEE:
        return [sys.executable, "--ouvrier", nom]
    return [sys.executable, str(WORKER)]


def start() -> bool:
    global _proc, _error, _loading
    with _lock:
        if _alive():
            return True
        if not available():
            _error = "transformers n'est pas installé"
            return False
        _loading = True
    try:
        flags = discret.drapeaux_processus()
        p = subprocess.Popen(
            _commande_ouvrier("translate"),
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, encoding="utf-8", bufsize=1, creationflags=flags,
            env=discret.env_calcul())
        line = p.stdout.readline()
        try:
            msg = json.loads(line or "{}")
        except Exception:
            msg = {}
        with _lock:
            if msg.get("ready"):
                _proc, _error = p, None
                return True
            _error = msg.get("fatal") or "démarrage du moteur de traduction impossible"
        try:
            p.kill()
        except Exception:
            pass
        return False
    finally:
        _loading = False


def stop():
    global _proc
    with _lock:
        if _proc is not None:
            try:
                _proc.stdin.write(json.dumps({"quit": True}) + "\n")
                _proc.stdin.flush()
                _proc.wait(timeout=5)
            except Exception:
                try:
                    _proc.kill()
                except Exception:
                    pass
            _proc = None


def translate(textes: list) -> dict:
    textes = [t for t in (textes or []) if (t or "").strip()]
    if not textes:
        return {"texts": []}

    resultat = {}
    manquants = []
    for t in textes:
        c = cached(t)
        if c is not None:
            resultat[t] = c
        elif t not in manquants:
            manquants.append(t)

    if manquants:
        if not start():
            return {"error": _error or "moteur indisponible"}
        req = json.dumps({"texts": manquants}, ensure_ascii=True)
        try:
            with _lock:
                _proc.stdin.write(req + "\n")
                _proc.stdin.flush()
                line = _proc.stdout.readline()
            rep = json.loads(line or "{}")
        except Exception as e:
            return {"error": f"moteur interrompu : {e}"}
        if rep.get("error"):
            return {"error": rep["error"]}
        sortie = rep.get("texts") or []
        if len(sortie) != len(manquants):
            return {"error": "réponse incohérente du moteur"}
        _remember(list(zip(manquants, sortie)))
        resultat.update(dict(zip(manquants, sortie)))

    return {"texts": [resultat.get(t, "") for t in textes],
            "from_cache": len(textes) - len(manquants)}
