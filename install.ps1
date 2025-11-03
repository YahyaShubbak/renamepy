# ============================================================================
# RenamePy - Robuste Installationsskript
# ============================================================================
# Dieses Skript installiert die renamepy Anwendung mit allen Abhängigkeiten
# ============================================================================

param(
    [switch]$SkipExifCheck = $false,
    [switch]$ForceVenv = $false,
    [switch]$Verbose = $false
)

# Setze Encoding auf UTF-8 für korrekte Darstellung von Umlauten
[System.Environment]::SetEnvironmentVariable('PYTHONIOENCODING', 'utf-8', 'Process')
$OutputEncoding = [System.Text.UTF8Encoding]::new()

# ============================================================================
# Globale Konfiguration
# ============================================================================
$SCRIPT_VERSION = "1.0.0"
$VENV_NAME = "renamepy"
$REQUIREMENTS_FILE = "requirements.txt"
$PROJECT_ROOT = Split-Path -Parent $MyInvocation.MyCommand.Path

# Farbige Ausgabe
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
# Funktion: Prüfe ob Befehl existiert
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
# Funktion: Prüfe Python Installation
# ============================================================================
function Test-PythonInstallation {
    Write-Log -Message "Prüfe Python Installation..." -Level "Info"
    
    if (-not (Test-CommandExists "python")) {
        Write-Error-Custom "Python ist nicht installiert oder nicht im PATH!"
        return $false
    }
    
    try {
        $pythonVersion = & python --version 2>&1
        Write-Success "Python gefunden: $pythonVersion"
        
        # Prüfe Python Version (mindestens 3.7)
        $versionMatch = $pythonVersion -match "Python (\d+\.\d+)"
        if ($Matches) {
            $version = [version]$Matches[1]
            if ($version -lt [version]"3.7") {
                Write-Error-Custom "Python Version muss mindestens 3.7 sein (gefunden: $version)"
                return $false
            }
        }
        return $true
    }
    catch {
        Write-Error-Custom "Fehler bei Python Versionsprüfung: $_"
        return $false
    }
}

# ============================================================================
# Funktion: Erkenne Conda/Miniconda/Mamba Installation
# ============================================================================
function Get-CondaInfo {
    Write-Log -Message "Suche nach Conda/Miniconda/Mamba Installation..." -Level "Info"
    
    $condaTools = @(
        @{Name = "Conda"; Command = "conda" },
        @{Name = "Mamba"; Command = "mamba" }
    )
    
    foreach ($tool in $condaTools) {
        if (Test-CommandExists $tool.Command) {
            try {
                $output = & $tool.Command --version 2>&1
                Write-Success "$($tool.Name) gefunden: $output"
                
                # Bestimme Conda Umgebungspfad
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
                Write-Debug-Custom "Fehler bei $($tool.Name) Prüfung: $_"
            }
        }
    }
    
    Write-Warning-Custom "Conda/Mamba nicht gefunden. Werde auf venv + pip ausweichen."
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
# Funktion: Erstelle Conda Environment
# ============================================================================
function New-CondaEnvironment {
    param(
        [string]$CondaTool,
        [string]$EnvName,
        [string]$EnvPath
    )
    
    $envFullPath = Join-Path $EnvPath $EnvName
    
    if (Test-Path $envFullPath) {
        Write-Warning-Custom "Conda Environment '$EnvName' existiert bereits unter $envFullPath"
        $response = Read-Host "Möchtest du das Environment löschen und neu erstellen? (ja/nein)"
        
        if ($response -eq "ja") {
            Write-Log -Message "Lösche bestehendes Environment..." -Level "Info"
            & $CondaTool env remove -n $EnvName -y
            if ($LASTEXITCODE -ne 0) {
                Write-Error-Custom "Konnte Environment nicht löschen"
                return $false
            }
        }
        else {
            Write-Log -Message "Nutze bestehendes Environment" -Level "Info"
            return $true
        }
    }
    
    Write-Log -Message "Erstelle Conda Environment '$EnvName' mit Python..." -Level "Info"
    & $CondaTool create -n $EnvName python -y
    
    if ($LASTEXITCODE -ne 0) {
        Write-Error-Custom "Konnte Conda Environment nicht erstellen"
        return $false
    }
    
    Write-Success "Conda Environment '$EnvName' erfolgreich erstellt"
    return $true
}

# ============================================================================
# Funktion: Erstelle venv Environment
# ============================================================================
function New-VenvEnvironment {
    param([string]$EnvName)
    
    $venvPath = Join-Path $PROJECT_ROOT $EnvName
    
    if (Test-Path $venvPath) {
        Write-Warning-Custom "Venv Environment '$EnvName' existiert bereits unter $venvPath"
        $response = Read-Host "Möchtest du das Environment löschen und neu erstellen? (ja/nein)"
        
        if ($response -eq "ja") {
            Write-Log -Message "Lösche bestehendes Environment..." -Level "Info"
            Remove-Item -Path $venvPath -Recurse -Force
        }
        else {
            Write-Log -Message "Nutze bestehendes Environment" -Level "Info"
            return $true
        }
    }
    
    Write-Log -Message "Erstelle venv Environment '$EnvName' unter $venvPath..." -Level "Info"
    & python -m venv $venvPath
    
    if ($LASTEXITCODE -ne 0) {
        Write-Error-Custom "Konnte venv Environment nicht erstellen"
        return $false
    }
    
    Write-Success "Venv Environment '$EnvName' erfolgreich erstellt"
    return $true
}

# ============================================================================
# Funktion: Aktiviere Environment und installiere Packages
# ============================================================================
function Install-Packages {
    param(
        [string]$EnvName,
        [string]$CondaTool = $null,
        [bool]$UsesConda = $false
    )
    
    if (-not (Test-Path $REQUIREMENTS_FILE)) {
        Write-Error-Custom "requirements.txt nicht gefunden!"
        return $false
    }
    
    Write-Log -Message "Installiere Packages mit pip..." -Level "Info"
    
    # Aktiviere venv oder conda Environment
    if ($UsesConda) {
        # Nutze conda run statt zu aktivieren
        Write-Log -Message "Verwende conda zum Installieren..." -Level "Debug"
        & $CondaTool run -n $EnvName pip install --upgrade pip
        & $CondaTool run -n $EnvName pip install -r $REQUIREMENTS_FILE
    }
    else {
        # Aktiviere venv
        $venvPath = Join-Path $PROJECT_ROOT $EnvName
        $activateScript = Join-Path $venvPath "Scripts\Activate.ps1"
        
        if (-not (Test-Path $activateScript)) {
            Write-Error-Custom "Activate.ps1 nicht gefunden: $activateScript"
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
        Write-Error-Custom "Package Installation fehlgeschlagen"
        return $false
    }
    
    Write-Success "Packages erfolgreich installiert"
    return $true
}

# ============================================================================
# Funktion: Pruefe ExifTool Installation und Download
# ============================================================================
function Test-ExifToolInstallation {
    if ($SkipExifCheck) {
        Write-Log -Message "ExifTool Pruche uebersprungen" -Level "Info"
        return
    }
    
    Write-Log -Message "Pruche ExifTool Installation..." -Level "Info"
    
    $exiftoolDir = Join-Path $PROJECT_ROOT "exiftool-13.40_64"
    $exiftoolExe = Join-Path $exiftoolDir "exiftool.exe"
    
    # Prueche ob lokal im Projekt vorhanden
    if (Test-Path $exiftoolExe) {
        try {
            $exiftoolVersion = & $exiftoolExe -ver 2>&1
            Write-Success "ExifTool gefunden (lokal): Version $exiftoolVersion"
            return
        }
        catch {
            Write-Warning-Custom "ExifTool Fehler: $_"
        }
    }
    
    # Prueche ob im System vorhanden
    if (Test-CommandExists "exiftool") {
        try {
            $exiftoolVersion = & exiftool -ver 2>&1
            Write-Success "ExifTool gefunden (System): Version $exiftoolVersion"
            return
        }
        catch {
            Write-Warning-Custom "ExifTool Fehler: $_"
        }
    }
    
    # ExifTool nicht gefunden - Angebot zum Download
    Write-Host ""
    Write-Warning-Custom "ExifTool ist nicht installiert"
    Write-Log -Message "ExifTool ist optional fuer erweiterte EXIF-Funktionen." -Level "Info"
    Write-Host ""
    
    Write-Host "Moechtest du ExifTool automatisch herunterladen und installieren?" -ForegroundColor Yellow
    Write-Host "  [J] Ja, automatisch herunterladen (~10 MB)" -ForegroundColor Cyan
    Write-Host "  [N] Nein, spaeter manuell installieren" -ForegroundColor Cyan
    Write-Host ""
    
    $response = Read-Host "Deine Wahl (J/N)"
    
    if ($response -match "^[jJ]") {
        Write-Log -Message "Starte ExifTool Setup..." -Level "Info"
        $setupScript = Join-Path $PROJECT_ROOT "setup_exiftool.ps1"
        
        if (Test-Path $setupScript) {
            try {
                & $setupScript
                if ($LASTEXITCODE -eq 0) {
                    Write-Success "ExifTool erfolgreich installiert"
                }
                else {
                    Write-Warning-Custom "ExifTool Installation hatte Fehler"
                }
            }
            catch {
                Write-Warning-Custom "ExifTool Setup Fehler: $_"
            }
        }
        else {
            Write-Warning-Custom "setup_exiftool.ps1 nicht gefunden"
            Write-Log -Message "Installiere manuell von: https://exiftool.org/" -Level "Info"
        }
    }
    else {
        Write-Log -Message "ExifTool Skip. Die Anwendung funktioniert auch ohne." -Level "Info"
        Write-Log -Message "Installiere spaeter manuell von: https://exiftool.org/" -Level "Info"
    }
}

# ============================================================================
# Funktion: Validiere Installation
# ============================================================================
function Test-InstallationSuccess {
    param(
        [string]$EnvName,
        [bool]$UsesConda = $false
    )
    
    Write-Log -Message "Validiere Installation..." -Level "Info"
    
    if ($UsesConda) {
        Write-Log -Message "Prüfe Conda Environment..." -Level "Debug"
        $envsList = & conda env list
        if ($envsList -match $EnvName) {
            Write-Success "Conda Environment bestätigt"
            return $true
        }
    }
    else {
        $venvPath = Join-Path $PROJECT_ROOT $EnvName
        if (Test-Path $venvPath) {
            Write-Success "Venv Environment bestätigt"
            return $true
        }
    }
    
    return $false
}

# ============================================================================
# Funktion: Erstelle Aktivierungs-Shortcuts
# ============================================================================
function Create-ActivationScripts {
    param(
        [string]$EnvName,
        [bool]$UsesConda = $false
    )
    
    $activateBat = Join-Path $PROJECT_ROOT "activate_env.bat"
    
    if ($UsesConda) {
        # Erstelle activate.bat für Conda
        $lines = @(
            "@echo off",
            "REM Aktiviere Conda Environment",
            "call conda activate $EnvName"
        )
        $content = $lines -join [Environment]::NewLine
        Set-Content -Path $activateBat -Value $content
        Write-Success "Aktivierungsskript erstellt: $activateBat"
    }
    else {
        # Erstelle activate.bat für Venv
        $venvPath = Join-Path $PROJECT_ROOT $EnvName
        $activateScriptPath = Join-Path $venvPath "Scripts\activate.bat"
        
        $lines = @(
            "@echo off",
            "REM Aktiviere Venv Environment",
            "call `"$activateScriptPath`""
        )
        $content = $lines -join [Environment]::NewLine
        Set-Content -Path $activateBat -Value $content
        Write-Success "Aktivierungsskript erstellt: $activateBat"
    }
}

# ============================================================================
# Hauptprogramm
# ============================================================================
function Main {
    Clear-Host
    Write-Host "======================================================" -ForegroundColor Cyan
    Write-Host "  RenamePy Installation Script v$SCRIPT_VERSION" -ForegroundColor Cyan
    Write-Host "======================================================" -ForegroundColor Cyan
    Write-Host ""
    
    # Schritt 1: Prüfe Python
    if (-not (Test-PythonInstallation)) {
        Write-Error-Custom "Installation abgebrochen: Python nicht korrekt konfiguriert"
        exit 1
    }
    
    # Schritt 2: Prüfe Requirements
    if (-not (Test-Path $REQUIREMENTS_FILE)) {
        Write-Error-Custom "requirements.txt nicht gefunden in: $PROJECT_ROOT"
        exit 1
    }
    Write-Success "requirements.txt gefunden"
    
    # Schritt 3: Erkenne Conda Installation
    $condaInfo = Get-CondaInfo
    $usesConda = $condaInfo.Available -and -not $ForceVenv
    
    # Schritt 4: Erstelle Environment
    Write-Host ""
    Write-Log -Message "========== Environment Erstellung ==========" -Level "Info"
    
    if ($usesConda) {
        if (-not (New-CondaEnvironment -CondaTool $condaInfo.Tool -EnvName $VENV_NAME -EnvPath $condaInfo.EnvPath)) {
            Write-Error-Custom "Installation abgebrochen"
            exit 1
        }
    }
    else {
        if (-not (New-VenvEnvironment -EnvName $VENV_NAME)) {
            Write-Error-Custom "Installation abgebrochen"
            exit 1
        }
    }
    
    # Schritt 5: Installiere Packages
    Write-Host ""
    Write-Log -Message "========== Package Installation ==========" -Level "Info"
    
    if (-not (Install-Packages -EnvName $VENV_NAME -CondaTool $condaInfo.Tool -UsesConda $usesConda)) {
        Write-Error-Custom "Installation abgebrochen"
        exit 1
    }
    
    # Schritt 6: Installiere ExifTool (optional)
    Write-Host ""
    Write-Log -Message "========== ExifTool Installation ==========" -Level "Info"
    if (-not $SkipExifCheck) {
        Test-ExifToolInstallation
    }
    else {
        Write-Log -Message "ExifTool Installation uebersprungen" -Level "Info"
    }
    
    # Schritt 7: Validiere Installation
    Write-Host ""
    Write-Log -Message "========== Validierung ==========" -Level "Info"
    
    if (Test-InstallationSuccess -EnvName $VENV_NAME -UsesConda $usesConda) {
        Write-Success "Installation erfolgreich validiert!"
    }
    else {
        Write-Error-Custom "Installation konnte nicht validiert werden"
        exit 1
    }
    
    # Schritt 8: Erstelle Shortcuts
    Create-ActivationScripts -EnvName $VENV_NAME -UsesConda $usesConda
    
    # Abschluss
    Write-Host ""
    Write-Host "======================================================" -ForegroundColor Green
    Write-Host "  Installation erfolgreich abgeschlossen!" -ForegroundColor Green
    Write-Host "======================================================" -ForegroundColor Green
    Write-Host ""
    
    if ($usesConda) {
        Write-Host "Aktiviere das Environment mit:" -ForegroundColor Yellow
        Write-Host "  conda activate $VENV_NAME" -ForegroundColor Cyan
    }
    else {
        Write-Host "Aktiviere das Environment mit:" -ForegroundColor Yellow
        Write-Host "  .\$VENV_NAME\Scripts\Activate.ps1" -ForegroundColor Cyan
        Write-Host "  oder:" -ForegroundColor Yellow
        Write-Host "  .\activate_env.bat" -ForegroundColor Cyan
    }
    
    Write-Host ""
    Write-Host "Starte die Anwendung mit:" -ForegroundColor Yellow
    Write-Host "  python RenameFiles.py" -ForegroundColor Cyan
    Write-Host ""
}

# ============================================================================
# Error Handling und Cleanup
# ============================================================================
$ErrorActionPreference = "Stop"

try {
    Main
}
catch {
    Write-Error-Custom "Kritischer Fehler: $_"
    Write-Error-Custom "Stack Trace: $($_.ScriptStackTrace)"
    exit 1
}
