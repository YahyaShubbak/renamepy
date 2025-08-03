#!/usr/bin/env python3
"""
Test script for JPG+RAW pair continuous counter functionality
"""

import os
import sys
import tempfile
import shutil
from datetime import datetime, timedelta

# Add the current directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from RenameFiles import RenameWorkerThread

def create_test_file_pairs():
    """Create test files with JPG+RAW pairs"""
    
    # Create temporary directory
    test_dir = tempfile.mkdtemp()
    print(f"Created test directory: {test_dir}")
    
    # Create test files with different modification times
    test_files = []
    
    # Day 1: 2 file pairs (JPG+ARW)
    base_time = datetime(2025, 7, 7, 10, 0, 0)
    for i in range(2):
        base_name = f"test_day1_{i+1:03d}"
        
        # Create JPG file
        jpg_filepath = os.path.join(test_dir, f"{base_name}.jpg")
        with open(jpg_filepath, 'w') as f:
            f.write(f"test jpg file {i+1}")
        
        # Create RAW file  
        arw_filepath = os.path.join(test_dir, f"{base_name}.ARW")
        with open(arw_filepath, 'w') as f:
            f.write(f"test raw file {i+1}")
        
        # Set same modification time for both files in pair
        file_time = base_time + timedelta(minutes=i*10)
        timestamp = file_time.timestamp()
        os.utime(jpg_filepath, (timestamp, timestamp))
        os.utime(arw_filepath, (timestamp, timestamp))
        
        test_files.extend([jpg_filepath, arw_filepath])
        print(f"Created pair: {base_name}.jpg + {base_name}.ARW with date {file_time.strftime('%Y%m%d')}")
    
    # Day 2: 1 file pair (JPG+ARW)
    base_time = datetime(2025, 7, 8, 10, 0, 0)
    base_name = "test_day2_001"
    
    # Create JPG file
    jpg_filepath = os.path.join(test_dir, f"{base_name}.jpg") 
    with open(jpg_filepath, 'w') as f:
        f.write("test jpg file day 2")
    
    # Create RAW file
    arw_filepath = os.path.join(test_dir, f"{base_name}.ARW")
    with open(arw_filepath, 'w') as f:
        f.write("test raw file day 2")
    
    # Set same modification time
    timestamp = base_time.timestamp()
    os.utime(jpg_filepath, (timestamp, timestamp))
    os.utime(arw_filepath, (timestamp, timestamp))
    
    test_files.extend([jpg_filepath, arw_filepath])
    print(f"Created pair: {base_name}.jpg + {base_name}.ARW with date {base_time.strftime('%Y%m%d')}")
    
    return test_dir, test_files

def test_continuous_counter_pairs():
    """Test the continuous counter functionality with JPG+RAW pairs"""
    
    test_dir, test_files = create_test_file_pairs()
    
    try:
        print("\n=== Testing Continuous Counter with JPG+RAW pairs ===")
        
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
        
        # Run the renaming
        try:
            renamed_files, errors = worker.optimized_rename_files()
            
            print(f"\nProcessed {len(renamed_files)} files successfully")
            if errors:
                print(f"Errors: {errors}")
            
            print("\nExpected behavior:")
            print("  Day 1, Pair 1: Both JPG and ARW should get number 001")
            print("  Day 1, Pair 2: Both JPG and ARW should get number 002") 
            print("  Day 2, Pair 1: Both JPG and ARW should get number 003")
            
            print("\nActual results:")
            for f in sorted(renamed_files):
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
    test_continuous_counter_pairs()
