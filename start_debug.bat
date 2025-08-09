@echo off
setlocal ENABLEDELAYEDEXPANSION
REM ---------------------------------------------------------
REM  FILE RENAMER - DEBUG STARTER
REM  Verbose diagnostics + optional conda env activation
REM ---------------------------------------------------------

set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%" || (echo FEHLER: Script-Verzeichnis nicht erreichbar & pause & exit /b 1)

echo ======================================
echo   FILE RENAMER - DEBUG MODUS
echo   Verzeichnis: %SCRIPT_DIR%
echo ======================================

REM Try to activate conda env if available (optional)
set USE_CONDA=1
if defined CONDA_DEFAULT_ENV (echo (Conda bereits aktiv: %CONDA_DEFAULT_ENV%) ) else (
    if exist "%USERPROFILE%\miniconda3\Scripts\activate.bat" (
        call "%USERPROFILE%\miniconda3\Scripts\activate.bat" || set USE_CONDA=
    ) else if exist "%USERPROFILE%\anaconda3\Scripts\activate.bat" (
        call "%USERPROFILE%\anaconda3\Scripts\activate.bat" || set USE_CONDA=
    ) else (
        set USE_CONDA=
    )
    if defined USE_CONDA (
         call conda activate renamepy 2>nul || echo (Nutze base oder System-Python)
    )
)

where py >nul 2>nul && (set PY_CMD=py) || (set PY_CMD=python)
echo Python Version / Pfad:
%PY_CMD% --version
%PY_CMD% -c "import sys; print(sys.executable)" 2>nul

echo Dateien prüfen...
if not exist RenameFiles.py (echo FEHLER: RenameFiles.py fehlt & pause & exit /b 1)
if not exist modules\ (echo FEHLER: modules Ordner fehlt & dir & pause & exit /b 1)
if not exist modules\__init__.py (echo Hinweis: __init__.py fehlte - wird angelegt & > modules\__init__.py echo # auto-created)

echo Inhaltsübersicht:
dir /b RenameFiles.py
dir /a-d /b modules | find /v "__pycache__"

echo ======================================
echo   START
echo ======================================
set START_TS=%time%
%PY_CMD% RenameFiles.py
set EXITCODE=%ERRORLEVEL%
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
