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
