# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
from PyInstaller.utils.hooks import (collect_data_files, collect_dynamic_libs,
                                     collect_submodules)

RACINE = Path(SPECPATH)

donnees = [
    (str(RACINE / "static"),      "static"),
    (str(RACINE / "modeles"),     "modeles"),
    (str(RACINE / "ressources"),  "ressources"),
    (str(RACINE / "NOTICE.md"),   "."),
    (str(RACINE / "README.md"),   "."),
]

dico = RACINE / "dicts" / "dictionary.db"
if dico.exists():
    donnees.append((str(dico), "dicts"))
else:
    raise SystemExit(
        "dicts/dictionary.db est absent : lance l'application une fois pour "
        "la construire, sinon le paquet obligerait chaque utilisateur à la "
        "reconstruire — dans un dossier où il n'a pas le droit d'écrire.")


donnees_paquets = []
for paquet in ("unidic_lite", "jaconv", "genanki"):
    try:
        donnees_paquets += collect_data_files(paquet)
    except Exception:
        pass

binaires = []
caches = []
for paquet in ("onnxruntime", "cv2"):
    try:
        binaires += collect_dynamic_libs(paquet)
    except Exception:
        pass

caches += collect_submodules("winrt")
caches += [
    "uvicorn.logging", "uvicorn.loops.auto", "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets.auto", "uvicorn.lifespan.on",
    "fugashi", "unidic_lite", "jaconv", "genanki",
    "webview.platforms.winforms", "clr_loader",
    "detect_worker", "precise_worker", "translate_worker",
]

a = Analysis(
    [str(RACINE / "lancer.pyw")],
    pathex=[str(RACINE / "app")],
    binaries=binaires,
    datas=donnees + donnees_paquets,
    hiddenimports=caches,
    hookspath=[],
    excludes=[
        "torch", "torchvision", "torchaudio", "transformers", "manga_ocr",
        "tensorflow", "matplotlib", "scipy", "pandas", "notebook", "IPython",
        "tkinter.test",
    ],
    noarchive=False,
    optimize=2,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="DNAreader",
    debug=False,
    strip=False,
    upx=False,
    console=False,
    icon=str(RACINE / "ressources" / "icon.ico"),
    version=str(RACINE / "version_windows.txt"),
)

COLLECT(
    exe, a.binaries, a.datas,
    strip=False, upx=False, name="DNAreader",
)
