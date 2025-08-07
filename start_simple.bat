@echo off
REM File Renamer - Einfache Version ohne Conda
echo File Renamer Starter (Einfach)

REM Change to project directory
cd /d "C:\Users\yshub\Documents\GitHub\renamepy"

REM Check if files exist
if not exist "RenameFiles.py" (
    echo FEHLER: RenameFiles.py nicht gefunden!
    pause
    exit /b 1
)

REM Show Python version
echo Python Version:
python --version

REM Start the application
echo Starte File Renamer...
python RenameFiles.py

REM Keep window open on error
if %errorlevel% neq 0 (
    echo Fehler beim Starten!
    pause
)
