@echo off
setlocal ENABLEDELAYEDEXPANSION
REM ============================================================================
REM  RenamePy - File Renamer GUI Starter
REM ============================================================================
REM Starts the application with the correct Conda environment

set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%" || (
    echo ERROR: Project directory unreachable
    pause
    exit /b 1
)

echo ======================================
echo   FILE RENAMER - GUI START
echo   Path: %cd%
echo ======================================
echo.

REM Check for renamepy Conda environment
set CONDA_ENV="%USERPROFILE%\miniconda3\envs\renamepy"
set CONDA_SCRIPTS="%USERPROFILE%\miniconda3\Scripts"

if exist "%USERPROFILE%\miniconda3\Scripts\activate.bat" (
    echo Activating Conda environment 'renamepy'...
    call "%USERPROFILE%\miniconda3\Scripts\activate.bat" renamepy
    if errorlevel 1 (
        echo ERROR: Could not activate Conda environment
        echo Solution: Run .\install.ps1
        pause
        exit /b 1
    )
) else (
    echo WARNING: Conda not found
    echo Installation recommended: .\install.bat
)

REM Check Python
python --version >nul 2>nul
if errorlevel 1 (
    echo ERROR: Python not available
    pause
    exit /b 1
)

REM Check required files
if not exist RenameFiles.py (
    echo ERROR: RenameFiles.py not found
    pause
    exit /b 1
)

if not exist modules\ (
    echo ERROR: modules folder not found
    pause
    exit /b 1
)

echo Python available
echo Starting application...
echo.

python RenameFiles.py
set EXITCODE=%ERRORLEVEL%

if %EXITCODE% neq 0 (
    echo.
    echo ERROR: Application exited with error code %EXITCODE%
    echo Solution: Run .\install.ps1 first
)

pause
endlocal
exit /b %EXITCODE%
