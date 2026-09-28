# -*- coding: utf-8 -*-
import email
import os
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.stdout.reconfigure(encoding="utf-8")

TMP = Path(tempfile.mkdtemp(prefix="dnar-livraison-"))
os.environ["DNAREADER_DONNEES"] = str(TMP)
sys.path.insert(0, str(RACINE / "app"))

import licences
import livraison

echecs = []
envoyes = []


def verifie(nom, condition, detail=""):
    print(f"  {'OK  ' if condition else 'ECHEC'} {nom}"
          + (f" — {detail}" if detail else ""))
    if not condition:
        echecs.append(nom)


AUTH_BON = ("mx.google.com; dkim=pass header.i=@paypal.com "
            "header.s=pp-dkim1 header.b=abc; spf=pass")


def courriel(de="service@paypal.fr", note="DNAR-nana", montant="5,00 EUR",
             auth=AUTH_BON, trans="9AB12345CD6789012",
             sujet="Vous avez recu un paiement"):
    m = email.message.EmailMessage()
    m["From"] = f"PayPal <{de}>"
    m["To"] = "moi@exemple.fr"
    m["Subject"] = sujet
    m["Message-ID"] = f"<{trans}@paypal>"
    if auth:
        m["Authentication-Results"] = auth
    m.set_content(
        f"Bonjour,\n\nVous avez recu {montant} de la part de Quelqu'un.\n"
        f"Numero de transaction {trans}\n"
        f"Note de l'acheteur : {note}\n")
    return m


def faux_envoi(pseudo, cle):
    envoyes.append((pseudo, cle))
    return {"ok": True, "tag": pseudo}


def cles(con):
    return con.execute("SELECT COUNT(*) FROM licences").fetchone()[0]


def main():
    livraison.PAYPAL_ME = "https://paypal.me/exemple"
    livraison.envoie_la_cle = faux_envoi
    con = sqlite3.connect(TMP / "banc.db", check_same_thread=False)
    licences.prepare(con)
    livraison.prepare(con)

    try:
        print("1. UN FAUX EXPEDITEUR NE LIVRE RIEN")
        for de, pourquoi in (
                ("paypal@attaquant.ru", "le mot est dans la partie locale"),
                ("service@paypal.attaquant.com", "paypal n'est qu'un sous-domaine"),
                ("noreply@notpaypal.com", "le domaine contient paypal"),
                ("service@paypal.com.attaquant.fr", "paypal.com au milieu")):
            avant = cles(con)
            r = livraison.traite_un_message(con, courriel(de=de, trans=f"T{de[:6]}"))
            verifie(f"refuse {de}", "ignore" in r and cles(con) == avant, pourquoi)

        print("\n2. SANS DKIM, ON NE LIVRE PAS NON PLUS")
        for auth, pourquoi in (
                ("", "aucun en-tete d'authentification"),
                ("mx.google.com; dkim=fail header.i=@paypal.com", "DKIM echoue"),
                ("mx.google.com; dkim=pass header.i=@attaquant.com",
                 "DKIM valide, mais pas pour PayPal"),
                ("mx.google.com; spf=pass", "SPF seul ne suffit pas")):
            avant = cles(con)
            r = livraison.traite_un_message(
                con, courriel(auth=auth, trans=f"D{abs(hash(auth)) % 99999}"))
            verifie(f"refuse : {pourquoi}", "ignore" in r and cles(con) == avant,
                    r.get("ignore", "")[:55])

        print("\n3. UN VRAI COURRIEL PAYPAL LIVRE LA CLE")
        avant = cles(con)
        r = livraison.traite_un_message(con, courriel())
        verifie("la cle est creee", bool(r.get("livree")), str(r)[:70])
        verifie("et une seule", cles(con) == avant + 1)
        verifie("elle part en message prive", envoyes and envoyes[-1][0] == "nana",
                str(envoyes[-1] if envoyes else None))
        cle = r.get("livree")

        print("\n4. LE MEME COURRIEL RELU NE LIVRE PAS DEUX FOIS")
        n = cles(con)
        r = livraison.traite_un_message(con, courriel())
        verifie("il est reconnu comme deja traite",
                r.get("ignore") == "paiement deja traite", str(r)[:60])
        verifie("aucune seconde cle", cles(con) == n)

        print("\n5. LE MOIS SUIVANT PROLONGE LA MEME CLE")
        n = cles(con)
        avant_exp = con.execute("SELECT expire FROM licences WHERE cle=?",
                                (cle,)).fetchone()[0]
        r = livraison.traite_un_message(
            con, courriel(trans="9ZZ88888ZZ8888888"))
        apres_exp = con.execute("SELECT expire FROM licences WHERE cle=?",
                                (cle,)).fetchone()[0]
        verifie("c'est la meme cle", r.get("livree") == cle, str(r.get("livree")))
        verifie("aucune cle supplementaire", cles(con) == n,
                "sinon l'abonne en recoit une nouvelle chaque mois")
        verifie("l'echeance avance de 31 jours",
                30.5 < (apres_exp - avant_exp) / 86400 < 31.5,
                f"+{(apres_exp - avant_exp) / 86400:.1f} jours")

        print("\n6. PAYER MOINS NE DONNE PAS UN MOIS")
        avant = cles(con)
        r = livraison.traite_un_message(
            con, courriel(note="DNAR-radin", montant="1,00 EUR",
                          trans="9RA11111DI1111111"))
        verifie("le paiement est refuse", "refuse" in r, str(r)[:60])
        verifie("aucune cle creee", cles(con) == avant)

        print("\n7. SANS NOTE, ON NE SAIT PAS A QUI ENVOYER")
        avant = cles(con)
        r = livraison.traite_un_message(
            con, courriel(note="merci beaucoup", trans="9NO00000TE0000000"))
        verifie("on n'invente pas de destinataire", "ignore" in r
                and cles(con) == avant, r.get("ignore", "")[:50])

        print("\n8. LA TOLERANCE LAISSE PASSER UN ARRONDI")
        avant = cles(con)
        r = livraison.traite_un_message(
            con, courriel(note="DNAR-arrondi", montant="4,80 EUR",
                          trans="9AR44444ON4444444"))
        verifie("4,80 EUR pour 5,00 passe", bool(r.get("livree")), str(r)[:60])

        print("\n9. UNE LIVRAISON QUI ECHOUE NE PERD PAS LA CLE")
        livraison.envoie_la_cle = lambda p, c: {"ok": False, "raison": "DM fermes"}
        r = livraison.traite_un_message(
            con, courriel(note="DNAR-injoignable", trans="9IN55555JO5555555"))
        verifie("la cle est quand meme creee", bool(r.get("cle")), str(r)[:60])
        etat = con.execute("SELECT etat, cle FROM livraisons WHERE virement=?",
                           ("9IN55555JO5555555",)).fetchone()
        verifie("et notee « a livrer »", etat and etat[0] == "a livrer",
                str(etat))
        verifie("avec la cle, pour la retrouver", etat and etat[1] == r.get("cle"))

        print("\nDEMANDER DE L'ARGENT N'EST PAS EN RECEVOIR")
        for sujet, ce_que_c_est in (
                ("Jean vous demande 10,00 EUR", "une demande de paiement"),
                ("Facture de 5,00 EUR", "une facture"),
                ("Recu de votre paiement PayPal", "un paiement sortant"),
                ("Votre commande Atolea Jewelry est en cours d'envoi",
                 "un suivi de commande"),
                ("Confirmation de changement de mot de passe", "autre chose")):
            envoyes.clear()
            r = livraison.traite_un_message(
                con, courriel(sujet=sujet, trans=f"T{abs(hash(sujet)) % 10**16:016d}"))
            verifie(f"{ce_que_c_est} ne livre rien",
                    not r.get("livree") and not envoyes,
                    r.get("ignore") or str(r)[:60])

        for sujet in ("Vous avez recu de l'argent",
                      "Vous avez reçu de l'argent",
                      "You have received money",
                      "Nana vous a envoye 5,00 EUR"):
            ok, pourquoi = livraison.est_un_encaissement(sujet)
            verifie(f"« {sujet} » reste un encaissement", ok, pourquoi)

    finally:
        con.close()
        shutil.rmtree(TMP, ignore_errors=True)

    print()
    if echecs:
        print(f"{len(echecs)} ECHEC(S) : " + " · ".join(echecs))
        return 1
    print("OK : un faux courriel ne livre rien, un vrai livre une fois,")
    print("     et un renouvellement prolonge la meme cle")
    return 0


if __name__ == "__main__":
    sys.exit(main())
