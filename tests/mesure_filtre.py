# -*- coding: utf-8 -*-
import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE / "app"))
sys.stdout.reconfigure(encoding="utf-8")

import fugashi
import judge
from dictionary import Dictionary

JEU = json.loads((Path(__file__).parent / "lignes_labellisees.json")
                 .read_text(encoding="utf-8"))
DIC = Dictionary()
TAG = fugashi.Tagger()


def mesure(nom, garde, verbeux=False):
    bonnes = JEU["bonnes"]
    dechets = JEU["dechets"]
    gardees_ok = [t for t in bonnes if garde(t)]
    gardees_ko = [t for t in dechets if garde(t)]
    rappel = len(gardees_ok) / len(bonnes)
    bruit = len(gardees_ko) / len(dechets)
    print(f"\n{nom}")
    print(f"  bonnes gardees  : {len(gardees_ok):2d}/{len(bonnes)}  ({rappel:.0%})")
    print(f"  dechets passes  : {len(gardees_ko):2d}/{len(dechets)}  ({bruit:.0%})")
    if verbeux:
        perdues = [t for t in bonnes if not garde(t)]
        if perdues:
            print("  PERDUES (grave) :", " · ".join(perdues))
        if gardees_ko:
            print("  bruit restant   :", " · ".join(gardees_ko))
    return {"nom": nom, "rappel": rappel, "bruit": bruit,
            "perdues": [t for t in bonnes if not garde(t)],
            "bruit_restant": gardees_ko}


if __name__ == "__main__":
    from plausible import garde_ligne, nettoie
    reel = lambda t: garde_ligne(nettoie(t), DIC, TAG)
    mesure("filtre de l'application", reel, verbeux=True)
    print()
    mesure("aucun filtre (reference)", lambda t: True)
    mesure("judge.score >= 0.5 seul", lambda t: judge.score(t, DIC, TAG) >= 0.5)
