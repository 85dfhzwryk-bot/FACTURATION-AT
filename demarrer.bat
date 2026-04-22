@echo off
title Facturation AT
echo.
echo  ================================
echo   Facturation AT - Demarrage
echo  ================================
echo.

:: Verifier Python
python --version >nul 2>&1
if errorlevel 1 (
    echo  ERREUR : Python n'est pas installe.
    echo.
    echo  Telechargez Python sur : https://www.python.org/downloads/
    echo  Cochez bien "Add Python to PATH" pendant l'installation.
    echo.
    pause
    exit
)

:: Installer les dependances si besoin
if not exist ".deps_ok" (
    echo  Installation des dependances ^(une seule fois^)...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo  ERREUR lors de l'installation. Verifiez votre connexion internet.
        pause
        exit
    )
    echo. > .deps_ok
    echo  Installation terminee.
    echo.
)

:: Lancer l'application
echo  Lancement de l'application...
echo  Ouvrez votre navigateur sur : http://localhost:8000
echo.
echo  Pour arreter : fermez cette fenetre.
echo.
start "" "http://localhost:8000"
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

pause
