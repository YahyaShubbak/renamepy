#!/usr/bin/env python3
"""
Settings Manager for RenamePy.
Handles persistence of application settings using QSettings.
"""

from PyQt6.QtCore import QSettings, QPoint, QSize
from typing import Any, Optional

class SettingsManager:
    """
    Manages application settings persistence.
    """
    
    def __init__(self, organization: str = "RenamePy", application: str = "FileRenamer"):
        self.settings = QSettings(organization, application)
    
    def get(self, key: str, default: Any = None, type_cls: Optional[type] = None) -> Any:
        """
        Get a setting value.
        
        Args:
            key: The setting key
            default: Default value if key doesn't exist
            type_cls: Optional type to cast the result to (e.g., bool, int)
        """
        if type_cls:
            return self.settings.value(key, default, type=type_cls)
        return self.settings.value(key, default)
    
    def set(self, key: str, value: Any):
        """
        Set a setting value.
        """
        self.settings.setValue(key, value)
        
    def sync(self):
        """Force write settings to disk."""
        self.settings.sync()

    # --- Specific Settings Helpers ---

    def get_window_geometry(self) -> bytes:
        return self.settings.value("window_geometry")

    def set_window_geometry(self, geometry: bytes):
        self.settings.setValue("window_geometry", geometry)

    def get_window_state(self) -> bytes:
        return self.settings.value("window_state")

    def set_window_state(self, state: bytes):
        self.settings.setValue("window_state", state)

    def get_theme(self) -> str:
        return self.settings.value("theme", "System", type=str)

    def set_theme(self, theme: str):
        self.settings.setValue("theme", theme)

    def get_show_exiftool_warning(self) -> bool:
        return self.settings.value("show_exiftool_warning", True, type=bool)

    def set_show_exiftool_warning(self, show: bool):
        self.settings.setValue("show_exiftool_warning", show)
        
    def get_last_directory(self) -> str:
        return self.settings.value("last_directory", "", type=str)
        
    def set_last_directory(self, path: str):
        self.settings.setValue("last_directory", path)
