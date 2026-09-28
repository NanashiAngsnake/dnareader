# -*- coding: utf-8 -*-
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import time

ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
PREFIXE = "DNAR"
GROUPES, TAILLE = 3, 5

GRACE_JOURS = 14

TOLERANCE_ECHEANCE = 3600


def _controle(corps: str) -> str:
    n = sum(ALPHABET.index(c) * (i + 1) for i, c in enumerate(corps)
            if c in ALPHABET)
    return ALPHABET[n % len(ALPHABET)]


def fabrique_cle() -> str:
    corps = "".join(secrets.choice(ALPHABET) for _ in range(GROUPES * TAILLE))
    bouts = [corps[i:i + TAILLE] for i in range(0, len(corps), TAILLE)]
    return f"{PREFIXE}-" + "-".join(bouts) + "-" + _controle(corps)


def normalise(cle: str) -> str:
    brut = "".join(c for c in (cle or "").upper() if c.isalnum())
    if brut.startswith(PREFIXE):
        brut = brut[len(PREFIXE):]
    if len(brut) != GROUPES * TAILLE + 1:
        return ""
    corps, ctrl = brut[:-1], brut[-1]
    if any(c not in ALPHABET for c in corps) or ctrl != _controle(corps):
        return ""
    bouts = [corps[i:i + TAILLE] for i in range(0, len(corps), TAILLE)]
    return f"{PREFIXE}-" + "-".join(bouts) + "-" + ctrl


def bien_formee(cle: str) -> bool:
    return bool(normalise(cle))


def prepare(con: sqlite3.Connection):
    con.execute("""CREATE TABLE IF NOT EXISTS licences(
                     cle        TEXT PRIMARY KEY,
                     etat       TEXT NOT NULL DEFAULT 'active',
                     plan       TEXT NOT NULL DEFAULT 'complet',
                     machines   INTEGER NOT NULL DEFAULT 2,
                     note       TEXT,
                     expire     REAL,
                     cree       REAL NOT NULL)""")
    try:
        con.execute("ALTER TABLE licences ADD COLUMN compte TEXT")
    except Exception:
        pass
    try:
        con.execute("ALTER TABLE licences ADD COLUMN discord TEXT")
    except Exception:
        pass
    con.execute("""CREATE TABLE IF NOT EXISTS activations(
                     cle       TEXT NOT NULL,
                     machine   TEXT NOT NULL,
                     premiere  REAL NOT NULL,
                     derniere  REAL NOT NULL,
                     PRIMARY KEY (cle, machine))""")
    con.commit()


def prepare_essais(con: sqlite3.Connection):
    con.execute("""CREATE TABLE IF NOT EXISTS essais(
                     machine  TEXT PRIMARY KEY,
                     debut    REAL NOT NULL,
                     derniere REAL NOT NULL)""")
    con.commit()


ESSAI_JOURS = 7


def essai(con, machine: str, secret: str) -> dict:
    machine = (machine or "")[:64]
    if not machine:
        return {"ok": False, "raison": "machine non identifiée"}
    r = con.execute("SELECT debut FROM essais WHERE machine=?", (machine,)).fetchone()
    if r:
        debut = float(r[0])
        con.execute("UPDATE essais SET derniere=? WHERE machine=?",
                    (time.time(), machine))
    else:
        debut = time.time()
        con.execute("INSERT INTO essais VALUES(?,?,?)", (machine, debut, debut))
    con.commit()
    fin = debut + ESSAI_JOURS * 86400
    reste = max(0.0, (fin - time.time()) / 86400)
    corps = {"cle": "", "machine": machine, "plan": "essai",
             "jusqu_a": round(fin, 3)}
    return {"ok": reste > 0, "mode": "essai", "debut": debut,
            "jours_restants": round(reste, 3), "jusqu_a": round(fin, 3),
            "signature": signe(corps, secret),
            "raison": "" if reste > 0 else "essai gratuit terminé"}


def essais(con, limite=200) -> list:
    lignes = con.execute("SELECT machine, debut, derniere FROM essais"
                         " ORDER BY debut DESC LIMIT ?", (limite,)).fetchall()
    return [{"machine": m, "debut": d, "derniere": v,
             "jours_restants": max(0.0, (d + ESSAI_JOURS * 86400 - time.time()) / 86400)}
            for m, d, v in lignes]


def cree(con, plan="complet", machines=2, note="", jours=None) -> dict:
    cle = fabrique_cle()
    con.execute("INSERT INTO licences(cle, plan, machines, note, expire, cree)"
                " VALUES(?,?,?,?,?,?)",
                (cle, plan, int(machines), note or "",
                 (time.time() + jours * 86400) if jours else None, time.time()))
    con.commit()
    return {"cle": cle, "plan": plan, "machines": int(machines),
            "note": note or "", "jours": jours}


def prolonge(con, cle: str, jours: int = 31) -> dict:
    cle = normalise(cle)
    if not cle:
        return {"ok": False, "raison": "clé mal formée"}
    r = con.execute("SELECT expire FROM licences WHERE cle=?", (cle,)).fetchone()
    if not r:
        return {"ok": False, "raison": "clé inconnue"}
    base = max(float(r[0] or 0), time.time())
    fin = base + int(jours) * 86400
    con.execute("UPDATE licences SET expire=?, etat='active' WHERE cle=?",
                (fin, cle))
    con.commit()
    return {"ok": True, "cle": cle, "expire": fin,
            "jours_restants": round((fin - time.time()) / 86400, 1)}


def garantit_jusqu_a(con, cle: str, jours: int = 31) -> dict:
    cle = normalise(cle)
    if not cle:
        return {"ok": False, "raison": "clé mal formée"}
    r = con.execute("SELECT expire FROM licences WHERE cle=?", (cle,)).fetchone()
    if not r:
        return {"ok": False, "raison": "clé inconnue"}
    vise = time.time() + int(jours) * 86400
    actuel = float(r[0] or 0)
    if actuel >= vise - TOLERANCE_ECHEANCE:
        return {"ok": True, "cle": cle, "expire": actuel, "change": False,
                "jours_restants": round((actuel - time.time()) / 86400, 1)}
    con.execute("UPDATE licences SET expire=?, etat='active' WHERE cle=?",
                (vise, cle))
    con.commit()
    return {"ok": True, "cle": cle, "expire": vise, "change": True,
            "jours_restants": round((vise - time.time()) / 86400, 1)}


def cle_du_discord(con, discord_id: str) -> str:
    r = con.execute("SELECT cle FROM licences WHERE discord=?"
                    " ORDER BY cree DESC LIMIT 1", (str(discord_id),)).fetchone()
    return r[0] if r else ""


def cle_pour_discord(con, discord_id: str, jours: int = 0,
                     note: str = "", machines: int = 2) -> dict:
    discord_id = str(discord_id or "").strip()
    if not discord_id.isdigit():
        return {"ok": False, "raison": "identifiant Discord invalide"}
    cle = cle_du_discord(con, discord_id)
    neuve = False
    if not cle:
        cle = cree(con, note=note or f"discord:{discord_id}",
                   machines=machines)["cle"]
        con.execute("UPDATE licences SET discord=? WHERE cle=?",
                    (discord_id, cle))
        con.commit()
        neuve = True
    etat = _etat_brut(con, cle)
    if etat and etat[0] != "active":
        return {"ok": False, "cle": cle, "neuve": neuve,
                "raison": f"clé {etat[0]}"}
    r = {"ok": True, "cle": cle, "neuve": neuve}
    if jours:
        r.update(garantit_jusqu_a(con, cle, jours))
        r["neuve"] = neuve
    else:
        exp = float((etat or [None, None, None, 0])[3] or 0)
        r["expire"] = exp
        r["jours_restants"] = round(max(0.0, (exp - time.time()) / 86400), 1)
    return r


def _etat_brut(con, cle):
    r = con.execute("SELECT etat, plan, machines, expire FROM licences WHERE cle=?",
                    (cle,)).fetchone()
    return r


def verifie(con, cle: str, machine: str, secret: str,
            compte: str = "") -> dict:
    cle = normalise(cle)
    if not cle:
        return {"ok": False, "raison": "clé mal formée"}
    r = _etat_brut(con, cle)
    if not r:
        return {"ok": False, "raison": "clé inconnue"}
    etat, plan, machines, expire = r
    if etat != "active":
        return {"ok": False, "raison": f"clé {etat}"}
    if expire and time.time() > expire:
        return {"ok": False, "raison": "clé expirée"}

    machine = (machine or "")[:64]
    if not machine:
        return {"ok": False, "raison": "machine non identifiée"}

    deja = con.execute("SELECT 1 FROM activations WHERE cle=? AND machine=?",
                       (cle, machine)).fetchone()
    if not deja:
        n = con.execute("SELECT COUNT(*) FROM activations WHERE cle=?",
                        (cle,)).fetchone()[0]
        if n >= machines:
            return {"ok": False, "raison": f"clé déjà activée sur {n} machine(s)",
                    "machines": machines}
        con.execute("INSERT INTO activations VALUES(?,?,?,?)",
                    (cle, machine, time.time(), time.time()))
    else:
        con.execute("UPDATE activations SET derniere=? WHERE cle=? AND machine=?",
                    (time.time(), cle, machine))
    con.commit()

    if compte:
        con.execute("UPDATE licences SET compte=? WHERE cle=? AND "
                    "(compte IS NULL OR compte='')", (compte, cle))
        con.commit()

    jusqu_a = time.time() + GRACE_JOURS * 86400
    if expire:
        jusqu_a = min(jusqu_a, expire)
    corps = {"cle": cle, "machine": machine, "plan": plan,
             "jusqu_a": round(jusqu_a, 3)}
    return {"ok": True, **corps, "signature": signe(corps, secret),
            "grace_jours": GRACE_JOURS}


def signe(corps: dict, secret: str) -> str:
    msg = json.dumps(corps, sort_keys=True, separators=(",", ":")).encode()
    return hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()


def signature_valide(corps: dict, signature: str, secret: str) -> bool:
    attendu = signe({k: corps[k] for k in ("cle", "machine", "plan", "jusqu_a")},
                    secret)
    return hmac.compare_digest(attendu, signature or "")


def cle_du_compte(con, compte: str) -> str:
    r = con.execute("SELECT cle FROM licences WHERE compte=? AND etat='active'"
                    " ORDER BY cree DESC LIMIT 1", (compte,)).fetchone()
    return r[0] if r else ""


def liste(con, limite=200) -> list:
    lignes = con.execute(
        "SELECT cle, etat, plan, machines, note, expire, cree FROM licences"
        " ORDER BY cree DESC LIMIT ?", (limite,)).fetchall()
    out = []
    for cle, etat, plan, machines, note, expire, cree in lignes:
        n = con.execute("SELECT COUNT(*) FROM activations WHERE cle=?",
                        (cle,)).fetchone()[0]
        out.append({"cle": cle, "etat": etat, "plan": plan, "machines": machines,
                    "activations": n, "note": note, "expire": expire,
                    "cree": cree})
    return out


def change_etat(con, cle: str, etat: str) -> dict:
    cle = normalise(cle)
    if etat not in ("active", "suspendue", "revoquee"):
        return {"ok": False, "raison": "état inconnu"}
    n = con.execute("UPDATE licences SET etat=? WHERE cle=?", (etat, cle)).rowcount
    con.commit()
    return {"ok": bool(n), "cle": cle, "etat": etat}


def libere_machine(con, cle: str, machine: str = None) -> dict:
    cle = normalise(cle)
    if machine:
        n = con.execute("DELETE FROM activations WHERE cle=? AND machine=?",
                        (cle, machine)).rowcount
    else:
        n = con.execute("DELETE FROM activations WHERE cle=?", (cle,)).rowcount
    con.commit()
    return {"ok": True, "liberees": n}


def _machine_guid() -> str:
    try:
        import winreg
        k = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                           r"SOFTWARE\Microsoft\Cryptography", 0,
                           winreg.KEY_READ | winreg.KEY_WOW64_64KEY)
        with k:
            return str(winreg.QueryValueEx(k, "MachineGuid")[0])
    except Exception:
        return ""


def _mac_reelle() -> str:
    try:
        import uuid
        n = uuid.getnode()
        if (n >> 40) & 1:
            return ""
        return f"{n:012x}"
    except Exception:
        return ""


def empreinte_machine() -> str:
    bouts = [
        _machine_guid(),
        os.environ.get("PROCESSOR_IDENTIFIER", ""),
        _mac_reelle(),
    ]
    if not any(b for b in bouts):
        return ""
    brut = "|".join(bouts).encode("utf-8", "replace")
    return hashlib.sha256(brut).hexdigest()[:32]
