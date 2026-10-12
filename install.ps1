# ============================================================================
# RenamePy - Robust Installation Script
# ============================================================================
# This script installs the renamepy application with all dependencies
# ============================================================================

param(
    [switch]$SkipExifCheck = $false,
    [switch]$ForceVenv = $false,
    [switch]$Yes = $false,
    [switch]$Verbose = $false
)
# -Yes: ask nothing and take every default (also automatic when input is
# redirected, e.g. in CI). Passed through by install.bat (install.bat -Yes).

# Without [CmdletBinding()] (which would clash with the own -Verbose switch)
# PowerShell puts unknown arguments into $args silently: a typo like
# "-ForceVnev" ran a full installation with conda instead of venv.
if ($args.Count -gt 0) {
    Write-Host "Unknown option(s): $($args -join ' ')" -ForegroundColor Red
    Write-Host "Options: -Yes -ForceVenv -SkipExifCheck -Verbose"
    exit 2
}

# Set encoding to UTF-8 for correct display of special characters.
# PYTHONIOENCODING makes Python (and conda, which is Python) write UTF-8;
# [Console]::OutputEncoding makes PowerShell *read* their output as UTF-8.
# Without the latter it decodes with the OEM code page (850), and a path
# like "C:\Users\Juergen Mueller" with real umlauts comes back mangled, so
# Test-Path on it fails.
[System.Environment]::SetEnvironmentVariable('PYTHONIOENCODING', 'utf-8', 'Process')
$OutputEncoding = [System.Text.UTF8Encoding]::new()
try { [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false) } catch { }  # no console (e.g. ISE)

# All file-system calls below use -LiteralPath: with -Path, PowerShell reads
# "[...]" as a wildcard, so a project folder like "Fotos [2024]" made every
# Test-Path report its files as missing.

# ============================================================================
# Global Configuration
# ============================================================================
$SCRIPT_VERSION = "1.0.0"
$VENV_NAME = "renamepy"
$PROJECT_ROOT = Split-Path -Parent $MyInvocation.MyCommand.Path
# Absolute: the script may be started from another working directory.
$REQUIREMENTS_FILE = Join-Path $PROJECT_ROOT "requirements.txt"
# Same version as install.sh uses for conda; CI tests 3.10-3.13.
$CONDA_PYTHON = "3.12"

# Default install locations of Miniconda / Anaconda / Miniforge. The
# installers do not put conda on PATH by default, and install.bat starts
# PowerShell with -NoProfile, so `conda init powershell` never runs here.
$CondaRoots = @(
    "$env:USERPROFILE\miniconda3", "$env:USERPROFILE\anaconda3", "$env:USERPROFILE\miniforge3",
    "$env:LOCALAPPDATA\miniconda3", "$env:LOCALAPPDATA\anaconda3", "$env:LOCALAPPDATA\miniforge3",
    "$env:PROGRAMDATA\miniconda3", "$env:PROGRAMDATA\anaconda3", "$env:PROGRAMDATA\miniforge3",
    "C:\miniconda3", "C:\anaconda3"
)

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
$script:Interactive = -not $Yes
try { if ([Console]::IsInputRedirected) { $script:Interactive = $false } } catch { }

# Every question goes through here: returns the answer, or the default with
# -Yes / redirected input / Enter.
function Read-Answer {
    param([string]$Prompt, [string]$Default = "")
    if (-not $script:Interactive) {
        Write-Host "$Prompt $Default (default)"
        return $Default
    }
    $answer = Read-Host $Prompt
    if ([string]::IsNullOrWhiteSpace($answer)) { return $Default }
    return $answer.Trim()
}

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
    $response = Read-Answer "Do you want to continue? [[Y]/n]" "y"
    if ($response -match "^[yYjJ]") {
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
            & (Get-VenvPython -EnvName $EnvName) (Join-Path $PROJECT_ROOT "RenameFiles.py")
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
            if ($LASTEXITCODE -eq 0 -and (Test-Path -LiteralPath $pyPath)) {
                $candidates = @($pyPath) + $candidates
            }
        }
        catch { }
    }

    # Search common Windows installation paths. These hold one subfolder per
    # version (Python312\python.exe), so their subfolders are searched; -Path
    # on purpose, "Python*" is a wildcard.
    $searchRoots = @(
        "$env:LOCALAPPDATA\Programs\Python",
        "$env:PROGRAMFILES\Python*",
        "${env:PROGRAMFILES(x86)}\Python*",
        "$env:USERPROFILE\AppData\Local\Programs\Python"
    )

    foreach ($root in $searchRoots) {
        foreach ($dir in (Get-ChildItem -Path $root -Directory -ErrorAction SilentlyContinue)) {
            $exe = Join-Path $dir.FullName "python.exe"
            if (Test-Path -LiteralPath $exe) {
                $candidates += $exe
            }
        }
    }

    # Conda installations keep python.exe directly in their root folder (the
    # subfolder search above missed it, so Miniconda-only users were told
    # that no Python exists).
    foreach ($root in $CondaRoots) {
        $exe = Join-Path $root "python.exe"
        if (Test-Path -LiteralPath $exe) {
            $candidates += $exe
        }
    }

    # Microsoft Store Python (WindowsApps)
    $storeDir = "$env:LOCALAPPDATA\Microsoft\WindowsApps"
    if (Test-Path -LiteralPath $storeDir) {
        $storeExe = Join-Path $storeDir "python.exe"
        if (Test-Path -LiteralPath $storeExe) {
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
    # Not on PATH: the default install locations (see $CondaRoots).
    foreach ($root in $CondaRoots) {
        $bat = Join-Path $root "condabin\conda.bat"
        if (Test-Path -LiteralPath $bat) { $condaTools += @{Name = "Conda"; Command = $bat } }
    }

    # "Stop" would turn any line a native tool writes to stderr (a conda
    # deprecation warning, say) into a terminating error and silently fall
    # back to venv; exit codes are checked instead.
    $ErrorActionPreference = "Continue"
    foreach ($tool in $condaTools) {
        if ((Test-CommandExists $tool.Command) -or (Test-Path -LiteralPath $tool.Command)) {
            try {
                $output = (& $tool.Command --version 2>$null | Out-String).Trim()
                if ($LASTEXITCODE -ne 0) { continue }
                $condaPath = (& $tool.Command info --base 2>$null | Out-String).Trim()
                if ($LASTEXITCODE -eq 0 -and $condaPath -and (Test-Path -LiteralPath $condaPath)) {
                    Write-Success "$($tool.Name) found: $output ($condaPath)"
                    return @{
                        Available = $true
                        Tool      = $tool.Command
                        Name      = $tool.Name
                        Version   = $output
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
        BasePath  = $null
    }
}

# ============================================================================
# Function: Does a conda environment of this name exist?
# ============================================================================
# Asks conda instead of guessing "<base>\envs\<name>": with an all-users
# Anaconda the environment lives in %USERPROFILE%\.conda\envs, and a missed
# environment would end in `conda create -y`, which silently replaces it.
function Test-CondaEnvironment {
    param([string]$CondaTool, [string]$EnvName)
    $ErrorActionPreference = "Continue"
    $json = & $CondaTool env list --json 2>$null | Out-String
    # Throw rather than report "no environment": the caller would then run
    # `conda create -y` over an environment it merely failed to list.
    if ($LASTEXITCODE -ne 0) { throw "Could not list the conda environments ($CondaTool env list)." }
    $match = @((ConvertFrom-Json $json).envs | Where-Object { (Split-Path -Leaf $_) -eq $EnvName })
    if ($match.Count -gt 0) { return $match[0] }
    return $null
}

# ============================================================================
# Function: Create Conda environment
# ============================================================================
function New-CondaEnvironment {
    param(
        [string]$CondaTool,
        [string]$EnvName
    )

    try { $envFullPath = Test-CondaEnvironment -CondaTool $CondaTool -EnvName $EnvName }
    catch { Write-Error-Custom "$_"; return $false }

    if ($envFullPath) {
        Write-Warning-Custom "Conda environment '$EnvName' already exists at $envFullPath"
        $response = Read-Answer "Delete and recreate the environment? [y/[N]]" "n"

        if ($response -match "^[yYjJ]") {
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
    
    # conda-forge only: the "defaults" channel (repo.anaconda.com) falls under
    # Anaconda's terms of service, which require a paid licence in
    # organisations of more than 200 people (universities included), and
    # recent conda refuses it until the terms are accepted interactively.
    # Python pinned like install.sh, instead of whatever is newest.
    Write-Log -Message "Creating Conda environment '$EnvName' with Python $CONDA_PYTHON (conda-forge)..." -Level "Info"
    & $CondaTool create -n $EnvName --override-channels -c conda-forge "python=$CONDA_PYTHON" -y
    
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
    
    if (Test-Path -LiteralPath $venvPath) {
        # A venv that cannot run pip (its base Python was removed or
        # upgraded, or it was copied from another PC) is useless: offer to
        # recreate it with Yes as the default instead of reusing it.
        $venvPy = Join-Path $venvPath "Scripts\python.exe"
        $works = $false
        if (Test-Path -LiteralPath $venvPy) {
            $ErrorActionPreference = "Continue"
            # try: a python.exe that cannot be executed at all (0 bytes, an
            # interrupted copy) throws instead of setting an exit code.
            try {
                & $venvPy -m pip --version *> $null
                $works = ($LASTEXITCODE -eq 0)
            }
            catch { $works = $false }
        }
        if ($works) {
            Write-Warning-Custom "Venv environment '$EnvName' already exists at $venvPath"
            $response = Read-Answer "Delete and recreate the environment? [y/[N]]" "n"
        }
        else {
            Write-Warning-Custom "The venv at $venvPath is broken (its Python or pip does not start)."
            $response = Read-Answer "Delete and recreate the environment? [[Y]/n]" "y"
        }

        if ($response -match "^[yYjJ]") {
            Write-Log -Message "Deleting existing environment..." -Level "Info"
            Remove-Item -LiteralPath $venvPath -Recurse -Force
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
# Function: Path of the venv's python.exe / pythonw.exe
# ============================================================================
function Get-VenvPython {
    param(
        [string]$EnvName,
        [switch]$Windowed
    )
    $exe = if ($Windowed) { "pythonw.exe" } else { "python.exe" }
    return Join-Path (Join-Path $PROJECT_ROOT $EnvName) "Scripts\$exe"
}

# ============================================================================
# Function: Install packages into the environment
# ============================================================================
function Install-Packages {
    param(
        [string]$EnvName,
        [string]$CondaTool = $null,
        [bool]$UsesConda = $false
    )
    
    if (-not (Test-Path -LiteralPath $REQUIREMENTS_FILE)) {
        Write-Error-Custom "requirements.txt not found!"
        return $false
    }
    
    Write-Log -Message "Installing packages with pip..." -Level "Info"
    Write-Host ""
    
    if ($UsesConda) {
        # Use conda run instead of activating
        Write-Log -Message "Using conda for installation..." -Level "Debug"
        & $CondaTool run -n $EnvName python -m pip install --upgrade pip --progress-bar on
        & $CondaTool run -n $EnvName python -m pip install -r $REQUIREMENTS_FILE --progress-bar on
    }
    else {
        # Call the venv's own python.exe. $script:PythonExe is the *system*
        # Python (an absolute path found via the py launcher), so running pip
        # through it would install the packages outside the venv - even with
        # the venv activated - and the app would then fail to start.
        $venvPython = Get-VenvPython -EnvName $EnvName
        if (-not (Test-Path -LiteralPath $venvPython)) {
            Write-Error-Custom "venv Python not found: $venvPython"
            return $false
        }

        & $venvPython -m pip install --upgrade pip --progress-bar on
        & $venvPython -m pip install -r $REQUIREMENTS_FILE --progress-bar on
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
    # Newest version first, the same order the app uses.
    $exiftoolDirs = Get-ChildItem -LiteralPath $PROJECT_ROOT -Directory -Filter "exiftool*" -ErrorAction SilentlyContinue |
        Sort-Object -Descending { if ($_.Name -match '(\d+(\.\d+)+)') { [version]$Matches[1] } else { [version]'0.0' } }
    
    foreach ($dir in $exiftoolDirs) {
        $exiftoolExe = Join-Path $dir.FullName "exiftool.exe"
        if (Test-Path -LiteralPath $exiftoolExe) {
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
    $response = Read-Answer "Download and install ExifTool automatically? [[Y]/n]" "y"

    if ($response -match "^[yYjJ]") {
        Write-Log -Message "Starting ExifTool setup..." -Level "Info"
        $setupScript = Join-Path $PROJECT_ROOT "setup_exiftool.ps1"
        
        if (Test-Path -LiteralPath $setupScript) {
            try {
                # -Unattended: -Yes must reach the ExifTool setup too.
                & $setupScript -Unattended:(-not $script:Interactive)
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
        [string]$CondaTool = $null,
        [bool]$UsesConda = $false
    )
    
    Write-Log -Message "Validating installation..." -Level "Info"

    # Import the packages with the environment's own interpreter - checking
    # only that the environment folder exists would not notice packages
    # that were installed somewhere else.
    $check = "import PyQt6.QtWidgets, exiftool; print('PyQt6 and PyExifTool OK')"
    if ($UsesConda) {
        & $CondaTool run -n $EnvName python -c $check
    }
    else {
        $venvPython = Get-VenvPython -EnvName $EnvName
        if (-not (Test-Path -LiteralPath $venvPython)) {
            Write-Error-Custom "venv Python not found: $venvPython"
            return $false
        }
        & $venvPython -c $check
    }

    if ($LASTEXITCODE -eq 0) {
        Write-Success "Environment '$EnvName' can import all required packages"
        return $true
    }
    Write-Error-Custom "The environment '$EnvName' cannot import PyQt6/PyExifTool"
    return $false
}

# ============================================================================
# Function: Create activation shortcuts
# ============================================================================
function Create-ActivationScripts {
    param(
        [string]$EnvName,
        [bool]$UsesConda = $false,
        [string]$CondaBase = ""
    )

    $activateBat = Join-Path $PROJECT_ROOT "activate_env.bat"

    if ($UsesConda) {
        # Activate via the base's own activate.bat: works without conda on PATH.
        $activateScriptPath = Join-Path $CondaBase "Scripts\activate.bat"
        $lines = @(
            "@echo off",
            "chcp 65001 >nul",
            "REM Activate Conda environment",
            "call `"$activateScriptPath`" $EnvName"
        )
    }
    else {
        $venvPath = Join-Path $PROJECT_ROOT $EnvName
        $activateScriptPath = Join-Path $venvPath "Scripts\activate.bat"
        $lines = @(
            "@echo off",
            "chcp 65001 >nul",
            "REM Activate Venv environment",
            "call `"$activateScriptPath`""
        )
    }
    # UTF-8 without BOM, and chcp 65001 before the first path: cmd reads a
    # batch file in the console's code page (850 on German Windows), so a
    # path with umlauts written by Set-Content (ANSI in PowerShell 5.1, UTF-8
    # in 7) was misread and the call failed with "path not found". This
    # leaves the console on code page 65001 afterwards, which is harmless.
    [System.IO.File]::WriteAllText($activateBat, ($lines -join "`r`n") + "`r`n", [System.Text.UTF8Encoding]::new($false))
    Write-Success "Activation script created: $activateBat"
}

# ============================================================================
# Function: Create desktop shortcut (Windows)
# ============================================================================
function Create-DesktopShortcut {
    param(
        [string]$EnvName,
        [bool]$UsesConda = $false,
        [string]$CondaBase = ""
    )

    Write-Host ""
    $response = Read-Answer "Create a desktop shortcut for RenamePy? [[Y]/n]" "y"

    if ($response -notmatch "^[yYjJ]") {
        Write-Log -Message "Desktop shortcut skipped" -Level "Info"
        return
    }

    try {
        $desktopPath = [Environment]::GetFolderPath("Desktop")
        if (-not $desktopPath -or -not (Test-Path -LiteralPath $desktopPath)) {
            $desktopPath = Join-Path $env:USERPROFILE "Desktop"
        }

        $shortcutPath = Join-Path $desktopPath "RenamePy.lnk"

        $WScriptShell = New-Object -ComObject WScript.Shell
        $shortcut = $WScriptShell.CreateShortcut($shortcutPath)

        if ($UsesConda) {
            # Launch via cmd that activates conda then runs python. The base
            # found earlier, not `conda` from PATH: conda may only have been
            # found in its default folder, or only as mamba.
            $activateBat = Join-Path $CondaBase "Scripts\activate.bat"
            $shortcut.TargetPath = "cmd.exe"
            $shortcut.Arguments = "/c `"call `"$activateBat`" $EnvName && python RenameFiles.py`""
        }
        else {
            # pythonw.exe: no console window next to the GUI
            $pythonExe = Get-VenvPython -EnvName $EnvName -Windowed
            if (-not (Test-Path -LiteralPath $pythonExe)) {
                $pythonExe = Get-VenvPython -EnvName $EnvName
            }
            $shortcut.TargetPath = $pythonExe
            $shortcut.Arguments = "RenameFiles.py"
        }

        $shortcut.WorkingDirectory = $PROJECT_ROOT
        $shortcut.Description = "RenamePy - Advanced Photo Renaming Tool"
        $shortcut.WindowStyle = 1  # Normal window

        # Use .ico if available
        $iconPath = Join-Path $PROJECT_ROOT "icon.ico"
        if (Test-Path -LiteralPath $iconPath) {
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
    if (-not (Test-Path -LiteralPath $REQUIREMENTS_FILE)) {
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
        if (-not (New-CondaEnvironment -CondaTool $condaInfo.Tool -EnvName $VENV_NAME)) {
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
    $packageLines = Get-Content -LiteralPath $REQUIREMENTS_FILE -ErrorAction SilentlyContinue |
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
    
    if (Test-InstallationSuccess -EnvName $VENV_NAME -CondaTool $condaInfo.Tool -UsesConda $usesConda) {
        Write-Success "Installation successfully validated!"
    }
    else {
        Write-Error-Custom "Installation could not be validated"
        exit 1
    }
    
    # Step 8: Create shortcuts
    Create-ActivationScripts -EnvName $VENV_NAME -UsesConda $usesConda -CondaBase $condaInfo.BasePath

    # Step 9: Create desktop shortcut
    Create-DesktopShortcut -EnvName $VENV_NAME -UsesConda $usesConda -CondaBase $condaInfo.BasePath

    # ============ Completion Screen ============
    $o = [char]27 + "[38;5;208m"
    $r = [char]27 + "[0m"
    Write-Host ""
    Write-Host "${o}  ======================================================${r}"
    Write-Host "${o}  RenamePy installed successfully!${r}"
    Write-Host "${o}  ======================================================${r}"
    Write-Host ""

    # start.bat finds the environment by itself. The former hint
    # ".\activate_env.bat && python ..." was a syntax error in Windows
    # PowerShell 5.1 and, in PowerShell 7, ran the system Python: a .bat file
    # cannot activate an environment for the PowerShell session.
    Write-Host "  To start manually later: double-click start.bat, or in a terminal:" -ForegroundColor DarkYellow
    if ($usesConda) {
        Write-Host "    conda activate $VENV_NAME" -ForegroundColor Green
        Write-Host "    python RenameFiles.py" -ForegroundColor Green
    }
    else {
        Write-Host "    .\$VENV_NAME\Scripts\python.exe RenameFiles.py" -ForegroundColor Green
    }

    Write-Host ""
    Write-Host "  [R]  Start RenamePy now" -ForegroundColor Green
    Write-Host "  [any other key]  Exit" -ForegroundColor Gray
    Write-Host ""

    $choice = Read-Answer "[Any key] / R" ""
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
