# Video Support - Implementierung

## Überblick

Die RenameFiles-Anwendung wurde erfolgreich um Video-Unterstützung erweitert. Sie kann jetzt sowohl Bilder als auch Videos basierend auf deren Metadaten umbenennen.

## Unterstützte Video-Formate

Die folgenden Video-Formate werden unterstützt:
- **MP4** (.mp4) - Am häufigsten verwendet
- **MOV** (.mov) - Apple QuickTime
- **AVI** (.avi) - Windows Standard
- **MKV** (.mkv) - Matroska Container
- **M4V** (.m4v) - iTunes-kompatibel
- **3GP** (.3gp) - Mobile Geräte
- **WMV** (.wmv) - Windows Media
- **FLV** (.flv) - Flash Video
- **WebM** (.webm) - Web-Standard
- **MPEG** (.mpg, .mpeg, .m2v) - MPEG-Standards
- **AVCHD** (.mts, .m2ts) - Camcorder-Formate
- **Weitere** (.ts, .vob, .asf, .rm, .rmvb, .f4v, .ogv)

## Metadaten-Extraktion

### ExifTool (Empfohlen)
ExifTool bietet die beste Video-Unterstützung:
- **Aufnahmedatum**: Aus Video-Metadaten
- **Kamera-Modell**: Bei Kamera-aufgenommenen Videos
- **Objektiv**: Bei kompatiblen Kameras
- **Dauer**: Video-Länge
- **GPS-Daten**: Standortinformationen
- **Technische Details**: Auflösung, Framerate, Codec

### Pillow (Begrenzt)
Pillow unterstützt nur Bilder, nicht Videos. Bei Video-Dateien wird eine entsprechende Warnung angezeigt.

## Neue Funktionen

### 1. Datei-Erkennung
```python
is_video_file(filename)    # Nur Videos
is_image_file(filename)    # Nur Bilder  
is_media_file(filename)    # Bilder + Videos
```

### 2. Erweiterte Dateiauswahl
Der Datei-Dialog bietet jetzt mehrere Filter:
- **Media Files**: Alle unterstützten Formate
- **Image Files**: Nur Bilder
- **Video Files**: Nur Videos
- **All Files**: Alle Dateien

### 3. Video-Metadaten im Status
Bei Klick auf Video-Dateien wird im Status-Bereich angezeigt:
- Video-Dauer (falls verfügbar)
- Frame-Anzahl (falls verfügbar)
- Allgemeine Video-Info

### 4. Erweiterte Metadaten-Dialoge
Doppelklick auf Videos öffnet einen Dialog mit vollständigen Metadaten, einschließlich technischer Video-Details.

## Anwendung

### Video-Dateien hinzufügen
1. **Button "📄 Select Media Files"** - Wählt Bilder und Videos
2. **Drag & Drop** - Unterstützt alle Medien-Formate
3. **Ordner auswählen** - Scannt rekursiv nach Medien-Dateien

### Umbenennung
Videos werden genauso behandelt wie Bilder:
- Gleiche Namenskonventionen
- Metadaten-basierte Sortierung
- Batch-Verarbeitung
- Rückgängig-Funktion

### Beispiel
**Vorher:**
```
IMG_0123.MP4
VID_20250730_142530.MOV
```

**Nachher (mit Datum + Kamera + Zähler):**
```
2025-07-30-A7R3-001.MP4
2025-07-30-A7R3-002.MOV
```

## Voraussetzungen

### Für optimale Video-Unterstützung:
1. **ExifTool KOMPLETT installiert** ⚠️ **WICHTIG:**
   - **Gesamten Ordner** aus der ZIP-Datei extrahieren
   - **NICHT nur die exiftool.exe kopieren!** - Das führt zu Abstürzen
   - Benötigte Struktur:
     ```
     Programmordner/
     ├── RenameFiles.py
     └── exiftool-13.32_64/          # Kompletter Ordner!
         ├── exiftool.exe
         ├── perl.exe               # Perl-Interpreter
         ├── perl532.dll            # Perl-Bibliothek
         ├── lib/                   # Perl-Module (ESSENTIAL)
         │   ├── Image/
         │   ├── File/
         │   └── (viele weitere)
         └── exiftool_files/        # ExifTool-Skripte
     ```
2. **Vollständige Metadaten**: Besonders bei Kamera-Videos
3. **Unterstützte Formate**: Siehe Liste oben

### Fallback-Verhalten:
- **Ohne ExifTool**: Nur Datei-Datum verfügbar
- **Incomplete ExifTool**: Anwendung erkennt fehlende Abhängigkeiten und zeigt Warnung
- **Ohne Metadaten**: Verwendung des Datei-Änderungsdatums
- **Unbekannte Formate**: Werden übersprungen

## Technische Details

### Performance
- **Gleiche Cache-Optimierungen** wie bei Bildern
- **Batch-Verarbeitung** für große Video-Sammlungen
- **Hintergrund-Threads** verhindern UI-Einfrieren

### Kompatibilität
- **Alle ExifTool-unterstützten Video-Formate**
- **Camera RAW + Video** gemischt möglich
- **Verschiedene Codecs** werden unterstützt

## Tipps für beste Ergebnisse

### 1. Kamera-Videos
Moderne Kameras (Canon, Nikon, Sony) speichern umfangreiche Metadaten in Videos:
- Aufnahmedatum und -zeit
- Kamera-Modell und Einstellungen
- Objektiv-Informationen
- GPS-Koordinaten

### 2. Smartphone-Videos
Smartphone-Videos enthalten oft:
- Aufnahmedatum
- Geräte-Modell
- GPS-Standort
- Orientierung

### 3. Bearbeitete Videos
Videos von Videobearbeitungs-Software können:
- Original-Metadaten verlieren
- Neue Erstellungsdaten haben
- Weniger Kamera-Informationen enthalten

## Fehlerbehebung

### Problem: Video wird nicht erkannt
- **Lösung**: Prüfen Sie, ob die Dateierweiterung in der unterstützten Liste steht

### Problem: Keine Video-Metadaten
- **Lösung**: Stellen Sie sicher, dass ExifTool installiert ist
- **Alternative**: Verwenden Sie Datei-Änderungsdatum

### Problem: Slow Performance bei vielen Videos
- **Lösung**: Videos sind größer als Bilder - das ist normal
- **Tipp**: Batch-Verarbeitung läuft im Hintergrund

Die Video-Unterstützung erweitert die Anwendung erheblich und macht sie zu einem vollständigen Medien-Datei-Organizer!
