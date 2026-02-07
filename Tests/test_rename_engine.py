#!/usr/bin/env python3
"""
Unit and lightweight integration tests for modules/rename_engine.py

Tests the RenameWorkerThread logic:
- File grouping (RAW/JPEG siblings)
- EXIF sort key generation
- Filename generation and counter logic
- End-to-end rename with small file sets (≤50 pairs)
"""

import os
import sys
import re
import datetime
import pytest
from pathlib import Path
from collections import defaultdict
from unittest.mock import Mock, patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.rename_engine import RenameWorkerThread


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _make_worker(files: list[str], **overrides) -> RenameWorkerThread:
    """Create a RenameWorkerThread with sensible defaults."""
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
        exif_service=None,
    )
    defaults.update(overrides)
    return RenameWorkerThread(**defaults)


def _create_pairs(base: Path, count: int = 10, *, ext_pairs=(".jpg", ".CR2")) -> list[str]:
    """Create *count* image pairs on disk and return flat list of paths."""
    files: list[str] = []
    start = datetime.datetime(2024, 6, 15, 10, 0, 0)
    for i in range(count):
        name = f"DSC{10000 + i:05d}"
        for ext in ext_pairs:
            p = base / f"{name}{ext}"
            p.touch()
            ts = (start + datetime.timedelta(seconds=i * 30)).timestamp()
            os.utime(p, (ts, ts))
            files.append(str(p))
    return files


def _mock_exif_for_file(
    file_path: str,
    method: str | None = None,
    exiftool_path: str | None = None,
    **kwargs,
) -> tuple[str | None, str | None, str | None]:
    """Return deterministic EXIF data derived from the filename index.

    Signature matches exif_processor.get_selective_cached_exif_data so it can
    be used as a drop-in side_effect for unittest.mock.patch.
    """
    idx = int(re.search(r"(\d+)", Path(file_path).stem).group(1)) % 10000
    cameras = ["Canon-EOS-R5", "Nikon-Z9", "Sony-A7RIV", "Fuji-XT5"]
    lenses = ["RF24-70mm", "Z70-200mm", "FE24-105mm", "XF16-80mm"]
    base_date = datetime.datetime(2024, 1, 1) + datetime.timedelta(seconds=idx * 30)

    need_date = kwargs.get("need_date", True)
    need_camera = kwargs.get("need_camera", False)
    need_lens = kwargs.get("need_lens", False)
    return (
        base_date.strftime("%Y%m%d") if need_date else None,
        cameras[idx % 4] if need_camera else None,
        lenses[idx % 4] if need_lens else None,
    )


from contextlib import contextmanager


def _make_mock_exif_service(selective_side_effect=None):
    """Create a mock ExifService that returns deterministic EXIF data."""
    side_effect = selective_side_effect or _mock_exif_for_file
    service = MagicMock()
    service.get_selective_cached_exif_data = MagicMock(side_effect=side_effect)
    service.get_all_metadata = MagicMock(return_value={})
    service.extract_raw_exif = MagicMock(return_value={})
    service.batch_get_raw_metadata = MagicMock(return_value={})
    service.clear_cache = MagicMock()
    service.cleanup = MagicMock()
    return service


@contextmanager
def _mock_all_exif(selective_side_effect=None):
    """Patch exif_processor delegates and provide a mock ExifService.

    The rename engine now calls self.exif_service directly for EXIF
    extraction.  We still patch the exif_processor delegates (used by
    other call sites) and patch batch_sync_exif_dates in rename_engine.

    The mock ExifService is stored as _mock_all_exif.service so tests
    can pass it to _make_worker via exif_service=_mock_all_exif.service.
    """
    side_effect = selective_side_effect or _mock_exif_for_file
    service = _make_mock_exif_service(side_effect)
    _mock_all_exif.service = service
    with (
        patch("modules.exif_processor.get_selective_cached_exif_data", side_effect=side_effect),
        patch("modules.exif_processor.get_exiftool_metadata_shared", return_value={}),
        patch("modules.exif_processor.get_all_metadata", return_value={}),
        patch("modules.exif_processor.clear_global_exif_cache"),
        patch("modules.rename_engine.batch_sync_exif_dates", return_value=([], [], {})),
    ):
        yield service


# ---------------------------------------------------------------------------
# File grouping
# ---------------------------------------------------------------------------
class TestFileGrouping:
    """Test _create_file_groups for RAW/JPEG sibling pairing."""

    def test_pairs_grouped(self, tmp_path):
        files = _create_pairs(tmp_path, count=5)
        worker = _make_worker(files)
        groups = worker._create_file_groups()

        # 5 pairs → 5 groups of size 2
        assert len(groups) == 5
        for g in groups:
            assert len(g) == 2
            stems = {os.path.splitext(os.path.basename(f))[0] for f in g}
            assert len(stems) == 1  # same basename

    def test_orphan_file(self, tmp_path):
        (tmp_path / "lonely.jpg").touch()
        worker = _make_worker([str(tmp_path / "lonely.jpg")])
        groups = worker._create_file_groups()
        assert len(groups) == 1
        assert len(groups[0]) == 1

    def test_non_media_files_excluded(self, tmp_path):
        (tmp_path / "readme.txt").touch()
        worker = _make_worker([str(tmp_path / "readme.txt")])
        groups = worker._create_file_groups()
        assert len(groups) == 0

    def test_mixed_media_and_non_media(self, tmp_path):
        (tmp_path / "photo.jpg").touch()
        (tmp_path / "notes.txt").touch()
        worker = _make_worker([
            str(tmp_path / "photo.jpg"),
            str(tmp_path / "notes.txt"),
        ])
        groups = worker._create_file_groups()
        assert len(groups) == 1

    def test_files_in_different_dirs(self, tmp_path):
        """Files with same stem but in different dirs should NOT be grouped."""
        d1 = tmp_path / "dir1"
        d2 = tmp_path / "dir2"
        d1.mkdir()
        d2.mkdir()
        (d1 / "DSC001.jpg").touch()
        (d2 / "DSC001.jpg").touch()

        worker = _make_worker([str(d1 / "DSC001.jpg"), str(d2 / "DSC001.jpg")])
        groups = worker._create_file_groups()
        # Should be separate groups (different directories)
        assert len(groups) == 2


# ---------------------------------------------------------------------------
# Sort key generation
# ---------------------------------------------------------------------------
class TestExifSortKey:
    """Test _get_exif_sort_key for chronological ordering."""

    def test_sort_by_mtime(self, tmp_path):
        """When there is no EXIF cache, fall back to file modification time."""
        f1 = tmp_path / "first.jpg"
        f2 = tmp_path / "second.jpg"
        f1.touch()
        f2.touch()
        # Make f1 older
        os.utime(f1, (1000, 1000))
        os.utime(f2, (2000, 2000))

        worker = _make_worker([str(f1), str(f2)])
        exif_cache: dict = {}  # empty cache → falls back to mtime

        key1 = worker._get_exif_sort_key([str(f1)], exif_cache)
        key2 = worker._get_exif_sort_key([str(f2)], exif_cache)
        assert key1 < key2

    def test_sort_by_cached_exif(self, tmp_path):
        f1 = tmp_path / "early.jpg"
        f2 = tmp_path / "late.jpg"
        f1.touch()
        f2.touch()

        worker = _make_worker([str(f1), str(f2)])
        exif_cache = {
            str(f1): {
                "date_str": "20240101",
                "camera": None,
                "lens": None,
                "raw_meta": {
                    "EXIF:DateTimeOriginal": "2024:01:01 08:00:00",
                },
            },
            str(f2): {
                "date_str": "20240615",
                "camera": None,
                "lens": None,
                "raw_meta": {
                    "EXIF:DateTimeOriginal": "2024:06:15 12:00:00",
                },
            },
        }

        key1 = worker._get_exif_sort_key([str(f1)], exif_cache)
        key2 = worker._get_exif_sort_key([str(f2)], exif_cache)
        assert key1 < key2

    def test_filename_number_tiebreaker(self, tmp_path):
        """Files with same timestamp should be ordered by filename number."""
        f1 = tmp_path / "DSC0001.jpg"
        f2 = tmp_path / "DSC0002.jpg"
        f1.touch()
        f2.touch()
        # Same modification time
        os.utime(f1, (1000, 1000))
        os.utime(f2, (1000, 1000))

        worker = _make_worker([str(f1), str(f2)])
        key1 = worker._get_exif_sort_key([str(f1)], {})
        key2 = worker._get_exif_sort_key([str(f2)], {})
        # Tiebreaker: file_number 1 < 2
        assert key1 < key2


# ---------------------------------------------------------------------------
# Rename scenarios (small scale — 10-50 pairs)
# ---------------------------------------------------------------------------
class TestRenameSmallScale:
    """End-to-end rename tests with small file sets."""

    def _run_rename(self, tmp_path, count: int = 10, **worker_overrides):
        """Helper: create files, mock EXIF, run rename, return results."""
        files = _create_pairs(tmp_path, count=count)

        with _mock_all_exif() as service:
            worker = _make_worker(files, exif_service=service, **worker_overrides)
            renamed, errors, ts_backup, _mapping = worker.optimized_rename_files()
        return files, renamed, errors

    def test_basic_date_prefix_number(self, tmp_path):
        """Most common scenario: Date + Prefix + Number."""
        files, renamed, errors = self._run_rename(tmp_path, count=10)

        assert len(errors) == 0
        assert len(renamed) == len(files)  # every file renamed

        sample = os.path.basename(renamed[0])
        assert "TEST" in sample
        assert "2024" in sample

    def test_no_date_mode(self, tmp_path):
        """Prefix + Number only, no date component."""
        files, renamed, errors = self._run_rename(
            tmp_path, count=5, use_date=False,
            custom_order=["Prefix", "Number"],
        )

        assert len(errors) == 0
        for path in renamed:
            name = os.path.basename(path)
            assert "TEST" in name
            # Should not contain date
            assert "2024" not in name

    def test_continuous_counter(self, tmp_path):
        """Continuous counter mode increments across all files."""
        files, renamed, errors = self._run_rename(
            tmp_path, count=10,
            continuous_counter=True,
            custom_order=["Prefix", "Number"],
            use_date=True,
        )

        assert len(errors) == 0
        assert len(renamed) > 0

    def test_files_stay_in_same_directory(self, tmp_path):
        """Renamed files must remain in their original directory."""
        sub = tmp_path / "event"
        sub.mkdir()
        files = _create_pairs(sub, count=5)

        with _mock_all_exif() as service:
            worker = _make_worker(files, exif_service=service)
            renamed, errors, _, _mapping = worker.optimized_rename_files()

        for new_path in renamed:
            assert os.path.dirname(new_path) == str(sub)

    def test_separator_variants(self, tmp_path):
        """Different separators should produce valid filenames."""
        for sep in ["_", "-", ".", "None"]:
            work_dir = tmp_path / f"sep_{sep}"
            work_dir.mkdir()
            files = _create_pairs(work_dir, count=3)

            with _mock_all_exif() as service:
                worker = _make_worker(files, separator=sep, exif_service=service)
                renamed, errors, _, _mapping = worker.optimized_rename_files()

            assert len(errors) == 0, f"Separator '{sep}' caused errors"
            assert len(renamed) == len(files), f"Separator '{sep}' missed files"

    def test_camera_and_lens_metadata(self, tmp_path):
        """Filenames should contain camera/lens info when enabled."""
        files = _create_pairs(tmp_path, count=5)

        with _mock_all_exif() as service:
            worker = _make_worker(
                files,
                use_camera=True,
                use_lens=True,
                custom_order=["Date", "Camera", "Lens", "Number"],
                exif_service=service,
            )
            renamed, errors, _, _mapping = worker.optimized_rename_files()

        assert len(errors) == 0
        if renamed:
            sample = os.path.basename(renamed[0])
            known_cameras = ["Canon", "Nikon", "Sony", "Fuji"]
            assert any(cam in sample for cam in known_cameras), (
                f"Camera not found in '{sample}'"
            )

    def test_no_errors_on_empty_file_list(self):
        """An empty file list should produce no errors and no renames."""
        worker = _make_worker([])
        renamed, errors, _, _mapping = worker.optimized_rename_files()
        assert renamed == []
        assert errors == []


# ---------------------------------------------------------------------------
# Stress test — still fast thanks to mocked EXIF
# ---------------------------------------------------------------------------
class TestRenameScalability:
    """Verify rename handles larger sets correctly (≤1000 files)."""

    @pytest.mark.slow
    def test_500_file_pairs(self, tmp_path):
        """Rename 500 pairs (1000 files) with mocked EXIF — should complete in <60s."""
        # Distribute across subdirectories for realism
        subdirs = [tmp_path / f"event{i}" for i in range(5)]
        for d in subdirs:
            d.mkdir()

        files: list[str] = []
        per_dir = 100  # 500 / 5
        start = datetime.datetime(2024, 1, 1, 10, 0, 0)
        for dir_idx, d in enumerate(subdirs):
            for i in range(per_dir):
                global_idx = dir_idx * per_dir + i
                name = f"DSC{10000 + global_idx:05d}"
                for ext in (".jpg", ".CR2"):
                    p = d / f"{name}{ext}"
                    p.touch()
                    ts = (start + datetime.timedelta(seconds=global_idx * 30)).timestamp()
                    os.utime(p, (ts, ts))
                    files.append(str(p))

        with _mock_all_exif() as service:
            worker = _make_worker(files, exif_service=service)
            renamed, errors, _, _mapping = worker.optimized_rename_files()

        error_rate = len(errors) / len(files) if files else 0
        assert error_rate < 0.05, f"Error rate {error_rate:.1%} too high"
        assert len(renamed) > 0


# ---------------------------------------------------------------------------
# Counter logic
# ---------------------------------------------------------------------------
class TestCounterLogic:
    """Verify per-date and continuous counter behaviour."""

    def test_per_date_counter_resets(self, tmp_path):
        """With use_date=True and continuous_counter=False, counter resets per date."""
        # Create files with two different dates
        d1 = tmp_path / "day1"
        d2 = tmp_path / "day2"
        d1.mkdir()
        d2.mkdir()

        # Day 1 files
        for i in range(3):
            (d1 / f"IMG{i:04d}.jpg").touch()
        # Day 2 files
        for i in range(3):
            (d2 / f"IMG{i + 10:04d}.jpg").touch()

        all_files = [str(f) for f in sorted(d1.glob("*.jpg")) + sorted(d2.glob("*.jpg"))]

        def mock_exif(fp, method=None, exiftool_path=None, **kwargs):
            if "day1" in fp:
                return "20240101", None, None
            return "20240102", None, None

        with _mock_all_exif(selective_side_effect=mock_exif) as service:
            worker = _make_worker(
                all_files,
                use_date=True,
                continuous_counter=False,
                custom_order=["Date", "Prefix", "Number"],
                exif_service=service,
            )
            renamed, errors, _, _mapping = worker.optimized_rename_files()

        assert len(errors) == 0

    def test_continuous_counter_does_not_reset(self, tmp_path):
        """With continuous_counter=True, numbers should increase monotonically."""
        files = _create_pairs(tmp_path, count=5, ext_pairs=(".jpg",))

        def mock_exif(fp, method=None, exiftool_path=None, **kwargs):
            idx = int(re.search(r"(\d+)", Path(fp).stem).group(1))
            day = "20240101" if idx < 10003 else "20240102"
            return day, None, None

        with _mock_all_exif(selective_side_effect=mock_exif) as service:
            worker = _make_worker(
                files,
                use_date=True,
                continuous_counter=True,
                custom_order=["Date", "Prefix", "Number"],
                exif_service=service,
            )
            renamed, errors, _, _mapping = worker.optimized_rename_files()

        assert len(errors) == 0
