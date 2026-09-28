# -*- coding: utf-8 -*-
import sys
from pathlib import Path

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI))
import donnees as D

ASSEZ = 200


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    dossiers = D.dossiers_de_recolte()
    lignes = D.recoltees()
    n = len(lignes)

    if not dossiers:
        print("      Aucune ligne récoltée pour l'instant.")
        print()
        print("      Dans DNAreader : Réglages > Plus d'options > « Aider le")
        print("      lecteur ». Tu allumes une fois, tu joues, et les lignes")
        print("      que les deux moteurs lisent pareil sont gardées.")
        return 2

    from collections import Counter
    par_dossier = Counter(f.parent for f, _ in lignes)
    print(f"      {n} ligne(s) récoltée(s)")
    for origine, d in dossiers:
        print(f"        · {par_dossier.get(d, 0):5d}  {origine}")
        print(f"                 {d}")
    jeux = D.jeux_recoltes()
    if jeux and list(jeux) != ["(jeu non noté)"]:
        print("      par jeu :")
        for jeu, c in jeux.most_common():
            print(f"        · {c:5d}  {jeu}")

    if n:
        print("      exemples :")
        for _, texte in lignes[-3:]:
            print(f"        « {texte} »")

    if n < ASSEZ:
        print()
        print(f"      C'est peu : en dessous de {ASSEZ} lignes, elles pèsent")
        print("      moins de 20 % de l'entraînement et le gain ne se mesure")
        print("      pas. Joue quelques parties avec la récolte allumée.")
        print()
        rep = input("      Entraîner quand même ? [o/N] ").strip().lower()
        if rep not in ("o", "oui", "y"):
            return 2
    else:
        print()
        part = min(33, n * 100 // 1000)
        print(f"      De quoi travailler : elles compteront pour "
              f"{part} % de l'entraînement.")
        if part >= 33:
            print("      C'est le plafond. En récolter plus n'augmente pas ce")
            print("      tiers : ça le diversifie. Utile pour un jeu dont la")
            print("      police n'est pas encore dans la liste ci-dessus,")
            print("      inutile pour refaire du déjà-vu.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
