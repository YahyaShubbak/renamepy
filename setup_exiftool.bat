@echo off
REM ============================================================================
REM  ExifTool Setup - Batch Wrapper
REM ============================================================================
REM Launches the PowerShell setup script for ExifTool

setlocal enabledelayedexpansion

echo.
echo ============================================================
echo   ExifTool Setup for RenamePy
echo ============================================================
echo.

REM Check PowerShell availability
powershell -Command "exit" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] PowerShell is not available!
    pause
    exit /b 1
)

REM Launch PowerShell setup script
echo [INFO] Starting PowerShell setup script...
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup_exiftool.ps1" %*

if errorlevel 1 (
    echo.
    echo [ERROR] ExifTool setup failed!
    pause
    exit /b 1
)

echo.
echo [OK] ExifTool setup completed!
pause
exit /b 0
