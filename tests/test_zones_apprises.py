# -*- coding: utf-8 -*-
import asyncio, json, os, sys
from pathlib import Path
from PIL import Image

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "app"))
os.chdir(RACINE)

import chemins

chemins.ZONES_APPRISES = RACINE / "tests" / "tmp_zones.json"
if chemins.ZONES_APPRISES.exists():
    chemins.ZONES_APPRISES.unlink()

import zones_apprises
import chaine_lecture

import sys
sys.stdout.reconfigure(encoding="utf-8")

IMAGES = RACINE / "tests" / "images_reelles"
JEU = "BANC"
RECT = [0.073, 0.868, 0.100, 0.036]
ATTENDU = "たたかう"


def lues(lignes):
    return [l["text"] for l in lignes]


def contient(lignes, mot):
    return any(mot in t for t in lues(lignes))


async def main():
    hud = Image.open(IMAGES / "ff7r_combat_hud.jpg").convert("RGB")
    vide = Image.open(IMAGES / "ff7r_menu_quetes.jpg").convert("RGB")

    echecs = []

    zones_apprises._cache = None
    avant = await chaine_lecture._read(hud, "auto", "windows", JEU, None)
    if contient(avant, ATTENDU):
        echecs.append(f"« {ATTENDU} » etait deja lu sans rien apprendre : "
                      "le test ne prouve plus rien, choisir un autre libelle")
    print(f"1. sans apprentissage      : « {ATTENDU} » "
          f"{'PRESENT' if contient(avant, ATTENDU) else 'absent'} "
          f"({len(avant)} lignes lues)")

    r = zones_apprises.ajoute(JEU, RECT, ATTENDU)
    if not r.get("ok"):
        echecs.append(f"apprentissage refuse : {r}")

    apres = await chaine_lecture._read(hud, "auto", "windows", JEU, None)
    ok = contient(apres, ATTENDU)
    if not ok:
        echecs.append(f"« {ATTENDU} » toujours absent apres apprentissage : {lues(apres)}")
    print(f"2. endroit appris          : « {ATTENDU} » "
          f"{'PRESENT' if ok else 'ABSENT'} ({len(apres)} lignes lues)")

    surVide = await chaine_lecture._read(vide, "auto", "windows", JEU, None)
    invente = contient(surVide, ATTENDU)
    if invente:
        echecs.append(f"« {ATTENDU} » invente sur une image ou l'endroit est vide")
    print(f"3. autre ecran, endroit vide : « {ATTENDU} » "
          f"{'INVENTE' if invente else 'absent, comme il faut'} "
          f"({len(surVide)} lignes lues)")

    propose = await chaine_lecture.lit_un_endroit(hud, RECT)
    surRienDuTout = await chaine_lecture.lit_un_endroit(vide, RECT)
    if not propose.strip():
        echecs.append("le champ arriverait vide : il faudrait tout retaper")
    if surRienDuTout.strip():
        echecs.append(f"texte proposé là où il n'y a rien : « {surRienDuTout} »")
    print(f"4. champ pré-rempli        : « {propose} », "
          f"et « {surRienDuTout} » sur un écran vide")

    APEUPRES = [RECT[0] - 0.012, RECT[1] + 0.008, RECT[2] + 0.02, RECT[3] + 0.006]
    zones_apprises.ajoute(JEU, APEUPRES, "たたかう！")
    n = len(zones_apprises.pour(JEU))
    if n != 1:
        echecs.append(f"le même endroit retracé a empilé {n} zones au lieu d'en corriger 1")
    r = zones_apprises.retire(JEU, APEUPRES)
    reste = len(zones_apprises.pour(JEU))
    if reste:
        echecs.append(f"impossible d'oublier : il reste {reste} zone(s)")
    print(f"5. retracé à la main       : {n} zone (corrigée, pas empilée), "
          f"puis oubliée : {reste} restante(s)")

    try:
        chemins.ZONES_APPRISES.unlink()
    except Exception:
        pass

    if echecs:
        print()
        for e in echecs:
            print("  ECHEC :", e)
        return 1
    print("\nOK : un endroit appris rattrape le texte, et n'en invente pas ailleurs")
    return 0


raise SystemExit(asyncio.run(main()))
