@echo off
REM File Renamer Starter - Korrigierte Version
echo Starting File Renamer...

REM Change to your project directory
echo Wechsle zu Projektverzeichnis...
cd /d "C:\Users\yshub\Documents\GitHub\renamepy"
if %errorlevel% neq 0 (
    echo FEHLER: Projektverzeichnis nicht gefunden!
    pause
    exit /b 1
)
echo Projektverzeichnis: %cd%

REM Initialize conda for this shell
echo Initialisiere Conda...
CALL "%USERPROFILE%\miniconda3\Scripts\activate.bat"
if %errorlevel% neq 0 (
    echo FEHLER: Conda nicht gefunden! Versuche alternative Pfade...
    REM Alternative Pfade für Conda
    if exist "%USERPROFILE%\anaconda3\Scripts\activate.bat" (
        CALL "%USERPROFILE%\anaconda3\Scripts\activate.bat"
    ) else if exist "C:\ProgramData\miniconda3\Scripts\activate.bat" (
        CALL "C:\ProgramData\miniconda3\Scripts\activate.bat"
    ) else (
        echo WARNUNG: Conda nicht gefunden, verwende System-Python
        goto skip_conda
    )
)

REM Activate your conda environment
echo Aktiviere renamepy Environment...
CALL conda activate renamepy
if %errorlevel% neq 0 (
    echo WARNUNG: Environment 'renamepy' nicht gefunden, verwende base
)

:skip_conda
REM Show current environment
echo Aktuelle Python-Version:
python --version
echo.

REM Check if required files exist
if not exist "RenameFiles.py" (
    echo FEHLER: RenameFiles.py nicht gefunden!
    pause
    exit /b 1
)

if not exist "modules\" (
    echo FEHLER: modules Verzeichnis nicht gefunden!
    pause
    exit /b 1
)

REM Run your GUI program
echo Starte File Renamer GUI...
python RenameFiles.py

REM Keep window open if there was an error
if %errorlevel% neq 0 (
    echo.
    echo FEHLER beim Starten der Anwendung!
    echo Fehlercode: %errorlevel%
    pause
)

echo.
echo Anwendung beendet.
REM Optionally keep window open
REM pause
