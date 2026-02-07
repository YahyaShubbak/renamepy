@echo off
setlocal ENABLEDELAYEDEXPANSION
REM ============================================================================
REM  RenamePy - DEBUG STARTER
REM ============================================================================
REM Starts the application with debugging and Conda environment

set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%" || (
    echo ERROR: Script directory unreachable
    pause
    exit /b 1
)

echo ======================================
echo   FILE RENAMER - DEBUG MODE
echo   Directory: %SCRIPT_DIR%
echo ======================================
echo.

REM Activate Conda Environment
if exist "%USERPROFILE%\miniconda3\Scripts\activate.bat" (
    echo [1] Activating Conda environment 'renamepy'...
    call "%USERPROFILE%\miniconda3\Scripts\activate.bat" renamepy
    if errorlevel 1 (
        echo ERROR: Could not activate Conda environment
        pause
        exit /b 1
    )
    echo [OK] Conda environment activated
) else (
    echo ERROR: Conda not found
    echo Installation required: .\install.bat
    pause
    exit /b 1
)

echo.
echo [2] Checking Python directory and version...
python --version
python -c "import sys; print('Python path: ' + sys.executable)"

echo.
echo [3] Checking files...
if not exist RenameFiles.py (
    echo ERROR: RenameFiles.py is missing
    pause
    exit /b 1
)
if not exist modules\ (
    echo ERROR: modules folder is missing
    dir
    pause
    exit /b 1
)
if not exist modules\__init__.py (
    echo Note: Creating modules\__init__.py
    > modules\__init__.py echo # auto-created
)

echo [OK] All files present

echo.
echo [4] Checking required modules...
python -c "import PyQt6; print('PyQt6: OK')" 2>nul || echo "PyQt6: ERROR"
python -c "import exiftool; print('PyExifTool: OK')" 2>nul || echo "PyExifTool: ERROR"

echo.
echo ======================================
echo   START APPLICATION
echo ======================================
set START_TS=%time%
python RenameFiles.py
set EXITCODE=%ERRORLEVEL%
set END_TS=%time%

echo.
echo ======================================
echo   DEBUG INFO
echo ======================================
echo Start time: %START_TS%
echo End time:   %END_TS%
echo Exit code:  %EXITCODE%
if %EXITCODE% neq 0 (
    echo Status: ERROR
    echo Solution: Run .\install.ps1 first
) else (
    echo Status: OK
)
echo ======================================

pause
endlocal
exit /b %EXITCODE%
