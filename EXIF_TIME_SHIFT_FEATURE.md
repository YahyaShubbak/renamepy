# ⏰ EXIF TIME SHIFT FEATURE

**Datum:** 2025-10-14  
**Feature:** EXIF-Zeitverschiebung für falsch eingestellte Kamera-Uhren  
**Status:** ✅ Implementiert

---

## 🎯 Problem

**Szenario:**
Die Kamera-Uhr war falsch eingestellt. Alle Fotos haben ein falsches EXIF-Aufnahmedatum.

**Beispiel:**
```
Tatsächliche Aufnahmezeit:  12:00, 12:05, 13:02 Uhr
EXIF zeigt:                 11:00, 11:05, 12:02 Uhr
Differenz:                  -1 Stunde
```

**Lösung:**
Alle EXIF-Zeitstempel um +1 Stunde 0 Minuten verschieben.

---

## 🚀 Feature-Übersicht

### **GUI-Dialog:**
```
Tools → ⏰ EXIF Time Shift...
```

### **Funktionen:**

1. **Richtungswahl:**
   - ⏩ Forward (Zeit hinzufügen)
   - ⏪ Backward (Zeit abziehen)

2. **Zeit-Einstellung:**
   - Stunden: 0-23
   - Minuten: 0-59

3. **Live-Preview:**
   - Zeigt erste 10 Dateien
   - Aktuelles vs. neues Datum
   - Farbcodierung (grün=vorwärts, gelb=rückwärts)

4. **Batch-Verarbeitung:**
   - Alle selektierten Dateien
   - Progress-Dialog
   - Fehlerbehandlung

---

## 📋 Dateien

### **Neu erstellt:**

1. **`modules/dialogs/exif_time_shift_dialog.py`** (435 Zeilen)
   - `ExifTimeShiftDialog` - Haupt-Dialog
   - `TimeShiftWorker` - Background-Thread für Verarbeitung
   
   **Komponenten:**
   - Richtungs-Auswahl (RadioButtons)
   - Zeit-Eingabe (SpinBoxen)
   - Preview-Tabelle (erste 10 Dateien)
   - Warnung vor permanenten Änderungen
   - Progress-Dialog
   - Fehler-Reporting

2. **Update: `modules/dialogs/__init__.py`**
   - Export von `ExifTimeShiftDialog`

3. **Update: `modules/main_application.py`**
   - Tools-Menü: "⏰ EXIF Time Shift..." Action
   - `show_time_shift_dialog()` Methode
   - Validierung (Dateien vorhanden, ExifTool verfügbar)
   - EXIF-Cache Clear nach Update
   - Preview-Refresh

---

## 🔧 Technische Details

### **ExifTool-Befehl:**

```bash
exiftool "-AllDates+=HH:MM:SS" -overwrite_original datei.jpg
```

**Beispiele:**
```bash
# +1 Stunde vorwärts
exiftool "-AllDates+=1:00:00" -overwrite_original IMG_1234.JPG

# -30 Minuten zurück
exiftool "-AllDates+=-0:30:00" -overwrite_original IMG_1234.JPG

# +2 Stunden 15 Minuten
exiftool "-AllDates+=2:15:00" -overwrite_original IMG_1234.JPG
```

### **Betroffene EXIF-Felder:**

```
-AllDates modifiziert:
  • EXIF:DateTimeOriginal
  • EXIF:CreateDate
  • EXIF:ModifyDate
  • QuickTime:CreateDate (Videos)
  • QuickTime:ModifyDate (Videos)
```

### **Datetime-Parsing:**

```python
# EXIF Format: "2024:01:15 10:30:45"
dt_str_clean = dt_str.replace(':', '-', 2)  # "2024-01-15 10:30:45"
current_dt = datetime.strptime(dt_str_clean, "%Y-%m-%d %H:%M:%S")

# Verschiebung anwenden
delta = timedelta(hours=hours, minutes=minutes)
new_dt = current_dt + delta  # oder - delta

# Zurück zu EXIF-Format
new_time_str = new_dt.strftime("%Y:%m:%d %H:%M:%S")
```

---

## 💡 Verwendungsbeispiele

### **Beispiel 1: Zeitzone vergessen**
```
Problem: Kamera auf UTC, Fotos in CET (UTC+1)
Lösung: +1 Stunde vorwärts
```

### **Beispiel 2: Sommerzeit nicht umgestellt**
```
Problem: Kamera 1 Stunde zurück (Winterzeit statt Sommerzeit)
Lösung: +1 Stunde vorwärts
```

### **Beispiel 3: Kamera-Reset**
```
Problem: Kamera-Uhr auf Werkeinstellungen (01.01.2000)
Lösung: Manuelle Korrektur pro Foto (nicht mit diesem Tool)
```

### **Beispiel 4: Mehrere Kameras synchronisieren**
```
Kamera A: 12:00 Uhr (korrekt)
Kamera B: 12:30 Uhr (30 Min vor)

Workflow:
1. Sortiere Kamera B Fotos aus
2. Wende -30 Minuten an
3. Merge beide Sets
```

---

## 🎨 GUI-Screenshots (Konzept)

### **Dialog-Layout:**
```
┌─────────────────────────────────────────────────────┐
│  ⏰ EXIF Time Shift                                 │
├─────────────────────────────────────────────────────┤
│                                                      │
│  Adjust timestamps for all selected photos.         │
│  Useful when your camera clock was set incorrectly. │
│                                                      │
│  ⚙️ Time Shift Settings                             │
│  ┌──────────────────────────────────────────┐      │
│  │ Direction:                                │      │
│  │  ⏩ Forward (add time)                    │      │
│  │  ⏪ Backward (subtract time)              │      │
│  │                                            │      │
│  │ Time shift:  [1] hours  [0] minutes       │      │
│  └──────────────────────────────────────────┘      │
│                                                      │
│  📋 Preview Changes (First 10 Files)                │
│  ┌──────────────────────────────────────────┐      │
│  │ File         │ Current Time  │ New Time   │      │
│  ├──────────────┼───────────────┼───────────│      │
│  │ IMG_001.JPG  │ 2024:01:15... │ 2024:01:.. │      │
│  │ IMG_002.JPG  │ 2024:01:15... │ 2024:01:.. │      │
│  └──────────────────────────────────────────┘      │
│                                                      │
│  📊 Total files: 596                                │
│                                                      │
│  ⚠️ WARNING: This will permanently modify EXIF!    │
│                                                      │
│  [ ✅ Apply Time Shift ]  [ ❌ Cancel ]             │
└─────────────────────────────────────────────────────┘
```

---

## ⚠️ Wichtige Hinweise

### **Sicherheit:**
1. **Backup empfohlen** - Änderungen sind permanent!
2. **`-overwrite_original`** - Keine `_original` Backup-Dateien
3. **Nur EXIF-Daten** - Bilddaten bleiben unverändert

### **Einschränkungen:**
1. **Nur mit ExifTool** - Pillow kann EXIF nicht schreiben
2. **Nur Mediendateien** - JPG, RAW, Videos
3. **Keine Undo-Funktion** - Bei Fehler manuell korrigieren

### **Performance:**
- ExifTool: ~5-10 files/sec
- 596 Dateien: ~1-2 Minuten
- Progress-Dialog zeigt Fortschritt

---

## 🧪 Testing-Checkliste

### **Funktional:**
- [ ] Dialog öffnet korrekt
- [ ] Preview zeigt korrekte Zeiten
- [ ] Forward-Shift funktioniert (+Zeit)
- [ ] Backward-Shift funktioniert (-Zeit)
- [ ] Progress-Dialog erscheint
- [ ] Fehlerbehandlung funktioniert
- [ ] EXIF-Cache wird nach Update geleert
- [ ] Preview aktualisiert sich

### **Edge Cases:**
- [ ] Keine Dateien ausgewählt → Warnung
- [ ] ExifTool nicht verfügbar → Warnung
- [ ] Dateien ohne EXIF → "No change"
- [ ] Gemischte Dateien (mit/ohne EXIF) → Partielle Updates
- [ ] Videos mit QuickTime-Timestamps

### **Performance:**
- [ ] 100 Dateien < 30 Sekunden
- [ ] 596 Dateien < 2 Minuten
- [ ] Keine Freezes während Verarbeitung

---

## 🔄 Workflow

### **Typischer Ablauf:**

1. **Dateien auswählen**
   ```
   Select Files/Folder → 596 Dateien geladen
   ```

2. **Time Shift öffnen**
   ```
   Tools → ⏰ EXIF Time Shift...
   ```

3. **Einstellungen vornehmen**
   ```
   Direction: Forward
   Time: 1 hours 0 minutes
   ```

4. **Preview prüfen**
   ```
   IMG_001.JPG: 11:00 → 12:00 ✓
   IMG_002.JPG: 11:05 → 12:05 ✓
   ```

5. **Anwenden**
   ```
   [Apply] → Progress Dialog → Fertig!
   ```

6. **Verifizieren**
   ```
   Preview in Hauptfenster prüfen
   Sortierung sollte korrekt sein
   ```

---

## 🚀 Zukünftige Erweiterungen (Optional)

### **Mögliche Features:**

1. **Undo-Funktion**
   ```python
   # Backup der Original-Timestamps speichern
   original_timestamps = {}
   # Restore-Button im Dialog
   ```

2. **Batch-Gruppen**
   ```python
   # Verschiedene Shifts für verschiedene Kameras
   shift_groups = {
       'Camera_A': timedelta(hours=0),
       'Camera_B': timedelta(hours=1),
   }
   ```

3. **Auto-Detect Shift**
   ```python
   # Vergleiche Dateinamen-Zeitstempel mit EXIF
   # Schlage Korrektur vor
   ```

4. **GPS-basierte Zeitzone**
   ```python
   # Wenn GPS-Daten vorhanden
   # Automatische Zeitzone-Korrektur
   ```

5. **CSV Export/Import**
   ```python
   # Export: Original → Neu
   # Import: Anwenden von gespeicherten Shifts
   ```

---

## 📚 Code-Referenzen

### **Haupt-Komponenten:**

```python
# Dialog-Klasse
class ExifTimeShiftDialog(QDialog):
    def __init__(self, parent, files, exiftool_path)
    def setup_ui()
    def load_sample_times()
    def update_preview()
    def apply_time_shift()
    def on_shift_complete(success_count, errors)

# Worker-Thread
class TimeShiftWorker(QThread):
    progress_update = pyqtSignal(str)
    progress_value = pyqtSignal(int)
    finished_signal = pyqtSignal(int, list)
    
    def run()  # ExifTool batch processing
```

### **Integration:**

```python
# main_application.py
def show_time_shift_dialog(self):
    # Validierung
    if not self.files: return
    if not self.exiftool_path: return
    
    # Dialog öffnen
    dialog = ExifTimeShiftDialog(self, self.files, self.exiftool_path)
    if dialog.exec():
        clear_global_exif_cache()
        self.update_preview()
```

---

## ✅ Zusammenfassung

**Feature:** ⏰ EXIF Time Shift  
**Zweck:** Korrektur falsch eingestellter Kamera-Uhren  
**Umfang:** +/- Stunden und Minuten für alle Dateien  
**UI:** GUI-Dialog mit Live-Preview  
**Backend:** ExifTool mit `-AllDates+=` Befehl  
**Performance:** ~5-10 files/sec  
**Sicherheit:** Warnung vor permanenten Änderungen  

**Status:** ✅ Bereit zum Testen!
