# -*- coding: utf-8 -*-
import json
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import chemins
ETAT = chemins.PARTAGE
_lock = threading.Lock()

ACCORDS_REQUIS = 2


def etat() -> dict:
    try:
        d = json.loads(ETAT.read_text("utf-8"))
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _ecris(d: dict) -> None:
    tmp = ETAT.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1), "utf-8")
    tmp.replace(ETAT)


def status() -> dict:
    e = etat()
    return {"actif": bool(e.get("actif")),
            "serveur": e.get("serveur", ""),
            "envoyees": e.get("envoyees", 0),
            "recues": e.get("recues", 0),
            "derniere": e.get("derniere")}


def regle(actif=None, serveur=None) -> dict:
    with _lock:
        e = etat()
        if actif is not None:
            e["actif"] = bool(actif)
        if serveur is not None:
            e["serveur"] = serveur.strip()
        _ecris(e)
    return status()


def _appel(route: str, corps: dict, methode="POST", timeout=12) -> dict:
    e = etat()
    serveur = e.get("serveur") or ""
    if not serveur:
        return {"ok": False, "error": "aucun serveur de partage configuré"}
    url = serveur.rstrip("/") + route
    try:
        if methode == "GET":
            from urllib.parse import urlencode
            with urllib.request.urlopen(url + "?" + urlencode(corps), timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        req = urllib.request.Request(
            url, data=json.dumps(corps).encode("utf-8"),
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e2:
        try:
            return json.loads(e2.read().decode("utf-8"))
        except Exception:
            return {"ok": False, "error": f"HTTP {e2.code}"}
    except Exception as e2:
        return {"ok": False, "error": str(e2)}


def merite_envoi(faux: str, juste: str, dic=None, tagger=None) -> str:
    faux = (faux or "").strip()
    juste = (juste or "").strip()
    if not faux or not juste:
        return "correction vide"
    if faux == juste:
        return "rien n'a changé"
    if len(juste) > 200 or len(faux) > 200:
        return "trop long pour être une ligne de dialogue"

    from dictionary import is_jp_char
    if not any(is_jp_char(c) for c in juste):
        return "la correction ne contient aucun japonais"

    if dic is not None and tagger is not None:
        import judge
        s_faux = judge.score(faux, dic, tagger)
        s_juste = judge.score(juste, dic, tagger)
        if s_juste < s_faux:
            return (f"la correction est moins plausible que la lecture d'origine "
                    f"({s_juste:.2f} contre {s_faux:.2f})")
    return ""


def propose(jeu: str, faux: str, juste: str, contexte: str = "",
            seconde: float = 0.0, dic=None, tagger=None) -> dict:
    e = etat()
    if not e.get("actif"):
        return {"ok": False, "error": "partage désactivé", "ignore": True}
    if not jeu:
        return {"ok": False, "error": "aucun jeu", "ignore": True}

    refus = merite_envoi(faux, juste, dic, tagger)
    if refus:
        return {"ok": False, "error": refus, "ignore": True}

    import comptes
    c = comptes.etat()
    if not c.get("jeton"):
        return {"ok": False, "error": "connecte-toi pour contribuer", "ignore": True}

    r = _appel("/correction", {"jeton": c["jeton"], "jeu": jeu, "faux": faux,
                               "juste": juste, "contexte": contexte[:300],
                               "seconde": round(float(seconde or 0), 1)})
    if r.get("ok"):
        with _lock:
            d = etat()
            d["envoyees"] = int(d.get("envoyees", 0)) + 1
            d["derniere"] = time.time()
            _ecris(d)
    return r


def tire(jeu: str, appliquer=True) -> dict:
    e = etat()
    if not e.get("actif") or not jeu:
        return {"ok": False, "error": "partage désactivé ou aucun jeu", "ignore": True}

    r = _appel("/corrections", {"jeu": jeu}, methode="GET")
    if not r.get("ok"):
        return r
    liste = r.get("corrections") or []
    if not appliquer:
        return {"ok": True, "corrections": liste}

    import corrections
    connues = {(c.get("wrong"), c.get("right")) for c in corrections.listing(limit=100000)}
    n = 0
    for c in liste:
        cle = (c.get("faux"), c.get("juste"))
        if not cle[0] or not cle[1] or cle in connues:
            continue
        corrections.add(c["faux"], c["juste"], "partagé")
        connues.add(cle)
        n += 1
    with _lock:
        d = etat()
        d["recues"] = int(d.get("recues", 0)) + n
        d["derniere"] = time.time()
        _ecris(d)
    return {"ok": True, "ajoutees": n, "disponibles": len(liste)}


def conteste(jeu: str, faux: str, juste: str) -> dict:
    import comptes
    c = comptes.etat()
    if not c.get("jeton"):
        return {"ok": False, "error": "connecte-toi pour signaler"}
    return _appel("/correction/contester",
                  {"jeton": c["jeton"], "jeu": jeu, "faux": faux, "juste": juste})


def contributions() -> dict:
    e = etat()
    if not e.get("actif"):
        return {"ok": False, "error": "partage désactivé", "inactif": True}
    import comptes
    c = comptes.etat()
    if not c.get("jeton"):
        return {"ok": False, "error": "connecte-toi pour voir tes contributions",
                "sans_compte": True}
    return _appel("/contributions", {"jeton": c["jeton"]})


def propositions(jeu: str) -> dict:
    return _appel("/corrections", {"jeu": jeu, "attente": "1"}, methode="GET")
