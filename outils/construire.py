# -*- coding: utf-8 -*-
import argparse
import hashlib
import os
import re
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "app"))
sys.stdout.reconfigure(encoding="utf-8")

import version

PY = RACINE / ".venv" / "Scripts" / "python.exe"
DIST = RACINE / "dist"
SORTIE = DIST / "DNAreader"

ISCC_CANDIDATS = [
    Path(r"C:\Program Files\Inno Setup 7\ISCC.exe"),
    Path(r"C:\Program Files (x86)\Inno Setup 7\ISCC.exe"),
    Path(r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"),
    Path(r"C:\Program Files\Inno Setup 6\ISCC.exe"),
]


def titre(t):
    print(f"\n{'=' * 4} {t}")


def trouve_iscc():
    depuis_path = shutil.which("iscc")
    if depuis_path:
        return Path(depuis_path)
    for c in ISCC_CANDIDATS:
        if c.exists():
            return c
    return None


def verifie() -> list:
    manques = []
    if not PY.exists():
        manques.append(f"l'environnement Python est absent : {PY}")
    try:
        subprocess.run([str(PY), "-c", "import PyInstaller"], check=True,
                       capture_output=True)
    except Exception:
        manques.append("PyInstaller n'est pas installé "
                       "(.venv\\Scripts\\python.exe -m pip install pyinstaller)")
    dico = RACINE / "dicts" / "dictionary.db"
    if not dico.exists():
        manques.append(
            "dicts/dictionary.db est absent. Lance l'application une fois : "
            "elle le construit. Sans lui, le paquet obligerait chaque "
            "utilisateur à le reconstruire dans un dossier en lecture seule.")
    for f in ("static", "modeles", "ressources", "NOTICE.md",
              "ressources/icon.ico"):
        if not (RACINE / f).exists():
            manques.append(f"il manque {f}")
    return manques


def ecris_version():
    v = version.version_windows()
    txt = f"""VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={v}, prodvers={v},
    mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        '040C04B0',
        [StringStruct('CompanyName', '{version.EDITEUR}'),
         StringStruct('FileDescription', 'Lecteur de japonais pour jeux video'),
         StringStruct('FileVersion', '{version.VERSION}'),
         StringStruct('InternalName', '{version.NOM}'),
         StringStruct('OriginalFilename', '{version.NOM}.exe'),
         StringStruct('ProductName', '{version.NOM}'),
         StringStruct('ProductVersion', '{version.VERSION}')])
    ]),
    VarFileInfo([VarStruct('Translation', [1036, 1200])])
  ]
)
"""
    (RACINE / "version_windows.txt").write_text(txt, encoding="utf-8")
    print(f"   ressource de version : {version.complet()}")


def lis_version_py() -> str:
    with open(RACINE / "app" / "version.py", encoding="utf-8", newline="") as f:
        return f.read()


def ecris_version_py(texte: str):
    with open(RACINE / "app" / "version.py", "w", encoding="utf-8",
              newline="") as f:
        f.write(texte)


def inscris_serveur(url: str) -> str:
    return inscris(SERVEUR_LICENCE=url)


def inscris(**champs) -> str:
    avant = lis_version_py()
    texte = avant
    for nom, valeur in champs.items():
        motif = re.compile(rf'^{nom} = "[^"\n]*"', re.M)
        if not motif.search(texte):
            raise SystemExit(f"impossible de trouver {nom} dans app/version.py")
        texte = motif.sub(f'{nom} = "{valeur}"', texte, count=1)
    ecris_version_py(texte)
    return avant


def empreinte(fichier: Path) -> Path:
    h = hashlib.sha256()
    with open(fichier, "rb") as f:
        for bloc in iter(lambda: f.read(1 << 20), b""):
            h.update(bloc)
    cible = fichier.with_name(fichier.name + ".sha256")
    cible.write_text(f"{h.hexdigest()}  {fichier.name}\n", encoding="utf-8")
    print(f"   {cible.name} — {h.hexdigest()[:16]}…")
    return cible


def construit_web(setup: Path, empreinte_hex: str, depot: str):
    iscc = trouve_iscc()
    if not iscc:
        print("   (Inno Setup absent : pas d'installateur web)")
        return None
    r = subprocess.run([str(iscc), f"/DVersion={version.VERSION}",
                        f"/DSetupHash={empreinte_hex}", f"/DDepot={depot}",
                        str(RACINE / "installateur" / "DNAreader-Web.iss")],
                       cwd=str(RACINE / "installateur"),
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    if r.returncode != 0:
        print("   Inno Setup a refusé l'installateur web :")
        print("  ", (r.stdout or r.stderr or "").strip().splitlines()[-1][:200])
        return None
    web = DIST / f"DNAreader-WebSetup-{version.VERSION}.exe"
    if not web.exists():
        print(f"   {web.name} attendu et absent")
        return None
    print(f"   {web} — {poids(web)}")
    return web


def dis_comment_publier(setup: Path, somme: Path, depot: str):
    tag = f"v{version.VERSION}"
    print()
    print("   Pour publier cette version :")
    print(f"     gh release create {tag} --repo {depot} \\")
    print(f"       --title \"{version.NOM} {version.VERSION}\" \\")
    print(f"       --notes \"ce qui change\" \\")
    print(f"       \"{setup}\" \\")
    print(f"       \"{somme}\"")
    print()
    print("   LES DEUX FICHIERS, pas seulement l'installateur : sans l'empreinte")
    print("   l'application refuse la mise à jour, et personne ne la recevra.")


def annonce_le_mode(url: str):
    if url:
        print(f"   CLÉ EXIGÉE — serveur : {url}")
        print(f"   essai gratuit de {version.ESSAI_JOURS} jours, compté par ce serveur")
    else:
        print("   MODE LIBRE — aucune clé, aucun essai, rien n'est demandé.")
        print("   Pour la version vendue : --serveur https://sync.exemple.fr")


def poids(chemin: Path) -> str:
    if chemin.is_file():
        o = chemin.stat().st_size
    else:
        o = sum(f.stat().st_size for f in chemin.rglob("*") if f.is_file())
    return f"{o / 1e6:.0f} Mo"


def construit_exe():
    t0 = time.time()
    r = subprocess.run(
        [str(PY), "-m", "PyInstaller", str(RACINE / "DNAreader.spec"),
         "--noconfirm", "--distpath", str(DIST), "--workpath", str(RACINE / "build")],
        cwd=str(RACINE), env=dict(os.environ, PYTHONIOENCODING="utf-8"))
    if r.returncode != 0:
        raise SystemExit("PyInstaller a échoué (voir ci-dessus)")
    exe = SORTIE / "DNAreader.exe"
    if not exe.exists():
        raise SystemExit(f"l'exécutable attendu est absent : {exe}")
    print(f"   {SORTIE} — {poids(SORTIE)} en {time.time() - t0:.0f} s")


def construit_installateur():
    iscc = trouve_iscc()
    if not iscc:
        print("   Inno Setup n'est pas installé : pas de .exe d'installation.")
        print("   À installer une fois depuis https://jrsoftware.org/isdl.php")
        print("   (gratuit, libre). En attendant, archive portable :")
        zip_portable()
        return None
    r = subprocess.run([str(iscc), f"/DVersion={version.VERSION}",
                        str(RACINE / "installateur" / "DNAreader.iss")],
                       cwd=str(RACINE / "installateur"))
    if r.returncode != 0:
        raise SystemExit("Inno Setup a échoué (voir ci-dessus)")
    setup = DIST / f"DNAreader-Setup-{version.VERSION}.exe"
    if not setup.exists():
        autres = sorted(p.name for p in DIST.glob("DNAreader-Setup-*.exe"))
        raise SystemExit(
            f"Inno Setup a réussi mais {setup.name} est absent.\n"
            f"   Trouvé à la place : {', '.join(autres) or '(rien)'}\n"
            f"   Le numéro de version du .iss ne suit pas app/version.py.")
    print(f"   {setup} — {poids(setup)}")
    return setup


def zip_portable():
    cible = DIST / f"DNAreader-{version.VERSION}-portable.zip"
    with zipfile.ZipFile(cible, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for f in sorted(SORTIE.rglob("*")):
            if f.is_file():
                z.write(f, "DNAreader/" + str(f.relative_to(SORTIE)).replace("\\", "/"))
    print(f"   {cible} — {poids(cible)}")
    return cible


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sans-installateur", action="store_true")
    ap.add_argument("--portable", action="store_true",
                    help="fabrique aussi l'archive portable")
    ap.add_argument("--serveur", default="", metavar="URL",
                    help="adresse du serveur de licence a INSCRIRE dans la "
                         "build. Sans elle : mode libre, aucune cle demandee")
    ap.add_argument("--depot", default=None, metavar="OWNER/REPO",
                    help="depot GitHub ou l'app cherchera ses mises a jour. "
                         f"Par defaut {version.DEPOT_RELEASES or '(aucun)'} ; "
                         "\"\" pour ne jamais chercher")
    a = ap.parse_args()

    print(f"Construction de {version.complet()}")

    titre("1. ce qu'il faut avoir")
    manques = verifie()
    if manques:
        for m in manques:
            print(f"   MANQUE : {m}")
        raise SystemExit(1)
    print("   tout est là")

    titre("2. ce que cette build demandera")
    annonce_le_mode(a.serveur or version.SERVEUR_LICENCE)
    depot = version.DEPOT_RELEASES if a.depot is None else a.depot
    if depot:
        print(f"   mises à jour cherchées sur : {depot}")
    else:
        print("   AUCUNE recherche de mise à jour dans cette build.")

    a_inscrire = {}
    if a.serveur:
        a_inscrire["SERVEUR_LICENCE"] = a.serveur
    if a.depot is not None:
        a_inscrire["DEPOT_RELEASES"] = a.depot
    avant = inscris(**a_inscrire) if a_inscrire else None
    try:
        titre("3. ressource de version")
        ecris_version()

        titre("4. l'exécutable")
        construit_exe()
    finally:
        if avant is not None:
            ecris_version_py(avant)
            print("   (app/version.py remis comme avant)")

    if a.sans_installateur:
        if a.portable:
            titre("5. archive portable")
            zip_portable()
        print("\nTerminé.")
        return 0

    titre("5. l'installateur")
    setup = construit_installateur()
    somme = None
    web = None
    if setup and setup.exists():
        titre("6. l'empreinte de l'installateur")
        somme = empreinte(setup)
        titre("7. l'installateur web (celui qu'on peut envoyer)")
        web = construit_web(setup, somme.read_text(encoding="utf-8").split()[0],
                            depot or version.DEPOT_RELEASES)
    if a.portable and setup:
        titre("8. archive portable")
        zip_portable()

    print("\nTerminé. À vérifier AVANT de diffuser :")
    print("   · l'exécutable démarre sur une machine sans Python ;")
    print("   · %LOCALAPPDATA%\\DNAreader se crée au premier lancement ;")
    print("   · l'application n'est pas signée : SmartScreen affichera un")
    print("     avertissement tant qu'elle n'aura pas de réputation.")
    if somme and depot:
        dis_comment_publier(setup, somme, depot)
    return 0


if __name__ == "__main__":
    sys.exit(main())
