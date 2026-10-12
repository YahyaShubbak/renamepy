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

REM %* passes options through, e.g. install.bat -ForceVenv -SkipExifCheck
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\install.ps1" %*
set "RC=%ERRORLEVEL%"

if %RC% NEQ 0 (
    echo.
    REM Parentheses inside an if-block must be escaped (caret before them)
    echo Installation finished with errors ^(exit code: %RC%^).
    echo.
)

pause
REM Pass the result on: pause itself ends with exit code 0, which hid a
REM failed installation from anything that runs install.bat (CI, scripts).
exit /b %RC%
