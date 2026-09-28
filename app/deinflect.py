# -*- coding: utf-8 -*-

from collections import deque

V1 = "v1"
V5 = "v5"
VS = "vs"
VK = "vk"
ADJ = "adj-i"
MASU = "_masu"

_RULES = []


def _r(kana_in, kana_out, types_in, types_out):
    _RULES.append((kana_in, kana_out, frozenset(types_in) if types_in else None,
                   frozenset(types_out)))


def _build_rules():
    te_map = [
        ("って", "う", {V5}), ("って", "つ", {V5}), ("って", "る", {V5}),
        ("いて", "く", {V5}), ("いで", "ぐ", {V5}), ("して", "す", {V5}),
        ("んで", "ぬ", {V5}), ("んで", "ぶ", {V5}), ("んで", "む", {V5}),
        ("て", "る", {V1, VK}),
    ]
    for te, out, types in te_map:
        voiced = te.endswith("で")
        base = te[:-1]
        d = "だ" if voiced else "た"
        _r(te, out, None, types)
        _r(base + d, out, None, types)
        _r(base + d + "り", out, None, types)
        _r(base + d + "ら", out, None, types)
        chau = "じゃう" if voiced else "ちゃう"
        _r(base + chau, out, {V5}, types)
        _r(base + chau[:-1] + "った", out, None, types)
        _r(te + "いる", out, {V1}, types)
        _r(te + "る", out, {V1}, types)
        _r(te + "おく", out, {V5}, types)

    _r("行って", "行く", None, {V5})
    _r("行った", "行く", None, {V5})
    _r("いって", "いく", None, {V5})
    _r("いった", "いく", None, {V5})

    stem_map = [
        ("い", "う"), ("き", "く"), ("ぎ", "ぐ"), ("し", "す"), ("ち", "つ"),
        ("に", "ぬ"), ("び", "ぶ"), ("み", "む"), ("り", "る"),
    ]
    stem_suffixes = [
        ("ます", {MASU}, None),
        ("たい", None, ADJ),
        ("たがる", None, V5),
        ("なさい", None, None),
        ("ながら", None, None),
        ("すぎる", None, V1),
        ("そう", None, None),
    ]
    for suf, types_in, _out in stem_suffixes:
        for stem, dic in stem_map:
            _r(stem + suf, dic, types_in, {V5})
        _r(suf, "る", types_in, {V1, VK})

    _r("ました", "ます", None, {MASU})
    _r("ません", "ます", None, {MASU})
    _r("ましょう", "ます", None, {MASU})
    _r("まして", "ます", None, {MASU})
    _r("ませんでした", "ます", None, {MASU})
    for stem, dic in stem_map:
        _r(stem + "ます", dic, None, {V5})
    _r("ます", "る", None, {V1, VK})

    a_map = [
        ("わ", "う"), ("か", "く"), ("が", "ぐ"), ("さ", "す"), ("た", "つ"),
        ("な", "ぬ"), ("ば", "ぶ"), ("ま", "む"), ("ら", "る"),
    ]
    for a, dic in a_map:
        _r(a + "ない", dic, None, {V5})
        _r(a + "ず", dic, None, {V5})
        _r(a + "ぬ", dic, None, {V5})
        _r(a + "れる", dic, {V1}, {V5})
        _r(a + "せる", dic, {V1}, {V5})
        _r(a + "なかった", dic, None, {V5})
    _r("ない", "る", None, {V1, VK})
    _r("ず", "る", None, {V1, VK})
    _r("られる", "る", {V1}, {V1, VK})
    _r("させる", "る", {V1}, {V1, VK})
    _r("なかった", "る", None, {V1, VK})

    ba_map = [
        ("えば", "う"), ("けば", "く"), ("げば", "ぐ"), ("せば", "す"),
        ("てば", "つ"), ("ねば", "ぬ"), ("べば", "ぶ"), ("めば", "む"),
        ("れば", "る"),
    ]
    for ba, dic in ba_map:
        _r(ba, dic, None, {V5})
    _r("れば", "る", None, {V1, VK})

    pot_map = [
        ("える", "う"), ("ける", "く"), ("げる", "ぐ"), ("せる", "す"),
        ("てる", "つ"), ("ねる", "ぬ"), ("べる", "ぶ"), ("める", "む"),
        ("れる", "る"),
    ]
    for pot, dic in pot_map:
        _r(pot, dic, {V1}, {V5})

    imp_map = [
        ("え", "う"), ("け", "く"), ("げ", "ぐ"), ("せ", "す"), ("て", "つ"),
        ("ね", "ぬ"), ("べ", "ぶ"), ("め", "む"), ("れ", "る"),
    ]
    for imp, dic in imp_map:
        _r(imp, dic, None, {V5})
    _r("ろ", "る", None, {V1})
    _r("よ", "る", None, {V1})

    vol_map = [
        ("おう", "う"), ("こう", "く"), ("ごう", "ぐ"), ("そう", "す"),
        ("とう", "つ"), ("のう", "ぬ"), ("ぼう", "ぶ"), ("もう", "む"),
        ("ろう", "る"),
    ]
    for vol, dic in vol_map:
        _r(vol, dic, None, {V5})
    _r("よう", "る", None, {V1})

    _r("かった", "い", None, {ADJ})
    _r("くない", "い", None, {ADJ})
    _r("くなかった", "い", None, {ADJ})
    _r("くて", "い", None, {ADJ})
    _r("く", "い", None, {ADJ})
    _r("ければ", "い", None, {ADJ})
    _r("さ", "い", None, {ADJ})
    _r("すぎる", "い", None, {ADJ})
    _r("そう", "い", None, {ADJ})

    for inf in ["した", "して", "しない", "しなかった", "される", "させる",
                "しよう", "すれば", "しろ", "せよ", "します", "しました",
                "しません", "していた", "している", "してる", "しちゃう",
                "しちゃった", "できる"]:
        _r(inf, "する", None, {VS})

    for inf, out in [("きた", "くる"), ("きて", "くる"), ("こない", "くる"),
                     ("こなかった", "くる"), ("きます", "くる"),
                     ("きました", "くる"), ("こよう", "くる"),
                     ("こられる", "くる"), ("こい", "くる"),
                     ("くれば", "くる")]:
        _r(inf, out, None, {VK})
        _r(inf.replace("く", "来", 1) if inf.startswith("く") else "来" + inf[1:],
           "来る", None, {VK})


_build_rules()

MAX_DEPTH = 6


def deinflect(text):
    results = [(text, None)]
    seen = {text}
    queue = deque([(text, None, 0)])
    while queue:
        word, types, depth = queue.popleft()
        if depth >= MAX_DEPTH:
            continue
        for kana_in, kana_out, t_in, t_out in _RULES:
            if not word.endswith(kana_in):
                continue
            if types is not None and t_in is not None and not (types & t_in):
                continue
            if types is not None and t_in is None:
                if not (types & {V1, V5, VS, VK, ADJ, MASU}):
                    continue
            new_word = word[: len(word) - len(kana_in)] + kana_out
            if len(new_word) == 0:
                continue
            key = (new_word, t_out)
            if key in seen:
                continue
            seen.add(key)
            results.append((new_word, t_out))
            queue.append((new_word, t_out, depth + 1))
    return results


def rules_match(entry_rules: str, required_types) -> bool:
    if required_types is None:
        return True
    if not entry_rules:
        return False
    entry_set = set()
    for r in entry_rules.split():
        if r.startswith("v5"):
            entry_set.add(V5)
        elif r == "v1" or r.startswith("v1"):
            entry_set.add(V1)
        elif r == "vs":
            entry_set.add(VS)
        elif r == "vk":
            entry_set.add(VK)
        elif r == "adj-i":
            entry_set.add(ADJ)
        elif r == "vz":
            entry_set.add(V1)
    return bool(entry_set & required_types)
