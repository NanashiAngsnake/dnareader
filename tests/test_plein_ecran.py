# -*- coding: utf-8 -*-
import sys
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "app"))
sys.stdout.reconfigure(encoding="utf-8")
echecs = []


def verifie(nom, condition, detail=""):
    print(f"  {'OK  ' if condition else 'ECHEC'} {nom}" + (f" — {detail}" if detail else ""))
    if not condition:
        echecs.append(nom)


def main():
    import capture
    from PIL import Image, ImageDraw

    print("1. CE QUI DOIT ETRE VU COMME UNE CAPTURE RATEE")
    noir = Image.new("RGB", (1920, 1080), (0, 0, 0))
    verifie("un ecran entierement noir", capture._image_muette(noir))
    presque = Image.new("RGB", (1920, 1080), (3, 3, 4))
    verifie("un noir « presque » (bruit de compression)",
            capture._image_muette(presque))

    print("\n2. CE QUI NE DOIT SURTOUT PAS L'ETRE")
    nuit = Image.new("RGB", (1920, 1080), (6, 6, 9))
    ImageDraw.Draw(nuit).rectangle([700, 900, 1200, 940], fill=(230, 230, 230))
    verifie("une scene de nuit AVEC un sous-titre",
            not capture._image_muette(nuit),
            "c'est exactement le cas ou l'app sert le plus")
    lune = Image.new("RGB", (1920, 1080), (4, 4, 6))
    ImageDraw.Draw(lune).ellipse([1700, 80, 1760, 140], fill=(200, 200, 180))
    verifie("une nuit avec une seule tache claire",
            not capture._image_muette(lune))
    vrai = capture.capture_screen()
    verifie("l'ecran reel de cette machine", not capture._image_muette(vrai),
            f"{vrai.width}x{vrai.height}")

    print("\n3. LES DEUX SIGNAUX DOIVENT CONCORDER")
    etat = capture._etat_notifications()
    print(f"   etat systeme ici : {etat} "
          f"(3 = Direct3D plein ecran exclusif)")
    verifie("sur cette machine, rien n'est signale",
            capture.plein_ecran_exclusif(vrai) == "",
            "l'ecran est capturable, donc il n'y a rien a dire")
    vrai_etat = capture._etat_notifications
    try:
        capture._etat_notifications = lambda: 3
        verifie("etat « exclusif » MAIS image lisible -> on se tait",
                capture.plein_ecran_exclusif(nuit) == "",
                "sinon on envoie changer un reglage qui marchait")
        verifie("etat « exclusif » ET image noire -> on previent",
                capture.plein_ecran_exclusif(noir) != "")
        capture._etat_notifications = lambda: 5
        verifie("bureau normal ET image noire -> on se tait",
                capture.plein_ecran_exclusif(noir) == "",
                "un ecran noir sans jeu n'est pas un probleme de plein ecran")
    finally:
        capture._etat_notifications = vrai_etat

    print("\n4. LE COUT, PARCE QUE CA TOURNE 8 FOIS PAR SECONDE")
    t0 = time.perf_counter()
    for _ in range(200):
        capture._etat_notifications()
    ms_etat = (time.perf_counter() - t0) / 200 * 1000
    t0 = time.perf_counter()
    for _ in range(200):
        capture._image_muette(vrai)
    ms_img = (time.perf_counter() - t0) / 200 * 1000
    print(f"   etat systeme : {ms_etat:.3f} ms · examen de l'image : {ms_img:.3f} ms")
    verifie("l'examen de l'image reste sous 0,5 ms", ms_img < 0.5,
            "reduire AVANT de convertir en gris, pas l'inverse (3,17 -> 0,01 ms)")
    verifie("et il ne se paie que quand il apprend quelque chose",
            "if _etat_notifications() != QUNS_RUNNING_D3D_FULL_SCREEN"
            in (RACINE / "app" / "capture.py").read_text(encoding="utf-8"),
            "l'etat systeme court-circuite avant de toucher aux pixels")

    print("\n5. LE MESSAGE ARRIVE JUSQU'A LA BULLE, ET AVANT « couvert »")
    srv = (RACINE / "app" / "server.py").read_text(encoding="utf-8")
    verifie("la route le renvoie", '"plein_ecran": plein or None' in srv)
    cap_js = (RACINE / "static" / "js" / "10-capture.js").read_text(encoding="utf-8")
    verifie("le client le lit", "PLEIN_ECRAN = (g && g.plein_ecran)" in cap_js)
    bulle = (RACINE / "static" / "js" / "46-bulle.js").read_text(encoding="utf-8")
    verifie("la bulle le dit", "etat.pleinecran" in bulle)
    verifie("et il passe AVANT « le jeu est derriere X »",
            bulle.index("PLEIN_ECRAN)") < bulle.index("} else if (COUVERT)"),
            "sinon on accuse une fenetre au hasard")
    tuto = (RACINE / "static" / "js" / "60-tuto.js").read_text(encoding="utf-8")
    verifie("et le tutoriel le dit des l'etape « choisis ton jeu »",
            "sans bordure" in tuto,
            "le meilleur moment pour l'apprendre est avant le probleme")

    print()
    if echecs:
        print(f"{len(echecs)} ECHEC(S) : " + " · ".join(echecs))
        return 1
    print("OK : le plein ecran exclusif se dit, une scene de nuit ne le")
    print("     declenche pas, et le controle ne coute rien quand tout va bien")
    return 0


if __name__ == "__main__":
    sys.exit(main())
