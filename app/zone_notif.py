# -*- coding: utf-8 -*-
import ctypes
import threading
from ctypes import wintypes
from pathlib import Path

import chemins

_u32 = ctypes.windll.user32
_shell = ctypes.windll.shell32
_k32 = ctypes.windll.kernel32

WM_DESTROY = 0x0002
WM_COMMAND = 0x0111
WM_LBUTTONUP = 0x0202
WM_RBUTTONUP = 0x0205
WM_APP_ICONE = 0x0400 + 20

NIM_ADD, NIM_MODIFY, NIM_DELETE = 0, 1, 2
NIF_MESSAGE, NIF_ICON, NIF_TIP = 0x01, 0x02, 0x04
IMAGE_ICON, LR_LOADFROMFILE, LR_DEFAULTSIZE = 1, 0x0010, 0x0040
MF_STRING, MF_SEPARATOR = 0x0000, 0x0800
TPM_RIGHTBUTTON, TPM_RETURNCMD = 0x0002, 0x0100
TPM_LEFTALIGN, TPM_RIGHTALIGN = 0x0000, 0x0008
TPM_TOPALIGN, TPM_BOTTOMALIGN = 0x0000, 0x0020
TPM_WORKAREA = 0x10000

WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.c_uint,
                             ctypes.c_void_p, ctypes.c_void_p)


class WNDCLASS(ctypes.Structure):
    _fields_ = [("style", ctypes.c_uint), ("lpfnWndProc", WNDPROC),
                ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int),
                ("hInstance", ctypes.c_void_p), ("hIcon", ctypes.c_void_p),
                ("hCursor", ctypes.c_void_p), ("hbrBackground", ctypes.c_void_p),
                ("lpszMenuName", wintypes.LPCWSTR), ("lpszClassName", wintypes.LPCWSTR)]


class NOTIFYICONDATA(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("hWnd", ctypes.c_void_p),
                ("uID", ctypes.c_uint), ("uFlags", ctypes.c_uint),
                ("uCallbackMessage", ctypes.c_uint), ("hIcon", ctypes.c_void_p),
                ("szTip", ctypes.c_wchar * 128), ("dwState", wintypes.DWORD),
                ("dwStateMask", wintypes.DWORD), ("szInfo", ctypes.c_wchar * 256),
                ("uVersion", ctypes.c_uint), ("szInfoTitle", ctypes.c_wchar * 64),
                ("dwInfoFlags", wintypes.DWORD)]


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


for _f, _ret, _args in (
    ("AppendMenuW", wintypes.BOOL, [ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, wintypes.LPCWSTR]),
    ("TrackPopupMenu", ctypes.c_int, [ctypes.c_void_p, ctypes.c_uint, ctypes.c_int,
                                      ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p]),
    ("TrackPopupMenuEx", ctypes.c_int, [ctypes.c_void_p, ctypes.c_uint, ctypes.c_int,
                                        ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p]),
    ("SystemParametersInfoW", wintypes.BOOL, [ctypes.c_uint, ctypes.c_uint,
                                              ctypes.c_void_p, ctypes.c_uint]),
    ("GetWindowRect", wintypes.BOOL, [ctypes.c_void_p, ctypes.c_void_p]),
    ("DestroyMenu", wintypes.BOOL, [ctypes.c_void_p]),
    ("SetForegroundWindow", wintypes.BOOL, [ctypes.c_void_p]),
    ("PostMessageW", wintypes.BOOL, [ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_void_p]),
    ("DefWindowProcW", ctypes.c_long, [ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_void_p]),
    ("RegisterClassW", ctypes.c_ushort, [ctypes.c_void_p]),
):
    try:
        _fn = getattr(_u32, _f)
        _fn.restype = _ret
        _fn.argtypes = _args
    except Exception:
        pass
_shell.Shell_NotifyIconW.restype = wintypes.BOOL
_shell.Shell_NotifyIconW.argtypes = [wintypes.DWORD, ctypes.c_void_p]

_etat = {"hwnd": None, "thread": None, "proc": None, "actions": {},
         "erreur": None, "posee": False}


def _charge_icone():
    for p in (chemins.ICONE,):
        if not p.exists():
            continue
        _u32.LoadImageW.restype = ctypes.c_void_p
        _u32.LoadImageW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR, ctypes.c_uint,
                                    ctypes.c_int, ctypes.c_int, ctypes.c_uint]
        h = _u32.LoadImageW(None, str(p), IMAGE_ICON, 0, 0,
                            LR_LOADFROMFILE | LR_DEFAULTSIZE)
        if h:
            return h
    _u32.LoadIconW.restype = ctypes.c_void_p
    return _u32.LoadIconW(None, ctypes.c_wchar_p(32512))


class TPMPARAMS(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.UINT), ("rcExclude", wintypes.RECT)]


def _rect_barre_taches():
    try:
        _u32.FindWindowW.restype = ctypes.c_void_p
        _u32.FindWindowW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p]
        h = _u32.FindWindowW("Shell_TrayWnd", None)
        if not h:
            return None
        r = wintypes.RECT()
        _u32.GetWindowRect(ctypes.c_void_p(h), ctypes.byref(r))
        return r
    except Exception:
        return None


def _alignement(pt) -> int:
    zone = wintypes.RECT()
    try:
        if not _u32.SystemParametersInfoW(0x0030, 0, ctypes.byref(zone), 0):
            raise OSError
    except Exception:
        return TPM_LEFTALIGN | TPM_TOPALIGN
    milieu_x = (zone.left + zone.right) // 2
    milieu_y = (zone.top + zone.bottom) // 2
    return ((TPM_RIGHTALIGN if pt.x > milieu_x else TPM_LEFTALIGN)
            | (TPM_BOTTOMALIGN if pt.y > milieu_y else TPM_TOPALIGN))


def _menu(hwnd, entrees):
    _u32.CreatePopupMenu.restype = ctypes.c_void_p
    m = _u32.CreatePopupMenu()
    for ident, libelle in entrees:
        if libelle == "-":
            _u32.AppendMenuW(ctypes.c_void_p(m), MF_SEPARATOR, 0, None)
        else:
            _u32.AppendMenuW(ctypes.c_void_p(m), MF_STRING, ident, libelle)
    pt = POINT()
    _u32.GetCursorPos(ctypes.byref(pt))
    _u32.SetForegroundWindow(ctypes.c_void_p(hwnd))

    drapeaux = TPM_RIGHTBUTTON | TPM_RETURNCMD | TPM_WORKAREA | _alignement(pt)
    tpm = TPMPARAMS()
    tpm.cbSize = ctypes.sizeof(TPMPARAMS)
    barre = _rect_barre_taches()
    if barre is not None:
        tpm.rcExclude = barre
    _u32.TrackPopupMenuEx.restype = wintypes.BOOL
    choix = _u32.TrackPopupMenuEx(ctypes.c_void_p(m), drapeaux, pt.x, pt.y,
                                  ctypes.c_void_p(hwnd),
                                  ctypes.byref(tpm) if barre is not None else None)
    _u32.PostMessageW(ctypes.c_void_p(hwnd), 0x0000, 0, 0)
    _u32.DestroyMenu(ctypes.c_void_p(m))
    return choix


def _boucle(titre, entrees):
    def wndproc(hwnd, msg, wparam, lparam):
        if msg == WM_APP_ICONE:
            bas = (int(lparam) if lparam else 0) & 0xFFFF
            if bas == WM_RBUTTONUP:
                choix = _menu(hwnd, entrees)
                if choix:
                    fn = _etat["actions"].get(choix)
                    if fn:
                        threading.Thread(target=fn, daemon=True).start()
            elif bas == WM_LBUTTONUP:
                fn = _etat["actions"].get(1)
                if fn:
                    threading.Thread(target=fn, daemon=True).start()
            return 0
        if msg == WM_DESTROY:
            _u32.PostQuitMessage(0)
            return 0
        return _u32.DefWindowProcW(ctypes.c_void_p(hwnd), msg,
                                   ctypes.c_void_p(wparam), ctypes.c_void_p(lparam))

    proc = WNDPROC(wndproc)
    _etat["proc"] = proc

    cls = WNDCLASS()
    cls.lpfnWndProc = proc
    cls.lpszClassName = "DNAreaderZoneNotif"
    _k32.GetModuleHandleW.restype = ctypes.c_void_p
    _k32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
    cls.hInstance = _k32.GetModuleHandleW(None)
    if not _u32.RegisterClassW(ctypes.byref(cls)):
        pass

    _u32.CreateWindowExW.restype = ctypes.c_void_p
    _u32.CreateWindowExW.argtypes = [
        wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
        ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
    _k32.GetModuleHandleW.restype = ctypes.c_void_p
    _k32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
    hwnd = _u32.CreateWindowExW(0, "DNAreaderZoneNotif", titre, 0,
                                0, 0, 0, 0, None, None, cls.hInstance, None)
    if not hwnd:
        _etat["erreur"] = "fenetre de service impossible"
        return
    _etat["hwnd"] = hwnd

    nid = NOTIFYICONDATA()
    nid.cbSize = ctypes.sizeof(NOTIFYICONDATA)
    nid.hWnd = hwnd
    nid.uID = 1
    nid.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
    nid.uCallbackMessage = WM_APP_ICONE
    nid.hIcon = _charge_icone()
    nid.szTip = titre[:127]
    if not _shell.Shell_NotifyIconW(NIM_ADD, ctypes.byref(nid)):
        _etat["erreur"] = "icone refusee par la zone de notification"
        return
    _etat["posee"] = True

    msg = wintypes.MSG()
    while _u32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
        _u32.TranslateMessage(ctypes.byref(msg))
        _u32.DispatchMessageW(ctypes.byref(msg))

    _shell.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(nid))
    _etat["posee"] = False


def demarre(titre: str, entrees, actions: dict) -> dict:
    if _etat["thread"] and _etat["thread"].is_alive():
        return {"ok": True, "deja": True}
    _etat["actions"] = dict(actions)
    t = threading.Thread(target=_boucle, args=(titre, entrees), daemon=True)
    _etat["thread"] = t
    t.start()
    for _ in range(40):
        if _etat["posee"] or _etat["erreur"]:
            break
        import time
        time.sleep(0.05)
    return {"ok": bool(_etat["posee"]), "error": _etat["erreur"]}


def arrete() -> None:
    h = _etat.get("hwnd")
    if h:
        _u32.PostMessageW(ctypes.c_void_p(h), WM_DESTROY, 0, 0)


def status() -> dict:
    return {"posee": bool(_etat["posee"]), "erreur": _etat["erreur"]}
