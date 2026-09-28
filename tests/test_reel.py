# -*- coding: utf-8 -*-
import asyncio
import difflib
import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE.parent / "app"))
DOSSIER = BASE / "images_reelles"
RESSEMBLANCE_MIN = 0.70
MOTEUR = "maison" if "--maison" in sys.argv else (
    "precise" if "--precise" in sys.argv else "windows")


def ressemble(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a, b).ratio()


def _meilleure(attendu, lues):
    meilleur, score = "", 0.0
    for lue in lues:
        s = ressemble(attendu, lue)
        if s > score:
            meilleur, score = lue, s
    return meilleur, score


def _distance(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a or not b:
        return len(a) or len(b)
    prec = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cour = [i]
        for j, cb in enumerate(b, 1):
            cour.append(min(prec[j] + 1, cour[j - 1] + 1,
                            prec[j - 1] + (ca != cb)))
        prec = cour
    return prec[-1]


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    if not (DOSSIER / "attendu.json").exists():
        print("tests_reels/attendu.json absent : test ignoré")
        return 0

    from PIL import Image

    import server

    print(f"moteur mesure : {MOTEUR}")
    print()
    cfg = json.loads((DOSSIER / "attendu.json").read_text("utf-8"))
    bande_defaut = cfg["bande"]

    total = trouvees = bruit = 0
    fautes = []
    echecs, surprises = [], []
    for cas in cfg["cas"]:
        haut, bas = cas.get("bande", bande_defaut)
        lues, hors = [], 0
        manquantes = []
        for nom in cas["images"]:
            chemin = DOSSIER / nom
            if not chemin.exists():
                manquantes.append(nom)
                continue
            img = Image.open(chemin).convert("RGB")
            lignes = asyncio.run(server._read(img, "auto", MOTEUR))
            for l in lignes:
                if not l.get("jp"):
                    continue
                lues.append(l["text"])
                if not (haut <= l["box"][1] / img.height <= bas):
                    hors += 1
        if manquantes:
            print(f"[!] {cas['nom']} : image(s) absente(s) {manquantes}, cas ignoré")
            continue
        bruit += hors

        print(f"\n--- {cas['nom']}   ({len(cas['images'])} image(s))")
        for attendu in cas["attendu"]:
            total += 1
            meilleur, score = _meilleure(attendu, lues)
            fautes.append((attendu, meilleur if score >= RESSEMBLANCE_MIN else ""))
            if score >= RESSEMBLANCE_MIN:
                trouvees += 1
                comment = "identique" if meilleur == attendu else f"lu « {meilleur} »"
                print(f"  OK    {attendu}   ({score:.2f}, {comment})")
            else:
                echecs.append((cas["nom"], attendu, meilleur, score))
                print(f"  ÉCHEC {attendu}   introuvable "
                      f"(le plus proche : « {meilleur} » à {score:.2f})")
        for attendu, raison in (cas.get("attendu_defaillant") or {}).items():
            meilleur, score = _meilleure(attendu, lues)
            if score >= RESSEMBLANCE_MIN:
                surprises.append((cas["nom"], attendu, meilleur, score))
                print(f"  PASSE {attendu}   ({score:.2f}) — connu défaillant "
                      f"jusqu'ici ; retirer le drapeau")
            else:
                print(f"  connu {attendu}   ({score:.2f}) : {raison}")
        print(f"  … {hors} ligne(s) retenue(s) hors de la bande (décor)")

    exactes = sum(1 for a, m in fautes if a == m)
    signes = sum(len(a) for a, _ in fautes) or 1
    erreurs = sum(_distance(a, m) for a, m in fautes)
    print(f"\n{trouvees}/{total} répliques exigées retrouvées ; "
          f"{bruit} lignes de décor retenues au total")
    print(f"{exactes}/{total} rendues EXACTEMENT · "
          f"{erreurs/signes*100:.1f} % de caractères à corriger")
    if surprises:
        print("\nÀ METTRE À JOUR — ces cas connus défaillants passent maintenant :")
        for nom, a, m, s in surprises:
            print(f"  {nom} : « {a} » lu « {m} » à {s:.2f}")
    if echecs:
        print("\nRÉPLIQUES PERDUES :")
        for nom, a, m, s in echecs:
            print(f"  {nom} : « {a} »  (plus proche « {m} » à {s:.2f})")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
