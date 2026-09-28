# -*- coding: utf-8 -*-
import email
import email.utils
import imaplib
import json
import os
import re
import sqlite3
import ssl
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

import licences

IMAP_HOTE = os.environ.get("IMAP_HOTE", "").strip()
IMAP_PORT = int(os.environ.get("IMAP_PORT", "993"))
IMAP_UTILISATEUR = os.environ.get("IMAP_UTILISATEUR", "").strip()
IMAP_MOTDEPASSE = os.environ.get("IMAP_MOTDEPASSE", "")
IMAP_DOSSIER = os.environ.get("IMAP_DOSSIER", "INBOX").strip()

DISCORD_JETON = os.environ.get("DISCORD_JETON", "").strip()
DISCORD_SERVEUR = os.environ.get("DISCORD_SERVEUR", "").strip()

PREFIXE = os.environ.get("DNAREADER_PREFIXE", "DNAR").strip().upper()
PRIX = float(os.environ.get("DNAREADER_PRIX", "5.00"))
PAYPAL_ME = os.environ.get("PAYPAL_ME", "").strip()
TOLERANCE = float(os.environ.get("DNAREADER_TOLERANCE", "0.50"))
JOURS = 31
MACHINES = int(os.environ.get("DNAREADER_MACHINES", "2"))

DOMAINES = ("paypal.com", "paypal.fr", "paypal.co.uk", "paypal.de", "paypal.es")
ENTRE_DEUX_LECTURES = int(os.environ.get("DNAREADER_IMAP_SECONDES", "60"))
DELAI = 20


def configuree() -> bool:
    return bool(IMAP_HOTE and IMAP_UTILISATEUR and IMAP_MOTDEPASSE
                and DISCORD_JETON and DISCORD_SERVEUR)


def pourquoi_pas() -> str:
    manque = [n for n, v in (("IMAP_HOTE", IMAP_HOTE),
                             ("IMAP_UTILISATEUR", IMAP_UTILISATEUR),
                             ("IMAP_MOTDEPASSE", IMAP_MOTDEPASSE),
                             ("DISCORD_JETON", DISCORD_JETON),
                             ("DISCORD_SERVEUR", DISCORD_SERVEUR)) if not v]
    return "il manque " + ", ".join(manque) if manque else ""


def prepare(con: sqlite3.Connection):
    con.execute("""CREATE TABLE IF NOT EXISTS livraisons(
                     virement TEXT PRIMARY KEY,
                     pseudo      TEXT NOT NULL,
                     montant     REAL,
                     cle         TEXT,
                     etat        TEXT NOT NULL,
                     detail      TEXT,
                     quand       REAL NOT NULL)""")
    con.commit()


def _deja_livre(con, virement: str) -> bool:
    if not virement:
        return False
    try:
        con.execute("INSERT INTO livraisons(virement, pseudo, montant, cle,"
                    " etat, detail, quand) VALUES(?,?,?,?,?,?,?)",
                    (virement, "", None, None, "en cours", "", time.time()))
        con.commit()
        return False
    except sqlite3.IntegrityError:
        return True


def _note(con, virement, **champs):
    if not virement:
        return
    bouts = ", ".join(f"{k}=?" for k in champs)
    con.execute(f"UPDATE livraisons SET {bouts} WHERE virement=?",
                (*champs.values(), virement))
    con.commit()


def vient_de_paypal(msg) -> tuple:
    de = email.utils.parseaddr(msg.get("From", ""))[1].lower()
    domaine = de.rsplit("@", 1)[-1] if "@" in de else ""
    if not any(domaine == d or domaine.endswith("." + d) for d in DOMAINES):
        return False, f"expediteur hors PayPal : {de or '(vide)'}"

    auth = " ".join(msg.get_all("Authentication-Results") or []).lower()
    if not auth:
        return False, ("aucun en-tete Authentication-Results : "
                       "le serveur de courriel ne verifie pas DKIM")
    if "dkim=pass" not in auth:
        return False, "DKIM n'a pas valide ce courriel"
    if not re.search(r"header\.(?:d|i)=[^\s;]*paypal\.(?:com|fr|co\.uk|de|es)",
                     auth):
        return False, "DKIM valide, mais pas pour un domaine PayPal"
    return True, ""


RECU = (
    "vous avez recu de l argent", "vous avez recu un paiement",
    "you have received money", "you ve got money", "you received a payment",
    "has sent you", "vous a envoye", "vous a envoye de l argent",
    "has sent you money", "recibiste dinero", "has recibido un pago",
    "sie haben geld erhalten", "zahlungseingang",
)
PAS_UN_ENCAISSEMENT = (
    (("demande", "reclame", "requests money", "requested money",
      "vous demande", "facture", "invoice"),
     "c'est une DEMANDE de paiement, pas un encaissement"),
    (("recu de votre paiement", "receipt for your payment",
      "vous avez envoye", "you sent"),
     "c'est un paiement SORTANT"),
    (("commande", "expedition", "order", "shipped", "livraison"),
     "c'est un suivi de commande"),
)


def _sans_accent(t: str) -> str:
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", t or "")
                   if unicodedata.category(c) != "Mn")


def est_un_encaissement(sujet: str) -> tuple:
    plat = _sans_accent((sujet or "").lower())
    plat = "".join(c if c.isalnum() else " " for c in plat)
    plat = " ".join(plat.split())
    if any(motif in plat for motif in RECU):
        return True, ""
    for motifs, raison in PAS_UN_ENCAISSEMENT:
        if any(m in plat for m in motifs):
            return False, raison
    return False, "le sujet ne dit pas qu'on a recu de l'argent"


def _texte(msg) -> str:
    bouts = []
    for part in msg.walk() if msg.is_multipart() else [msg]:
        if part.get_content_type() not in ("text/plain", "text/html"):
            continue
        try:
            brut = part.get_payload(decode=True) or b""
            t = brut.decode(part.get_content_charset() or "utf-8", "replace")
        except Exception:
            continue
        if part.get_content_type() == "text/html":
            t = re.sub(r"<[^>]+>", " ", t)
        bouts.append(t)
    return re.sub(r"[ \t\xa0]+", " ", " ".join(bouts))


def lis_le_paiement(msg) -> dict:
    corps = _texte(msg)
    sujet = str(email.header.make_header(email.header.decode_header(
        msg.get("Subject", "")))) if msg.get("Subject") else ""
    tout = sujet + " " + corps

    m = re.search(rf"\b{PREFIXE}[-_ ]?([A-Za-z0-9._]{{2,32}})", tout, re.I)
    pseudo = m.group(1).strip(" .") if m else ""

    montants = [float(x.replace(",", ".")) for x in
                re.findall(r"(\d{1,4}[.,]\d{2})\s*(?:EUR|€|\bEUR\b)", tout, re.I)]
    montants += [float(x.replace(",", ".")) for x in
                 re.findall(r"(?:EUR|€)\s*(\d{1,4}[.,]\d{2})", tout, re.I)]

    trans = ""
    mt = re.search(r"\b([A-Z0-9]{17})\b", tout)
    if mt:
        trans = mt.group(1)
    else:
        trans = (msg.get("Message-ID") or "").strip("<> ")

    return {"pseudo": pseudo, "montants": montants, "virement": trans,
            "sujet": sujet}


def _discord(route: str, corps=None, methode="GET") -> dict:
    data = json.dumps(corps).encode() if corps is not None else None
    req = urllib.request.Request(
        "https://discord.com/api/v10" + route, data,
        {"Authorization": f"Bot {DISCORD_JETON}",
         "Content-Type": "application/json",
         "User-Agent": "DNAreader (https://github.com/NanashiAngsnake, 1.0)"},
        method=methode)
    try:
        with urllib.request.urlopen(req, timeout=DELAI) as r:
            return json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        try:
            return {"_erreur": json.loads(e.read().decode()), "_code": e.code}
        except Exception:
            return {"_erreur": str(e), "_code": e.code}


def trouve_le_membre(pseudo: str) -> dict:
    r = _discord(f"/guilds/{DISCORD_SERVEUR}/members/search"
                 f"?query={urllib.parse.quote(pseudo)}&limit=10")
    if isinstance(r, dict) and "_erreur" in r:
        return {"ok": False, "raison": str(r["_erreur"])[:120]}
    voulu = pseudo.lower().lstrip("@")
    for m in r or []:
        u = m.get("user") or {}
        if (u.get("username") or "").lower() == voulu \
                or (m.get("nick") or "").lower() == voulu \
                or (u.get("global_name") or "").lower() == voulu:
            return {"ok": True, "id": u.get("id"), "tag": u.get("username")}
    return {"ok": False, "raison": f"aucun membre nomme « {pseudo} »"}


def envoie_la_cle(pseudo: str, cle: str) -> dict:
    m = trouve_le_membre(pseudo)
    if not m.get("ok"):
        return m
    salon = _discord("/users/@me/channels", {"recipient_id": m["id"]}, "POST")
    if "_erreur" in salon:
        return {"ok": False, "raison": f"DM impossible : {salon['_erreur']}"}
    texte = (
        f"**Merci !** Voici ta cle DNAreader :\n\n"
        f"```\n{cle}\n```\n"
        f"Colle-la dans l'application : **Reglages > Cle d'acces**.\n"
        f"Elle vaut pour {MACHINES} machines et fonctionne quatorze jours sans "
        f"reseau.\n\n"
        f"Ton acces court **{JOURS} jours**. Pour le prolonger, renvoie le "
        f"meme montant avec la meme note : c'est la MEME cle qui est "
        f"repoussee, tu n'auras jamais a en ressaisir une autre.\n\n"
        f"Telecharger : https://github.com/NanashiAngsnake/dnareader-releases/releases/latest")
    r = _discord(f"/channels/{salon['id']}/messages", {"content": texte}, "POST")
    if "_erreur" in r:
        return {"ok": False, "raison": f"envoi refuse : {r['_erreur']}"}
    return {"ok": True, "tag": m.get("tag")}


def livre(con, info: dict) -> dict:
    pseudo = info["pseudo"]
    licences.prepare(con)
    r = con.execute("SELECT cle FROM licences WHERE note LIKE ? AND etat='active'"
                    " ORDER BY cree DESC LIMIT 1",
                    (f"discord {pseudo.lower()}%",)).fetchone()
    if r:
        p = licences.prolonge(con, r[0], JOURS)
        return {"ok": True, "cle": r[0], "prolongee": True,
                "jours_restants": p.get("jours_restants")}
    faite = licences.cree(con, plan="complet", machines=MACHINES,
                          note=f"discord {pseudo.lower()}", jours=JOURS)
    return {"ok": True, "cle": faite["cle"], "prolongee": False}


def traite_un_message(con, msg) -> dict:
    bon, pourquoi = vient_de_paypal(msg)
    if not bon:
        return {"ignore": pourquoi}

    info = lis_le_paiement(msg)
    encaisse, pourquoi_pas_lui = est_un_encaissement(info["sujet"])
    if not encaisse:
        return {"ignore": pourquoi_pas_lui}
    if not info["pseudo"]:
        return {"ignore": f"aucune note « {PREFIXE}-pseudo »"}
    if _deja_livre(con, info["virement"]):
        return {"ignore": "paiement deja traite"}

    assez = [m for m in info["montants"] if m >= PRIX - TOLERANCE]
    if not assez:
        _note(con, info["virement"], pseudo=info["pseudo"], etat="montant",
              detail=f"montants vus : {info['montants']}")
        return {"refuse": f"montant insuffisant : {info['montants']} pour {PRIX}"}

    fait = livre(con, info)
    envoi = envoie_la_cle(info["pseudo"], fait["cle"])
    _note(con, info["virement"], pseudo=info["pseudo"],
          montant=max(assez), cle=fait["cle"],
          etat="livree" if envoi.get("ok") else "a livrer",
          detail="" if envoi.get("ok") else envoi.get("raison", ""))
    if not envoi.get("ok"):
        return {"cle": fait["cle"], "pseudo": info["pseudo"],
                "a_livrer": envoi.get("raison")}
    return {"livree": fait["cle"], "pseudo": info["pseudo"],
            "prolongee": fait["prolongee"]}


def tourne_une_fois(con) -> dict:
    if not configuree():
        return {"ok": False, "raison": pourquoi_pas()}
    prepare(con)
    resultats = []
    try:
        ctx = ssl.create_default_context()
        with imaplib.IMAP4_SSL(IMAP_HOTE, IMAP_PORT, ssl_context=ctx) as boite:
            boite.login(IMAP_UTILISATEUR, IMAP_MOTDEPASSE)
            boite.select(IMAP_DOSSIER)
            typ, donnees = boite.search(None, "UNSEEN")
            if typ != "OK":
                return {"ok": False, "raison": "recherche refusee"}
            for num in (donnees[0].split() if donnees and donnees[0] else []):
                typ, bout = boite.fetch(num, "(RFC822)")
                if typ != "OK" or not bout or not bout[0]:
                    continue
                msg = email.message_from_bytes(bout[0][1])
                try:
                    resultats.append(traite_un_message(con, msg))
                except Exception as e:
                    resultats.append({"erreur": str(e)})
    except Exception as e:
        return {"ok": False, "raison": f"boite injoignable : {e}"}
    return {"ok": True, "vus": len(resultats), "resultats": resultats}


def au_demarrage(fabrique_connexion, verrou):
    if not configuree():
        return

    def boucle():
        while True:
            try:
                with verrou:
                    r = tourne_une_fois(fabrique_connexion())
                for x in (r.get("resultats") or []):
                    if any(k in x for k in ("livree", "a_livrer", "refuse")):
                        print(f"[livraison] {x}")
                if not r.get("ok"):
                    print(f"[livraison] {r.get('raison')}")
            except Exception as e:
                print(f"[livraison] tour rate : {e}")
            time.sleep(ENTRE_DEUX_LECTURES)

    threading.Thread(target=boucle, daemon=True).start()
