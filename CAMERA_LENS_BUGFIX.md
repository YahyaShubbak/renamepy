# BUGFIX: Camera/Lens Labels zeigen "no files selected" trotz geladener Dateien

## Problem
- 906 Bilder sind geladen
- Camera und Lens Labels zeigen "(no files selected)" statt erkannter Kamera/Objektiv-Daten
- Preview für Kamera und Linse bleibt leer

## Root Cause Analysis
**Ursprünglich**: `extract_camera_info()` verwendete falsche EXIF-Extraktion
```python
# Fehlerhaft:
exif_data = self.exif_handler.extract_exif(sample_file)  # Returniert Tupel (date, camera, lens)
camera = exif_data.get('camera_model', '')  # Versucht Dictionary-Zugriff auf Tupel!
```

## Solution Implemented

### 1. ✅ Korrigierte EXIF-Extraktion
```python
def extract_camera_info(self):
    # Neue Implementierung:
    date_taken, camera_model, lens_model = get_selective_cached_exif_data(
        sample_file, self.exif_handler.current_method, self.exif_handler.exiftool_path,
        need_date=False, need_camera=True, need_lens=True
    )
```

### 2. ✅ Verbesserte Label-Anzeige
```python
def update_camera_lens_labels(self):
    if self.camera_models:
        # Erkannte Kamera anzeigen
        self.camera_model_label.setText(f"({camera})")
    else:
        if self.files:
            # Fallback-Anzeige wenn Dateien geladen aber keine EXIF-Daten
            self.camera_model_label.setText("(using fallback: ILCE-7CM2)")
        else:
            self.camera_model_label.setText("(no files selected)")
```

### 3. ✅ Robuste Multi-File-Sampling
- Prüft die ersten 5 Dateien statt nur der ersten
- Erhöht Chance auf EXIF-Daten-Erkennung
- Stoppt bei erfolgreichem Fund von Camera + Lens

### 4. ✅ Korrekte State-Verwaltung
- `clear_file_list()` leert jetzt auch camera_models und lens_models
- Konsistente Label-Updates bei allen Operationen

## Expected Results
**Wenn EXIF-Daten gefunden werden**:
- Camera Label: `(Sony ILCE-7RM5)` (tatsächlich erkannte Kamera)
- Lens Label: `(FE 20-70mm F4 G)` (tatsächlich erkanntes Objektiv)

**Wenn keine EXIF-Daten gefunden werden**:
- Camera Label: `(using fallback: ILCE-7CM2)`
- Lens Label: `(using fallback: FE-20-70mm-F4-G)`

**Beim Rename**:
- Fallback-Werte werden in Dateinamen verwendet wenn aktiviert
- Konsistenz zwischen Label-Anzeige und tatsächlichem Rename

## Technical Changes
**File**: `modules/original_ui_complete.py`
- `extract_camera_info()`: Korrigierte EXIF-Extraktion
- `update_camera_lens_labels()`: Verbesserte Label-Anzeige mit Fallback-Hinweis
- `clear_file_list()`: Korrekte State-Bereinigung

## Status
✅ **FIXED**: Camera/Lens Labels sollten jetzt korrekt angezeigt werden
🔄 **TESTING**: Benötigt User-Test mit den geladenen Bildern
