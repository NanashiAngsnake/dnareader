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
PORT = 8879
BASE = f"http://127.0.0.1:{PORT}"
ADMIN = "jeton-admin-de-test"
SECRET = "secret-serveur-de-test"
sys.stdout.reconfigure(encoding="utf-8")


def poste(route, corps):
    req = urllib.request.Request(BASE + route, json.dumps(corps).encode(),
                                 {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=8) as r:
        return json.loads(r.read().decode())


def main():
    tmp = Path(tempfile.mkdtemp(prefix="dnar-licence-"))
    env = dict(os.environ, DNAREADER_ADMIN=ADMIN, DNAREADER_SECRET=SECRET,
               DNAREADER_DONNEES=str(tmp / "serveur"), PYTHONIOENCODING="utf-8")
    srv = subprocess.Popen(
        [str(PY_EXE), str(RACINE / "app" / "serveur_sync.py"),
         "--port", str(PORT), "--host", "127.0.0.1"],
        env=env, cwd=str(RACINE / "app"),
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    echecs = []

    client = tmp / "client"
    code = (
        'import os, sys, json\n'
        f'os.environ["DNAREADER_DONNEES"] = r"{client}"\n'
        f'sys.path.insert(0, r"{RACINE / "app"}")\n'
        'import licence_client\n'
        'q = sys.argv[1]\n'
        f'r = (licence_client.active("{BASE}", sys.argv[2]) if q == "activer"\n'
        '     else licence_client.etat())\n'
        'print(json.dumps(r, ensure_ascii=False))\n')

    def cli(*args):
        out = subprocess.run([str(PY_EXE), "-c", code, *args], capture_output=True,
                             text=True, encoding="utf-8",
                             env=dict(os.environ, PYTHONIOENCODING="utf-8"))
        lignes = (out.stdout or "").strip().splitlines()
        return json.loads(lignes[-1]) if lignes else {"err": (out.stderr or "")[-300:]}

    try:
        for _ in range(60):
            try:
                urllib.request.urlopen(BASE + "/sante", timeout=1)
                break
            except Exception:
                time.sleep(0.4)
        else:
            print("ECHEC : le serveur de licences n'a pas démarré")
            return 1

        print("1. sans jeton d'administration, aucune clé n'est délivrée")
        try:
            poste("/licence/creer", {"admin": "n'importe quoi"})
            echecs.append("une clé a été créée sans le bon jeton")
            print("   REPONSE INATTENDUE : une clé a été créée")
        except urllib.error.HTTPError as e:
            print(f"   refusé : HTTP {e.code}")
            if e.code != 403:
                echecs.append(f"code inattendu : {e.code}")

        print("\n2. avec le jeton, on délivre une clé — « comme si elle avait payé »")
        r = poste("/licence/creer", {"admin": ADMIN, "note": "offerte", "machines": 1})
        cle = r["cle"]
        print(f"   {cle}  (plan {r['plan']}, {r['machines']} machine)")

        print("\n3. le client l'active")
        avant = cli("etat")
        a = cli("activer", cle)
        apres = cli("etat")
        if avant.get("ok") or not a.get("ok") or not apres.get("ok"):
            echecs.append(f"activation ratée : {avant} / {a} / {apres}")
        print(f"   avant : {avant.get('raison')} · après : ok={apres.get('ok')}, "
              f"{apres.get('jours_restants', 0):.0f} jours de grâce")

        print("\n4. une deuxième machine sur une clé à UNE machine")
        r = poste("/licence/verifier", {"cle": cle, "machine": "une-autre-machine"})
        if r.get("ok"):
            echecs.append("une deuxième machine est passée")
        print(f"   refusé : {r.get('raison')}")

        print("\n5. révoquée à distance : ça doit mordre TOUT DE SUITE")
        poste("/licence/etat", {"admin": ADMIN, "cle": cle, "etat": "revoquee"})
        r = cli("etat")
        if r.get("ok"):
            echecs.append("la clé révoquée fonctionne encore")
        print(f"   le client : {r.get('raison')}")

        print("\n6. serveur injoignable, dans la période de grâce")
        poste("/licence/etat", {"admin": ADMIN, "cle": cle, "etat": "active"})
        poste("/licence/liberer", {"admin": ADMIN, "cle": cle})
        cli("activer", cle)
        srv.terminate()
        srv.wait(timeout=5)
        r = cli("etat")
        if not r.get("ok"):
            echecs.append("une coupure de réseau bloque l'application : "
                          "c'est punir les gens honnêtes")
        print(f"   serveur éteint : ok={r.get('ok')} "
              f"(hors ligne : {r.get('hors_ligne')})")
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
    print("\nOK : la clé se délivre, s'active, se limite, se retire tout de "
          "suite,\n     et une coupure de réseau ne bloque pas.")
    return 0


raise SystemExit(main())
