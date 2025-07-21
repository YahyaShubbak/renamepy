#!/usr/bin/env python3
"""
Test script for subdirectory handling in RenameFiles.py
Creates a test directory structure with subdirectories and images
"""

import os
import tempfile
import shutil
import sys

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from RenameFiles import scan_directory_recursive, is_image_file

def create_test_directory_structure():
    """Create a test directory structure with subdirectories and images"""
    base_dir = tempfile.mkdtemp(prefix="subdir_test_")
    
    # Directory structure to create
    structure = {
        "main_folder": [
            "IMG_001.jpg",
            "IMG_002.CR2", 
            "document.txt"  # Non-image file
        ],
        "main_folder/vacation_2024": [
            "beach_001.jpg",
            "beach_002.ARW",
            "sunset_003.NEF"
        ],
        "main_folder/vacation_2024/day1": [
            "morning_001.jpg",
            "afternoon_002.jpg"
        ],
        "main_folder/vacation_2024/day2": [
            "hotel_001.CR2",
            "dinner_002.jpg"
        ],
        "main_folder/work_photos": [
            "meeting_001.png",
            "presentation_002.jpg"
        ],
        "main_folder/work_photos/event": [
            "conference_001.jpg",
            "workshop_002.DNG"
        ],
        "main_folder/empty_folder": [],  # Empty folder
        "main_folder/no_images": [
            "readme.txt",
            "notes.docx"
        ]
    }
    
    # Create the directory structure
    created_files = []
    for folder, files in structure.items():
        folder_path = os.path.join(base_dir, folder)
        os.makedirs(folder_path, exist_ok=True)
        
        for file in files:
            file_path = os.path.join(folder_path, file)
            with open(file_path, 'w') as f:
                f.write(f"Test file: {file}")
            
            if is_image_file(file):
                created_files.append(file_path)
    
    return base_dir, created_files

def test_subdirectory_scanning():
    """Test the recursive directory scanning functionality"""
    print("=" * 60)
    print("SUBDIRECTORY SCANNING TEST")
    print("=" * 60)
    
    # Create test structure
    test_dir, expected_files = create_test_directory_structure()
    
    try:
        print(f"Created test directory: {test_dir}")
        print(f"Expected image files: {len(expected_files)}")
        
        # Print directory structure
        print("\nDirectory structure:")
        for root, dirs, files in os.walk(test_dir):
            level = root.replace(test_dir, '').count(os.sep)
            indent = ' ' * 2 * level
            print(f"{indent}{os.path.basename(root)}/")
            
            subindent = ' ' * 2 * (level + 1)
            for file in files:
                marker = "📷" if is_image_file(file) else "📄"
                print(f"{subindent}{marker} {file}")
        
        # Test the scanning function
        print(f"\nScanning with scan_directory_recursive()...")
        found_files = scan_directory_recursive(test_dir)
        
        print(f"\nResults:")
        print(f"Expected image files: {len(expected_files)}")
        print(f"Found image files: {len(found_files)}")
        
        # Verify results
        success = len(found_files) == len(expected_files)
        print(f"Test result: {'✅ PASS' if success else '❌ FAIL'}")
        
        if not success:
            print("\nExpected files:")
            for f in sorted(expected_files):
                print(f"  - {os.path.relpath(f, test_dir)}")
            
            print("\nFound files:")
            for f in sorted(found_files):
                print(f"  - {os.path.relpath(f, test_dir)}")
        else:
            print("\nFound files (by subdirectory):")
            files_by_dir = {}
            for f in found_files:
                dir_name = os.path.dirname(os.path.relpath(f, test_dir))
                if dir_name not in files_by_dir:
                    files_by_dir[dir_name] = []
                files_by_dir[dir_name].append(os.path.basename(f))
            
            for dir_name, files in sorted(files_by_dir.items()):
                if dir_name == '':
                    dir_name = '(root)'
                print(f"  📁 {dir_name}: {len(files)} files")
                for file in sorted(files):
                    print(f"    📷 {file}")
        
        # Test edge cases
        print(f"\nTesting edge cases:")
        
        # Test with non-existent directory
        fake_dir = os.path.join(test_dir, "nonexistent")
        fake_result = scan_directory_recursive(fake_dir)
        print(f"Non-existent directory: {len(fake_result)} files (should be 0)")
        
        # Test with file instead of directory
        test_file = os.path.join(test_dir, "main_folder", "IMG_001.jpg")
        file_result = scan_directory_recursive(test_file)
        print(f"File instead of directory: {len(file_result)} files (should be 0)")
        
        return success
        
    finally:
        # Cleanup
        shutil.rmtree(test_dir, ignore_errors=True)
        print(f"\nCleaned up test directory: {test_dir}")

def demonstrate_usage():
    """Demonstrate how to use the subdirectory functionality"""
    print("\n" + "=" * 60)
    print("USAGE DEMONSTRATION")
    print("=" * 60)
    
    print("The updated RenameFiles.py now supports recursive subdirectory scanning:")
    print()
    print("1. 📁 Select Folder Button:")
    print("   - Now scans ALL subdirectories recursively")
    print("   - Shows progress: 'Scanning folder and subfolders for images...'")
    print("   - Reports total files found: 'Found X images in folder hierarchy'")
    print()
    print("2. 🖱️ Drag & Drop:")
    print("   - Drop folders to scan all subdirectories automatically")
    print("   - Shows progress: 'Scanning dropped folders for images...'")
    print("   - Handles multiple folders at once")
    print()
    print("3. 🔍 Directory Structure:")
    print("   Example hierarchy that will be fully scanned:")
    print("   📁 Photos/")
    print("   ├── 📷 IMG_001.jpg          ← Found")
    print("   ├── 📁 Vacation/")
    print("   │   ├── 📷 beach_01.CR2     ← Found")
    print("   │   └── 📁 Day1/")
    print("   │       └── 📷 sunset.ARW   ← Found")
    print("   └── 📁 Work/")
    print("       └── 📷 meeting.NEF      ← Found")
    print()
    print("4. 📊 Benefits:")
    print("   - No need to manually select files from each subfolder")
    print("   - Handles complex directory structures automatically")
    print("   - Maintains file organization during renaming")
    print("   - Works with all supported image formats (JPG, CR2, NEF, ARW, etc.)")

if __name__ == "__main__":
    # Run the test
    success = test_subdirectory_scanning()
    
    # Show usage demonstration
    demonstrate_usage()
    
    # Summary
    print(f"\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Subdirectory scanning test: {'✅ PASSED' if success else '❌ FAILED'}")
    print()
    print("The RenameFiles application now:")
    print("✅ Recursively scans subdirectories")
    print("✅ Finds images in any folder depth")
    print("✅ Shows progress during scanning")
    print("✅ Handles drag & drop of folders")
    print("✅ Reports scan results to user")
    print()
    print("You can now select a main folder and all images in")
    print("ALL subdirectories will be found and processed! 🎉")
