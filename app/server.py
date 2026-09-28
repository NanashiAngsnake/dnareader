# -*- coding: utf-8 -*-

import asyncio
import base64
import hashlib
import io
import re
import threading
import time
import webbrowser
from collections import deque
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image
from pydantic import BaseModel

import apprentissage
import capture
import corrections
import detect
import hotkey
import precise
import comptes
import partage
import profiles
import stream
import translate
import vocab
import zones_apprises

import chaine_lecture
from chaine_lecture import (PERF, REJETS, DICT, TAGGER,
                            _read, _annotate, _apprend_texte, segment)
_DEBUT_FLUX = [0.0]

import chemins
from dictionary import is_jp_char
app = FastAPI(title="DNAreader")



class OcrBody(BaseModel):
    image: str | None = None
    window: str | None = None
    screen: bool = False
    auto: bool = False
    region: list[float] | None = None
    enhance: str = "auto"
    engine: str = "windows"
    want_image: bool = True


class LookupBody(BaseModel):
    text: str
    offset: int
    langue: str = "fr"


class ProbeBody(BaseModel):
    window: str | None = None
    screen: bool = False
    region: list[float] | None = None


_NO_CACHE = {"Cache-Control": "no-store, must-revalidate", "Pragma": "no-cache"}


@app.get("/")
def index():
    return FileResponse(chemins.STATIC / "index.html", headers=_NO_CACHE)


@app.get("/overlay")
def overlay():
    return FileResponse(chemins.STATIC / "overlay.html", headers=_NO_CACHE)


@app.get("/api/ping")
def ping():
    import os
    return {"app": "dnareader", "pid": os.getpid()}


REGLAGES = {}


class ReglageBody(BaseModel):
    cle: str
    valeur: object = None


@app.get("/api/reglage")
def reglage_lire():
    return {"reglages": REGLAGES}


@app.post("/api/reglage")
async def reglage_ecrire(body: ReglageBody):
    REGLAGES[body.cle] = body.valeur
    await _broadcast({"type": "reglage", "cle": body.cle, "valeur": body.valeur})
    return {"ok": True}


@app.post("/api/reglage/etat")
def reglage_etat(body: dict):
    if isinstance(body, dict):
        REGLAGES.update(body)
    return {"ok": True}


@app.get("/reglages")
def page_reglages():
    return FileResponse(chemins.STATIC / "reglages.html", headers=_NO_CACHE)


class CompteBody(BaseModel):
    serveur: str = ""
    identifiant: str = ""
    motdepasse: str = ""


class CheminBody(BaseModel):
    chemin: str = ""


@app.get("/api/compte")
def compte_etat():
    return comptes.status()


@app.post("/api/compte/inscription")
def compte_inscription(b: CompteBody):
    return comptes.inscription(b.serveur, b.identifiant, b.motdepasse)


@app.post("/api/compte/connexion")
def compte_connexion(b: CompteBody):
    return comptes.connexion(b.serveur, b.identifiant, b.motdepasse)


@app.post("/api/compte/deconnexion")
def compte_deconnexion():
    return comptes.deconnexion()


@app.post("/api/compte/sync")
def compte_sync():
    return comptes.synchronise()


@app.post("/api/compte/export")
def compte_export(b: CheminBody):
    return comptes.exporte(b.chemin)


@app.post("/api/compte/import")
def compte_import(b: CheminBody):
    return comptes.importe(b.chemin)


class PartageBody(BaseModel):
    actif: bool = None
    serveur: str = None


class ProposeBody(BaseModel):
    jeu: str = ""
    faux: str = ""
    juste: str = ""
    contexte: str = ""
    seconde: float = 0.0


@app.get("/api/partage")
def partage_etat():
    return partage.status()


@app.post("/api/partage")
def partage_regle(b: PartageBody):
    return partage.regle(b.actif, b.serveur)


@app.post("/api/partage/propose")
def partage_propose(b: ProposeBody):
    return partage.propose(b.jeu, b.faux, b.juste, b.contexte, b.seconde,
                           DICT, TAGGER)


@app.post("/api/partage/tirer")
def partage_tirer(b: ProposeBody):
    return partage.tire(b.jeu)


@app.get("/api/contributions")
def contributions_lire():
    try:
        return partage.contributions()
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.get("/api/partage/propositions")
def partage_propositions(jeu: str = ""):
    return partage.propositions(jeu)


@app.post("/api/partage/contester")
def partage_conteste(b: ProposeBody):
    return partage.conteste(b.jeu, b.faux, b.juste)


class ZoneBody(BaseModel):
    jeu: str = ""
    rect: list[float] | None = None
    texte: str = ""


@app.get("/api/zones-apprises")
def zones_lire(jeu: str = ""):
    return {"zones": zones_apprises.pour(jeu) if jeu else [],
            "total": zones_apprises.compte()}


@app.post("/api/zone-apprise")
def zone_apprend(b: ZoneBody):
    return zones_apprises.ajoute(b.jeu, b.rect, b.texte)


@app.post("/api/zone-apprise/remove")
def zone_retire(b: ZoneBody):
    return zones_apprises.retire(b.jeu, b.rect or [])


@app.post("/api/zone-lire")
async def zone_lire(b: ZoneBody):
    if not b.rect or len(b.rect) < 4:
        return {"ok": False, "error": "rectangle manquant"}
    try:
        img = (capture.capture_window(b.jeu) if b.jeu else capture.capture_screen(None))
    except Exception as e:
        return {"ok": False, "error": str(e)}
    texte = await chaine_lecture.lit_un_endroit(img, b.rect)
    return {"ok": True, "texte": texte}


@app.get("/api/rejets")
def rejets():
    return {"rejets": list(REJETS)}


@app.get("/api/perf")
def perf():
    st = stream.status()
    q = stream.quiet_for()
    fps = None
    try:
        depuis = time.time() - _DEBUT_FLUX[0] if _DEBUT_FLUX[0] else 0
        if st.get("on") and depuis > 1:
            fps = round(st.get("frames", 0) / depuis, 1)
    except Exception:
        pass
    return {"flux": {"actif": st.get("on"), "images": st.get("frames"),
                     "images_par_seconde": fps,
                     "silence_s": round(q, 2) if q >= 0 else None},
            "lecture": PERF,
            "moteurs": {"detecteur": detect.status().get("loaded"),
                        "precision": precise.status().get("loaded"),
                        "lignes_memorisees": precise.status().get("memorisees"),
                        "traduction": translate.status().get("loaded")}}


@app.get("/api/windows")
def windows():
    return {"windows": capture.list_windows()}


_LAST_SIG = None


def _signature(img: Image.Image) -> bytes:
    return img.convert("L").resize((32, 32)).tobytes()


def _similar(a, b, tol: int = 8, frac: float = 0.02) -> bool:
    if a is None or b is None or len(a) != len(b):
        return False
    changed = sum(1 for x, y in zip(a, b) if abs(x - y) > tol)
    return changed <= frac * len(a)


def _crop_region(img: Image.Image, region) -> Image.Image:
    try:
        fx, fy, fw, fh = region
        W, H = img.width, img.height
        x1, y1 = max(0, int(fx * W)), max(0, int(fy * H))
        x2, y2 = min(W, int((fx + fw) * W)), min(H, int((fy + fh) * H))
        if x2 - x1 >= 10 and y2 - y1 >= 10:
            return img.crop((x1, y1, x2, y2))
    except Exception:
        pass
    return img


def _refus_acces():
    try:
        import acces
        e = acces.etat()
    except Exception:
        return None
    if e.get("ok"):
        return None
    return {"error": e.get("raison_cle") or e.get("raison") or "acces expire",
            "acces": e}


@app.post("/api/ocr")
async def do_ocr(body: OcrBody):
    refus = _refus_acces()
    if refus:
        return refus
    try:
        if body.image:
            raw = body.image.split(",", 1)[-1]
            img = Image.open(io.BytesIO(base64.b64decode(raw)))
            if body.region:
                img = _crop_region(img, body.region)
        elif body.window:
            img = capture.capture_window(body.window, body.region)
        else:
            img = capture.capture_screen(body.region)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)

    global _LAST_SIG
    if not body.image:
        sig = _signature(img)
        if body.auto and _similar(sig, _LAST_SIG):
            return {"nochange": True}
        _LAST_SIG = sig

    lines = await _read(img, body.enhance, body.engine,
                        body.window or "", body.region)
    out = {"width": img.width, "height": img.height, "lines": lines}
    if body.want_image:
        buf = io.BytesIO()
        img.convert("RGB").save(buf, format="JPEG", quality=88)
        out["image"] = "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
    return out


_PROBES: dict = {}


@app.post("/api/probe")
def probe(body: ProbeBody):
    refus = _refus_acces()
    if refus:
        return refus
    if stream.status().get("on"):
        q = stream.quiet_for()
        return {"sig": f"s{stream._state['frames']}", "changed": q >= 0 and q < 0.25,
                "quiet": round(q, 3), "stream": True}
    try:
        img = (capture.capture_window(body.window, body.region) if body.window
               else capture.capture_screen(body.region))
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)

    key = (body.window or "screen", tuple(body.region) if body.region else None)
    sig = _signature(img)
    prev = _PROBES.get(key)
    if prev and _similar(sig, prev["sig"]):
        return {"sig": prev["token"], "changed": False}
    token = hashlib.blake2b(sig, digest_size=8).hexdigest()
    _PROBES[key] = {"sig": sig, "token": token}
    return {"sig": token, "changed": True}


class TextBody(BaseModel):
    text: str


class GrabBody(BaseModel):
    window: str | None = None
    screen: bool = False
    region: list[float] | None = None


class DrainBody(BaseModel):
    enhance: str = "auto"
    engine: str = "windows"


_PENDING: deque = deque(maxlen=6)
_LAST_DRAIN_SIG = None
_LAST_DRAIN_LINES = None


class StreamBody(BaseModel):
    on: bool = False
    window: str | None = None


@app.post("/api/stream")
async def stream_toggle(body: StreamBody):
    if body.on and body.window:
        r = await asyncio.to_thread(stream.start, body.window)
        _DEBUT_FLUX[0] = time.time()
    else:
        r = await asyncio.to_thread(stream.stop)
        _DEBUT_FLUX[0] = 0.0
    return {**r, **stream.status()}


@app.get("/api/stream")
def stream_status():
    return stream.status()


@app.post("/api/grab")
def grab(body: GrabBody):
    try:
        img = (capture.capture_window(body.window, body.region) if body.window
               else capture.capture_screen(body.region))
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    _PENDING.append({"img": img, "jeu": body.window or "", "region": body.region})
    couvert = capture.couverte_par(body.window, body.region) if body.window else None
    plein = capture.plein_ecran_exclusif(img)
    return {"queued": len(_PENDING), "couvert": couvert,
            "plein_ecran": plein or None}


@app.post("/api/drain")
async def drain(body: DrainBody):
    refus = _refus_acces()
    if refus:
        return refus
    if not _PENDING:
        return {"empty": True, "queued": 0}
    item = _PENDING.popleft()
    img = item["img"]

    global _LAST_DRAIN_SIG, _LAST_DRAIN_LINES
    sig = _signature(img)
    if _LAST_DRAIN_LINES is not None and _similar(sig, _LAST_DRAIN_SIG):
        return {"queued": len(_PENDING), "lines": _LAST_DRAIN_LINES, "cached": True}

    lines = await _read(img, body.enhance, body.engine,
                        item.get("jeu") or "", item.get("region"))
    _LAST_DRAIN_SIG, _LAST_DRAIN_LINES = sig, lines
    return {"queued": len(_PENDING), "lines": lines}


@app.post("/api/text")
def read_text(body: TextBody):
    lines = []
    for raw in (body.text or "").splitlines():
        txt = raw.strip()
        if not txt:
            continue
        chars = [[i * 20.0, 0.0, 20.0, 28.0] for i in range(len(txt))]
        lines.append({"text": txt, "box": [0.0, 0.0, len(txt) * 20.0, 28.0],
                      "chars": chars})
    return {"width": 0, "height": 0, "lines": _annotate(lines), "from_text": True}


class VocabBody(BaseModel):
    expr: str
    reading: str = ""
    gloss: str = ""
    sentence: str = ""
    source: str = ""


@app.get("/api/vocab")
def vocab_list():
    return {"words": vocab.listing(), "count": vocab.count()}


@app.post("/api/vocab")
def vocab_add(body: VocabBody):
    r = vocab.add(body.expr, body.reading, body.gloss, body.sentence, body.source)
    if r.get("ok") and body.sentence:
        _apprend_texte(body.sentence, 1, 1.0, "vocabulaire", body.source)
    return r


@app.post("/api/vocab/remove")
def vocab_remove(body: VocabBody):
    return vocab.remove(body.expr, body.reading)


@app.get("/api/vocab/export")
def vocab_export():
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(vocab.to_anki_tsv(),
                             headers={"Content-Disposition":
                                      'attachment; filename="vocabulaire-anki.tsv"'})


@app.get("/api/vocab/export.apkg")
def vocab_export_apkg():
    import tempfile
    try:
        f = Path(tempfile.gettempdir()) / "dnareader.apkg"
        vocab.to_anki_apkg(f)
        return FileResponse(f, media_type="application/octet-stream",
                            filename="DNAreader.apkg")
    except Exception as e:
        return JSONResponse({"error": f"export impossible : {e}"}, status_code=500)


class TranslateBody(BaseModel):
    texts: list[str] = []


@app.get("/api/translate")
def translate_status():
    return translate.status()


_VERBALISATIONS = ("il y a ", "il y a d'", "c'est ", "ce sont ", "voici ",
                   "voilà ", "j'ai ", "vous avez ", "on a ")


def _groupe_nominal(texte: str) -> bool:
    if any(c in texte for c in "。．！？!?、…"):
        return False
    try:
        for tok in TAGGER(texte):
            if (getattr(tok.feature, "pos1", "") or "") in ("動詞", "形容詞", "助動詞"):
                return False
    except Exception:
        return False
    return True


def _degroupe(fr: str) -> str:
    bas = fr.lstrip().lower()
    for p in sorted(_VERBALISATIONS, key=len, reverse=True):
        if bas.startswith(p):
            reste = fr.lstrip()[len(p):].strip(" .")
            return reste[:1].upper() + reste[1:] if reste else fr
    return fr.rstrip(" .")


PORTEUSE = "{}という道具"
_EXTRAIT = re.compile(
    r"outil\s+(?:appel[ée]e?|nomm[ée]e?|dit[e]?|de\s+la|de\s+l'|du|des|de|d')\s*"
    r"[\"«“]?\s*(.+?)\s*[\"»”]?\s*\.?\s*$", re.I)


def _sort_de_la_porteuse(fr: str) -> str | None:
    m = _EXTRAIT.search(fr or "")
    if not m:
        return None
    nom = m.group(1).strip(" .\"«»")
    return nom or None


def _gloss_dictionnaire(texte: str) -> str | None:
    t = texte.strip()
    if not t or len(t) > 14:
        return None
    try:
        r = DICT.lookup(t, 0)
        if r.get("matchLen") != len(t):
            return None
        for m in (r.get("matches") or []):
            if m.get("expression") != t and m.get("reading") != t:
                continue
            defs = m.get("defs") or []
            fr = next((d["glosses"] for d in defs
                       if d.get("lang") == "fr" and d.get("glosses")), None)
            if fr:
                return ", ".join(fr[:3])
            en = next((d["glosses"] for d in defs
                       if d.get("lang") == "en" and d.get("glosses")), None)
            if en:
                utiles = [g for g in en if not any(is_jp_char(c) for c in g)]
                if utiles:
                    return "[en] " + ", ".join(utiles[:3])
    except Exception:
        pass
    return None


@app.post("/api/translate")
async def translate_lines(body: TranslateBody):
    textes = body.texts or []
    direct = {t: g for t in textes if (g := _gloss_dictionnaire(t))}
    reste = [t for t in textes if t not in direct]

    noms = {t for t in reste if _groupe_nominal(t)}
    envoi = [PORTEUSE.format(t) if t in noms else t for t in reste]

    r = await asyncio.to_thread(translate.translate, envoi) if envoi else {"texts": []}
    if r.get("error") and not direct:
        return r
    traduit = dict(zip(reste, r.get("texts") or []))

    sortie = []
    for t in textes:
        if t in direct:
            sortie.append(direct[t])
            continue
        fr = traduit.get(t, "")
        if fr and t in noms:
            fr = _sort_de_la_porteuse(fr) or _degroupe(fr)
        sortie.append(fr)
    return {"texts": sortie, "from_cache": r.get("from_cache", 0),
            "from_dict": len(direct)}


@app.post("/api/translate/warmup")
async def translate_warmup():
    ok = await asyncio.to_thread(translate.start)
    return {"ok": ok, **translate.status()}


@app.get("/api/apprentissage")
def apprentissage_stats():
    return apprentissage.stats()


@app.post("/api/apprentissage/entrainer")
async def apprentissage_entrainer():
    return await asyncio.to_thread(apprentissage.entraine)


class ProfileBody(BaseModel):
    game: str = ""
    data: dict = {}


@app.get("/api/profile")
def profile_get(game: str = ""):
    return {"game": game, "profile": profiles.get(game)}


@app.post("/api/profile")
def profile_save(body: ProfileBody):
    return profiles.save(body.game, body.data)


@app.post("/api/profile/remove")
def profile_remove(body: ProfileBody):
    return profiles.remove(body.game)


@app.get("/api/profiles")
def profile_list():
    return {"profiles": profiles.listing(), "count": profiles.count()}


class FixBody(BaseModel):
    wrong: str = ""
    right: str = ""
    source: str = ""


@app.get("/api/corrections")
def corrections_list():
    return {"fixes": corrections.listing(), "count": corrections.count()}


@app.post("/api/corrections")
def corrections_add(body: FixBody):
    r = corrections.add(body.wrong, body.right, body.source)
    if r.get("ok"):
        _apprend_texte(body.wrong, 0, 1.0, "correction", body.source)
        _apprend_texte(body.right, 1, 1.0, "correction", body.source)
        try:
            p = partage.propose(body.source or "", body.wrong, body.right,
                                dic=DICT, tagger=TAGGER)
            if p.get("ok"):
                r["partagee"] = True
                r["confirmee"] = p.get("confirmee")
                r["manque"] = p.get("manque")
        except Exception:
            pass
    return r


@app.post("/api/corrections/remove")
def corrections_remove(body: FixBody):
    return corrections.remove(body.wrong)


@app.get("/api/corrections/export")
def corrections_export():
    return {"pairs": corrections.export_pairs(), "count": corrections.count()}


@app.post("/api/lookup")
def lookup(body: LookupBody):
    res = DICT.lookup(body.text, body.offset, langue=body.langue)
    res["words"] = segment(body.text)
    if not res["matches"]:
        for w in res["words"]:
            if w["s"] <= body.offset < w["e"] and w["lemma"]:
                fb = DICT.lookup(w["lemma"], 0, langue=body.langue)
                if fb["matches"]:
                    for m in fb["matches"]:
                        m["matchLen"] = w["e"] - body.offset
                    res["matches"] = fb["matches"]
                    res["matchLen"] = w["e"] - body.offset
                break
    return res


class LicenceBody(BaseModel):
    serveur: str = ""
    cle: str = ""


@app.get("/api/licence")
def licence_lire():
    try:
        import licence_client
        return licence_client.resume()
    except Exception as e:
        return {"ok": False, "raison": str(e), "aucune_cle": True}


@app.post("/api/licence/activer")
async def licence_activer(b: LicenceBody):
    try:
        import licence_client
        r = licence_client.active(b.serveur, b.cle)
    except Exception as e:
        return {"ok": False, "raison": str(e)}
    if r.get("ok"):
        await _broadcast({"type": "acces"})
    return r


class RecolteBody(BaseModel):
    actif: bool = False


@app.get("/api/recolte")
def recolte_etat():
    try:
        import chaine_lecture
        import recolte
        import recolte_envoi
        return {"ok": True, "actif": bool(chaine_lecture.RECOLTE_ACTIVE),
                **recolte.etat(), "envoi": recolte_envoi.etat()}
    except Exception as e:
        return {"ok": False, "raison": str(e)}


@app.post("/api/recolte")
def recolte_regle(b: RecolteBody):
    try:
        import chaine_lecture
        import recolte
        import recolte_envoi
        chaine_lecture.RECOLTE_ACTIVE = bool(b.actif)
        recolte.retiens(chaine_lecture.RECOLTE_ACTIVE)
        if chaine_lecture.RECOLTE_ACTIVE:
            recolte_envoi.demarre()
        else:
            recolte_envoi.arrete()
        return {"ok": True, "actif": chaine_lecture.RECOLTE_ACTIVE,
                **recolte.etat(), "envoi": recolte_envoi.etat()}
    except Exception as e:
        return {"ok": False, "raison": str(e)}


class SignalementBody(BaseModel):
    message: str = ""
    journal: bool = True


@app.get("/api/signalement/apercu")
def signalement_apercu(journal: bool = True):
    try:
        import signalement
        return {"ok": True, **signalement.apercu(journal)}
    except Exception as e:
        return {"ok": False, "raison": str(e)}


@app.post("/api/signalement")
def signalement_envoie(b: SignalementBody):
    try:
        import signalement
        return signalement.envoie(b.message, b.journal)
    except Exception as e:
        return {"ok": False, "raison": str(e)}


@app.get("/api/licence/boutique")
def licence_boutique():
    try:
        import licence_client
        return licence_client.boutique_ouverte()
    except Exception as e:
        return {"ouverte": False, "raison": str(e)}


@app.post("/api/licence/abonner")
def licence_abonner():
    try:
        import licence_client
        return licence_client.abonne()
    except Exception as e:
        return {"ok": False, "raison": str(e)}


@app.get("/api/licence/attente")
def licence_attente():
    try:
        import licence_client
        return licence_client.attente()
    except Exception as e:
        return {"ok": False, "raison": str(e)}


@app.post("/api/licence/oublier")
async def licence_oublier():
    try:
        import licence_client
        r = licence_client.oublie()
    except Exception as e:
        return {"ok": False, "raison": str(e)}
    await _broadcast({"type": "acces"})
    return r


@app.get("/api/acces")
def acces_lire():
    try:
        import acces
        return acces.etat()
    except Exception as e:
        return {"ok": True, "mode": "libre", "raison": str(e)}


@app.get("/api/version")
def version_lire():
    import version
    return {"nom": version.NOM, "version": version.VERSION,
            "editeur": version.EDITEUR}


@app.get("/api/maj")
def maj_etat():
    try:
        import maj
        return maj.etat()
    except Exception as e:
        return {"possible": False, "erreur": str(e)}


@app.post("/api/maj/chercher")
def maj_chercher():
    try:
        import maj
        return maj.cherche(force=True)
    except Exception as e:
        return {"possible": False, "erreur": str(e)}


@app.post("/api/maj/telecharger")
def maj_telecharger():
    try:
        import maj
        return maj.telecharge()
    except Exception as e:
        return {"ok": False, "raison": str(e)}


@app.post("/api/maj/annuler")
def maj_annuler():
    try:
        import maj
        return maj.annule()
    except Exception as e:
        return {"ok": False, "raison": str(e)}


@app.post("/api/maj/installer")
def maj_installer():
    try:
        import maj
        return maj.installe()
    except Exception as e:
        return {"ok": False, "raison": str(e)}


class MajIgnore(BaseModel):
    version: str = ""


@app.post("/api/maj/ignorer")
def maj_ignorer(d: MajIgnore):
    try:
        import maj
        return maj.ignore(d.version)
    except Exception as e:
        return {"ok": False, "raison": str(e)}


class MajAuto(BaseModel):
    actif: bool = True


@app.post("/api/maj/auto")
def maj_auto(d: MajAuto):
    try:
        import maj
        return maj.auto(d.actif)
    except Exception as e:
        return {"ok": False, "raison": str(e)}


@app.get("/api/tags")
def tags():
    return DICT.tags


@app.get("/api/engines")
def engines():
    r = {"windows": True, "precise": precise.available(), **precise.status()}
    try:
        import maison
        r["maison"] = maison.available()
        r["maison_etat"] = maison.status()
    except Exception:
        r["maison"] = False
    return r


@app.post("/api/precise/warmup")
async def precise_warmup():
    if not precise.available():
        return JSONResponse({"error": "manga-ocr n'est pas installé"}, status_code=400)
    try:
        ok = await asyncio.to_thread(precise.start)
        if not ok:
            return JSONResponse({"error": precise.status().get("error") or "démarrage impossible"},
                                status_code=500)
        return {"ok": True}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


_ws_clients: set = set()
_loop = None


class HotkeyBody(BaseModel):
    hotkey: str
    name: str = "capture"


@app.on_event("startup")
async def _startup():
    global _loop
    _loop = asyncio.get_running_loop()
    hotkey.init(_on_hotkey)
    try:
        import chaine_lecture
        import recolte_envoi
        if chaine_lecture.RECOLTE_ACTIVE:
            recolte_envoi.demarre()
    except Exception:
        pass


def _on_hotkey():
    if _loop is not None:
        _loop.call_soon_threadsafe(
            lambda: asyncio.create_task(_broadcast({"type": "capture"})))


async def _broadcast(msg: dict):
    clients = list(_ws_clients)
    if not clients:
        return

    async def _envoie(ws):
        try:
            await asyncio.wait_for(ws.send_json(msg), timeout=1.0)
        except Exception:
            _ws_clients.discard(ws)
            try:
                await ws.close()
            except Exception:
                pass

    await asyncio.gather(*(_envoie(ws) for ws in clients))


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    _ws_clients.add(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        _ws_clients.discard(ws)


@app.get("/api/hotkey")
def get_hotkey():
    return {"hotkey": hotkey.current(), "hotkeys": hotkey.all_hotkeys()}


@app.post("/api/hotkey")
def post_hotkey(body: HotkeyBody):
    try:
        hk = hotkey.set_hotkey(body.hotkey, body.name)
    except Exception as e:
        return JSONResponse({"error": f"Raccourci invalide : {e}"}, status_code=400)
    return {"hotkey": hk, "name": body.name, "hotkeys": hotkey.all_hotkeys()}


class _FreshStatic(StaticFiles):
    def file_response(self, *args, **kwargs):
        resp = super().file_response(*args, **kwargs)
        resp.headers.update(_NO_CACHE)
        return resp


app.mount("/static", _FreshStatic(directory=chemins.STATIC), name="static")


def _open_browser():
    time.sleep(1.2)
    webbrowser.open("http://localhost:8765")


if __name__ == "__main__":
    import uvicorn
    threading.Thread(target=_open_browser, daemon=True).start()
    uvicorn.run(app, host="127.0.0.1", port=8765, log_level="warning")
