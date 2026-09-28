# -*- coding: utf-8 -*-
import difflib
import json
import sys
from pathlib import Path

import numpy as np
import torch
from PIL import Image

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI))
import donnees as D
from entraine import cer, distance
from modele import CRNN, Alphabet

LIGNES = D.SORTIE / "lignes_reelles"
ATTENDU = D.IMAGES_REELLES / "attendu.json"
RESSEMBLANCE_MIN = 0.70


def ressemblance(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a, b).ratio()


def meilleure(attendu: str, candidats: list) -> tuple:
    best, score = "", 0.0
    for c in candidats:
        s = ressemblance(attendu, c)
        if s > score:
            best, score = c, s
    return best, score


@torch.no_grad()
def lis_tout(reseau, alpha, appareil, chemins) -> list:
    out = []
    for c in chemins:
        img = D.en_bande(Image.open(c))
        x = np.asarray(img, dtype="float32")[None, None] / 127.5 - 1.0
        x = torch.from_numpy(x).to(appareil)
        with torch.autocast("cuda", dtype=torch.bfloat16,
                            enabled=(appareil.type == "cuda")):
            y = reseau(x)
        pred = y.float().argmax(2)[0].cpu().tolist()
        out.append(alpha.decode(pred[:CRNN.largeur_sortie(img.width)]))
    return out


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    manifeste = json.loads((LIGNES / "manifeste.json").read_text("utf-8"))
    etat_f = D.SORTIE / "crnn.pt"
    if not etat_f.exists():
        print("aucun modele entraine : lance d'abord entraine.py")
        return 1
    appareil = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    etat = torch.load(etat_f, map_location=appareil)
    alpha = Alphabet(etat["alphabet"])
    reseau = CRNN(len(alpha)).to(appareil)
    reseau.load_state_dict(etat["reseau"])
    reseau.eval()
    print(f"modele : {etat.get('pas')} etapes d'entrainement, "
          f"CER {etat.get('cer', 0)*100:.2f} % sur images fabriquees\n")

    nous = lis_tout(reseau, alpha, appareil,
                    [LIGNES / m["image"] for m in manifeste])
    lecteurs = {"windows": [m["windows"] for m in manifeste],
                "ppocr": [m.get("ppocr", "") for m in manifeste],
                "maison": nous}
    f_manga = LIGNES / "mangaocr.json"
    if f_manga.exists():
        lecteurs["mangaocr"] = json.loads(f_manga.read_text("utf-8"))

    cfg = json.loads(ATTENDU.read_text("utf-8"))
    attendus = []
    for cas in cfg["cas"]:
        for a in cas.get("attendu", []):
            attendus.append((cas["nom"], a, {i["image"] for i in manifeste
                                             if i["source"] in cas["images"]}))

    print("réplique attendue → ce que chacun en fait\n")
    cles = list(lecteurs)
    scores = {c: [] for c in cles}
    trouvees = {c: 0 for c in cles}
    paires = {c: [] for c in cles}
    for nom, att, images in attendus:
        idx = [i for i, m in enumerate(manifeste) if m["image"] in images]
        print(f"   « {att} »")
        for c in cles:
            b, s = meilleure(att, [lecteurs[c][i] for i in idx])
            scores[c].append(s)
            if s >= RESSEMBLANCE_MIN:
                trouvees[c] += 1
                paires[c].append((att, b))
            print(f"     {c:8} {s:.2f} : « {b} »")

    n = len(attendus)
    print(f"\n{'':10} {'retrouvees':>12} {'ressemblance':>14} {'CER':>8}")
    for cle in cles:
        moy = sum(scores[cle]) / max(1, n)
        c = cer([a for a, _ in paires[cle]], [b for _, b in paires[cle]]) \
            if paires[cle] else 1.0
        print(f"{cle:10} {trouvees[cle]:>6}/{n:<5} {moy:>13.2f} "
              f"{c*100:>7.1f} %")
    print("\n(CER calcule sur les repliques retrouvees par chacun : il dit la"
          "\n qualite de ce qui est lu, pas la quantite.)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
