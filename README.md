# RenameFiles - Advanced Photo Renaming Tool

A powerful and user-friendly PyQt6 application for batch renaming image files with EXIF data integration.

![File Renamer](https://img.shields.io/badge/Python-3.10+-blue.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)
![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey.svg)

## ✨ Features

### 🖼️ **Smart Image Processing**
- **EXIF Data Extraction**: Automatic camera model, lens, and date detection
- **RAW File Support**: Works with CR2, NEF, ARW, DNG, and more
- **ExifTool Integration**: Professional-grade metadata extraction using the excellent https://exiftool.org/

### 🎯 **Flexible Naming System**
- **Interactive Preview**: Drag & drop components to customize filename order
- **Multiple Date Formats**: YYYY-MM-DD, DD-MM-YYYY, YYYYMMDD, and more
- **Custom Prefixes**: Add camera identifiers (e.g., A7R3, D850)
- **Additional Fields**: Project names, locations, events
- **Sequential Numbering**: Automatic counter with collision detection

### 🔧 **Advanced Options**
- **Subdirectory Support**: Recursive folder scanning
- **File Safety**: Access validation and conflict resolution
- **Undo Functionality**: Restore original filenames
- **Batch Processing**: Handle hundreds of files efficiently
- **Dark/Light Themes**: Customizable UI appearance

### 🚀 **User Experience**
- **Drag & Drop Interface**: Easy file selection
- **Live Preview**: See results before renaming
- **Progress Tracking**: Real-time operation feedback
- **Error Handling**: Detailed failure reports
- **Tooltips & Help**: Built-in guidance system

## 🖥️ Screenshots

### Main Interface (System Theme)
```
┌────────────────────────────────────────────────────────────┐
│ Theme: [System ▼]                                          │
│                                                            │
│ [📄 Select Files] [📁 Select Folder] [🗑️ Clear Files]      │
│                                                            │
│ ☑ Include date in filename  Date Format: [YYYY-MM-DD ▼]    │
│                                                            │
│ Camera Prefix: [A7R3                    ] ℹ️               │
│ Additional:    [vacation                ] ℹ️               │
│ Separator:     [- ▼] ℹ️                                    │
│                                                            │
│ Interactive Preview (Drag & Drop): ℹ️                      │
│ ┌────────────────────────────────────────────────────────┐ │
│ │ [2025-07-29] - [A7R3] - [vacation] - [001]             │ │
│ └────────────────────────────────────────────────────────┘ │
│                                                            │
│ ☐ Include camera model from EXIF (Sony ILCE-7RM3)          │
│ ☐ Include lens model from EXIF (FE 24-70mm F2.8 GM)        │
│                                                            │
│ EXIF Method: [exiftool ▼]   ExifTool Path: [Browse...]     │
│                                                            │
│ ┌─── File List (0 files) ────────────────────────────────┐ │
│ │ 📁 Drag and drop image files here...                   │ │
│ │    Supports: RAW (.arw, .cr2, .nef), JPEG, PNG, etc.   │ │
│ └────────────────────────────────────────────────────────┘ │
│                                                            │
│ [🚀 Rename Files] [↶ Restore Original Names]               │
│                                                            │
│ Status: Ready to rename files                              │
└────────────────────────────────────────────────────────────┘
```

## 📋 Requirements

### System Requirements
- **Python**: 3.10 or higher (required for modern type hints)
- **Operating System**: Windows, macOS, Linux (cross-platform compatible)

### Python Dependencies
```bash
pip install PyQt6>=6.0.0        # Core GUI framework
pip install PyExifTool>=0.5.5   # ExifTool Python wrapper (required)
```

### External Dependencies
- **ExifTool**: Professional metadata extraction tool
  - 📥 **Download**: Get latest from [exiftool.org](https://exiftool.org)
  - 📦 **Package Managers**: Available via Chocolatey, Homebrew, apt-get
  - 🔧 **Manual Setup**: Extract to program folder or system PATH

## 🚀 Installation

### Option 1: Automated Installation (Recommended)

**Linux (Arch / EndeavourOS / Ubuntu / Debian):**
```bash
git clone https://github.com/YahyaShubbak/renamepy.git
cd renamepy
./install.sh
```
The script handles everything: system dependencies (Qt6 libs, ExifTool), environment creation (Conda or venv), and package installation.

**Windows:**
```powershell
git clone https://github.com/YahyaShubbak/renamepy.git
cd renamepy
powershell -ExecutionPolicy Bypass -File install.ps1
```

### Option 2: Manual Installation
```bash
git clone https://github.com/YahyaShubbak/renamepy.git
cd renamepy
pip install -r requirements.txt
python RenameFiles.py
```

> ⚠️ **Linux users**: You also need Qt6 system libraries and ExifTool:
> - **Arch**: `sudo pacman -S mesa libxcb xcb-util xcb-util-cursor libxkbcommon libxkbcommon-x11 perl-image-exiftool`
> - **Debian/Ubuntu**: `sudo apt install libgl1 libegl1 libxcb-cursor0 libxcb-icccm4 libxcb-keysyms1 libxkbcommon0 libxkbcommon-x11-0 libimage-exiftool-perl`

### Option 3: Download Release
1. Go to [Releases](https://github.com/YahyaShubbak/renamepy/releases)
2. Download latest version
3. Extract and run `RenameFiles.py`

### ExifTool Setup (Required for EXIF Data)

> 💡 **Linux**: ExifTool is installed automatically by `install.sh` (via pacman/apt). No extra steps needed!

> 💡 **Windows**: No Renaming Required! The application automatically detects both `exiftool.exe` and `exiftool(-k).exe`

**Option A: Download from Official Site (Windows, Recommended)**
1. Go to [exiftool.org](https://exiftool.org) and download the Windows version
2. Extract the archive (e.g., `exiftool-13.33_64.zip`) into the program directory
3. Keep the original folder name (e.g., `exiftool-13.33_64`) and place it in the program directory
4. Renaming `exiftool(-k).exe` to `exiftool.exe` is not required
5. The application automatically detects both `exiftool.exe` and `exiftool(-k).exe`

**Option B: Package Manager Installation**
```bash
# Windows (Chocolatey)
choco install exiftool

# macOS (Homebrew)
brew install exiftool

# Linux (Ubuntu/Debian)
sudo apt-get install libimage-exiftool-perl
```

**Option C: Portable Installation**
1. Download ExifTool from [exiftool.org](https://exiftool.org)
2. Extract to any folder containing "exiftool" in the name
3. **No renaming required** - keep `exiftool(-k).exe` as is!
4. The application will automatically detect it!

## 📖 Usage Guide

### Basic Workflow
1. **Select Files**: Use buttons or drag & drop
2. **Configure Settings**: Set date format, prefixes, etc.
3. **Preview Results**: Check the interactive preview
4. **Customize Order**: Drag components to reorder
5. **Rename Files**: Click the rename button
6. **Undo if Needed**: Use restore function

### Advanced Features

#### Custom Filename Order
Drag components in the Interactive Preview to customize order:
- Date → Camera Prefix → Additional → Camera Model → Lens → Number

#### Date Format Options
- `YYYY-MM-DD`: 2025-07-25
- `YYYYMMDD`: 20250725
- `DD-MM-YYYY`: 25-07-2025
- `MM_DD_YYYY`: 07_25_2025

#### Separator Options
- **Dash (--)**: `2025-07-25-A7R3-vacation-001.jpg`
- **Underscore (_)**: `2025_07_25_A7R3_vacation_001.jpg`
- **None**: `20250725A7R3vacation001.jpg`

### Safety Features
- **File Access Validation**: Checks before renaming
- **Path Length Validation**: Prevents Windows path issues
- **Collision Detection**: Handles duplicate names
- **Undo Functionality**: Restore original names
- **Error Reporting**: Detailed failure information

## 🔧 Configuration

### EXIF Method
1. **ExifTool** (required) - Best performance and compatibility
2. **File timestamps** (fallback when ExifTool unavailable)

### Supported File Formats
- **JPEG**: .jpg, .jpeg
- **RAW Files**: .cr2, .nef, .arw, .dng, .orf, .rw2, .raf
- **TIFF**: .tif, .tiff
- **Others**: .png, .bmp

## 🐛 Troubleshooting

### Common Issues

**Q: "No EXIF support available" message**
A: Install ExifTool and PyExifTool: `pip install PyExifTool` and download ExifTool from [exiftool.org](https://exiftool.org)

**Q: ExifTool not detected**
A: The application automatically searches for ExifTool in this order:
   1. System PATH
   2. Program folder (next to RenameFiles.py)
   3. Any subfolder containing "exiftool" in the name
   4. Common installation locations
   
   The application looks for both file names:
   - `exiftool.exe` (renamed version)
   - `exiftool(-k).exe` (original download name)
   
   If still not detected:
   - Download ExifTool from [exiftool.org](https://exiftool.org)
   - Extract to a folder in the program directory (keep original name like `exiftool-13.33_64`)
   - **No need to rename** `exiftool(-k).exe` - the app finds it automatically!
   - Check file permissions (ExifTool must be executable)

**Q: "ExifTool executable not found" error**
A: Install PyExifTool wrapper: `pip install PyExifTool`

**Q: Files not renaming**
A: Check file permissions and ensure files aren't locked by other programs

**Q: RAW files not supported**
A: Install ExifTool for full RAW format support

**Q: Dark theme issues**
A: Try switching to Light theme in the dropdown menu

### Performance Tips
- Process files in smaller batches for very large collections
- Use ExifTool for better performance with RAW files
- Close other applications when processing many files

## 🤝 Contributing

Contributions are welcome! Please feel free to submit issues and pull requests.

### Development Setup
```bash
git clone https://github.com/YahyaShubbak/renamepy.git
cd renamepy
pip install -r requirements.txt
# Run tests
python -m pytest tests/
```

### Reporting Issues
Please include:
- Operating system and Python version
- Error messages and logs
- Steps to reproduce the issue
- Sample files (if applicable)

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **ExifTool** by Phil Harvey - Excellent metadata extraction
- **PyQt6** - Powerful GUI framework
- **Python Community** - For the amazing ecosystem

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/YahyaShubbak/renamepy/issues)
- **Discussions**: [GitHub Discussions](https://github.com/YahyaShubbak/renamepy/discussions)

---

**Made with ❤️ for photographers**
