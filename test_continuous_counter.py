#!/usr/bin/env python3
"""
Quick test for continuous counter functionality
"""

import os
import sys
import tempfile
import shutil
from datetime import datetime, timedelta

# Add the current directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from RenameFiles import RenameWorkerThread

def create_test_files():
    """Create test files with different dates"""
    
    # Create temporary directory
    test_dir = tempfile.mkdtemp()
    print(f"Created test directory: {test_dir}")
    
    # Create test files with different modification times
    test_files = []
    
    # Day 1: 3 files 
    base_time = datetime(2025, 7, 7, 10, 0, 0)
    for i in range(3):
        filename = f"test_day1_{i+1:03d}.jpg"
        filepath = os.path.join(test_dir, filename)
        with open(filepath, 'w') as f:
            f.write(f"test file {i+1}")
        
        # Set modification time
        file_time = base_time + timedelta(minutes=i*10)
        timestamp = file_time.timestamp()
        os.utime(filepath, (timestamp, timestamp))
        test_files.append(filepath)
        print(f"Created: {filename} with date {file_time.strftime('%Y%m%d')}")
    
    # Day 2: 2 files
    base_time = datetime(2025, 7, 8, 10, 0, 0)
    for i in range(2):
        filename = f"test_day2_{i+1:03d}.jpg"
        filepath = os.path.join(test_dir, filename)
        with open(filepath, 'w') as f:
            f.write(f"test file {i+4}")
        
        # Set modification time 
        file_time = base_time + timedelta(minutes=i*10)
        timestamp = file_time.timestamp()
        os.utime(filepath, (timestamp, timestamp))
        test_files.append(filepath)
        print(f"Created: {filename} with date {file_time.strftime('%Y%m%d')}")
    
    return test_dir, test_files

def test_continuous_counter():
    """Test the continuous counter functionality"""
    
    test_dir, test_files = create_test_files()
    
    try:
        print("\n=== Testing Continuous Counter ===")
        
        # Create a rename worker with continuous counter enabled
        worker = RenameWorkerThread(
            files=test_files,
            exif_method=None,  # No EXIF method, use file dates
            devider="-",
            exiftool_path=None,
            custom_order=["Date", "Number"],
            date_format="YYYY-MM-DD",
            use_date=True,
            continuous_counter=True,  # Enable continuous counter
            camera_prefix="",
            additional="",
            use_camera=False,
            use_lens=False
        )
        
        print("\nFiles before processing:")
        for f in test_files:
            print(f"  {os.path.basename(f)}")
        
        # Run the renaming (but catch any issues)
        try:
            renamed_files, errors = worker.optimized_rename_files()
            
            print(f"\nProcessed {len(renamed_files)} files successfully")
            if errors:
                print(f"Errors: {errors}")
            
            print("\nExpected behavior:")
            print("  Day 1 (2025-07-07): Files should get numbers 001, 002, 003")
            print("  Day 2 (2025-07-08): Files should get numbers 004, 005")
            
            print("\nActual results:")
            for f in renamed_files:
                print(f"  {os.path.basename(f)}")
                
        except Exception as e:
            print(f"Error during processing: {e}")
            import traceback
            traceback.print_exc()
    
    finally:
        # Cleanup
        print(f"\nCleaning up test directory: {test_dir}")
        shutil.rmtree(test_dir)

if __name__ == "__main__":
    test_continuous_counter()
