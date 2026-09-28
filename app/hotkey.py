# -*- coding: utf-8 -*-
import json
from pathlib import Path

import keyboard

import chemins

SETTINGS = chemins.REGLAGES
DEFAULTS = {"capture": "f8", "toggle": "f9", "ghost": "0",
            "freeze": "f11", "bulle": "f7", "zone": "ctrl+shift+a",
            "quitter": "ctrl+shift+q",
            "muet": "f6", "souris": "f2"}
DEFAULT_HOTKEY = DEFAULTS["capture"]

_actions: dict[str, dict] = {}


def _read_settings() -> dict:
    try:
        return json.loads(SETTINGS.read_text("utf-8"))
    except Exception:
        return {}


def _load_hotkey(name: str) -> str:
    data = _read_settings()
    saved = (data.get("hotkeys") or {}).get(name)
    if not saved and name == "capture":
        saved = data.get("hotkey")
    return saved or DEFAULTS.get(name, "f8")


def _save_hotkey(name: str, hk: str):
    data = _read_settings()
    data.setdefault("hotkeys", {})[name] = hk
    data.pop("hotkey", None)
    SETTINGS.write_text(json.dumps(data, indent=2, ensure_ascii=False), "utf-8")


def current(name: str = "capture") -> str:
    a = _actions.get(name)
    if a and a["hotkey"]:
        return a["hotkey"]
    return _load_hotkey(name)


def all_hotkeys() -> dict:
    noms = set(DEFAULTS) | set(_actions) | set(_read_settings().get("hotkeys") or {})
    return {n: current(n) for n in sorted(noms)}


def normalize(hk: str) -> str:
    hk = (hk or "").strip().lower()
    if not hk:
        raise ValueError("raccourci vide")
    keyboard.parse_hotkey(hk)
    if len(hk) == 1 and hk.isalpha():
        raise ValueError("une lettre seule se déclencherait en jouant ou en "
                         "écrivant : ajoute Ctrl, Alt ou Maj, ou prends une "
                         "touche de fonction")
    return hk


def _fire(name: str):
    cb = (_actions.get(name) or {}).get("callback")
    if cb:
        try:
            cb()
        except Exception:
            pass


def _register(name: str, hk: str):
    a = _actions.setdefault(name, {"hotkey": None, "handle": None, "callback": None})
    if a["handle"] is not None:
        try:
            keyboard.remove_hotkey(a["handle"])
        except Exception:
            pass
        a["handle"] = None
    a["handle"] = keyboard.add_hotkey(hk, lambda n=name: _fire(n), suppress=False)
    a["hotkey"] = hk


def register(name: str, callback) -> str:
    a = _actions.setdefault(name, {"hotkey": None, "handle": None, "callback": None})
    a["callback"] = callback
    hk = _load_hotkey(name)
    try:
        _register(name, hk)
    except Exception as e:
        print(f"[hotkey] impossible d'enregistrer '{name}' sur {hk} ({e})")
        a["hotkey"] = hk
    return current(name)


def set_hotkey(hk: str, name: str = "capture") -> str:
    hk = normalize(hk)
    if any(n != name and current(n) == hk for n in _actions):
        raise ValueError("raccourci déjà utilisé par une autre action")
    _register(name, hk)
    _save_hotkey(name, hk)
    return hk


def init(callback) -> str:
    return register("capture", callback)
