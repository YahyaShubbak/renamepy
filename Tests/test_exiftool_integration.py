#!/usr/bin/env python3
"""
Integration tests against a real ExifTool (skipped if none is installed).

These cover behaviour that mocked tests cannot: how ExifTool applies tag
assignments across files, conditional writes, UTF-8 file names, and the
round trip of the EXIF time-shift backup.
"""

import os
import sys
import datetime

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.exif_processor import find_exiftool_path

EXIFTOOL = find_exiftool_path()
pytestmark = pytest.mark.skipif(not EXIFTOOL, reason="ExifTool not installed")


def _make_jpeg(path, date_time_original=None):
    """Create a small JPEG (optionally with EXIF:DateTimeOriginal)."""
    from PyQt6.QtGui import QImage, QColor
    from modules.exif_service_new import run_exiftool_on_file

    image = QImage(8, 8, QImage.Format.Format_RGB32)
    image.fill(QColor("red"))
    assert image.save(str(path), "JPEG")
    if date_time_original:
        result = run_exiftool_on_file(
            EXIFTOOL, ["-q", "-overwrite_original", f"-EXIF:DateTimeOriginal={date_time_original}"], str(path)
        )
        assert result.returncode == 0, result.stderr
    return str(path)


@pytest.fixture
def service():
    from modules.exif_service_new import ExifService
    svc = ExifService(EXIFTOOL)
    yield svc
    svc.cleanup()


class TestOriginalFilenameMetadata:

    def test_each_file_keeps_its_own_original_name(self, tmp_path):
        from modules.exif_undo_manager import (
            batch_write_original_filenames, batch_get_original_filenames,
        )
        files = [(_make_jpeg(tmp_path / f"renamed_{i}.jpg"), f"DSC{i:05d}.JPG") for i in range(3)]

        successes, errors = batch_write_original_filenames(files, EXIFTOOL)

        assert errors == []
        assert len(successes) == 3
        stored = batch_get_original_filenames([p for p, _ in files], EXIFTOOL)
        assert stored == {path: original for path, original in files}

    def test_existing_original_name_is_kept(self, tmp_path):
        from modules.exif_undo_manager import (
            batch_write_original_filenames, get_original_filename_from_exif,
        )
        path = _make_jpeg(tmp_path / "a.jpg")
        batch_write_original_filenames([(path, "FIRST.JPG")], EXIFTOOL)
        successes, errors = batch_write_original_filenames([(path, "SECOND.JPG")], EXIFTOOL)
        assert successes == [path] and errors == []
        assert get_original_filename_from_exif(path, EXIFTOOL) == "FIRST.JPG"

    def test_unicode_file_name(self, tmp_path):
        from modules.exif_undo_manager import (
            batch_write_original_filenames, get_original_filename_from_exif,
        )
        path = _make_jpeg(tmp_path / "Urlaub Müller 😀.jpg")
        successes, errors = batch_write_original_filenames([(path, "IMG_Ü01.JPG")], EXIFTOOL)
        assert errors == []
        assert get_original_filename_from_exif(path, EXIFTOOL) == "IMG_Ü01.JPG"


class TestReading:

    def test_batch_read_unicode_name(self, tmp_path, service):
        path = _make_jpeg(tmp_path / "Café 😀.jpg", "2024:05:01 10:20:30")
        meta = service.batch_get_raw_metadata([path])[path]
        assert service.parse_date_from_raw(meta) == "20240501"


class TestSharedProcessAndThreads:
    """Regression: on Linux PyExifTool ties ExifTool's life to the *thread*
    that started it (PR_SET_PDEATHSIG). A shared process started by a worker
    thread died with it, and a read in progress then hung forever."""

    def _in_thread(self, func):
        import threading
        result = {}
        thread = threading.Thread(target=lambda: result.update(value=func()))
        thread.start()
        thread.join(timeout=60)
        assert not thread.is_alive(), "worker thread hung"
        return result["value"]

    def test_worker_does_not_start_shared_process(self, tmp_path, service):
        path = _make_jpeg(tmp_path / "a.jpg", "2024:05:01 10:00:00")
        meta = self._in_thread(lambda: service.batch_get_raw_metadata([path]))
        assert service.parse_date_from_raw(meta[path]) == "20240501"
        assert service._exiftool_instance is None

    def test_shared_process_survives_worker(self, tmp_path, service):
        import time
        path = _make_jpeg(tmp_path / "a.jpg", "2024:05:01 10:00:00")
        service.extract_raw_exif(path)  # main thread starts the shared process
        process = service._exiftool_instance._process
        self._in_thread(lambda: service.batch_get_raw_metadata([path]))
        time.sleep(0.3)
        assert process.poll() is None
        assert service.extract_raw_exif(path)

    def test_concurrent_cold_reads(self, tmp_path, service):
        import threading
        paths = [_make_jpeg(tmp_path / f"{i}.jpg", "2024:05:01 10:00:00") for i in range(4)]
        results = {}
        threads = [threading.Thread(target=lambda p=p: results.update({p: service.extract_raw_exif(p)}))
                   for p in paths]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=60)
        assert not any(t.is_alive() for t in threads), "a reader thread hung"
        assert all(results[p].get("SourceFile") for p in paths)

    def test_unreadable_file_does_not_break_batch(self, tmp_path, service):
        good = _make_jpeg(tmp_path / "good.jpg", "2024:05:01 10:00:00")
        bad = tmp_path / "bad.jpg"
        bad.write_bytes(b"not a jpeg")
        service.extract_raw_exif(good)
        process = service._exiftool_instance._process
        meta = service.batch_get_raw_metadata([good, str(bad)])
        assert service.parse_date_from_raw(meta[good]) == "20240501"
        assert service._exiftool_instance._process is process  # not restarted


class TestExifTimeShiftRoundTrip:

    def test_backup_and_restore(self, tmp_path, service):
        import subprocess
        from modules.exif_processor import restore_exif_timestamps
        from modules.dialogs.exif_time_shift_dialog import BACKUP_DATE_FIELDS

        path = _make_jpeg(tmp_path / "a.jpg", "2024:05:01 10:00:00")
        meta = service.extract_raw_exif(path)
        backup = {f: meta[f] for f in BACKUP_DATE_FIELDS if f in meta}
        assert backup == {"EXIF:DateTimeOriginal": "2024:05:01 10:00:00"}

        assert subprocess.run([EXIFTOOL, "-q", "-overwrite_original", "-AllDates+=1:00:00", path]).returncode == 0
        service.clear_cache()
        assert service.parse_datetime_from_raw(service.extract_raw_exif(path)).hour == 11

        ok, msg = restore_exif_timestamps(path, backup, EXIFTOOL)
        assert ok, msg
        restored = service.parse_datetime_from_raw(service.extract_raw_exif(path))
        assert restored == datetime.datetime(2024, 5, 1, 10, 0, 0)


    def test_worker_shift_and_restore_unicode_name(self, tmp_path, service):
        from modules import exif_processor
        from modules.exif_processor import restore_exif_timestamps
        from modules.dialogs.exif_time_shift_dialog import TimeShiftWorker

        path = _make_jpeg(tmp_path / "Straße 😀.jpg", "2024:05:01 10:00:00")
        exif_processor.set_default_exif_service(service)
        try:
            worker = TimeShiftWorker([path], 2, 30, "backward", EXIFTOOL)
            results = []
            worker.finished_signal.connect(lambda *args: results.append(args))
            worker.run()
        finally:
            exif_processor.set_default_exif_service(None)

        success_count, errors, backup = results[0]
        assert (success_count, errors) == (1, [])
        service.clear_cache()
        shifted = service.parse_datetime_from_raw(service.extract_raw_exif(path))
        assert shifted == datetime.datetime(2024, 5, 1, 7, 30, 0)

        ok, msg = restore_exif_timestamps(path, backup[path], EXIFTOOL)
        assert ok, msg
        service.clear_cache()
        assert service.parse_datetime_from_raw(service.extract_raw_exif(path)) == datetime.datetime(2024, 5, 1, 10, 0, 0)


    def test_worker_mixed_chunk(self, tmp_path, service):
        from modules import exif_processor
        from modules.dialogs.exif_time_shift_dialog import TimeShiftWorker

        good = [_make_jpeg(tmp_path / f"ok_{i}.jpg", "2024:05:01 10:00:00") for i in range(3)]
        no_dates = _make_jpeg(tmp_path / "no_dates.jpg")
        broken = tmp_path / "broken.jpg"
        broken.write_bytes(b"not a jpeg")
        exif_processor.set_default_exif_service(service)
        try:
            worker = TimeShiftWorker(good + [no_dates, str(broken)], 1, 0, "forward", EXIFTOOL)
            results = []
            worker.finished_signal.connect(lambda *args: results.append(args))
            worker.run()
        finally:
            exif_processor.set_default_exif_service(None)

        success_count, errors, backup = results[0]
        assert success_count == 3
        assert {os.path.basename(p) for p, _ in errors} == {"no_dates.jpg", "broken.jpg"}
        assert set(backup) == set(good)
        for path in good:
            assert service.parse_datetime_from_raw(service.extract_raw_exif(path)).hour == 11


class TestRenameWithMetadata:

    def test_rename_stores_original_names(self, tmp_path, service):
        from modules.rename_engine import RenameWorkerThread
        from modules.exif_undo_manager import batch_get_original_filenames

        a = _make_jpeg(tmp_path / "DSC00001.JPG", "2024:05:01 10:00:00")
        b = _make_jpeg(tmp_path / "DSC00002.JPG", "2024:05:01 11:00:00")
        worker = RenameWorkerThread(
            files=[a, b], camera_prefix="", additional="Trip", use_camera=False,
            use_lens=False, exif_method="exiftool", separator="_",
            exiftool_path=EXIFTOOL, custom_order=["Date", "Additional", "Number"],
            date_format="YYYY-MM-DD", use_date=True, continuous_counter=False,
            selected_metadata={}, sync_exif_date=False, exif_service=service,
            save_original_to_exif=True,
        )
        renamed, errors, _ts, _mapping = worker.optimized_rename_files()

        assert errors == []
        assert sorted(os.path.basename(p) for p in renamed) == [
            "2024-05-01_Trip_001.JPG", "2024-05-01_Trip_002.JPG",
        ]
        stored = batch_get_original_filenames(renamed, EXIFTOOL)
        assert sorted(stored.values()) == ["DSC00001.JPG", "DSC00002.JPG"]
        by_new = {os.path.basename(k): v for k, v in stored.items()}
        assert by_new["2024-05-01_Trip_001.JPG"] == "DSC00001.JPG"
