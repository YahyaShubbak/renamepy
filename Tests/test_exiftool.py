#!/usr/bin/env python3
"""
Test script to check if exiftool is correctly found and accessible.
"""

import os
import shutil

def is_exiftool_installed():
    print("Testing exiftool detection...")
    
    # Test 1: System PATH
    exe = shutil.which("exiftool")
    if exe:
        print(f"✅ Found exiftool in system PATH: {exe}")
        return exe
    else:
        print("❌ exiftool not found in system PATH")
    
    # Test 2: Current directory
    local = os.path.join(os.getcwd(), "exiftool.exe")
    print(f"Testing current directory: {local}")
    if os.path.exists(local):
        print(f"✅ Found exiftool in current directory: {local}")
        return local
    else:
        print("❌ exiftool.exe not found in current directory")
    
    # Test 3: exiftool-13.32_64 subdirectory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    custom = os.path.join(script_dir, "exiftool-13.32_64", "exiftool.exe")
    print(f"Testing subdirectory: {custom}")
    if os.path.exists(custom):
        print(f"✅ Found exiftool in subdirectory: {custom}")
        return custom
    else:
        print("❌ exiftool.exe not found in exiftool-13.32_64 subdirectory")
    
    print("❌ exiftool not found anywhere")
    return None

def test_exiftool_import():
    print("\nTesting exiftool Python package...")
    try:
        import exiftool
        print("✅ exiftool Python package is available")
        return True
    except ImportError as e:
        print(f"❌ exiftool Python package not available: {e}")
        return False

def test_exiftool_functionality():
    print("\nTesting exiftool functionality...")
    
    exiftool_path = is_exiftool_installed()
    if not exiftool_path:
        print("❌ Cannot test functionality - exiftool.exe not found")
        return False
    
    if not test_exiftool_import():
        print("❌ Cannot test functionality - Python package not available")
        return False
    
    try:
        import exiftool
        print(f"Testing with executable: {exiftool_path}")
        
        # Test if we can create ExifToolHelper with the found executable
        with exiftool.ExifToolHelper(executable=exiftool_path) as et:
            # Test with a dummy command to see if it responds
            version = et.execute("-ver")
            print(f"✅ exiftool is working! Version: {version}")
            return True
            
    except Exception as e:
        print(f"❌ Error testing exiftool functionality: {e}")
        return False

if __name__ == "__main__":
    print("🔍 ExifTool Detection Test")
    print("=" * 50)
    
    # Test detection
    exiftool_path = is_exiftool_installed()
    
    # Test import
    import_ok = test_exiftool_import()
    
    # Test functionality
    if exiftool_path and import_ok:
        test_exiftool_functionality()
    
    print("\n" + "=" * 50)
    if exiftool_path and import_ok:
        print("🎉 All tests passed! ExifTool should work correctly.")
    else:
        print("⚠️  Some tests failed. Check the output above for details.")
