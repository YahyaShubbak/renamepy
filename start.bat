@echo off
setlocal
REM ============================================================================
REM  RenamePy - Application Starter (Windows)
REM ============================================================================
REM  Automatically detects Conda or venv environment and starts the application.
REM  Usage:  start.bat            (normal mode, no console window for the app)
REM          start.bat --debug    (verbose debug output, app runs in this console)
REM
REM  Keep this file ASCII-only with CRLF line endings (see .gitattributes):
REM  cmd.exe mis-parses labels/goto in batch files with LF-only line endings.
REM ============================================================================

set "SCRIPT_DIR=%~dp0"
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
    echo   Directory: "%SCRIPT_DIR%"
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

REM --- venv environments created by install.ps1 / install.sh ---
if exist "%SCRIPT_DIR%renamepy\Scripts\activate.bat" (
    echo [INFO] Activating venv from renamepy\
    call "%SCRIPT_DIR%renamepy\Scripts\activate.bat"
    goto :env_ready
)
if exist "%SCRIPT_DIR%.venv\Scripts\activate.bat" (
    echo [INFO] Activating venv from .venv\
    call "%SCRIPT_DIR%.venv\Scripts\activate.bat"
    goto :env_ready
)

REM --- Conda environment 'renamepy' in common locations ---
REM Each location is quoted separately so that user names with spaces
REM ("C:\Users\Max Mustermann") are not split into several items.
for %%D in (
    "%USERPROFILE%\miniconda3"
    "%USERPROFILE%\anaconda3"
    "%USERPROFILE%\Miniconda3"
    "%USERPROFILE%\Anaconda3"
    "%USERPROFILE%\miniforge3"
    "%LOCALAPPDATA%\miniconda3"
    "%LOCALAPPDATA%\anaconda3"
    "%PROGRAMDATA%\miniconda3"
    "%PROGRAMDATA%\anaconda3"
    "C:\miniconda3"
    "C:\anaconda3"
) do (
    if exist "%%~D\Scripts\activate.bat" if exist "%%~D\envs\renamepy" (
        echo [INFO] Activating Conda environment 'renamepy' from %%~D
        call "%%~D\Scripts\activate.bat" renamepy
        if not errorlevel 1 goto :env_ready
    )
)

REM --- conda from PATH ---
REM "call" is required: conda is a .bat file, and invoking a batch file
REM without "call" never returns to this script.
where conda >nul 2>nul
if not errorlevel 1 (
    call conda activate renamepy >nul 2>nul
    if not errorlevel 1 (
        echo [INFO] Activated Conda environment 'renamepy' from PATH
        goto :env_ready
    )
)

REM No environment found - try system Python
echo [WARNING] No Conda or venv environment found.
echo [WARNING] Trying system Python. Run install.bat first for best results.

:env_ready

REM ============================================================================
REM  Step 2: Find Python
REM ============================================================================
set "PYTHON_CMD="
set "PYTHONW_CMD="

python --version >nul 2>nul
if not errorlevel 1 (
    set "PYTHON_CMD=python"
    set "PYTHONW_CMD=pythonw"
    goto :python_found
)

python3 --version >nul 2>nul
if not errorlevel 1 (
    set "PYTHON_CMD=python3"
    goto :python_found
)

py -3 --version >nul 2>nul
if not errorlevel 1 (
    set "PYTHON_CMD=py -3"
    set "PYTHONW_CMD=pyw -3"
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
REM  Step 3: Check required files and packages
REM ============================================================================
if not exist RenameFiles.py (
    echo ERROR: RenameFiles.py not found in "%SCRIPT_DIR%"
    pause
    exit /b 1
)

if not exist modules\ (
    echo ERROR: modules folder not found
    pause
    exit /b 1
)

REM Check imports here, in the console: without a console window (pythonw)
REM a missing package would otherwise fail silently.
%PYTHON_CMD% -c "import PyQt6.QtWidgets" >nul 2>nul
if errorlevel 1 (
    echo ERROR: PyQt6 is not installed for %PYTHON_CMD%.
    echo Run install.bat to set up the environment.
    pause
    exit /b 1
)

REM ============================================================================
REM  Step 4: Start application
REM ============================================================================
if %DEBUG_MODE%==1 goto :start_debug
if not defined PYTHONW_CMD goto :start_debug

REM Normal mode: start without a console window and close this one.
start "" %PYTHONW_CMD% RenameFiles.py
endlocal
exit /b 0

:start_debug
if %DEBUG_MODE%==1 (
    echo [DEBUG] Starting application...
    echo ======================================
)
set "START_TS=%time%"

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

if not "%EXITCODE%"=="0" (
    echo.
    echo ERROR: Application exited with error code %EXITCODE%
    echo Tip: Run install.bat to set up the environment.
    pause
)

endlocal & exit /b %EXITCODE%
