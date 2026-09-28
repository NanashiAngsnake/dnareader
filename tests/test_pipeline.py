# -*- coding: utf-8 -*-
import asyncio
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "app"))

from PIL import Image, ImageDraw, ImageFont

sys.stdout.reconfigure(encoding="utf-8")

from dictionary import Dictionary
import ocr


def make_test_image(path):
    img = Image.new("RGB", (670, 480), (8, 20, 45))
    d = ImageDraw.Draw(img)
    font_big = ImageFont.truetype("C:/Windows/Fonts/YuGothM.ttc", 26)
    font_med = ImageFont.truetype("C:/Windows/Fonts/YuGothM.ttc", 20)
    d.text((180, 90), "2026/04/28 19:18:35", font=font_med, fill=(80, 160, 255))
    d.text((160, 130), "CHAPTER 3  セブンスヘブン", font=font_big, fill=(230, 235, 240))
    d.text((190, 175), "七番街スラム／居住区", font=font_med, fill=(150, 200, 230))
    d.text((100, 235), "前回の続きからゲームを再開します。", font=font_big,
           fill=(235, 240, 245))
    d.text((300, 320), "はい", font=font_big, fill=(255, 255, 255))
    d.text((290, 370), "いいえ", font=font_big, fill=(200, 205, 210))
    img.save(path)
    return img


def main():
    print("=== Construction/chargement dictionnaire ===")
    dic = Dictionary()
    n = dic.con.execute("SELECT dict, COUNT(*) FROM terms GROUP BY dict").fetchall()
    print("Entrées par dictionnaire:", n)

    print("\n=== Tests de déconjugaison + lookup ===")
    tests = [
        ("前回の続きからゲームを再開します。", 11, "再開"),
        ("前回の続きからゲームを再開します。", 0, "前回"),
        ("前回の続きからゲームを再開します。", 3, "続き"),
        ("前回の続きからゲームを再開します。", 7, "ゲーム"),
        ("ご飯を食べた", 3, "食べる"),
        ("本を読んでいる", 2, "読む"),
        ("行かなければならない", 0, "行く"),
        ("高くなかった", 0, "高い"),
        ("こわくない", 0, "怖い"),
        ("走れば", 0, "走る"),
        ("食べさせられた", 0, "食べる"),
        ("セブンスヘブン", 0, None),
    ]
    ok = 0
    for text, off, expected in tests:
        r = dic.lookup(text, off)
        tops = [(m["expression"], m["reading"], m["matchLen"]) for m in r["matches"][:4]]
        found = expected is None or any(m["expression"] == expected or
                                        m["reading"] == expected
                                        for m in r["matches"][:6])
        status = "OK " if found else "FAIL"
        if found:
            ok += 1
        print(f"[{status}] {text}[{off}:] attendu={expected} -> {tops}")
    print(f"{ok}/{len(tests)} lookups OK")

    print("\n=== Test OCR sur image synthétique ===")
    img = make_test_image(str(RACINE / "tests" / "tmp_pipeline.png"))
    lines = asyncio.run(ocr.ocr_image(img))
    for line in lines:
        print(f"  '{line['text']}'  box={[round(v) for v in line['box']]}")

    print("\n=== Lookup sur ligne OCR ===")
    target = next((l for l in lines if "再開" in l["text"]), None)
    if target:
        idx = target["text"].index("再開")
        r = dic.lookup(target["text"], idx)
        print(f"Survol de '再開' dans '{target['text']}' :")
        for m in r["matches"][:3]:
            gl = m["defs"][0]["glosses"][:2]
            print(f"  {m['expression']} [{m['reading']}] len={m['matchLen']} "
                  f"({m['defs'][0]['lang']}) {gl}")
    else:
        print("FAIL: ligne 再開 non trouvée par l'OCR")


if __name__ == "__main__":
    main()
