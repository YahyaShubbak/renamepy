#!/usr/bin/env python3
"""
Debug script to test ExifTool detection
"""

import os
import sys

# Add modules to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'modules'))

print("="*60)
print("🔍 ExifTool Detection Debug")
print("="*60)

# Test 1: Check if exiftool module is available
print("\n1️⃣ Testing PyExifTool import...")
try:
    import exiftool
    print("   ✅ PyExifTool module imported successfully")
    EXIFTOOL_AVAILABLE = True
except ImportError as e:
    print(f"   ❌ PyExifTool import failed: {e}")
    EXIFTOOL_AVAILABLE = False

# Test 2: Check if exiftool executable exists
print("\n2️⃣ Checking for exiftool executable...")
script_dir = os.path.dirname(os.path.abspath(__file__))
exiftool_path = os.path.join(script_dir, "exiftool-13.33_64", "exiftool(-k).exe")
print(f"   Looking for: {exiftool_path}")
if os.path.exists(exiftool_path):
    print(f"   ✅ ExifTool executable found!")
else:
    print(f"   ❌ ExifTool executable NOT found")

# Test 3: Try to run exiftool
print("\n3️⃣ Testing exiftool execution...")
if os.path.exists(exiftool_path):
    import subprocess
    try:
        result = subprocess.run(
            [exiftool_path, "-ver"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            version = result.stdout.strip()
            print(f"   ✅ ExifTool version: {version}")
        else:
            print(f"   ❌ ExifTool execution failed")
            print(f"      stdout: {result.stdout}")
            print(f"      stderr: {result.stderr}")
    except Exception as e:
        print(f"   ❌ Error executing ExifTool: {e}")
else:
    print("   ⏭️  Skipped (executable not found)")

# Test 4: Test find_exiftool_path function
print("\n4️⃣ Testing find_exiftool_path() function...")
try:
    from modules.exif_processor import find_exiftool_path
    detected_path = find_exiftool_path()
    if detected_path:
        print(f"   ✅ Detected path: {detected_path}")
    else:
        print(f"   ❌ find_exiftool_path() returned None")
except Exception as e:
    print(f"   ❌ Error: {e}")
    import traceback
    traceback.print_exc()

# Test 5: Test SimpleExifHandler
print("\n5️⃣ Testing SimpleExifHandler initialization...")
try:
    from modules.main_application import SimpleExifHandler
    handler = SimpleExifHandler()
    print(f"   Current method: {handler.current_method}")
    print(f"   ExifTool path: {handler.exiftool_path}")
    if handler.exiftool_path:
        print(f"   ✅ SimpleExifHandler has ExifTool path")
    else:
        print(f"   ❌ SimpleExifHandler has NO ExifTool path")
except Exception as e:
    print(f"   ❌ Error: {e}")
    import traceback
    traceback.print_exc()

# Test 6: Check EXIFTOOL_AVAILABLE in modules
print("\n6️⃣ Checking EXIFTOOL_AVAILABLE in modules...")
try:
    from modules.exif_processor import EXIFTOOL_AVAILABLE as exif_proc_available
    from modules.main_application import EXIFTOOL_AVAILABLE as main_app_available
    print(f"   exif_processor.EXIFTOOL_AVAILABLE: {exif_proc_available}")
    print(f"   main_application.EXIFTOOL_AVAILABLE: {main_app_available}")
except Exception as e:
    print(f"   ❌ Error: {e}")

print("\n" + "="*60)
print("🎯 Summary:")
print("="*60)
print(f"PyExifTool module: {'✅ Available' if EXIFTOOL_AVAILABLE else '❌ Not available'}")
print(f"ExifTool executable: {'✅ Found' if os.path.exists(exiftool_path) else '❌ Not found'}")
print("\n💡 Recommendation:")
if not EXIFTOOL_AVAILABLE:
    print("   Install PyExifTool: pip install PyExifTool")
elif not os.path.exists(exiftool_path):
    print("   Download ExifTool to exiftool-13.33_64 folder")
else:
    print("   Everything should be working! Check logs for details.")
print("="*60)
