#!/usr/bin/env python3
"""
Theme management for the RenameFiles application.
Handles Dark/Light theme switching with original styling.
"""

from PyQt6.QtWidgets import QApplication

class ThemeManager:
    """Manages application themes - Dark, Light, and System"""
    
    def __init__(self):
        self.current_theme = "System"
    
    def apply_theme(self, theme_name, main_window):
        """Apply the specified theme to the application"""
        self.current_theme = theme_name
        app = QApplication.instance()
        
        if theme_name == "Dark":
            self._apply_dark_theme(app, main_window)
        elif theme_name == "Light":
            self._apply_light_theme(app, main_window)
        else:  # System
            self._apply_system_theme(app, main_window)
    
    def _apply_dark_theme(self, app, main_window):
        """Apply dark theme styling"""
        dark_style = """
        QMainWindow {
            background-color: #2b2b2b;
            color: #ffffff;
        }
        QWidget {
            background-color: #2b2b2b;
            color: #ffffff;
        }
        QLineEdit {
            background-color: #3c3c3c;
            border: 1px solid #5a5a5a;
            border-radius: 3px;
            padding: 5px;
            color: #ffffff;
        }
        QLineEdit:focus {
            border: 2px solid #0078d4;
        }
        QPushButton {
            background-color: #404040;
            border: 1px solid #5a5a5a;
            border-radius: 3px;
            padding: 8px;
            color: #ffffff;
        }
        QPushButton:hover {
            background-color: #4a4a4a;
            border: 1px solid #0078d4;
        }
        QPushButton:pressed {
            background-color: #0078d4;
        }
        QComboBox {
            background-color: #3c3c3c;
            border: 1px solid #5a5a5a;
            border-radius: 3px;
            padding: 5px;
            color: #ffffff;
        }
        QComboBox::drop-down {
            background-color: #3c3c3c;
            border: none;
        }
        QComboBox::down-arrow {
            image: none;
            border-left: 5px solid transparent;
            border-right: 5px solid transparent;
            border-top: 5px solid #ffffff;
        }
        QComboBox QAbstractItemView {
            background-color: #3c3c3c;
            border: 1px solid #5a5a5a;
            color: #ffffff;
            selection-background-color: #0078d4;
        }
        QListWidget {
            background-color: #3c3c3c;
            border: 1px solid #5a5a5a;
            color: #ffffff;
        }
        QListWidget::item {
            background-color: #3c3c3c;
            border-bottom: 1px solid #5a5a5a;
            padding: 4px;
            color: #ffffff;
        }
        QListWidget::item:selected {
            background-color: #0078d4;
            color: #ffffff;
        }
        QListWidget::item:hover {
            background-color: #4a4a4a;
        }
        QCheckBox {
            color: #ffffff;
        }
        QCheckBox::indicator {
            background-color: #3c3c3c;
            border: 1px solid #5a5a5a;
            border-radius: 2px;
        }
        QCheckBox::indicator:checked {
            background-color: #0078d4;
            border: 1px solid #0078d4;
        }
        QLabel {
            color: #ffffff;
            background-color: transparent;
        }
        QStatusBar {
            background-color: #404040;
            color: #ffffff;
        }
        QScrollBar:vertical {
            background-color: #3c3c3c;
            border: 1px solid #5a5a5a;
            width: 12px;
        }
        QScrollBar::handle:vertical {
            background-color: #5a5a5a;
            border-radius: 6px;
            min-height: 20px;
        }
        QScrollBar::handle:vertical:hover {
            background-color: #6a6a6a;
        }
        /* Interactive Preview Widget - Dark Theme */
        InteractivePreviewWidget {
            background-color: #3c3c3c;
            border: 2px solid #5a5a5a;
            color: #ffffff;
        }
        InteractivePreviewWidget::item {
            background-color: #404040;
            border: 1px solid #6a6a6a;
            color: #ffffff;
        }
        InteractivePreviewWidget::item:selected {
            background-color: #0078d4;
            border: 2px solid #66c2ff;
        }
        InteractivePreviewWidget::item:hover {
            background-color: #4a4a4a;
            border: 1px solid #0078d4;
        }
        """
        app.setStyleSheet(dark_style)
        
        # Apply dark theme to specific widgets with custom stylesheets
        if hasattr(main_window, 'interactive_preview'):
            main_window.interactive_preview.setStyleSheet("""
                QListWidget {
                    border: 2px solid #5a5a5a;
                    border-radius: 6px;
                    background-color: #3c3c3c;
                    padding: 8px;
                    font-size: 11px;
                    color: #ffffff;
                }
                QListWidget::item {
                    background-color: #404040;
                    border: 1px solid #6a6a6a;
                    border-radius: 2px;
                    padding: 1px 3px;
                    margin: 0px;
                    font-weight: bold;
                    text-align: center;
                    font-size: 8px;
                    color: #ffffff;
                }
                QListWidget::item:selected {
                    background-color: #0078d4;
                    border: 2px solid #66c2ff;
                }
                QListWidget::item:hover {
                    background-color: #4a4a4a;
                    border: 1px solid #0078d4;
                }
            """)
        
        # File Statistics Dark Theme
        if hasattr(main_window, 'file_stats_label'):
            main_window.file_stats_label.setStyleSheet("""
                QLabel {
                    background-color: #2d3748;
                    border: 2px solid #4a5568;
                    border-radius: 6px;
                    padding: 8px 12px;
                    color: #63b3ed;
                    font-size: 11px;
                    font-weight: bold;
                    text-align: left;
                }
            """)
        
        # File List Dark Theme
        if hasattr(main_window, 'file_list'):
            main_window.file_list.setStyleSheet("""
                QListWidget {
                    border: 2px dashed #5a5a5a;
                    border-radius: 8px;
                    background-color: #3c3c3c;
                    padding: 20px;
                    min-height: 120px;
                    color: #ffffff;
                }
                QListWidget::item {
                    padding: 4px;
                    border-bottom: 1px solid #5a5a5a;
                    background-color: #404040;
                    border-radius: 3px;
                    margin: 1px;
                    color: #ffffff;
                }
                QListWidget::item:selected {
                    background-color: #0078d4;
                    color: white;
                }
                QListWidget::item:hover {
                    background-color: #4a4a4a;
                }
            """)
    
    def _apply_light_theme(self, app, main_window):
        """Apply light theme styling"""
        # Light theme (default Qt)
        app.setStyleSheet("")
        
        # Restore original light theme styles for specific widgets
        if hasattr(main_window, 'interactive_preview'):
            main_window.interactive_preview.setStyleSheet("""
                QListWidget {
                    border: 2px solid #cccccc;
                    border-radius: 6px;
                    background-color: #f9f9f9;
                    padding: 8px;
                    font-size: 11px;
                }
                QListWidget::item {
                    background-color: #e6f3ff;
                    border: 1px solid #b3d9ff;
                    border-radius: 2px;
                    padding: 1px 3px;
                    margin: 0px;
                    font-weight: bold;
                    text-align: center;
                    font-size: 8px;
                }
                QListWidget::item:selected {
                    background-color: #cce7ff;
                    border: 2px solid #0078d4;
                }
                QListWidget::item:hover {
                    background-color: #d9ecff;
                    border: 1px solid #66c2ff;
                }
            """)
        
        # File Statistics Light Theme
        if hasattr(main_window, 'file_stats_label'):
            main_window.file_stats_label.setStyleSheet("""
                QLabel {
                    background-color: #e8f4fd;
                    border: 2px solid #b3d9ff;
                    border-radius: 6px;
                    padding: 8px 12px;
                    color: #0066cc;
                    font-size: 11px;
                    font-weight: bold;
                    text-align: left;
                }
            """)
        
        # File List Light Theme
        if hasattr(main_window, 'file_list'):
            main_window.file_list.setStyleSheet("""
                QListWidget {
                    border: 2px dashed #cccccc;
                    border-radius: 8px;
                    background-color: #fafafa;
                    padding: 20px;
                    min-height: 120px;
                }
                QListWidget::item {
                    padding: 4px;
                    border-bottom: 1px solid #e0e0e0;
                    background-color: #ffffff;
                    border-radius: 3px;
                    margin: 1px;
                }
                QListWidget::item:selected {
                    background-color: #0078d4;
                    color: white;
                }
                QListWidget::item:hover {
                    background-color: #f0f8ff;
                }
            """)
    
    def _apply_system_theme(self, app, main_window):
        """Apply system default theme"""
        app.setStyleSheet("")
        
        # Reset all custom stylesheets to system defaults
        if hasattr(main_window, 'interactive_preview'):
            main_window.interactive_preview.setStyleSheet("""
                QListWidget {
                    border: 2px solid #cccccc;
                    border-radius: 6px;
                    background-color: #f9f9f9;
                    padding: 8px;
                    font-size: 11px;
                }
                QListWidget::item {
                    background-color: #e6f3ff;
                    border: 1px solid #b3d9ff;
                    border-radius: 2px;
                    padding: 1px 3px;
                    margin: 0px;
                    font-weight: bold;
                    text-align: center;
                    font-size: 8px;
                }
                QListWidget::item:selected {
                    background-color: #cce7ff;
                    border: 2px solid #0078d4;
                }
                QListWidget::item:hover {
                    background-color: #d9ecff;
                    border: 1px solid #66c2ff;
                }
            """)
        
        if hasattr(main_window, 'file_stats_label'):
            main_window.file_stats_label.setStyleSheet("""
                QLabel {
                    background-color: #e8f4fd;
                    border: 2px solid #b3d9ff;
                    border-radius: 6px;
                    padding: 8px 12px;
                    color: #0066cc;
                    font-size: 11px;
                    font-weight: bold;
                    text-align: left;
                }
            """)
        
        if hasattr(main_window, 'file_list'):
            main_window.file_list.setStyleSheet("""
                QListWidget {
                    border: 2px dashed #cccccc;
                    border-radius: 8px;
                    background-color: #fafafa;
                    padding: 20px;
                    min-height: 120px;
                }
                QListWidget::item {
                    padding: 4px;
                    border-bottom: 1px solid #e0e0e0;
                    background-color: #ffffff;
                    border-radius: 3px;
                    margin: 1px;
                }
                QListWidget::item:selected {
                    background-color: #0078d4;
                    color: white;
                }
                QListWidget::item:hover {
                    background-color: #f0f8ff;
                }
            """)
    
    def get_current_theme(self):
        """Get the currently active theme"""
        return self.current_theme
