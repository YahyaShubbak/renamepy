@echo off
setlocal ENABLEDELAYEDEXPANSION
REM ============================================================================
REM  RenamePy - Simple Starter (mit Conda Environment)
REM ============================================================================
REM Startet die Anwendung mit Conda Environment

set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%" || (
    echo FEHLER: Pfad nicht erreichbar
    pause
    exit /b 1
)

echo ======================================
echo   FILE RENAMER (Simple)
echo   Pfad: %SCRIPT_DIR%
echo ======================================
echo.

REM Aktiviere Conda Environment
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
    echo FEHLER: Conda nicht gefunden
    echo Installation erforderlich: .\install.bat
    pause
    exit /b 1
)

REM Prüfe Python Verfügbarkeit
python --version >nul 2>nul
if errorlevel 1 (
    echo FEHLER: Python im Environment nicht verfuegbar
    pause
    exit /b 1
)

REM Prüfe erforderliche Dateien
if not exist RenameFiles.py (
    echo FEHLER: RenameFiles.py fehlt
    pause
    exit /b 1
)

if not exist modules\ (
    echo FEHLER: modules Ordner fehlt
    pause
    exit /b 1
)

if not exist modules\__init__.py (
    echo Hinweis: modules\__init__.py wird erstellt
    > modules\__init__.py echo # auto-created
)

echo Python verfuegbar
echo Starte Anwendung...
echo.

python RenameFiles.py
set EXITCODE=%ERRORLEVEL%

echo.
if %EXITCODE% neq 0 (
    echo FEHLER: Anwendung beendet mit Code %EXITCODE%
    echo Loesung: Fuehre zuerst .\install.ps1 aus
) else (
    echo Beendet erfolgreich
)

pause
endlocal
exit /b %EXITCODE%
