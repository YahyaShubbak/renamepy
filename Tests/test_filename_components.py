#!/usr/bin/env python3
"""
Unit tests for modules/filename_components.py

Covers the pure-function component builder with no I/O:
- Date formatting across all supported patterns
- Component sanitization
- Metadata formatting (ISO, aperture, shutter speed, etc.)
- Full build_ordered_components with various custom orders
"""

import os
import sys
import pytest
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.filename_components import (
    build_ordered_components,
    _format_date,
    _sanitize_component,
    _format_metadata,
)


# ---------------------------------------------------------------------------
# Date formatting
# ---------------------------------------------------------------------------
class TestFormatDate:
    """Test date string formatting for all supported patterns."""

    @pytest.mark.parametrize("fmt, expected", [
        ("YYYY-MM-DD", "2024-06-15"),
        ("YYYY_MM_DD", "2024_06_15"),
        ("YYYYMMDD", "20240615"),
        ("DD-MM-YYYY", "15-06-2024"),
        ("DD_MM_YYYY", "15_06_2024"),
        ("MM-DD-YYYY", "06-15-2024"),
        ("MM_DD_YYYY", "06_15_2024"),
    ])
    def test_all_formats(self, fmt: str, expected: str):
        assert _format_date("20240615", fmt) == expected

    def test_unknown_format_falls_back_to_iso(self):
        result = _format_date("20240615", "UNKNOWN_FMT")
        assert result == "2024-06-15"

    def test_none_input(self):
        assert _format_date(None, "YYYY-MM-DD") is None

    def test_empty_string(self):
        assert _format_date("", "YYYY-MM-DD") is None

    def test_too_short_string(self):
        assert _format_date("2024", "YYYY-MM-DD") is None

    def test_eight_digit_minimum(self):
        """Exactly 8 characters should work."""
        result = _format_date("20240101", "YYYYMMDD")
        assert result == "20240101"

    def test_longer_string_only_uses_first_eight(self):
        """Extra characters after 8 should be ignored."""
        result = _format_date("20240615_120000", "YYYY-MM-DD")
        assert result == "2024-06-15"


# ---------------------------------------------------------------------------
# Component sanitization
# ---------------------------------------------------------------------------
class TestSanitizeComponent:
    """Test individual component sanitization."""

    def test_clean_string_unchanged(self):
        assert _sanitize_component("Canon-EOS-R5") == "Canon-EOS-R5"

    def test_spaces_become_underscores(self):
        assert _sanitize_component("Canon EOS R5") == "Canon_EOS_R5"

    def test_forbidden_chars_removed(self):
        result = _sanitize_component('file<>:"/\\|?*name')
        assert all(c not in result for c in '<>:"/\\|?*')

    def test_whitespace_stripped(self):
        assert _sanitize_component("  hello  ") == "hello"

    def test_multiple_spaces_collapsed(self):
        result = _sanitize_component("a   b   c")
        assert result == "a_b_c"


# ---------------------------------------------------------------------------
# Metadata formatting
# ---------------------------------------------------------------------------
class TestFormatMetadata:
    """Test metadata value formatting for various EXIF keys."""

    def test_none_returns_none(self):
        assert _format_metadata("iso", None) is None

    def test_empty_string_returns_none(self):
        assert _format_metadata("iso", "") is None

    def test_unknown_returns_none(self):
        assert _format_metadata("camera", "Unknown") is None

    def test_bool_returns_none(self):
        """Unresolved boolean flags should be ignored."""
        assert _format_metadata("iso", True) is None

    # ISO
    def test_iso_numeric(self):
        result = _format_metadata("iso", "400")
        assert result == "ISO400"

    def test_iso_already_prefixed(self):
        result = _format_metadata("iso", "ISO 800")
        assert "ISO" in result

    # Aperture
    def test_aperture_plain_number(self):
        result = _format_metadata("aperture", "2.8")
        assert result.startswith("f")
        assert "2.8" in result

    def test_aperture_with_f_slash(self):
        result = _format_metadata("aperture", "f/4.0")
        assert result == "f4.0"

    # Camera
    def test_camera_spaces_become_dashes(self):
        result = _format_metadata("camera", "Canon EOS R5")
        assert result == "Canon-EOS-R5"

    # Lens
    def test_lens_spaces_become_dashes(self):
        result = _format_metadata("lens", "RF24-70mm F2.8")
        assert result == "RF24-70mm-F2.8"

    # Focal length
    def test_focal_length_extraction(self):
        result = _format_metadata("focal_length", "70mm")
        assert result == "70mm"

    def test_focal_length_with_extra_text(self):
        result = _format_metadata("focal_length", "70mm (35mm equivalent)")
        assert "70mm" in result

    # Shutter speed
    def test_shutter_speed_fraction(self):
        result = _format_metadata("shutter", "1/250")
        assert result is not None
        assert "/" not in result  # slashes are replaced

    # Generic key
    def test_generic_key_formatting(self):
        result = _format_metadata("some_key", "A B/C:D")
        assert result is not None
        assert " " not in result


# ---------------------------------------------------------------------------
# build_ordered_components — the main public API
# ---------------------------------------------------------------------------
class TestBuildOrderedComponents:
    """Test the full component builder with various configurations."""

    def _build(self, **overrides) -> list[str]:
        """Helper with sensible defaults."""
        defaults = dict(
            date_taken="20240615",
            camera_prefix="TEST",
            additional="",
            camera_model=None,
            lens_model=None,
            use_camera=False,
            use_lens=False,
            number=1,
            custom_order=["Date", "Prefix", "Number"],
            date_format="YYYY-MM-DD",
            use_date=True,
            selected_metadata=None,
        )
        defaults.update(overrides)
        return build_ordered_components(**defaults)

    # -- Basic ordering --
    def test_date_prefix_number(self):
        parts = self._build()
        assert parts == ["2024-06-15", "TEST", "001"]

    def test_prefix_number_only(self):
        parts = self._build(use_date=False)
        assert parts == ["TEST", "001"]

    def test_number_only(self):
        parts = self._build(
            use_date=False, camera_prefix="", custom_order=["Number"]
        )
        assert parts == ["001"]

    # -- Camera and lens --
    def test_camera_included(self):
        parts = self._build(
            use_camera=True,
            camera_model="Canon EOS R5",
            custom_order=["Camera", "Number"],
        )
        assert any("Canon" in p for p in parts)

    def test_lens_included(self):
        parts = self._build(
            use_lens=True,
            lens_model="RF24-70mm F2.8",
            custom_order=["Lens", "Number"],
        )
        assert any("RF24" in p for p in parts)

    def test_camera_excluded_when_flag_false(self):
        parts = self._build(
            use_camera=False,
            camera_model="Canon EOS R5",
            custom_order=["Camera", "Number"],
        )
        assert not any("Canon" in p for p in parts)

    # -- Number auto-append --
    def test_number_auto_appended_if_missing_from_order(self):
        parts = self._build(custom_order=["Date", "Prefix"])
        assert "001" in parts

    # -- Date formats --
    @pytest.mark.parametrize("fmt, expected_date", [
        ("YYYY-MM-DD", "2024-06-15"),
        ("YYYYMMDD", "20240615"),
        ("DD-MM-YYYY", "15-06-2024"),
    ])
    def test_date_format_variants(self, fmt: str, expected_date: str):
        parts = self._build(date_format=fmt, custom_order=["Date", "Number"])
        assert parts[0] == expected_date

    # -- No date available --
    def test_no_date_produces_no_date_component(self):
        parts = self._build(date_taken=None)
        assert not any("2024" in p for p in parts)

    # -- Additional field --
    def test_additional_field(self):
        parts = self._build(
            additional="Wedding",
            custom_order=["Date", "Additional", "Number"],
        )
        assert "Wedding" in parts

    # -- Metadata components --
    def test_metadata_iso(self):
        parts = self._build(
            selected_metadata={"iso": "800"},
            custom_order=["Date", "Meta_iso", "Number"],
        )
        assert any("ISO800" in p for p in parts)

    def test_metadata_aperture(self):
        parts = self._build(
            selected_metadata={"aperture": "f/2.8"},
            custom_order=["Date", "Meta_aperture", "Number"],
        )
        assert any("f2.8" in p for p in parts)

    def test_metadata_bool_flag_ignored(self):
        """Boolean True = unresolved flag, should not appear."""
        parts = self._build(
            selected_metadata={"iso": True},
            custom_order=["Date", "Meta_iso", "Number"],
        )
        assert not any("ISO" in p for p in parts)
        # Date and Number should still be there
        assert len(parts) >= 2

    def test_metadata_fallback_when_no_meta_prefix_in_order(self):
        """Metadata without explicit Meta_ ordering should still be appended."""
        parts = self._build(
            selected_metadata={"iso": "400"},
            custom_order=["Date", "Prefix", "Number"],
        )
        assert any("ISO400" in p for p in parts)

    # -- Zero-padded number --
    @pytest.mark.parametrize("num, expected", [
        (1, "001"),
        (10, "010"),
        (999, "999"),
        (1000, "1000"),
    ])
    def test_number_zero_padding(self, num: int, expected: str):
        parts = self._build(number=num, custom_order=["Number"])
        assert parts == [expected]

    # -- Edge: all empty components --
    def test_all_empty_produces_just_number(self):
        parts = self._build(
            date_taken=None,
            camera_prefix="",
            additional="",
            use_date=False,
            custom_order=["Date", "Prefix", "Additional", "Number"],
        )
        assert parts == ["001"]
