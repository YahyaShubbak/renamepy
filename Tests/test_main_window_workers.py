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
