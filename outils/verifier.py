# -*- coding: utf-8 -*-
import json
import re
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
APP = BASE / "app"
sys.path.insert(0, str(APP))
PY = BASE / ".venv" / "Scripts" / "python.exe"
PORT = 8766

INLINE = re.compile(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", re.S)
ID_IN_HTML = re.compile(r"\bid=[\"']([^\"']+)[\"']")
ID_IN_JS = re.compile(r"""\$\(\s*['"]([A-Za-z0-9_-]+)['"]\s*\)"""
                      r"""|getElementById\(\s*['"]([A-Za-z0-9_-]+)['"]\s*\)""")
BTN_IN_HTML = re.compile(r"<button[^>]*\bid=[\"']([^\"']+)[\"']")
BIND_WINDOW = 400
BOUND_NEAR = re.compile(r"""\.addEventListener\(\s*['"]click['"]|\.onclick\s*=""")

_fails: list[str] = []
_notes: list[str] = []
_skipped: list[str] = []


def check(ok: bool, label: str, detail: str = "") -> bool:
    print(f"  {'OK  ' if ok else 'ECHEC'} {label}")
    if not ok:
        _fails.append(f"{label}\n{detail}".rstrip())
    return ok


def check_python() -> None:
    print("\nA. modules Python")
    mods = sorted(p.stem for p in APP.glob("*.py")
                  if p.stem not in {"verifier", "verifier_js"})
    code = "import sys\n" + "".join(
        f"import {m}\n" for m in mods) + "print('ok')"
    r = subprocess.run([str(PY), "-c", code], capture_output=True, text=True,
                       cwd=APP)
    check(r.returncode == 0, f"{len(mods)} module(s) s'importent",
          (r.stderr or r.stdout).strip())


def _node_check(code: str, label: str):
    with tempfile.NamedTemporaryFile("w", suffix=".js", encoding="utf-8",
                                     delete=False) as f:
        f.write(code)
        tmp = f.name
    try:
        r = subprocess.run(["node", "--check", tmp], capture_output=True, text=True)
        return None if r.returncode == 0 else (r.stderr or r.stdout).replace(tmp, label).strip()
    finally:
        Path(tmp).unlink(missing_ok=True)


def check_js_loaded() -> None:
    print("\nB'. les modules sont chargés par une page")
    charges = set()
    for page in ("overlay.html", "reglages.html", "index.html"):
        p = BASE / "static" / page
        if p.exists():
            charges |= set(re.findall(r'src="/static/js/([^"]+)"',
                                      p.read_text(encoding="utf-8")))
    sur_disque = {p.name for p in (BASE / "static" / "js").glob("*.js")}
    oublies = sorted(sur_disque - charges)
    fantomes = sorted(charges - sur_disque)
    check(not oublies, "aucun module oublié par les pages",
          "présents sur le disque mais chargés nulle part : " + ", ".join(oublies))
    check(not fantomes, "aucun module manquant",
          "référencés par une page mais absents du disque : " + ", ".join(fantomes))


def check_js_syntax() -> None:
    print("\nB. syntaxe JavaScript")
    for html in sorted((BASE / "static").glob("*.html")):
        blocs = INLINE.findall(html.read_text(encoding="utf-8"))
        if blocs:
            check(_node_check("\n".join(blocs), html.name) is None,
                  f"{html.name} ({len(blocs)} bloc(s) inline)",
                  _node_check("\n".join(blocs), html.name) or "")
    for js in sorted((BASE / "static" / "js").glob("*.js")):
        err = _node_check(js.read_text(encoding="utf-8"), js.name)
        check(err is None, f"js/{js.name}", err or "")


def _ids_available(html_text: str, js_texts: list[str]) -> set:
    ids = set(ID_IN_HTML.findall(html_text))
    for t in js_texts:
        ids |= set(ID_IN_HTML.findall(t))
    return ids


def check_ids_uniques() -> None:
    import collections
    print("\nC'. aucun identifiant en double")
    for nom in ("overlay.html", "reglages.html", "index.html"):
        page = BASE / "static" / nom
        if not page.exists():
            continue
        ids = re.findall(r'id="([A-Za-z0-9_-]+)"', page.read_text(encoding="utf-8"))
        dup = sorted(i for i, c in collections.Counter(ids).items() if c > 1)
        check(not dup, nom, "ids presents plusieurs fois : " + ", ".join(dup))


def check_ids() -> None:
    print("\nC. chaque id utilisé par le JS existe")
    pairs = []
    for page in ("overlay.html", "reglages.html"):
        p = BASE / "static" / page
        if not p.exists():
            continue
        html = p.read_text(encoding="utf-8")
        noms = re.findall(r'src="/static/js/([^"]+)"', html)
        mods = [(n, (BASE / "static" / "js" / n).read_text(encoding="utf-8"))
                for n in noms if (BASE / "static" / "js" / n).exists()]
        if mods:
            pairs.append((page, html, mods))
    idx = (BASE / "static" / "index.html").read_text(encoding="utf-8")
    pairs.append(("index.html", idx, [("index.html (inline)", "\n".join(INLINE.findall(idx)))]))

    for page, html, sources in pairs:
        available = _ids_available(html, [s for _, s in sources])
        for name, src in sources:
            used = {a or b for a, b in ID_IN_JS.findall(src)}
            missing = sorted(used - available)
            check(not missing, f"{name} -> {page}",
                  "ids absents de la page : " + ", ".join(missing))


def _is_bound(btn_id: str, js: str) -> bool:
    for m in re.finditer(r"['\"]" + re.escape(btn_id) + r"['\"]", js):
        if BOUND_NEAR.search(js, m.end(), m.end() + BIND_WINDOW):
            return True
    return False


def check_buttons() -> None:
    print("\nD. chaque bouton visible répond au clic")
    ovl = (BASE / "static" / "overlay.html").read_text(encoding="utf-8")
    js = "\n".join(p.read_text(encoding="utf-8")
                   for p in sorted((BASE / "static" / "js").glob("*.js")))
    orphelins = sorted(b for b in set(BTN_IN_HTML.findall(ovl.split("<body>", 1)[1]))
                       if not _is_bound(b, js))
    check(not orphelins, "overlay.html",
          "boutons sans gestionnaire de clic : " + ", ".join(orphelins))

    reg = BASE / "static" / "reglages.html"
    if reg.exists():
        h = reg.read_text(encoding="utf-8")
        corps = h.split("<header>", 1)[-1]
        orph_r = sorted(b for b in set(BTN_IN_HTML.findall(corps))
                        if not _is_bound(b, js))
        check(not orph_r, "reglages.html",
              "boutons sans gestionnaire de clic : " + ", ".join(orph_r))

    idx = (BASE / "static" / "index.html").read_text(encoding="utf-8")
    inline = "\n".join(INLINE.findall(idx))
    orph2 = sorted(b for b in set(BTN_IN_HTML.findall(idx.split("<body>", 1)[1]))
                   if not _is_bound(b, inline))
    check(not orph2, "index.html",
          "boutons sans gestionnaire de clic : " + ", ".join(orph2))


def _port_busy() -> bool:
    with socket.socket() as s:
        s.settimeout(0.4)
        return s.connect_ex(("127.0.0.1", PORT)) == 0


def _get(path: str, timeout: float = 4.0):
    with urllib.request.urlopen(f"http://127.0.0.1:{PORT}{path}", timeout=timeout) as r:
        return r.status, r.read()


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def check_live() -> None:
    global PORT
    print("\nE. démarrage réel de l'application")
    doublon_testable = not _port_busy()
    if not doublon_testable:
        PORT = _free_port()
        print(f"  NOTE   le port 8766 est pris : contrôles menés sur {PORT}")
        _skipped.append("refus du doublon : une instance occupe deja le port 8766 "
                        "(ferme l'app puis relance pour le tester)")

    proc = subprocess.Popen(
        [str(PY), "-c",
         "import overlay, uvicorn\n"
         "from server import app\n"
         f"uvicorn.run(app, host='127.0.0.1', port={PORT}, log_level='warning')"],
        cwd=APP, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        up = False
        for _ in range(80):
            if proc.poll() is not None:
                break
            try:
                _get("/api/ping", timeout=1)
                up = True
                break
            except Exception:
                time.sleep(0.5)
        if not check(up, "le serveur répond sur le port réel",
                     (proc.stdout.read() if proc.poll() is not None else "")):
            return

        st, body = _get("/api/ping")
        check(json.loads(body)["app"] == "dnareader",
              "/api/ping identifie bien l'app")

        for route in ["/", "/overlay", "/api/windows", "/api/engines",
                      "/api/hotkey", "/api/vocab", "/api/corrections",
                      "/static/js/00-core.js", "/static/js/50-boot.js"]:
            try:
                st, _ = _get(route)
                check(st == 200, f"GET {route}", f"code HTTP {st}")
            except Exception as e:
                check(False, f"GET {route}", str(e))

        if doublon_testable:
            print("\nF. un second lancement est refusé proprement")
            check(overlay_already_running(), "l'app détecte l'instance déjà en place")

        print("\nG. la fenêtre de l'app affiche vraiment l'interface")
        check_window()
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()


_WINDOW_PROBE = r'''
import json, time, webview, overlay
OUT = {}
def probe(w):
    time.sleep(3.5)
    try:
        OUT["boutons"] = w.evaluate_js("document.querySelectorAll('button').length")
        # On mesure #bar, ce qui est REELLEMENT visible : l'app demarre en mode
        # bulle, ou la barre de controle (#ctl) est masquee. Mesurer #ctl
        # rapportait donc 0 px et faisait echouer un controle sain.
        OUT["barre"]   = w.evaluate_js(
            "(function(){var c=document.getElementById('bar');"
            "return c?Math.round(c.getBoundingClientRect().height):0})()")
        OUT["regles_css"] = w.evaluate_js(
            "(function(){try{return document.styleSheets[0].cssRules.length}"
            "catch(e){return 0}})()")
        OUT["erreurs"] = w.evaluate_js("JSON.stringify(window.__errors||[])")
        OUT["selfcheck"] = w.evaluate_js(
            "typeof selfCheck==='function' ? selfCheck() : false")
    except Exception as e:
        OUT["erreur"] = repr(e)
    print("PROBE " + json.dumps(OUT), flush=True)
    w.destroy()
# js_api : la MEME interface que l'application, sinon la fenetre de controle
# n'exerce pas le meme code (les appels vers Python n'existeraient pas)
w = webview.create_window("DNAreader - controle",
                          url="http://127.0.0.1:%d/overlay",
                          js_api=overlay.Api(),
                          width=900, height=150, frameless=True,
                          easy_drag=False, background_color="#141519")
webview.start(probe, w)
'''


def check_window() -> None:
    r = subprocess.run([str(PY), "-c", _WINDOW_PROBE % PORT],
                       capture_output=True, text=True, cwd=APP, timeout=90)
    line = next((l for l in r.stdout.splitlines() if l.startswith("PROBE ")), None)
    if not check(line is not None, "la fenêtre répond",
                 (r.stderr or r.stdout)[-800:]):
        return
    d = json.loads(line[6:])
    check(d.get("boutons", 0) >= 6, f"les contrôles sont présents ({d.get('boutons')} boutons)")
    check(d.get("barre", 0) > 20, f"la barre a une hauteur réelle ({d.get('barre')} px)")
    check(d.get("regles_css", 0) > 50, f"le style est appliqué ({d.get('regles_css')} règles)")
    check(d.get("erreurs") in ("[]", None), "aucune erreur JavaScript",
          str(d.get("erreurs")))
    check(bool(d.get("selfcheck")), "l'auto-contrôle interne passe")


def overlay_already_running() -> bool:
    r = subprocess.run(
        [str(PY), "-c", "import overlay; print(overlay._already_running())"],
        capture_output=True, text=True, cwd=APP)
    return r.stdout.strip().endswith("True")


def check_repeint() -> None:
    print("\nH''. tout redimensionnement repeint la fenêtre")
    src = (BASE / "app" / "overlay.py").read_text(encoding="utf-8").splitlines()
    manques = []
    for i, ligne in enumerate(src):
        if "SetWindowPos(" not in ligne:
            continue
        appel = "\n".join(src[i:i + 4])
        if "SWP_NOSIZE" in appel or "SWP_NOMOVE | SWP_NOSIZE" in appel:
            continue
        suite = "\n".join(src[i:i + 12])
        if "InvalidateRect" not in suite:
            manques.append(f"ligne {i + 1}")
    check(not manques,
          "chaque redimensionnement est suivi d'une invalidation",
          "SetWindowPos sans InvalidateRect : " + ", ".join(manques))


def check_lanceur() -> None:
    print("\nH'. le lanceur ouvre la bulle")
    src = (BASE / "lancer.pyw").read_text(encoding="utf-8")
    m = re.search(r"overlay\.main\(\s*start_mode\s*=\s*[\"'](\w+)[\"']", src)
    mode = m.group(1) if m else None
    check(mode == "overlay",
          "lancer.pyw démarre en mode bulle",
          f"start_mode = {mode!r} — « window » ouvre la vue fenêtre, "
          f"où la visite guidée n'existe pas")


def check_modes_imposes() -> None:
    print("\nH. aucun mode d'affichage ne s'impose tout seul")
    import profiles
    interdits = [c for c in ("ghost", "bulle") if c in profiles.CHAMPS]
    check(not interdits,
          "le profil du jeu ne mémorise aucun mode d'affichage",
          "champ(s) à retirer de profiles.CHAMPS : " + ", ".join(interdits))

    js = (BASE / "static" / "js" / "46-bulle.js").read_text("utf-8")
    check("localStorage.getItem('kgr_bulle')" not in js,
          "le mode bulle ne se réveille pas depuis le navigateur")

    prof = BASE / "donnees" / "profils.json"
    if prof.exists():
        import json as _json
        try:
            d = _json.loads(prof.read_text("utf-8"))
        except Exception:
            d = {}
        sales = [g for g, v in d.items()
                 if isinstance(v, dict) and ("bulle" in v or "ghost" in v)]
        check(not sales, "aucun profil enregistré ne traîne un ancien mode",
              "profil(s) à nettoyer : " + ", ".join(sales))


def check_bulle_reelle() -> None:
    print("\nI. le mode bulle, mesuré dans une vraie fenêtre")
    sonde = BASE / "outils" / "sonde_bulle.py"
    if not (sonde.exists() and (BASE / "tests" / "lignes_test.json").exists()):
        _skipped.append("mode bulle (sonde_bulle.py ou ses lignes de test absents)")
        print("  NOTE   sonde absente, controle non mene")
        return
    r = subprocess.run([str(PY), str(sonde)], cwd=BASE, capture_output=True,
                       text=True, encoding="utf-8", errors="replace", timeout=300)
    for ligne in (r.stdout or "").splitlines():
        if ligne.strip().startswith(("OK", "ECHEC")):
            print("  " + ligne.strip())
    check(r.returncode == 0, "tous les controles du mode bulle passent",
          (r.stdout or "").strip().splitlines()[-1] if r.stdout else "sonde muette")


def _console_utf8() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def main() -> int:
    _console_utf8()
    rapide = "--rapide" in sys.argv
    print("Controle complet de DNAreader" + (" (rapide)" if rapide else ""))
    check_python()
    check_js_syntax()
    check_js_loaded()
    check_ids()
    check_ids_uniques()
    check_buttons()
    if rapide:
        _skipped.append("demarrage reel, fenetre et doublon "
                        "(mode --rapide : relance sans l'option avant de livrer)")
    else:
        check_live()

    check_repeint()
    check_lanceur()
    check_modes_imposes()
    if not rapide:
        check_bulle_reelle()

    print()
    for n in _notes:
        print("NOTE :", n)
    if _fails:
        print()
        for f in _fails:
            print("---", f)
        print(f"\n{len(_fails)} controle(s) en echec - NE PAS LIVRER.")
        return 1
    if _skipped:
        print()
        for s in _skipped:
            print("NON TESTE :", s)
        print("\nControles STATIQUES ok, mais incomplets - ne pas conclure "
              "que l'app fonctionne.")
        return 2
    print("Tous les controles passent.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
