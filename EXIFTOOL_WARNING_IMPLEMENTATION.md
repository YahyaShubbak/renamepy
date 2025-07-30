# ExifTool Warning System Implementation

## Was wurde implementiert:

### 1. **ExifToolWarningDialog Klasse**
- Vollständiges Warnfenster mit professionellem Design
- Erklärt was ExifTool ist und warum es besser als Pillow ist
- Anleitung zur Installation mit direktem Link
- "Don't show again" Option mit persistenter Speicherung
- Zwei Buttons: "Open Download Page" und "Continue with Pillow"

### 2. **Verbesserte Status-Anzeige**
- **ExifTool verfügbar**: `"EXIF method: ExifTool v13.32 (recommended) ✓"` (grün, fett)
- **Nur Pillow verfügbar**: `"EXIF method: Pillow (limited) ⚠️"` (orange, fett)
- **Keine EXIF-Unterstützung**: `"No EXIF support available ❌"` (rot, fett)

### 3. **Automatische Warning-Logik**
- Zeigt Warning nur wenn Pillow verwendet wird (ExifTool nicht verfügbar)
- Verwendet QSettings für persistente "Don't show again" Einstellung
- Wird nach vollständiger UI-Initialisierung angezeigt

### 4. **Benutzerfreundliche Features**
- Warning-Dialog ist modal und zentriert
- Klickbarer Link öffnet ExifTool Download-Seite
- Professionelles Design mit Warning-Icon
- Detaillierte Erklärung der Vorteile

## Verhalten:

### **Beim Programmstart:**
1. **ExifTool installiert** → Keine Warnung, grüner Status
2. **Nur Pillow verfügbar** → Warning-Dialog erscheint, oranger Status nach Schließen
3. **Nichts verfügbar** → Keine Warnung, roter Status

### **Nach "Don't show again":**
- Warning wird nicht mehr angezeigt
- Status bleibt orange mit entsprechendem Text
- Einstellung wird dauerhaft gespeichert

## Technische Details:

### **QSettings Speicherung:**
- Organisation: "RenameFiles"
- Anwendung: "ExifToolWarning"  
- Key: "show_exiftool_warning"

### **Dialog-Verhalten:**
- `exec()`: Blockiert bis Benutzer reagiert
- `open_download_page()`: Öffnet Browser und schließt Dialog
- `should_show_again()`: Gibt Checkbox-Status zurück

### **UI-Integration:**
- Dialog wird nach `QApplication.processEvents()` angezeigt
- Stellt sicher, dass Haupt-UI vollständig gerendert ist
- Verwendet konsistentes Styling mit Rest der Anwendung

## Testen:
Verwenden Sie `test_exiftool_warning.py` um das Warning-Dialog separat zu testen.
