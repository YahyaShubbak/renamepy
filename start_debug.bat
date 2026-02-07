@echo off
setlocal ENABLEDELAYEDEXPANSION
REM ============================================================================
REM  RenamePy - DEBUG STARTER
REM ============================================================================
REM Startet die Anwendung mit Debugging und Conda Environment

set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%" || (
    echo FEHLER: Skript-Verzeichnis nicht erreichbar
    pause
    exit /b 1
)

echo ======================================
echo   FILE RENAMER - DEBUG MODUS
echo   Verzeichnis: %SCRIPT_DIR%
echo ======================================
echo.

REM Aktiviere Conda Environment
if exist "%USERPROFILE%\miniconda3\Scripts\activate.bat" (
    echo [1] Aktiviere Conda Environment 'renamepy'...
    call "%USERPROFILE%\miniconda3\Scripts\activate.bat" renamepy
    if errorlevel 1 (
        echo FEHLER: Conda Environment konnte nicht aktiviert werden
        pause
        exit /b 1
    )
    echo [OK] Conda Environment aktiviert
) else (
    echo FEHLER: Conda nicht gefunden
    echo Installation erforderlich: .\install.bat
    pause
    exit /b 1
)

echo.
echo [2] Python Verzeichnis und Version pruefen...
python --version
python -c "import sys; print('Python Pfad: ' + sys.executable)"

echo.
echo [3] Dateien pruefen...
if not exist RenameFiles.py (
    echo FEHLER: RenameFiles.py fehlt
    pause
    exit /b 1
)
if not exist modules\ (
    echo FEHLER: modules Ordner fehlt
    dir
    pause
    exit /b 1
)
if not exist modules\__init__.py (
    echo Hinweis: modules\__init__.py wird erstellt
    > modules\__init__.py echo # auto-created
)

echo [OK] Alle Dateien vorhanden

echo.
echo [4] Pruefen auf erforderliche Module...
python -c "import PyQt6; print('PyQt6: OK')" 2>nul || echo "PyQt6: FEHLER"
python -c "import exiftool; print('PyExifTool: OK')" 2>nul || echo "PyExifTool: FEHLER"

echo.
echo ======================================
echo   START ANWENDUNG
echo ======================================
set START_TS=%time%
python RenameFiles.py
set EXITCODE=%ERRORLEVEL%
set END_TS=%time%

echo.
echo ======================================
echo   DEBUG INFO
echo ======================================
echo Startzeit: %START_TS%
echo Endzeit:   %END_TS%
echo Exit Code: %EXITCODE%
if %EXITCODE% neq 0 (
    echo Status: FEHLER
    echo Loesung: Fuehre zuerst .\install.ps1 aus
) else (
    echo Status: OK
)
echo ======================================

pause
endlocal
exit /b %EXITCODE%
echo ======================================
echo   ENDE (Code %EXITCODE%)
echo   Startzeit : %START_TS%
echo   Endzeit   : %time%
echo ======================================

if %EXITCODE% neq 0 (
    echo Stacktrace (falls vorhanden):
    REM (Trace wird bereits im Programm ausgegeben)
)
echo Druecken Sie eine Taste zum Schliessen...
pause
endlocal
