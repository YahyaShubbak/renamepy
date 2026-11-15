#!/usr/bin/env python3
"""
Unit tests for modules/exif_undo_manager.py

Tests the metadata-based undo persistence layer: writing, reading, batch
operations, clearing, and edge cases. All ExifTool calls are mocked here;
Tests/test_exiftool_integration.py runs the same paths against a real
ExifTool when one is installed.
"""

import os
import sys
import json
import subprocess
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules import exif_undo_manager
from modules.exif_undo_manager import (
    write_original_filename_to_exif,
    get_original_filename_from_exif,
    batch_write_original_filenames,
    batch_get_original_filenames,
    clear_original_filename_from_exif,
    has_original_filename,
    get_rename_info,
    ORIGINAL_NAME_PREFIX,
    RENAME_DATE_PREFIX,
    EXIF_USER_COMMENT_FIELD,
    PRESERVED_FILENAME_TAG,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _completed(returncode: int = 0, stdout: str = "", stderr: str = ""):
    """Create a mock subprocess.CompletedProcess."""
    cp = MagicMock(spec=subprocess.CompletedProcess)
    cp.returncode = returncode
    cp.stdout = stdout
    cp.stderr = stderr
    return cp


@pytest.fixture
def fake_exiftool(tmp_path):
    """An existing file standing in for the ExifTool executable."""
    exe = tmp_path / "exiftool"
    exe.write_text("")
    return str(exe)


def _argfile_of(cmd):
    return cmd[cmd.index("-@") + 1]


class _FakeExifTool:
    """Minimal in-memory stand-in for ExifTool's -@/-execute/-json behaviour."""

    def __init__(self):
        self.tags = {}  # path -> {"PreservedFileName": ..., "UserComment": ...}
        self.write_argfiles = []
        self.write_cmds = []

    def __call__(self, cmd, timeout):
        with open(_argfile_of(cmd), encoding="utf-8") as f:
            lines = f.read().splitlines()
        if "-json" in cmd:
            entries = []
            for path in lines:
                entry = {"SourceFile": path}
                entry.update(self.tags.get(path, {}))
                entries.append(entry)
            return _completed(0, stdout=json.dumps(entries))
        # Write: blocks separated by -execute
        self.write_argfiles.append(lines)
        self.write_cmds.append(cmd)
        block = []
        for line in lines + ["-execute"]:
            if line != "-execute":
                block.append(line)
                continue
            path = block[-1]
            value = block[1].split("=", 1)[1]
            self.tags.setdefault(path, {}).setdefault("PreservedFileName", value)
            block = []
        return _completed(0)


# ---------------------------------------------------------------------------
# batch_write_original_filenames
# ---------------------------------------------------------------------------
class TestBatchWrite:
    """Test batch write operations."""

    def test_empty_list(self, fake_exiftool):
        successes, errors = batch_write_original_filenames([], fake_exiftool)
        assert successes == []
        assert errors == []

    def test_missing_exiftool(self, tmp_path):
        f = tmp_path / "a.jpg"
        f.touch()
        successes, errors = batch_write_original_filenames(
            [(str(f), "a.jpg")], ""
        )
        assert len(successes) == 0
        assert len(errors) == 1

    def test_missing_file_reported(self, tmp_path, fake_exiftool):
        successes, errors = batch_write_original_filenames(
            [(str(tmp_path / "nope.jpg"), "orig.jpg")], fake_exiftool
        )
        assert successes == []
        assert "not found" in errors[0][1].lower()

    def test_each_file_gets_its_own_value(self, tmp_path, fake_exiftool):
        """Regression: one command with several -TAG=VALUE applied the last
        value to every file. Each file needs its own -execute block."""
        files = []
        for i in range(5):
            f = tmp_path / f"renamed_{i}.jpg"
            f.touch()
            files.append((str(f), f"DSC{i:05d}.jpg"))

        fake = _FakeExifTool()
        with patch.object(exif_undo_manager, "_run_exiftool", side_effect=fake):
            successes, errors = batch_write_original_filenames(files, fake_exiftool)

        assert errors == []
        assert len(successes) == 5
        for path, original in files:
            assert fake.tags[path]["PreservedFileName"] == original
        lines = fake.write_argfiles[0]
        assert lines.count("-execute") == 4
        assert f"-{PRESERVED_FILENAME_TAG}-=" in lines  # create-only
        cmd = fake.write_cmds[0]
        assert "-P" in cmd[cmd.index("-common_args"):]  # keep mtime in every block

    def test_file_not_confirmed_is_an_error(self, tmp_path, fake_exiftool):
        f = tmp_path / "clip.mp4"
        f.touch()

        def run(cmd, timeout):
            if "-json" in cmd:
                return _completed(0, stdout=json.dumps([{"SourceFile": str(f)}]))
            return _completed(1, stderr="Error: can't write this")

        with patch.object(exif_undo_manager, "_run_exiftool", side_effect=run):
            successes, errors = batch_write_original_filenames([(str(f), "C0001.MP4")], fake_exiftool)

        assert successes == []
        assert "can't write" in errors[0][1]

    def test_timeout_is_an_error(self, tmp_path, fake_exiftool):
        f = tmp_path / "a.jpg"
        f.touch()

        def run(cmd, timeout):
            if "-json" in cmd:
                return _completed(0, stdout="[]")
            raise subprocess.TimeoutExpired(cmd, timeout)

        with patch.object(exif_undo_manager, "_run_exiftool", side_effect=run):
            successes, errors = batch_write_original_filenames([(str(f), "a0.jpg")], fake_exiftool)

        assert successes == []
        assert "timed out" in errors[0][1].lower()

    def test_single_write_wrapper(self, tmp_path, fake_exiftool):
        f = tmp_path / "DSC00001.jpg"
        f.touch()
        fake = _FakeExifTool()
        with patch.object(exif_undo_manager, "_run_exiftool", side_effect=fake):
            ok, msg = write_original_filename_to_exif(str(f), "ORIG.jpg", fake_exiftool)
        assert ok is True
        assert "written" in msg.lower()

    def test_single_write_missing_file(self, tmp_path, fake_exiftool):
        ok, msg = write_original_filename_to_exif(
            str(tmp_path / "nope.jpg"), "orig.jpg", fake_exiftool
        )
        assert ok is False
        assert "not found" in msg.lower()


# ---------------------------------------------------------------------------
# Reading (batch_get_original_filenames, get_original_filename_from_exif,
# get_rename_info)
# ---------------------------------------------------------------------------
class TestRead:

    def test_no_exiftool(self, tmp_path):
        f = tmp_path / "a.jpg"
        f.touch()
        result = batch_get_original_filenames([str(f)], "")
        assert result[str(f)] is None

    def test_preserved_filename_preferred(self, tmp_path, fake_exiftool):
        f1 = tmp_path / "renamed1.jpg"
        f2 = tmp_path / "renamed2.jpg"
        f1.touch()
        f2.touch()
        json_out = json.dumps([
            {"SourceFile": str(f1), "PreservedFileName": "DSC01.jpg",
             "UserComment": "OriginalName: OLD.jpg | RenameDate: 2026:01:01 12:00:00"},
            {"SourceFile": str(f2),
             "UserComment": "OriginalName: DSC02.jpg | RenameDate: 2026:01:01 12:01:00"},
        ])
        with patch.object(exif_undo_manager, "_run_exiftool", return_value=_completed(0, stdout=json_out)):
            result = batch_get_original_filenames([str(f1), str(f2)], fake_exiftool)

        assert result[str(f1)] == "DSC01.jpg"
        assert result[str(f2)] == "DSC02.jpg"  # legacy format still read

    def test_nonzero_exit_still_parsed(self, tmp_path, fake_exiftool):
        """ExifTool exits 1 if one file is unreadable but prints JSON for the rest."""
        f = tmp_path / "ok.jpg"
        f.touch()
        json_out = json.dumps([{"SourceFile": str(f), "PreservedFileName": "A.jpg"}])
        with patch.object(exif_undo_manager, "_run_exiftool",
                          return_value=_completed(1, stdout=json_out, stderr="Error: File not found")):
            result = batch_get_original_filenames([str(f)], fake_exiftool)
        assert result[str(f)] == "A.jpg"

    def test_plain_user_comment_ignored(self, tmp_path, fake_exiftool):
        f = tmp_path / "photo.jpg"
        f.touch()
        json_out = json.dumps([{"SourceFile": str(f), "UserComment": "Holiday at the lake"}])
        with patch.object(exif_undo_manager, "_run_exiftool", return_value=_completed(0, stdout=json_out)):
            assert get_original_filename_from_exif(str(f), fake_exiftool) is None

    def test_missing_file(self, tmp_path, fake_exiftool):
        assert get_original_filename_from_exif(str(tmp_path / "nope.jpg"), fake_exiftool) is None

    def test_rename_info_legacy_date(self, tmp_path, fake_exiftool):
        f = tmp_path / "img.jpg"
        f.touch()
        json_out = json.dumps([{"SourceFile": str(f),
                                "UserComment": "OriginalName: DSC.jpg | RenameDate: 2026:02:07 10:00:00"}])
        with patch.object(exif_undo_manager, "_run_exiftool", return_value=_completed(0, stdout=json_out)):
            info = get_rename_info(str(f), fake_exiftool)
        assert info == {"original_filename": "DSC.jpg", "rename_date": "2026:02:07 10:00:00"}

    def test_rename_info_nonexistent_file(self, tmp_path, fake_exiftool):
        info = get_rename_info(str(tmp_path / "nope.jpg"), fake_exiftool)
        assert info == {"original_filename": None, "rename_date": None}


# ---------------------------------------------------------------------------
# clear_original_filename_from_exif
# ---------------------------------------------------------------------------
class TestClearOriginalFilename:

    def test_missing_file(self, tmp_path, fake_exiftool):
        ok, _ = clear_original_filename_from_exif(str(tmp_path / "nope.jpg"), fake_exiftool)
        assert ok is False

    @pytest.mark.parametrize("comment, clears_comment", [
        ("OriginalName: DSC.jpg | RenameDate: 2026:01:01 10:00:00", True),
        ("My own comment", False),
    ])
    def test_user_comment_only_cleared_if_ours(self, tmp_path, fake_exiftool, comment, clears_comment):
        f = tmp_path / "img.jpg"
        f.touch()
        calls = []

        def run(cmd, timeout):
            calls.append(cmd)
            if "-json" in cmd:
                return _completed(0, stdout=json.dumps([{"SourceFile": str(f), "UserComment": comment}]))
            return _completed(0)

        with patch.object(exif_undo_manager, "_run_exiftool", side_effect=run):
            ok, msg = clear_original_filename_from_exif(str(f), fake_exiftool)

        assert ok is True
        assert "cleared" in msg.lower()
        write_cmd = calls[-1]
        assert "-P" in write_cmd
        assert f"-{PRESERVED_FILENAME_TAG}=" in write_cmd
        assert (f"-{EXIF_USER_COMMENT_FIELD}=" in write_cmd) is clears_comment


# ---------------------------------------------------------------------------
# Write timeouts follow the file size; a killed write leaves no temp files
# ---------------------------------------------------------------------------
GIB = 1024 ** 3


@pytest.fixture
def huge_files(monkeypatch):
    """Report a size of 10 GiB for the paths added to the returned set."""
    huge = set()
    real_getsize = os.path.getsize
    monkeypatch.setattr(os.path, "getsize", lambda p: 10 * GIB if p in huge else real_getsize(p))
    return huge


class TestWriteTimeouts:

    def test_batch_write_timeout_follows_size(self, tmp_path, fake_exiftool, huge_files):
        f = tmp_path / "clip.mov"
        f.touch()
        huge_files.add(str(f))
        timeouts = []

        def run(cmd, timeout):
            if "-json" in cmd:
                return _completed(0, stdout="[]")
            timeouts.append(timeout)
            return _completed(0)

        with patch.object(exif_undo_manager, "_run_exiftool", side_effect=run):
            batch_write_original_filenames([(str(f), "C0001.MOV")], fake_exiftool)

        assert timeouts and timeouts[0] >= 10 * GIB // (5 * 1024 * 1024)

    def test_clear_timeout_follows_size(self, tmp_path, fake_exiftool, huge_files):
        f = tmp_path / "clip.mov"
        f.touch()
        huge_files.add(str(f))
        timeouts = []

        def run(cmd, timeout):
            timeouts.append(timeout)
            if "-json" in cmd:
                return _completed(0, stdout="[]")
            return _completed(0)

        with patch.object(exif_undo_manager, "_run_exiftool", side_effect=run):
            clear_original_filename_from_exif(str(f), fake_exiftool)

        assert timeouts[-1] >= 10 * GIB // (5 * 1024 * 1024)

    def test_exif_restore_timeout_follows_size(self, tmp_path, fake_exiftool, huge_files, monkeypatch):
        from modules.exif_processor import restore_exif_timestamps
        f = tmp_path / "clip.mov"
        f.touch()
        huge_files.add(str(f))
        run = MagicMock(return_value=_completed(0))
        monkeypatch.setattr("subprocess.run", run)

        ok, _msg = restore_exif_timestamps(str(f), {"QuickTime:CreateDate": "2024:01:01 10:00:00"}, fake_exiftool)

        assert ok
        assert run.call_args.kwargs["timeout"] >= 10 * GIB // (5 * 1024 * 1024)

    def test_time_shift_timeout_follows_size(self, tmp_path, huge_files, monkeypatch):
        from modules.dialogs.exif_time_shift_dialog import TimeShiftWorker
        f = str(tmp_path / "clip.mov")
        huge_files.add(f)
        run = MagicMock(return_value=_completed(0))
        monkeypatch.setattr("subprocess.run", run)
        monkeypatch.setattr("modules.exif_processor.get_exiftool_metadata_batch",
                            lambda paths, *a, **k: {p: {"QuickTime:CreateDate": "2024:01:01 10:00:00"} for p in paths})

        TimeShiftWorker([f], 1, 0, "forward", "/fake/exiftool").run()

        assert run.call_args.kwargs["timeout"] >= 10 * GIB // (5 * 1024 * 1024)

    def test_batch_write_timeout_removes_own_tmp_files(self, tmp_path, fake_exiftool):
        a = tmp_path / "a.jpg"
        b = tmp_path / "b.jpg"
        a.touch()
        b.touch()
        stale = tmp_path / "b.jpg_exiftool_tmp"  # left by an earlier crash
        stale.write_text("keep me")

        def run(cmd, timeout):
            if "-json" in cmd:
                return _completed(0, stdout="[]")
            (tmp_path / "a.jpg_exiftool_tmp").write_text("partial")  # killed mid-write
            raise subprocess.TimeoutExpired(cmd, timeout)

        with patch.object(exif_undo_manager, "_run_exiftool", side_effect=run):
            successes, errors = batch_write_original_filenames(
                [(str(a), "A0.jpg"), (str(b), "B0.jpg")], fake_exiftool)

        assert successes == [] and len(errors) == 2
        assert not (tmp_path / "a.jpg_exiftool_tmp").exists()
        assert stale.read_text() == "keep me"

    def test_time_shift_timeout_removes_own_tmp_files(self, tmp_path, monkeypatch):
        from modules.dialogs.exif_time_shift_dialog import TimeShiftWorker
        f = str(tmp_path / "a.jpg")

        def run(cmd, **kwargs):
            open(f + "_exiftool_tmp", "w").close()
            raise subprocess.TimeoutExpired(cmd, kwargs["timeout"])

        monkeypatch.setattr("subprocess.run", run)
        monkeypatch.setattr("modules.exif_processor.get_exiftool_metadata_batch",
                            lambda paths, *a, **k: {p: {"EXIF:DateTimeOriginal": "2024:01:01 10:00:00"} for p in paths})
        worker = TimeShiftWorker([f], 1, 0, "forward", "/fake/exiftool")
        results = []
        worker.finished_signal.connect(lambda *args: results.append(args))
        worker.run()

        assert results[0][1] == [(f, "ExifTool operation timed out")]
        assert not os.path.exists(f + "_exiftool_tmp")


# ---------------------------------------------------------------------------
# Argument files: one argument per line, no injection
# ---------------------------------------------------------------------------
class TestArgfileInjection:

    def test_line_break_in_original_name_is_refused(self, tmp_path, fake_exiftool):
        good = tmp_path / "good.jpg"
        evil = tmp_path / "evil.jpg"
        good.touch()
        evil.touch()
        fake = _FakeExifTool()
        with patch.object(exif_undo_manager, "_run_exiftool", side_effect=fake):
            successes, errors = batch_write_original_filenames(
                [(str(good), "DSC1.jpg"), (str(evil), "x.jpg\n-o\n/tmp/x")], fake_exiftool)

        assert successes == [str(good)]
        assert errors == [(str(evil), "Unsupported characters in file name")]
        assert fake.write_argfiles == [[f"-{PRESERVED_FILENAME_TAG}-=",
                                        f"-{PRESERVED_FILENAME_TAG}=DSC1.jpg", str(good)]]

    @pytest.mark.skipif(os.name == "nt", reason="Windows file names cannot contain line breaks")
    def test_line_break_in_file_name_is_refused(self, tmp_path, fake_exiftool):
        evil = tmp_path / "evil\n-FileName=pwned.jpg"
        evil.touch()
        run = MagicMock()
        with patch.object(exif_undo_manager, "_run_exiftool", run):
            successes, errors = batch_write_original_filenames([(str(evil), "a.jpg")], fake_exiftool)
            info = batch_get_original_filenames([str(evil)], fake_exiftool)
        assert successes == [] and errors == [(str(evil), "Unsupported characters in file name")]
        assert info == {str(evil): None}
        run.assert_not_called()

    def test_relative_name_starting_with_dash(self, tmp_path, fake_exiftool, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "-o.jpg").touch()
        fake = _FakeExifTool()
        with patch.object(exif_undo_manager, "_run_exiftool", side_effect=fake):
            batch_write_original_filenames([("-o.jpg", "a.jpg")], fake_exiftool)
        assert fake.write_argfiles[0][-1] == "./-o.jpg"

    def test_run_exiftool_on_files_drops_unsafe_names(self, tmp_path):
        from modules.exif_service_new import run_exiftool_on_files, argfile_safe
        lines = []

        def run(cmd, **kwargs):
            with open(cmd[cmd.index("-@") + 1], encoding="utf-8") as f:
                lines.extend(f.read().splitlines())
            return _completed(0)

        with patch("subprocess.run", side_effect=run):
            run_exiftool_on_files("/fake/exiftool", ["-AllDates+=1:00:00"],
                                  [str(tmp_path / "a.jpg"), "b.jpg\n-o\nx", "#c.jpg"])
            only_unsafe = run_exiftool_on_files("/fake/exiftool", [], ["x\r-o"])

        assert lines == [str(tmp_path / "a.jpg"), "./#c.jpg"]
        assert only_unsafe.returncode == 1 and "Unsupported" in only_unsafe.stderr
        assert not argfile_safe("a\0b") and argfile_safe("Straße 😀.jpg")


# ---------------------------------------------------------------------------
# has_original_filename
# ---------------------------------------------------------------------------
class TestHasOriginalFilename:

    @patch("modules.exif_undo_manager.get_original_filename_from_exif", return_value="DSC.jpg")
    def test_returns_true(self, _mock):
        assert has_original_filename("file.jpg", "exiftool") is True

    @patch("modules.exif_undo_manager.get_original_filename_from_exif", return_value=None)
    def test_returns_false(self, _mock):
        assert has_original_filename("file.jpg", "exiftool") is False

    @patch("modules.exif_undo_manager.get_original_filename_from_exif", return_value="")
    def test_empty_string_returns_false(self, _mock):
        assert has_original_filename("file.jpg", "exiftool") is False


# ---------------------------------------------------------------------------
# Constants consistency
# ---------------------------------------------------------------------------
class TestConstants:

    def test_prefix_values(self):
        assert ORIGINAL_NAME_PREFIX == "OriginalName: "
        assert RENAME_DATE_PREFIX == " | RenameDate: "
        assert EXIF_USER_COMMENT_FIELD == "EXIF:UserComment"
        assert PRESERVED_FILENAME_TAG == "XMP-xmpMM:PreservedFileName"
