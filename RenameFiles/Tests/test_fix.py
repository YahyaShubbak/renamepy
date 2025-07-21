#!/usr/bin/env python3

import sys
import os
sys.path.append('.')

from RenameFiles import FileRenamerApp, is_exiftool_installed, EXIFTOOL_AVAILABLE

print("=== ExifTool Detection Test ===")
print(f"EXIFTOOL_AVAILABLE (Python package): {EXIFTOOL_AVAILABLE}")

path = is_exiftool_installed()
print(f"is_exiftool_installed() returns: {path}")

if EXIFTOOL_AVAILABLE:
    print("✅ ExifTool Python package is available")
    
    # Test if ExifTool works without explicit path
    try:
        import exiftool
        with exiftool.ExifToolHelper() as et:
            # This should work even without explicit path if exiftool is in PATH
            print("✅ ExifTool works without explicit path!")
    except Exception as e:
        print(f"❌ ExifTool failed without explicit path: {e}")
    
    # Test with explicit path if available
    if path:
        try:
            with exiftool.ExifToolHelper(executable=path) as et:
                print(f"✅ ExifTool works with explicit path: {path}")
        except Exception as e:
            print(f"❌ ExifTool failed with explicit path: {e}")
else:
    print("❌ ExifTool Python package NOT available")

print("\n=== App Initialization Test ===")
app = FileRenamerApp()
print(f"Selected EXIF method: {app.exif_method}")
print(f"ExifTool path: {app.exiftool_path}")
