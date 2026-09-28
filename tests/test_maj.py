# -*- coding: utf-8 -*-
import hashlib
import http.server
import io
import json
import os
import shutil
import sys
import tempfile
import threading
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
PORT = 8886
BASE = f"http://127.0.0.1:{PORT}"
sys.stdout.reconfigure(encoding="utf-8")

TMP = Path(tempfile.mkdtemp(prefix="dnar-maj-"))
os.environ["DNAREADER_DONNEES"] = str(TMP)
sys.path.insert(0, str(RACINE / "app"))

import chemins
import maj
import version

echecs = []
SERVI = {"release": {}, "fichier": b"", "somme": b"", "coupe": False,
         "lent": False, "requetes": 0, "entetes": []}


def verifie(nom, condition, detail=""):
    print(f"  {'OK  ' if condition else 'ECHEC'} {nom}"
          + (f" — {detail}" if detail else ""))
    if not condition:
        echecs.append(nom)


class Faux(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.path.endswith("/releases/latest"):
            SERVI["requetes"] += 1
            SERVI["entetes"].append(dict(self.headers))
            corps = json.dumps(SERVI["release"]).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(corps)))
            self.end_headers()
            self.wfile.write(corps)
            return
        if self.path.endswith(".sha256"):
            corps = SERVI["somme"]
        elif self.path.endswith(".exe"):
            corps = SERVI["fichier"]
            if SERVI["coupe"]:
                self.send_response(200)
                self.send_header("Content-Length", str(len(corps)))
                self.end_headers()
                try:
                    self.wfile.write(corps[:len(corps) // 2])
                except Exception:
                    pass
                return
        else:
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Length", str(len(corps)))
        self.end_headers()
        if SERVI["lent"] and self.path.endswith(".exe"):
            pas = max(1, len(corps) // 20)
            for i in range(0, len(corps), pas):
                try:
                    self.wfile.write(corps[i:i + pas])
                    self.wfile.flush()
                except Exception:
                    return
                time.sleep(0.05)
            return
        self.wfile.write(corps)


def release(tag, contenu=b"MZ faux installateur", somme=None, sans_somme=False,
            sans_setup=False):
    SERVI["fichier"] = contenu
    vraie = hashlib.sha256(contenu).hexdigest()
    SERVI["somme"] = (f"{somme or vraie}  DNAreader-Setup.exe\n").encode()
    SERVI["coupe"] = False
    SERVI["lent"] = False
    assets = []
    if not sans_setup:
        assets.append({"name": f"DNAreader-Setup-{tag.lstrip('v')}.exe",
                       "browser_download_url": f"{BASE}/dl/DNAreader-Setup.exe",
                       "size": len(contenu)})
    if not sans_somme:
        assets.append({"name": f"DNAreader-Setup-{tag.lstrip('v')}.exe.sha256",
                       "browser_download_url": f"{BASE}/dl/DNAreader-Setup.exe.sha256",
                       "size": 100})
    SERVI["release"] = {"tag_name": tag, "name": f"DNAreader {tag}",
                        "body": "ce qui change", "html_url": f"{BASE}/r/{tag}",
                        "assets": assets}
    return SERVI["release"]


def remet_a_zero():
    maj._trouve = {}
    maj._phase = "rien"
    maj._recus = 0
    maj._erreur = ""
    try:
        maj.FICHIER_ETAT.unlink()
    except Exception:
        pass
    shutil.rmtree(maj.DOSSIER, ignore_errors=True)
    SERVI["requetes"] = 0


def attends_la_fin(secondes=15):
    t0 = time.time()
    while time.time() - t0 < secondes:
        if maj._phase in ("prete", "echec", "trouvee"):
            return maj._phase
        time.sleep(0.05)
    return maj._phase


def main():
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), Faux)
    threading.Thread(target=srv.serve_forever, daemon=True).start()

    maj.API_BASE = BASE
    chemins.EMPAQUETEE = True
    version.DEPOT_RELEASES = "NanashiAngsnake/dnareader-releases"
    version.VERSION = "1.0.0"

    try:
        print("1. depuis les SOURCES, on ne cherche rien")
        chemins.EMPAQUETEE = False
        remet_a_zero()
        e = maj.cherche(force=True)
        verifie("possible=False sans empaquetage", e["possible"] is False)
        verifie("et aucune requete n'est partie", SERVI["requetes"] == 0,
                f"{SERVI['requetes']} requete(s)")
        chemins.EMPAQUETEE = True

        print("\n2. depot vide : une build sans mise a jour reste valide")
        remet_a_zero()
        version.DEPOT_RELEASES = ""
        e = maj.cherche(force=True)
        verifie("possible=False sans depot", e["possible"] is False)
        verifie("et aucune requete", SERVI["requetes"] == 0)
        version.DEPOT_RELEASES = "NanashiAngsnake/dnareader-releases"

        print("\n3. comparer des VERSIONS, pas des chaines")
        for a, b, attendu, pourquoi in (
                ("1.10.0", "1.9.0", True, "le piege de la comparaison de texte"),
                ("v1.1.0", "1.0.0", True, "le v du tag est ignore"),
                ("1.0.0", "1.0.0", False, "la meme version ne se propose pas"),
                ("0.9.0", "1.0.0", False, "une release retiree ne fait pas regresser"),
                ("1.2", "1.1.9", True, "un numero court reste comparable"),
                ("1.2.3-beta", "1.2.2", True, "le suffixe est ignore"),
                ("coucou", "1.0.0", False, "un tag illisible ne declenche rien")):
            verifie(f"{a} > {b} = {attendu}", maj.plus_recente(a, b) is attendu,
                    pourquoi)

        print("\n4. une version plus recente est proposee")
        remet_a_zero()
        release("v1.1.0")
        e = maj.cherche(force=True)
        verifie("elle est annoncee", e["version_distante"] == "1.1.0", str(e["version_distante"]))
        verifie("avec ses notes et son poids",
                e["notes"] == "ce qui change" and e["octets"] > 0)
        verifie("GitHub a bien recu un User-Agent",
                any("User-Agent" in h and version.NOM in h.get("User-Agent", "")
                    for h in SERVI["entetes"]),
                "sans lui GitHub rend un 403 qu'on prendrait pour une panne")

        print("\n5. la MEME version ne propose rien")
        remet_a_zero()
        release("v1.0.0")
        e = maj.cherche(force=True)
        verifie("rien a proposer", e["version_distante"] == "")

        print("\n6. une release sans empreinte n'est PAS proposee")
        remet_a_zero()
        release("v1.1.0", sans_somme=True)
        e = maj.cherche(force=True)
        verifie("on ne promet pas une mise a jour qu'on refuserait ensuite",
                e["version_distante"] == "", e["erreur"][:50])

        print("\n6bis. LE CONTROLE A LIEU A CHAQUE LANCEMENT")
        verifie("le delai se compte en heures, pas en jours",
                maj.ENTRE_DEUX_CONTROLES <= 3600,
                f"{maj.ENTRE_DEUX_CONTROLES} s")
        verifie("et il reste assez large pour ne pas marteler GitHub",
                maj.ENTRE_DEUX_CONTROLES >= 600,
                "60 requetes par heure et par adresse, sans jeton")

        print("\n7. UNE SEULE REQUETE PAR PERIODE")
        remet_a_zero()
        release("v1.1.0")
        maj.cherche(force=True)
        n = SERVI["requetes"]
        maj.cherche(force=False)
        maj.cherche(force=False)
        verifie("les appels suivants ne repartent pas sur le reseau",
                SERVI["requetes"] == n, f"{SERVI['requetes']} au lieu de {n}")
        maj.cherche(force=True)
        verifie("mais « chercher maintenant » passe outre",
                SERVI["requetes"] == n + 1)

        print("\n8. auto decoche : plus aucune requete")
        remet_a_zero()
        release("v1.1.0")
        maj.auto(False)
        n = SERVI["requetes"]
        maj.cherche(force=False)
        verifie("un reglage qui ne regle rien serait un mensonge",
                SERVI["requetes"] == n)
        maj.cherche(force=True)
        verifie("le bouton continue de marcher", SERVI["requetes"] == n + 1)
        maj.auto(True)

        print("\n9. TELECHARGEMENT correct : verifie, puis renomme")
        remet_a_zero()
        contenu = b"MZ" + os.urandom(200000)
        release("v1.1.0", contenu=contenu)
        maj.cherche(force=True)
        maj.telecharge()
        phase = attends_la_fin()
        verifie("la phase passe a « prete »", phase == "prete", maj._erreur[:60])
        fichiers = sorted(p.name for p in maj.DOSSIER.glob("*"))
        verifie("le fichier porte enfin le nom d'un exe",
                any(f.endswith(".exe") for f in fichiers), str(fichiers))
        verifie("et plus aucun .partiel ne traine",
                not any(f.endswith(".partiel") for f in fichiers), str(fichiers))
        verifie("son contenu est exactement celui publie",
                (maj.DOSSIER / maj._trouve["setup_nom"]).read_bytes() == contenu)

        print("\n10. EMPREINTE FAUSSE : refus, et rien d'executable ne reste")
        remet_a_zero()
        release("v1.1.0", contenu=b"MZ" + os.urandom(100000),
                somme="0" * 64)
        maj.cherche(force=True)
        maj.telecharge()
        phase = attends_la_fin()
        verifie("la phase passe a « echec »", phase == "echec")
        verifie("l'ecart est dit franchement", "empreinte" in maj._erreur.lower(),
                maj._erreur[:60])
        restants = sorted(p.name for p in maj.DOSSIER.glob("*"))
        verifie("AUCUN fichier ne reste, ni .exe ni .partiel", restants == [],
                str(restants))
        verifie("et installer est refuse", maj.installe()["ok"] is False)

        print("\n11. TELECHARGEMENT TRONQUE : refus")
        remet_a_zero()
        release("v1.1.0", contenu=b"MZ" + os.urandom(400000))
        SERVI["coupe"] = True
        maj.cherche(force=True)
        SERVI["coupe"] = True
        maj.telecharge()
        phase = attends_la_fin()
        verifie("un fichier tronque n'est jamais accepte", phase == "echec",
                f"phase={phase} erreur={maj._erreur[:40]}")
        restants = sorted(p.name for p in maj.DOSSIER.glob("*"))
        verifie("il ne reste rien a executer", restants == [], str(restants))
        SERVI["coupe"] = False

        print("\n12. IGNORER une version, et seulement celle-la")
        remet_a_zero()
        release("v1.1.0")
        maj.cherche(force=True)
        maj.ignore("1.1.0")
        e = maj.etat()
        verifie("elle est marquee ignoree", e["ignoree"] is True)
        maj._trouve, maj._phase = {}, "rien"
        release("v1.1.0")
        e = maj.cherche(force=True)
        verifie("elle le reste au relancement", e["ignoree"] is True)
        release("v1.2.0")
        e = maj.cherche(force=True)
        verifie("mais 1.2.0 est quand meme proposee",
                e["version_distante"] == "1.2.0" and e["ignoree"] is False,
                "ignorer une version ne doit pas rendre sourd aux suivantes")

        print("\n13. GITHUB INJOIGNABLE : silence, pas une erreur affichee")
        remet_a_zero()
        ancien, maj.API_BASE = maj.API_BASE, "http://127.0.0.1:1"
        e = maj.cherche(force=False)
        verifie("on ne derange pas pour une coupure reseau",
                e["erreur"] == "" and e["version_distante"] == "")
        maj.API_BASE = ancien

        print("\n14. le vieux dossier maj/ est PURGE")
        remet_a_zero()
        maj.DOSSIER.mkdir(parents=True, exist_ok=True)
        (maj.DOSSIER / "DNAreader-Setup-0.9.0.exe").write_bytes(b"vieux" * 1000)
        release("v1.1.0")
        maj.cherche(force=True)
        restants = sorted(p.name for p in maj.DOSSIER.glob("*"))
        verifie("122 Mo par version ne s'accumulent pas a vie",
                "DNAreader-Setup-0.9.0.exe" not in restants, str(restants))

        print("\n15. LE LANCEMENT : les bons arguments, et rien sans verification")
        remet_a_zero()
        verifie("installer sans rien de pret est refuse",
                maj.installe()["ok"] is False)

        contenu = b"MZ" + os.urandom(50000)
        release("v1.1.0", contenu=contenu)
        maj.cherche(force=True)
        maj.telecharge()
        attends_la_fin()
        temoin = TMP / "temoin.txt"
        faux = maj.DOSSIER / maj._trouve["setup_nom"]
        vus = []
        vrai_popen = maj.subprocess.Popen

        def espion(args, **kw):
            vus.append(list(args))
            temoin.write_text(" ".join(args[1:]), encoding="utf-8")
            class Faux:
                pid = 1
            return Faux()
        maj.subprocess.Popen = espion
        try:
            r = maj.installe()
        finally:
            maj.subprocess.Popen = vrai_popen
        verifie("l'installateur est lance", r["ok"] is True, str(r)[:60])
        verifie("avec /SILENT", vus and "/SILENT" in vus[0],
                str(vus[0][1:]) if vus else "aucun appel")
        verifie("et /RELANCE=1 — sans lui l'app ne reviendrait jamais",
                vus and "/RELANCE=1" in vus[0])
        verifie("c'est bien le fichier verifie qui est lance",
                vus and vus[0][0] == str(faux))

        print("\n16. le fichier disparait entre la verification et le lancement")
        faux.unlink()
        r = maj.installe()
        verifie("on refuse plutot que de lancer dans le vide", r["ok"] is False,
                r.get("raison", "")[:50])

        print("\n17. CHERCHER pendant un telechargement ne l'efface pas")
        remet_a_zero()
        release("v1.1.0", contenu=b"MZ" + os.urandom(300000))
        maj.cherche(force=True)
        SERVI["lent"] = True
        maj.telecharge()
        time.sleep(0.2)
        e = maj.cherche(force=True)
        verifie("chercher ne fait pas reculer l'etat",
                e["phase"] in ("telechargement", "prete"), e["phase"])
        phase = attends_la_fin()
        verifie("et le telechargement va au bout", phase == "prete",
                maj._erreur[:60])

        print("\n18. CHERCHER apres coup ne redemande pas 122 Mo")
        avant = sorted(p.name for p in maj.DOSSIER.glob("*"))
        e = maj.cherche(force=True)
        verifie("un fichier deja verifie reste « pret »", e["phase"] == "prete",
                e["phase"])
        verifie("et il est toujours la", sorted(p.name for p in maj.DOSSIER.glob("*")) == avant,
                str(avant))
        r = maj.telecharge()
        verifie("relancer le telechargement ne refait rien",
                r.get("deja") is True, str(r))

        print("\n19. ANNULER puis RELANCER : un seul fil ecrit")
        remet_a_zero()
        release("v1.1.0", contenu=b"MZ" + os.urandom(400000))
        maj.cherche(force=True)
        SERVI["lent"] = True
        maj.telecharge()
        time.sleep(0.2)
        gen1 = maj._generation
        maj.annule()
        maj.telecharge()
        verifie("la relance porte un NOUVEAU numero de generation",
                maj._generation > gen1,
                f"{gen1} -> {maj._generation}")
        phase = attends_la_fin(20)
        verifie("le second telechargement aboutit", phase == "prete",
                f"phase={phase} erreur={maj._erreur[:50]}")
        restants = sorted(p.name for p in maj.DOSSIER.glob("*"))
        verifie("et aucun .partiel de l'ancien fil ne traine",
                not any(f.endswith(".partiel") for f in restants), str(restants))

        print("\n20. UN NOM D'ASSET NE PEUT PAS DESIGNER UN AUTRE DOSSIER")
        for mechant in ("../../../Startup/DNAreader-Setup.exe",
                        "..\\..\\DNAreader-Setup.exe",
                        "C:/Windows/System32/DNAreader-Setup.exe",
                        "DNAreader-Setup:1.exe"):
            verifie(f"refuse {mechant[:34]}", maj.nom_sain(mechant)
                    in ("", "DNAreader-Setup.exe"),
                    f"-> {maj.nom_sain(mechant)!r}")
        verifie("mais un nom honnete passe intact",
                maj.nom_sain("DNAreader-Setup-1.1.0.exe") == "DNAreader-Setup-1.1.0.exe")

        print("\n21. UN FICHIER ANNONCE HORS DE GITHUB EST REFUSE")
        remet_a_zero()
        release("v1.1.0")
        SERVI["release"]["assets"][0]["browser_download_url"] = \
            "https://exemple-mechant.fr/DNAreader-Setup.exe"
        e = maj.cherche(force=True)
        verifie("rien n'est propose", e["version_distante"] == "")
        verifie("et on dit pourquoi", "hors de GitHub" in e["erreur"],
                e["erreur"][:50])
        for u, sur in (("https://github.com/a/b/releases/download/v1/x.exe", True),
                       ("https://objects.githubusercontent.com/x", True),
                       ("http://github.com/a/b/x.exe", False),
                       ("https://github.com.mechant.fr/x.exe", False),
                       ("https://raw.githubusercontent.com/x.exe", False)):
            verifie(f"{'accepte' if sur else 'refuse'} {u[:44]}",
                    maj._url_sure(u) is sur)

        print("\n22. UNE VERSION REFUSEE NE S'INSTALLE PAS, meme prete")
        remet_a_zero()
        release("v1.1.0", contenu=b"MZ" + os.urandom(60000))
        maj.cherche(force=True)
        maj.telecharge()
        attends_la_fin()
        verifie("le fichier est bien pret", maj._phase == "prete")
        maj.ignore("1.1.0")
        r = maj.installe()
        verifie("installer une version refusee est REFUSE", r["ok"] is False,
                r.get("raison", "")[:50])

        print("\n23. UN REDEMARRAGE DANS LES 24 H ne fait pas disparaitre la maj")
        remet_a_zero()
        release("v1.1.0")
        maj.cherche(force=True)
        verifie("elle est trouvee", maj.etat()["version_distante"] == "1.1.0")
        maj._trouve, maj._phase = {}, "rien"
        n = SERVI["requetes"]
        maj.au_demarrage()
        time.sleep(1.0)
        e = maj.etat()
        verifie("elle est retrouvee au redemarrage",
                e["version_distante"] == "1.1.0", str(e["version_distante"]))
        verifie("sans redemander a GitHub (le controle est quotidien)",
                SERVI["requetes"] == n, f"{SERVI['requetes']} vs {n}")

        print("\n24. APRES la mise a jour, les 122 Mo ne restent pas a vie")
        remet_a_zero()
        release("v1.1.0", contenu=b"MZ" + os.urandom(50000))
        maj.cherche(force=True)
        maj.telecharge()
        attends_la_fin()
        verifie("l'installateur est sur le disque",
                any(p.suffix == ".exe" for p in maj.DOSSIER.glob("*")))
        version.VERSION = "1.1.0"
        maj._trouve, maj._phase = {}, "rien"
        release("v1.1.0")
        maj.cherche(force=True)
        restants = sorted(p.name for p in maj.DOSSIER.glob("*"))
        verifie("il est jete une fois installe", restants == [], str(restants))
        version.VERSION = "1.0.0"

        print("\n25. UNE ERREUR NE RESTE PAS COLLEE A L'ECRAN")
        remet_a_zero()
        release("v1.1.0")
        SERVI["release"]["assets"][0]["browser_download_url"] = "https://mechant.fr/x.exe"
        e = maj.cherche(force=True)
        verifie("l'erreur s'affiche", e["erreur"] != "")
        release("v1.0.0")
        e = maj.cherche(force=True)
        verifie("et disparait au controle suivant qui a repondu",
                e["erreur"] == "", e["erreur"][:50])

        print("\n26. UN FLUX SANS FIN NE REMPLIT PAS LE DISQUE")
        remet_a_zero()
        vrai = b"MZ" + os.urandom(40000)
        release("v1.1.0", contenu=vrai)
        SERVI["fichier"] = vrai + os.urandom(4 << 20)
        maj.cherche(force=True)
        maj.telecharge()
        phase = attends_la_fin(30)
        verifie("on s'arrete au plafond", phase == "echec", phase)
        verifie("et on dit que la taille depasse",
                "taille" in maj._erreur or "depasse" in maj._erreur,
                maj._erreur[:60])
        restants = sorted(p.name for p in maj.DOSSIER.glob("*"))
        verifie("rien ne reste sur le disque", restants == [], str(restants))

        print("\n27. UN DEPOT SANS RELEASE N'EST PAS UNE PANNE")
        import urllib.error
        for code, attendu in ((404, "aucune version publiee"),
                              (403, "trop de demandes"),
                              (500, "GitHub a repondu 500")):
            e = urllib.error.HTTPError("http://x", code, "", None, None)
            verifie(f"{code} se dit en francais", attendu in maj._dit_pourquoi(e),
                    maj._dit_pourquoi(e))
        verifie("une panne reseau reste une panne reseau",
                "injoignable" in maj._dit_pourquoi(OSError("coupure")))

        print("\n28. ANNULER n'est pas une PANNE")
        remet_a_zero()
        release("v1.1.0", contenu=b"MZ" + os.urandom(800000))
        maj.cherche(force=True)
        SERVI["lent"] = True
        maj.telecharge()
        time.sleep(0.2)
        maj.annule()
        time.sleep(1.5)
        e = maj.etat()
        verifie("la phase revient a « trouvee », pas a « echec »",
                e["phase"] == "trouvee", e["phase"])
        verifie("et rien n'est presente comme une erreur", e["erreur"] == "",
                e["erreur"][:60])

    finally:
        srv.shutdown()
        shutil.rmtree(TMP, ignore_errors=True)

    print()
    if echecs:
        print(f"{len(echecs)} ECHEC(S) : " + " · ".join(echecs))
        return 1
    print("OK : la mise a jour se trouve, se verifie, se refuse quand il le faut,")
    print("     et rien de non verifie ne porte jamais le nom d'un executable")
    return 0


if __name__ == "__main__":
    sys.exit(main())
