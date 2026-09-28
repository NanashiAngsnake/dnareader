# -*- coding: utf-8 -*-
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
PY_EXE = RACINE / ".venv" / "Scripts" / "python.exe"
PORT = 8881
BASE = f"http://127.0.0.1:{PORT}"
ADMIN = "jeton-admin-de-test"
SECRET = "secret-serveur-de-test"
sys.stdout.reconfigure(encoding="utf-8")


def poste(route, corps):
    req = urllib.request.Request(BASE + route, json.dumps(corps).encode(),
                                 {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read().decode())


def compte(nom):
    preuve = ("derive-pbkdf2-de-test-" + nom).ljust(32, "0")
    r = poste("/inscription", {"identifiant": nom, "preuve": preuve})
    if not r.get("ok"):
        r = poste("/connexion", {"identifiant": nom, "preuve": preuve})
    return r.get("jeton", "")


def main():
    tmp = Path(tempfile.mkdtemp(prefix="dnar-contrib-"))
    env = dict(os.environ, DNAREADER_ADMIN=ADMIN, DNAREADER_SECRET=SECRET,
               DNAREADER_DONNEES=str(tmp), PYTHONIOENCODING="utf-8",
               DNAREADER_ANTI_INONDATION="0")
    srv = subprocess.Popen(
        [str(PY_EXE), str(RACINE / "app" / "serveur_sync.py"),
         "--port", str(PORT), "--host", "127.0.0.1"],
        env=env, cwd=str(RACINE / "app"),
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    echecs = []
    try:
        for _ in range(60):
            try:
                urllib.request.urlopen(BASE + "/sante", timeout=1)
                break
            except Exception:
                time.sleep(0.4)
        else:
            print("ECHEC : le serveur n'a pas démarré")
            return 1

        alice, bob = compte("alice"), compte("bob")
        if not alice or not bob:
            print("ECHEC : comptes non créés")
            return 1

        print("1. une correction proposée mais non confirmée reste EN ATTENTE")
        poste("/correction", {"jeton": alice, "jeu": "FF7R",
                              "faux": "ハイポーシヨン", "juste": "ハイポーション"})
        c = poste("/contributions", {"jeton": alice})
        if c.get("confirmees") != 0 or c.get("en_attente") != 1:
            echecs.append(f"attendu 0 confirmée / 1 en attente, reçu {c}")
        print(f"   confirmées={c.get('confirmees')} · "
              f"en attente={c.get('en_attente')}")

        print("\n2. confirmée par un autre compte, elle est créditée à L'AUTEUR")
        poste("/correction", {"jeton": bob, "jeu": "FF7R",
                              "faux": "ハイポーシヨン", "juste": "ハイポーション"})
        ca = poste("/contributions", {"jeton": alice})
        cb = poste("/contributions", {"jeton": bob})
        if ca.get("confirmees") != 1:
            echecs.append(f"alice devrait avoir 1 confirmée : {ca}")
        if cb.get("confirmees") != 0:
            echecs.append("bob a confirmé, il ne doit pas être crédité "
                          f"comme auteur : {cb}")
        print(f"   alice (auteur) : {ca.get('confirmees')} · "
              f"bob (confirmateur) : {cb.get('confirmees')}")

        print("\n3. LE COMPTEUR NE REND AUCUNE MONNAIE")
        monnaie = [k for k in ca
                   if k in ("par_mois", "mois_gagnes", "mois_accordes",
                            "mois_a_accorder", "avant_le_prochain",
                            "par_mois_lignes", "lignes_recoltees")]
        if monnaie:
            echecs.append(f"le compteur promet encore : {monnaie}")
        print(f"   champs rendus : {sorted(ca)}")

        print("\n4. LES ROUTES QUI OFFRAIENT DES MOIS N'EXISTENT PLUS")
        for route in ("/licence/recompenses", "/licence/recompenser"):
            try:
                r = poste(route, {"admin": ADMIN, "compte": "alice"})
                echecs.append(f"{route} répond encore : {str(r)[:80]}")
                print(f"   {route} -> REPOND ENCORE")
            except urllib.error.HTTPError as e:
                print(f"   {route} -> HTTP {e.code}")
                if e.code not in (404, 405):
                    echecs.append(f"{route} : code inattendu {e.code}")

        print("\n5. LE SEUL CADEAU : l'essai, et il ne se remet pas à zéro")
        machine = "empreinte-de-machine-de-test"
        e1 = poste("/essai", {"cle": "", "machine": machine})
        debut = e1.get("debut")
        print(f"   premier lancement : {e1.get('jours_restants'):.2f} jours")
        for _ in range(3):
            e2 = poste("/essai", {"cle": "", "machine": machine})
        if abs((e2.get("debut") or 0) - (debut or 0)) > 0.001:
            echecs.append("réinstaller a redémarré l'essai")
        print(f"   après 3 « réinstallations » : {e2.get('jours_restants'):.2f} "
              f"jours — même date de départ")
        e3 = poste("/essai", {"cle": "", "machine": "une-autre-machine"})
        if abs((e3.get("debut") or 0) - (debut or 0)) < 0.0001:
            echecs.append("deux machines partagent le même essai")
        print(f"   une autre machine : essai distinct, "
              f"{e3.get('jours_restants'):.2f} jours")
        e4 = poste("/essai", {"cle": "", "machine": ""})
        if e4.get("ok"):
            echecs.append("un essai a démarré sans empreinte de machine")
        print(f"   sans empreinte : refusé — {e4.get('raison')}")
    finally:
        try:
            srv.terminate()
            srv.wait(timeout=5)
        except Exception:
            srv.kill()

    if echecs:
        print()
        for e in echecs:
            print("  ECHEC :", e)
        return 1
    print("\nOK : le compteur compte et ne paie rien, les routes de récompense")
    print("     ont disparu, et l'essai ne se remet pas à zéro")
    return 0


raise SystemExit(main())
