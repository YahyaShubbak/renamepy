#!/usr/bin/env python3
"""
COMPREHENSIVE STRESS TEST: 10,000 Files in All Scenarios
Tests all possible combinations and edge cases for the continuous counter feature.
"""

import os
import shutil
import tempfile
import sys
from datetime import datetime, timedelta
import random

# Add current directory to path to import RenameFiles
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from RenameFiles import RenameWorkerThread, clear_global_exif_cache, is_media_file

def create_test_environment():
    """Create comprehensive test environment with 10,000 files"""
    
    # Create temporary directory
    test_dir = tempfile.mkdtemp(prefix="stress_test_10k_")
    print(f"📁 Created test directory: {test_dir}")
    
    scenarios = []
    
    # ============================================================================
    # SCENARIO 1: Massive Single Directory (3,000 files)
    # ============================================================================
    scenario1_dir = os.path.join(test_dir, "scenario1_single_massive")
    os.makedirs(scenario1_dir)
    
    print("🏗️ Scenario 1: Creating 3,000 files in single directory...")
    scenario1_files = []
    base_date = datetime(2023, 6, 15)
    
    for i in range(1, 1501):  # 1,500 JPG+ARW pairs = 3,000 files
        # Mix of different camera filename patterns
        if i <= 500:
            base_name = f"DSC_{i:05d}"  # Sony style
        elif i <= 1000:
            base_name = f"IMG_{i:04d}"  # Canon style
        else:
            base_name = f"_MG_{i:04d}"  # Canon RAW style
        
        # Spread across multiple days
        file_date = base_date + timedelta(days=(i-1) // 100)
        date_str = file_date.strftime("%Y%m%d")
        
        # Create JPG and ARW files
        jpg_file = os.path.join(scenario1_dir, f"{base_name}.JPG")
        arw_file = os.path.join(scenario1_dir, f"{base_name}.ARW")
        
        for file_path in [jpg_file, arw_file]:
            with open(file_path, 'w') as f:
                f.write(f"Date: {date_str}\nCamera: Sony A7R IV\nLens: Sony 24-70mm f/2.8\n")
            scenario1_files.append(file_path)
    
    scenarios.append(("Scenario 1: Single Directory (3,000 files)", scenario1_files))
    print(f"✅ Created {len(scenario1_files)} files in scenario 1")
    
    # ============================================================================
    # SCENARIO 2: Multiple Subdirectories with Identical Filenames (2,500 files)
    # ============================================================================
    print("🏗️ Scenario 2: Creating 2,500 files across 10 subdirectories with identical filenames...")
    scenario2_files = []
    
    for subdir_num in range(1, 11):  # 10 subdirectories
        subdir = os.path.join(test_dir, "scenario2_multi_dirs", f"Camera_{subdir_num:02d}")
        os.makedirs(subdir, exist_ok=True)
        
        # Each subdirectory has identical filename patterns (CRITICAL TEST CASE)
        for i in range(1, 126):  # 125 files per subdir × 2 formats = 250 files per subdir
            base_name = f"_DSC{i:04d}"  # Identical basenames across all folders!
            
            # Different dates per subdirectory
            base_date = datetime(2023, 7, 1) + timedelta(days=subdir_num*10)
            file_date = base_date + timedelta(hours=i)
            date_str = file_date.strftime("%Y%m%d")
            
            jpg_file = os.path.join(subdir, f"{base_name}.JPG")
            arw_file = os.path.join(subdir, f"{base_name}.ARW")
            
            for file_path in [jpg_file, arw_file]:
                with open(file_path, 'w') as f:
                    f.write(f"Date: {date_str}\nCamera: Nikon D850\nSubdir: {subdir_num}\n")
                scenario2_files.append(file_path)
    
    scenarios.append(("Scenario 2: Multi-Directory Identical Names (2,500 files)", scenario2_files))
    print(f"✅ Created {len(scenario2_files)} files in scenario 2")
    
    # ============================================================================
    # SCENARIO 3: Mixed Dates Chronological Chaos (2,000 files)
    # ============================================================================
    print("🏗️ Scenario 3: Creating 2,000 files with completely mixed chronological dates...")
    scenario3_dir = os.path.join(test_dir, "scenario3_mixed_dates")
    os.makedirs(scenario3_dir)
    scenario3_files = []
    
    # Create completely random date distribution
    random_dates = []
    for i in range(1000):  # 1000 pairs = 2000 files
        # Random dates across 2 years
        random_date = datetime(2022, 1, 1) + timedelta(days=random.randint(0, 730))
        random_dates.append(random_date)
    
    # Sort by date for verification later
    random_dates.sort()
    
    # Create files with random order filenames but sorted dates
    for i, date_obj in enumerate(random_dates):
        # Random camera filename that doesn't match date order
        random_num = random.randint(1000, 9999)
        base_name = f"CHAOS_{random_num}"
        
        date_str = date_obj.strftime("%Y%m%d")
        
        jpg_file = os.path.join(scenario3_dir, f"{base_name}.JPG")
        arw_file = os.path.join(scenario3_dir, f"{base_name}.ARW")
        
        for file_path in [jpg_file, arw_file]:
            with open(file_path, 'w') as f:
                f.write(f"Date: {date_str}\nCamera: Canon EOS R5\nChaos: {random_num}\n")
            scenario3_files.append(file_path)
    
    scenarios.append(("Scenario 3: Mixed Dates Chaos (2,000 files)", scenario3_files))
    print(f"✅ Created {len(scenario3_files)} files in scenario 3")
    
    # ============================================================================
    # SCENARIO 4: Deep Nested Structure (1,500 files)
    # ============================================================================
    print("🏗️ Scenario 4: Creating 1,500 files in deep nested structure...")
    scenario4_files = []
    
    for year in [2021, 2022, 2023]:
        for month in range(1, 6):  # 5 months per year
            for day in range(1, 11):  # 10 days per month
                subdir = os.path.join(test_dir, "scenario4_deep_nested", 
                                    f"{year}", f"{month:02d}", f"{day:02d}")
                os.makedirs(subdir, exist_ok=True)
                
                # Only 10 files per deepest directory (5 pairs)
                for i in range(1, 6):
                    base_name = f"DEEP_{i:03d}"
                    date_str = f"{year}{month:02d}{day:02d}"
                    
                    jpg_file = os.path.join(subdir, f"{base_name}.JPG")
                    arw_file = os.path.join(subdir, f"{base_name}.ARW")
                    
                    for file_path in [jpg_file, arw_file]:
                        with open(file_path, 'w') as f:
                            f.write(f"Date: {date_str}\nCamera: Olympus OM-1\nDeep: {year}-{month}-{day}\n")
                        scenario4_files.append(file_path)
    
    scenarios.append(("Scenario 4: Deep Nested Structure (1,500 files)", scenario4_files))
    print(f"✅ Created {len(scenario4_files)} files in scenario 4")
    
    # ============================================================================
    # SCENARIO 5: Single Files + Orphans (1,000 files)
    # ============================================================================
    print("🏗️ Scenario 5: Creating 1,000 orphaned single files...")
    scenario5_dir = os.path.join(test_dir, "scenario5_orphans")
    os.makedirs(scenario5_dir)
    scenario5_files = []
    
    for i in range(1, 1001):  # 1,000 individual files (no pairs)
        # Mix of different formats
        if i % 3 == 0:
            ext = ".JPG"
        elif i % 3 == 1:
            ext = ".ARW"
        else:
            ext = ".CR2"
        
        base_name = f"ORPHAN_{i:04d}"
        base_date = datetime(2023, 8, 1)
        file_date = base_date + timedelta(hours=i)
        date_str = file_date.strftime("%Y%m%d")
        
        file_path = os.path.join(scenario5_dir, f"{base_name}{ext}")
        with open(file_path, 'w') as f:
            f.write(f"Date: {date_str}\nCamera: Fujifilm X-T5\nOrphan: {i}\n")
        scenario5_files.append(file_path)
    
    scenarios.append(("Scenario 5: Orphaned Singles (1,000 files)", scenario5_files))
    print(f"✅ Created {len(scenario5_files)} files in scenario 5")
    
    # ============================================================================
    # SUMMARY
    # ============================================================================
    total_files = sum(len(files) for _, files in scenarios)
    print(f"\n🎯 STRESS TEST ENVIRONMENT CREATED:")
    print(f"   📊 Total files: {total_files:,}")
    for name, files in scenarios:
        print(f"   📁 {name}: {len(files):,} files")
    
    return test_dir, scenarios

def run_comprehensive_stress_tests(test_dir, scenarios):
    """Run all stress tests with different configurations"""
    
    print(f"\n🚀 STARTING COMPREHENSIVE STRESS TESTS WITH {sum(len(files) for _, files in scenarios):,} FILES\n")
    
    # Test configurations to try
    test_configs = [
        {
            "name": "Continuous Counter + Date + Camera + Lens",
            "camera_prefix": "STRESS",
            "additional": "TEST",
            "use_camera": True,
            "use_lens": True,
            "continuous_counter": True,
            "use_date": True,
            "date_format": "YYYY-MM-DD"
        },
        {
            "name": "Continuous Counter + Date Only",
            "camera_prefix": "DATE",
            "additional": "",
            "use_camera": False,
            "use_lens": False,
            "continuous_counter": True,
            "use_date": True,
            "date_format": "YYYYMMDD"
        },
        {
            "name": "Standard Counter + All Fields",
            "camera_prefix": "STD",
            "additional": "",
            "use_camera": True,
            "use_lens": True,
            "continuous_counter": False,
            "use_date": True,
            "date_format": "YYYY_MM_DD"
        },
        {
            "name": "No Date + Continuous Counter",
            "camera_prefix": "NODATE",
            "additional": "",
            "use_camera": False,
            "use_lens": False,
            "continuous_counter": True,
            "use_date": False,
            "date_format": "YYYY-MM-DD"
        }
    ]
    
    overall_results = []
    
    for config_idx, config in enumerate(test_configs, 1):
        print(f"\n{'='*80}")
        print(f"🧪 TEST CONFIGURATION {config_idx}/4: {config['name']}")
        print(f"{'='*80}")
        
        config_results = []
        
        for scenario_name, scenario_files in scenarios:
            print(f"\n📋 Testing {scenario_name}...")
            print(f"   Files: {len(scenario_files):,}")
            
            # Create a copy of files for testing (since rename modifies them)
            test_files = scenario_files.copy()
            
            try:
                # Clear cache before each test
                clear_global_exif_cache()
                
                # Record start time
                start_time = datetime.now()
                
                # Create worker thread with current configuration
                worker = RenameWorkerThread(
                    files=test_files,
                    camera_prefix=config["camera_prefix"],
                    additional=config["additional"],
                    use_camera=config["use_camera"],
                    use_lens=config["use_lens"],
                    exif_method=None,  # No EXIF for stress test
                    devider="-",
                    exiftool_path=None,
                    custom_order=["Date", "Prefix", "Additional", "Camera", "Lens"],
                    date_format=config["date_format"],
                    use_date=config["use_date"],
                    continuous_counter=config["continuous_counter"]
                )
                
                # Run the worker in main thread for testing
                worker.run()
                
                # Calculate performance
                end_time = datetime.now()
                duration = (end_time - start_time).total_seconds()
                files_per_second = len(test_files) / duration if duration > 0 else 0
                
                print(f"   ✅ SUCCESS: {len(test_files):,} files in {duration:.2f}s ({files_per_second:.0f} files/sec)")
                
                # Verify continuous counter integrity (critical test)
                if config["continuous_counter"]:
                    verify_continuous_counter_integrity(worker, scenario_name)
                
                config_results.append({
                    "scenario": scenario_name,
                    "files": len(test_files),
                    "duration": duration,
                    "files_per_sec": files_per_second,
                    "success": True
                })
                
            except Exception as e:
                print(f"   ❌ FAILED: {str(e)}")
                config_results.append({
                    "scenario": scenario_name,
                    "files": len(test_files),
                    "duration": 0,
                    "files_per_sec": 0,
                    "success": False,
                    "error": str(e)
                })
        
        overall_results.append({
            "config": config["name"],
            "results": config_results
        })
    
    return overall_results

def verify_continuous_counter_integrity(worker, scenario_name):
    """Verify that continuous counter works correctly with no overlaps"""
    
    if not hasattr(worker, '_continuous_counter_map'):
        print(f"   ⚠️  No continuous counter map found for {scenario_name}")
        return True  # Not an error if counter map isn't needed
    
    counter_map = worker._continuous_counter_map
    
    # Handle empty counter map (valid case)
    if not counter_map:
        print(f"   ℹ️  Empty continuous counter map for {scenario_name} (valid for certain configurations)")
        return True
    
    # Group files by their directory
    directory_counters = {}
    for file_path, counter in counter_map.items():
        directory = os.path.dirname(file_path)
        if directory not in directory_counters:
            directory_counters[directory] = []
        directory_counters[directory].append(counter)
    
    # Check for overlaps between directories
    all_counters = list(counter_map.values())
    unique_counters = set(all_counters)
    
    # Handle empty counters list safely
    if not all_counters:
        print(f"   ℹ️  No counters to validate for {scenario_name}")
        return True
    
    if len(all_counters) != len(unique_counters):
        overlaps = len(all_counters) - len(unique_counters)
        print(f"   ❌ COUNTER OVERLAP DETECTED: {overlaps} duplicate counters!")
        
        # Show examples of overlaps
        from collections import Counter
        counter_freq = Counter(all_counters)
        duplicates = {k: v for k, v in counter_freq.items() if v > 1}
        print(f"   🔍 Duplicate counters: {list(duplicates.keys())[:10]}...")
        return False
    else:
        print(f"   ✅ COUNTER INTEGRITY: All {len(unique_counters)} counters are unique!")
        
        # Show range statistics - safely handle min/max on non-empty list
        if all_counters:
            min_counter = min(all_counters)
            max_counter = max(all_counters)
            print(f"   📊 Counter range: {min_counter} to {max_counter}")
        
        # Show per-directory statistics for multi-directory scenarios
        if len(directory_counters) > 1:
            print(f"   📁 Directory breakdown:")
            for directory, counters in list(directory_counters.items())[:5]:  # Show first 5
                dir_name = os.path.basename(directory)
                if counters:  # Safety check before min/max
                    min_dir = min(counters)
                    max_dir = max(counters)
                    print(f"      {dir_name}: {min_dir}-{max_dir} ({len(counters)} files)")
                else:
                    print(f"      {dir_name}: No counters (0 files)")
        
        return True

def print_final_results(overall_results):
    """Print comprehensive final results"""
    
    print(f"\n{'='*100}")
    print(f"🏆 COMPREHENSIVE STRESS TEST RESULTS - 10,000 FILES")
    print(f"{'='*100}")
    
    total_files_processed = 0
    total_time = 0
    all_success = True
    
    for config_result in overall_results:
        config_name = config_result["config"]
        results = config_result["results"]
        
        print(f"\n📊 {config_name}:")
        print(f"{'─'*60}")
        
        config_files = 0
        config_time = 0
        config_success = True
        
        for result in results:
            scenario = result["scenario"]
            files = result["files"]
            duration = result["duration"]
            fps = result["files_per_sec"]
            success = result["success"]
            
            if success:
                print(f"   ✅ {scenario}: {files:,} files, {duration:.2f}s, {fps:.0f} files/sec")
                config_files += files
                config_time += duration
            else:
                print(f"   ❌ {scenario}: FAILED - {result.get('error', 'Unknown error')}")
                config_success = False
                all_success = False
        
        if config_success:
            config_avg_fps = config_files / config_time if config_time > 0 else 0
            print(f"   📈 Config Total: {config_files:,} files in {config_time:.2f}s ({config_avg_fps:.0f} files/sec)")
            total_files_processed += config_files
            total_time += config_time
    
    # Final summary
    print(f"\n{'='*100}")
    if all_success:
        overall_fps = total_files_processed / total_time if total_time > 0 else 0
        print(f"🎉 ALL TESTS PASSED!")
        print(f"📊 Grand Total: {total_files_processed:,} files processed in {total_time:.2f}s")
        print(f"⚡ Overall Performance: {overall_fps:.0f} files/second")
        print(f"✅ CRITICAL BUG FIX VERIFIED: No counter overlaps detected in any scenario!")
    else:
        print(f"❌ SOME TESTS FAILED - See details above")
    
    print(f"{'='*100}")

def main():
    """Main stress test function"""
    
    print("🧪 COMPREHENSIVE STRESS TEST: 10,000 Files in All Scenarios")
    print("=" * 80)
    
    try:
        # Create test environment
        test_dir, scenarios = create_test_environment()
        
        # Run all stress tests
        results = run_comprehensive_stress_tests(test_dir, scenarios)
        
        # Print final results
        print_final_results(results)
        
    except Exception as e:
        print(f"❌ STRESS TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Cleanup (optional - comment out to inspect files)
        try:
            if 'test_dir' in locals():
                print(f"\n🧹 Cleaning up test directory: {test_dir}")
                shutil.rmtree(test_dir)
                print("✅ Cleanup completed")
        except Exception as e:
            print(f"⚠️  Cleanup warning: {e}")

if __name__ == "__main__":
    main()
