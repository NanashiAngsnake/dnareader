# -*- coding: utf-8 -*-
import os
import sys
from pathlib import Path

RACINE = Path(__file__).parent
sys.path.insert(0, str(RACINE / "app"))
os.chdir(RACINE)

import chemins

LOG = chemins.JOURNAL
if sys.stdout is None or not hasattr(sys.stdout, "write"):
    try:
        f = open(LOG, "a", encoding="utf-8", buffering=1)
        sys.stdout = sys.stderr = f
    except Exception:
        import io
        sys.stdout = sys.stderr = io.StringIO()

def _ouvrier(nom: str) -> int:
    modules = {"detect": "detect_worker", "precise": "precise_worker",
               "translate": "translate_worker"}
    if nom not in modules:
        return 2
    import importlib
    m = importlib.import_module(modules[nom])
    m.main()
    return 0


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--ouvrier":
        sys.exit(_ouvrier(sys.argv[2]))
    import overlay
    overlay.main(start_mode="overlay")
