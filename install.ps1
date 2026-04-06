# ======================================================
#   RenamePy Installation Script v1.0.1
# ======================================================
# Installs Python dependencies and optionally downloads
# ExifTool for enhanced EXIF metadata support.
# ======================================================

param(
    [switch]$SkipExifTool,
    [switch]$ForceRecreate
)

$ErrorActionPreference = "Stop"

# --- Helpers -----------------------------------------------------------
function Write-Info    { param($msg) Write-Host "[$(Get-Date -f 'yyyy-MM-dd HH:mm:ss')] [Info] $msg" }
function Write-Success { param($msg) Write-Host "[$(Get-Date -f 'yyyy-MM-dd HH:mm:ss')] [Success] $msg" -ForegroundColor Green }
function Write-Warn    { param($msg) Write-Host "[$(Get-Date -f 'yyyy-MM-dd HH:mm:ss')] [Warning] $msg" -ForegroundColor Yellow }
function Write-Err     { param($msg) Write-Host "[$(Get-Date -f 'yyyy-MM-dd HH:mm:ss')] [Error] $msg" -ForegroundColor Red }

# ExifTool version – update this line when a new release is available.
$ExifToolVersion = "13.54"
$ExifToolFolder  = "exiftool-${ExifToolVersion}_64"
$ExifToolZip     = "${ExifToolFolder}.zip"
# Primary source: exiftool.org (official, direct link)
$ExifToolUrl     = "https://exiftool.org/${ExifToolZip}"
# Fallback source: SourceForge mirror
$ExifToolUrlFallback = "https://downloads.sourceforge.net/project/exiftool/${ExifToolZip}"

# -----------------------------------------------------------------------
Write-Host ""
Write-Host "======================================================"
Write-Host "  RenamePy Installation Script v1.0.1"
Write-Host "======================================================"
Write-Host ""

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition

# --- 1. Python check ---------------------------------------------------
Write-Info "Checking Python installation..."
$pythonCmd = $null
foreach ($cmd in @("python", "python3", "py")) {
    try {
        $ver = & $cmd --version 2>&1
        if ($LASTEXITCODE -eq 0) { $pythonCmd = $cmd; break }
    } catch {}
}
if (-not $pythonCmd) {
    Write-Err "Python not found. Please install Python 3.9+ and try again."
    exit 1
}
$pythonPath = (& $pythonCmd -c "import sys; print(sys.executable)" 2>&1)
Write-Success "Python found: $(& $pythonCmd --version 2>&1)"
Write-Info    "  Path: $pythonPath"

# Check requirements.txt
$reqFile = Join-Path $ScriptDir "requirements.txt"
if (Test-Path $reqFile) { Write-Success "requirements.txt found" }
else { Write-Warn "requirements.txt not found – skipping pip install" }

# --- 2. Conda detection ------------------------------------------------
Write-Info "Searching for Conda/Miniconda/Mamba installation..."
$condaExe = $null
$condaCandidates = @(
    (Join-Path $env:USERPROFILE "miniconda3\Scripts\conda.exe"),
    (Join-Path $env:USERPROFILE "anaconda3\Scripts\conda.exe"),
    (Join-Path $env:USERPROFILE "mambaforge\Scripts\conda.exe"),
    "C:\ProgramData\miniconda3\Scripts\conda.exe",
    "C:\ProgramData\anaconda3\Scripts\conda.exe"
)
foreach ($c in $condaCandidates) {
    if (Test-Path $c) { $condaExe = $c; break }
}
if (-not $condaExe) {
    try { $condaExe = (Get-Command conda -ErrorAction SilentlyContinue).Source } catch {}
}

# --- 3. Environment creation -------------------------------------------
Write-Host ""
Write-Info "========== Environment Creation =========="

if ($condaExe) {
    Write-Success "Conda found: $(& $condaExe --version 2>&1)"
    $envName = "renamepy"

    # Check if env already exists
    $envList = & $condaExe env list 2>&1
    $envExists = $envList | Select-String -SimpleMatch $envName

    if ($envExists) {
        $envPath = ($envList | Select-String -SimpleMatch $envName | Select-Object -First 1).Line -replace "^$envName\s+\*?\s*", ""
        Write-Warn "Conda environment '$envName' already exists at $envPath"
        if ($ForceRecreate) { $answer = "yes" }
        else {
            $answer = Read-Host "Do you want to delete and recreate the environment? (yes/no)"
        }
        if ($answer -eq "yes") {
            Write-Info "Deleting existing environment..."
            & $condaExe env remove -n $envName -y | Out-Null
        }
    }

    Write-Info "Creating Conda environment '$envName' with Python..."
    & $condaExe create -n $envName python -y
    if ($LASTEXITCODE -ne 0) { Write-Err "Failed to create Conda environment"; exit 1 }
    Write-Success "Conda environment '$envName' successfully created"

    Write-Host ""
    Write-Info "========== Package Installation =========="
    Write-Info "Installing packages with pip..."
    & $condaExe run -n $envName pip install -r $reqFile
    if ($LASTEXITCODE -ne 0) { Write-Err "pip install failed"; exit 1 }
    Write-Success "Packages successfully installed"
} else {
    Write-Warn "Conda not found – using system pip"
    Write-Host ""
    Write-Info "========== Package Installation =========="
    if (Test-Path $reqFile) {
        & $pythonCmd -m pip install --upgrade pip
        & $pythonCmd -m pip install -r $reqFile
        if ($LASTEXITCODE -ne 0) { Write-Err "pip install failed"; exit 1 }
        Write-Success "Packages successfully installed"
    }
}

# --- 4. ExifTool installation ------------------------------------------
Write-Host ""
Write-Info "========== ExifTool Installation =========="
Write-Info "Checking ExifTool installation..."

$exifToolTarget = Join-Path $ScriptDir $ExifToolFolder
$exifToolExe    = Join-Path $exifToolTarget "exiftool(-k).exe"
$exifToolExeAlt = Join-Path $exifToolTarget "exiftool.exe"

$exifInstalled = (Test-Path $exifToolExe) -or (Test-Path $exifToolExeAlt)
if ($exifInstalled) {
    Write-Success "ExifTool already installed in $exifToolTarget"
} elseif ($SkipExifTool) {
    Write-Warn "ExifTool installation skipped (--SkipExifTool flag)"
} else {
    Write-Warn "ExifTool is not installed"
    Write-Info "ExifTool is optional for extended EXIF functions."
    Write-Host ""
    Write-Host "Would you like to automatically download and install ExifTool?"
    Write-Host "  [Y] Yes, automatically download (~10 MB)"
    Write-Host "  [N] No, install manually later"
    $choice = Read-Host "Your choice (Y/N)"

    if ($choice -match "^[Yy]") {
        Write-Info "Starting ExifTool setup..."
        Write-Host ""
        Write-Host "======================================================"
        Write-Host "  ExifTool Setup for RenamePy"
        Write-Host "======================================================"
        Write-Host ""
        Write-Host "[INFO] Project directory: $ScriptDir"
        Write-Host "[INFO] ExifTool target folder: $exifToolTarget"
        Write-Host ""

        $zipPath = Join-Path $env:TEMP $ExifToolZip
        $downloaded = $false

        foreach ($url in @($ExifToolUrl, $ExifToolUrlFallback)) {
            Write-Host "[INFO] Downloading ExifTool..."
            Write-Host "[INFO] Source: $url"
            Write-Host "[INFO] Downloading (this may take 1-2 minutes)..."
            try {
                $wc = New-Object System.Net.WebClient
                $wc.DownloadFile($url, $zipPath)
                Write-Host "[INFO] Download complete."
                $downloaded = $true
                break
            } catch {
                Write-Host "[WARN] Download failed from $url : $($_.Exception.Message)"
                Write-Host "[INFO] Trying next source..."
            }
        }

        if (-not $downloaded) {
            Write-Err "All download sources failed."
            Write-Host "[INFO] Please download ExifTool manually:"
            Write-Host "       https://exiftool.org/${ExifToolZip}"
            Write-Host "       Extract the '${ExifToolFolder}' folder into: $ScriptDir"
        } else {
            Write-Host "[INFO] Extracting archive..."
            try {
                Expand-Archive -Path $zipPath -DestinationPath $ScriptDir -Force
                Remove-Item $zipPath -ErrorAction SilentlyContinue
                Write-Host "[INFO] Extraction complete."
                Write-Success "ExifTool installed to $exifToolTarget"
            } catch {
                Write-Err "Extraction failed: $($_.Exception.Message)"
            }
        }
    } else {
        Write-Warn "ExifTool installation skipped by user"
        Write-Info "Manual install: download https://exiftool.org/ and extract '${ExifToolFolder}' into $ScriptDir"
    }
}

# --- 5. Validation -----------------------------------------------------
Write-Host ""
Write-Info "========== Validation =========="
Write-Info "Validating installation..."

$valid = $true

if ($condaExe) {
    $envCheck = & $condaExe env list 2>&1 | Select-String -SimpleMatch "renamepy"
    if ($envCheck) { Write-Success "Conda environment 'renamepy' confirmed" }
    else { Write-Warn "Conda environment 'renamepy' not found"; $valid = $false }
}

$renameMain = Join-Path $ScriptDir "RenameFiles.py"
if (Test-Path $renameMain) { Write-Success "RenameFiles.py found" }
else { Write-Warn "RenameFiles.py missing"; $valid = $false }

if ($valid) { Write-Success "Installation successfully validated!" }
else { Write-Warn "Validation completed with warnings" }

# Create convenience activation batch file
$activateBat = Join-Path $ScriptDir "activate_env.bat"
if ($condaExe -and -not (Test-Path $activateBat)) {
    @"
@echo off
call conda activate renamepy
python RenameFiles.py
"@ | Set-Content $activateBat
    Write-Success "Activation script created: $activateBat"
}

Write-Host ""
Write-Host "======================================================"
Write-Host "  Installation completed successfully!"
Write-Host "======================================================"
Write-Host ""
if ($condaExe) {
    Write-Host "Activate the environment with:"
    Write-Host "  conda activate renamepy"
    Write-Host ""
}
Write-Host "Start the application with:"
Write-Host "  python RenameFiles.py"
Write-Host ""
Write-Host "[SUCCESS] Installation completed"
