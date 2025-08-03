#!/usr/bin/env python3
"""
Performance optimized version of rename functionality
Addresses bottlenecks in EXIF processing and file operations
"""

import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache
import threading

# Global cache for EXIF data with thread safety
_exif_cache = {}
_cache_lock = threading.Lock()

def clear_exif_cache():
    """Clear the global EXIF cache"""
    global _exif_cache
    with _cache_lock:
        _exif_cache.clear()

@lru_cache(maxsize=1000)
def get_file_stat_cached(filepath):
    """Cached file stat to avoid repeated filesystem calls"""
    try:
        return os.path.getmtime(filepath), os.path.getsize(filepath)
    except:
        return None, None

def extract_exif_cached(image_path, method, exiftool_path=None):
    """
    Extract EXIF with intelligent caching based on file modification time
    """
    # Generate cache key based on file path and modification time
    mtime, size = get_file_stat_cached(image_path)
    if mtime is None:
        return None, None, None
    
    cache_key = (image_path, mtime, size, method)
    
    with _cache_lock:
        if cache_key in _exif_cache:
            return _exif_cache[cache_key]
    
    # Extract EXIF data (not cached)
    from RenameFiles import extract_exif_fields_with_retry
    try:
        result = extract_exif_fields_with_retry(image_path, method, exiftool_path, max_retries=2)
        
        # Cache the result
        with _cache_lock:
            _exif_cache[cache_key] = result
            
        return result
    except Exception as e:
        print(f"EXIF extraction failed for {image_path}: {e}")
        return None, None, None

def batch_extract_exif(files, method, exiftool_path=None, max_workers=4):
    """
    Extract EXIF data from multiple files in parallel
    """
    results = {}
    
    # Use ThreadPoolExecutor for I/O bound EXIF reading
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_file = {
            executor.submit(extract_exif_cached, file, method, exiftool_path): file 
            for file in files
        }
        
        # Collect results as they complete
        for future in as_completed(future_to_file):
            file = future_to_file[future]
            try:
                result = future.result(timeout=10)  # 10 second timeout per file
                results[file] = result
            except Exception as e:
                print(f"Failed to process {file}: {e}")
                results[file] = (None, None, None)
    
    return results

def optimized_group_files(files, exif_method, exiftool_path=None):
    """
    Optimized file grouping with batch EXIF processing and minimal I/O
    """
    from collections import defaultdict
    import re
    from datetime import datetime
    
    print(f"Processing {len(files)} files for grouping...")
    start_time = time.time()
    
    # Step 1: Group by basename (fast - no I/O)
    basename_groups = defaultdict(list)
    for file in files:
        base = os.path.splitext(os.path.basename(file))[0]
        basename_groups[base].append(file)
    
    # Step 2: Identify groups and orphans
    final_groups = []
    orphaned_files = []
    
    for base, file_list in basename_groups.items():
        if len(file_list) > 1:
            final_groups.append(file_list)
        else:
            orphaned_files.append(file_list[0])
    
    basename_time = time.time()
    print(f"Basename grouping: {basename_time - start_time:.2f}s")
    print(f"Found {len(final_groups)} base groups, {len(orphaned_files)} orphans")
    
    # Step 3: Process orphans with batch EXIF extraction (if needed)
    if len(orphaned_files) > 1 and exif_method:
        print("Processing orphaned files with batch EXIF extraction...")
        
        # Extract timestamps for all orphaned files in parallel
        exif_results = batch_extract_exif(orphaned_files, exif_method, exiftool_path)
        
        # Parse timestamps efficiently
        file_timestamps = {}
        for file in orphaned_files:
            _, _, _ = exif_results.get(file, (None, None, None))
            # For timestamp matching, we need a separate function
            timestamp = get_file_timestamp_from_cache(file, exif_method, exiftool_path)
            if timestamp:
                try:
                    clean_timestamp = timestamp.split('+')[0].split('-')[0]
                    parsed_time = datetime.strptime(clean_timestamp, '%Y:%m:%d %H:%M:%S')
                    file_timestamps[file] = parsed_time
                except:
                    try:
                        parsed_time = datetime.strptime(clean_timestamp, '%Y-%m-%d %H:%M:%S')
                        file_timestamps[file] = parsed_time
                    except:
                        continue
        
        # Group by timestamp (fast - in memory)
        used_files = set()
        for file1 in orphaned_files:
            if file1 in used_files or file1 not in file_timestamps:
                continue
                
            group = [file1]
            used_files.add(file1)
            
            for file2 in orphaned_files:
                if file2 in used_files or file2 not in file_timestamps:
                    continue
                
                time_diff = abs((file_timestamps[file1] - file_timestamps[file2]).total_seconds())
                if time_diff <= 2:
                    group.append(file2)
                    used_files.add(file2)
            
            final_groups.append(group)
        
        # Add remaining orphans
        for file in orphaned_files:
            if file not in used_files:
                final_groups.append([file])
    else:
        # Add orphans as individual groups
        for file in orphaned_files:
            final_groups.append([file])
    
    total_time = time.time() - start_time
    print(f"Total grouping time: {total_time:.2f}s")
    
    return final_groups

def get_file_timestamp_from_cache(image_path, method, exiftool_path=None):
    """Get timestamp using the cached EXIF data"""
    # This would need to be implemented to use cached data
    # For now, fall back to original function
    from RenameFiles import get_file_timestamp
    return get_file_timestamp(image_path, method, exiftool_path)

def optimized_rename_files(files, camera_prefix, additional, use_camera, use_lens, 
                          exif_method, devider="_", exiftool_path=None):
    """
    Optimized rename function with batch processing and minimal EXIF reads
    """
    import re
    from RenameFiles import (
        sanitize_filename, check_file_access, get_safe_target_path, 
        validate_path_length, verify_group_consistency
    )
    
    print(f"Starting optimized rename of {len(files)} files...")
    start_time = time.time()
    
    # Clear cache for fresh start
    clear_exif_cache()
    
    # Step 1: Fast grouping
    file_groups = optimized_group_files(files, exif_method, exiftool_path)
    grouping_time = time.time()
    print(f"Grouping completed in {grouping_time - start_time:.2f}s")
    
    # Step 2: Batch EXIF extraction for all files that need it
    all_files_needing_exif = []
    for group in file_groups:
        all_files_needing_exif.extend(group)
    
    print(f"Batch extracting EXIF from {len(all_files_needing_exif)} files...")
    exif_data_batch = batch_extract_exif(all_files_needing_exif, exif_method, exiftool_path)
    exif_time = time.time()
    print(f"EXIF extraction completed in {exif_time - grouping_time:.2f}s")
    
    # Step 3: Fast rename processing using cached data
    renamed_files = []
    errors = []
    skipped_files = []
    date_counter = {}
    
    for group_files in file_groups:
        # Quick file access check
        accessible_files = [f for f in group_files if check_file_access(f)]
        if not accessible_files:
            continue
        
        # Use cached EXIF data
        date_taken = None
        camera_model = None
        lens_model = None
        
        for file in accessible_files:
            if file in exif_data_batch:
                date, camera, lens = exif_data_batch[file]
                if not date_taken:
                    date_taken = date
                if use_camera and not camera_model:
                    camera_model = camera
                if use_lens and not lens_model:
                    lens_model = lens
                
                if date_taken and (not use_camera or camera_model) and (not use_lens or lens_model):
                    break
        
        # Fallback date extraction (fast)
        if not date_taken:
            for file in accessible_files:
                m = re.search(r'(20\d{2})(\d{2})(\d{2})', os.path.basename(file))
                if m:
                    date_taken = f"{m.group(1)}{m.group(2)}{m.group(3)}"
                    break
        
        if not date_taken:
            # Fallback: use file modification date
            file = accessible_files[0]
            mtime = os.path.getmtime(file)
            import datetime
            dt = datetime.datetime.fromtimestamp(mtime)
            date_taken = dt.strftime('%Y%m%d')
        
        # Counter logic (fast)
        if date_taken not in date_counter:
            date_counter[date_taken] = 1
        else:
            date_counter[date_taken] += 1
        num = date_counter[date_taken]
        year = date_taken[:4]
        month = date_taken[4:6]
        day = date_taken[6:8]
        
        # Fast rename processing
        for file in accessible_files:
            try:
                ext = os.path.splitext(file)[1]
                name_parts = [year, month, day, f"{num:02d}"]
                if camera_prefix:
                    name_parts.append(camera_prefix)
                if additional:
                    name_parts.append(additional)
                if use_camera and camera_model:
                    name_parts.append(camera_model)
                if use_lens and lens_model:
                    name_parts.append(lens_model)
                
                sep = "" if devider == "None" else devider
                new_name = sep.join(name_parts) + ext
                new_name = sanitize_filename(new_name)
                new_path = get_safe_target_path(file, new_name)
                
                if not validate_path_length(new_path):
                    # Quick path shortening
                    directory = os.path.dirname(file)
                    base, ext = os.path.splitext(new_name)
                    max_name_len = 200 - len(directory)
                    if max_name_len > 10:
                        shortened_base = base[:max_name_len - len(ext)]
                        new_name = shortened_base + ext
                        new_path = os.path.join(directory, new_name)
                    else:
                        errors.append(f"Path too long: {file}")
                        continue
                
                os.rename(file, new_path)
                renamed_files.append(new_path)
                
            except Exception as e:
                errors.append(f"Failed to rename {os.path.basename(file)}: {e}")
                skipped_files.append(file)
    
    total_time = time.time() - start_time
    print(f"\nOptimized rename completed in {total_time:.2f}s")
    print(f"Performance breakdown:")
    print(f"  - Grouping: {grouping_time - start_time:.2f}s")
    print(f"  - EXIF extraction: {exif_time - grouping_time:.2f}s") 
    print(f"  - File operations: {total_time - exif_time:.2f}s")
    print(f"Successfully renamed: {len(renamed_files)} files")
    if errors:
        print(f"Errors: {len(errors)}")
    
    return renamed_files, errors

if __name__ == "__main__":
    # Performance test
    print("Performance optimization module loaded")
    print("Use optimized_rename_files() instead of rename_files() for better performance")
