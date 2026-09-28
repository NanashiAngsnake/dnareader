# -*- coding: utf-8 -*-

import ctypes

import mss
import pygetwindow as gw
from PIL import Image

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


def list_windows():
    seen = set()
    titles = []
    for t in gw.getAllTitles():
        t = t.strip()
        if t and t not in seen:
            seen.add(t)
            titles.append(t)
    return titles


def _sub_rect(left, top, width, height, region):
    if not region:
        return {"left": left, "top": top, "width": width, "height": height}
    try:
        fx, fy, fw, fh = region
        x1 = left + max(0, int(fx * width))
        y1 = top + max(0, int(fy * height))
        w = min(width - (x1 - left), int(fw * width))
        h = min(height - (y1 - top), int(fh * height))
        if w >= 10 and h >= 10:
            return {"left": x1, "top": y1, "width": w, "height": h}
    except Exception:
        pass
    return {"left": left, "top": top, "width": width, "height": height}


_zone_app = None


def set_zone_app(fn):
    global _zone_app
    _zone_app = fn


def _effacer_notre_fenetre(img: Image.Image, mon) -> Image.Image:
    if _zone_app is None:
        return img
    try:
        r = _zone_app()
        if not r:
            return img
        l, t, rr, b = r
        x1 = max(0, int(l) - int(mon["left"]))
        y1 = max(0, int(t) - int(mon["top"]))
        x2 = min(img.width, int(rr) - int(mon["left"]))
        y2 = min(img.height, int(b) - int(mon["top"]))
        if x2 - x1 > 1 and y2 - y1 > 1:
            img.paste((0, 0, 0), (x1, y1, x2, y2))
    except Exception:
        pass
    return img


_masquer = None


def set_masquage(fn):
    global _masquer
    _masquer = fn


def _grab(mon) -> Image.Image:
    masque = False
    if _masquer is not None:
        try:
            masque = bool(_masquer(True))
        except Exception:
            masque = False
    try:
        with mss.mss() as sct:
            shot = sct.grab(mon)
            img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
    finally:
        if masque:
            try:
                _masquer(False)
            except Exception:
                pass
    return img if masque else _effacer_notre_fenetre(img, mon)


def capture_window(title: str, region=None) -> Image.Image:
    wins = gw.getWindowsWithTitle(title)
    if not wins:
        raise ValueError(f"Fenêtre introuvable : {title}")
    win = next((w for w in wins if w.title == title), wins[0])
    if win.isMinimized:
        raise ValueError("La fenêtre est réduite : restaure-la d'abord.")
    left, top = max(win.left, 0), max(win.top, 0)
    width = min(win.width, 10000)
    height = min(win.height, 10000)
    if width < 20 or height < 20:
        raise ValueError("Fenêtre trop petite pour être capturée.")
    return _grab(_sub_rect(left, top, width, height, region))


_u32 = ctypes.windll.user32
GA_ROOT = 2


class _POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


def _fenetre_au_point(x, y):
    _u32.WindowFromPoint.restype = ctypes.c_void_p
    _u32.WindowFromPoint.argtypes = [_POINT]
    _u32.GetAncestor.restype = ctypes.c_void_p
    _u32.GetAncestor.argtypes = [ctypes.c_void_p, ctypes.c_uint]
    h = _u32.WindowFromPoint(_POINT(int(x), int(y)))
    return _u32.GetAncestor(ctypes.c_void_p(h), GA_ROOT) if h else None


def _titre_de(hwnd) -> str:
    _u32.GetWindowTextLengthW.argtypes = [ctypes.c_void_p]
    _u32.GetWindowTextW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_int]
    n = _u32.GetWindowTextLengthW(ctypes.c_void_p(hwnd))
    buf = ctypes.create_unicode_buffer(n + 1)
    _u32.GetWindowTextW(ctypes.c_void_p(hwnd), buf, n + 1)
    return buf.value


def _pid_de(hwnd) -> int:
    _u32.GetWindowThreadProcessId.argtypes = [ctypes.c_void_p,
                                              ctypes.POINTER(ctypes.c_ulong)]
    pid = ctypes.c_ulong()
    _u32.GetWindowThreadProcessId(ctypes.c_void_p(hwnd), ctypes.byref(pid))
    return int(pid.value)


def couverte_par(title: str, region=None):
    try:
        import os
        wins = gw.getWindowsWithTitle(title)
        if not wins:
            return None
        win = next((w for w in wins if w.title == title), wins[0])
        if win.isMinimized:
            return None
        zone = _sub_rect(max(win.left, 0), max(win.top, 0),
                         win.width, win.height, region)
        cible = getattr(win, "_hWnd", None)
        for fx, fy in ((0.5, 0.5), (0.5, 0.82)):
            x = zone["left"] + zone["width"] * fx
            y = zone["top"] + zone["height"] * fy
            h = _fenetre_au_point(x, y)
            if not h or (cible and int(h) == int(cible)):
                continue
            if _pid_de(h) == os.getpid():
                continue
            nom = _titre_de(h).strip()
            if nom and nom != title:
                return nom
        return None
    except Exception:
        return None


QUNS_RUNNING_D3D_FULL_SCREEN = 3


def _etat_notifications() -> int:
    try:
        etat = ctypes.c_int()
        if ctypes.windll.shell32.SHQueryUserNotificationState(
                ctypes.byref(etat)) == 0:
            return int(etat.value)
    except Exception:
        pass
    return 0


def _image_muette(img, seuil=10) -> bool:
    try:
        petite = img.resize((64, 36), Image.NEAREST).convert("L")
        return petite.getextrema()[1] <= seuil
    except Exception:
        return False


def plein_ecran_exclusif(img=None) -> str:
    if _etat_notifications() != QUNS_RUNNING_D3D_FULL_SCREEN:
        return ""
    if img is not None and not _image_muette(img):
        return ""
    return "plein ecran exclusif"


def capture_screen(region=None) -> Image.Image:
    with mss.mss() as sct:
        mon = sct.monitors[1]
    return _grab(_sub_rect(mon["left"], mon["top"], mon["width"], mon["height"], region))
