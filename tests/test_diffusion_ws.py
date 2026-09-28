# -*- coding: utf-8 -*-
import asyncio, os, sys, time
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "app"))
os.chdir(RACINE)

import server

import sys
sys.stdout.reconfigure(encoding="utf-8")


class PageMuette:
    def __init__(self):
        self.fermee = False

    async def send_json(self, msg):
        await asyncio.sleep(3600)

    async def close(self):
        self.fermee = True


class PageVivante:
    def __init__(self):
        self.recu = []

    async def send_json(self, msg):
        self.recu.append(msg)

    async def close(self):
        pass


async def main():
    muette, vivante = PageMuette(), PageVivante()
    server._ws_clients.clear()
    server._ws_clients.update({muette, vivante})

    debut = time.perf_counter()
    await server._broadcast({"type": "reglage", "cle": "jeu", "valeur": "TEST"})
    duree = time.perf_counter() - debut

    echecs = []
    if duree > 2.0:
        echecs.append(f"la diffusion a pris {duree:.1f} s (attendu : moins de 2)")
    if vivante.recu != [{"type": "reglage", "cle": "jeu", "valeur": "TEST"}]:
        echecs.append(f"la page vivante n'a pas recu le message : {vivante.recu}")
    if muette in server._ws_clients:
        echecs.append("la page muette n'a pas ete retiree")
    if not muette.fermee:
        echecs.append("la page muette n'a pas ete fermee")

    print(f"diffusion en {duree:.2f} s · page vivante servie : "
          f"{len(vivante.recu)} message(s) · page muette retiree : "
          f"{muette not in server._ws_clients}")
    if echecs:
        for e in echecs:
            print("  ECHEC :", e)
        return 1
    print("OK : une page muette ne fige plus l'application")
    return 0


raise SystemExit(asyncio.run(main()))
