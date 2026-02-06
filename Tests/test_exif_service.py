#!/usr/bin/env python3
"""
Unit tests for modules/exif_service_new.py

Tests the ExifService wrapper with mocked ExifTool calls,
verifying caching, cleanup, selective extraction, and error handling.
"""

import os
import sys
import pytest
from unittest.mock import Mock, patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.exif_service_new import ExifService


# ---------------------------------------------------------------------------
# Service lifecycle
# ---------------------------------------------------------------------------
class TestExifServiceLifecycle:
    """Test creation, cleanup, and basic state."""

    def test_creation(self):
        service = ExifService()
        assert service is not None
        assert hasattr(service, "_cache")
        assert hasattr(service, "_cache_lock")

    def test_initial_cache_empty(self):
        service = ExifService()
        assert len(service._cache) == 0

    def test_cleanup_without_instance(self):
        """cleanup() should be safe even if no ExifTool was started."""
        service = ExifService()
        service.cleanup()  # should not raise

    def test_cleanup_calls_exit_on_instance(self):
        service = ExifService()
        mock_instance = Mock()
        mock_instance.__exit__ = Mock()
        service._exiftool_instance = mock_instance

        service.cleanup()

        mock_instance.__exit__.assert_called_once()
        assert service._exiftool_instance is None

    def test_double_cleanup_safe(self):
        """Calling cleanup twice should be harmless."""
        service = ExifService()
        mock_instance = Mock()
        mock_instance.__exit__ = Mock()
        service._exiftool_instance = mock_instance

        service.cleanup()
        service.cleanup()  # second call should not raise


# ---------------------------------------------------------------------------
# Cache management
# ---------------------------------------------------------------------------
class TestExifServiceCache:
    """Test cache operations."""

    def test_clear_cache(self):
        service = ExifService()
        service._cache["key1"] = "value1"
        service._cache["key2"] = "value2"
        assert len(service._cache) == 2

        service.clear_cache()
        assert len(service._cache) == 0

    def test_cache_eviction_removes_entries(self):
        """Eviction should shrink the cache when it exceeds the limit."""
        service = ExifService()
        max_size = service._cache_max_size
        overflow = 100
        for i in range(max_size + overflow):
            service._cache[f"file_{i}.jpg"] = {"date_str": "20240101"}

        before = len(service._cache)
        service._evict_cache_if_needed()
        after = len(service._cache)
        assert after < before, "Eviction should have removed entries"

    def test_cached_result_returned(self, tmp_path):
        """Second call with same file should return cached data."""
        service = ExifService()
        test_file = tmp_path / "photo.jpg"
        test_file.write_bytes(b"\xff\xd8")  # minimal content

        # Build the same cache key the service uses: (path, mtime, method)
        mtime = os.path.getmtime(str(test_file))
        cache_key = (str(test_file), mtime, "exiftool")
        service._cache[cache_key] = ("20240615", "Canon", "RF50mm")

        with patch.object(service, "_extract_exif_fields_with_retry") as mock_extract:
            date, camera, lens = service.get_cached_exif_data(
                str(test_file), method="exiftool"
            )
            # Should NOT have called the extractor — cache was used
            mock_extract.assert_not_called()

        assert date == "20240615"
        assert camera == "Canon"
        assert lens == "RF50mm"


# ---------------------------------------------------------------------------
# Mocked EXIF extraction
# ---------------------------------------------------------------------------
class TestExifServiceExtraction:
    """Test EXIF data extraction with mocked backends."""

    @patch("modules.exif_service_new.EXIFTOOL_AVAILABLE", True)
    def test_extraction_returns_tuple(self, tmp_path):
        test_file = tmp_path / "photo.jpg"
        test_file.touch()

        service = ExifService()
        with patch.object(service, "_extract_exif_fields_with_retry") as mock_extract:
            mock_extract.return_value = ("20240615", "Canon-EOS-R5", "RF24-70mm")
            date, camera, lens = service.get_cached_exif_data(
                str(test_file), method="exiftool"
            )

        assert date == "20240615"
        assert camera == "Canon-EOS-R5"
        assert lens == "RF24-70mm"

    @patch("modules.exif_service_new.EXIFTOOL_AVAILABLE", True)
    def test_selective_extraction_date_only(self, tmp_path):
        test_file = tmp_path / "photo.jpg"
        test_file.touch()

        service = ExifService()
        with patch.object(service, "_extract_selective_exif_fields") as mock_extract:
            mock_extract.return_value = ("20240615", None, None)
            date, camera, lens = service.get_selective_cached_exif_data(
                str(test_file),
                method="exiftool",
                exiftool_path=None,
                need_date=True,
                need_camera=False,
                need_lens=False,
            )

        assert date == "20240615"
        assert camera is None
        assert lens is None

    @patch("modules.exif_service_new.EXIFTOOL_AVAILABLE", True)
    def test_extraction_failure_returns_none_tuple(self, tmp_path):
        test_file = tmp_path / "corrupt.jpg"
        test_file.touch()

        service = ExifService()
        with patch.object(service, "_extract_exif_fields_with_retry") as mock_extract:
            mock_extract.side_effect = Exception("EXIF read error")
            date, camera, lens = service.get_cached_exif_data(
                str(test_file), method="exiftool"
            )

        assert date is None
        assert camera is None
        assert lens is None
