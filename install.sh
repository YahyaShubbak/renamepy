#!/usr/bin/env bash
# ======================================================
#   RenamePy Installation Script v1.0.1  (Linux / macOS)
# ======================================================
#   - Checks Python 3
#   - Installs system dependencies (EGL/Qt6, ExifTool)
#   - Installs pip packages from requirements.txt
#   - Creates a desktop launcher (optional)
# ======================================================

set -euo pipefail

EXIFTOOL_VERSION="13.54"
EXIFTOOL_FOLDER="exiftool-${EXIFTOOL_VERSION}_64"
EXIFTOOL_ZIP="${EXIFTOOL_FOLDER}.zip"
EXIFTOOL_URL="https://exiftool.org/${EXIFTOOL_ZIP}"
EXIFTOOL_URL_FB="https://downloads.sourceforge.net/project/exiftool/${EXIFTOOL_ZIP}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── colour helpers ──────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
log_info()    { echo "[$(date '+%Y-%m-%d %H:%M:%S')] [Info]    $*"; }
log_success() { echo -e "[$(date '+%Y-%m-%d %H:%M:%S')] ${GREEN}[Success]${NC} $*"; }
log_warn()    { echo -e "[$(date '+%Y-%m-%d %H:%M:%S')] ${YELLOW}[Warning]${NC} $*"; }
log_err()     { echo -e "[$(date '+%Y-%m-%d %H:%M:%S')] ${RED}[Error]${NC}   $*" >&2; }

echo ""
echo "======================================================"
echo "  RenamePy Installation Script v1.0.1"
echo "======================================================"
echo ""

# -------------------------------------------------------
# 1. Detect OS / package manager
# -------------------------------------------------------
OS="$(uname -s)"
PKG_MGR=""
if   command -v apt-get  &>/dev/null; then PKG_MGR="apt"
elif command -v dnf      &>/dev/null; then PKG_MGR="dnf"
elif command -v pacman   &>/dev/null; then PKG_MGR="pacman"
elif command -v brew     &>/dev/null; then PKG_MGR="brew"
fi

# -------------------------------------------------------
# 2. Python check
# -------------------------------------------------------
log_info "Checking Python installation..."
PY=""
for cmd in python3 python; do
    if command -v "$cmd" &>/dev/null; then
        ver=$("$cmd" --version 2>&1)
        major=$("$cmd" -c "import sys; print(sys.version_info.major)")
        minor=$("$cmd" -c "import sys; print(sys.version_info.minor)")
        if [ "$major" -ge 3 ] && [ "$minor" -ge 9 ]; then
            PY="$cmd"
            break
        fi
    fi
done

if [ -z "$PY" ]; then
    log_err "Python 3.9+ not found."
    if [ "$PKG_MGR" = "apt" ]; then
        log_info "Install with: sudo apt-get install python3 python3-pip"
    elif [ "$PKG_MGR" = "dnf" ]; then
        log_info "Install with: sudo dnf install python3 python3-pip"
    fi
    exit 1
fi

PY_PATH=$("$PY" -c "import sys; print(sys.executable)")
log_success "Python found: $($PY --version 2>&1)"
log_info    "  Path: $PY_PATH"

# requirements.txt
if [ -f "$SCRIPT_DIR/requirements.txt" ]; then
    log_success "requirements.txt found"
else
    log_warn "requirements.txt not found"
fi

# -------------------------------------------------------
# 3. System dependencies
# -------------------------------------------------------
echo ""
log_info "========== System Dependencies =========="

install_system_deps() {
    case "$PKG_MGR" in
        apt)
            log_info "Installing Qt/EGL system libraries via apt..."
            sudo apt-get update -qq
            sudo apt-get install -y --no-install-recommends \
                libegl1 libgl1-mesa-dri libgles2-mesa-dev \
                libxkbcommon0 libxcb-xinerama0 \
                libimage-exiftool-perl \
                wget unzip 2>/dev/null || true
            ;;
        dnf)
            log_info "Installing system libraries via dnf..."
            sudo dnf install -y \
                mesa-libEGL mesa-libGL \
                libxkbcommon perl-Image-ExifTool \
                wget unzip 2>/dev/null || true
            ;;
        pacman)
            log_info "Installing system libraries via pacman..."
            sudo pacman -Sy --noconfirm \
                mesa libxkbcommon perl-image-exiftool \
                wget unzip 2>/dev/null || true
            ;;
        brew)
            log_info "Installing via Homebrew..."
            brew install exiftool wget 2>/dev/null || true
            ;;
        *)
            log_warn "Unknown package manager – skipping system package install"
            ;;
    esac
}

install_system_deps
log_success "System dependency step complete"

# -------------------------------------------------------
# 4. Python packages
# -------------------------------------------------------
echo ""
log_info "========== Package Installation =========="
log_info "Upgrading pip..."
"$PY" -m pip install --upgrade pip --quiet

if [ -f "$SCRIPT_DIR/requirements.txt" ]; then
    log_info "Installing Python packages from requirements.txt..."
    "$PY" -m pip install -r "$SCRIPT_DIR/requirements.txt"
    log_success "Packages successfully installed"
else
    log_warn "Skipping pip install – requirements.txt not found"
fi

# -------------------------------------------------------
# 5. ExifTool (binary fallback when package not found)
# -------------------------------------------------------
echo ""
log_info "========== ExifTool Installation =========="
log_info "Checking ExifTool installation..."

EXIF_TARGET="$SCRIPT_DIR/$EXIFTOOL_FOLDER"
EXIF_FOUND=0

# Check if installed via package manager
if command -v exiftool &>/dev/null; then
    log_success "ExifTool already available: $(exiftool -ver 2>/dev/null || echo '(version unknown)')"
    EXIF_FOUND=1
elif [ -f "$EXIF_TARGET/exiftool" ]; then
    log_success "ExifTool already installed in $EXIF_TARGET"
    EXIF_FOUND=1
fi

if [ "$EXIF_FOUND" -eq 0 ]; then
    log_warn "ExifTool is not installed"
    log_info "ExifTool is optional for extended EXIF functions."
    echo ""
    echo "Would you like to automatically download and install ExifTool?"
    echo "  [Y] Yes, automatically download (~10 MB)"
    echo "  [N] No, install manually later"
    read -r -p "Your choice (Y/N): " DL_CHOICE

    if [[ "$DL_CHOICE" =~ ^[Yy]$ ]]; then
        log_info "Downloading ExifTool $EXIFTOOL_VERSION..."
        ZIP_TMP="/tmp/$EXIFTOOL_ZIP"
        DL_OK=0

        for url in "$EXIFTOOL_URL" "$EXIFTOOL_URL_FB"; do
            log_info "Source: $url"
            if command -v wget &>/dev/null; then
                wget -q --show-progress -O "$ZIP_TMP" "$url" && DL_OK=1 && break
            elif command -v curl &>/dev/null; then
                curl -L --progress-bar -o "$ZIP_TMP" "$url" && DL_OK=1 && break
            fi
            log_warn "Download failed from $url, trying next..."
        done

        if [ "$DL_OK" -eq 1 ]; then
            log_info "Extracting archive..."
            if command -v unzip &>/dev/null; then
                unzip -q "$ZIP_TMP" -d "$SCRIPT_DIR"
            else
                log_warn "unzip not found – trying python..."
                "$PY" -c "import zipfile, sys; zipfile.ZipFile('$ZIP_TMP').extractall('$SCRIPT_DIR')"
            fi
            rm -f "$ZIP_TMP"

            # Make executable
            find "$EXIF_TARGET" -type f -name "exiftool" -exec chmod +x {} \;
            log_success "ExifTool installed to $EXIF_TARGET"
        else
            log_err "Download failed from all sources."
            echo "Please download ExifTool manually:"
            echo "  $EXIFTOOL_URL"
            echo "Then extract the '$EXIFTOOL_FOLDER' folder into:"
            echo "  $SCRIPT_DIR"
        fi
    else
        log_warn "ExifTool installation skipped"
        log_info "Manual install: $EXIFTOOL_URL"
    fi
fi

# -------------------------------------------------------
# 6. Desktop shortcut / launcher (optional)
# -------------------------------------------------------
echo ""
log_info "========== Desktop Shortcut =========="
echo "Would you like to create a Desktop shortcut for RenamePy?"
echo "  [Y] Yes, create shortcut"
echo "  [N] No"
read -r -p "Your choice (Y/N): " SC_CHOICE

if [[ "$SC_CHOICE" =~ ^[Yy]$ ]]; then
    ICON_PATH="$SCRIPT_DIR/icon.ico"
    DESKTOP_FILE=""

    if [ "$OS" = "Linux" ]; then
        # Try XDG desktop directory first, then ~/Desktop
        XDG_DESK="${XDG_DESKTOP_DIR:-}"
        if [ -z "$XDG_DESK" ] && command -v xdg-user-dir &>/dev/null; then
            XDG_DESK="$(xdg-user-dir DESKTOP 2>/dev/null || echo '')"
        fi
        DESK_DIR="${XDG_DESK:-$HOME/Desktop}"

        mkdir -p "$DESK_DIR"
        DESKTOP_FILE="$DESK_DIR/RenamePy.desktop"

        cat > "$DESKTOP_FILE" << EOF
[Desktop Entry]
Version=1.0
Name=RenamePy
Comment=Photo File Renamer
Exec=$PY "$SCRIPT_DIR/RenameFiles.py"
Icon=$ICON_PATH
Terminal=false
Type=Application
Categories=Graphics;Photography;
StartupWMClass=RenameFiles
EOF
        chmod +x "$DESKTOP_FILE"
        # Trust the launcher if gio is available (GNOME)
        if command -v gio &>/dev/null; then
            gio set "$DESKTOP_FILE" metadata::trusted true 2>/dev/null || true
        fi
        log_success "Desktop shortcut created: $DESKTOP_FILE"

        # Also install to applications menu
        APP_DIR="$HOME/.local/share/applications"
        mkdir -p "$APP_DIR"
        cp "$DESKTOP_FILE" "$APP_DIR/RenamePy.desktop" 2>/dev/null && \
            log_success "Application menu entry created: $APP_DIR/RenamePy.desktop" || true

    elif [ "$OS" = "Darwin" ]; then
        # macOS: create a simple shell-script app bundle or alias
        DESK_DIR="$HOME/Desktop"
        LAUNCHER="$DESK_DIR/RenamePy.command"
        cat > "$LAUNCHER" << EOF
#!/usr/bin/env bash
cd "$SCRIPT_DIR"
exec "$PY" "$SCRIPT_DIR/RenameFiles.py"
EOF
        chmod +x "$LAUNCHER"
        log_success "Desktop launcher created: $LAUNCHER"
    else
        log_warn "Desktop shortcut not supported on this OS ($OS)"
    fi
else
    log_info "Desktop shortcut skipped"
fi

# -------------------------------------------------------
# 7. Validation
# -------------------------------------------------------
echo ""
log_info "========== Validation =========="
log_info "Validating installation..."

VALID=1
if [ -f "$SCRIPT_DIR/RenameFiles.py" ]; then
    log_success "RenameFiles.py found"
else
    log_warn "RenameFiles.py missing"
    VALID=0
fi

if "$PY" -c "import PyQt6" &>/dev/null; then
    log_success "PyQt6 import OK"
else
    log_warn "PyQt6 import failed – check pip installation"
    VALID=0
fi

if [ "$VALID" -eq 1 ]; then
    log_success "Installation successfully validated!"
else
    log_warn "Validation completed with warnings"
fi

echo ""
echo "======================================================"
echo "  Installation completed!"
echo "======================================================"
echo ""
echo "Start the application with:"
echo "  cd \"$SCRIPT_DIR\""
echo "  $PY RenameFiles.py"
echo ""
echo "[SUCCESS] Installation completed"
