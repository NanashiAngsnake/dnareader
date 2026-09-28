# -*- coding: utf-8 -*-
import os, sys, threading, traceback
RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RACINE, "app"))
os.chdir(RACINE)

import dictionary, judge, fugashi

import sys
sys.stdout.reconfigure(encoding="utf-8")

DICT = dictionary.Dictionary()
TAGGER = fugashi.Tagger()

PHRASES = ["兄貴と呼べる青年に会った", "ゲームを再開する", "装備を変更するメンバーを選択してください。",
           "魔法防御力", "疾風のスカーフ", "混乱を起こして", "プレジデントを狙うっていう",
           "極秘開店モーグリショップ", "そんな話をしてる場合じゃないッス"]

erreurs = []
tours = [0]
verrou = threading.Lock()


def survol():
    try:
        for _ in range(120):
            for p in PHRASES:
                for o in range(0, len(p), 2):
                    DICT.lookup(p, o)
                    with verrou:
                        tours[0] += 1
    except Exception:
        with verrou:
            erreurs.append(traceback.format_exc())


def lecture():
    try:
        for _ in range(400):
            for p in PHRASES:
                judge.score(p, DICT, TAGGER)
                with verrou:
                    tours[0] += 1
    except Exception:
        with verrou:
            erreurs.append(traceback.format_exc())


fils = [threading.Thread(target=survol) for _ in range(4)] + \
       [threading.Thread(target=lecture) for _ in range(4)]
for f in fils:
    f.start()
for f in fils:
    f.join()

print(f"{tours[0]} interrogations sur 8 fils simultanes")
if erreurs:
    print(f"ECHEC : {len(erreurs)} fil(s) en erreur\n")
    print(erreurs[0][-900:])
    raise SystemExit(1)
print("OK : aucune erreur, aucun blocage")
