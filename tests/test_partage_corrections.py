# -*- coding: utf-8 -*-
import json
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "app"))
sys.stdout.reconfigure(encoding="utf-8")

import uvicorn

PORT = 8815
db = RACINE / "tests" / "tmp_sync.db"
if db.exists():
    db.unlink()

import serveur_sync
serveur_sync.DB = db

threading.Thread(target=lambda: uvicorn.run(serveur_sync.app, host="127.0.0.1",
                                            port=PORT, log_level="error"),
                 daemon=True).start()
for _ in range(60):
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{PORT}/sante", timeout=1).read()
        break
    except Exception:
        time.sleep(0.4)

S = f"http://127.0.0.1:{PORT}"


def poste(route, corps):
    req = urllib.request.Request(S + route, data=json.dumps(corps).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=6) as r:
        return json.loads(r.read().decode())


def lis(route, **q):
    from urllib.parse import urlencode
    with urllib.request.urlopen(S + route + "?" + urlencode(q), timeout=6) as r:
        return json.loads(r.read().decode())


def compte(nom):
    r = poste("/inscription", {"identifiant": nom, "preuve": "x" * 40 + nom})
    return r["jeton"]


ok = 0
ko = 0


def check(cond, titre, detail=""):
    global ok, ko
    print(("  OK   " if cond else "  ECHEC ") + titre + (" — " + detail if detail else ""))
    if cond:
        ok += 1
    else:
        ko += 1


print("Verification des corrections partagees\n")

a, b, c = compte("alice"), compte("bob"), compte("chloe")
JEU = "FINAL FANTASY VII REMAKE"
FAUX, JUSTE = "セプンスヘプン", "セブンスヘブン"

r = poste("/correction", {"jeton": a, "jeu": JEU, "faux": FAUX, "juste": JUSTE,
                          "contexte": "chapitre 3", "seconde": 512.0})
check(r.get("ok") and not r.get("confirmee"),
      "une seule proposition ne s'applique pas",
      f"{r.get('pour')} voix, il en manque {r.get('manque')}")

conf = lis("/corrections", jeu=JEU)
check(conf["corrections"] == [], "elle n'est pas servie comme confirmee")
att = lis("/corrections", jeu=JEU, attente="1")
check(len(att["corrections"]) == 1, "elle est visible comme proposition")

for _ in range(3):
    time.sleep(2.1)
    r = poste("/correction", {"jeton": a, "jeu": JEU, "faux": FAUX, "juste": JUSTE})
check(r.get("pour") == 1,
      "renvoyer la meme correction ne la confirme pas",
      f"toujours {r.get('pour')} voix apres 4 envois du meme compte")

time.sleep(2.1)
r = poste("/correction", {"jeton": b, "jeu": JEU, "faux": FAUX, "juste": JUSTE})
check(r.get("confirmee") is True,
      "deux comptes distincts la confirment", f"{r.get('pour')} voix")
conf = lis("/corrections", jeu=JEU)
check(len(conf["corrections"]) == 1, "elle est desormais servie aux autres")

time.sleep(0.2)
poste("/correction/contester", {"jeton": c, "jeu": JEU, "faux": FAUX, "juste": JUSTE})
r = poste("/correction/contester", {"jeton": a, "jeu": JEU, "faux": FAUX, "juste": JUSTE})
check(r.get("confirmee") is False,
      "assez de contestations la retirent", f"{r.get('contre')} contre")

time.sleep(2.1)
r = poste("/correction", {"jeton": a, "jeu": JEU, "faux": "テスト", "juste": "hello"})
check(not r.get("ok"), "une correction sans japonais est refusee", r.get("error", ""))
time.sleep(2.1)
r = poste("/correction", {"jeton": a, "jeu": JEU, "faux": "テスト", "juste": "テスト"})
check(not r.get("ok"), "une correction identique est refusee", r.get("error", ""))
r = poste("/correction", {"jeton": "faux-jeton", "jeu": JEU, "faux": "テスト",
                          "juste": "試験"})
check(not r.get("ok"), "sans compte valide, rien n'est accepte", r.get("error", ""))

att = lis("/corrections", jeu=JEU, attente="1")
avec = [x for x in att["corrections"] if x["faux"] == FAUX]
check(bool(avec) and avec[0].get("seconde") == 512.0
      and avec[0].get("contexte") == "chapitre 3",
      "le moment et le contexte sont conserves",
      f"seconde={avec[0].get('seconde') if avec else '?'}")

print(f"\n{ok} controle(s) OK, {ko} echec(s)")
if db.exists():
    try:
        db.unlink()
    except Exception:
        pass
raise SystemExit(1 if ko else 0)
