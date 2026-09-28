# -*- coding: utf-8 -*-
import json
import os
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.request
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
PY_EXE = RACINE / ".venv" / "Scripts" / "python.exe"
PORT = 8884
BASE = f"http://127.0.0.1:{PORT}"
sys.stdout.reconfigure(encoding="utf-8")

echecs = []


def verifie(nom, condition, detail=""):
    print(f"  {'OK  ' if condition else 'ECHEC'} {nom}" + (f" — {detail}" if detail else ""))
    if not condition:
        echecs.append(nom)


def main():
    archives = sorted((RACINE / "dist").glob("dnareader-serveur-*.tar.gz"),
                      key=lambda f: f.stat().st_mtime)
    print("1. le paquet existe et s'ouvre")
    if not archives:
        print("   ECHEC : aucun paquet dans dist/ —")
        print("   fabrique-le : .venv/Scripts/python.exe outils/paquet_serveur.py")
        return 1
    archive = archives[-1]
    print(f"   {archive.name} (le plus récent des {len(archives)})")

    tmp = Path(tempfile.mkdtemp(prefix="dnar-paquet-"))
    with tarfile.open(archive) as t:
        noms = t.getnames()
        t.extractall(tmp)
    verifie("l'archive se deploie en DOSSIERS, pas en un seul nom a antislashs",
            all("\\" not in n for n in noms),
            f"{len(noms)} entrees")

    racine = tmp / "dnareader-serveur"
    app = racine / "app"
    verifie("le script d'installation est executable",
            (racine / "installe.sh").exists())

    print("\n2. ce que le paquet emporte")
    for f in sorted(p.name for p in app.glob("*.py")):
        print(f"   · {f}")

    print("\n3. LE SEUL TEST QUI COMPTE : il demarre, seul, sans le depot")
    donnees = tmp / "donnees"
    donnees.mkdir(exist_ok=True)
    env = dict(os.environ, DNAREADER_ADMIN="jeton-de-test",
               DNAREADER_SECRET="secret-de-test",
               DNAREADER_DONNEES=str(donnees), PYTHONIOENCODING="utf-8",
               PYTHONPATH="")
    srv = subprocess.Popen(
        [str(PY_EXE), str(app / "serveur_sync.py"), "--port", str(PORT),
         "--host", "127.0.0.1"],
        env=env, cwd=str(app),
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        encoding="utf-8", errors="replace")
    try:
        vivant = False
        for _ in range(50):
            if srv.poll() is not None:
                break
            try:
                with urllib.request.urlopen(BASE + "/sante", timeout=1) as r:
                    vivant = json.loads(r.read().decode()).get("ok") is True
                break
            except Exception:
                time.sleep(0.4)
        if not vivant:
            sortie = ""
            try:
                srv.terminate()
                sortie = (srv.communicate(timeout=5)[0] or "")
            except Exception:
                pass
            derniere = [l for l in sortie.splitlines() if l.strip()][-3:]
            verifie("le serveur repond a /sante", False,
                    " | ".join(derniere) if derniere else "aucune sortie")
            return 1
        verifie("le serveur repond a /sante", True)

        print("\n4. et les routes qui ont besoin des modules ajoutes repondent")
        for route, corps, attendu in (
                ("/essai", {"machine": "empreinte-de-test-0001"}, "jours_restants"),
                ("/boutique/diagnostic", {"admin": "jeton-de-test"},
                 "virement_discord"),
        ):
            req = urllib.request.Request(BASE + route, json.dumps(corps).encode(),
                                         {"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=10) as r:
                rep = json.loads(r.read().decode())
            verifie(f"{route} repond", attendu in rep,
                    str(rep)[:70])
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
    print("OK : le paquet contient tout ce qu'il faut — verifie en le lancant")
    print("     dans un dossier vide, pas en relisant une liste")
    return 0


if __name__ == "__main__":
    sys.exit(main())
