# DNAreader

Real-time Japanese reader for video games. It captures the screen, reads the
Japanese text with OCR and shows readings and dictionary entries in a small
overlay next to the game. Works offline once installed.

Download: [latest Windows installer](https://github.com/NanashiAngsnake/dnareader-releases/releases/latest)

## Features

- Screen capture OCR with ONNX models (RapidOCR), plus detection and recognition
  models trained for game text (`modeles/`, training code in `outils/ocr_maison/`).
- Optional high-accuracy engine based on manga-ocr.
- Word segmentation (fugashi) and JMdict lookup from a local SQLite database.
- Vocabulary list with Anki export (genanki).
- Overlay window (pywebview) with a windowed mode for low-end machines.
- Auto-update from GitHub releases, with SHA-256 verification of the installer.
- License server with HMAC-signed responses and a 14-day offline grace period,
  and a Discord bot that issues and manages license keys.

## Stack

Python, FastAPI / uvicorn, pywebview, HTML / JavaScript, mss, ONNX Runtime,
RapidOCR, manga-ocr, fugashi, SQLite, genanki, PyInstaller, Inno Setup.

## Run from source

```bash
pip install -r requirements-extra.txt
python lancer.pyw
```

Dictionaries are in `dicts/`, models in `modeles/`. Build the installer with
`python outils/construire.py`.

## Notes

Third-party data and models are listed with their licenses in
[NOTICE.md](NOTICE.md). JMdict is CC BY-SA 4.0 (EDRDG). Identifiers and UI
text are in French.

## License

All rights reserved. Published as a portfolio for viewing and evaluation only;
reuse or redistribution is not permitted. See [LICENSE](LICENSE).
