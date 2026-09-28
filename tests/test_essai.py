# -*- coding: utf-8 -*-
import json
import os
import sqlite3
import sys
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "app"))
os.environ["DNAREADER_DONNEES"] = str(RACINE / "tests" / "tmp_essai")
sys.stdout.reconfigure(encoding="utf-8")

import licences

SECRET = "secret-de-test"


def main():
    echecs = []
    con = sqlite3.connect(":memory:")
    licences.prepare(con)
    licences.prepare_essais(con)
    m = "machine-de-test"

    print("1. sans serveur de licence, l'application ne demande rien")
    import version
    ancien = version.SERVEUR_LICENCE
    version.SERVEUR_LICENCE = ""
    import acces
    e = acces.etat()
    if not (e["ok"] and e["mode"] == "libre"):
        echecs.append(f"mode libre attendu, obtenu {e}")
    print(f"   {e['mode']} — ok={e['ok']}")

    print("\n2. le premier contact démarre l'essai, et la date vient du serveur")
    r = licences.essai(con, m, SECRET)
    if not r["ok"] or round(r["jours_restants"]) != licences.ESSAI_JOURS:
        echecs.append(f"essai mal démarré : {r}")
    print(f"   {r['jours_restants']:.2f} jours restants, signé")

    print("\n3. réinstaller ne remet PAS le compteur à zéro")
    debut = r["debut"]
    con.execute("UPDATE essais SET debut=? WHERE machine=?",
                (debut - 3 * 86400, m))
    con.commit()
    r2 = licences.essai(con, m, SECRET)
    reste = r2["jours_restants"]
    if not (3.5 < reste < 4.5):
        echecs.append(f"le compteur a été remis à zéro : {reste:.2f} jours "
                      f"au lieu de ~4")
    print(f"   après 3 jours et une réinstallation : {reste:.2f} jours "
          f"(et non {licences.ESSAI_JOURS})")

    print("\n4. l'essai épuisé, c'est fini")
    con.execute("UPDATE essais SET debut=? WHERE machine=?",
                (time.time() - (licences.ESSAI_JOURS + 1) * 86400, m))
    con.commit()
    r3 = licences.essai(con, m, SECRET)
    if r3["ok"]:
        echecs.append("un essai dépassé passe encore")
    print(f"   {r3['raison']}")

    print("\n5. une clé rouvre l'accès, même après un essai épuisé")
    cle = licences.cree(con, note="abonnement", machines=2, jours=31)["cle"]
    v = licences.verifie(con, cle, m, SECRET)
    if not v["ok"]:
        echecs.append(f"la clé devrait passer : {v}")
    print(f"   {cle} → ok={v['ok']}, plan {v.get('plan')}")

    print("\n6. prolonger un abonnement ne perd pas les jours déjà payés")
    avant = con.execute("SELECT expire FROM licences WHERE cle=?", (cle,)).fetchone()[0]
    p = licences.prolonge(con, cle, 31)
    gagne = (p["expire"] - avant) / 86400
    if not (30.5 < gagne < 31.5):
        echecs.append(f"prolongation de {gagne:.1f} jours au lieu de 31 : "
                      f"renouveler en avance perdrait des jours payés")
    print(f"   {avant:.0f} → {p['expire']:.0f}, soit +{gagne:.1f} jours "
          f"({p['jours_restants']:.0f} au total)")

    print("\n7. prolonger réactive une clé suspendue")
    licences.change_etat(con, cle, "suspendue")
    licences.prolonge(con, cle, 31)
    v = licences.verifie(con, cle, m, SECRET)
    if not v["ok"]:
        echecs.append("un paiement devrait remettre l'accès : la clé reste "
                      f"suspendue ({v.get('raison')})")
    print(f"   suspendue puis payée → ok={v['ok']}")

    version.SERVEUR_LICENCE = ancien
    if echecs:
        print()
        for e in echecs:
            print("  ECHEC :", e)
        return 1
    print("\nOK : l'essai dure sept jours, ne se remet pas à zéro, et la clé "
          "prend le relais")
    return 0


raise SystemExit(main())
