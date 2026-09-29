#!/usr/bin/env python3
"""
Regression tests for data-integrity, crash and security fixes:

- rename errors are (path, message) tuples and the result dialog handles them
- loading the same files twice does not duplicate them
- camera/lens are resolved per file, never frozen to the first file's value
- original names from metadata are validated before a restore
- backups keep the *first* (original) values across repeated operations
- undo only forgets entries that were restored successfully
- renames are journaled before any file is moved
- renames never overwrite an existing file
- exposure times round correctly, video dates are read
"""

import os
import sys
import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules import backup_journal
from modules.backup_journal import PersistedBackupDict, load_journal
from modules.exif_service_new import ExifService, format_exposure_time, parse_exif_datetime
from modules.file_utilities import (
    is_safe_restore_name, safe_rename, scan_directory_recursive, is_case_variant,
)
from modules.rename_engine import RenameWorkerThread


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _make_worker(files, **overrides):
    defaults = dict(
        files=files,
        camera_prefix="",
        additional="",
        use_camera=False,
        use_lens=False,
        exif_method="exiftool",
        separator="_",
        exiftool_path=None,
        custom_order=["Date", "Number"],
        date_format="YYYY-MM-DD",
        use_date=True,
        continuous_counter=False,
        selected_metadata={},
        sync_exif_date=False,
        exif_service=None,
    )
    defaults.update(overrides)
    return RenameWorkerThread(**defaults)


def _raw_meta_service(meta_by_name):
    """Mock ExifService whose batch read returns meta_by_name[basename]."""
    service = MagicMock()
    service.batch_get_raw_metadata = MagicMock(
        side_effect=lambda paths, chunk_size=50: {
            p: meta_by_name.get(os.path.basename(p), {}) for p in paths
        }
    )
    service.get_selective_cached_exif_data = MagicMock(return_value=(None, None, None))
    service.get_all_metadata = MagicMock(return_value={})
    return service


def _touch(path: Path, when: datetime.datetime | None = None) -> str:
    path.write_bytes(b"x")
    if when is not None:
        ts = when.timestamp()
        os.utime(path, (ts, ts))
    return str(path)


# ---------------------------------------------------------------------------
# Rename results: error tuples must not crash the result dialog
# ---------------------------------------------------------------------------
class TestRenameResultErrors:

    def test_engine_reports_errors_as_tuples(self, tmp_path):
        a = _touch(tmp_path / "a.jpg", datetime.datetime(2024, 5, 1, 10))
        worker = _make_worker([a, a], exif_method=None)  # same file twice
        renamed, errors, _ts, _mapping = worker.optimized_rename_files()
        assert errors, "renaming the same file twice must report an error"
        assert all(isinstance(e, tuple) and len(e) == 2 for e in errors)

    def test_result_dialog_accepts_tuples(self, qapp, tmp_path):
        from PyQt6.QtWidgets import QWidget, QDialog, QPlainTextEdit
        from modules.main_application import FileRenamerApp

        shown = {}

        def fake_exec(dialog):
            shown["text"] = dialog.findChild(QPlainTextEdit).toPlainText()
            return 0

        from modules.theme_manager import ThemeManager

        class _Parent(QWidget):
            _label_style = FileRenamerApp._label_style

        parent = _Parent()
        parent.theme_manager = ThemeManager()
        with patch.object(QDialog, "exec", fake_exec):
            FileRenamerApp._show_rename_results(
                parent, ["/x/new.jpg"], [("/x/a.jpg", "boom"), ("/x/b.jpg", "Timestamp sync: no date")]
            )
        assert "a.jpg: boom" in shown["text"]
        assert "b.jpg: Timestamp sync: no date" in shown["text"]

    def test_sync_errors_are_reported(self, tmp_path):
        a = _touch(tmp_path / "a.jpg", datetime.datetime(2024, 5, 1, 10))
        worker = _make_worker([a], exif_method=None, sync_exif_date=True)
        with patch("modules.rename_engine.batch_sync_exif_dates",
                   return_value=([], [(a, "No EXIF date found in file")], {})):
            _renamed, errors, _ts, _mapping = worker.optimized_rename_files()
        assert (a, "Timestamp sync: No EXIF date found in file") in errors


# ---------------------------------------------------------------------------
# Loading files
# ---------------------------------------------------------------------------
class TestFileLoading:

    def _manager(self):
        from modules.ui.file_list_manager import FileListManager
        parent = MagicMock()
        parent.files = []
        return FileListManager(parent), parent

    def test_same_folder_twice_is_not_duplicated(self, tmp_path):
        for i in range(3):
            _touch(tmp_path / f"DSC{i:04d}.JPG")
        manager, parent = self._manager()
        manager.add_files_to_list(scan_directory_recursive(str(tmp_path)))
        manager.add_files_to_list(scan_directory_recursive(str(tmp_path)))
        assert len(parent.files) == 3

    def test_adding_appends(self, tmp_path):
        a = _touch(tmp_path / "a.jpg")
        b = _touch(tmp_path / "b.jpg")
        manager, parent = self._manager()
        manager.add_files_to_list([a])
        manager.add_files_to_list([b])  # e.g. drag & drop after a button
        assert parent.files == [a, b]

    def test_scan_skips_system_artifacts(self, tmp_path):
        _touch(tmp_path / "DSC0001.ARW")
        _touch(tmp_path / "._DSC0001.ARW")
        (tmp_path / "@eaDir").mkdir()
        _touch(tmp_path / "@eaDir" / "SYNOPHOTO_THUMB_XL.jpg")
        (tmp_path / ".thumbnails").mkdir()
        _touch(tmp_path / ".thumbnails" / "t.jpg")
        found = [os.path.basename(p) for p in scan_directory_recursive(str(tmp_path))]
        assert found == ["DSC0001.ARW"]


# ---------------------------------------------------------------------------
# Camera / lens are per file
# ---------------------------------------------------------------------------
class TestPerFileCamera:

    def _dialog_manager(self):
        from modules.ui.metadata_dialog_manager import MetadataDialogManager
        parent = MagicMock()
        parent.selected_metadata = {}
        parent.camera_model_label.text.return_value = "(ILCE-7RM3)"
        parent.lens_model_label.text.return_value = "(FE-24-70mm)"
        parent.checkbox_camera.isChecked.return_value = True
        parent.checkbox_lens.isChecked.return_value = True
        return MetadataDialogManager(parent), parent

    def test_camera_checkbox_does_not_freeze_value(self):
        manager, parent = self._dialog_manager()
        manager.on_camera_checkbox_changed()
        manager.on_lens_checkbox_changed()
        assert "camera" not in parent.selected_metadata
        assert "lens" not in parent.selected_metadata

    def test_dialog_camera_checkbox_toggles_main_checkbox(self):
        manager, parent = self._dialog_manager()
        manager.on_metadata_checkbox_changed("camera", "Sony ILCE-7RM3", True, user_action=True)
        parent.checkbox_camera.setChecked.assert_called_once_with(True)
        assert "camera" not in parent.selected_metadata

    def test_metadata_dialog_widget_builds(self, qapp, tmp_path):
        """Regression: info-only rows (file, size, flash, ...) crashed with
        UnboundLocalError; only per-file fields get a checkbox."""
        from PyQt6.QtWidgets import QCheckBox, QLabel
        manager, parent = self._dialog_manager()
        parent.exiftool_path = None
        parent.checkbox_date.isChecked.return_value = True
        photo = tmp_path / "DSC0001.JPG"
        photo.write_bytes(b"x")
        info = "\n".join([
            "File:FileType: JPEG", "EXIF:Make: Sony", "EXIF:Model: ILCE-7RM3",
            "EXIF:DateTimeOriginal: 2024:05:01 10:00:00", "EXIF:ISO: 400",
            "EXIF:ExposureTime: 0.0166666666666667", "EXIF:Flash: 16", "EXIF:MeteringMode: 5",
        ])
        widget = manager.create_essential_metadata_widget(info, str(photo))
        labels = [label.text() for label in widget.findChildren(QLabel)]
        assert "Shutter: 1/60s" in labels
        assert "Flash: No" in labels
        assert len(widget.findChildren(QCheckBox)) == 4  # camera, date, iso, shutter

    def test_dialog_shooting_setting_is_a_flag(self):
        manager, parent = self._dialog_manager()
        manager.on_metadata_checkbox_changed("iso", "400", True, user_action=True)
        assert parent.selected_metadata["iso"] is True
        manager.on_metadata_checkbox_changed("iso", "400", False, user_action=True)
        assert "iso" not in parent.selected_metadata

    def test_mixed_cameras_get_their_own_model(self, tmp_path):
        a = _touch(tmp_path / "IMG_0001.JPG")
        b = _touch(tmp_path / "DSC_0002.JPG")
        service = _raw_meta_service({
            "IMG_0001.JPG": {"EXIF:DateTimeOriginal": "2024:05:01 10:00:00", "EXIF:Model": "iPhone 15"},
            "DSC_0002.JPG": {"EXIF:DateTimeOriginal": "2024:05:01 11:00:00", "EXIF:Model": "Nikon Z9"},
        })
        worker = _make_worker([a, b], use_camera=True, exif_service=service,
                              custom_order=["Date", "Camera", "Number"])
        renamed, errors, _ts, _mapping = worker.optimized_rename_files()
        names = sorted(os.path.basename(p) for p in renamed)
        assert errors == []
        assert names == ["2024-05-01_Nikon-Z9_002.JPG", "2024-05-01_iPhone-15_001.JPG"]


# ---------------------------------------------------------------------------
# Restore-name validation (untrusted metadata)
# ---------------------------------------------------------------------------
class TestRestoreNameValidation:

    @pytest.mark.parametrize("name", [
        "../x.jpg", "..\\..\\Startup\\x.jpg", "/etc/x.jpg", "C:\\x.jpg", "sub/x.jpg",
        "x.bat", "", " x.jpg", "..", "a\x00.jpg", "a:b.jpg",
    ])
    def test_rejects_unsafe(self, name):
        assert is_safe_restore_name(name, "/photos/2024-05-01_001.jpg") is False

    @pytest.mark.parametrize("name", ["DSC00001.JPG", "IMG_1234.jpg", "Urlaub Müller (2).jpg"])
    def test_accepts_plain_names(self, name):
        assert is_safe_restore_name(name, "/photos/2024-05-01_001.jpg") is True

    def test_undo_rejects_ambiguous_and_unsafe_entries(self, tmp_path):
        from modules.handlers.undo_handler import UndoHandler
        handler = UndoHandler(MagicMock())
        d = str(tmp_path)
        candidates = [
            (os.path.join(d, "a.jpg"), "DSC0001.jpg"),
            (os.path.join(d, "b.jpg"), "DSC0001.jpg"),   # same claim -> ambiguous
            (os.path.join(d, "c.jpg"), "..\\evil.jpg"),  # unsafe
            (os.path.join(d, "d.jpg"), "DSC0004.jpg"),
        ]
        result = handler._validate_candidates(candidates)
        assert result == [(os.path.join(d, "d.jpg"), "DSC0004.jpg")]
        assert len(handler._rejected) == 3


# ---------------------------------------------------------------------------
# Backups: first (original) value wins
# ---------------------------------------------------------------------------
class TestBackupsKeepOriginals:

    def test_persisted_dict_loads_pending_entries(self):
        first = PersistedBackupDict("exif_backup")
        first["/p/a.jpg"] = {"EXIF:DateTimeOriginal": "2024:01:01 10:00:00"}
        second = PersistedBackupDict("exif_backup")
        assert second.record_original("/p/a.jpg", {"EXIF:DateTimeOriginal": "2024:01:01 11:00:00"}) is False
        assert second.record_original("/p/b.jpg", {"EXIF:DateTimeOriginal": "2024:01:01 12:00:00"}) is True
        journal = load_journal()["exif_backup"]
        assert journal["/p/a.jpg"]["EXIF:DateTimeOriginal"] == "2024:01:01 10:00:00"
        assert "/p/b.jpg" in journal

    def test_second_sync_keeps_original_timestamps(self, tmp_path):
        from modules.exif_processor import batch_sync_exif_dates
        original = datetime.datetime(2020, 1, 1, 12, 0, 0)
        f = _touch(tmp_path / "a.jpg", original)

        def options(dt):
            return {"creation": False, "modification": True, "access": True,
                    "use_custom": True, "custom_dt": dt}

        batch_sync_exif_dates([f], options=options(datetime.datetime(2021, 1, 1)))
        _s, errors, backup = batch_sync_exif_dates([f], options=options(datetime.datetime(2022, 1, 1)))

        assert errors == []
        assert backup[f]["mtime"] == pytest.approx(original.timestamp())
        assert load_journal()["timestamp_backup"][f]["mtime"] == pytest.approx(original.timestamp())
        assert os.path.getmtime(f) == pytest.approx(datetime.datetime(2022, 1, 1).timestamp())

    def test_time_shift_skips_file_without_backup(self, monkeypatch):
        from modules.dialogs.exif_time_shift_dialog import TimeShiftWorker
        run = MagicMock()
        monkeypatch.setattr("subprocess.run", run)
        monkeypatch.setattr("modules.exif_processor.get_exiftool_metadata_batch",
                            lambda paths, *a, **k: {p: {} for p in paths})
        worker = TimeShiftWorker(["/p/a.jpg"], 1, 0, "forward", "/fake/exiftool")
        results = []
        worker.finished_signal.connect(lambda *args: results.append(args))
        worker.run()
        success_count, errors, _backup = results[0]
        assert success_count == 0
        assert "no backup" in errors[0][1]
        run.assert_not_called()

    def test_second_time_shift_keeps_first_backup(self, monkeypatch):
        from modules.dialogs.exif_time_shift_dialog import TimeShiftWorker
        original = {"EXIF:DateTimeOriginal": "2024:01:01 10:00:00"}
        PersistedBackupDict("exif_backup")["/p/a.jpg"] = original
        monkeypatch.setattr("subprocess.run", MagicMock(return_value=MagicMock(returncode=0, stderr="")))
        # current dates (after an earlier shift), then the result of this shift
        reads = iter(["2024:01:01 11:00:00", "2024:01:01 12:00:00"])
        monkeypatch.setattr("modules.exif_processor.get_exiftool_metadata_batch",
                            lambda paths, *a, **k: {p: {"EXIF:DateTimeOriginal": next(reads)} for p in paths})
        worker = TimeShiftWorker(["/p/a.jpg"], 1, 0, "forward", "/fake/exiftool")
        results = []
        worker.finished_signal.connect(lambda *args: results.append(args))
        worker.run()
        assert results[0][0] == 1
        assert results[0][2]["/p/a.jpg"] == original
        assert load_journal()["exif_backup"]["/p/a.jpg"] == original


    def test_time_shift_one_exiftool_call_per_chunk(self, monkeypatch):
        from modules.dialogs.exif_time_shift_dialog import TimeShiftWorker
        run = MagicMock(return_value=MagicMock(returncode=0, stderr="Error: locked - /p/b.jpg"))
        monkeypatch.setattr("subprocess.run", run)
        reads = iter([
            {"/p/a.jpg": {"EXIF:DateTimeOriginal": "2024:01:01 10:00:00"},
             "/p/b.jpg": {"EXIF:DateTimeOriginal": "2024:01:01 10:00:00"}},
            {"/p/a.jpg": {"EXIF:DateTimeOriginal": "2024:01:01 10:30:00"},
             "/p/b.jpg": {"EXIF:DateTimeOriginal": "2024:01:01 10:00:00"}},  # b unchanged
        ])
        monkeypatch.setattr("modules.exif_processor.get_exiftool_metadata_batch", lambda *a, **k: next(reads))
        worker = TimeShiftWorker(["/p/a.jpg", "/p/b.jpg"], 0, 30, "forward", "/fake/exiftool")
        results = []
        worker.finished_signal.connect(lambda *args: results.append(args))
        worker.run()
        success_count, errors, backup = results[0]
        assert run.call_count == 1
        assert success_count == 1
        assert errors == [("/p/b.jpg", "Error: locked - /p/b.jpg")]
        assert list(backup) == ["/p/a.jpg"]
        assert list(load_journal()["exif_backup"]) == ["/p/a.jpg"]


# ---------------------------------------------------------------------------
# Undo keeps entries that could not be restored
# ---------------------------------------------------------------------------
class TestUndoKeepsFailures:

    def test_failed_timestamp_restore_keeps_backup(self, tmp_path):
        from modules.handlers.undo_handler import UndoHandler
        present = _touch(tmp_path / "present.jpg", datetime.datetime(2024, 1, 1))
        missing = str(tmp_path / "missing.jpg")
        times = {"atime": 1.0e9, "mtime": 1.0e9, "ctime": 1.0e9}
        app = MagicMock()
        app.timestamp_backup = {present: dict(times), missing: dict(times)}
        app.exif_backup = {}
        backup_journal.save_backup("timestamp_backup", dict(app.timestamp_backup))

        errors = UndoHandler(app)._restore_all_timestamps()

        assert len(errors) == 1 and "missing.jpg" in errors[0]
        assert list(app.timestamp_backup) == [missing]
        assert list(load_journal()["timestamp_backup"]) == [missing]
        assert os.path.getmtime(present) == pytest.approx(1.0e9)

    def test_failed_name_restore_keeps_mapping(self, tmp_path):
        from modules.handlers.undo_handler import UndoHandler
        a = _touch(tmp_path / "2024_001.jpg")
        b = _touch(tmp_path / "2024_002.jpg")
        _touch(tmp_path / "DSC0002.jpg")  # blocks restoring b
        app = MagicMock()
        app.files = [a, b]
        app.original_filenames = {a: "DSC0001.jpg", b: "DSC0002.jpg"}
        app.timestamp_backup = {}
        app.exif_backup = {}

        restored, errors = UndoHandler(app)._restore_filenames(list(app.original_filenames.items()))

        assert restored == [str(tmp_path / "DSC0001.jpg")]
        assert len(errors) == 1 and "already exists" in errors[0]
        assert app.original_filenames == {b: "DSC0002.jpg"}
        assert app.files == [str(tmp_path / "DSC0001.jpg"), b]


# ---------------------------------------------------------------------------
# Rename journal
# ---------------------------------------------------------------------------
class TestRenameJournal:

    def test_journal_maps_new_names_to_originals(self, tmp_path):
        a = _touch(tmp_path / "DSC0001.jpg", datetime.datetime(2024, 5, 1, 10))
        worker = _make_worker([a], exif_method=None)
        renamed, errors, _ts, _mapping = worker.optimized_rename_files()
        assert errors == []
        assert load_journal()["original_filenames"] == {renamed[0]: "DSC0001.jpg"}

    def test_second_rename_keeps_true_original(self, tmp_path):
        a = _touch(tmp_path / "2024-05-01_001.jpg", datetime.datetime(2024, 5, 1, 10))
        worker = _make_worker([a], exif_method=None, camera_prefix="X",
                              custom_order=["Date", "Prefix", "Number"],
                              prior_originals={a: "DSC0001.jpg"})
        renamed, errors, _ts, _mapping = worker.optimized_rename_files()
        assert errors == []
        assert load_journal()["original_filenames"] == {renamed[0]: "DSC0001.jpg"}

    def test_crash_mid_rename_leaves_undo_information(self, tmp_path):
        a = _touch(tmp_path / "DSC0001.jpg", datetime.datetime(2024, 5, 1, 10))
        b = _touch(tmp_path / "DSC0002.jpg", datetime.datetime(2024, 5, 1, 11))
        real_rename = safe_rename
        calls = []

        def crash_on_second(source, target):
            calls.append(source)
            if len(calls) == 2:
                raise KeyboardInterrupt  # process killed mid-batch
            real_rename(source, target)

        worker = _make_worker([a, b], exif_method=None)
        with patch("modules.rename_engine.safe_rename", side_effect=crash_on_second):
            with pytest.raises(KeyboardInterrupt):
                worker.optimized_rename_files()

        journal = load_journal()["original_filenames"]
        renamed_now = [p for p in journal if os.path.exists(p)]
        assert len(renamed_now) == 1
        assert journal[renamed_now[0]] == "DSC0001.jpg"

    def test_backups_follow_renamed_files(self, tmp_path):
        a = _touch(tmp_path / "DSC0001.jpg", datetime.datetime(2024, 5, 1, 10))
        backup_journal.save_backup("timestamp_backup", {a: {"atime": 1, "mtime": 1, "ctime": 1}})
        worker = _make_worker([a], exif_method=None)
        renamed, _errors, _ts, _mapping = worker.optimized_rename_files()
        assert list(load_journal()["timestamp_backup"]) == [renamed[0]]


# ---------------------------------------------------------------------------
# No silent overwrite
# ---------------------------------------------------------------------------
class TestSafeRename:

    def test_refuses_existing_target(self, tmp_path):
        a = _touch(tmp_path / "a.jpg")
        b = tmp_path / "b.jpg"
        b.write_bytes(b"precious")
        with pytest.raises(FileExistsError):
            safe_rename(a, str(b))
        assert b.read_bytes() == b"precious"
        assert os.path.exists(a)

    def test_plain_rename(self, tmp_path):
        a = _touch(tmp_path / "a.jpg")
        safe_rename(a, str(tmp_path / "c.jpg"))
        assert not os.path.exists(a)
        assert (tmp_path / "c.jpg").exists()

    def test_case_only_rename(self, tmp_path):
        folder = tmp_path / "photos"
        folder.mkdir()
        a = _touch(folder / "img.jpg")
        target = str(folder / "IMG.jpg")
        safe_rename(a, target)
        assert os.listdir(folder) == ["IMG.jpg"]

    def test_case_variant_detection(self, tmp_path):
        a = _touch(tmp_path / "img.jpg")
        # Only a case variant if the other name resolves to the same file
        # (true on case-insensitive filesystems such as macOS/Windows).
        assert is_case_variant(a, str(tmp_path / "IMG.jpg")) == os.path.exists(tmp_path / "IMG.jpg")
        assert is_case_variant(a, str(tmp_path / "other.jpg")) is False


# ---------------------------------------------------------------------------
# EXIF parsing
# ---------------------------------------------------------------------------
class TestExifParsing:

    @pytest.mark.parametrize("value, expected", [
        (0.0166666666666667, "1/60s"),   # int(1/x) gave 1/59
        (0.0666666666666667, "1/15s"),   # int(1/x) gave 1/14
        (0.004, "1/250s"),
        ("1/250", "1/250s"),
        (1 / 3, "0.3s"),
        (2.0, "2s"),
        (2.5, "2.5s"),
        (0, None),
        ("n/a", None),
    ])
    def test_exposure_time(self, value, expected):
        assert format_exposure_time(value) == expected

    def test_filename_shutter_component(self):
        meta = {"EXIF:ExposureTime": 0.0166666666666667}
        assert ExifService.parse_all_metadata_from_raw(meta)["shutter_speed"] == "1/60s"

    @pytest.mark.parametrize("meta, expected", [
        ({"QuickTime:CreateDate": "2024:05:01 10:00:00"}, "20240501"),
        ({"QuickTime:CreationDate": "2024:05:01 23:30:00+02:00"}, "20240501"),
        ({"EXIF:DateTimeOriginal": "0000:00:00 00:00:00", "EXIF:CreateDate": "2023:02:03 04:05:06"}, "20230203"),
        ({"EXIF:DateTimeOriginal": "2024:06:15 10:30:00.123"}, "20240615"),
        ({"EXIF:DateTimeOriginal": "0000:00:00 00:00:00"}, None),
    ])
    def test_capture_date(self, meta, expected):
        assert ExifService.parse_date_from_raw(meta) == expected

    def test_datetime_with_zone(self):
        dt = parse_exif_datetime("2024:05:01 23:30:00+02:00")
        assert dt.utcoffset() == datetime.timedelta(hours=2)
        assert (dt.year, dt.month, dt.day, dt.hour) == (2024, 5, 1, 23)


# ---------------------------------------------------------------------------
# Sorting
# ---------------------------------------------------------------------------
class TestSortKeys:

    def test_continuous_counter_mixed_names_same_mtime(self, tmp_path):
        """Equal date and mtime used to compare an int with a str (TypeError)."""
        when = datetime.datetime(2024, 5, 1, 10)
        a = _touch(tmp_path / "IMG_0001.jpg", when)
        b = _touch(tmp_path / "holiday.jpg", when)
        worker = _make_worker([a, b], exif_method=None, continuous_counter=True)
        renamed, errors, _ts, _mapping = worker.optimized_rename_files()
        assert errors == []
        assert len(renamed) == 2

    def test_sorted_by_capture_time_not_mtime(self, tmp_path):
        # mtime order is the reverse of the capture order
        a = _touch(tmp_path / "A.jpg", datetime.datetime(2024, 5, 2))
        b = _touch(tmp_path / "B.jpg", datetime.datetime(2024, 5, 1))
        service = _raw_meta_service({
            "A.jpg": {"EXIF:DateTimeOriginal": "2024:05:01 09:00:00"},
            "B.jpg": {"EXIF:DateTimeOriginal": "2024:05:01 10:00:00"},
        })
        worker = _make_worker([a, b], exif_service=service, continuous_counter=True)
        _renamed, errors, _ts, mapping = worker.optimized_rename_files()
        assert errors == []
        by_source = {os.path.basename(old): os.path.basename(new) for new, old in mapping.items()}
        assert by_source == {"A.jpg": "2024-05-01_001.jpg", "B.jpg": "2024-05-01_002.jpg"}


# ---------------------------------------------------------------------------
# EXIF restore only writes allow-listed date tags
# ---------------------------------------------------------------------------
class TestExifRestoreAllowlist:

    def test_unknown_tag_is_not_passed_to_exiftool(self, tmp_path, monkeypatch):
        from modules.exif_processor import restore_exif_timestamps
        f = _touch(tmp_path / "a.jpg")
        run = MagicMock()
        monkeypatch.setattr("subprocess.run", run)
        ok, msg = restore_exif_timestamps(f, {"o": "/tmp/x", "config": "evil"}, "/fake/exiftool")
        assert ok is False
        run.assert_not_called()
