@echo off
setlocal ENABLEDELAYEDEXPANSION
REM ---------------------------------------------------------
REM  File Renamer - Simple Starter (no conda activation)
REM  Uses the Python first on PATH. Makes script location agnostic.
REM ---------------------------------------------------------

REM Resolve script directory (works even if started via shortcut)
set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%" || (echo FEHLER: Pfad nicht erreichbar & pause & exit /b 1)

echo ======================================
echo   FILE RENAMER (Simple)
echo   Pfad: %SCRIPT_DIR%
echo ======================================

REM Prefer py launcher if available (Windows standard)
where py >nul 2>nul && (set PY_CMD=py) || (set PY_CMD=python)

%PY_CMD% --version || (echo FEHLER: Python nicht gefunden & pause & exit /b 1)

if not exist RenameFiles.py (
    echo FEHLER: RenameFiles.py fehlt im Verzeichnis %SCRIPT_DIR%
    pause & exit /b 1
)
if not exist modules\__init__.py (
    echo WARNUNG: modules\__init__.py fehlt (erstellt automatisch)
    > modules\__init__.py echo # auto-created
)

echo Starte Anwendung...
%PY_CMD% RenameFiles.py
set EXITCODE=%ERRORLEVEL%
echo.
echo Beendet mit Code %EXITCODE%
if %EXITCODE% neq 0 pause
endlocal
