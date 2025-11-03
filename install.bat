@echo off
REM ============================================================================
REM RenamePy - Robuste Installations-Datei (Batch Version fuer Windows)
REM ============================================================================
REM Diese Datei startet die PowerShell Installation, falls PowerShell nicht
REM erreichbar ist, bietet sie auch eine manuelle Installationsoption
REM ============================================================================

setlocal enabledelayedexpansion

echo.
echo Installation wird vorbereitet...
echo.

REM Pruefen ob PowerShell verfuegbar ist
powershell -Command "exit" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] PowerShell ist nicht verfuegbar!
    echo.
    echo Manuelle Installationsoption:
    echo 1. Oeffne PowerShell als Administrator
    echo 2. Fuehre diesen Befehl aus:
    echo    Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
    echo 3. Fuehre dann aus:
    echo    .\install.ps1
    echo.
    pause
    exit /b 1
)

REM Starte PowerShell mit dem Install-Script
echo [INFO] Starte PowerShell Installation...
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" %*

if errorlevel 1 (
    echo.
    echo [ERROR] Installation fehlgeschlagen!
    pause
    exit /b 1
)

echo.
echo [SUCCESS] Installation abgeschlossen!
pause
exit /b 0
