# -*- coding: utf-8 -*-
import threading
import time

_lock = threading.Lock()
_state = {
    "on": False,
    "title": None,
    "ctrl": None,
    "last_change": 0.0,
    "frames": 0,
    "error": None,
}


def available() -> bool:
    try:
        import importlib.util
        return importlib.util.find_spec("windows_capture") is not None
    except Exception:
        return False


def status() -> dict:
    with _lock:
        return {"available": available(), "on": _state["on"],
                "title": _state["title"], "frames": _state["frames"],
                "error": _state["error"]}


def start(title: str) -> dict:
    if not available():
        return {"ok": False, "error": "windows-capture n'est pas installé"}
    stop()
    try:
        from windows_capture import WindowsCapture, Frame, InternalCaptureControl

        cap = WindowsCapture(cursor_capture=False, draw_border=False,
                             window_name=title)

        @cap.event
        def on_frame_arrived(frame: Frame, ctrl: InternalCaptureControl):
            _state["last_change"] = time.perf_counter()
            _state["frames"] += 1

        @cap.event
        def on_closed():
            _state["on"] = False

        with _lock:
            _state["ctrl"] = cap.start_free_threaded()
            _state["on"] = True
            _state["title"] = title
            _state["frames"] = 0
            _state["error"] = None
        return {"ok": True}
    except Exception as e:
        with _lock:
            _state["on"] = False
            _state["error"] = str(e)
        return {"ok": False, "error": str(e)}


def stop() -> dict:
    with _lock:
        ctrl = _state["ctrl"]
        _state["ctrl"] = None
        _state["on"] = False
        _state["title"] = None
    if ctrl is None:
        return {"ok": True}

    fini = threading.Event()

    def _fermer():
        try:
            ctrl.stop()
        except Exception as e:
            print(f"[flux] fermeture en erreur : {e}")
        finally:
            fini.set()

    threading.Thread(target=_fermer, daemon=True).start()
    if not fini.wait(1.0):
        print("[flux] la fermeture ne rend pas la main : on continue sans elle")
        return {"ok": True, "abandonne": True}
    return {"ok": True}


def quiet_for() -> float:
    if not _state["on"] or not _state["last_change"]:
        return -1.0
    return time.perf_counter() - _state["last_change"]
