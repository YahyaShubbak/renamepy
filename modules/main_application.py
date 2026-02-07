#!/usr/bin/env python3
"""
Complete original UI implementation with all features from RenameFiles.py
"""

import os
import sys
import re
import datetime
import time
import shutil
import subprocess
from .logger_util import get_logger, set_level
log = get_logger()

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QPushButton, QLineEdit, QCheckBox, QComboBox, QListWidget,
    QFileDialog, QStatusBar, QListWidgetItem, QMessageBox, QDialog,
    QStyle, QPlainTextEdit, QScrollArea
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QIcon, QDragEnterEvent, QDropEvent, QDragMoveEvent

# Import the modular components
from .file_utilities import (
    is_media_file, scan_directory_recursive,
    rename_files, FileConstants, MEDIA_EXTENSIONS, IMAGE_EXTENSIONS, VIDEO_EXTENSIONS,
    is_image_file, is_video_file
)
from .exif_service_new import ExifService, EXIFTOOL_AVAILABLE, PIL_AVAILABLE
from .exif_processor import (
    cleanup_global_exiftool, clear_global_exif_cache,
    find_exiftool_path, batch_restore_timestamps
)
from .rename_engine import RenameWorkerThread
from .ui_components import InteractivePreviewWidget
from .theme_manager import ThemeManager
from .filename_components import build_ordered_components
from .timestamp_options_dialog import TimestampSyncOptionsDialog
from .dialogs import ExifToolWarningDialog
from .handlers import extract_image_number
from .performance_benchmark import (
    PerformanceBenchmark, analyze_pattern_complexity
)
from .exif_undo_manager import get_original_filename_from_exif, get_rename_info
from .ui import FileListManager, PreviewGenerator, MainWindowUI
from .state_model import RenamerState
from .settings_manager import SettingsManager


class FileRenamerApp(QMainWindow):
    DEBUG_VERBOSE = False

    # --- State Model Delegation Properties ---
    @property
    def files(self): return self.state.files
    @files.setter
    def files(self, value): self.state.files = value

    @property
    def camera_models(self): return self.state.camera_models
    @camera_models.setter
    def camera_models(self, value): self.state.camera_models = value

    @property
    def lens_models(self): return self.state.lens_models
    @lens_models.setter
    def lens_models(self, value): self.state.lens_models = value

    @property
    def original_filenames(self): return self.state.original_filenames
    @original_filenames.setter
    def original_filenames(self, value): self.state.original_filenames = value

    @property
    def timestamp_backup(self): return self.state.timestamp_backup
    @timestamp_backup.setter
    def timestamp_backup(self, value): self.state.timestamp_backup = value

    @property
    def exif_backup(self): return self.state.exif_backup
    @exif_backup.setter
    def exif_backup(self, value): self.state.exif_backup = value

    @property
    def selected_metadata(self): return self.state.selected_metadata
    @selected_metadata.setter
    def selected_metadata(self, value): self.state.selected_metadata = value
    
    @property
    def save_original_to_exif(self): return self.state.save_original_to_exif
    @save_original_to_exif.setter
    def save_original_to_exif(self, value): self.state.save_original_to_exif = value
    # -----------------------------------------

    def __init__(self):
        super().__init__()
        # Ensure log method exists early
        if not hasattr(self, 'log'):
            def _early_log(msg: str):
                if getattr(self, 'DEBUG_VERBOSE', False):
                    log.debug(msg)  # Use module-level logger to avoid infinite recursion
            self.log = _early_log  # type: ignore
        # Busy state flag
        self._busy = False
        self.setWindowTitle("File Renamer")
        
        # Set application icon using custom icon.ico file
        icon_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        else:
            # Fallback to standard icon if icon.ico is not found
            self.setWindowIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView))
        
        self.setGeometry(100, 100, 600, 400)
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)

        # Initialize backend modules (simplified - no handler needed)
        # Note: RenameWorkerThread is used directly, no need for RenameEngine wrapper
        
        # EXIF method setup (copied from original)
        self.exiftool_path = self.get_exiftool_path()
        
        # Initialize ExifService (NEW: replaces global cache and exiftool instance)
        self.exif_service = ExifService(self.exiftool_path)
        
        if EXIFTOOL_AVAILABLE and self.exiftool_path:
            self.exif_method = "exiftool"
        elif PIL_AVAILABLE:
            self.exif_method = "pillow"
        else:
            self.exif_method = None
        
        # Initialize theme manager
        self.theme_manager = ThemeManager()
        
        # Initialize UI managers
        self.file_list_manager = FileListManager(self)
        self.preview_generator = PreviewGenerator(self)
        
        # State variables (Managed by RenamerState)
        self.state = RenamerState()
        self.settings_manager = SettingsManager()
        self.current_order = ["Date", "Prefix", "Additional", "Camera", "Lens"]
        
        self.setup_ui()
        
        # Restore settings
        self.restore_settings()
        
        # Initialize EXIF cache
        self._preview_exif_cache = {}
        self._preview_exif_file = None  # Track which file the preview cache belongs to
        
        # Initialize performance benchmark manager
        self.benchmark_manager = PerformanceBenchmark(self.exiftool_path)
        self.benchmark_thread = None

    # ------------------------------------------------------------------
    # Helper utilities (added for Phase 2 refactor: logging & UI state)
    # ------------------------------------------------------------------
    def _set_debug(self, enabled: bool):
        self.DEBUG_VERBOSE = enabled
        if hasattr(self, 'status'):
            self.status.showMessage(f"Verbose logging {'on' if enabled else 'off'}", 2500)

    def _update_buttons(self):
        """Central place to update enabled state of primary buttons.

        Heavy EXIF look-ups are deferred to a background thread so the
        GUI never blocks.  While the check is running, the undo button
        stays in its previous state; once the result arrives we simply
        call ``_update_buttons`` again (the cached flag is then set).
        """
        if not hasattr(self, 'rename_button'):
            return  # UI not built yet
        has_files = bool(self.files)
        
        # Check for undo availability (in-memory OR EXIF metadata)
        can_undo = bool(getattr(self, 'original_filenames', {})) or bool(getattr(self, 'timestamp_backup', {}))
        
        # Also check if any loaded file has original filename in EXIF (cached check)
        if not can_undo and has_files and self.exiftool_path:
            # Use cached result if available
            if hasattr(self, '_exif_undo_checked'):
                can_undo = self._exif_undo_available
            else:
                # Defer the expensive ExifTool check to a background thread
                self._start_async_exif_undo_check()
        
        if self._busy:
            self.rename_button.setEnabled(False)
            self.select_files_menu_button.setEnabled(False)
            self.select_folder_menu_button.setEnabled(False)
            self.clear_files_menu_button.setEnabled(False)
            self.undo_button.setEnabled(False)
        else:
            self.rename_button.setEnabled(has_files)
            # Undo only if there is something to restore
            self.undo_button.setEnabled(can_undo)
            # File selection buttons always active when not busy
            self.select_files_menu_button.setEnabled(True)
            self.select_folder_menu_button.setEnabled(True)
            self.clear_files_menu_button.setEnabled(True)

    def _start_async_exif_undo_check(self):
        """Run the EXIF undo-availability check off the GUI thread.

        Spawns a lightweight QThread that probes up to 3 files for the
        original-filename EXIF tag.  On completion, the cached flag is
        set and ``_update_buttons`` is re-invoked (from the main thread
        via a signal/slot connection).
        """
        # Guard against duplicate concurrent checks
        if getattr(self, '_exif_undo_check_running', False):
            return
        self._exif_undo_check_running = True

        from PyQt6.QtCore import QThread, pyqtSignal

        files_to_check = list(self.files[:3])
        exiftool_path = self.exiftool_path

        class _ExifUndoChecker(QThread):
            result_ready = pyqtSignal(bool)

            def run(self_inner):  # noqa: N805 — nested class
                found = False
                for fp in files_to_check:
                    if get_original_filename_from_exif(fp, exiftool_path):
                        found = True
                        break
                self_inner.result_ready.emit(found)

        def _on_result(available: bool):
            self._exif_undo_available = available
            self._exif_undo_checked = True
            self._exif_undo_check_running = False
            self._update_buttons()  # Re-evaluate with the fresh cache

        checker = _ExifUndoChecker(self)
        checker.result_ready.connect(_on_result)
        # prevent garbage collection by keeping a reference
        self._exif_undo_checker_ref = checker
        checker.start()

    def _ui_set_busy(self, busy: bool):
        """Toggle busy state and update button states/labels."""
        self._busy = busy
        if hasattr(self, 'rename_button'):
            self.rename_button.setText('⏳ Processing...' if busy else '🚀 Rename Files')
        self._update_buttons()

    def has_restore_data(self):
        """
        Check if there's anything that can be restored (filenames or timestamps)
        
        Returns:
            bool: True if there are filenames or timestamps that can be restored
        """
        # Check if we have original filename tracking (regardless of whether they've changed)
        has_filename_data = bool(self.original_filenames)
        
        # Check if we have timestamp backup data
        has_timestamp_data = bool(self.timestamp_backup)
        
        return has_filename_data or has_timestamp_data

    def update_restore_button_state(self):
        """Update the restore button state based on available restore data"""
        if self.has_restore_data():
            self.undo_button.setEnabled(True)
            # Update button text based on what can be restored
            if self.original_filenames and self.timestamp_backup:
                self.undo_button.setText("↶ Restore Names & Timestamps")
            elif self.timestamp_backup:
                self.undo_button.setText("↶ Restore Timestamps")
            else:
                self.undo_button.setText("↶ Restore Original Names")
        else:
            self.undo_button.setEnabled(False)
            self.undo_button.setText("↶ Restore Original Names")
        self._preview_exif_file = None
        
        # Check for ExifTool availability and show warning if needed
        self.check_exiftool_warning()
    
    def setup_ui(self):
        """Setup the complete original UI design"""
        # Delegate UI setup to MainWindowUI
        self.ui = MainWindowUI()
        self.ui.setup_ui(self)
        
        # Connect callbacks after UI is created
        self._connect_ui_callbacks()
        
        # Initialize placeholder and stats (since they are called in setup_ui but methods are on self)
        self.update_file_list_placeholder()
        self.update_file_statistics()
        
        # Initialize custom ordering
        self.custom_order = ["Date", "Camera", "Lens", "Prefix", "Additional", "Number"]
        
        self.update_exif_status()
        self.update_preview()
        self.update_camera_lens_labels()
        
        # Ensure rename button starts disabled
        self.rename_button.setEnabled(False)
        
        # Show ExifTool warning if needed
        QApplication.processEvents()
        self.check_exiftool_warning()
    
    def _connect_ui_callbacks(self):
        """Connect UI widget callbacks to application logic"""
        # File selection buttons
        self.select_files_menu_button.clicked.connect(self.select_files)
        self.select_folder_menu_button.clicked.connect(self.select_folder)
        self.clear_files_menu_button.clicked.connect(self.clear_file_list)

    def check_exiftool_warning(self):
        """Check if ExifTool warning should be shown"""
        if not (EXIFTOOL_AVAILABLE and self.exiftool_path):
            show_warning = self.settings_manager.get_show_exiftool_warning()
            
            if show_warning:
                dialog = ExifToolWarningDialog(self, self.exif_method)
                dialog.exec()
                
                if not dialog.should_show_again():
                    self.settings_manager.set_show_exiftool_warning(False)
    
    def get_exiftool_path(self):
        """Simple ExifTool path detection for the modular version"""
        # Delegate to exif_processor.find_exiftool_path which includes flexible folder search
        try:
            path = find_exiftool_path()
            # Optionally log version if available using subprocess - handled inside find_exiftool_path verify
            return path
        except Exception as e:
            self.log(f"Error locating ExifTool: {e}")
            return None
    
    # Event handlers implementation
    def select_files(self):
        """Select individual media files - delegates to FileListManager"""
        self.file_list_manager.select_files()
    
    def select_folder(self):
        """Select folder and scan for media files - delegates to FileListManager"""
        self.file_list_manager.select_folder()
    
    def clear_file_list(self):
        """Clear the file list - delegates to FileListManager"""
        self.file_list_manager.clear_file_list()
    
    def update_file_list(self):
        """Update the file list display - delegates to FileListManager"""
        self.file_list_manager.update_file_list()
    
    def update_file_list_placeholder(self):
        """Add placeholder text when file list is empty - delegates to FileListManager"""
        self.file_list_manager.update_file_list_placeholder()
    
    def update_file_statistics(self):
        """Update file statistics display - delegates to FileListManager"""
        self.file_list_manager.update_file_statistics()
    
    def show_media_info(self, item):
        """Show media info in status bar on single click"""
        file_path = item.data(Qt.ItemDataRole.UserRole)
        if not file_path or not is_media_file(file_path):
            return
        
        try:
            # Normalize path to prevent double backslashes
            normalized_path = os.path.normpath(file_path)
            
            # Verify file exists
            if not os.path.exists(normalized_path):
                self.log(f"show_media_info: File not found: {normalized_path}")
                return
            
            if is_video_file(file_path):
                # For videos, try to extract duration info
                if EXIFTOOL_AVAILABLE and self.exiftool_path:
                    raw_exif_data = self.exif_service.extract_raw_exif(normalized_path)
                    if raw_exif_data:
                        # Try to get video duration or frame count
                        duration_fields = ['QuickTime:Duration', 'Track1:MediaDuration', 'Duration', 'EXIF:Duration']
                        frame_fields = ['VideoFrameCount', 'FrameCount', 'TotalFrames']
                        
                        found_info = False
                        for field in duration_fields:
                            if field in raw_exif_data and raw_exif_data[field]:
                                duration = raw_exif_data[field]
                                self.status.showMessage(f"Video Duration: {duration}", 5000)
                                found_info = True
                                break
                        
                        if not found_info:
                            for field in frame_fields:
                                if field in raw_exif_data and raw_exif_data[field]:
                                    frame_count = raw_exif_data[field]
                                    self.status.showMessage(f"Video Frame Count: {frame_count}", 5000)
                                    found_info = True
                                    break
                        
                        if not found_info:
                            self.status.showMessage("Video metadata available - double click for details", 3000)
                    else:
                        self.status.showMessage("No video metadata found", 3000)
                else:
                    self.status.showMessage("Video files require ExifTool for metadata extraction", 3000)
            else:
                # For images, extract image number
                image_number = extract_image_number(file_path, self.exif_method, self.exiftool_path)
                
                if image_number:
                    self.status.showMessage(f"Image Number/Shutter Count: {image_number}", 5000)
                else:
                    self.status.showMessage("Image number not found in EXIF data", 3000)
                
        except Exception as e:
            self.status.showMessage(f"Error reading media metadata: {e}", 3000)
    
    def show_selected_exif(self, item):
        """Show EXIF data dialog on double click"""
        file_path = item.data(Qt.ItemDataRole.UserRole)
        if file_path and is_media_file(file_path):
            self.show_exif_info(file_path)
    
    def show_exif_info(self, file_path):
        """Show complete EXIF information in a dialog"""
        if not self.exif_method:
            file_type = "Video" if is_video_file(file_path) else "Image"
            self.show_exif_dialog(file_path, f"No metadata support available for {file_type.lower()} files.")
            return
        
        try:
            # Normalize path to prevent double backslashes
            normalized_file = os.path.normpath(file_path)
            
            # Verify file exists
            if not os.path.exists(normalized_file):
                self.log(f"show_exif_info: File not found: {normalized_file}")
                self.show_exif_dialog(file_path, "File not found.")
                return
            
            # Extract raw EXIF data using direct function
            if self.exif_method == "exiftool" and self.exiftool_path:
                raw_exif_data = self.exif_service.extract_raw_exif(normalized_file)
            else:
                raw_exif_data = {}
            
            if not raw_exif_data:
                file_type = "Video" if is_video_file(file_path) else "Image"
                self.show_exif_dialog(file_path, f"No metadata found in {file_type.lower()} file.")
                return
            
            # Format the EXIF data for display
            info = []
            for key, value in sorted(raw_exif_data.items()):
                if isinstance(value, (str, int, float)):
                    info.append(f"{key}: {value}")
                else:
                    info.append(f"{key}: {str(value)}")
            
            if info:
                info_str = "\n".join(info)
            else:
                file_type = "Video" if is_video_file(file_path) else "Image"
                info_str = f"No readable metadata found in {file_type.lower()} file."
            
            self.show_exif_dialog(file_path, info_str)
            
        except Exception as e:
            self.log(f"Error in show_exif_info: {e}")
            file_type = "Video" if is_video_file(file_path) else "Image"
            self.show_exif_dialog(file_path, f"Error reading {file_type.lower()} metadata: {e}")
    
    def show_exif_dialog(self, file_path, info_str):
        """Show detailed EXIF metadata dialog with two-stage display and checkboxes for filename inclusion"""
        file_type = "Video" if is_video_file(file_path) else "Image"
        
        # Parse the full metadata to extract essential information
        essential_info = self.extract_essential_metadata(info_str, file_path)
        
        dialog = QDialog(self)
        dialog.setWindowTitle(f"{file_type} Metadata: {os.path.basename(file_path)}")
        dialog.setModal(True)
        dialog.resize(550, 400)  # More compact initial size
        
        layout = QVBoxLayout(dialog)
        layout.setSpacing(8)  # Reduce spacing between elements
        layout.setContentsMargins(15, 10, 15, 10)  # Reduce margins
        
        # Essential metadata section with checkboxes
        essential_widget = self.create_essential_metadata_widget(info_str, file_path)
        layout.addWidget(essential_widget)
        
        # Button section
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        
        # Toggle button for full metadata
        self.show_full_button = QPushButton("Show All Metadata")
        self.show_full_button.clicked.connect(lambda: self.toggle_full_metadata(dialog, layout, info_str, essential_widget))
        button_layout.addWidget(self.show_full_button)
        
        button_layout.addStretch()
        
        # Close button
        close_button = QPushButton("Close")
        close_button.clicked.connect(dialog.accept)
        button_layout.addWidget(close_button)
        
        layout.addLayout(button_layout)
        
        # Store reference for toggling
        self.full_metadata_widget = None
        self.dialog_layout = layout
        
        dialog.exec()
    
    def create_essential_metadata_widget(self, full_metadata, file_path):
        """Create widget with essential metadata and checkboxes for filename inclusion"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(2)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Parse metadata
        lines = full_metadata.split('\n')
        metadata_dict = {}
        for line in lines:
            if ':' in line and line.strip():
                try:
                    parts = line.split(':', 2)
                    if len(parts) >= 2:
                        key = parts[0].strip() + ':' + parts[1].strip()
                        value = parts[2].strip() if len(parts) > 2 else ''
                        metadata_dict[key] = value
                except (ValueError, IndexError):
                    continue
        
        # Helper function to add metadata row with checkbox
        def add_metadata_row(parent_layout, label_text, value, metadata_key=None, checked=False):
            if value and value != 'Unknown':
                row_layout = QHBoxLayout()
                row_layout.setContentsMargins(0, 2, 0, 2)
                
                # Check if this metadata is already selected (for persistence)
                is_selected = False
                if metadata_key and hasattr(self, 'selected_metadata'):
                    is_selected = metadata_key in self.selected_metadata
                    
                # Checkbox for filename inclusion
                checkbox = QCheckBox()
                checkbox.setChecked(is_selected or checked)
                if metadata_key:
                    # Add flag to distinguish user actions from programmatic changes
                    checkbox.toggled.connect(lambda checked, key=metadata_key, val=value: 
                                           self.on_metadata_checkbox_changed(key, val, checked, user_action=True))
                checkbox.setToolTip(f"Include {label_text.lower()} in filename")
                row_layout.addWidget(checkbox)
                
                # Label
                label = QLabel(f"{label_text}: {value}")
                label.setStyleSheet("margin-left: 5px;")
                row_layout.addWidget(label)
                
                row_layout.addStretch()
                parent_layout.addLayout(row_layout)
                return checkbox
            return None
        
        # Get file information
        file_stats = os.stat(file_path)
        file_size_mb = file_stats.st_size / (1024 * 1024)
        
        # FILE INFORMATION section
        file_section = QLabel("📁 FILE INFORMATION")
        file_section.setStyleSheet("font-weight: bold; color: #666; margin: 5px 0px 3px 0px;")
        layout.addWidget(file_section)
        
        add_metadata_row(layout, "File", os.path.basename(file_path))
        add_metadata_row(layout, "Size", f"{file_size_mb:.1f} MB")
        add_metadata_row(layout, "Type", metadata_dict.get('File:FileType', 'Unknown'))
        
        # Check for original filename in EXIF metadata
        if self.exiftool_path:
            rename_info = get_rename_info(file_path, self.exiftool_path)
            if rename_info['original_filename']:
                # Display original filename with special formatting
                original_row = QHBoxLayout()
                original_row.setContentsMargins(0, 2, 0, 2)
                
                original_label = QLabel(f"📝 Original: {rename_info['original_filename']}")
                original_label.setStyleSheet("margin-left: 5px; color: #2196F3; font-weight: bold;")
                original_label.setToolTip(
                    f"This file was renamed from '{rename_info['original_filename']}'\n"
                    f"Rename date: {rename_info.get('rename_date', 'Unknown')}\n\n"
                    "You can restore the original filename using the Undo function."
                )
                original_row.addWidget(original_label)
                original_row.addStretch()
                layout.addLayout(original_row)
        
        # CAMERA & LENS section
        camera_section = QLabel("📷 CAMERA & LENS")
        camera_section.setStyleSheet("font-weight: bold; color: #666; margin: 10px 0px 3px 0px;")
        layout.addWidget(camera_section)
        
        make = metadata_dict.get('EXIF:Make', '')
        model = metadata_dict.get('EXIF:Model', '')
        camera = f"{make} {model}".strip()
        lens = metadata_dict.get('EXIF:LensModel', metadata_dict.get('MakerNotes:LensSpec', ''))
        
        # Synchronize with main window checkboxes - combine both states
        camera_checked = (self.checkbox_camera.isChecked() if hasattr(self, 'checkbox_camera') else False) or ('camera' in self.selected_metadata)
        lens_checked = (self.checkbox_lens.isChecked() if hasattr(self, 'checkbox_lens') else False) or ('lens' in self.selected_metadata)
        
        add_metadata_row(layout, "Camera", camera if camera else 'Unknown', 'camera', camera_checked)
        add_metadata_row(layout, "Lens", lens, 'lens', lens_checked)
        
        # SHOOTING SETTINGS section
        shooting_section = QLabel("⚙️ SHOOTING SETTINGS")
        shooting_section.setStyleSheet("font-weight: bold; color: #666; margin: 10px 0px 3px 0px;")
        layout.addWidget(shooting_section)
        
        date_taken = metadata_dict.get('EXIF:DateTimeOriginal', metadata_dict.get('EXIF:CreateDate', ''))
        if date_taken:
            add_metadata_row(layout, "Date", date_taken, 'date')
        
        iso = metadata_dict.get('EXIF:ISO', metadata_dict.get('MakerNotes:SonyISO', ''))
        if iso:
            add_metadata_row(layout, "ISO", iso, 'iso')
        
        aperture = metadata_dict.get('EXIF:FNumber', metadata_dict.get('Composite:Aperture', ''))
        if aperture:
            add_metadata_row(layout, "Aperture", f"f/{aperture}", 'aperture')
        
        exposure_time = metadata_dict.get('EXIF:ExposureTime', '')
        if exposure_time:
            try:
                exp_val = float(exposure_time)
                if exp_val < 1:
                    shutter_display = f"1/{int(1/exp_val)}s"
                else:
                    shutter_display = f"{exp_val}s"
                add_metadata_row(layout, "Shutter", shutter_display, 'shutter')
            except (ValueError, TypeError, ZeroDivisionError):
                add_metadata_row(layout, "Shutter", exposure_time, 'shutter')
        
        focal_length = metadata_dict.get('EXIF:FocalLength', '')
        if focal_length:
            focal_length_35 = metadata_dict.get('EXIF:FocalLengthIn35mmFormat', '')
            if focal_length_35 and focal_length != focal_length_35:
                focal_display = f"{focal_length}mm ({focal_length_35}mm equiv.)"
            else:
                focal_display = f"{focal_length}mm"
            add_metadata_row(layout, "Focal Length", focal_display, 'focal_length')
        
        # IMAGE PROPERTIES section
        image_section = QLabel("🖼️ IMAGE PROPERTIES")
        image_section.setStyleSheet("font-weight: bold; color: #666; margin: 10px 0px 3px 0px;")
        layout.addWidget(image_section)
        
        width = metadata_dict.get('EXIF:ExifImageWidth', metadata_dict.get('EXIF:ImageWidth', ''))
        height = metadata_dict.get('EXIF:ExifImageHeight', metadata_dict.get('EXIF:ImageHeight', ''))
        if width and height:
            try:
                megapixels = (int(width) * int(height)) / 1000000
                resolution_display = f"{width} x {height} ({megapixels:.1f} MP)"
                add_metadata_row(layout, "Resolution", resolution_display, 'resolution')
            except (ValueError, TypeError):
                add_metadata_row(layout, "Resolution", f"{width} x {height}", 'resolution')
        
        # CAMERA SETTINGS section
        settings_section = QLabel("🔧 CAMERA SETTINGS")
        settings_section.setStyleSheet("font-weight: bold; color: #666; margin: 10px 0px 3px 0px;")
        layout.addWidget(settings_section)
        
        exposure_mode = metadata_dict.get('EXIF:ExposureProgram', '')
        if exposure_mode:
            mode_names = {
                '0': 'Manual', '1': 'Manual', '2': 'Program Auto', '3': 'Aperture Priority',
                '4': 'Shutter Priority', '5': 'Creative Program', '6': 'Action Program'
            }
            mode_name = mode_names.get(exposure_mode, f'Mode {exposure_mode}')
            add_metadata_row(layout, "Exposure Mode", mode_name, 'exposure_mode')
        
        metering_mode = metadata_dict.get('EXIF:MeteringMode', '')
        if metering_mode:
            meter_names = {
                '1': 'Average', '2': 'Center-weighted', '3': 'Spot', 
                '4': 'Multi-spot', '5': 'Multi-segment', '6': 'Partial'
            }
            meter_name = meter_names.get(metering_mode, f'Mode {metering_mode}')
            add_metadata_row(layout, "Metering", meter_name, 'metering')
        
        flash = metadata_dict.get('EXIF:Flash', '')
        if flash:
            try:
                flash_fired = 'Yes' if int(flash) & 1 else 'No'
                add_metadata_row(layout, "Flash", flash_fired, 'flash')
            except (ValueError, TypeError):
                add_metadata_row(layout, "Flash", flash, 'flash')
        
        image_stab = metadata_dict.get('MakerNotes:ImageStabilization', '')
        if image_stab:
            stab_status = 'On' if image_stab == '1' else 'Off'
            add_metadata_row(layout, "Image Stabilization", stab_status, 'image_stabilization')
        
        layout.addStretch()
        
        # Make it scrollable
        scroll_area = QScrollArea()
        scroll_area.setWidget(widget)
        scroll_area.setWidgetResizable(True)
        scroll_area.setMinimumHeight(250)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        return scroll_area
    
    def on_metadata_checkbox_changed(self, metadata_key, value, checked, user_action=False):
        """Handle metadata checkbox changes for filename inclusion"""
        # Initialize metadata inclusion dict if not exists
        if not hasattr(self, 'selected_metadata'):
            self.selected_metadata = {}
        
        if checked:
            # SIMPLIFIED FIX: Store boolean flags instead of placeholders
            # This tells the rename engine which metadata types to extract
            if metadata_key in ['aperture', 'iso', 'focal_length', 'shutter', 'shutter_speed', 'exposure_bias']:
                # For EXIF metadata, store True to indicate extraction needed
                self.selected_metadata[metadata_key] = True
            else:
                # For camera/lens, store the actual value (these are typically the same for all files)
                self.selected_metadata[metadata_key] = value
        else:
            self.selected_metadata.pop(metadata_key, None)
        
        # Only synchronize with main window checkboxes if this is a user action
        # This prevents automatic sync when dialog is reopened with existing selected_metadata
        if user_action:
            if metadata_key == 'camera' and hasattr(self, 'checkbox_camera'):
                self.checkbox_camera.setChecked(checked)
            elif metadata_key == 'lens' and hasattr(self, 'checkbox_lens'):
                self.checkbox_lens.setChecked(checked)
        
        # Update preview to show new filename format immediately
        self.update_preview()
    
    def on_camera_checkbox_changed(self):
        """Handle camera checkbox changes and sync with metadata"""
        checked = self.checkbox_camera.isChecked()
        
        # Update selected_metadata first - BEFORE updating preview
        if hasattr(self, 'selected_metadata'):
            if checked:
                # Only add if we have valid camera info and it's not already there
                camera_info = self.camera_model_label.text()
                # Remove parentheses if present (e.g., "(ILCE-7CM2)" -> "ILCE-7CM2")
                if camera_info.startswith('(') and camera_info.endswith(')'):
                    camera_info = camera_info[1:-1]
                
                if camera_info and camera_info not in ["detecting...", "not detected", "no files selected"] and 'camera' not in self.selected_metadata:
                    self.selected_metadata['camera'] = camera_info
            else:
                # Remove camera from selected metadata when checkbox is unchecked
                if 'camera' in self.selected_metadata:
                    self.selected_metadata.pop('camera', None)
        
        # Now update preview with the corrected metadata
        self.update_preview()
    
    def on_lens_checkbox_changed(self):
        """Handle lens checkbox changes and sync with metadata"""
        checked = self.checkbox_lens.isChecked()
        
        # Update selected_metadata first - BEFORE updating preview
        if hasattr(self, 'selected_metadata'):
            if checked:
                # Only add if we have valid lens info and it's not already there
                lens_info = self.lens_model_label.text()
                # Remove parentheses if present (e.g., "(FE-20-70mm-F4-G)" -> "FE-20-70mm-F4-G")
                if lens_info.startswith('(') and lens_info.endswith(')'):
                    lens_info = lens_info[1:-1]
                
                if lens_info and lens_info not in ["detecting...", "not detected", "no files selected"] and 'lens' not in self.selected_metadata:
                    self.selected_metadata['lens'] = lens_info
            else:
                # Remove lens from selected metadata when checkbox is unchecked
                if 'lens' in self.selected_metadata:
                    self.selected_metadata.pop('lens', None)
        
        # Now update preview with the corrected metadata
        self.update_preview()
    
    def extract_essential_metadata(self, full_metadata, file_path):
        """Extract the most relevant metadata for human users"""
        lines = full_metadata.split('\n')
        essential = {}
        
        # Parse all metadata into a dictionary for easier access
        metadata_dict = {}
        for line in lines:
            if ':' in line and line.strip():
                try:
                    # Split only on the first colon to handle values that contain colons
                    parts = line.split(':', 2)  # Split into max 3 parts
                    if len(parts) >= 2:
                        key = parts[0].strip() + ':' + parts[1].strip()
                        value = parts[2].strip() if len(parts) > 2 else ''
                        metadata_dict[key] = value
                except (ValueError, IndexError):
                    continue
        
        # File information
        file_stats = os.stat(file_path)
        file_size_mb = file_stats.st_size / (1024 * 1024)
        
        essential_text = f"📁 FILE INFORMATION\n"
        essential_text += f"File: {os.path.basename(file_path)}\n"
        essential_text += f"Size: {file_size_mb:.1f} MB\n"
        essential_text += f"Type: {metadata_dict.get('File:FileType', 'Unknown')}\n"
        
        # Camera information
        make = metadata_dict.get('EXIF:Make', '')
        model = metadata_dict.get('EXIF:Model', '')
        camera = f"{make} {model}".strip()
        lens = metadata_dict.get('EXIF:LensModel', metadata_dict.get('MakerNotes:LensSpec', 'Unknown'))
        
        essential_text += f"\n📷 CAMERA & LENS\n"
        essential_text += f"Camera: {camera if camera else 'Unknown'}\n"
        essential_text += f"Lens: {lens}\n"
        
        # Shooting information
        essential_text += f"\n⚙️ SHOOTING SETTINGS\n"
        
        # Date/Time
        date_taken = metadata_dict.get('EXIF:DateTimeOriginal', metadata_dict.get('EXIF:CreateDate', ''))
        if date_taken:
            essential_text += f"Date: {date_taken}\n"
        
        # Exposure settings
        iso = metadata_dict.get('EXIF:ISO', metadata_dict.get('MakerNotes:SonyISO', ''))
        if iso:
            essential_text += f"ISO: {iso}\n"
        
        aperture = metadata_dict.get('EXIF:FNumber', metadata_dict.get('Composite:Aperture', ''))
        if aperture:
            essential_text += f"Aperture: f/{aperture}\n"
        
        exposure_time = metadata_dict.get('EXIF:ExposureTime', '')
        if exposure_time:
            # Convert decimal to fraction for readability
            try:
                exp_val = float(exposure_time)
                if exp_val < 1:
                    essential_text += f"Shutter: 1/{int(1/exp_val)}s\n"
                else:
                    essential_text += f"Shutter: {exp_val}s\n"
            except (ValueError, TypeError, ZeroDivisionError):
                essential_text += f"Shutter: {exposure_time}\n"
        
        focal_length = metadata_dict.get('EXIF:FocalLength', '')
        focal_length_35 = metadata_dict.get('EXIF:FocalLengthIn35mmFormat', '')
        if focal_length:
            if focal_length_35 and focal_length != focal_length_35:
                essential_text += f"Focal Length: {focal_length}mm ({focal_length_35}mm equiv.)\n"
            else:
                essential_text += f"Focal Length: {focal_length}mm\n"
        
        # Image properties
        essential_text += f"\n🖼️ IMAGE PROPERTIES\n"
        
        width = metadata_dict.get('EXIF:ExifImageWidth', metadata_dict.get('EXIF:ImageWidth', ''))
        height = metadata_dict.get('EXIF:ExifImageHeight', metadata_dict.get('EXIF:ImageHeight', ''))
        if width and height:
            try:
                megapixels = (int(width) * int(height)) / 1000000
                essential_text += f"Resolution: {width} x {height} ({megapixels:.1f} MP)\n"
            except (ValueError, TypeError):
                essential_text += f"Resolution: {width} x {height}\n"
        
        # Additional useful settings
        essential_text += f"\n🔧 CAMERA SETTINGS\n"
        
        exposure_mode = metadata_dict.get('EXIF:ExposureProgram', '')
        if exposure_mode:
            mode_names = {
                '0': 'Manual', '1': 'Manual', '2': 'Program Auto', '3': 'Aperture Priority',
                '4': 'Shutter Priority', '5': 'Creative Program', '6': 'Action Program'
            }
            mode_name = mode_names.get(exposure_mode, f'Mode {exposure_mode}')
            essential_text += f"Exposure Mode: {mode_name}\n"
        
        metering_mode = metadata_dict.get('EXIF:MeteringMode', '')
        if metering_mode:
            meter_names = {
                '1': 'Average', '2': 'Center-weighted', '3': 'Spot', 
                '4': 'Multi-spot', '5': 'Multi-segment', '6': 'Partial'
            }
            meter_name = meter_names.get(metering_mode, f'Mode {metering_mode}')
            essential_text += f"Metering: {meter_name}\n"
        
        flash = metadata_dict.get('EXIF:Flash', '')
        if flash:
            try:
                flash_fired = 'Yes' if int(flash) & 1 else 'No'
                essential_text += f"Flash: {flash_fired}\n"
            except (ValueError, TypeError):
                essential_text += f"Flash: {flash}\n"
        
        # Image stabilization (Sony specific)
        image_stab = metadata_dict.get('MakerNotes:ImageStabilization', '')
        if image_stab:
            stab_status = 'On' if image_stab == '1' else 'Off'
            essential_text += f"Image Stabilization: {stab_status}\n"
        
        return essential_text
    
    def toggle_full_metadata(self, dialog, layout, full_info, essential_widget):
        """Toggle between essential and full metadata view"""
        if self.full_metadata_widget is None:
            # Show full metadata
            self.show_full_button.setText("Hide Full Metadata")
            
            # Add separator
            separator = QLabel("📊 Complete Metadata")
            separator.setStyleSheet("font-weight: bold; font-size: 12px; margin: 10px 0px 5px 0px; border-top: 1px solid palette(mid); padding-top: 8px;")
            layout.insertWidget(layout.count() - 1, separator)
            
            # Add full metadata text area
            full_text = QPlainTextEdit()
            full_text.setPlainText(full_info)
            full_text.setReadOnly(True)
            # Make font smaller for full metadata to fit more content
            font = full_text.font()
            font.setPointSize(8)
            full_text.setFont(font)
            layout.insertWidget(layout.count() - 1, full_text)
            
            # Store widgets for removal
            self.full_metadata_widget = [separator, full_text]
            
            # Resize dialog to accommodate full metadata (more compact)
            dialog.resize(700, 600)
            
        else:
            # Hide full metadata
            self.show_full_button.setText("Show All Metadata")
            
            # Remove full metadata widgets
            for widget in self.full_metadata_widget:
                widget.setParent(None)
            self.full_metadata_widget = None
            
            # Resize dialog back to compact size
            dialog.resize(550, 400)
    
    def extract_camera_info(self):
        """Extract camera and lens info from first media file (copied from original)"""
        if not self.files:
            self.update_camera_lens_labels()
            return
        
        # Use first media file for detection (prioritize images, then videos)
        first_media = next((f for f in self.files if is_image_file(f)), None)
        if not first_media:
            first_media = next((f for f in self.files if is_video_file(f)), None)
        if not first_media:
            first_media = next((f for f in self.files if is_media_file(f)), None)
        
        if not first_media:
            self.update_camera_lens_labels()
            return
        
        try:
            # Use ExifService for camera/lens extraction
            date, camera, lens = self.exif_service.get_cached_exif_data(first_media, self.exif_method, self.exiftool_path)
            
            # Store results for label update
            self.detected_camera = camera
            self.detected_lens = lens
            
        except Exception as e:
            self.log(f"Error extracting camera info from {first_media}: {e}")
            self.detected_camera = None
            self.detected_lens = None
        
        # Update labels
        self.update_camera_lens_labels()

    def update_camera_lens_labels(self):
        """Update the camera and lens model labels (copied from original)"""
        if not self.files or not self.exif_method:
            self.camera_model_label.setText("(no files selected)")
            self.lens_model_label.setText("(no files selected)")
            return
        
        # Use stored detection results
        if hasattr(self, 'detected_camera') and self.detected_camera:
            self.camera_model_label.setText(f"({self.detected_camera})")
            self.camera_model_label.setStyleSheet("color: green; font-style: italic;")
        else:
            self.camera_model_label.setText("(not detected)")
            self.camera_model_label.setStyleSheet("color: orange; font-style: italic;")
        
        if hasattr(self, 'detected_lens') and self.detected_lens:
            self.lens_model_label.setText(f"({self.detected_lens})")
            self.lens_model_label.setStyleSheet("color: green; font-style: italic;")
        else:
            self.lens_model_label.setText("(not detected)")
            self.lens_model_label.setStyleSheet("color: orange; font-style: italic;")
    
    def update_preview(self):
        """Update the interactive preview widget with current settings - delegates to PreviewGenerator"""
        self.preview_generator.update_preview()
    
    def format_metadata_for_filename(self, metadata_key, metadata_value):
        """Format metadata values for use in filenames - delegates to PreviewGenerator"""
        return self.preview_generator.format_metadata_for_filename(metadata_key, metadata_value)
    
    def on_preview_order_changed(self, new_order):
        """Handle changes from the interactive preview widget"""
        
        # Build mapping from display values to component names
        value_to_component = {}
        
        # Get current text values for basic components
        camera_prefix = self.camera_prefix_entry.text().strip()
        additional = self.additional_entry.text().strip()
        use_camera = self.checkbox_camera.isChecked()
        use_lens = self.checkbox_lens.isChecked()
        use_date = self.checkbox_date.isChecked()
        
        # Map basic components (same as before)
        if camera_prefix:
            value_to_component[camera_prefix] = "Prefix"
        if additional:
            value_to_component[additional] = "Additional"
            
        # Map date component - CRITICAL FIX: Use the same date logic as update_preview()
        if use_date:
            # Get the same preview file as used in update_preview
            preview_file = next((f for f in self.files if os.path.splitext(f)[1].lower() in [".jpg", ".jpeg"]), None)
            if not preview_file:
                preview_file = next((f for f in self.files if is_media_file(f)), None)
            if not preview_file and self.files:
                preview_file = self.files[0]
            
            # Extract date using the same logic as update_preview()
            date_taken = None
            if hasattr(self, '_preview_exif_cache') and self._preview_exif_cache:
                date_taken = self._preview_exif_cache.get('date')
            
            # Fallback date extraction (same as update_preview)
            if not date_taken:
                if preview_file:
                    m = re.search(r'(20\d{2})(\d{2})(\d{2})', os.path.basename(preview_file))
                    if m:
                        date_taken = f"{m.group(1)}{m.group(2)}{m.group(3)}"
            
            if not date_taken:
                if preview_file and os.path.exists(preview_file):
                    mtime = os.path.getmtime(preview_file)
                    dt = datetime.datetime.fromtimestamp(mtime)
                    date_taken = dt.strftime('%Y%m%d')
                else:
                    date_taken = datetime.datetime.now().strftime('%Y%m%d')  # Use current date as fallback
            
            # Format date using the same logic as update_preview()
            if date_taken:
                year = date_taken[:4]
                month = date_taken[4:6]
                day = date_taken[6:8]
                
                date_format = self.date_format_combo.currentText()
                if date_format == "YYYY-MM-DD":
                    formatted_date = f"{year}-{month}-{day}"
                elif date_format == "YYYY_MM_DD":
                    formatted_date = f"{year}_{month}_{day}"
                elif date_format == "DD-MM-YYYY":
                    formatted_date = f"{day}-{month}-{year}"
                elif date_format == "DD_MM_YYYY":
                    formatted_date = f"{day}_{month}_{year}"
                elif date_format == "YYYYMMDD":
                    formatted_date = f"{year}{month}{day}"
                elif date_format == "MM-DD-YYYY":
                    formatted_date = f"{month}-{day}-{year}"
                elif date_format == "MM_DD_YYYY":
                    formatted_date = f"{month}_{day}_{year}"
                else:
                    formatted_date = f"{year}-{month}-{day}"  # Default fallback
                
                value_to_component[formatted_date] = "Date"
                self.log(f"🔄 Debug: Mapped Date '{formatted_date}' -> 'Date'")
            
        # Map camera and lens components
        if use_camera:
            camera_value = None
            if hasattr(self, '_preview_exif_cache') and self._preview_exif_cache:
                camera_value = self._preview_exif_cache.get('camera')
            if not camera_value:
                camera_value = "Camera"  # Fallback
            value_to_component[camera_value] = "Camera"
            
        if use_lens:
            lens_value = None
            if hasattr(self, '_preview_exif_cache') and self._preview_exif_cache:
                lens_value = self._preview_exif_cache.get('lens')
            if not lens_value:
                lens_value = "Lens"  # Fallback
            value_to_component[lens_value] = "Lens"
            
        # FLEXIBLE: Map Number component
        value_to_component["001"] = "Number"
            
        # Map metadata components - this is the key fix!
        if hasattr(self, 'selected_metadata') and self.selected_metadata:
            # We need to get the same preview metadata that update_preview() creates
            # This ensures we're mapping the same values that are actually displayed
            
            # Get the preview file (same logic as in update_preview)
            preview_file = next((f for f in self.files if os.path.splitext(f)[1].lower() in [".jpg", ".jpeg"]), None)
            if not preview_file:
                preview_file = next((f for f in self.files if is_media_file(f)), None)
            if not preview_file and self.files:
                preview_file = self.files[0]
            
            # Get preview metadata (same logic as in update_preview)
            preview_metadata = self.selected_metadata.copy()
            if self.exif_method and preview_file and os.path.exists(preview_file):
                needs_real_metadata = any(
                    value is True for value in self.selected_metadata.values()
                )
                
                if needs_real_metadata:
                    try:
                        real_metadata = self.exif_service.get_all_metadata(preview_file, self.exif_method, self.exiftool_path)
                        
                        # Replace Boolean flags with real values for preview
                        for key, value in self.selected_metadata.items():
                            if value is True:
                                # CRITICAL FIX: Add key mapping for shutter -> shutter_speed
                                exif_key = key
                                if key == 'shutter' and 'shutter_speed' in real_metadata:
                                    exif_key = 'shutter_speed'
                                
                                if exif_key in real_metadata:
                                    preview_metadata[key] = real_metadata[exif_key]
                                    self.log(f"🔄 Debug: Mapped preview {key} True -> {real_metadata[exif_key]}")
                    except Exception as e:
                        self.log(f"❌ Warning: Could not extract real metadata for preview mapping: {e}")
            
            # Now map the actual formatted values that are displayed
            for metadata_key, metadata_value in preview_metadata.items():
                # Skip if this metadata conflicts with main checkboxes
                if metadata_key == 'camera' and not use_camera:
                    continue
                if metadata_key == 'lens' and not use_lens:
                    continue
                    
                display_value = self.format_metadata_for_filename(metadata_key, metadata_value)
                if display_value:
                    meta_component_name = f"Meta_{metadata_key}"
                    value_to_component[display_value] = meta_component_name
                    self.log(f"🔄 Debug: Mapped EXIF '{display_value}' -> '{meta_component_name}'")
        
        # Convert display order to internal order
        new_internal_order = []
        for display_value in new_order:
            if display_value in value_to_component:
                component_name = value_to_component[display_value]
                if component_name not in new_internal_order:  # Prevent duplicates
                    new_internal_order.append(component_name)
        
        # Update custom order - respect EXACT order from preview (no auto-insertion)
        # This ensures "What You See Is What You Get"
        self.custom_order = new_internal_order
        
        # Update preview to reflect the change
        self.update_preview()
    
    def on_continuous_counter_changed(self):
        """Handle continuous counter checkbox change"""
        self.update_preview()
    
    def on_separator_changed(self):
        """Handle separator change"""
        self.update_preview()
    
    def validate_and_update_preview(self):
        """Validate input and update preview - delegates to PreviewGenerator"""
        self.preview_generator.validate_and_update_preview()
    
    def on_theme_changed(self, theme_name):
        """Handle theme changes using ThemeManager"""
        self.theme_manager.apply_theme(theme_name, self)
        self.settings_manager.set_theme(theme_name)
    
    def _detect_exiftool_version(self) -> str:
        """Detect the installed ExifTool version by running exiftool -ver.
        
        Returns:
            Version string (e.g. '13.33') or 'unknown' if detection fails.
        """
        if hasattr(self, '_exiftool_version'):
            return self._exiftool_version
        try:
            result = subprocess.run(
                [self.exiftool_path, '-ver'],
                capture_output=True, text=True, timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
            )
            self._exiftool_version = result.stdout.strip() if result.returncode == 0 else 'unknown'
        except Exception:
            self._exiftool_version = 'unknown'
        return self._exiftool_version

    def update_exif_status(self):
        """Update EXIF method status in status bar"""
        if EXIFTOOL_AVAILABLE and self.exiftool_path:
            version = self._detect_exiftool_version()
            self.exif_status_label.setText(f"EXIF method: ExifTool v{version} ✓")
            self.exif_status_label.setStyleSheet("color: green; font-weight: bold;")
        else:
            self.exif_status_label.setText("⚠ ExifTool not found — EXIF features unavailable")
            self.exif_status_label.setStyleSheet("color: red; font-weight: bold;")
    
    def rename_files_action(self):
        # Guard: prevent starting a second rename while one is running
        if getattr(self, '_busy', False):
            log.warning("Rename already in progress — ignoring duplicate request")
            return
        if hasattr(self, 'worker') and self.worker is not None and self.worker.isRunning():
            log.warning("Worker thread still running — ignoring duplicate request")
            return

        # Defensive fallback: ensure helper methods exist (in case of partial import issues)
        if not hasattr(self, '_ui_set_busy'):
            def _fallback_ui_set_busy(busy: bool):
                if hasattr(self, 'status'):
                    self.status.showMessage('Processing...' if busy else 'Ready', 1500)
            self._ui_set_busy = _fallback_ui_set_busy  # type: ignore
        if not hasattr(self, '_update_buttons'):
            def _fallback_update_buttons():
                if hasattr(self, 'rename_button'):
                    self.rename_button.setEnabled(bool(self.files) and not getattr(self, '_busy', False))
            self._update_buttons = _fallback_update_buttons  # type: ignore
        if not self.files:
            QMessageBox.warning(self, "Warning", "No files selected for renaming.")
            return
        camera_prefix = self.camera_prefix_entry.text().strip()
        additional = self.additional_entry.text().strip()
        use_camera = self.checkbox_camera.isChecked()
        use_lens = self.checkbox_lens.isChecked()
        use_date = self.checkbox_date.isChecked()
        continuous_counter = self.checkbox_continuous_counter.isChecked()
        date_format = self.date_format_combo.currentText()
        separator = self.separator_combo.currentText()
        non_media = [f for f in self.files if not is_media_file(f)]
        if non_media:
            reply = QMessageBox.question(
                self,
                "Non-media files found",
                "Some selected files are not media files. Continue renaming?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                return
        media_files = [f for f in self.files if is_media_file(f)]
        if not media_files:
            QMessageBox.warning(self, "Warning", "No media files found for renaming.")
            return
        
        # Disable UI during processing
        self._ui_set_busy(True)
        
        # Get EXIF date sync setting
        sync_exif_date = getattr(self, 'checkbox_sync_exif_date', None) and self.checkbox_sync_exif_date.isChecked()
        leave_file_names = getattr(self, 'checkbox_leave_names', None) and self.checkbox_leave_names.isChecked()
        save_original_to_exif = getattr(self, 'checkbox_save_original_to_exif', None) and self.checkbox_save_original_to_exif.isChecked()

        # Analyze pattern complexity and estimate time
        exif_field_count, text_field_count = analyze_pattern_complexity(
            use_date=use_date,
            use_camera=use_camera,
            use_lens=use_lens,
            additional_text=additional or "",
            camera_prefix=camera_prefix or "",
            selected_metadata=self.state.selected_metadata
        )
        
        log.debug(f"Pattern analysis: {exif_field_count} EXIF fields, {text_field_count} text fields")
        log.debug(f"Benchmark ready: {self.benchmark_manager.is_ready()}, results: {len(self.benchmark_manager.benchmark_results)}")
        
        # Get time estimate from benchmark (or use fallback)
        confidence = 0.0  # Default for fallback path
        if self.benchmark_manager.is_ready():
            log.debug("Using benchmark data for estimate")
            estimated_time, confidence = self.benchmark_manager.estimate_time(
                file_count=len(media_files),
                exif_field_count=exif_field_count,
                text_field_count=text_field_count,
                with_exif_save=save_original_to_exif
            )
            log.debug(f"Benchmark estimate: {estimated_time:.1f}s, confidence={confidence}")
            confidence_text = {
                1.0: "exact measurement",
                0.7: "similar scenario",
                0.5: "estimated",
                0.3: "rough estimate"
            }.get(confidence, "estimated")
        else:
            log.debug("Using fallback estimate (no benchmark data)")
            # Fallback to simple estimation if benchmark not ready
            base_time = len(media_files) * 0.03
            exif_time = exif_field_count * 0.01 * len(media_files)
            exif_save_time = len(media_files) * 0.1 if save_original_to_exif else 0
            estimated_time = base_time + exif_time + exif_save_time
            confidence_text = "rough estimate (no benchmark)"
        
        # Calculate time range based on confidence
        # High confidence (exact match) = narrower range
        # Low confidence (interpolated) = wider range
        if confidence >= 0.9:
            # Exact measurement - tight range
            time_range_low = max(1, estimated_time * 0.9)
            time_range_high = estimated_time * 1.1
        elif confidence >= 0.7:
            # Similar scenario - moderate range
            time_range_low = max(1, estimated_time * 0.8)
            time_range_high = estimated_time * 1.2
        else:
            # Rough estimate - wider range
            time_range_low = max(1, estimated_time * 0.7)
            time_range_high = estimated_time * 1.3
        
        # Format time as min:sec if > 60 seconds
        def format_time(seconds: float) -> str:
            if seconds >= 60:
                mins = int(seconds // 60)
                secs = int(seconds % 60)
                return f"{mins}:{secs:02d}"
            else:
                return f"{seconds:.1f}s"
        
        time_range_text = f"{format_time(time_range_low)}-{format_time(time_range_high)}"
        
        # Build pattern complexity description
        complexity_parts = []
        if exif_field_count > 0:
            complexity_parts.append(f"{exif_field_count} EXIF field{'s' if exif_field_count != 1 else ''}")
        if text_field_count > 0:
            complexity_parts.append(f"{text_field_count} text field{'s' if text_field_count != 1 else ''}")
        if save_original_to_exif:
            complexity_parts.append("metadata save enabled")
        
        complexity_desc = ", ".join(complexity_parts) if complexity_parts else "simple pattern"
        
        # Always show estimation dialog before renaming
        reply = QMessageBox.information(
            self,
            "⏱️ Operation Time Estimate",
            f"Ready to rename {len(media_files)} files\n\n"
            f"Pattern complexity: {complexity_desc}\n"
            f"Estimated time: {time_range_text}\n"
            f"Confidence: {confidence_text}\n\n"
            f"Continue with rename operation?",
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Ok
        )
        if reply != QMessageBox.StandardButton.Ok:
            self._ui_set_busy(False)
            return

        timestamp_options = None
        if sync_exif_date:
            reply = QMessageBox.warning(
                self,
                "⚠️ EXIF Date Sync Warning",
                "You have enabled EXIF date synchronization.\n\n"
                "This will modify selected file timestamps (creation / modification / access)\n"
                "to match the EXIF DateTimeOriginal OR a custom date you specify.\n\n"
                "Safety: Original timestamps are backed up and can be restored.\n\n"
                "Proceed?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                self._ui_set_busy(False)
                return
            dlg = TimestampSyncOptionsDialog(self)
            if dlg.exec() == QDialog.DialogCode.Accepted:
                timestamp_options = dlg.get_result()
                if not timestamp_options:
                    self._ui_set_busy(False)
                    return
            else:
                self._ui_set_busy(False)
                return
        
        # Store estimation data for calibration after rename completes
        self._last_estimate_data = {
            'estimated_time': estimated_time,
            'file_count': len(media_files),
            'exif_field_count': exif_field_count,
            'text_field_count': text_field_count,
            'with_exif_save': save_original_to_exif,
            'start_time': time.time()
        }

        # Start worker thread for background processing
        self.worker = RenameWorkerThread(
            media_files,
            camera_prefix,
            additional,
            use_camera,
            use_lens,
            self.exif_method,
            separator,
            self.exiftool_path,
            self.custom_order,
            date_format,
            use_date,
            continuous_counter,
            self.selected_metadata,
            sync_exif_date,
            timestamp_options=timestamp_options,
            leave_names=leave_file_names,
            save_original_to_exif=save_original_to_exif,
            log_callable=self.log,
            exif_service=self.exif_service,  # NEW: Pass ExifService instance
        )
        self.worker.progress_update.connect(self.update_status)
        self.worker.finished.connect(self.on_rename_finished)
        self.worker.error.connect(self.on_rename_error)
        self.worker.start()
    
    def update_status(self, message):
        """Update status bar with progress message.

        The status update is delivered via a signal/slot connection from
        the worker thread, so Qt already schedules it on the main thread
        event loop — no need for ``processEvents()``, which would cause
        dangerous reentrancy.
        """
        self.status.showMessage(message)

    # ----------------------- Logging Controls -----------------------
    def _on_toggle_debug_logging(self, enabled: bool):
        set_level('DEBUG' if enabled else 'INFO')
        self._set_debug(enabled)
        if hasattr(self, 'status'):
            self.status.showMessage(f"Debug logging {'enabled' if enabled else 'disabled'}", 3000)
    
    def show_time_shift_dialog(self):
        """Show EXIF Time Shift dialog"""
        from .dialogs import ExifTimeShiftDialog
        
        if not self.files:
            QMessageBox.warning(
                self,
                "No Files Selected",
                "Please select files first before adjusting EXIF timestamps."
            )
            return
        
        if not self.exiftool_path:
            QMessageBox.warning(
                self,
                "ExifTool Not Found",
                "ExifTool is required for this feature.\n\n"
                "Please install ExifTool and restart the application."
            )
            return
        
        # Open dialog
        dialog = ExifTimeShiftDialog(self, self.files, self.exiftool_path)
        if dialog.exec():
            # Time shift was applied successfully
            # Get EXIF backup for undo functionality
            exif_backup = dialog.get_exif_backup()
            if exif_backup:
                # Merge with existing backup (in case of multiple shifts)
                self.exif_backup.update(exif_backup)
                self.log(f"📦 Backed up EXIF data for {len(exif_backup)} files")
                
                # Enable undo button
                self.undo_button.setEnabled(True)
                self.undo_button.setText("↶ Restore Original EXIF & Names")
            
            # Clear EXIF cache to reload updated data
            self.exif_service.clear_cache()
            
            # Update preview with new times
            self.update_preview()
            
            # Show success message
            self.status.showMessage("EXIF timestamps updated successfully", 5000)

    # ------------------------------------------------------------------
    # Phase 2 Refactoring: Helper functions for on_rename_finished
    # ------------------------------------------------------------------
    
    def _create_filename_mapping_from_worker(self, rename_mapping: dict) -> dict:
        """
        Build the undo mapping from the authoritative rename_mapping dict
        produced by the worker thread during the actual rename loop.
        
        Args:
            rename_mapping: Dict of {new_path: old_path} from the worker.
            
        Returns:
            dict: Mapping of {current_path: original_basename} for undo.
        """
        if not hasattr(self, 'original_filenames') or not self.original_filenames:
            # First rename — build fresh mapping
            new_mapping = {}
            for new_path, old_path in rename_mapping.items():
                original_basename = os.path.basename(old_path)
                new_mapping[new_path] = original_basename
                self.log(f"Mapping: {os.path.basename(new_path)} -> {original_basename}")
            return new_mapping
        else:
            # Subsequent rename — preserve the chain back to the *original* name
            updated = {}
            for new_path, old_path in rename_mapping.items():
                # Look up the original name from the previous round
                if old_path in self.original_filenames:
                    updated[new_path] = self.original_filenames[old_path]
                else:
                    updated[new_path] = os.path.basename(old_path)
            return updated
    
    def _create_filename_mapping_fallback(self, old_media_files, renamed_files, timestamp_backup):
        """
        Fallback mapping for timestamp-only operations where no rename_mapping
        is available (e.g. leave_names mode, EXIF-only sync).
        
        Args:
            old_media_files: List of original file paths.
            renamed_files: List of new file paths (may be empty for sync-only).
            timestamp_backup: Dict of timestamp backups.
            
        Returns:
            dict: Mapping of {current_path: original_basename}.
        """
        new_original_filenames = {}
        
        if timestamp_backup and old_media_files and not renamed_files:
            # EXIF-only sync — filename didn't change, but we track for timestamp restore
            self.log("EXIF-only sync detected - creating filename mapping for restore functionality")
            for media_file in old_media_files:
                if media_file in timestamp_backup:
                    new_original_filenames[media_file] = os.path.basename(media_file)
        
        return new_original_filenames
    
    def _rebuild_file_list(self, renamed_files, original_non_media, old_media_files):
        """
        Rebuild the file list widget after rename operation.
        
        Args:
            renamed_files: List of renamed file paths
            original_non_media: List of non-media files (unchanged)
            old_media_files: List of original media files (for EXIF-only case)
        """
        self.files.clear()
        self.file_list.clear()
        
        # CASE 1: Normal rename operation - use renamed files
        if renamed_files:
            for renamed_file in renamed_files:
                self.files.append(renamed_file)
                item = QListWidgetItem(os.path.basename(renamed_file))
                item.setData(Qt.ItemDataRole.UserRole, renamed_file)
                self.file_list.addItem(item)
        else:
            # CASE 2: EXIF-only sync - keep original files
            for media_file in old_media_files:
                self.files.append(media_file)
                item = QListWidgetItem(os.path.basename(media_file))
                item.setData(Qt.ItemDataRole.UserRole, media_file)
                self.file_list.addItem(item)
        
        # Add back non-media files
        for non_media in original_non_media:
            self.files.append(non_media)
            item = QListWidgetItem(os.path.basename(non_media))
            item.setData(Qt.ItemDataRole.UserRole, non_media)
            self.file_list.addItem(item)
            # Preserve original tracking for non-media files
            if non_media not in self.original_filenames:
                self.original_filenames[non_media] = os.path.basename(non_media)
    
    def _show_rename_results(self, renamed_files, errors):
        """
        Show results dialog with success/error/conflict information.
        
        Args:
            renamed_files: List of successfully renamed files
            errors: List of error messages
        """
        if errors:
            # Separate name conflicts from real errors
            name_conflicts = [e for e in errors if e.startswith("Name conflict:")]
            real_errors = [e for e in errors if not e.startswith("Name conflict:")]
            
            # Show detailed error report
            error_dialog = QDialog(self)
            error_dialog.setWindowTitle("Rename Results")
            error_layout = QVBoxLayout(error_dialog)
            
            success_label = QLabel(f"Successfully renamed: {len(renamed_files)} files")
            success_label.setStyleSheet("color: green; font-weight: bold;")
            error_layout.addWidget(success_label)
            
            # Show name conflicts as warnings
            if name_conflicts:
                conflict_label = QLabel(f"⚠️ Name conflicts: {len(name_conflicts)}")
                conflict_label.setStyleSheet("color: #ff6b35; font-weight: bold;")
                error_layout.addWidget(conflict_label)
                
                conflict_info = QLabel(
                    "Some files were renamed with (1), (2) suffixes because files with the same name already exist.\n"
                    "This usually happens when renaming files that are already in the target format."
                )
                conflict_info.setWordWrap(True)
                conflict_info.setStyleSheet("color: #666; font-style: italic; margin-bottom: 10px;")
                error_layout.addWidget(conflict_info)
                
                conflict_text = QPlainTextEdit()
                conflict_text.setReadOnly(True)
                conflict_text.setPlainText("\n".join(name_conflicts))
                conflict_text.setMaximumHeight(150)
                error_layout.addWidget(conflict_text)
            
            # Show real errors
            if real_errors:
                error_label = QLabel(f"❌ Errors encountered: {len(real_errors)}")
                error_label.setStyleSheet("color: red; font-weight: bold;")
                error_layout.addWidget(error_label)
                
                error_text = QPlainTextEdit()
                error_text.setReadOnly(True)
                error_text.setPlainText("\n".join(real_errors))
                error_layout.addWidget(error_text)
            
            close_button = QPushButton("Close")
            close_button.clicked.connect(error_dialog.accept)
            error_layout.addWidget(close_button)
            
            error_dialog.resize(600, 400)
            error_dialog.exec()
        else:
            QMessageBox.information(self, "Success", f"All files renamed successfully!\n{len(renamed_files)} files processed.")
    
    # ------------------------------------------------------------------
    # End of Phase 2 helper functions
    # ------------------------------------------------------------------
    
    def on_rename_finished(self, renamed_files, errors, timestamp_backup=None, rename_mapping=None):
        """
        Handle completion of rename operation.
        
        Simplified version after Phase 2 refactoring - delegates to helper functions.
        
        Args:
            renamed_files: List of new file paths after rename.
            errors: List of (path, error) tuples.
            timestamp_backup: Dict of original timestamps for undo.
            rename_mapping: Dict of {new_path: old_path} built by the worker
                            during the rename loop - authoritative source for undo.
        """
        # Store timestamp backup for potential undo operations
        if timestamp_backup:
            self.timestamp_backup = timestamp_backup
        
        # Get file lists
        original_non_media = [f for f in self.files if not is_media_file(f)]
        old_media_files = [f for f in self.files if is_media_file(f)]
        
        # Build undo mapping from the authoritative rename_mapping
        if rename_mapping:
            self.original_filenames = self._create_filename_mapping_from_worker(rename_mapping)
        else:
            # Fallback for timestamp-only operations or legacy callers
            self.original_filenames = self._create_filename_mapping_fallback(
                old_media_files, renamed_files, timestamp_backup
            )
        
        # Rebuild file list widget
        self._rebuild_file_list(renamed_files, original_non_media, old_media_files)
        
        # Update restore button state
        self.update_restore_button_state()
        
        # Show results dialog
        self._show_rename_results(renamed_files, errors)
        
        # Update preview and status
        self.update_preview()
        self.status.showMessage(f"Completed: {len(renamed_files)} files renamed", 5000)
        
        # Calibrate benchmark safety factor based on actual operation time
        if hasattr(self, '_last_estimate_data') and self._last_estimate_data:
            actual_time = time.time() - self._last_estimate_data['start_time']
            self.benchmark_manager.calibrate_from_actual(
                estimated_time=self._last_estimate_data['estimated_time'],
                actual_time=actual_time,
                file_count=self._last_estimate_data['file_count'],
                exif_field_count=self._last_estimate_data['exif_field_count'],
                text_field_count=self._last_estimate_data['text_field_count'],
                with_exif_save=self._last_estimate_data['with_exif_save']
            )
            self._last_estimate_data = None  # Clear after calibration
        
        # Re-enable UI
        self._ui_set_busy(False)
    
    def on_rename_error(self, error_message):
        self._ui_set_busy(False)
        QMessageBox.critical(self, "Critical Error", f"Unexpected error during renaming:\n{error_message}")
        self.status.showMessage("Rename operation failed", 3000)
    
    # ------------------------------------------------------------------
    # Phase 2 Refactoring: Helper functions for undo_rename_action
    # ------------------------------------------------------------------
    
    def _check_undo_availability(self):
        """
        Check if undo operation is available and what can be restored.
        
        Uses only in-memory data and cached async EXIF check results to
        avoid blocking the GUI thread with synchronous ExifTool calls.
        
        Returns:
            tuple: (files_to_undo, timestamp_backup_exists, exif_backup_exists)
        """
        timestamp_backup_exists = hasattr(self, 'timestamp_backup') and bool(getattr(self, 'timestamp_backup'))
        exif_backup_exists = hasattr(self, 'exif_backup') and bool(getattr(self, 'exif_backup'))
        
        # Check which files need to be undone
        files_to_undo = []
        
        # Check in-memory tracking (current session - fast)
        if hasattr(self, 'original_filenames') and self.original_filenames:
            for current_file, original_filename in self.original_filenames.items():
                current_filename = os.path.basename(current_file)
                if current_filename != original_filename and current_file in self.files:
                    files_to_undo.append((current_file, original_filename))
        
        # Check cached EXIF undo results (populated by _start_async_exif_undo_check)
        # If the async check found EXIF undo data and we have no in-memory data,
        # run a batch read to populate the undo list (non-blocking: uses batch JSON).
        if not files_to_undo and getattr(self, '_exif_undo_available', False):
            if self.exiftool_path and hasattr(self, 'files') and self.files:
                from .exif_undo_manager import batch_get_original_filenames
                exif_results = batch_get_original_filenames(self.files, self.exiftool_path)
                for file_path, original_filename in exif_results.items():
                    if original_filename:
                        current_filename = os.path.basename(file_path)
                        if original_filename != current_filename:
                            files_to_undo.append((file_path, original_filename))
                            # Cache in memory for future calls
                            if not hasattr(self, 'original_filenames'):
                                self.original_filenames = {}
                            self.original_filenames[file_path] = original_filename
        
        return files_to_undo, timestamp_backup_exists, exif_backup_exists
    
    def _restore_timestamps_only(self):
        """
        Restore only timestamps (file and EXIF) without renaming files.
        
        Returns:
            list: Error messages
        """
        errors = []
        
        # Disable UI
        self.undo_button.setEnabled(False)
        self.undo_button.setText("⏳ Restoring...")
        self.rename_button.setEnabled(False)
        self.select_files_menu_button.setEnabled(False)
        self.select_folder_menu_button.setEnabled(False)
        self.clear_files_menu_button.setEnabled(False)
        
        # Restore file timestamps
        if hasattr(self, 'timestamp_backup') and self.timestamp_backup:
            try:
                ts_success, ts_errors = batch_restore_timestamps(
                    self.timestamp_backup,
                    progress_callback=lambda msg: self.status.showMessage(msg, 1000)
                )
                if ts_success:
                    self.log(f"✅ Restored file timestamps for {len(ts_success)} files")
                if ts_errors:
                    for file_path, err in ts_errors:
                        errors.append(f"File timestamp restore failed for {os.path.basename(file_path)}: {err}")
                self.timestamp_backup = {}
            except Exception as e:
                errors.append(f"File timestamp restore error: {e}")
        
        # Restore EXIF timestamps
        if hasattr(self, 'exif_backup') and self.exif_backup:
            try:
                from .exif_processor import batch_restore_exif_timestamps
                exif_success, exif_errors = batch_restore_exif_timestamps(
                    self.exif_backup,
                    self.exiftool_path,
                    progress_callback=lambda msg: self.status.showMessage(msg, 1000)
                )
                if exif_success:
                    self.log(f"✅ Restored EXIF timestamps for {len(exif_success)} files")
                    self.exif_service.clear_cache()
                if exif_errors:
                    for file_path, err in exif_errors:
                        errors.append(f"EXIF timestamp restore failed for {os.path.basename(file_path)}: {err}")
                self.exif_backup = {}
            except Exception as e:
                errors.append(f"EXIF timestamp restore error: {e}")
        
        # Re-enable UI
        self.undo_button.setText("↶ Restore Original Names")
        self.rename_button.setEnabled(True)
        self.select_files_menu_button.setEnabled(True)
        self.select_folder_menu_button.setEnabled(True)
        self.clear_files_menu_button.setEnabled(True)
        
        return errors
    
    def _restore_filenames(self, files_to_undo):
        """
        Restore files to their original filenames.
        
        Args:
            files_to_undo: List of (current_file, original_filename) tuples
            
        Returns:
            tuple: (restored_files, errors)
        """
        restored_files = []
        errors = []
        
        # Create a mapping of old paths to new paths for batch update
        path_mapping = {}
        
        for current_file, original_filename in files_to_undo:
            try:
                if os.path.exists(current_file):
                    # Only restore filename, never move between directories
                    current_directory = os.path.dirname(current_file)
                    target_path = os.path.join(current_directory, original_filename)
                    
                    # Check if target already exists
                    if os.path.exists(target_path) and os.path.normpath(target_path) != os.path.normpath(current_file):
                        errors.append(f"Cannot restore {os.path.basename(current_file)}: Target name already exists")
                        continue
                    
                    # Perform the rename
                    shutil.move(current_file, target_path)
                    restored_files.append(target_path)
                    path_mapping[os.path.normpath(current_file)] = target_path
                    
                else:
                    errors.append(f"File not found: {os.path.basename(current_file)}")
            except Exception as e:
                errors.append(f"Failed to restore {os.path.basename(current_file)}: {e}")
        
        # Update all file references in self.files and UI
        if path_mapping:
            # Update self.files list
            for i, file_path in enumerate(self.files):
                normalized_path = os.path.normpath(file_path)
                if normalized_path in path_mapping:
                    self.files[i] = path_mapping[normalized_path]
            
            # Update UI list
            for i in range(self.file_list.count()):
                item = self.file_list.item(i)
                if item:
                    item_path = item.data(Qt.ItemDataRole.UserRole)
                    if item_path:
                        normalized_path = os.path.normpath(item_path)
                        if normalized_path in path_mapping:
                            new_path = path_mapping[normalized_path]
                            item.setText(os.path.basename(new_path))
                            item.setData(Qt.ItemDataRole.UserRole, new_path)
        
        return restored_files, errors
    
    def _restore_all_timestamps(self):
        """
        Restore file and EXIF timestamps after filename restore.
        
        Returns:
            list: Error messages
        """
        errors = []
        
        # Restore file timestamps
        if hasattr(self, 'timestamp_backup') and self.timestamp_backup:
            self.log("🔄 Restoring original file timestamps...")
            try:
                timestamp_successes, timestamp_errors = batch_restore_timestamps(
                    self.timestamp_backup,
                    progress_callback=lambda msg: self.status.showMessage(msg, 1000)
                )
                if timestamp_successes:
                    self.log(f"✅ Restored file timestamps for {len(timestamp_successes)} files")
                if timestamp_errors:
                    self.log(f"❌ Failed to restore file timestamps for {len(timestamp_errors)} files")
                    for file_path, error_msg in timestamp_errors:
                        errors.append(f"File timestamp restore failed for {os.path.basename(file_path)}: {error_msg}")
                self.timestamp_backup = {}
            except Exception as e:
                self.log(f"❌ Error during file timestamp restore: {e}")
                errors.append(f"File timestamp restore error: {e}")
        
        # Restore EXIF timestamps
        if hasattr(self, 'exif_backup') and self.exif_backup:
            self.log("🔄 Restoring original EXIF timestamps...")
            try:
                from .exif_processor import batch_restore_exif_timestamps
                exif_successes, exif_errors = batch_restore_exif_timestamps(
                    self.exif_backup,
                    self.exiftool_path,
                    progress_callback=lambda msg: self.status.showMessage(msg, 1000)
                )
                if exif_successes:
                    self.log(f"✅ Restored EXIF timestamps for {len(exif_successes)} files")
                    self.exif_service.clear_cache()
                if exif_errors:
                    self.log(f"❌ Failed to restore EXIF timestamps for {len(exif_errors)} files")
                    for file_path, error_msg in exif_errors:
                        errors.append(f"EXIF timestamp restore failed for {os.path.basename(file_path)}: {error_msg}")
                self.exif_backup = {}
            except Exception as e:
                self.log(f"❌ Error during EXIF timestamp restore: {e}")
                errors.append(f"EXIF timestamp restore error: {e}")
        
        return errors
    
    # ------------------------------------------------------------------
    # End of Phase 2 undo helper functions
    # ------------------------------------------------------------------
    
    def undo_rename_action(self):
        """
        Restore files to their original names and EXIF timestamps.
        
        Simplified version after Phase 2 refactoring - delegates to helper functions.
        """
        # Check what can be undone
        files_to_undo, timestamp_backup_exists, exif_backup_exists = self._check_undo_availability()
        
        # Nothing to undo?
        if not files_to_undo and not timestamp_backup_exists and not exif_backup_exists:
            QMessageBox.information(
                self,
                "No Undo Available",
                "Nothing to restore.\n\nThe undo function becomes available when either:\n"
                "• Files have been renamed in this session, or\n"
                "• File timestamps were synchronized (and a backup exists), or\n"
                "• EXIF timestamps were shifted (and a backup exists)."
            )
            return
        
        # Only timestamps to restore (no filename changes)?
        if not files_to_undo and (timestamp_backup_exists or exif_backup_exists):
            restore_msg = "File names are unchanged. Restore original "
            restore_items = []
            if timestamp_backup_exists:
                restore_items.append("file timestamps")
            if exif_backup_exists:
                restore_items.append("EXIF timestamps")
            restore_msg += " and ".join(restore_items) + "?"
            
            reply = QMessageBox.question(
                self,
                "Restore Original Timestamps",
                restore_msg,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
            
            # Restore only timestamps
            errors = self._restore_timestamps_only()
            
            if errors:
                QMessageBox.warning(self, "Timestamp Restore", "Some timestamp restores failed:\n" + "\n".join(errors[:10]))
            else:
                QMessageBox.information(self, "Timestamp Restore", "Original timestamps restored successfully.")
            
            self.status.showMessage("Timestamps restored", 4000)
            self.update_preview()
            return
        
        # Confirm filename restore
        reply = QMessageBox.question(
            self,
            "Confirm Undo",
            f"Restore {len(files_to_undo)} files to their original names?\n\n"
            "This will undo all rename operations performed in this session.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        # Disable UI during processing
        self.undo_button.setEnabled(False)
        self.undo_button.setText("⏳ Restoring...")
        self.rename_button.setEnabled(False)
        self.select_files_menu_button.setEnabled(False)
        self.select_folder_menu_button.setEnabled(False)
        self.clear_files_menu_button.setEnabled(False)
        
        # Restore filenames
        restored_files, errors = self._restore_filenames(files_to_undo)
        
        # Restore timestamps
        timestamp_errors = self._restore_all_timestamps()
        errors.extend(timestamp_errors)
        
        # Clear original_filenames tracking
        self.original_filenames = {}
        
        # Show results
        if errors:
            error_dialog = QDialog(self)
            error_dialog.setWindowTitle("Undo Results")
            error_layout = QVBoxLayout(error_dialog)
            
            if restored_files:
                success_label = QLabel(f"Successfully restored: {len(restored_files)} files")
                success_label.setStyleSheet("color: green; font-weight: bold;")
                error_layout.addWidget(success_label)
            
            if errors:
                error_label = QLabel(f"Errors encountered: {len(errors)}")
                error_label.setStyleSheet("color: red; font-weight: bold;")
                error_layout.addWidget(error_label)
                
                error_text = QPlainTextEdit()
                error_text.setReadOnly(True)
                error_text.setPlainText("\n".join(errors))
                error_layout.addWidget(error_text)
            
            close_button = QPushButton("Close")
            close_button.clicked.connect(error_dialog.accept)
            error_layout.addWidget(close_button)
            
            error_dialog.resize(500, 300)
            error_dialog.exec()
        else:
            QMessageBox.information(self, "Undo Complete", f"Successfully restored {len(restored_files)} files to their original names.")
        
        # Update status and UI
        self.status.showMessage(f"Restored {len(restored_files)} files to original names", 5000)
        self.undo_button.setText("↶ Restore Original Names")
        self.undo_button.setEnabled(False)
        self.rename_button.setEnabled(True)
        self.select_files_menu_button.setEnabled(True)
        self.select_folder_menu_button.setEnabled(True)
        self.clear_files_menu_button.setEnabled(True)
        
        # Update preview
        self.update_preview()
    
    # Info dialogs
    def show_camera_prefix_info(self):
        """Show camera prefix help dialog"""
        dialog = QDialog(self)
        dialog.setWindowTitle("Camera Prefix Help")
        dialog.setModal(True)
        dialog.resize(400, 300)
        layout = QVBoxLayout(dialog)
        
        info_text = QLabel("""
Camera Prefix allows you to add a custom identifier for your camera:

Examples:
• A7R3 (for Sony A7R III)
• D850 (for Nikon D850)
• R5 (for Canon EOS R5)

This appears in your filename like:
2025-04-20-A7R3-vacation-001.jpg
        """)
        info_text.setWordWrap(True)
        layout.addWidget(info_text)
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)
        dialog.exec()
    
    def show_additional_info(self):
        """Show additional field help dialog"""
        dialog = QDialog(self)
        dialog.setWindowTitle("Additional Field Help")
        dialog.setModal(True)
        dialog.resize(400, 300)
        layout = QVBoxLayout(dialog)
        
        info_text = QLabel("""
Additional field for custom text in your filename:

Examples:
• vacation
• wedding
• portrait
• landscape

This appears in your filename like:
2025-04-20-A7R3-vacation-001.jpg
        """)
        info_text.setWordWrap(True)
        layout.addWidget(info_text)
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)
        dialog.exec()
    
    def show_separator_info(self):
        """Show separator help dialog"""
        dialog = QDialog(self)
        dialog.setWindowTitle("Separator Help")
        dialog.setModal(True)
        dialog.resize(400, 300)
        layout = QVBoxLayout(dialog)
        
        info_text = QLabel("""
Choose how to separate filename components:

Options:
• - (dash): 2025-04-20-A7R3-vacation-001.jpg
• _ (underscore): 2025_04_20_A7R3_vacation_001.jpg
• (none): 20250420A7R3vacation001.jpg
        """)
        info_text.setWordWrap(True)
        layout.addWidget(info_text)
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)
        dialog.exec()
    
    def show_preview_info(self):
        """Show interactive preview help dialog - delegates to PreviewGenerator"""
        self.preview_generator.show_preview_info()

    def show_exif_sync_info(self):
        """Show EXIF date synchronization help dialog"""
        dialog = QDialog(self)
        dialog.setWindowTitle("⚠️ EXIF Date Synchronization")
        dialog.setModal(True)
        dialog.resize(500, 400)
        layout = QVBoxLayout(dialog)
        
        # Warning header
        warning_label = QLabel("⚠️ WARNING: This feature modifies file metadata!")
        warning_label.setStyleSheet("color: #ff6b35; font-weight: bold; font-size: 14px;")
        layout.addWidget(warning_label)
        
        info_text = QLabel("""
<b>What this feature does:</b>
• Extracts DateTimeOriginal from EXIF metadata
• Sets it as the file's creation and modification date
• Helps cloud services show correct photo dates

<b>Why you might need this:</b>
Many cloud storage services (Google Photos, iCloud, OneDrive) use the file's creation date instead of the EXIF DateTimeOriginal for photo organization and timeline display.

<b>Requirements:</b>
• ExifTool must be installed and detected
• Files must contain valid EXIF DateTimeOriginal data

<b>Safety features:</b>
• Original file timestamps are backed up
• Can be reversed using the "Restore Original Names" function
• Only processes files with valid EXIF dates
• Skips files that already have matching dates

<b>Supported formats:</b>
JPG, TIFF, RAW files (CR2, NEF, ARW, etc.)
        """)
        info_text.setWordWrap(True)
        layout.addWidget(info_text)
        
        close_btn = QPushButton("I Understand")
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)
        dialog.exec()

    def restore_settings(self):
        """Restore application settings"""
        # Restore window geometry and state
        geometry = self.settings_manager.get_window_geometry()
        if geometry:
            self.restoreGeometry(geometry)
            
        state = self.settings_manager.get_window_state()
        if state:
            self.restoreState(state)
            
        # Restore theme
        theme = self.settings_manager.get_theme()
        if theme:
            self.theme_combo.setCurrentText(theme)
            self.theme_manager.apply_theme(theme, self)
            
        # Restore last directory
        last_dir = self.settings_manager.get_last_directory()
        if last_dir and os.path.exists(last_dir):
            # We don't automatically load files, but we could set the default dir for dialogs
            pass

    def closeEvent(self, event):
        """Handle application close event.
        
        Cleans up both the instance-based ExifService and the legacy
        global ExifTool process to prevent subprocess leaks.
        """
        # Cleanup instance-based ExifService
        if hasattr(self, 'exif_service') and self.exif_service:
            self.exif_service.cleanup()
        
        # Cleanup legacy global ExifTool instance (prevents subprocess leak)
        cleanup_global_exiftool()
        
        # Save window geometry and state
        self.settings_manager.set_window_geometry(self.saveGeometry())
        self.settings_manager.set_window_state(self.saveState())
        self.settings_manager.sync()
        super().closeEvent(event)
    
    # Drag and drop implementation
    def dragEnterEvent(self, event: QDragEnterEvent):
        """Handle drag enter events - delegates to FileListManager"""
        self.file_list_manager.handle_drag_enter(event)

    def dragMoveEvent(self, event: QDragMoveEvent):
        """Handle drag move events - delegates to FileListManager"""
        self.file_list_manager.handle_drag_move(event)

    def dropEvent(self, event: QDropEvent):
        """Handle drop events - delegates to FileListManager"""
        self.file_list_manager.handle_drop(event)
    
    def eventFilter(self, obj, event):
        """Event filter for tooltips and other events"""
        if obj == self.file_list and event.type() == event.Type.ToolTip:
            item = self.file_list.itemAt(event.pos())
            if item:
                file_path = item.data(Qt.ItemDataRole.UserRole)
                if file_path and is_media_file(file_path):
                    # Show file info as tooltip
                    file_info = f"File: {os.path.basename(file_path)}\nPath: {file_path}"
                    item.setToolTip(file_info)
        return super().eventFilter(obj, event)


def analyze_file_statistics(files):
    """Analyze file statistics by type and extension"""
    stats = {
        'total': 0,
        'images': 0,
        'videos': 0,
        'extensions': {},
        'categories': {
            'JPEG': 0,
            'RAW': 0,
            'PNG/Other Images': 0,
            'MP4/MOV': 0,
            'MKV/AVI': 0,
            'Other Videos': 0
        }
    }
    
    # Define category mappings
    jpeg_extensions = ['.jpg', '.jpeg']
    raw_extensions = ['.cr2', '.nef', '.arw', '.orf', '.rw2', '.dng', '.raw', '.sr2', '.pef', '.raf', '.3fr', '.erf', '.kdc', '.mos', '.nrw', '.srw', '.x3f']
    png_other_image_extensions = ['.png', '.bmp', '.tiff', '.tif', '.gif']
    mp4_mov_extensions = ['.mp4', '.mov', '.m4v']
    mkv_avi_extensions = ['.mkv', '.avi', '.wmv', '.flv']
    other_video_extensions = ['.webm', '.mpg', '.mpeg', '.m2v', '.mts', '.m2ts', '.ts', '.vob', '.asf', '.rm', '.rmvb', '.f4v', '.ogv', '.3gp']
    
    for file_path in files:
        if is_media_file(file_path):
            stats['total'] += 1
            
            # Get extension
            ext = os.path.splitext(file_path)[1].lower()
            stats['extensions'][ext] = stats['extensions'].get(ext, 0) + 1
            
            # Categorize by type
            if ext in jpeg_extensions + raw_extensions + png_other_image_extensions:
                stats['images'] += 1
                
                # Subcategorize images
                if ext in jpeg_extensions:
                    stats['categories']['JPEG'] += 1
                elif ext in raw_extensions:
                    stats['categories']['RAW'] += 1
                elif ext in png_other_image_extensions:
                    stats['categories']['PNG/Other Images'] += 1
                    
            elif ext in mp4_mov_extensions + mkv_avi_extensions + other_video_extensions:
                stats['videos'] += 1
                
                # Subcategorize videos
                if ext in mp4_mov_extensions:
                    stats['categories']['MP4/MOV'] += 1
                elif ext in mkv_avi_extensions:
                    stats['categories']['MKV/AVI'] += 1
                elif ext in other_video_extensions:
                    stats['categories']['Other Videos'] += 1
    
    return stats

def format_file_statistics(stats):
    """Format file statistics into a human-readable string"""
    if stats['total'] == 0:
        return "No media files loaded"
    
    # Build summary line
    summary_parts = []
    if stats['images'] > 0:
        summary_parts.append(f"{stats['images']} image{'s' if stats['images'] != 1 else ''}")
    if stats['videos'] > 0:
        summary_parts.append(f"{stats['videos']} video{'s' if stats['videos'] != 1 else ''}")
    
    summary = f"📊 Total: {stats['total']} files ({', '.join(summary_parts)})"
    
    # Build detailed breakdown
    details = []
    for category, count in stats['categories'].items():
        if count > 0:
            details.append(f"{category}: {count}")
    
    if details:
        detail_text = " | ".join(details)
        return f"{summary}\n💾 {detail_text}"
    else:
        return summary


def main():
    """Main entry point"""
    app = QApplication(sys.argv)
    
    # Set application properties
    app.setApplicationName("File Renamer")
    app.setApplicationVersion("2.0")
    app.setOrganizationName("FileRenamer")
    
    window = FileRenamerApp()
    window.show()
    
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
