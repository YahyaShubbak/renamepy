# RenamePy - Schnellstart Installation

## ⚡ Einfachste Methode (Empfohlen)

**Doppelklick auf `install.bat`** und fertig! ✓

Das Skript wird automatisch:
- Python prüfen
- Conda oder venv installieren (falls nötig)
- Alle Abhängigkeiten installieren
- Ein Aktivierungs-Skript erstellen

---

## 🚀 Manuelle Installation (PowerShell)

Falls die `.bat` nicht funktioniert:

### 1. PowerShell öffnen
Drücke `Windows + X` → PowerShell öffnen

### 2. Zum Projektordner navigieren
```powershell
cd c:\Users\YaSh\Documents\GitHub\renamepy
```

### 3. Execution Policy temporär ändern
```powershell
Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process
```

### 4. Installation starten
```powershell
.\install.ps1
```

### Optionale Parameter
```powershell
# Ohne ExifTool Prüfung
.\install.ps1 -SkipExifCheck

# Erzwinge venv statt Conda
.\install.ps1 -ForceVenv

# Mit Debug-Ausgaben
.\install.ps1 -Verbose
```

---

## ✅ Nach der Installation

### Aktiviere das Environment

**Option 1 (empfohlen):**
```bash
.\activate_env.bat
```

**Option 2 (PowerShell):**
```powershell
.\renamepy\Scripts\Activate.ps1
```

**Option 3 (Conda):**
```bash
conda activate renamepy
```

### Starte die Anwendung
```bash
python RenameFiles.py
```

---

## 🐛 Häufige Probleme

### Problem: PowerShell Skript wird nicht ausgeführt
**Lösung:**
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
.\install.ps1
```

### Problem: "Python nicht gefunden"
- **Lösung:** Python reinstallieren von https://www.python.org/
- Wichtig: ✓ "Add Python to PATH" ankreuzen!
- System-Neustart erforderlich

### Problem: "Packages konnten nicht installiert werden"
- Prüfe Internet-Verbindung
- Versuche manuell:
```powershell
.\renamepy\Scripts\Activate.ps1
pip install PyQt6 PyExifTool Pillow
```

### Problem: "ExifTool nicht gefunden"
- Das ist optional und nicht kritisch!
- Falls benötigt: https://exiftool.org/
- Oder skip: `.\install.ps1 -SkipExifCheck`

---

## 📦 Was wird installiert?

- **PyQt6** - GUI Framework
- **PyExifTool** - EXIF Metadaten
- **Pillow** - Bildverarbeitung (Fallback)

---

## 📁 Wo wird installiert?

Virtual Environment wird erstellt unter:
```
c:\Users\YaSh\Documents\GitHub\renamepy\renamepy\
```

Oder wenn Conda installiert:
```
%USERPROFILE%\miniconda3\envs\renamepy\
```

---

## 🆘 Weitere Hilfe

Siehe ausführliche Dokumentation: [INSTALLATION.md](./INSTALLATION.md)

---

## ✨ Tipps

### 1. Deinstallation
```powershell
# Venv löschen:
Remove-Item -Path ".\renamepy" -Recurse -Force

# Oder Conda:
conda env remove -n renamepy
```

### 2. Environment neu erstellen
```powershell
.\install.ps1
# → Wähle "ja" wenn gefragt ob überschrieben werden soll
```

### 3. Packages aktualisieren
```powershell
.\renamepy\Scripts\Activate.ps1
pip install --upgrade -r requirements.txt
```

---

**Viel Spaß mit RenamePy!** 🎉
