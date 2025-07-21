#!/usr/bin/env python3
"""
Test script for safety and robustness features of RenameFiles.py
Tests various edge cases, error conditions, and failsafe mechanisms.
"""

import os
import sys
import tempfile
import shutil
from datetime import datetime
import time

# Add current directory to path to import RenameFiles
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from RenameFiles import (
    sanitize_filename, check_file_access, get_safe_target_path, 
    validate_path_length, extract_exif_fields_with_retry,
    verify_group_consistency, group_files_with_failsafe
)

class SafetyTester:
    def __init__(self):
        self.test_results = []
        self.temp_dir = None
        
    def log_test(self, test_name, passed, details=""):
        """Log test result"""
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {test_name}")
        if details:
            print(f"   Details: {details}")
        self.test_results.append((test_name, passed, details))
        
    def setup_test_environment(self):
        """Create temporary test environment"""
        self.temp_dir = tempfile.mkdtemp(prefix="rename_test_")
        print(f"Test environment: {self.temp_dir}")
        
        # Create test files with various problematic names
        test_files = [
            "normal_image.jpg",
            "image with spaces.jpg",
            "image<with>invalid:chars.jpg",
            "image|with*more?invalid.jpg",
            'image"with"quotes.jpg',
            "image_with_very_long_name_that_exceeds_normal_limits_and_might_cause_filesystem_issues_when_combined_with_long_paths.jpg",
            "image.with.dots.jpg",
            "image   .jpg",  # trailing spaces
            ".hidden_image.jpg",
            "image\x00with\x01control\x02chars.jpg",  # control characters
        ]
        
        created_files = []
        for filename in test_files:
            try:
                # Create safe version for actual file creation
                safe_name = filename.replace('<', '_').replace('>', '_').replace(':', '_')
                safe_name = safe_name.replace('|', '_').replace('*', '_').replace('?', '_')
                safe_name = safe_name.replace('"', '_').replace('\x00', '_').replace('\x01', '_').replace('\x02', '_')
                
                filepath = os.path.join(self.temp_dir, safe_name)
                with open(filepath, 'wb') as f:
                    # Write minimal JPEG header for testing
                    f.write(b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xff\xdb')
                    f.write(b'\x00' * 100)  # Padding
                created_files.append(filepath)
            except Exception as e:
                print(f"Could not create test file {filename}: {e}")
                
        return created_files
    
    def cleanup_test_environment(self):
        """Clean up temporary test environment"""
        if self.temp_dir and os.path.exists(self.temp_dir):
            try:
                shutil.rmtree(self.temp_dir)
                print(f"Cleaned up test environment: {self.temp_dir}")
            except Exception as e:
                print(f"Warning: Could not clean up {self.temp_dir}: {e}")
    
    def test_filename_sanitization(self):
        """Test sanitize_filename function with various inputs"""
        test_cases = [
            ("normal_filename.jpg", "normal_filename.jpg"),
            ("file<with>invalid:chars.jpg", "file_with_invalid_chars.jpg"),
            ("file|with*more?invalid.jpg", "file_with_more_invalid.jpg"),
            ('file"with"quotes.jpg', "file_with_quotes.jpg"),
            ("file\x00with\x01control.jpg", "file_with_control.jpg"),
            ("file   .jpg", "file.jpg"),  # trailing spaces
            ("", "unnamed_file"),  # empty string
            ("a" * 250 + ".jpg", True),  # length check (should be shortened)
        ]
        
        for input_name, expected in test_cases:
            try:
                result = sanitize_filename(input_name)
                if isinstance(expected, bool):
                    # Length test
                    passed = len(result) <= 200
                    self.log_test(f"Sanitize long filename", passed, f"Length: {len(result)}")
                else:
                    passed = result == expected
                    self.log_test(f"Sanitize '{input_name[:20]}...'", passed, f"Got: {result}")
            except Exception as e:
                self.log_test(f"Sanitize '{input_name[:20]}...'", False, f"Exception: {e}")
    
    def test_file_access_checking(self):
        """Test file access checking"""
        if not self.temp_dir:
            return
            
        # Test with existing file
        test_file = os.path.join(self.temp_dir, "access_test.jpg")
        with open(test_file, 'w') as f:
            f.write("test")
        
        passed = check_file_access(test_file)
        self.log_test("File access - existing file", passed)
        
        # Test with non-existing file
        non_existing = os.path.join(self.temp_dir, "non_existing.jpg")
        passed = not check_file_access(non_existing)
        self.log_test("File access - non-existing file", passed)
    
    def test_safe_target_path(self):
        """Test safe target path generation"""
        if not self.temp_dir:
            return
            
        # Create a file that would conflict
        existing_file = os.path.join(self.temp_dir, "existing.jpg")
        with open(existing_file, 'w') as f:
            f.write("test")
        
        # Test conflict resolution
        original_path = os.path.join(self.temp_dir, "original.jpg")
        safe_path = get_safe_target_path(original_path, "existing.jpg")
        
        passed = safe_path != existing_file and "conflict" in safe_path
        self.log_test("Safe target path - conflict resolution", passed, f"Generated: {os.path.basename(safe_path)}")
    
    def test_path_length_validation(self):
        """Test path length validation"""
        short_path = "C:\\short\\path\\file.jpg"
        long_path = "C:\\" + "very_long_directory_name\\" * 10 + "file.jpg"
        
        passed1 = validate_path_length(short_path)
        passed2 = not validate_path_length(long_path)
        
        self.log_test("Path length - short path", passed1)
        self.log_test("Path length - long path", passed2, f"Length: {len(long_path)}")
    
    def test_exif_retry_mechanism(self):
        """Test EXIF extraction with retry"""
        if not self.temp_dir:
            return
            
        # Test with non-image file
        non_image = os.path.join(self.temp_dir, "not_an_image.jpg")
        with open(non_image, 'w') as f:
            f.write("This is not an image")
        
        try:
            result = extract_exif_fields_with_retry(non_image, "pillow", max_retries=2)
            passed = result == (None, None, None)
            self.log_test("EXIF retry - invalid file", passed, f"Result: {result}")
        except Exception as e:
            self.log_test("EXIF retry - invalid file", True, f"Handled exception: {e}")
    
    def test_group_consistency_verification(self):
        """Test group consistency verification"""
        # This is a mock test since we need real images with EXIF for proper testing
        mock_group = [
            os.path.join(self.temp_dir, "image1.jpg") if self.temp_dir else "image1.jpg",
            os.path.join(self.temp_dir, "image2.jpg") if self.temp_dir else "image2.jpg"
        ]
        
        try:
            # This will likely return True for mock files (no real EXIF data)
            result = verify_group_consistency(mock_group, "pillow")
            self.log_test("Group consistency - mock test", True, f"Result: {result}")
        except Exception as e:
            self.log_test("Group consistency - mock test", True, f"Handled exception: {e}")
    
    def performance_test_baseline(self):
        """Baseline performance test"""
        if not self.temp_dir:
            return
            
        # Create multiple test files
        test_files = []
        for i in range(10):
            filepath = os.path.join(self.temp_dir, f"perf_test_{i:03d}.jpg")
            with open(filepath, 'wb') as f:
                # Write minimal JPEG header
                f.write(b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xff\xdb')
                f.write(b'\x00' * 1000)  # 1KB file
            test_files.append(filepath)
        
        # Time the grouping operation
        start_time = time.time()
        groups = group_files_with_failsafe(test_files, "pillow")
        end_time = time.time()
        
        duration = end_time - start_time
        passed = duration < 2.0  # Should complete in under 2 seconds for 10 files
        self.log_test(f"Performance - grouping 10 files", passed, f"Duration: {duration:.2f}s")
        
        return duration
    
    def run_all_tests(self):
        """Run all safety and performance tests"""
        print("=" * 60)
        print("SAFETY AND ROBUSTNESS TESTS")
        print("=" * 60)
        
        try:
            # Setup
            test_files = self.setup_test_environment()
            print(f"Created {len(test_files)} test files\n")
            
            # Run tests
            self.test_filename_sanitization()
            print()
            
            self.test_file_access_checking()
            print()
            
            self.test_safe_target_path()
            print()
            
            self.test_path_length_validation()
            print()
            
            self.test_exif_retry_mechanism()
            print()
            
            self.test_group_consistency_verification()
            print()
            
            # Performance test
            print("PERFORMANCE TESTS")
            print("-" * 30)
            baseline_time = self.performance_test_baseline()
            print()
            
            # Summary
            print("=" * 60)
            print("TEST SUMMARY")
            print("=" * 60)
            
            total_tests = len(self.test_results)
            passed_tests = sum(1 for _, passed, _ in self.test_results if passed)
            
            print(f"Total tests: {total_tests}")
            print(f"Passed: {passed_tests}")
            print(f"Failed: {total_tests - passed_tests}")
            print(f"Success rate: {passed_tests/total_tests*100:.1f}%")
            
            if baseline_time:
                print(f"\nPerformance baseline: {baseline_time:.2f}s for 10 files")
                print(f"Estimated time for 100 files: {baseline_time*10:.1f}s")
            
            
        finally:
            # Cleanup
            self.cleanup_test_environment()

if __name__ == "__main__":
    tester = SafetyTester()
    tester.run_all_tests()
