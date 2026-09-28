# -*- coding: utf-8 -*-

import json
import re
import sqlite3
import threading
from pathlib import Path

from deinflect import deinflect, rules_match, VS

import chemins

DB_PATH = chemins.DB_DICTIONNAIRE

MAX_SCAN = 22

_JP_CHAR = re.compile(
    r"[぀-ゟ゠-ヿ一-鿿㐀-䶿ｦ-ﾟ"
    r"ー々〆仝々〆〤ヶ]"
)


def is_jp_char(ch: str) -> bool:
    return bool(_JP_CHAR.match(ch))


def kata_to_hira(s: str) -> str:
    out = []
    for ch in s:
        o = ord(ch)
        if 0x30A1 <= o <= 0x30F6:
            out.append(chr(o - 0x60))
        else:
            out.append(ch)
    return "".join(out)


def _flatten_content(node, out, buf):
    if node is None:
        return
    if isinstance(node, str):
        buf.append(node)
        return
    if isinstance(node, list):
        for child in node:
            _flatten_content(child, out, buf)
        return
    if isinstance(node, dict):
        data = node.get("data") or {}
        dc = data.get("content", "")
        if dc in ("example-sentence", "extra-info", "examples"):
            return
        tag = node.get("tag", "")
        if tag == "li":
            sub_buf = []
            _flatten_content(node.get("content"), out, sub_buf)
            text = "".join(sub_buf).strip()
            if text:
                out.append(text)
            return
        if tag == "rt":
            return
        _flatten_content(node.get("content"), out, buf)


def flatten_glosses(glosses) -> list:
    out = []
    for g in glosses:
        if isinstance(g, str):
            out.append(g)
        elif isinstance(g, dict) and g.get("type") == "structured-content":
            buf = []
            _flatten_content(g.get("content"), out, buf)
            text = "".join(buf).strip()
            if text:
                out.append(text)
        elif isinstance(g, dict) and g.get("type") == "text":
            out.append(str(g.get("text", "")))
    seen = set()
    res = []
    for g in out:
        g = g.strip()
        if g and g not in seen:
            seen.add(g)
            res.append(g)
    return res


LANGUES_DICO = ("fr", "en")


def langue_dico(langue: str) -> str:
    return "fr" if (langue or "").lower().startswith("fr") else "en"


def build_db(force=False):
    if DB_PATH.exists() and not force:
        return
    tmp = DB_PATH.with_suffix(".tmp")
    if tmp.exists():
        tmp.unlink()
    con = sqlite3.connect(tmp)
    con.execute(
        """CREATE TABLE terms(
            id INTEGER PRIMARY KEY, expr TEXT, reading TEXT, def_tags TEXT,
            rules TEXT, score INTEGER, glosses TEXT, seq INTEGER,
            term_tags TEXT, dict TEXT)"""
    )
    con.execute("CREATE TABLE tags(name TEXT, dict TEXT, category TEXT, notes TEXT)")
    for lang, folder in [("fr", "french"), ("en", "english")]:
        d = chemins.DICTS / folder
        if not d.exists():
            continue
        for tb in sorted(d.glob("term_bank_*.json")):
            rows = json.loads(tb.read_text(encoding="utf-8"))
            batch = []
            for e in rows:
                expr, reading, def_tags, rules, score, glosses, seq, term_tags = e[:8]
                flat = flatten_glosses(glosses)
                if not flat:
                    continue
                batch.append((expr, reading or "", def_tags or "", rules or "",
                              score or 0, json.dumps(flat, ensure_ascii=False),
                              seq or 0, term_tags or "", lang))
            con.executemany(
                "INSERT INTO terms(expr,reading,def_tags,rules,score,glosses,seq,term_tags,dict)"
                " VALUES (?,?,?,?,?,?,?,?,?)", batch)
        for tb in sorted(d.glob("tag_bank_*.json")):
            rows = json.loads(tb.read_text(encoding="utf-8"))
            con.executemany(
                "INSERT INTO tags(name,dict,category,notes) VALUES (?,?,?,?)",
                [(r[0], lang, r[1], r[3]) for r in rows])
    con.execute("CREATE INDEX idx_expr ON terms(expr)")
    con.execute("CREATE INDEX idx_reading ON terms(reading)")
    con.commit()
    con.close()
    tmp.replace(DB_PATH)


class Dictionary:
    def __init__(self):
        build_db()
        self._fils = threading.local()
        self.tags = {}
        for name, dic, cat, notes in self.con.execute(
                "SELECT name,dict,category,notes FROM tags"):
            self.tags.setdefault(name, {"category": cat, "notes": notes})

    @property
    def con(self):
        c = getattr(self._fils, "con", None)
        if c is None:
            c = sqlite3.connect(DB_PATH)
            self._fils.con = c
        return c

    def _query(self, terms, by_reading_terms):
        rows = []
        if terms:
            q = ",".join("?" * len(terms))
            rows += self.con.execute(
                f"SELECT expr,reading,def_tags,rules,score,glosses,seq,term_tags,dict"
                f" FROM terms WHERE expr IN ({q})", list(terms)).fetchall()
        if by_reading_terms:
            q = ",".join("?" * len(by_reading_terms))
            rows += self.con.execute(
                f"SELECT expr,reading,def_tags,rules,score,glosses,seq,term_tags,dict"
                f" FROM terms WHERE reading IN ({q})", list(by_reading_terms)).fetchall()
        return rows

    def lookup(self, text: str, offset: int, max_results=32, langue: str = "fr"):
        langue = langue_dico(langue)
        sub = []
        for ch in text[offset:offset + MAX_SCAN]:
            if not is_jp_char(ch):
                break
            sub.append(ch)
        sub = "".join(sub)
        if not sub:
            return {"matchLen": 0, "matches": []}

        groups = {}
        best_len = 0
        for length in range(len(sub), 0, -1):
            surface = sub[:length]
            candidates = deinflect(surface)
            hira = kata_to_hira(surface)
            exprs = {c[0] for c in candidates}
            readings = {c[0] for c in candidates if _is_kana(c[0])}
            if _is_kana(surface):
                readings.add(hira)
                exprs.add(hira)
            rows = self._query(exprs, readings)
            cand_types = {c[0]: c[1] for c in candidates}
            hits = []
            for expr, reading, def_tags, rules, score, glosses, seq, term_tags, dic in rows:
                matched = None
                for cand, types in cand_types.items():
                    if expr == cand or (reading == cand and _is_kana(surface)) \
                       or (_is_kana(surface) and reading == hira):
                        if types is None or rules_match(rules, types):
                            matched = cand
                            break
                if matched is None:
                    continue
                hits.append((expr, reading, def_tags, rules, score, glosses,
                             seq, term_tags, dic))
            for cand, types in cand_types.items():
                if types and VS in types and cand.endswith("する") and len(cand) > 2:
                    stem = cand[:-2]
                    for row in self._query({stem}, set()):
                        if "vs" in f"{row[2]} {row[3]} {row[7]}":
                            hits.append(row)
            if hits and best_len == 0:
                best_len = length
            for expr, reading, def_tags, rules, score, glosses, seq, term_tags, dic in hits:
                key = (expr, reading)
                g = groups.get(key)
                if g is None:
                    g = {
                        "expression": expr, "reading": reading,
                        "matchLen": length, "score": score,
                        "tags": _split_tags(def_tags) + _split_tags(term_tags),
                        "defs": [],
                    }
                    groups[key] = g
                g["defs"].append({"lang": dic, "glosses": json.loads(glosses)})
                g["score"] = max(g["score"], score)
            if len(groups) >= max_results:
                break

        matches = sorted(
            groups.values(),
            key=lambda m: (-m["matchLen"], -m["score"], len(m["expression"])))
        for m in matches:
            m["defs"].sort(key=lambda d: 0 if d["lang"] == langue else 1)
            m["tags"] = list(dict.fromkeys(m["tags"]))[:8]
            merged = []
            for d in m["defs"]:
                prev = next((p for p in merged if p["lang"] == d["lang"]), None)
                if prev is None:
                    merged.append({"lang": d["lang"], "glosses": list(d["glosses"])})
                else:
                    prev["glosses"] += [g for g in d["glosses"]
                                        if g not in prev["glosses"]]
            m["defs"] = merged
        return {"matchLen": best_len, "matches": matches[:max_results]}

    def tag_info(self, name):
        return self.tags.get(name)


def _is_kana(s: str) -> bool:
    return all(0x3040 <= ord(c) <= 0x30FF or c == "ー" for c in s)


def _split_tags(s: str):
    return [t for t in (s or "").split() if t]
