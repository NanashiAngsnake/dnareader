# -*- coding: utf-8 -*-
import sqlite3
import threading
import time
from pathlib import Path

import chemins

DB_PATH = chemins.DB_CORRECTIONS
MIN_FRAGMENT = 3
_lock = threading.Lock()
_con = None
_cache = None


def _db():
    global _con
    if _con is None:
        _con = sqlite3.connect(DB_PATH, check_same_thread=False)
        _con.execute("""CREATE TABLE IF NOT EXISTS fixes (
            id INTEGER PRIMARY KEY,
            wrong TEXT NOT NULL UNIQUE,
            right_ TEXT NOT NULL,
            source TEXT,
            added REAL,
            hits INTEGER DEFAULT 0
        )""")
        _con.commit()
    return _con


def _reload():
    global _cache
    rows = _db().execute("SELECT wrong, right_ FROM fixes").fetchall()
    _cache = sorted(rows, key=lambda r: -len(r[0]))
    return _cache


def add(wrong: str, right: str, source: str = "") -> dict:
    wrong = (wrong or "").strip()
    right = (right or "").strip()
    if not wrong or not right:
        return {"ok": False, "error": "texte vide"}
    if wrong == right:
        return {"ok": False, "error": "identique à la lecture actuelle"}
    with _lock:
        _db().execute(
            "INSERT INTO fixes (wrong, right_, source, added) VALUES (?,?,?,?) "
            "ON CONFLICT(wrong) DO UPDATE SET right_=excluded.right_, added=excluded.added",
            (wrong, right, source, time.time()))
        _db().commit()
        _reload()
    return {"ok": True, "count": count()}


def remove(wrong: str) -> dict:
    with _lock:
        _db().execute("DELETE FROM fixes WHERE wrong = ?", (wrong,))
        _db().commit()
        _reload()
    return {"ok": True, "count": count()}


def count() -> int:
    return _db().execute("SELECT COUNT(*) FROM fixes").fetchone()[0]


def listing(limit: int = 200):
    rows = _db().execute(
        "SELECT wrong, right_, source, hits FROM fixes ORDER BY added DESC LIMIT ?",
        (limit,)).fetchall()
    return [{"wrong": w, "right": r, "source": s, "hits": h} for w, r, s, h in rows]


def apply(text: str) -> str:
    if not text:
        return text
    fixes = _cache if _cache is not None else _reload()
    if not fixes:
        return text
    for wrong, right in fixes:
        if wrong == text:
            return right
    for wrong, right in fixes:
        if len(wrong) >= MIN_FRAGMENT and wrong in text:
            text = text.replace(wrong, right)
    return text


def note_hits(before: str, after: str) -> None:
    if before == after:
        return
    fixes = _cache or []
    with _lock:
        for wrong, _ in fixes:
            if wrong in before:
                _db().execute("UPDATE fixes SET hits = hits + 1 WHERE wrong = ?", (wrong,))
        _db().commit()


def export_pairs():
    return [{"wrong": w, "right": r} for w, r in (_cache if _cache is not None else _reload())]
