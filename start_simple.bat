@echo off
setlocal ENABLEDELAYEDEXPANSION
REM ============================================================================
REM  RenamePy - Simple Starter (with Conda Environment)
REM ============================================================================
REM Starts the application with Conda environment

set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%" || (
    echo ERROR: Path unreachable
    pause
    exit /b 1
)

echo ======================================
echo   FILE RENAMER (Simple)
echo   Path: %SCRIPT_DIR%
echo ======================================
echo.

REM Activate Conda Environment
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
    echo ERROR: Conda not found
    echo Installation required: .\install.bat
    pause
    exit /b 1
)

REM Check Python availability
python --version >nul 2>nul
if errorlevel 1 (
    echo ERROR: Python not available in environment
    pause
    exit /b 1
)

REM Check required files
if not exist RenameFiles.py (
    echo ERROR: RenameFiles.py is missing
    pause
    exit /b 1
)

if not exist modules\ (
    echo ERROR: modules folder is missing
    pause
    exit /b 1
)

if not exist modules\__init__.py (
    echo Note: Creating modules\__init__.py
    > modules\__init__.py echo # auto-created
)

echo Python available
echo Starting application...
echo.

python RenameFiles.py
set EXITCODE=%ERRORLEVEL%

echo.
if %EXITCODE% neq 0 (
    echo ERROR: Application exited with code %EXITCODE%
    echo Solution: Run .\install.ps1 first
) else (
    echo Finished successfully
)

pause
endlocal
exit /b %EXITCODE%
