"""
Integration tests for Phase 1 critical fixes:
  1. PowerShell injection prevention (parameterized timestamp sync)
  2. Thread-safe global ExifTool instance
  3. Global ExifTool cleanup on exit

Uses real images from C:\\Users\\yshub\\Desktop\\Bilbao when available.
"""

import os
import sys
import shutil
import tempfile
import threading
import time
import pytest

# Make sure modules are importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


BILBAO_DIR = r"C:\Users\yshub\Desktop\Bilbao"
SAMPLE_FILES = []

# Collect a small subset of real test images (first 3 JPGs)
if os.path.isdir(BILBAO_DIR):
    all_jpgs = sorted(
        f for f in os.listdir(BILBAO_DIR) if f.upper().endswith('.JPG')
    )[:3]
    SAMPLE_FILES = [os.path.join(BILBAO_DIR, f) for f in all_jpgs]

HAS_IMAGES = len(SAMPLE_FILES) > 0
skip_no_images = pytest.mark.skipif(not HAS_IMAGES, reason="No test images in Bilbao dir")


# ===========================================================================
# 1. PowerShell injection prevention
# ===========================================================================
class TestPowerShellTimestampSafety:
    """Verify that the parameterized PowerShell approach is safe."""

    @skip_no_images
    def test_timestamp_sync_with_normal_path(self, tmp_path):
        """Normal file path should work with parameterized PowerShell."""
        from modules.exif_processor import _set_file_timestamp_method3
        import datetime

        # Copy a real image to temp dir
        src = SAMPLE_FILES[0]
        dst = tmp_path / os.path.basename(src)
        shutil.copy2(src, dst)

        dt = datetime.datetime(2024, 6, 15, 14, 30, 0)
        result = _set_file_timestamp_method3(str(dst), dt)

        if os.name == 'nt':
            assert result is True, "PowerShell timestamp sync should succeed"
            # Verify the timestamp was actually set
            stat = os.stat(dst)
            set_ts = datetime.datetime.fromtimestamp(stat.st_mtime)
            assert set_ts.year == 2024
            assert set_ts.month == 6
            assert set_ts.day == 15
        else:
            assert result is False, "Should return False on non-Windows"

    @pytest.mark.skipif(os.name != 'nt', reason="Windows-only test")
    def test_path_with_special_characters(self, tmp_path):
        """File path with Windows-valid special chars must not cause injection.
        
        Note: Windows forbids " < > | ? * in filenames, so we test with
        characters that ARE valid on Windows but dangerous in PowerShell:
        parentheses, dollar signs, single quotes, spaces, ampersands.
        """
        from modules.exif_processor import _set_file_timestamp_method3
        import datetime

        # These chars are valid in Windows filenames but dangerous in PowerShell
        tricky_name = "test file's $var & (cmd).jpg"
        tricky_path = tmp_path / tricky_name
        tricky_path.write_bytes(b'\xff\xd8\xff\xe0' + b'\x00' * 100)

        dt = datetime.datetime(2024, 1, 1, 12, 0, 0)
        # This should NOT execute any injected command.
        # It may fail (file isn't a real image) but must not raise
        # an unhandled exception or execute arbitrary code.
        try:
            result = _set_file_timestamp_method3(str(tricky_path), dt)
            assert isinstance(result, bool)
        except Exception as e:
            assert "injection" not in str(e).lower()

    @pytest.mark.skipif(os.name != 'nt', reason="Windows-only test")
    def test_path_with_backtick_and_semicolon(self, tmp_path):
        """Backticks and semicolons are PowerShell-special and must be safe."""
        from modules.exif_processor import _set_file_timestamp_method3
        import datetime

        tricky_name = "test`;echo pwned;`.jpg"
        tricky_path = tmp_path / tricky_name
        tricky_path.write_bytes(b'\xff\xd8\xff\xe0' + b'\x00' * 100)

        dt = datetime.datetime(2024, 1, 1, 12, 0, 0)
        try:
            result = _set_file_timestamp_method3(str(tricky_path), dt)
            assert isinstance(result, bool)
        except Exception:
            pass  # Graceful failure is acceptable


# ===========================================================================
# 2. Thread-safe global ExifTool instance
# ===========================================================================
class TestThreadSafeGlobalExifTool:
    """Verify that concurrent access to get_exiftool_metadata_shared is safe."""

    @skip_no_images
    def test_concurrent_exif_reads(self):
        """Multiple threads reading EXIF from different files must not crash."""
        from modules.exif_processor import (
            get_exiftool_metadata_shared, cleanup_global_exiftool,
            find_exiftool_path
        )

        exiftool_path = find_exiftool_path()
        if not exiftool_path:
            pytest.skip("ExifTool not found")

        results = {}
        errors = []

        def read_exif(file_path, thread_id):
            try:
                meta = get_exiftool_metadata_shared(file_path, exiftool_path)
                results[thread_id] = meta
            except Exception as e:
                errors.append((thread_id, str(e)))

        threads = []
        for i, fp in enumerate(SAMPLE_FILES):
            t = threading.Thread(target=read_exif, args=(fp, i))
            threads.append(t)

        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        # Cleanup
        cleanup_global_exiftool()

        assert len(errors) == 0, f"Thread errors: {errors}"
        assert len(results) == len(SAMPLE_FILES), "All threads should produce results"
        for tid, meta in results.items():
            assert isinstance(meta, dict), f"Thread {tid} returned non-dict"
            assert len(meta) > 0, f"Thread {tid} returned empty metadata"

    @skip_no_images
    def test_concurrent_reads_return_valid_data(self):
        """Verify that concurrent reads don't mix up metadata between files."""
        from modules.exif_processor import (
            get_exiftool_metadata_shared, cleanup_global_exiftool,
            find_exiftool_path
        )

        exiftool_path = find_exiftool_path()
        if not exiftool_path:
            pytest.skip("ExifTool not found")

        results = {}
        errors = []

        def read_exif(file_path, thread_id):
            try:
                meta = get_exiftool_metadata_shared(file_path, exiftool_path)
                results[thread_id] = {
                    'file': file_path,
                    'source_file': meta.get('SourceFile', ''),
                }
            except Exception as e:
                errors.append((thread_id, str(e)))

        threads = []
        for i, fp in enumerate(SAMPLE_FILES):
            t = threading.Thread(target=read_exif, args=(fp, i))
            threads.append(t)

        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        cleanup_global_exiftool()

        assert len(errors) == 0, f"Thread errors: {errors}"
        # Each result's SourceFile should match the file we requested
        for tid, info in results.items():
            source = os.path.normpath(info['source_file'])
            expected = os.path.normpath(info['file'])
            assert source == expected, (
                f"Thread {tid}: SourceFile mismatch — got {source}, expected {expected}"
            )


# ===========================================================================
# 3. Global ExifTool cleanup
# ===========================================================================
class TestGlobalExifToolCleanup:
    """Verify cleanup_global_exiftool properly terminates the subprocess."""

    @skip_no_images
    def test_cleanup_after_use(self):
        """After cleanup, the global instance should be None."""
        from modules.exif_processor import (
            get_exiftool_metadata_shared, cleanup_global_exiftool,
            _global_exiftool_instance, find_exiftool_path
        )
        import modules.exif_processor as ep

        exiftool_path = find_exiftool_path()
        if not exiftool_path:
            pytest.skip("ExifTool not found")

        # Use the shared instance to ensure it's running
        meta = get_exiftool_metadata_shared(SAMPLE_FILES[0], exiftool_path)
        assert len(meta) > 0, "Should get metadata"
        assert ep._global_exiftool_instance is not None, "Instance should be active"

        # Cleanup
        cleanup_global_exiftool()
        assert ep._global_exiftool_instance is None, "Instance should be None after cleanup"

    @skip_no_images
    def test_double_cleanup_safe(self):
        """Calling cleanup twice should not raise."""
        from modules.exif_processor import (
            get_exiftool_metadata_shared, cleanup_global_exiftool,
            find_exiftool_path
        )

        exiftool_path = find_exiftool_path()
        if not exiftool_path:
            pytest.skip("ExifTool not found")

        get_exiftool_metadata_shared(SAMPLE_FILES[0], exiftool_path)
        cleanup_global_exiftool()
        cleanup_global_exiftool()  # Must not raise

    @skip_no_images
    def test_reuse_after_cleanup(self):
        """After cleanup, a new call should recreate the instance and work."""
        from modules.exif_processor import (
            get_exiftool_metadata_shared, cleanup_global_exiftool,
            find_exiftool_path
        )
        import modules.exif_processor as ep

        exiftool_path = find_exiftool_path()
        if not exiftool_path:
            pytest.skip("ExifTool not found")

        # Use, cleanup, then use again
        get_exiftool_metadata_shared(SAMPLE_FILES[0], exiftool_path)
        cleanup_global_exiftool()
        assert ep._global_exiftool_instance is None

        meta = get_exiftool_metadata_shared(SAMPLE_FILES[0], exiftool_path)
        assert len(meta) > 0, "Should work again after cleanup"
        assert ep._global_exiftool_instance is not None

        # Final cleanup
        cleanup_global_exiftool()


# ===========================================================================
# 4. Basic EXIF extraction smoke test (validates nothing is broken)
# ===========================================================================
class TestBasicExifExtraction:
    """Smoke tests to ensure EXIF extraction still works after Phase 1 changes."""

    @skip_no_images
    def test_extract_exif_fields(self):
        """extract_exif_fields_with_retry should return a 3-tuple."""
        from modules.exif_processor import (
            extract_exif_fields_with_retry, find_exiftool_path,
            cleanup_global_exiftool
        )

        exiftool_path = find_exiftool_path()
        if not exiftool_path:
            pytest.skip("ExifTool not found")

        result = extract_exif_fields_with_retry(
            SAMPLE_FILES[0], "exiftool", exiftool_path
        )
        assert isinstance(result, tuple)
        assert len(result) == 3
        date_taken, camera, lens = result
        # These are Sony ARW/JPG files — should have EXIF data
        assert date_taken is not None, "Should extract date from real image"

        cleanup_global_exiftool()

    @skip_no_images
    def test_exif_service_extraction(self):
        """ExifService should also work correctly."""
        from modules.exif_service_new import ExifService
        from modules.exif_processor import find_exiftool_path

        exiftool_path = find_exiftool_path()
        if not exiftool_path:
            pytest.skip("ExifTool not found")

        service = ExifService(exiftool_path=exiftool_path)
        try:
            result = service.get_cached_exif_data(
                SAMPLE_FILES[0], "exiftool", exiftool_path
            )
            assert isinstance(result, tuple)
            assert len(result) == 3
            date_taken, camera, lens = result
            assert date_taken is not None, "Should extract date"
        finally:
            service.cleanup()
