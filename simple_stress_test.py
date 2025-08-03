#!/usr/bin/env python3
"""
SIMPLIFIED STRESS TEST für RenameFiles.py
==========================================

Testet die echte RenameWorkerThread Klasse mit einer kleineren, aber realistischen Menge.
"""

import os
import sys
import tempfile
import shutil
import random
import datetime
import time
from pathlib import Path

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import required components
from RenameFiles import RenameWorkerThread, is_media_file

def create_test_files(base_dir, num_files_per_folder=10, num_folders=3):
    """Create real test files in multiple folders"""
    print(f"📁 Creating test files in {base_dir}")
    
    all_files = []
    
    for folder_id in range(num_folders):
        folder_path = Path(base_dir) / f"folder_{folder_id:02d}"
        folder_path.mkdir(exist_ok=True)
        
        for file_id in range(num_files_per_folder):
            # Create JPEG files
            jpg_file = folder_path / f"IMG_{file_id:04d}.jpg"
            jpg_file.touch()
            all_files.append(str(jpg_file))
            
            # Create ARW files  
            arw_file = folder_path / f"IMG_{file_id:04d}.arw"
            arw_file.touch()
            all_files.append(str(arw_file))
    
    print(f"✅ Created {len(all_files)} test files in {num_folders} folders")
    return all_files

def test_directory_integrity(original_files, renamed_files):
    """Test that files stay in their original directories"""
    print(f"🔍 Testing directory integrity...")
    
    directory_moves = 0
    
    # Create mapping from original to renamed
    original_dirs = {os.path.basename(f): os.path.dirname(f) for f in original_files}
    renamed_dirs = {os.path.basename(f): os.path.dirname(f) for f in renamed_files}
    
    for original_file in original_files:
        original_dir = os.path.dirname(original_file)
        original_basename = os.path.basename(original_file)
        
        # Find corresponding renamed file
        found_in_different_dir = False
        for renamed_file in renamed_files:
            renamed_dir = os.path.dirname(renamed_file)
            
            # Check if this could be the same file (based on original basename pattern)
            if original_dir != renamed_dir:
                # Different directory = potential move
                if any(pattern in os.path.basename(renamed_file) for pattern in ["IMG_", ".jpg", ".arw"]):
                    found_in_different_dir = True
        
        if found_in_different_dir:
            directory_moves += 1
    
    return directory_moves

def run_real_rename_test():
    """Run test with real RenameWorkerThread"""
    
    with tempfile.TemporaryDirectory() as temp_dir:
        print(f"🧪 Testing with real RenameWorkerThread")
        print(f"📁 Test directory: {temp_dir}")
        
        # Create test files
        original_files = create_test_files(temp_dir, num_files_per_folder=5, num_folders=3)
        
        print(f"\n📋 Original file locations:")
        for f in original_files[:6]:  # Show first 6
            print(f"   {f}")
        
        # Test parameters
        camera_prefix = "TEST"
        additional = "stress"
        use_camera = False  # Disable to avoid EXIF dependency
        use_lens = False
        exif_method = None  # No EXIF
        devider = "-"
        exiftool_path = None
        custom_order = ["Date", "Prefix", "Additional", "Camera", "Lens"]
        date_format = "YYYY-MM-DD"
        use_date = True
        continuous_counter = False
        
        # Create and run worker thread
        print(f"\n🚀 Starting rename operation...")
        
        worker = RenameWorkerThread(
            original_files, camera_prefix, additional, use_camera, use_lens,
            exif_method, devider, exiftool_path, custom_order, 
            date_format, use_date
        )
        
        # Capture results
        renamed_files = []
        errors = []
        
        def on_finished(files, errs):
            nonlocal renamed_files, errors
            renamed_files = files
            errors = errs
        
        worker.finished.connect(on_finished)
        
        # Run synchronously
        start_time = time.time()
        worker.run()  # Direct call instead of start() to avoid threading
        duration = time.time() - start_time
        
        print(f"✅ Rename completed in {duration:.2f}s")
        print(f"   ✅ Renamed: {len(renamed_files)} files")
        print(f"   ❌ Errors: {len(errors)}")
        
        if errors:
            print(f"   First few errors:")
            for error in errors[:3]:
                print(f"     • {error}")
        
        print(f"\n📋 Renamed file locations:")
        for f in renamed_files[:6]:  # Show first 6
            print(f"   {f}")
        
        # Test directory integrity
        directory_moves = test_directory_integrity(original_files, renamed_files)
        
        print(f"\n🔍 Directory Integrity Check:")
        if directory_moves == 0:
            print(f"✅ PASSED: All files stayed in their original directories")
        else:
            print(f"❌ FAILED: {directory_moves} files moved between directories!")
        
        # Show directory structure
        print(f"\n📁 Final directory structure:")
        for root, dirs, files in os.walk(temp_dir):
            level = root.replace(temp_dir, '').count(os.sep)
            indent = ' ' * 2 * level
            print(f"{indent}{os.path.basename(root)}/")
            subindent = ' ' * 2 * (level + 1)
            for file in files[:3]:  # Show first 3 files per folder
                print(f"{subindent}{file}")
            if len(files) > 3:
                print(f"{subindent}... and {len(files) - 3} more")
        
        return directory_moves == 0

if __name__ == "__main__":
    print("🚀 SIMPLIFIED STRESS TEST FOR DIRECTORY INTEGRITY")
    print("="*60)
    
    try:
        success = run_real_rename_test()
        
        if success:
            print(f"\n🎉 TEST PASSED: Directory integrity maintained!")
            sys.exit(0)
        else:
            print(f"\n❌ TEST FAILED: Directory integrity violated!")
            sys.exit(1)
            
    except Exception as e:
        print(f"\n💥 Test crashed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
