# -*- coding: utf-8 -*-
import base64
import io
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
PORT = 8887
BASE = f"http://127.0.0.1:{PORT}"
ADMIN = "jeton-admin-de-test"
SECRET = "secret-serveur-de-test"
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(RACINE / "app"))


def poste(route, corps, timeout=20):
    req = urllib.request.Request(BASE + route, json.dumps(corps).encode(),
                                 {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def compte(nom):
    preuve = ("derive-pbkdf2-de-test-" + nom).ljust(32, "0")
    r = poste("/inscription", {"identifiant": nom, "preuve": preuve})
    if not r.get("ok"):
        r = poste("/connexion", {"identifiant": nom, "preuve": preuve})
    return r.get("jeton", "")


def png(larg, haut, graine=0) -> str:
    from PIL import Image
    im = Image.new("RGB", (larg, haut), (255, 255, 255))
    px = im.load()
    for x in range(min(larg, 64)):
        px[x, 0] = ((x * 7 + graine) % 256, (graine * 13) % 256, 0)
    b = io.BytesIO()
    im.save(b, format="PNG")
    return base64.b64encode(b.getvalue()).decode("ascii")


def main():
    tmp = Path(tempfile.mkdtemp(prefix="dnar-recolte-"))
    env = dict(os.environ, DNAREADER_ADMIN=ADMIN, DNAREADER_SECRET=SECRET,
               DNAREADER_DONNEES=str(tmp), PYTHONIOENCODING="utf-8")
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

        jeton = compte("recolteur")
        if not jeton:
            print("ECHEC : pas de compte")
            return 1

        print("1. UNE CAPTURE D'ÉCRAN EST REFUSÉE (le point qui coûte cher)")
        r = poste("/recolte", {"jeton": jeton, "jeu": "FF7R",
                               "lignes": [{"texte": "魔法攻撃力",
                                           "image": png(1920, 1080, 1)}]})
        if r.get("gardees"):
            echecs.append("un écran 1920x1080 a été accepté et stocké")
        print(f"   1920x1080 -> gardées={r.get('gardees')} "
              f"raisons={r.get('raisons')}")
        sur_disque = list((tmp / "recolte_recue").rglob("*.png"))
        if sur_disque:
            echecs.append(f"{len(sur_disque)} fichier(s) écrit(s) malgré le refus")

        print("\n2. une vraie ligne passe")
        r = poste("/recolte", {"jeton": jeton, "jeu": "FF7R",
                               "lignes": [{"texte": "魔法攻撃力",
                                           "image": png(232, 48, 2)}]})
        if r.get("gardees") != 1:
            echecs.append(f"une ligne 232x48 n'a pas été gardée : {r}")
        print(f"   232x48 -> gardées={r.get('gardees')}")

        print("\n3. la MÊME image ne compte qu'une fois")
        meme = png(232, 48, 3)
        r1 = poste("/recolte", {"jeton": jeton, "jeu": "FF7R",
                                "lignes": [{"texte": "疾風のスカーフ", "image": meme}]})
        r2 = poste("/recolte", {"jeton": jeton, "jeu": "FF7R",
                                "lignes": [{"texte": "疾風のスカーフ", "image": meme}]})
        if r1.get("gardees") != 1 or r2.get("gardees") != 0 \
                or r2.get("deja_connues") != 1:
            echecs.append(f"le doublon n'est pas écarté : {r1} puis {r2}")
        print(f"   1er envoi : {r1.get('gardees')} gardée · "
              f"2e envoi : {r2.get('gardees')} gardée, "
              f"{r2.get('deja_connues')} déjà connue")

        print("\n4. sans compte valide, rien n'entre")
        r = poste("/recolte", {"jeton": "pas-un-jeton", "jeu": "FF7R",
                               "lignes": [{"texte": "魔法攻撃力",
                                           "image": png(232, 48, 4)}]})
        if r.get("ok"):
            echecs.append("un jeton invalide a été accepté")
        print(f"   refusé : {r.get('error')}")

        print("\n5. ce qui n'est pas un PNG est refusé")
        r = poste("/recolte", {"jeton": jeton, "jeu": "FF7R",
                               "lignes": [{"texte": "魔法攻撃力",
                                           "image": base64.b64encode(
                                               b"GIF89a pas un png").decode()}]})
        if r.get("gardees"):
            echecs.append("un fichier qui n'est pas un PNG a été gardé")
        print(f"   raisons={r.get('raisons')}")

        print("\n6. un texte sans japonais est refusé")
        r = poste("/recolte", {"jeton": jeton, "jeu": "FF7R",
                               "lignes": [{"texte": "HP 9999",
                                           "image": png(232, 48, 6)}]})
        if r.get("gardees"):
            echecs.append("un texte sans japonais a été gardé")
        print(f"   raisons={r.get('raisons')}")

        print("\n7. l'état par jeu se lit, et seulement avec le jeton d'admin")
        try:
            poste("/recolte/etat", {"admin": "n'importe quoi"})
            echecs.append("l'état a été rendu sans le bon jeton")
        except urllib.error.HTTPError as e:
            if e.code != 403:
                echecs.append(f"code inattendu : {e.code}")
            print(f"   sans admin : HTTP {e.code}")
        e = poste("/recolte/etat", {"admin": ADMIN})
        print(f"   réserve : {e.get('lignes')} ligne(s), "
              f"{e.get('octets', 0) / 1024:.1f} Ko, jeux={e.get('jeux')}")
        if e.get("lignes") != 2:
            echecs.append(f"la réserve devrait contenir 2 lignes, pas {e.get('lignes')}")

        print("\n8. CÔTÉ CLIENT : on n'envoie pas deux fois, et un échec ne perd rien")
        client = Path(tempfile.mkdtemp(prefix="dnar-client-"))
        sortie = subprocess.run(
            [str(PY_EXE), "-c", _SCENARIO_CLIENT, BASE, jeton],
            env=dict(os.environ, DNAREADER_DONNEES=str(client),
                     PYTHONIOENCODING="utf-8"),
            cwd=str(RACINE / "app"), capture_output=True, text=True,
            encoding="utf-8", timeout=180)
        print(sortie.stdout.rstrip() or sortie.stderr[-1500:])
        if sortie.returncode != 0:
            echecs.append("le scénario client a échoué")
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
    print("\nOK : l'écran entier est refusé, le doublon ne compte qu'une fois,")
    print("     l'anonyme n'entre pas, et un envoi raté ne perd aucune ligne")
    return 0


_SCENARIO_CLIENT = r'''
import io, json, sys, os
sys.path.insert(0, ".")
from PIL import Image
base, jeton = sys.argv[1], sys.argv[2]

import chemins, partage, recolte, recolte_envoi

# On se branche sur le vrai serveur, avec un vrai compte.
partage.regle(actif=True, serveur=base)
import comptes
comptes.etat = lambda: {"jeton": jeton}

recolte.DOSSIER.mkdir(parents=True, exist_ok=True)
def pose(nom, jeu, texte, graine):
    im = Image.new("RGB", (200, 40), (255, 255, 255))
    px = im.load()
    for x in range(64):
        px[x, 0] = ((x * 5 + graine) % 256, graine % 256, 7)
    im.save(recolte.DOSSIER / nom)
    with recolte.INDEX.open("a", encoding="utf-8") as f:
        e = {"image": nom, "texte": texte}
        if jeu:
            e["jeu"] = jeu
        f.write(json.dumps(e, ensure_ascii=False) + "\n")

for i in range(5):
    pose(f"l{i}.png", "FF7R", "魔法攻撃力" + "ー" * i, 100 + i)
pose("sansjeu.png", "", "疾風のスカーフ", 200)     # sans jeu : ne doit pas partir

attente = recolte_envoi.en_attente()
print(f"   {len(attente)} ligne(s) en attente (la 6e n'a pas de jeu)")
if len(attente) != 5:
    print("   ECHEC : une ligne sans jeu est partie en attente"); sys.exit(1)

r = recolte_envoi.envoie_un_lot()
print(f"   envoi -> gardées={r.get('gardees')} ok={r.get('ok')}")
if not r.get("ok") or r.get("gardees") != 5:
    print("   ECHEC : le lot n'est pas passé"); sys.exit(1)

reste = recolte_envoi.en_attente()
print(f"   après envoi : {len(reste)} ligne(s) en attente")
if reste:
    print("   ECHEC : on renverrait des lignes déjà envoyées"); sys.exit(1)

# UN ÉCHEC NE DOIT RIEN MARQUER. On casse l'adresse du serveur et on vérifie
# que la ligne reste à envoyer — c'est ce qui protège d'une coupure réseau.
pose("l9.png", "FF7R", "イノセンスフォース", 300)
partage.regle(serveur="http://127.0.0.1:9")        # personne n'écoute là
avant = len(recolte_envoi.en_attente())
r = recolte_envoi.envoie_un_lot()
apres = len(recolte_envoi.en_attente())
print(f"   serveur injoignable -> ok={r.get('ok')} ; "
      f"en attente {avant} avant, {apres} après")
if apres != avant:
    print("   ECHEC : une ligne a été marquée envoyée sans que le serveur l'ait reçue")
    sys.exit(1)

# Et elle repart bien une fois le serveur revenu.
partage.regle(serveur=base)
r = recolte_envoi.envoie_un_lot()
print(f"   serveur revenu -> gardées={r.get('gardees')}")
if r.get("gardees") != 1:
    print("   ECHEC : la ligne retenue n'est pas repartie"); sys.exit(1)
print("   OK client")
'''


raise SystemExit(main())
