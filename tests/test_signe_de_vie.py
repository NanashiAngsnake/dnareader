# -*- coding: utf-8 -*-
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
PY_EXE = RACINE / ".venv" / "Scripts" / "python.exe"
sys.stdout.reconfigure(encoding="utf-8")

echecs = []


def verifie(nom, condition, detail=""):
    print(f"  {'OK  ' if condition else 'ECHEC'} {nom}"
          + (f" — {detail}" if detail else ""))
    if not condition:
        echecs.append(nom)


def dans_un_processus_neuf(tmp: Path, code: str) -> str:
    r = subprocess.run(
        [str(PY_EXE), "-c", "import sys; sys.path.insert(0, '.')\n" + code],
        cwd=str(RACINE / "app"), capture_output=True, text=True,
        encoding="utf-8", errors="replace",
        env=dict(os.environ, DNAREADER_DONNEES=str(tmp), PYTHONIOENCODING="utf-8"))
    return (r.stdout or "") + (r.stderr or "")


def main():
    tmp = Path(tempfile.mkdtemp(prefix="dnar-touches-"))

    print("1. LES TOUCHES SURVIVENT AU REDEMARRAGE")
    print("   (chaque etape dans un processus NEUF — sinon on ne prouverait")
    print("    qu'une variable restee en memoire)")
    sortie = dans_un_processus_neuf(tmp, """
import hotkey
print('DEFAUT', hotkey.current('capture'))
""")
    verifie("au depart, la touche par defaut", "DEFAUT f8" in sortie,
            sortie.strip()[-60:])

    sortie = dans_un_processus_neuf(tmp, """
import hotkey
hotkey._save_hotkey('capture', 'f4')
hotkey._save_hotkey('bulle', 'ctrl+alt+b')
print('ECRIT')
""")
    verifie("on rebinde deux touches", "ECRIT" in sortie, sortie.strip()[-60:])

    sortie = dans_un_processus_neuf(tmp, """
import hotkey
print('RELU', hotkey.current('capture'), hotkey.current('bulle'))
""")
    verifie("elles sont retrouvees telles quelles",
            "RELU f4 ctrl+alt+b" in sortie, sortie.strip()[-70:])

    fichier = tmp / "settings.json"
    verifie("et elles sont bien sur le disque", fichier.exists(),
            str(fichier.name))
    if fichier.exists():
        d = json.loads(fichier.read_text(encoding="utf-8"))
        verifie("dans settings.json, sous « hotkeys »",
                d.get("hotkeys", {}).get("capture") == "f4", str(d)[:70])

    sortie = dans_un_processus_neuf(tmp, """
import hotkey
h = hotkey.all_hotkeys()
print('TOUTES', len(h), sorted(h)[:4])
""")
    verifie("les autres gardent leur defaut", "TOUTES 9" in sortie,
            sortie.strip()[-70:])

    print("\n2. LE SIGNE DE VIE EN VEILLE")
    js = (RACINE / "static" / "js" / "46-bulle.js").read_text(encoding="utf-8")
    html = (RACINE / "static" / "overlay.html").read_text(encoding="utf-8")

    verifie("la veille se rend toujours plus discrete",
            "applyOpacity(false);" in js,
            "c'est voulu : on joue, elle s'efface")
    verifie("mais elle annonce d'abord ce qu'elle ecoute",
            "annonceLaVeille()" in js and "bulle.jecoute" in js)
    verifie("le nom du jeu y figure",
            "replace('{0}', court)" in js,
            "sinon le signe de vie ne dit pas SUR QUOI elle est branchee")
    verifie("une seule fois par jeu",
            "if (jeuAnnonce === gameTitle) return;" in js,
            "un signe de vie, pas un rappel")
    verifie("puis elle repasse aux trois points",
            "oeil.textContent = '···';" in js)
    verifie("et redevient discrete SEULEMENT si toujours en veille",
            "classList.contains('veille')" in js,
            "une lecture arrivee entre-temps a repris la main sur l'opacite")
    verifie("l'annonce a son propre style, lisible",
            "body.bulle.veille.annonce #veilleoeil" in html
            and "var(--accent)" in html.split("annonce #veilleoeil")[1][:120])
    verifie("la fenetre se recolle a son contenu apres coup",
            "ajusteFenetreAuContenu()" in js.split("annonceLaVeille")[1][:1400],
            "sinon la bulle garde la largeur de l'annonce disparue")

    print("\n3. AUCUN BOUTON LIÉ TROP TARD (le piège qui bloque tout)")
    js_dir = RACINE / "static" / "js"
    coupables = []
    for f in sorted(js_dir.glob("*.js")):
        t = f.read_text(encoding="utf-8")
        for m in re.finditer(r"DOMContentLoaded['\"]\s*,", t):
            bloc = t[m.end():m.end() + 3000]
            if re.search(r"addEventListener\(\s*['\"]click", bloc):
                coupables.append(f.name)
    verifie("aucun clic n'est lié dans un DOMContentLoaded",
            not coupables, ", ".join(sorted(set(coupables))) or "aucun")

    html = (RACINE / "static" / "overlay.html").read_text(encoding="utf-8")
    boutons = set(re.findall(r'<button[^>]*id="([a-zA-Z0-9_]+)"', html))
    tout_js = "\n".join(f.read_text(encoding="utf-8") for f in js_dir.glob("*.js"))
    orphelins = [b for b in sorted(boutons)
                 if f"'{b}'" not in tout_js and f'"{b}"' not in tout_js]
    verifie(f"les {len(boutons)} boutons de la bulle sont tous cites en JS",
            not orphelins, ", ".join(orphelins) or "aucun orphelin")

    print("\n4. LE JEU CHOISI SE RETIENT")
    cap = (js_dir / "10-capture.js").read_text(encoding="utf-8")
    boot = (js_dir / "50-boot.js").read_text(encoding="utf-8")
    verifie("setGame l'enregistre", "localStorage.setItem(JEU_RETENU" in cap)
    verifie("et le démarrage le reprend",
            "reprendLeJeuRetenu()" in boot)
    verifie("mais SEULEMENT si la fenêtre existe encore",
            "noms.includes(voulu)" in cap,
            "sinon la bulle veille sur une fenêtre absente, sans rien dire")
    verifie("sans await au niveau racine",
            "await reprendLeJeuRetenu" not in boot,
            "un await hors fonction async empêche tout le fichier de charger")

    print("\n5. CHOISIR UNE ZONE EFFACE CE QU'ON VOYAIT")
    zone = cap[cap.index("async function startZonePick"):]
    zone = zone[:zone.index("window.startZonePick")]
    verifie("LINES est vide a la selection", "LINES = [];" in zone)
    verifie("et l'affichage refait tout de suite", "renderText()" in zone,
            "sinon l'ancien texte reste a l'ecran")
    verifie("les donnees de travail aussi", "resetLive();" in zone)
    verifie("et la prochaine lecture est forcee", "lastSig = null" in zone)

    print("\n6. DEPLACER LA BULLE, C'EST CHOISIR — MEME QUAND ELLE PARLE")
    win = (js_dir / "40-window.js").read_text(encoding="utf-8")
    i = win.index("memoriseRepos === 'function'")
    garde = win[max(0, i - 400):i]
    verifie("l'endroit se retient meme hors attente",
            "classList.contains('attente')" not in garde.split("if (aBouge")[-1],
            "on ne jette plus le geste quand la bulle affiche du texte")
    verifie("mais toujours pas sur un simple clic", "if (aBouge" in win,
            "aBouge distingue un vrai deplacement d'un clic sur la poignee")
    bulle = (js_dir / "46-bulle.js").read_text(encoding="utf-8")
    verifie("et le rangement ne se fait qu'en attente",
            "if (!enAttente || !gameTitle) return;" in bulle,
            "sinon elle serait arrachee a la phrase qu'elle explique")

    print("\n7. « À JOUR » NE SE DIT PLUS SANS DIRE QUAND")
    m = (js_dir / "80-maj.js").read_text(encoding="utf-8")
    verifie("la date du dernier controle accompagne « à jour »",
            "depuisQuand(MAJ.dernier_controle)" in m)
    verifie("et elle se lit en francais courant",
            "instant" in m and "il y a" in m,
            "la question posee est « est-ce recent », pas « quel jour »")
    verifie("« À jour. » tout court a disparu",
            "'À jour.'" not in m and '"À jour."' not in m)

    print("\n8. LE BOUTON DE PAIEMENT NE RESTE JAMAIS BLOQUÉ")
    bloc = cap[cap.index("let MAJ_ATTENTE"):cap.index("setInterval(relisAcces")]
    verifie("l'arret de surveillance rend le bouton",
            "rendLeBouton();" in bloc.split("function arreteLaSurveillance")[1][:200])
    verifie("un abandon est reconnu",
            "r.aucune_attente || r.expire" in bloc)
    verifie("et une attente trop longue aussi",
            "ATTENTE_MAX_MIN" in bloc,
            "quelqu'un qui ferme l'onglet ne revient pas dans l'heure")
    verifie("un seul chemin le desactive, plusieurs le rendent",
            bloc.count("ab.disabled = true") == 1
            and bloc.count("rendLeBouton()") + bloc.count("ab.disabled = false") >= 3)
    verifie("recliquer ROUVRE la meme page de paiement",
            "PAIEMENT_URL" in bloc and "if (MAJ_ATTENTE && PAIEMENT_URL)" in bloc,
            "sinon trois clics laissent trois abonnements chez PayPal")
    verifie("le libelle d'origine n'est retenu qu'une fois",
            "if (!ab.dataset.libelle)" in bloc,
            "sinon « en attente… » deviendrait le libelle de repos")

    print("\n9. LE SERVEUR DE LICENCE NE SE DEMANDE PAS")
    lc = (RACINE / "app" / "licence_client.py").read_text(encoding="utf-8")
    reg = (js_dir / "70-reglages.js").read_text(encoding="utf-8")
    verifie("l'adresse inscrite dans la build est rendue a l'interface",
            "version.SERVEUR_LICENCE" in lc and "serveur_impose" in lc)
    verifie("le champ arrive rempli et verrouille",
            "serveur_impose" in reg and "readOnly = true" in reg,
            "la changer ne peut que casser l'activation")
    verifie("« J'ai une clé » mene droit au champ",
            "ouvrir_reglages('cle')" in cap and "location.hash === '#cle'" in reg)

    print("\n10. ACTIVER UNE CLÉ FAIT DISPARAÎTRE LE BANDEAU TOUT DE SUITE")
    srv = (RACINE / "app" / "server.py").read_text(encoding="utf-8")
    for route, quoi in (("licence_activer", "activer"), ("licence_oublier", "retirer")):
        bout = srv[srv.index(f"def {route}"):]
        bout = bout[:bout.index("@app.")] if "@app." in bout else bout[:800]
        verifie(f"{quoi} une clé prévient la bulle",
                '_broadcast({"type": "acces"})' in bout,
                "la diffusion part du SERVEUR : tous les chemins sont couverts")
        verifie(f"  et la route est bien async", bout.lstrip().startswith("async")
                or srv[max(0, srv.index(f"def {route}") - 6):].startswith("async"),
                "await _broadcast dans une route sync ne partirait jamais")
    verifie("la bulle écoute ce signal",
            "m.type === 'acces'" in cap and "relisAcces()" in cap)

    print("\n11. DEUX TRANSPARENCES, ET LES DEUX FENETRES REGLENT LES MEMES")
    set_js = (js_dir / "30-settings.js").read_text(encoding="utf-8")
    bulle = (js_dir / "46-bulle.js").read_text(encoding="utf-8")
    reg_js = (js_dir / "70-reglages.js").read_text(encoding="utf-8")
    reg_html = (RACINE / "static" / "reglages.html").read_text(encoding="utf-8")

    verifie("la lecture n'est plus figee a 100 en dur",
            "enVeille ? OPACITY : 100" not in set_js,
            "c'etait la ligne qui interdisait le reglage")
    verifie("chaque etat a SA variable",
            "enVeille ? OPACITY : OPACITY_LECTURE" in set_js)
    verifie("la valeur de lecture survit au redemarrage",
            "kgr_opacity_lecture" in set_js)
    verifie("elle a un plancher plus haut que l'autre",
            "Math.max(40, Math.min(100, OPACITY_LECTURE))" in set_js,
            "sous 40 % le japonais sur un decor anime passe pour une panne")
    verifie("elle suit le jeu, comme le reste du profil",
            "opacitylec: OPACITY_LECTURE" in
            (js_dir / "45-profile.js").read_text(encoding="utf-8"))
    verifie("le curseur de la bulle repond",
            "$('bopacitylec').addEventListener" in bulle)
    verifie("celui de la fenetre de reglages aussi",
            "$('opacitelec').addEventListener" in reg_js
            and 'id="opacitelec"' in reg_html)
    verifie("et il passe par le MEME chemin que l'autre",
            "regle('opacitylec'" in reg_js
            and "case 'opacitylec':" in set_js,
            "deux fenetres qui reglent la meme chose par deux codes divergent")

    print("\n12. « RIEN NE QUITTE LA MACHINE » N'EST PLUS ECRIT NULLE PART")
    for nom, txt in (("reglages.html", reg_html),
                     ("overlay.html", html),
                     ("70-reglages.js", reg_js)):
        verifie(f"{nom} ne promet plus le contraire",
                "Rien ne quitte la machine" not in txt
                and "ne part nulle part" not in txt)

    print()
    if echecs:
        print(f"{len(echecs)} ECHEC(S) : " + " · ".join(echecs))
        return 1
    print("OK : les touches tiennent d'un lancement a l'autre, et la bulle dit")
    print("     ce qu'elle ecoute avant de s'effacer")
    return 0


if __name__ == "__main__":
    sys.exit(main())
