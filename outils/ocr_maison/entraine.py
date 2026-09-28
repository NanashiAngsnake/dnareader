# -*- coding: utf-8 -*-
import argparse
import json
import random
import sys
import time
from pathlib import Path

import torch
import torch.nn as nn
from torch.utils.data import DataLoader, IterableDataset

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI))
import donnees as D
from modele import CRNN, Alphabet

SORTIE = D.SORTIE
SORTIE.mkdir(parents=True, exist_ok=True)
LARGEUR_MAX = 1408


def alphabet_du_projet() -> str:
    f = SORTIE / "alphabet.txt"
    if f.exists():
        return f.read_text(encoding="utf-8")
    expr = D.expressions()
    a = D.alphabet(expr)
    f.write_text(a, encoding="utf-8")
    return a


class Lignes(IterableDataset):
    def __init__(self, alpha: str, graine: int = 0, fige: int = 0,
                 tampon: int = 384, budget: int = 110_000,
                 lot_max: int = 256, lot_min: int = 24,
                 part_vraie: float = 0.33):
        self.alpha = alpha
        self.graine = graine
        self.fige = fige
        self.tampon = max(8, tampon)
        self.budget = budget
        self.lot_max = lot_max
        self.lot_min = lot_min
        self.part_vraie = part_vraie

    def __iter__(self):
        info = torch.utils.data.get_worker_info()
        k = self.graine + (info.id if info else 0) * 1000
        expr = D.expressions()
        jeu = D.lignes_de_jeu()
        phrases = D.Phrases(expr, jeu, self.alpha, k)
        peintre = D.Peintre(k)
        vraies = D.Vraies(k)
        part_vraie = min(self.part_vraie, len(vraies) / 1000.0)
        n = 0
        tampon = []
        while True:
            if self.fige and n >= self.fige:
                return
            if part_vraie and phrases.r.random() < part_vraie:
                v = vraies.une()
                if not v:
                    continue
                brute, t = v
                if any(c not in self.alpha for c in t):
                    continue
                img = D.en_bande(brute)
            else:
                t = phrases.une()
                if not t:
                    continue
                img = D.en_bande(peintre.peins(t))
            if img.width > LARGEUR_MAX:
                continue
            tampon.append((img, t))
            if len(tampon) < self.tampon:
                continue
            tampon.sort(key=lambda x: x[0].width)
            i = 0
            while i < len(tampon):
                lot, large = [], 0
                while i < len(tampon):
                    w = ((tampon[i][0].width + 127) // 128) * 128
                    neuve = max(large, w)
                    if lot and ((len(lot) + 1) * neuve > self.budget
                                or len(lot) >= self.lot_max):
                        break
                    lot.append(tampon[i])
                    large = neuve
                    i += 1
                if not lot:
                    break
                yield lot
                n += len(lot)
            tampon = []


def en_lot(lot, alpha: Alphabet):
    import numpy as np
    imgs = [x[0] for x in lot]
    txts = [x[1] for x in lot]
    W = max(i.width for i in imgs)
    W = ((W + 127) // 128) * 128
    X = np.full((len(imgs), 1, D.HAUTEUR, W), 128, dtype="uint8")
    largeurs = []
    for i, im in enumerate(imgs):
        X[i, 0, :, :im.width] = np.asarray(im, dtype="uint8")
        largeurs.append(CRNN.largeur_sortie(im.width))
    cibles, longueurs = [], []
    for t in txts:
        e = alpha.encode(t)
        cibles += e
        longueurs.append(len(e))
    return (torch.from_numpy(X), torch.tensor(cibles, dtype=torch.long),
            torch.tensor(largeurs, dtype=torch.long),
            torch.tensor(longueurs, dtype=torch.long), txts)


class Ranger:
    def __init__(self, alphabet):
        self.alphabet = alphabet

    def __call__(self, lot):
        return en_lot(lot, self.alphabet)


def distance(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prec = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cour = [i]
        for j, cb in enumerate(b, 1):
            cour.append(min(prec[j] + 1, cour[j - 1] + 1,
                            prec[j - 1] + (ca != cb)))
        prec = cour
    return prec[-1]


def cer(vrais, lus) -> float:
    n = sum(len(v) for v in vrais) or 1
    return sum(distance(v, l) for v, l in zip(vrais, lus)) / n


@torch.no_grad()
def mesure(reseau, lots, alpha, appareil) -> tuple:
    reseau.eval()
    vrais, lus = [], []
    for X, _, largeurs, _, txts in lots:
        X = X.to(appareil, non_blocking=True).float().div_(127.5).sub_(1.0)
        with torch.autocast("cuda", dtype=torch.bfloat16,
                            enabled=(appareil.type == "cuda")):
            y = reseau(X)
        pred = y.float().argmax(2).cpu()
        for i, t in enumerate(txts):
            lus.append(alpha.decode(pred[i, :largeurs[i]].tolist()))
            vrais.append(t)
    reseau.train()
    exact = sum(1 for v, l in zip(vrais, lus) if v == l) / max(1, len(vrais))
    rates = [(v, l) for v, l in zip(vrais, lus) if v != l]
    return cer(vrais, lus), exact, rates[:3]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--minutes", type=float, default=30)
    ap.add_argument("--budget", type=int, default=60_000,
                    help="pixels par lot (lignes x largeur) : c'est LUI qui"
                         " remplit la carte, pas le nombre de lignes")
    ap.add_argument("--ouvriers", type=int, default=10)
    ap.add_argument("--pas-mesure", type=int, default=400)
    ap.add_argument("--pas-affichage", type=int, default=50)
    ap.add_argument("--reprend", action="store_true",
                    help="repart du dernier etat enregistre")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    if torch.cuda.is_available():
        libre, total = torch.cuda.mem_get_info()
        part = max(0.15, min(0.55, (libre * 0.65) / total))
        torch.cuda.set_per_process_memory_fraction(part)
        print(f"carte     : {libre/1e9:.1f} Go libres sur {total/1e9:.1f} · "
              f"on s'autorise {part*total/1e9:.1f} Go")
        plafond = int(libre * 0.65 / 60_000)
        if plafond < a.budget:
            print(f"budget    : ramene de {a.budget//1000}k a {plafond//1000}k "
                  f"pixels par lot, faute de place")
            a.budget = max(20_000, plafond)

    torch.backends.cudnn.benchmark = False
    appareil = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    alpha_txt = alphabet_du_projet()
    alpha = Alphabet(alpha_txt)
    print(f"appareil : {appareil} · alphabet : {len(alpha)} classes "
          f"(dont le blanc)")

    reseau = CRNN(len(alpha)).to(appareil)
    params = sum(p.numel() for p in reseau.parameters())
    print(f"reseau   : {params/1e6:.1f} M parametres")
    vraies = len(D.recoltees())
    print(f"donnees  : lignes fabriquees + {vraies} ligne(s) recoltees "
          f"dans de vrais jeux"
          + ("" if vraies else "  (aucune : voir Reglages > Aider le lecteur)"))

    LR = 6e-4
    CHAUFFE = 500
    opt = torch.optim.AdamW(reseau.parameters(), lr=LR, weight_decay=1e-4)
    ctc = nn.CTCLoss(blank=0, zero_infinity=True)
    etat = SORTIE / "crnn.pt"
    depart = 0
    if a.reprend and etat.exists():
        d = torch.load(etat, map_location=appareil)
        reseau.load_state_dict(d["reseau"])
        opt.load_state_dict(d["opt"])
        depart = d.get("pas", 0)
        print(f"reprise a l'etape {depart}")

    def fabrique_le_flux(budget, graine):
        return DataLoader(
            Lignes(alpha_txt, graine=graine, budget=budget),
            batch_size=None, num_workers=a.ouvriers,
            collate_fn=Ranger(alpha),
            persistent_workers=a.ouvriers > 0, pin_memory=True,
            prefetch_factor=6 if a.ouvriers else None)

    print("préparation du lot de mesure…")
    mesureur = DataLoader(Lignes(alpha_txt, graine=999_000, fige=512,
                                 tampon=128, budget=40_000),
                          batch_size=None, num_workers=0,
                          collate_fn=Ranger(alpha))
    lots_mesure = list(mesureur)
    print(f"  {sum(len(l[4]) for l in lots_mesure)} lignes de contrôle")

    fin = time.time() + a.minutes * 60
    pas = depart
    meilleur = float("inf")
    perte_moy, vus, t0 = 0.0, 0, time.time()
    journal = []
    print(f"\nentrainement pour {a.minutes:.0f} minutes "
          f"(budget {a.budget//1000}k pixels par lot, {a.ouvriers} ouvriers)\n")
    from collections import deque
    lents = deque(maxlen=15)
    train = fabrique_le_flux(a.budget, depart + 1)
    a_refaire = True
    while a_refaire and time.time() < fin:
        a_refaire = False
        for X, cibles, largeurs, longueurs, _ in train:
            depart_pas = time.time()
            X = X.to(appareil, non_blocking=True).float().div_(127.5).sub_(1.0)
            with torch.autocast("cuda", dtype=torch.bfloat16,
                                enabled=(appareil.type == "cuda")):
                y = reseau(X)
            lp = torch.log_softmax(y, dim=2, dtype=torch.float32).permute(1, 0, 2)
            perte = ctc(lp, cibles, largeurs, longueurs)
            opt.zero_grad(set_to_none=True)
            perte.backward()
            nn.utils.clip_grad_norm_(reseau.parameters(), 5.0)
            if pas < CHAUFFE:
                for g in opt.param_groups:
                    g["lr"] = LR * (pas + 1) / CHAUFFE
            opt.step()
            pas += 1
            perte_moy += perte.item()
            vus += X.size(0)
            lent = time.time() - depart_pas > 5
            lents.append(lent)
            if lent:
                print(f"  [lent] le pas {pas} a pris "
                      f"{time.time()-depart_pas:.0f}s sur un lot "
                      f"{tuple(X.shape)} — la carte est pleine", flush=True)
            if sum(lents) >= 4 and a.budget > 24_000:
                a.budget = max(24_000, a.budget // 2)
                print(f"  [place] la carte s'est remplie (un jeu ? un "
                      f"navigateur ?) : lots ramenes a {a.budget//1000}k "
                      f"pixels", flush=True)
                lents.clear()
                a_refaire = True
                break

            if pas % a.pas_affichage == 0:
                dt = time.time() - t0
                print(f"  pas {pas:6d} · perte {perte_moy/a.pas_affichage:6.3f} · "
                      f"{vus/dt:6.0f} lignes/s", flush=True)
                perte_moy, vus, t0 = 0.0, 0, time.time()

            if pas % a.pas_mesure == 0:
                c, exact, apercu = mesure(reseau, lots_mesure, alpha, appareil)
                torch.cuda.empty_cache() if appareil.type == 'cuda' else None
                reste = max(0, fin - time.time()) / 60
                print(f"  --- mesure a {pas} : CER {c*100:5.2f} % · "
                      f"lignes exactes {exact*100:5.1f} % · reste {reste:.0f} min")
                if apercu:
                    print("      ce qu'il rate encore :")
                    for v, l in apercu:
                        print(f"        attendu « {v} »   lu « {l} »")
                else:
                    print("      aucune erreur sur le lot de contrôle")
                journal.append({"pas": pas, "cer": c, "exact": exact})
                (SORTIE / "journal.json").write_text(
                    json.dumps(journal, ensure_ascii=False, indent=1),
                    encoding="utf-8")
                if c < meilleur:
                    meilleur = c
                    torch.save({"reseau": reseau.state_dict(),
                                "opt": opt.state_dict(), "pas": pas,
                                "alphabet": alpha_txt, "cer": c}, etat)
                    print(f"      (enregistre : meilleur CER {c*100:.2f} %)")
            if time.time() > fin:
                break
        if a_refaire:
            del train
            train = fabrique_le_flux(a.budget, pas + 1)

    print(f"\nfini. meilleur CER sur images fabriquees : {meilleur*100:.2f} %")
    print(f"etat : {etat}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
