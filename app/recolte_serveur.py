# -*- coding: utf-8 -*-
import base64
import hashlib
import os
import struct
import time

import chemins

DOSSIER = chemins.DONNEES / "recolte_recue"

MAX_OCTETS_LIGNE = 400_000
MAX_HAUTEUR = 200
MAX_LARGEUR = 4000
MIN_COTE = 8
MAX_PAR_LOT = 40
LONGUEUR_MAX = 40

PAR_JEU = 20_000
MAX_TOTAL_OCTETS = int(os.environ.get("DNAREADER_RECOLTE_MAX_OCTETS",
                                      str(20 * 1024 ** 3)))
PAR_COMPTE_ET_PAR_JOUR = 10_000


def prepare(con):
    con.execute("""CREATE TABLE IF NOT EXISTS lignes_recoltees(
                     empreinte TEXT PRIMARY KEY,
                     jeu       TEXT NOT NULL,
                     texte     TEXT NOT NULL,
                     compte    TEXT NOT NULL,
                     quand     REAL NOT NULL,
                     octets    INTEGER NOT NULL)""")
    con.execute("CREATE INDEX IF NOT EXISTS i_recolte_jeu "
                "ON lignes_recoltees(jeu)")
    con.execute("CREATE INDEX IF NOT EXISTS i_recolte_compte "
                "ON lignes_recoltees(compte)")
    con.commit()


def _taille_png(octets: bytes):
    if len(octets) < 24 or octets[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    if octets[12:16] != b"IHDR":
        return None
    try:
        larg, haut = struct.unpack(">II", octets[16:24])
    except struct.error:
        return None
    return larg, haut


def _chemin(empreinte: str):
    return DOSSIER / empreinte[:2] / f"{empreinte}.png"


def _octets_stockes(con) -> int:
    r = con.execute("SELECT COALESCE(SUM(octets), 0) FROM lignes_recoltees").fetchone()
    return int(r[0] or 0)


def etat(con) -> dict:
    prepare(con)
    n, o = con.execute("SELECT COUNT(*), COALESCE(SUM(octets), 0) "
                       "FROM lignes_recoltees").fetchone()
    jeux = con.execute("SELECT jeu, COUNT(*) FROM lignes_recoltees "
                       "GROUP BY jeu ORDER BY 2 DESC").fetchall()
    return {"lignes": int(n or 0), "octets": int(o or 0),
            "jeux": [{"jeu": j, "lignes": c} for j, c in jeux]}


def _est_jp(t: str) -> bool:
    for c in t or "":
        o = ord(c)
        if 0x3040 <= o <= 0x30FF or 0x4E00 <= o <= 0x9FFF or 0xFF66 <= o <= 0xFF9D:
            return True
    return False


def recois(con, compte: str, jeu: str, lignes: list) -> dict:
    prepare(con)
    jeu = (jeu or "").strip()[:120]
    if not jeu:
        return {"ok": False, "error": "aucun jeu"}
    if not isinstance(lignes, list) or not lignes:
        return {"ok": False, "error": "lot vide"}
    if len(lignes) > MAX_PAR_LOT:
        return {"ok": False, "error": f"lot trop gros (max {MAX_PAR_LOT})"}

    if _octets_stockes(con) >= MAX_TOTAL_OCTETS:
        return {"ok": False, "error": "la reserve est pleine", "plein": True}

    depuis = time.time() - 86400
    du_jour = con.execute("SELECT COUNT(*) FROM lignes_recoltees "
                          "WHERE compte=? AND quand>=?",
                          (compte, depuis)).fetchone()[0]
    if du_jour >= PAR_COMPTE_ET_PAR_JOUR:
        return {"ok": False, "error": "assez pour aujourd hui, merci",
                "quota": True}

    deja_du_jeu = con.execute("SELECT COUNT(*) FROM lignes_recoltees WHERE jeu=?",
                              (jeu,)).fetchone()[0]

    gardees, connues, refusees = [], [], []
    for l in lignes:
        texte = (l.get("texte") or "").strip()
        b64 = l.get("image") or ""
        if not texte or len(texte) > LONGUEUR_MAX or not _est_jp(texte):
            refusees.append("texte")
            continue
        try:
            brut = base64.b64decode(b64, validate=True)
        except Exception:
            refusees.append("image illisible")
            continue
        if not brut or len(brut) > MAX_OCTETS_LIGNE:
            refusees.append("image trop lourde")
            continue
        taille = _taille_png(brut)
        if not taille:
            refusees.append("pas un PNG")
            continue
        larg, haut = taille
        if haut > MAX_HAUTEUR or larg > MAX_LARGEUR \
                or haut < MIN_COTE or larg < MIN_COTE:
            refusees.append(f"{larg}x{haut} : ce n est pas une ligne")
            continue

        empreinte = hashlib.sha256(brut).hexdigest()
        if con.execute("SELECT 1 FROM lignes_recoltees WHERE empreinte=?",
                       (empreinte,)).fetchone():
            connues.append(empreinte)
            continue
        if deja_du_jeu + len(gardees) >= PAR_JEU:
            refusees.append("ce jeu est complet")
            continue
        gardees.append((empreinte, texte, brut))

    ecrites = 0
    for empreinte, texte, brut in gardees:
        p = _chemin(empreinte)
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(brut)
        except Exception:
            refusees.append("disque")
            continue
        con.execute("INSERT OR IGNORE INTO lignes_recoltees "
                    "VALUES(?,?,?,?,?,?)",
                    (empreinte, jeu, texte, compte, time.time(), len(brut)))
        ecrites += 1
    con.commit()
    return {"ok": True, "gardees": ecrites, "deja_connues": len(connues),
            "refusees": len(refusees),
            "raisons": sorted(set(refusees))[:5],
            "traitees": ecrites + len(connues) + len(refusees)}
