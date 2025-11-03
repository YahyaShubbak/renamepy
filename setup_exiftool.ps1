# ============================================================================
# ExifTool Setup - Automatischer Download und Installation
# ============================================================================
# Dieses Skript laedt ExifTool herunter und entpackt es im Repository

param(
    [switch]$Force = $false,
    [switch]$Verbose = $false
)

$ErrorActionPreference = "Continue"

# ============================================================================
# Konfiguration
# ============================================================================
$PROJECT_ROOT = Split-Path -Parent $MyInvocation.MyCommand.Path
$EXIFTOOL_DIR = Join-Path $PROJECT_ROOT "exiftool-13.40_64"
$DOWNLOAD_DIR = Join-Path $PROJECT_ROOT "temp_download"

# Direkte SourceForge Download-URL (nicht Redirect-URL)
$SOURCEFORGE_URL = "https://sourceforge.net/projects/exiftool/files/exiftool-13.40_64.zip/download"
$DIRECT_URL = "https://downloads.sourceforge.net/project/exiftool/exiftool-13.40_64.zip"

# ============================================================================
# Hilfsfunktionen fuer farbige Ausgabe
# ============================================================================
function Write-ColorMessage {
    param(
        [string]$Message,
        [string]$Type = "Info"
    )
    
    $colors = @{
        Success = "Green"
        Error   = "Red"
        Info    = "Cyan"
        Warning = "Yellow"
    }
    
    $symbols = @{
        Success = "[OK]"
        Error   = "[FEHLER]"
        Info    = "[INFO]"
        Warning = "[WARNUNG]"
    }
    
    $color = $colors[$Type]
    $symbol = $symbols[$Type]
    
    Write-Host "$symbol $Message" -ForegroundColor $color
}

function Write-Success { param([string]$msg) Write-ColorMessage -Message $msg -Type "Success" }
function Write-Info { param([string]$msg) Write-ColorMessage -Message $msg -Type "Info" }
function Write-Warning-Custom { param([string]$msg) Write-ColorMessage -Message $msg -Type "Warning" }
function Write-Error-Custom { param([string]$msg) Write-ColorMessage -Message $msg -Type "Error" }

# ============================================================================
# Funktion: Prüfe ob ExifTool bereits existiert
# ============================================================================
function Test-ExifToolExists {
    if (Test-Path $EXIFTOOL_DIR) {
        # Pruehe beide moegliche exe Namen
        $exeFile1 = Join-Path $EXIFTOOL_DIR "exiftool.exe"
        $exeFile2 = Join-Path $EXIFTOOL_DIR "exiftool(-k).exe"
        
        $exeFile = if (Test-Path $exeFile1) { $exeFile1 } elseif (Test-Path $exeFile2) { $exeFile2 } else { $null }
        
        if ($exeFile) {
            Write-Success "ExifTool bereits vorhanden: $EXIFTOOL_DIR"
            Write-Success "Executable gefunden: $(Split-Path -Leaf $exeFile)"
            
            try {
                $version = & $exeFile -ver 2>&1
                Write-Info "Version: $version"
                return $true
            }
            catch {
                Write-Warning-Custom "Konnte Version nicht abrufen"
            }
        }
    }
    return $false
}

# ============================================================================
# Funktion: Download ExifTool
# ============================================================================
function Invoke-ExifToolDownload {
    Write-Info "Lade ExifTool herunter..."
    Write-Info "Quelle: $DIRECT_URL"
    
    # Erstelle Download-Verzeichnis
    if (-not (Test-Path $DOWNLOAD_DIR)) {
        New-Item -ItemType Directory -Path $DOWNLOAD_DIR | Out-Null
        Write-Info "Download-Verzeichnis erstellt"
    }
    
    $zipFile = Join-Path $DOWNLOAD_DIR "exiftool-13.40_64.zip"
    
    # Loesche alte ZIP falls vorhanden
    if (Test-Path $zipFile) {
        Remove-Item $zipFile -Force
    }
    
    try {
        Write-Info "Download laeuft (dies kann 1-2 Minuten dauern)..."
        
        # Setze TLS 1.2 fuer sichere Downloads
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        
        # Download mit WebClient (robuster als Invoke-WebRequest)
        $webClient = New-Object System.Net.WebClient
        $webClient.DownloadFile($DIRECT_URL, $zipFile)
        
        if (Test-Path $zipFile) {
            $fileSize = [math]::Round((Get-Item $zipFile).Length / 1MB, 2)
            
            if ($fileSize -lt 1.0) {
                Write-Error-Custom "Download zu klein ($fileSize MB) - moeglicherweise Fehler"
                Write-Info "Versuche alternative Download-Methode..."
                
                # Fallback: Invoke-WebRequest mit MaximumRedirection
                $ProgressPreference = 'SilentlyContinue'
                Invoke-WebRequest -Uri $SOURCEFORGE_URL -OutFile $zipFile -MaximumRedirection 10 -UseBasicParsing
                
                $fileSize = [math]::Round((Get-Item $zipFile).Length / 1MB, 2)
            }
            
            if ($fileSize -gt 10.0) {
                Write-Success "Download abgeschlossen ($fileSize MB)"
                return $zipFile
            }
            else {
                Write-Error-Custom "Download fehlgeschlagen - Datei zu klein ($fileSize MB)"
                Write-Info "Erwartete Groesse: ca. 11 MB"
                return $null
            }
        }
        else {
            Write-Error-Custom "Download fehlgeschlagen - Datei nicht erstellt"
            return $null
        }
    }
    catch {
        Write-Error-Custom "Download-Fehler: $($_.Exception.Message)"
        Write-Info "Pruefe Internetverbindung und Firewall-Einstellungen"
        Write-Info "Alternativer Download: https://exiftool.org/"
        return $null
    }
    finally {
        if ($webClient) {
            $webClient.Dispose()
        }
    }
}

# ============================================================================
# Funktion: Entpacke ExifTool ZIP
# ============================================================================
function Expand-ExifToolArchive {
    param([string]$ZipPath)
    
    Write-Info "Entpacke ExifTool..."
    
    try {
        # Entpacke in temp_download
        Expand-Archive -Path $ZipPath -DestinationPath $DOWNLOAD_DIR -Force
        Write-Success "ZIP entpackt"
        
        # Pruehe ob exiftool-13.40_64 Ordner im ZIP war
        $unpackedDir = Join-Path $DOWNLOAD_DIR "exiftool-13.40_64"
        
        if (-not (Test-Path $unpackedDir)) {
            Write-Error-Custom "exiftool-13.40_64 Ordner nicht gefunden nach Entpacken"
            Write-Info "Inhalte von temp_download:"
            Get-ChildItem $DOWNLOAD_DIR | ForEach-Object { Write-Info "  - $($_.Name)" }
            return $false
        }
        
        # Verschiebe direkt ins Repository (nicht verschachtelt!)
        if (Test-Path $EXIFTOOL_DIR) {
            Write-Warning-Custom "ExifTool-Ordner existiert bereits - loesche..."
            Remove-Item -Path $EXIFTOOL_DIR -Recurse -Force
        }
        
        Write-Info "Verschiebe exiftool-13.40_64 ins Repository..."
        Move-Item -Path $unpackedDir -Destination $EXIFTOOL_DIR -Force
        
        Write-Success "ExifTool installiert: $EXIFTOOL_DIR"
        
        # Pruehe beide moeglichen exe Namen
        $exeFile1 = Join-Path $EXIFTOOL_DIR "exiftool.exe"
        $exeFile2 = Join-Path $EXIFTOOL_DIR "exiftool(-k).exe"
        
        if (Test-Path $exeFile1) {
            Write-Success "exiftool.exe gefunden"
            return $true
        }
        elseif (Test-Path $exeFile2) {
            Write-Success "exiftool(-k).exe gefunden"
            
            # Kopiere zu exiftool.exe fuer einfachere Verwendung
            Copy-Item -Path $exeFile2 -Destination $exeFile1 -Force
            Write-Info "Kopiert nach exiftool.exe"
            return $true
        }
        else {
            Write-Error-Custom "Keine exiftool.exe gefunden"
            Write-Info "Inhalte von exiftool-13.40_64:"
            Get-ChildItem $EXIFTOOL_DIR | ForEach-Object { Write-Info "  - $($_.Name)" }
            return $false
        }
    }
    catch {
        Write-Error-Custom "Entpacken fehlgeschlagen: $($_.Exception.Message)"
        return $false
    }
}

# ============================================================================
# Funktion: Aufräumen
# ============================================================================
function Remove-TempDirectory {
    Write-Info "Raeume temporaere Dateien auf..."
    
    if (Test-Path $DOWNLOAD_DIR) {
        Remove-Item -Path $DOWNLOAD_DIR -Recurse -Force
        Write-Success "Temp-Verzeichnis geloescht"
    }
}

# ============================================================================
# Funktion: Prüfe ExifTool Funktionalität
# ============================================================================
function Test-ExifToolFunctionality {
    # Pruehe beide moegliche exe Namen
    $exeFile1 = Join-Path $EXIFTOOL_DIR "exiftool.exe"
    $exeFile2 = Join-Path $EXIFTOOL_DIR "exiftool(-k).exe"
    
    $exeFile = if (Test-Path $exeFile1) { $exeFile1 } elseif (Test-Path $exeFile2) { $exeFile2 } else { $null }
    
    if (-not $exeFile) {
        Write-Error-Custom "Keine exiftool.exe gefunden"
        return $false
    }
    
    try {
        Write-Info "Teste ExifTool..."
        $output = & $exeFile -ver 2>&1
        Write-Success "ExifTool Version: $output"
        Write-Success "Executable: $(Split-Path -Leaf $exeFile)"
        return $true
    }
    catch {
        Write-Error-Custom "ExifTool Test fehlgeschlagen: $($_.Exception.Message)"
        return $false
    }
}

# ============================================================================
# Hauptprogramm
# ============================================================================
function Main {
    Write-Host ""
    Write-Host "======================================================" -ForegroundColor Cyan
    Write-Host "  ExifTool Setup für RenamePy" -ForegroundColor Cyan
    Write-Host "======================================================" -ForegroundColor Cyan
    Write-Host ""
    
    Write-Info "Projekt-Verzeichnis: $PROJECT_ROOT"
    Write-Info "ExifTool Zielordner: $EXIFTOOL_DIR"
    Write-Host ""
    
    # Schritt 1: Prüfe ob bereits vorhanden
    if (Test-ExifToolExists) {
        if (-not $Force) {
            Write-Success "ExifTool bereits installiert und funktionsfähig"
            Write-Info "Für Neuinstallation nutze: .\setup_exiftool.ps1 -Force"
            return $true
        }
        else {
            Write-Warning-Custom "Force-Flag gesetzt - Installation wird überschrieben"
        }
    }
    
    # Schritt 2: Download
    $zipFile = Invoke-ExifToolDownload
    if (-not $zipFile) {
        Write-Error-Custom "Installation abgebrochen"
        return $false
    }
    
    # Schritt 3: Entpacken
    if (-not (Expand-ExifToolArchive -ZipPath $zipFile)) {
        Write-Error-Custom "Installation abgebrochen"
        return $false
    }
    
    # Schritt 4: Cleanup
    Remove-TempDirectory
    
    # Schritt 5: Validierung
    if (-not (Test-ExifToolFunctionality)) {
        Write-Error-Custom "ExifTool konnte nicht validiert werden"
        return $false
    }
    
    # Erfolg
    Write-Host ""
    Write-Host "======================================================" -ForegroundColor Green
    Write-Host "  ExifTool erfolgreich installiert!" -ForegroundColor Green
    Write-Host "======================================================" -ForegroundColor Green
    Write-Host ""
    
    Write-Host "ExifTool ist jetzt verfügbar unter:" -ForegroundColor Yellow
    Write-Host "  $EXIFTOOL_DIR" -ForegroundColor Cyan
    Write-Host ""
    
    Write-Host "Verwendung:" -ForegroundColor Yellow
    Write-Host "  exiftool.exe <bildatei>" -ForegroundColor Cyan
    Write-Host "  oder im Python-Code:" -ForegroundColor Cyan
    Write-Host "  exiftool = ExifTool('exiftool-13.40_64/exiftool.exe')" -ForegroundColor Cyan
    Write-Host ""
    
    return $true
}

# ============================================================================
# Ausfuehrung
# ============================================================================
try {
    $success = Main
    if ($success) {
        exit 0
    }
    else {
        Write-Host "[FEHLER] Setup fehlgeschlagen" -ForegroundColor Red
        exit 1
    }
}
catch {
    Write-Host "[FEHLER] Kritischer Fehler: $_" -ForegroundColor Red
    Write-Host "Stack Trace: $($_.ScriptStackTrace)" -ForegroundColor Red
    exit 1
}
