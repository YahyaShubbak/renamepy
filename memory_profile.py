#!/usr/bin/env python3
"""
Memory profiling tool for File Renamer application
"""

import os
import sys
import psutil
import time
from pathlib import Path

# Add modules to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'modules'))

def get_memory_usage():
    """Get current memory usage in MB"""
    process = psutil.Process()
    mem = process.memory_info()
    return {
        'rss_mb': mem.rss / (1024 * 1024),  # Resident Set Size
        'vms_mb': mem.vms / (1024 * 1024),  # Virtual Memory Size
    }

def profile_exif_cache():
    """Profile EXIF cache memory usage"""
    from modules.exif_processor import get_cached_exif_data, find_exiftool_path, _exif_cache
    from modules.file_utilities import scan_directory_recursive
    
    TEST_DIR = r"C:\Users\yshub\Desktop\Bilbao"
    
    print("="*70)
    print("📊 EXIF Cache Memory Profiling")
    print("="*70)
    
    # Baseline memory
    baseline = get_memory_usage()
    print(f"\n📍 Baseline memory: {baseline['rss_mb']:.1f} MB")
    
    # Scan files
    files = scan_directory_recursive(TEST_DIR)
    image_files = [f for f in files if os.path.splitext(f)[1].lower() in {'.jpg', '.jpeg', '.arw'}]
    print(f"📂 Found {len(image_files)} image files")
    
    exiftool_path = find_exiftool_path()
    
    # Process files in batches
    batch_sizes = [10, 50, 100, 200, 500, len(image_files)]
    results = []
    
    for batch_size in batch_sizes:
        if batch_size > len(image_files):
            continue
        
        # Clear cache before test
        _exif_cache.clear()
        
        # Process batch
        start_time = time.time()
        start_mem = get_memory_usage()
        
        for i, filepath in enumerate(image_files[:batch_size]):
            get_cached_exif_data(filepath, "exiftool", exiftool_path)
        
        end_time = time.time()
        end_mem = get_memory_usage()
        
        # Calculate stats
        duration = end_time - start_time
        mem_increase = end_mem['rss_mb'] - baseline['rss_mb']
        mem_per_file = mem_increase / batch_size if batch_size > 0 else 0
        cache_size = len(_exif_cache)
        
        results.append({
            'batch_size': batch_size,
            'duration': duration,
            'mem_mb': mem_increase,
            'mem_per_file_kb': mem_per_file * 1024,
            'cache_entries': cache_size
        })
        
        print(f"\n{'─'*70}")
        print(f"Batch: {batch_size} files")
        print(f"  ⏱️  Duration: {duration:.2f}s ({batch_size/duration:.1f} files/sec)")
        print(f"  💾 Memory: {mem_increase:.1f} MB (+{mem_per_file*1024:.1f} KB/file)")
        print(f"  📦 Cache: {cache_size} entries")
    
    print(f"\n{'='*70}")
    print("📈 Memory Usage Summary:")
    print(f"{'='*70}")
    
    for r in results:
        print(f"{r['batch_size']:>4} files: {r['mem_mb']:>6.1f} MB "
              f"({r['mem_per_file_kb']:>5.1f} KB/file, "
              f"{r['cache_entries']} cache entries)")
    
    # Estimate for large batches
    if results:
        avg_kb_per_file = sum(r['mem_per_file_kb'] for r in results) / len(results)
        
        print(f"\n💡 Extrapolation:")
        for size in [1000, 5000, 10000]:
            est_mb = (size * avg_kb_per_file) / 1024
            print(f"  {size:>5} files ≈ {est_mb:>6.1f} MB")
    
    print(f"{'='*70}")

def profile_file_list():
    """Profile file list memory usage"""
    print("\n" + "="*70)
    print("📋 File List Memory Profiling")
    print("="*70)
    
    baseline = get_memory_usage()
    print(f"\n📍 Baseline memory: {baseline['rss_mb']:.1f} MB")
    
    # Simulate file list with paths
    TEST_DIR = r"C:\Users\yshub\Desktop\Bilbao"
    file_paths = []
    
    batches = [100, 500, 1000, 5000]
    
    for batch_size in batches:
        # Generate dummy file paths
        file_paths = [
            os.path.join(TEST_DIR, f"image_{i:05d}.jpg")
            for i in range(batch_size)
        ]
        
        mem = get_memory_usage()
        mem_increase = mem['rss_mb'] - baseline['rss_mb']
        mem_per_file_kb = (mem_increase / batch_size * 1024) if batch_size > 0 else 0
        
        print(f"\n{batch_size:>5} paths: {mem_increase:>6.2f} MB ({mem_per_file_kb:>5.2f} KB/path)")
    
    print(f"{'='*70}")

if __name__ == "__main__":
    print("\n🚀 Memory Profiling Tool\n")
    
    # Test 1: EXIF Cache
    profile_exif_cache()
    
    # Test 2: File List
    profile_file_list()
    
    print("\n✅ Profiling complete!")
