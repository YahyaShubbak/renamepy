# ============================================================================
# RenamePy - Robust Installation Script
# ============================================================================
# This script installs the renamepy application with all dependencies
# ============================================================================

param(
    [switch]$SkipExifCheck = $false,
    [switch]$ForceVenv = $false,
    [switch]$Verbose = $false
)

# Set encoding to UTF-8 for correct display of special characters
[System.Environment]::SetEnvironmentVariable('PYTHONIOENCODING', 'utf-8', 'Process')
$OutputEncoding = [System.Text.UTF8Encoding]::new()

# ============================================================================
# Global Configuration
# ============================================================================
$SCRIPT_VERSION = "1.0.0"
$VENV_NAME = "renamepy"
$REQUIREMENTS_FILE = "requirements.txt"
$PROJECT_ROOT = Split-Path -Parent $MyInvocation.MyCommand.Path

# Colored output
$Colors = @{
    Success = "Green"
    Error   = "Red"
    Warning = "Yellow"
    Info    = "Cyan"
    Debug   = "Gray"
}

function Write-Log {
    param(
        [string]$Message,
        [string]$Level = "Info"
    )
    
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $color = $Colors[$Level]
    
    if ($Verbose -or $Level -ne "Debug") {
        Write-Host "[$timestamp] [$Level] $Message" -ForegroundColor $color
    }
}

function Write-Success {
    param([string]$Message)
    Write-Log -Message $Message -Level "Success"
}

function Write-Error-Custom {
    param([string]$Message)
    Write-Log -Message $Message -Level "Error"
}

function Write-Warning-Custom {
    param([string]$Message)
    Write-Log -Message $Message -Level "Warning"
}

function Write-Debug-Custom {
    param([string]$Message)
    Write-Log -Message $Message -Level "Debug"
}

# ============================================================================
# Function: Check if command exists
# ============================================================================
function Test-CommandExists {
    param([string]$Command)
    
    try {
        if (Get-Command $Command -ErrorAction Stop) {
            return $true
        }
    }
    catch {
        return $false
    }
}

# ============================================================================
# Function: Check Python installation
# ============================================================================
function Test-PythonInstallation {
    Write-Log -Message "Checking Python installation..." -Level "Info"
    
    if (-not (Test-CommandExists "python")) {
        Write-Error-Custom "Python is not installed or not in PATH!"
        return $false
    }
    
    try {
        $pythonVersion = & python --version 2>&1
        Write-Success "Python found: $pythonVersion"
        
        # Check Python version (at least 3.10 required for PEP 604 type hints)
        $versionMatch = $pythonVersion -match "Python (\d+\.\d+)"
        if ($Matches) {
            $version = [version]$Matches[1]
            if ($version -lt [version]"3.10") {
                Write-Error-Custom "Python version must be at least 3.10 (found: $version)"
                return $false
            }
        }
        return $true
    }
    catch {
        Write-Error-Custom "Error checking Python version: $_"
        return $false
    }
}

# ============================================================================
# Function: Detect Conda/Miniconda/Mamba installation
# ============================================================================
function Get-CondaInfo {
    Write-Log -Message "Searching for Conda/Miniconda/Mamba installation..." -Level "Info"
    
    $condaTools = @(
        @{Name = "Conda"; Command = "conda" },
        @{Name = "Mamba"; Command = "mamba" }
    )
    
    foreach ($tool in $condaTools) {
        if (Test-CommandExists $tool.Command) {
            try {
                $output = & $tool.Command --version 2>&1
                Write-Success "$($tool.Name) found: $output"
                
                # Determine Conda environment path
                $condaPath = & $tool.Command info --base 2>&1
                if ($condaPath) {
                    $envPath = Join-Path $condaPath "envs"
                    return @{
                        Available = $true
                        Tool      = $tool.Command
                        Name      = $tool.Name
                        Version   = $output
                        EnvPath   = $envPath
                        BasePath  = $condaPath
                    }
                }
            }
            catch {
                Write-Debug-Custom "Error checking $($tool.Name): $_"
            }
        }
    }
    
    Write-Warning-Custom "Conda/Mamba not found. Will fall back to venv + pip."
    return @{
        Available = $false
        Tool      = $null
        Name      = $null
        Version   = $null
        EnvPath   = $null
        BasePath  = $null
    }
}

# ============================================================================
# Function: Create Conda environment
# ============================================================================
function New-CondaEnvironment {
    param(
        [string]$CondaTool,
        [string]$EnvName,
        [string]$EnvPath
    )
    
    $envFullPath = Join-Path $EnvPath $EnvName
    
    if (Test-Path $envFullPath) {
        Write-Warning-Custom "Conda environment '$EnvName' already exists at $envFullPath"
        $response = Read-Host "Do you want to delete and recreate the environment? (yes/no)"
        
        if ($response -eq "yes") {
            Write-Log -Message "Deleting existing environment..." -Level "Info"
            & $CondaTool env remove -n $EnvName -y
            if ($LASTEXITCODE -ne 0) {
                Write-Error-Custom "Could not delete environment"
                return $false
            }
        }
        else {
            Write-Log -Message "Using existing environment" -Level "Info"
            return $true
        }
    }
    
    Write-Log -Message "Creating Conda environment '$EnvName' with Python..." -Level "Info"
    & $CondaTool create -n $EnvName python -y
    
    if ($LASTEXITCODE -ne 0) {
        Write-Error-Custom "Could not create Conda environment"
        return $false
    }
    
    Write-Success "Conda environment '$EnvName' successfully created"
    return $true
}

# ============================================================================
# Function: Create venv environment
# ============================================================================
function New-VenvEnvironment {
    param([string]$EnvName)
    
    $venvPath = Join-Path $PROJECT_ROOT $EnvName
    
    if (Test-Path $venvPath) {
        Write-Warning-Custom "Venv environment '$EnvName' already exists at $venvPath"
        $response = Read-Host "Do you want to delete and recreate the environment? (yes/no)"
        
        if ($response -eq "yes") {
            Write-Log -Message "Deleting existing environment..." -Level "Info"
            Remove-Item -Path $venvPath -Recurse -Force
        }
        else {
            Write-Log -Message "Using existing environment" -Level "Info"
            return $true
        }
    }
    
    Write-Log -Message "Creating venv environment '$EnvName' at $venvPath..." -Level "Info"
    & python -m venv $venvPath
    
    if ($LASTEXITCODE -ne 0) {
        Write-Error-Custom "Could not create venv environment"
        return $false
    }
    
    Write-Success "Venv environment '$EnvName' successfully created"
    return $true
}

# ============================================================================
# Function: Activate environment and install packages
# ============================================================================
function Install-Packages {
    param(
        [string]$EnvName,
        [string]$CondaTool = $null,
        [bool]$UsesConda = $false
    )
    
    if (-not (Test-Path $REQUIREMENTS_FILE)) {
        Write-Error-Custom "requirements.txt not found!"
        return $false
    }
    
    Write-Log -Message "Installing packages with pip..." -Level "Info"
    
    # Activate venv or conda environment
    if ($UsesConda) {
        # Use conda run instead of activating
        Write-Log -Message "Using conda for installation..." -Level "Debug"
        & $CondaTool run -n $EnvName pip install --upgrade pip
        & $CondaTool run -n $EnvName pip install -r $REQUIREMENTS_FILE
    }
    else {
        # Activate venv
        $venvPath = Join-Path $PROJECT_ROOT $EnvName
        $activateScript = Join-Path $venvPath "Scripts\Activate.ps1"
        
        if (-not (Test-Path $activateScript)) {
            Write-Error-Custom "Activate.ps1 not found: $activateScript"
            return $false
        }
        
        & $activateScript
        & python -m pip install --upgrade pip 2>$null
        & pip install -r $REQUIREMENTS_FILE
        $result = $LASTEXITCODE -eq 0
        deactivate 2>$null
        return $result
    }
    
    if ($LASTEXITCODE -ne 0) {
        Write-Error-Custom "Package installation failed"
        return $false
    }
    
    Write-Success "Packages successfully installed"
    return $true
}

# ============================================================================
# Function: Check ExifTool installation and download
# ============================================================================
function Test-ExifToolInstallation {
    if ($SkipExifCheck) {
        Write-Log -Message "ExifTool check skipped" -Level "Info"
        return
    }
    
    Write-Log -Message "Checking ExifTool installation..." -Level "Info"
    
    $exiftoolDir = Join-Path $PROJECT_ROOT "exiftool-13.40_64"
    $exiftoolExe = Join-Path $exiftoolDir "exiftool.exe"
    
    # Check if available locally in project
    if (Test-Path $exiftoolExe) {
        try {
            $exiftoolVersion = & $exiftoolExe -ver 2>&1
            Write-Success "ExifTool found (local): Version $exiftoolVersion"
            return
        }
        catch {
            Write-Warning-Custom "ExifTool error: $_"
        }
    }
    
    # Check if available in system
    if (Test-CommandExists "exiftool") {
        try {
            $exiftoolVersion = & exiftool -ver 2>&1
            Write-Success "ExifTool found (system): Version $exiftoolVersion"
            return
        }
        catch {
            Write-Warning-Custom "ExifTool error: $_"
        }
    }
    
    # ExifTool not found - offer to download
    Write-Host ""
    Write-Warning-Custom "ExifTool is not installed"
    Write-Log -Message "ExifTool is optional for extended EXIF functions." -Level "Info"
    Write-Host ""
    
    Write-Host "Would you like to automatically download and install ExifTool?" -ForegroundColor Yellow
    Write-Host "  [Y] Yes, automatically download (~10 MB)" -ForegroundColor Cyan
    Write-Host "  [N] No, install manually later" -ForegroundColor Cyan
    Write-Host ""
    
    $response = Read-Host "Your choice (Y/N)"
    
    if ($response -match "^[yY]") {
        Write-Log -Message "Starting ExifTool setup..." -Level "Info"
        $setupScript = Join-Path $PROJECT_ROOT "setup_exiftool.ps1"
        
        if (Test-Path $setupScript) {
            try {
                & $setupScript
                if ($LASTEXITCODE -eq 0) {
                    Write-Success "ExifTool successfully installed"
                }
                else {
                    Write-Warning-Custom "ExifTool installation had errors"
                }
            }
            catch {
                Write-Warning-Custom "ExifTool setup error: $_"
            }
        }
        else {
            Write-Warning-Custom "setup_exiftool.ps1 not found"
            Write-Log -Message "Install manually from: https://exiftool.org/" -Level "Info"
        }
    }
    else {
        Write-Log -Message "ExifTool skipped. The application will work without it." -Level "Info"
        Write-Log -Message "Install manually later from: https://exiftool.org/" -Level "Info"
    }
}

# ============================================================================
# Function: Validate installation
# ============================================================================
function Test-InstallationSuccess {
    param(
        [string]$EnvName,
        [bool]$UsesConda = $false
    )
    
    Write-Log -Message "Validating installation..." -Level "Info"
    
    if ($UsesConda) {
        Write-Log -Message "Checking Conda environment..." -Level "Debug"
        $envsList = & conda env list
        if ($envsList -match $EnvName) {
            Write-Success "Conda environment confirmed"
            return $true
        }
    }
    else {
        $venvPath = Join-Path $PROJECT_ROOT $EnvName
        if (Test-Path $venvPath) {
            Write-Success "Venv environment confirmed"
            return $true
        }
    }
    
    return $false
}

# ============================================================================
# Function: Create activation shortcuts
# ============================================================================
function Create-ActivationScripts {
    param(
        [string]$EnvName,
        [bool]$UsesConda = $false
    )
    
    $activateBat = Join-Path $PROJECT_ROOT "activate_env.bat"
    
    if ($UsesConda) {
        # Create activate.bat for Conda
        $lines = @(
            "@echo off",
            "REM Activate Conda environment",
            "call conda activate $EnvName"
        )
        $content = $lines -join [Environment]::NewLine
        Set-Content -Path $activateBat -Value $content
        Write-Success "Activation script created: $activateBat"
    }
    else {
        # Create activate.bat for Venv
        $venvPath = Join-Path $PROJECT_ROOT $EnvName
        $activateScriptPath = Join-Path $venvPath "Scripts\activate.bat"
        
        $lines = @(
            "@echo off",
            "REM Activate Venv environment",
            "call `"$activateScriptPath`""
        )
        $content = $lines -join [Environment]::NewLine
        Set-Content -Path $activateBat -Value $content
        Write-Success "Activation script created: $activateBat"
    }
}

# ============================================================================
# Main Program
# ============================================================================
function Main {
    Clear-Host
    Write-Host "======================================================" -ForegroundColor Cyan
    Write-Host "  RenamePy Installation Script v$SCRIPT_VERSION" -ForegroundColor Cyan
    Write-Host "======================================================" -ForegroundColor Cyan
    Write-Host ""
    
    # Step 1: Check Python
    if (-not (Test-PythonInstallation)) {
        Write-Error-Custom "Installation aborted: Python not correctly configured"
        exit 1
    }
    
    # Step 2: Check requirements
    if (-not (Test-Path $REQUIREMENTS_FILE)) {
        Write-Error-Custom "requirements.txt not found in: $PROJECT_ROOT"
        exit 1
    }
    Write-Success "requirements.txt found"
    
    # Step 3: Detect Conda installation
    $condaInfo = Get-CondaInfo
    $usesConda = $condaInfo.Available -and -not $ForceVenv
    
    # Step 4: Create environment
    Write-Host ""
    Write-Log -Message "========== Environment Creation ==========" -Level "Info"
    
    if ($usesConda) {
        if (-not (New-CondaEnvironment -CondaTool $condaInfo.Tool -EnvName $VENV_NAME -EnvPath $condaInfo.EnvPath)) {
            Write-Error-Custom "Installation aborted"
            exit 1
        }
    }
    else {
        if (-not (New-VenvEnvironment -EnvName $VENV_NAME)) {
            Write-Error-Custom "Installation aborted"
            exit 1
        }
    }
    
    # Step 5: Install packages
    Write-Host ""
    Write-Log -Message "========== Package Installation ==========" -Level "Info"
    
    if (-not (Install-Packages -EnvName $VENV_NAME -CondaTool $condaInfo.Tool -UsesConda $usesConda)) {
        Write-Error-Custom "Installation aborted"
        exit 1
    }
    
    # Step 6: Install ExifTool (optional)
    Write-Host ""
    Write-Log -Message "========== ExifTool Installation ==========" -Level "Info"
    if (-not $SkipExifCheck) {
        Test-ExifToolInstallation
    }
    else {
        Write-Log -Message "ExifTool installation skipped" -Level "Info"
    }
    
    # Step 7: Validate installation
    Write-Host ""
    Write-Log -Message "========== Validation ==========" -Level "Info"
    
    if (Test-InstallationSuccess -EnvName $VENV_NAME -UsesConda $usesConda) {
        Write-Success "Installation successfully validated!"
    }
    else {
        Write-Error-Custom "Installation could not be validated"
        exit 1
    }
    
    # Step 8: Create shortcuts
    Create-ActivationScripts -EnvName $VENV_NAME -UsesConda $usesConda
    
    # Completion
    Write-Host ""
    Write-Host "======================================================" -ForegroundColor Green
    Write-Host "  Installation completed successfully!" -ForegroundColor Green
    Write-Host "======================================================" -ForegroundColor Green
    Write-Host ""
    
    if ($usesConda) {
        Write-Host "Activate the environment with:" -ForegroundColor Yellow
        Write-Host "  conda activate $VENV_NAME" -ForegroundColor Cyan
    }
    else {
        Write-Host "Activate the environment with:" -ForegroundColor Yellow
        Write-Host "  .\$VENV_NAME\Scripts\Activate.ps1" -ForegroundColor Cyan
        Write-Host "  or:" -ForegroundColor Yellow
        Write-Host "  .\activate_env.bat" -ForegroundColor Cyan
    }
    
    Write-Host ""
    Write-Host "Start the application with:" -ForegroundColor Yellow
    Write-Host "  python RenameFiles.py" -ForegroundColor Cyan
    Write-Host ""
}

# ============================================================================
# Error Handling and Cleanup
# ============================================================================
$ErrorActionPreference = "Stop"

try {
    Main
}
catch {
    Write-Error-Custom "Critical error: $_"
    Write-Error-Custom "Stack Trace: $($_.ScriptStackTrace)"
    exit 1
}
