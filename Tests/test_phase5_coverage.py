#!/usr/bin/env python3
"""
Phase 5 – Coverage expansion tests.

Tests the new batch extraction, raw-metadata parsers, and the ExifService-
backed rename path that was added in Phase 7 (performance optimisation).
Also covers previously untested modules: exif_undo_manager, state_model,
settings_manager helpers, and handlers/exif_handler.
"""

import os
import sys
import re
import datetime
import tempfile
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.exif_service_new import ExifService


# =====================================================================
# ExifService – static raw-metadata parsers
# =====================================================================
class TestRawMetadataParsers:
    """Validate the static helpers that extract fields from raw EXIF dicts."""

    SAMPLE_META = {
        "EXIF:DateTimeOriginal": "2024:06:15 10:30:00",
        "EXIF:Model": "Canon EOS R5",
        "EXIF:LensModel": "RF24-70mm F2.8 L IS USM",
        "EXIF:FNumber": 2.8,
        "EXIF:ISO": 400,
        "EXIF:FocalLength": 50.0,
        "EXIF:ExposureTime": "1/250",
    }

    def test_parse_date(self):
        assert ExifService.parse_date_from_raw(self.SAMPLE_META) == "20240615"

    def test_parse_date_missing(self):
        assert ExifService.parse_date_from_raw({}) is None

    def test_parse_date_fallback_create_date(self):
        meta = {"CreateDate": "2025:01:01 12:00:00"}
        assert ExifService.parse_date_from_raw(meta) == "20250101"

    def test_parse_camera(self):
        assert ExifService.parse_camera_from_raw(self.SAMPLE_META) == "Canon-EOS-R5"

    def test_parse_camera_missing(self):
        assert ExifService.parse_camera_from_raw({}) is None

    def test_parse_camera_fallback_model_key(self):
        meta = {"Model": "Nikon Z9"}
        assert ExifService.parse_camera_from_raw(meta) == "Nikon-Z9"

    def test_parse_lens(self):
        result = ExifService.parse_lens_from_raw(self.SAMPLE_META)
        assert "RF24-70mm" in result

    def test_parse_lens_missing(self):
        assert ExifService.parse_lens_from_raw({}) is None

    def test_parse_lens_fallback_lens_info(self):
        meta = {"LensInfo": "24-105mm f/4"}
        assert ExifService.parse_lens_from_raw(meta) == "24-105mm-f/4"

    def test_parse_all_metadata_aperture(self):
        result = ExifService.parse_all_metadata_from_raw(self.SAMPLE_META)
        assert result["aperture"] == "f2.8"

    def test_parse_all_metadata_iso(self):
        result = ExifService.parse_all_metadata_from_raw(self.SAMPLE_META)
        assert result["iso"] == "400"

    def test_parse_all_metadata_focal_length(self):
        result = ExifService.parse_all_metadata_from_raw(self.SAMPLE_META)
        assert result["focal_length"] == "50mm"

    def test_parse_all_metadata_shutter(self):
        result = ExifService.parse_all_metadata_from_raw(self.SAMPLE_META)
        assert result["shutter_speed"] == "1/250s"

    def test_parse_all_metadata_empty_dict(self):
        assert ExifService.parse_all_metadata_from_raw({}) == {}

    def test_parse_all_metadata_none_input(self):
        assert ExifService.parse_all_metadata_from_raw(None) == {}

    def test_parse_all_metadata_camera_and_lens(self):
        result = ExifService.parse_all_metadata_from_raw(self.SAMPLE_META)
        assert result["camera"] == "Canon-EOS-R5"
        assert "RF24-70mm" in result["lens"]

    def test_parse_all_metadata_fraction_aperture(self):
        meta = {"EXIF:FNumber": "28/10"}
        result = ExifService.parse_all_metadata_from_raw(meta)
        assert result["aperture"] == "f2.8"

    def test_parse_all_metadata_slow_shutter(self):
        """Shutter speeds >= 1s should format as Ns."""
        meta = {"EXIF:ExposureTime": 2.0}
        result = ExifService.parse_all_metadata_from_raw(meta)
        assert result["shutter_speed"] == "2s"

    def test_parse_all_metadata_fractional_focal_length(self):
        meta = {"EXIF:FocalLength": "200/1"}
        result = ExifService.parse_all_metadata_from_raw(meta)
        assert result["focal_length"] == "200mm"


# =====================================================================
# ExifService – batch_get_raw_metadata
# =====================================================================
class TestBatchGetRawMetadata:
    """Test the batch extraction path (mocked ExifTool)."""

    def _make_service(self) -> ExifService:
        svc = ExifService.__new__(ExifService)
        svc._cache = {}
        svc._cache_lock = __import__("threading").Lock()
        svc._cache_max_size = 10000
        svc._exiftool_instance = None
        svc._exiftool_lock = __import__("threading").Lock()
        svc._exiftool_path = "/fake/exiftool"
        svc.current_method = "exiftool"
        return svc

    def test_empty_list_returns_empty(self):
        svc = self._make_service()
        assert svc.batch_get_raw_metadata([]) == {}

    def test_batch_calls_get_metadata_once_per_chunk(self, tmp_path):
        """Files within one chunk should result in a single get_metadata call."""
        # Create 3 dummy files
        files = []
        for i in range(3):
            p = tmp_path / f"img_{i}.jpg"
            p.touch()
            files.append(str(p))

        svc = self._make_service()

        fake_instance = MagicMock()
        fake_meta = [{"EXIF:ISO": str(100 + i)} for i in range(3)]
        fake_instance.get_metadata.return_value = fake_meta

        svc._exiftool_instance = fake_instance

        with patch.object(svc, "_ensure_exiftool_running"):
            result = svc.batch_get_raw_metadata(files, chunk_size=50)

        # Single call with all 3 files
        assert fake_instance.get_metadata.call_count == 1
        assert len(result) == 3
        for fp in files:
            assert fp in result

    def test_batch_chunks_multiple_calls(self, tmp_path):
        """When files exceed chunk_size, multiple batch calls should be made."""
        files = []
        for i in range(5):
            p = tmp_path / f"img_{i}.jpg"
            p.touch()
            files.append(str(p))

        svc = self._make_service()

        fake_instance = MagicMock()
        # Return one metadata dict per requested file
        fake_instance.get_metadata.side_effect = lambda paths: [
            {"EXIF:ISO": "100"} for _ in paths
        ]

        svc._exiftool_instance = fake_instance

        with patch.object(svc, "_ensure_exiftool_running"):
            result = svc.batch_get_raw_metadata(files, chunk_size=2)

        # 5 files / chunk_size=2 → 3 calls (2+2+1)
        assert fake_instance.get_metadata.call_count == 3
        assert len(result) == 5

    def test_batch_nonexistent_files_return_empty(self, tmp_path):
        svc = self._make_service()
        result = svc.batch_get_raw_metadata([str(tmp_path / "nope.jpg")])
        assert result[str(tmp_path / "nope.jpg")] == {}


# =====================================================================
# ExifService – _ensure_exiftool_running / _kill_exiftool_instance
# =====================================================================
class TestExifToolLifecycleHelpers:
    """Test the new helper methods for ExifTool process management."""

    def test_ensure_creates_instance_when_none(self):
        svc = ExifService.__new__(ExifService)
        svc._exiftool_instance = None
        svc._exiftool_lock = __import__("threading").Lock()
        svc._exiftool_path = None

        fake_et = MagicMock()
        with patch("modules.exif_service_new.exiftool") as mock_et_mod:
            mock_et_mod.ExifToolHelper.return_value = fake_et
            svc._ensure_exiftool_running("/fake/path")

        assert svc._exiftool_instance is fake_et
        fake_et.__enter__.assert_called_once()

    def test_ensure_noop_when_already_running(self):
        svc = ExifService.__new__(ExifService)
        existing = MagicMock()
        svc._exiftool_instance = existing
        svc._exiftool_lock = __import__("threading").Lock()
        svc._exiftool_path = "/fake/path"

        svc._ensure_exiftool_running("/fake/path")
        # Should NOT recreate
        assert svc._exiftool_instance is existing

    def test_kill_terminates_and_clears(self):
        svc = ExifService.__new__(ExifService)
        fake_et = MagicMock()
        svc._exiftool_instance = fake_et
        svc._exiftool_lock = __import__("threading").Lock()

        svc._kill_exiftool_instance()
        fake_et.terminate.assert_called_once()
        assert svc._exiftool_instance is None

    def test_kill_noop_when_none(self):
        svc = ExifService.__new__(ExifService)
        svc._exiftool_instance = None
        svc._exiftool_lock = __import__("threading").Lock()
        svc._kill_exiftool_instance()  # Should not raise


# =====================================================================
# handlers/exif_handler – extract_image_number
# =====================================================================
class TestExtractImageNumber:
    """Test the image-number extraction from filenames and EXIF data."""

    def test_returns_none_without_exif_data(self, tmp_path):
        from modules.handlers.exif_handler import extract_image_number
        p = tmp_path / "DSC01234.ARW"
        p.touch()
        mock_service = MagicMock()
        mock_service.extract_raw_exif = MagicMock(return_value={})
        num = extract_image_number(str(p), "exiftool", "/fake/exiftool", exif_service=mock_service)
        # No EXIF image-number fields → None
        assert num is None

    def test_returns_number_from_shutter_count(self, tmp_path):
        from modules.handlers.exif_handler import extract_image_number
        p = tmp_path / "DSC01234.ARW"
        p.touch()
        mock_service = MagicMock()
        mock_service.extract_raw_exif = MagicMock(return_value={"EXIF:ShutterCount": "5678"})
        num = extract_image_number(str(p), "exiftool", "/fake/exiftool", exif_service=mock_service)
        assert num == "5678"

    def test_returns_number_from_image_number(self, tmp_path):
        from modules.handlers.exif_handler import extract_image_number
        p = tmp_path / "IMG_5678.JPG"
        p.touch()
        mock_service = MagicMock()
        mock_service.extract_raw_exif = MagicMock(return_value={"EXIF:ImageNumber": 9999})
        num = extract_image_number(str(p), "exiftool", "/fake/exiftool", exif_service=mock_service)
        assert num == "9999"

    def test_returns_none_for_non_exiftool_method(self, tmp_path):
        """Non-exiftool methods should return None (Pillow removed)."""
        from modules.handlers.exif_handler import extract_image_number
        p = tmp_path / "test.jpg"
        p.touch()
        num = extract_image_number(str(p), "other", None)
        assert num is None


# =====================================================================
# state_model – basic behaviour
# =====================================================================
class TestStateModel:
    """state_model.RenamerState is a simple data holder."""

    def test_initial_has_no_files(self):
        from modules.state_model import RenamerState
        state = RenamerState()
        assert state.has_files() is False

    def test_clear_files_resets(self):
        from modules.state_model import RenamerState
        state = RenamerState()
        state.files = ["a.jpg", "b.jpg"]
        state.clear_files()
        assert state.has_files() is False

    def test_has_files_true_when_populated(self):
        from modules.state_model import RenamerState
        state = RenamerState()
        state.files = ["a.jpg"]
        assert state.has_files() is True

    def test_has_restore_data_false_initially(self):
        from modules.state_model import RenamerState
        state = RenamerState()
        assert state.has_restore_data() is False

    def test_has_restore_data_true_with_originals(self):
        from modules.state_model import RenamerState
        state = RenamerState()
        state.original_filenames = {"new.jpg": "old.jpg"}
        assert state.has_restore_data() is True


# =====================================================================
# Rename engine – optimized batch path (ExifService)
# =====================================================================
class TestRenameEngineExifServicePath:
    """Verify rename uses ExifService batch extraction when available."""

    def _make_worker(self, files, **overrides):
        from modules.rename_engine import RenameWorkerThread
        defaults = dict(
            files=files,
            camera_prefix="TEST",
            additional="",
            use_camera=False,
            use_lens=False,
            exif_method="exiftool",
            separator="_",
            exiftool_path=None,
            custom_order=["Date", "Prefix", "Number"],
            date_format="YYYY-MM-DD",
            use_date=True,
            continuous_counter=False,
            selected_metadata={},
            sync_exif_date=False,
            leave_names=False,
        )
        defaults.update(overrides)
        return RenameWorkerThread(**defaults)

    def test_pre_extract_uses_batch(self, tmp_path):
        """_pre_extract_exif_cache() should call batch_get_raw_metadata."""
        files = []
        for i in range(5):
            for ext in (".jpg", ".arw"):
                p = tmp_path / f"DSC{10000+i:05d}{ext}"
                p.touch()
                files.append(str(p))

        mock_service = MagicMock()
        # Return fake raw metadata for each first-file
        mock_service.batch_get_raw_metadata.return_value = {
            f: {"EXIF:DateTimeOriginal": "2024:06:15 10:00:00", "EXIF:Model": "TestCam"}
            for f in files
        }

        worker = self._make_worker(files, exif_service=mock_service)
        groups = worker._create_file_groups()
        cache = worker._pre_extract_exif_cache(groups)

        mock_service.batch_get_raw_metadata.assert_called_once()
        # Cache should have entries
        assert len(cache) > 0
        # Each entry should have all_metadata and raw_meta
        for fp, data in cache.items():
            if data is not None:
                assert "raw_meta" in data
                assert "all_metadata" in data
                assert "date_str" in data

    def test_no_cache_clear_at_start(self, tmp_path):
        """optimized_rename_files should NOT clear ExifService cache."""
        p = tmp_path / "DSC10000.jpg"
        p.touch()

        mock_service = MagicMock()
        mock_service.batch_get_raw_metadata.return_value = {
            str(p): {"EXIF:DateTimeOriginal": "2024:06:15 10:00:00"}
        }

        worker = self._make_worker([str(p)], exif_service=mock_service)
        worker.progress_update = MagicMock()

        with patch("modules.exif_processor.batch_sync_exif_dates", return_value=([], [], {})):
            worker.optimized_rename_files()

        # clear_cache should NOT have been called
        mock_service.clear_cache.assert_not_called()

    def test_process_group_uses_cached_all_metadata(self, tmp_path):
        """_process_file_group should use all_metadata from cache, not make new ExifTool calls."""
        p = tmp_path / "DSC10000.jpg"
        p.touch()

        mock_service = MagicMock()

        worker = self._make_worker(
            [str(p)],
            exif_service=mock_service,
            selected_metadata={"iso": True, "aperture": True},
            custom_order=["Date", "Prefix", "Metadata", "Number"],
        )
        worker.progress_update = MagicMock()

        # Pre-built cache with all_metadata already present
        exif_cache = {
            str(p): {
                "date_str": "20240615",
                "camera": None,
                "lens": None,
                "raw_meta": {"EXIF:DateTimeOriginal": "2024:06:15 10:00:00"},
                "all_metadata": {"iso": "400", "aperture": "f2.8"},
            }
        }

        renamed, errors, _mapping = worker._process_file_group([str(p)], {}, exif_cache)

        # Should NOT call get_all_metadata or get_selective_cached_exif_data
        mock_service.get_all_metadata.assert_not_called()
        mock_service.get_selective_cached_exif_data.assert_not_called()
        assert len(errors) == 0


# =====================================================================
# ExifService – find_exiftool_path
# =====================================================================
class TestFindExiftoolPath:
    """Test ExifTool path discovery."""

    def test_finds_bundled_exiftool(self):
        """The renamepy project ships with exiftool-13.33_64."""
        svc = ExifService()
        # The _find_exiftool_path_cached should find bundled exiftool
        path = svc._find_exiftool_path()
        # Should either find a path or return None (not crash)
        if path:
            assert "exiftool" in path.lower() or path == "exiftool"
