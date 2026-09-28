# Composants tiers

DNAreader est distribué avec des données et des modèles tiers. Ce fichier
accompagne toute copie de l'application.

## JMdict

- Source : [JMdict / EDICT](https://www.edrdg.org/jmdict/j_jmdict.html),
  Electronic Dictionary Research and Development Group (EDRDG), Université Monash.
- Fichiers au format Yomitan issus de [jmdict-yomitan](https://github.com/yomidevs/jmdict-yomitan)
  (`JMdict_english`, `JMdict_french`).
- Licence : [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/).

Les définitions ne sont pas modifiées : elles sont converties dans une base
SQLite. L'EDRDG est aussi cité dans l'écran « À propos » de l'application.

## Modèle de reconnaissance ONNX

- Fichiers : `modeles/japan_rec.onnx`, `modeles/japan_dict.txt`.
- Source : PaddleOCR / RapidOCR (PP-OCR, modèle de reconnaissance japonais).
- Licence : Apache License 2.0.

## manga-ocr (facultatif)

- Source : [manga-ocr](https://github.com/kha-white/manga-ocr), Maciej Budyś.
- Licence : Apache License 2.0.
- Non livré : téléchargé depuis Hugging Face au premier usage du mode « Haute précision ».

## Traduction hors ligne (facultatif)

Modèle de traduction japonais vers français, téléchargé à la demande via
`transformers` (Hugging Face). Non livré avec l'application.

## MeCab / UniDic

- Bibliothèques : `fugashi` (MIT), `unidic-lite`.
- Dictionnaire UniDic : licence BSD à trois clauses, Université de Tokyo / NINJAL.

## Autres bibliothèques

Windows OCR (`winrt`), FastAPI, uvicorn, Pillow, pywebview, onnxruntime et
OpenCV, sous licences MIT, BSD ou Apache 2.0. Leurs textes de licence sont
fournis avec leurs paquets.

## Contenu des jeux

Le texte des jeux appartient à leurs éditeurs. L'application le lit à l'écran
sans le conserver. La base de corrections partagées ne contient que des paires
« lecture erronée / lecture correcte » liées à un jeu, pas de dialogues.
