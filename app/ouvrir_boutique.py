# -*- coding: utf-8 -*-
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding="utf-8")

SECRETS = Path(os.environ.get("DNAREADER_SECRETS")
               or Path.home() / "dnareader" / "secrets.env")


def charge(fichier: Path):
    if not fichier.exists():
        return
    for ligne in fichier.read_text(encoding="utf-8").splitlines():
        ligne = ligne.strip()
        if not ligne or ligne.startswith("#") or "=" not in ligne:
            continue
        nom, _, valeur = ligne.partition("=")
        os.environ.setdefault(nom.strip(), valeur.strip())


def ecris(fichier: Path, nom: str, valeur: str):
    texte = fichier.read_text(encoding="utf-8") if fichier.exists() else ""
    motif = re.compile(rf"^{re.escape(nom)}=.*$", re.M)
    if motif.search(texte):
        texte = motif.sub(f"{nom}={valeur}", texte, count=1)
    else:
        texte = texte.rstrip("\n") + f"\n{nom}={valeur}\n"
    fichier.write_text(texte, encoding="utf-8")
    os.chmod(fichier, 0o600)


def main():
    charge(SECRETS)
    import boutique

    print(f"Environnement PayPal : {boutique.ENV}")
    print(f"Adresse publique     : {boutique.PUBLIQUE or '(vide)'}")
    print()

    if not (boutique.ID and boutique.SECRET):
        print("Il manque PAYPAL_ID et/ou PAYPAL_SECRET dans", SECRETS)
        print()
        print("  Va sur https://developer.paypal.com/dashboard/applications/sandbox")
        print("  → Create App → note le Client ID et le Secret")
        print(f"  → mets-les dans {SECRETS}, puis relance ce script.")
        return 1

    r = boutique.assure_webhook()
    if not r.get("ok"):
        print("Echec :", r.get("raison"))
        return 1

    print(("Webhook deja en place" if r["deja"] else "Webhook cree"), ":", r["url"])
    print("  evenements :", ", ".join(boutique.EVENEMENTS))
    print("  identifiant :", r["id"])
    ecris(SECRETS, "PAYPAL_WEBHOOK_ID", r["id"])
    print()
    print(f"Ecrit dans {SECRETS}.")
    print()
    print("Il reste a relancer le service :")
    print("  sudo systemctl restart dnareader-sync")
    print("  curl -s localhost:8800/boutique | head -3")
    return 0


if __name__ == "__main__":
    sys.exit(main())
