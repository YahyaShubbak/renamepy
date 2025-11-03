# 🚀 RenamePy - Starter Dateien

## Problem gelöst! ✅

Die `.bat` Dateien aktivieren jetzt **automatisch das Conda Environment**, sodass PyQt6 und andere Packages gefunden werden.

---

## 📋 Verfügbare Starter

### 1. **start_simple.bat** ⭐ Empfohlen
- **Zweck:** Normale Anwendung starten
- **Kontext:** Einfach, produktiv
- **Was es macht:**
  - ✅ Aktiviert Conda Environment 'renamepy'
  - ✅ Prüft Python Verfügbarkeit
  - ✅ Startet RenameFiles.py
  - ✅ Zeigt Erfolgs-/Fehlermeldung

**Verwendung:**
```bash
start_simple.bat
```

---

### 2. **start_debug.bat** 🔍 Für Entwickler
- **Zweck:** Detailliertes Debugging
- **Kontext:** Entwicklung, Fehlersuche
- **Was es macht:**
  - ✅ Aktiviert Conda Environment
  - ✅ Zeigt Python Version & Pfad
  - ✅ Prüft alle erforderlichen Module
  - ✅ Zeigt Start-/Endzeit
  - ✅ Exit-Code Display
  - ✅ Vollständiger Debug-Output

**Verwendung:**
```bash
start_debug.bat
```

**Beispiel-Output:**
```
======================================
   FILE RENAMER - DEBUG MODUS
   Verzeichnis: C:\Users\YaSh\...
======================================

[1] Aktiviere Conda Environment 'renamepy'...
[OK] Conda Environment aktiviert

[2] Python Verzeichnis und Version pruefen...
Python 3.14.0
Python Pfad: C:\Users\YaSh\miniconda3\envs\renamepy\python.exe

[3] Dateien pruefen...
[OK] Alle Dateien vorhanden

[4] Pruefen auf erforderliche Module...
PyQt6: OK
Pillow: OK
PyExifTool: OK

======================================
   START ANWENDUNG
======================================
[... GUI startet ...]

======================================
   DEBUG INFO
======================================
Startzeit: 16:42:05,45
Endzeit:   16:42:10,12
Exit Code: 0
Status: OK
======================================
```

---

### 3. **start_file_renamer.bat** 
- **Zweck:** Alternative zu start_simple.bat
- **Unterschied:** Gleiches wie start_simple, aber anderer Name

**Verwendung:**
```bash
start_file_renamer.bat
```

---

## 🔧 Was wurde repariert

### Das Problem:
```
ModuleNotFoundError: No module named 'PyQt6'
```

**Ursache:** Die Starter-Dateien haben das Conda Environment **nicht** aktiviert. Sie nutzten direkten System-Python statt des Environment-Python.

### Die Lösung:
```batch
call "%USERPROFILE%\miniconda3\Scripts\activate.bat" renamepy
```

Dies aktiviert das Conda Environment **vor** dem Ausführen der Python-Anwendung.

---

## 🚀 Schnellstart

### 1️⃣ Installation (einmalig)
```bash
install.bat
```

### 2️⃣ Anwendung starten (jederzeit)
```bash
start_simple.bat
```

oder für Debug:
```bash
start_debug.bat
```

---

## 📊 Vergleich der Starter

| Starter | Umgebung | Debug | Für |
|---------|----------|-------|-----|
| start_simple.bat | Conda | Minimal | Normalnutzer |
| start_debug.bat | Conda | Maximal | Entwickler |
| start_file_renamer.bat | Conda | Minimal | Alternative |

---

## ✅ Fehlertoleranz

Die Dateien prüfen jetzt:

1. ✅ **Conda vorhanden?** - Aktiviert Environment
2. ✅ **Python im Environment?** - Startet App
3. ✅ **RenameFiles.py vorhanden?** - Prüfung vor Start
4. ✅ **modules Ordner vorhanden?** - Existenz-Prüfung
5. ✅ **modules/__init__.py?** - Wird ggf. erstellt

---

## 🐛 Debugging

### Start mit Debug-Informationen:
```bash
start_debug.bat
```

Du siehst dann:
- ✓ Python Version
- ✓ Python Pfad
- ✓ Alle Module (PyQt6, Pillow, exiftool)
- ✓ Exit-Code
- ✓ Zeitstempel

### Manuelles Debugging:
```powershell
# 1. Conda aktivieren
conda activate renamepy

# 2. Python-Befehle testen
python --version
python -c "import PyQt6; print('OK')"

# 3. Anwendung starten
python RenameFiles.py
```

---

## 🎯 Verwendungsszenarien

### Szenario 1: Normale Nutzung
```
Doppelklick auf start_simple.bat
→ GUI öffnet sich
→ Fertig!
```

### Szenario 2: Debugging eines Fehlers
```
Doppelklick auf start_debug.bat
→ Sehe Debug-Informationen
→ Prüfe Log
→ Behebe Problem
```

### Szenario 3: Automated Startup (Script)
```powershell
# In PowerShell oder Automation
cmd /c start_simple.bat
```

---

## 🔄 Fallback-Logik

Falls Conda nicht gefunden:
```
❌ Conda nicht gefunden
→ FEHLER anzeigen
→ Installation vorschlagen: .\install.bat
→ Exit mit Fehlercode
```

Das ist **absichtlich** - wir wollen sichergehen, dass das korrekte Environment genutzt wird.

---

## 📝 Environment-Struktur

Nachdem `start_simple.bat` startet:

```
(base) PS C:\...>
  ↓
call activate.bat renamepy
  ↓
(renamepy) PS C:\...>
  ↓
python RenameFiles.py
  ↓
✓ PyQt6 verfügbar (im renamepy Environment)
✓ App lädt Module erfolgreich
✓ GUI startet
```

---

## ✨ Neue Features der Starter

| Feature | Vorher | Nachher |
|---------|--------|---------|
| Environment | ❌ Nicht aktiviert | ✅ Aktiviert |
| Module | ❌ PyQt6 fehlt | ✅ PyQt6 da |
| Error Handling | ⚠️ Minimal | ✅ Umfassend |
| Debug Info | ❌ Keine | ✅ Detailliert |
| Fehlermeldungen | ⚠️ Unklar | ✅ Klar & Hilfreich |

---

## 🎓 Best Practices

1. **Immer `start_simple.bat` für normale Nutzung verwenden**
2. **`start_debug.bat` nur bei Problemen**
3. **Falls Module fehlen: `install.ps1` ausführen**
4. **Conda Environment **muss** aktiviert sein**

---

## 🚨 Wenn immer noch nicht funktioniert

### 1. Prüfe Conda Installation
```powershell
conda env list
# Sollte 'renamepy' anzeigen
```

### 2. Aktiviere manuell
```powershell
conda activate renamepy
python RenameFiles.py
```

### 3. Reinstalliere Environment
```powershell
.\install.ps1
```

### 4. Debug Details
```powershell
start_debug.bat
# Prüfe Output auf Fehler
```

---

## 📞 Support

Falls Probleme:
1. Ausführe `start_debug.bat`
2. Lies die Debug-Ausgabe
3. Siehe `INSTALL_GUIDE.md` → Troubleshooting
4. Oder führe aus: `.\install.ps1 -Verbose`

---

## ✅ Checkliste vor erste Nutzung

- [ ] `install.ps1` erfolgreich ausgeführt
- [ ] `.\activate_env.bat` zeigt korrekte Environment
- [ ] `conda env list` zeigt 'renamepy'
- [ ] `start_debug.bat` zeigt "Status: OK"
- [ ] GUI-Fenster öffnet sich bei `start_simple.bat`

---

**Jetzt sind die Starter bereit für den produktiven Einsatz!** 🚀
