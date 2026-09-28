# -*- coding: utf-8 -*-
import argparse
import asyncio
import subprocess
import sys
import tempfile
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(RACINE / "app"))

IMAGES = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}
VIDEOS = {".mp4", ".mkv", ".mov", ".avi", ".flv", ".ts", ".webm"}


def images_de_la_video(chemin: Path, pas: float, sortie: Path) -> list:
    sortie.mkdir(parents=True, exist_ok=True)
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(chemin),
           "-vf", f"fps=1/{pas}", "-q:v", "3", str(sortie / "img_%06d.jpg")]
    print(f"extraction d'une image toutes les {pas} s…")
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit("ffmpeg a refusé : " + (r.stderr or "")[-400:])
    return sorted(sortie.glob("*.jpg"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("source", help="un dossier d'images, ou un fichier vidéo")
    ap.add_argument("--pas", type=float, default=2.0,
                    help="secondes entre deux images extraites d'une vidéo")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    src = Path(a.source)
    if not src.exists():
        raise SystemExit(f"introuvable : {src}")

    temporaire = None
    if src.is_dir():
        fichiers = sorted(f for f in src.rglob("*") if f.suffix.lower() in IMAGES)
    elif src.suffix.lower() in VIDEOS:
        temporaire = Path(tempfile.mkdtemp(prefix="dnar-recolte-"))
        fichiers = images_de_la_video(src, a.pas, temporaire)
    else:
        fichiers = [src]
    if not fichiers:
        raise SystemExit("aucune image à lire")
    print(f"{len(fichiers)} image(s) à passer en revue\n")

    from PIL import Image
    import chaine_lecture as C
    import detect
    import ocr
    import recolte

    depart = recolte.compte()
    for i, f in enumerate(fichiers, 1):
        try:
            img = Image.open(f).convert("RGB")
        except Exception:
            continue
        lignes = [l for l in asyncio.run(ocr.ocr_image(img, "auto"))
                  if l.get("text") and l.get("box")]
        if not lignes:
            continue
        boites = []
        for l in lignes:
            x, y, w, h = (int(v) for v in l["box"][:4])
            m = max(8, h // 3)
            boites.append([max(0, x - m), max(0, y - m // 2),
                           min(img.width, x + w + m),
                           min(img.height, y + h + m // 2)])
        try:
            lus = detect.lire_lignes(img, boites)
        except Exception:
            continue
        recolte.moisson(img, lignes, lus)
        if i % 25 == 0 or i == len(fichiers):
            print(f"  {i}/{len(fichiers)} images · "
                  f"{recolte.compte() - depart} ligne(s) récoltées", flush=True)

    print(f"\n{recolte.compte() - depart} nouvelles lignes ; "
          f"{recolte.compte()} au total dans {recolte.DOSSIER}")
    if temporaire:
        import shutil
        shutil.rmtree(temporaire, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
