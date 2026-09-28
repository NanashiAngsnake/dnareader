# -*- coding: utf-8 -*-
import torch
import torch.nn as nn


class Alphabet:
    def __init__(self, caracteres: str):
        self.caracteres = caracteres
        self.vers_i = {c: i + 1 for i, c in enumerate(caracteres)}
        self.vers_c = {i + 1: c for i, c in enumerate(caracteres)}

    def __len__(self):
        return len(self.caracteres) + 1

    def encode(self, texte: str) -> list:
        return [self.vers_i[c] for c in texte if c in self.vers_i]

    def decode(self, indices) -> str:
        out, precedent = [], -1
        for i in indices:
            i = int(i)
            if i != precedent and i != 0:
                out.append(self.vers_c.get(i, ""))
            precedent = i
        return "".join(out)


class CRNN(nn.Module):
    def __init__(self, n_classes: int, hauteur: int = 48, canaux: int = 1):
        super().__init__()
        self.hauteur = hauteur
        c = canaux
        self.conv = nn.Sequential(
            nn.Conv2d(c, 64, 3, 1, 1), nn.BatchNorm2d(64), nn.ReLU(True),
            nn.MaxPool2d(2, 2),
            nn.Conv2d(64, 128, 3, 1, 1), nn.BatchNorm2d(128), nn.ReLU(True),
            nn.MaxPool2d(2, 2),
            nn.Conv2d(128, 256, 3, 1, 1), nn.BatchNorm2d(256), nn.ReLU(True),
            nn.Conv2d(256, 256, 3, 1, 1), nn.BatchNorm2d(256), nn.ReLU(True),
            nn.MaxPool2d(2, 2),
            nn.Conv2d(256, 384, 3, 1, 1), nn.BatchNorm2d(384), nn.ReLU(True),
            nn.MaxPool2d((2, 1), (2, 1)),
            nn.Conv2d(384, 384, (3, 3), 1, (0, 1)),
            nn.BatchNorm2d(384), nn.ReLU(True),
        )
        self.rnn = nn.LSTM(384, 256, num_layers=2, bidirectional=True,
                           batch_first=True, dropout=0.1)
        self.sortie = nn.Linear(512, n_classes)

    def forward(self, x):
        h = self.conv(x)
        assert h.size(2) == 1, f"hauteur residuelle {h.size(2)}, attendu 1"
        h = h.squeeze(2).permute(0, 2, 1)
        h, _ = self.rnn(h)
        return self.sortie(h)

    @staticmethod
    def largeur_sortie(w: int) -> int:
        return max(1, w // 8)
