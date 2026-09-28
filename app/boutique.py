# -*- coding: utf-8 -*-
import base64
import json
import os
import smtplib
import secrets
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request
from email.message import EmailMessage

import licences

ENV = os.environ.get("PAYPAL_ENV", "sandbox").strip().lower()
API = ("https://api-m.paypal.com" if ENV == "live"
       else "https://api-m.sandbox.paypal.com")
ID = os.environ.get("PAYPAL_ID", "").strip()
SECRET = os.environ.get("PAYPAL_SECRET", "").strip()
WEBHOOK_ID = os.environ.get("PAYPAL_WEBHOOK_ID", "").strip()

PRIX = os.environ.get("DNAREADER_PRIX", "5.00").strip()
DEVISE = os.environ.get("DNAREADER_DEVISE", "EUR").strip()
PUBLIQUE = os.environ.get("DNAREADER_PUBLIQUE", "").rstrip("/")

JOURS_PAR_MOIS = 31
MACHINES = int(os.environ.get("DNAREADER_MACHINES", "2"))
DELAI = 20

SMTP_HOTE = os.environ.get("SMTP_HOTE", "").strip()
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_UTILISATEUR = os.environ.get("SMTP_UTILISATEUR", "").strip()
SMTP_MOTDEPASSE = os.environ.get("SMTP_MOTDEPASSE", "")
SMTP_DE = os.environ.get("SMTP_DE", "").strip() or SMTP_UTILISATEUR


def configuree() -> bool:
    return bool(ID and SECRET and WEBHOOK_ID and PUBLIQUE)


def pourquoi_pas() -> str:
    manque = [n for n, v in (("PAYPAL_ID", ID), ("PAYPAL_SECRET", SECRET),
                             ("PAYPAL_WEBHOOK_ID", WEBHOOK_ID),
                             ("DNAREADER_PUBLIQUE", PUBLIQUE)) if not v]
    return "il manque " + ", ".join(manque) if manque else ""


def prepare(con: sqlite3.Connection):
    con.execute("""CREATE TABLE IF NOT EXISTS commandes(
                     abonnement  TEXT PRIMARY KEY,
                     cle         TEXT,
                     courriel    TEXT NOT NULL,
                     etat        TEXT NOT NULL,
                     cree        REAL NOT NULL,
                     dernier     REAL,
                     paiements   INTEGER NOT NULL DEFAULT 0,
                     -- L'ACTIVATION A DEJA CREDITE LE PREMIER MOIS. PayPal
                     -- envoie ensuite un rappel de paiement pour cette meme
                     -- premiere echeance : sans ce drapeau, chaque nouvel
                     -- abonne recevrait deux mois pour un. On avait d'abord
                     -- compare des dates a soixante secondes pres — un
                     -- rappel retarde, et le compte etait faux.
                     premier_vu  INTEGER NOT NULL DEFAULT 0,
                     -- LE JETON DE RETRAIT, quand l'achat part de l'application.
                     -- Elle le garde, interroge avec, et pose la clé toute
                     -- seule : personne ne recopie un code reçu par courriel.
                     -- Il est tiré au hasard et ne vaut que pour cette
                     -- commande — le connaître ne donne accès à aucune autre.
                     retrait     TEXT)""")
    con.execute("CREATE INDEX IF NOT EXISTS i_retrait ON commandes(retrait)")
    con.execute("""CREATE TABLE IF NOT EXISTS evenements(
                     id     TEXT PRIMARY KEY,
                     genre  TEXT,
                     quand  REAL NOT NULL)""")
    con.commit()


def _deja_vu(con, id_evenement: str, genre: str) -> bool:
    if not id_evenement:
        return False
    try:
        con.execute("INSERT INTO evenements VALUES(?,?,?)",
                    (id_evenement, genre, time.time()))
        con.commit()
        return False
    except sqlite3.IntegrityError:
        return True


def _jeton() -> str:
    corps = urllib.parse.urlencode({"grant_type": "client_credentials"}).encode()
    auth = base64.b64encode(f"{ID}:{SECRET}".encode()).decode()
    req = urllib.request.Request(
        API + "/v1/oauth2/token", corps,
        {"Authorization": f"Basic {auth}",
         "Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=DELAI) as r:
        return json.loads(r.read().decode())["access_token"]


def _appelle(route: str, corps=None, methode="POST", jeton=None) -> dict:
    jeton = jeton or _jeton()
    data = json.dumps(corps).encode() if corps is not None else None
    req = urllib.request.Request(
        API + route, data,
        {"Authorization": f"Bearer {jeton}", "Content-Type": "application/json"},
        method=methode)
    try:
        with urllib.request.urlopen(req, timeout=DELAI) as r:
            brut = r.read().decode() or "{}"
            return json.loads(brut)
    except urllib.error.HTTPError as e:
        try:
            return {"_erreur": json.loads(e.read().decode()), "_code": e.code}
        except Exception:
            return {"_erreur": str(e), "_code": e.code}


_plan = {"id": ""}


def assure_plan() -> str:
    if _plan["id"]:
        return _plan["id"]
    import chemins
    memo = chemins.DONNEES / f"paypal-plan-{ENV}.json"
    try:
        _plan["id"] = json.loads(memo.read_text(encoding="utf-8"))["plan"]
        return _plan["id"]
    except Exception:
        pass

    produit = _appelle("/v1/catalogs/products", {
        "name": "DNAreader", "type": "DIGITAL",
        "description": "Lecteur de japonais pour jeux video"})
    if "_erreur" in produit:
        raise RuntimeError(f"produit refuse : {produit['_erreur']}")

    plan = _appelle("/v1/billing/plans", {
        "product_id": produit["id"],
        "name": f"DNAreader — {PRIX} {DEVISE} par mois",
        "billing_cycles": [{
            "frequency": {"interval_unit": "MONTH", "interval_count": 1},
            "tenure_type": "REGULAR", "sequence": 1,
            "total_cycles": 0,
            "pricing_scheme": {"fixed_price": {"value": PRIX,
                                               "currency_code": DEVISE}}}],
        "payment_preferences": {"auto_bill_outstanding": True,
                                "setup_fee_failure_action": "CANCEL",
                                "payment_failure_threshold": 2}})
    if "_erreur" in plan:
        raise RuntimeError(f"plan refuse : {plan['_erreur']}")
    _plan["id"] = plan["id"]
    try:
        memo.write_text(json.dumps({"plan": plan["id"], "produit": produit["id"]}),
                        encoding="utf-8")
    except Exception:
        pass
    return _plan["id"]


EVENEMENTS = ["BILLING.SUBSCRIPTION.ACTIVATED", "PAYMENT.SALE.COMPLETED"]


def assure_webhook() -> dict:
    if not (ID and SECRET):
        return {"ok": False, "raison": "il manque PAYPAL_ID et PAYPAL_SECRET"}
    if not PUBLIQUE:
        return {"ok": False, "raison": "il manque DNAREADER_PUBLIQUE"}
    url = f"{PUBLIQUE}/boutique/paypal"

    existants = _appelle("/v1/notifications/webhooks", methode="GET")
    if "_erreur" in existants:
        return {"ok": False, "raison": f"PayPal a refuse : {existants['_erreur']}"}
    for w in existants.get("webhooks") or []:
        if (w.get("url") or "").rstrip("/") == url.rstrip("/"):
            return {"ok": True, "id": w["id"], "deja": True, "url": url}

    cree = _appelle("/v1/notifications/webhooks", {
        "url": url,
        "event_types": [{"name": n} for n in EVENEMENTS]})
    if "_erreur" in cree:
        return {"ok": False, "raison": f"PayPal a refuse : {cree['_erreur']}"}
    return {"ok": True, "id": cree["id"], "deja": False, "url": url}


def commence(con, courriel: str = "", depuis_app=False) -> dict:
    courriel = (courriel or "").strip()
    if not depuis_app and ("@" not in courriel or len(courriel) > 200):
        return {"ok": False, "raison": "adresse de courriel invalide"}
    if not configuree():
        return {"ok": False, "raison": "boutique non configuree : " + pourquoi_pas()}

    prepare(con)
    demande = {
        "plan_id": assure_plan(),
        "application_context": {
            "brand_name": "DNAreader",
            "user_action": "SUBSCRIBE_NOW",
            "return_url": f"{PUBLIQUE}/boutique/merci",
            "cancel_url": f"{PUBLIQUE}/boutique"}}
    if courriel:
        demande["subscriber"] = {"email_address": courriel}
    s = _appelle("/v1/billing/subscriptions", demande)
    if "_erreur" in s:
        return {"ok": False, "raison": f"PayPal a refuse : {s['_erreur']}"}

    jeton = secrets.token_urlsafe(24) if depuis_app else None
    try:
        con.execute("INSERT INTO commandes(abonnement, cle, courriel, etat,"
                    " cree, dernier, paiements, premier_vu, retrait)"
                    " VALUES(?,?,?,?,?,?,?,?,?)",
                    (s["id"], None, courriel, "en attente", time.time(),
                     None, 0, 0, jeton))
        con.commit()
    except sqlite3.IntegrityError:
        r = con.execute("SELECT retrait FROM commandes WHERE abonnement=?",
                        (s["id"],)).fetchone()
        jeton = (r[0] if r else None) or jeton
    lien = next((l["href"] for l in s.get("links", [])
                 if l.get("rel") == "approve"), "")
    r = {"ok": True, "abonnement": s["id"], "url": lien}
    if jeton:
        r["retrait"] = jeton
    return r


RETRAIT_VALIDE = 6 * 3600


def retrait(con, jeton: str) -> dict:
    prepare(con)
    jeton = (jeton or "").strip()
    if not jeton:
        return {"ok": False, "raison": "aucun jeton"}
    r = con.execute("SELECT abonnement, cle, cree, etat FROM commandes"
                    " WHERE retrait=?", (jeton,)).fetchone()
    if not r:
        return {"ok": False, "raison": "jeton inconnu"}
    if time.time() - r[2] > RETRAIT_VALIDE:
        return {"ok": False, "expire": True,
                "raison": "demande trop ancienne : recommence l'abonnement"}
    if not r[1]:
        return {"ok": True, "pret": False, "etat": r[3]}
    return {"ok": True, "pret": True, "cle": r[1], "abonnement": r[0]}


def verifie_signature(entetes: dict, corps: str) -> bool:
    def h(nom):
        return entetes.get(nom) or entetes.get(nom.lower()) or ""
    demande = {
        "auth_algo": h("PAYPAL-AUTH-ALGO"),
        "cert_url": h("PAYPAL-CERT-URL"),
        "transmission_id": h("PAYPAL-TRANSMISSION-ID"),
        "transmission_sig": h("PAYPAL-TRANSMISSION-SIG"),
        "transmission_time": h("PAYPAL-TRANSMISSION-TIME"),
        "webhook_id": WEBHOOK_ID,
    }
    if not all(demande.values()):
        return False
    try:
        demande["webhook_event"] = json.loads(corps)
    except Exception:
        return False
    r = _appelle("/v1/notifications/verify-webhook-signature", demande)
    return r.get("verification_status") == "SUCCESS"


def rappel(con, entetes: dict, corps: str, secret_licence: str,
           deja_verifie=False) -> dict:
    if not configuree():
        return {"ok": False, "raison": "boutique non configuree"}
    if not deja_verifie and not verifie_signature(entetes, corps):
        return {"ok": False, "raison": "signature refusee"}

    e = json.loads(corps)
    genre = e.get("event_type", "")
    prepare(con)
    licences.prepare(con)

    if _deja_vu(con, e.get("id", ""), genre):
        return {"ok": True, "deja_traite": True, "genre": genre}

    ressource = e.get("resource") or {}

    if genre == "BILLING.SUBSCRIPTION.ACTIVATED":
        return _active(con, ressource, secret_licence)
    if genre in ("PAYMENT.SALE.COMPLETED", "PAYMENT.CAPTURE.COMPLETED"):
        return _paiement(con, ressource)
    return {"ok": True, "ignore": genre}


def _active(con, ressource: dict, secret_licence: str) -> dict:
    abonnement = ressource.get("id") or ""
    courriel = ((ressource.get("subscriber") or {}).get("email_address")
                or "").strip()
    r = con.execute("SELECT cle, courriel FROM commandes WHERE abonnement=?",
                    (abonnement,)).fetchone()
    if r and r[0]:
        return {"ok": True, "deja_delivree": True, "cle": r[0]}
    courriel = courriel or (r[1] if r else "")

    faite = licences.cree(con, plan="complet", machines=MACHINES,
                          note=f"paypal {abonnement} · {courriel}",
                          jours=JOURS_PAR_MOIS)
    modifiees = con.execute(
        "UPDATE commandes SET cle=?, courriel=?, etat='active', dernier=?,"
        " paiements=1 WHERE abonnement=?",
        (faite["cle"], courriel, time.time(), abonnement)).rowcount
    if not modifiees:
        con.execute("INSERT INTO commandes(abonnement, cle, courriel, etat,"
                    " cree, dernier, paiements, premier_vu, retrait)"
                    " VALUES(?,?,?,?,?,?,?,?,?)",
                    (abonnement, faite["cle"], courriel, "active",
                     time.time(), time.time(), 1, 0, None))
    con.commit()
    envoie_la_cle(courriel, faite["cle"])
    return {"ok": True, "cle": faite["cle"], "courriel": courriel}


def _paiement(con, ressource: dict) -> dict:
    abonnement = (ressource.get("billing_agreement_id")
                  or ressource.get("id") or "")
    r = con.execute("SELECT cle, premier_vu FROM commandes WHERE abonnement=?",
                    (abonnement,)).fetchone()
    if not r or not r[0]:
        return {"ok": True, "en_attente_activation": abonnement}
    if not r[1]:
        con.execute("UPDATE commandes SET premier_vu=1 WHERE abonnement=?",
                    (abonnement,))
        con.commit()
        return {"ok": True, "premier_paiement_deja_compte": True}

    p = licences.prolonge(con, r[0], JOURS_PAR_MOIS)
    con.execute("UPDATE commandes SET dernier=?, paiements=paiements+1,"
                " etat='active' WHERE abonnement=?",
                (time.time(), abonnement))
    con.commit()
    return {"ok": True, "cle": r[0], "prolongee": p.get("jours_restants")}


def envoie_la_cle(courriel: str, cle: str) -> dict:
    if not (SMTP_HOTE and SMTP_DE and courriel):
        return {"ok": False, "raison": "aucun serveur d'envoi configure"}
    m = EmailMessage()
    m["Subject"] = "Ta cle DNAreader"
    m["From"] = SMTP_DE
    m["To"] = courriel
    m.set_content(
        f"""Merci !

Voici ta cle d'acces DNAreader :

    {cle}

Colle-la dans l'application : Reglages > Cle d'acces.
Elle vaut pour {MACHINES} machines et fonctionne quatorze jours sans reseau.

L'abonnement se renouvelle tout seul chaque mois, et la meme cle est
prolongee : tu n'auras jamais a en ressaisir une autre. Si tu resilies, la
cle continue jusqu'a la fin du mois deja paye, puis s'arrete.

Telecharger la derniere version :
https://github.com/NanashiAngsnake/dnareader-releases/releases/latest
""")
    try:
        with smtplib.SMTP(SMTP_HOTE, SMTP_PORT, timeout=DELAI) as s:
            s.starttls()
            if SMTP_UTILISATEUR:
                s.login(SMTP_UTILISATEUR, SMTP_MOTDEPASSE)
            s.send_message(m)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "raison": str(e)}


def abonnement_de(con, cle: str) -> dict:
    try:
        prepare(con)
        r = con.execute("SELECT etat, paiements, dernier, courriel FROM commandes"
                        " WHERE cle=?", (cle or "",)).fetchone()
    except Exception:
        return {}
    if not r:
        return {}
    return {"abonnement": r[0], "paiements": r[1], "dernier": r[2],
            "courriel": r[3]}


def commande(con, abonnement: str) -> dict:
    prepare(con)
    r = con.execute("SELECT cle, courriel, etat, paiements FROM commandes"
                    " WHERE abonnement=?", (abonnement or "",)).fetchone()
    if not r:
        return {"ok": False, "raison": "commande inconnue"}
    return {"ok": True, "cle": r[0] or "", "courriel": r[1], "etat": r[2],
            "paiements": r[3], "prete": bool(r[0])}
