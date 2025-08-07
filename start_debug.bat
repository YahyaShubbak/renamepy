@echo off
REM File Renamer - Debug Version (hält Konsole offen)
echo ===================================
echo    FILE RENAMER - DEBUG MODUS
echo ===================================

REM Change to project directory
echo Wechsle zu: C:\Users\yshub\Documents\GitHub\renamepy
cd /d "C:\Users\yshub\Documents\GitHub\renamepy"

REM Check if we're in the right directory
echo Aktuelles Verzeichnis: %cd%

REM Check if files exist
if not exist "RenameFiles.py" (
    echo.
    echo FEHLER: RenameFiles.py nicht gefunden!
    echo Bitte überprüfen Sie den Pfad.
    echo.
    pause
    exit /b 1
)

if not exist "modules\" (
    echo.
    echo FEHLER: modules Verzeichnis nicht gefunden!
    echo.
    dir
    echo.
    pause
    exit /b 1
)

REM Show Python info
echo.
echo Python Informationen:
python --version
echo Python Pfad: 
python -c "import sys; print(sys.executable)"

REM List important files
echo.
echo Wichtige Dateien:
dir RenameFiles.py
dir modules\

REM Start the application
echo.
echo ===================================
echo    STARTE FILE RENAMER
echo ===================================
echo.

python RenameFiles.py

echo.
echo ===================================
echo    ANWENDUNG BEENDET
echo ===================================
echo Exit Code: %errorlevel%

REM Always keep window open for debugging
echo.
echo Konsole bleibt für Debugging offen...
pause
