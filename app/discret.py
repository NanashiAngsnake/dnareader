# -*- coding: utf-8 -*-
import os
import subprocess
import sys

CREATE_NO_WINDOW = 0x08000000
BELOW_NORMAL_PRIORITY_CLASS = 0x00004000


def fils_de_calcul() -> int:
    coeurs = os.cpu_count() or 4
    return max(1, min(4, coeurs // 2))


def drapeaux_processus() -> int:
    if sys.platform != "win32":
        return 0
    return CREATE_NO_WINDOW | BELOW_NORMAL_PRIORITY_CLASS


def env_calcul() -> dict:
    n = str(fils_de_calcul())
    env = dict(os.environ)
    env.update({"OMP_NUM_THREADS": n, "MKL_NUM_THREADS": n,
                "OPENBLAS_NUM_THREADS": n, "NUMEXPR_NUM_THREADS": n,
                "TORCH_NUM_THREADS": n})
    return env


def efface_ce_processus() -> bool:
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        k32 = ctypes.windll.kernel32
        return bool(k32.SetPriorityClass(k32.GetCurrentProcess(),
                                         BELOW_NORMAL_PRIORITY_CLASS))
    except Exception:
        return False
