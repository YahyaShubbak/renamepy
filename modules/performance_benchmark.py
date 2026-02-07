"""
Performance Benchmark Module for Adaptive Time Estimation.

This module provides automatic background benchmarking to estimate rename operation
times based on the user's system performance and pattern complexity.
"""
from __future__ import annotations

import os
import time
import tempfile
import shutil
import re
import json
from typing import Optional
from dataclasses import dataclass
from PyQt6.QtCore import QThread, pyqtSignal

from .logger_util import get_logger

logger = get_logger(__name__)

# Safety factor calibration
DEFAULT_SAFETY_FACTOR = 2.0
_project_root = os.path.realpath(os.path.join(os.path.dirname(__file__), '..'))
SAFETY_FACTOR_FILE = os.path.join(_project_root, '.benchmark_calibration.json')

# EXIF field patterns that may appear in filename patterns
EXIF_FIELD_PATTERNS = [
    r'\{camera\}', r'\{lens\}', r'\{iso\}', r'\{aperture\}',
    r'\{focal_?length\}', r'\{shutter(?:_speed)?\}', r'\{resolution\}',
    r'\{date\}', r'\{time\}'
]


def analyze_pattern_complexity(
    use_date: bool = False,
    use_camera: bool = False,
    use_lens: bool = False,
    additional_text: str = "",
    camera_prefix: str = "",
    selected_metadata: dict = None
) -> tuple[int, int]:
    """
    Analyze the complexity of the current renaming pattern.
    
    Args:
        use_date: Whether date is used
        use_camera: Whether camera model is used
        use_lens: Whether lens model is used
        additional_text: Additional text field content
        camera_prefix: Camera prefix field content
        selected_metadata: Dictionary of selected metadata fields (e.g., {'iso': True, 'aperture': True})
        
    Returns:
        Tuple of (exif_field_count, text_field_count)
    """
    exif_count = 0
    text_count = 0
    
    # Count EXIF fields
    if use_date:
        exif_count += 1
    if use_camera:
        exif_count += 1
    if use_lens:
        exif_count += 1
        
    # Count selected metadata fields
    if selected_metadata:
        for key, value in selected_metadata.items():
            if value is True:  # Boolean True means field is selected
                exif_count += 1
    
    # Count text fields
    if additional_text and additional_text.strip():
        text_count += 1
    if camera_prefix and camera_prefix.strip():
        text_count += 1
    
    return exif_count, text_count


@dataclass
class BenchmarkResult:
    """Results from a performance benchmark run."""
    exif_field_count: int
    text_field_count: int
    file_count: int
    total_time: float
    per_file_time: float
    with_exif_save: bool


class PerformanceBenchmark:
    """Manages performance benchmarking for rename operations."""
    
    def __init__(self, exiftool_path: Optional[str] = None):
        """
        Initialize the benchmark manager.
        
        Args:
            exiftool_path: Path to ExifTool executable
        """
        self.exiftool_path = exiftool_path
        self.benchmark_results: dict[str, BenchmarkResult] = {}
        self._benchmark_complete = False
        self.safety_factor = self._load_safety_factor()
        
    def run_benchmark(self, sample_files: list[str], max_samples: int = 10) -> None:
        """
        Run background benchmark with sample files.
        
        Tests different scenarios:
        - 0 EXIF fields (text only)
        - 1 EXIF field + text
        - 2 EXIF fields + text
        - 3 EXIF fields + text
        - 4 EXIF fields + text
        
        Args:
            sample_files: List of image files to use for benchmarking
            max_samples: Maximum number of file pairs to test (default: 10)
        """
        if not sample_files:
            logger.warning("No sample files provided for benchmarking")
            return
            
        # Limit sample size
        samples = sample_files[:min(max_samples, len(sample_files))]
        logger.info(f"Starting performance benchmark with {len(samples)} files")
        
        # Create temporary directory for benchmark
        temp_dir = tempfile.mkdtemp(prefix="renamepy_benchmark_")
        
        try:
            # Note: We DON'T pre-extract EXIF here - the benchmark will call ExifTool
            # during timing to measure realistic performance
            # Each scenario creates its own ExifTool instance to avoid blocking the main GUI
            
            # Validate that sample files exist
            valid_samples = [f for f in samples if os.path.exists(f)]
            if not valid_samples:
                logger.warning("No valid sample files for benchmarking")
                return
            
            samples = valid_samples
            
            # Test scenarios
            scenarios = [
                (0, 2, False),  # Text only
                (1, 1, False),  # 1 EXIF + 1 text
                (2, 1, False),  # 2 EXIF + 1 text
                (3, 1, False),  # 3 EXIF + 1 text
                (4, 1, False),  # 4 EXIF + 1 text
                (2, 1, True),   # 2 EXIF + 1 text + EXIF save
            ]
            
            logger.info(f"Starting {len(scenarios)} benchmark scenarios...")
            
            for i, (exif_count, text_count, with_exif_save) in enumerate(scenarios, 1):
                logger.info(f"Running scenario {i}/{len(scenarios)}: {exif_count} EXIF, {text_count} text, EXIF save={with_exif_save}")
                
                result = self._benchmark_scenario(
                    samples=samples,
                    temp_dir=temp_dir,
                    exif_field_count=exif_count,
                    text_field_count=text_count,
                    with_exif_save=with_exif_save
                )
                
                if result:
                    key = self._get_benchmark_key(exif_count, text_count, with_exif_save)
                    self.benchmark_results[key] = result
                    logger.info(f"Scenario {i} completed: {key} -> {result.per_file_time*1000:.1f}ms per file")
                else:
                    logger.warning(f"Scenario {i} failed to produce results")
            
            self._benchmark_complete = True
            logger.info(f"Performance benchmark completed successfully with {len(self.benchmark_results)} results")
            
        except Exception as e:
            logger.error(f"Benchmark failed: {e}")
        finally:
            # Cleanup temporary directory
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception as e:
                logger.debug(f"Could not remove temp benchmark dir: {e}")
    
    def _benchmark_scenario(
        self,
        samples: list[str],
        temp_dir: str,
        exif_field_count: int,
        text_field_count: int,
        with_exif_save: bool
    ) -> Optional[BenchmarkResult]:
        """
        Benchmark a specific scenario with real ExifTool calls.
        
        Args:
            samples: List of sample files
            temp_dir: Temporary directory for test files
            exif_field_count: Number of EXIF fields to simulate
            text_field_count: Number of text fields to simulate
            with_exif_save: Whether to include EXIF save operation
            
        Returns:
            BenchmarkResult if successful, None otherwise
        """
        try:
            # PERF 3: Use hard links instead of full copies when possible.
            # Hard links are instant (no I/O) and ExifTool can still read
            # EXIF from them.  Only fall back to copy2 when EXIF writes are
            # needed (writes modify the file data) or when linking fails
            # (e.g., cross-volume).
            test_files = []
            for i, src in enumerate(samples):
                ext = os.path.splitext(src)[1]
                dst = os.path.join(temp_dir, f"test_{i}{ext}")
                if with_exif_save:
                    # Must copy — EXIF write would alter the original via link
                    shutil.copy2(src, dst)
                else:
                    try:
                        os.link(src, dst)
                    except (OSError, NotImplementedError):
                        shutil.copy2(src, dst)
                test_files.append(dst)
            
            # Simulate rename with pattern complexity - using REAL ExifTool calls
            start_time = time.perf_counter()
            
            renamed_files = []
            for test_file in test_files:
                # REAL EXIF extraction (not cached!) - this is what takes time
                if exif_field_count > 0 and self.exiftool_path:
                    from .exif_processor import get_exiftool_metadata_shared
                    # This is the expensive operation - actual ExifTool call
                    exif_data = get_exiftool_metadata_shared(test_file, self.exiftool_path)
                    if exif_data and isinstance(exif_data, dict):
                        # Access different EXIF fields (already extracted)
                        _ = exif_data.get('EXIF:DateTimeOriginal')
                        if exif_field_count > 1:
                            _ = exif_data.get('EXIF:ISO')
                        if exif_field_count > 2:
                            _ = exif_data.get('EXIF:FocalLength')
                        if exif_field_count > 3:
                            _ = exif_data.get('EXIF:LensModel')
                
                # Simulate text field processing
                for _ in range(text_field_count):
                    _ = "TestText"  # Simulate string operations
                
                # Simulate EXIF save if enabled
                if with_exif_save and self.exiftool_path:
                    from .exif_undo_manager import write_original_filename_to_exif
                    original_name = os.path.basename(test_file)
                    write_original_filename_to_exif(test_file, original_name, self.exiftool_path)
                
                # Simulate actual rename with unique name to avoid conflicts
                timestamp = int(time.time() * 1000000)  # Microsecond timestamp
                new_name = os.path.join(
                    temp_dir,
                    f"renamed_{timestamp}_{os.path.basename(test_file)}"
                )
                shutil.move(test_file, new_name)
                renamed_files.append(new_name)
            
            elapsed_time = time.perf_counter() - start_time
            per_file_time = elapsed_time / len(renamed_files)
            
            return BenchmarkResult(
                exif_field_count=exif_field_count,
                text_field_count=text_field_count,
                file_count=len(renamed_files),
                total_time=elapsed_time,
                per_file_time=per_file_time,
                with_exif_save=with_exif_save
            )
            
        except Exception as e:
            logger.debug(f"Scenario benchmark failed: {e}")
            return None
    
    def estimate_time(
        self,
        file_count: int,
        exif_field_count: int,
        text_field_count: int,
        with_exif_save: bool
    ) -> tuple[float, float]:
        """
        Estimate operation time based on benchmark results.
        
        Args:
            file_count: Number of files to process
            exif_field_count: Number of EXIF fields in pattern
            text_field_count: Number of text fields in pattern
            with_exif_save: Whether EXIF save is enabled
            
        Returns:
            Tuple of (estimated_time, confidence) in seconds
            confidence is 0.0-1.0, where 1.0 means exact benchmark match
        """
        if not self._benchmark_complete or not self.benchmark_results:
            # No benchmark data - use conservative defaults
            base_time = 0.03 * file_count  # 30ms per file
            exif_time = exif_field_count * 0.01 * file_count  # 10ms per EXIF field
            exif_save_time = 0.1 * file_count if with_exif_save else 0
            return base_time + exif_time + exif_save_time, 0.3
        
        # Use adaptive safety factor (calibrated based on actual rename operations)
        # Starts at 2.0, adjusts automatically based on real-world performance
        # Accounts for GUI updates, logging, disk I/O overhead
        
        # Try to find exact match
        key = self._get_benchmark_key(exif_field_count, text_field_count, with_exif_save)
        if key in self.benchmark_results:
            result = self.benchmark_results[key]
            estimated = result.per_file_time * file_count * self.safety_factor
            return estimated, 1.0
        
        # Find closest match
        closest_key = None
        min_diff = float('inf')
        
        for bm_key, result in self.benchmark_results.items():
            if result.with_exif_save != with_exif_save:
                continue
                
            diff = abs(result.exif_field_count - exif_field_count)
            if diff < min_diff:
                min_diff = diff
                closest_key = bm_key
        
        if closest_key:
            result = self.benchmark_results[closest_key]
            # Adjust for difference in EXIF field count
            adjustment = (exif_field_count - result.exif_field_count) * 0.01
            estimated_per_file = result.per_file_time + adjustment
            confidence = 0.7 if min_diff <= 1 else 0.5
            estimated = estimated_per_file * file_count * self.safety_factor
            return estimated, confidence
        
        # Fallback to defaults (already conservative, no safety factor needed)
        return 0.10 * file_count, 0.2
    
    @staticmethod
    def _get_benchmark_key(exif_count: int, text_count: int, with_exif_save: bool) -> str:
        """Generate unique key for benchmark scenario."""
        save_suffix = "_exifsave" if with_exif_save else ""
        return f"exif{exif_count}_text{text_count}{save_suffix}"
    
    def is_ready(self) -> bool:
        """Check if benchmark is complete and ready for estimates."""
        return self._benchmark_complete and bool(self.benchmark_results)
    
    def _load_safety_factor(self) -> float:
        """Load calibrated safety factor from file, or return default."""
        try:
            real_path = os.path.realpath(SAFETY_FACTOR_FILE)
            if not real_path.startswith(_project_root):
                logger.warning("Safety factor file path outside project — ignoring")
                return DEFAULT_SAFETY_FACTOR
            if os.path.exists(real_path):
                with open(real_path, 'r') as f:
                    data = json.load(f)
                    factor = data.get('safety_factor', DEFAULT_SAFETY_FACTOR)
                    # Clamp to sane range even on load
                    factor = max(1.0, min(5.0, float(factor)))
                    logger.info(f"Loaded calibrated safety factor: {factor:.2f}")
                    return factor
        except (json.JSONDecodeError, ValueError, TypeError) as e:
            logger.warning(f"Corrupt safety factor file, using default: {e}")
        except Exception as e:
            logger.debug(f"Could not load safety factor: {e}")
        return DEFAULT_SAFETY_FACTOR
    
    def _save_safety_factor(self):
        """Save calibrated safety factor to file."""
        try:
            real_path = os.path.realpath(SAFETY_FACTOR_FILE)
            if not real_path.startswith(_project_root):
                logger.warning("Safety factor file path outside project — not saving")
                return
            data = {
                'safety_factor': round(self.safety_factor, 4),
                'last_updated': time.time()
            }
            # Write atomically via temp file to avoid corruption on crash
            tmp_path = real_path + '.tmp'
            with open(tmp_path, 'w') as f:
                json.dump(data, f, indent=2)
            os.replace(tmp_path, real_path)
            logger.info(f"Saved calibrated safety factor: {self.safety_factor:.2f}")
        except Exception as e:
            logger.debug(f"Could not save safety factor: {e}")
    
    def calibrate_from_actual(
        self,
        estimated_time: float,
        actual_time: float,
        file_count: int,
        exif_field_count: int,
        text_field_count: int,
        with_exif_save: bool
    ):
        """
        Calibrate safety factor based on actual rename operation time.
        
        This adaptively adjusts the safety factor to improve future estimates
        based on real-world performance data.
        
        Args:
            estimated_time: The time we estimated (in seconds)
            actual_time: The actual time the operation took (in seconds)
            file_count: Number of files that were renamed
            exif_field_count: Number of EXIF fields used
            text_field_count: Number of text fields used
            with_exif_save: Whether EXIF save was enabled
        """
        if not self.is_ready():
            logger.debug("Cannot calibrate - benchmark not complete")
            return
        
        # Find the benchmark result that was used for this estimate
        key = self._get_benchmark_key(exif_field_count, text_field_count, with_exif_save)
        if key not in self.benchmark_results:
            logger.debug(f"Cannot calibrate - no benchmark for key {key}")
            return
        
        result = self.benchmark_results[key]
        benchmark_time = result.per_file_time * file_count
        
        # Calculate what the safety factor SHOULD have been
        ideal_factor = actual_time / benchmark_time if benchmark_time > 0 else DEFAULT_SAFETY_FACTOR
        
        # Use exponential moving average to smooth out fluctuations
        # Weight: 30% new measurement, 70% existing factor
        ALPHA = 0.3
        old_factor = self.safety_factor
        self.safety_factor = ALPHA * ideal_factor + (1 - ALPHA) * old_factor
        
        # Clamp to reasonable bounds (1.2 to 3.5)
        self.safety_factor = max(1.2, min(3.5, self.safety_factor))
        
        logger.info(
            f"Calibration: estimated={estimated_time:.1f}s, actual={actual_time:.1f}s, "
            f"ideal_factor={ideal_factor:.2f}, old_factor={old_factor:.2f}, new_factor={self.safety_factor:.2f}"
        )
        
        # Save to disk
        self._save_safety_factor()


class BenchmarkThread(QThread):
    """Background thread for running performance benchmarks."""
    
    benchmark_complete = pyqtSignal(dict)  # Emits benchmark results
    progress_update = pyqtSignal(str, int)  # Emits (message, percentage)
    
    def __init__(
        self,
        sample_files: list[str],
        exiftool_path: Optional[str] = None,
        max_samples: int = 10
    ):
        """
        Initialize benchmark thread.
        
        Args:
            sample_files: Files to use for benchmarking
            exiftool_path: Path to ExifTool executable
            max_samples: Maximum number of samples to test
        """
        super().__init__()
        self.sample_files = sample_files
        self.exiftool_path = exiftool_path
        self.max_samples = max_samples
    
    def run(self) -> None:
        """Run benchmark in background thread."""
        try:
            logger.info("BenchmarkThread: Starting background benchmark")
            self.progress_update.emit("Initializing benchmark...", 0)
            
            benchmark = PerformanceBenchmark(self.exiftool_path)
            
            # Calculate total scenarios
            total_scenarios = 6
            completed = 0
            
            # Override run_benchmark to emit progress
            original_benchmark_scenario = benchmark._benchmark_scenario
            
            def progress_wrapper(*args, **kwargs):
                nonlocal completed
                result = original_benchmark_scenario(*args, **kwargs)
                completed += 1
                progress = int((completed / total_scenarios) * 100)
                self.progress_update.emit(f"Testing scenario {completed}/{total_scenarios}...", progress)
                return result
            
            benchmark._benchmark_scenario = progress_wrapper
            
            logger.info(f"BenchmarkThread: Running benchmark with {len(self.sample_files)} sample files")
            benchmark.run_benchmark(self.sample_files, self.max_samples)
            
            self.progress_update.emit("Benchmark complete!", 100)
            logger.info(f"BenchmarkThread: Benchmark finished with {len(benchmark.benchmark_results)} scenarios")
            
            self.benchmark_complete.emit(benchmark.benchmark_results)
        except Exception as e:
            logger.error(f"BenchmarkThread: Benchmark thread failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
            self.benchmark_complete.emit({})
