# -*- coding: utf-8 -*-
import sqlite3
import threading
import time
from pathlib import Path

import chemins

DB_PATH = chemins.DB_VOCABULAIRE
_lock = threading.Lock()
_con = None


def _db():
    global _con
    if _con is None:
        _con = sqlite3.connect(DB_PATH, check_same_thread=False)
        _con.execute("""CREATE TABLE IF NOT EXISTS words (
            id INTEGER PRIMARY KEY,
            expr TEXT NOT NULL,
            reading TEXT,
            gloss TEXT,
            sentence TEXT,
            source TEXT,
            added REAL,
            seen INTEGER DEFAULT 0,
            UNIQUE(expr, reading)
        )""")
        _con.execute("CREATE INDEX IF NOT EXISTS idx_added ON words(added DESC)")
        _con.commit()
    return _con


def add(expr, reading="", gloss="", sentence="", source=""):
    if not (expr or "").strip():
        return {"ok": False, "error": "mot vide"}
    with _lock:
        db = _db()
        db.execute(
            """INSERT INTO words (expr, reading, gloss, sentence, source, added)
               VALUES (?,?,?,?,?,?)
               ON CONFLICT(expr, reading) DO UPDATE SET
                 added=excluded.added,
                 sentence=COALESCE(NULLIF(excluded.sentence,''), words.sentence)""",
            (expr.strip(), reading or "", gloss or "", sentence or "", source or "", time.time()))
        db.commit()
    return {"ok": True, "expr": expr, "count": count()}


def remove(expr, reading=""):
    with _lock:
        db = _db()
        db.execute("DELETE FROM words WHERE expr=? AND reading=?", (expr, reading or ""))
        db.commit()
    return {"ok": True, "count": count()}


def has(expr, reading=""):
    cur = _db().execute("SELECT 1 FROM words WHERE expr=? AND reading=? LIMIT 1",
                        (expr, reading or ""))
    return cur.fetchone() is not None


def count():
    return _db().execute("SELECT COUNT(*) FROM words").fetchone()[0]


def listing(limit=500):
    rows = _db().execute(
        """SELECT expr, reading, gloss, sentence, source, added, seen
           FROM words ORDER BY added DESC LIMIT ?""", (limit,)).fetchall()
    return [{"expr": r[0], "reading": r[1], "gloss": r[2], "sentence": r[3],
             "source": r[4], "added": r[5], "seen": r[6]} for r in rows]


def to_anki_tsv():
    out = []
    for w in listing(100000):
        front = w["expr"]
        back = " / ".join(x for x in (w["reading"], w["gloss"]) if x)
        ctx = (w["sentence"] or "").replace("\t", " ").replace("\n", " ")
        out.append(f"{front}\t{back}\t{ctx}")
    return "\n".join(out)


_ID_MODELE = 1607392319
_ID_PAQUET = 2059400110

_MODELE_CSS = """
.card { font-family: 'Yu Gothic', 'Hiragino Sans', sans-serif;
        font-size: 22px; text-align: center; color: #eef3f4; background: #16202a; }
.expr { font-size: 44px; }
.lecture { color: #91e1e2; font-size: 20px; }
.sens { margin-top: 10px; }
.phrase { margin-top: 16px; font-size: 17px; color: #9fb3bb; font-style: italic; }
.source { margin-top: 12px; font-size: 12px; color: #6b828a; }
"""


def to_anki_apkg(chemin) -> str:
    import genanki

    modele = genanki.Model(
        _ID_MODELE, "Kanji Game Reader",
        fields=[{"name": "Expression"}, {"name": "Lecture"},
                {"name": "Sens"}, {"name": "Phrase"}, {"name": "Source"}],
        templates=[{
            "name": "Reconnaissance",
            "qfmt": '<div class="expr">{{Expression}}</div>',
            "afmt": '{{FrontSide}}<hr id="answer">'
                    '<div class="lecture">{{Lecture}}</div>'
                    '<div class="sens">{{Sens}}</div>'
                    '{{#Phrase}}<div class="phrase">{{Phrase}}</div>{{/Phrase}}'
                    '{{#Source}}<div class="source">{{Source}}</div>{{/Source}}',
        }],
        css=_MODELE_CSS)

    paquet = genanki.Deck(_ID_PAQUET, "Kanji Game Reader")
    for w in listing(100000):
        paquet.add_note(genanki.Note(model=modele, fields=[
            w["expr"] or "", w["reading"] or "", w["gloss"] or "",
            w["sentence"] or "", w["source"] or "",
        ]))
    genanki.Package(paquet).write_to_file(str(chemin))
    return str(chemin)
