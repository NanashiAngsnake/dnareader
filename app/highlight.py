# -*- coding: utf-8 -*-
import ctypes
import queue
import threading
import tkinter as tk

_u32 = ctypes.windll.user32
GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
WDA_MONITOR, WDA_EXCLUDEFROMCAPTURE = 0x01, 0x11
_u32.GetWindowLongPtrW.restype = ctypes.c_longlong
_u32.GetWindowLongPtrW.argtypes = [ctypes.c_void_p, ctypes.c_int]
_u32.SetWindowLongPtrW.restype = ctypes.c_longlong
_u32.SetWindowLongPtrW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_longlong]

KEY = "#010203"
COLORS = {"word": "#5ecfd4", "a": "#7fd18a", "b": "#e0a95e"}

_q: queue.Queue = queue.Queue()
_thread = None
_started = threading.Event()


def _merge_runs(rects):
    if not rects:
        return []
    boxes = sorted(((r[0], r[1], r[0] + r[2], r[1] + r[3]) for r in rects),
                   key=lambda b: (round(b[1] / 12), b[0]))
    runs = []
    cur = list(boxes[0])
    for x1, y1, x2, y2 in boxes[1:]:
        same_line = abs(y1 - cur[1]) <= max(6, (cur[3] - cur[1]) * 0.5)
        touching = x1 <= cur[2] + max(8, (cur[3] - cur[1]) * 0.4)
        if same_line and touching:
            cur[2] = max(cur[2], x2)
            cur[1] = min(cur[1], y1)
            cur[3] = max(cur[3], y2)
        else:
            runs.append(tuple(cur))
            cur = [x1, y1, x2, y2]
    runs.append(tuple(cur))
    return runs


def _worker():
    _showing = [False]
    root = tk.Tk()
    root.overrideredirect(True)
    root.attributes("-topmost", True)
    root.attributes("-transparentcolor", KEY)
    root.configure(bg=KEY)
    root.geometry("10x10+0+0")
    cv = tk.Canvas(root, bg=KEY, highlightthickness=0, bd=0)
    cv.pack(fill="both", expand=True)

    def make_click_through():
        try:
            h = _u32.GetAncestor(root.winfo_id(), 2)
            st = _u32.GetWindowLongPtrW(ctypes.c_void_p(h), GWL_EXSTYLE)
            _u32.SetWindowLongPtrW(ctypes.c_void_p(h), GWL_EXSTYLE,
                                   st | WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW)
            _u32.SetWindowDisplayAffinity.argtypes = [ctypes.c_void_p, ctypes.c_uint]
            if not _u32.SetWindowDisplayAffinity(ctypes.c_void_p(h), WDA_EXCLUDEFROMCAPTURE):
                _u32.SetWindowDisplayAffinity(ctypes.c_void_p(h), WDA_MONITOR)
        except Exception:
            pass

    root.after(60, make_click_through)
    _started.set()

    def pump():
        try:
            while True:
                msg = _q.get_nowait()
                if msg.get("quit"):
                    root.quit()
                    root.destroy()
                    return
                rects = msg.get("rects") or []
                _showing[0] = bool(rects)
                if not rects:
                    cv.delete("all")
                    root.geometry("10x10+0+0")
                else:
                    xs = [r[0] for r in rects]
                    ys = [r[1] for r in rects]
                    x2 = max(r[0] + r[2] for r in rects)
                    y2 = max(r[1] + r[3] for r in rects)
                    pad = 6
                    ox, oy = int(min(xs)) - pad, int(min(ys)) - pad
                    w, h = int(x2 - min(xs)) + pad * 2, int(y2 - min(ys)) + pad * 2
                    root.geometry(f"{max(w,1)}x{max(h,1)}+{ox}+{oy}")
                    cv.delete("all")
                    cv.configure(width=w, height=h)
                    for x1, y1, x2, y2 in _merge_runs(rects):
                        x1, y1, x2, y2 = x1 - ox, y1 - oy, x2 - ox, y2 - oy
                        col = COLORS["word"]
                        cv.create_rectangle(x1, y1, x2, y2,
                                            outline=col, width=2)
                        cv.create_rectangle(x1, y2 - 5, x2, y2,
                                            fill=col, outline="")
        except queue.Empty:
            pass
        except Exception:
            pass
        root.after(40 if _showing[0] else 200, pump)

    root.after(40, pump)
    root.mainloop()


def start():
    global _thread
    if _thread and _thread.is_alive():
        return True
    _started.clear()
    _thread = threading.Thread(target=_worker, daemon=True)
    _thread.start()
    return _started.wait(timeout=5)


def show(rects):
    if not start():
        return False
    _q.put({"rects": rects})
    return True


def clear():
    if _thread and _thread.is_alive():
        _q.put({"rects": []})
    return True


def stop():
    global _thread
    t = _thread
    if t and t.is_alive():
        _q.put({"quit": True})
        t.join(timeout=2)
    _thread = None
    return True
