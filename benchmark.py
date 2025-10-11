#!/usr/bin/env python3
"""
Comprehensive Benchmark Suite for RenameFiles
Tests performance, safety, and edge cases with baseline comparison
"""

import os
import sys
import time
import shutil
import tempfile
import random
import string
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import List, Dict, Tuple, Optional
import json
from datetime import datetime

# Import modules to test
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'modules'))
from modules.rename_engine import RenameWorkerThread
from modules.exif_processor import get_cached_exif_data, clear_global_exif_cache
from modules.file_utilities import scan_directory_recursive, get_safe_target_path

@dataclass
class BenchmarkResult:
    """Stores benchmark results"""
    scenario: str
    file_count: int
    duration_seconds: float
    memory_mb: float
    success_rate: float
    throughput_files_per_sec: float
    errors_count: int
    warnings_count: int
    errors: List[str]
    warnings: List[str]
    timestamp: str
    version: str  # "baseline" or "optimized"

class BenchmarkSuite:
    """Comprehensive benchmark suite with comparison"""
    
    def __init__(self, output_dir: str = "benchmark_results", version: str = "baseline"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.results: List[BenchmarkResult] = []
        self.test_data_dir = None
        self.version = version  # "baseline" or "optimized"
        
    def setup_test_environment(self):
        """Create temporary test environment"""
        self.test_data_dir = tempfile.mkdtemp(prefix="renamepy_benchmark_")
        print(f"📁 Test environment: {self.test_data_dir}")
        return self.test_data_dir
    
    def cleanup_test_environment(self):
        """Clean up test environment"""
        if self.test_data_dir and os.path.exists(self.test_data_dir):
            shutil.rmtree(self.test_data_dir)
            print(f"🧹 Cleaned up: {self.test_data_dir}")
    
    def generate_test_files(self, count: int, subdirs: int = 0, 
                           file_types: List[str] = None) -> List[str]:
        """Generate dummy test files"""
        if file_types is None:
            file_types = ['.jpg', '.cr2', '.mp4']
        
        files = []
        base_dir = Path(self.test_data_dir)
        
        # Create subdirectories
        dirs = [base_dir]
        if subdirs > 0:
            for i in range(subdirs):
                subdir = base_dir / f"subdir_{i:03d}"
                subdir.mkdir(exist_ok=True)
                dirs.append(subdir)
        
        # Generate files
        for i in range(count):
            # Distribute files across directories
            target_dir = random.choice(dirs)
            ext = random.choice(file_types)
            filename = f"test_{i:06d}{ext}"
            filepath = target_dir / filename
            
            # Create dummy file with minimal content
            filepath.write_bytes(b'DUMMY_CONTENT_' + str(i).encode())
            files.append(str(filepath))
        
        return files
    
    def measure_memory(self) -> float:
        """Measure current memory usage in MB"""
        try:
            import psutil
            process = psutil.Process()
            return process.memory_info().rss / 1024 / 1024  # MB
        except ImportError:
            print("⚠️  psutil not installed - memory measurements will be 0")
            return 0.0
    
    # ========== BENCHMARK SCENARIOS ==========
    
    def benchmark_small_batch(self) -> BenchmarkResult:
        """Scenario 1: Small batch (10-50 files, single directory)"""
        print("\n🔬 Running: Small Batch Test")
        
        files = self.generate_test_files(30, subdirs=0)
        
        mem_before = self.measure_memory()
        start_time = time.time()
        
        worker = RenameWorkerThread(
            files=files,
            camera_prefix="TEST",
            additional="small",
            use_camera=False,
            use_lens=False,
            exif_method=None,
            devider="-",
            exiftool_path=None,
            custom_order=["Date", "Prefix", "Additional", "Number"],
            date_format="YYYY-MM-DD",
            use_date=False,
            continuous_counter=False,
            selected_metadata={},
            sync_exif_date=False
        )
        
        renamed, errors, _ = worker.optimized_rename_files()
        
        duration = time.time() - start_time
        mem_after = self.measure_memory()
        
        success_rate = len(renamed) / len(files) if files else 0
        throughput = len(files) / duration if duration > 0 else 0
        
        return BenchmarkResult(
            scenario="Small Batch (30 files)",
            file_count=len(files),
            duration_seconds=duration,
            memory_mb=mem_after - mem_before,
            success_rate=success_rate,
            throughput_files_per_sec=throughput,
            errors_count=len(errors),
            warnings_count=0,
            errors=errors,
            warnings=[],
            timestamp=datetime.now().isoformat(),
            version=self.version
        )
    
    def benchmark_medium_batch(self) -> BenchmarkResult:
        """Scenario 2: Medium batch (100-500 files, multiple directories)"""
        print("\n🔬 Running: Medium Batch Test")
        
        files = self.generate_test_files(250, subdirs=5)
        
        mem_before = self.measure_memory()
        start_time = time.time()
        
        worker = RenameWorkerThread(
            files=files,
            camera_prefix="CAM",
            additional="medium",
            use_camera=False,
            use_lens=False,
            exif_method=None,
            devider="_",
            exiftool_path=None,
            custom_order=["Prefix", "Date", "Number"],
            date_format="YYYYMMDD",
            use_date=False,
            continuous_counter=True,
            selected_metadata={},
            sync_exif_date=False
        )
        
        renamed, errors, _ = worker.optimized_rename_files()
        
        duration = time.time() - start_time
        mem_after = self.measure_memory()
        
        success_rate = len(renamed) / len(files) if files else 0
        throughput = len(files) / duration if duration > 0 else 0
        
        return BenchmarkResult(
            scenario="Medium Batch (250 files, 5 subdirs)",
            file_count=len(files),
            duration_seconds=duration,
            memory_mb=mem_after - mem_before,
            success_rate=success_rate,
            throughput_files_per_sec=throughput,
            errors_count=len(errors),
            warnings_count=0,
            errors=errors,
            warnings=[],
            timestamp=datetime.now().isoformat(),
            version=self.version
        )
    
    def benchmark_large_batch(self) -> BenchmarkResult:
        """Scenario 3: Large batch (1000+ files, deep directory structure)"""
        print("\n🔬 Running: Large Batch Test")
        
        files = self.generate_test_files(1500, subdirs=20)
        
        mem_before = self.measure_memory()
        start_time = time.time()
        
        worker = RenameWorkerThread(
            files=files,
            camera_prefix="BULK",
            additional="",
            use_camera=False,
            use_lens=False,
            exif_method=None,
            devider="-",
            exiftool_path=None,
            custom_order=["Date", "Number"],
            date_format="YYYY-MM-DD",
            use_date=False,
            continuous_counter=False,
            selected_metadata={},
            sync_exif_date=False
        )
        
        renamed, errors, _ = worker.optimized_rename_files()
        
        duration = time.time() - start_time
        mem_after = self.measure_memory()
        
        success_rate = len(renamed) / len(files) if files else 0
        throughput = len(files) / duration if duration > 0 else 0
        
        return BenchmarkResult(
            scenario="Large Batch (1500 files, 20 subdirs)",
            file_count=len(files),
            duration_seconds=duration,
            memory_mb=mem_after - mem_before,
            success_rate=success_rate,
            throughput_files_per_sec=throughput,
            errors_count=len(errors),
            warnings_count=0,
            errors=errors,
            warnings=[],
            timestamp=datetime.now().isoformat(),
            version=self.version
        )
    
    def benchmark_mixed_file_types(self) -> BenchmarkResult:
        """Scenario 4: Mixed file types (RAW, JPG, Video)"""
        print("\n🔬 Running: Mixed File Types Test")
        
        file_types = ['.jpg', '.cr2', '.nef', '.arw', '.mp4', '.mov', '.dng']
        files = self.generate_test_files(200, subdirs=3, file_types=file_types)
        
        mem_before = self.measure_memory()
        start_time = time.time()
        
        worker = RenameWorkerThread(
            files=files,
            camera_prefix="MIXED",
            additional="types",
            use_camera=False,
            use_lens=False,
            exif_method=None,
            devider="_",
            exiftool_path=None,
            custom_order=["Prefix", "Additional", "Number"],
            date_format="YYYY-MM-DD",
            use_date=False,
            continuous_counter=False,
            selected_metadata={},
            sync_exif_date=False
        )
        
        renamed, errors, _ = worker.optimized_rename_files()
        
        duration = time.time() - start_time
        mem_after = self.measure_memory()
        
        success_rate = len(renamed) / len(files) if files else 0
        throughput = len(files) / duration if duration > 0 else 0
        
        return BenchmarkResult(
            scenario="Mixed File Types (200 files, 7 types)",
            file_count=len(files),
            duration_seconds=duration,
            memory_mb=mem_after - mem_before,
            success_rate=success_rate,
            throughput_files_per_sec=throughput,
            errors_count=len(errors),
            warnings_count=0,
            errors=errors,
            warnings=[],
            timestamp=datetime.now().isoformat(),
            version=self.version
        )
    
    def benchmark_edge_case_names(self) -> BenchmarkResult:
        """Scenario 5: Edge case filenames (special chars, long names, unicode)"""
        print("\n🔬 Running: Edge Case Filenames Test")
        
        # Create files with problematic names
        base_dir = Path(self.test_data_dir)
        edge_case_files = []
        
        test_names = [
            "normal_file.jpg",
            "file with spaces.jpg",
            "file-with-dashes.jpg",
            "file_with_underscores.jpg",
            "UPPERCASE.JPG",
            "MixedCase.Jpg",
            "123_numeric_start.jpg",
            "special!@#$%chars.jpg",  # Will be sanitized
            "very_" + ("long_" * 30) + "filename.jpg",  # Long name
            "unicode_文件名.jpg",  # Unicode
            "dots.in.middle.jpg",
            "trailing_dot.jpg.",  # Problematic
            " leading_space.jpg",  # Problematic
            "multiple___underscores.jpg",
        ]
        
        for i, name in enumerate(test_names):
            filepath = base_dir / name
            try:
                filepath.write_bytes(b'EDGE_CASE_' + str(i).encode())
                edge_case_files.append(str(filepath))
            except:
                # Some names might fail to create
                pass
        
        mem_before = self.measure_memory()
        start_time = time.time()
        
        worker = RenameWorkerThread(
            files=edge_case_files,
            camera_prefix="EDGE",
            additional="test",
            use_camera=False,
            use_lens=False,
            exif_method=None,
            devider="-",
            exiftool_path=None,
            custom_order=["Prefix", "Number"],
            date_format="YYYY-MM-DD",
            use_date=False,
            continuous_counter=False,
            selected_metadata={},
            sync_exif_date=False
        )
        
        renamed, errors, _ = worker.optimized_rename_files()
        
        duration = time.time() - start_time
        mem_after = self.measure_memory()
        
        success_rate = len(renamed) / len(edge_case_files) if edge_case_files else 0
        throughput = len(edge_case_files) / duration if duration > 0 else 0
        
        warnings = []
        if success_rate < 1.0:
            warnings.append(f"Only {success_rate*100:.1f}% success rate with edge cases")
        
        return BenchmarkResult(
            scenario="Edge Case Filenames",
            file_count=len(edge_case_files),
            duration_seconds=duration,
            memory_mb=mem_after - mem_before,
            success_rate=success_rate,
            throughput_files_per_sec=throughput,
            errors_count=len(errors),
            warnings_count=len(warnings),
            errors=errors,
            warnings=warnings,
            timestamp=datetime.now().isoformat(),
            version=self.version
        )
    
    def benchmark_cache_stress_test(self) -> BenchmarkResult:
        """Scenario 6: EXIF Cache stress test (simulated repeated access)"""
        print("\n🔬 Running: EXIF Cache Stress Test")
        
        files = self.generate_test_files(500, subdirs=10)
        
        # Clear cache before test
        clear_global_exif_cache()
        
        mem_before = self.measure_memory()
        start_time = time.time()
        
        # Simulate repeated EXIF access to test cache
        cache_accesses = 0
        
        for _ in range(3):  # 3 passes over the same files
            for file in files:
                # Note: Without real EXIF data, this tests cache infrastructure
                result = get_cached_exif_data(file, None, None)
                cache_accesses += 1
        
        duration = time.time() - start_time
        mem_after = self.measure_memory()
        
        # Measure cache memory
        cache_memory = mem_after - mem_before
        
        # Clear cache and measure memory drop
        clear_global_exif_cache()
        mem_after_clear = self.measure_memory()
        
        warnings = []
        if cache_memory > 100:  # More than 100MB for 500 files
            warnings.append(f"Excessive cache memory: {cache_memory:.1f} MB")
        
        return BenchmarkResult(
            scenario=f"EXIF Cache Stress (500 files × 3 passes)",
            file_count=len(files),
            duration_seconds=duration,
            memory_mb=cache_memory,
            success_rate=1.0,
            throughput_files_per_sec=cache_accesses / duration if duration > 0 else 0,
            errors_count=0,
            warnings_count=len(warnings),
            errors=[],
            warnings=warnings,
            timestamp=datetime.now().isoformat(),
            version=self.version
        )
    
    def benchmark_directory_scan_performance(self) -> BenchmarkResult:
        """Scenario 7: Directory scanning performance (deep nesting)"""
        print("\n🔬 Running: Directory Scan Performance Test")
        
        # Create deep directory structure
        base_dir = Path(self.test_data_dir)
        files_created = []
        
        # Create nested structure: 5 levels, 5 dirs per level
        def create_nested(parent, depth, max_depth=5):
            if depth >= max_depth:
                return
            
            for i in range(5):
                subdir = parent / f"level{depth}_dir{i}"
                subdir.mkdir(exist_ok=True)
                
                # Add 10 files per directory
                for j in range(10):
                    filepath = subdir / f"file_{j}.jpg"
                    filepath.write_bytes(b'NESTED_' + str(j).encode())
                    files_created.append(str(filepath))
                
                # Recurse
                create_nested(subdir, depth + 1, max_depth)
        
        create_nested(base_dir, 0, max_depth=4)  # 4 levels deep
        
        mem_before = self.measure_memory()
        start_time = time.time()
        
        # Scan directory recursively
        scanned_files = scan_directory_recursive(str(base_dir))
        
        duration = time.time() - start_time
        mem_after = self.measure_memory()
        
        success_rate = len(scanned_files) / len(files_created) if files_created else 0
        throughput = len(scanned_files) / duration if duration > 0 else 0
        
        warnings = []
        if success_rate < 1.0:
            warnings.append(f"Scan found only {len(scanned_files)}/{len(files_created)} files")
        
        return BenchmarkResult(
            scenario=f"Deep Directory Scan (4 levels, {len(files_created)} files)",
            file_count=len(scanned_files),
            duration_seconds=duration,
            memory_mb=mem_after - mem_before,
            success_rate=success_rate,
            throughput_files_per_sec=throughput,
            errors_count=0,
            warnings_count=len(warnings),
            errors=[],
            warnings=warnings,
            timestamp=datetime.now().isoformat(),
            version=self.version
        )
    
    # ========== REPORTING ==========
    
    def generate_report(self):
        """Generate comprehensive report"""
        print("\n" + "="*80)
        print(f"📊 BENCHMARK RESULTS SUMMARY - {self.version.upper()}")
        print("="*80)
        
        for result in self.results:
            print(f"\n{result.scenario}")
            print(f"  Files:        {result.file_count}")
            print(f"  Duration:     {result.duration_seconds:.3f}s")
            print(f"  Memory:       {result.memory_mb:.1f} MB")
            print(f"  Success Rate: {result.success_rate*100:.1f}%")
            print(f"  Throughput:   {result.throughput_files_per_sec:.1f} files/sec")
            
            if result.errors_count > 0:
                print(f"  ⚠️  Errors: {result.errors_count}")
                for error in result.errors[:3]:  # Show first 3
                    print(f"      - {error}")
            
            if result.warnings_count > 0:
                print(f"  ⚡ Warnings:")
                for warning in result.warnings:
                    print(f"      - {warning}")
        
        # Save JSON report
        report_file = self.output_dir / f"benchmark_{self.version}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        report_data = {
            "version": self.version,
            "timestamp": datetime.now().isoformat(),
            "results": [asdict(r) for r in self.results]
        }
        
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 Report saved to: {report_file}")
        
        return report_file
    
    def run_all_benchmarks(self):
        """Run all benchmark scenarios"""
        print(f"🚀 Starting RenameFiles Benchmark Suite - {self.version.upper()}")
        print("="*80)
        
        try:
            self.setup_test_environment()
            
            # Run all scenarios
            self.results.append(self.benchmark_small_batch())
            self.results.append(self.benchmark_medium_batch())
            self.results.append(self.benchmark_large_batch())
            self.results.append(self.benchmark_mixed_file_types())
            self.results.append(self.benchmark_edge_case_names())
            self.results.append(self.benchmark_cache_stress_test())
            self.results.append(self.benchmark_directory_scan_performance())
            
            # Generate report
            report_file = self.generate_report()
            
            return report_file
            
        finally:
            self.cleanup_test_environment()
        
        print("\n✅ Benchmark suite completed!")


class BenchmarkComparator:
    """Compare baseline and optimized benchmark results"""
    
    def __init__(self, baseline_file: str, optimized_file: str):
        self.baseline_file = Path(baseline_file)
        self.optimized_file = Path(optimized_file)
        
        with open(self.baseline_file, 'r', encoding='utf-8') as f:
            self.baseline_data = json.load(f)
        
        with open(self.optimized_file, 'r', encoding='utf-8') as f:
            self.optimized_data = json.load(f)
    
    def calculate_improvement(self, baseline_val: float, optimized_val: float, 
                            lower_is_better: bool = True) -> Tuple[float, str]:
        """Calculate improvement percentage"""
        if baseline_val == 0:
            return 0.0, "N/A"
        
        if lower_is_better:
            improvement = ((baseline_val - optimized_val) / baseline_val) * 100
        else:
            improvement = ((optimized_val - baseline_val) / baseline_val) * 100
        
        if improvement > 0:
            symbol = "🟢" if improvement > 10 else "🟡"
        elif improvement < 0:
            symbol = "🔴"
        else:
            symbol = "⚪"
        
        return improvement, symbol
    
    def compare_results(self):
        """Generate comparison report"""
        print("\n" + "="*80)
        print("📈 BENCHMARK COMPARISON: BASELINE vs OPTIMIZED")
        print("="*80)
        
        baseline_results = self.baseline_data['results']
        optimized_results = self.optimized_data['results']
        
        # Match results by scenario
        for i, baseline in enumerate(baseline_results):
            if i >= len(optimized_results):
                break
            
            optimized = optimized_results[i]
            scenario = baseline['scenario']
            
            print(f"\n{'─'*80}")
            print(f"📊 {scenario}")
            print(f"{'─'*80}")
            
            # Duration comparison
            dur_improve, dur_symbol = self.calculate_improvement(
                baseline['duration_seconds'], 
                optimized['duration_seconds'], 
                lower_is_better=True
            )
            print(f"\n⏱️  Duration:")
            print(f"  Baseline:  {baseline['duration_seconds']:.3f}s")
            print(f"  Optimized: {optimized['duration_seconds']:.3f}s")
            print(f"  {dur_symbol} Improvement: {dur_improve:+.1f}%")
            
            # Throughput comparison
            tp_improve, tp_symbol = self.calculate_improvement(
                baseline['throughput_files_per_sec'], 
                optimized['throughput_files_per_sec'], 
                lower_is_better=False
            )
            print(f"\n🚀 Throughput:")
            print(f"  Baseline:  {baseline['throughput_files_per_sec']:.1f} files/sec")
            print(f"  Optimized: {optimized['throughput_files_per_sec']:.1f} files/sec")
            print(f"  {tp_symbol} Improvement: {tp_improve:+.1f}%")
            
            # Memory comparison
            mem_improve, mem_symbol = self.calculate_improvement(
                baseline['memory_mb'], 
                optimized['memory_mb'], 
                lower_is_better=True
            )
            print(f"\n💾 Memory Usage:")
            print(f"  Baseline:  {baseline['memory_mb']:.1f} MB")
            print(f"  Optimized: {optimized['memory_mb']:.1f} MB")
            print(f"  {mem_symbol} Improvement: {mem_improve:+.1f}%")
            
            # Success rate comparison
            sr_improve, sr_symbol = self.calculate_improvement(
                baseline['success_rate'], 
                optimized['success_rate'], 
                lower_is_better=False
            )
            print(f"\n✅ Success Rate:")
            print(f"  Baseline:  {baseline['success_rate']*100:.1f}%")
            print(f"  Optimized: {optimized['success_rate']*100:.1f}%")
            print(f"  {sr_symbol} Change: {sr_improve:+.1f}%")
            
            # Errors comparison
            if baseline['errors_count'] > 0 or optimized['errors_count'] > 0:
                print(f"\n⚠️  Errors:")
                print(f"  Baseline:  {baseline['errors_count']}")
                print(f"  Optimized: {optimized['errors_count']}")
        
        print("\n" + "="*80)
        print("📊 OVERALL SUMMARY")
        print("="*80)
        
        # Calculate overall improvements
        total_baseline_time = sum(r['duration_seconds'] for r in baseline_results)
        total_optimized_time = sum(r['duration_seconds'] for r in optimized_results)
        overall_time_improve, _ = self.calculate_improvement(
            total_baseline_time, total_optimized_time, lower_is_better=True
        )
        
        total_baseline_mem = sum(r['memory_mb'] for r in baseline_results)
        total_optimized_mem = sum(r['memory_mb'] for r in optimized_results)
        overall_mem_improve, _ = self.calculate_improvement(
            total_baseline_mem, total_optimized_mem, lower_is_better=True
        )
        
        print(f"\n⏱️  Total Time Improvement: {overall_time_improve:+.1f}%")
        print(f"   ({total_baseline_time:.3f}s → {total_optimized_time:.3f}s)")
        
        print(f"\n💾 Total Memory Improvement: {overall_mem_improve:+.1f}%")
        print(f"   ({total_baseline_mem:.1f} MB → {total_optimized_mem:.1f} MB)")
        
        # Save comparison report
        output_dir = Path("benchmark_results")
        comparison_file = output_dir / f"comparison_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        comparison_data = {
            "timestamp": datetime.now().isoformat(),
            "baseline_file": str(self.baseline_file),
            "optimized_file": str(self.optimized_file),
            "overall_improvements": {
                "time_improvement_percent": overall_time_improve,
                "memory_improvement_percent": overall_mem_improve,
                "total_baseline_time": total_baseline_time,
                "total_optimized_time": total_optimized_time,
                "total_baseline_memory": total_baseline_mem,
                "total_optimized_memory": total_optimized_mem
            },
            "detailed_comparisons": []
        }
        
        for i, baseline in enumerate(baseline_results):
            if i >= len(optimized_results):
                break
            optimized = optimized_results[i]
            
            dur_improve, _ = self.calculate_improvement(
                baseline['duration_seconds'], optimized['duration_seconds'], True
            )
            mem_improve, _ = self.calculate_improvement(
                baseline['memory_mb'], optimized['memory_mb'], True
            )
            tp_improve, _ = self.calculate_improvement(
                baseline['throughput_files_per_sec'], optimized['throughput_files_per_sec'], False
            )
            
            comparison_data["detailed_comparisons"].append({
                "scenario": baseline['scenario'],
                "baseline": baseline,
                "optimized": optimized,
                "improvements": {
                    "duration_percent": dur_improve,
                    "memory_percent": mem_improve,
                    "throughput_percent": tp_improve
                }
            })
        
        with open(comparison_file, 'w', encoding='utf-8') as f:
            json.dump(comparison_data, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 Comparison saved to: {comparison_file}")
        print("\n" + "="*80)


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="RenameFiles Benchmark Suite")
    parser.add_argument('--version', choices=['baseline', 'optimized'], default='baseline',
                       help='Version to benchmark (default: baseline)')
    parser.add_argument('--compare', nargs=2, metavar=('BASELINE', 'OPTIMIZED'),
                       help='Compare two benchmark result files')
    
    args = parser.parse_args()
    
    if args.compare:
        # Compare mode
        baseline_file, optimized_file = args.compare
        comparator = BenchmarkComparator(baseline_file, optimized_file)
        comparator.compare_results()
    else:
        # Benchmark mode
        suite = BenchmarkSuite(version=args.version)
        report_file = suite.run_all_benchmarks()
        
        print(f"\n✅ Benchmark completed! Report: {report_file}")
        print(f"\n💡 To compare with optimized version later, run:")
        print(f"   python benchmark.py --version optimized")
        print(f"   python benchmark.py --compare {report_file} <optimized_report>")


if __name__ == "__main__":
    main()