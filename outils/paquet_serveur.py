# -*- coding: utf-8 -*-
import ast
import io
import sys
import tarfile
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "app"))
sys.stdout.reconfigure(encoding="utf-8")
import version

INSTALLE = """#!/usr/bin/env bash
# Installe le serveur DNAreader. A lancer SUR LE SERVEUR, une fois.
set -euo pipefail

BASE="${DNAREADER_BASE:-$HOME/dnareader}"
PORT="${DNAREADER_PORT:-8800}"

echo "Installation dans $BASE"
mkdir -p "$BASE/donnees"
cp -f app/*.py "$BASE/"

python3 -m venv "$BASE/venv"
"$BASE/venv/bin/pip" install --quiet --upgrade pip
"$BASE/venv/bin/pip" install --quiet fastapi uvicorn

# LES SECRETS SE FABRIQUENT ICI, sur la machine qui les utilisera. Les mettre
# dans le depot les rendrait publics, et un secret publie n'est plus un secret.
if [ ! -f "$BASE/secrets.env" ]; then
  {
    echo "DNAREADER_SECRET=$(openssl rand -hex 32)"
    echo "DNAREADER_ADMIN=$(openssl rand -hex 24)"
    echo "DNAREADER_DONNEES=$BASE/donnees"
  } > "$BASE/secrets.env"
  chmod 600 "$BASE/secrets.env"
  echo
  echo "Secrets crees dans $BASE/secrets.env :"
  echo
  grep DNAREADER_ADMIN "$BASE/secrets.env"
  echo
  echo "  ^ c'est le jeton qui permet de DELIVRER des cles. Garde-le."
  echo "    Sans lui, le serveur refuse d'en creer aucune."
else
  echo "secrets.env existe deja : on n'y touche pas."
fi

echo
echo "Pour le lancer a la main :"
echo "  set -a; . $BASE/secrets.env; set +a"
echo "  $BASE/venv/bin/python $BASE/serveur_sync.py --port $PORT"

# LE FICHIER DE SERVICE EST ECRIT ICI, AVEC LE VRAI UTILISATEUR ET LE VRAI PORT.
#
# Le modele porte %i et 8800 en dur. Or %i ne s'etend QUE dans une unite
# « template » (nom@instance.service) : copie tel quel sous un nom simple, il
# donne User= vide et des chemins /home//dnareader, et le service refuse de
# demarrer avec un message qui ne dit pas pourquoi. Mesure faite en deployant.
sed -e "s|%i|$(id -un)|g" -e "s|--port 8800|--port $PORT|" \
    dnareader-sync.service > "$BASE/dnareader-sync.service"

sed -e "s|%i|$(id -un)|g" dnareader-bot.service > "$BASE/dnareader-bot.service"

# LE BOT DISCORD EST FACULTATIF, et sa bibliotheque ne pese rien : on l'installe
# d'office, le service ne se lance que si on le demande. Un bot sans jeton
# s'arreterait en boucle et remplirait le journal pour rien.
"$BASE/venv/bin/pip" install --quiet -U discord.py ||   echo "  (discord.py non installe : le bot ne pourra pas demarrer)"
# LE PAIEMENT : ON PREPARE LES LIGNES, VIDES, AVEC CE QU'IL FAUT EN FACE.
#
# Tout le code d'encaissement etait ecrit et verifie, et la boutique restait
# fermee : il manquait des variables que rien ne mentionnait. On deployait, on
# ouvrait la page, on lisait « boutique non configuree », et il fallait
# retrouver dans le code lesquelles. Elles sont donc ecrites ici, commentees,
# avec les deux chemins possibles — et « cles.py boutique » dit a tout moment
# lequel est pret.
if ! grep -q PAYPAL_ME "$BASE/secrets.env"; then
  {
    echo ""
    echo "# ============================ ENCAISSER ============================"
    echo "# DEUX CHEMINS. Le premier suffit pour commencer."
    echo "#"
    echo "# ---- 1. VIREMENT PayPal + livraison Discord --------------------"
    echo "# Marche depuis un compte PayPal ORDINAIRE : pas de societe a creer."
    echo "# L'acheteur paie en laissant « DNAR-sonpseudo » en note ; on lit le"
    echo "# courriel de PayPal et on lui envoie sa cle en message prive."
    echo "# Il faut une boite mail qui recoit les courriels PayPal, en IMAP."
    echo "PAYPAL_ME="
    echo "IMAP_HOTE="
    echo "IMAP_UTILISATEUR="
    echo "IMAP_MOTDEPASSE="
    echo "DISCORD_JETON="
    echo "DISCORD_SERVEUR="
    echo "#"
    echo "# ---- 2. ABONNEMENT automatique (API PayPal) --------------------"
    echo "# Preleve tout seul chaque mois. Demande un compte PayPal BUSINESS,"
    echo "# donc une entreprise enregistree."
    echo "# Une fois ID et SECRET remplis :  python ouvrir_boutique.py"
    echo "# (il cree le webhook et remplit PAYPAL_WEBHOOK_ID tout seul)"
    echo "#"
    echo "# ET SURTOUT : PAYPAL_ENV=live. En « sandbox » PayPal repond, cree"
    echo "# des abonnements et envoie de vrais rappels signes — sans jamais"
    echo "# encaisser un centime."
    echo "PAYPAL_ENV=sandbox"
    echo "PAYPAL_ID="
    echo "PAYPAL_SECRET="
    echo "PAYPAL_WEBHOOK_ID="
    echo "#"
    echo "# L'adresse publique du serveur, en https. PayPal y postera ses"
    echo "# rappels : sans elle le webhook ne peut pas etre cree."
    echo "DNAREADER_PUBLIQUE="
    echo "#"
    echo "DNAREADER_PRIX=5.00"
    echo "DNAREADER_DEVISE=EUR"
  } >> "$BASE/secrets.env"
fi

if ! grep -q DISCORD_TOKEN "$BASE/secrets.env"; then
  {
    echo ""
    echo "# Bot Discord — a remplir pour distribuer les cles sur le serveur."
    echo "# Le jeton se cree sur https://discord.com/developers/applications"
    echo "# et n'existe QUE dans ce fichier."
    echo "DISCORD_TOKEN="
    echo "DISCORD_GUILD="
    echo "DISCORD_ROLE_ABONNE="
  } >> "$BASE/secrets.env"
fi

echo
echo "Pour en faire un service (fichier deja prepare pour $(id -un) et le port $PORT) :"
echo "  sudo cp $BASE/dnareader-sync.service /etc/systemd/system/"
echo "  sudo systemctl daemon-reload && sudo systemctl enable --now dnareader-sync"
echo
echo
echo "Bot Discord (facultatif) : remplis DISCORD_TOKEN dans secrets.env, puis"
echo "  sudo cp $BASE/dnareader-bot.service /etc/systemd/system/"
echo "  sudo systemctl daemon-reload && sudo systemctl enable --now dnareader-bot"
echo
echo "ENCAISSER : les lignes sont preparees, vides, dans secrets.env."
echo "  Le plus simple : remplis PAYPAL_ME + IMAP_* + DISCORD_JETON"
echo "  (compte PayPal ordinaire, pas de societe a creer)."
echo "  A tout moment, pour savoir ce qui manque encore :"
echo "    python outils/cles.py boutique"
echo
echo "ET DERRIERE HTTPS. Sans lui, le derive du mot de passe circule en clair,"
echo "et le rejouer suffit a se connecter."
"""

SERVICE_BOT = """[Unit]
Description=DNAreader — bot Discord (cles et abonnes Twitch)
After=network-online.target dnareader-sync.service
Wants=network-online.target

[Service]
Type=simple
# %i EST UN MODELE : installe.sh le remplace par l'utilisateur reel.
User=%i
WorkingDirectory=/home/%i/dnareader
EnvironmentFile=/home/%i/dnareader/secrets.env
ExecStart=/home/%i/dnareader/venv/bin/python /home/%i/dnareader/bot_discord.py
Restart=always
RestartSec=15
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
"""


SERVICE = """[Unit]
Description=DNAreader — cles d'acces et corrections partagees
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
# %i EST UN MODELE : installe.sh le remplace par l'utilisateur reel et ecrit le
# fichier pret a copier dans le dossier d'installation. Ne copie pas CE
# fichier-ci tel quel — %i ne s'etend que dans une unite « nom@instance ».
User=%i
WorkingDirectory=/home/%i/dnareader
EnvironmentFile=/home/%i/dnareader/secrets.env
ExecStart=/home/%i/dnareader/venv/bin/python /home/%i/dnareader/serveur_sync.py --port 8800 --host 127.0.0.1
Restart=always
RestartSec=5
# Le serveur n'ecoute que sur la boucle locale : c'est le reverse proxy (ou le
# tunnel) qui l'expose en HTTPS. L'ouvrir directement sur Internet ferait
# circuler en clair le derive du mot de passe.
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
"""

LISEZMOI = f"""# Serveur DNAreader {version.VERSION}

Clés d'accès + corrections partagées + synchronisation. FastAPI et SQLite,
rien d'autre : ni dictionnaire, ni modèle, ni OCR.

## Installer

    tar xzf dnareader-serveur-{version.VERSION}.tar.gz
    cd dnareader-serveur
    ./installe.sh

Le script fabrique les secrets sur place et affiche le **jeton
d'administration** : c'est lui qui permet de délivrer des clés. Sans lui, le
serveur en refuse la création — un serveur mal configuré doit être inutile,
pas permissif.

## Exposer

**En HTTPS, obligatoirement.** Le serveur écoute sur 127.0.0.1 ; c'est un
reverse proxy (nginx + Let's Encrypt) ou un tunnel Cloudflare qui le publie.

## Délivrer une clé, depuis ton poste

    set DNAREADER_SERVEUR=https://ton-serveur
    set DNAREADER_ADMIN=<le jeton>
    python outils\\cles.py creer --note "offerte a X"

## Vérifier qu'il vit

    curl https://ton-serveur/sante
    -> {{"ok": true, "app": "dnareader-sync"}}

## Sauvegarder

Tout est dans `donnees/sync.db`. C'est ce fichier qui contient les clés, les
activations et les corrections de la communauté : c'est lui qu'il faut
sauvegarder, et rien d'autre.
"""


def modules_du_serveur(depart="serveur_sync.py") -> list:
    app = RACINE / "app"
    vus, a_voir = [], [depart, "ouvrir_boutique.py", "bot_discord.py"]
    while a_voir:
        f = a_voir.pop(0)
        if f in vus or not (app / f).exists():
            continue
        vus.append(f)
        arbre = ast.parse((app / f).read_text(encoding="utf-8"))
        for n in ast.walk(arbre):
            noms = []
            if isinstance(n, ast.Import):
                noms = [a.name.split(".")[0] for a in n.names]
            elif isinstance(n, ast.ImportFrom) and n.level == 0 and n.module:
                noms = [n.module.split(".")[0]]
            for nom in noms:
                if (app / f"{nom}.py").exists():
                    a_voir.append(f"{nom}.py")
    return vus


def main():
    dist = RACINE / "dist"
    dist.mkdir(exist_ok=True)
    cible = dist / f"dnareader-serveur-{version.VERSION}.tar.gz"
    quand = time.time()

    def ajoute(tar, nom, contenu: str, mode=0o644):
        data = contenu.replace("\r\n", "\n").encode("utf-8")
        info = tarfile.TarInfo("dnareader-serveur/" + nom)
        info.size = len(data)
        info.mode = mode
        info.mtime = int(quand)
        tar.addfile(info, io.BytesIO(data))

    modules = modules_du_serveur()
    with tarfile.open(cible, "w:gz") as tar:
        for f in modules:
            ajoute(tar, "app/" + f,
                   (RACINE / "app" / f).read_text(encoding="utf-8"))
        ajoute(tar, "installe.sh", INSTALLE, mode=0o755)
        ajoute(tar, "dnareader-sync.service", SERVICE)
        ajoute(tar, "dnareader-bot.service", SERVICE_BOT)
        ajoute(tar, "LISEZMOI.md", LISEZMOI)

    print(f"{cible}")
    print(f"{cible.stat().st_size / 1024:.0f} Ko — {len(modules)} fichiers "
          f"Python ({', '.join(modules)}), un script d'installation, "
          f"un service systemd.")
    print()
    print("Ce paquet ne se deploie pas tout seul, et c'est voulu : le poser sur")
    print("le serveur et lancer ./installe.sh reste un geste humain.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
