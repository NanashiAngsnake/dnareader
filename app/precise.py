# -*- coding: utf-8 -*-
import base64
import importlib.util
import io
import json
import subprocess

import discret
import sys
import threading
from pathlib import Path

BASE = Path(__file__).parent
WORKER = BASE / "precise_worker.py"

try:
    from dictionary import is_jp_char as _is_jp
except Exception:
    def _is_jp(c):
        return "぀" <= c <= "ヿ" or "一" <= c <= "鿿"

_proc = None
_lock = threading.Lock()
_error = None

_MEMOIRE: dict = {}
_MEMOIRE_MAX = 500


def _empreinte(img) -> bytes:
    return img.convert("L").resize((32, 16)).tobytes()


def vider_memoire():
    _MEMOIRE.clear()




def available() -> bool:
    try:
        return importlib.util.find_spec("manga_ocr") is not None
    except Exception:
        return False


def status() -> dict:
    return {"installed": available(), "loaded": _alive(), "error": _error,
            "memorisees": len(_MEMOIRE)}


def _alive() -> bool:
    return _proc is not None and _proc.poll() is None


def _commande_ouvrier(nom: str) -> list:
    import chemins
    if chemins.EMPAQUETEE:
        return [sys.executable, "--ouvrier", nom]
    return [sys.executable, str(WORKER)]


def start():
    global _proc, _error
    with _lock:
        if _alive():
            return True
        if not available():
            _error = "manga-ocr n'est pas installé"
            return False
        flags = discret.drapeaux_processus()
        _proc = subprocess.Popen(
            _commande_ouvrier("precise"),
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, encoding="utf-8", bufsize=1, creationflags=flags,
            env=discret.env_calcul(),
        )
        line = _proc.stdout.readline()
        try:
            msg = json.loads(line or "{}")
        except Exception:
            msg = {}
        if msg.get("ready"):
            _error = None
            return True
        _error = msg.get("fatal") or "démarrage du moteur impossible"
        stop()
        return False


def stop():
    global _proc
    with _lock:
        if _proc is not None:
            try:
                _proc.stdin.write(json.dumps({"quit": True}) + "\n")
                _proc.stdin.flush()
                _proc.wait(timeout=3)
            except Exception:
                try:
                    _proc.kill()
                except Exception:
                    pass
            _proc = None


def _read_one(img) -> str | None:
    if not _alive():
        return None
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    req = json.dumps({"img": base64.b64encode(buf.getvalue()).decode()})
    try:
        with _lock:
            _proc.stdin.write(req + "\n")
            _proc.stdin.flush()
            line = _proc.stdout.readline()
        return (json.loads(line or "{}") or {}).get("text")
    except Exception:
        return None


def _pad(box, w, h):
    x, y, bw, bh = box
    mx = max(10, bh * 0.6)
    my = max(6, bh * 0.25)
    return (max(0, int(x - mx)), max(0, int(y - my)),
            min(w, int(x + bw + mx)), min(h, int(y + bh + my)))


def _normalize(text: str) -> str:
    out = []
    for c in text:
        o = ord(c)
        if 0xFF01 <= o <= 0xFF5E:
            out.append(chr(o - 0xFEE0))
        elif o == 0x3000:
            out.append(" ")
        else:
            out.append(c)
    return "".join(out)


def refine_lines(img, lines, min_chars=1, a_relire=None):
    if not start():
        return lines
    W, H = img.width, img.height
    out = []
    for line in lines:
        box = line.get("box")
        if not box or box[2] < 6 or box[3] < 6:
            out.append(line)
            continue
        if not any(_is_jp(c) for c in line.get("text", "")):
            out.append(line)
            continue
        if a_relire is not None and not a_relire(line):
            out.append(line)
            continue
        x1, y1, x2, y2 = _pad(box, W, H)
        decoupe = img.crop((x1, y1, x2, y2))
        cle = _empreinte(decoupe)
        if cle in _MEMOIRE:
            text = _MEMOIRE[cle]
        else:
            text = _read_one(decoupe)
            if text is not None:
                if len(_MEMOIRE) >= _MEMOIRE_MAX:
                    _MEMOIRE.pop(next(iter(_MEMOIRE)))
                _MEMOIRE[cle] = text
        if text is None:
            out.append(line)
            continue
        text = _normalize(text.strip())
        if len(text) < min_chars:
            continue
        n = len(text)
        bx, by, bw, bh = box
        cw = bw / n
        out.append({"text": text, "box": box, "alt": line.get("text", ""),
                    "chars": [[bx + i * cw, by, cw, bh] for i in range(n)]})
    return out
