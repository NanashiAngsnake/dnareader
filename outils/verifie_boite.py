# -*- coding: utf-8 -*-
import email
import email.header
import imaplib
import os
import ssl
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "app"))
sys.stdout.reconfigure(encoding="utf-8")

HOTE = os.environ.get("IMAP_HOTE", "").strip()
PORT = int(os.environ.get("IMAP_PORT", "993"))
UTILISATEUR = os.environ.get("IMAP_UTILISATEUR", "").strip()
MOTDEPASSE = os.environ.get("IMAP_MOTDEPASSE", "")
DOSSIER = os.environ.get("IMAP_DOSSIER", "INBOX").strip()
JOURS = int(os.environ.get("DNAREADER_VERIF_JOURS", "120"))


def main():
    if not (HOTE and UTILISATEUR and MOTDEPASSE):
        print("Il manque IMAP_HOTE, IMAP_UTILISATEUR ou IMAP_MOTDEPASSE dans")
        print("l'environnement. Cet outil ne les lit QUE là : un mot de passe")
        print("écrit dans un fichier du dépôt finirait publié au premier push.")
        return 2

    import livraison
    print(f"Boîte    : {UTILISATEUR} sur {HOTE}:{PORT}, dossier {DOSSIER}")
    print(f"Prix     : {livraison.PRIX:.2f} € (tolérance {livraison.TOLERANCE:.2f})")
    print(f"Note attendue dans le virement : « {livraison.PREFIXE}-pseudo »")
    print()

    try:
        ctx = ssl.create_default_context()
        boite = imaplib.IMAP4_SSL(HOTE, PORT, ssl_context=ctx)
    except Exception as e:
        print(f"ECHEC : impossible de joindre {HOTE}:{PORT} — {e}")
        return 1
    with boite:
        try:
            boite.login(UTILISATEUR, MOTDEPASSE)
        except Exception as e:
            print(f"ECHEC : connexion refusée — {e}")
            print()
            print("Sur Gmail, un mot de passe ordinaire ne marche pas : il faut")
            print("un « mot de passe d'application » (compte Google → Sécurité →")
            print("Validation en deux étapes → Mots de passe des applications).")
            return 1
        print("Connexion : OK")

        typ, _ = boite.select(DOSSIER, readonly=True)
        if typ != "OK":
            print(f"ECHEC : le dossier « {DOSSIER} » est introuvable.")
            typ, boites = boite.list()
            if typ == "OK":
                print("Dossiers disponibles :")
                for b in (boites or [])[:25]:
                    print("   ", b.decode("utf-8", "replace"))
            return 1

        typ, donnees = boite.search(None, "UNSEEN")
        non_lus = len(donnees[0].split()) if typ == "OK" and donnees[0] else 0
        print(f"Messages non lus dans {DOSSIER} : {non_lus}")
        print("   (c'est là-dedans que la boucle de production cherche)")
        print()

        import datetime
        depuis = (datetime.date.today()
                  - datetime.timedelta(days=JOURS)).strftime("%d-%b-%Y")
        trouves = []
        for domaine in livraison.DOMAINES:
            typ, d = boite.search(None, f'(SINCE {depuis} FROM "{domaine}")')
            if typ == "OK" and d and d[0]:
                trouves += d[0].split()
        trouves = sorted(set(trouves), key=int)[-10:]

        print(f"Courriels PayPal des {JOURS} derniers jours : {len(trouves)}")
        if not trouves:
            print()
            print("AUCUN. C'est le point à régler avant tout le reste : si les")
            print("courriels de PayPal n'arrivent pas dans ce dossier, la clé ne")
            print("partira jamais. Vérifie que c'est bien l'adresse de ton compte")
            print("PayPal, et qu'aucun filtre ne les range ailleurs.")
            return 1

        print()
        bons = 0
        for num in trouves:
            typ, bout = boite.fetch(num, "(BODY.PEEK[])")
            if typ != "OK" or not bout or not bout[0]:
                continue
            msg = email.message_from_bytes(bout[0][1])
            ok, pourquoi = livraison.vient_de_paypal(msg)
            info = livraison.lis_le_paiement(msg)
            sujet = (info["sujet"] or "(sans sujet)")[:58]
            if ok:
                ok, pourquoi = livraison.est_un_encaissement(info["sujet"])
            print(f"  {'ENCAISSEMENT' if ok else 'ecarte      '}  {sujet}")
            if not ok:
                print(f"                -> {pourquoi}")
                continue
            bons += 1
            m = [x for x in info["montants"]
                 if abs(x - livraison.PRIX) <= livraison.TOLERANCE]
            print(f"           montants lus : {info['montants'] or 'aucun'}"
                  f"{'  (dont un au bon prix)' if m else ''}")
            print(f"           note « {livraison.PREFIXE}-… » : "
                  f"{info['pseudo'] or 'absente'}")

        print()
        print(f"{bons}/{len(trouves)} courriels PayPal sont de VRAIS "
              f"encaissements.")
        print("   (les autres sont authentiques mais ne rapportent rien :")
        print("    demandes, paiements sortants, suivis de commande)")
        if not bons:
            print()
            print("AUCUN N'EST UN ENCAISSEMENT. Si tu n'as jamais reçu d'argent")
            print("sur ce compte, c'est normal. Sinon, cause la plus fréquente :")
            print("l'en-tête")
            print("`Authentication-Results` manque, parce que le serveur de")
            print("réception ne vérifie pas DKIM. Sans lui on ne peut pas")
            print("distinguer un vrai courriel PayPal d'un faux — et on refuse,")
            print("plutôt que de livrer des clés à qui sait s'envoyer un mail.")
            return 1
        print("La boîte est lisible et les courriels PayPal sont reconnus.")
        print()
        print("IL RESTE LE VRAI TEST : un virement de "
              f"{livraison.PRIX:.2f} € à toi-même,")
        print(f"avec « {livraison.PREFIXE}-tonpseudo » en note.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
