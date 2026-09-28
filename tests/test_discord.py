# -*- coding: utf-8 -*-
import email.message
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
PORT = 8883
BASE = f"http://127.0.0.1:{PORT}"
ADMIN = "jeton-admin-de-test"
SECRET = "secret-serveur-de-test"
MOI = "123456789012345678"
sys.stdout.reconfigure(encoding="utf-8")


def poste(route, corps):
    req = urllib.request.Request(BASE + route, json.dumps(corps).encode(),
                                 {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read().decode())


def main():
    tmp = Path(tempfile.mkdtemp(prefix="dnar-discord-"))
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

        print("1. sans jeton d'administration, aucune clé n'est délivrée")
        try:
            poste("/licence/discord", {"admin": "n'importe quoi", "note": MOI})
            echecs.append("une clé a été délivrée sans le bon jeton")
            print("   REPONSE INATTENDUE")
        except urllib.error.HTTPError as e:
            print(f"   refusé : HTTP {e.code}")
            if e.code != 403:
                echecs.append(f"code inattendu : {e.code}")

        print("\n2. une personne, une clé — même après dix appels")
        cles = set()
        for _ in range(10):
            r = poste("/licence/discord", {"admin": ADMIN, "note": MOI})
            cles.add(r.get("cle"))
        if len(cles) != 1:
            echecs.append(f"{len(cles)} clés différentes pour un seul compte")
        cle = cles.pop()
        print(f"   dix appels -> une seule clé : {cle}")

        print("\n3. GARANTIR, ET NON AJOUTER : le bot repasse sans empiler")
        r1 = poste("/licence/discord", {"admin": ADMIN, "note": MOI, "jours": 31})
        j1 = r1["jours_restants"]
        for _ in range(9):
            rN = poste("/licence/discord", {"admin": ADMIN, "note": MOI,
                                            "jours": 31})
        jN = rN["jours_restants"]
        if abs(jN - j1) > 0.1:
            echecs.append(f"dix passages ont donné {jN:.0f} jours au lieu de "
                          f"{j1:.0f} : le bot empile")
        if rN.get("change"):
            echecs.append("le dixième passage a réécrit l'échéance pour rien")
        print(f"   1er passage : {j1:.0f} jours · après 10 passages : "
              f"{jN:.0f} jours (et non {j1 * 10:.0f})")

        print("\n4. on ne raccourcit jamais un abonnement déjà payé")
        poste("/licence/prolonger", {"admin": ADMIN, "cle": cle, "jours": 365})
        avant = poste("/licence/liste", {"admin": ADMIN})
        exp_avant = next(x["expire"] for x in avant["licences"] if x["cle"] == cle)
        r = poste("/licence/discord", {"admin": ADMIN, "note": MOI, "jours": 31})
        if r.get("change") or abs(r["expire"] - exp_avant) > 1:
            echecs.append("un abonnement d'un an a été ramené à un mois")
        print(f"   un an payé, puis passage du bot : échéance inchangée "
              f"({r['jours_restants']:.0f} jours)")

        print("\n5. couper est réversible")
        poste("/licence/discord/retirer", {"admin": ADMIN, "note": MOI})
        r = poste("/licence/discord", {"admin": ADMIN, "note": MOI})
        if r.get("ok"):
            echecs.append("une clé suspendue est rendue comme active")
        print(f"   suspendue -> {r.get('raison')}")
        poste("/licence/prolonger", {"admin": ADMIN, "cle": cle, "jours": 31})
        r = poste("/licence/discord", {"admin": ADMIN, "note": MOI})
        if not r.get("ok") or r.get("cle") != cle:
            echecs.append(f"se réabonner devrait rendre la MÊME clé : {r}")
        print(f"   réabonné -> même clé {r.get('cle')}, active")

        print("\n6. un identifiant Discord invalide est refusé")
        r = poste("/licence/discord", {"admin": ADMIN, "note": "pas-un-id"})
        if r.get("ok"):
            echecs.append("un identifiant non numérique a été accepté")
        print(f"   refusé : {r.get('raison')}")
        print("\n7. LE PANNEAU DE VENTE : la note doit revenir a la bonne personne")
        sys.path.insert(0, str(RACINE / "app"))
        import bot_discord
        import livraison

        class FauxMembre:
            def __init__(self, nom):
                self.name = nom

        for nom in ("nana", "nana_challenger", "n.a.n.a", "xX_dark_99_Xx",
                    "a" * 32, "u2"):
            ligne = bot_discord.note_de(FauxMembre(nom))
            faux = email.message.EmailMessage()
            faux["Subject"] = "Vous avez recu de l argent"
            faux.set_content(f"Note de l acheteur : {ligne}" + chr(10) + "5,00 EUR")
            relu = livraison.lis_le_paiement(faux)["pseudo"]
            if relu != nom:
                echecs.append(f"« {nom} » : le bot donne « {ligne} », "
                              f"la livraison relit « {relu} »")
            print(f"   {ligne:42} -> relu « {relu} »"
                  f"{'' if relu == nom else '   <-- ECART'}")

        print("\n8. le panneau ne recopie AUCUNE valeur en dur")
        src = (RACINE / "app" / "bot_discord.py").read_text(encoding="utf-8")
        for interdit, pourquoi in (
                ("5.00", "le prix"), ("5,00", "le prix"),
                ("paypal.me/", "l'adresse de paiement")):
            if interdit in src:
                echecs.append(f"{pourquoi} est ecrit en dur dans le bot "
                              f"(« {interdit} ») : un salon epingle vendrait au "
                              f"vieux prix pour toujours")
        print("   prix et lien de paiement : lus sur /boutique/etat a chaque clic")

        for attendu, pourquoi in (
                ('custom_id="dnar:payer"', "le bouton payer a un identifiant fixe"),
                ("timeout=None", "la vue ne s'eteint pas toute seule"),
                ("self.add_view(PanneauBoutique())",
                 "elle est re-enregistree au demarrage")):
            if attendu not in src:
                echecs.append(f"panneau non persistant : {pourquoi} manque")
        print("   boutons persistants : custom_id + timeout=None + add_view")

        if "manage_guild" not in src:
            echecs.append("n'importe qui peut poser le panneau")
        print("   « !shop » reserve a l'administration (manage_guild)")

        if "intents.message_content = True" not in src:
            echecs.append("intents.message_content manque : « !shop » ne se "
                          "declenchera jamais")
        print("   intention « contenu des messages » demandee")

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
    print("\nOK : une personne une clé, le bot n'empile pas, ne raccourcit "
          "pas,\n     et couper reste réversible")
    return 0


raise SystemExit(main())
