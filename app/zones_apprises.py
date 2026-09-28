# -*- coding: utf-8 -*-
import json
import threading

import chemins

_verrou = threading.Lock()
_cache = None


def _charge() -> dict:
    global _cache
    if _cache is not None:
        return _cache
    try:
        _cache = json.loads(chemins.ZONES_APPRISES.read_text("utf-8"))
        if not isinstance(_cache, dict):
            _cache = {}
    except Exception:
        _cache = {}
    return _cache


def _ecris():
    try:
        chemins.ZONES_APPRISES.write_text(
            json.dumps(_cache, ensure_ascii=False, indent=1), "utf-8")
    except Exception as e:
        print(f"[zones] enregistrement impossible : {e}")


def pour(jeu: str) -> list:
    if not jeu:
        return []
    with _verrou:
        return list(_charge().get(jeu) or [])


def toutes() -> dict:
    with _verrou:
        return {k: list(v) for k, v in _charge().items()}


def _proche(a, b, tol=0.01, recouvrement=0.4) -> bool:
    if all(abs(x - y) <= tol for x, y in zip(a[:4], b[:4])):
        return True
    if len(a) < 4 or len(b) < 4:
        return False
    ax, ay, aw, ah = a[:4]
    bx, by, bw, bh = b[:4]
    ix = max(0.0, min(ax + aw, bx + bw) - max(ax, bx))
    iy = max(0.0, min(ay + ah, by + bh) - max(ay, by))
    commun = ix * iy
    if commun <= 0:
        return False
    union = aw * ah + bw * bh - commun
    return union > 0 and commun / union >= recouvrement


def ajoute(jeu: str, rect, texte: str) -> dict:
    texte = (texte or "").strip()
    if not jeu or not texte or not rect or len(rect) < 4:
        return {"ok": False, "error": "jeu, rectangle et texte sont nécessaires"}
    rect = [max(0.0, min(1.0, float(v))) for v in rect[:4]]
    if rect[2] <= 0.001 or rect[3] <= 0.001:
        return {"ok": False, "error": "rectangle trop petit"}
    with _verrou:
        d = _charge()
        liste = d.setdefault(jeu, [])
        for z in liste:
            if _proche(z.get("rect") or [], rect):
                z["texte"] = texte
                _ecris()
                return {"ok": True, "remplace": True, "count": len(liste)}
        liste.append({"rect": rect, "texte": texte})
        _ecris()
        return {"ok": True, "remplace": False, "count": len(liste)}


def retire(jeu: str, rect) -> dict:
    with _verrou:
        d = _charge()
        liste = d.get(jeu) or []
        avant = len(liste)
        d[jeu] = [z for z in liste if not _proche(z.get("rect") or [], rect)]
        if not d[jeu]:
            d.pop(jeu, None)
        _ecris()
        return {"ok": True, "retire": avant - len(d.get(jeu, []))}


def compte() -> int:
    with _verrou:
        return sum(len(v) for v in _charge().values())
