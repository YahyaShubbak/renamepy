#!/usr/bin/env python3
"""
State Model for RenamePy.
This module encapsulates the application state (data), separating it from the UI logic.
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

@dataclass
class RenamerState:
    """
    Holds the state of the File Renamer application.
    """
    # The list of files currently loaded
    files: List[str] = field(default_factory=list)
    
    # Metadata caches
    camera_models: Dict[str, str] = field(default_factory=dict)
    lens_models: Dict[str, str] = field(default_factory=dict)
    
    # Undo / Restore data
    original_filenames: Dict[str, str] = field(default_factory=dict)
    timestamp_backup: Dict[str, Any] = field(default_factory=dict)
    exif_backup: Dict[str, Any] = field(default_factory=dict)
    
    # User selections
    selected_metadata: Dict[str, Any] = field(default_factory=dict)
    
    def clear_files(self):
        """Clears all file-related data."""
        self.files.clear()
        self.camera_models.clear()
        self.lens_models.clear()
        # Note: We might want to keep undo data or clear it depending on UX requirements
        # For now, clearing files usually implies a reset
    
    def has_files(self) -> bool:
        return len(self.files) > 0

    def has_restore_data(self) -> bool:
        return bool(self.original_filenames) or bool(self.timestamp_backup) or bool(self.exif_backup)
