#!/usr/bin/env python3
"""
Unit tests for modules/file_utilities.py

Covers pure functions with no external dependencies:
- Media file detection (is_image_file, is_video_file, is_media_file)
- Natural sort key generation
- Filename sanitization
- Path validation and safe path generation
- Directory scanning
"""

import os
import sys
import pytest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.file_utilities import (
    is_image_file,
    is_video_file,
    is_media_file,
    natural_sort_key,
    sanitize_filename,
    sanitize_final_filename,
    validate_path_length,
    validate_path,
    get_safe_target_path,
    get_safe_filename,
    scan_directory,
    scan_directory_recursive,
    check_file_access,
    FileConstants,
)


# ---------------------------------------------------------------------------
# Media file detection
# ---------------------------------------------------------------------------
class TestIsImageFile:
    """Test image and RAW file detection."""

    @pytest.mark.parametrize("filename, expected", [
        ("photo.jpg", True),
        ("photo.JPG", True),
        ("photo.jpeg", True),
        ("photo.JPEG", True),
        ("photo.png", True),
        ("photo.tiff", True),
        ("photo.cr2", True),
        ("photo.CR2", True),
        ("photo.nef", True),
        ("photo.NEF", True),
        ("photo.arw", True),
        ("photo.ARW", True),
        ("photo.dng", True),
        ("photo.raf", True),
        ("photo.rw2", True),
        ("photo.orf", True),
    ])
    def test_common_image_extensions(self, filename: str, expected: bool):
        assert is_image_file(filename) is expected

    @pytest.mark.parametrize("filename", [
        "document.txt", "report.pdf", "data.csv", "script.py",
        "music.mp3", "video.mp4", "archive.zip", "noextension",
    ])
    def test_non_image_files(self, filename: str):
        assert is_image_file(filename) is False

    def test_empty_filename(self):
        assert is_image_file("") is False


class TestIsVideoFile:
    """Test video file detection."""

    @pytest.mark.parametrize("filename, expected", [
        ("clip.mp4", True),
        ("clip.MP4", True),
        ("clip.mov", True),
        ("clip.MOV", True),
        ("clip.avi", True),
        ("clip.mkv", True),
        ("clip.m4v", True),
        ("clip.mts", True),
    ])
    def test_common_video_extensions(self, filename: str, expected: bool):
        assert is_video_file(filename) is expected

    @pytest.mark.parametrize("filename", [
        "photo.jpg", "document.txt", "music.mp3",
    ])
    def test_non_video_files(self, filename: str):
        assert is_video_file(filename) is False


class TestIsMediaFile:
    """Test combined media detection (images + videos)."""

    @pytest.mark.parametrize("filename, expected", [
        ("photo.jpg", True),
        ("photo.CR2", True),
        ("clip.mp4", True),
        ("clip.MOV", True),
        ("document.txt", False),
        ("data.csv", False),
        ("script.py", False),
    ])
    def test_media_detection(self, filename: str, expected: bool):
        assert is_media_file(filename) is expected


# ---------------------------------------------------------------------------
# Natural sort key
# ---------------------------------------------------------------------------
class TestNaturalSortKey:
    """Test natural (human-friendly) sorting of filenames."""

    def test_numeric_sorting(self):
        """Numbers should sort numerically, not lexicographically."""
        filenames = ["DSC10", "DSC9", "DSC100", "DSC2", "DSC1"]
        sorted_names = sorted(filenames, key=natural_sort_key)
        assert sorted_names == ["DSC1", "DSC2", "DSC9", "DSC10", "DSC100"]

    def test_mixed_case_insensitive(self):
        """Sorting should be case-insensitive."""
        filenames = ["Bravo", "alpha", "Charlie"]
        sorted_names = sorted(filenames, key=natural_sort_key)
        assert sorted_names == ["alpha", "Bravo", "Charlie"]

    def test_realistic_camera_filenames(self):
        """Realistic DSC-style filenames should sort correctly."""
        filenames = ["DSC00100.jpg", "DSC00009.jpg", "DSC00010.jpg", "DSC00001.jpg"]
        sorted_names = sorted(filenames, key=natural_sort_key)
        assert sorted_names == [
            "DSC00001.jpg", "DSC00009.jpg", "DSC00010.jpg", "DSC00100.jpg"
        ]

    def test_empty_string(self):
        """Empty string should not raise."""
        key = natural_sort_key("")
        assert isinstance(key, list)


# ---------------------------------------------------------------------------
# Filename sanitization
# ---------------------------------------------------------------------------
class TestSanitizeFilename:
    """Test invalid-character removal and filename cleanup."""

    def test_clean_filename_unchanged(self):
        assert sanitize_filename("normal_file.jpg") == "normal_file.jpg"

    @pytest.mark.parametrize("char", list('<>:"/\\|?*'))
    def test_invalid_characters_replaced(self, char: str):
        result = sanitize_filename(f"file{char}name.jpg")
        assert char not in result

    def test_multiple_underscores_collapsed(self):
        result = sanitize_filename("file___name.jpg")
        assert "___" not in result
        assert "_" in result

    def test_control_characters_removed(self):
        result = sanitize_filename("file\x00\x01name.jpg")
        assert "\x00" not in result
        assert "\x01" not in result

    def test_trailing_dots_stripped(self):
        result = sanitize_filename("file...")
        assert not result.endswith(".")

    def test_empty_input_returns_empty(self):
        assert sanitize_filename("") == ""

    def test_whitespace_only_returns_empty(self):
        assert sanitize_filename("   ") == ""

    def test_length_limit(self):
        """Very long filenames should be truncated to ≤200 chars."""
        long_name = "a" * 300 + ".jpg"
        result = sanitize_filename(long_name)
        assert len(result) <= 200


class TestSanitizeFinalFilename:
    """Test final filename sanitization with fallback."""

    def test_normal_name_passes_through(self):
        assert sanitize_final_filename("photo.jpg") == "photo.jpg"

    def test_empty_gets_fallback(self):
        result = sanitize_final_filename("")
        assert result == "unnamed_file"

    def test_only_invalid_chars_gets_fallback(self):
        result = sanitize_final_filename('???')
        assert result != ""  # Should have some fallback


# ---------------------------------------------------------------------------
# Path validation
# ---------------------------------------------------------------------------
class TestValidatePathLength:
    """Test path length validation (platform-aware)."""

    def test_short_path_valid(self):
        assert validate_path_length("C:\\short\\path.jpg") is True

    def test_very_long_path_invalid(self):
        """A path exceeding even long-path limits should fail."""
        long_path = "C:\\" + "a" * 40000 + ".jpg"
        assert validate_path_length(long_path) is False

    def test_filename_component_over_255_invalid(self):
        """Filename > 255 chars should fail regardless of total path length."""
        long_name = "a" * 256 + ".jpg"
        path = "C:\\Photos\\" + long_name
        assert validate_path_length(path) is False

    def test_filename_component_exactly_255_valid(self):
        """Filename of exactly 255 chars (incl extension) should be valid."""
        name = "a" * 251 + ".jpg"  # 251 + 4 = 255
        path = "C:\\Photos\\" + name
        assert validate_path_length(path) is True

    def test_normal_length_path_valid(self):
        path = "C:\\Users\\photographer\\Pictures\\Vacation\\" + "photo_001.jpg"
        assert validate_path_length(path) is True


class TestValidatePath:
    """Test comprehensive path validation."""

    def test_empty_path(self):
        is_valid, msg = validate_path("")
        assert is_valid is False
        assert "empty" in msg.lower()

    def test_nonexistent_path(self):
        is_valid, msg = validate_path("/nonexistent/file.jpg")
        assert is_valid is False

    def test_valid_media_file(self, tmp_path):
        test_file = tmp_path / "test.jpg"
        test_file.touch()
        is_valid, msg = validate_path(str(test_file))
        assert is_valid is True
        assert msg == "Valid"

    def test_non_media_file(self, tmp_path):
        test_file = tmp_path / "test.txt"
        test_file.touch()
        is_valid, msg = validate_path(str(test_file))
        assert is_valid is False
        assert "media" in msg.lower()

    def test_directory_not_valid(self, tmp_path):
        is_valid, msg = validate_path(str(tmp_path))
        assert is_valid is False


# ---------------------------------------------------------------------------
# Safe target path
# ---------------------------------------------------------------------------
class TestGetSafeTargetPath:
    """Test conflict-free target path generation."""

    def test_no_conflict(self, tmp_path):
        original = tmp_path / "original.jpg"
        original.touch()
        result = get_safe_target_path(str(original), "renamed.jpg")
        assert result == str(tmp_path / "renamed.jpg")

    def test_with_conflict_appends_counter(self, tmp_path):
        original = tmp_path / "original.jpg"
        conflict = tmp_path / "renamed.jpg"
        original.touch()
        conflict.touch()

        result = get_safe_target_path(str(original), "renamed.jpg")
        assert result != str(conflict)
        assert "renamed(1).jpg" in result

    def test_multiple_conflicts(self, tmp_path):
        original = tmp_path / "original.jpg"
        original.touch()
        (tmp_path / "renamed.jpg").touch()
        (tmp_path / "renamed(1).jpg").touch()

        result = get_safe_target_path(str(original), "renamed.jpg")
        assert "renamed(2).jpg" in result

    def test_same_name_is_safe(self, tmp_path):
        """Renaming a file to itself should return the same path."""
        original = tmp_path / "photo.jpg"
        original.touch()
        result = get_safe_target_path(str(original), "photo.jpg")
        assert os.path.normcase(result) == os.path.normcase(str(original))


class TestGetSafeFilename:
    """Test safe filename generation in a directory."""

    def test_no_conflict(self, tmp_path):
        result = get_safe_filename(str(tmp_path), "new_file.jpg")
        assert result == "new_file.jpg"

    def test_with_conflict(self, tmp_path):
        (tmp_path / "existing.jpg").touch()
        result = get_safe_filename(str(tmp_path), "existing.jpg")
        assert result == "existing(1).jpg"


# ---------------------------------------------------------------------------
# Directory scanning
# ---------------------------------------------------------------------------
class TestScanDirectory:
    """Test directory scanning for media files."""

    def _create_test_tree(self, base: Path) -> None:
        """Helper: create a small directory tree with mixed file types."""
        (base / "photo1.jpg").touch()
        (base / "photo2.CR2").touch()
        (base / "video.mp4").touch()
        (base / "readme.txt").touch()
        sub = base / "subdir"
        sub.mkdir()
        (sub / "photo3.nef").touch()
        (sub / "notes.md").touch()

    def test_flat_scan(self, tmp_path):
        self._create_test_tree(tmp_path)
        results = scan_directory(str(tmp_path), include_subdirs=False)
        basenames = [os.path.basename(f) for f in results]
        assert "photo1.jpg" in basenames
        assert "photo2.CR2" in basenames
        assert "video.mp4" in basenames
        assert "readme.txt" not in basenames
        # Subdirectory files should NOT appear
        assert "photo3.nef" not in basenames

    def test_recursive_scan(self, tmp_path):
        self._create_test_tree(tmp_path)
        results = scan_directory_recursive(str(tmp_path))
        basenames = [os.path.basename(f) for f in results]
        assert "photo1.jpg" in basenames
        assert "photo3.nef" in basenames
        assert "readme.txt" not in basenames
        assert "notes.md" not in basenames

    def test_empty_directory(self, tmp_path):
        results = scan_directory(str(tmp_path), include_subdirs=False)
        assert results == []

    def test_nonexistent_directory(self):
        results = scan_directory("/nonexistent/path", include_subdirs=False)
        assert results == []


# ---------------------------------------------------------------------------
# File access check
# ---------------------------------------------------------------------------
class TestCheckFileAccess:
    """Test file accessibility checks."""

    def test_accessible_file(self, tmp_path):
        f = tmp_path / "test.jpg"
        f.write_bytes(b"\xff\xd8")  # minimal JPEG-ish bytes
        assert check_file_access(str(f)) is True

    def test_nonexistent_file(self):
        assert check_file_access("/nonexistent/file.jpg") is False


# ---------------------------------------------------------------------------
# FileConstants
# ---------------------------------------------------------------------------
class TestFileConstants:
    """Validate constant definitions."""

    def test_media_extensions_is_union(self):
        assert set(FileConstants.MEDIA_EXTENSIONS) == set(
            FileConstants.IMAGE_EXTENSIONS + FileConstants.VIDEO_EXTENSIONS
        )

    def test_all_extensions_start_with_dot(self):
        for ext in FileConstants.MEDIA_EXTENSIONS:
            assert ext.startswith("."), f"Extension missing dot: {ext}"

    def test_all_extensions_lowercase(self):
        for ext in FileConstants.MEDIA_EXTENSIONS:
            assert ext == ext.lower(), f"Extension not lowercase: {ext}"
