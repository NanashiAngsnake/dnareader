# -*- coding: utf-8 -*-
import argparse
import hashlib
import json
import os
import secrets
import sqlite3
import threading
import time
from pathlib import Path

import hmac
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, HTMLResponse
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel

import boutique
import chemins
import contributions
import licences
import livraison
import rapports
import recolte_serveur
DB = chemins.DB_SYNC
_lock = threading.Lock()
TOURS_SERVEUR = 50_000

app = FastAPI(title="DNAreader — synchronisation")

DEPOT_PUBLIC = "https://github.com/NanashiAngsnake/dnareader-releases"


_connexion = None


def _con():
    global _connexion
    if _connexion is not None:
        return _connexion
    c = sqlite3.connect(DB, check_same_thread=False, timeout=30)
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA busy_timeout=30000")
    c.execute("PRAGMA synchronous=NORMAL")
    c.execute("""CREATE TABLE IF NOT EXISTS comptes(
                   identifiant TEXT PRIMARY KEY,
                   empreinte   TEXT NOT NULL,
                   sel         TEXT NOT NULL,
                   cree        REAL NOT NULL)""")
    c.execute("""CREATE TABLE IF NOT EXISTS donnees(
                   identifiant TEXT PRIMARY KEY,
                   paquet      TEXT NOT NULL,
                   maj         REAL NOT NULL)""")
    c.execute("""CREATE TABLE IF NOT EXISTS corrections(
                   id          INTEGER PRIMARY KEY,
                   jeu         TEXT NOT NULL,
                   faux        TEXT NOT NULL,
                   juste       TEXT NOT NULL,
                   contexte    TEXT,
                   seconde     REAL,
                   cree        REAL NOT NULL,
                   UNIQUE(jeu, faux, juste))""")
    c.execute("""CREATE TABLE IF NOT EXISTS voix(
                   correction  INTEGER NOT NULL,
                   compte      TEXT NOT NULL,
                   sens        INTEGER NOT NULL,
                   quand       REAL NOT NULL,
                   UNIQUE(correction, compte))""")
    c.execute("""CREATE TABLE IF NOT EXISTS jetons(
                   jeton       TEXT PRIMARY KEY,
                   identifiant TEXT NOT NULL,
                   cree        REAL NOT NULL)""")
    c.commit()
    _connexion = c
    return c


def _empreinte(preuve: str, sel: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", preuve.encode(), sel.encode(),
                               TOURS_SERVEUR).hex()


class Identite(BaseModel):
    identifiant: str
    preuve: str


class Jeton(BaseModel):
    jeton: str


class Envoi(BaseModel):
    jeton: str
    paquet: dict


def _nouveau_jeton(c, identifiant: str) -> str:
    j = secrets.token_urlsafe(32)
    c.execute("INSERT INTO jetons VALUES(?,?,?)", (j, identifiant, time.time()))
    c.commit()
    return j


def _qui(c, jeton: str):
    r = c.execute("SELECT identifiant FROM jetons WHERE jeton=?", (jeton,)).fetchone()
    return r[0] if r else None


@app.post("/inscription")
def inscription(i: Identite):
    ident = (i.identifiant or "").strip().lower()
    if len(ident) < 3 or len(i.preuve or "") < 16:
        return {"ok": False, "error": "identifiant ou mot de passe trop court"}
    with _lock:
        c = _con()
        if c.execute("SELECT 1 FROM comptes WHERE identifiant=?", (ident,)).fetchone():
            return {"ok": False, "error": "cet identifiant est déjà pris"}
        sel = secrets.token_hex(16)
        c.execute("INSERT INTO comptes VALUES(?,?,?,?)",
                  (ident, _empreinte(i.preuve, sel), sel, time.time()))
        c.commit()
        return {"ok": True, "jeton": _nouveau_jeton(c, ident)}


@app.post("/connexion")
def connexion(i: Identite):
    ident = (i.identifiant or "").strip().lower()
    with _lock:
        c = _con()
        r = c.execute("SELECT empreinte, sel FROM comptes WHERE identifiant=?",
                      (ident,)).fetchone()
        if not r or not secrets.compare_digest(_empreinte(i.preuve, r[1]), r[0]):
            return {"ok": False, "error": "identifiant ou mot de passe incorrect"}
        return {"ok": True, "jeton": _nouveau_jeton(c, ident)}


@app.post("/tirer")
def tirer(j: Jeton):
    with _lock:
        c = _con()
        ident = _qui(c, j.jeton)
        if not ident:
            return {"ok": False, "error": "session expirée : reconnecte-toi"}
        r = c.execute("SELECT paquet, maj FROM donnees WHERE identifiant=?",
                      (ident,)).fetchone()
        if not r:
            return {"ok": True, "paquet": None}
        return {"ok": True, "paquet": json.loads(r[0]), "maj": r[1]}


@app.post("/pousser")
def pousser(e: Envoi):
    with _lock:
        c = _con()
        ident = _qui(c, e.jeton)
        if not ident:
            return {"ok": False, "error": "session expirée : reconnecte-toi"}
        c.execute("INSERT INTO donnees VALUES(?,?,?) "
                  "ON CONFLICT(identifiant) DO UPDATE SET paquet=?, maj=?",
                  (ident, json.dumps(e.paquet), time.time(),
                   json.dumps(e.paquet), time.time()))
        c.commit()
        return {"ok": True}


ACCORDS_REQUIS = 2
CONTESTATIONS_MAX = 2


class Correction(BaseModel):
    jeton: str
    jeu: str
    faux: str
    juste: str
    contexte: str = ""
    seconde: float = 0.0


def _japonais(t: str) -> bool:
    for c in t or "":
        o = ord(c)
        if 0x3040 <= o <= 0x30FF or 0x4E00 <= o <= 0x9FFF or 0xFF66 <= o <= 0xFF9D:
            return True
    return False


def _etat_correction(c, cid: int) -> dict:
    pour = c.execute("SELECT COUNT(*) FROM voix WHERE correction=? AND sens>0",
                     (cid,)).fetchone()[0]
    contre = c.execute("SELECT COUNT(*) FROM voix WHERE correction=? AND sens<0",
                       (cid,)).fetchone()[0]
    return {"pour": pour, "contre": contre,
            "confirmee": pour >= ACCORDS_REQUIS and contre < CONTESTATIONS_MAX}


@app.post("/correction")
def correction_propose(x: Correction):
    faux, juste = (x.faux or "").strip(), (x.juste or "").strip()
    jeu = (x.jeu or "").strip()
    if not jeu or not faux or not juste:
        return {"ok": False, "error": "jeu, texte lu et correction sont requis"}
    if faux == juste:
        return {"ok": False, "error": "la correction est identique a la lecture"}
    if len(faux) > 200 or len(juste) > 200:
        return {"ok": False, "error": "trop long pour une ligne de dialogue"}
    if not _japonais(juste):
        return {"ok": False, "error": "la correction ne contient aucun japonais"}

    with _lock:
        c = _con()
        ident = _qui(c, x.jeton)
        if not ident:
            return {"ok": False, "error": "session expiree : reconnecte-toi"}
        dernier = c.execute(
            "SELECT MAX(quand) FROM voix WHERE compte=?", (ident,)).fetchone()[0]
        if dernier and time.time() - dernier < ANTI_INONDATION:
            return {"ok": False, "error": "trop de propositions coup sur coup"}

        c.execute("INSERT OR IGNORE INTO corrections(jeu, faux, juste, contexte, "
                  "seconde, cree) VALUES(?,?,?,?,?,?)",
                  (jeu, faux, juste, (x.contexte or "")[:300], x.seconde, time.time()))
        cid = c.execute("SELECT id FROM corrections WHERE jeu=? AND faux=? AND juste=?",
                        (jeu, faux, juste)).fetchone()[0]
        c.execute("INSERT OR REPLACE INTO voix VALUES(?,?,?,?)",
                  (cid, ident, 1, time.time()))
        c.commit()
        e = _etat_correction(c, cid)
        return {"ok": True, "id": cid, **e,
                "manque": max(0, ACCORDS_REQUIS - e["pour"])}


@app.post("/correction/contester")
def correction_conteste(x: Correction):
    with _lock:
        c = _con()
        ident = _qui(c, x.jeton)
        if not ident:
            return {"ok": False, "error": "session expiree : reconnecte-toi"}
        r = c.execute("SELECT id FROM corrections WHERE jeu=? AND faux=? AND juste=?",
                      ((x.jeu or "").strip(), (x.faux or "").strip(),
                       (x.juste or "").strip())).fetchone()
        if not r:
            return {"ok": False, "error": "correction inconnue"}
        c.execute("INSERT OR REPLACE INTO voix VALUES(?,?,?,?)",
                  (r[0], ident, -1, time.time()))
        c.commit()
        return {"ok": True, **_etat_correction(c, r[0])}


@app.get("/corrections")
def corrections_du_jeu(jeu: str, attente: str = ""):
    veut_attente = attente in ("1", "true", "oui")
    with _lock:
        c = _con()
        lignes = c.execute(
            "SELECT id, faux, juste, contexte, seconde, cree FROM corrections "
            "WHERE jeu=? ORDER BY cree DESC LIMIT 2000", (jeu,)).fetchall()
        out = []
        for cid, faux, juste, ctx, sec, cree in lignes:
            e = _etat_correction(c, cid)
            if e["confirmee"] == veut_attente:
                continue
            out.append({"faux": faux, "juste": juste, "contexte": ctx,
                        "seconde": sec, "quand": cree, **e})
        return {"ok": True, "jeu": jeu, "corrections": out,
                "accords_requis": ACCORDS_REQUIS}


ADMIN = os.environ.get("DNAREADER_ADMIN", "")
ANTI_INONDATION = float(os.environ.get("DNAREADER_ANTI_INONDATION", "2.0"))
SECRET = os.environ.get("DNAREADER_SECRET", "")


class DemandeCle(BaseModel):
    cle: str = ""
    machine: str = ""
    jeton: str = ""


class DemandeAdmin(BaseModel):
    admin: str = ""
    cle: str = ""
    plan: str = "complet"
    machines: int = 2
    note: str = ""
    jours: int | None = None
    etat: str = ""
    compte: str = ""


def _admin_ok(jeton: str) -> bool:
    return bool(ADMIN) and hmac.compare_digest(jeton or "", ADMIN)


@app.post("/licence/verifier")
def licence_verifier(d: DemandeCle):
    if not SECRET:
        return {"ok": False, "raison": "serveur mal configure (DNAREADER_SECRET)"}
    with _lock:
        c = _con()
        licences.prepare(c)
        compte = _qui(c, d.jeton) if d.jeton else ""
        r = licences.verifie(c, d.cle, d.machine, SECRET, compte or "")
        info = boutique.abonnement_de(c, licences.normalise(d.cle))
        if info:
            r = {**r, "abonnement": info.get("abonnement", ""),
                 "paiements": info.get("paiements", 0)}
        brut = licences._etat_brut(c, licences.normalise(d.cle))
        if brut:
            r["expire"] = brut[3]
        return r


@app.post("/essai")
def essai_verifier(d: DemandeCle):
    if not SECRET:
        return {"ok": False, "raison": "serveur mal configure (DNAREADER_SECRET)"}
    with _lock:
        c = _con()
        licences.prepare_essais(c)
        return licences.essai(c, d.machine, SECRET)


@app.post("/licence/discord")
def licence_discord(d: DemandeAdmin):
    if not _admin_ok(d.admin):
        return JSONResponse({"ok": False, "raison": "refuse"}, status_code=403)
    with _lock:
        c = _con()
        licences.prepare(c)
        return licences.cle_pour_discord(c, d.note, d.jours or 0,
                                         machines=d.machines or 2)


@app.post("/licence/discord/retirer")
def licence_discord_retirer(d: DemandeAdmin):
    if not _admin_ok(d.admin):
        return JSONResponse({"ok": False, "raison": "refuse"}, status_code=403)
    with _lock:
        c = _con()
        licences.prepare(c)
        cle = licences.cle_du_discord(c, d.note)
        if not cle:
            return {"ok": False, "raison": "aucune cle pour ce compte Discord"}
        return licences.change_etat(c, cle, "suspendue")


@app.post("/licence/prolonger")
def licence_prolonger(d: DemandeAdmin):
    if not _admin_ok(d.admin):
        return JSONResponse({"ok": False, "raison": "refuse"}, status_code=403)
    with _lock:
        c = _con()
        licences.prepare(c)
        return licences.prolonge(c, d.cle, d.jours or 31)


@app.post("/licence/essais")
def licence_essais(d: DemandeAdmin):
    if not _admin_ok(d.admin):
        return JSONResponse({"ok": False, "raison": "refuse"}, status_code=403)
    with _lock:
        c = _con()
        licences.prepare_essais(c)
        return {"ok": True, "essais": licences.essais(c)}


@app.post("/licence/creer")
def licence_creer(d: DemandeAdmin):
    if not _admin_ok(d.admin):
        return JSONResponse({"ok": False, "raison": "refuse"}, status_code=403)
    with _lock:
        c = _con()
        licences.prepare(c)
        return {"ok": True, **licences.cree(c, d.plan, d.machines, d.note, d.jours)}


@app.post("/licence/etat")
def licence_etat(d: DemandeAdmin):
    if not _admin_ok(d.admin):
        return JSONResponse({"ok": False, "raison": "refuse"}, status_code=403)
    with _lock:
        c = _con()
        licences.prepare(c)
        return licences.change_etat(c, d.cle, d.etat or "active")


@app.post("/licence/liberer")
def licence_liberer(d: DemandeAdmin):
    if not _admin_ok(d.admin):
        return JSONResponse({"ok": False, "raison": "refuse"}, status_code=403)
    with _lock:
        c = _con()
        licences.prepare(c)
        return licences.libere_machine(c, d.cle)


@app.post("/licence/liste")
def licence_liste(d: DemandeAdmin):
    if not _admin_ok(d.admin):
        return JSONResponse({"ok": False, "raison": "refuse"}, status_code=403)
    with _lock:
        c = _con()
        licences.prepare(c)
        return {"ok": True, "licences": licences.liste(c)}


class LotRecolte(BaseModel):
    jeton: str
    jeu: str
    lignes: list = []


@app.post("/recolte")
def recolte_recois(x: LotRecolte):
    with _lock:
        c = _con()
        ident = _qui(c, x.jeton)
        if not ident:
            return {"ok": False, "error": "session expiree : reconnecte-toi"}
        return recolte_serveur.recois(c, ident, x.jeu, x.lignes)


@app.post("/recolte/etat")
def recolte_etat_admin(d: DemandeAdmin):
    if not _admin_ok(d.admin):
        return JSONResponse({"ok": False, "raison": "refuse"}, status_code=403)
    with _lock:
        return {"ok": True, **recolte_serveur.etat(_con())}


@app.post("/contributions")
def contributions_lire(j: Jeton):
    with _lock:
        c = _con()
        ident = _qui(c, j.jeton)
        if not ident:
            return {"ok": False, "raison": "session expiree : reconnecte-toi"}
        e = contributions.etat(c, ident, ACCORDS_REQUIS, CONTESTATIONS_MAX)
        return {"ok": True, **e}


class DemandeAbonnement(BaseModel):
    courriel: str = ""


@app.post("/boutique/abonner")
def boutique_abonner(d: DemandeAbonnement):
    with _lock:
        return boutique.commence(_con(), d.courriel)


class DemandeRetrait(BaseModel):
    retrait: str = ""


@app.post("/boutique/depuis-app")
def boutique_depuis_app():
    with _lock:
        return boutique.commence(_con(), "", depuis_app=True)


@app.post("/boutique/retrait")
def boutique_retrait(d: DemandeRetrait):
    with _lock:
        return boutique.retrait(_con(), d.retrait)


@app.post("/boutique/paypal")
async def boutique_paypal(request: Request):
    brut = (await request.body()).decode("utf-8", "replace")
    entetes = dict(request.headers)

    def traite():
        if not boutique.configuree():
            return {"ok": False, "raison": "boutique non configuree"}
        if not boutique.verifie_signature(entetes, brut):
            return {"ok": False, "raison": "signature refusee"}
        with _lock:
            return boutique.rappel(_con(), entetes, brut, SECRET,
                                   deja_verifie=True)

    r = await run_in_threadpool(traite)
    if not r.get("ok"):
        return JSONResponse(r, status_code=400)
    return r


@app.get("/boutique/merci", response_class=HTMLResponse)
def boutique_merci(subscription_id: str = ""):
    with _lock:
        c = boutique.commande(_con(), subscription_id)
    if c.get("prete"):
        corps = f"""<h1>C'est bon.</h1>
      <p>Voici ta cle d'acces. Elle t'a aussi ete envoyee par courriel.</p>
      <p class="cle">{c['cle']}</p>
      <p>Colle-la dans l'application : <b>Reglages &rsaquo; Cle d'acces</b>,
         avec l'adresse du serveur affichee sur la page de la boutique.</p>
      <p><a href="https://github.com/NanashiAngsnake/dnareader-releases/releases/latest">
         Telecharger DNAreader</a></p>"""
    else:
        corps = """<h1>Paiement recu</h1>
      <p>Ta cle est en train d'etre creee — quelques secondes.
         Cette page se rafraichit toute seule.</p>
      <script>setTimeout(() => location.reload(), 3000)</script>"""
    return HTMLResponse(_page(corps))




@app.get("/boutique/etat")
def boutique_etat():
    par_api = boutique.configuree() and boutique.ENV == "live"
    par_virement = bool(livraison.PAYPAL_ME)
    return {"ouverte": par_api or par_virement,
            "comment": "virement" if par_virement else ("api" if par_api else ""),
            "prix": livraison.PRIX if par_virement else boutique.PRIX,
            "devise": boutique.DEVISE,
            "paypal_me": livraison.PAYPAL_ME,
            "prefixe_note": livraison.PREFIXE,
            "essai_jours": licences.ESSAI_JOURS,
            "machines": livraison.MACHINES,
            "jours_par_paiement": livraison.JOURS,
            "telechargement": f"{DEPOT_PUBLIC}/releases/latest"}


class DemandeDiag(BaseModel):
    admin: str = ""


@app.post("/boutique/diagnostic")
def boutique_diagnostic(d: DemandeDiag):
    if not _admin_ok(d.admin):
        return JSONResponse({"ok": False, "raison": "refuse"}, status_code=403)

    api_manque = [x.strip() for x in
                  boutique.pourquoi_pas().replace("il manque ", "").split(",")
                  if x.strip()]
    vir_manque = [x.strip() for x in
                  livraison.pourquoi_pas().replace("il manque ", "").split(",")
                  if x.strip()]
    if boutique.ENV != "live":
        api_manque.append("PAYPAL_ENV=live (actuellement « %s »)" % boutique.ENV)
    if not livraison.PAYPAL_ME:
        vir_manque.append("PAYPAL_ME")

    return {"ok": True,
            "prix": boutique.PRIX, "devise": boutique.DEVISE,
            "ouverte": (not api_manque) or (not vir_manque),
            "abonnement_api": {
                "pret": not api_manque, "manque": api_manque,
                "environnement": boutique.ENV,
                "demande": "un compte PayPal Business",
                "apres": ["remplir PAYPAL_ID et PAYPAL_SECRET dans secrets.env",
                          "python ouvrir_boutique.py  (cree le webhook)",
                          "systemctl restart dnareader-sync"]},
            "virement_discord": {
                "pret": not vir_manque, "manque": vir_manque,
                "demande": "un compte PayPal ordinaire et une boite IMAP",
                "apres": ["remplir IMAP_* , DISCORD_JETON, DISCORD_SERVEUR, "
                          "PAYPAL_ME dans secrets.env",
                          "systemctl restart dnareader-sync",
                          "le journal doit dire « Livraison Discord active »"]},
            "courriel_facultatif": {
                "pret": bool(boutique.SMTP_HOTE),
                "a_quoi": "envoyer la cle par courriel en plus du reste"}}


@app.get("/", response_class=HTMLResponse)
def accueil():
    return HTMLResponse(_page(f"""<h1>DNAreader</h1>
      <p class="chapeau">Le japonais de tes jeux, lu a l'ecran pendant que tu
         joues. La lecture, le sens et le vocabulaire s'affichent dans une bulle
         posee a cote — sans capture manuelle, sans quitter la partie.</p>

      <p><a class="bouton" href="{DEPOT_PUBLIC}/releases/latest">
         Telecharger pour Windows</a></p>
      <p class="petit">Windows 10 ou 11, 64 bits. Aucun droit administrateur.
         <b>Sept jours d'essai gratuit</b>, sans carte bancaire.</p>

      <h2>Ensuite</h2>
      <ul>
        <li>{boutique.PRIX} &euro; par mois, resiliable a tout moment</li>
        <li>L'abonnement se prend depuis l'application, en un clic</li>
        <li>Deux machines, et quatorze jours d'autonomie sans reseau</li>
      </ul>

      <p class="petit">Windows affichera « Windows a proteg&eacute; votre
         ordinateur » : l'application n'est pas encore signee.
         <b>Informations complementaires &rsaquo; Executer quand meme.</b></p>
      <p class="petit">Dictionnaire <a href="https://www.edrdg.org/">JMdict</a>
         de l'EDRDG, sous licence CC BY-SA 4.0.</p>"""))


@app.get("/boutique", response_class=HTMLResponse)
def boutique_page():
    if livraison.PAYPAL_ME:
        return HTMLResponse(_page(_page_discord()))
    if not boutique.configuree():
        return HTMLResponse(_page(
            "<h1>Boutique pas encore ouverte</h1>"
            f"<p>{boutique.pourquoi_pas()}</p>"), status_code=503)
    return HTMLResponse(_page(f"""<h1>DNAreader</h1>
      <p class="chapeau">Le japonais de tes jeux, lu a l'ecran pendant que tu
         joues. Lecture, sens et vocabulaire dans une bulle posee a cote.</p>
      <p class="prix">{boutique.PRIX} &euro; <span>par mois</span></p>
      <ul>
        <li>Sept jours d'essai gratuit, sans carte</li>
        <li>Deux machines par cle</li>
        <li>Fonctionne quatorze jours sans reseau</li>
        <li>Resiliable a tout moment — la cle court jusqu'a la fin du mois paye</li>
      </ul>
      <form id="f">
        <input id="courriel" type="email" required placeholder="ton@courriel.fr">
        <button type="submit">S'abonner</button>
      </form>
      <p id="erreur"></p>
      <script>
      document.getElementById('f').addEventListener('submit', async ev => {{
        ev.preventDefault();
        const b = ev.target.querySelector('button');
        b.disabled = true; b.textContent = 'un instant...';
        const r = await fetch('/boutique/abonner', {{method:'POST',
          headers:{{'Content-Type':'application/json'}},
          body: JSON.stringify({{courriel: document.getElementById('courriel').value}})
        }}).then(x => x.json()).catch(e => ({{ok:false, raison:String(e)}}));
        if (r.ok && r.url) {{ location.href = r.url; return; }}
        document.getElementById('erreur').textContent = r.raison || 'echec';
        b.disabled = false; b.textContent = "S'abonner";
      }});
      </script>"""))


def _page_discord() -> str:
    return f"""<h1>DNAreader</h1>
      <p class="chapeau">Le japonais de tes jeux, lu a l'ecran pendant que tu
         joues.</p>
      <p class="prix">{livraison.PRIX:.2f} &euro; <span>par mois</span></p>
      <ul>
        <li>Sept jours d'essai gratuit avant de payer quoi que ce soit</li>
        <li>Deux machines par cle, quatorze jours sans reseau</li>
        <li>Ta cle arrive en message prive sur Discord</li>
      </ul>

      <h2>1. Ton pseudo Discord</h2>
      <form id="f" onsubmit="return false">
        <input id="pseudo" type="text" placeholder="tonpseudo" spellcheck="false"
               autocomplete="off" maxlength="32">
      </form>
      <p class="petit">Il faut etre sur le serveur Discord pour recevoir le
         message.</p>

      <h2>2. La note a mettre dans le paiement</h2>
      <p class="cle" id="note">{livraison.PREFIXE}-<i>tonpseudo</i></p>
      <p><button id="copier" type="button">Copier la note</button></p>
      <p class="petit"><b>Sans cette note, on ne sait pas a qui envoyer la
         cle.</b> C'est elle qui fait le lien entre le virement et toi.</p>

      <h2>3. Payer</h2>
      <p><a class="bouton" id="payer" href="{livraison.PAYPAL_ME}"
            target="_blank" rel="noopener">Payer {livraison.PRIX:.2f} &euro;
            sur PayPal</a></p>
      <p class="petit">Ta cle arrive en message prive dans la minute qui suit.
         Pour le mois suivant, renvoie la meme somme avec la meme note : c'est
         la <b>meme cle</b> qui est prolongee, tu n'as jamais a en ressaisir une
         autre.</p>

      <script>
      const p = document.getElementById('pseudo');
      const n = document.getElementById('note');
      const PREFIXE = {json.dumps(livraison.PREFIXE)};
      function note() {{
        const v = p.value.trim().replace(/^@/, '');
        return v ? PREFIXE + '-' + v : '';
      }}
      p.addEventListener('input', () => {{
        n.textContent = note() || PREFIXE + '-tonpseudo';
      }});
      document.getElementById('copier').addEventListener('click', async e => {{
        const v = note();
        if (!v) {{ p.focus(); return; }}
        try {{ await navigator.clipboard.writeText(v); }} catch (x) {{}}
        e.target.textContent = 'copie !';
        setTimeout(() => e.target.textContent = 'Copier la note', 1500);
      }});
      </script>"""


def _page(corps: str) -> str:
    return f"""<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>DNAreader</title><style>
:root {{ color-scheme: light dark; }}
body {{ font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
  max-width: 34rem; margin: 0 auto; padding: 3rem 1.25rem 5rem; line-height: 1.6;
  background: Canvas; color: CanvasText; }}
h1 {{ font-size: 1.9rem; margin: 0 0 .6rem; letter-spacing: -.02em; }}
.chapeau {{ color: GrayText; margin-top: 0; }}
.prix {{ font-size: 2.6rem; font-weight: 600; margin: 1.6rem 0 .2rem; }}
.prix span {{ font-size: 1rem; font-weight: 400; color: GrayText; }}
ul {{ padding-left: 1.1rem; color: GrayText; }}
li {{ margin: .3rem 0; }}
form {{ display: flex; gap: .5rem; margin: 1.8rem 0 .5rem; flex-wrap: wrap; }}
input {{ flex: 1 1 14rem; padding: .7rem .8rem; font-size: 1rem;
  border: 1px solid GrayText; border-radius: .4rem; background: Canvas;
  color: CanvasText; }}
button {{ padding: .7rem 1.4rem; font-size: 1rem; font-weight: 600;
  border: 0; border-radius: .4rem; background: CanvasText; color: Canvas;
  cursor: pointer; }}
button[disabled] {{ opacity: .5; cursor: default; }}
.cle {{ font-family: ui-monospace, Consolas, monospace; font-size: 1.35rem;
  font-weight: 600; padding: .9rem 1rem; border: 1px solid GrayText;
  border-radius: .5rem; text-align: center; letter-spacing: .04em;
  overflow-wrap: anywhere; }}
#erreur {{ color: #c0392b; }}
a {{ color: inherit; }}
h2 {{ font-size: 1.1rem; margin: 2.2rem 0 .4rem; }}
.petit {{ font-size: .88rem; color: GrayText; }}
/* Le geste principal se voit de loin : c'est la seule chose qu'on demande a
   quelqu'un qui arrive sur cette page. */
.bouton {{ display: inline-block; padding: .85rem 1.7rem; font-size: 1.05rem;
  font-weight: 600; border-radius: .45rem; background: CanvasText;
  color: Canvas; text-decoration: none; margin: 1.4rem 0 .4rem; }}
.bouton:hover {{ opacity: .85; }}
</style></head><body>{corps}</body></html>"""


class Rapport(BaseModel):
    machine: str = ""
    version: str = ""
    message: str = ""
    contexte: dict | None = None
    journal: str = ""


@app.post("/rapport")
def rapport_recois(r: Rapport):
    with _lock:
        return rapports.recois(_con(), r.model_dump())


@app.post("/rapport/liste")
def rapport_liste(d: DemandeAdmin):
    if not _admin_ok(d.admin):
        return JSONResponse({"ok": False, "raison": "refuse"}, status_code=403)
    with _lock:
        return {"ok": True,
                "rapports": rapports.liste(_con(), tous=(d.etat == "tous"))}


@app.post("/rapport/detail")
def rapport_detail(d: DemandeAdmin):
    if not _admin_ok(d.admin):
        return JSONResponse({"ok": False, "raison": "refuse"}, status_code=403)
    with _lock:
        return rapports.detail(_con(), int(d.jours or 0))


@app.post("/rapport/classer")
def rapport_classer(d: DemandeAdmin):
    if not _admin_ok(d.admin):
        return JSONResponse({"ok": False, "raison": "refuse"}, status_code=403)
    with _lock:
        return rapports.classe(_con(), int(d.jours or 0), d.etat or "traite")


@app.get("/sante")
def sante():
    return {"ok": True, "app": "dnareader-sync"}


if __name__ == "__main__":
    import uvicorn
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8800)
    ap.add_argument("--host", default="0.0.0.0")
    a = ap.parse_args()
    print(f"Serveur de synchronisation DNAreader sur {a.host}:{a.port}")
    if livraison.configuree():
        print(f"Livraison Discord active — note « {livraison.PREFIXE}-pseudo », "
              f"relecture toutes les {livraison.ENTRE_DEUX_LECTURES}s")
        livraison.au_demarrage(_con, _lock)
    else:
        print(f"Livraison Discord en sommeil : {livraison.pourquoi_pas()}")
    uvicorn.run(app, host=a.host, port=a.port, log_level="warning")
