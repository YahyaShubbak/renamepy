#!/usr/bin/env python3
"""
Tests for the interactive preview:

- the example name comes from the same planner as the real rename
- components are identified by id, not by their displayed text
- drag & drop reordering keeps components that are not displayed
- metadata formatting (shared with the rename engine)
"""

import os
import sys
import datetime
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.filename_components import _format_metadata
from modules.rename_engine import RenameWorkerThread
from modules.ui.preview_generator import PreviewGenerator, SAMPLE_FILE


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _checkbox(checked):
    box = MagicMock()
    box.isChecked.return_value = checked
    return box


def _text(value):
    widget = MagicMock()
    widget.text.return_value = value
    widget.currentText.return_value = value
    return widget


def _parent(files=(), *, prefix="", additional="", camera=False, lens=False, date=True,
            date_format="YYYY-MM-DD", separator="-", continuous=False, selected=None,
            order=None, exif_method=None, raw=None):
    parent = MagicMock()
    parent.files = list(files)
    parent.camera_prefix_entry = _text(prefix)
    parent.additional_entry = _text(additional)
    parent.checkbox_camera = _checkbox(camera)
    parent.checkbox_lens = _checkbox(lens)
    parent.checkbox_date = _checkbox(date)
    parent.checkbox_continuous_counter = _checkbox(continuous)
    parent.date_format_combo = _text(date_format)
    parent.separator_combo = _text(separator)
    parent.selected_metadata = dict(selected or {})
    parent.custom_order = list(order or ["Date", "Prefix", "Additional", "Camera", "Lens", "Number"])
    parent.exif_method = exif_method
    parent.exif_service.batch_get_raw_metadata.side_effect = (
        lambda paths, chunk_size=50: {p: (raw or {}).get(os.path.basename(p), {}) for p in paths}
    )
    parent.log = lambda msg: None
    return parent


class TestPreviewMatchesRename:

    def test_sample_before_files_are_loaded(self):
        gen = PreviewGenerator(_parent(prefix="A7R3", camera=True, selected={"iso": True}))
        gen._sync_custom_order(gen.planner_settings())
        components, name = gen.build_preview()
        assert name == "2025-07-25-A7R3-Camera-ISO100-001.JPG"
        assert [cid for cid, _ in components] == ["Date", "Prefix", "Camera", "Meta_iso", "Number"]
        assert SAMPLE_FILE.endswith(".JPG")

    def test_preview_equals_real_rename(self, tmp_path):
        photo = tmp_path / "DSC00001.JPG"
        photo.write_bytes(b"x")
        raw = {"DSC00001.JPG": {
            "EXIF:DateTimeOriginal": "2024:05:01 10:00:00",
            "EXIF:Model": "ILCE-7RM3",
            "EXIF:ExposureTime": 0.0166666666666667,
        }}
        parent = _parent([str(photo)], prefix="Trip / 2024", camera=True, lens=True,
                         selected={"shutter": True}, exif_method="exiftool", raw=raw)
        gen = PreviewGenerator(parent)
        gen._sync_custom_order(gen.planner_settings())
        _components, preview_name = gen.build_preview()

        worker = RenameWorkerThread(
            files=[str(photo)], camera_prefix="Trip / 2024", additional="", use_camera=True,
            use_lens=True, exif_method="exiftool", separator="-", exiftool_path=None,
            custom_order=parent.custom_order, date_format="YYYY-MM-DD", use_date=True,
            continuous_counter=False, selected_metadata={"shutter": True},
            sync_exif_date=False, exif_service=parent.exif_service,
        )
        entries, errors = worker.build_plan()
        assert errors == []
        assert os.path.basename(entries[0].target) == preview_name
        # Sanitized prefix, fallback lens and correctly rounded shutter speed
        assert preview_name == "2024-05-01-Trip_2024-ILCE-7RM3-Unknown-Lens-1_60s-001.JPG"

    def test_without_exiftool_uses_file_date(self, tmp_path):
        photo = tmp_path / "holiday.jpg"
        photo.write_bytes(b"x")
        when = datetime.datetime(2023, 8, 9, 12, 0)
        os.utime(photo, (when.timestamp(), when.timestamp()))
        gen = PreviewGenerator(_parent([str(photo)], camera=True))
        _components, name = gen.build_preview()
        assert name == "2023-08-09-Unknown-Camera-001.jpg"


class TestComponentOrder:

    def test_new_components_are_inserted_before_number(self):
        parent = _parent(prefix="P", additional="A", order=["Number", "Date"])
        gen = PreviewGenerator(parent)
        gen._sync_custom_order(gen.planner_settings())
        assert parent.custom_order == ["Prefix", "Additional", "Number", "Date"]

    def test_apply_order_keeps_hidden_components(self):
        # Meta_iso is active but not displayed (the file has no ISO)
        parent = _parent(order=["Date", "Meta_iso", "Prefix", "Number"], prefix="P", selected={"iso": True})
        parent.interactive_preview = MagicMock()
        gen = PreviewGenerator(parent)
        gen.apply_order(["Prefix", "Number", "Date"])
        assert parent.custom_order == ["Prefix", "Meta_iso", "Number", "Date"]


class TestPreviewWidget:

    def test_identical_texts_are_distinguished(self, qapp):
        from modules.ui_components import InteractivePreviewWidget
        widget = InteractivePreviewWidget()
        received = []
        widget.order_changed.connect(received.append)
        # Prefix and additional text are the same word
        widget.set_components([("Date", "2024-05-01"), ("Prefix", "Rome"), ("Additional", "Rome"), ("Number", "001")])
        widget.move_component("Additional", "Date")
        assert received[-1] == ["Additional", "Prefix", "Date", "Number"]
        widget.move_component("Prefix", None)
        assert received[-1] == ["Additional", "Date", "Number", "Prefix"]

    def test_separators_between_components(self, qapp):
        from modules.ui_components import InteractivePreviewWidget, ITEM_TYPE_ROLE
        widget = InteractivePreviewWidget()
        widget.set_separator("_")
        widget.set_components([("Date", "2024"), ("Number", "001")])
        types = [widget.item(i).data(ITEM_TYPE_ROLE) for i in range(widget.count())]
        assert types == ["component", "separator", "component"]


class TestMetadataFormatting:
    """Formatting shared by preview and rename (filename_components)."""

    @pytest.mark.parametrize("key, value, expected", [
        ("aperture", "f/2.8", "f2.8"),
        ("aperture", "f5.6", "f5.6"),
        ("aperture", "2.8", "f2.8"),
        ("aperture", 2.8, "f2.8"),
        ("aperture", 4, "f4"),
        ("shutter", "1/250s", "1_250s"),
        ("focal_length", "85mm", "85mm"),
        ("iso", 400, "ISO400"),
        ("custom_tag", 12345, "12345"),
    ])
    def test_values(self, key, value, expected):
        assert _format_metadata(key, value) == expected

    @pytest.mark.parametrize("value", [None, "", "Unknown", True])
    def test_empty_or_unresolved(self, value):
        assert _format_metadata("iso", value) is None

    def test_numeric_focal_length_and_resolution_do_not_crash(self):
        assert "85" in _format_metadata("focal_length", 85)
        assert isinstance(_format_metadata("resolution", 24000000), str)
