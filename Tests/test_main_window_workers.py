#!/usr/bin/env python3
"""
Worker threads of the main window are released after use (pytest-qt).

Builds the real FileRenamerApp with its settings in a temporary INI file
(never the user's QSettings) and the undo journal in tmp_path (conftest).
"""

import datetime
import os
import sys
from unittest.mock import MagicMock

import pytest
from PyQt6.QtCore import QCoreApplication, QEvent, QSettings, QThread
from PyQt6.QtWidgets import QDialog

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def window(qtbot, tmp_path, monkeypatch):
    from modules import main_application, exif_processor
    from modules.settings_manager import SettingsManager
    from modules.main_application import FileRenamerApp

    def isolated_settings():
        manager = SettingsManager()
        manager.settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
        return manager

    monkeypatch.setattr(main_application, "SettingsManager", isolated_settings)
    monkeypatch.setattr(FileRenamerApp, "check_exiftool_warning", lambda self: None)
    win = FileRenamerApp()
    qtbot.addWidget(win)
    yield win
    win.close()
    exif_processor.set_default_exif_service(None)


def _threads_released(win):
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete.value)
    return win.worker is None and not win._busy and not win.findChildren(QThread)


def _run_rename(qtbot, win, monkeypatch):
    from modules.dialogs import RenamePlanDialog
    monkeypatch.setattr(RenamePlanDialog, "exec", lambda self: QDialog.DialogCode.Accepted)
    monkeypatch.setattr(win, "_show_rename_results", MagicMock())
    win.rename_files_action()
    qtbot.waitUntil(lambda: _threads_released(win), timeout=20000)
    return win._show_rename_results.call_args.args


def test_rename_workers_are_released(qtbot, tmp_path, window, monkeypatch):
    photos = tmp_path / "photos"
    photos.mkdir()
    files = []
    for i in range(3):
        path = photos / f"DSC{i:04d}.jpg"
        path.write_bytes(b"x")
        ts = datetime.datetime(2024, 5, 1, 10, i).timestamp()
        os.utime(path, (ts, ts))
        files.append(str(path))
    window.files[:] = files
    window.update_file_list()

    for additional in ("TripA", "TripB"):
        window.additional_entry.setText(additional)
        renamed, errors = _run_rename(qtbot, window, monkeypatch)
        assert errors == []
        assert len(renamed) == 3 and all(additional in os.path.basename(p) for p in renamed)

    assert window.worker is None
    assert window.findChildren(QThread) == []
    assert getattr(window, "_exif_undo_checker_ref", None) is None


def test_worker_signal_does_not_shadow_qthread_finished():
    from modules.rename_engine import RenameWorkerThread
    assert RenameWorkerThread.finished is QThread.finished
    assert hasattr(RenameWorkerThread, "rename_finished")


def test_planner_releases_continuous_raw_cache(tmp_path):
    from modules.rename_engine import RenameWorkerThread
    files = []
    for i in range(3):
        path = tmp_path / f"DSC{i:04d}.jpg"
        path.write_bytes(b"x")
        files.append(str(path))
    service = MagicMock()
    service.batch_get_raw_metadata.side_effect = lambda paths, chunk_size=50: {
        p: {"EXIF:DateTimeOriginal": "2024:05:01 10:00:00", "EXIF:Model": "X" * 1000} for p in paths
    }
    worker = RenameWorkerThread(
        files=files, camera_prefix="", additional="", use_camera=False, use_lens=False,
        exif_method="exiftool", separator="_", exiftool_path=None,
        custom_order=["Date", "Number"], date_format="YYYY-MM-DD", use_date=True,
        continuous_counter=True, selected_metadata={}, sync_exif_date=False,
        exif_service=service,
    )

    entries, errors = worker.build_plan()

    assert errors == [] and len(entries) == 3
    assert worker.planner._continuous_raw_cache == {}


# ---------------------------------------------------------------------------
# "Files carry their original name" check (Restore button)
# ---------------------------------------------------------------------------
def _loaded(window, tmp_path, count=4):
    files = []
    for i in range(count):
        path = tmp_path / f"2024_{i:03d}.jpg"
        path.write_bytes(b"x")
        files.append(str(path))
    window.files[:] = files
    window.exiftool_path = window.exiftool_path or "/fake/exiftool"
    return files


def test_undo_check_is_one_call_and_restarts_after_invalidation(qtbot, tmp_path, window, monkeypatch):
    from modules import main_application
    calls = []

    def batch(paths, exiftool_path):
        calls.append(list(paths))
        return {p: "DSC0001.jpg" for p in paths}

    monkeypatch.setattr(main_application, "batch_get_original_filenames", batch)
    _loaded(window, tmp_path)
    window.invalidate_exif_undo_cache()

    window._start_async_exif_undo_check()
    window.invalidate_exif_undo_cache()  # files changed while the check runs

    qtbot.waitUntil(lambda: getattr(window, "_exif_undo_checked", False), timeout=10000)
    assert [len(c) for c in calls] == [3, 3]  # first result discarded, checked again
    assert window._exif_undo_available is True
    qtbot.waitUntil(lambda: getattr(window, "_exif_undo_checker_ref", None) is None, timeout=10000)


def test_files_at_their_original_name_offer_nothing(qtbot, tmp_path, window, monkeypatch):
    from modules import main_application
    monkeypatch.setattr(main_application, "batch_get_original_filenames",
                        lambda paths, exiftool_path: {p: os.path.basename(p) for p in paths})
    _loaded(window, tmp_path)
    window.invalidate_exif_undo_cache()

    window._start_async_exif_undo_check()

    qtbot.waitUntil(lambda: getattr(window, "_exif_undo_checked", False), timeout=10000)
    assert window._exif_undo_available is False


@pytest.mark.parametrize("action", ["clear", "forget"])
def test_cached_result_is_dropped(qtbot, tmp_path, window, monkeypatch, action):
    from PyQt6.QtWidgets import QMessageBox
    from modules import main_application
    monkeypatch.setattr(main_application, "batch_get_original_filenames",
                        lambda paths, exiftool_path: {p: None for p in paths})
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    window._exif_undo_checked = True
    window._exif_undo_available = True
    window.original_filenames = {str(tmp_path / "x.jpg"): "y.jpg"}

    if action == "clear":
        window.clear_file_list()
    else:
        window.forget_undo_data()

    assert not hasattr(window, "_exif_undo_available")
    qtbot.waitUntil(lambda: getattr(window, "_exif_undo_checker_ref", None) is None, timeout=10000)


# ---------------------------------------------------------------------------
# Real errors are logged at the default level (not only with debug on)
# ---------------------------------------------------------------------------
@pytest.fixture
def warnings_logged():
    """WARNING+ records of the app logger (it does not propagate to root)."""
    import logging
    from modules.logger_util import get_logger

    class _Collect(logging.Handler):
        def __init__(self):
            super().__init__(logging.WARNING)
            self.messages = []

        def emit(self, record):
            self.messages.append(record.getMessage())

    handler = _Collect()
    logger = get_logger()
    logger.addHandler(handler)
    yield handler.messages
    logger.removeHandler(handler)


def test_exiftool_lookup_error_is_a_warning(monkeypatch, warnings_logged):
    from modules import main_application
    from modules.main_application import FileRenamerApp

    def broken():
        raise OSError("permission denied")

    monkeypatch.setattr(main_application, "find_exiftool_path", broken)
    assert FileRenamerApp.get_exiftool_path(MagicMock()) is None
    assert warnings_logged == ["Error locating ExifTool: permission denied"]


def test_camera_info_errors_are_warnings(tmp_path, window, warnings_logged):
    photo = tmp_path / "a.jpg"
    photo.write_bytes(b"x")
    window.files[:] = [str(photo)]
    window.exif_method = "exiftool"
    window.exif_service.get_cached_exif_data = MagicMock(side_effect=RuntimeError("busy"))
    window.exif_service.extract_raw_exif = MagicMock(side_effect=RuntimeError("busy"))

    window.extract_camera_info()

    assert f"Error extracting camera info from {photo}: busy" in warnings_logged
    assert f"Error extracting shooting settings from {photo}: busy" in warnings_logged
