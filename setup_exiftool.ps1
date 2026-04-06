# ============================================================================
# ExifTool Setup - Automatic Download and Installation
# ============================================================================
# This script downloads ExifTool and extracts it into the repository.

param(
    [switch]$Force = $false,
    [switch]$Verbose = $false
)

$ErrorActionPreference = "Continue"

# ============================================================================
# Configuration
# ============================================================================
$PROJECT_ROOT = Split-Path -Parent $MyInvocation.MyCommand.Path

# ExifTool architecture
$EXIFTOOL_ARCH = "64"

$DOWNLOAD_DIR = Join-Path $PROJECT_ROOT "temp_download"

# ============================================================================
# Helper functions for coloured output
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
        Error   = "[ERROR]"
        Info    = "[INFO]"
        Warning = "[WARNING]"
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
# Function: Resolve latest ExifTool version and build download URLs
# ============================================================================
function Get-ExifToolLatestVersion {
    Write-Info "Detecting latest ExifTool version from exiftool.org..."
    try {
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        $html = (Invoke-WebRequest -Uri 'https://exiftool.org/' -UseBasicParsing -TimeoutSec 20).Content
        $match = [regex]::Match($html, 'exiftool-([\.\d]+)_64\.zip')
        if ($match.Success) {
            $version = $match.Groups[1].Value
            Write-Info "Latest version detected: $version"
            return $version
        }
    }
    catch {
        Write-Warning-Custom "Could not detect version online: $($_.Exception.Message)"
    }

    # Fallback to a known-good version
    $fallback = "13.54"
    Write-Warning-Custom "Falling back to version $fallback"
    return $fallback
}

# ============================================================================
# Function: Initialise version-dependent globals (called once in Main)
# ============================================================================
$script:EXIFTOOL_VERSION = $null
$script:EXIFTOOL_FOLDER  = $null
$script:EXIFTOOL_ZIP     = $null
$script:EXIFTOOL_DIR     = $null
$script:DOWNLOAD_URLS    = @()

function Initialize-ExifToolGlobals {
    $script:EXIFTOOL_VERSION = Get-ExifToolLatestVersion
    $script:EXIFTOOL_FOLDER  = "exiftool-$($script:EXIFTOOL_VERSION)_${EXIFTOOL_ARCH}"
    $script:EXIFTOOL_ZIP     = "$($script:EXIFTOOL_FOLDER).zip"
    $script:EXIFTOOL_DIR     = Join-Path $PROJECT_ROOT $script:EXIFTOOL_FOLDER
    $script:DOWNLOAD_URLS    = @(
        "https://exiftool.org/$($script:EXIFTOOL_ZIP)"
    )
}

# ============================================================================
# Function: Check whether ExifTool already exists
# ============================================================================
function Test-ExifToolExists {
    if (Test-Path $script:EXIFTOOL_DIR) {
        # Check both possible exe names
        $exeFile1 = Join-Path $script:EXIFTOOL_DIR "exiftool.exe"
        $exeFile2 = Join-Path $script:EXIFTOOL_DIR "exiftool(-k).exe"
        
        $exeFile = if (Test-Path $exeFile1) { $exeFile1 } elseif (Test-Path $exeFile2) { $exeFile2 } else { $null }
        
        if ($exeFile) {
            Write-Success "ExifTool already present: $($script:EXIFTOOL_DIR)"
            Write-Success "Executable found: $(Split-Path -Leaf $exeFile)"
            
            try {
                $version = & $exeFile -ver 2>&1
                Write-Info "Version: $version"
                return $true
            }
            catch {
                Write-Warning-Custom "Could not retrieve version"
            }
        }
    }
    return $false
}

# ============================================================================
# Function: Download ExifTool
# ============================================================================
function Invoke-ExifToolDownload {
    Write-Info "Downloading ExifTool $($script:EXIFTOOL_VERSION)..."
    
    # Create download directory
    if (-not (Test-Path $DOWNLOAD_DIR)) {
        New-Item -ItemType Directory -Path $DOWNLOAD_DIR | Out-Null
        Write-Info "Download directory created"
    }
    
    $zipFile = Join-Path $DOWNLOAD_DIR $script:EXIFTOOL_ZIP
    
    # Remove old ZIP if present
    if (Test-Path $zipFile) {
        Remove-Item $zipFile -Force
    }
    
    # Set TLS 1.2 for secure downloads
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    
    foreach ($url in $script:DOWNLOAD_URLS) {
        try {
            Write-Info "Trying: $url"
            
            $ProgressPreference = 'SilentlyContinue'
            Invoke-WebRequest -Uri $url -OutFile $zipFile -MaximumRedirection 10 -UseBasicParsing -TimeoutSec 60
            
            if (Test-Path $zipFile) {
                $fileSize = [math]::Round((Get-Item $zipFile).Length / 1MB, 2)
                
                if ($fileSize -gt 5.0) {
                    Write-Success "Download completed ($fileSize MB)"
                    return $zipFile
                }
                else {
                    Write-Warning-Custom "Download too small ($fileSize MB), trying next URL..."
                    Remove-Item $zipFile -Force -ErrorAction SilentlyContinue
                }
            }
        }
        catch {
            Write-Warning-Custom "Failed: $($_.Exception.Message)"
        }
    }
    
        Write-Warning-Custom "All download URLs failed."
        Write-Info "Please download ExifTool manually from: https://exiftool.org/"
        Write-Info "Extract the ZIP into the project folder: $PROJECT_ROOT"
        return $null
}

# ============================================================================
# Function: Extract ExifTool ZIP
# ============================================================================
function Expand-ExifToolArchive {
    param([string]$ZipPath)
    
    Write-Info "Extracting ExifTool..."
    
    try {
        # Extract into temp_download
        Expand-Archive -Path $ZipPath -DestinationPath $DOWNLOAD_DIR -Force
        Write-Success "ZIP extracted"
        
        # Check whether the exiftool folder was inside the ZIP
        $unpackedDir = Join-Path $DOWNLOAD_DIR $script:EXIFTOOL_FOLDER
        
        if (-not (Test-Path $unpackedDir)) {
            Write-Error-Custom "$($script:EXIFTOOL_FOLDER) folder not found after extraction"
            Write-Info "Contents of temp_download:"
            Get-ChildItem $DOWNLOAD_DIR | ForEach-Object { Write-Info "  - $($_.Name)" }
            return $false
        }
        
        # Move directly into the repository (not nested!)
        if (Test-Path $script:EXIFTOOL_DIR) {
            Write-Warning-Custom "ExifTool folder already exists - removing..."
            Remove-Item -Path $script:EXIFTOOL_DIR -Recurse -Force
        }
        
        Write-Info "Moving $($script:EXIFTOOL_FOLDER) into repository..."
        Move-Item -Path $unpackedDir -Destination $script:EXIFTOOL_DIR -Force
        
        Write-Success "ExifTool installed: $($script:EXIFTOOL_DIR)"
        
        # Check both possible exe names
        $exeFile1 = Join-Path $script:EXIFTOOL_DIR "exiftool.exe"
        $exeFile2 = Join-Path $script:EXIFTOOL_DIR "exiftool(-k).exe"
        
        if (Test-Path $exeFile1) {
            Write-Success "exiftool.exe found"
            return $true
        }
        elseif (Test-Path $exeFile2) {
            Write-Success "exiftool(-k).exe found"
            
            # Copy to exiftool.exe for easier usage
            Copy-Item -Path $exeFile2 -Destination $exeFile1 -Force
            Write-Info "Copied to exiftool.exe"
            return $true
        }
        else {
            Write-Error-Custom "No exiftool.exe found"
            Write-Info "Contents of $($script:EXIFTOOL_FOLDER):"
            Get-ChildItem $script:EXIFTOOL_DIR | ForEach-Object { Write-Info "  - $($_.Name)" }
            return $false
        }
    }
    catch {
        Write-Error-Custom "Extraction failed: $($_.Exception.Message)"
        return $false
    }
}

# ============================================================================
# Function: Clean up temporary files
# ============================================================================
function Remove-TempDirectory {
    Write-Info "Cleaning up temporary files..."
    
    if (Test-Path $DOWNLOAD_DIR) {
        Remove-Item -Path $DOWNLOAD_DIR -Recurse -Force
        Write-Success "Temporary directory removed"
    }
}

# ============================================================================
# Function: Verify ExifTool functionality
# ============================================================================
function Test-ExifToolFunctionality {
    # Check both possible exe names
    $exeFile1 = Join-Path $script:EXIFTOOL_DIR "exiftool.exe"
    $exeFile2 = Join-Path $script:EXIFTOOL_DIR "exiftool(-k).exe"
    
    $exeFile = if (Test-Path $exeFile1) { $exeFile1 } elseif (Test-Path $exeFile2) { $exeFile2 } else { $null }
    
    if (-not $exeFile) {
        Write-Error-Custom "No exiftool.exe found"
        return $false
    }
    
    try {
        Write-Info "Testing ExifTool..."
        $output = & $exeFile -ver 2>&1
        Write-Success "ExifTool version: $output"
        Write-Success "Executable: $(Split-Path -Leaf $exeFile)"
        return $true
    }
    catch {
        Write-Error-Custom "ExifTool test failed: $($_.Exception.Message)"
        return $false
    }
}

# ============================================================================
# Main
# ============================================================================
function Main {
    Write-Host ""
    Write-Host "======================================================" -ForegroundColor Cyan
    Write-Host "  ExifTool Setup for RenamePy" -ForegroundColor Cyan
    Write-Host "======================================================" -ForegroundColor Cyan
    Write-Host ""
    
    Write-Info "Project directory: $PROJECT_ROOT"
    Write-Host ""

    # Resolve version and globals first
    Initialize-ExifToolGlobals

    Write-Info "ExifTool target folder: $($script:EXIFTOOL_DIR)"
    Write-Host ""
    
    # Step 1: Check whether already present
    if (Test-ExifToolExists) {
        if (-not $Force) {
            Write-Success "ExifTool already installed and functional"
            Write-Info "To reinstall use: .\setup_exiftool.ps1 -Force"
            return $true
        }
        else {
            Write-Warning-Custom "Force flag set - installation will be overwritten"
        }
    }
    
    # Step 2: Download
    $zipFile = Invoke-ExifToolDownload
    if (-not $zipFile) {
        Write-Error-Custom "Installation aborted"
        return $false
    }
    
    # Step 3: Extract
    if (-not (Expand-ExifToolArchive -ZipPath $zipFile)) {
        Write-Error-Custom "Installation aborted"
        return $false
    }
    
    # Step 4: Cleanup
    Remove-TempDirectory
    
    # Step 5: Validation
    if (-not (Test-ExifToolFunctionality)) {
        Write-Error-Custom "ExifTool could not be validated"
        return $false
    }
    
    # Success
    Write-Host ""
    Write-Host "======================================================" -ForegroundColor Green
    Write-Host "  ExifTool successfully installed!" -ForegroundColor Green
    Write-Host "======================================================" -ForegroundColor Green
    Write-Host ""
    
    Write-Host "ExifTool is now available at:" -ForegroundColor Yellow
    Write-Host "  $($script:EXIFTOOL_DIR)" -ForegroundColor Cyan
    Write-Host ""
    
    Write-Host "Usage:" -ForegroundColor Yellow
    Write-Host "  exiftool.exe <image_file>" -ForegroundColor Cyan
    Write-Host "  or in Python code:" -ForegroundColor Cyan
    Write-Host "  exiftool = ExifTool('$($script:EXIFTOOL_FOLDER)/exiftool.exe')" -ForegroundColor Cyan
    Write-Host ""
    
    return $true
}

# ============================================================================
# Execution
# ============================================================================
try {
    $success = Main
    if ($success) {
        exit 0
    }
    else {
        Write-Host "[ERROR] Setup failed" -ForegroundColor Red
        exit 1
    }
}
catch {
    Write-Host "[ERROR] Critical error: $_" -ForegroundColor Red
    Write-Host "Stack trace: $($_.ScriptStackTrace)" -ForegroundColor Red
    exit 1
}
