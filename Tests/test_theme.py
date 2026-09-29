#!/usr/bin/env python3
"""
Tests for theming: Light/Dark set a matching palette (so palette-based
colours such as alternating table rows follow the theme), "System" detects
dark mode from the platform and restores the platform palette, and status
colours are chosen per theme.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def app():
    from PyQt6.QtWidgets import QApplication
    application = QApplication.instance() or QApplication([])
    palette, sheet = application.palette(), application.styleSheet()
    yield application
    application.setPalette(palette)
    application.setStyleSheet(sheet)


class _Window:
    """Stand-in main window without custom-styled widgets."""

    def __init__(self):
        self.refreshed = 0

    def on_theme_colors_changed(self):
        self.refreshed += 1


def _dark_palette():
    from PyQt6.QtGui import QPalette, QColor
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#202020"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#eeeeee"))
    return palette


class TestThemes:

    def test_dark_sets_dark_palette_and_item_view_colours(self, app):
        from modules.theme_manager import ThemeManager, _is_dark
        window = _Window()
        manager = ThemeManager()
        manager.apply_theme("Dark", window)
        assert _is_dark(app.palette())
        assert "alternate-background-color" in app.styleSheet()
        assert manager.is_dark()
        assert window.refreshed == 1

    def test_light_sets_light_palette(self, app):
        from modules.theme_manager import ThemeManager, _is_dark
        manager = ThemeManager()
        manager.apply_theme("Light", _Window())
        assert not _is_dark(app.palette())
        assert not manager.is_dark()

    def test_system_restores_platform_palette(self, app):
        from modules.theme_manager import ThemeManager
        from PyQt6.QtGui import QPalette
        app.setPalette(_dark_palette())
        manager = ThemeManager()  # captures the "platform" palette
        manager.apply_theme("Light", _Window())
        manager.apply_theme("System", _Window())
        assert app.palette().color(QPalette.ColorRole.Window).name() == "#202020"
        assert app.styleSheet() == ""

    def test_system_detects_dark_desktop(self, app):
        from modules.theme_manager import ThemeManager
        from PyQt6.QtGui import QGuiApplication
        from PyQt6.QtCore import Qt
        hints = QGuiApplication.styleHints()
        if hasattr(hints, "colorScheme") and hints.colorScheme() != Qt.ColorScheme.Unknown:
            pytest.skip("platform reports its own colour scheme")
        app.setPalette(_dark_palette())
        manager = ThemeManager()
        manager.apply_theme("System", _Window())
        assert manager.system_is_dark()
        assert manager.is_dark()

    def test_status_colours_depend_on_theme(self, app):
        from modules.theme_manager import ThemeManager
        manager = ThemeManager()
        manager.apply_theme("Dark", _Window())
        dark = manager.color("success")
        manager.apply_theme("Light", _Window())
        assert manager.color("success") != dark
