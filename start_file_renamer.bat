@echo off
setlocal ENABLEDELAYEDEXPANSION
REM ---------------------------------------------------------
REM  File Renamer Starter (mit optionalem Conda Env)
REM ---------------------------------------------------------

set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%" || (echo FEHLER: Projektverzeichnis nicht erreichbar & pause & exit /b 1)
echo Projektverzeichnis: %cd%

REM Optional: Conda aktivieren (falls vorhanden)
set _TRY_CONDA=
for %%A in ("%USERPROFILE%\miniconda3","%USERPROFILE%\anaconda3","C:\ProgramData\miniconda3") do (
    if exist %%A\Scripts\activate.bat set _TRY_CONDA=%%A\Scripts\activate.bat
)
if defined _TRY_CONDA (
    call "%_TRY_CONDA%" && (call conda activate renamepy 2>nul || echo (Nutze base/env nicht gefunden))
) else (
    echo (Conda nicht gefunden - nutze System-Python)
)

where py >nul 2>nul && (set PY_CMD=py) || (set PY_CMD=python)
%PY_CMD% --version || (echo FEHLER: Python nicht gefunden & pause & exit /b 1)

if not exist RenameFiles.py (echo FEHLER: RenameFiles.py fehlt & pause & exit /b 1)
if not exist modules\ (echo FEHLER: modules Ordner fehlt & pause & exit /b 1)
if not exist modules\__init__.py (echo Hinweis: __init__.py fehlte - wird angelegt & > modules\__init__.py echo # auto-created)

echo Starte GUI...
%PY_CMD% RenameFiles.py
set EXITCODE=%ERRORLEVEL%
echo Fertig (Code %EXITCODE%)
if %EXITCODE% neq 0 pause
endlocal
