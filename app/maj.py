# -*- coding: utf-8 -*-
import hashlib
import json
import os
import re
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request

import chemins
import version

FICHIER_ETAT = chemins.DONNEES / "maj.json"
DOSSIER = chemins.DONNEES / "maj"

API_BASE = "https://api.github.com"

HOTES_AUTORISES = ("github.com", "objects.githubusercontent.com",
                   "release-assets.githubusercontent.com")

DELAI_RESEAU = 8.0
ENTRE_DEUX_CONTROLES = int(os.environ.get("DNAREADER_ENTRE_CONTROLES", "3600"))
MORCEAU = 256 * 1024

_verrou = threading.RLock()
_trouve = {}
_phase = "rien"
_recus = 0
_erreur = ""
_fil = None

_generation = 0


def _lis() -> dict:
    try:
        d = json.loads(FICHIER_ETAT.read_text(encoding="utf-8"))
    except Exception:
        d = {}
    return {"dernier_controle": float(d.get("dernier_controle") or 0),
            "version_ignoree": str(d.get("version_ignoree") or ""),
            "auto": bool(d.get("auto", True)),
            "trouve": d.get("trouve") if isinstance(d.get("trouve"), dict) else {}}


def _ecris(**champs):
    d = _lis()
    d.update(champs)
    try:
        FICHIER_ETAT.write_text(json.dumps(d, ensure_ascii=False, indent=1),
                                encoding="utf-8")
    except Exception:
        pass
    return d


def en_tuple(v: str):
    if not v:
        return None
    m = re.match(r"v?(\d+(?:\.\d+)*)", str(v).strip())
    if not m:
        return None
    bouts = [int(x) for x in m.group(1).split(".")][:4]
    while len(bouts) < 3:
        bouts.append(0)
    return tuple(bouts)


def plus_recente(distante: str, locale: str) -> bool:
    a, b = en_tuple(distante), en_tuple(locale)
    return bool(a and b and a > b)


def possible() -> bool:
    return bool(chemins.EMPAQUETEE and getattr(version, "DEPOT_RELEASES", ""))


def _demande_a_github() -> dict:
    url = f"{API_BASE}/repos/{version.DEPOT_RELEASES}/releases/latest"
    req = urllib.request.Request(url, headers={
        "User-Agent": f"{version.NOM}/{version.VERSION}",
        "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=DELAI_RESEAU) as r:
        return json.loads(r.read().decode("utf-8"))


def nom_sain(nom: str) -> str:
    nom = (nom or "").replace("\\", "/").split("/")[-1].strip()
    if not re.fullmatch(r"[A-Za-z0-9._-]{1,120}", nom) or nom.startswith("."):
        return ""
    return nom


def _url_sure(url: str) -> bool:
    from urllib.parse import urlparse
    u = urlparse(url or "")
    if u.scheme != "https":
        return u.scheme == "http" and u.hostname in ("127.0.0.1", "localhost")
    return (u.hostname or "").lower() in HOTES_AUTORISES


class _RedirectionSure(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not _url_sure(newurl):
            raise urllib.error.HTTPError(
                newurl, code, "redirection hors de GitHub : refusee",
                headers, fp)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_ouvreur = urllib.request.build_opener(_RedirectionSure())


def _dit_pourquoi(e: Exception) -> str:
    code = getattr(e, "code", None)
    if code == 404:
        return "aucune version publiee pour l'instant"
    if code == 403:
        return "trop de demandes a GitHub : reessaie dans une heure"
    if code:
        return f"GitHub a repondu {code}"
    return "serveur injoignable : verifie ta connexion"


def _pieces(release: dict) -> tuple:
    setup = somme = None
    for a in release.get("assets") or []:
        nom = nom_sain(a.get("name") or "")
        if not nom:
            continue
        a = dict(a, name=nom)
        if nom.endswith(".exe.sha256") or nom.endswith(".exe.sha256.txt"):
            somme = a
        elif nom.lower().startswith(version.NOM.lower() + "-setup") \
                and nom.lower().endswith(".exe"):
            setup = a
    return setup, somme


def reprend():
    global _trouve, _phase
    t = _lis()["trouve"]
    if not t or not plus_recente(t.get("tag", ""), version.VERSION):
        with _verrou:
            _trouve = {}
        purge()
        return
    with _verrou:
        if not _trouve:
            _trouve = dict(t)
            _phase = "prete" if (DOSSIER / t.get("setup_nom", "_")).exists() \
                     else "trouvee"
    purge()


def cherche(force=False) -> dict:
    global _trouve, _phase, _erreur
    if not possible():
        return etat()
    d = _lis()
    if not force:
        if not d["auto"]:
            return etat()
        if time.time() - d["dernier_controle"] < ENTRE_DEUX_CONTROLES:
            reprend()
            return etat()
    try:
        release = _demande_a_github()
    except Exception as e:
        if force:
            with _verrou:
                _erreur = _dit_pourquoi(e)
        return etat()

    _ecris(dernier_controle=time.time())
    tag = release.get("tag_name") or ""
    if not plus_recente(tag, version.VERSION):
        with _verrou:
            _trouve = {}
            if _phase in ("rien", "trouvee"):
                _phase = "rien"
            _erreur = ""
        _ecris(trouve={})
        purge()
        return etat()

    setup, somme = _pieces(release)
    if setup and somme and not (
            _url_sure(setup.get("browser_download_url", ""))
            and _url_sure(somme.get("browser_download_url", ""))):
        with _verrou:
            _trouve = {}
            _erreur = "fichier annonce hors de GitHub : refuse"
        return etat()
    if not setup or not somme:
        with _verrou:
            _trouve = {}
            _erreur = "release incomplète (installateur ou empreinte absent)"
        return etat()

    with _verrou:
        if (_trouve.get("tag") == tag
                and _phase in ("telechargement", "prete")):
            return etat()

        _trouve = {
            "version": (en_tuple(tag) and ".".join(str(x) for x in en_tuple(tag))) or tag,
            "tag": tag,
            "titre": release.get("name") or tag,
            "notes": release.get("body") or "",
            "url": release.get("html_url") or "",
            "setup_url": setup.get("browser_download_url") or "",
            "setup_nom": setup.get("name") or "",
            "octets": int(setup.get("size") or 0),
            "somme_url": somme.get("browser_download_url") or "",
        }
        _phase = "trouvee"
        _erreur = ""
        a_garder = dict(_trouve)
    _ecris(trouve=a_garder)
    purge()
    return etat()


def _telecharge_texte(url: str) -> str:
    req = urllib.request.Request(url, headers={
        "User-Agent": f"{version.NOM}/{version.VERSION}"})
    with _ouvreur.open(req, timeout=DELAI_RESEAU) as r:
        return r.read(65536).decode("utf-8", "replace")


def _empreinte_attendue(texte: str) -> str:
    m = re.search(r"\b([0-9a-fA-F]{64})\b", texte or "")
    return m.group(1).lower() if m else ""


class _Perime(Exception):
    pass


def _jette(fichier):
    try:
        if fichier.exists():
            fichier.unlink()
    except Exception:
        pass


def _perime(ma_generation: int) -> bool:
    with _verrou:
        return _generation != ma_generation


def _travail_telechargement(ma_generation: int):
    global _phase, _recus, _erreur
    with _verrou:
        t = dict(_trouve)
    cible = DOSSIER / t["setup_nom"]
    partiel = cible.with_name(f"{cible.name}.{ma_generation}.partiel")
    try:
        DOSSIER.mkdir(parents=True, exist_ok=True)
        attendue = _empreinte_attendue(_telecharge_texte(t["somme_url"]))
        if not attendue:
            raise RuntimeError("empreinte publiée illisible")

        req = urllib.request.Request(t["setup_url"], headers={
            "User-Agent": f"{version.NOM}/{version.VERSION}"})
        h = hashlib.sha256()
        recus = 0
        annonce = max(int(t.get("octets") or 0), 0)
        plafond = int(annonce * 1.05) + (1 << 20) if annonce else (400 << 20)
        with _ouvreur.open(req, timeout=DELAI_RESEAU) as r, \
                open(partiel, "wb") as f:
            while True:
                if _perime(ma_generation):
                    raise _Perime()
                bloc = r.read(MORCEAU)
                if not bloc:
                    break
                f.write(bloc)
                h.update(bloc)
                recus += len(bloc)
                if recus > plafond:
                    raise RuntimeError(
                        f"le fichier depasse la taille annoncee "
                        f"({recus} octets recus pour {annonce} annonces)")
                with _verrou:
                    _recus = recus

        obtenue = h.hexdigest()
        if obtenue != attendue:
            raise RuntimeError(
                f"empreinte differente : attendu {attendue[:12]}…, "
                f"obtenu {obtenue[:12]}…")

        if _perime(ma_generation):
            raise _Perime()
        if cible.exists():
            cible.unlink()
        os.replace(partiel, cible)
        with _verrou:
            if _generation == ma_generation:
                _phase = "prete"
                _erreur = ""
    except _Perime:
        _jette(partiel)
    except Exception as e:
        _jette(partiel)
        with _verrou:
            if _generation == ma_generation:
                _phase = "echec"
                _erreur = str(e)
                _recus = 0


def telecharge() -> dict:
    global _fil, _phase, _recus, _erreur, _generation
    with _verrou:
        if not _trouve:
            return {"ok": False, "raison": "aucune mise a jour proposee"}
        if _phase == "telechargement":
            return {"ok": True, "deja": True}
        if _phase == "prete" and (DOSSIER / _trouve["setup_nom"]).exists():
            return {"ok": True, "deja": True}
        _generation += 1
        ma_generation = _generation
        _phase = "telechargement"
        _recus = 0
        _erreur = ""
        _fil = threading.Thread(target=_travail_telechargement,
                                args=(ma_generation,), daemon=True)
        _fil.start()
    return {"ok": True}


def annule() -> dict:
    global _phase, _generation, _recus
    with _verrou:
        _generation += 1
        _recus = 0
        if _phase == "telechargement":
            _phase = "trouvee"
    return {"ok": True}


def installe() -> dict:
    with _verrou:
        t = dict(_trouve)
        phase = _phase
    if phase != "prete" or not t:
        return {"ok": False, "raison": "aucune mise a jour prete"}
    if _lis()["version_ignoree"] == t.get("version"):
        return {"ok": False, "raison": "cette version a ete refusee"}
    cible = DOSSIER / t["setup_nom"]
    if not cible.exists():
        return {"ok": False, "raison": "le fichier verifie a disparu"}
    if t["octets"] and cible.stat().st_size != t["octets"]:
        return {"ok": False, "raison": "le fichier verifie a change de taille"}

    drapeaux = 0
    if os.name == "nt":
        drapeaux = (getattr(subprocess, "DETACHED_PROCESS", 0)
                    | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
    try:
        subprocess.Popen([str(cible), "/SILENT", "/RELANCE=1"],
                         creationflags=drapeaux, close_fds=True,
                         cwd=str(DOSSIER))
    except Exception as e:
        return {"ok": False, "raison": f"l'installateur n'a pas demarre : {e}"}
    return {"ok": True, "version": t["version"]}


def ignore(v: str = "") -> dict:
    with _verrou:
        v = v or (_trouve.get("version") or "")
    if not v:
        return {"ok": False, "raison": "aucune version a ignorer"}
    _ecris(version_ignoree=v)
    return {"ok": True, "version_ignoree": v}


def auto(actif: bool) -> dict:
    _ecris(auto=bool(actif))
    return {"ok": True, "auto": bool(actif)}


def purge():
    with _verrou:
        nom = _trouve.get("setup_nom") or ""
        garder = {nom, f"{nom}.{_generation}.partiel"} - {""}
    try:
        for f in DOSSIER.glob("*"):
            if f.is_file() and f.name not in garder:
                try:
                    f.unlink()
                except Exception:
                    pass
    except Exception:
        pass


def etat() -> dict:
    d = _lis()
    with _verrou:
        t = dict(_trouve)
        phase, recus, erreur = _phase, _recus, _erreur
    v = t.get("version") or ""
    ignoree = bool(v and v == d["version_ignoree"])
    return {
        "possible": possible(),
        "version_locale": version.VERSION,
        "version_distante": v,
        "titre": t.get("titre", ""),
        "notes": t.get("notes", ""),
        "url": t.get("url", ""),
        "octets": t.get("octets", 0),
        "ignoree": ignoree,
        "auto": d["auto"],
        "dernier_controle": d["dernier_controle"],
        "phase": phase,
        "recus": recus,
        "erreur": erreur,
    }


def au_demarrage():
    if not possible():
        return

    def _travail():
        reprend()
        cherche(force=False)

    threading.Thread(target=_travail, daemon=True).start()
