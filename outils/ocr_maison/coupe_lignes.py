# -*- coding: utf-8 -*-
import asyncio
import json
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(RACINE / "app"))

IMAGES = RACINE / "tests" / "images_reelles"
SORTIE = RACINE / "modeles" / "ocr_maison" / "lignes_reelles"


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    from PIL import Image
    import detect
    import precise
    import server

    SORTIE.mkdir(parents=True, exist_ok=True)
    for vieux in SORTIE.glob("*.png"):
        vieux.unlink()

    manifeste = []
    for chemin in sorted(IMAGES.glob("*.jpg")):
        img = Image.open(chemin).convert("RGB")
        lignes = asyncio.run(server._read(img, "auto", "windows"))
        gardees, boites = [], []
        for i, l in enumerate(lignes):
            if not l.get("jp"):
                continue
            boite = precise._pad(l["box"], img.width, img.height)
            bout = img.crop(boite)
            if bout.width < 12 or bout.height < 8:
                continue
            nom = f"{chemin.stem}_{i:03d}.png"
            bout.save(SORTIE / nom)
            gardees.append({"image": nom, "source": chemin.name,
                            "windows": l["text"], "box": list(l["box"]),
                            "ppocr": ""})
            boites.append(list(boite))
        if boites and detect.rec_disponible():
            try:
                for g, txt in zip(gardees, detect.lire_lignes(img, boites)):
                    g["ppocr"] = txt or ""
            except Exception as e:
                print(f"  (PP-OCR indisponible sur cette image : {e})")
        manifeste += gardees
        print(f"{chemin.name} : {len(gardees)} ligne(s)")

    (SORTIE / "manifeste.json").write_text(
        json.dumps(manifeste, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n{len(manifeste)} lignes decoupees dans {SORTIE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
