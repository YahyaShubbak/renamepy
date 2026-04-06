@echo off
setlocal ENABLEDELAYEDEXPANSION
REM ============================================================================
REM  RenamePy - Application Starter (Windows)
REM ============================================================================
REM  Automatically detects Conda or venv environment and starts the application.
REM  Usage:  start.bat            (normal mode)
REM          start.bat --debug    (verbose debug output)
REM ============================================================================

set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%" || (
    echo ERROR: Project directory unreachable
    pause
    exit /b 1
)

REM Check for --debug flag
set DEBUG_MODE=0
if "%~1"=="--debug" set DEBUG_MODE=1

if %DEBUG_MODE%==1 (
    echo ======================================
    echo   RENAMEPY - DEBUG MODE
    echo   Directory: %SCRIPT_DIR%
    echo ======================================
) else (
    echo ======================================
    echo   RENAMEPY
    echo ======================================
)
echo.

REM ============================================================================
REM  Step 1: Find and activate environment
REM ============================================================================
set ENV_FOUND=0

REM --- Try Conda environments ---
REM Search common Conda/Miniconda/Anaconda locations
set "CONDA_LOCATIONS=%USERPROFILE%\miniconda3 %USERPROFILE%\anaconda3 %USERPROFILE%\Miniconda3 %USERPROFILE%\Anaconda3 %LOCALAPPDATA%\miniconda3 %LOCALAPPDATA%\anaconda3 %PROGRAMDATA%\miniconda3 %PROGRAMDATA%\anaconda3 C:\miniconda3 C:\anaconda3 C:\ProgramData\miniconda3 C:\ProgramData\anaconda3"

for %%D in (%CONDA_LOCATIONS%) do (
    if exist "%%D\Scripts\activate.bat" (
        if exist "%%D\envs\renamepy" (
            echo [INFO] Activating Conda environment 'renamepy' from %%D
            call "%%D\Scripts\activate.bat" renamepy
            if not errorlevel 1 (
                set ENV_FOUND=1
                goto :env_ready
            )
        )
    )
)

REM Try conda from PATH
where conda >nul 2>nul
if not errorlevel 1 (
    conda activate renamepy >nul 2>nul
    if not errorlevel 1 (
        echo [INFO] Activated Conda environment 'renamepy' from PATH
        set ENV_FOUND=1
        goto :env_ready
    )
)

REM --- Try venv environments ---
REM Check for .venv folder (created by install.sh/install.ps1 venv mode)
if exist "%SCRIPT_DIR%.venv\Scripts\activate.bat" (
    echo [INFO] Activating venv from .venv\
    call "%SCRIPT_DIR%.venv\Scripts\activate.bat"
    set ENV_FOUND=1
    goto :env_ready
)

REM Check for renamepy folder (created by install.ps1 venv mode)
if exist "%SCRIPT_DIR%renamepy\Scripts\activate.bat" (
    echo [INFO] Activating venv from renamepy\
    call "%SCRIPT_DIR%renamepy\Scripts\activate.bat"
    set ENV_FOUND=1
    goto :env_ready
)

REM No environment found — try system Python
echo [WARNING] No Conda or venv environment found.
echo [WARNING] Trying system Python. Run install.ps1 first for best results.

:env_ready

REM ============================================================================
REM  Step 2: Find Python
REM ============================================================================
set PYTHON_CMD=

REM Try 'python' first
python --version >nul 2>nul
if not errorlevel 1 (
    set PYTHON_CMD=python
    goto :python_found
)

REM Try 'python3'
python3 --version >nul 2>nul
if not errorlevel 1 (
    set PYTHON_CMD=python3
    goto :python_found
)

REM Try Python Launcher
py -3 --version >nul 2>nul
if not errorlevel 1 (
    set PYTHON_CMD=py -3
    goto :python_found
)

echo.
echo ERROR: Python not found!
echo Please install Python 3.10+ from https://www.python.org/downloads/
echo Make sure to check "Add Python to PATH" during installation.
pause
exit /b 1

:python_found
if %DEBUG_MODE%==1 (
    echo.
    echo [DEBUG] Python command: %PYTHON_CMD%
    %PYTHON_CMD% --version
    %PYTHON_CMD% -c "import sys; print('Python path:', sys.executable)"
    echo.
    echo [DEBUG] Checking modules...
    %PYTHON_CMD% -c "import PyQt6; print('  PyQt6: OK')" 2>nul || echo   PyQt6: NOT FOUND
    %PYTHON_CMD% -c "import exiftool; print('  PyExifTool: OK')" 2>nul || echo   PyExifTool: NOT FOUND
    echo.
)

REM ============================================================================
REM  Step 3: Check required files
REM ============================================================================
if not exist RenameFiles.py (
    echo ERROR: RenameFiles.py not found in %SCRIPT_DIR%
    pause
    exit /b 1
)

if not exist modules\ (
    echo ERROR: modules folder not found
    pause
    exit /b 1
)

REM ============================================================================
REM  Step 4: Start application
REM ============================================================================
if %DEBUG_MODE%==1 (
    echo [DEBUG] Starting application...
    echo ======================================
    set START_TS=%time%
)

%PYTHON_CMD% RenameFiles.py
set EXITCODE=%ERRORLEVEL%

if %DEBUG_MODE%==1 (
    echo.
    echo ======================================
    echo   DEBUG INFO
    echo ======================================
    echo Start time: %START_TS%
    echo End time:   %time%
    echo Exit code:  %EXITCODE%
    echo ======================================
)

if %EXITCODE% neq 0 (
    echo.
    echo ERROR: Application exited with error code %EXITCODE%
    echo Tip: Run install.ps1 to set up the environment.
    pause
)

endlocal
exit /b %EXITCODE%
