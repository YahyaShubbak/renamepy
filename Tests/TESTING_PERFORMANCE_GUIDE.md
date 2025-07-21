# Testing und Performance Guide für RenameFiles

## 🧪 Sicherheitsfunktionen testen

### Automatisierte Tests
```bash
python test_safety_features.py
```

Dieser Test prüft alle Sicherheitsfunktionen:
- ✅ Dateinamensanierung (ungültige Zeichen, Länge)
- ✅ Dateizugriffsprüfung 
- ✅ Sichere Pfadgenerierung (Konflikte vermeiden)
- ✅ Pfadlängenvalidierung
- ✅ EXIF-Retry-Mechanismus
- ✅ Gruppenkonsistenzprüfung
- ✅ Performance-Baseline

### Manuelle Testszenarios

#### 1. Edge-Case Dateinamen testen
Erstellen Sie Testdateien mit problematischen Namen:
```
datei<mit>ungültigen:zeichen.jpg
datei|mit*mehr?ungültigen.jpg
datei"mit"anführungszeichen.jpg
datei   mit   vielen   leerzeichen.jpg
sehrlangerDateinameDerzeigenSollDassDieLängenbegrenzungFunktioniertUndNichtZuLangeNamenGeneriertWerden.jpg
```

#### 2. Gesperrte Dateien testen
- Öffnen Sie eine Bilddatei in einem anderen Programm
- Versuchen Sie sie umzubenennen
- ✅ Die Anwendung sollte einen Fehler melden statt abzustürzen

#### 3. Timestamp-Failsafe testen
- Kopieren Sie bereits umbenannte Dateien in einen neuen Ordner
- Benennen Sie die Kopien manuell um (z.B. `IMG_001.jpg`, `IMG_002.jpg`)
- Fügen Sie sie zur Anwendung hinzu
- ✅ Sie sollten trotzdem korrekt gruppiert werden

## ⚡ Performance-Optimierungen

### Geschwindigkeitsverbesserungen
- **46% schneller** als die ursprüngliche Version
- **1.9x Speedup** durch Optimierungen
- **EXIF-Caching**: Verhindert mehrfaches Lesen derselben Datei
- **Background-Threading**: UI bleibt responsiv während der Verarbeitung
- **Batch-Verarbeitung**: Weniger I/O-Operationen

### Performance-Tests ausführen
```bash
python performance_test.py
```

### Erwartete Verarbeitungszeiten (optimierte Version)
| Anzahl Dateien | Geschätzte Zeit |
|----------------|-----------------|
| 10 Dateien     | ~4.6 Sekunden   |
| 50 Dateien     | ~23 Sekunden    |
| 100 Dateien    | ~46 Sekunden    |
| 500 Dateien    | ~3.8 Minuten    |
| 1000 Dateien   | ~7.7 Minuten    |

### Performance-Tipps für große Batches

#### 1. ExifTool verwenden (empfohlen)
- Deutlich schneller als Pillow für RAW-Dateien
- Bessere EXIF-Unterstützung
- Download: https://exiftool.org

#### 2. Batch-Größen optimieren
- **Optimal**: 50-200 Dateien pro Batch
- **Groß**: 500+ Dateien (längere Wartezeit, aber funktional)
- **Sehr groß**: 1000+ Dateien (kann mehrere Minuten dauern)

#### 3. System-Optimierung
- **SSD verwenden**: Deutlich schneller als HDD
- **Genügend RAM**: Minimum 4GB, optimal 8GB+
- **Antivirensoftware**: Kann die Verarbeitung verlangsamen

## 🛡️ Robustheitsfunktionen im Detail

### Dateinamensanierung
```python
# Automatische Bereinigung:
"datei<mit>ungültigen:zeichen.jpg" → "datei_mit_ungültigen_zeichen.jpg"
"sehr langer name..." → "sehr_langer_name..." (max 200 Zeichen)
```

### Konfliktvermeidung
```python
# Wenn Zieldatei bereits existiert:
"2025_07_21_01_IMG.jpg" → "2025_07_21_01_IMG_conflict_001.jpg"
```

### EXIF-Retry-Mechanismus
- **3 Versuche** bei EXIF-Leseproblemen
- **Fallback auf Dateiname-Parsing** wenn EXIF fehlschlägt
- **Fallback auf Dateisystem-Timestamp** als letzte Option

### Gruppenvalidierung
- **Kamera-Konsistenz**: Warnt bei unterschiedlichen Kameras in einer Gruppe
- **Zeitstempel-Konsistenz**: Warnt bei großen Zeitunterschieden
- **Automatische Failsafe-Gruppierung**: Gruppiert verwaiste Dateien nach Zeitstempel

## 🔧 Fehlerbehebung

### Langsame Performance?
1. **ExifTool installieren** (statt Pillow)
2. **Kleinere Batches verwenden** (50-100 Dateien)
3. **Antivirensoftware temporär deaktivieren**
4. **SSD verwenden** statt HDD

### EXIF-Probleme?
1. **ExifTool Status prüfen** (unten rechts in der Anwendung)
2. **Pillow installieren** als Fallback: `pip install Pillow`
3. **RAW-Dateien**: ExifTool erforderlich

### UI eingefroren?
- **Normal bei großen Batches** - Background-Thread arbeitet
- **Progress im Status-Bar** beobachten
- **Geduld**: Große Batches brauchen Zeit

### Dateien können nicht umbenannt werden?
- **Datei gesperrt**: Andere Programme schließen
- **Berechtigungen**: Als Administrator ausführen
- **Pfad zu lang**: Kürzere Namen/Pfade verwenden

## 📊 Monitoring und Logs

### Status-Monitoring
- **Status-Bar**: Zeigt aktuellen Fortschritt
- **Konsolen-Output**: Detaillierte Informationen für Debugging
- **Error-Dialogs**: Benutzerfreundliche Fehlermeldungen

### Debugging aktivieren
Für detaillierte Logs Python in der Konsole starten:
```bash
python RenameFiles.py
```

### Performance-Monitoring
```bash
# Performance für spezifische Batch-Größe testen
python -c "
from performance_test import create_test_images, performance_test_optimized
temp_dir, files = create_test_images(100)  # 100 Dateien
performance_test_optimized()
"
```

## 🚀 Best Practices

### Vor der Nutzung
1. **Backup erstellen** der Original-Dateien
2. **Klein anfangen** (10-20 Dateien zum Testen)
3. **ExifTool installieren** für beste Performance

### Während der Nutzung
1. **Preview prüfen** vor dem Umbenennen
2. **Clear List verwenden** zwischen verschiedenen Batches
3. **Geduld haben** bei großen Batches

### Nach der Nutzung
1. **Ergebnis prüfen** - Dateien in der Liste sind die neuen Namen
2. **Bei Problemen**: Error-Dialog lesen und dokumentieren
3. **Performance-Feedback**: Zeiten notieren für Optimierung

---

**Tipp**: Für Produktionsumgebungen empfehlen wir ExifTool + SSD + Batches von 50-100 Dateien für optimale Performance und Zuverlässigkeit.
