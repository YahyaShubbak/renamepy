#!/usr/bin/env python3
"""
Complete original UI implementation with all features from RenameFiles.py
"""

import os
import sys
import subprocess
from .logger_util import get_logger, set_level
log = get_logger()

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel, QPushButton,
    QMessageBox, QDialog, QStyle, QPlainTextEdit
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon, QDragEnterEvent, QDropEvent, QDragMoveEvent

# Import the modular components
from .file_utilities import is_media_file, is_image_file, is_video_file
from .exif_service_new import ExifService, EXIFTOOL_AVAILABLE, format_exposure_time
from .exif_processor import find_exiftool_path, set_default_exif_service
from .rename_engine import RenameWorkerThread
from .theme_manager import ThemeManager
from .timestamp_options_dialog import TimestampSyncOptionsDialog
from .dialogs import ExifToolWarningDialog
from .handlers import UndoHandler
from .handlers.info_dialogs import (
    show_camera_prefix_info as _show_camera_prefix_info,
    show_additional_info as _show_additional_info,
    show_separator_info as _show_separator_info,
    show_exif_sync_info as _show_exif_sync_info,
)
from .exif_undo_manager import get_original_filename_from_exif
from .ui import FileListManager, PreviewGenerator, MainWindowUI, MetadataDialogManager
from .state_model import RenamerState
from .settings_manager import SettingsManager
from .backup_journal import load_journal as _load_undo_journal


class FileRenamerApp(QMainWindow):
    DEBUG_VERBOSE = False

    # --- State Model Delegation Properties ---
    @property
    def files(self): return self.state.files
    @files.setter
    def files(self, value): self.state.files = value

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
        
        # Initialize ExifService (single source of truth for all EXIF operations)
        self.exif_service = ExifService(self.exiftool_path)
        # Register with exif_processor so legacy delegate functions work
        set_default_exif_service(self.exif_service)
        
        if EXIFTOOL_AVAILABLE and self.exiftool_path:
            self.exif_method = "exiftool"
        else:
            self.exif_method = None
        
        # Initialize theme manager
        self.theme_manager = ThemeManager()
        
        # Initialize UI managers
        self.file_list_manager = FileListManager(self)
        self.preview_generator = PreviewGenerator(self)
        self.undo_handler = UndoHandler(self)
        self.metadata_dialog_manager = MetadataDialogManager(self)
        
        # State variables (Managed by RenamerState)
        self.state = RenamerState()
        self.settings_manager = SettingsManager()
        self.current_order = ["Date", "Prefix", "Additional", "Camera", "Lens"]
        
        self.setup_ui()
        
        # Restore settings
        self.restore_settings()
        
        # Recover any undo backup left on disk from a previous session
        # (e.g. the app crashed or was closed before Undo was used).
        self._recover_pending_backups()
        self.worker = None
        self._progress_dialog = None

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

        # Check for undo availability (in-memory/journal OR EXIF metadata)
        can_undo = self.has_restore_data()
        
        # Also check if any loaded file has original filename in EXIF (cached check)
        # (not while a rename runs: the check would read files being renamed)
        if not can_undo and has_files and self.exiftool_path and not self._busy:
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
            bool: True if there are filenames, file timestamps, or EXIF
                  timestamps that can be restored
        """
        # Check if we have original filename tracking (regardless of whether they've changed)
        has_filename_data = bool(self.original_filenames)
        
        # Check if we have timestamp backup data
        has_timestamp_data = bool(self.timestamp_backup)

        # Check if we have EXIF timestamp backup data (e.g. from a Time
        # Shift operation, or recovered from a previous session)
        has_exif_data = bool(self.exif_backup)
        
        return has_filename_data or has_timestamp_data or has_exif_data

    def update_restore_button_state(self):
        """Update the restore button state based on available restore data"""
        if self.has_restore_data():
            self.undo_button.setEnabled(True)
            # Update button text based on what can be restored
            pending = []
            if self.original_filenames:
                pending.append("Names")
            if self.timestamp_backup:
                pending.append("Timestamps")
            if self.exif_backup:
                pending.append("EXIF")
            self.undo_button.setText(f"↶ Restore {' & '.join(pending)}")
        else:
            self.undo_button.setEnabled(False)
            self.undo_button.setText("↶ Restore Original Names")

    def _recover_pending_backups(self):
        """Load any undo backup left on disk by a previous session.

        The timestamp-sync and EXIF time-shift features persist their
        backups to an on-disk journal *before* performing the destructive
        write for each file (see backup_journal.PersistedBackupDict). If the
        app was closed or crashed before the user clicked Undo, that backup
        is recovered here instead of being lost.
        """
        try:
            journal = _load_undo_journal()
        except Exception as e:
            log.warning(f"Could not read undo journal on startup: {e}")
            return

        recovered = []
        if journal.get("original_filenames"):
            self.original_filenames = dict(journal["original_filenames"])
            recovered.append(f"{len(self.original_filenames)} file name(s)")
        if journal.get("timestamp_backup"):
            self.timestamp_backup = dict(journal["timestamp_backup"])
            recovered.append(f"{len(self.timestamp_backup)} file timestamp(s)")
        if journal.get("exif_backup"):
            self.exif_backup = dict(journal["exif_backup"])
            recovered.append(f"{len(self.exif_backup)} EXIF timestamp(s)")

        if recovered:
            log.info(
                "Recovered pending undo data from a previous session: "
                + ", ".join(recovered)
            )
            self.update_restore_button_state()
            self.status.showMessage(
                "⚠ Recovered an unfinished undo from your last session — "
                "click Restore to review it.",
                8000,
            )

    def forget_undo_data(self):
        """Discard all pending undo data (in memory and in the on-disk journal).

        Backups are kept until they are restored, so without this a user who
        is happy with a sync or rename would carry them - and an always
        enabled Restore button - forever.
        """
        if not self.has_restore_data():
            QMessageBox.information(self, "Forget Undo Data", "There is no undo data to forget.")
            return
        reply = QMessageBox.question(
            self,
            "Forget Undo Data",
            "Discard all undo information (original file names, timestamps and EXIF dates)?\n\n"
            "The current state of your files becomes final; this cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        from .backup_journal import clear_all as _clear_undo_journal
        self.original_filenames = {}
        self.timestamp_backup = {}
        self.exif_backup = {}
        _clear_undo_journal()
        self.update_restore_button_state()
        self._update_buttons()
        self.status.showMessage("Undo data discarded", 4000)

    def setup_ui(self):
        """Setup the complete original UI design"""
        # Delegate UI setup to MainWindowUI
        self.ui = MainWindowUI()
        self.ui.setup_ui(self)
        
        # Sensible default size so the file-list drop zone doesn't dominate
        # the window with empty space on first launch. restore_settings()
        # (called after setup_ui() in __init__) will override this with the
        # user's own saved geometry on subsequent launches, if any exists.
        self.resize(940, 640)
        # Qt otherwise computes an effective minimum size from the widgets'
        # own size hints (long checkbox labels, etc.), which can end up
        # larger than people expect and stop the window shrinking further.
        # Set an explicit, small floor instead so it can always be resized
        # down if wanted.
        self.setMinimumSize(560, 420)
        
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
                dialog = ExifToolWarningDialog(self)
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
        self.metadata_dialog_manager.show_media_info(item)

    def show_file_list_context_menu(self, position):
        """Right-click menu on the file list - discoverable alternative to the click gestures"""
        self.metadata_dialog_manager.show_context_menu(position)

    def show_selected_exif(self, item):
        """Show EXIF data dialog on double click"""
        self.metadata_dialog_manager.show_selected_exif(item)

    def show_exif_info(self, file_path):
        """Show complete EXIF information in a dialog"""
        self.metadata_dialog_manager.show_exif_info(file_path)

    def show_exif_dialog(self, file_path, info_str):
        """Show detailed EXIF metadata dialog with two-stage display and checkboxes for filename inclusion"""
        self.metadata_dialog_manager.show_exif_dialog(file_path, info_str)

    def create_essential_metadata_widget(self, full_metadata, file_path):
        """Create widget with essential metadata and checkboxes for filename inclusion"""
        return self.metadata_dialog_manager.create_essential_metadata_widget(full_metadata, file_path)

    def on_metadata_checkbox_changed(self, metadata_key, value, checked, user_action=False):
        """Handle metadata checkbox changes for filename inclusion"""
        self.metadata_dialog_manager.on_metadata_checkbox_changed(metadata_key, value, checked, user_action)

    def on_camera_checkbox_changed(self):
        """Handle camera checkbox changes and sync with metadata"""
        self.metadata_dialog_manager.on_camera_checkbox_changed()

    def on_lens_checkbox_changed(self):
        """Handle lens checkbox changes and sync with metadata"""
        self.metadata_dialog_manager.on_lens_checkbox_changed()

    def on_shooting_setting_checkbox_changed(self, key):
        """Handle ISO/Aperture/Shutter/Focal Length checkbox changes"""
        self.metadata_dialog_manager.on_shooting_setting_checkbox_changed(key)

    def toggle_full_metadata(self, dialog, layout, full_info, essential_widget):
        """Toggle between essential and full metadata view"""
        self.metadata_dialog_manager.toggle_full_metadata(dialog, layout, full_info, essential_widget)

    def extract_camera_info(self):
        """Extract camera and lens info from first media file (copied from original)"""
        if not self.files:
            self.update_camera_lens_labels()
            self.update_shooting_settings_labels()
            return
        
        # Use first media file for detection (prioritize images, then videos)
        first_media = next((f for f in self.files if is_image_file(f)), None)
        if not first_media:
            first_media = next((f for f in self.files if is_video_file(f)), None)
        if not first_media:
            first_media = next((f for f in self.files if is_media_file(f)), None)
        
        if not first_media:
            self.update_camera_lens_labels()
            self.update_shooting_settings_labels()
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
        
        # Detect ISO/Aperture/Shutter/Focal Length availability from the
        # same file's raw EXIF data, so the corresponding checkboxes can be
        # disabled when the field genuinely isn't there (e.g. a video file,
        # or a camera that doesn't record focal length).
        self.detected_shooting_settings = {}
        try:
            raw_exif = self.exif_service.extract_raw_exif(first_media) or {}
            iso = raw_exif.get('EXIF:ISO') or raw_exif.get('MakerNotes:SonyISO')
            aperture = raw_exif.get('EXIF:FNumber') or raw_exif.get('Composite:Aperture')
            shutter = raw_exif.get('EXIF:ExposureTime')
            focal_length = raw_exif.get('EXIF:FocalLength')
            self.detected_shooting_settings = {
                'iso': iso,
                'aperture': aperture,
                'shutter': shutter,
                'focal_length': focal_length,
            }
        except Exception as e:
            self.log(f"Error extracting shooting settings from {first_media}: {e}")
        
        # Update labels
        self.update_camera_lens_labels()
        self.update_shooting_settings_labels()

    def _label_style(self, color_name, bold=False):
        """Style sheet for a status label in a colour that suits the theme."""
        weight = "font-weight: bold;" if bold else "font-style: italic;"
        return f"color: {self.theme_manager.color(color_name)}; {weight}"

    def on_theme_colors_changed(self):
        """Re-colour the status labels after a theme change (called by ThemeManager)."""
        if not hasattr(self, 'camera_model_label'):
            return  # UI not built yet
        self.update_camera_lens_labels()
        self.update_shooting_settings_labels()
        self.update_exif_status()

    def update_camera_lens_labels(self):
        """Update the camera and lens model labels (copied from original)"""
        if not self.files or not self.exif_method:
            self.camera_model_label.setText("(no files selected)")
            self.lens_model_label.setText("(no files selected)")
            return
        
        # Use stored detection results
        if hasattr(self, 'detected_camera') and self.detected_camera:
            self.camera_model_label.setText(f"({self.detected_camera})")
            self.camera_model_label.setStyleSheet(self._label_style("success"))
        else:
            self.camera_model_label.setText("(not detected)")
            self.camera_model_label.setStyleSheet(self._label_style("warning"))
        
        if hasattr(self, 'detected_lens') and self.detected_lens:
            self.lens_model_label.setText(f"({self.detected_lens})")
            self.lens_model_label.setStyleSheet(self._label_style("success"))
        else:
            self.lens_model_label.setText("(not detected)")
            self.lens_model_label.setStyleSheet(self._label_style("warning"))

    def update_shooting_settings_labels(self):
        """Update the ISO/Aperture/Shutter/Focal Length labels, and enable
        or disable each checkbox depending on whether that field is
        actually present in the detected file's EXIF data - a field that
        isn't there (e.g. no focal length on some cameras, no EXIF at all
        on a video file) shouldn't be clickable.
        """
        detected = getattr(self, 'detected_shooting_settings', {}) or {}
        
        for key, checkbox in self.shooting_setting_checkboxes.items():
            label = self.shooting_setting_labels[key]
            value = detected.get(key)
            
            if not self.files or not self.exif_method:
                label.setText("(no files selected)")
                label.setStyleSheet(self._label_style("muted"))
                available = False
            elif value:
                display = self._format_shooting_setting_display(key, value)
                label.setText(f"({display})")
                label.setStyleSheet(self._label_style("success"))
                available = True
            else:
                label.setText("(not available)")
                label.setStyleSheet(self._label_style("warning"))
                available = False
            
            checkbox.setEnabled(available)
            if not available and checkbox.isChecked():
                # Field disappeared (e.g. files changed to a set without
                # it) - uncheck and drop the stale flag rather than leaving
                # a checked-but-disabled box with a flag nothing will
                # resolve at rename time.
                checkbox.blockSignals(True)
                checkbox.setChecked(False)
                checkbox.blockSignals(False)
                self.selected_metadata.pop(key, None)

    @staticmethod
    def _format_shooting_setting_display(key, value):
        """Format a raw EXIF value for the small status label, matching the
        same conventions as the Essential Metadata dialog
        (MetadataDialogManager.create_essential_metadata_widget) so the two
        places agree on what "aperture"/"shutter"/etc. look like.
        """
        if key == 'iso':
            return f"ISO {value}"
        if key == 'aperture':
            return f"f/{value}"
        if key == 'shutter':
            return format_exposure_time(value) or f"{value}"
        if key == 'focal_length':
            return f"{value}mm" if 'mm' not in str(value).lower() else str(value)
        return str(value)
    
    def update_preview(self):
        """Update the interactive preview widget with current settings - delegates to PreviewGenerator"""
        self.preview_generator.update_preview()
    
    def on_preview_order_changed(self, new_order):
        """Handle drag & drop reordering in the interactive preview.

        The widget reports component ids (not display texts), so the order
        is taken over as is.
        """
        self.preview_generator.apply_order(new_order)
    
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
            self.exif_status_label.setStyleSheet(self._label_style("success", bold=True))
        else:
            self.exif_status_label.setText("⚠ ExifTool not found — EXIF features unavailable")
            self.exif_status_label.setStyleSheet(self._label_style("error", bold=True))
    
    def rename_files_action(self):
        # Guard: prevent starting a second rename while one is running
        if getattr(self, '_busy', False):
            log.warning("Rename already in progress — ignoring duplicate request")
            return
        if self.worker is not None and self.worker.isRunning():
            log.warning("Worker thread still running — ignoring duplicate request")
            return
        # The background undo check reads the current files; let it finish
        # (it probes at most three files) before they get renamed.
        checker = getattr(self, '_exif_undo_checker_ref', None)
        if checker is not None and checker.isRunning():
            checker.wait(10000)

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
        try:
            self._confirm_and_start_rename(
                media_files, camera_prefix, additional, use_camera, use_lens,
                use_date, continuous_counter, date_format, separator,
            )
        except Exception:
            # Never leave the UI stuck in "Processing..." if anything before
            # the worker start fails; the global excepthook reports the error.
            if not (self.worker is not None and self.worker.isRunning()):
                self._close_progress()
                self._ui_set_busy(False)
            raise

    def _confirm_and_start_rename(self, media_files, camera_prefix, additional, use_camera,
                                  use_lens, use_date, continuous_counter, date_format, separator):
        """Ask the sync questions, then compute the rename plan in the background.

        Flow: (optional) timestamp-sync confirmation -> plan (background,
        cancellable) -> RenamePlanDialog listing every old -> new name ->
        execution with a progress dialog (cancellable) -> results.
        """
        sync_exif_date = self.checkbox_sync_exif_date.isChecked()
        leave_file_names = self.checkbox_leave_names.isChecked()
        save_original_to_exif = self.checkbox_save_original_to_exif.isChecked()
        rename_sidecars = self.checkbox_rename_sidecars.isChecked()

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
            if dlg.exec() != QDialog.DialogCode.Accepted or not dlg.get_result():
                self._ui_set_busy(False)
                return
            timestamp_options = dlg.get_result()
        elif leave_file_names:
            QMessageBox.information(
                self, "Nothing to Do",
                "'Leave file names as-is' is enabled and timestamp sync is off, "
                "so there is nothing to change."
            )
            self._ui_set_busy(False)
            return

        # Everything needed to create the plan and the execution workers
        self._rename_request = dict(
            files=media_files,
            camera_prefix=camera_prefix,
            additional=additional,
            use_camera=use_camera,
            use_lens=use_lens,
            exif_method=self.exif_method,
            separator=separator,
            exiftool_path=self.exiftool_path,
            custom_order=list(self.custom_order),
            date_format=date_format,
            use_date=use_date,
            continuous_counter=continuous_counter,
            selected_metadata=dict(self.selected_metadata),
            sync_exif_date=sync_exif_date,
            timestamp_options=timestamp_options,
            leave_names=leave_file_names,
            save_original_to_exif=save_original_to_exif,
            rename_sidecars=rename_sidecars,
        )

        if leave_file_names:
            # Only the timestamp sync: no names to review
            self._start_rename_execution([], [])
            return

        self._start_worker("plan")
        self.worker.plan_ready.connect(self.on_plan_ready)
        self._show_progress("Reading metadata and computing new names...", busy=True)
        self.worker.start()

    def _start_worker(self, mode, **extra):
        """Create the rename worker for *mode* from the stored request."""
        request = self._rename_request
        self.worker = RenameWorkerThread(
            request['files'],
            request['camera_prefix'],
            request['additional'],
            request['use_camera'],
            request['use_lens'],
            request['exif_method'],
            request['separator'],
            request['exiftool_path'],
            request['custom_order'],
            request['date_format'],
            request['use_date'],
            request['continuous_counter'],
            request['selected_metadata'],
            request['sync_exif_date'],
            timestamp_options=request['timestamp_options'],
            leave_names=request['leave_names'],
            save_original_to_exif=request['save_original_to_exif'],
            rename_sidecars=request['rename_sidecars'],
            log_callable=self.log,
            exif_service=self.exif_service,
            prior_originals=dict(self.original_filenames),
            mode=mode,
            parent=self,
            **extra,
        )
        self.worker.progress_update.connect(self.update_status)
        self.worker.error.connect(self.on_rename_error)

    def _show_progress(self, text, busy=False, total=0):
        """Modal progress dialog whose Cancel button stops the worker."""
        from PyQt6.QtWidgets import QProgressDialog

        self._close_progress()
        progress = QProgressDialog(text, "Cancel", 0, 0 if busy else max(total, 1), self)
        progress.setWindowTitle("RenamePy")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(300)
        progress.setAutoClose(False)
        progress.setAutoReset(False)
        progress.setValue(0)
        worker = self.worker
        progress.canceled.connect(worker.requestInterruption)
        progress.canceled.connect(lambda: progress.setLabelText("Cancelling after the current file..."))
        worker.progress_update.connect(progress.setLabelText)

        def on_value(done, total_):
            if progress.maximum() != total_:
                progress.setMaximum(max(total_, 1))
            progress.setValue(done)

        worker.progress_value.connect(on_value)
        self._progress_dialog = progress

    def _close_progress(self):
        progress = getattr(self, '_progress_dialog', None)
        if progress is not None:
            progress.close()
            progress.deleteLater()
            self._progress_dialog = None

    def on_plan_ready(self, entries, errors):
        """Show the complete plan and execute it after confirmation."""
        from .dialogs import RenamePlanDialog

        self._close_progress()
        worker = self.worker
        worker.wait()
        if worker.was_cancelled:
            self._ui_set_busy(False)
            self.status.showMessage("Rename cancelled", 4000)
            return

        dialog = RenamePlanDialog(entries, errors, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            self._ui_set_busy(False)
            self.status.showMessage("Rename cancelled - no files were changed", 4000)
            return
        self._start_rename_execution(entries, errors)

    def _start_rename_execution(self, entries, plan_errors):
        self._start_worker("execute", plan=entries, plan_errors=plan_errors)
        self.worker.finished.connect(self.on_rename_finished)
        total = sum(1 for e in entries if e.changed)
        self._show_progress("Renaming files..." if total else "Synchronizing timestamps...",
                            busy=not total, total=total)
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
                # Merge with existing backup (in case of multiple shifts).
                # The first backup of a file holds its original dates, so
                # it must never be replaced by a later, already-shifted one.
                for path, fields in exif_backup.items():
                    self.exif_backup.setdefault(path, fields)
                self.log(f"📦 Backed up EXIF data for {len(exif_backup)} files")
                self.update_restore_button_state()
            
            # Clear EXIF cache to reload updated data
            self.exif_service.clear_cache()
            
            # Update preview with new times
            self.update_preview()
            
            # Show success message
            self.status.showMessage("EXIF timestamps updated successfully", 5000)

    # ------------------------------------------------------------------
    # Phase 2 Refactoring: Helper functions for on_rename_finished
    # ------------------------------------------------------------------
    
    def _merge_rename_mapping(self, rename_mapping: dict) -> dict:
        """
        Merge the worker's rename_mapping into the undo mapping.

        Keeps entries for files that were not part of this rename (or whose
        rename failed) and preserves the chain back to the *original* name
        across repeated renames.

        Args:
            rename_mapping: Dict of {new_path: old_path} from the worker.

        Returns:
            dict: Mapping of {current_path: original_basename} for undo.
        """
        merged = dict(self.original_filenames)
        for new_path, old_path in rename_mapping.items():
            if new_path == old_path:
                continue
            original = merged.pop(old_path, None) or os.path.basename(old_path)
            merged[new_path] = original
            self.log(f"Mapping: {os.path.basename(new_path)} -> {original}")
        return merged

    def _rebuild_file_list(self, moved: dict):
        """
        Rebuild the file list after a rename operation.

        Every file stays in the list in its original order - renamed files
        under their new path, files whose rename failed (or that were not
        renamed, e.g. non-media files) under their current path.

        Args:
            moved: Dict of {old_path: new_path} for files that were renamed.
        """
        current_files = [moved.get(path, path) for path in self.files]
        self.files.clear()
        self.files.extend(current_files)
        self.file_list_manager.update_file_list()
    
    def _show_rename_results(self, renamed_files, errors):
        """
        Show results dialog with success/error information.
        
        Args:
            renamed_files: List of successfully renamed files
            errors: List of (file_path, message) tuples
        """
        if errors:
            error_lines = [
                f"{os.path.basename(path)}: {message}" if path else str(message)
                for path, message in errors
            ]

            # Show detailed error report
            error_dialog = QDialog(self)
            error_dialog.setWindowTitle("Rename Results")
            error_layout = QVBoxLayout(error_dialog)
            
            success_label = QLabel(f"Successfully renamed: {len(renamed_files)} files")
            success_label.setStyleSheet(self._label_style("success", bold=True))
            error_layout.addWidget(success_label)

            error_label = QLabel(f"❌ Problems encountered: {len(error_lines)}")
            error_label.setStyleSheet(self._label_style("error", bold=True))
            error_layout.addWidget(error_label)

            error_text = QPlainTextEdit()
            error_text.setReadOnly(True)
            error_text.setPlainText("\n".join(error_lines))
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
        
        Args:
            renamed_files: List of new file paths after rename.
            errors: List of (path, error) tuples.
            timestamp_backup: Dict of original timestamps for undo.
            rename_mapping: Dict of {new_path: old_path} built by the worker
                            during the rename loop - authoritative source for undo.
        """
        from .backup_journal import rekey_entries

        self._close_progress()
        rename_mapping = rename_mapping or {}
        moved = {old: new for new, old in rename_mapping.items() if new != old}

        # Store timestamp backup for potential undo operations. The worker's
        # backup already contains the pending journal entries; earlier
        # in-memory entries (the file's original times) always win.
        if timestamp_backup:
            for path, times in timestamp_backup.items():
                self.timestamp_backup.setdefault(path, times)

        # Backups are keyed by path, so they must follow renamed files
        # (the worker already did the same for the on-disk journal).
        if moved:
            self.timestamp_backup = rekey_entries(self.timestamp_backup, moved)
            self.exif_backup = rekey_entries(self.exif_backup, moved)
            self.original_filenames = self._merge_rename_mapping(rename_mapping)

        # Rebuild file list widget
        self._rebuild_file_list(moved)
        
        # Update restore button state
        self.update_restore_button_state()

        # Re-enable UI before the (modal) results dialog
        self._ui_set_busy(False)
        
        # Show results dialog
        self._show_rename_results(renamed_files, errors)
        
        # Update preview and status
        self.update_preview()
        self.status.showMessage(f"Completed: {len(renamed_files)} files renamed", 5000)

    def on_rename_error(self, error_message):
        self._close_progress()
        self._ui_set_busy(False)
        QMessageBox.critical(self, "Critical Error", f"Unexpected error during renaming:\n{error_message}")
        self.status.showMessage("Rename operation failed", 3000)
    
    # ------------------------------------------------------------------
    # Undo operations — delegated to modules.handlers.undo_handler
    # ------------------------------------------------------------------

    def _check_undo_availability(self):
        """Check if undo operation is available and what can be restored."""
        return self.undo_handler._check_undo_availability()

    def _restore_timestamps_only(self):
        """Restore only timestamps (file and EXIF) without renaming files."""
        return self.undo_handler._restore_timestamps_only()

    def _restore_filenames(self, files_to_undo):
        """Restore files to their original filenames."""
        return self.undo_handler._restore_filenames(files_to_undo)

    def _restore_all_timestamps(self):
        """Restore file and EXIF timestamps after filename restore."""
        return self.undo_handler._restore_all_timestamps()

    def undo_rename_action(self):
        """Restore files to their original names and EXIF timestamps."""
        self.undo_handler.undo_rename_action()

    # Info dialogs — delegated to modules.handlers.info_dialogs
    def show_camera_prefix_info(self):
        """Show camera prefix help dialog."""
        _show_camera_prefix_info(self)

    def show_additional_info(self):
        """Show additional field help dialog."""
        _show_additional_info(self)

    def show_separator_info(self):
        """Show separator help dialog."""
        _show_separator_info(self)

    def show_preview_info(self):
        """Show interactive preview help dialog - delegates to PreviewGenerator."""
        self.preview_generator.show_preview_info()

    def show_exif_sync_info(self):
        """Show EXIF date synchronization help dialog."""
        _show_exif_sync_info(self)

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
        
        Refuses to close while a rename is running (destroying a running
        QThread aborts the process mid-operation), stops background threads,
        and cleans up the ExifService to prevent subprocess leaks.
        """
        worker = getattr(self, 'worker', None)
        if worker is not None and worker.isRunning():
            QMessageBox.warning(
                self,
                "Rename in Progress",
                "Files are still being renamed.\n\n"
                "Please wait until the operation has finished before closing the application.",
            )
            event.ignore()
            return

        checker = getattr(self, '_exif_undo_checker_ref', None)
        if checker is not None and checker.isRunning():
            checker.wait()

        if hasattr(self, 'exif_service') and self.exif_service:
            self.exif_service.cleanup()
        
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


def _install_excepthook():
    """Report unhandled exceptions instead of letting PyQt6 abort the process.

    With the default hook, PyQt6 calls qFatal() for any exception raised in
    a slot, killing the application - including in-memory undo state.
    """
    import traceback

    def _hook(exc_type, exc_value, exc_tb):
        details = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        log.error(f"Unhandled exception:\n{details}")
        if QApplication.instance() is not None:
            box = QMessageBox(QMessageBox.Icon.Critical, "Unexpected Error",
                              f"An unexpected error occurred:\n{exc_value}\n\n"
                              "The application keeps running; please report this problem.")
            box.setDetailedText(details)
            box.exec()

    sys.excepthook = _hook


def main():
    """Main entry point"""
    app = QApplication(sys.argv)
    _install_excepthook()
    
    # Set application properties
    app.setApplicationName("File Renamer")
    app.setApplicationVersion("2.0")
    app.setOrganizationName("FileRenamer")
    
    window = FileRenamerApp()
    window.show()
    
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
