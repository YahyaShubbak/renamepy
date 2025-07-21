#!/usr/bin/env python3

import sys
import os
sys.path.append('.')

from RenameFiles import is_exiftool_installed, EXIFTOOL_AVAILABLE, extract_exif_fields

print("=== Simple ExifTool Test ===")
print(f"EXIFTOOL_AVAILABLE: {EXIFTOOL_AVAILABLE}")

path = is_exiftool_installed()
print(f"ExifTool path: {path}")

if EXIFTOOL_AVAILABLE and path:
    print("✅ All conditions met for ExifTool")
    
    # Test with a non-existent file (should give a specific error)
    try:
        result = extract_exif_fields('test.jpg', 'exiftool', path)
        print(f"Result: {result}")
    except Exception as e:
        if 'File not found' in str(e) or 'does not exist' in str(e) or 'No such file' in str(e):
            print("✅ ExifTool is working! (File not found error is expected)")
        else:
            print(f"❌ Unexpected error: {e}")
else:
    print(f"❌ Conditions not met:")
    print(f"  - EXIFTOOL_AVAILABLE: {EXIFTOOL_AVAILABLE}")
    print(f"  - exiftool_path: {path}")
