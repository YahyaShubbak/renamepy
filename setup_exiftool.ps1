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
$EXIFTOOL_DIR = Join-Path $PROJECT_ROOT "exiftool-13.40_64"
$DOWNLOAD_DIR = Join-Path $PROJECT_ROOT "temp_download"

# Direct SourceForge download URL (not a redirect URL)
$SOURCEFORGE_URL = "https://sourceforge.net/projects/exiftool/files/exiftool-13.40_64.zip/download"
$DIRECT_URL = "https://downloads.sourceforge.net/project/exiftool/exiftool-13.40_64.zip"

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
# Function: Check whether ExifTool already exists
# ============================================================================
function Test-ExifToolExists {
    if (Test-Path $EXIFTOOL_DIR) {
        # Check both possible exe names
        $exeFile1 = Join-Path $EXIFTOOL_DIR "exiftool.exe"
        $exeFile2 = Join-Path $EXIFTOOL_DIR "exiftool(-k).exe"
        
        $exeFile = if (Test-Path $exeFile1) { $exeFile1 } elseif (Test-Path $exeFile2) { $exeFile2 } else { $null }
        
        if ($exeFile) {
            Write-Success "ExifTool already present: $EXIFTOOL_DIR"
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
    Write-Info "Downloading ExifTool..."
    Write-Info "Source: $DIRECT_URL"
    
    # Create download directory
    if (-not (Test-Path $DOWNLOAD_DIR)) {
        New-Item -ItemType Directory -Path $DOWNLOAD_DIR | Out-Null
        Write-Info "Download directory created"
    }
    
    $zipFile = Join-Path $DOWNLOAD_DIR "exiftool-13.40_64.zip"
    
    # Remove old ZIP if present
    if (Test-Path $zipFile) {
        Remove-Item $zipFile -Force
    }
    
    try {
        Write-Info "Downloading (this may take 1-2 minutes)..."
        
        # Set TLS 1.2 for secure downloads
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        
        # Download with WebClient (more robust than Invoke-WebRequest)
        $webClient = New-Object System.Net.WebClient
        $webClient.DownloadFile($DIRECT_URL, $zipFile)
        
        if (Test-Path $zipFile) {
            $fileSize = [math]::Round((Get-Item $zipFile).Length / 1MB, 2)
            
            if ($fileSize -lt 1.0) {
                Write-Error-Custom "Download too small ($fileSize MB) - possible error"
                Write-Info "Trying alternative download method..."
                
                # Fallback: Invoke-WebRequest with MaximumRedirection
                $ProgressPreference = 'SilentlyContinue'
                Invoke-WebRequest -Uri $SOURCEFORGE_URL -OutFile $zipFile -MaximumRedirection 10 -UseBasicParsing
                
                $fileSize = [math]::Round((Get-Item $zipFile).Length / 1MB, 2)
            }
            
            if ($fileSize -gt 10.0) {
                Write-Success "Download completed ($fileSize MB)"
                return $zipFile
            }
            else {
                Write-Error-Custom "Download failed - file too small ($fileSize MB)"
                Write-Info "Expected size: approx. 11 MB"
                return $null
            }
        }
        else {
            Write-Error-Custom "Download failed - file not created"
            return $null
        }
    }
    catch {
        Write-Error-Custom "Download error: $($_.Exception.Message)"
        Write-Info "Check your internet connection and firewall settings"
        Write-Info "Alternative download: https://exiftool.org/"
        return $null
    }
    finally {
        if ($webClient) {
            $webClient.Dispose()
        }
    }
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
        
        # Check whether the exiftool-13.40_64 folder was inside the ZIP
        $unpackedDir = Join-Path $DOWNLOAD_DIR "exiftool-13.40_64"
        
        if (-not (Test-Path $unpackedDir)) {
            Write-Error-Custom "exiftool-13.40_64 folder not found after extraction"
            Write-Info "Contents of temp_download:"
            Get-ChildItem $DOWNLOAD_DIR | ForEach-Object { Write-Info "  - $($_.Name)" }
            return $false
        }
        
        # Move directly into the repository (not nested!)
        if (Test-Path $EXIFTOOL_DIR) {
            Write-Warning-Custom "ExifTool folder already exists - removing..."
            Remove-Item -Path $EXIFTOOL_DIR -Recurse -Force
        }
        
        Write-Info "Moving exiftool-13.40_64 into repository..."
        Move-Item -Path $unpackedDir -Destination $EXIFTOOL_DIR -Force
        
        Write-Success "ExifTool installed: $EXIFTOOL_DIR"
        
        # Check both possible exe names
        $exeFile1 = Join-Path $EXIFTOOL_DIR "exiftool.exe"
        $exeFile2 = Join-Path $EXIFTOOL_DIR "exiftool(-k).exe"
        
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
            Write-Info "Contents of exiftool-13.40_64:"
            Get-ChildItem $EXIFTOOL_DIR | ForEach-Object { Write-Info "  - $($_.Name)" }
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
    $exeFile1 = Join-Path $EXIFTOOL_DIR "exiftool.exe"
    $exeFile2 = Join-Path $EXIFTOOL_DIR "exiftool(-k).exe"
    
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
    Write-Info "ExifTool target folder: $EXIFTOOL_DIR"
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
    Write-Host "  $EXIFTOOL_DIR" -ForegroundColor Cyan
    Write-Host ""
    
    Write-Host "Usage:" -ForegroundColor Yellow
    Write-Host "  exiftool.exe <image_file>" -ForegroundColor Cyan
    Write-Host "  or in Python code:" -ForegroundColor Cyan
    Write-Host "  exiftool = ExifTool('exiftool-13.40_64/exiftool.exe')" -ForegroundColor Cyan
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
