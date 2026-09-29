"""
Integration tests for Phase 1 critical fixes:
  2. Thread-safe global ExifTool instance
  3. Global ExifTool cleanup on exit

(The PowerShell timestamp helper and its tests were removed: arguments after
``powershell -Command`` are appended to the script text, so the helper was
injectable through file names and was never used by the application.)

Uses real camera images (read-only) from $RENAMEPY_TEST_IMAGES, Tests/Testbilder
or C:\\Users\\yshub\\Desktop\\Bilbao, whichever exists first.
"""

import os
import sys
import threading
import pytest

# Make sure modules are importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


_IMAGE_DIRS = [
    os.environ.get("RENAMEPY_TEST_IMAGES", ""),
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "Testbilder"),
    r"C:\Users\yshub\Desktop\Bilbao",
]
IMAGE_DIR = next((d for d in _IMAGE_DIRS if d and os.path.isdir(d)), None)
SAMPLE_FILES = []

# Collect a small subset of real test images (first 3 JPGs)
if IMAGE_DIR:
    all_jpgs = sorted(
        f for f in os.listdir(IMAGE_DIR) if f.upper().endswith('.JPG')
    )[:3]
    SAMPLE_FILES = [os.path.join(IMAGE_DIR, f) for f in all_jpgs]

HAS_IMAGES = len(SAMPLE_FILES) > 0
skip_no_images = pytest.mark.skipif(not HAS_IMAGES, reason="No real test images (see module docstring)")


# ===========================================================================
# 2. Thread-safe EXIF reads via ExifService delegates
# ===========================================================================
class TestThreadSafeGlobalExifTool:
    """Verify that concurrent access to get_exiftool_metadata_shared is safe."""

    @skip_no_images
    def test_concurrent_exif_reads(self):
        """Multiple threads reading EXIF from different files must not crash."""
        from modules.exif_processor import (
            get_exiftool_metadata_shared, cleanup_global_exiftool,
            set_default_exif_service, find_exiftool_path
        )
        from modules.exif_service_new import ExifService

        exiftool_path = find_exiftool_path()
        if not exiftool_path:
            pytest.skip("ExifTool not found")

        service = ExifService(exiftool_path=exiftool_path)
        set_default_exif_service(service)

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
        set_default_exif_service(None)

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
            set_default_exif_service, find_exiftool_path
        )
        from modules.exif_service_new import ExifService

        exiftool_path = find_exiftool_path()
        if not exiftool_path:
            pytest.skip("ExifTool not found")

        service = ExifService(exiftool_path=exiftool_path)
        set_default_exif_service(service)

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
        set_default_exif_service(None)

        assert len(errors) == 0, f"Thread errors: {errors}"
        # Each result's SourceFile should match the file we requested
        for tid, info in results.items():
            source = os.path.normpath(info['source_file'])
            expected = os.path.normpath(info['file'])
            assert source == expected, (
                f"Thread {tid}: SourceFile mismatch — got {source}, expected {expected}"
            )


# ===========================================================================
# 3. ExifService delegate cleanup
# ===========================================================================
class TestGlobalExifToolCleanup:
    """Verify cleanup_global_exiftool properly cleans up the ExifService."""

    @skip_no_images
    def test_cleanup_after_use(self):
        """After cleanup, delegate calls should return safe defaults."""
        from modules.exif_processor import (
            get_exiftool_metadata_shared, cleanup_global_exiftool,
            set_default_exif_service, find_exiftool_path
        )
        from modules.exif_service_new import ExifService

        exiftool_path = find_exiftool_path()
        if not exiftool_path:
            pytest.skip("ExifTool not found")

        service = ExifService(exiftool_path=exiftool_path)
        set_default_exif_service(service)

        # Use the shared instance to ensure it's running
        meta = get_exiftool_metadata_shared(SAMPLE_FILES[0], exiftool_path)
        assert len(meta) > 0, "Should get metadata"

        # Cleanup
        cleanup_global_exiftool()
        set_default_exif_service(None)

    @skip_no_images
    def test_double_cleanup_safe(self):
        """Calling cleanup twice should not raise."""
        from modules.exif_processor import (
            get_exiftool_metadata_shared, cleanup_global_exiftool,
            set_default_exif_service, find_exiftool_path
        )
        from modules.exif_service_new import ExifService

        exiftool_path = find_exiftool_path()
        if not exiftool_path:
            pytest.skip("ExifTool not found")

        service = ExifService(exiftool_path=exiftool_path)
        set_default_exif_service(service)

        get_exiftool_metadata_shared(SAMPLE_FILES[0], exiftool_path)
        cleanup_global_exiftool()
        cleanup_global_exiftool()  # Must not raise
        set_default_exif_service(None)

    @skip_no_images
    def test_reuse_after_cleanup(self):
        """After cleanup and re-registration, a new call should work."""
        from modules.exif_processor import (
            get_exiftool_metadata_shared, cleanup_global_exiftool,
            set_default_exif_service, find_exiftool_path
        )
        from modules.exif_service_new import ExifService

        exiftool_path = find_exiftool_path()
        if not exiftool_path:
            pytest.skip("ExifTool not found")

        # Use, cleanup
        service1 = ExifService(exiftool_path=exiftool_path)
        set_default_exif_service(service1)
        get_exiftool_metadata_shared(SAMPLE_FILES[0], exiftool_path)
        cleanup_global_exiftool()

        # Re-register new service and use again
        service2 = ExifService(exiftool_path=exiftool_path)
        set_default_exif_service(service2)
        meta = get_exiftool_metadata_shared(SAMPLE_FILES[0], exiftool_path)
        assert len(meta) > 0, "Should work again after re-registration"

        # Final cleanup
        cleanup_global_exiftool()
        set_default_exif_service(None)


# ===========================================================================
# 4. Basic EXIF extraction smoke test (validates nothing is broken)
# ===========================================================================
class TestBasicExifExtraction:
    """Smoke tests to ensure EXIF extraction still works after Phase 1 changes."""

    @skip_no_images
    def test_extract_exif_fields(self):
        """ExifService.get_selective_cached_exif_data should return a 3-tuple."""
        from modules.exif_processor import (
            find_exiftool_path,
            cleanup_global_exiftool, set_default_exif_service
        )
        from modules.exif_service_new import ExifService

        exiftool_path = find_exiftool_path()
        if not exiftool_path:
            pytest.skip("ExifTool not found")

        service = ExifService(exiftool_path=exiftool_path)
        set_default_exif_service(service)

        result = service.get_selective_cached_exif_data(
            SAMPLE_FILES[0], "exiftool", exiftool_path
        )
        assert isinstance(result, tuple)
        assert len(result) == 3
        date_taken, camera, lens = result
        # These are Sony ARW/JPG files — should have EXIF data
        assert date_taken is not None, "Should extract date from real image"

        cleanup_global_exiftool()
        set_default_exif_service(None)

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
