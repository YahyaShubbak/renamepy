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
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color
BOLD='\033[1m'

LINE="==============================================================================="

# Helper functions
print_header() { echo -e "${CYAN}${LINE}${NC}"; }
print_ok()      { echo -e "  ${GREEN}[OK]${NC} $1"; }
print_error()   { echo -e "  ${RED}[ERROR]${NC} $1"; }
print_warning() { echo -e "  ${YELLOW}[WARNING]${NC} $1"; }
print_info()    { echo -e "  ${BLUE}[INFO]${NC} $1"; }

# ============================================================================
#  Welcome
# ============================================================================
clear
echo -e "${CYAN}"
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
read -p " Press Enter to continue..."

# ============================================================================
#  Step 1: System Dependencies
# ============================================================================
echo ""
echo -e "${BOLD}[1/6] Checking system dependencies...${NC}"
echo ""

install_system_deps() {
    if [[ "$OSTYPE" != "linux-gnu"* ]]; then
        print_info "Not Linux, skipping system dependency check."
        return 0
    fi

    if command -v pacman &>/dev/null; then
        # Arch Linux / EndeavourOS / Manjaro
        print_info "Detected Arch-based system (pacman)"
        local MISSING_PKGS=()
        local ARCH_DEPS=("mesa" "libxcb" "xcb-util" "xcb-util-wm" "xcb-util-image" \
                         "xcb-util-keysyms" "xcb-util-renderutil" "xcb-util-cursor" \
                         "libxkbcommon" "libxkbcommon-x11" "fontconfig" "freetype2" \
                         "dbus" "libglvnd" "perl-image-exiftool")
        for pkg in "${ARCH_DEPS[@]}"; do
            if ! pacman -Qi "$pkg" &>/dev/null; then
                MISSING_PKGS+=("$pkg")
            fi
        done
        if [ ${#MISSING_PKGS[@]} -gt 0 ]; then
            print_warning "Missing system packages: ${MISSING_PKGS[*]}"
            read -p "  Install them now with pacman? (Y/n): " DO_INSTALL
            if [[ ! "$DO_INSTALL" =~ ^[Nn]$ ]]; then
                sudo pacman -S --needed --noconfirm "${MISSING_PKGS[@]}"
                print_ok "System packages installed."
            else
                print_warning "Skipped. Qt6/ExifTool may not work without these."
            fi
        else
            print_ok "All required system packages are installed."
        fi

    elif command -v apt-get &>/dev/null; then
        # Debian / Ubuntu / Mint
        print_info "Detected Debian/Ubuntu-based system (apt)"
        local MISSING_PKGS=()
        local DEB_DEPS=("libgl1" "libegl1" "libxcb-xinerama0" "libxcb-cursor0" \
                        "libxcb-shape0" "libxcb-icccm4" "libxcb-image0" \
                        "libxcb-keysyms1" "libxcb-render-util0" "libxkbcommon0" \
                        "libxkbcommon-x11-0" "libfontconfig1" "libfreetype6" \
                        "libdbus-1-3" "libimage-exiftool-perl")
        for pkg in "${DEB_DEPS[@]}"; do
            if ! dpkg -s "$pkg" &>/dev/null 2>&1; then
                MISSING_PKGS+=("$pkg")
            fi
        done
        if [ ${#MISSING_PKGS[@]} -gt 0 ]; then
            print_warning "Missing system packages: ${MISSING_PKGS[*]}"
            read -p "  Install them now with apt? (Y/n): " DO_INSTALL
            if [[ ! "$DO_INSTALL" =~ ^[Nn]$ ]]; then
                sudo apt-get update && sudo apt-get install -y "${MISSING_PKGS[@]}"
                print_ok "System packages installed."
            else
                print_warning "Skipped. Qt6/ExifTool may not work without these."
            fi
        else
            print_ok "All required system packages are installed."
        fi

    else
        print_warning "Could not detect package manager (pacman/apt)."
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
    CONDA_EXE=$(which conda 2>/dev/null || true)
fi

if [ -n "$CONDA_EXE" ] && [ -x "$CONDA_EXE" ]; then
    print_ok "Conda found: $CONDA_EXE"
    echo ""
    echo -e "  Choose environment type:"
    echo -e "    ${CYAN}[1]${NC} Conda environment (recommended if you use conda)"
    echo -e "    ${CYAN}[2]${NC} Python venv (lightweight, no conda needed)"
    echo ""
    read -p "  Your choice (1/2) [1]: " ENV_CHOICE
    if [[ "$ENV_CHOICE" == "2" ]]; then
        print_info "Using Python venv."
    else
        USE_CONDA=true
        CONDA_BASE=$(dirname "$(dirname "$CONDA_EXE")")
        source "$CONDA_BASE/etc/profile.d/conda.sh"
        print_info "Using Conda."
    fi
else
    print_info "Conda not found. Using Python venv."
    # Verify python3 is available
    if ! command -v python3 &>/dev/null; then
        print_error "python3 not found! Please install Python 3.10+."
        exit 1
    fi
    PYTHON_VER=$(python3 --version 2>&1)
    print_ok "Python found: $PYTHON_VER"
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
        read -p "  Recreate it? All changes will be lost! (Y/n): " RECREATE
        if [[ ! "$RECREATE" =~ ^[Nn]$ ]]; then
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
        read -p "  Recreate it? (Y/n): " RECREATE
        if [[ ! "$RECREATE" =~ ^[Nn]$ ]]; then
            rm -rf "$VENV_DIR"
            print_ok "Old venv removed."
            python3 -m venv "$VENV_DIR"
            print_ok "New venv created."
        else
            print_info "Keeping existing venv. Will update packages."
        fi
    else
        echo "  Creating venv at $VENV_DIR..."
        python3 -m venv "$VENV_DIR"
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

echo "  Upgrading pip..."
pip install --upgrade pip --quiet

echo "  Installing requirements..."
pip install -r requirements.txt || {
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
read -p " Would you like to create a desktop shortcut? (Y/n): " CREATE_SHORTCUT

if [[ ! "$CREATE_SHORTCUT" =~ ^[Nn]$ ]]; then
    echo ""
    echo "  Creating desktop shortcut..."

    # Detect desktop location
    if [ -n "$XDG_DESKTOP_DIR" ]; then
        DESKTOP_DIR="$XDG_DESKTOP_DIR"
    elif [ -d "$HOME/Desktop" ]; then
        DESKTOP_DIR="$HOME/Desktop"
    elif [ -d "$HOME/Schreibtisch" ]; then
        DESKTOP_DIR="$HOME/Schreibtisch"
    else
        DESKTOP_DIR="$HOME"
    fi

    SHORTCUT_PATH="$DESKTOP_DIR/RenamePy.desktop"

    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        if [ "$USE_CONDA" = true ]; then
            EXEC_CMD="bash -c \"cd '$SCRIPT_DIR' && source '$CONDA_BASE/etc/profile.d/conda.sh' && conda activate $ENV_NAME && python RenameFiles.py\""
        else
            EXEC_CMD="bash -c \"cd '$SCRIPT_DIR' && source '$VENV_DIR/bin/activate' && python RenameFiles.py\""
        fi

        cat > "$SHORTCUT_PATH" << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=RenamePy
Comment=Advanced Photo Renaming Tool
Exec=$EXEC_CMD
Icon=$SCRIPT_DIR/icon.ico
Terminal=false
Categories=Graphics;Photography;Utility;
EOF
        chmod +x "$SHORTCUT_PATH"
        print_ok "Desktop shortcut created: $SHORTCUT_PATH"

    elif [[ "$OSTYPE" == "darwin"* ]]; then
        SHORTCUT_PATH="$DESKTOP_DIR/RenamePy.command"
        if [ "$USE_CONDA" = true ]; then
            cat > "$SHORTCUT_PATH" << EOF
#!/bin/bash
cd "$SCRIPT_DIR"
source "$CONDA_BASE/etc/profile.d/conda.sh"
conda activate $ENV_NAME
python RenameFiles.py
EOF
        else
            cat > "$SHORTCUT_PATH" << EOF
#!/bin/bash
cd "$SCRIPT_DIR"
source "$VENV_DIR/bin/activate"
python RenameFiles.py
EOF
        fi
        chmod +x "$SHORTCUT_PATH"
        print_ok "Desktop shortcut created: $SHORTCUT_PATH"
    else
        print_warning "Could not detect OS type. No shortcut created."
    fi
fi

echo ""
print_header
echo ""
echo -e " All done! Start the application with:"
echo ""
if [ "$USE_CONDA" = true ]; then
    echo -e "   ${CYAN}conda activate $ENV_NAME && python RenameFiles.py${NC}"
else
    echo -e "   ${CYAN}source .venv/bin/activate && python RenameFiles.py${NC}"
fi
echo -e "   or use the desktop shortcut (if created)."
echo ""
echo -e " If you encounter problems:"
echo -e "   1. Open a terminal in the project folder"
if [ "$USE_CONDA" = true ]; then
    echo -e "   2. Run: ${CYAN}conda activate $ENV_NAME${NC}"
else
    echo -e "   2. Run: ${CYAN}source .venv/bin/activate${NC}"
fi
echo -e "   3. Start: ${CYAN}python RenameFiles.py${NC}"
echo ""
print_header
echo ""
