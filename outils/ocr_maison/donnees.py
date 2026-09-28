# -*- coding: utf-8 -*-
import json
import os
import random
import sqlite3
import unicodedata
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

RACINE = Path(__file__).resolve().parent.parent.parent
DICO = RACINE / "dicts" / "dictionary.db"
IMAGES_REELLES = RACINE / "tests" / "images_reelles"
SORTIE = RACINE / "entrainement" / "ocr_maison"
MODELES = RACINE / "modeles"

HAUTEUR = 48
MARGE = 4

POLICES = [
    ("meiryo.ttc", 0), ("meiryo.ttc", 1), ("meiryob.ttc", 0),
    ("YuGothR.ttc", 0), ("YuGothM.ttc", 0), ("YuGothB.ttc", 0),
    ("YuGothL.ttc", 0),
    ("msgothic.ttc", 0), ("msgothic.ttc", 1), ("msgothic.ttc", 2),
    ("msmincho.ttc", 0), ("yumin.ttf", 0), ("yumindb.ttf", 0),
    ("BIZ-UDGothicR.ttc", 0), ("BIZ-UDGothicB.ttc", 0),
    ("BIZ-UDMinchoM.ttc", 0),
    ("NotoSansJP-VF.ttf", 0), ("NotoSerifJP-VF.ttf", 0),
]
DOSSIER_POLICES = Path("C:/Windows/Fonts")

SIGNES = ("　、。，．・：；？！゛゜´｀¨＾￣＿ヽヾゝゞ〃仝々〆〇ー―‐／＼～∥｜…‥"
          "‘’“”（）〔〕［］｛｝〈〉《》「」『』【】＋－±×÷＝≠＜＞≦≧°′″℃￥＄"
          "％＃＆＊＠※〒→←↑↓♪")
LATIN = ("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
         "!?.,:;'\"()[]{}+-=/%&#@*<>~_ ")


def kana() -> str:
    h = "".join(chr(c) for c in range(0x3041, 0x3097))
    k = "".join(chr(c) for c in range(0x30A1, 0x30FB))
    return h + k


def _est_kanji(c: str) -> bool:
    return "\u4e00" <= c <= "\u9fff"


def expressions(limite: int = 120000) -> list:
    con = sqlite3.connect(str(DICO))
    lignes = con.execute(
        "SELECT expr FROM terms WHERE expr IS NOT NULL"
        " ORDER BY score DESC LIMIT ?", (limite,)).fetchall()
    con.close()
    vus, out = set(), []
    for (e,) in lignes:
        e = (e or "").strip()
        if not e or e in vus:
            continue
        vus.add(e)
        out.append(e)
    return out


def lignes_de_jeu() -> list:
    out = []
    f = IMAGES_REELLES / "attendu.json"
    if f.exists():
        d = json.loads(f.read_text(encoding="utf-8"))
        for cas in d.get("cas", []):
            out += [l for l in cas.get("attendu", []) if l]
    return out


def dossiers_de_recolte() -> list:
    import os
    out = [("le dépôt (essais de mise au point)", RACINE / "donnees" / "recolte")]
    local = os.environ.get("LOCALAPPDATA")
    if local:
        out.append(("ton application installée",
                    Path(local) / "DNAreader" / "recolte"))
    force = os.environ.get("DNAREADER_DONNEES")
    if force:
        out.append(("un dossier imposé (DNAREADER_DONNEES)",
                    Path(force) / "recolte"))
    return [(o, d) for o, d in out if (d / "lignes.jsonl").exists()]


def recoltees() -> list:
    out = []
    for _, d in dossiers_de_recolte():
        for ligne in (d / "lignes.jsonl").read_text(encoding="utf-8").splitlines():
            try:
                e = json.loads(ligne)
            except Exception:
                continue
            f = d / e.get("image", "")
            if e.get("texte") and f.exists():
                out.append((f, e["texte"]))
    return out


def jeux_recoltes() -> dict:
    from collections import Counter
    c = Counter()
    for _, d in dossiers_de_recolte():
        for ligne in (d / "lignes.jsonl").read_text(encoding="utf-8").splitlines():
            try:
                e = json.loads(ligne)
            except Exception:
                continue
            if e.get("texte") and (d / e.get("image", "")).exists():
                c[e.get("jeu") or "(jeu non noté)"] += 1
    return c


def alphabet(expr: list, mini: int = 3) -> str:
    freq = {}
    for e in expr:
        for c in e:
            if _est_kanji(c):
                freq[c] = freq.get(c, 0) + 1
    kanji = sorted(c for c, n in freq.items() if n >= mini)
    base = kana() + SIGNES + LATIN + "".join(kanji)
    vus, out = set(), []
    for c in base:
        if c not in vus and c not in "\n\r\t":
            vus.add(c)
            out.append(c)
    return "".join(out)


class Phrases:
    PARTICULES = ["は", "が", "を", "に", "で", "と", "も", "の", "へ", "から",
                  "まで", "より", "や", "ね", "よ", "な", "か", "だ", "です",
                  "ます", "した", "する", "って", "けど", "ので", "たら"]
    FINS = ["。", "！", "？", "…", "、", "", "", "。", "！？"]

    def __init__(self, expr: list, jeu: list, alpha: str, graine: int = 0):
        self.expr = [e for e in expr if all(c in alpha for c in e)]
        self.jeu = jeu
        self.alpha = alpha
        self.r = random.Random(graine)

    def une(self) -> str:
        d = self.r.random()
        if d < 0.10 and self.jeu:
            return self.r.choice(self.jeu)
        if d < 0.35:
            return self._menu()
        if d < 0.85:
            return self._replique()
        return self._bruit()

    def _menu(self) -> str:
        n = self.r.randint(1, 3)
        return "".join(self.r.choice(self.expr) for _ in range(n))

    def _replique(self) -> str:
        n = self.r.randint(2, 7)
        bouts = []
        for i in range(n):
            bouts.append(self.r.choice(self.expr))
            if self.r.random() < 0.6 and i < n - 1:
                bouts.append(self.r.choice(self.PARTICULES))
        t = "".join(bouts) + self.r.choice(self.FINS)
        if self.r.random() < 0.15:
            t = self.r.choice(self.expr) + "　" + t
        return t[:40]

    def _bruit(self) -> str:
        n = self.r.randint(1, 24)
        return "".join(self.r.choice(self.alpha) for _ in range(n))


class Peintre:
    def __init__(self, graine: int = 0):
        self.r = random.Random(graine)
        self._polices = {}
        self._fonds = self._charge_les_fonds()

    def _charge_les_fonds(self) -> list:
        fonds = []
        for f in sorted(IMAGES_REELLES.glob("*.jpg")):
            try:
                fonds.append(Image.open(f).convert("RGB"))
            except Exception:
                pass
        return fonds

    def police(self, taille: int):
        nom, index = self.r.choice(POLICES)
        cle = (nom, index, taille)
        if cle not in self._polices:
            try:
                self._polices[cle] = ImageFont.truetype(
                    str(DOSSIER_POLICES / nom), taille, index=index)
            except Exception:
                self._polices[cle] = ImageFont.truetype(
                    str(DOSSIER_POLICES / "meiryo.ttc"), taille)
        return self._polices[cle]

    def _fond(self, w: int, h: int) -> Image.Image:
        if self._fonds and self.r.random() < 0.75:
            src = self.r.choice(self._fonds)
            if src.width > w and src.height > h:
                x = self.r.randint(0, src.width - w - 1)
                y = self.r.randint(0, src.height - h - 1)
                bout = src.crop((x, y, x + w, y + h))
                if self.r.random() < 0.35:
                    voile = Image.new("RGB", (w, h), (0, 0, 0))
                    bout = Image.blend(bout, voile, self.r.uniform(0.3, 0.75))
                return bout
        g = self.r.randint(0, 90)
        return Image.new("RGB", (w, h), (g, g, g))

    def _couleur_texte(self, fond: Image.Image) -> tuple:
        gris = sum(fond.convert("L").resize((8, 4)).getdata()) / 32
        if gris < 128:
            base = self.r.randint(205, 255)
        else:
            base = self.r.randint(0, 60)
        c = [base, base, base]
        if self.r.random() < 0.25:
            i = self.r.randrange(3)
            c[i] = max(0, min(255, c[i] + self.r.randint(-90, 90)))
        return tuple(c)

    def peins(self, texte: str) -> Image.Image:
        taille = self.r.randint(20, 40)
        police = self.police(taille)
        contour = self.r.choice([0, 0, 1, 1, 2, 2, 3])
        espacement = self.r.choice([0, 0, 0, 0, 2, 4, 6, 9, 13,
                                    int(taille * 0.4)])

        tmp = Image.new("RGB", (8, 8))
        d = ImageDraw.Draw(tmp)
        try:
            b = d.textbbox((0, 0), texte, font=police, stroke_width=contour)
        except Exception:
            b = (0, 0, 8 * len(texte), taille)
        avances = [police.getlength(c) for c in texte]
        tw = max(1, int(sum(avances) + espacement * max(0, len(texte) - 1)
                        + 2 * contour))
        th = max(1, b[3] - b[1])

        marge = self.r.randint(MARGE, MARGE + 8)
        w, h = tw + 2 * marge, th + 2 * marge
        img = self._fond(w, h)
        couleur = self._couleur_texte(img)
        d = ImageDraw.Draw(img)
        cc = (0, 0, 0) if sum(couleur) > 380 else (255, 255, 255)
        ombre = self.r.random() < 0.5
        y = marge - b[1]

        if not espacement:
            if ombre:
                d.text((marge - b[0] + 2, y + 2), texte, font=police,
                       fill=(0, 0, 0), stroke_width=contour,
                       stroke_fill=(0, 0, 0))
            d.text((marge - b[0], y), texte, font=police, fill=couleur,
                   stroke_width=contour, stroke_fill=cc)
        else:
            x = float(marge + contour)
            for c, av in zip(texte, avances):
                if ombre:
                    d.text((x + 2, y + 2), c, font=police, fill=(0, 0, 0),
                           stroke_width=contour, stroke_fill=(0, 0, 0))
                d.text((x, y), c, font=police, fill=couleur,
                       stroke_width=contour, stroke_fill=cc)
                x += av + espacement

        return self.abime(img)

    def abime(self, img: Image.Image) -> Image.Image:
        r = self.r
        if r.random() < 0.5:
            img = img.filter(ImageFilter.GaussianBlur(r.uniform(0.2, 1.1)))
        if r.random() < 0.4:
            img = ImageEnhance.Contrast(img).enhance(r.uniform(0.6, 1.5))
        if r.random() < 0.3:
            img = ImageEnhance.Brightness(img).enhance(r.uniform(0.7, 1.3))
        if r.random() < 0.35:
            import io
            b = io.BytesIO()
            img.save(b, "JPEG", quality=r.randint(35, 85))
            b.seek(0)
            img = Image.open(b).convert("RGB")
        return img


class Vraies:
    def __init__(self, graine: int = 0):
        self.r = random.Random(graine + 7717)
        self.lignes = recoltees()
        self._cache = {}

    def __len__(self):
        return len(self.lignes)

    def une(self):
        if not self.lignes:
            return None
        chemin, texte = self.r.choice(self.lignes)
        img = self._cache.get(chemin)
        if img is None:
            try:
                img = Image.open(chemin).convert("RGB")
            except Exception:
                return None
            self._cache[chemin] = img
        r = self.r
        m = max(1, img.height // 12)
        b = (r.randint(0, m), r.randint(0, m),
             img.width - r.randint(0, m), img.height - r.randint(0, m))
        bout = img.crop(b) if b[2] > b[0] + 8 and b[3] > b[1] + 8 else img
        e = r.uniform(0.75, 1.35)
        if abs(e - 1) > 0.05:
            bout = bout.resize((max(8, int(bout.width * e)),
                                max(8, int(bout.height * e))), Image.BILINEAR)
        if r.random() < 0.5:
            bout = bout.filter(ImageFilter.GaussianBlur(r.uniform(0.2, 0.9)))
        if r.random() < 0.5:
            bout = ImageEnhance.Contrast(bout).enhance(r.uniform(0.7, 1.4))
        if r.random() < 0.4:
            bout = ImageEnhance.Brightness(bout).enhance(r.uniform(0.8, 1.25))
        return bout, texte


def en_bande(img: Image.Image, hauteur: int = HAUTEUR):
    img = img.convert("L")
    w = max(8, int(round(img.width * hauteur / max(1, img.height))))
    return img.resize((w, hauteur), Image.BILINEAR)
