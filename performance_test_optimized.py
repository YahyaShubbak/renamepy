#!/usr/bin/env python3
"""
Performance Test Script for Optimized File Renaming

This script tests the performance improvements of the optimized EXIF extraction
and selective metadata processing.
"""

import os
import sys
import time
import shutil
import tempfile
from pathlib import Path

# Add the current directory to the path so we can import RenameFiles
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from RenameFiles import (
    extract_exif_fields_with_retry, 
    extract_selective_exif_fields,
    get_cached_exif_data,
    get_selective_cached_exif_data,
    clear_global_exif_cache,
    cleanup_global_exiftool,
    is_exiftool_installed
)

def create_test_images(num_images=50, test_dir=None):
    """
    Create test images by copying existing images in the current directory
    """
    if test_dir is None:
        test_dir = tempfile.mkdtemp(prefix="rename_test_")
    
    # Find existing image files in the current directory
    current_dir = Path(os.path.dirname(os.path.abspath(__file__)))
    image_extensions = ['.jpg', '.jpeg', '.JPG', '.JPEG', '.CR2', '.NEF', '.ARW']
    
    source_images = []
    for ext in image_extensions:
        source_images.extend(current_dir.glob(f"*{ext}"))
        source_images.extend(current_dir.glob(f"**/*{ext}"))  # Search subdirectories too
    
    if not source_images:
        print("No source images found for testing. Please place some test images in the directory.")
        return None, []
    
    # Copy images to create test set
    test_files = []
    for i in range(num_images):
        source = source_images[i % len(source_images)]
        dest_name = f"test_image_{i:03d}{source.suffix}"
        dest_path = Path(test_dir) / dest_name
        
        try:
            shutil.copy2(source, dest_path)
            test_files.append(str(dest_path))
        except Exception as e:
            print(f"Failed to copy {source} to {dest_path}: {e}")
    
    print(f"Created {len(test_files)} test images in {test_dir}")
    return test_dir, test_files

def test_old_method(test_files, exiftool_path):
    """Test the old method that extracts all EXIF fields"""
    print("\n=== Testing OLD method (extract all fields) ===")
    clear_global_exif_cache()
    
    start_time = time.time()
    results = []
    
    for i, file_path in enumerate(test_files):
        if i % 10 == 0:
            print(f"Processing file {i+1}/{len(test_files)}")
        
        # Old method: always extract all three fields
        date, camera, lens = extract_exif_fields_with_retry(file_path, "exiftool", exiftool_path)
        results.append((date, camera, lens))
    
    end_time = time.time()
    elapsed = end_time - start_time
    
    print(f"OLD method completed in {elapsed:.2f} seconds")
    print(f"Average time per file: {elapsed/len(test_files):.3f} seconds")
    
    return elapsed, results

def test_new_method_date_only(test_files, exiftool_path):
    """Test the new method extracting only date (common scenario)"""
    print("\n=== Testing NEW method (date only) ===")
    clear_global_exif_cache()
    
    start_time = time.time()
    results = []
    
    for i, file_path in enumerate(test_files):
        if i % 10 == 0:
            print(f"Processing file {i+1}/{len(test_files)}")
        
        # New method: only extract date
        date, camera, lens = get_selective_cached_exif_data(
            file_path, "exiftool", exiftool_path,
            need_date=True, need_camera=False, need_lens=False
        )
        results.append((date, camera, lens))
    
    end_time = time.time()
    elapsed = end_time - start_time
    
    # Clean up the shared ExifTool instance
    cleanup_global_exiftool()
    
    print(f"NEW method (date only) completed in {elapsed:.2f} seconds")
    print(f"Average time per file: {elapsed/len(test_files):.3f} seconds")
    
    return elapsed, results

def test_new_method_all_fields(test_files, exiftool_path):
    """Test the new method extracting all fields (worst case)"""
    print("\n=== Testing NEW method (all fields) ===")
    clear_global_exif_cache()
    
    start_time = time.time()
    results = []
    
    for i, file_path in enumerate(test_files):
        if i % 10 == 0:
            print(f"Processing file {i+1}/{len(test_files)}")
        
        # New method: extract all fields
        date, camera, lens = get_selective_cached_exif_data(
            file_path, "exiftool", exiftool_path,
            need_date=True, need_camera=True, need_lens=True
        )
        results.append((date, camera, lens))
    
    end_time = time.time()
    elapsed = end_time - start_time
    
    # Clean up the shared ExifTool instance
    cleanup_global_exiftool()
    
    print(f"NEW method (all fields) completed in {elapsed:.2f} seconds")
    print(f"Average time per file: {elapsed/len(test_files):.3f} seconds")
    
    return elapsed, results

def main():
    print("Performance Test for Optimized EXIF Extraction")
    print("=" * 50)
    
    # Check if ExifTool is available
    exiftool_path = is_exiftool_installed()
    if not exiftool_path:
        print("ExifTool is not available. Please install ExifTool for testing.")
        return
    
    print(f"Using ExifTool at: {exiftool_path}")
    
    # Create test images
    num_test_images = 100  # Adjust this number based on your needs
    print(f"Creating {num_test_images} test images...")
    
    test_dir, test_files = create_test_images(num_test_images)
    if not test_files:
        print("Failed to create test images. Exiting.")
        return
    
    print(f"Created {len(test_files)} test files")
    
    try:
        # Run performance tests
        old_time, old_results = test_old_method(test_files, exiftool_path)
        date_only_time, date_only_results = test_new_method_date_only(test_files, exiftool_path)
        all_fields_time, all_fields_results = test_new_method_all_fields(test_files, exiftool_path)
        
        # Calculate improvements
        print("\n" + "=" * 50)
        print("PERFORMANCE COMPARISON RESULTS")
        print("=" * 50)
        
        print(f"Old method (all fields):     {old_time:.2f} seconds")
        print(f"New method (date only):      {date_only_time:.2f} seconds")
        print(f"New method (all fields):     {all_fields_time:.2f} seconds")
        
        if old_time > 0:
            date_only_improvement = ((old_time - date_only_time) / old_time) * 100
            all_fields_improvement = ((old_time - all_fields_time) / old_time) * 100
            
            print(f"\nSpeed improvements:")
            print(f"Date only: {date_only_improvement:.1f}% faster")
            print(f"All fields: {all_fields_improvement:.1f}% faster")
            
            # Estimate time for 516 images
            print(f"\nEstimated time for 516 images:")
            print(f"Old method:        {(old_time / len(test_files)) * 516:.1f} seconds")
            print(f"New method (date): {(date_only_time / len(test_files)) * 516:.1f} seconds")
            print(f"New method (all):  {(all_fields_time / len(test_files)) * 516:.1f} seconds")
        
        # Verify that results are equivalent
        print(f"\nVerifying results consistency...")
        date_matches = sum(1 for (o, _, _), (n, _, _) in zip(old_results, date_only_results) if o == n)
        print(f"Date extraction matches: {date_matches}/{len(test_files)} ({date_matches/len(test_files)*100:.1f}%)")
        
    finally:
        # Clean up test directory
        try:
            shutil.rmtree(test_dir)
            print(f"\nCleaned up test directory: {test_dir}")
        except Exception as e:
            print(f"Failed to clean up test directory {test_dir}: {e}")

if __name__ == "__main__":
    main()
