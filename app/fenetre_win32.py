# -*- coding: utf-8 -*-

import ctypes
import time
from ctypes import wintypes

import pygetwindow as gw

import chemins


_u32 = ctypes.windll.user32
GWL_STYLE = -16
WS_CAPTION = 0x00C00000
WS_THICKFRAME = 0x00040000
WS_MINIMIZEBOX = 0x00020000
WS_MAXIMIZEBOX = 0x00010000
WS_SYSMENU = 0x00080000
FRAME_BITS = WS_CAPTION | WS_THICKFRAME | WS_MINIMIZEBOX | WS_MAXIMIZEBOX | WS_SYSMENU
SWP_NOMOVE, SWP_NOSIZE, SWP_NOZORDER, SWP_FRAMECHANGED = 0x0002, 0x0001, 0x0004, 0x0020

_u32.InvalidateRect.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_bool]
_u32.UpdateWindow.argtypes = [ctypes.c_void_p]
WM_NCLBUTTONDOWN, HTCAPTION = 0x00A1, 2
HWND_TOPMOST, HWND_NOTOPMOST = -1, -2
GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
LWA_ALPHA = 0x00000002
_u32.GetWindowLongPtrW.restype = ctypes.c_longlong
_u32.GetWindowLongPtrW.argtypes = [ctypes.c_void_p, ctypes.c_int]
_u32.SetWindowLongPtrW.restype = ctypes.c_longlong
_u32.SetWindowLongPtrW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_longlong]
_u32.SetLayeredWindowAttributes.argtypes = [ctypes.c_void_p, ctypes.c_uint,
                                            ctypes.c_ubyte, ctypes.c_uint]


ICON_PATH = str(chemins.ICONE)
IMAGE_ICON, LR_LOADFROMFILE = 1, 0x00000010
WM_SETICON, ICON_SMALL, ICON_BIG = 0x0080, 0, 1




def _set_window_icon(hwnd):
    try:
        _u32.LoadImageW.restype = ctypes.c_void_p
        _u32.LoadImageW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_uint,
                                    ctypes.c_int, ctypes.c_int, ctypes.c_uint]
        _u32.SendMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint,
                                      ctypes.c_void_p, ctypes.c_void_p]
        for size, which in ((16, ICON_SMALL), (32, ICON_BIG)):
            h = _u32.LoadImageW(None, ICON_PATH, IMAGE_ICON, size, size, LR_LOADFROMFILE)
            if h:
                _u32.SendMessageW(hwnd, WM_SETICON, ctypes.c_void_p(which), ctypes.c_void_p(h))
        return True
    except Exception as e:
        print(f"[overlay] icône non appliquée ({e})")
        return False


CF_UNICODETEXT = 13


def _clipboard_text():
    try:
        if not _u32.OpenClipboard(None):
            return None
        try:
            h = _u32.GetClipboardData(CF_UNICODETEXT)
            if not h:
                return None
            k32 = ctypes.windll.kernel32
            k32.GlobalLock.restype = ctypes.c_void_p
            p = k32.GlobalLock(ctypes.c_void_p(h))
            if not p:
                return None
            try:
                return ctypes.c_wchar_p(p).value
            finally:
                k32.GlobalUnlock(ctypes.c_void_p(h))
        finally:
            _u32.CloseClipboard()
    except Exception:
        return None


def _force_foreground(hwnd) -> bool:
    try:
        if _u32.GetForegroundWindow() == hwnd:
            return True
        k32 = ctypes.windll.kernel32
        cur = k32.GetCurrentThreadId()
        fg = _u32.GetForegroundWindow()
        other = _u32.GetWindowThreadProcessId(fg, None) if fg else 0
        target = _u32.GetWindowThreadProcessId(hwnd, None)
        for t in {other, target} - {0, cur}:
            _u32.AttachThreadInput(cur, t, True)
        try:
            _u32.BringWindowToTop(hwnd)
            _u32.SetForegroundWindow(hwnd)
        finally:
            for t in {other, target} - {0, cur}:
                _u32.AttachThreadInput(cur, t, False)
        time.sleep(0.05)
        return _u32.GetForegroundWindow() == hwnd
    except Exception:
        return False


def _echelle(window) -> float:
    try:
        _u32.GetDpiForWindow.restype = ctypes.c_uint
        _u32.GetDpiForWindow.argtypes = [ctypes.c_void_p]
        dpi = _u32.GetDpiForWindow(ctypes.c_void_p(_hwnd_of(window)))
        if dpi:
            return dpi / 96.0
    except Exception:
        pass
    return 1.0


def _place(window, x, y, w, h):
    try:
        hwnd = ctypes.c_void_p(_hwnd_of(window))
        _u32.SetWindowPos(hwnd, None, int(x), int(y), int(w), int(h), SWP_NOZORDER)
        _u32.InvalidateRect(hwnd, None, True)
        _u32.UpdateWindow(hwnd)
        return True
    except Exception:
        return False


def _rect_fenetre(window):
    try:
        r = wintypes.RECT()
        if not _u32.GetWindowRect(ctypes.c_void_p(_hwnd_of(window)), ctypes.byref(r)):
            return None
        if r.right - r.left <= 1 or r.bottom - r.top <= 1:
            return None
        m = 3
        return (r.left - m, r.top - m, r.right + m, r.bottom + m)
    except Exception:
        return None


def _hwnd_of(window):
    h = window.native.Handle
    return int(h.ToInt64()) if hasattr(h, "ToInt64") else int(h)


def _set_framed(hwnd, framed: bool):
    st = _u32.GetWindowLongPtrW(hwnd, GWL_STYLE)
    st = (st | FRAME_BITS) if framed else (st & ~FRAME_BITS)
    _u32.SetWindowLongPtrW(hwnd, GWL_STYLE, st)
    _u32.SetWindowPos(hwnd, 0, 0, 0, 0, 0,
                      SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED)


def _opaque(hwnd):
    try:
        h = ctypes.c_void_p(hwnd) if not isinstance(hwnd, ctypes.c_void_p) else hwnd
        st = _u32.GetWindowLongPtrW(h, GWL_EXSTYLE)
        _u32.SetWindowLongPtrW(h, GWL_EXSTYLE, st & ~WS_EX_LAYERED)
        _u32.InvalidateRect(h, None, True)
        _u32.UpdateWindow(h)
        return True
    except Exception:
        return False


def _set_topmost(window, hwnd, on: bool):
    form = getattr(window, "native", None)
    done = False
    if form is not None:
        try:
            from System import Action
            if form.InvokeRequired:
                form.Invoke(Action(lambda: setattr(form, "TopMost", on)))
            else:
                form.TopMost = on
            done = True
        except Exception:
            done = False
    if not done:
        try:
            window._Window__on_top = on
        except Exception:
            pass
    if hwnd:
        _u32.SetWindowPos(hwnd, HWND_TOPMOST if on else HWND_NOTOPMOST,
                          0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE)

def _screen_height():
    try:
        return ctypes.windll.user32.GetSystemMetrics(1)
    except Exception:
        return 1080


def _find_win(title):
    try:
        wins = gw.getWindowsWithTitle(title)
        return next((w for w in wins if w.title == title), wins[0] if wins else None)
    except Exception:
        return None


def _game_rect(title):
    win = _find_win(title)
    if win and not win.isMinimized and win.width > 20:
        return (max(win.left, 0), max(win.top, 0), win.width, win.height)
    return None
