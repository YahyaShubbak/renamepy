#!/usr/bin/env python3
"""
Debug script to check if ExifTool persistent mode is working
"""

import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'modules'))

# Patch get_exiftool_metadata_shared to add debug output
import modules.exif_processor as exif_proc

original_func = exif_proc.get_exiftool_metadata_shared

def debug_get_exiftool_metadata_shared(image_path, exiftool_path=None):
    print(f"   >>> Called get_exiftool_metadata_shared")
    print(f"       Global instance before: {exif_proc._global_exiftool_instance}")
    result = original_func(image_path, exiftool_path)
    print(f"       Global instance after: {exif_proc._global_exiftool_instance}")
    return result

exif_proc.get_exiftool_metadata_shared = debug_get_exiftool_metadata_shared

from modules.exif_processor import get_cached_exif_data, find_exiftool_path, _global_exiftool_instance

TEST_FILE = r"C:\Users\yshub\Desktop\Bilbao\2025-09-10-Northern-Spain-Bilbao-001.JPG"

print("="*60)
print("🔍 ExifTool Persistent Mode Debug")
print("="*60)

exiftool_path = find_exiftool_path()
print(f"ExifTool path: {exiftool_path}")
print()

# Test 1: Check if global instance is created
print("1️⃣ Before first call:")
print(f"   Global instance: {_global_exiftool_instance}")
print()

# Test 2: First call
print("2️⃣ First call to get_cached_exif_data...")
start = time.perf_counter()
date1, camera1, lens1 = get_cached_exif_data(TEST_FILE, "exiftool", exiftool_path)
duration1 = time.perf_counter() - start
print(f"   Duration: {duration1*1000:.1f} ms")
print(f"   Result: {date1}, {camera1}, {lens1}")
print(f"   Global instance after: {_global_exiftool_instance}")
print()

# Test 3: Second call (should use cache)
print("3️⃣ Second call (cache hit)...")
start = time.perf_counter()
date2, camera2, lens2 = get_cached_exif_data(TEST_FILE, "exiftool", exiftool_path)
duration2 = time.perf_counter() - start
print(f"   Duration: {duration2*1000:.1f} ms")
print(f"   Speedup: {duration1/duration2:.1f}x")
print()

# Test 4: Third call with different file (should use persistent instance)
TEST_FILE2 = r"C:\Users\yshub\Desktop\Bilbao\2025-09-10-Northern-Spain-Bilbao-002.JPG"
print("4️⃣ Third call (different file, no cache, should use persistent instance)...")
start = time.perf_counter()
date3, camera3, lens3 = get_cached_exif_data(TEST_FILE2, "exiftool", exiftool_path)
duration3 = time.perf_counter() - start
print(f"   Duration: {duration3*1000:.1f} ms")
print(f"   Result: {date3}, {camera3}, {lens3}")
print()

print("="*60)
print("📊 Analysis:")
print("="*60)
print(f"First call (cold):     {duration1*1000:.1f} ms")
print(f"Second call (cache):   {duration2*1000:.1f} ms")
print(f"Third call (no cache): {duration3*1000:.1f} ms")
print()

if duration3 < duration1 * 0.5:
    print("✅ Persistent mode is WORKING! (3rd call faster than 1st)")
else:
    print("❌ Persistent mode NOT working! (3rd call as slow as 1st)")
    print("   Expected: ~100ms for persistent, ~250ms for new process")
print("="*60)
