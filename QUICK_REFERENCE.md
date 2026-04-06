# RenamePy - Quick Reference Guide

## Installation & Start

### 1. Installation (One-time Setup)

**Windows (PowerShell):**
```powershell
powershell -ExecutionPolicy Bypass -File install.ps1
```

**Linux / macOS:**
```bash
./install.sh
```

### 2. Start Application

**Windows:**
```
start.bat
start.bat --debug    # With debug information
```

**Linux / macOS:**
```bash
conda activate renamepy && python RenameFiles.py
# or (if using venv):
source .venv/bin/activate && python RenameFiles.py
```

---

## Key Files

| File | Purpose | When to Use |
|------|---------|-------------|
| **install.ps1** | Windows installation | Once only |
| **install.sh** | Linux/macOS installation | Once only |
| **start.bat** | Start app (Windows) | Always |
| **activate_env.bat** | Manual env activation | Optional |
| **setup_exiftool.ps1** | Install ExifTool | If ExifTool is missing |
| **README.md** | Complete guide | For detailed help |

---

## Quick Solutions

### "ModuleNotFoundError: PyQt6"
```bash
# Reinstall packages:
conda activate renamepy
pip install -r requirements.txt
```

### "Conda not found"
```bash
# Install Miniconda: https://docs.conda.io/miniconda.html
# Then run install.ps1 / install.sh again
```

### "Python not found"
```bash
# Install Python: https://www.python.org/
# Check "Add to PATH" during installation!
# Restart system, then run install.ps1 again
```

### "Still not working"
```
start.bat --debug
# Read output and check README.md → Troubleshooting section
```

---

## Environments

After installation, you have two options:

```
[A] Conda Environment (Recommended)
    Windows: C:\Users\<User>\miniconda3\envs\renamepy\
    Linux:   ~/miniconda3/envs/renamepy/
    → Use: conda activate renamepy

[B] Venv Environment (if -ForceVenv used or no Conda)
    Windows: .\renamepy\  or  .\.venv\
    Linux:   ./.venv/
    → Use: source .venv/bin/activate
```

---

## Checklist

- [ ] `install.ps1` / `install.sh` executed successfully
- [ ] `start.bat` / `python RenameFiles.py` works
- [ ] GUI window opens
- [ ] No errors in console

---

## Emergency Commands

```powershell
# Check installation
conda env list

# Manually activate
conda activate renamepy

# List all packages
pip list

# Test modules
python -c "import PyQt6; import exiftool; print('OK')"

# Reinstall everything
# Windows:
powershell -ExecutionPolicy Bypass -File install.ps1
# Linux:
./install.sh
```

---

**That's it! Enjoy RenamePy!** 🚀
