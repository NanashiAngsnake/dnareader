# -*- coding: utf-8 -*-
import asyncio
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
    from PIL import Image
    import detect

    penche = Image.open(RACINE / "tests" / "images_reelles"
                        / "p5r_combat_commandes.png").convert("RGB")
    droit = Image.open(RACINE / "tests" / "images_reelles"
                       / "ff7r_menu_ability.jpg").convert("RGB")

    print("1. UN MENU PENCHE REND DES LIGNES, AVEC LEUR ANGLE")
    lignes = detect.lignes_rattrapees(penche, [], "rec", 12)
    verifie("des lignes sont trouvees", len(lignes) >= 4, f"{len(lignes)} ligne(s)")
    angles = [abs(l["angle"]) for l in lignes]
    verifie("dont plusieurs franchement penchees",
            sum(1 for a in angles if a >= 15) >= 2,
            "angles : " + ", ".join(f"{l['angle']:+.0f}" for l in lignes[:8]))
    textes = [l["text"] for l in lignes]
    print("   lu :", " · ".join(f"« {t} »" for t in textes[:6]))
    from dictionary import is_jp_char
    verifie("et tout ce qui sort contient du japonais",
            all(any(is_jp_char(c) for c in t) for t in textes),
            [t for t in textes if not any(is_jp_char(c) for c in t)] or "aucun latin")

    print("\n2. SUR UN ECRAN DROIT, ELLE RATTRAPE — ELLE N'INVENTE PAS")
    import json
    att = json.loads((RACINE / "tests" / "images_reelles" / "attendu.json")
                     .read_text(encoding="utf-8"))
    connues = set()
    for c in att["cas"]:
        connues.update(c.get("attendu") or [])
    rattrapees = detect.lignes_rattrapees(droit, [], "rec", 12)
    textes_d = [l["text"] for l in rattrapees]
    print("   rattrape :", " · ".join(f"« {t} »" for t in textes_d))
    vraies = [t for t in textes_d
              if any(t == k or (len(t) >= 3 and t in k) for k in connues)]
    verifie("ce qu'elle rend sur un ecran droit est du VRAI texte attendu",
            len(vraies) >= 2,
            f"{len(vraies)}/{len(textes_d)} figurent dans la verite de reference")
    verifie("et elle n'en deverse pas des dizaines", len(rattrapees) <= 12,
            f"{len(rattrapees)} ligne(s) — le plafond « maxi » les borne")

    print("\n3. PAS DE DOUBLON : ce qui est deja lu n'est pas relu")
    deja = [l["box"] for l in lignes]
    encore = detect.lignes_rattrapees(penche, deja, "rec", 12)
    verifie("en redonnant les memes boites, plus rien ne sort",
            len(encore) < len(lignes),
            f"{len(lignes)} sans filtre -> {len(encore)} avec")

    print("\n4. LA CARTE N'EST CALCULEE QU'UNE FOIS")
    boites = [[10, 10, 100, 30]]
    t0 = time.perf_counter()
    notes, penchees = detect.juge_complet(penche, boites, "rec", 6)
    ms_ensemble = (time.perf_counter() - t0) * 1000
    t0 = time.perf_counter()
    detect.score_boites(penche, boites)
    detect.lignes_rattrapees(penche, boites, "rec", 6)
    ms_separes = (time.perf_counter() - t0) * 1000
    print(f"   ensemble : {ms_ensemble:.0f} ms · separement : {ms_separes:.0f} ms")
    verifie("les deux ensemble ne coutent pas plus que separement",
            ms_ensemble <= ms_separes * 1.05,
            "sinon la carte est calculee deux fois par image lue")
    verifie("et l'appel groupe rend bien les deux",
            len(notes) == 1 and isinstance(penchees, list))

    print("\n5. REPRODUCTIBLE : deux passes donnent le meme resultat")
    import chaine_lecture as cl

    async def lis():
        return await cl._read(penche, "auto", "windows", "Persona 5 Royal", None)

    a = [l["text"] for l in asyncio.run(lis())]
    b = [l["text"] for l in asyncio.run(lis())]
    verifie("deux lectures de la meme image rendent la meme chose", a == b,
            f"{len(a)} vs {len(b)} lignes")
    verifie("et le menu penche rend maintenant plusieurs repliques",
            len(a) >= 5, " · ".join(a[:6]))

    print("\n6. CE QUE CA COUTE SUR UN JEU ORDINAIRE")
    async def lis_droit():
        return await cl._read(droit, "auto", "windows", "FF7R", None)
    asyncio.run(lis_droit())
    asyncio.run(lis_droit())
    incline_ms = cl.PERF.get("incline_ms", 0)
    print(f"   detecteur {cl.PERF.get('detecteur_ms')} ms · "
          f"passe penchee {incline_ms} ms")
    verifie("la passe penchee ne coute presque rien quand il n'y a rien",
            incline_ms <= 5,
            "la carte est partagee avec la notation des boites")

    print()
    if echecs:
        print(f"{len(echecs)} ECHEC(S) : " + " · ".join(echecs))
        return 1
    print("OK : le texte penche se lit, l'horizontal ne paie rien,")
    print("     et deux passes donnent le meme resultat")
    return 0


if __name__ == "__main__":
    sys.exit(main())
