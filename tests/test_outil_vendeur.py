# -*- coding: utf-8 -*-
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
PY_EXE = RACINE / ".venv" / "Scripts" / "python.exe"
OUTIL = RACINE / "outils" / "cles.py"
PORT = 8883
BASE = f"http://127.0.0.1:{PORT}"
ADMIN = "jeton-admin-de-test"
SECRET = "secret-serveur-de-test"
sys.stdout.reconfigure(encoding="utf-8")

echecs = []


def verifie(nom, condition, detail=""):
    print(f"  {'OK  ' if condition else 'ECHEC'} {nom}" + (f" — {detail}" if detail else ""))
    if not condition:
        echecs.append(nom)


def poste(route, corps):
    req = urllib.request.Request(BASE + route, json.dumps(corps).encode(),
                                 {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read().decode())


def cles(*args, env=None):
    r = subprocess.run([str(PY_EXE), str(OUTIL), *args], env=env,
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=30)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def compte(nom):
    preuve = ("derive-pbkdf2-de-test-" + nom).ljust(32, "0")
    r = poste("/inscription", {"identifiant": nom, "preuve": preuve})
    if not r.get("ok"):
        r = poste("/connexion", {"identifiant": nom, "preuve": preuve})
    return r.get("jeton", "")


def main():
    tmp = Path(tempfile.mkdtemp(prefix="dnar-outil-"))
    base_env = dict(os.environ, DNAREADER_ADMIN=ADMIN, DNAREADER_SECRET=SECRET,
                    DNAREADER_DONNEES=str(tmp), PYTHONIOENCODING="utf-8",
                    DNAREADER_ANTI_INONDATION="0")
    srv = subprocess.Popen(
        [str(PY_EXE), str(RACINE / "app" / "serveur_sync.py"),
         "--port", str(PORT), "--host", "127.0.0.1"],
        env=base_env, cwd=str(RACINE / "app"),
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    env = dict(base_env, DNAREADER_SERVEUR=BASE, DNAREADER_ADMIN=ADMIN)
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

        sys.path.insert(0, str(RACINE / "app"))
        import contributions

        print("1. sans jeton d'administration, l'outil refuse de parler")
        code, sortie = cles("liste", env=dict(base_env, DNAREADER_SERVEUR=BASE,
                                              DNAREADER_ADMIN=""))
        verifie("un jeton manquant est signalé, pas ignoré",
                code != 0 and "DNAREADER_ADMIN" in sortie, sortie.strip()[:60])

        print("\n2. créer une clé qui expire dans 3 jours")
        code, sortie = cles("creer", "--note", "achat #1", "--jours", "3", env=env)
        trouve = re.search(r"DNAR-[A-Z0-9-]+", sortie)
        verifie("la clé s'affiche telle qu'on la donne", code == 0 and bool(trouve))
        if not trouve:
            return 1
        cle = trouve.group(0)
        print(f"   {cle}")

        print("\n3. PROLONGER : c'est l'abonnement, et il n'efface pas le reste")
        code, sortie = cles("prolonger", cle, env=env)
        reste = re.search(r"\(([\d.]+) jours restants\)", sortie)
        verifie("un mois s'ajoute aux jours déjà payés", code == 0 and bool(reste)
                and 33.5 < float(reste.group(1)) < 34.5,
                f"3 + 31 = {reste.group(1) if reste else '?'} jours")

        print("\n4. prolonger une clé inconnue échoue au lieu de faire semblant")
        code, sortie = cles("prolonger", "DNAR-AAAAA-AAAAA-AAAAA-A", env=env)
        verifie("le refus remonte comme un échec", code != 0,
                sortie.strip().splitlines()[-1][:60] if sortie.strip() else "")

        print("\n5. ESSAIS : la machine qui teste apparaît, avec ce qui lui reste")
        poste("/essai", {"machine": "empreinte-machine-de-test-0001"})
        code, sortie = cles("essais", env=env)
        verifie("l'essai en cours est listé",
                code == 0 and "empreinte-machine-de-test-0001" in sortie
                and "1 essai(s), dont 1 en cours" in sortie)

        print("\n6. RECOMPENSES : personne n'a encore rien gagné")
        code, sortie = cles("recompenses", env=env)
        verifie("un tableau vide se dit en toutes lettres",
                code == 0 and "personne n'a de mois en attente" in sortie)

        print("\n7. Alice gagne un mois, et l'outil le voit")
        alice, bob = compte("alice"), compte("bob")
        N = contributions.PAR_MOIS
        for i in range(N):
            poste("/correction", {"jeton": alice, "jeu": "JEU",
                                  "faux": f"ハイボーション{i}",
                                  "juste": f"ハイポーション{i}"})
            time.sleep(0.01)
            poste("/correction", {"jeton": bob, "jeu": "JEU",
                                  "faux": f"ハイボーション{i}",
                                  "juste": f"ハイポーション{i}"})
        poste("/licence/verifier", {"cle": cle, "machine": "machine-alice",
                                    "jeton": alice})
        code, sortie = cles("recompenses", env=env)
        verifie("Alice apparaît avec sa clé",
                code == 0 and "alice" in sortie and cle in sortie)
        verifie("Bob, qui n'a fait que confirmer, n'apparaît pas",
                "bob" not in sortie)

        print("\n8. RECOMPENSER : le mois est offert, la clé prolongée")
        avant = poste("/licence/liste", {"admin": ADMIN})
        exp_avant = next(x["expire"] for x in avant["licences"] if x["cle"] == cle)
        code, sortie = cles("recompenser", "alice", env=env)
        apres = poste("/licence/liste", {"admin": ADMIN})
        exp_apres = next(x["expire"] for x in apres["licences"] if x["cle"] == cle)
        gagne = (exp_apres - exp_avant) / 86400
        verifie("un mois offert prolonge bien de 31 jours",
                code == 0 and 30.9 < gagne < 31.1, f"+{gagne:.1f} jours")

        print("\n9. le même mois ne se redonne pas au passage suivant")
        code, sortie = cles("recompenser", "alice", env=env)
        verifie("le second appel est refusé", code != 0,
                sortie.strip().splitlines()[-1][:60] if sortie.strip() else "")

        print("\n10. récompenser un compte qui n'a rien fait est refusé")
        code, sortie = cles("recompenser", "bob", env=env)
        verifie("Bob n'obtient rien", code != 0)

    finally:
        srv.terminate()
        try:
            srv.wait(timeout=5)
        except Exception:
            srv.kill()

    print()
    if echecs:
        print(f"{len(echecs)} ECHEC(S) : " + " · ".join(echecs))
        return 1
    print("OK : les dix commandes du vendeur marchent, prolonger compris —")
    print("     l'abonnement s'encaisse sans fabriquer une requete a la main")
    return 0


if __name__ == "__main__":
    sys.exit(main())
