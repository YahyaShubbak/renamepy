#!/usr/bin/env python3
"""
Debug script to check what's happening with exiftool detection in the main program.
"""

import os
import shutil

def is_exiftool_installed():
    print("=== DEBUG: ExifTool Detection ===")
    
    # Test 1: System PATH
    exe = shutil.which("exiftool")
    print(f"1. System PATH check: {exe}")
    if exe:
        return exe
    
    # Test 2: Current directory
    local = os.path.join(os.getcwd(), "exiftool.exe")
    print(f"2. Current directory check: {local}")
    print(f"   File exists: {os.path.exists(local)}")
    if os.path.exists(local):
        return local
    
    # Test 3: exiftool-13.32_64 subdirectory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    custom = os.path.join(script_dir, "exiftool-13.32_64", "exiftool.exe")
    print(f"3. Subdirectory check: {custom}")
    print(f"   Script dir: {script_dir}")
    print(f"   File exists: {os.path.exists(custom)}")
    if os.path.exists(custom):
        return custom
    
    print("4. No exiftool found")
    return None

def test_exiftool_import():
    print("\n=== DEBUG: ExifTool Import ===")
    try:
        import exiftool
        print("✅ exiftool Python package available")
        EXIFTOOL_AVAILABLE = True
    except ImportError as e:
        print(f"❌ exiftool Python package not available: {e}")
        EXIFTOOL_AVAILABLE = False
    
    return EXIFTOOL_AVAILABLE

def main():
    print("🔍 ExifTool Debug Check for Main Program")
    print("=" * 60)
    
    # Test detection
    exiftool_path = is_exiftool_installed()
    print(f"\nDetected exiftool path: {exiftool_path}")
    
    # Test import
    exiftool_available = test_exiftool_import()
    
    # Final logic (same as in main program)
    print("\n=== DEBUG: Main Program Logic ===")
    if exiftool_available and exiftool_path:
        exif_method = "exiftool"
        print("✅ Would use: exiftool (recommended)")
    else:
        try:
            from PIL import Image
            from PIL.ExifTags import TAGS
            exif_method = "pillow"
            print("⚠️  Would use: Pillow (limited RAW support)")
        except ImportError:
            exif_method = None
            print("❌ Would use: None (no EXIF support)")
    
    print(f"\nFinal EXIF method: {exif_method}")
    print(f"ExifTool path: {exiftool_path}")
    
    return exif_method, exiftool_path

if __name__ == "__main__":
    main()
