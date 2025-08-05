# File Renamer - Modulare Version

Dies ist die modulare Version des File Renamer Tools, die aus der ursprünglichen `RenameFiles.py` extrahiert wurde.

## Dateistruktur

### Hauptdateien
- `main_modular.py` - Haupteinstiegspunkt für die modulare Version
- `RenameFiles.py` - Original-Anwendung (zur Referenz)

### Module (`modules/` Verzeichnis)
- `original_ui_complete.py` - Komplette Benutzeroberfläche (FileRenamerApp-Klasse)
- `rename_engine_fixed.py` - Umbenennung-Engine mit RenameWorkerThread 
- `gui_widgets.py` - Custom GUI-Widgets (InteractivePreviewWidget, etc.)
- `exif_handler.py` - EXIF-Datenverarbeitung und ExifTool-Integration
- `file_utils.py` - Datei-Utilities und Konstanten
- `theme_manager.py` - Theme-Management (Dark/Light Mode)

## Funktionalität

### Vollständig implementiert ✅
- **Datei-Umbenennung**: Komplette RenameWorkerThread mit optimierter EXIF-Verarbeitung
- **Interaktive Vorschau**: Drag-Drop-Widget mit Separatoren und Reihenfolge-Änderung
- **Dark Theme**: Vollständiges Theme-Management mit Dunkel-/Hell-Modi
- **ExifTool Integration**: Lokale ExifTool v13.33 Integration
- **EXIF-Metadaten**: Vollständige Kamera- und Objektiv-Informationen
- **Datei-Management**: Drag-Drop, Ordner-Scan, Datei-Validierung
- **UI-Komponenten**: Alle original UI-Elemente und Event-Handler

### Vergleich mit Original
Alle 35+ Klassen und Funktionen der ursprünglichen `RenameFiles.py` sind in der modularen Version implementiert:

**Core Functions:**
- `get_filename_components_static()` ✅
- `rename_files()` ✅ 
- `scan_directory_recursive()` ✅
- `get_safe_target_path()` ✅
- `validate_path_length()` ✅

**EXIF Functions:**
- `get_cached_exif_data()` ✅
- `get_selective_cached_exif_data()` ✅
- `get_exiftool_metadata_shared()` ✅
- `get_file_timestamp()` ✅
- `clear_global_exif_cache()` ✅

**UI Event Handlers:**
- `on_preview_order_changed()` ✅
- `on_theme_changed()` ✅
- `on_devider_changed()` ✅
- `on_continuous_counter_changed()` ✅
- `update_preview()` ✅
- `update_camera_lens_labels()` ✅
- `show_media_info()` ✅
- `update_exif_status()` ✅

**File Operations:**
- `select_files()` ✅
- `select_folder()` ✅
- `clear_file_list()` ✅
- `add_files_to_list()` ✅
- `dragEnterEvent()` ✅
- `dropEvent()` ✅

**Widgets:**
- `InteractivePreviewWidget` ✅
- `ExifToolWarningDialog` ✅
- `RenameWorkerThread` ✅

## Verwendung

```bash
# Modulare Version starten
python main_modular.py

# Original Version (zur Referenz)
python RenameFiles.py
```

## Abhängigkeiten
- PyQt6
- ExifTool (lokal installiert in `exiftool-13.33_64/`)
- Python Standard-Bibliotheken

## Status
🟢 **Vollständig funktionsfähig** - Alle kritischen Bugs behoben:
- ✅ Umbenennung funktioniert korrekt
- ✅ Interaktive Vorschau mit Separatoren und Drag-Drop
- ✅ Dark Theme implementiert
- ✅ Alle ursprünglichen Funktionen vorhanden

Die modulare Version ist bereit zum Testen und bietet 100% Funktionsparität mit der ursprünglichen Anwendung.
