@echo off
setlocal ENABLEDELAYEDEXPANSION
REM ============================================================================
REM  RenamePy - File Renamer GUI Starter
REM ============================================================================
REM Startet die Anwendung mit korrektem Conda Environment

set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%" || (
    echo FEHLER: Projektverzeichnis nicht erreichbar
    pause
    exit /b 1
)

echo ======================================
echo   FILE RENAMER - GUI START
echo   Pfad: %cd%
echo ======================================
echo.

REM Prüfe auf renamepy Conda Environment
set CONDA_ENV="%USERPROFILE%\miniconda3\envs\renamepy"
set CONDA_SCRIPTS="%USERPROFILE%\miniconda3\Scripts"

if exist "%USERPROFILE%\miniconda3\Scripts\activate.bat" (
    echo Aktiviere Conda Environment 'renamepy'...
    call "%USERPROFILE%\miniconda3\Scripts\activate.bat" renamepy
    if errorlevel 1 (
        echo FEHLER: Conda Environment konnte nicht aktiviert werden
        echo Loesung: .\install.ps1
        pause
        exit /b 1
    )
) else (
    echo WARNUNG: Conda nicht gefunden
    echo Installation empfohlen: .\install.bat
)

REM Prüfe Python
python --version >nul 2>nul
if errorlevel 1 (
    echo FEHLER: Python nicht verfuegbar
    pause
    exit /b 1
)

REM Prüfe erforderliche Dateien
if not exist RenameFiles.py (
    echo FEHLER: RenameFiles.py nicht gefunden
    pause
    exit /b 1
)

if not exist modules\ (
    echo FEHLER: modules Ordner nicht gefunden
    pause
    exit /b 1
)

echo Python verfuegbar
echo Starte Anwendung...
echo.

python RenameFiles.py

if errorlevel 1 (
    echo.
    echo FEHLER: Anwendung wurde mit Fehler beendet
    echo Loesung: Fuehre zuerst .\install.ps1 aus
)

pause
exit /b %errorlevel%
set EXITCODE=%ERRORLEVEL%
echo Fertig (Code %EXITCODE%)
if %EXITCODE% neq 0 pause
endlocal
