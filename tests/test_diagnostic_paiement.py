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
ADMIN = "jeton-admin-de-test"
SECRET = "secret-serveur-de-test"
sys.stdout.reconfigure(encoding="utf-8")
echecs = []


def verifie(nom, condition, detail=""):
    print(f"  {'OK  ' if condition else 'ECHEC'} {nom}" + (f" — {detail}" if detail else ""))
    if not condition:
        echecs.append(nom)


def lance(port, extra):
    tmp = Path(tempfile.mkdtemp(prefix="dnar-diag-"))
    env = dict(os.environ, DNAREADER_ADMIN=ADMIN, DNAREADER_SECRET=SECRET,
               DNAREADER_DONNEES=str(tmp), PYTHONIOENCODING="utf-8", **extra)
    p = subprocess.Popen(
        [str(PY_EXE), str(RACINE / "app" / "serveur_sync.py"),
         "--port", str(port), "--host", "127.0.0.1"],
        env=env, cwd=str(RACINE / "app"),
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    for _ in range(60):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/sante", timeout=1)
            return p
        except Exception:
            time.sleep(0.4)
    p.kill()
    raise SystemExit(f"le serveur du port {port} n'a pas démarré")


def poste(port, route, corps):
    req = urllib.request.Request(f"http://127.0.0.1:{port}{route}",
                                 json.dumps(corps).encode(),
                                 {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read().decode())


def main():
    print("1. RIEN N'EST CONFIGURE : le diagnostic doit NOMMER ce qui manque")
    srv = lance(8893, {})
    try:
        try:
            poste(8893, "/boutique/diagnostic", {"admin": "n'importe quoi"})
            verifie("il est ferme sans le jeton d'administration", False,
                    "la liste de ce qui manque dit ou est le trou")
        except urllib.error.HTTPError as e:
            verifie("il est ferme sans le jeton d'administration", e.code == 403,
                    f"HTTP {e.code}")

        d = poste(8893, "/boutique/diagnostic", {"admin": ADMIN})
        verifie("la boutique est annoncee fermee", d.get("ouverte") is False)

        api = d["abonnement_api"]
        vir = d["virement_discord"]
        print(f"     API      : manque {', '.join(api['manque'])}")
        print(f"     virement : manque {', '.join(vir['manque'])}")
        for nom in ("PAYPAL_ID", "PAYPAL_SECRET", "PAYPAL_WEBHOOK_ID",
                    "DNAREADER_PUBLIQUE"):
            verifie(f"l'API dit qu'il manque {nom}",
                    any(nom in m for m in api["manque"]))
        for nom in ("IMAP_HOTE", "DISCORD_JETON", "PAYPAL_ME"):
            verifie(f"le virement dit qu'il manque {nom}",
                    any(nom in m for m in vir["manque"]))
        verifie("et chaque chemin dit ce qu'il DEMANDE",
                "Business" in api["demande"] and "ordinaire" in vir["demande"],
                "sinon on ne sait pas lequel est a notre portee")
        verifie("et ce qu'il faut faire ENSUITE",
                len(api["apres"]) >= 2 and len(vir["apres"]) >= 2)
    finally:
        srv.terminate()

    print("\n2. TOUT EST REMPLI, MAIS EN BAC A SABLE — le piege le plus cher")
    srv = lance(8894, {
        "PAYPAL_ENV": "sandbox",
        "PAYPAL_ID": "id-de-test", "PAYPAL_SECRET": "secret-de-test",
        "PAYPAL_WEBHOOK_ID": "WH-TEST",
        "DNAREADER_PUBLIQUE": "https://dnareader.test"})
    try:
        d = poste(8894, "/boutique/diagnostic", {"admin": ADMIN})
        api = d["abonnement_api"]
        verifie("le bac a sable n'est PAS considere pret", not api["pret"])
        verifie("et la raison est nommee",
                any("live" in m for m in api["manque"]),
                ", ".join(api["manque"]))
        verifie("la boutique reste fermee", d.get("ouverte") is False)
        brut = json.dumps(d, ensure_ascii=False)
        verifie("aucun secret ne figure dans la reponse",
                "secret-de-test" not in brut and "id-de-test" not in brut,
                "on rend la PRESENCE, jamais la valeur")
    finally:
        srv.terminate()

    print("\n3. LE CHEMIN SIMPLE EST COMPLET : il doit dire PRET")
    srv = lance(8895, {
        "PAYPAL_ME": "https://paypal.me/nana",
        "IMAP_HOTE": "imap.test", "IMAP_UTILISATEUR": "moi@test",
        "IMAP_MOTDEPASSE": "motdepasse-reconnaissable",
        "DISCORD_JETON": "jeton-discord-reconnaissable",
        "DISCORD_SERVEUR": "123456789012345678"})
    try:
        d = poste(8895, "/boutique/diagnostic", {"admin": ADMIN})
        vir = d["virement_discord"]
        verifie("le virement est PRET", vir["pret"], str(vir["manque"]))
        verifie("et la boutique s'annonce ouverte", d.get("ouverte") is True)
        brut = json.dumps(d, ensure_ascii=False)
        verifie("toujours aucun secret dans la reponse",
                "motdepasse-reconnaissable" not in brut
                and "jeton-discord-reconnaissable" not in brut)
        verifie("l'autre chemin reste annonce incomplet",
                not d["abonnement_api"]["pret"],
                "les deux chemins ne se confondent pas")
    finally:
        srv.terminate()

    print("\n4. LE SCRIPT D'INSTALLATION PREPARE LES LIGNES")
    src = (RACINE / "outils" / "paquet_serveur.py").read_text(encoding="utf-8")
    for nom in ("PAYPAL_ME", "IMAP_HOTE", "DISCORD_JETON", "PAYPAL_ID",
                "PAYPAL_ENV", "DNAREADER_PUBLIQUE"):
        verifie(f"secrets.env recevra {nom}", f'echo "{nom}=' in src)
    verifie("et l'installation renvoie vers le diagnostic",
            "cles.py boutique" in src,
            "sinon il faut relire le code pour savoir ou on en est")

    print()
    if echecs:
        print(f"{len(echecs)} ECHEC(S) : " + " · ".join(echecs))
        return 1
    print("OK : on sait enfin ce qui manque pour encaisser, sans se connecter")
    print("     au serveur — et le bac a sable ne passe pas pour une boutique")
    return 0


if __name__ == "__main__":
    sys.exit(main())
