# -*- coding: utf-8 -*-
import difflib
import json
import threading
import time

import chemins

DOSSIER = chemins.DONNEES / "recolte"
INDEX = DOSSIER / "lignes.jsonl"

RESSEMBLANCE = 0.98
LONGUEUR_MIN = 2
LONGUEUR_MAX = 40
MAX_LIGNES = 20000

_vues = {}
_VUES_MAX = 3000
_n = None
_verrou = threading.Lock()


from dictionary import is_jp_char


def _est_jp(t: str) -> bool:
    return any(is_jp_char(c) for c in (t or ""))


def recevable(texte: str) -> bool:
    t = (texte or "").replace(" ", "").replace("　", "")
    return bool(t) and LONGUEUR_MIN <= len(t) <= LONGUEUR_MAX and _est_jp(t)


def compte() -> int:
    global _n
    if _n is None:
        _n = 0
        if INDEX.exists():
            try:
                with INDEX.open(encoding="utf-8") as f:
                    _n = sum(1 for _ in f)
            except Exception:
                _n = 0
    return _n


def etat() -> dict:
    return {"lignes": compte(), "max": MAX_LIGNES, "dossier": str(DOSSIER)}


def _lu() -> dict:
    try:
        return json.loads(chemins.REGLAGES.read_text("utf-8"))
    except Exception:
        return {}


def voulue() -> bool:
    return bool(_lu().get("recolte", False))


def retiens(actif: bool):
    d = _lu()
    d["recolte"] = bool(actif)
    try:
        chemins.REGLAGES.write_text(
            json.dumps(d, indent=2, ensure_ascii=False), "utf-8")
    except Exception:
        pass


def accord(a: str, b: str) -> bool:
    a = (a or "").replace(" ", "").replace("　", "")
    b = (b or "").replace(" ", "").replace("　", "")
    if not a or a != a.strip() or len(a) < LONGUEUR_MIN or len(a) > LONGUEUR_MAX:
        return False
    if not _est_jp(a):
        return False
    if a == b:
        return True
    return difflib.SequenceMatcher(None, a, b).ratio() >= RESSEMBLANCE


_dossier_pret = False


def _assure_le_dossier():
    global _dossier_pret
    if not _dossier_pret:
        DOSSIER.mkdir(parents=True, exist_ok=True)
        _dossier_pret = True


def garde(img, boite, texte_windows: str, texte_ppocr: str, jeu: str = ""):
    if not accord(texte_windows, texte_ppocr):
        return None
    if compte() >= MAX_LIGNES:
        return None
    try:
        import precise
        x1, y1, x2, y2 = precise._pad(boite, img.width, img.height)
        bout = img.crop((x1, y1, x2, y2))
        if bout.width < 16 or bout.height < 10:
            return None
        cle = precise._empreinte(bout)
        with _verrou:
            if cle in _vues:
                return None
            if len(_vues) >= _VUES_MAX:
                _vues.pop(next(iter(_vues)))
            _vues[cle] = True
        texte = (texte_windows or "").replace(" ", "").strip()
        nom = f"{int(time.time()*1000):013d}_{abs(hash(cle)) % 10000:04d}.png"
        _assure_le_dossier()
        bout.save(DOSSIER / nom)
        e = {"image": nom, "texte": texte}
        if jeu:
            e["jeu"] = jeu
        return e
    except Exception:
        return None


def moisson(img, lignes, textes_ppocr, jeu: str = "") -> int:
    entrees = []
    for l, tp in zip(lignes, textes_ppocr or []):
        if not tp or not l.get("box"):
            continue
        e = garde(img, l["box"], l.get("text", ""), tp, jeu)
        if e:
            entrees.append(e)
    if not entrees:
        return 0
    _assure_le_dossier()
    with _verrou:
        try:
            with INDEX.open("a", encoding="utf-8") as f:
                for e in entrees:
                    f.write(json.dumps(e, ensure_ascii=False) + "\n")
        except Exception:
            return 0
        global _n
        _n = compte() + len(entrees)
    return len(entrees)
