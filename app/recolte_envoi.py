# -*- coding: utf-8 -*-
import base64
import json
import threading
import time

import chemins
import recolte

MARQUEUR = recolte.DOSSIER / "envoyees.txt"

PAR_LOT = 30
PAUSE_ENTRE_LOTS = 20.0
PAUSE_AU_REPOS = 300.0
PAUSE_APRES_ECHEC = 900.0

_fil = None
_stop = threading.Event()
_verrou = threading.Lock()
_dernier = {"envoyees": 0, "connues": 0, "refusees": 0, "quand": 0.0,
            "erreur": ""}


def _deja_envoyees() -> set:
    try:
        return set(MARQUEUR.read_text(encoding="utf-8").split())
    except Exception:
        return set()


def _marque(noms) -> None:
    if not noms:
        return
    try:
        MARQUEUR.parent.mkdir(parents=True, exist_ok=True)
        with MARQUEUR.open("a", encoding="utf-8") as f:
            f.write("".join(n + "\n" for n in noms))
    except Exception:
        pass


def en_attente(limite: int = 0) -> list:
    faites = _deja_envoyees()
    out = []
    try:
        brut = recolte.INDEX.read_text(encoding="utf-8").splitlines()
    except Exception:
        return out
    for ligne in brut:
        try:
            e = json.loads(ligne)
        except Exception:
            continue
        nom = e.get("image") or ""
        if not nom or nom in faites or not e.get("texte") or not e.get("jeu"):
            continue
        if not (recolte.DOSSIER / nom).exists():
            _marque([nom])
            continue
        out.append(e)
        if limite and len(out) >= limite:
            break
    return out


def etat() -> dict:
    with _verrou:
        d = dict(_dernier)
    d["actif"] = bool(_fil and _fil.is_alive())
    d["deja_envoyees"] = len(_deja_envoyees())
    return d


def _lot_a_envoyer():
    attente = en_attente(limite=PAR_LOT * 4)
    if not attente:
        return None, []
    jeu = attente[0]["jeu"]
    return jeu, [e for e in attente if e["jeu"] == jeu][:PAR_LOT]


def envoie_un_lot() -> dict:
    import comptes
    import partage
    e = partage.etat()
    if not e.get("actif") or not e.get("serveur"):
        return {"ok": False, "error": "partage désactivé", "ignore": True}
    c = comptes.etat()
    if not c.get("jeton"):
        return {"ok": False, "error": "aucun compte connecté", "ignore": True}

    jeu, lot = _lot_a_envoyer()
    if not lot:
        return {"ok": True, "vide": True, "gardees": 0}

    charge = []
    noms = []
    for x in lot:
        try:
            brut = (recolte.DOSSIER / x["image"]).read_bytes()
        except Exception:
            continue
        charge.append({"texte": x["texte"],
                       "image": base64.b64encode(brut).decode("ascii")})
        noms.append(x["image"])
    if not charge:
        return {"ok": True, "vide": True, "gardees": 0}

    r = partage._appel("/recolte", {"jeton": c["jeton"], "jeu": jeu,
                                    "lignes": charge}, timeout=60)
    if not r.get("ok"):
        with _verrou:
            _dernier.update(erreur=str(r.get("error") or "envoi refusé"),
                            quand=time.time())
        return r
    _marque(noms)
    with _verrou:
        _dernier.update(envoyees=_dernier["envoyees"] + int(r.get("gardees", 0)),
                        connues=_dernier["connues"] + int(r.get("deja_connues", 0)),
                        refusees=_dernier["refusees"] + int(r.get("refusees", 0)),
                        quand=time.time(), erreur="")
    return r


def _boucle():
    while not _stop.is_set():
        try:
            r = envoie_un_lot()
        except Exception as ex:
            with _verrou:
                _dernier.update(erreur=str(ex), quand=time.time())
            r = {"ok": False}
        if r.get("ignore") or r.get("vide"):
            attente = PAUSE_AU_REPOS
        elif not r.get("ok"):
            attente = PAUSE_APRES_ECHEC
        else:
            attente = PAUSE_ENTRE_LOTS
        _stop.wait(attente)


def demarre() -> bool:
    global _fil
    with _verrou:
        if _fil and _fil.is_alive():
            return False
        _stop.clear()
        _fil = threading.Thread(target=_boucle, name="recolte-envoi", daemon=True)
        _fil.start()
        return True


def arrete() -> None:
    _stop.set()
