# -*- coding: utf-8 -*-
import json
import os
import shutil
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
PORT_PP = 8896
sys.stdout.reconfigure(encoding="utf-8")

TMP = Path(tempfile.mkdtemp(prefix="dnar-boutique-"))
os.environ["DNAREADER_DONNEES"] = str(TMP)
sys.path.insert(0, str(RACINE / "app"))

import boutique
import licences

echecs = []
FAUX = {"signature": "SUCCESS", "appels": [], "n": 0, "webhooks": []}


def verifie(nom, condition, detail=""):
    print(f"  {'OK  ' if condition else 'ECHEC'} {nom}"
          + (f" — {detail}" if detail else ""))
    if not condition:
        echecs.append(nom)


class PayPalDeBanc(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        rep = ({"webhooks": FAUX["webhooks"]}
               if self.path.endswith("/notifications/webhooks") else {})
        data = json.dumps(rep).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        corps = self.rfile.read(n).decode() if n else "{}"
        FAUX["appels"].append(self.path)
        if self.path.endswith("/oauth2/token"):
            rep = {"access_token": "jeton-de-banc", "expires_in": 3600}
        elif self.path.endswith("/catalogs/products"):
            rep = {"id": "PROD-BANC"}
        elif self.path.endswith("/billing/plans"):
            rep = {"id": "P-BANC"}
        elif self.path.endswith("/billing/subscriptions"):
            FAUX["n"] += 1
            i = f"I-ABONNE{FAUX['n']}"
            rep = {"id": i, "status": "APPROVAL_PENDING",
                   "links": [{"rel": "approve",
                              "href": f"https://paypal.test/approve/{i}"}]}
        elif self.path.endswith("/notifications/webhooks"):
            FAUX["webhooks"].append({"id": f"WH-BANC{len(FAUX['webhooks'])+1}",
                                     "url": json.loads(corps).get("url")})
            rep = FAUX["webhooks"][-1]
        elif "verify-webhook-signature" in self.path:
            rep = {"verification_status": FAUX["signature"]}
        else:
            rep = {}
        data = json.dumps(rep).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


ENTETES = {
    "PAYPAL-AUTH-ALGO": "SHA256withRSA",
    "PAYPAL-CERT-URL": "https://paypal.test/cert",
    "PAYPAL-TRANSMISSION-ID": "t-1",
    "PAYPAL-TRANSMISSION-SIG": "sig",
    "PAYPAL-TRANSMISSION-TIME": "2026-08-23T02:00:00Z",
}


def evenement(genre, id_evenement, ressource):
    return json.dumps({"id": id_evenement, "event_type": genre,
                       "resource": ressource})


def cles(con):
    return con.execute("SELECT COUNT(*) FROM licences").fetchone()[0]


def expire_de(con, cle):
    r = con.execute("SELECT expire FROM licences WHERE cle=?", (cle,)).fetchone()
    return r[0] if r else None


def main():
    srv = ThreadingHTTPServer(("127.0.0.1", PORT_PP), PayPalDeBanc)
    threading.Thread(target=srv.serve_forever, daemon=True).start()

    boutique.API = f"http://127.0.0.1:{PORT_PP}"
    boutique.ID = "id-de-banc"
    boutique.SECRET = "secret-de-banc"
    boutique.WEBHOOK_ID = "webhook-de-banc"
    boutique.PUBLIQUE = "https://dnareader.test"

    import sqlite3
    con = sqlite3.connect(TMP / "banc.db", check_same_thread=False)
    licences.prepare(con)
    boutique.prepare(con)
    SECRET_LIC = "secret-licence-de-banc"

    try:
        print("1. LA BOUTIQUE REFUSE DE S'OUVRIR SANS SA CONFIGURATION")
        vrai = boutique.WEBHOOK_ID
        boutique.WEBHOOK_ID = ""
        verifie("elle se declare fermee", boutique.configuree() is False)
        verifie("et elle dit ce qui manque",
                "PAYPAL_WEBHOOK_ID" in boutique.pourquoi_pas(),
                boutique.pourquoi_pas())
        boutique.WEBHOOK_ID = vrai

        print("\n2. UN FAUX RAPPEL NE DELIVRE AUCUNE CLE")
        avant = cles(con)
        FAUX["signature"] = "FAILURE"
        r = boutique.rappel(con, ENTETES, evenement(
            "BILLING.SUBSCRIPTION.ACTIVATED", "EV-FAUX",
            {"id": "I-VOLEUR",
             "subscriber": {"email_address": "voleur@exemple.fr"}}), SECRET_LIC)
        verifie("le rappel est refuse", r.get("ok") is False,
                r.get("raison", ""))
        verifie("AUCUNE cle n'a ete creee", cles(con) == avant,
                f"{cles(con)} cle(s), {avant} avant")

        print("\n3. sans en-tetes de signature du tout : refuse aussi")
        FAUX["signature"] = "SUCCESS"
        r = boutique.rappel(con, {}, evenement(
            "BILLING.SUBSCRIPTION.ACTIVATED", "EV-NU",
            {"id": "I-NU"}), SECRET_LIC)
        verifie("un rappel sans signature ne passe pas", r.get("ok") is False)
        verifie("toujours aucune cle", cles(con) == avant)

        print("\n4. UN VRAI RAPPEL delivre une cle, et une seule")
        r = boutique.rappel(con, ENTETES, evenement(
            "BILLING.SUBSCRIPTION.ACTIVATED", "EV-1",
            {"id": "I-DIRECT",
             "subscriber": {"email_address": "acheteur@exemple.fr"}}), SECRET_LIC)
        verifie("la cle est delivree", r.get("ok") and r.get("cle"),
                str(r.get("cle")))
        cle = r["cle"]
        verifie("elle est liee au courriel de l'acheteur",
                r.get("courriel") == "acheteur@exemple.fr")
        e1 = expire_de(con, cle)
        verifie("elle court 31 jours",
                30.5 < (e1 - time.time()) / 86400 < 31.5,
                f"{(e1 - time.time()) / 86400:.1f} jours")

        print("\n5. LE MEME RAPPEL REJOUE NE DONNE RIEN DE PLUS")
        n = cles(con)
        r = boutique.rappel(con, ENTETES, evenement(
            "BILLING.SUBSCRIPTION.ACTIVATED", "EV-1",
            {"id": "I-DIRECT",
             "subscriber": {"email_address": "acheteur@exemple.fr"}}), SECRET_LIC)
        verifie("il est reconnu comme deja traite",
                r.get("deja_traite") is True, str(r)[:60])
        verifie("aucune seconde cle", cles(con) == n)
        verifie("et l'echeance n'a pas bouge", expire_de(con, cle) == e1)

        print("\n6. le premier paiement ne compte PAS deux fois")
        r = boutique.rappel(con, ENTETES, evenement(
            "PAYMENT.SALE.COMPLETED", "EV-P1",
            {"id": "S-1", "billing_agreement_id": "I-DIRECT"}), SECRET_LIC)
        verifie("il est reconnu comme deja credite",
                r.get("premier_paiement_deja_compte") is True, str(r)[:60])
        verifie("l'echeance n'a pas bouge", expire_de(con, cle) == e1,
                f"{(expire_de(con, cle) - e1) / 86400:.1f} jours d'ecart")

        print("\n7. LE MOIS SUIVANT prolonge LA MEME cle")
        n = cles(con)
        r = boutique.rappel(con, ENTETES, evenement(
            "PAYMENT.SALE.COMPLETED", "EV-P2",
            {"id": "S-2", "billing_agreement_id": "I-DIRECT"}), SECRET_LIC)
        e2 = expire_de(con, cle)
        verifie("c'est bien la meme cle", r.get("cle") == cle, str(r.get("cle")))
        verifie("aucune cle supplementaire n'est creee", cles(con) == n,
                "sinon l'abonne recoit une cle par mois")
        verifie("l'echeance avance de 31 jours",
                30.5 < (e2 - e1) / 86400 < 31.5,
                f"+{(e2 - e1) / 86400:.1f} jours")

        print("\n8. un paiement rejoue ne prolonge pas non plus")
        boutique.rappel(con, ENTETES, evenement(
            "PAYMENT.SALE.COMPLETED", "EV-P2",
            {"id": "S-2", "billing_agreement_id": "I-DIRECT"}), SECRET_LIC)
        verifie("l'echeance est inchangee", expire_de(con, cle) == e2,
                "cinq euros ne doivent pas acheter deux mois")

        print("\n9. un paiement pour un abonnement INCONNU ne fabrique rien")
        n = cles(con)
        r = boutique.rappel(con, ENTETES, evenement(
            "PAYMENT.SALE.COMPLETED", "EV-P3",
            {"id": "S-3", "billing_agreement_id": "I-JAMAIS-VU"}), SECRET_LIC)
        verifie("aucune cle n'est creee", cles(con) == n, str(r)[:60])
        verifie("et on ne fait pas echouer PayPal pour autant",
                r.get("ok") is True,
                "sinon il reessaierait sans fin un rappel qui n'aboutira jamais")

        print("\n10. RESILIER ne revoque PAS la cle du mois deja paye")
        r = boutique.rappel(con, ENTETES, evenement(
            "BILLING.SUBSCRIPTION.CANCELLED", "EV-C1",
            {"id": "I-DIRECT"}), SECRET_LIC)
        etat = con.execute("SELECT etat FROM licences WHERE cle=?",
                           (cle,)).fetchone()[0]
        verifie("la cle reste active", etat == "active", etat)
        verifie("et l'echeance est intacte", expire_de(con, cle) == e2,
                "elle s'eteindra d'elle-meme, sans couper un mois paye")

        print("\n11. la commande se relit, pour la page de retour")
        c = boutique.commande(con, "I-DIRECT")
        verifie("elle est prete", c.get("prete") is True)
        verifie("et porte la bonne cle", c.get("cle") == cle)
        verifie("une commande inconnue est dite inconnue",
                boutique.commande(con, "I-RIEN").get("ok") is False)

        print("\n12. une adresse de courriel invalide est refusee tout de suite")
        for mauvaise in ("", "pasdarobase", "x" * 250 + "@a.fr"):
            r = boutique.commence(con, mauvaise)
            verifie(f"refuse {mauvaise[:18] or '(vide)'}",
                    r.get("ok") is False, r.get("raison", ""))

        print("\n13. l'abonnement se cree et rend l'adresse de paiement")
        r = boutique.commence(con, "nouveau@exemple.fr")
        verifie("PayPal a rendu une adresse d'approbation",
                r.get("ok") and "approve" in (r.get("url") or ""), str(r)[:70])
        verifie("la commande est notee en attente",
                boutique.commande(con, r["abonnement"]).get("prete") is False,
                "aucune cle avant que PayPal ait encaisse")

        print("\n14. S'ABONNER DEPUIS L'APPLICATION, sans code a recopier")
        d = boutique.commence(con, "", depuis_app=True)
        verifie("aucune adresse n'est demandee", d.get("ok") is True,
                "PayPal en reclame deja une pour encaisser")
        verifie("un jeton de retrait est rendu", bool(d.get("retrait")))
        verifie("il est assez long pour ne pas se deviner",
                len(d.get("retrait", "")) >= 24, str(len(d.get("retrait", ""))))
        jeton = d["retrait"]

        print("\n15. avant paiement, l'application attend — sans rien recevoir")
        r = boutique.retrait(con, jeton)
        verifie("elle est dite pas prete", r.get("ok") and r.get("pret") is False)
        verifie("et AUCUNE cle ne fuit", "cle" not in r, str(r))

        print("\n16. apres le rappel signe, l'application prend la cle toute seule")
        n = cles(con)
        boutique.rappel(con, ENTETES, evenement(
            "BILLING.SUBSCRIPTION.ACTIVATED", "EV-APP",
            {"id": d["abonnement"],
             "subscriber": {"email_address": "depuis-app@exemple.fr"}}), SECRET_LIC)
        r = boutique.retrait(con, jeton)
        verifie("elle est prete", r.get("pret") is True)
        verifie("et porte une vraie cle", (r.get("cle") or "").startswith("DNAR-"),
                str(r.get("cle")))
        cle_app = r.get("cle")
        verifie("une seule cle a ete creee", cles(con) == n + 1)

        print("\n17. un jeton inconnu ou perime ne donne rien")
        verifie("inconnu : refuse",
                boutique.retrait(con, "jeton-invente").get("ok") is False)
        verifie("vide : refuse", boutique.retrait(con, "").get("ok") is False)
        con.execute("UPDATE commandes SET cree=? WHERE retrait=?",
                    (time.time() - boutique.RETRAIT_VALIDE - 10, jeton))
        con.commit()
        r = boutique.retrait(con, jeton)
        verifie("trop ancien : refuse", r.get("expire") is True, r.get("raison", ""))
        verifie("et la cle ne fuit plus par ce jeton", "cle" not in r)

        print("\n18. l'etat de l'abonnement remonte, pour l'ecrire en francais")
        a = boutique.abonnement_de(con, cle_app)
        verifie("on sait que cette cle vient d'un abonnement",
                a.get("abonnement") == "active", str(a)[:60])
        verifie("et une commande deja payee n'est jamais ecrasee",
                boutique.abonnement_de(con, cle).get("abonnement") == "active",
                "INSERT OR REPLACE l'aurait effacee")
        verifie("une cle sans abonnement ne pretend rien",
                boutique.abonnement_de(con, "DNAR-AAAAA-AAAAA-AAAAA-A") == {})

        print("\n19. LE WEBHOOK SE CREE TOUT SEUL, et pas deux fois")
        w = boutique.assure_webhook()
        verifie("il est cree", w.get("ok") and w.get("id"), str(w)[:70])
        verifie("a la bonne adresse",
                w.get("url") == "https://dnareader.test/boutique/paypal",
                str(w.get("url")))
        premier = w["id"]
        w2 = boutique.assure_webhook()
        verifie("un second lancement le RETROUVE au lieu d'en creer un autre",
                w2.get("deja") is True and w2.get("id") == premier,
                "sinon chaque paiement arriverait en double")
        verifie("il ne demande que les deux evenements utiles",
                boutique.EVENEMENTS == ["BILLING.SUBSCRIPTION.ACTIVATED",
                                        "PAYMENT.SALE.COMPLETED"])

        print("\n20. l'outil ecrit la valeur SANS abimer le reste du fichier")
        import ouvrir_boutique
        f = TMP / "secrets-de-banc.env"
        f.write_text("DNAREADER_SECRET=garde-moi\nPAYPAL_ID=abc\n"
                     "PAYPAL_WEBHOOK_ID=\nSMTP_HOTE=\n", encoding="utf-8")
        ouvrir_boutique.ecris(f, "PAYPAL_WEBHOOK_ID", premier)
        apres = f.read_text(encoding="utf-8")
        verifie("la valeur est en place", f"PAYPAL_WEBHOOK_ID={premier}" in apres)
        verifie("le reste est intact", "DNAREADER_SECRET=garde-moi" in apres
                and "PAYPAL_ID=abc" in apres)
        verifie("et la ligne n'est pas dupliquee",
                apres.count("PAYPAL_WEBHOOK_ID=") == 1,
                "deux lignes du meme nom, et on ne peut plus deviner l'effet")

        print("\n21. le plan memorise porte l'ENVIRONNEMENT dans son nom")
        import chemins
        memos = sorted(p.name for p in chemins.DONNEES.glob("paypal-plan*.json"))
        verifie("le fichier nomme l'environnement",
                memos == [f"paypal-plan-{boutique.ENV}.json"], str(memos))

    finally:
        srv.shutdown()
        con.close()
        shutil.rmtree(TMP, ignore_errors=True)

    print()
    if echecs:
        print(f"{len(echecs)} ECHEC(S) : " + " · ".join(echecs))
        return 1
    print("OK : un faux rappel ne delivre rien, un rappel rejoue non plus,")
    print("     et un renouvellement prolonge la meme cle au lieu d'en creer une")
    return 0


if __name__ == "__main__":
    sys.exit(main())
