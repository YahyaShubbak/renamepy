#!/usr/bin/env python3
"""
Test script for ExifTool installation validation

This script demonstrates the improved ExifTool detection that validates
complete installations and prevents crashes from incomplete setups.
"""

import os
import sys

# Add current directory to path to import RenameFiles
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from RenameFiles import is_exiftool_installed, EXIFTOOL_AVAILABLE

def test_exiftool_validation():
    print("=== ExifTool Installation Validation Test ===\n")
    
    print("EXIFTOOL_AVAILABLE (PyExifTool library):", EXIFTOOL_AVAILABLE)
    print()
    
    if not EXIFTOOL_AVAILABLE:
        print("❌ PyExifTool library not installed!")
        print("   Install with: pip install PyExifTool")
        print()
    
    print("Checking for ExifTool installation...")
    print("=" * 50)
    
    exiftool_path = is_exiftool_installed()
    
    print("=" * 50)
    
    if exiftool_path:
        print(f"✅ ExifTool found and validated: {exiftool_path}")
        print()
        print("Installation Details:")
        print(f"   Executable: {os.path.basename(exiftool_path)}")
        print(f"   Directory: {os.path.dirname(exiftool_path)}")
        
        # Check what files are actually present
        exe_dir = os.path.dirname(exiftool_path)
        print(f"\n   Contents of {os.path.basename(exe_dir)}:")
        
        try:
            contents = os.listdir(exe_dir)
            files = [f for f in contents if os.path.isfile(os.path.join(exe_dir, f))]
            dirs = [d for d in contents if os.path.isdir(os.path.join(exe_dir, d))]
            
            print(f"      📄 Files: {len(files)}")
            for f in sorted(files)[:10]:  # Show first 10 files
                print(f"         - {f}")
            if len(files) > 10:
                print(f"         ... and {len(files) - 10} more files")
            
            print(f"      📁 Directories: {len(dirs)}")
            for d in sorted(dirs):
                print(f"         - {d}/")
                
        except Exception as e:
            print(f"      Error listing contents: {e}")
    else:
        print("❌ ExifTool not found or installation incomplete!")
        print()
        print("Common issues:")
        print("1. Only exiftool.exe copied (insufficient)")
        print("2. Missing Perl dependencies")
        print("3. Incomplete ZIP extraction")
        print("4. ExifTool not installed")
        print()
        print("Solution:")
        print("1. Download complete ExifTool ZIP from https://exiftool.org/")
        print("2. Extract ENTIRE contents to your program folder")
        print("3. Do NOT copy just the .exe file")
        print("4. Restart the application")
    
    print("\n" + "=" * 60)
    print("Installation Guide:")
    print("✅ CORRECT: Extract complete exiftool-13.32_64/ folder")
    print("❌ WRONG:   Copy only exiftool.exe (will crash!)")
    print("=" * 60)

def simulate_installation_scenarios():
    """Demonstrate different installation scenarios"""
    print("\n=== Installation Scenario Examples ===\n")
    
    scenarios = [
        {
            "name": "Complete Installation",
            "structure": [
                "exiftool-13.32_64/",
                "  exiftool.exe",
                "  perl.exe",
                "  perl532.dll",
                "  lib/",
                "    Image/",
                "    File/", 
                "    Exporter/",
                "  exiftool_files/"
            ],
            "result": "✅ VALID - Will work correctly"
        },
        {
            "name": "Incomplete Installation (only .exe)",
            "structure": [
                "exiftool.exe"
            ],
            "result": "❌ INVALID - Will crash application!"
        },
        {
            "name": "Missing Perl Dependencies",
            "structure": [
                "exiftool-13.32_64/",
                "  exiftool.exe",
                "  lib/ (empty)"
            ],
            "result": "❌ INVALID - Missing perl.exe and modules"
        },
        {
            "name": "Missing Perl Modules",
            "structure": [
                "exiftool-13.32_64/",
                "  exiftool.exe", 
                "  perl.exe",
                "  perl532.dll",
                "  lib/ (incomplete)"
            ],
            "result": "❌ INVALID - Essential modules missing"
        }
    ]
    
    for scenario in scenarios:
        print(f"Scenario: {scenario['name']}")
        print("Structure:")
        for item in scenario['structure']:
            print(f"  {item}")
        print(f"Result: {scenario['result']}")
        print()

if __name__ == "__main__":
    test_exiftool_validation()
    simulate_installation_scenarios()
