# -*- coding: utf-8 -*-
import threading

import chemins
import detect

MODELE = chemins.MODELES / "ocr_maison.onnx"
ALPHABET = chemins.MODELES / "ocr_maison_alphabet.txt"

_MEMOIRE = {}
_MEMOIRE_MAX = 400
_verrou = threading.Lock()


def available() -> bool:
    try:
        return detect.maison_disponible()
    except Exception:
        return False


def status() -> dict:
    return {"installed": available(), "loaded": detect.status().get("loaded"),
            "error": detect.status().get("error"), "memorisees": len(_MEMOIRE)}


def start() -> bool:
    return available() and detect.start()


def stop():
    vider_memoire()


def vider_memoire():
    _MEMOIRE.clear()


import os
SEUIL_CONFIANCE = float(os.environ.get('DNAREADER_SEUIL_MAISON', '0.90'))


def lis_une(image, avec_confiance=False):
    r = detect.lire_lignes_maison(image, [[0, 0, image.width, image.height]])
    if not r or r[0] is None:
        return (None, 0.0) if avec_confiance else None
    texte, conf = r[0] if isinstance(r[0], (tuple, list)) else (r[0], 1.0)
    return (texte, conf) if avec_confiance else texte


def refine_lines(img, lines, min_chars=1, a_relire=None):
    if not start():
        return lines
    import precise
    W, H = img.width, img.height
    a_lire, boites, connues = [], [], {}
    for i, line in enumerate(lines):
        box = line.get("box")
        if not box or box[2] < 6 or box[3] < 6:
            continue
        if a_relire is not None and not a_relire(line):
            continue
        x1, y1, x2, y2 = precise._pad(box, W, H)
        cle = precise._empreinte(img.crop((x1, y1, x2, y2)))
        if cle in _MEMOIRE:
            connues[i] = _MEMOIRE[cle]
            continue
        a_lire.append((i, cle))
        boites.append([x1, y1, x2, y2])

    lus = detect.lire_lignes_maison(img, boites) if boites else []
    for (i, cle), rep in zip(a_lire, lus):
        texte, conf = rep if isinstance(rep, (tuple, list)) else (rep, 1.0)
        if not texte or conf < SEUIL_CONFIANCE:
            continue
        with _verrou:
            if len(_MEMOIRE) >= _MEMOIRE_MAX:
                _MEMOIRE.pop(next(iter(_MEMOIRE)))
            _MEMOIRE[cle] = texte
        connues[i] = texte

    out = []
    for i, line in enumerate(lines):
        texte = connues.get(i)
        if not texte or len(texte) < min_chars:
            out.append(line)
            continue
        n = len(texte)
        bx, by, bw, bh = line["box"]
        cw = bw / n
        out.append({"text": texte, "box": line["box"], "alt": line.get("text", ""),
                    "chars": [[bx + i2 * cw, by, cw, bh] for i2 in range(n)]})
    return out
