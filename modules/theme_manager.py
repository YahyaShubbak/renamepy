#!/usr/bin/env python3
"""
Theme management for the RenameFiles application.
Handles Dark/Light/System theme switching via parametrised CSS templates.
"""

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


class ThemeManager:
    """Manages application themes — Dark, Light, and System."""

    def __init__(self) -> None:
        self.current_theme = "System"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def apply_theme(self, theme_name: str, main_window) -> None:
        """Apply the specified theme to the application."""
        self.current_theme = theme_name
        app = QApplication.instance()

        if theme_name == "Dark":
            palette = _DARK
            app.setStyleSheet(_GLOBAL_STYLE.format_map(palette))
        elif theme_name == "Light":
            palette = _LIGHT
            app.setStyleSheet("")  # Reset to Qt defaults first
        else:  # System
            palette = _LIGHT
            app.setStyleSheet("")

        # Apply widget-specific styles
        self._apply_widget_styles(main_window, palette)

    def get_current_theme(self) -> str:
        """Get the currently active theme."""
        return self.current_theme

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
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
