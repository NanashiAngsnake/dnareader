# -*- coding: utf-8 -*-
import base64
import hashlib
import hmac
import json
import os
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import chemins
ETAT = chemins.COMPTE
_lock = threading.Lock()

TOURS = 200_000
EXT = ".dnar"


def derive(motdepasse: str, sel: str) -> str:
    dk = hashlib.pbkdf2_hmac("sha256", (motdepasse or "").encode("utf-8"),
                             (sel or "").encode("utf-8"), TOURS)
    return base64.b64encode(dk).decode()


def sel_de(identifiant: str) -> str:
    return hashlib.sha256(("dnareader:" + (identifiant or "").strip().lower())
                          .encode("utf-8")).hexdigest()[:32]


def etat() -> dict:
    try:
        d = json.loads(ETAT.read_text("utf-8"))
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _ecris_etat(d: dict) -> None:
    tmp = ETAT.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1), "utf-8")
    tmp.replace(ETAT)


def status() -> dict:
    e = etat()
    return {"connecte": bool(e.get("identifiant")),
            "identifiant": e.get("identifiant"),
            "serveur": e.get("serveur", ""),
            "derniere_sync": e.get("derniere_sync")}


def deconnexion() -> dict:
    with _lock:
        e = etat()
        e.pop("identifiant", None)
        e.pop("jeton", None)
        _ecris_etat(e)
    return {"ok": True}


def _charge_modules():
    import corrections
    import profiles
    import vocab
    return vocab, profiles, corrections


def paquet() -> dict:
    vocab, profiles, corrections = _charge_modules()
    return {
        "version": 1,
        "app": "dnareader",
        "quand": time.time(),
        "vocabulaire": vocab.listing(limit=100000),
        "profils": _lis_json(chemins.PROFILS),
        "corrections": corrections.listing(limit=100000),
    }


def _lis_json(p: Path):
    try:
        return json.loads(p.read_text("utf-8"))
    except Exception:
        return {}


def _ecris_json(p: Path, d) -> None:
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1), "utf-8")
    tmp.replace(p)


def _cle_mot(m: dict) -> str:
    return f"{m.get('expr', '')}{m.get('reading', '')}"


def fusionne(distant: dict) -> dict:
    if not isinstance(distant, dict) or distant.get("app") != "dnareader":
        return {"ok": False, "error": "fichier ou réponse non reconnue"}

    ajoutes = {"mots": 0, "profils": 0, "corrections": 0}
    vocab, _, corrections = _charge_modules()

    connus = {_cle_mot(m) for m in vocab.listing(limit=100000)}
    for m in distant.get("vocabulaire") or []:
        if not (m.get("expr") or "").strip():
            continue
        if _cle_mot(m) in connus:
            continue
        vocab.add(m.get("expr", ""), m.get("reading", ""), m.get("gloss", ""),
                  m.get("sentence", ""), m.get("source", ""))
        connus.add(_cle_mot(m))
        ajoutes["mots"] += 1

    pl = _lis_json(BASE / "profils.json")
    for jeu, prof in (distant.get("profils") or {}).items():
        if not isinstance(prof, dict):
            continue
        if jeu not in pl:
            pl[jeu] = {}
            ajoutes["profils"] += 1
        for k, v in prof.items():
            pl[jeu].setdefault(k, v)
    _ecris_json(chemins.PROFILS, pl)

    vues = {(c.get("wrong"), c.get("right"))
            for c in corrections.listing(limit=100000)}
    for c in distant.get("corrections") or []:
        cle = (c.get("wrong"), c.get("right"))
        if not cle[0] or not cle[1] or cle in vues:
            continue
        corrections.add(c.get("wrong", ""), c.get("right", ""), c.get("source", ""))
        vues.add(cle)
        ajoutes["corrections"] += 1

    return {"ok": True, "ajoutes": ajoutes}


def exporte(chemin: str = "") -> dict:
    p = Path(chemin) if chemin else (Path.home() / "Documents" / ("DNAreader" + EXT))
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(paquet(), ensure_ascii=False, indent=1), "utf-8")
        return {"ok": True, "chemin": str(p)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def importe(chemin: str) -> dict:
    try:
        d = json.loads(Path(chemin).read_text("utf-8"))
    except Exception as e:
        return {"ok": False, "error": f"lecture impossible : {e}"}
    return fusionne(d)


def _appel(serveur: str, route: str, corps: dict, timeout=15) -> dict:
    url = serveur.rstrip("/") + route
    data = json.dumps(corps).encode("utf-8")
    req = urllib.request.Request(url, data=data,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read().decode("utf-8"))
        except Exception:
            return {"ok": False, "error": f"HTTP {e.code}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _identifie(serveur, identifiant, motdepasse, route) -> dict:
    if not serveur:
        return {"ok": False, "error": "aucun serveur de synchronisation configuré"}
    if not identifiant or not motdepasse:
        return {"ok": False, "error": "identifiant et mot de passe requis"}
    preuve = derive(motdepasse, sel_de(identifiant))
    r = _appel(serveur, route, {"identifiant": identifiant, "preuve": preuve})
    if not r.get("ok"):
        return r
    with _lock:
        e = etat()
        e.update({"identifiant": identifiant, "jeton": r.get("jeton"),
                  "serveur": serveur})
        _ecris_etat(e)
    return {"ok": True, "identifiant": identifiant}


def inscription(serveur, identifiant, motdepasse) -> dict:
    return _identifie(serveur, identifiant, motdepasse, "/inscription")


def connexion(serveur, identifiant, motdepasse) -> dict:
    return _identifie(serveur, identifiant, motdepasse, "/connexion")


def synchronise() -> dict:
    e = etat()
    serveur, jeton = e.get("serveur"), e.get("jeton")
    if not (serveur and jeton):
        return {"ok": False, "error": "aucun compte connecté"}

    tire = _appel(serveur, "/tirer", {"jeton": jeton})
    if not tire.get("ok"):
        return tire
    resume = {"ajoutes": {"mots": 0, "profils": 0, "corrections": 0}}
    if tire.get("paquet"):
        f = fusionne(tire["paquet"])
        if f.get("ok"):
            resume = f

    pousse = _appel(serveur, "/pousser", {"jeton": jeton, "paquet": paquet()})
    if not pousse.get("ok"):
        return pousse
    with _lock:
        e = etat()
        e["derniere_sync"] = time.time()
        _ecris_etat(e)
    return {"ok": True, "ajoutes": resume.get("ajoutes"),
            "quand": e.get("derniere_sync")}
