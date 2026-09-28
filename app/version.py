# -*- coding: utf-8 -*-

NOM = "DNAreader"
VERSION = "1.0.7"
EDITEUR = "DNAreader"
SITE = "https://github.com"

SERVEUR_LICENCE = ""

DEPOT_RELEASES = "NanashiAngsnake/dnareader-releases"

ESSAI_JOURS = 7

def version_windows() -> tuple:
    bouts = [int(x) for x in VERSION.split(".")]
    while len(bouts) < 4:
        bouts.append(0)
    return tuple(bouts[:4])


def complet() -> str:
    return f"{NOM} {VERSION}"
