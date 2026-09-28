# -*- coding: utf-8 -*-
import json
import platform
import urllib.error
import urllib.request

import chemins
import licences
import version

DELAI = 12
LIGNES_JOURNAL = 100


def journal_recent(lignes: int = LIGNES_JOURNAL) -> str:
    try:
        t = chemins.JOURNAL.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""
    return "\n".join(t.splitlines()[-lignes:])


def contexte() -> dict:
    d = {"os": f"{platform.system()} {platform.release()}",
         "version": version.VERSION,
         "python": platform.python_version(),
         "empaquetee": bool(chemins.EMPAQUETEE)}
    try:
        import acces
        e = acces.etat()
        d["acces"] = e.get("mode", "?")
        if e.get("jours_restants") is not None:
            d["jours_restants"] = round(e["jours_restants"], 1)
    except Exception:
        pass
    try:
        import server
        r = dict(getattr(server, "REGLAGES", {}) or {})
        for k in ("jeu", "engine", "mode", "bulle", "stream", "zone", "langue"):
            if k in r:
                d[k] = r[k]
    except Exception:
        pass
    try:
        import precise
        d["precise_dispo"] = bool(precise.available())
    except Exception:
        pass
    return d


def envoie(message: str, avec_journal: bool = True, serveur: str = "") -> dict:
    serveur = (serveur or version.SERVEUR_LICENCE or "").rstrip("/")
    if not serveur:
        return {"ok": False, "raison": "aucun serveur configuré dans cette "
                                       "version — écris-moi directement"}
    corps = {
        "machine": licences.empreinte_machine(),
        "version": version.VERSION,
        "message": (message or "").strip(),
        "contexte": contexte(),
        "journal": journal_recent() if avec_journal else "",
    }
    try:
        req = urllib.request.Request(
            serveur + "/rapport", json.dumps(corps).encode(),
            {"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=DELAI) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return {"ok": False, "raison": "ce serveur ne reçoit pas encore de "
                                           "signalements"}
        return {"ok": False, "raison": f"le serveur a répondu {e.code}"}
    except Exception as e:
        return {"ok": False, "raison": f"serveur injoignable ({e})"}


def apercu(avec_journal: bool = True) -> dict:
    return {"contexte": contexte(),
            "journal": journal_recent() if avec_journal else ""}
