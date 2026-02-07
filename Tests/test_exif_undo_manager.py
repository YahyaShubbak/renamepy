#!/usr/bin/env python3
"""
Unit tests for modules/exif_undo_manager.py

Tests the EXIF-based undo persistence layer: writing, reading, batch
operations, clearing, and edge cases.  All ExifTool calls are mocked.
"""

import os
import sys
import json
import subprocess
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.exif_undo_manager import (
    write_original_filename_to_exif,
    get_original_filename_from_exif,
    batch_write_original_filenames,
    batch_get_original_filenames,
    clear_original_filename_from_exif,
    has_original_filename,
    get_rename_info,
    _read_existing_user_comment,
    ORIGINAL_NAME_PREFIX,
    RENAME_DATE_PREFIX,
    EXIF_USER_COMMENT_FIELD,
)


FAKE_EXIFTOOL = r"C:\fake\exiftool.exe"


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


# ---------------------------------------------------------------------------
# write_original_filename_to_exif
# ---------------------------------------------------------------------------
class TestWriteOriginalFilename:
    """Test individual write operations."""

    def test_missing_file_returns_error(self, tmp_path):
        ok, msg = write_original_filename_to_exif(
            str(tmp_path / "nope.jpg"), "orig.jpg", FAKE_EXIFTOOL
        )
        assert ok is False
        assert "not found" in msg.lower()

    def test_missing_exiftool_returns_error(self, tmp_path):
        f = tmp_path / "img.jpg"
        f.touch()
        ok, msg = write_original_filename_to_exif(str(f), "orig.jpg", "")
        assert ok is False
        assert "not found" in msg.lower()

    @patch("modules.exif_undo_manager.subprocess.run")
    @patch("modules.exif_undo_manager._read_existing_user_comment", return_value=None)
    def test_successful_write(self, _mock_read, mock_run, tmp_path):
        f = tmp_path / "DSC00001.jpg"
        f.touch()
        mock_run.return_value = _completed(0)

        with patch("os.path.exists", return_value=True):
            ok, msg = write_original_filename_to_exif(
                str(f), "DSC00001.jpg", FAKE_EXIFTOOL
            )

        assert ok is True
        assert "written" in msg.lower()
        # Verify the constructed command
        args = mock_run.call_args[0][0]
        assert "-overwrite_original" in args
        written_tag = [a for a in args if EXIF_USER_COMMENT_FIELD in a]
        assert len(written_tag) == 1
        assert ORIGINAL_NAME_PREFIX in written_tag[0]
        assert RENAME_DATE_PREFIX.strip() in written_tag[0]

    @patch("modules.exif_undo_manager.subprocess.run")
    @patch("modules.exif_undo_manager._read_existing_user_comment", return_value=None)
    def test_write_without_timestamp(self, _mock_read, mock_run, tmp_path):
        f = tmp_path / "DSC00002.jpg"
        f.touch()
        mock_run.return_value = _completed(0)

        with patch("os.path.exists", return_value=True):
            ok, _ = write_original_filename_to_exif(
                str(f), "DSC00002.jpg", FAKE_EXIFTOOL, add_timestamp=False
            )

        assert ok is True
        tag_arg = [a for a in mock_run.call_args[0][0] if EXIF_USER_COMMENT_FIELD in a][0]
        assert RENAME_DATE_PREFIX.strip() not in tag_arg

    @patch("modules.exif_undo_manager.subprocess.run")
    @patch("modules.exif_undo_manager._read_existing_user_comment", return_value=None)
    def test_exiftool_failure(self, _mock_read, mock_run, tmp_path):
        f = tmp_path / "DSC00003.jpg"
        f.touch()
        mock_run.return_value = _completed(1, stderr="write error")

        with patch("os.path.exists", return_value=True):
            ok, msg = write_original_filename_to_exif(
                str(f), "DSC00003.jpg", FAKE_EXIFTOOL
            )

        assert ok is False
        assert "error" in msg.lower()

    @patch("modules.exif_undo_manager.subprocess.run", side_effect=subprocess.TimeoutExpired("cmd", 30))
    @patch("modules.exif_undo_manager._read_existing_user_comment", return_value=None)
    def test_timeout(self, _mock_read, _mock_run, tmp_path):
        f = tmp_path / "DSC00004.jpg"
        f.touch()

        with patch("os.path.exists", return_value=True):
            ok, msg = write_original_filename_to_exif(
                str(f), "DSC00004.jpg", FAKE_EXIFTOOL
            )

        assert ok is False
        assert "timed out" in msg.lower()


# ---------------------------------------------------------------------------
# get_original_filename_from_exif
# ---------------------------------------------------------------------------
class TestGetOriginalFilename:
    """Test individual read operations."""

    def test_missing_file(self, tmp_path):
        result = get_original_filename_from_exif(
            str(tmp_path / "nope.jpg"), FAKE_EXIFTOOL
        )
        assert result is None

    @patch("modules.exif_undo_manager.subprocess.run")
    def test_reads_original_name(self, mock_run, tmp_path):
        f = tmp_path / "renamed.jpg"
        f.touch()
        mock_run.return_value = _completed(
            0, stdout="OriginalName: DSC00100.jpg | RenameDate: 2026:01:01 12:00:00"
        )

        with patch("os.path.exists", return_value=True):
            result = get_original_filename_from_exif(str(f), FAKE_EXIFTOOL)

        assert result == "DSC00100.jpg"

    @patch("modules.exif_undo_manager.subprocess.run")
    def test_no_original_name_returns_none(self, mock_run, tmp_path):
        f = tmp_path / "img.jpg"
        f.touch()
        mock_run.return_value = _completed(0, stdout="Just a regular comment")

        with patch("os.path.exists", return_value=True):
            result = get_original_filename_from_exif(str(f), FAKE_EXIFTOOL)

        assert result is None

    @patch("modules.exif_undo_manager.subprocess.run")
    def test_empty_output(self, mock_run, tmp_path):
        f = tmp_path / "img.jpg"
        f.touch()
        mock_run.return_value = _completed(0, stdout="")

        with patch("os.path.exists", return_value=True):
            result = get_original_filename_from_exif(str(f), FAKE_EXIFTOOL)

        assert result is None


# ---------------------------------------------------------------------------
# batch_write_original_filenames
# ---------------------------------------------------------------------------
class TestBatchWrite:
    """Test batch write operations."""

    def test_empty_list(self):
        successes, errors = batch_write_original_filenames([], FAKE_EXIFTOOL)
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

    @patch("modules.exif_undo_manager.subprocess.run")
    def test_batch_success(self, mock_run, tmp_path):
        files = []
        for i in range(5):
            f = tmp_path / f"DSC{i:05d}.jpg"
            f.touch()
            files.append((str(f), f"DSC{i:05d}.jpg"))

        mock_run.return_value = _completed(0)

        with patch("os.path.exists", return_value=True):
            successes, errors = batch_write_original_filenames(files, FAKE_EXIFTOOL)

        assert len(errors) == 0
        assert len(successes) == 5

    @patch("modules.exif_undo_manager.subprocess.run")
    @patch("modules.exif_undo_manager.write_original_filename_to_exif")
    def test_batch_fallback_on_error(self, mock_individual, mock_run, tmp_path):
        """When batch fails, falls back to individual writes."""
        f = tmp_path / "img.jpg"
        f.touch()
        mock_run.return_value = _completed(1, stderr="batch error")
        mock_individual.return_value = (True, "ok")

        with patch("os.path.exists", return_value=True):
            successes, errors = batch_write_original_filenames(
                [(str(f), "img.jpg")], FAKE_EXIFTOOL
            )

        assert mock_individual.called
        assert len(successes) == 1


# ---------------------------------------------------------------------------
# batch_get_original_filenames
# ---------------------------------------------------------------------------
class TestBatchGet:
    """Test batch read operations."""

    def test_no_exiftool(self, tmp_path):
        f = tmp_path / "a.jpg"
        f.touch()
        result = batch_get_original_filenames([str(f)], "")
        assert result[str(f)] is None

    @patch("modules.exif_undo_manager.subprocess.run")
    def test_batch_json_parse(self, mock_run, tmp_path):
        f1 = tmp_path / "renamed1.jpg"
        f2 = tmp_path / "renamed2.jpg"
        f1.touch()
        f2.touch()

        json_out = json.dumps([
            {
                "SourceFile": str(f1),
                "FileName": "renamed1.jpg",
                "UserComment": "OriginalName: DSC01.jpg | RenameDate: 2026:01:01 12:00:00",
            },
            {
                "SourceFile": str(f2),
                "FileName": "renamed2.jpg",
                "UserComment": "OriginalName: DSC02.jpg | RenameDate: 2026:01:01 12:01:00",
            },
        ])
        mock_run.return_value = _completed(0, stdout=json_out)

        with patch("os.path.exists", return_value=True):
            result = batch_get_original_filenames([str(f1), str(f2)], FAKE_EXIFTOOL)

        assert result[str(f1)] == "DSC01.jpg"
        assert result[str(f2)] == "DSC02.jpg"

    @patch("modules.exif_undo_manager.subprocess.run")
    def test_no_original_returns_none(self, mock_run, tmp_path):
        f = tmp_path / "photo.jpg"
        f.touch()

        json_out = json.dumps([
            {
                "SourceFile": str(f),
                "FileName": "photo.jpg",
                "UserComment": "",
            },
        ])
        mock_run.return_value = _completed(0, stdout=json_out)

        with patch("os.path.exists", return_value=True):
            result = batch_get_original_filenames([str(f)], FAKE_EXIFTOOL)

        assert result[str(f)] is None


# ---------------------------------------------------------------------------
# clear_original_filename_from_exif
# ---------------------------------------------------------------------------
class TestClearOriginalFilename:

    def test_missing_file(self, tmp_path):
        ok, _ = clear_original_filename_from_exif(
            str(tmp_path / "nope.jpg"), FAKE_EXIFTOOL
        )
        assert ok is False

    @patch("modules.exif_undo_manager.subprocess.run")
    def test_clear_success(self, mock_run, tmp_path):
        f = tmp_path / "img.jpg"
        f.touch()
        mock_run.return_value = _completed(0)

        with patch("os.path.exists", return_value=True):
            ok, msg = clear_original_filename_from_exif(str(f), FAKE_EXIFTOOL)

        assert ok is True
        assert "cleared" in msg.lower()


# ---------------------------------------------------------------------------
# has_original_filename
# ---------------------------------------------------------------------------
class TestHasOriginalFilename:

    @patch("modules.exif_undo_manager.get_original_filename_from_exif", return_value="DSC.jpg")
    def test_returns_true(self, _mock):
        assert has_original_filename("file.jpg", FAKE_EXIFTOOL) is True

    @patch("modules.exif_undo_manager.get_original_filename_from_exif", return_value=None)
    def test_returns_false(self, _mock):
        assert has_original_filename("file.jpg", FAKE_EXIFTOOL) is False

    @patch("modules.exif_undo_manager.get_original_filename_from_exif", return_value="")
    def test_empty_string_returns_false(self, _mock):
        assert has_original_filename("file.jpg", FAKE_EXIFTOOL) is False


# ---------------------------------------------------------------------------
# get_rename_info
# ---------------------------------------------------------------------------
class TestGetRenameInfo:

    @patch("modules.exif_undo_manager.subprocess.run")
    def test_parses_full_info(self, mock_run, tmp_path):
        f = tmp_path / "img.jpg"
        f.touch()
        mock_run.return_value = _completed(
            0, stdout="OriginalName: DSC.jpg | RenameDate: 2026:02:07 10:00:00"
        )

        with patch("os.path.exists", return_value=True):
            info = get_rename_info(str(f), FAKE_EXIFTOOL)

        assert info["original_filename"] == "DSC.jpg"
        assert info["rename_date"] == "2026:02:07 10:00:00"

    @patch("modules.exif_undo_manager.subprocess.run")
    def test_no_metadata(self, mock_run, tmp_path):
        f = tmp_path / "img.jpg"
        f.touch()
        mock_run.return_value = _completed(0, stdout="")

        with patch("os.path.exists", return_value=True):
            info = get_rename_info(str(f), FAKE_EXIFTOOL)

        assert info["original_filename"] is None
        assert info["rename_date"] is None

    def test_nonexistent_file(self, tmp_path):
        info = get_rename_info(str(tmp_path / "nope.jpg"), FAKE_EXIFTOOL)
        assert info["original_filename"] is None
        assert info["rename_date"] is None


# ---------------------------------------------------------------------------
# _read_existing_user_comment
# ---------------------------------------------------------------------------
class TestReadExistingUserComment:

    @patch("modules.exif_undo_manager.subprocess.run")
    def test_reads_value(self, mock_run):
        mock_run.return_value = _completed(0, stdout="Some user comment")
        with patch("os.path.exists", return_value=True):
            result = _read_existing_user_comment("img.jpg", FAKE_EXIFTOOL)
        assert result == "Some user comment"

    @patch("modules.exif_undo_manager.subprocess.run")
    def test_empty_returns_none(self, mock_run):
        mock_run.return_value = _completed(0, stdout="")
        result = _read_existing_user_comment("img.jpg", FAKE_EXIFTOOL)
        assert result is None

    @patch("modules.exif_undo_manager.subprocess.run", side_effect=Exception("fail"))
    def test_exception_returns_none(self, _mock):
        result = _read_existing_user_comment("img.jpg", FAKE_EXIFTOOL)
        assert result is None


# ---------------------------------------------------------------------------
# Constants consistency
# ---------------------------------------------------------------------------
class TestConstants:

    def test_prefix_values(self):
        assert ORIGINAL_NAME_PREFIX == "OriginalName: "
        assert RENAME_DATE_PREFIX == " | RenameDate: "
        assert EXIF_USER_COMMENT_FIELD == "EXIF:UserComment"
