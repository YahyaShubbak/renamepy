#!/bin/bash
# ============================================================================
#  RenamePy - Automated Installation Script (Linux/macOS)
#  Creates a virtual environment with all required dependencies
# ============================================================================

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
ORANGE='\033[38;5;208m'
NC='\033[0m' # No Color
BOLD='\033[1m'

LINE="==============================================================================="

# Helper functions
print_header()  { echo -e "${ORANGE}${LINE}${NC}"; }
print_ok()      { echo -e "  ${GREEN}[OK]${NC} $1"; }
print_error()   { echo -e "  ${RED}[ERROR]${NC} $1"; }
print_warning() { echo -e "  ${YELLOW}[WARNING]${NC} $1"; }
print_info()    { echo -e "  ${ORANGE}[INFO]${NC} $1"; }

# Ask user to confirm a step. Default is YES (Enter = proceed).
# Usage: confirm_step "Step name" "Description" || exit 1
confirm_step() {
    local step="$1"
    local desc="${2:-}"
    echo ""
    echo -e " The following step will be performed:"
    echo -e "   ${ORANGE}${step}${NC}"
    if [ -n "$desc" ]; then
        echo -e "   ${desc}"
    fi
    echo ""
    read -r -p " Do you want to continue? [[Y]/n]: " _resp
    if [[ "$_resp" =~ ^[Nn]$ ]]; then
        print_warning "Aborted by user."
        return 1
    fi
    return 0
}

# ============================================================================
#  Welcome
# ============================================================================
clear
echo -e "${ORANGE}"
cat << "EOF"
===============================================================================

   ██████╗ ███████╗███╗   ██╗ █████╗ ███╗   ███╗███████╗██████╗ ██╗   ██╗
   ██╔══██╗██╔════╝████╗  ██║██╔══██╗████╗ ████║██╔════╝██╔══██╗╚██╗ ██╔╝
   ██████╔╝█████╗  ██╔██╗ ██║███████║██╔████╔██║█████╗  ██████╔╝ ╚████╔╝ 
   ██╔══██╗██╔══╝  ██║╚██╗██║██╔══██║██║╚██╔╝██║██╔══╝  ██╔═══╝   ╚██╔╝  
   ██║  ██║███████╗██║ ╚████║██║  ██║██║ ╚═╝ ██║███████╗██║        ██║   
   ╚═╝  ╚═╝╚══════╝╚═╝  ╚═══╝╚═╝  ╚═╝╚═╝     ╚═╝╚══════╝╚═╝        ╚═╝   

===============================================================================
EOF
echo -e "${NC}"

echo -e " Welcome to the RenamePy installation assistant!"
echo ""
echo -e " This script will:"
echo ""
echo -e "   1. Install system dependencies (Qt6 libraries, ExifTool)"
echo -e "   2. Detect Conda or fall back to Python venv"
echo -e "   3. Create a virtual environment 'renamepy'"
echo -e "   4. Install all required Python packages"
echo -e "   5. Verify the installation"
echo -e "   6. Optional: Create a desktop shortcut"
echo ""
echo -e " Required Python packages:"
echo -e "   - PyQt6 (GUI Framework)"
echo -e "   - PyExifTool (EXIF metadata extraction)"
echo ""
print_header
echo ""
read -r -p " Press Enter to continue..."

# ============================================================================
#  Step 1: System Dependencies
# ============================================================================
echo ""
echo -e "${BOLD}[1/6] Checking system dependencies...${NC}"
echo ""

# Install missing packages with the given package manager command.
# Failure is reported but not fatal: the Python part can still be set up.
install_missing() {
    local manager="$1"; shift
    local install_cmd="$1"; shift
    local pkgs=("$@")
    if [ ${#pkgs[@]} -eq 0 ]; then
        print_ok "All required system packages are installed."
        return 0
    fi
    print_warning "Missing system packages: ${pkgs[*]}"
    read -r -p "  Install them now with ${manager}? [[Y]/n]: " DO_INSTALL
    if [[ ! "$DO_INSTALL" =~ ^[Nn]$ ]]; then
        # shellcheck disable=SC2086  # install_cmd is a trusted command line
        if sudo $install_cmd "${pkgs[@]}"; then
            print_ok "System packages installed."
        else
            print_warning "Installing system packages failed - Qt6/ExifTool may not work."
        fi
    else
        print_warning "Skipped. Qt6/ExifTool may not work without these."
    fi
}

install_system_deps() {
    local MISSING_PKGS=()

    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS: PyQt6 wheels bundle Qt; only ExifTool is needed (Homebrew)
        if command -v exiftool &>/dev/null; then
            :
        elif command -v brew &>/dev/null; then
            read -r -p "  ExifTool is missing. Install it with Homebrew (brew install exiftool)? [[Y]/n]: " DO_INSTALL
            if [[ ! "$DO_INSTALL" =~ ^[Nn]$ ]]; then
                brew install exiftool || print_warning "brew install exiftool failed."
            fi
        else
            print_warning "ExifTool not found and Homebrew is not installed."
            print_info "Install ExifTool from https://exiftool.org (macOS package) or via https://brew.sh"
        fi

    elif [[ "$OSTYPE" != "linux-gnu"* ]]; then
        print_info "Unknown OS ($OSTYPE), skipping system dependency check."
        return 0

    elif command -v pacman &>/dev/null; then
        # Arch Linux / EndeavourOS / Manjaro
        print_info "Detected Arch-based system (pacman)"
        local ARCH_DEPS=("mesa" "libxcb" "xcb-util" "xcb-util-wm" "xcb-util-image" \
                         "xcb-util-keysyms" "xcb-util-renderutil" "xcb-util-cursor" \
                         "libxkbcommon" "libxkbcommon-x11" "fontconfig" "freetype2" \
                         "dbus" "libglvnd" "perl-image-exiftool")
        for pkg in "${ARCH_DEPS[@]}"; do
            pacman -Qi "$pkg" &>/dev/null || MISSING_PKGS+=("$pkg")
        done
        install_missing pacman "pacman -S --needed --noconfirm" "${MISSING_PKGS[@]}"

    elif command -v apt-get &>/dev/null; then
        # Debian / Ubuntu / Mint
        print_info "Detected Debian/Ubuntu-based system (apt)"
        # python3-venv: Debian/Ubuntu ship Python without the venv module
        local DEB_DEPS=("python3-venv" "libgl1" "libegl1" "libxcb-xinerama0" "libxcb-cursor0" \
                        "libxcb-shape0" "libxcb-icccm4" "libxcb-image0" \
                        "libxcb-keysyms1" "libxcb-render-util0" "libxkbcommon0" \
                        "libxkbcommon-x11-0" "libfontconfig1" "libfreetype6" \
                        "libdbus-1-3" "libimage-exiftool-perl")
        for pkg in "${DEB_DEPS[@]}"; do
            dpkg -s "$pkg" &>/dev/null || MISSING_PKGS+=("$pkg")
        done
        if [ ${#MISSING_PKGS[@]} -gt 0 ]; then
            sudo apt-get update || true
        fi
        install_missing apt "apt-get install -y" "${MISSING_PKGS[@]}"

    elif command -v dnf &>/dev/null; then
        # Fedora / RHEL-based
        print_info "Detected Fedora/RHEL-based system (dnf)"
        local RPM_DEPS=("perl-Image-ExifTool" "mesa-libGL" "mesa-libEGL" "libxkbcommon-x11" \
                        "xcb-util-cursor" "xcb-util-wm" "xcb-util-image" \
                        "xcb-util-keysyms" "xcb-util-renderutil")
        for pkg in "${RPM_DEPS[@]}"; do
            rpm -q "$pkg" &>/dev/null || MISSING_PKGS+=("$pkg")
        done
        install_missing dnf "dnf install -y" "${MISSING_PKGS[@]}"

    elif command -v zypper &>/dev/null; then
        # openSUSE
        print_info "Detected openSUSE (zypper)"
        local SUSE_DEPS=("exiftool" "Mesa-libGL1" "Mesa-libEGL1" "libxkbcommon-x11-0" \
                         "libxcb-cursor0" "libxcb-icccm4" "libxcb-image0" \
                         "libxcb-keysyms1" "libxcb-render-util0")
        for pkg in "${SUSE_DEPS[@]}"; do
            rpm -q "$pkg" &>/dev/null || MISSING_PKGS+=("$pkg")
        done
        install_missing zypper "zypper --non-interactive install" "${MISSING_PKGS[@]}"

    else
        print_warning "Could not detect package manager (pacman/apt/dnf/zypper)."
        print_info "Please ensure Qt6 libraries and exiftool are installed."
    fi

    # Verify exiftool is available after installation
    if command -v exiftool &>/dev/null; then
        local EXIF_VER
        EXIF_VER=$(exiftool -ver 2>/dev/null || echo "unknown")
        print_ok "ExifTool found: version $EXIF_VER"
    else
        print_warning "ExifTool not found in PATH."
        print_info "The app will still work, but EXIF features will be limited."
    fi
}

install_system_deps
echo ""

# ============================================================================
#  Step 2: Detect Python environment manager (Conda or venv)
# ============================================================================
echo -e "${BOLD}[2/6] Detecting Python environment manager...${NC}"
echo ""

USE_CONDA=false
CONDA_EXE=""
ENV_NAME="renamepy"

# Check common conda locations
CONDA_LOCATIONS=(
    "$HOME/miniconda3/bin/conda"
    "$HOME/anaconda3/bin/conda"
    "$HOME/.miniconda3/bin/conda"
    "$HOME/.anaconda3/bin/conda"
    "/opt/miniconda3/bin/conda"
    "/opt/anaconda3/bin/conda"
    "/usr/local/miniconda3/bin/conda"
    "/usr/local/anaconda3/bin/conda"
    "$HOME/opt/miniconda3/bin/conda"
    "$HOME/opt/anaconda3/bin/conda"
)

for loc in "${CONDA_LOCATIONS[@]}"; do
    if [ -x "$loc" ]; then
        CONDA_EXE="$loc"
        break
    fi
done

# Try PATH
if [ -z "$CONDA_EXE" ]; then
    CONDA_EXE=$(command -v conda 2>/dev/null || true)
fi

if [ -n "$CONDA_EXE" ] && [ -x "$CONDA_EXE" ]; then
    print_ok "Conda found: $CONDA_EXE"
    echo ""
    echo -e "  Choose environment type:"
    echo -e "    ${ORANGE}[1]${NC} Conda environment (recommended if you use conda)"
    echo -e "    ${ORANGE}[2]${NC} Python venv (lightweight, no conda needed)"
    echo ""
    read -r -p "  Your choice [[1]/2]: " ENV_CHOICE
    if [[ "$ENV_CHOICE" == "2" ]]; then
        print_info "Using Python venv."
    else
        USE_CONDA=true
        CONDA_BASE=$(dirname "$(dirname "$CONDA_EXE")")
        # shellcheck disable=SC1091
        source "$CONDA_BASE/etc/profile.d/conda.sh"
        print_info "Using Conda."
    fi
else
    print_info "Conda not found. Using Python venv."
fi

if [ "$USE_CONDA" != true ]; then
    # Find a Python >= 3.10 (e.g. macOS' /usr/bin/python3 is 3.9)
    PYTHON_BIN=""
    for candidate in python3.13 python3.12 python3.11 python3.10 python3; do
        if command -v "$candidate" &>/dev/null && \
           "$candidate" -c 'import sys; sys.exit(sys.version_info < (3, 10))' 2>/dev/null; then
            PYTHON_BIN="$(command -v "$candidate")"
            break
        fi
    done
    if [ -z "$PYTHON_BIN" ]; then
        print_error "No Python 3.10 or newer found!"
        if [[ "$OSTYPE" == "darwin"* ]]; then
            print_info "Install one with: brew install python@3.12"
        fi
        exit 1
    fi
    PYTHON_VER=$("$PYTHON_BIN" --version 2>&1)
    print_ok "Python found: $PYTHON_VER ($PYTHON_BIN)"
fi
echo ""

# ============================================================================
#  Step 3: Create virtual environment
# ============================================================================
echo -e "${BOLD}[3/6] Setting up virtual environment '$ENV_NAME'...${NC}"
echo ""

if [ "$USE_CONDA" = true ]; then
    # --- Conda path ---
    if conda env list | grep -q "^${ENV_NAME} "; then
        print_warning "Conda environment '$ENV_NAME' already exists."
        echo ""
        read -r -p "  Recreate it? All changes will be lost! [y/[N]]: " RECREATE
        # Default (Enter) is No: only an explicit "y" deletes the environment
        if [[ "$RECREATE" =~ ^[Yy]$ ]]; then
            echo "  Removing existing environment..."
            conda remove -n "$ENV_NAME" --all -y
            print_ok "Old environment removed."
            echo ""
            echo "  Creating new environment..."
            conda create -n "$ENV_NAME" python=3.12 -y
            print_ok "Environment created."
        else
            print_info "Keeping existing environment. Will update packages."
        fi
    else
        echo "  Creating Conda environment '$ENV_NAME' with Python 3.12..."
        conda create -n "$ENV_NAME" python=3.12 -y
        print_ok "Environment created."
    fi
    conda activate "$ENV_NAME"

else
    # --- venv path ---
    VENV_DIR="$SCRIPT_DIR/.venv"

    if [ -d "$VENV_DIR" ]; then
        print_warning "venv directory already exists: $VENV_DIR"
        echo ""
        read -r -p "  Recreate it? [y/[N]]: " RECREATE
        # Default (Enter) is No: only an explicit "y" deletes the venv
        if [[ "$RECREATE" =~ ^[Yy]$ ]]; then
            rm -rf "$VENV_DIR"
            print_ok "Old venv removed."
            "$PYTHON_BIN" -m venv "$VENV_DIR"
            print_ok "New venv created."
        else
            print_info "Keeping existing venv. Will update packages."
        fi
    else
        echo "  Creating venv at $VENV_DIR..."
        "$PYTHON_BIN" -m venv "$VENV_DIR"
        print_ok "venv created."
    fi
    # shellcheck disable=SC1091
    source "$VENV_DIR/bin/activate"
fi
echo ""

# ============================================================================
#  Step 4: Install Python packages
# ============================================================================
echo -e "${BOLD}[4/6] Installing Python packages...${NC}"
echo ""

# Read and display package list from requirements.txt
echo " The following packages will be installed:"
while IFS= read -r line || [ -n "$line" ]; do
    # Skip comments and blank lines
    [[ "$line" =~ ^[[:space:]]*# ]] && continue
    [[ -z "${line// }" ]] && continue
    echo -e "   ${ORANGE}${line}${NC}"
done < requirements.txt
echo ""
read -r -p " Do you want to continue? [[Y]/n]: " _pkg_resp
if [[ "$_pkg_resp" =~ ^[Nn]$ ]]; then
    print_warning "Aborted by user."
    exit 1
fi
echo ""

echo "  Upgrading pip..."
python -m pip install --upgrade pip

echo "  Installing requirements..."
python -m pip install -r requirements.txt || {
    print_error "Package installation failed."
    exit 1
}
print_ok "All Python packages installed."
echo ""

# ============================================================================
#  Step 5: Verify installation
# ============================================================================
echo -e "${BOLD}[5/6] Verifying installation...${NC}"
echo ""

python -c "
import PyQt6.QtWidgets
print('  ✓ PyQt6 OK')
" || {
    print_error "PyQt6 could not be imported."
    print_info "On Wayland, try: export QT_QPA_PLATFORM=wayland"
    exit 1
}

python -c "
try:
    import exiftool
    print('  ✓ PyExifTool OK')
except ImportError:
    print('  ⚠ PyExifTool not available (optional)')
" || true

echo ""
print_header
echo -e "${GREEN}${BOLD} Installation complete!${NC}"
print_header
echo ""

# ============================================================================
#  Step 6: Desktop Shortcut (Linux)
# ============================================================================
read -r -p " Create a desktop shortcut for RenamePy? [[Y]/n]: " CREATE_SHORTCUT

# Python interpreter of the environment (works without activating it)
ENV_PYTHON="$(python -c 'import sys; print(sys.executable)')"

# Quote one argument for the Exec= key of a .desktop file (Desktop Entry
# spec: wrap in double quotes, backslash-escape " ` $ \ and double %).
desktop_quote() {
    local arg="$1"
    arg="${arg//\\/\\\\}"
    arg="${arg//\"/\\\"}"
    arg="${arg//\`/\\\`}"
    arg="${arg//\$/\\\$}"
    arg="${arg//%/%%}"
    printf '"%s"' "$arg"
}

if [[ ! "$CREATE_SHORTCUT" =~ ^[Nn]$ ]]; then
    echo ""
    echo "  Creating shortcut..."

    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        # Application menu entry (works in every desktop environment)
        APPS_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
        ICON_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/icons"
        mkdir -p "$APPS_DIR" "$ICON_DIR"

        # Most desktops don't render .ico files - convert with Qt
        ICON_PATH="$SCRIPT_DIR/icon.ico"
        if python -c "import sys; from PyQt6.QtGui import QImage; sys.exit(not QImage(sys.argv[1]).save(sys.argv[2], 'PNG'))" \
                "$SCRIPT_DIR/icon.ico" "$ICON_DIR/renamepy.png" 2>/dev/null; then
            ICON_PATH="$ICON_DIR/renamepy.png"
        fi

        SHORTCUT_PATH="$APPS_DIR/renamepy.desktop"
        cat > "$SHORTCUT_PATH" << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=RenamePy
Comment=Advanced Photo Renaming Tool
Exec=$(desktop_quote "$ENV_PYTHON") $(desktop_quote "$SCRIPT_DIR/RenameFiles.py")
Path=$SCRIPT_DIR
Icon=$ICON_PATH
Terminal=false
Categories=Graphics;Photography;
EOF
        chmod +x "$SHORTCUT_PATH"
        if command -v update-desktop-database &>/dev/null; then
            update-desktop-database "$APPS_DIR" &>/dev/null || true
        fi
        print_ok "Application menu entry created: $SHORTCUT_PATH"

        # Optional copy on the desktop
        DESKTOP_DIR="$(xdg-user-dir DESKTOP 2>/dev/null || true)"
        if [ -z "$DESKTOP_DIR" ] || [ "$DESKTOP_DIR" = "$HOME" ]; then
            DESKTOP_DIR="$HOME/Desktop"
        fi
        if [ -d "$DESKTOP_DIR" ]; then
            cp "$SHORTCUT_PATH" "$DESKTOP_DIR/RenamePy.desktop"
            chmod +x "$DESKTOP_DIR/RenamePy.desktop"
            # GNOME only starts desktop launchers marked as trusted
            if command -v gio &>/dev/null; then
                gio set "$DESKTOP_DIR/RenamePy.desktop" metadata::trusted true &>/dev/null || true
            fi
            print_ok "Desktop shortcut created: $DESKTOP_DIR/RenamePy.desktop"
        fi

    elif [[ "$OSTYPE" == "darwin"* ]]; then
        SHORTCUT_PATH="$HOME/Desktop/RenamePy.command"
        {
            echo '#!/bin/bash'
            printf 'cd %q || exit 1\n' "$SCRIPT_DIR"
            printf 'exec %q %q\n' "$ENV_PYTHON" "$SCRIPT_DIR/RenameFiles.py"
        } > "$SHORTCUT_PATH"
        chmod +x "$SHORTCUT_PATH"
        print_ok "Desktop shortcut created: $SHORTCUT_PATH"
    else
        print_warning "Could not detect OS type. No shortcut created."
    fi
fi

echo ""
print_header
echo ""
echo -e " ${ORANGE}All done! RenamePy is ready.${NC}"
echo ""

if [ "$USE_CONDA" = true ]; then
    echo -e "  To start manually later:"
    echo -e "   ${GREEN}conda activate $ENV_NAME && python RenameFiles.py${NC}"
else
    echo -e "  To start manually later:"
    echo -e "   ${GREEN}source .venv/bin/activate && python RenameFiles.py${NC}"
fi
echo ""
echo -e "  ${GREEN}[R]${NC}  Start RenamePy now"
echo -e "  ${NC}[any other key]  Exit${NC}"
echo ""
read -r -p " [Any key] / R: " _launch
if [[ "$_launch" =~ ^[Rr]$ ]]; then
    echo ""
    print_info "Launching RenamePy..."
    if [ "$USE_CONDA" = true ]; then
        conda run -n "$ENV_NAME" python "$SCRIPT_DIR/RenameFiles.py"
    else
        python "$SCRIPT_DIR/RenameFiles.py"
    fi
fi

