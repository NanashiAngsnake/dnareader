# -*- coding: utf-8 -*-
import json
import sqlite3
import time

MAX_MESSAGE = 4000
MAX_JOURNAL = 20000
MAX_CONTEXTE = 4000
PAR_HEURE = 10


def prepare(con: sqlite3.Connection):
    con.execute("""CREATE TABLE IF NOT EXISTS rapports(
                     id       INTEGER PRIMARY KEY,
                     machine  TEXT,
                     version  TEXT,
                     message  TEXT NOT NULL,
                     contexte TEXT,
                     journal  TEXT,
                     etat     TEXT NOT NULL DEFAULT 'nouveau',
                     quand    REAL NOT NULL)""")
    con.execute("CREATE INDEX IF NOT EXISTS i_rapports_quand"
                " ON rapports(quand DESC)")
    con.commit()


def _trop_souvent(con, machine: str) -> bool:
    if not machine:
        return False
    n = con.execute("SELECT COUNT(*) FROM rapports WHERE machine=? AND quand>?",
                    (machine, time.time() - 3600)).fetchone()[0]
    return n >= PAR_HEURE


def recois(con, d: dict) -> dict:
    prepare(con)
    message = (d.get("message") or "").strip()[:MAX_MESSAGE]
    if len(message) < 5:
        return {"ok": False, "raison": "dis en deux mots ce qui s'est passé"}
    machine = (d.get("machine") or "")[:64]
    if _trop_souvent(con, machine):
        return {"ok": False, "raison": "trop de signalements d'affilée — "
                                       "réessaie dans une heure"}
    contexte = d.get("contexte")
    contexte = json.dumps(contexte, ensure_ascii=False)[:MAX_CONTEXTE] \
        if contexte else ""
    cur = con.execute(
        "INSERT INTO rapports(machine, version, message, contexte, journal,"
        " etat, quand) VALUES(?,?,?,?,?,?,?)",
        (machine, (d.get("version") or "")[:32], message, contexte,
         (d.get("journal") or "")[-MAX_JOURNAL:], "nouveau", time.time()))
    con.commit()
    return {"ok": True, "numero": cur.lastrowid}


def liste(con, limite=50, tous=False) -> list:
    prepare(con)
    ou = "" if tous else " WHERE etat='nouveau'"
    lignes = con.execute(
        f"SELECT id, machine, version, message, contexte, etat, quand"
        f" FROM rapports{ou} ORDER BY quand DESC LIMIT ?", (limite,)).fetchall()
    return [{"id": i, "machine": (m or "")[:8], "version": v, "message": msg,
             "contexte": json.loads(c) if c else {}, "etat": e, "quand": q}
            for i, m, v, msg, c, e, q in lignes]


def detail(con, numero: int) -> dict:
    prepare(con)
    r = con.execute("SELECT id, machine, version, message, contexte, journal,"
                    " etat, quand FROM rapports WHERE id=?",
                    (numero,)).fetchone()
    if not r:
        return {"ok": False, "raison": "numéro inconnu"}
    return {"ok": True, "id": r[0], "machine": r[1], "version": r[2],
            "message": r[3], "contexte": json.loads(r[4]) if r[4] else {},
            "journal": r[5] or "", "etat": r[6], "quand": r[7]}


def classe(con, numero: int, etat: str) -> dict:
    prepare(con)
    con.execute("UPDATE rapports SET etat=? WHERE id=?", (etat, numero))
    con.commit()
    return {"ok": True, "id": numero, "etat": etat}
