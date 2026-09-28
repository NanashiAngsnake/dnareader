# -*- coding: utf-8 -*-
import json
import time
import urllib.error
import urllib.request

import chemins
import licences
import version

CACHE = chemins.DONNEES / "licence.json"
DELAI_RESEAU = 6.0
REVERIF_SECONDES = 6 * 3600

_deja_verifie = False


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


def oublie():
    try:
        CACHE.unlink()
    except Exception:
        pass
    return {"ok": True}


def _interroge(serveur: str, cle: str, machine: str) -> dict:
    url = serveur.rstrip("/") + "/licence/verifier"
    corps = json.dumps({"cle": cle, "machine": machine}).encode()
    req = urllib.request.Request(url, corps, {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=DELAI_RESEAU) as r:
        return json.loads(r.read().decode("utf-8"))


def active(serveur: str, cle: str) -> dict:
    cle = licences.normalise(cle)
    if not cle:
        return {"ok": False, "raison": "clé mal formée — vérifie ta saisie"}
    if not serveur:
        return {"ok": False, "raison": "aucun serveur de licence configuré"}
    machine = licences.empreinte_machine()
    try:
        r = _interroge(serveur, cle, machine)
    except urllib.error.URLError as e:
        return {"ok": False, "raison": f"serveur injoignable ({e.reason})"}
    except Exception as e:
        return {"ok": False, "raison": str(e)}
    if not r.get("ok"):
        return {"ok": False, "raison": r.get("raison", "refusée")}
    _ecris({"serveur": serveur, "cle": cle, "machine": machine,
            "plan": r.get("plan", "complet"), "jusqu_a": r.get("jusqu_a", 0),
            "signature": r.get("signature", ""), "verifiee": time.time(),
            "expire": r.get("expire"), "abonnement": r.get("abonnement", "")})
    return {"ok": True, "plan": r.get("plan"), "jusqu_a": r.get("jusqu_a")}


def boutique_ouverte(serveur: str = "") -> dict:
    serveur = (serveur or version.SERVEUR_LICENCE or "").rstrip("/")
    if not serveur:
        return {"ouverte": False, "raison": "aucun serveur"}
    try:
        with urllib.request.urlopen(serveur + "/boutique/etat",
                                    timeout=DELAI_RESEAU) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return {"ouverte": False, "code": e.code}
    except Exception as e:
        return {"ouverte": False, "raison": str(e)[:80]}


def abonne(serveur: str = "") -> dict:
    serveur = (serveur or version.SERVEUR_LICENCE or "").rstrip("/")
    if not serveur:
        return {"ok": False, "raison": "aucun serveur de licence configuré"}
    try:
        req = urllib.request.Request(
            serveur + "/boutique/depuis-app", b"{}",
            {"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=DELAI_RESEAU) as r:
            rep = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        if e.code == 503:
            return {"ok": False, "raison": "la boutique n'est pas encore ouverte"}
        if e.code == 404:
            return {"ok": False, "raison": "ce serveur ne sait pas encore vendre "
                                           "d'abonnement — il est plus ancien "
                                           "que l'application"}
        return {"ok": False, "raison": f"le serveur a repondu {e.code}"}
    except Exception as e:
        return {"ok": False, "raison": f"serveur injoignable ({e})"}
    if not rep.get("ok"):
        return rep
    _ecris({**_lis(), "attente": rep.get("retrait", ""),
            "attente_depuis": time.time(), "serveur": serveur})
    return rep


def attente(serveur: str = "") -> dict:
    d = _lis()
    jeton = d.get("attente") or ""
    serveur = (serveur or d.get("serveur") or version.SERVEUR_LICENCE or "").rstrip("/")
    if not jeton:
        return {"ok": False, "aucune_attente": True}
    try:
        req = urllib.request.Request(
            serveur + "/boutique/retrait",
            json.dumps({"retrait": jeton}).encode(),
            {"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=DELAI_RESEAU) as r:
            rep = json.loads(r.read().decode())
    except Exception as e:
        return {"ok": False, "raison": str(e)}

    if rep.get("expire"):
        _ecris({k: v for k, v in _lis().items()
                if k not in ("attente", "attente_depuis")})
        return {"ok": False, "expire": True, "raison": rep.get("raison", "")}
    if not rep.get("pret"):
        return {"ok": True, "pret": False}

    r = active(serveur, rep["cle"])
    _ecris({k: v for k, v in _lis().items()
            if k not in ("attente", "attente_depuis")})
    if not r.get("ok"):
        return {"ok": False, "pret": True, "cle": rep["cle"],
                "raison": r.get("raison", "activation refusée")}
    return {"ok": True, "pret": True, "active": True}


def etat(reverifie=True) -> dict:
    d = _lis()
    if not d.get("cle"):
        return {"ok": False, "raison": "aucune clé", "aucune_cle": True}

    machine = licences.empreinte_machine()
    if d.get("machine") != machine:
        return {"ok": False, "raison": "cette clé a été activée sur une autre "
                                       "machine", "aucune_cle": False}

    global _deja_verifie
    perime = time.time() > float(d.get("jusqu_a") or 0)
    vieux = time.time() - float(d.get("verifiee") or 0) > REVERIF_SECONDES
    premier = not _deja_verifie

    if reverifie and (perime or vieux or premier):
        _deja_verifie = True
        try:
            r = _interroge(d.get("serveur", ""), d["cle"], machine)
            if r.get("ok"):
                d.update({"plan": r.get("plan", d.get("plan")),
                          "jusqu_a": r.get("jusqu_a", 0),
                          "signature": r.get("signature", ""),
                          "verifiee": time.time(),
                          "expire": r.get("expire", d.get("expire")),
                          "abonnement": r.get("abonnement",
                                              d.get("abonnement", ""))})
                _ecris(d)
                perime = False
            elif r.get("raison"):
                oublie()
                return {"ok": False, "raison": r["raison"], "aucune_cle": True}
        except Exception:
            pass

    if perime:
        return {"ok": False, "raison": "clé à revérifier — connecte-toi une fois",
                "aucune_cle": False}
    fin = d.get("expire")
    return {"ok": True, "plan": d.get("plan", "complet"),
            "jours_restants": max(0, (float(d["jusqu_a"]) - time.time()) / 86400),
            "hors_ligne": time.time() - float(d.get("verifiee") or 0) > 3600,
            "expire": float(fin) if fin else None,
            "abonnement": d.get("abonnement", ""),
            "jours_avant_echeance": (max(0, (float(fin) - time.time()) / 86400)
                                     if fin else None)}


def resume() -> dict:
    d = _lis()
    cle = d.get("cle", "")
    e = etat(reverifie=False)
    return {**e, "cle_masquee": (cle[:9] + "…" + cle[-2:]) if cle else "",
            "serveur": d.get("serveur", "") or version.SERVEUR_LICENCE,
            "serveur_impose": bool(version.SERVEUR_LICENCE)}
