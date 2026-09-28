# -*- coding: utf-8 -*-
import base64
import ctypes
import io
import json
import threading
import os
import pathlib
import sys
import time
import urllib.request
from ctypes import wintypes

import uvicorn
import webview
from PIL import ImageGrab

for _flux in (sys.stdout, sys.stderr):
    try:
        _flux.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from fenetre_win32 import (_u32, GWL_EXSTYLE, WS_EX_LAYERED, WS_EX_TRANSPARENT,
                           LWA_ALPHA, SWP_NOSIZE, SWP_NOZORDER,
                           _set_window_icon, _clipboard_text, _force_foreground,
                           _echelle, _place, _rect_fenetre, _hwnd_of,
                           _set_framed, _set_topmost, _screen_height, _opaque,
                           _find_win, _game_rect)
import discret
import highlight
import hotkey
import picker
from server import app

PORT = 8766

OVERLAY_H = 150
MIN_H, MAX_H = 26, 1000


def start_server():
    config = uvicorn.Config(app, host="127.0.0.1", port=PORT, log_level="warning")
    uvicorn.Server(config).run()


class Api:
    def __init__(self):
        self._window = None
        self._title = None
        self._docked = False
        self._tracking = False
        self._oh = OVERLAY_H
        self._w = 900
        self._orig = None
        self._visible = True
        self._minimized = False
        self._drag_off = None
        self._frozen_pid = None
        self._mode = "overlay"
        self._fenetre_morte = False
        self._ferme_pour_de_bon = False

    def undock(self):
        self._docked = False
        self._title = None
        self._orig = None
        return True

    def _ecran_du_point(self, x, y):
        return self._ecran_du_jeu((int(x), int(y), 1, 1))

    def hauteur_vers_le_bas(self, h):
        try:
            hwnd = _hwnd_of(self._window)
            r = wintypes.RECT()
            _u32.GetWindowRect(ctypes.c_void_p(hwnd), ctypes.byref(r))
            haut = max(MIN_H, min(int(round(int(h) * _echelle(self._window))), MAX_H))
            x0, y0, x1, y1 = self._ecran_du_jeu(
                (r.left, r.top, max(1, r.right - r.left), max(1, r.bottom - r.top)))
            y = min(r.top, max(y0, y1 - haut))
            self._oh = haut
            _place(self._window, r.left, y, r.right - r.left, haut)
            return {"ok": True, "h": haut}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def set_overlay_height(self, h):
        self._oh = max(MIN_H, min(int(round(int(h) * _echelle(self._window))), MAX_H))
        if self._docked:
            self._apply_layout()
        else:
            try:
                r = wintypes.RECT()
                _u32.GetWindowRect(ctypes.c_void_p(_hwnd_of(self._window)), ctypes.byref(r))
                bottom = r.bottom
                haut = bottom - self._oh
                x0, y0, x1, y1 = self._ecran_du_point(r.left, r.top)
                if haut < y0:
                    haut = y0
                if haut + self._oh > y1:
                    haut = max(y0, y1 - self._oh)
                _place(self._window, r.left, haut,
                       r.right - r.left, self._oh)
            except Exception:
                pass
        return self._oh

    def _place_a_cote_du_jeu(self, titre=None):
        rect = _game_rect(titre) if titre else None
        ex0, ey0, ex1, ey1 = self._ecran_du_jeu(
            rect or (0, 0, _u32.GetSystemMetrics(0), _screen_height()))
        VOULU_W, VOULU_H = 1200, 860
        MIN_W, MIN_H = 560, 420
        if rect:
            gl, gt, gw_, gh = rect
            gr, gb = gl + gw_, gt + gh
            bandes = [
                (gr, ey0, ex1 - gr, ey1 - ey0),
                (ex0, ey0, gl - ex0, ey1 - ey0),
                (ex0, gb, ex1 - ex0, ey1 - gb),
                (ex0, ey0, ex1 - ex0, gt - ey0),
            ]
            bonnes = [b for b in bandes if b[2] >= MIN_W and b[3] >= MIN_H]
            if bonnes:
                bx, by, bw, bh = max(bonnes, key=lambda b: b[2] * b[3])
                w = max(MIN_W, min(VOULU_W, bw))
                h = max(MIN_H, min(VOULU_H, bh))
                return (bx + (bw - w) // 2, by + (bh - h) // 2, w, h, False)
        w = max(MIN_W, min(VOULU_W, ex1 - ex0 - 80))
        h = max(MIN_H, min(VOULU_H, ey1 - ey0 - 80))
        return (ex0 + (ex1 - ex0 - w) // 2, ey0 + (ey1 - ey0 - h) // 2, w, h, True)

    def set_mode(self, mode, titre=None):
        mode = "window" if mode == "window" else "overlay"
        if self._fenetre_morte:
            print("[overlay] changement de mode impossible : la fenêtre "
                  "principale a été détruite.")
            return {"ok": False, "error": "fenetre detruite"}
        self._mode = mode
        try:
            highlight.clear()
        except Exception:
            pass
        try:
            hwnd = _hwnd_of(self._window)
        except Exception:
            hwnd = None

        def _go(url):
            def run():
                time.sleep(0.15)
                try:
                    self._window.load_url(url)
                except Exception:
                    pass
            threading.Thread(target=run, daemon=True).start()
        if mode == "window":
            self.undock()
            if hwnd:
                _set_framed(hwnd, True)
                _opaque(hwnd)
            try:
                x, y, w, h, couvre = self._place_a_cote_du_jeu(titre)
                _place(self._window, x, y, w, h)
                _set_topmost(self._window, hwnd, False)
                if couvre:
                    print("[overlay] la vue fenêtre recouvre le jeu : la partie "
                          "recouverte ne peut pas être lue. Mets le jeu en "
                          "fenêtré, ou déplace cette fenêtre hors de lui.")
            except Exception:
                pass
            _go(f"http://127.0.0.1:{PORT}/")
        else:
            if hwnd:
                _set_framed(hwnd, False)
            self._cache_en_attendant_la_bulle()
            try:
                r = wintypes.RECT()
                _u32.GetWindowRect(ctypes.c_void_p(_hwnd_of(self._window)), ctypes.byref(r))
                _place(self._window, r.left, r.top, 420, 40)
                _set_topmost(self._window, hwnd, True)
            except Exception:
                pass
            _go(f"http://127.0.0.1:{PORT}/overlay")
        return mode

    def begin_drag(self, sx, sy):
        try:
            r = wintypes.RECT()
            _u32.GetWindowRect(ctypes.c_void_p(_hwnd_of(self._window)), ctypes.byref(r))
            self._drag_off = (int(sx) - r.left, int(sy) - r.top)
        except Exception:
            self._drag_off = None
        return True

    def drag_to(self, sx, sy):
        if not self._drag_off:
            return False
        try:
            dx, dy = self._drag_off
            _u32.SetWindowPos(ctypes.c_void_p(_hwnd_of(self._window)), None,
                              int(sx) - dx, int(sy) - dy, 0, 0,
                              SWP_NOSIZE | SWP_NOZORDER)
        except Exception:
            pass
        return True

    def end_drag(self):
        self._drag_off = None
        return True

    def highlight(self, boxes, title=None, region=None):
        if not boxes:
            highlight.clear()
            return True
        rect = _game_rect(title) if title else None
        if not rect:
            sw = _u32.GetSystemMetrics(0)
            rect = (0, 0, sw, _screen_height())
        gl, gt, gw_, gh = rect
        ox, oy = gl, gt
        if region:
            try:
                fx, fy, _, _ = region
                ox += int(fx * gw_)
                oy += int(fy * gh)
            except Exception:
                pass
        highlight.show([[b[0] + ox, b[1] + oy, b[2], b[3],
                         b[4] if len(b) > 4 else "word"] for b in boxes])
        return True

    def _ecran_du_jeu(self, rect):
        try:
            gl, gt, gw_, gh = rect
            pt = wintypes.POINT(int(gl + gw_ // 2), int(gt + gh // 2))
            MONITOR_DEFAULTTONEAREST = 2
            _u32.MonitorFromPoint.restype = ctypes.c_void_p
            _u32.MonitorFromPoint.argtypes = [wintypes.POINT, ctypes.c_uint]
            hm = _u32.MonitorFromPoint(pt, MONITOR_DEFAULTTONEAREST)

            class MONITORINFO(ctypes.Structure):
                _fields_ = [("cbSize", wintypes.DWORD),
                            ("rcMonitor", wintypes.RECT),
                            ("rcWork", wintypes.RECT),
                            ("dwFlags", wintypes.DWORD)]

            mi = MONITORINFO()
            mi.cbSize = ctypes.sizeof(MONITORINFO)
            _u32.GetMonitorInfoW.argtypes = [ctypes.c_void_p,
                                             ctypes.POINTER(MONITORINFO)]
            if _u32.GetMonitorInfoW(ctypes.c_void_p(hm), ctypes.byref(mi)):
                r = mi.rcMonitor
                return r.left, r.top, r.right, r.bottom
        except Exception:
            pass
        return 0, 0, _u32.GetSystemMetrics(0), _screen_height()

    def taille_bulle(self, w, h):
        r = self._grandir_sur_place(w, h)
        self._montre_la_bulle()
        return r

    def _montre_la_bulle(self):
        if getattr(self, "_bulle_montree", False):
            return
        if not self._visible:
            return
        self._bulle_montree = True
        try:
            self._window.show()
        except Exception:
            pass

    def _cache_en_attendant_la_bulle(self):
        self._bulle_montree = False
        try:
            self._window.hide()
        except Exception:
            pass
        self.arme_filet_affichage()

    def arme_filet_affichage(self, delai=4.0):
        def filet():
            time.sleep(delai)
            if not getattr(self, "_bulle_montree", False) and not self._fenetre_morte:
                print("[overlay] la page n'a pas donné sa taille : on affiche quand même.")
                self._montre_la_bulle()
        threading.Thread(target=filet, daemon=True).start()

    def _grandir_sur_place(self, w, h, title=None, vers_le_haut=False,
                           garde_ancre_x=False):
        try:
            hwnd = _hwnd_of(self._window)
            r = wintypes.RECT()
            _u32.GetWindowRect(ctypes.c_void_p(hwnd), ctypes.byref(r))
            x, y = r.left, r.top
            w, h = max(40, int(w)), max(20, int(h))
            rect = _game_rect(title) if title else None
            bx0, by0, bx1, by1 = self._ecran_du_jeu(
                rect or (0, 0, _u32.GetSystemMetrics(0), _screen_height()))
            if not garde_ancre_x:
                x = max(bx0, min(x, bx1 - w))
            if vers_le_haut:
                y = r.bottom - h
            else:
                y = max(by0, min(y, by1 - h))
            _u32.SetWindowPos(ctypes.c_void_p(hwnd), None, int(x), int(y),
                              int(w), int(h), 0x0210)
            _u32.InvalidateRect(ctypes.c_void_p(hwnd), None, True)
            _u32.UpdateWindow(ctypes.c_void_p(hwnd))
            return {"ok": True, "x": int(x), "y": int(y), "w": w, "h": h}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def ouvrir_lien(self, url: str):
        import webbrowser
        u = (url or "").strip()
        if not u.startswith("https://"):
            print(f"[overlay] lien refusé (pas en https) : {u[:60]}")
            return {"ok": False}
        try:
            webbrowser.open(u)
            return {"ok": True}
        except Exception as e:
            print(f"[overlay] impossible d'ouvrir {u[:60]} : {e}")
            return {"ok": False}

    def ouvrir_reglages(self, vers: str = ""):
        cible = "#" + vers if vers else ""
        try:
            if getattr(self, "_win_reglages", None) is not None:
                try:
                    self._win_reglages.show()
                    if vers:
                        self._win_reglages.load_url(
                            f"http://127.0.0.1:{PORT}/reglages{cible}")
                    return {"ok": True, "deja": True}
                except Exception:
                    self._win_reglages = None
            w = webview.create_window(
                "DNAreader — Réglages",
                url=f"http://127.0.0.1:{PORT}/reglages{cible}",
                js_api=self, width=880, height=760, min_size=(560, 460),
                background_color="#12141a")

            def _oublie():
                self._win_reglages = None
            w.events.closed += _oublie
            self._win_reglages = w

            def _icone():
                for _ in range(40):
                    try:
                        h = _hwnd_of(w)
                        if h:
                            _set_window_icon(h)
                            return
                    except Exception:
                        pass
                    time.sleep(0.1)
            threading.Thread(target=_icone, daemon=True).start()
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def choisir_fichier(self):
        try:
            r = self._window.create_file_dialog(
                webview.OPEN_DIALOG, allow_multiple=False,
                file_types=("Sauvegarde DNAreader (*.dnar)", "Tous les fichiers (*.*)"))
            return r[0] if r else ""
        except Exception:
            return ""

    @staticmethod
    def _zone_ecran(rect, region):
        if not region:
            return None
        gl, gt, gw, gh = rect
        fx, fy, fw, fh = region
        return (gl + int(fx * gw), gt + int(fy * gh),
                gl + int((fx + fw) * gw), gt + int((fy + fh) * gh))

    @staticmethod
    def _poser(x, y, w, h, bornes, zone=None, ancre=None):
        bx0, by0, bx1, by1 = bornes

        def dans_le_cadre(cx, cy):
            return (max(bx0, min(cx, max(bx0, bx1 - w))),
                    max(by0, min(cy, max(by0, by1 - h))))

        x, y = dans_le_cadre(x, y)
        if not zone:
            return x, y
        zx0, zy0, zx1, zy1 = zone
        if x + w <= zx0 or x >= zx1 or y + h <= zy0 or y >= zy1:
            return x, y
        m = 10
        dessous, dessus = (x, zy1 + m), (x, zy0 - h - m)
        candidats = [dessous, dessus, (zx1 + m, y), (zx0 - w - m, y)]
        ax, ay = ancre if ancre else (x + w / 2, y + h / 2)
        tenables = [c for c in candidats
                    if bx0 <= c[0] and by0 <= c[1]
                    and c[0] + w <= bx1 and c[1] + h <= by1]
        if tenables:
            return min(tenables,
                       key=lambda c: (c[0] + w / 2 - ax) ** 2
                                     + (c[1] + h / 2 - ay) ** 2)
        return dans_le_cadre(*(dessus if (zy0 - by0) >= (by1 - zy1) else dessous))

    def place_bubble(self, box, w, h, title=None, region=None, libre=False,
                     garder_position=False, vers_le_haut=False,
                     garde_ancre_x=False):
        try:
            if garder_position:
                return self._grandir_sur_place(w, h, title, vers_le_haut,
                                               garde_ancre_x)
            rect = _game_rect(title) if title else None
            if not rect:
                rect = (0, 0, _u32.GetSystemMetrics(0), _screen_height())
            gl, gt, gw_, gh = rect
            ox, oy = gl, gt
            zone = self._zone_ecran(rect, region)
            if region:
                ox, oy = zone[0], zone[1]
            w, h = max(120, int(w)), max(32, int(h))
            if libre:
                bx0, by0, bx1, by1 = self._ecran_du_jeu(rect)
            else:
                bx0, by0 = gl, gt
                bx1, by1 = gl + gw_, gt + gh

            lx = int(ox + box[0])
            ly = int(oy + box[1])
            lw = int(box[2] or 0)
            lh = int(box[3] or 0)
            marge = 12
            y = ly + lh // 2 - h // 2

            x = lx + lw + marge
            if x + w > bx1:
                x = lx - w - marge
            if x < bx0:
                x, y = lx, ly + lh + marge
            x, y = self._poser(x, y, w, h, (bx0, by0, bx1, by1), zone,
                               (lx + lw / 2, ly + lh / 2))
            _place(self._window, x, y, w, h)
            return {"ok": True, "x": x, "y": y, "w": w, "h": h}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def garer_bulle(self, w, h, title=None, x=None, y=None, region=None):
        try:
            rect = _game_rect(title) if title else None
            if not rect:
                rect = (0, 0, _u32.GetSystemMetrics(0), _screen_height())
            gl, gt, gw_, gh = rect
            w, h = max(24, int(w)), max(16, int(h))
            marge = 16
            a_la_main = x is not None and y is not None
            if a_la_main:
                x, y = int(x), int(y)
            else:
                x = gl + gw_ - w - marge
                y = gt + gh - h - marge
            x, y = self._poser(x, y, w, h, self._ecran_du_jeu(rect),
                               None if a_la_main else self._zone_ecran(rect, region))
            r = wintypes.RECT()
            _u32.GetWindowRect(ctypes.c_void_p(_hwnd_of(self._window)),
                               ctypes.byref(r))
            if (abs(r.left - x) <= 2 and abs(r.top - y) <= 2
                    and abs((r.right - r.left) - w) <= 2
                    and abs((r.bottom - r.top) - h) <= 2):
                return {"ok": True, "x": r.left, "y": r.top,
                        "w": r.right - r.left, "h": r.bottom - r.top,
                        "deja": True}
            _place(self._window, x, y, w, h)
            return {"ok": True, "x": x, "y": y, "w": w, "h": h}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def bubble_visible(self, on):
        try:
            if not self._visible:
                return False
            if on:
                self._window.show()
            else:
                self._window.hide()
            return True
        except Exception:
            return False

    def clear_highlight(self):
        highlight.clear()
        return True

    def pick_region(self, title=None):
        rect = _game_rect(title) if title else None
        if not rect:
            sw = _u32.GetSystemMetrics(0)
            rect = (0, 0, sw, _screen_height())
        gl, gt, gw_, gh = rect
        sel = picker.pick((gl, gt, gw_, gh))
        if not sel:
            return None
        x, y, w, h = sel
        return {"region": [max(0.0, (x - gl) / gw_), max(0.0, (y - gt) / gh),
                           min(1.0, w / gw_), min(1.0, h / gh)]}

    def toggle_freeze(self, title=None):
        win = _find_win(title) if title else None
        if not win:
            return {"ok": False, "error": "fenêtre du jeu introuvable"}
        pid = wintypes.DWORD()
        _u32.GetWindowThreadProcessId(win._hWnd, ctypes.byref(pid))
        if not pid.value:
            return {"ok": False, "error": "processus introuvable"}
        try:
            nt = ctypes.windll.ntdll
            k32 = ctypes.windll.kernel32
            PROCESS_SUSPEND_RESUME = 0x0800
            h = k32.OpenProcess(PROCESS_SUSPEND_RESUME, False, pid.value)
            if not h:
                return {"ok": False, "error": "accès refusé — lance l'app en administrateur"}
            try:
                if self._frozen_pid == pid.value:
                    nt.NtResumeProcess(h)
                    self._frozen_pid = None
                    return {"ok": True, "frozen": False}
                nt.NtSuspendProcess(h)
                self._frozen_pid = pid.value
                return {"ok": True, "frozen": True}
            finally:
                k32.CloseHandle(h)
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _unfreeze_all(self):
        if not self._frozen_pid:
            return
        try:
            k32 = ctypes.windll.kernel32
            h = k32.OpenProcess(0x0800, False, self._frozen_pid)
            if h:
                ctypes.windll.ntdll.NtResumeProcess(h)
                k32.CloseHandle(h)
        except Exception:
            pass
        self._frozen_pid = None

    def set_opacity(self, percent):
        try:
            p = max(10, min(100, int(percent)))
            hwnd = ctypes.c_void_p(_hwnd_of(self._window))
            st = _u32.GetWindowLongPtrW(hwnd, GWL_EXSTYLE)
            _u32.SetWindowLongPtrW(hwnd, GWL_EXSTYLE, st | WS_EX_LAYERED)
            _u32.SetLayeredWindowAttributes(hwnd, 0, int(p * 255 / 100), LWA_ALPHA)
            return {"ok": True, "opacity": p}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def set_click_through(self, on):
        try:
            hwnd = ctypes.c_void_p(_hwnd_of(self._window))
            st = _u32.GetWindowLongPtrW(hwnd, GWL_EXSTYLE)
            st = (st | WS_EX_LAYERED | WS_EX_TRANSPARENT) if on \
                else (st & ~WS_EX_TRANSPARENT)
            _u32.SetWindowLongPtrW(hwnd, GWL_EXSTYLE, st)
            return {"ok": True, "on": bool(on)}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def get_geometry(self):
        try:
            r = wintypes.RECT()
            _u32.GetWindowRect(ctypes.c_void_p(_hwnd_of(self._window)), ctypes.byref(r))
            ex0, ey0, ex1, ey1 = self._ecran_du_point(r.left, r.top)
            return {"x": r.left, "y": r.top,
                    "w": r.right - r.left, "h": r.bottom - r.top,
                    "ecran": {"x0": ex0, "y0": ey0, "x1": ex1, "y1": ey1}}
        except Exception:
            return None

    def set_geometry(self, x, y, w, h):
        try:
            if self._docked:
                return {"ok": False, "error": "attaché : la position suit le jeu"}
            sw = _u32.GetSystemMetrics(78) or _u32.GetSystemMetrics(0)
            sh = _u32.GetSystemMetrics(79) or _u32.GetSystemMetrics(1)
            w = max(240, min(int(w), sw))
            h = max(MIN_H, min(int(h), MAX_H))
            x = max(-w + 120, min(int(x), sw - 120))
            y = max(0, min(int(y), sh - 40))
            _place(self._window, x, y, w, h)
            self._oh = h
            return {"ok": True, "x": x, "y": y, "w": w, "h": h}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def toggle_click_through(self):
        maintenant = time.perf_counter()
        if maintenant - getattr(self, "_ghost_at", 0) < 0.35:
            return getattr(self, "_ghost", False)
        self._ghost_at = maintenant
        self._ghost = not getattr(self, "_ghost", False)
        self.set_click_through(self._ghost)
        try:
            self._window.evaluate_js(
                f"window.setGhost && window.setGhost({str(self._ghost).lower()})")
        except Exception:
            pass
        return self._ghost

    def freeze_hotkey(self):
        try:
            self._window.evaluate_js("window.hotFreeze && window.hotFreeze()")
        except Exception:
            pass
        return True

    def bulle_hotkey(self):
        try:
            self._window.evaluate_js("window.toggleBulle && window.toggleBulle()")
        except Exception:
            pass
        return True

    def muet_hotkey(self):
        try:
            self._window.evaluate_js("window.toggleMuet && window.toggleMuet()")
        except Exception:
            pass
        return True

    def souris_hotkey(self):
        try:
            hwnd = _hwnd_of(self._window)
            if not hwnd:
                return {"ok": False, "error": "pas de fenetre"}
            _force_foreground(hwnd)
            r = wintypes.RECT()
            _u32.GetWindowRect(ctypes.c_void_p(hwnd), ctypes.byref(r))
            _u32.SetCursorPos((r.left + r.right) // 2, (r.top + r.bottom) // 2)
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def pick_zone_hotkey(self):
        try:
            self._window.evaluate_js("window.startZonePick && window.startZonePick()")
        except Exception:
            pass
        return True

    def minimize_window(self):
        try:
            hwnd = _hwnd_of(self._window)
        except Exception:
            hwnd = None
        _set_topmost(self._window, hwnd, False)
        try:
            self._window.minimize()
        except Exception:
            pass
        try:
            self._window.evaluate_js("window.setOverlayVisible && window.setOverlayVisible(false)")
        except Exception:
            pass
        self._minimized = True
        return True

    def restore_window(self):
        try:
            self._window.restore()
        except Exception:
            pass
        if self._mode == "overlay":
            try:
                _set_topmost(self._window, _hwnd_of(self._window), True)
            except Exception:
                pass
        try:
            self._window.evaluate_js("window.setOverlayVisible && window.setOverlayVisible(true)")
        except Exception:
            pass
        self._minimized = False
        return True

    def toggle_visibility(self):
        if self._minimized:
            self.restore_window()
            self._visible = True
            return True
        self._visible = not self._visible
        try:
            if self._visible:
                self._window.show()
            else:
                self._window.hide()
        except Exception:
            pass
        try:
            self._window.evaluate_js(
                f"window.setOverlayVisible && window.setOverlayVisible({str(self._visible).lower()})")
        except Exception:
            pass
        return self._visible

    def paste_clipboard(self):
        txt = _clipboard_text()
        if txt and any("぀" <= c <= "ヿ" or "一" <= c <= "鿿" for c in txt):
            return {"text": txt}
        try:
            data = ImageGrab.grabclipboard()
        except Exception:
            return None
        img = None
        if isinstance(data, list):
            from PIL import Image
            for path in data:
                try:
                    img = Image.open(path)
                    break
                except Exception:
                    continue
        elif data is not None and hasattr(data, "convert"):
            img = data
        if img is None:
            return None
        buf = io.BytesIO()
        img.convert("RGB").save(buf, format="PNG")
        return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()

    def _sur_fermeture(self):
        if self._ferme_pour_de_bon:
            return True
        if self._mode == "window":
            threading.Thread(target=lambda: self.set_mode("overlay"),
                             daemon=True).start()
            return False
        return True

    def _sur_fermee(self):
        self._fenetre_morte = True

    def close_app(self):
        self._ferme_pour_de_bon = True
        try:
            import zone_notif
            zone_notif.arrete()
        except Exception:
            pass
        self._unfreeze_all()
        highlight.stop()
        try:
            import detect, precise, translate
            detect.stop(); precise.stop(); translate.stop()
        except Exception:
            pass
        try:
            self._window.destroy()
        except Exception:
            pass
        return True

    def _docked_rect(self, rect):
        gl, gt, gw_, gh = rect
        oh = max(MIN_H, min(self._oh, max(MIN_H, gh // 2)))
        return gl, gt + gh - oh, gw_, oh

    def _apply_layout(self):
        if not self._window:
            return
        rect = _game_rect(self._title) or self._orig
        if not rect:
            return
        x, y, w, h = self._docked_rect(rect)
        self._w = w
        _place(self._window, x, y, w, h)

    def _track(self):
        last = None
        while True:
            if self._docked and self._title and self._window:
                rect = _game_rect(self._title)
                if rect:
                    target = self._docked_rect(rect)
                    if target != last:
                        _place(self._window, *target)
                        self._w = target[2]
                        last = target
            time.sleep(0.25)


def _wait_server():
    for _ in range(60):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{PORT}/api/windows", timeout=1)
            return True
        except Exception:
            time.sleep(0.2)
    return False


_NOMS_CONNUS = ("dnareader", "kanji-game-reader")


def _already_running() -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/api/ping", timeout=0.8) as r:
            return json.loads(r.read().decode("utf-8")).get("app") in _NOMS_CONNUS
    except Exception:
        return False


def _port_occupe() -> bool:
    import socket
    s = socket.socket()
    try:
        s.bind(("127.0.0.1", PORT))
        return False
    except OSError:
        return True
    finally:
        s.close()


_k32 = ctypes.windll.kernel32
_k32.OpenProcess.restype = ctypes.c_void_p
_k32.OpenProcess.argtypes = [ctypes.c_uint, ctypes.c_bool, ctypes.c_uint]
_k32.TerminateProcess.argtypes = [ctypes.c_void_p, ctypes.c_uint]
_k32.CloseHandle.argtypes = [ctypes.c_void_p]


def _pid_de_l_instance():
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/api/ping", timeout=0.8) as r:
            d = json.loads(r.read().decode("utf-8"))
        return d.get("pid") if d.get("app") in _NOMS_CONNUS else None
    except Exception:
        return None


def _tuer_le_fantome() -> bool:
    pid = _pid_de_l_instance()
    if not pid or pid == os.getpid():
        return False
    try:
        h = _k32.OpenProcess(0x0001, False, int(pid))
        if not h:
            return False
        _k32.TerminateProcess(h, 0)
        _k32.CloseHandle(h)
    except Exception:
        return False
    for _ in range(40):
        if not _already_running():
            return True
        time.sleep(0.1)
    return False


def _focus_existing() -> bool:
    _u32.FindWindowW.restype = ctypes.c_void_p
    _u32.FindWindowW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p]
    hwnd = _u32.FindWindowW(None, "DNAreader — Overlay")
    if not hwnd:
        return False
    _u32.ShowWindow(ctypes.c_void_p(hwnd), 9)
    _force_foreground(hwnd)
    return True


def main(start_mode="overlay"):
    if _already_running():
        if _focus_existing():
            print("[overlay] DNAreader est déjà ouvert — fenêtre ramenée devant.")
            return
        print("[overlay] instance fantôme détectée (plus de fenêtre) — on la termine.")
        if not _tuer_le_fantome():
            print("[overlay] impossible de terminer l'instance fantôme : "
                  f"ferme le processus python occupant le port {PORT}.")
            return
    elif _port_occupe():
        print(f"[overlay] le port {PORT} est occupé par un autre programme. "
              "Ferme-le (ou change de port) puis relance.")
        return
    discret.efface_ce_processus()
    threading.Thread(target=start_server, daemon=True).start()
    if not _wait_server():
        print("[overlay] le serveur local n'a pas démarré : lancement interrompu.")
        return
    try:
        import maj
        maj.au_demarrage()
    except Exception as e:
        print(f"[overlay] recherche de mise a jour ignoree : {e}")

    api = Api()
    window = webview.create_window(
        "DNAreader — Overlay",
        url=f"http://127.0.0.1:{PORT}/" if start_mode == "window"
            else f"http://127.0.0.1:{PORT}/overlay",
        js_api=api,
        width=1200 if start_mode == 'window' else 420,
        height=800 if start_mode == 'window' else 40,
        x=160, y=120,
        hidden=(start_mode != 'window'),
        frameless=(start_mode != 'window'), easy_drag=False,
        on_top=(start_mode != 'window'),
        min_size=(60, 24),
        background_color="#121b22",
    )
    api._window = window
    api._mode = start_mode
    window.events.closing += api._sur_fermeture
    window.events.closed += api._sur_fermee
    if start_mode != 'window':
        api.arme_filet_affichage()

    def _arm_toggle():
        time.sleep(1.5)
        hk = hotkey.register("toggle", api.toggle_visibility)
        print(f"[overlay] {hk.upper()} = afficher/masquer l'overlay")
        for nom, cb, quoi in (("ghost", api.toggle_click_through, "clics traversants"),
                              ("freeze", api.freeze_hotkey, "geler / relancer le jeu"),
                              ("bulle", api.bulle_hotkey, "entrer / sortir du mode bulle"),
                              ("muet", api.muet_hotkey, "mettre la lecture en pause"),
                              ("souris", api.souris_hotkey, "rendre la souris et la poser sur la bulle"),
                              ("zone", api.pick_zone_hotkey, "redéfinir la zone lue"),
                              ("quitter", api.close_app, "fermer l'application")):
            try:
                print(f"[overlay] {hotkey.register(nom, cb).upper()} = {quoi}")
            except Exception as e:
                print(f"[overlay] raccourci « {nom} » indisponible : {e}")
        try:
            hw = _hwnd_of(window)
            _set_window_icon(hw)
            import capture
            capture.set_zone_app(lambda: _rect_fenetre(window))

            WDA_NONE, WDA_EXCLUDEFROMCAPTURE = 0x00, 0x11
            _u32.SetWindowDisplayAffinity.argtypes = [ctypes.c_void_p, ctypes.c_uint]

            def _masque(on):
                try:
                    h = ctypes.c_void_p(_hwnd_of(window))
                    ok = _u32.SetWindowDisplayAffinity(
                        h, WDA_EXCLUDEFROMCAPTURE if on else WDA_NONE)
                    return bool(ok)
                except Exception:
                    return False

            capture.set_masquage(_masque)
            print("[overlay] visible aux captures ; effacée le temps de chaque lecture")
        except Exception as e:
            print(f"[overlay] zone d'effacement indisponible : {e}")
    threading.Thread(target=_arm_toggle, daemon=True).start()

    def _pose_icone():
        try:
            import zone_notif
        except Exception:
            return

        def afficher():
            try:
                api.restore_window()
            except Exception:
                pass

        def reglages():
            try:
                api.ouvrir_reglages()
            except Exception:
                pass

        def bulle():
            try:
                window.evaluate_js("window.toggleBulle && window.toggleBulle()")
            except Exception:
                pass

        def quitter():
            try:
                api.close_app()
            except Exception:
                pass

        r = zone_notif.demarre(
            "DNAreader",
            [(1, "Afficher DNAreader"), (2, "Réglages…"),
             (3, "Bulle / barre"), ("-", "-"), (4, "Quitter")],
            {1: afficher, 2: reglages, 3: bulle, 4: quitter})
        if r.get("ok"):
            print("[overlay] icône posée dans la zone de notification")
        else:
            print(f"[overlay] zone de notification indisponible : {r.get('error')}")

    threading.Thread(target=_pose_icone, daemon=True).start()
    stockage = os.path.join(os.environ.get("LOCALAPPDATA") or str(pathlib.Path.home()),
                            "DNAreader", "webview")
    try:
        os.makedirs(stockage, exist_ok=True)
    except Exception:
        stockage = None
    webview.start(private_mode=False, storage_path=stockage)


if __name__ == "__main__":
    main()
