# -*- coding: utf-8 -*-
import re

from dictionary import is_jp_char

LATIN = re.compile(r"[A-Za-z]")
SYMBOLES = re.compile(r"[\\|_^~`<>{}\[\]=+*#@$%&]")
FAUX_CADRES = "ロロ口一ー・．…"
CHIFFRE = re.compile(r"[0-9０-９]")


def _tout_katakana(texte: str) -> bool:
    utiles = [("ヘ" if c == "へ" else c)
              for c in texte if c not in "、。・！？「」 　"]
    if not utiles:
        return False
    jp_only = [c for c in utiles if is_jp_char(c)]
    if not jp_only:
        return False
    return all("ァ" <= c <= "ヶ" or c == "ー" for c in jp_only)


ICONES = "0OoDQ口ロ回目・．,.:~/\\|<>ZVX×+*=「『、。･"
TIRETS = "ー―－‐—–-"
KATAKANA = "ァ-ヶー"

RECOLLE = {
    "丿レ": "ル",
    "ノレ": "ル",
    "丿ヽ": "ハ",
    "ノヽ": "ハ",
}


def recolle(texte: str) -> str:
    t = texte or ""
    for coupe, entier in RECOLLE.items():
        t = t.replace(coupe, entier)
    return t


def nettoie(texte: str) -> str:
    t = recolle((texte or "").strip())
    while len(t) >= 4 and t[0] in ICONES + TIRETS:
        suite = t[1:].strip()
        if sum(1 for c in suite if is_jp_char(c)) < 3:
            break
        t = suite
    return t


def chiffres_et_pictogrammes(texte: str) -> bool:
    t = (texte or "").strip()
    if len(t) < 4:
        return False
    chiffres = sum(1 for c in t if c.isdigit())
    if chiffres * 2 < len(t):
        return False
    suite = plus_longue = 0
    for c in t:
        suite = suite + 1 if is_jp_char(c) else 0
        plus_longue = max(plus_longue, suite)
    return plus_longue < 2


def _parts(texte: str):
    jp = sum(1 for c in texte if is_jp_char(c))
    lat = len(LATIN.findall(texte))
    return jp, lat, len(texte)


def bascules_chiffres(texte: str) -> int:
    prec, n = None, 0
    for c in texte:
        genre = "c" if CHIFFRE.match(c) else ("j" if is_jp_char(c) else None)
        if genre is None:
            continue
        if prec and genre != prec:
            n += 1
        prec = genre
    return n


def _bribe_latine(t: str) -> bool:
    mot = t.strip()
    if not (2 <= len(mot) <= 5):
        return False
    if not mot.isascii() or not mot.isalpha():
        return False
    return mot.islower()


def raison_rejet(texte: str, dic=None, tagger=None) -> str:
    t = (texte or "").strip()
    if not t:
        return "vide"
    if chiffres_et_pictogrammes(t):
        return "rangée de compteurs, pas une phrase"
    jp, lat, n = _parts(t)

    if jp == 0:
        if _bribe_latine(t):
            return "bribe latine minuscule, typique d'une icône mal lue"
        return ""

    if n == 1 and t in FAUX_CADRES:
        return "signe isolé issu d'un cadre"

    if lat >= 2 and jp <= 2:
        return f"bribe latine autour de {jp} signe(s) japonais"

    if n <= 3 and lat >= 1 and jp <= 1:
        return "un signe japonais isolé contre du latin"

    bc = bascules_chiffres(t)
    if bc >= 3:
        return f"chiffres éparpillés dans le japonais ({bc} bascules)"

    chiffres = len(CHIFFRE.findall(t))
    if n >= 8 and chiffres > jp + 2:
        return f"relevé de valeurs ({chiffres} chiffres pour {jp} signes japonais)"

    if lat and lat / float(lat + jp) > 0.6:
        return f"dominée par du latin ({lat} latins pour {jp} japonais)"

    bascules, precedent = 0, None
    for c in t:
        genre = "l" if LATIN.match(c) else ("j" if is_jp_char(c) else None)
        if genre is None:
            continue
        if precedent and genre != precedent:
            bascules += 1
        precedent = genre
    if bascules >= 3:
        return f"latin et japonais entrelacés ({bascules} alternances)"

    sym = len(SYMBOLES.findall(t))
    if sym and sym / n > 0.12:
        return f"symboles parasites ({sym}/{n})"

    if t[0] in "/\\.,:;!?-–—" and n > 1:
        return "commence par un signe de ponctuation"

    if t[0] == "ー" and n > 1:
        return "commence par un prolongateur"

    if dic is not None and tagger is not None and n >= 4 and not _tout_katakana(t):
        try:
            import judge
            if judge.score(t, dic, tagger) < 0.45:
                return "ne correspond à aucun mot connu"
        except Exception:
            pass
    return ""


def garde_ligne(texte: str, dic=None, tagger=None) -> bool:
    return raison_rejet(texte, dic, tagger) == ""


def confiance(texte: str, encre: float, dic=None, tagger=None) -> float:
    t = (texte or "").strip()
    if not t:
        return 0.0
    jp, lat, n = _parts(t)
    if jp == 0:
        return 0.0

    note = 0.35
    if dic is not None and tagger is not None:
        try:
            import judge
            note = judge.score(t, dic, tagger)
        except Exception:
            pass
    if _tout_katakana(t):
        note = max(note, 0.72)

    if n >= 8:
        note += 0.12
    elif n <= 2:
        note -= 0.25

    if lat:
        note -= 0.15

    if 0.02 <= encre <= 0.25:
        note += 0.10
    elif encre < 0.008 or encre > 0.35:
        note -= 0.20

    return max(0.0, min(1.0, note))
