# -*- coding: utf-8 -*-
"""Délivrer, lister, suspendre les clés d'accès de DNAreader."""
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
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise SystemExit(f"refuse par le serveur ({e.code}) : verifie le jeton")
    except urllib.error.URLError as e:
        raise SystemExit(f"serveur injoignable : {e.reason}")


def quand(t):
    return time.strftime("%Y-%m-%d", time.localtime(t)) if t else "—"


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sous = ap.add_subparsers(dest="quoi", required=True)

    c = sous.add_parser("creer", help="delivrer une cle")
    c.add_argument("--note", default="", help="a qui, et pourquoi")
    c.add_argument("--machines", type=int, default=2)
    c.add_argument("--jours", type=int, default=None, help="sans : illimitee")
    c.add_argument("--plan", default="complet")

    sous.add_parser("liste", help="toutes les cles et leurs activations")

    p = sous.add_parser("prolonger", help="repousser l'echeance : L'ABONNEMENT")
    p.add_argument("cle")
    p.add_argument("--jours", type=int, default=31, help="par defaut un mois")

    p = sous.add_parser("discord", help="la cle d'un compte Discord")
    p.add_argument("id", help="identifiant Discord (clic droit > Copier l'ID)")
    p.add_argument("--jours", type=int, default=0,
                   help="garantir que la cle coure au moins N jours")

    p = sous.add_parser("discord-couper", help="suspendre l'acces d'un Discord")
    p.add_argument("id")

    sous.add_parser("essais", help="les essais gratuits en cours")
    sous.add_parser("boutique", help="qu est-ce qui manque pour encaisser")

    for nom, aide in (("suspendre", "couper l'acces, reversible"),
                      ("revoquer", "couper l'acces definitivement"),
                      ("reactiver", "remettre en service"),
                      ("rendre", "liberer les machines d'une cle")):
        s = sous.add_parser(nom, help=aide)
        s.add_argument("cle")

    a = ap.parse_args()

    if a.quoi == "creer":
        r = appelle("/licence/creer", {"note": a.note, "machines": a.machines,
                                       "jours": a.jours, "plan": a.plan})
        if not r.get("ok"):
            raise SystemExit(f"refuse : {r.get('raison')}")
        print()
        print("  " + r["cle"])
        print()
        print(f"  plan {r['plan']} · {r['machines']} machine(s) · "
              f"{'illimitee' if not a.jours else str(a.jours) + ' jours'}")
        if a.note:
            print(f"  note : {a.note}")
        print()
        print("  A donner tel quel. La personne la colle dans DNAreader,")
        print("  Reglages > Cle d'acces.")
        return

    if a.quoi == "liste":
        r = appelle("/licence/liste", {})
        lignes = r.get("licences") or []
        if not lignes:
            print("aucune cle delivree")
            return
        print(f"{'cle':28} {'etat':11} {'act.':5} {'expire':11} note")
        print("-" * 88)
        for l in lignes:
            print(f"{l['cle']:28} {l['etat']:11} "
                  f"{l['activations']}/{l['machines']:<3} {quand(l['expire']):11} "
                  f"{l.get('note') or ''}")
        print(f"\n{len(lignes)} cle(s)")
        return

    if a.quoi == "prolonger":
        r = appelle("/licence/prolonger", {"cle": a.cle, "jours": a.jours})
        if not r.get("ok"):
            raise SystemExit(f"refuse : {r.get('raison')}")
        print(f"{r['cle']} : +{a.jours} jours -> expire le {quand(r['expire'])}"
              f" ({r['jours_restants']} jours restants)")
        return

    if a.quoi == "discord":
        r = appelle("/licence/discord", {"note": a.id, "jours": a.jours})
        if not r.get("ok"):
            raise SystemExit(f"echec : {r.get('raison')}")
        print()
        print("  " + r["cle"])
        print()
        print(f"  {'cle neuve' if r.get('neuve') else 'cle deja existante'}"
              f" · {r.get('jours_restants', 0):.0f} jour(s) restant(s)")
        if a.jours and not r.get("change"):
            print("  (l'echeance etait deja assez loin : rien n'a ete ajoute)")
        return

    if a.quoi == "discord-couper":
        r = appelle("/licence/discord/retirer", {"note": a.id})
        if not r.get("ok"):
            raise SystemExit(f"echec : {r.get('raison')}")
        print(f"{r.get('cle')} -> suspendue. Prolonger la reactivera.")
        return

    if a.quoi == "essais":
        r = appelle("/licence/essais", {})
        lignes = r.get("essais") or []
        if not lignes:
            print("aucun essai en cours")
            return
        print(f"{'machine':34} {'debut':11} {'vu le':11} reste")
        print("-" * 74)
        for l in lignes:
            reste = l["jours_restants"]
            print(f"{l['machine']:34} {quand(l['debut']):11} "
                  f"{quand(l['derniere']):11} "
                  f"{('%.1f j' % reste) if reste > 0 else 'termine'}")
        encore = sum(1 for l in lignes if l["jours_restants"] > 0)
        print(f"\n{len(lignes)} essai(s), dont {encore} en cours")
        return

    if a.quoi == "boutique":
        r = appelle("/boutique/diagnostic", {})
        print(f"Prix : {r.get('prix')} {r.get('devise')}")
        print(f"Boutique ouverte : {'OUI' if r.get('ouverte') else 'NON'}")
        for cle, titre in (("abonnement_api", "ABONNEMENT AUTOMATIQUE (API PayPal)"),
                           ("virement_discord", "VIREMENT + LIVRAISON DISCORD")):
            d = r.get(cle) or {}
            print()
            print(f"  {titre}")
            print(f"    demande : {d.get('demande')}")
            if d.get("pret"):
                print("    PRET")
                continue
            print(f"    il manque : {', '.join(d.get('manque') or []) or '(rien)'}")
            for i, etape in enumerate(d.get("apres") or [], 1):
                print(f"      {i}. {etape}")
        c = r.get("courriel_facultatif") or {}
        print()
        print(f"  Courriel (facultatif) : "
              f"{'configure' if c.get('pret') else 'absent'} — {c.get('a_quoi')}")
        return

    if a.quoi == "rendre":
        r = appelle("/licence/liberer", {"cle": a.cle})
        print(f"{r.get('liberees', 0)} machine(s) liberee(s) pour {a.cle}")
        return

    etats = {"suspendre": "suspendue", "revoquer": "revoquee",
             "reactiver": "active"}
    r = appelle("/licence/etat", {"cle": a.cle, "etat": etats[a.quoi]})
    if not r.get("ok"):
        raise SystemExit(f"echec : cle inconnue ? ({r})")
    print(f"{r['cle']} -> {r['etat']}")


if __name__ == "__main__":
    sys.exit(main())
