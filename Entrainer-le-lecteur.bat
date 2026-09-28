@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
title Entrainer le lecteur DNAreader

echo.
echo   ENTRAINEMENT DU LECTEUR DNAreader
echo   =================================
echo.

if not exist ".venv-ocr\Scripts\python.exe" (
  echo   [!] L'environnement d'entrainement est absent ^(.venv-ocr^).
  echo       Il porte torch et la carte graphique.
  echo.
  pause
  exit /b 1
)

echo   1. Ce qui a ete recolte pendant tes parties
.venv-ocr\Scripts\python.exe outils\ocr_maison\combien.py
if errorlevel 2 goto fin

set MINUTES=%1
if "%MINUTES%"=="" set MINUTES=60
echo.
echo   2. Entrainement pour %MINUTES% minutes.
echo      Ctrl+C arrete SANS RIEN PERDRE : le meilleur etat est enregistre
echo      au fil de l'eau.
echo.
.venv-ocr\Scripts\python.exe outils\ocr_maison\entraine.py --minutes %MINUTES% --reprend
if errorlevel 1 goto fin

echo.
echo   3. Depot du modele dans l'application
.venv-ocr\Scripts\python.exe outils\ocr_maison\exporte.py
if errorlevel 1 goto fin

echo.
echo   4. Ce que ca donne sur les vraies captures
.venv-ocr\Scripts\python.exe outils\ocr_maison\evalue.py

echo.
echo   Termine. Relance DNAreader : le moteur DNAreader (embarque) utilise
echo   desormais ce modele.

:fin
echo.
pause
