# -*- coding: utf-8 -*-
import base64
import glob
import io
import json
import os


def _plafond_fils():
    c = os.cpu_count() or 4
    return max(1, min(4, c // 2))


_FILS = _plafond_fils()
import sys

sys.stdout.reconfigure(encoding="utf-8")

MOYENNE = [0.485, 0.456, 0.406]
ECART = [0.229, 0.224, 0.225]
COTE_MAX = 960

_sess = _entree = None
_np = None

_rec = _rec_entree = None
_carac = None
import chemins

MODELES = str(chemins.MODELES)


def _chemin_modele():
    local = os.path.join(MODELES, "detection.onnx")
    if os.path.exists(local):
        return local
    try:
        import rapidocr_onnxruntime as r
        base = os.path.dirname(r.__file__)
        for m in glob.glob(os.path.join(base, "**", "*.onnx"), recursive=True):
            if "det" in os.path.basename(m).lower():
                return m
    except Exception:
        pass
    return None


def _charger_rec():
    global _rec, _rec_entree, _carac
    if _rec is not None:
        return True
    m = os.path.join(MODELES, "japan_rec.onnx")
    d = os.path.join(MODELES, "japan_dict.txt")
    if not (os.path.exists(m) and os.path.exists(d)):
        return False
    import onnxruntime as ort
    opts = ort.SessionOptions()
    opts.log_severity_level = 3
    opts.intra_op_num_threads = _FILS
    opts.inter_op_num_threads = 1
    _rec = ort.InferenceSession(m, opts, providers=["CPUExecutionProvider"])
    _rec_entree = _rec.get_inputs()[0].name
    with open(d, encoding="utf-8") as f:
        _carac = ["blank"] + f.read().splitlines() + [" "]
    return True


def _lire_ligne(img):
    np = _np
    from PIL import Image
    h = 32
    w = max(16, int(img.width * h / max(img.height, 1)))
    im = img.convert("RGB").resize((w, h), Image.BILINEAR)
    x = (np.asarray(im, np.float32) / 255.0 - 0.5) / 0.5
    x = np.transpose(x, (2, 0, 1))[None]
    y = _rec.run(None, {_rec_entree: x})[0][0]
    idx = y.argmax(axis=1)
    sortie, prec = [], -1
    for i in idx:
        if i != prec and i != 0 and i < len(_carac):
            sortie.append(_carac[i])
        prec = i
    return "".join(sortie).strip()


_mai = _mai_entree = None
_mai_alpha = None
MAISON_HAUTEUR = 48
MAISON_PAS = 8


def _charger_maison():
    global _mai, _mai_entree, _mai_alpha
    if _mai is not None:
        return True
    m = os.path.join(MODELES, "ocr_maison.onnx")
    a = os.path.join(MODELES, "ocr_maison_alphabet.txt")
    if not (os.path.exists(m) and os.path.exists(a)):
        return False
    import onnxruntime as ort
    opts = ort.SessionOptions()
    opts.log_severity_level = 3
    opts.intra_op_num_threads = _FILS
    opts.inter_op_num_threads = 1
    _mai = ort.InferenceSession(m, opts, providers=["CPUExecutionProvider"])
    _mai_entree = _mai.get_inputs()[0].name
    with open(a, encoding="utf-8") as f:
        _mai_alpha = f.read()
    return True


def _lire_ligne_maison(img):
    np = _np
    from PIL import Image
    g = img.convert("L")
    h = MAISON_HAUTEUR
    w = max(8, int(round(g.width * h / max(g.height, 1))))
    g = g.resize((w, h), Image.BILINEAR)
    x = (np.asarray(g, np.float32) / 127.5 - 1.0)[None, None]
    y = _mai.run(None, {_mai_entree: x})[0][0]
    colonnes = max(1, w // MAISON_PAS)
    y = y[:colonnes]
    m = y.max(axis=1, keepdims=True)
    p = np.exp(y - m)
    p /= p.sum(axis=1, keepdims=True)
    idx = y.argmax(axis=1)
    sortie, prec, certitudes = [], -1, []
    for k, i in enumerate(idx):
        if i != prec and i != 0 and i - 1 < len(_mai_alpha):
            sortie.append(_mai_alpha[i - 1])
            certitudes.append(float(p[k, i]))
        prec = i
    conf = float(sum(certitudes) / len(certitudes)) if certitudes else 0.0
    return "".join(sortie).strip(), round(conf, 4)


def _charger():
    global _sess, _entree, _np
    import numpy as np
    import onnxruntime as ort
    _np = np
    chemin = _chemin_modele()
    if not chemin:
        raise RuntimeError("modèle de détection introuvable")
    opts = ort.SessionOptions()
    opts.log_severity_level = 3
    opts.intra_op_num_threads = _FILS
    opts.inter_op_num_threads = 1
    _sess = ort.InferenceSession(chemin, opts, providers=["CPUExecutionProvider"])
    _entree = _sess.get_inputs()[0].name


def _carte(img):
    from PIL import Image
    np = _np
    w0, h0 = img.size
    ech = min(1.0, COTE_MAX / max(w0, h0))
    w = max(32, int(round(w0 * ech / 32)) * 32)
    h = max(32, int(round(h0 * ech / 32)) * 32)
    x = np.asarray(img.convert("RGB").resize((w, h), Image.BILINEAR),
                   dtype=np.float32) / 255.0
    x = (x - np.array(MOYENNE, dtype=np.float32)) / np.array(ECART, dtype=np.float32)
    x = np.transpose(x, (2, 0, 1))[None, ...].astype(np.float32)
    carte = np.asarray(_sess.run(None, {_entree: x})[0])[0, 0]
    return carte, w / float(w0), h / float(h0)


_carte_cache = {"cle": None, "val": None}


def _carte_partagee(img):
    np = _np
    petite = np.asarray(img.convert("L").resize((16, 16)))
    cle = (img.size, int(petite.sum()), int(petite[::3, ::3].sum()))
    if _carte_cache["cle"] != cle:
        _carte_cache["cle"] = cle
        _carte_cache["val"] = _carte(img)
    return _carte_cache["val"]


def _scores_carte(img, boites):
    return _scores(img, boites)


def _scores(img, boites):
    np = _np
    carte, sx, sy = _carte_partagee(img)
    H, W = carte.shape
    out = []
    for b in boites:
        try:
            x, y, w, h = (float(v) for v in b[:4])
            x0 = max(0, min(W - 1, int(x * sx)))
            y0 = max(0, min(H - 1, int(y * sy)))
            x1 = max(x0 + 1, min(W, int((x + w) * sx)))
            y1 = max(y0 + 1, min(H, int((y + h) * sy)))
            zone = carte[y0:y1, x0:x1]
            out.append(round(float((zone > 0.5).mean()), 4) if zone.size else 0.0)
        except Exception:
            out.append(None)
    return out


ANGLE_MINI = 0.0
AIRE_MINI = 120
MARGE_L = 1.15
MARGE_H = 1.60


def _boites_inclinees(carte, sx, sy):
    np = _np
    import cv2
    m = (carte > 0.3).astype(np.uint8) * 255
    m = cv2.dilate(m, cv2.getStructuringElement(cv2.MORPH_RECT, (9, 3)),
                   iterations=2)
    cont, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    out = []
    for c in cont:
        if cv2.contourArea(c) < AIRE_MINI:
            continue
        (cx, cy), (w, h), a = cv2.minAreaRect(c)
        if w < h:
            w, h, a = h, w, a + 90
        if a > 90:
            a -= 180
        if w < 30 or h < 10:
            continue
        out.append((cx / sx, cy / sy, w / sx * MARGE_L, h / sy * MARGE_H, a))
    out.sort(key=lambda r: -r[2] * r[3])
    return out


def _redresse(arr, cx, cy, w, h, a):
    import cv2
    M = cv2.getRotationMatrix2D((float(cx), float(cy)), float(a), 1.0)
    M[0, 2] += w / 2 - cx
    M[1, 2] += h / 2 - cy
    return cv2.warpAffine(arr, M, (max(8, int(round(w))), max(8, int(round(h)))),
                          flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)


def _recouvre(a, b) -> float:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    x0, y0 = max(ax, bx), max(ay, by)
    x1, y1 = min(ax + aw, bx + bw), min(ay + ah, by + bh)
    if x1 <= x0 or y1 <= y0:
        return 0.0
    return (x1 - x0) * (y1 - y0) / max(1.0, aw * ah)


def _juge_complet(img, deja, mode="rec", maxi=6):
    return {"scores": _scores_carte(img, deja),
            "lignes": _lignes_rattrapees(img, deja, mode, maxi)}


def _lignes_rattrapees(img, deja, mode="rec", maxi=6):
    np = _np
    from PIL import Image
    if _sess is None:
        return []
    lire = _lire_ligne if mode != "maison" else None
    if mode == "maison":
        if not _charger_maison():
            return []
    elif not _charger_rec():
        return []
    carte, sx, sy = _carte_partagee(img)
    arr = np.asarray(img.convert("RGB"))
    out = []
    for cx, cy, w, h, a in _boites_inclinees(carte, sx, sy):
        if abs(a) < ANGLE_MINI:
            continue
        x0, y0 = cx - w / 2, cy - h / 2
        if any(_recouvre((x0, y0, w, h), b) > 0.5 for b in deja):
            continue
        bout = _redresse(arr, cx, cy, w, h, a)
        try:
            im = Image.fromarray(bout)
            if mode == "maison":
                txt, conf = _lire_ligne_maison(im)
            else:
                txt, conf = lire(im), None
        except Exception:
            continue
        if not txt or len(txt.strip()) < 2:
            continue
        if not any(0x3040 <= ord(c) <= 0x30FF or 0x4E00 <= ord(c) <= 0x9FFF
                   or 0xFF66 <= ord(c) <= 0xFF9D for c in txt):
            continue
        out.append({"text": txt, "angle": round(float(a), 1),
                    "box": [round(x0, 1), round(y0, 1), round(w, 1), round(h, 1)],
                    "conf": conf})
        if len(out) >= maxi:
            break
    return out


def main():
    manque = ""
    try:
        _charger()
    except Exception as e:
        manque = f"{e.__class__.__name__}: {e}"
        import numpy as np
        global _np
        _np = np
    print(json.dumps({"ready": True, "detecteur": not manque,
                      "sans_detecteur": manque}), flush=True)

    from PIL import Image
    for ligne in sys.stdin:
        ligne = ligne.strip()
        if not ligne:
            continue
        try:
            req = json.loads(ligne)
        except Exception:
            continue
        if req.get("quit"):
            return
        try:
            img = Image.open(io.BytesIO(base64.b64decode(req["img"])))
            if req.get("mode") == "maison":
                if not _charger_maison():
                    rep = {"error": "modele maison absent"}
                else:
                    lus = [_lire_ligne_maison(img.crop(tuple(int(v) for v in b)))
                           for b in (req.get("boxes") or [])]
                    rep = {"textes": [t for t, _ in lus],
                           "confiances": [c for _, c in lus]}
            elif req.get("mode") == "rec":
                if not _charger_rec():
                    rep = {"error": "modele de reconnaissance japonaise absent"}
                else:
                    rep = {"textes": [_lire_ligne(img.crop(tuple(int(v) for v in b)))
                                      for b in (req.get("boxes") or [])]}
            elif req.get("mode") == "complet":
                if _sess is None:
                    rep = {"scores": [None] * len(req.get("boxes") or []),
                           "lignes": []}
                else:
                    rep = _juge_complet(img, req.get("boxes") or [],
                                        req.get("moteur") or "rec",
                                        int(req.get("maxi") or 6))
            elif req.get("mode") == "rattrapees":
                rep = {"lignes": _lignes_rattrapees(
                    img, req.get("boxes") or [], req.get("moteur") or "rec",
                    int(req.get("maxi") or 6))}
            elif _sess is None:
                rep = {"scores": [None] * len(req.get("boxes") or [])}
            else:
                rep = {"scores": _scores(img, req.get("boxes") or [])}
        except Exception as e:
            rep = {"error": f"{e.__class__.__name__}: {e}"}
        print(json.dumps(rep), flush=True)


if __name__ == "__main__":
    main()
