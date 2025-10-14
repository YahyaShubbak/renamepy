# 🔧 CHRONOLOGISCHE SORTIERUNG - IMPLEMENTATION

**Datum:** 2025-10-14  
**Änderung:** EXIF-basierte Sortierung ist nun IMMER aktiv  
**Datei:** `modules/rename_engine.py`

---

## 🎯 Was wurde geändert?

### **VORHER:**
- Sortierung nur bei **Continuous Counter** Modus nach EXIF-Datum
- Im Standard-Modus: **Alphabetische Sortierung** nach Dateinamen
- Keine sekundengenaue Berücksichtigung

### **NACHHER:**
- **IMMER** Sortierung nach EXIF DateTimeOriginal
- **Sekundengenau** - vollständiger Timestamp (YYYY-MM-DD HH:MM:SS)
- Fallback zu `mtime` (Datei-Änderungszeit) wenn kein EXIF
- Dateinamen-Nummer als finaler Tiebreaker

---

## 📋 Sortier-Priorität (neu)

```python
# Zeilen 280-337 in rename_engine.py

def get_exif_sort_key(group):
    # Priorität:
    1. EXIF DateTimeOriginal (Sekunden-genau)
    2. Datei-Änderungszeit (mtime) [Fallback]
    3. Nummer im Dateinamen (z.B. IMG_1234 → 1234)
    4. Dateipfad (Tiebreaker)
    
    return (exif_datetime, file_number, first_file)
```

### **Konkret:**

1. **EXIF-Timestamp extrahieren:**
   - Liest EXIF:DateTimeOriginal, EXIF:CreateDate, QuickTime:CreateDate
   - Format: `"2024:01:15 10:30:45"` → `datetime(2024, 1, 15, 10, 30, 45)`
   - **Sekundengenau!**

2. **Fallback zu mtime:**
   - Wenn kein EXIF vorhanden
   - Nutzt Datei-Änderungszeit

3. **Filename-Nummer:**
   - Extrahiert erste Zahl aus Dateinamen
   - `DSC00123.JPG` → 123
   - Als Tiebreaker bei identischen Timestamps

---

## 🔬 Performance-Auswirkungen

### **Zusätzliche Operationen pro Datei-Gruppe:**

1. **EXIF-Datum extrahieren:** `get_selective_cached_exif_data()` (gecached!)
2. **Vollständiges EXIF lesen:** `get_exiftool_metadata_shared()` (für Timestamp)
3. **Datetime-Parsing:** String → datetime Objekt
4. **Sortierung:** Python's Timsort (sehr effizient)

### **Erwartete Performance:**

Basierend auf bisherigen Benchmarks:
- **ExifTool ist bereits optimiert** (persistent mode, 51.1 files/sec)
- **EXIF-Cache reduziert** wiederholte Lesevorgänge
- **Sortierung ist O(n log n)** - sehr schnell für 596 Dateien

**Geschätzte zusätzliche Zeit:**
- 596 Dateien: **+2-5 Sekunden** (Worst Case)
- Amortisiert durch Cache: **+1-2 Sekunden** (Best Case)

---

## 🧪 Performance-Test

### Test-Script erstellt:
```bash
python test_exif_sorting_performance.py [ORDNER] --runs 3
```

**Was wird getestet:**
- ✅ EXIF-Extraktion für alle Dateien
- ✅ Datetime-Parsing
- ✅ Sortierung nach Timestamp
- ✅ Durchsatz (groups/sec, files/sec)
- ✅ Sample der sortierten Reihenfolge

**Beispiel-Output:**
```
Files:          596
Groups:         596
Average Time:   3.45 seconds
Throughput:     172.8 groups/sec
```

---

## 📊 Beispiel: Sortier-Ergebnis

### **Vorher (alphabetisch):**
```
DSC00005.JPG (2024-01-15 12:30:45) → 001
DSC00010.JPG (2024-01-15 10:00:00) → 002
DSC00020.JPG (2024-01-15 09:15:30) → 003
```

### **Nachher (chronologisch):**
```
DSC00020.JPG (2024-01-15 09:15:30) → 001
DSC00010.JPG (2024-01-15 10:00:00) → 002
DSC00005.JPG (2024-01-15 12:30:45) → 003
```

**✅ Sortierung nach tatsächlicher Aufnahme-Reihenfolge!**

---

## 🎯 Use Cases

### **Szenario 1: Fotos von mehreren Kameras**
```
KameraA_IMG_001.JPG (10:00:00)
KameraB_DSC_001.JPG (10:05:30)
KameraA_IMG_002.JPG (10:10:15)
```

**Sortierung:**
```
001 → KameraA_IMG_001.JPG (10:00:00)
002 → KameraB_DSC_001.JPG (10:05:30)
003 → KameraA_IMG_002.JPG (10:10:15)
```

**✅ Chronologisch korrekt, unabhängig vom Kamera-Namen!**

### **Szenario 2: Importierte Fotos mit neuen mtime**
```
IMG_5000.JPG (EXIF: 2024-01-15 10:00, mtime: 2024-10-14)
IMG_5001.JPG (EXIF: 2024-01-15 09:00, mtime: 2024-10-14)
```

**Sortierung:**
```
001 → IMG_5001.JPG (EXIF: 09:00)  ← Nutzt EXIF, nicht mtime!
002 → IMG_5000.JPG (EXIF: 10:00)
```

**✅ EXIF hat Vorrang vor mtime!**

---

## ⚙️ Code-Änderungen

### **Datei:** `modules/rename_engine.py`

**Zeilen 277-337:**

```python
# ALWAYS sort by EXIF timestamp for chronological ordering
self.progress_update.emit("Sorting files by capture time...")

def get_exif_sort_key(group):
    """Sort key based on EXIF DateTimeOriginal (down to seconds)"""
    first_file = group[0]
    
    # Try to get EXIF timestamp
    exif_datetime = None
    if self.exif_method:
        try:
            # Get EXIF date
            date_str, _, _ = exif_processor.get_selective_cached_exif_data(...)
            
            if date_str:
                # Get full datetime with seconds
                raw_meta = exif_processor.get_exiftool_metadata_shared(...)
                
                # Parse: "2024:01:15 10:30:45" → datetime object
                datetime_fields = [
                    'EXIF:DateTimeOriginal',
                    'EXIF:CreateDate', 
                    'QuickTime:CreateDate',
                    'QuickTime:CreationDate'
                ]
                for field in datetime_fields:
                    if field in raw_meta:
                        dt_str = raw_meta[field]
                        dt_str_clean = dt_str.replace(':', '-', 2)
                        exif_datetime = datetime.strptime(dt_str_clean, "%Y-%m-%d %H:%M:%S")
                        break
        except:
            pass
    
    # Fallback to mtime
    if not exif_datetime:
        mtime = os.path.getmtime(first_file)
        exif_datetime = datetime.fromtimestamp(mtime)
    
    # Extract filename number as tiebreaker
    file_number = extract_number_from_filename(first_file)
    
    return (exif_datetime, file_number, first_file)

# Sort all file groups
file_groups.sort(key=get_exif_sort_key)
```

**Ersetzt:**
```python
# OLD: Only sort when use_date=False
if not self.use_date:
    def earliest(group):
        mtimes = [os.path.getmtime(p) for p in group]
        return min(mtimes)
    file_groups.sort(key=earliest)
```

---

## ✅ Testing-Checkliste

### **Vor dem Commit:**
- [ ] Performance-Test mit Bilbao-Fotos (596 files)
- [ ] Überprüfe Sortier-Reihenfolge manuell
- [ ] Teste mit Dateien ohne EXIF (mtime Fallback)
- [ ] Teste mit gemischten Kameras
- [ ] Teste mit Videos (QuickTime:CreateDate)

### **Performance-Ziele:**
- [ ] Sortierung < 5 Sekunden für 596 Dateien
- [ ] Gesamte Umbenennung < 20 Sekunden
- [ ] Durchsatz > 30 files/sec

---

## 🚀 Nächste Schritte

1. **Performance-Test ausführen:**
   ```bash
   python test_exif_sorting_performance.py "PFAD_ZU_BILBAO_FOTOS" --runs 3
   ```

2. **Ergebnisse prüfen:**
   - Ist die Sortierung korrekt?
   - Ist die Performance akzeptabel?

3. **GUI-Test:**
   - Umbenennung durchführen
   - Preview prüfen
   - Sortierung visuell validieren

4. **Dokumentation:**
   - Update README.md mit neuer Sortier-Logik
   - Add to CHANGELOG.md

---

## 💡 Mögliche Optimierungen

Falls Performance nicht ausreichend:

1. **Parallel EXIF-Extraktion:**
   ```python
   from concurrent.futures import ThreadPoolExecutor
   with ThreadPoolExecutor(max_workers=4) as executor:
       timestamps = list(executor.map(get_exif_timestamp, file_groups))
   ```

2. **Lazy Evaluation:**
   - Nur EXIF lesen wenn wirklich sortiert werden muss
   - Cache erweitern

3. **Batch-Processing:**
   - ExifTool kann mehrere Dateien gleichzeitig verarbeiten
   - `-json` Output für schnelleres Parsing

**Aktuell: Einfache, klare Implementierung bevorzugt** ✅
