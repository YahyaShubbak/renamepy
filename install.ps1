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
    Info    = "DarkYellow"
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
# Function: Ask user to confirm a step before proceeding
# Returns $true if confirmed, $false if aborted
# ============================================================================
function Confirm-Step {
    param(
        [string]$StepName,
        [string]$Description = "",
        # Optional list of items to display (e.g. package names)
        [string[]]$ItemList = @()
    )

    Write-Host ""
    Write-Host "The following step will be performed:" -ForegroundColor White
    Write-Host "  $StepName" -ForegroundColor DarkYellow
    if ($Description) {
        Write-Host "  $Description" -ForegroundColor Gray
    }

    if ($ItemList.Count -gt 0) {
        Write-Host ""
        foreach ($item in $ItemList) {
            Write-Host "  $item" -ForegroundColor DarkYellow
        }
    }

    Write-Host ""
    # [Y] = default (Enter accepts), n = must be typed explicitly
    $response = Read-Host "Do you want to continue? [[Y]/n]"
    if ([string]$response -eq "" -or $response -match "^[yY]") {
        return $true
    }

    Write-Warning-Custom "Aborted by user."
    return $false
}

# ============================================================================
# Function: Launch RenamePy after installation
# ============================================================================
function Start-RenamePy {
    param(
        [string]$EnvName,
        [string]$CondaTool = $null,
        [bool]$UsesConda = $false
    )

    Write-Host ""
    Write-Log -Message "Starting RenamePy..." -Level "Info"

    try {
        if ($UsesConda) {
            & $CondaTool run -n $EnvName python (Join-Path $PROJECT_ROOT "RenameFiles.py")
        }
        else {
            $pythonExe = Join-Path $PROJECT_ROOT "$EnvName\Scripts\python.exe"
            if (-not (Test-Path $pythonExe)) {
                $pythonExe = $script:PythonExe
            }
            & $pythonExe (Join-Path $PROJECT_ROOT "RenameFiles.py")
        }
    }
    catch {
        Write-Error-Custom "Could not start RenamePy: $_"
    }
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
# Function: Find Python executable
# ============================================================================
$script:PythonExe = $null

function Find-PythonExecutable {
    # Try multiple common commands and locations
    $candidates = @("python", "python3")

    # Try the Python Launcher for Windows (py.exe)
    if (Test-CommandExists "py") {
        try {
            $pyPath = & py -3 -c "import sys; print(sys.executable)" 2>&1
            if ($LASTEXITCODE -eq 0 -and (Test-Path $pyPath)) {
                $candidates = @($pyPath) + $candidates
            }
        }
        catch { }
    }

    # Search common Windows installation paths
    $searchRoots = @(
        "$env:LOCALAPPDATA\Programs\Python",
        "$env:PROGRAMFILES\Python*",
        "${env:PROGRAMFILES(x86)}\Python*",
        "$env:USERPROFILE\AppData\Local\Programs\Python",
        "$env:USERPROFILE\miniconda3",
        "$env:USERPROFILE\anaconda3"
    )

    foreach ($root in $searchRoots) {
        foreach ($dir in (Get-ChildItem -Path $root -Directory -ErrorAction SilentlyContinue)) {
            $exe = Join-Path $dir.FullName "python.exe"
            if (Test-Path $exe) {
                $candidates += $exe
            }
        }
    }

    # Microsoft Store Python (WindowsApps)
    $storeDir = "$env:LOCALAPPDATA\Microsoft\WindowsApps"
    if (Test-Path $storeDir) {
        $storeExe = Join-Path $storeDir "python.exe"
        if (Test-Path $storeExe) {
            $candidates += $storeExe
        }
    }

    foreach ($cmd in $candidates) {
        try {
            $output = & $cmd --version 2>&1
            if ($LASTEXITCODE -eq 0 -and $output -match "Python (\d+\.\d+)") {
                $version = [version]$Matches[1]
                if ($version -ge [version]"3.10") {
                    return $cmd
                }
                else {
                    Write-Debug-Custom "Skipping $cmd (Python $version < 3.10)"
                }
            }
        }
        catch { }
    }

    return $null
}

# ============================================================================
# Function: Check Python installation
# ============================================================================
function Test-PythonInstallation {
    Write-Log -Message "Checking Python installation..." -Level "Info"

    $found = Find-PythonExecutable

    if (-not $found) {
        Write-Error-Custom "Python >= 3.10 not found!"
        Write-Log -Message "Searched: python, python3, py launcher, common install paths" -Level "Info"
        Write-Log -Message "Install Python from https://www.python.org/downloads/" -Level "Info"
        Write-Log -Message "Make sure to check 'Add Python to PATH' during installation." -Level "Info"
        return $false
    }

    $script:PythonExe = $found
    $pythonVersion = & $found --version 2>&1
    Write-Success "Python found: $pythonVersion ($found)"
    return $true
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
        $response = Read-Host "Delete and recreate the environment? [y/[N]]"
        
        if ($response -match "^[yY]") {
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
        $response = Read-Host "Delete and recreate the environment? [y/[N]]"
        
        if ($response -match "^[yY]") {
            Write-Log -Message "Deleting existing environment..." -Level "Info"
            Remove-Item -Path $venvPath -Recurse -Force
        }
        else {
            Write-Log -Message "Using existing environment" -Level "Info"
            return $true
        }
    }
    
    Write-Log -Message "Creating venv environment '$EnvName' at $venvPath..." -Level "Info"
    & $script:PythonExe -m venv $venvPath
    
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
    Write-Host ""
    
    # Activate venv or conda environment
    if ($UsesConda) {
        # Use conda run instead of activating
        Write-Log -Message "Using conda for installation..." -Level "Debug"
        & $CondaTool run -n $EnvName pip install --upgrade pip --progress-bar on
        & $CondaTool run -n $EnvName pip install -r $REQUIREMENTS_FILE --progress-bar on
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
        & $script:PythonExe -m pip install --upgrade pip --progress-bar on
        & $script:PythonExe -m pip install -r $REQUIREMENTS_FILE --progress-bar on
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
    
    # Search for any exiftool-* folder in the project
    $exiftoolDirs = Get-ChildItem -Path $PROJECT_ROOT -Directory -Filter "exiftool*" -ErrorAction SilentlyContinue
    
    foreach ($dir in $exiftoolDirs) {
        $exiftoolExe = Join-Path $dir.FullName "exiftool.exe"
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
    
    Write-Host "  exiftool  (~10 MB, from exiftool.org)" -ForegroundColor DarkYellow
    Write-Host ""
    $response = Read-Host "Download and install ExifTool automatically? [[Y]/n]"
    
    if ([string]$response -eq "" -or $response -match "^[yY]") {
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
# Function: Create desktop shortcut (Windows)
# ============================================================================
function Create-DesktopShortcut {
    param(
        [string]$EnvName,
        [bool]$UsesConda = $false
    )

    Write-Host ""
    $response = Read-Host "Create a desktop shortcut for RenamePy? [[Y]/n]"

    if ([string]$response -ne "" -and $response -notmatch "^[yY]") {
        Write-Log -Message "Desktop shortcut skipped" -Level "Info"
        return
    }

    try {
        $desktopPath = [Environment]::GetFolderPath("Desktop")
        if (-not $desktopPath -or -not (Test-Path $desktopPath)) {
            $desktopPath = Join-Path $env:USERPROFILE "Desktop"
        }

        $shortcutPath = Join-Path $desktopPath "RenamePy.lnk"

        $WScriptShell = New-Object -ComObject WScript.Shell
        $shortcut = $WScriptShell.CreateShortcut($shortcutPath)

        if ($UsesConda) {
            # Launch via cmd that activates conda then runs python
            $condaBase = (& conda info --base 2>&1).Trim()
            $activateBat = Join-Path $condaBase "Scripts\activate.bat"
            $shortcut.TargetPath = "cmd.exe"
            $shortcut.Arguments = "/c `"call `"$activateBat`" $EnvName && python RenameFiles.py`""
        }
        else {
            $venvPath = Join-Path $PROJECT_ROOT $EnvName
            $pythonExe = Join-Path $venvPath "Scripts\python.exe"
            $shortcut.TargetPath = $pythonExe
            $shortcut.Arguments = "RenameFiles.py"
        }

        $shortcut.WorkingDirectory = $PROJECT_ROOT
        $shortcut.Description = "RenamePy - Advanced Photo Renaming Tool"
        $shortcut.WindowStyle = 1  # Normal window

        # Use .ico if available
        $iconPath = Join-Path $PROJECT_ROOT "icon.ico"
        if (Test-Path $iconPath) {
            $shortcut.IconLocation = $iconPath
        }

        $shortcut.Save()

        # Release COM object
        [System.Runtime.Interopservices.Marshal]::ReleaseComObject($WScriptShell) | Out-Null

        Write-Success "Desktop shortcut created: $shortcutPath"
    }
    catch {
        Write-Warning-Custom "Could not create desktop shortcut: $_"
        Write-Log -Message "You can start the application manually from the project folder." -Level "Info"
    }
}

# ============================================================================
# Main Program
# ============================================================================
function Main {
    Clear-Host

    # Orange ANSI color (works in Windows Terminal & modern PowerShell)
    $o = [char]27 + "[38;5;208m"
    $r = [char]27 + "[0m"

    Write-Host ""
    Write-Host "${o} ____  _____ _   _    _    __  __ _____ ______   ___${r}"
    Write-Host "${o}|  _ \| ____| \ | |  / \  |  \/  | ____|  _ \ \ / / |${r}"
    Write-Host "${o}| |_) |  _| |  \| | / _ \ | |\/| |  _| | |_) \ V /  |${r}"
    Write-Host "${o}|  _ <| |___| |\  |/ ___ \| |  | | |___|  __/ | |   |${r}"
    Write-Host "${o}|_| \_\_____|_| \_/_/   \_\_|  |_|_____|_|    |_|   |${r}"
    Write-Host ""
    Write-Host "  Installation Script v$SCRIPT_VERSION" -ForegroundColor DarkYellow
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
    $envType = if ($usesConda) { "Conda" } else { "venv" }
    if (-not (Confirm-Step -StepName "Create $envType environment" -Description "Creates the Python environment '$VENV_NAME' for RenamePy.")) {
        exit 1
    }

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
    
    # Step 5: Install packages - read requirements.txt and display package list
    $packageLines = Get-Content $REQUIREMENTS_FILE -ErrorAction SilentlyContinue |
        Where-Object { $_ -notmatch '^\s*#' -and $_.Trim() -ne '' }

    $pkgDesc = "The following packages will be installed into the [${VENV_NAME}] environment:"
    if (-not (Confirm-Step -StepName "Install Python packages" -Description $pkgDesc -ItemList $packageLines)) {
        exit 1
    }

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

    # Step 9: Create desktop shortcut
    Create-DesktopShortcut -EnvName $VENV_NAME -UsesConda $usesConda

    # ============ Completion Screen ============
    $o = [char]27 + "[38;5;208m"
    $r = [char]27 + "[0m"
    Write-Host ""
    Write-Host "${o}  ======================================================${r}"
    Write-Host "${o}  RenamePy installed successfully!${r}"
    Write-Host "${o}  ======================================================${r}"
    Write-Host ""

    if ($usesConda) {
        Write-Host "  To start manually later:" -ForegroundColor DarkYellow
        Write-Host "    conda activate $VENV_NAME && python RenameFiles.py" -ForegroundColor Green
    }
    else {
        Write-Host "  To start manually later:" -ForegroundColor DarkYellow
        Write-Host "    .\activate_env.bat && python RenameFiles.py" -ForegroundColor Green
    }

    Write-Host ""
    Write-Host "  [R]  Start RenamePy now" -ForegroundColor Green
    Write-Host "  [any other key]  Exit" -ForegroundColor Gray
    Write-Host ""

    $choice = Read-Host "[Any key] / R"
    if ($choice -match "^[rR]") {
        Start-RenamePy -EnvName $VENV_NAME -CondaTool $condaInfo.Tool -UsesConda $usesConda
    }
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
