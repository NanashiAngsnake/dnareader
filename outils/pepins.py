# -*- coding: utf-8 -*-
"""Lire les signalements de problème envoyés depuis l'application."""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

SERVEUR = os.environ.get("DNAREADER_SERVEUR", "").rstrip("/")
ADMIN = os.environ.get("DNAREADER_ADMIN", "")


def appelle(route: str, corps: dict) -> dict:
    if not SERVEUR:
        raise SystemExit("DNAREADER_SERVEUR n'est pas defini")
    if not ADMIN:
        raise SystemExit("DNAREADER_ADMIN n'est pas defini")
    req = urllib.request.Request(
        SERVEUR + route, json.dumps({**corps, "admin": ADMIN}).encode(),
        {"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise SystemExit("ce serveur ne recoit pas encore de signalements"
                             " : redeploie-le")
        raise SystemExit(f"refuse par le serveur ({e.code}) : verifie le jeton")
    except urllib.error.URLError as e:
        raise SystemExit(f"serveur injoignable : {e.reason}")


def quand(t: float) -> str:
    d = time.time() - (t or 0)
    if d < 3600:
        return f"il y a {int(d // 60)} min"
    if d < 86400:
        return f"il y a {int(d // 3600)} h"
    return time.strftime("%d/%m %H:%M", time.localtime(t or 0))


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    s = p.add_subparsers(dest="quoi", required=True)
    l = s.add_parser("liste", help="les signalements a traiter")
    l.add_argument("--tous", action="store_true", help="y compris les traites")
    for nom in ("lire", "traite", "ignore"):
        c = s.add_parser(nom)
        c.add_argument("numero", type=int)
    a = p.parse_args()

    if a.quoi == "liste":
        r = appelle("/rapport/liste", {"etat": "tous" if a.tous else "nouveau"})
        rr = r.get("rapports", [])
        if not rr:
            print("aucun signalement" + ("" if a.tous else " a traiter"))
            return 0
        for x in rr:
            ctx = x.get("contexte") or {}
            bout = " ".join(f"{k}={ctx[k]}" for k in
                            ("version", "os", "jeu", "engine", "acces")
                            if k in ctx)
            marque = "" if x["etat"] == "nouveau" else f" [{x['etat']}]"
            print(f"#{x['id']}{marque}  {quand(x['quand'])}  ({x['machine']})")
            print(f"   {x['message'].strip().splitlines()[0][:100]}")
            if bout:
                print(f"   {bout}")
        print(f"({len(rr)} signalement(s) - 'pepins.py lire N' pour le detail)")
        return 0

    if a.quoi == "lire":
        r = appelle("/rapport/detail", {"jours": a.numero})
        if not r.get("ok"):
            raise SystemExit(r.get("raison", "numero inconnu"))
        print(f"#{r['id']}  {quand(r['quand'])}  machine {r['machine'][:12]}"
              f"  version {r['version']}  [{r['etat']}]")
        print()
        print(r["message"])
        print()
        for k, v in (r.get("contexte") or {}).items():
            print(f"  {k} : {v}")
        if r.get("journal"):
            print()
            print("--- journal ---")
            print(r["journal"])
        return 0

    r = appelle("/rapport/classer",
                {"jours": a.numero,
                 "etat": "traite" if a.quoi == "traite" else "ignore"})
    print(f"#{r.get('id')} -> {r.get('etat')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
