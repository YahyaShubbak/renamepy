@echo off
REM ============================================================================
REM RenamePy - Robust Installation File (Batch Version for Windows)
REM ============================================================================
REM This file starts the PowerShell installation. If PowerShell is not
REM available, it also offers a manual installation option.
REM ============================================================================

setlocal enabledelayedexpansion

echo.
echo Preparing installation...
echo.

REM Check if PowerShell is available
powershell -Command "exit" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] PowerShell is not available!
    echo.
    echo Manual Installation Option:
    echo 1. Open PowerShell as Administrator
    echo 2. Run this command:
    echo    Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
    echo 3. Then execute:
    echo    .\install.ps1
    echo.
    pause
    exit /b 1
)

REM Start PowerShell with the Install Script
echo [INFO] Starting PowerShell installation...
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" %*

if errorlevel 1 (
    echo.
    echo [ERROR] Installation failed!
    pause
    exit /b 1
)

echo.
echo [SUCCESS] Installation completed!
pause
exit /b 0
