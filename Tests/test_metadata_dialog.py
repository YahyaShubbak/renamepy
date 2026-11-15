#!/usr/bin/env python3
"""Metadata dialog: missing files, no extra ExifTool process, raw values (pytest-qt)."""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest
from PyQt6.QtWidgets import QDialog, QLabel, QWidget

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.ui.metadata_dialog_manager import MetadataDialogManager


class _Window(QWidget):
    """The main window as far as the dialog uses it (dialogs need a QWidget parent)."""

    def __init__(self):
        super().__init__()
        self.exiftool_path = "/fake/exiftool"
        self.exif_method = "exiftool"
        self.selected_metadata = {}
        self.exif_service = MagicMock()
        self.log = MagicMock()
        for name in ("checkbox_camera", "checkbox_lens", "checkbox_date"):
            checkbox = MagicMock()
            checkbox.isChecked.return_value = False
            setattr(self, name, checkbox)


@pytest.fixture
def manager(qtbot):
    window = _Window()
    qtbot.addWidget(window)
    return MetadataDialogManager(window)


def _labels(widget):
    return [label.text() for label in widget.widget().findChildren(QLabel)]


RAW = {
    "SourceFile": "/photos/2024-05-01_001.JPG",
    "File:FileType": "JPEG",
    "EXIF:Make": "SONY",
    "EXIF:Model": "ILCE-7CM2",
    "EXIF:DateTimeOriginal": "2024:05:01 10:00:00",
    "EXIF:ImageDescription": "line one\nline two: with colon",
    "XMP:PreservedFileName": "DSC00001.JPG",
}


def test_missing_file_does_not_raise(manager, tmp_path):
    """Regression: the "File not found." dialog crashed on os.stat."""
    with patch("modules.ui.metadata_dialog_manager.get_rename_info",
               return_value={"original_filename": None, "rename_date": None}):
        widget = manager.create_essential_metadata_widget("File not found.", str(tmp_path / "gone.jpg"))
    labels = _labels(widget)
    assert "File: gone.jpg" in labels
    assert not any(text.startswith("Size:") for text in labels)


def test_raw_metadata_is_used_without_extra_exiftool_call(manager, tmp_path):
    photo = tmp_path / "2024-05-01_001.JPG"
    photo.write_bytes(b"x" * 2048)
    with patch("modules.ui.metadata_dialog_manager.get_rename_info") as rename_info:
        widget = manager.create_essential_metadata_widget("ignored text", str(photo), dict(RAW))
    rename_info.assert_not_called()
    labels = _labels(widget)
    assert "📝 Original: DSC00001.JPG" in labels
    assert "Camera: SONY ILCE-7CM2" in labels
    assert "Type: JPEG" in labels
    assert "Date: 2024:05:01 10:00:00" in labels


def test_legacy_original_name_from_raw(manager, tmp_path):
    photo = tmp_path / "a.jpg"
    photo.touch()
    raw = {"SourceFile": str(photo),
           "EXIF:UserComment": "OriginalName: IMG_7.JPG | RenameDate: 2024:01:01 10:00:00"}
    with patch("modules.ui.metadata_dialog_manager.get_rename_info") as rename_info:
        widget = manager.create_essential_metadata_widget("", str(photo), raw)
    rename_info.assert_not_called()
    assert "📝 Original: IMG_7.JPG" in _labels(widget)


def test_show_exif_info_passes_the_raw_dict(manager, tmp_path, monkeypatch):
    photo = tmp_path / "2024-05-01_001.JPG"
    photo.touch()
    manager.parent.exif_service.extract_raw_exif.return_value = dict(RAW)
    shown = []
    monkeypatch.setattr(QDialog, "exec", lambda self: shown.append(self) or 0)
    with patch("modules.ui.metadata_dialog_manager.get_rename_info") as rename_info:
        manager.show_exif_info(str(photo))
    rename_info.assert_not_called()
    assert len(shown) == 1


def test_show_exif_info_for_missing_file(manager, tmp_path, monkeypatch):
    shown = []
    monkeypatch.setattr(QDialog, "exec", lambda self: shown.append(self) or 0)
    with patch("modules.ui.metadata_dialog_manager.get_rename_info",
               return_value={"original_filename": None, "rename_date": None}):
        manager.show_exif_info(str(tmp_path / "gone.jpg"))
    assert len(shown) == 1
    manager.parent.log.assert_called()  # the "File not found" note, not an error


# ---------------------------------------------------------------------------
# EXIF time shift dialog: preview parses dates like the rename does
# ---------------------------------------------------------------------------
def _shift_preview(qtbot, monkeypatch, metas, hours=1):
    from modules.dialogs.exif_time_shift_dialog import ExifTimeShiftDialog
    files = list(metas)
    monkeypatch.setattr("modules.exif_processor.get_exiftool_metadata_shared",
                        lambda path, exiftool_path=None: metas[path])
    dialog = ExifTimeShiftDialog(None, files, "/fake/exiftool")
    qtbot.addWidget(dialog)
    dialog.hours_spin.setValue(hours)
    dialog.minutes_spin.setValue(0)
    table = dialog.preview_table
    return [(table.item(r, 1).text(), table.item(r, 2).text()) for r in range(table.rowCount())]


def test_time_shift_preview_with_subseconds_and_zone(qtbot, monkeypatch):
    """Regression: strptime failed on sub-seconds/zones ("Error: ...")."""
    rows = _shift_preview(qtbot, monkeypatch, {
        "/p/a.jpg": {"EXIF:DateTimeOriginal": "2024:01:15 10:30:45.12+02:00"},
    })
    assert rows == [("2024:01:15 10:30:45", "2024:01:15 11:30:45")]


def test_time_shift_preview_uses_the_rename_tags(qtbot, monkeypatch):
    rows = _shift_preview(qtbot, monkeypatch, {
        # Apple video: CreationDate (local, with zone) ranks above CreateDate
        "/p/clip.mov": {"QuickTime:CreateDate": "2024:01:15 08:30:45",
                        "QuickTime:CreationDate": "2024:01:15 10:30:45+02:00"},
        # Not a string (ExifTool -n can return numbers): row must not be dropped
        "/p/b.jpg": {"EXIF:DateTimeOriginal": 20240115},
        "/p/c.jpg": {"EXIF:Model": "X"},
    })
    assert rows[0] == ("2024:01:15 10:30:45", "2024:01:15 11:30:45")
    assert len(rows) == 3
    assert rows[2] == ("No EXIF time found", "No change")


def test_show_exif_info_error_is_a_warning(manager, tmp_path, monkeypatch):
    import logging
    from modules.logger_util import get_logger
    photo = tmp_path / "a.jpg"
    photo.touch()
    manager.parent.exif_service.extract_raw_exif.side_effect = RuntimeError("pipe closed")
    monkeypatch.setattr(QDialog, "exec", lambda self: 0)
    records = []
    handler = logging.Handler(logging.WARNING)
    handler.emit = lambda record: records.append(record.getMessage())
    get_logger().addHandler(handler)
    try:
        with patch("modules.ui.metadata_dialog_manager.get_rename_info",
                   return_value={"original_filename": None, "rename_date": None}):
            manager.show_exif_info(str(photo))
    finally:
        get_logger().removeHandler(handler)
    assert records == ["Error in show_exif_info: pipe closed"]
