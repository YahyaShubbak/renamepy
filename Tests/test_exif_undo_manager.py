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
        assert f"-{PRESERVED_FILENAME_TAG}=" in write_cmd
        assert (f"-{EXIF_USER_COMMENT_FIELD}=" in write_cmd) is clears_comment


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
