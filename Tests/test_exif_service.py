#!/usr/bin/env python3
"""
Unit tests for modules/exif_service_new.py

Tests the ExifService wrapper with mocked ExifTool calls,
verifying caching, cleanup, selective extraction, and error handling.
"""

import os
import sys
from unittest.mock import Mock, patch

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


# ---------------------------------------------------------------------------
# ExifTool write helpers
# ---------------------------------------------------------------------------
class TestExifToolWriteHelpers:

    def test_write_timeout_grows_with_bytes(self, tmp_path):
        from modules.exif_service_new import exiftool_write_timeout
        small = tmp_path / "small.jpg"
        small.write_bytes(b"x" * 1000)
        large = tmp_path / "large.mov"
        large.write_bytes(b"x" * 3000)
        missing = str(tmp_path / "missing.jpg")

        timeout = exiftool_write_timeout([str(small), str(large), missing],
                                         base=10, per_file=1, min_bytes_per_second=100)

        assert timeout == 10 + 3 + 40  # base + 3 files + 4000 bytes at 100 B/s

    def test_write_timeout_defaults(self, tmp_path):
        from modules.exif_service_new import exiftool_write_timeout
        assert exiftool_write_timeout([]) == 60
        assert exiftool_write_timeout([str(tmp_path / "missing.jpg")]) == 62

    def test_remove_tmp_files_keeps_preexisting(self, tmp_path):
        from modules.exif_service_new import (
            existing_exiftool_tmp_files, remove_exiftool_tmp_files,
        )
        a, b, c = (str(tmp_path / n) for n in ("a.jpg", "b.jpg", "c.jpg"))
        old = b + "_exiftool_tmp"
        open(old, "w").close()
        before = existing_exiftool_tmp_files([a, b, c])
        new = a + "_exiftool_tmp"
        open(new, "w").close()

        remove_exiftool_tmp_files([a, b, c], keep=before)

        assert before == {old}
        assert not os.path.exists(new)
        assert os.path.exists(old)


# ---------------------------------------------------------------------------
# Unreadable files and the batch fallback
# ---------------------------------------------------------------------------
class TestUnreadableFiles:

    def test_usable_metadata(self):
        from modules.exif_service_new import usable_metadata
        assert usable_metadata({"SourceFile": "a.jpg", "ExifTool:Error": "File is empty"}) == {}
        assert usable_metadata(None) == {}
        meta = {"SourceFile": "a.jpg", "EXIF:Model": "X"}
        assert usable_metadata(meta) is meta

    def test_helper_does_not_raise_on_exit_status(self):
        from modules.exif_service_new import new_exiftool_helper
        with patch("modules.exif_service_new.exiftool.ExifToolHelper") as helper:
            new_exiftool_helper()
        assert helper.call_args.kwargs["check_execute"] is False

    def test_error_entry_in_batch_maps_to_empty(self, tmp_path):
        good, bad = str(tmp_path / "good.jpg"), str(tmp_path / "bad.jpg")
        open(good, "w").close()
        open(bad, "w").close()
        svc = ExifService()
        svc._exiftool_instance = Mock()
        svc._exiftool_instance.get_metadata.return_value = [
            {"SourceFile": good, "EXIF:Model": "X"},
            {"SourceFile": bad, "ExifTool:Error": "File format error"},
        ]
        with patch.object(svc, "_ensure_exiftool_running", return_value=True):
            result = svc.batch_get_raw_metadata([good, bad])
        assert result[good]["EXIF:Model"] == "X"
        assert result[bad] == {}
        assert svc._exiftool_instance.get_metadata.call_count == 1

    def test_raising_batch_still_falls_back_per_file(self, tmp_path):
        """A dead process still raises; the per-file fallback stays."""
        files = [str(tmp_path / f"{i}.jpg") for i in range(2)]
        for f in files:
            open(f, "w").close()
        svc = ExifService()
        svc._exiftool_instance = Mock()

        def get_metadata(paths):
            if len(paths) > 1:
                raise RuntimeError("process died")
            return [{"SourceFile": paths[0], "EXIF:Model": "X"}]

        svc._exiftool_instance.get_metadata.side_effect = get_metadata
        with patch.object(svc, "_ensure_exiftool_running", return_value=True):
            result = svc.batch_get_raw_metadata(files)
        assert all(result[f]["EXIF:Model"] == "X" for f in files)
        assert svc._exiftool_instance.get_metadata.call_count == 3


# ---------------------------------------------------------------------------
# One cached extraction path for both getters
# ---------------------------------------------------------------------------
class TestCachedBasicFields:

    META = {"SourceFile": "x", "EXIF:DateTimeOriginal": "2024:06:15 10:00:00",
            "EXIF:Model": "ILCE 7CM2", "EXIF:LensModel": "FE 100-400mm"}

    def _service(self, *reads):
        service = ExifService()
        service.current_method = "exiftool"
        service._get_exiftool_metadata_shared = Mock(side_effect=list(reads))
        return service

    def test_failed_read_is_not_cached(self, tmp_path):
        """Regression: an empty read was cached as "no metadata"."""
        f = tmp_path / "photo.jpg"
        f.touch()
        service = self._service({}, dict(self.META))

        assert service.get_cached_exif_data(str(f)) == (None, None, None)
        assert service.get_cached_exif_data(str(f)) == ("20240615", "ILCE-7CM2", "FE-100-400mm")

    def test_failed_selective_read_is_not_cached(self, tmp_path):
        f = tmp_path / "photo.jpg"
        f.touch()
        service = self._service({}, dict(self.META))

        assert service.get_selective_cached_exif_data(str(f)) == (None, None, None)
        assert service.get_selective_cached_exif_data(str(f), need_camera=True) == ("20240615", "ILCE-7CM2", None)

    def test_getters_share_one_normalized_cache_entry(self, tmp_path):
        (tmp_path / "sub").mkdir()
        f = tmp_path / "sub" / "photo.jpg"
        f.touch()
        service = self._service(dict(self.META))

        first = service.get_cached_exif_data(os.path.join(str(tmp_path), "sub", ".", "photo.jpg"))
        second = service.get_selective_cached_exif_data(str(f), need_camera=True, need_lens=True)

        assert first == second == ("20240615", "ILCE-7CM2", "FE-100-400mm")
        assert service._get_exiftool_metadata_shared.call_count == 1

    def test_readable_file_without_fields_is_cached(self, tmp_path):
        f = tmp_path / "scan.png"
        f.touch()
        service = self._service({"SourceFile": "x", "File:FileType": "PNG"})

        assert service.get_cached_exif_data(str(f)) == (None, None, None)
        assert service.get_cached_exif_data(str(f)) == (None, None, None)
        assert service._get_exiftool_metadata_shared.call_count == 1
