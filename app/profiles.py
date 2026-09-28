# -*- coding: utf-8 -*-
import json
import threading
from pathlib import Path

import chemins

STORE = chemins.PROFILS
_lock = threading.Lock()

CHAMPS = ("zone", "opacity", "fontsize", "engine", "stream",
          "mode", "geom", "enhance", "gamehl", "autofreeze")


def _read() -> dict:
    try:
        d = json.loads(STORE.read_text("utf-8"))
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _write(d: dict) -> None:
    tmp = STORE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1), "utf-8")
    tmp.replace(STORE)


def get(game: str) -> dict:
    if not game:
        return {}
    return _read().get(game, {})


def save(game: str, data: dict) -> dict:
    if not game:
        return {"ok": False, "error": "aucun jeu sélectionné"}
    clean = {k: v for k, v in (data or {}).items() if k in CHAMPS}
    if not clean:
        return {"ok": False, "error": "rien à enregistrer"}
    with _lock:
        d = _read()
        prof = d.get(game, {})
        prof.update(clean)
        d[game] = prof
        _write(d)
    return {"ok": True, "profile": prof}


def remove(game: str) -> dict:
    with _lock:
        d = _read()
        d.pop(game, None)
        _write(d)
    return {"ok": True}


def listing() -> list:
    d = _read()
    return [{"game": g, "keys": sorted(p.keys())} for g, p in sorted(d.items())]


def count() -> int:
    return len(_read())
