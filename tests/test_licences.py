# -*- coding: utf-8 -*-
import os
import sqlite3
import sys
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "app"))
os.environ.setdefault("DNAREADER_DONNEES", str(RACINE / "tests" / "tmp_licences"))
sys.stdout.reconfigure(encoding="utf-8")

import licences

SECRET = "secret-de-test-uniquement"


def main():
    con = sqlite3.connect(":memory:")
    licences.prepare(con)
    echecs = []
    m1, m2, m3 = "machine-un", "machine-deux", "machine-trois"

    print("1. une clé se recopie à la main")
    cle = licences.cree(con, note="offerte à quelqu'un")["cle"]
    print(f"   clé délivrée : {cle}")
    for variante, attendu in [
        (cle, cle),
        (cle.lower(), cle),
        (cle.replace("-", ""), cle),
        (" " + cle.replace("-", " ") + " ", cle),
        (cle[:-1] + ("A" if cle[-1] != "A" else "B"), ""),
        ("DNAR-AAAAA-AAAAA-AAAAA-B", ""),
        ("DNAR-AAAAA-AAAAA-AAAA", ""),
        ("DNAR-AAAAA-AAAAA-AAAIO-A", ""),
    ]:
        eu = licences.normalise(variante)
        if eu != attendu:
            echecs.append(f"« {variante} » -> {eu!r}, attendu {attendu!r}")
    print("   minuscules, espaces, tirets oubliés : acceptés ; "
          "faute de frappe : refusée sans réseau")

    print("\n2. une clé inconnue ne donne rien")
    r = licences.verifie(con, licences.fabrique_cle(), m1, SECRET)
    if r["ok"]:
        echecs.append("une clé jamais délivrée a été acceptée")
    print(f"   refusée : {r.get('raison')}")

    print("\n3. le nombre de machines est limité")
    a = licences.verifie(con, cle, m1, SECRET)
    b = licences.verifie(con, cle, m1, SECRET)
    c = licences.verifie(con, cle, m2, SECRET)
    d = licences.verifie(con, cle, m3, SECRET)
    if not (a["ok"] and b["ok"] and c["ok"]):
        echecs.append("les deux machines permises devraient passer")
    if d["ok"]:
        echecs.append("une troisième machine est passée alors que la clé en permet 2")
    print(f"   machine 1 : {a['ok']} · la même à nouveau : {b['ok']} · "
          f"machine 2 : {c['ok']} · machine 3 : {d['ok']} ({d.get('raison')})")

    print("\n4. on retire et on rend un accès, à distance")
    licences.change_etat(con, cle, "revoquee")
    r = licences.verifie(con, cle, m1, SECRET)
    if r["ok"]:
        echecs.append("une clé révoquée passe encore")
    print(f"   révoquée -> {r.get('raison')}")
    licences.change_etat(con, cle, "active")
    licences.libere_machine(con, cle)
    r = licences.verifie(con, cle, m3, SECRET)
    if not r["ok"]:
        echecs.append("après libération, une nouvelle machine devrait passer")
    print(f"   réactivée et places libérées -> machine 3 : {r['ok']}")

    print("\n5. une clé expirée ne passe plus")
    courte = licences.cree(con, jours=1)["cle"]
    con.execute("UPDATE licences SET expire=? WHERE cle=?",
                (time.time() - 10, courte))
    con.commit()
    r = licences.verifie(con, courte, m1, SECRET)
    if r["ok"]:
        echecs.append("une clé expirée passe encore")
    print(f"   expirée -> {r.get('raison')}")

    print("\n6. le « oui » est signé : pas de faux hors ligne")
    bon = licences.verifie(con, cle, m3, SECRET)
    corps = {k: bon[k] for k in ("cle", "machine", "plan", "jusqu_a")}
    if not licences.signature_valide(corps, bon["signature"], SECRET):
        echecs.append("la signature d'une réponse honnête est refusée")
    faux = dict(corps, jusqu_a=corps["jusqu_a"] + 10 * 365 * 86400)
    if licences.signature_valide(faux, bon["signature"], SECRET):
        echecs.append("GRAVE : une date rallongée à la main passe encore")
    if licences.signature_valide(corps, licences.signe(corps, "autre"), SECRET):
        echecs.append("GRAVE : une signature faite avec un autre secret passe")
    print("   signature honnête acceptée · date rallongée refusée · "
          "autre secret refusé")

    print("\n7. l'empreinte de machine est stable et anonyme")
    e1, e2 = licences.empreinte_machine(), licences.empreinte_machine()
    if e1 != e2:
        echecs.append("l'empreinte change d'un appel à l'autre")
    if len(e1) != 32:
        echecs.append(f"empreinte de longueur inattendue : {len(e1)}")
    nom = os.environ.get("COMPUTERNAME", "")
    if nom and nom.lower() in e1.lower():
        echecs.append("l'empreinte laisse lire le nom de la machine")
    print(f"   {e1} — stable, et ne laisse rien lire")

    print("\n8. ELLE SURVIT À CE QUI SERT À REMETTRE UN ESSAI À ZÉRO")
    avant = os.environ.get("COMPUTERNAME", "")
    os.environ["COMPUTERNAME"] = "PC-RENOMME-POUR-REPARTIR-A-ZERO"
    renomme = licences.empreinte_machine()
    os.environ["COMPUTERNAME"] = avant
    if renomme != e1:
        echecs.append("renommer le PC suffit à remettre l'essai à zéro")
    print(f"   PC renommé  -> {'inchangée' if renomme == e1 else 'A CHANGÉ'}")

    avant_n = os.environ.get("NUMBER_OF_PROCESSORS", "")
    os.environ["NUMBER_OF_PROCESSORS"] = "1"
    autre_cpu = licences.empreinte_machine()
    os.environ["NUMBER_OF_PROCESSORS"] = avant_n
    if autre_cpu != e1:
        echecs.append("changer le nombre de cœurs remet l'essai à zéro")
    print(f"   coeurs à 1  -> {'inchangée' if autre_cpu == e1 else 'A CHANGÉ'}")

    import uuid as _uuid
    vrai = _uuid.getnode
    try:
        _uuid.getnode = lambda: 0x010000000001
        faux1 = licences.empreinte_machine()
        _uuid.getnode = lambda: 0x030000000003
        faux2 = licences.empreinte_machine()
    finally:
        _uuid.getnode = vrai
    if faux1 != faux2:
        echecs.append("une MAC inventée fait changer l'empreinte à chaque "
                      "lancement : essai gratuit infini")
    print(f"   MAC inventée deux fois -> "
          f"{'même empreinte (bien)' if faux1 == faux2 else 'DEUX EMPREINTES'}")

    if licences._machine_guid():
        print(f"   ancrée sur l'installation Windows (MachineGuid) : oui")
    else:
        print("   MachineGuid illisible — repli sur processeur + MAC")

    if echecs:
        print()
        for e in echecs:
            print("  ECHEC :", e)
        return 1
    print("\nOK : la clé limite, se retire, se rend, et son « oui » ne se "
          "fabrique pas hors ligne")
    return 0


raise SystemExit(main())
