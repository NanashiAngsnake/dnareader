# -*- coding: utf-8 -*-
import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

BASE = Path(__file__).resolve().parent.parent
SORTIE = (BASE / "ressources" / "icon.png").resolve()
CYAN = (140, 222, 230, 255)
ROUGE = (178, 22, 40, 255)
BLEU = (35, 35, 158, 255)

TAILLES = (16, 24, 32, 48, 64, 128, 256)
TOURS = 1.5
PAS = 120

DOSSIERS = [BASE, Path.home() / "Downloads", Path.home() / "Desktop",
            Path.home() / "Pictures", Path.home() / "Documents"]
NOMS = ["logo", "dnareader", "logo-dnareader"]
EXTS = [".png", ".webp", ".jpg", ".jpeg"]


def trouve_logo() -> Path | None:
    for d in DOSSIERS:
        for n in NOMS:
            for e in EXTS:
                p = d / (n + e)
                if p.exists() and p.is_file() and p.resolve() != SORTIE:
                    return p
    return None


def _geo(n):
    x0, y0 = n * 0.17, n * 0.83
    x1, y1 = n * 0.83, n * 0.17
    dx, dy = x1 - x0, y1 - y0
    lg = math.hypot(dx, dy)
    return (x0, y0, dx, dy, -dy / lg, dx / lg, n * 0.235)


def _pt(g, t, phase):
    x0, y0, dx, dy, ux, uy, amp = g
    e = amp * math.sin(2 * math.pi * TOURS * t + phase)
    return (x0 + dx * t + ux * e, y0 + dy * t + uy * e)


def _helice(d, n, ep):
    g = _geo(n)
    for i in range(1, 13):
        t = i / 13
        a, b = _pt(g, t, 0.0), _pt(g, t, math.pi)
        if math.hypot(a[0] - b[0], a[1] - b[1]) < n * 0.20:
            continue
        if t > 0.62:
            coul = ROUGE
        elif t < 0.38:
            coul = BLEU
        else:
            continue
        d.line([a, b], fill=coul, width=max(1, int(ep * 0.20)))
    for phase in (0.0, math.pi):
        d.line([_pt(g, i / PAS, phase) for i in range(PAS + 1)],
               fill=CYAN, width=max(2, int(ep)), joint="curve")


def _ha(img, n):
    if n < 32:
        return
    for nom in ("YuGothB.ttc", "meiryob.ttc", "msgothic.ttc", "YuGothM.ttc"):
        f = Path("C:/Windows/Fonts") / nom
        if not f.exists():
            continue
        try:
            police = ImageFont.truetype(str(f), int(n * 0.26))
        except Exception:
            continue
        d = ImageDraw.Draw(img)
        b = d.textbbox((0, 0), "は", font=police)
        x = (n - (b[2] - b[0])) / 2 - b[0]
        y = (n - (b[3] - b[1])) / 2 - b[1]
        d.text((x, y), "は", font=police, fill=(255, 255, 255, 255),
               stroke_width=max(1, int(n * 0.012)), stroke_fill=(20, 60, 70, 255))
        return


def dessine(n: int) -> Image.Image:
    k = 4
    img = Image.new("RGBA", (n * k, n * k), (0, 0, 0, 0))
    _helice(ImageDraw.Draw(img), n * k, max(2, n * 0.105) * k)
    img = img.resize((n, n), Image.LANCZOS)
    _ha(img, n)
    return img


def main() -> int:
    perso = Path(sys.argv[1]) if len(sys.argv) > 1 else trouve_logo()
    if perso and perso.exists():
        src = Image.open(perso).convert("RGBA")
        if src.width != src.height:
            c = max(src.size)
            fond = Image.new("RGBA", (c, c), (0, 0, 0, 0))
            fond.paste(src, ((c - src.width) // 2, (c - src.height) // 2), src)
            src = fond
        images = [src.resize((n, n), Image.LANCZOS) for n in TAILLES]
        print(f"icône construite depuis : {perso}")
    else:
        images = [dessine(n) for n in TAILLES]
        print("AUCUN LOGO TROUVÉ — icône dessinée en substitut.")
        print("Pour utiliser la vraie : enregistre-la sous")
        print(f"    {BASE / 'ressources' / 'logo.png'}")
        print("puis relance ce script (ou passe le chemin en argument).")
    images[-1].save(BASE / "ressources" / "icon.png")
    for cible in (BASE / "static" / "icon.png",):
        cible.parent.mkdir(exist_ok=True)
        images[-1].save(cible)
    images[-1].save(BASE / "ressources" / "icon.ico", format="ICO",
                    sizes=[(n, n) for n in TAILLES])
    print("écrit : icon.ico, icon.png, static/icon.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
