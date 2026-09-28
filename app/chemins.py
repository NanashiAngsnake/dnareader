# -*- coding: utf-8 -*-
import os
import sys
from pathlib import Path

EMPAQUETEE = bool(getattr(sys, "frozen", False))

if EMPAQUETEE:
    RACINE = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)).resolve()
    APP = RACINE / "app"
else:
    APP = Path(__file__).resolve().parent
    RACINE = APP.parent

STATIC = RACINE / "static"
DICTS = RACINE / "dicts"
MODELES = RACINE / "modeles"
RESSOURCES = RACINE / "ressources"
OUTILS = RACINE / "outils"
TESTS = RACINE / "tests"


def _dossier_donnees() -> Path:
    force = os.environ.get("DNAREADER_DONNEES")
    if force:
        return Path(force).expanduser().resolve()
    if EMPAQUETEE:
        base = os.environ.get("LOCALAPPDATA") or str(Path.home())
        return Path(base) / "DNAreader"
    return RACINE / "donnees"


DONNEES = _dossier_donnees()

DONNEES.mkdir(parents=True, exist_ok=True)

DB_VOCABULAIRE = DONNEES / "vocab.db"
DB_CORRECTIONS = DONNEES / "corrections.db"
DB_APPRENTISSAGE = DONNEES / "apprentissage.db"
DB_TRADUCTIONS = DONNEES / "translations.db"
DB_SYNC = DONNEES / "sync.db"
MODELE_APPRENTISSAGE = DONNEES / "modele.json"
PROFILS = DONNEES / "profils.json"
ZONES_APPRISES = DONNEES / "zones_apprises.json"
PARTAGE = DONNEES / "partage.json"
COMPTE = DONNEES / "compte.json"
REGLAGES = DONNEES / "settings.json"
JOURNAL = DONNEES / "kanji-reader.log"

_DICO_LIVRE = DICTS / "dictionary.db"
DB_DICTIONNAIRE = _DICO_LIVRE if _DICO_LIVRE.exists() else (DONNEES / "dictionary.db")
ICONE = RESSOURCES / "icon.ico"
ICONE_PNG = RESSOURCES / "icon.png"
LOGO = RESSOURCES / "logo.png"
