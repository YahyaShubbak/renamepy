@echo off
REM ============================================================================
REM  RenamePy - Installation Launcher (Windows)
REM ============================================================================
REM  Double-click this file to install RenamePy.
REM  It launches install.ps1 with the correct execution policy automatically.
REM ============================================================================

cd /d "%~dp0" || (
    echo ERROR: Could not change to script directory.
    pause
    exit /b 1
)

powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\install.ps1"

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Installation finished with errors (exit code: %ERRORLEVEL%).
    echo.
)

pause
