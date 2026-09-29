#!/usr/bin/env python3
"""
Theme management for the RenameFiles application.
Handles Dark/Light/System theme switching via parametrised CSS templates.

Light and Dark set both a style sheet and a matching QPalette: widgets that
use palette colours (alternating table rows, ``palette(button)`` in style
sheets, ...) would otherwise stay light inside a dark style sheet. "System"
keeps the platform's own palette and style and only adapts the few custom-
styled widgets, detecting dark mode from the platform.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QGuiApplication, QPalette
from PyQt6.QtWidgets import QApplication


# ---------------------------------------------------------------------------
# Colour palettes — single source of truth for each theme
# ---------------------------------------------------------------------------
_DARK: dict[str, str] = {
    "bg":           "#2b2b2b",
    "fg":           "#ffffff",
    "input_bg":     "#3c3c3c",
    "input_border": "#5a5a5a",
    "btn_bg":       "#404040",
    "btn_hover":    "#4a4a4a",
    "accent":       "#0078d4",
    "accent_light": "#66c2ff",
    "scrollbar":    "#5a5a5a",
    "scrollbar_hv": "#6a6a6a",
    "item_bg":      "#404040",
    "item_border":  "#6a6a6a",
    "item_hover":   "#4a4a4a",
    "preview_bg":   "#3c3c3c",
    "preview_bdr":  "#5a5a5a",
    "stats_bg":     "#2d3748",
    "stats_bdr":    "#4a5568",
    "stats_fg":     "#63b3ed",
    "list_bg":      "#3c3c3c",
    "list_bdr":     "#5a5a5a",
    "list_item_bg": "#404040",
    "list_sel":     "#0078d4",
    "list_hover":   "#4a4a4a",
    "alt_bg":       "#333333",
    "muted":        "#a8a8a8",
    "success":      "#5fd068",
    "warning":      "#ffb347",
    "error":        "#ff6b6b",
}

_LIGHT: dict[str, str] = {
    "bg":           "#ffffff",
    "fg":           "#000000",
    "input_bg":     "#ffffff",
    "input_border": "#cccccc",
    "btn_bg":       "#f0f0f0",
    "btn_hover":    "#e0e0e0",
    "accent":       "#0078d4",
    "accent_light": "#66c2ff",
    "scrollbar":    "#cccccc",
    "scrollbar_hv": "#aaaaaa",
    "item_bg":      "#e6f3ff",
    "item_border":  "#b3d9ff",
    "item_hover":   "#d9ecff",
    "preview_bg":   "#f9f9f9",
    "preview_bdr":  "#cccccc",
    "stats_bg":     "#e8f4fd",
    "stats_bdr":    "#b3d9ff",
    "stats_fg":     "#0066cc",
    "list_bg":      "#fafafa",
    "list_bdr":     "#cccccc",
    "list_item_bg": "#ffffff",
    "list_sel":     "#0078d4",
    "list_hover":   "#f0f8ff",
    "alt_bg":       "#f5f5f5",
    "muted":        "#666666",
    "success":      "#1e7e34",
    "warning":      "#b35900",
    "error":        "#c62828",
}


# ---------------------------------------------------------------------------
# Shared CSS templates — filled via str.format_map(palette)
# ---------------------------------------------------------------------------

_GLOBAL_STYLE = """\
QMainWindow {{
    background-color: {bg};
    color: {fg};
}}
QWidget {{
    background-color: {bg};
    color: {fg};
}}
QLineEdit {{
    background-color: {input_bg};
    border: 1px solid {input_border};
    border-radius: 3px;
    padding: 5px;
    color: {fg};
}}
QLineEdit:focus {{
    border: 2px solid {accent};
}}
QPushButton {{
    background-color: {btn_bg};
    border: 1px solid {input_border};
    border-radius: 3px;
    padding: 8px;
    color: {fg};
}}
QPushButton:hover {{
    background-color: {btn_hover};
    border: 1px solid {accent};
}}
QPushButton:pressed {{
    background-color: {accent};
}}
QComboBox {{
    background-color: {input_bg};
    border: 1px solid {input_border};
    border-radius: 3px;
    padding: 5px;
    color: {fg};
}}
QComboBox::drop-down {{
    background-color: {input_bg};
    border: none;
}}
QComboBox::down-arrow {{
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 5px solid {fg};
}}
QComboBox QAbstractItemView {{
    background-color: {input_bg};
    border: 1px solid {input_border};
    color: {fg};
    selection-background-color: {accent};
}}
QListWidget {{
    background-color: {input_bg};
    border: 1px solid {input_border};
    color: {fg};
}}
QListWidget::item {{
    background-color: {input_bg};
    border-bottom: 1px solid {input_border};
    padding: 4px;
    color: {fg};
}}
QListWidget::item:selected {{
    background-color: {accent};
    color: {fg};
}}
QListWidget::item:hover {{
    background-color: {item_hover};
}}
QCheckBox {{
    color: {fg};
}}
QCheckBox::indicator {{
    background-color: {input_bg};
    border: 1px solid {input_border};
    border-radius: 2px;
}}
QCheckBox::indicator:checked {{
    background-color: {accent};
    border: 1px solid {accent};
}}
QLabel {{
    color: {fg};
    background-color: transparent;
}}
QAbstractItemView {{
    background-color: {input_bg};
    alternate-background-color: {alt_bg};
    color: {fg};
    gridline-color: {input_border};
    selection-background-color: {accent};
    selection-color: #ffffff;
}}
QHeaderView::section {{
    background-color: {btn_bg};
    color: {fg};
    border: 1px solid {input_border};
    padding: 4px;
}}
QPlainTextEdit, QTextEdit {{
    background-color: {input_bg};
    border: 1px solid {input_border};
    color: {fg};
}}
QGroupBox {{
    border: 1px solid {input_border};
    border-radius: 4px;
    margin-top: 10px;
    padding-top: 6px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 8px;
    padding: 0 3px;
}}
QMenuBar, QMenu {{
    background-color: {btn_bg};
    color: {fg};
}}
QMenuBar::item:selected, QMenu::item:selected {{
    background-color: {accent};
}}
QToolTip {{
    background-color: {btn_bg};
    color: {fg};
    border: 1px solid {input_border};
}}
QStatusBar {{
    background-color: {btn_bg};
    color: {fg};
}}
QScrollBar:vertical {{
    background-color: {input_bg};
    border: 1px solid {input_border};
    width: 12px;
}}
QScrollBar::handle:vertical {{
    background-color: {scrollbar};
    border-radius: 6px;
    min-height: 20px;
}}
QScrollBar::handle:vertical:hover {{
    background-color: {scrollbar_hv};
}}
InteractivePreviewWidget {{
    background-color: {preview_bg};
    border: 2px solid {preview_bdr};
    color: {fg};
}}
InteractivePreviewWidget::item {{
    background-color: {item_bg};
    border: 1px solid {item_border};
    color: {fg};
}}
InteractivePreviewWidget::item:selected {{
    background-color: {accent};
    border: 2px solid {accent_light};
}}
InteractivePreviewWidget::item:hover {{
    background-color: {item_hover};
    border: 1px solid {accent};
}}
"""

_PREVIEW_STYLE = """\
QListWidget {{
    border: 2px solid {preview_bdr};
    border-radius: 6px;
    background-color: {preview_bg};
    padding: 8px;
    font-size: 11px;
    color: {fg};
}}
QListWidget::item {{
    background-color: {item_bg};
    border: 1px solid {item_border};
    border-radius: 2px;
    padding: 1px 3px;
    margin: 0px;
    font-weight: bold;
    text-align: center;
    font-size: 8px;
    color: {fg};
}}
QListWidget::item:selected {{
    background-color: {accent};
    border: 2px solid {accent_light};
}}
QListWidget::item:hover {{
    background-color: {item_hover};
    border: 1px solid {accent};
}}
"""

_STATS_STYLE = """\
QLabel {{
    background-color: {stats_bg};
    border: 2px solid {stats_bdr};
    border-radius: 6px;
    padding: 8px 12px;
    color: {stats_fg};
    font-size: 11px;
    font-weight: bold;
    text-align: left;
}}
"""

_FILE_LIST_STYLE = """\
QListWidget {{
    border: 2px dashed {list_bdr};
    border-radius: 8px;
    background-color: {list_bg};
    padding: 20px;
    min-height: 120px;
    color: {fg};
}}
QListWidget::item {{
    padding: 4px;
    border-bottom: 1px solid {input_border};
    background-color: {list_item_bg};
    border-radius: 3px;
    margin: 1px;
    color: {fg};
}}
QListWidget::item:selected {{
    background-color: {list_sel};
    color: white;
}}
QListWidget::item:hover {{
    background-color: {list_hover};
}}
"""


def _palette_from(colors: dict[str, str]) -> QPalette:
    """QPalette with the colours of one of the theme dictionaries."""
    palette = QPalette()
    role = QPalette.ColorRole
    for r, key in (
        (role.Window, "bg"), (role.WindowText, "fg"), (role.Base, "input_bg"),
        (role.AlternateBase, "alt_bg"), (role.Text, "fg"), (role.Button, "btn_bg"),
        (role.ButtonText, "fg"), (role.Highlight, "accent"), (role.ToolTipBase, "btn_bg"),
        (role.ToolTipText, "fg"), (role.PlaceholderText, "muted"), (role.Mid, "input_border"),
        (role.Midlight, "btn_hover"), (role.Light, "btn_hover"), (role.Dark, "input_border"),
        (role.Link, "accent_light"),
    ):
        palette.setColor(r, QColor(colors[key]))
    palette.setColor(role.HighlightedText, QColor("#ffffff"))
    for r in (role.WindowText, role.Text, role.ButtonText):
        palette.setColor(QPalette.ColorGroup.Disabled, r, QColor(colors["muted"]))
    return palette


def _is_dark(palette: QPalette) -> bool:
    return palette.color(QPalette.ColorRole.Window).lightness() < 128


class ThemeManager:
    """Manages application themes — Dark, Light, and System."""

    def __init__(self) -> None:
        self.current_theme = "System"
        self._main_window = None
        self._palette_changed = False
        app = QApplication.instance()
        # The platform's palette, restored when switching back to "System"
        self._system_palette = QPalette(app.palette()) if app else QPalette()
        hints = QGuiApplication.styleHints() if app else None
        if hints is not None and hasattr(hints, "colorSchemeChanged"):  # Qt >= 6.5
            hints.colorSchemeChanged.connect(self._on_system_scheme_changed)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def apply_theme(self, theme_name: str, main_window) -> None:
        """Apply the specified theme to the application."""
        self.current_theme = theme_name
        self._main_window = main_window
        app = QApplication.instance()

        if theme_name in ("Dark", "Light"):
            palette = _DARK if theme_name == "Dark" else _LIGHT
            app.setPalette(_palette_from(palette))
            self._palette_changed = True
            app.setStyleSheet(_GLOBAL_STYLE.format_map(palette))
        else:  # System: native style and palette
            if self._palette_changed:
                app.setPalette(self._system_palette)
                self._palette_changed = False
            app.setStyleSheet("")
            palette = _DARK if self.system_is_dark() else _LIGHT

        # Apply widget-specific styles
        self._apply_widget_styles(main_window, palette)
        refresh = getattr(main_window, "on_theme_colors_changed", None)
        if callable(refresh):
            refresh()

    def get_current_theme(self) -> str:
        """Get the currently active theme."""
        return self.current_theme

    def is_dark(self) -> bool:
        """Whether the active theme is dark."""
        if self.current_theme == "Dark":
            return True
        if self.current_theme == "Light":
            return False
        return self.system_is_dark()

    def system_is_dark(self) -> bool:
        """Whether the platform uses a dark colour scheme."""
        hints = QGuiApplication.styleHints()
        if hasattr(hints, "colorScheme"):  # Qt >= 6.5
            scheme = hints.colorScheme()
            if scheme == Qt.ColorScheme.Dark:
                return True
            if scheme == Qt.ColorScheme.Light:
                return False
        # Unknown (older Qt, some Linux desktops): judge by the palette
        app = QApplication.instance()
        palette = app.palette() if (app and not self._palette_changed) else self._system_palette
        return _is_dark(palette)

    def color(self, name: str) -> str:
        """A semantic colour of the active theme: success, warning, error, muted."""
        return (_DARK if self.is_dark() else _LIGHT)[name]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _on_system_scheme_changed(self, *_args) -> None:
        if self.current_theme == "System" and self._main_window is not None:
            self.apply_theme("System", self._main_window)

    def _apply_widget_styles(self, main_window, palette: dict[str, str]) -> None:
        """Apply styles to specific widgets using the given colour palette."""
        if hasattr(main_window, "interactive_preview"):
            main_window.interactive_preview.setStyleSheet(
                _PREVIEW_STYLE.format_map(palette)
            )

        if hasattr(main_window, "file_stats_label"):
            main_window.file_stats_label.setStyleSheet(
                _STATS_STYLE.format_map(palette)
            )

        if hasattr(main_window, "file_list"):
            main_window.file_list.setStyleSheet(
                _FILE_LIST_STYLE.format_map(palette)
            )
