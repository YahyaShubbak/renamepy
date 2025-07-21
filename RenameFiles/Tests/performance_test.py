#!/usr/bin/env python3
"""
Performance benchmark for the file renaming application
Tests the optimization improvements
"""

import os
import sys
import tempfile
import time
import shutil
from datetime import datetime

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def create_test_images(num_files=20, with_exif=False):
    """Create test image files for performance testing"""
    temp_dir = tempfile.mkdtemp(prefix="perf_test_")
    test_files = []
    
    print(f"Creating {num_files} test files in {temp_dir}")
    
    for i in range(num_files):
        filename = f"IMG_{i:04d}.jpg"
        filepath = os.path.join(temp_dir, filename)
        
        with open(filepath, 'wb') as f:
            # Write minimal JPEG header
            f.write(b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xff\xdb')
            
            if with_exif:
                # Add some fake EXIF-like data
                exif_data = f"DateTime: 2025:01:0{i%9 + 1}:12:30:45\nModel: TestCamera\nLensModel: TestLens\n"
                f.write(exif_data.encode('utf-8'))
            
            # Add some content to make it a reasonable size
            f.write(b'\x00' * 10000)  # 10KB file
        
        test_files.append(filepath)
    
    return temp_dir, test_files

def performance_test_original():
    """Test performance of original rename_files function"""
    from RenameFiles import rename_files
    
    temp_dir, test_files = create_test_images(20)
    
    print("\n" + "="*50)
    print("ORIGINAL PERFORMANCE TEST")
    print("="*50)
    
    try:
        start_time = time.time()
        
        renamed_files, errors = rename_files(
            files=test_files,
            camera_prefix="TEST",
            additional="perf",
            use_camera=False,
            use_lens=False,
            exif_method="pillow",
            devider="_",
            exiftool_path=None
        )
        
        end_time = time.time()
        duration = end_time - start_time
        
        print(f"Original method:")
        print(f"  Files processed: {len(renamed_files)}")
        print(f"  Errors: {len(errors)}")
        print(f"  Total time: {duration:.2f} seconds")
        print(f"  Time per file: {duration/len(test_files):.3f} seconds")
        print(f"  Files per second: {len(test_files)/duration:.1f}")
        
        return duration
        
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

def performance_test_optimized():
    """Test performance of optimized rename function using worker thread logic"""
    temp_dir, test_files = create_test_images(20)
    
    print("\n" + "="*50)
    print("OPTIMIZED PERFORMANCE TEST")
    print("="*50)
    
    try:
        from RenameFiles import RenameWorkerThread
        import time
        
        # Simulate the optimized process without actual GUI
        start_time = time.time()
        
        # Mock worker thread logic
        from RenameFiles import clear_global_exif_cache, get_cached_exif_data, sanitize_filename, check_file_access, get_safe_target_path
        from collections import defaultdict
        import re
        
        # Clear cache
        clear_global_exif_cache()
        
        # Group files
        file_groups = []
        basename_groups = defaultdict(list)
        for file in test_files:
            base = os.path.splitext(os.path.basename(file))[0]
            basename_groups[base].append(file)
        
        orphaned_files = []
        for base, file_list in basename_groups.items():
            if len(file_list) > 1:
                file_groups.append(file_list)
            else:
                orphaned_files.extend(file_list)
        
        for file in orphaned_files:
            file_groups.append([file])
        
        # Process groups with caching
        renamed_files = []
        errors = []
        date_counter = {}
        
        for group_files in file_groups:
            accessible_files = [f for f in group_files if check_file_access(f)]
            if not accessible_files:
                continue
            
            # Use cached EXIF (will be None for test files)
            date_taken = None
            for file in accessible_files:
                date_taken, _, _ = get_cached_exif_data(file, "pillow", None)
                if date_taken:
                    break
            
            # Fallback to filename date
            if not date_taken:
                for file in accessible_files:
                    m = re.search(r'(20\d{2})(\d{2})(\d{2})', os.path.basename(file))
                    if m:
                        date_taken = f"{m.group(1)}{m.group(2)}{m.group(3)}"
                        break
            
            if not date_taken:
                # Use current date
                date_taken = datetime.now().strftime('%Y%m%d')
            
            # Counter logic
            if date_taken not in date_counter:
                date_counter[date_taken] = 1
            else:
                date_counter[date_taken] += 1
            num = date_counter[date_taken]
            year = date_taken[:4]
            month = date_taken[4:6]
            day = date_taken[6:8]
            
            # Rename files
            for file in accessible_files:
                try:
                    ext = os.path.splitext(file)[1]
                    name_parts = [year, month, day, f"{num:02d}", "TEST", "perf"]
                    new_name = "_".join(name_parts) + ext
                    new_name = sanitize_filename(new_name)
                    new_path = get_safe_target_path(file, new_name)
                    
                    os.rename(file, new_path)
                    renamed_files.append(new_path)
                    
                except Exception as e:
                    errors.append(f"Failed to rename {os.path.basename(file)}: {e}")
        
        end_time = time.time()
        duration = end_time - start_time
        
        print(f"Optimized method:")
        print(f"  Files processed: {len(renamed_files)}")
        print(f"  Errors: {len(errors)}")
        print(f"  Total time: {duration:.2f} seconds")
        print(f"  Time per file: {duration/len(test_files):.3f} seconds")
        print(f"  Files per second: {len(test_files)/duration:.1f}")
        
        return duration
        
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

def run_performance_comparison():
    """Run performance comparison between original and optimized methods"""
    print("PERFORMANCE COMPARISON")
    print("Testing file renaming performance with 20 test files")
    
    # Test original method
    try:
        original_time = performance_test_original()
    except Exception as e:
        print(f"Original test failed: {e}")
        original_time = None
    
    # Test optimized method
    try:
        optimized_time = performance_test_optimized()
    except Exception as e:
        print(f"Optimized test failed: {e}")
        optimized_time = None
    
    # Compare results
    print("\n" + "="*50)
    print("PERFORMANCE COMPARISON RESULTS")
    print("="*50)
    
    if original_time and optimized_time:
        improvement = ((original_time - optimized_time) / original_time) * 100
        speedup = original_time / optimized_time
        
        print(f"Original method:  {original_time:.2f} seconds")
        print(f"Optimized method: {optimized_time:.2f} seconds")
        print(f"Improvement:      {improvement:.1f}% faster")
        print(f"Speedup factor:   {speedup:.1f}x")
        
        if improvement > 0:
            print("✓ Optimization successful!")
        else:
            print("⚠ Optimization did not improve performance")
    else:
        print("Could not complete performance comparison")

def estimate_large_batch_performance():
    """Estimate performance for larger batches"""
    print("\n" + "="*50)
    print("LARGE BATCH ESTIMATION")
    print("="*50)
    
    # Test with smaller batch and extrapolate
    temp_dir, test_files = create_test_images(5)
    
    try:
        start_time = time.time()
        optimized_time = performance_test_optimized()
        
        # Estimate for different batch sizes
        batch_sizes = [10, 50, 100, 500, 1000]
        time_per_file = optimized_time / len(test_files)
        
        print(f"Time per file (5 file sample): {time_per_file:.3f} seconds")
        print("\nEstimated processing times:")
        
        for batch_size in batch_sizes:
            estimated_time = time_per_file * batch_size
            if estimated_time < 60:
                print(f"  {batch_size:4d} files: {estimated_time:.1f} seconds")
            else:
                minutes = estimated_time / 60
                print(f"  {batch_size:4d} files: {minutes:.1f} minutes")
                
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

if __name__ == "__main__":
    run_performance_comparison()
    estimate_large_batch_performance()
