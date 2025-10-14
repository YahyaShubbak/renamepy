#!/usr/bin/env python3
"""
Performance Test: EXIF-basierte Sortierung (bis auf Sekunde genau)

Testet die Performance-Auswirkungen der neuen chronologischen Sortierung
"""

import os
import sys
import time
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.file_utilities import scan_directory_recursive, is_media_file
from modules.exif_processor import (
    get_selective_cached_exif_data, 
    get_exiftool_metadata_shared,
    find_exiftool_path,
    clear_global_exif_cache
)
import re
import datetime
from collections import defaultdict


def test_exif_sorting_performance(directory, num_runs=3):
    """
    Test the performance of EXIF-based chronological sorting
    
    Args:
        directory: Directory with test images
        num_runs: Number of test runs for averaging
    """
    print("=" * 80)
    print("🔬 EXIF SORTING PERFORMANCE TEST")
    print("=" * 80)
    print()
    
    # Find ExifTool
    exiftool_path = find_exiftool_path()
    if not exiftool_path:
        print("❌ ExifTool not found! Test cannot proceed.")
        return
    
    print(f"✅ ExifTool found: {exiftool_path}")
    print()
    
    # Scan directory
    print(f"📁 Scanning directory: {directory}")
    files = scan_directory_recursive(directory)
    print(f"✅ Found {len(files)} media files")
    print()
    
    if len(files) == 0:
        print("❌ No files found to test!")
        return
    
    # Group files (same logic as rename_engine)
    basename_groups = defaultdict(list)
    for path in files:
        if is_media_file(path):
            directory_path = os.path.dirname(path)
            stem = os.path.splitext(os.path.basename(path))[0]
            basename_groups[f"{directory_path}#{stem}"].append(path)
    
    file_groups = []
    orphans = []
    for _k, group in basename_groups.items():
        if len(group) > 1:
            file_groups.append(group)
        else:
            orphans.extend(group)
    for f in orphans:
        file_groups.append([f])
    
    print(f"📊 Created {len(file_groups)} file groups")
    print()
    
    # Define the sorting function (same as in rename_engine.py)
    def get_exif_sort_key(group):
        """Sort key based on EXIF DateTimeOriginal (down to seconds)"""
        first_file = group[0]
        
        # Try to get EXIF timestamp
        exif_datetime = None
        try:
            date_str, _, _ = get_selective_cached_exif_data(
                first_file, "exiftool", exiftool_path,
                need_date=True, need_camera=False, need_lens=False
            )
            if date_str:
                # Try to get full datetime from raw EXIF
                raw_meta = get_exiftool_metadata_shared(first_file, exiftool_path)
                if raw_meta:
                    # Look for DateTimeOriginal with time
                    datetime_fields = [
                        'EXIF:DateTimeOriginal',
                        'EXIF:CreateDate', 
                        'QuickTime:CreateDate',
                        'QuickTime:CreationDate'
                    ]
                    for field in datetime_fields:
                        if field in raw_meta:
                            dt_str = raw_meta[field]
                            # Parse format: "2024:01:15 10:30:45"
                            try:
                                if ':' in dt_str:
                                    # Handle both "2024:01:15 10:30:45" and "2024-01-15 10:30:45"
                                    dt_str_clean = dt_str.replace(':', '-', 2)  # Replace first 2 colons
                                    exif_datetime = datetime.datetime.strptime(dt_str_clean, "%Y-%m-%d %H:%M:%S")
                                    break
                            except Exception:
                                pass
        except Exception:
            pass
        
        # Fallback to file modification time
        if not exif_datetime:
            try:
                mtime = os.path.getmtime(first_file)
                exif_datetime = datetime.datetime.fromtimestamp(mtime)
            except Exception:
                exif_datetime = datetime.datetime(1970, 1, 1)
        
        # Extract number from filename as tiebreaker
        basename = os.path.basename(first_file)
        match = re.search(r'(\d+)', basename)
        file_number = int(match.group(1)) if match else 0
        
        return (exif_datetime, file_number, first_file)
    
    # Run performance tests
    times = []
    
    for run in range(num_runs):
        print(f"🔄 Run {run + 1}/{num_runs}...")
        
        # Clear cache before each run for fair comparison
        clear_global_exif_cache()
        
        # Measure sorting time
        start_time = time.time()
        
        # Perform the sort
        sorted_groups = sorted(file_groups, key=get_exif_sort_key)
        
        end_time = time.time()
        elapsed = end_time - start_time
        times.append(elapsed)
        
        print(f"   ⏱️  Time: {elapsed:.2f} seconds ({len(file_groups) / elapsed:.1f} groups/sec)")
        print()
    
    # Calculate statistics
    avg_time = sum(times) / len(times)
    min_time = min(times)
    max_time = max(times)
    
    print("=" * 80)
    print("📊 RESULTS")
    print("=" * 80)
    print(f"Files:          {len(files)}")
    print(f"Groups:         {len(file_groups)}")
    print(f"Runs:           {num_runs}")
    print()
    print(f"Average Time:   {avg_time:.2f} seconds")
    print(f"Min Time:       {min_time:.2f} seconds")
    print(f"Max Time:       {max_time:.2f} seconds")
    print()
    print(f"Throughput:     {len(file_groups) / avg_time:.1f} groups/sec")
    print(f"                {len(files) / avg_time:.1f} files/sec")
    print()
    
    # Show sample of sorted results
    print("=" * 80)
    print("📋 SAMPLE SORTED ORDER (First 10 groups)")
    print("=" * 80)
    
    sorted_groups = sorted(file_groups, key=get_exif_sort_key)
    for idx, group in enumerate(sorted_groups[:10]):
        first_file = group[0]
        basename = os.path.basename(first_file)
        
        # Get EXIF datetime
        exif_dt, file_num, _ = get_exif_sort_key(group)
        
        print(f"{idx + 1:3}. {basename:50} → {exif_dt.strftime('%Y-%m-%d %H:%M:%S')}")
    
    if len(sorted_groups) > 10:
        print(f"... and {len(sorted_groups) - 10} more groups")
    
    print()
    print("=" * 80)
    print("✅ PERFORMANCE TEST COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Test EXIF sorting performance")
    parser.add_argument(
        "directory",
        nargs="?",
        default=".",
        help="Directory to test (default: current directory)"
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=3,
        help="Number of test runs (default: 3)"
    )
    
    args = parser.parse_args()
    
    test_exif_sorting_performance(args.directory, args.runs)
