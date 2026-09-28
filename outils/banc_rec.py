# -*- coding: utf-8 -*-
"""Banc d'essai : lire un ENREGISTREMENT de partie avec la vraie chaîne."""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path


def extrait(video: Path, travail: Path, fps: float) -> None:
    travail.mkdir(parents=True, exist_ok=True)
    img = travail / "img"
    if not img.exists() or not any(img.iterdir()):
        img.mkdir(parents=True, exist_ok=True)
        print("extraction des images…", flush=True)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(video),
                        "-vf", f"fps={fps}", "-q:v", "3", "-vsync", "0",
                        str(img / "t%05d.jpg")], check=True)


def passe_image(dossier: Path, fps: float, debut=0.0, fin=None, sortie=None,
                echantillon=1) -> list:
    import asyncio

    from PIL import Image

    import server

    class _Journal(list):
        def appendleft(self, x):
            self.append(x)

    server.REJETS = _Journal()

    fichiers = sorted(dossier.glob("t*.jpg"))
    resultats = []
    t_debut = time.perf_counter()
    for i_f, f in enumerate(fichiers):
        seconde = (int(f.stem[1:]) - 1) / fps
        if seconde < debut or (fin is not None and seconde > fin):
            continue
        if echantillon > 1 and i_f % echantillon:
            continue
        img = Image.open(f).convert("RGB")
        n_rejets_avant = len(server.REJETS)
        lignes = asyncio.run(server._read(img, "auto", "windows"))
        jp = [l for l in lignes if l.get("jp")]
        L, H = img.size
        resultats.append({
            "t": round(seconde, 2),
            "n_jp": len(jp),
            "textes": [l["text"] for l in jp],
            "conf": [round(l.get("conf", 0), 2) for l in jp],
            "boites": [[round(l["box"][0] / L, 4), round(l["box"][1] / H, 4),
                        round(l["box"][2] / L, 4), round(l["box"][3] / H, 4)]
                       for l in jp if l.get("box")],
            "rejets": len(server.REJETS) - n_rejets_avant,
        })
        if len(resultats) % 25 == 0:
            fait = len(resultats)
            par = (time.perf_counter() - t_debut) / fait
            print(f"  {fait} images lues ({par * 1000:.0f} ms/image)", flush=True)
            if sortie:
                _ecris(sortie, resultats)
    if sortie:
        _ecris(sortie, resultats)
    return resultats


def _ecris(chemin: Path, obj) -> None:
    Path(chemin).write_text(json.dumps(obj, ensure_ascii=False, indent=1), "utf-8")


def resume(images: list) -> dict:
    avec = [r for r in images if r["n_jp"]]
    lignes = sum(r["n_jp"] for r in images)
    rejets = sum(r.get("rejets", 0) for r in images)
    return {
        "images_lues": len(images),
        "images_avec_texte": len(avec),
        "lignes_gardees": lignes,
        "lignes_rejetees": rejets,
        "lignes_par_image_avec_texte": round(lignes / len(avec), 2) if avec else 0,
    }


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--video")
    p.add_argument("--travail", required=True)
    p.add_argument("--fps", type=float, default=1.0)
    p.add_argument("--debut", type=float, default=0.0)
    p.add_argument("--fin", type=float, default=None)
    p.add_argument("--echantillon", type=int, default=1,
                   help="ne lire qu'une image sur N")
    p.add_argument("--sortie", default=None,
                   help="nom du fichier de résultats (défaut images.json)")
    a = p.parse_args()

    travail = Path(a.travail)
    if a.video:
        extrait(Path(a.video), travail, a.fps)

    print("=== lecture par server._read ===")
    dest = travail / (a.sortie or "images.json")
    images = passe_image(travail / "img", a.fps, a.debut, a.fin, dest,
                         a.echantillon)
    print(f"  {len(images)} images lues -> {dest.name}\n")
    for k, v in resume(images).items():
        print(f"  {k:30s} {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
