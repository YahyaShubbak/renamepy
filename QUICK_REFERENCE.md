# 🚀 RenamePy - Quick Reference Guide

## Installation & Start (2 Simple Steps!)

### 1️⃣ Installation (One-time Setup)
```bash
install.bat
# OR
.\install.ps1
```

### 2️⃣ Start Application (Anytime)
```bash
start_simple.bat
# OR
start_debug.bat     # With debug information
```

---

## 📁 Key Files

| File | Purpose | When to Use |
|------|---------|-------------|
| **install.bat** | Installation | Once only! |
| **start_simple.bat** | Start app | Always use this |
| **start_debug.bat** | With debug output | For troubleshooting |
| **activate_env.bat** | Manual activation | Optional |
| **README.md** | Complete guide | For detailed help |

---

## 🆘 Quick Solutions

### "ModuleNotFoundError: PyQt6"
```bash
# If installation didn't work:
→ Use start_simple.bat
→ It automatically activates the conda environment
```

### "Conda not found"
```bash
→ Install Miniconda: https://docs.conda.io/miniconda.html
→ Then run: install.bat
```

### "Python not found"
```bash
→ Install Python: https://www.python.org/
→ ✓ Check "Add to PATH" during installation!
→ Restart system
→ Then run: install.bat
```

### "Still not working"
```bash
start_debug.bat
# Read output and check README.md → Troubleshooting section
```

---

## 💾 Environments

After installation, you have two options:

```
Two possibilities:

[A] Conda Environment (Recommended)
    C:\Users\<User>\miniconda3\envs\renamepy\
    → Use: conda activate renamepy

[B] Venv Environment (if -ForceVenv used)
    .\renamepy\
    → Use: .\renamepy\Scripts\Activate.ps1
```

---

## 🔄 Daily Usage

```bash
# Option 1 (Simple - Recommended):
start_simple.bat
→ Everything automatic

# Option 2 (Manual):
conda activate renamepy
python RenameFiles.py

# Option 3 (Debug Mode):
start_debug.bat
→ Detailed information
```

---

## 📊 Post-Installation Status

Check with:
```powershell
conda env list
# Should display: renamepy ← Conda
```

or:

```powershell
.\activate_env.bat
python -c "import PyQt6, PIL; print('OK')"
```

---

## 🎯 The Three Starter Scripts Explained

```
start_simple.bat
└─ Normal usage
   └─ Starts the application
   └─ Minimal console output
   └─ ← USE THIS ONE!

start_file_renamer.bat
└─ Alternative to simple
   └─ Functionally identical
   └─ Different name only

start_debug.bat
└─ Debug mode
   └─ Shows Python information
   └─ Checks all modules
   └─ ← USE WHEN TROUBLESHOOTING
```

---

## ⚙️ If Something Is Missing

```bash
# Install missing packages
conda activate renamepy
pip install -r requirements.txt

# Or complete reinstall
.\install.ps1
```

---

## 📞 Documentation

```
Quick start?
→ You're reading it ✓

Full understanding?
→ README.md

Installation details?
→ Check install.bat comments

Technical documentation?
→ CHANGELOG.md (version history)
```

---

## ✅ Checklist

- [ ] `install.bat` executed successfully
- [ ] `start_simple.bat` works
- [ ] GUI window opens
- [ ] No errors in console

→ **Done!** 🎉

---

## 🆘 Emergency Commands

```powershell
# Check installation
conda env list

# Manually activate
conda activate renamepy

# List all packages
pip list

# Test modules
python -c "import PyQt6; import PIL; print('OK')"

# Reinstall everything
.\install.ps1
```

---

**That's it! Enjoy RenamePy!** 🚀
