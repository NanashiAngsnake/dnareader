# -*- coding: utf-8 -*-
import os
import sqlite3
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "app"))
os.chdir(RACINE)
sys.stdout.reconfigure(encoding="utf-8")

import chemins
from dictionary import Dictionary, langue_dico

DEUX_LANGUES = ["再開", "攻撃", "魔法", "回復", "破壊", "獲得", "潜入"]
SANS_FRANCAIS = "毒消し"


def premier(dic, mot, langue):
    r = dic.lookup(mot, 0, langue=langue)
    m = next((m for m in r["matches"] if m["expression"] == mot), None)
    if not m or not m["defs"]:
        return None, None
    d = m["defs"][0]
    return d["lang"], ", ".join(d["glosses"][:2])


def main():
    echecs = []

    print("1. correspondance langue d'interface -> dictionnaire")
    attendu = {"fr": "fr", "fr-FR": "fr", "en": "en", "en-US": "en",
               "es": "en", "de": "en", "pt": "en", "ja": "en", "": "en"}
    for interface, veut in attendu.items():
        eu = langue_dico(interface)
        if eu != veut:
            echecs.append(f"langue_dico({interface!r}) rend {eu!r}, attendu {veut!r}")
    print(f"   {len(attendu)} correspondances verifiees "
          f"(fr -> fr ; tout le reste -> en, le dictionnaire le plus complet)")

    dic = Dictionary()

    print("\n2. l'ordre des definitions suit la langue demandee")
    for mot in DEUX_LANGUES:
        lfr, gfr = premier(dic, mot, "fr")
        len_, gen = premier(dic, mot, "en")
        if lfr is None or len_ is None:
            echecs.append(f"« {mot} » introuvable : le cas ne mesure plus rien")
            continue
        if lfr != "fr":
            echecs.append(f"« {mot} » demande en francais rend d'abord du {lfr}")
        if len_ != "en":
            echecs.append(f"« {mot} » demande en anglais rend d'abord du {len_}")
        print(f"   {mot:6} fr -> [{lfr}] {gfr[:34]:36} en -> [{len_}] {gen[:30]}")

    print("\n3. repli : demander le francais ne doit rien faire perdre")
    lfr, gfr = premier(dic, SANS_FRANCAIS, "fr")
    if lfr is None:
        echecs.append(f"« {SANS_FRANCAIS} » ne rend RIEN en francais : le repli"
                      " sur l'anglais est casse")
    else:
        print(f"   {SANS_FRANCAIS} n'a aucun sens francais -> on sert [{lfr}] {gfr}")

    con = sqlite3.connect(chemins.DICTS / "dictionary.db")
    fr = {r[0] for r in con.execute("SELECT DISTINCT expr FROM terms WHERE dict='fr'")}
    en = {r[0] for r in con.execute("SELECT DISTINCT expr FROM terms WHERE dict='en'")}
    part = 100 * len(fr & en) / max(len(en), 1)
    print(f"   couverture du francais : {len(fr)} expressions contre {len(en)} "
          f"en anglais, soit {part:.1f} %")
    if part > 50:
        echecs.append("le dictionnaire francais couvre soudain plus de la moitie"
                      " de l'anglais : verifier que la base est bien construite")

    if echecs:
        print()
        for e in echecs:
            print("  ECHEC :", e)
        return 1
    print("\nOK : le dictionnaire suit la langue, et ne fait jamais perdre de sens")
    return 0


raise SystemExit(main())
