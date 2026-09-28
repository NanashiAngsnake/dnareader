# -*- coding: utf-8 -*-
import json
import time
import urllib.error
import urllib.request

import chemins
import licence_client
import licences
import version

CACHE = chemins.DONNEES / "essai.json"
DELAI_RESEAU = 6.0
REVERIF = 3600
GRACE_ESSAI_JOURS = 2


def _lis() -> dict:
    try:
        return json.loads(CACHE.read_text("utf-8"))
    except Exception:
        return {}


def _ecris(d: dict):
    try:
        CACHE.write_text(json.dumps(d, ensure_ascii=False, indent=1), "utf-8")
    except Exception:
        pass


def _demande_essai(serveur: str, machine: str) -> dict:
    url = serveur.rstrip("/") + "/essai"
    corps = json.dumps({"machine": machine}).encode()
    req = urllib.request.Request(url, corps, {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=DELAI_RESEAU) as r:
        return json.loads(r.read().decode("utf-8"))


def _essai() -> dict:
    serveur = version.SERVEUR_LICENCE
    machine = licences.empreinte_machine()
    d = _lis()
    vieux = time.time() - float(d.get("vu") or 0) > REVERIF

    if vieux or not d:
        try:
            r = _demande_essai(serveur, machine)
            if r.get("mode") == "essai":
                d = {"machine": machine, "jusqu_a": r.get("jusqu_a", 0),
                     "signature": r.get("signature", ""), "vu": time.time()}
                _ecris(d)
        except Exception:
            pass

    if not d.get("jusqu_a"):
        return {"ok": False, "mode": "essai", "jours_restants": 0,
                "raison": "connecte-toi une fois pour démarrer l'essai gratuit"}

    if d.get("machine") != machine:
        return {"ok": False, "mode": "essai", "jours_restants": 0,
                "raison": "essai démarré sur une autre machine"}

    if time.time() - float(d.get("vu") or 0) > GRACE_ESSAI_JOURS * 86400:
        return {"ok": False, "mode": "essai", "jours_restants": 0,
                "raison": "essai à revérifier — connecte-toi une fois"}

    reste = (float(d["jusqu_a"]) - time.time()) / 86400
    return {"ok": reste > 0, "mode": "essai" if reste > 0 else "expire",
            "jours_restants": max(0.0, reste),
            "raison": "" if reste > 0 else "essai gratuit terminé"}


def etat() -> dict:
    if not version.SERVEUR_LICENCE:
        return {"ok": True, "mode": "libre", "jours_restants": None, "raison": ""}

    cle = licence_client.etat()
    if cle.get("ok"):
        return {"ok": True, "mode": "cle",
                "jours_restants": cle.get("jours_restants"),
                "hors_ligne": cle.get("hors_ligne"), "raison": "",
                "expire": cle.get("expire"),
                "abonnement": cle.get("abonnement", ""),
                "jours_avant_echeance": cle.get("jours_avant_echeance")}

    e = _essai()
    if not cle.get("aucune_cle") and cle.get("raison"):
        e = {**e, "raison_cle": cle["raison"]}
    return e


def peut_lire() -> bool:
    return bool(etat().get("ok"))
