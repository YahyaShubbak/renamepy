# 🚀 RenamePy - Quick Reference Card

## Installation & Start (Nur 2 Schritte!)

### 1️⃣ Installation (einmalig)
```bash
install.bat
# ODER
.\install.ps1
```

### 2️⃣ Anwendung Starten (jederzeit)
```bash
start_simple.bat
# ODER
start_debug.bat     # Mit Debug-Info
```

---

## 📁 Wichtigste Dateien

| Datei | Was | Wann |
|-------|-----|------|
| **install.bat** | Installation | Nur einmal! |
| **start_simple.bat** | App starten | Immer nutzen |
| **start_debug.bat** | Mit Debug | Bei Problemen |
| **activate_env.bat** | Manuell aktivieren | Optional |
| **INSTALL_GUIDE.md** | Vollständiger Guide | Bei Fragen |

---

## 🆘 Schnelle Lösungen

### "ModuleNotFoundError: PyQt6"
```bash
# Hat nicht funktioniert:
→ Nutze start_simple.bat
→ Es aktiviert automatisch das Conda Environment
```

### "Conda nicht gefunden"
```bash
→ Install Miniconda: https://docs.conda.io/miniconda.html
→ Dann: install.bat
```

### "Python nicht gefunden"
```bash
→ Installiere Python: https://www.python.org/
→ ✓ "Add to PATH" ankreuzen!
→ System-Neustart
→ Dann: install.bat
```

### "Es funktioniert immer noch nicht"
```bash
start_debug.bat
# Liest Output und nutze INSTALL_GUIDE.md → Troubleshooting
```

---

## 💾 Umgebungen

Nachdem Installation:

```
Zwei Möglichkeiten:

[A] Conda Environment
    C:\Users\YaSh\miniconda3\envs\renamepy\
    → Nutze: conda activate renamepy

[B] Venv Environment (falls -ForceVenv)
    .\renamepy\
    → Nutze: .\renamepy\Scripts\Activate.ps1
```

---

## 🔄 Tägliche Nutzung

```bash
# Option 1 (Einfach):
start_simple.bat
→ Alles automatisch

# Option 2 (Manuell):
conda activate renamepy
python RenameFiles.py

# Option 3 (Mit Debug):
start_debug.bat
→ Viel Info
```

---

## 📊 Status nach Installation

Prüfe mit:
```powershell
conda env list
# Sollte anzeigen: renamepy ← Conda
```

oder:

```powershell
.\activate_env.bat
python -c "import PyQt6, PIL; print('OK')"
```

---

## 🎯 Die drei Starter erklärt

```
start_simple.bat
└─ Normale Nutzung
   └─ Startet die App
   └─ Minimal Output
   └─ ← NUTZE DIESEN!

start_file_renamer.bat
└─ Alternative zu simple
   └─ Identisch funktional
   └─ Anderer Name

start_debug.bat
└─ Debug-Modus
   └─ Zeigt Python-Info
   └─ Prüft alle Module
   └─ ← NUTZE BEI PROBLEMEN
```

---

## ⚙️ Wenn etwas fehlt

```bash
# Fehlende Packages installieren
conda activate renamepy
pip install -r requirements.txt

# Oder Alles neu
.\install.ps1
```

---

## 📞 Dokumentation

```
Schnell starten?
→ Du liest diese Datei ✓

Alles verstehen?
→ INSTALL_GUIDE.md

Nur Installation?
→ INSTALL_QUICK_START.md

Starter erklärt?
→ STARTER_GUIDE.md

Technische Details?
→ INSTALLATION.md
```

---

## ✅ Checkliste

- [ ] `install.bat` ausgeführt
- [ ] `start_simple.bat` funktioniert
- [ ] GUI-Fenster öffnet sich
- [ ] Keine Fehler im Console

→ **Fertig!** 🎉

---

## 🆘 Notfall-Befehle

```powershell
# Prüfe Installation
conda env list

# Manuell aktivieren
conda activate renamepy

# Alle Packages prüfen
pip list

# Module testen
python -c "import PyQt6; import PIL; print('OK')"

# Neuinstallation
.\install.ps1
```

---

**Das war's! Viel Spaß mit RenamePy!** 🚀
