# -*- coding: utf-8 -*-
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
PY_EXE = RACINE / ".venv" / "Scripts" / "python.exe"
PORT_SYNC = 8893
PORT_APP = 8894
SYNC = f"http://127.0.0.1:{PORT_SYNC}"
APP = f"http://127.0.0.1:{PORT_APP}"
ADMIN = "admin-de-test"
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


def attends(url, secondes=90):
    t0 = time.time()
    while time.time() - t0 < secondes:
        try:
            urllib.request.urlopen(url, timeout=2).read()
            return True
        except Exception:
            time.sleep(0.4)
    return False


def main():
    tmp_sync = Path(tempfile.mkdtemp(prefix="dnar-sig-sync-"))
    tmp_app = Path(tempfile.mkdtemp(prefix="dnar-sig-app-"))
    base_env = dict(os.environ, PYTHONIOENCODING="utf-8")

    sync = subprocess.Popen(
        [str(PY_EXE), str(RACINE / "app" / "serveur_sync.py"),
         "--port", str(PORT_SYNC), "--host", "127.0.0.1"],
        env=dict(base_env, DNAREADER_DONNEES=str(tmp_sync),
                 DNAREADER_ADMIN=ADMIN, DNAREADER_SECRET="secret-de-test",
                 DNAREADER_ANTI_INONDATION="0"),
        cwd=str(RACINE / "app"),
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

    app = subprocess.Popen(
        [str(PY_EXE), "-c",
         "import sys; sys.path.insert(0,'.');"
         "import version;"
         f"version.SERVEUR_LICENCE = '{SYNC}';"
         "import uvicorn, server;"
         f"uvicorn.run(server.app, host='127.0.0.1', port={PORT_APP},"
         " log_level='error')"],
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

        print("1. LE BOUTON EXISTE ET EST BRANCHÉ")
        html = (RACINE / "static" / "reglages.html").read_text(encoding="utf-8")
        js = (RACINE / "static" / "js" / "70-reglages.js").read_text(
            encoding="utf-8")
        for ident in ("bugtexte", "bugjournal", "bugvoir", "bugenvoi",
                      "bugetat", "bugapercu"):
            verifie(f"  l'écran a « {ident} »", f'id="{ident}"' in html)
        verifie("le bouton Envoyer écoute le clic",
                "$('bugenvoi').addEventListener" in js)
        verifie("le bouton Voir écoute le clic",
                "$('bugvoir').addEventListener" in js)
        verifie("décocher le journal rafraîchit l'aperçu",
                "$('bugjournal').addEventListener" in js)
        verifie("un envoi en cours désactive le bouton",
                "b.disabled = true" in js,
                "sinon un serveur lent fait recliquer, "
                "et le pépin arrive en trois exemplaires")

        print("\n2. UN MESSAGE CREUX EST REFUSÉ")
        r = poste(APP, "/api/signalement", {"message": "  ", "journal": False})
        verifie("le vide est refusé", r.get("ok") is False, str(r)[:80])
        r = poste(APP, "/api/signalement", {"message": "bug", "journal": False})
        verifie("trois lettres ne suffisent pas", r.get("ok") is False,
                str(r)[:80])
        verifie("  et on dit quoi faire",
                "deux mots" in str(r.get("raison", "")), str(r)[:80])

        print("\n3. CE QUI EST MONTRÉ EST CE QUI EST ENVOYÉ")
        rep = json.loads(urllib.request.urlopen(
            APP + "/api/signalement/apercu?journal=1", timeout=20).read())
        verifie("l'aperçu répond", rep.get("ok") is True, str(rep)[:80])
        ctx = rep.get("contexte") or {}
        verifie("il porte la version", bool(ctx.get("version")), str(ctx)[:80])
        verifie("il porte le système", bool(ctx.get("os")), str(ctx)[:80])
        verifie("il porte le mode d'accès", bool(ctx.get("acces")),
                str(ctx)[:80])
        verifie("il ne porte AUCUNE clé",
                not any("cle" in str(k) for k in ctx),
                "le mode explique un comportement, le numéro n'explique rien")

        texte = "le texte reste figé quand je change de scène"
        r = poste(APP, "/api/signalement", {"message": texte, "journal": True})
        verifie("le signalement part", r.get("ok") is True, str(r)[:90])
        numero = r.get("numero")

        lu = poste(SYNC, "/rapport/detail", {"admin": ADMIN, "jours": numero})
        verifie("je peux le relire côté serveur", lu.get("ok") is True,
                str(lu)[:90])
        verifie("  avec le message exact", lu.get("message") == texte,
                repr(lu.get("message"))[:90])
        verifie("  et le contexte que l'aperçu annonçait",
                lu.get("contexte", {}).get("version") == ctx.get("version")
                and lu.get("contexte", {}).get("os") == ctx.get("os"),
                "un aperçu approximatif est pire que pas d'aperçu")

        print("\n4. DÉCOCHER LE JOURNAL LE RETIRE VRAIMENT")
        rep0 = json.loads(urllib.request.urlopen(
            APP + "/api/signalement/apercu?journal=0", timeout=20).read())
        verifie("l'aperçu sans journal est vide de journal",
                rep0.get("journal") == "", repr(rep0.get("journal"))[:60])
        r = poste(APP, "/api/signalement",
                  {"message": "je préfère ne pas envoyer mon journal",
                   "journal": False})
        lu0 = poste(SYNC, "/rapport/detail",
                    {"admin": ADMIN, "jours": r.get("numero")})
        verifie("et rien n'arrive côté serveur",
                (lu0.get("journal") or "") == "",
                "le journal dit à quoi la personne jouait")

        print("\n5. LA CLÉ D'ACCÈS NE PART JAMAIS")
        cree = poste(SYNC, "/licence/creer",
                     {"admin": ADMIN, "machines": 2, "jours": 30,
                      "note": "banc signalement"})
        cle = cree.get("cle")
        verifie("une clé de test est créée", bool(cle), str(cree)[:80])
        act = poste(APP, "/api/licence/activer", {"serveur": SYNC, "cle": cle})
        verifie("elle est active sur l'application", act.get("ok") is True,
                str(act)[:90])
        r = poste(APP, "/api/signalement",
                  {"message": "signalement envoyé alors que ma clé est active",
                   "journal": True})
        lu2 = poste(SYNC, "/rapport/detail",
                    {"admin": ADMIN, "jours": r.get("numero")})
        entier = json.dumps(lu2, ensure_ascii=False)
        verifie("la clé n'apparaît nulle part dans ce qui a été stocké",
                cle not in entier,
                f"cherchée dans {len(entier)} caractères")
        morceau = cle.split("-")[1] if "-" in cle else cle
        verifie("  pas même un de ses morceaux", morceau not in entier)
        verifie("le mode, lui, est bien passé à « cle »",
                lu2.get("contexte", {}).get("acces") == "cle",
                str(lu2.get("contexte"))[:80])

        print("\n6. LE DÉBIT EST BORNÉ")
        refus = None
        for i in range(12):
            rr = poste(APP, "/api/signalement",
                       {"message": f"envoi en rafale numéro {i}",
                        "journal": False})
            if not rr.get("ok"):
                refus = rr
                break
        verifie("l'inondation est arrêtée", refus is not None,
                "sinon le bouton devient un moyen de remplir mon disque")
        verifie("  et on dit quand réessayer",
                "heure" in str((refus or {}).get("raison", "")),
                str(refus)[:90])

        print("\n7. UN JOURNAL ÉNORME EST TRONQUÉ, PAS REFUSÉ")
        sys.path.insert(0, str(RACINE / "app"))
        import rapports
        c = sqlite3.connect(":memory:")
        r = rapports.recois(c, {"machine": "autre-machine", "version": "1.0.2",
                                "message": "journal volumineux",
                                "journal": "x" * 500000})
        verifie("il passe quand même", r.get("ok") is True, str(r)[:70])
        garde = rapports.detail(c, r["numero"])["journal"]
        verifie(f"  ramené à {rapports.MAX_JOURNAL} caractères",
                len(garde) == rapports.MAX_JOURNAL, f"{len(garde)} gardés")
        verifie("  et c'est la FIN qui est gardée", garde.endswith("x"),
                "c'est là que se trouve ce qui vient de rater")

        print("\n8. SANS SERVEUR CONFIGURÉ, ON EXPLIQUE — ON NE PLANTE PAS")
        import signalement
        import version as v
        avant = v.SERVEUR_LICENCE
        v.SERVEUR_LICENCE = ""
        try:
            r = signalement.envoie("un message", False, "")
        finally:
            v.SERVEUR_LICENCE = avant
        verifie("le refus est propre", r.get("ok") is False, str(r)[:70])
        verifie("  et dit quoi faire",
                "écris-moi" in str(r.get("raison", "")), str(r)[:90])

        print("\n9. LIRE LES SIGNALEMENTS DEMANDE LE JETON")
        try:
            urllib.request.urlopen(urllib.request.Request(
                SYNC + "/rapport/liste",
                json.dumps({"admin": "pas-le-bon"}).encode(),
                {"Content-Type": "application/json"}), timeout=10)
            verifie("un mauvais jeton est refusé", False, "il est passé !")
        except urllib.error.HTTPError as e:
            verifie("un mauvais jeton est refusé", e.code in (401, 403),
                    f"HTTP {e.code}")
        bons = poste(SYNC, "/rapport/liste", {"admin": ADMIN, "etat": "tous"})
        verifie("le bon jeton voit tout",
                len(bons.get("rapports", [])) >= 4,
                f"{len(bons.get('rapports', []))} signalement(s)")

        print("\n10. L'OUTIL DU VENDEUR SAIT LES LIRE ET LES CLASSER")
        env = dict(base_env, DNAREADER_SERVEUR=SYNC, DNAREADER_ADMIN=ADMIN)
        sortie = subprocess.run(
            [str(PY_EXE), str(RACINE / "outils" / "pepins.py"), "liste"],
            env=env, capture_output=True, text=True, encoding="utf-8",
            timeout=60).stdout
        verifie("« pepins.py liste » montre les signalements",
                "signalement(s)" in sortie, (sortie or "")[:60])
        sortie = subprocess.run(
            [str(PY_EXE), str(RACINE / "outils" / "pepins.py"), "lire",
             str(numero)], env=env, capture_output=True, text=True,
            encoding="utf-8", timeout=60).stdout
        verifie("« pepins.py lire N » montre le message entier",
                "le texte reste figé" in sortie, (sortie or "")[:60])
        subprocess.run([str(PY_EXE), str(RACINE / "outils" / "pepins.py"),
                        "traite", str(numero)], env=env, capture_output=True,
                       timeout=60)
        reste = poste(SYNC, "/rapport/liste", {"admin": ADMIN})
        verifie("« traite » le sort de la liste",
                all(x["id"] != numero for x in reste.get("rapports", [])),
                "sinon la liste ne montre jamais ce qui reste à faire")

        print()
        if echecs:
            print(f"{len(echecs)} ECHEC(S) : " + ", ".join(echecs))
            return 1
        print("OK : le bouton « un problème ? » envoie ce qu'il montre,")
        print("     rien de plus, et j'ai de quoi corriger en face.")
        return 0
    finally:
        for p in (app, sync):
            p.terminate()
            try:
                p.wait(timeout=10)
            except Exception:
                p.kill()


if __name__ == "__main__":
    sys.exit(main())
