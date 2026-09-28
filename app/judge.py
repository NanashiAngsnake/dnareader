# -*- coding: utf-8 -*-

from dictionary import is_jp_char

_SUSPECTES = tuple(
    [c + v for c in "フヴ" for v in "アイエオ"]
    + [c + "イ" for c in "テデ"]
    + [c + v for c in "キギシジチニヒビピミリ" for v in "ヤユヨ"]
)
_KATA = set("ァアィイゥウェエォオカガキギクグケゲコゴサザシジスズセゼソゾタダチヂッツヅテデトド"
            "ナニヌネノハバパヒビピフブプヘベペホボポマミムメモャヤュユョヨラリルレロヮワヰヱヲンヴー")


def _suspect(mot: str) -> int:
    return sum(mot.count(d) for d in _SUSPECTES)


def _known(dic, word: str) -> bool:
    if not word:
        return False
    cur = dic.con.execute(
        "SELECT 1 FROM terms WHERE expr = ? OR reading = ? LIMIT 1", (word, word))
    return cur.fetchone() is not None


def score(text: str, dic, tagger) -> float:
    if not text:
        return 0.0
    total = sum(1 for c in text if is_jp_char(c))
    if total == 0:
        return 0.0
    covered = 0.0
    for tok in tagger(text):
        surf = tok.surface
        n = sum(1 for c in surf if is_jp_char(c))
        if n == 0:
            continue
        lemma = ""
        try:
            lemma = (tok.feature.lemma or "").split("-")[0]
        except Exception:
            pass
        if _known(dic, surf) or (lemma and _known(dic, lemma)):
            covered += n if n > 1 else 0.5
        elif n > 1 and all(c in _KATA for c in surf) and not _suspect(surf):
            covered += n * 0.5
    note = (covered - 1.5 * _suspect(text)) / total
    return max(0.0, min(1.0, note))


def pick(a: str, b: str, dic, tagger, margin: float = 0.0):
    sa, sb = score(a, dic, tagger), score(b, dic, tagger)
    return (a, sa, sb) if sa > sb + margin else (b, sa, sb)
