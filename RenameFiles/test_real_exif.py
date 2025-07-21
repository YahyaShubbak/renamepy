#!/usr/bin/env python3
"""
Test ExifTool mit einer echten Bilddatei
"""

import os
import sys
sys.path.append('.')

from RenameFiles import extract_exif_fields, is_exiftool_installed

def test_with_real_image():
    print("🔍 Test mit echtem Bild")
    print("=" * 30)
    
    # Finde ExifTool
    exiftool_path = is_exiftool_installed()
    print(f"ExifTool Pfad: {exiftool_path}")
    
    # Suche nach Bilddateien im aktuellen Verzeichnis
    test_files = []
    for ext in ['.jpg', '.jpeg', '.png', '.arw', '.cr2', '.nef']:
        for root, dirs, files in os.walk('.'):
            for file in files:
                if file.lower().endswith(ext):
                    test_files.append(os.path.join(root, file))
                    if len(test_files) >= 3:  # Nur die ersten 3 Dateien testen
                        break
            if len(test_files) >= 3:
                break
        if len(test_files) >= 3:
            break
    
    if not test_files:
        print("❌ Keine Testbilder gefunden")
        return
    
    print(f"Gefundene Testbilder: {len(test_files)}")
    
    for test_file in test_files[:1]:  # Teste nur die erste Datei
        print(f"\nTeste: {os.path.basename(test_file)}")
        
        try:
            date, camera, lens = extract_exif_fields(test_file, "exiftool", exiftool_path)
            print(f"  Datum: {date}")
            print(f"  Kamera: {camera}")
            print(f"  Objektiv: {lens}")
            
            if date or camera or lens:
                print("✅ EXIF-Daten erfolgreich extrahiert!")
            else:
                print("⚠️ Keine EXIF-Daten gefunden")
                
        except Exception as e:
            print(f"❌ Fehler: {e}")

if __name__ == "__main__":
    test_with_real_image()
