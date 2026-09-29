#!/usr/bin/env python3
"""
Tests for the two-stage rename (plan -> confirm -> execute):

- planning never touches files
- sidecar files (.xmp, .pp3, ...) are renamed with their photo, both
  naming styles, and never get a "(1)" suffix
- cancelling planning or execution
- the review dialog
"""

import os
import sys
import datetime
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.backup_journal import load_journal
from modules.rename_engine import RenamePlanner, RenameWorkerThread, PlanningCancelled, PlanEntry


def _touch(path, when=datetime.datetime(2024, 5, 1, 10, 0)):
    path.write_bytes(b"x")
    os.utime(path, (when.timestamp(), when.timestamp()))
    return str(path)


def _worker(files, **overrides):
    defaults = dict(
        files=files, camera_prefix="", additional="", use_camera=False, use_lens=False,
        exif_method=None, separator="_", exiftool_path=None, custom_order=["Date", "Number"],
        date_format="YYYY-MM-DD", use_date=True, continuous_counter=False,
        selected_metadata={}, sync_exif_date=False, rename_sidecars=True,
    )
    defaults.update(overrides)
    return RenameWorkerThread(**defaults)


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


class TestPlanning:

    def test_plan_does_not_touch_files(self, tmp_path):
        a = _touch(tmp_path / "DSC0001.jpg")
        before = sorted(os.listdir(tmp_path))
        entries, errors = _worker([a]).build_plan()
        assert errors == []
        assert [os.path.basename(e.target) for e in entries] == ["2024-05-01_001.jpg"]
        assert sorted(os.listdir(tmp_path)) == before
        assert "original_filenames" not in load_journal()

    def test_execute_runs_the_confirmed_plan(self, tmp_path):
        a = _touch(tmp_path / "DSC0001.jpg")
        entries, _errors = _worker([a]).build_plan()
        worker = _worker([a], mode="execute", plan=entries)
        renamed, errors, _ts, mapping = worker._sync_then_execute(worker.plan, [])
        assert errors == []
        assert renamed == [str(tmp_path / "2024-05-01_001.jpg")]
        assert mapping == {renamed[0]: a}

    def test_name_conflict_is_noted(self, tmp_path):
        a = _touch(tmp_path / "DSC0001.jpg")
        (tmp_path / "2024-05-01_001.jpg").write_bytes(b"other")
        entries, _errors = _worker([a]).build_plan()
        assert os.path.basename(entries[0].target) == "2024-05-01_001(1).jpg"
        assert "already exists" in entries[0].note

    def test_planning_can_be_cancelled(self, tmp_path):
        a = _touch(tmp_path / "DSC0001.jpg")
        planner = RenamePlanner([a], is_cancelled=lambda: True)
        with pytest.raises(PlanningCancelled):
            planner.build_plan()

    def test_execution_can_be_cancelled(self, tmp_path):
        a = _touch(tmp_path / "DSC0001.jpg")
        b = _touch(tmp_path / "DSC0002.jpg", datetime.datetime(2024, 5, 1, 11))
        entries, _errors = _worker([a, b]).build_plan()
        worker = _worker([a, b])
        calls = []
        worker.isInterruptionRequested = lambda: bool(calls)  # cancel after the first file
        real_rename = __import__("modules.rename_engine", fromlist=["safe_rename"]).safe_rename

        def rename(source, target):
            calls.append(source)
            real_rename(source, target)

        with patch("modules.rename_engine.safe_rename", side_effect=rename):
            renamed, errors, mapping = worker.execute_plan(entries)
        assert len(renamed) == 1
        assert worker.was_cancelled
        assert errors == [("", "Cancelled - 1 file(s) not renamed")]
        assert os.path.exists(b)
        # The journal only keeps the rename that happened
        assert list(load_journal()["original_filenames"].values()) == ["DSC0001.jpg"]


class TestSidecars:

    def test_both_naming_styles(self, tmp_path):
        jpg = _touch(tmp_path / "IMG_0001.JPG")
        cr2 = _touch(tmp_path / "IMG_0001.CR2")
        (tmp_path / "IMG_0001.xmp").write_text("lightroom")
        (tmp_path / "IMG_0001.CR2.xmp").write_text("darktable")
        (tmp_path / "IMG_0001.CR2.pp3").write_text("rawtherapee")
        entries, errors = _worker([jpg, cr2]).build_plan()
        assert errors == []
        sidecars = {os.path.basename(e.source): os.path.basename(e.target) for e in entries if e.sidecar}
        assert sidecars == {
            "IMG_0001.xmp": "2024-05-01_001.xmp",
            "IMG_0001.CR2.xmp": "2024-05-01_001.CR2.xmp",
            "IMG_0001.CR2.pp3": "2024-05-01_001.CR2.pp3",
        }

    def test_sidecars_follow_and_are_undoable(self, tmp_path):
        jpg = _touch(tmp_path / "IMG_0001.JPG")
        (tmp_path / "IMG_0001.AAE").write_text("apple")
        renamed, errors, _ts, mapping = _worker([jpg]).optimized_rename_files()
        assert errors == []
        assert sorted(os.listdir(tmp_path / ".")) == sorted(["2024-05-01_001.JPG", "2024-05-01_001.AAE", "app_data"])
        assert renamed == [str(tmp_path / "2024-05-01_001.JPG")]  # sidecars are not "photos"
        journal = load_journal()["original_filenames"]
        assert journal[str(tmp_path / "2024-05-01_001.AAE")] == "IMG_0001.AAE"
        assert mapping[str(tmp_path / "2024-05-01_001.AAE")] == str(tmp_path / "IMG_0001.AAE")

    def test_taken_sidecar_name_is_left_alone(self, tmp_path):
        jpg = _touch(tmp_path / "IMG_0001.JPG")
        (tmp_path / "IMG_0001.xmp").write_text("mine")
        (tmp_path / "2024-05-01_001.xmp").write_text("someone else's")
        entries, errors = _worker([jpg]).build_plan()
        assert not any(e.sidecar for e in entries)
        assert "already exists" in errors[0][1]

    def test_option_off(self, tmp_path):
        jpg = _touch(tmp_path / "IMG_0001.JPG")
        (tmp_path / "IMG_0001.xmp").write_text("x")
        entries, _errors = _worker([jpg], rename_sidecars=False).build_plan()
        assert [e.sidecar for e in entries] == [False]

    def test_sidecar_skipped_when_photo_fails(self, tmp_path):
        jpg = _touch(tmp_path / "IMG_0001.JPG")
        (tmp_path / "IMG_0001.xmp").write_text("x")
        worker = _worker([jpg])
        entries, _errors = worker.build_plan()
        with patch("modules.rename_engine.safe_rename", side_effect=OSError("locked")):
            _renamed, errors, _mapping = worker.execute_plan(entries)
        assert any("its photo was not renamed" in message for _path, message in errors)
        assert (tmp_path / "IMG_0001.xmp").exists()

    def test_loaded_file_is_not_treated_as_sidecar(self, tmp_path):
        jpg = _touch(tmp_path / "IMG_0001.JPG")
        thm = str(tmp_path / "IMG_0001.THM")
        with open(thm, "w") as f:
            f.write("x")
        planner = RenamePlanner([jpg, thm], rename_sidecars=True, separator="_",
                                custom_order=["Date", "Number"])
        entries = [PlanEntry(jpg, str(tmp_path / "new.JPG"))]
        sidecars, _errors = planner.plan_sidecars(entries, set())
        assert sidecars == []


class TestSidecarUndo:

    def _app(self, files, originals):
        from unittest.mock import MagicMock
        app = MagicMock()
        app.files = list(files)
        app.original_filenames = dict(originals)
        app.timestamp_backup = {}
        app.exif_backup = {}
        return app

    def test_untracked_sidecars_follow_restored_photo(self, tmp_path):
        """Restoring from metadata: only the photo has an original name."""
        from modules.handlers.undo_handler import UndoHandler
        jpg = _touch(tmp_path / "2024_001.JPG")
        arw = _touch(tmp_path / "2024_001.ARW")
        (tmp_path / "2024_001.xmp").write_text("lr")
        (tmp_path / "2024_001.ARW.pp3").write_text("rt")
        app = self._app([jpg, arw], {jpg: "DSC0001.JPG", arw: "DSC0001.ARW"})
        restored, errors = UndoHandler(app)._restore_filenames(list(app.original_filenames.items()))
        assert errors == []
        assert sorted(p.name for p in tmp_path.iterdir() if p.name != "app_data") == [
            "DSC0001.ARW", "DSC0001.ARW.pp3", "DSC0001.JPG", "DSC0001.xmp",
        ]

    def test_tracked_sidecar_is_restored_once(self, tmp_path):
        from modules.handlers.undo_handler import UndoHandler
        jpg = _touch(tmp_path / "2024_001.JPG")
        xmp = tmp_path / "2024_001.xmp"
        xmp.write_text("lr")
        app = self._app([jpg], {jpg: "IMG_7.JPG", str(xmp): "IMG_7.xmp"})
        restored, errors = UndoHandler(app)._restore_filenames(list(app.original_filenames.items()))
        assert errors == []
        assert sorted(p.name for p in tmp_path.iterdir() if p.name != "app_data") == ["IMG_7.JPG", "IMG_7.xmp"]

    def test_taken_sidecar_name_is_reported(self, tmp_path):
        from modules.handlers.undo_handler import UndoHandler
        jpg = _touch(tmp_path / "2024_001.JPG")
        (tmp_path / "2024_001.xmp").write_text("mine")
        (tmp_path / "DSC0001.xmp").write_text("someone else's")
        app = self._app([jpg], {jpg: "DSC0001.JPG"})
        restored, errors = UndoHandler(app)._restore_filenames(list(app.original_filenames.items()))
        assert restored == [str(tmp_path / "DSC0001.JPG")]
        assert "not restored" in errors[0]
        assert (tmp_path / "DSC0001.xmp").read_text() == "someone else's"


class TestPlanDialog:

    def test_summary_and_rows(self, qapp, tmp_path):
        from modules.dialogs import RenamePlanDialog
        entries = [
            PlanEntry(str(tmp_path / "a.jpg"), str(tmp_path / "2024_001.jpg")),
            PlanEntry(str(tmp_path / "b.jpg"), str(tmp_path / "b.jpg")),
            PlanEntry(str(tmp_path / "a.xmp"), str(tmp_path / "2024_001.xmp"), sidecar=True,
                      main_source=str(tmp_path / "a.jpg")),
        ]
        dialog = RenamePlanDialog(entries, [(str(tmp_path / "c.jpg"), "Target path too long")])
        assert dialog.photo_count == 1 and dialog.sidecar_count == 1
        assert dialog.rename_button.text() == "Rename 1 files"
        assert dialog.proxy.rowCount() == 3
        dialog.show_unchanged.setChecked(False)
        assert dialog.proxy.rowCount() == 2
        model = dialog.model
        assert model.data(model.index(1, 1)) == "(unchanged)"

    def test_nothing_to_rename(self, qapp, tmp_path):
        from modules.dialogs import RenamePlanDialog
        dialog = RenamePlanDialog([PlanEntry(str(tmp_path / "a.jpg"), str(tmp_path / "a.jpg"))], [])
        assert not dialog.rename_button.isEnabled()
