# -*- coding: utf-8 -*-
import queue
import threading
import tkinter as tk

_result: queue.Queue = queue.Queue()

DIM = 0.45
ACCENT = "#5ecfd4"


def _worker(bounds):
    left, top, width, height = bounds
    root = tk.Tk()
    root.overrideredirect(True)
    root.attributes("-topmost", True)
    root.attributes("-alpha", DIM)
    root.configure(bg="#000000", cursor="crosshair")
    root.geometry(f"{width}x{height}+{left}+{top}")

    cv = tk.Canvas(root, bg="#000000", highlightthickness=0, cursor="crosshair")
    cv.pack(fill="both", expand=True)
    cv.create_text(width // 2, 40, fill="#ffffff", font=("Segoe UI", 16),
                   text="Trace un rectangle autour du texte à lire  ·  Échap pour annuler")

    state = {"x0": 0, "y0": 0, "rect": None, "done": False}

    def press(ev):
        state["x0"], state["y0"] = ev.x, ev.y
        if state["rect"]:
            cv.delete(state["rect"])
        state["rect"] = cv.create_rectangle(ev.x, ev.y, ev.x, ev.y,
                                            outline=ACCENT, width=2, fill="#ffffff")

    def drag(ev):
        if state["rect"]:
            cv.coords(state["rect"], state["x0"], state["y0"], ev.x, ev.y)

    def release(ev):
        x1, y1 = min(state["x0"], ev.x), min(state["y0"], ev.y)
        x2, y2 = max(state["x0"], ev.x), max(state["y0"], ev.y)
        state["done"] = True
        if x2 - x1 >= 20 and y2 - y1 >= 15:
            _result.put((left + x1, top + y1, x2 - x1, y2 - y1))
        else:
            _result.put(None)
        root.destroy()

    def cancel(_=None):
        if not state["done"]:
            _result.put(None)
        root.destroy()

    cv.bind("<ButtonPress-1>", press)
    cv.bind("<B1-Motion>", drag)
    cv.bind("<ButtonRelease-1>", release)
    root.bind("<Escape>", cancel)
    root.protocol("WM_DELETE_WINDOW", cancel)
    root.after(50, lambda: root.focus_force())
    root.mainloop()


def pick(bounds, timeout=60):
    while not _result.empty():
        try:
            _result.get_nowait()
        except queue.Empty:
            break
    t = threading.Thread(target=_worker, args=(bounds,), daemon=True)
    t.start()
    try:
        return _result.get(timeout=timeout)
    except queue.Empty:
        return None
