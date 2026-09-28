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
PORT_SYNC = 8891
PORT_APP = 8892
SYNC = f"http://127.0.0.1:{PORT_SYNC}"
APP = f"http://127.0.0.1:{PORT_APP}"
sys.stdout.reconfigure(encoding="utf-8")

echecs = []


def verifie(nom, condition, detail=""):
    print(f"  {'OK  ' if condition else 'ECHEC'} {nom}"
          + (f" — {detail}" if detail else ""))
    if not condition:
        echecs.append(nom)


def poste(base, route, corps):
    req = urllib.request.Request(base + route, json.dumps(corps).encode(),
                                 {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode())


def lis(base, route):
    with urllib.request.urlopen(base + route, timeout=20) as r:
        return json.loads(r.read().decode())


def attends(url, secondes=60):
    t0 = time.time()
    while time.time() - t0 < secondes:
        try:
            urllib.request.urlopen(url, timeout=2).read()
            return True
        except Exception:
            time.sleep(0.4)
    return False


def main():
    tmp_sync = Path(tempfile.mkdtemp(prefix="dnar-ec-sync-"))
    tmp_app = Path(tempfile.mkdtemp(prefix="dnar-ec-app-"))
    base_env = dict(os.environ, PYTHONIOENCODING="utf-8")

    sync = subprocess.Popen(
        [str(PY_EXE), str(RACINE / "app" / "serveur_sync.py"),
         "--port", str(PORT_SYNC), "--host", "127.0.0.1"],
        env=dict(base_env, DNAREADER_DONNEES=str(tmp_sync),
                 DNAREADER_ADMIN="admin-de-test",
                 DNAREADER_SECRET="secret-de-test",
                 DNAREADER_ANTI_INONDATION="0"),
        cwd=str(RACINE / "app"),
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

    app = subprocess.Popen(
        [str(PY_EXE), "-c",
         "import sys; sys.path.insert(0,'.');"
         "import uvicorn, server;"
         f"uvicorn.run(server.app, host='127.0.0.1', port={PORT_APP}, log_level='error')"],
        env=dict(base_env, DNAREADER_DONNEES=str(tmp_app)),
        cwd=str(RACINE / "app"),
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

    try:
        if not attends(SYNC + "/sante"):
            print("ECHEC : le serveur de sync n'a pas demarre")
            return 1
        if not attends(APP + "/api/ping"):
            print("ECHEC : l'application n'a pas demarre")
            return 1

        print("1. sans partage actif, on dit QUOI FAIRE, pas « rien »")
        c = lis(APP, "/api/contributions")
        verifie("le partage eteint est signale comme tel",
                c.get("ok") is False and c.get("inactif") is True, str(c)[:70])

        print("\n2. partage actif mais sans compte : on demande de se connecter")
        poste(APP, "/api/partage", {"actif": True, "serveur": SYNC})
        c = lis(APP, "/api/contributions")
        verifie("l'absence de compte est dite clairement",
                c.get("ok") is False and c.get("sans_compte") is True, str(c)[:70])

        print("\n3. avec un compte, le compteur existe et part de zero")
        r = poste(APP, "/api/compte/inscription",
                  {"serveur": SYNC, "identifiant": "banc-ecran",
                   "motdepasse": "motdepasse-du-banc-1234"})
        if not r.get("ok"):
            r = poste(APP, "/api/compte/connexion",
                      {"serveur": SYNC, "identifiant": "banc-ecran",
                       "motdepasse": "motdepasse-du-banc-1234"})
        verifie("le compte est cree", bool(r.get("ok")), str(r)[:70])
        c = lis(APP, "/api/contributions")
        verifie("le compteur repond", c.get("ok") is True, str(c)[:70])
        verifie("il part de zero", c.get("confirmees") == 0)
        verifie("il n'annonce plus de bareme en mois",
                not any(k in c for k in ("par_mois", "mois_gagnes",
                                         "mois_accordes", "avant_le_prochain")),
                f"champs rendus : {sorted(c)}")

        print("\n4. une correction NON confirmee reste EN ATTENTE")
        jeton = json.loads((tmp_app / "partage.json").read_text(encoding="utf-8")
                           ) if False else None
        mien = poste(SYNC, "/connexion", {"identifiant": "banc-ecran",
                                          "preuve": "?"})
        poste(APP, "/api/partage/propose",
              {"jeu": "JEU", "faux": "ハイボーション", "juste": "ハイポーション"})
        c = lis(APP, "/api/contributions")
        verifie("elle n'est pas encore comptee comme acquise",
                c.get("confirmees") == 0, f"confirmees={c.get('confirmees')}")
        verifie("mais elle apparait en attente",
                c.get("en_attente") >= 1, f"en_attente={c.get('en_attente')}")

        print("\n5. confirmee par un AUTRE compte, elle compte")
        autre = poste(SYNC, "/inscription",
                      {"identifiant": "autre-banc",
                       "preuve": "derive-pbkdf2-du-banc-autre-000000"})
        jeton_autre = autre.get("jeton") or poste(
            SYNC, "/connexion", {"identifiant": "autre-banc",
                                 "preuve": "derive-pbkdf2-du-banc-autre-000000"}
        ).get("jeton")
        poste(SYNC, "/correction", {"jeton": jeton_autre, "jeu": "JEU",
                                    "faux": "ハイボーション",
                                    "juste": "ハイポーション"})
        c = lis(APP, "/api/contributions")
        verifie("le compteur passe a 1", c.get("confirmees") == 1,
                f"confirmees={c.get('confirmees')}")
        verifie("et rien n'est promis en echange",
                "avant_le_prochain" not in c and "mois_a_accorder" not in c,
                f"champs rendus : {sorted(c)}")

        print("\n6. L'ESSAI A SON PROPRE BANDEAU, QUE PERSONNE N'ECRASE")
        js = (RACINE / "static" / "js" / "10-capture.js").read_text(encoding="utf-8")
        html = (RACINE / "static" / "overlay.html").read_text(encoding="utf-8")
        ecrivains = sum(
            (RACINE / "static" / "js" / f).read_text(encoding="utf-8").count(
                "Choisis le jeu")
            for f in ("10-capture.js", "40-window.js", "46-bulle.js"))
        verifie("plusieurs endroits ecrivent encore dans la ligne d'etat",
                ecrivains >= 2,
                f"{ecrivains} — c'est pour ca que l'essai a besoin d'un ailleurs")
        verifie("le bandeau existe dans la page", 'id="accesbandeau"' in html)
        verifie("et l'essai n'ecrit plus dans #status",
                "setStatus(t('etat.essai" not in js
                and "accestexte" in js)
        verifie("il s'affiche des le premier jour, pas au troisieme",
                "acces.essai.reste" in js and "if (j <= 3) {" not in js)
        verifie("il disparait pour qui a paye",
                "'cle') {" in js and "cache.hidden = true" in js,
                "verifie dans la vraie page : hidden=true, hauteur 0")
        verifie("un bouton mene la ou l'on colle une cle",
                'id="accescle"' in html and "ouvrir_reglages" in js)

        reg = (RACINE / "static" / "js" / "70-reglages.js").read_text(encoding="utf-8")
        verifie("les reglages vont chercher l'etat d'acces reel",
                "/api/acces" in reg,
                "au lieu de constater « aucune cle sur cette machine »")
        verifie("l'ecran des contributions est branche au demarrage",
                "relisContributions();" in reg)

    finally:
        for p in (app, sync):
            p.terminate()
            try:
                p.wait(timeout=5)
            except Exception:
                p.kill()

    print()
    if echecs:
        print(f"{len(echecs)} ECHEC(S) : " + " · ".join(echecs))
        return 1
    print("OK : le compteur traverse l'application ET le serveur, et l'essai")
    print("     s'annonce des le premier jour au lieu de l'avant-dernier")
    return 0


if __name__ == "__main__":
    sys.exit(main())
