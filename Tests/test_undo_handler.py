#!/usr/bin/env python3
"""
Undo runs in a worker thread (pytest-qt).

The window is a light QWidget stand-in: building the real FileRenamerApp
would locate ExifTool and read/write the user's QSettings.
"""

import os
import sys
import time
from unittest.mock import MagicMock

import pytest
from PyQt6.QtWidgets import QMessageBox, QWidget

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules import backup_journal
from modules.handlers import undo_handler
from modules.handlers.undo_handler import UndoHandler


class _FakeApp(QWidget):
    def __init__(self, files, original_filenames=None, timestamp_backup=None):
        super().__init__()
        self.files = list(files)
        self.original_filenames = dict(original_filenames or {})
        self.timestamp_backup = dict(timestamp_backup or {})
        self.exif_backup = {}
        self.exiftool_path = None
        self._exif_undo_available = False
        for name in ("status", "log", "_ui_set_busy", "update_restore_button_state",
                     "update_preview", "update_file_list", "exif_service", "preview_generator",
                     "invalidate_exif_undo_cache"):
            setattr(self, name, MagicMock())


@pytest.fixture
def dialogs(monkeypatch):
    """Answer every confirmation with Yes and record the result boxes."""
    boxes = MagicMock()
    monkeypatch.setattr(QMessageBox, "exec", lambda self: QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    for name in ("information", "warning", "critical"):
        monkeypatch.setattr(QMessageBox, name, getattr(boxes, name))
    return boxes


def _renamed_files(tmp_path, count=3):
    """Files renamed DSC000i.jpg -> 2024_00i.jpg, with timestamp backups."""
    originals, backups, files = {}, {}, []
    for i in range(1, count + 1):
        current = tmp_path / f"2024_{i:03d}.jpg"
        current.write_bytes(b"x")
        files.append(str(current))
        originals[str(current)] = f"DSC{i:04d}.jpg"
        backups[str(current)] = {"atime": 1.0e9, "mtime": 1.0e9, "ctime": 1.0e9}
    backup_journal.update_entries({"original_filenames": {"set": originals}})
    backup_journal.save_backup("timestamp_backup", backups)
    return files, originals, backups


def test_undo_returns_immediately_and_restores_in_worker(qtbot, tmp_path, monkeypatch, dialogs):
    files, originals, backups = _renamed_files(tmp_path)
    app = _FakeApp(files, originals, backups)
    qtbot.addWidget(app)
    real_restore = undo_handler.batch_restore_timestamps

    def slow_restore(*args, **kwargs):
        time.sleep(0.5)
        return real_restore(*args, **kwargs)

    monkeypatch.setattr(undo_handler, "batch_restore_timestamps", slow_restore)
    handler = UndoHandler(app)

    started = time.monotonic()
    handler.undo_rename_action()

    assert time.monotonic() - started < 0.4
    assert handler.worker is not None and handler.worker.isRunning()
    assert all(os.path.exists(f) for f in files)  # nothing renamed yet
    qtbot.waitUntil(lambda: handler.worker is None, timeout=10000)

    for i in range(1, 4):
        restored = tmp_path / f"DSC{i:04d}.jpg"
        assert restored.exists()
        assert os.path.getmtime(restored) == pytest.approx(1.0e9)
    assert app.original_filenames == {} and app.timestamp_backup == {}
    assert sorted(os.path.basename(f) for f in app.files) == ["DSC0001.jpg", "DSC0002.jpg", "DSC0003.jpg"]
    assert backup_journal.load_journal().keys() <= {"_last_updated"}
    assert [c.args for c in app._ui_set_busy.call_args_list] == [(True,), (False,)]
    assert dialogs.information.call_args.args[1] == "Undo Complete"
    app.update_file_list.assert_called_once()


def test_metadata_scan_runs_in_worker(qtbot, tmp_path, monkeypatch, dialogs):
    current = tmp_path / "2024_001.jpg"
    current.write_bytes(b"x")
    app = _FakeApp([str(current)])
    app._exif_undo_available = True
    app.exiftool_path = "/fake/exiftool"
    qtbot.addWidget(app)
    scanned_on = []

    def scan(files, exiftool_path):
        import threading
        scanned_on.append(threading.current_thread())
        time.sleep(0.3)
        return {str(current): "DSC0001.jpg"}

    monkeypatch.setattr("modules.exif_undo_manager.batch_get_original_filenames", scan)
    handler = UndoHandler(app)

    handler.undo_rename_action()

    assert handler.worker is not None and handler.worker.isRunning()
    qtbot.waitUntil(lambda: handler.worker is None and (tmp_path / "DSC0001.jpg").exists(), timeout=10000)
    import threading
    assert scanned_on and scanned_on[0] is not threading.main_thread()
    assert dialogs.information.call_args.args[1] == "Undo Complete"


def test_worker_exception_is_reported(qtbot, tmp_path, monkeypatch, dialogs):
    files, originals, backups = _renamed_files(tmp_path, count=1)
    app = _FakeApp(files, originals, backups)
    qtbot.addWidget(app)

    def boom(*args, **kwargs):
        raise RuntimeError("disk on fire")

    monkeypatch.setattr(undo_handler, "_do_restore_timestamps", boom)
    handler = UndoHandler(app)

    handler.undo_rename_action()
    qtbot.waitUntil(lambda: handler.worker is None, timeout=10000)

    assert "disk on fire" in dialogs.critical.call_args.args[2]
    assert app._ui_set_busy.call_args_list[-1].args == (False,)
    assert app.original_filenames == originals  # nothing was applied


def test_second_click_while_running_is_ignored(qtbot, tmp_path, monkeypatch, dialogs):
    files, originals, backups = _renamed_files(tmp_path, count=1)
    app = _FakeApp(files, originals, backups)
    qtbot.addWidget(app)
    real_restore = undo_handler.batch_restore_timestamps
    monkeypatch.setattr(undo_handler, "batch_restore_timestamps",
                        lambda *a, **k: (time.sleep(0.3), real_restore(*a, **k))[1])
    handler = UndoHandler(app)

    handler.undo_rename_action()
    first = handler.worker
    handler.undo_rename_action()

    assert handler.worker is first
    qtbot.waitUntil(lambda: handler.worker is None, timeout=10000)


def test_close_refused_while_undo_runs(monkeypatch):
    from modules.main_application import FileRenamerApp
    warning = MagicMock()
    monkeypatch.setattr(QMessageBox, "warning", warning)
    window = MagicMock()
    window.worker = None
    window.undo_handler.worker.isRunning.return_value = True
    event = MagicMock()

    FileRenamerApp.closeEvent(window, event)

    event.ignore.assert_called_once()
    warning.assert_called_once()
    window.exif_service.cleanup.assert_not_called()
