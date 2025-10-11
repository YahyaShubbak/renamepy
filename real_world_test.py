#!/usr/bin/env python3
"""
Real-World Performance Test with actual photos from Bilbao
Tests EXIF extraction performance with real JPEG and RAW files
"""

import os
import sys
import time
import json
from datetime import datetime

# Add modules to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'modules'))

from modules.exif_processor import get_cached_exif_data, EXIFTOOL_AVAILABLE, find_exiftool_path
from modules.file_utilities import scan_directory_recursive

# Test directory
TEST_DIR = r"C:\Users\yshub\Desktop\Bilbao"

def test_exif_extraction():
    """Test EXIF extraction performance with real photos"""
    
    print("="*70)
    print("🔬 Real-World EXIF Performance Test")
    print("="*70)
    print(f"Test Directory: {TEST_DIR}")
    print()
    
    # Get ExifTool path
    exiftool_path = find_exiftool_path()
    if not exiftool_path:
        print("❌ ExifTool not found!")
        return None
    
    print(f"✅ Using ExifTool: {exiftool_path}")
    print()
    
    # Scan directory
    print("📂 Scanning directory...")
    start_scan = time.perf_counter()
    files = scan_directory_recursive(TEST_DIR)
    scan_duration = time.perf_counter() - start_scan
    
    # Filter for images
    image_extensions = {'.jpg', '.jpeg', '.arw', '.cr2', '.nef', '.dng'}
    image_files = [f for f in files if os.path.splitext(f)[1].lower() in image_extensions]
    
    print(f"   Found {len(files)} total files")
    print(f"   Found {len(image_files)} image files")
    print(f"   Scan duration: {scan_duration:.3f}s ({len(files)/scan_duration:.0f} files/sec)")
    print()
    
    # Test EXIF extraction
    print("📸 Testing EXIF extraction...")
    
    results = {
        'total_files': len(image_files),
        'successful': 0,
        'failed': 0,
        'exif_data': [],
        'errors': [],
        'timing': {
            'total': 0,
            'per_file_avg': 0,
            'per_file_min': float('inf'),
            'per_file_max': 0
        }
    }
    
    file_times = []
    
    start_time = time.perf_counter()
    
    for i, filepath in enumerate(image_files, 1):
        if i % 50 == 0:
            print(f"   Progress: {i}/{len(image_files)} files...")
        
        try:
            file_start = time.perf_counter()
            date, camera, lens = get_cached_exif_data(filepath, "exiftool", exiftool_path)
            file_duration = time.perf_counter() - file_start
            file_times.append(file_duration)
            
            if date or camera or lens:
                results['successful'] += 1
                
                # Extract key metadata
                metadata = {
                    'file': os.path.basename(filepath),
                    'extension': os.path.splitext(filepath)[1],
                    'size_mb': os.path.getsize(filepath) / (1024*1024),
                    'extraction_time_ms': file_duration * 1000,
                    'date': date or 'N/A',
                    'camera': camera or 'N/A',
                    'lens': lens or 'N/A',
                }
                results['exif_data'].append(metadata)
            else:
                results['failed'] += 1
                results['errors'].append({
                    'file': os.path.basename(filepath),
                    'error': 'No EXIF data returned'
                })
                
        except Exception as e:
            results['failed'] += 1
            results['errors'].append({
                'file': os.path.basename(filepath),
                'error': str(e)
            })
    
    total_duration = time.perf_counter() - start_time
    
    # Calculate timing stats
    results['timing']['total'] = total_duration
    if file_times:
        results['timing']['per_file_avg'] = sum(file_times) / len(file_times)
        results['timing']['per_file_min'] = min(file_times)
        results['timing']['per_file_max'] = max(file_times)
    
    # Print results
    print()
    print("="*70)
    print("📊 Results")
    print("="*70)
    print(f"✅ Successful: {results['successful']}/{results['total_files']} ({results['successful']/results['total_files']*100:.1f}%)")
    print(f"❌ Failed: {results['failed']}/{results['total_files']}")
    print()
    print(f"⏱️  Total Time: {total_duration:.2f}s")
    print(f"⚡ Throughput: {len(image_files)/total_duration:.1f} files/sec")
    print()
    print(f"📈 Per-File Timing:")
    print(f"   Average: {results['timing']['per_file_avg']*1000:.1f} ms")
    print(f"   Min: {results['timing']['per_file_min']*1000:.1f} ms")
    print(f"   Max: {results['timing']['per_file_max']*1000:.1f} ms")
    print()
    
    # Show sample EXIF data
    if results['exif_data']:
        print("📸 Sample EXIF Data (first 5 files):")
        for item in results['exif_data'][:5]:
            print(f"\n   {item['file']} ({item['size_mb']:.1f} MB, {item['extension']})")
            print(f"      Date: {item['date']}")
            print(f"      Camera: {item['camera']}")
            print(f"      Lens: {item['lens']}")
            print(f"      Extraction: {item['extraction_time_ms']:.1f} ms")
    
    # Show errors if any
    if results['errors']:
        print(f"\n❌ Errors ({len(results['errors'])} files):")
        for error in results['errors'][:5]:
            print(f"   {error['file']}: {error['error']}")
        if len(results['errors']) > 5:
            print(f"   ... and {len(results['errors']) - 5} more")
    
    # Compare JPG vs RAW performance
    jpg_times = [d['extraction_time_ms'] for d in results['exif_data'] if d['extension'].lower() in ['.jpg', '.jpeg']]
    raw_times = [d['extraction_time_ms'] for d in results['exif_data'] if d['extension'].lower() == '.arw']
    
    if jpg_times and raw_times:
        print()
        print("📊 Format Comparison:")
        print(f"   JPG: {sum(jpg_times)/len(jpg_times):.1f} ms avg ({len(jpg_times)} files)")
        print(f"   RAW: {sum(raw_times)/len(raw_times):.1f} ms avg ({len(raw_times)} files)")
        print(f"   Ratio: RAW is {(sum(raw_times)/len(raw_times))/(sum(jpg_times)/len(jpg_times)):.1f}x slower")
    
    # Save detailed report
    report_file = f"real_world_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print()
    print(f"📄 Detailed report saved: {report_file}")
    print("="*70)
    
    return results


def test_cache_effectiveness():
    """Test how effective the EXIF cache is"""
    
    print()
    print("="*70)
    print("🔄 Cache Effectiveness Test")
    print("="*70)
    
    exiftool_path = find_exiftool_path()
    files = scan_directory_recursive(TEST_DIR)
    image_files = [f for f in files if os.path.splitext(f)[1].lower() in {'.jpg', '.jpeg', '.arw'}][:100]
    
    print(f"Testing with {len(image_files)} files")
    
    # First pass - populate cache
    print("\n1️⃣ First pass (cold cache)...")
    start = time.perf_counter()
    for f in image_files:
        get_cached_exif_data(f, "exiftool", exiftool_path)
    first_pass = time.perf_counter() - start
    
    # Second pass - use cache
    print("2️⃣ Second pass (warm cache)...")
    start = time.perf_counter()
    for f in image_files:
        get_cached_exif_data(f, "exiftool", exiftool_path)
    second_pass = time.perf_counter() - start
    
    speedup = first_pass / second_pass
    
    print()
    print(f"⏱️  First pass:  {first_pass:.3f}s ({len(image_files)/first_pass:.1f} files/sec)")
    print(f"⚡ Second pass: {second_pass:.3f}s ({len(image_files)/second_pass:.1f} files/sec)")
    print(f"🚀 Speedup: {speedup:.1f}x faster with cache")
    print("="*70)


if __name__ == "__main__":
    print("\n🚀 Starting Real-World Performance Tests\n")
    
    # Test 1: EXIF extraction
    results = test_exif_extraction()
    
    # Test 2: Cache effectiveness
    test_cache_effectiveness()
    
    print("\n✅ All tests completed!")
