@echo off
REM ============================================================================
REM  ExifTool Setup - Batch Wrapper
REM ============================================================================
REM Startet das PowerShell Setup-Skript für ExifTool

setlocal enabledelayedexpansion

echo.
echo ============================================================
echo   ExifTool Setup fuer RenamePy
echo ============================================================
echo.

REM Prueche PowerShell
powershell -Command "exit" >nul 2>&1
if errorlevel 1 (
    echo [FEHLER] PowerShell ist nicht verfuegbar!
    pause
    exit /b 1
)

REM Starte PowerShell Setup-Skript
echo [INFO] Starte PowerShell Setup-Skript...
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup_exiftool.ps1" %*

if errorlevel 1 (
    echo.
    echo [FEHLER] ExifTool Setup fehlgeschlagen!
    pause
    exit /b 1
)

echo.
echo [OK] ExifTool Setup abgeschlossen!
pause
exit /b 0
