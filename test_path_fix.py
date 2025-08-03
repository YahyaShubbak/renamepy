#!/usr/bin/env python3
"""
Test script to verify the path normalization fixes
"""

import os
import sys

# Add the current directory to the path so we can import RenameFiles
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from RenameFiles import get_selective_cached_exif_data, extract_selective_exif_fields

def test_path_normalization():
    """Test that path normalization prevents double backslashes"""
    
    # Test paths with potential double backslashes
    test_paths = [
        "C:/Users/yshub/Desktop/04_Fahrradtour\\10050420\\_DSC0402.ARW",
        "C:\\Users\\yshub\\Desktop\\test\\\\file.jpg",
        "C:/Users/test/folder\\subfolder\\\\file.png"
    ]
    
    print("Testing path normalization...")
    
    for path in test_paths:
        print(f"\nOriginal path: {path}")
        normalized = os.path.normpath(path)
        print(f"Normalized:    {normalized}")
        
        # Check if file exists (will fail, but should not crash)
        print(f"File exists check: {os.path.exists(normalized)}")
        
        # Test the EXIF functions with a non-existent file (should handle gracefully)
        print("Testing get_selective_cached_exif_data...")
        result = get_selective_cached_exif_data(
            path, "exiftool", None, 
            need_date=True, need_camera=False, need_lens=False
        )
        print(f"Result: {result}")
        
        print("Testing extract_selective_exif_fields...")
        result2 = extract_selective_exif_fields(
            path, "exiftool", None, 
            need_date=True, need_camera=False, need_lens=False
        )
        print(f"Result: {result2}")

if __name__ == "__main__":
    test_path_normalization()
    print("\nPath normalization test completed!")
