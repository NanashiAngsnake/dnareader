# -*- coding: utf-8 -*-

import asyncio
import time
from collections import deque

import fugashi
from PIL import Image

import apprentissage
import corrections
import detect
import judge
import maison
import ocr
import plausible
import precise
import zones_apprises
from dictionary import Dictionary, is_jp_char

PERF = {}
def _recolte_voulue() -> bool:
    try:
        import recolte
        return recolte.voulue()
    except Exception:
        return False


RECOLTE_ACTIVE = _recolte_voulue()
RECOLTE_PAR_IMAGE = 20


def _recolte():
    try:
        import recolte
        return recolte
    except Exception:
        return None
REJETS = deque(maxlen=40)

print("Chargement du dictionnaire (premiere fois : construction de la base)...")
DICT = Dictionary()
TAGGER = fugashi.Tagger()
print("Pret.")


def _annotate(lines):
    gardees = []
    for line in lines:
        propre = plausible.nettoie(line.get("text", ""))
        if propre != line.get("text"):
            n_avant = max(len(line["text"]), 1)
            bx, by, bw, bh = line.get("box") or [0, 0, 0, 0]
            oté = len(line["text"]) - len(propre)
            line["box"] = [bx + bw * oté / n_avant, by, bw * len(propre) / n_avant, bh]
            line["chars"] = (line.get("chars") or [])[oté:]
            line["text"] = propre
        motif = plausible.raison_rejet(line.get("text", ""), DICT, TAGGER)
        if motif:
            print(f"[filtre] rejet « {line.get('text','')} » : {motif}")
            REJETS.appendleft({"texte": line.get("text", ""), "motif": motif,
                               "quand": round(time.time(), 1)})
            _apprend(line, 0, 0.4, "filtre")
            continue
        gardees.append(line)
    lines = gardees
    for line in lines:
        fixed = corrections.apply(line["text"])
        if fixed != line["text"]:
            corrections.note_hits(line["text"], fixed)
            line["corrected"] = True
            line["text"] = fixed
        line["jp"] = any(is_jp_char(c) for c in line["text"])
        line["words"] = segment(line["text"]) if line["jp"] else []
        c = plausible.confiance(line["text"], line.get("encre", 0.05), DICT, TAGGER)
        det = line.get("det")
        if det is not None:
            c = min(1.0, c + 0.25) if det >= 0.20 else max(0.0, c - 0.20)
        v = _traits_ligne(line)
        line["traits"] = v
        appris = apprentissage.predit(v) if apprentissage.pret() else None
        if appris is not None:
            line["appris"] = round(appris, 3)
            if appris < 0.5:
                c = min(c, 0.5)
            elif appris > 0.85:
                c = max(c, 0.85)
        line["conf"] = round(c, 3)
    return lines


ZONE_HAUTEUR_VISEE = 96
ZONE_RESSEMBLANCE = 0.5


def _ressemblance(a: str, b: str) -> float:
    if a == b:
        return 1.0
    if not a or not b:
        return 0.0
    reste = list(b)
    communs = 0
    for c in a:
        if c in reste:
            reste.remove(c)
            communs += 1
    return (2 * communs) / (len(a) + len(b))


async def _lignes_apprises(img, lines, enhance, jeu, region):
    zones = zones_apprises.pour(jeu) if jeu else []
    if not zones:
        return lines
    W, H = img.width, img.height
    fx, fy, fw, fh = (region[:4] if region and len(region) >= 4 else (0.0, 0.0, 1.0, 1.0))
    ajoutees = 0
    for z in zones:
        try:
            zx, zy, zw, zh = (float(v) for v in z["rect"][:4])
            texte_appris = str(z.get("texte") or "")
        except Exception:
            continue
        if not texte_appris or fw <= 0 or fh <= 0:
            continue
        rx, ry = (zx - fx) / fw, (zy - fy) / fh
        rw, rh = zw / fw, zh / fh
        x, y = int(rx * W), int(ry * H)
        w, h = int(rw * W), int(rh * H)
        if w < 8 or h < 6 or x + w <= 0 or y + h <= 0 or x >= W or y >= H:
            continue
        x, y = max(0, x), max(0, y)
        w, h = min(w, W - x), min(h, H - y)

        encre = ocr.taux_encre(img, [x, y, w, h])
        if not (ocr.ENCRE_MIN <= encre <= ocr.ENCRE_MAX):
            continue
        if any(_recouvre(l.get("box"), (x, y, w, h)) for l in lines):
            continue

        m = max(6, h * 0.35)
        crop = img.crop((max(0, int(x - m)), max(0, int(y - m)),
                         min(W, int(x + w + m)), min(H, int(y + h + m))))
        k = min(8.0, max(1.0, ZONE_HAUTEUR_VISEE / max(h, 1.0)))
        if k > 1.01:
            crop = crop.resize((int(crop.width * k), int(crop.height * k)),
                               Image.LANCZOS)
        lu = ""
        try:
            relues = await ocr._ocr_once(crop, enhance, scale_hint=1.0)
            lu = "".join(r.get("text", "") for r in relues).strip()
        except Exception:
            pass

        if not lu:
            continue
        proche = _ressemblance(lu, texte_appris) >= ZONE_RESSEMBLANCE
        texte = texte_appris if proche else lu
        n = max(len(texte), 1)
        lines.append({
            "text": texte,
            "box": [float(x), float(y), float(w), float(h)],
            "chars": [[x + i * w / n, y, w / n, h] for i in range(n)],
            "conf": 1.0 if proche or not lu else 0.8,
            "encre": round(encre, 4),
            "apprise": True,
        })
        ajoutees += 1
        print(f"[appris] « {texte} » rendu a un endroit appris"
              + ("" if proche or not lu else f" (relu « {lu} », le libelle a change)"))
    if ajoutees:
        PERF["apprises"] = ajoutees
    return lines


async def lit_un_endroit(img, rect, enhance: str = "auto") -> str:
    try:
        zx, zy, zw, zh = (float(v) for v in rect[:4])
    except Exception:
        return ""
    W, H = img.width, img.height
    x, y, w, h = int(zx * W), int(zy * H), int(zw * W), int(zh * H)
    if w < 8 or h < 6:
        return ""
    x, y = max(0, x), max(0, y)
    w, h = min(w, W - x), min(h, H - y)
    m = max(6, h * 0.35)
    crop = img.crop((max(0, int(x - m)), max(0, int(y - m)),
                     min(W, int(x + w + m)), min(H, int(y + h + m))))
    k = min(8.0, max(1.0, ZONE_HAUTEUR_VISEE / max(h, 1.0)))
    if k > 1.01:
        crop = crop.resize((int(crop.width * k), int(crop.height * k)), Image.LANCZOS)
    try:
        relues = await ocr._ocr_once(crop, enhance, scale_hint=1.0)
        return "".join(r.get("text", "") for r in relues).strip()
    except Exception:
        return ""


def _recouvre(box, zone) -> bool:
    if not box:
        return False
    ax, ay, aw, ah = (float(v) for v in box[:4])
    bx, by, bw, bh = zone
    ix = max(0.0, min(ax + aw, bx + bw) - max(ax, bx))
    iy = max(0.0, min(ay + ah, by + bh) - max(ay, by))
    petite = min(aw * ah, bw * bh) or 1
    return (ix * iy) / petite > 0.35


MAXI_INCLINEES = 6

_PENCHEES = []
_MOTEUR_INCLINE = ["rec"]


def _ajoute_rattrapees(img, lines, jeu: str, engine: str):
    _MOTEUR_INCLINE[0] = "maison" if engine == "maison" else "rec"
    for t in list(_PENCHEES):
        txt = (t.get("text") or "").strip()
        if not txt:
            continue
        x, y, w, h = t.get("box") or [0, 0, 0, 0]
        n = max(len(txt), 1)
        lines.append({
            "text": txt,
            "box": [x, y, w, h],
            "chars": [[x + i * w / n, y, w / n, h] for i in range(n)],
            "incline": t.get("angle"),
        })
    return lines


async def _read(img, enhance: str, engine: str, jeu: str = "", region=None):
    t_debut = time.perf_counter()
    lines = await ocr.ocr_image(img, enhance=enhance)
    PERF["ocr_ms"] = round((time.perf_counter() - t_debut) * 1000)
    lines = ocr.sans_encre(img, lines)
    t0 = time.perf_counter()
    lines = await asyncio.to_thread(_juge_detecteur, img, lines)
    PERF["detecteur_ms"] = round((time.perf_counter() - t0) * 1000)
    t0 = time.perf_counter()
    lines = await asyncio.to_thread(_ajoute_rattrapees, img, lines, jeu, engine)
    PERF["incline_ms"] = round((time.perf_counter() - t0) * 1000)
    t0 = time.perf_counter()
    lines = await _relire_de_pres(img, lines, enhance)
    PERF["zoom_ms"] = round((time.perf_counter() - t0) * 1000)
    t0 = time.perf_counter()
    lines = await _lignes_apprises(img, lines, enhance, jeu, region)
    PERF["apprises_ms"] = round((time.perf_counter() - t0) * 1000)
    PERF["relecture_ms"] = 0
    t0 = time.perf_counter()
    lines = await asyncio.to_thread(_relire_ppocr, img, lines, jeu)
    PERF["ppocr_ms"] = round((time.perf_counter() - t0) * 1000)
    if engine == "maison" and maison.available():
        try:
            t0 = time.perf_counter()
            lines = await asyncio.to_thread(maison.refine_lines, img, lines,
                                            1, _merite_relecture)
            PERF["relecture_ms"] = round((time.perf_counter() - t0) * 1000)
            _arbitrate(lines)
        except Exception as e:
            print(f"[maison] indisponible, repli sur Windows OCR ({e})")
    elif engine == "precise" and precise.available():
        try:
            t0 = time.perf_counter()
            lines = await asyncio.to_thread(precise.refine_lines, img, lines,
                                            1, _merite_relecture)
            PERF["relecture_ms"] = round((time.perf_counter() - t0) * 1000)
            _arbitrate(lines)
        except Exception as e:
            print(f"[precise] indisponible, repli sur Windows OCR ({e})")
    t0 = time.perf_counter()
    out = _annotate(lines)
    PERF["annotation_ms"] = round((time.perf_counter() - t0) * 1000)
    PERF["total_ms"] = round((time.perf_counter() - t_debut) * 1000)
    PERF["lignes"] = len(out)
    PERF["moteur"] = engine
    return out


SEUIL_DETECTION = 0.01


HAUTEUR_CONFORT = 34
ZOOM_MAX_LIGNES = 6
ZOOM_HAUTEUR_VISEE = 72


async def _relire_de_pres(img, lines, enhance):
    if not lines:
        return lines
    cibles = []
    for i, l in enumerate(lines):
        try:
            x, y, w, h = (float(v) for v in (l.get("box") or [0, 0, 0, 0])[:4])
        except Exception:
            continue
        if w < 8 or h < 6:
            continue
        if h < HAUTEUR_CONFORT:
            cibles.append((i, x, y, w, h))
    if not cibles:
        return lines
    cibles.sort(key=lambda c: c[4])
    for i, x, y, w, h in cibles[:ZOOM_MAX_LIGNES]:
        m = max(6, h * 0.5)
        boite = (max(0, int(x - m)), max(0, int(y - m)),
                 min(img.width, int(x + w + m)), min(img.height, int(y + h + m)))
        if boite[2] - boite[0] < 8 or boite[3] - boite[1] < 8:
            continue
        crop = img.crop(boite)
        k = min(6.0, max(1.0, ZOOM_HAUTEUR_VISEE / max(h, 1.0)))
        if k > 1.01:
            crop = crop.resize((int(crop.width * k), int(crop.height * k)),
                               Image.LANCZOS)
        try:
            relues = await ocr._ocr_once(crop, enhance, scale_hint=1.0)
        except Exception:
            continue
        txt = "".join(r.get("text", "") for r in relues).strip()
        actuel = lines[i].get("text", "")
        if not txt or txt == actuel:
            continue
        meilleur, _, _ = judge.pick(txt, actuel, DICT, TAGGER, MARGE_ZOOM)
        if meilleur == actuel:
            continue
        print(f"[zoom] « {actuel} » -> « {meilleur} » (ligne de {int(h)} px)")
        lines[i]["avant_zoom"] = actuel
        lines[i]["text"] = meilleur
        bx, by, bw, bh = lines[i]["box"]
        n = max(len(meilleur), 1)
        lines[i]["chars"] = [[bx + j * bw / n, by, bw / n, bh] for j in range(n)]
        lines[i]["zoom"] = True
    return lines


MARGE_ZOOM = 0.05


def _juge_detecteur(img, lines):
    if not lines:
        return lines
    try:
        boites = [l.get("box") or [0, 0, 0, 0] for l in lines]
        notes, penchees = detect.juge_complet(img, boites, _MOTEUR_INCLINE[0],
                                              MAXI_INCLINEES)
    except Exception:
        return lines
    _PENCHEES.clear()
    _PENCHEES.extend(penchees)
    gardees = []
    for line, n in zip(lines, notes):
        if n is None and line.pop("sature", False):
            continue
        if n is not None:
            line["det"] = n
            line.pop("sature", None)
            if n < SEUIL_DETECTION:
                print(f"[detecteur] rejet « {line.get('text','')} » : "
                      f"aucune écriture à cet endroit ({n:.2f})")
                REJETS.appendleft({"texte": line.get("text", ""),
                                   "motif": f"le detecteur ne voit pas de texte ({n:.2f})",
                                   "quand": round(time.time(), 1)})
                continue
        gardees.append(line)
    return gardees


SEUIL_RELECTURE = 0.62


MARGE_PPOCR = 0.05


def _relire_ppocr(img, lines, jeu: str = ""):
    if not lines or not detect.rec_disponible():
        return lines
    W, H = img.width, img.height
    boites, idx, tous = {}, [], []
    recolte = _recolte() if RECOLTE_ACTIVE else None
    for i, l in enumerate(lines):
        try:
            x, y, w, h = (int(v) for v in l["box"][:4])
        except Exception:
            continue
        garde = recolte is not None and recolte.recevable(l.get("text", "")) \
            and len(tous) < RECOLTE_PAR_IMAGE
        if not _merite_relecture(l) and not garde:
            continue
        m = max(8, h // 3)
        boites[i] = [max(0, x - m), max(0, y - m // 2),
                     min(W, x + w + m), min(H, y + h + m // 2)]
        if _merite_relecture(l):
            idx.append(i)
        if garde:
            tous.append(i)
    if not boites:
        return lines
    ordre = list(boites)
    vus = dict(zip(ordre, detect.lire_lignes(img, [boites[i] for i in ordre])))
    if tous:
        try:
            recolte.moisson(img, [lines[i] for i in tous],
                            [vus.get(i) for i in tous], jeu)
        except Exception:
            pass
    for i, txt in ((i, vus.get(i)) for i in idx):
        if not txt:
            continue
        actuel = lines[i].get("text", "")
        if txt == actuel:
            continue
        if txt and actuel and not any(is_jp_char(c) for c in actuel) \
                and any(is_jp_char(c) for c in txt):
            print(f"[relecture] refus « {actuel} » -> « {txt} » : "
                  f"la lecture d'origine ne contient aucun japonais")
            continue
        meilleur, _, _ = judge.pick(txt, actuel, DICT, TAGGER, MARGE_PPOCR)
        if meilleur != actuel:
            lines[i]["avant_ppocr"] = actuel
            lines[i]["text"] = meilleur
            bx, by, bw, bh = lines[i]["box"]
            n = max(len(meilleur), 1)
            lines[i]["chars"] = [[bx + k * bw / n, by, bw / n, bh] for k in range(n)]
            lines[i]["ppocr"] = True
    return lines


def _merite_relecture(line) -> bool:
    try:
        txt = line.get("text", "")
        if len(txt.strip()) <= 2:
            return True
        return judge.score(txt, DICT, TAGGER) < SEUIL_RELECTURE
    except Exception:
        return True


def _traits_ligne(line):
    txt = line.get("text", "")
    try:
        sc = judge.score(txt, DICT, TAGGER)
    except Exception:
        sc = 0.0
    mots = line.get("words") or []
    connus = sum(1 for w in mots if w.get("lemma"))
    return apprentissage.traits(txt, line.get("det"), line.get("encre", 0.05),
                                sc, line.get("box") or [0, 0, 1, 1],
                                connus, len(mots))


def _apprend_texte(texte, label, poids, source, jeu=""):
    try:
        ligne = {"text": texte, "det": None, "encre": 0.05,
                 "box": [0, 0, max(len(texte) * 20, 20), 24],
                 "words": segment(texte)}
        apprentissage.ajoute(texte, _traits_ligne(ligne), label, poids, source, jeu)
    except Exception:
        pass


def _apprend(line, label, poids, source, jeu=""):
    try:
        v = line.get("traits") or _traits_ligne(line)
        apprentissage.ajoute(line.get("text", ""), v, label, poids, source, jeu)
    except Exception:
        pass


def _invente(windows: str, ia: str, box=None) -> bool:
    li = len(ia.strip())
    if li == 0:
        return False
    if not windows.strip() and li > 0:
        return True
    if box:
        try:
            _, _, bw, bh = (float(v) for v in box[:4])
            if bh > 2:
                capacite = int(bw / (bh * 0.55)) + 2
                return li > capacite
        except Exception:
            pass
    return li > len(windows.strip()) * 2.5 + 3


def _arbitrate(lines):
    for line in lines:
        alt = line.pop("alt", None)
        if not alt or alt == line["text"]:
            continue
        if _invente(alt, line["text"], line.get("box")):
            line["text"] = alt
            line["_invente"] = True
            continue
        best, _, _ = judge.pick(alt, line["text"], DICT, TAGGER)
        if best != line["text"]:
            line["text"] = best
            bx, by, bw, bh = line["box"]
            n = max(len(best), 1)
            cw = bw / n
            line["chars"] = [[bx + i * cw, by, cw, bh] for i in range(n)]


def segment(text: str):
    bounds = []
    pos = 0
    for word in TAGGER(text):
        surf = word.surface
        start = text.find(surf, pos)
        if start < 0:
            continue
        pos = start + len(surf)
        lemma = ""
        try:
            lemma = word.feature.lemma or ""
            lemma = lemma.split("-")[0]
        except Exception:
            pass
        pos1 = getattr(word.feature, "pos1", "") or ""
        if any(is_jp_char(c) for c in surf):
            bounds.append({"s": start, "e": pos, "lemma": lemma, "pos": pos1,
                           "ruby": _furigana(surf, getattr(word.feature, "kana", None))})
    return bounds


def _kata_to_hira(s: str) -> str:
    return "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c for c in s)


def _furigana(surface: str, kana) -> str:
    if not kana or not any("一" <= c <= "鿿" for c in surface):
        return ""
    hira = _kata_to_hira(str(kana))
    return "" if hira == surface else hira
