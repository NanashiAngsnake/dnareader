# -*- coding: utf-8 -*-
import io
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "outils"))
sys.path.insert(0, str(RACINE / "app"))
sys.stdout.reconfigure(encoding="utf-8")

import construire

VERSION_PY = RACINE / "app" / "version.py"
echecs = []


def verifie(nom, condition, detail=""):
    print(f"  {'OK  ' if condition else 'ECHEC'} {nom}" + (f" — {detail}" if detail else ""))
    if not condition:
        echecs.append(nom)


def octets() -> bytes:
    return VERSION_PY.read_bytes()


def main():
    origine = octets()
    URL = "https://sync.exemple.fr"
    try:
        print("1. sans --serveur, le depot reste en mode libre")
        import version
        verifie("le depot ne demande ni cle ni essai",
                version.SERVEUR_LICENCE == "",
                f"SERVEUR_LICENCE = {version.SERVEUR_LICENCE!r}")

        print("\n2. --serveur inscrit vraiment l'adresse dans la build")
        avant = construire.inscris_serveur(URL)
        ecrit = io.open(VERSION_PY, encoding="utf-8").read()
        verifie("l'adresse est dans app/version.py",
                f'SERVEUR_LICENCE = "{URL}"' in ecrit)
        verifie("et une seule ligne a change",
                ecrit.count("SERVEUR_LICENCE = ") == 1)

        print("\n3. le fichier revient OCTET POUR OCTET (le piege des fins de ligne)")
        construire.ecris_version_py(avant)
        rendu = octets()
        verifie("pas un octet de difference", rendu == origine,
                f"{len(origine)} octets avant, {len(rendu)} apres")
        verifie("les fins de ligne n'ont pas ete converties",
                rendu.count(b"\r\n") == origine.count(b"\r\n"),
                f"{origine.count(chr(13).encode() + chr(10).encode())} CRLF avant, "
                f"{rendu.count(chr(13).encode() + chr(10).encode())} apres")

        print("\n4. une construction qui echoue ne laisse pas l'adresse trainer")
        avant2 = construire.inscris_serveur(URL)
        try:
            raise RuntimeError("PyInstaller casse au milieu")
        except RuntimeError:
            construire.ecris_version_py(avant2)
        verifie("le depot est intact malgre l'echec", octets() == origine)

        print("\n5. une constante RENOMMEE arrete tout, au lieu de passer")
        construire.ecris_version_py(
            avant.replace('SERVEUR_LICENCE = ""', 'AUTRE_NOM = ""'))
        try:
            construire.inscris_serveur(URL)
            verifie("le script refuse d'ecrire n'importe ou", False,
                    "il a accepte alors que la constante n'existait plus")
        except SystemExit as e:
            verifie("le script refuse d'ecrire n'importe ou", True, str(e)[:50])
        construire.ecris_version_py(avant)

        print("\n6. --depot passe par la MEME mecanique")
        construire.inscris(DEPOT_RELEASES="moi/mes-releases")
        ecrit = io.open(VERSION_PY, encoding="utf-8").read()
        verifie("le depot des mises a jour s'inscrit aussi",
                'DEPOT_RELEASES = "moi/mes-releases"' in ecrit)
        construire.inscris(DEPOT_RELEASES="")
        ecrit = io.open(VERSION_PY, encoding="utf-8").read()
        verifie("et se vide, pour une build qui ne cherche jamais",
                'DEPOT_RELEASES = ""' in ecrit)
        construire.ecris_version_py(avant)
        verifie("le depot ressort intact", octets() == origine)

    finally:
        if octets() != origine:
            VERSION_PY.write_bytes(origine)
            print("\n(app/version.py remis de force par le banc)")

    print()
    if echecs:
        print(f"{len(echecs)} ECHEC(S) : " + " · ".join(echecs))
        return 1
    print("OK : la build vendue s'obtient avec --serveur, et le depot en ressort")
    print("     exactement comme il etait — fins de ligne comprises")
    return 0


if __name__ == "__main__":
    sys.exit(main())
