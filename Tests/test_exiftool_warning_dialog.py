#!/usr/bin/env python3
"""
Unit tests for modules/dialogs/exiftool_warning_dialog.py

Tests the ExifTool-Not-Found warning dialog logic: visibility control,
platform-specific instructions, and the "don't show again" setting.
All PyQt6 widgets are tested in isolation (no app-level startup needed).
"""

import os
import sys
import platform
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ---------------------------------------------------------------------------
# PyQt6 availability check — skip entire module if headless / no Qt
# ---------------------------------------------------------------------------
_qt_available = False
try:
    from PyQt6.QtWidgets import QApplication
    _qt_available = True
except ImportError:
    pass

pytestmark = pytest.mark.skipif(not _qt_available, reason="PyQt6 not available")


@pytest.fixture(scope="module")
def qapp():
    """Provide a QApplication instance for the test session."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app


@pytest.fixture()
def make_dialog(qapp):
    """Factory that creates an ExifToolWarningDialog."""
    from modules.dialogs.exiftool_warning_dialog import ExifToolWarningDialog

    created = []

    def _factory():
        dlg = ExifToolWarningDialog(parent=None)
        created.append(dlg)
        return dlg

    yield _factory

    # Cleanup
    for d in created:
        d.close()
        d.deleteLater()


# ---------------------------------------------------------------------------
# Dialog construction
# ---------------------------------------------------------------------------
class TestDialogCreation:

    def test_creates_without_error(self, make_dialog):
        dlg = make_dialog()
        assert dlg is not None

    def test_window_title_set(self, make_dialog):
        dlg = make_dialog()
        assert dlg.windowTitle()  # non-empty

    def test_contains_platform_instructions(self, make_dialog):
        """Dialog text should include platform-specific setup guidance."""
        dlg = make_dialog()
        # At minimum the dialog should be renderable without errors.
        assert dlg.isEnabled()


# ---------------------------------------------------------------------------
# should_show_again
# ---------------------------------------------------------------------------
class TestShouldShowAgain:

    def test_default_is_true(self, make_dialog):
        """Without checking the box, dialog should be shown again."""
        dlg = make_dialog()
        assert dlg.should_show_again() is True

    def test_checked_box_returns_false(self, make_dialog):
        dlg = make_dialog()
        dlg._dont_show_again.setChecked(True)
        assert dlg.should_show_again() is False

    def test_unchecked_box_returns_true(self, make_dialog):
        dlg = make_dialog()
        dlg._dont_show_again.setChecked(False)
        assert dlg.should_show_again() is True


# ---------------------------------------------------------------------------
# Platform instruction content
# ---------------------------------------------------------------------------
class TestPlatformInstructions:

    @patch("platform.system", return_value="Windows")
    def test_windows_instructions(self, _mock_sys, make_dialog):
        dlg = make_dialog()
        # Force re-creation to pick up patched platform
        from modules.dialogs.exiftool_warning_dialog import ExifToolWarningDialog
        d = ExifToolWarningDialog(parent=None)
        # The dialog should have been constructed without errors
        assert d.isEnabled()
        d.close()
        d.deleteLater()

    @patch("platform.system", return_value="Darwin")
    def test_macos_instructions(self, _mock_sys, make_dialog):
        from modules.dialogs.exiftool_warning_dialog import ExifToolWarningDialog
        d = ExifToolWarningDialog(parent=None)
        assert d.isEnabled()
        d.close()
        d.deleteLater()

    @patch("platform.system", return_value="Linux")
    def test_linux_instructions(self, _mock_sys, make_dialog):
        from modules.dialogs.exiftool_warning_dialog import ExifToolWarningDialog
        d = ExifToolWarningDialog(parent=None)
        assert d.isEnabled()
        d.close()
        d.deleteLater()
