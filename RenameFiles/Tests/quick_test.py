#!/usr/bin/env python3
"""
Schneller Test der ExifTool-Funktionalität
"""

import os
import shutil

def quick_exiftool_test():
    print("🔍 Schneller ExifTool Test")
    print("=" * 40)
    
    # Test 1: Import
    try:
        import exiftool
        print("✅ ExifTool Python-Paket: Verfügbar")
        EXIFTOOL_AVAILABLE = True
    except ImportError as e:
        print(f"❌ ExifTool Python-Paket: Nicht verfügbar ({e})")
        EXIFTOOL_AVAILABLE = False
        return False
    
    # Test 2: Executable finden
    script_dir = os.path.dirname(os.path.abspath(__file__))
    exiftool_path = os.path.join(script_dir, "exiftool-13.32_64", "exiftool.exe")
    
    print(f"Suche ExifTool in: {exiftool_path}")
    if os.path.exists(exiftool_path):
        print("✅ ExifTool.exe: Gefunden")
    else:
        print("❌ ExifTool.exe: Nicht gefunden")
        return False
    
    # Test 3: Funktionalität testen
    try:
        with exiftool.ExifToolHelper(executable=exiftool_path) as et:
            version = et.execute("-ver")
            print(f"✅ ExifTool funktioniert: Version {version}")
            return True
    except Exception as e:
        print(f"❌ ExifTool Fehler: {e}")
        return False

if __name__ == "__main__":
    success = quick_exiftool_test()
    if success:
        print("\n🎉 ExifTool ist bereit!")
    else:
        print("\n⚠️  ExifTool hat Probleme!")
