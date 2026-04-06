@echo off
setlocal ENABLEDELAYEDEXPANSION
REM ======================================================
REM   RenamePy Installation Script v1.0.1  (Windows)
REM ======================================================
REM   - Checks Python
REM   - Creates Conda environment (or uses system pip)
REM   - Installs pip packages from requirements.txt
REM   - Downloads ExifTool 13.54 (optional)
REM   - Creates a Desktop shortcut (optional)
REM ======================================================

set "EXIFTOOL_VERSION=13.54"
set "EXIFTOOL_FOLDER=exiftool-%EXIFTOOL_VERSION%_64"
set "EXIFTOOL_ZIP=%EXIFTOOL_FOLDER%.zip"
set "EXIFTOOL_URL=https://exiftool.org/%EXIFTOOL_ZIP%"
set "EXIFTOOL_URL_FB=https://downloads.sourceforge.net/project/exiftool/%EXIFTOOL_ZIP%"

set "SCRIPT_DIR=%~dp0"
REM Remove trailing backslash
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"

echo.
echo ======================================================
echo   RenamePy Installation Script v1.0.1
echo ======================================================
echo.

REM -------------------------------------------------------
REM  1. Check Python
REM -------------------------------------------------------
call :log Info "Checking Python installation..."
set "PY="
for %%C in (python py python3) do (
    if not defined PY (
        %%C --version >nul 2>&1
        if !ERRORLEVEL! EQU 0 set "PY=%%C"
    )
)
if not defined PY (
    call :log Error "Python not found. Please install Python 3.9+ and try again."
    goto :fail
)
for /f "delims=" %%V in ('!PY! --version 2^>^&1') do set "PY_VER=%%V"
for /f "delims=" %%P in ('!PY! -c "import sys; print(sys.executable)" 2^>^&1') do set "PY_PATH=%%P"
call :log Success "Python found: !PY_VER!"
call :log Info   "  Path: !PY_PATH!"

REM -------------------------------------------------------
REM  2. Check requirements.txt
REM -------------------------------------------------------
if exist "%SCRIPT_DIR%\requirements.txt" (
    call :log Success "requirements.txt found"
) else (
    call :log Warning "requirements.txt not found"
)

REM -------------------------------------------------------
REM  3. Find Conda
REM -------------------------------------------------------
call :log Info "Searching for Conda/Miniconda/Mamba installation..."
set "CONDA_EXE="
for %%D in (
    "%USERPROFILE%\miniconda3\Scripts\conda.exe"
    "%USERPROFILE%\anaconda3\Scripts\conda.exe"
    "%USERPROFILE%\mambaforge\Scripts\conda.exe"
    "C:\ProgramData\miniconda3\Scripts\conda.exe"
    "C:\ProgramData\anaconda3\Scripts\conda.exe"
) do (
    if not defined CONDA_EXE if exist %%D set "CONDA_EXE=%%~D"
)
if not defined CONDA_EXE (
    where conda >nul 2>&1 && set "CONDA_EXE=conda"
)

REM -------------------------------------------------------
REM  4. Environment creation / package install
REM -------------------------------------------------------
echo.
call :log Info "========== Environment Creation =========="

if defined CONDA_EXE (
    for /f "delims=" %%V in ('"!CONDA_EXE!" --version 2^>^&1') do set "CONDA_VER=%%V"
    call :log Success "Conda found: !CONDA_VER!"

    REM Check if env exists
    set "ENV_EXISTS="
    for /f "tokens=1" %%E in ('"!CONDA_EXE!" env list 2^>^&1') do (
        if "%%E"=="renamepy" set "ENV_EXISTS=1"
    )

    if defined ENV_EXISTS (
        call :log Warning "Conda environment 'renamepy' already exists"
        set /p "RECREATE=Do you want to delete and recreate the environment? (yes/no): "
        if /i "!RECREATE!"=="yes" (
            call :log Info "Deleting existing environment..."
            "!CONDA_EXE!" env remove -n renamepy -y >nul 2>&1
            set "ENV_EXISTS="
        )
    )

    if not defined ENV_EXISTS (
        call :log Info "Creating Conda environment 'renamepy' with Python..."
        "!CONDA_EXE!" create -n renamepy python -y
        if !ERRORLEVEL! NEQ 0 ( call :log Error "Failed to create Conda environment" & goto :fail )
        call :log Success "Conda environment 'renamepy' successfully created"
    )

    echo.
    call :log Info "========== Package Installation =========="
    call :log Info "Installing packages with pip..."
    if exist "%SCRIPT_DIR%\requirements.txt" (
        "!CONDA_EXE!" run -n renamepy pip install -r "%SCRIPT_DIR%\requirements.txt"
        if !ERRORLEVEL! NEQ 0 ( call :log Error "pip install failed" & goto :fail )
        call :log Success "Packages successfully installed"
    ) else (
        call :log Warning "Skipping pip install – requirements.txt not found"
    )
) else (
    call :log Warning "Conda not found – using system pip"
    echo.
    call :log Info "========== Package Installation =========="
    if exist "%SCRIPT_DIR%\requirements.txt" (
        !PY! -m pip install --upgrade pip
        !PY! -m pip install -r "%SCRIPT_DIR%\requirements.txt"
        if !ERRORLEVEL! NEQ 0 ( call :log Error "pip install failed" & goto :fail )
        call :log Success "Packages successfully installed"
    ) else (
        call :log Warning "Skipping pip install – requirements.txt not found"
    )
)

REM -------------------------------------------------------
REM  5. ExifTool download (optional)
REM -------------------------------------------------------
echo.
call :log Info "========== ExifTool Installation =========="
call :log Info "Checking ExifTool installation..."

set "EXIF_TARGET=%SCRIPT_DIR%\%EXIFTOOL_FOLDER%"
set "EXIF_FOUND="
if exist "%EXIF_TARGET%\exiftool(-k).exe" set "EXIF_FOUND=1"
if exist "%EXIF_TARGET%\exiftool.exe"     set "EXIF_FOUND=1"

if defined EXIF_FOUND (
    call :log Success "ExifTool already installed in %EXIF_TARGET%"
) else (
    call :log Warning "ExifTool is not installed"
    call :log Info   "ExifTool is optional for extended EXIF functions."
    echo.
    echo Would you like to automatically download and install ExifTool?
    echo   [Y] Yes, automatically download (~10 MB^)
    echo   [N] No, install manually later
    set /p "DL_CHOICE=Your choice (Y/N): "

    if /i "!DL_CHOICE!"=="Y" (
        call :log Info "Downloading ExifTool %EXIFTOOL_VERSION%..."
        set "ZIP_TMP=%TEMP%\%EXIFTOOL_ZIP%"
        set "DL_OK="

        REM Try primary URL first (exiftool.org)
        powershell -NoProfile -Command ^
            "try { (New-Object Net.WebClient).DownloadFile('!EXIFTOOL_URL!','!ZIP_TMP!'); exit 0 } catch { exit 1 }" >nul 2>&1
        if !ERRORLEVEL! EQU 0 (
            set "DL_OK=1"
        ) else (
            call :log Warning "Primary source failed, trying fallback..."
            powershell -NoProfile -Command ^
                "try { (New-Object Net.WebClient).DownloadFile('!EXIFTOOL_URL_FB!','!ZIP_TMP!'); exit 0 } catch { exit 1 }" >nul 2>&1
            if !ERRORLEVEL! EQU 0 set "DL_OK=1"
        )

        if defined DL_OK (
            call :log Info "Extracting archive..."
            powershell -NoProfile -Command ^
                "Expand-Archive -Path '!ZIP_TMP!' -DestinationPath '%SCRIPT_DIR%' -Force" >nul 2>&1
            del /f /q "!ZIP_TMP!" >nul 2>&1
            if exist "%EXIF_TARGET%" (
                call :log Success "ExifTool installed to %EXIF_TARGET%"
            ) else (
                call :log Error "Extraction failed – folder not found after unzip"
            )
        ) else (
            call :log Error "Download failed from all sources."
            echo.
            echo Please download ExifTool manually:
            echo   %EXIFTOOL_URL%
            echo Then extract the '%EXIFTOOL_FOLDER%' folder into:
            echo   %SCRIPT_DIR%
        )
    ) else (
        call :log Warning "ExifTool installation skipped"
        call :log Info   "Manual install: %EXIFTOOL_URL%"
    )
)

REM -------------------------------------------------------
REM  6. Desktop shortcut (optional)
REM -------------------------------------------------------
echo.
call :log Info "========== Desktop Shortcut =========="
echo Would you like to create a Desktop shortcut for RenamePy?
echo   [Y] Yes, create shortcut
echo   [N] No
set /p "SC_CHOICE=Your choice (Y/N): "

if /i "!SC_CHOICE!"=="Y" (
    set "DESKTOP=%USERPROFILE%\Desktop"
    set "SHORTCUT=!DESKTOP!\RenamePy.lnk"
    set "ICON_PATH=%SCRIPT_DIR%\icon.ico"
    if not exist "!ICON_PATH!" set "ICON_PATH="

    powershell -NoProfile -Command ^
        "$s = (New-Object -COM WScript.Shell).CreateShortcut('!SHORTCUT!'); " ^
        "$s.TargetPath = 'pythonw.exe'; " ^
        "$s.Arguments = '\"!SCRIPT_DIR!\RenameFiles.py\"'; " ^
        "$s.WorkingDirectory = '!SCRIPT_DIR!'; " ^
        "if ('!ICON_PATH!' -ne '') { $s.IconLocation = '!ICON_PATH!' }; " ^
        "$s.Description = 'RenamePy - Photo File Renamer'; " ^
        "$s.Save()" >nul 2>&1
    if !ERRORLEVEL! EQU 0 (
        call :log Success "Desktop shortcut created: !SHORTCUT!"
    ) else (
        call :log Warning "Could not create Desktop shortcut (PowerShell unavailable?)"
    )
) else (
    call :log Info "Desktop shortcut skipped"
)

REM -------------------------------------------------------
REM  7. Validation
REM -------------------------------------------------------
echo.
call :log Info "========== Validation =========="
call :log Info "Validating installation..."

set "VALID=1"

if defined CONDA_EXE (
    set "ENV_FOUND="
    for /f "tokens=1" %%E in ('"!CONDA_EXE!" env list 2^>^&1') do (
        if "%%E"=="renamepy" set "ENV_FOUND=1"
    )
    if defined ENV_FOUND (
        call :log Success "Conda environment 'renamepy' confirmed"
    ) else (
        call :log Warning "Conda environment 'renamepy' not found"
        set "VALID="
    )
)

if exist "%SCRIPT_DIR%\RenameFiles.py" (
    call :log Success "RenameFiles.py found"
) else (
    call :log Warning "RenameFiles.py missing"
    set "VALID="
)

if defined VALID (
    call :log Success "Installation successfully validated!"
) else (
    call :log Warning "Validation completed with warnings"
)

echo.
echo ======================================================
echo   Installation completed!
echo ======================================================
echo.
if defined CONDA_EXE (
    echo Activate the environment with:
    echo   conda activate renamepy
    echo.
)
echo Start the application with:
echo   python RenameFiles.py
echo.
echo [SUCCESS] Installation completed
goto :end

:fail
echo.
call :log Error "Installation failed. Please check the errors above."
echo.
pause
exit /b 1

:end
pause
endlocal
exit /b 0

REM -------------------------------------------------------
REM  Helper: timestamped log line
REM  Usage: call :log <Level> "message"
REM -------------------------------------------------------
:log
for /f "tokens=1-2 delims=T" %%A in ("%DATE%T%TIME%") do (
    set "_DT=%%A %%B"
)
REM Trim the datetime to hh:mm:ss
set "_DT=!_DT:~0,19!"
echo [!_DT!] [%~1] %~2
goto :eof
