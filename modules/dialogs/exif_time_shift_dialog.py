"""
EXIF Time Shift Dialog - Adjust timestamps for all photos
Useful when camera clock was set incorrectly
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSpinBox, QRadioButton, QButtonGroup, QGroupBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QMessageBox, QProgressDialog
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QColor
import os
from datetime import datetime, timedelta

from ..file_utilities import is_media_file
from ..logger_util import get_logger

log = get_logger()


# Date tags backed up before a shift (restored by
# exif_processor.restore_exif_timestamps, which only accepts these tags).
BACKUP_DATE_FIELDS = (
    'EXIF:DateTimeOriginal',
    'EXIF:CreateDate',
    'EXIF:ModifyDate',
    'QuickTime:CreateDate',
    'QuickTime:ModifyDate',
    'QuickTime:TrackCreateDate',
    'QuickTime:TrackModifyDate',
    'QuickTime:MediaCreateDate',
    'QuickTime:MediaModifyDate',
)


# Files per ExifTool invocation (one backup write, one shift, one check)
SHIFT_CHUNK = 50


class TimeShiftWorker(QThread):
    """Worker thread for applying time shifts to EXIF data"""
    progress_update = pyqtSignal(str)
    progress_value = pyqtSignal(int)
    finished_signal = pyqtSignal(int, list, dict)  # (success_count, errors, exif_backup)
    
    def __init__(self, files, hours, minutes, direction, exiftool_path):
        super().__init__()
        self.files = files
        self.hours = hours
        self.minutes = minutes
        self.direction = direction  # 'forward' or 'backward'
        self.exiftool_path = exiftool_path
    
    def run(self):
        """Apply the time shift to all files, backing up their dates first.

        Works in chunks: one batched metadata read, one journal write for the
        chunk's backups (before anything is modified), one ExifTool process
        shifting the whole chunk, then a second read that confirms per file
        that its dates moved by exactly the requested amount.
        """
        from ..exif_processor import get_exiftool_metadata_batch
        from ..backup_journal import PersistedBackupDict
        from ..exif_service_new import run_exiftool_on_files
        
        success_count = 0
        errors = []
        # The journal-backed dict starts with the backups still pending from
        # earlier shifts: a file shifted twice keeps the backup of its
        # original dates.
        exif_backup = PersistedBackupDict("exif_backup")
        total_files = len(self.files)
        
        # Calculate time delta
        delta_minutes = self.hours * 60 + self.minutes
        if self.direction == 'backward':
            delta_minutes = -delta_minutes
        delta = timedelta(minutes=delta_minutes)

        # ExifTool accepts: -AllDates+=HH:MM:SS or -AllDates-=HH:MM:SS
        hours_shift = abs(delta_minutes) // 60
        minutes_shift = abs(delta_minutes) % 60
        time_shift = f"{hours_shift}:{minutes_shift:02d}:00"
        operator = "+=" if delta_minutes >= 0 else "-="
        options = [f"-AllDates{operator}{time_shift}", "-overwrite_original"]
        
        for start in range(0, total_files, SHIFT_CHUNK):
            if self.isInterruptionRequested():
                errors.append(("", f"Cancelled - {total_files - start} files not processed"))
                break
            chunk = self.files[start:start + SHIFT_CHUNK]
            self.progress_update.emit(f"Processing files {start + 1}-{start + len(chunk)} of {total_files}...")
            self.progress_value.emit(int(start / total_files * 100))

            before = get_exiftool_metadata_batch(chunk, self.exiftool_path)

            # Back up original dates. Without a backup the change could not
            # be undone, so such files are skipped instead.
            new_backups = {}
            eligible = []
            for file_path in chunk:
                meta = before.get(file_path) or {}
                if not meta:
                    errors.append((file_path, "Could not read metadata - skipped (no backup possible)"))
                    continue
                if file_path not in exif_backup:
                    fields = {field: meta[field] for field in BACKUP_DATE_FIELDS if field in meta}
                    if not fields:
                        errors.append((file_path, "No date tags found - skipped"))
                        continue
                    new_backups[file_path] = fields
                eligible.append(file_path)
            created = exif_backup.record_originals(new_backups)
            if not eligible:
                continue

            stderr = ""
            try:
                result = run_exiftool_on_files(
                    self.exiftool_path, options, eligible, timeout=60 + 2 * len(eligible)
                )
                stderr = result.stderr.strip()
            except Exception as e:
                stderr = str(e)

            after = get_exiftool_metadata_batch(eligible, self.exiftool_path)
            failed = []
            for file_path in eligible:
                if _dates_shifted(before.get(file_path) or {}, after.get(file_path) or {}, delta):
                    success_count += 1
                else:
                    failed.append(file_path)
                    errors.append((file_path, _error_for(file_path, stderr) or "Dates were not changed"))
            # Drop the backups created for files that stayed unchanged
            exif_backup.remove_many(f for f in failed if f in created)
        
        self.progress_value.emit(100)
        self.finished_signal.emit(success_count, errors, dict(exif_backup))


def _dates_shifted(before, after, delta):
    """True if at least one backed-up date moved by exactly *delta*."""
    from ..exif_service_new import parse_exif_datetime

    for field in BACKUP_DATE_FIELDS:
        old = parse_exif_datetime(before.get(field))
        new = parse_exif_datetime(after.get(field))
        if old is not None and new is not None and new - old == delta:
            return True
    return False


def _error_for(file_path, stderr):
    """ExifTool's error line for *file_path* ("Error: ... - <path>"), if any."""
    for line in stderr.splitlines():
        if line.endswith(file_path) or line.endswith(os.path.basename(file_path)):
            return line.strip()
    return stderr.splitlines()[0].strip() if stderr else ""


class ExifTimeShiftDialog(QDialog):
    """
    Dialog for shifting EXIF timestamps
    Useful when camera clock was set incorrectly
    """
    
    def __init__(self, parent, files, exiftool_path):
        super().__init__(parent)
        self.files = [f for f in files if is_media_file(f)]
        self.exiftool_path = exiftool_path
        self.worker = None
        self.exif_backup = {}  # Store EXIF backup for undo
        
        self.setWindowTitle("⏰ EXIF Time Shift - Adjust Camera Timestamps")
        self.setModal(True)
        self.resize(700, 600)
        
        self.setup_ui()
        self.load_sample_times()
    
    def get_exif_backup(self):
        """Return the EXIF backup dictionary for undo functionality"""
        return self.exif_backup

    def _worker_running(self):
        return self.worker is not None and self.worker.isRunning()

    def reject(self):
        """Ignore Esc / window close while the shift is running: destroying
        a running QThread aborts the whole application."""
        if self._worker_running():
            return
        super().reject()

    def closeEvent(self, event):
        if self._worker_running():
            event.ignore()
            return
        super().closeEvent(event)
    
    def setup_ui(self):
        """Setup the dialog UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        
        # Title and description
        title = QLabel("⏰ EXIF Time Shift")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)
        
        desc = QLabel(
            "Adjust timestamps for all selected photos.\n"
            "Useful when your camera clock was set incorrectly.\n\n"
            "Example: Photos taken at 12:00, 12:05, 13:02 but EXIF shows 11:00, 11:05, 12:02\n"
            "→ Set time shift: +1 hour 0 minutes"
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("padding: 10px; border: 1px solid palette(mid); border-radius: 5px;")
        layout.addWidget(desc)
        
        # Time shift settings
        settings_group = QGroupBox("⚙️ Time Shift Settings")
        settings_layout = QVBoxLayout(settings_group)
        
        # Direction selection
        direction_layout = QHBoxLayout()
        direction_layout.addWidget(QLabel("Direction:"))
        
        self.direction_group = QButtonGroup(self)
        self.radio_forward = QRadioButton("⏩ Forward (add time)")
        self.radio_backward = QRadioButton("⏪ Backward (subtract time)")
        self.radio_forward.setChecked(True)
        
        self.direction_group.addButton(self.radio_forward, 1)
        self.direction_group.addButton(self.radio_backward, 2)
        
        direction_layout.addWidget(self.radio_forward)
        direction_layout.addWidget(self.radio_backward)
        direction_layout.addStretch()
        settings_layout.addLayout(direction_layout)
        
        # Time amount
        time_layout = QHBoxLayout()
        time_layout.addWidget(QLabel("Time shift:"))
        
        self.hours_spin = QSpinBox()
        self.hours_spin.setRange(0, 23)
        self.hours_spin.setValue(1)
        self.hours_spin.setSuffix(" hours")
        self.hours_spin.valueChanged.connect(self.update_preview)
        
        self.minutes_spin = QSpinBox()
        self.minutes_spin.setRange(0, 59)
        self.minutes_spin.setValue(0)
        self.minutes_spin.setSuffix(" minutes")
        self.minutes_spin.valueChanged.connect(self.update_preview)
        
        time_layout.addWidget(self.hours_spin)
        time_layout.addWidget(self.minutes_spin)
        time_layout.addStretch()
        settings_layout.addLayout(time_layout)
        
        # Connect direction change to preview update
        self.direction_group.buttonClicked.connect(self.update_preview)
        
        layout.addWidget(settings_group)
        
        # Preview table
        preview_group = QGroupBox("📋 Preview Changes (First 10 Files)")
        preview_layout = QVBoxLayout(preview_group)
        
        self.preview_table = QTableWidget()
        self.preview_table.setColumnCount(3)
        self.preview_table.setHorizontalHeaderLabels(["File", "Current Time", "New Time"])
        self.preview_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.preview_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.preview_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.preview_table.setAlternatingRowColors(True)
        
        preview_layout.addWidget(self.preview_table)
        layout.addWidget(preview_group)
        
        # File count info
        self.info_label = QLabel(f"📊 Total files: {len(self.files)}")
        self.info_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(self.info_label)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.apply_button = QPushButton("✅ Apply Time Shift")
        self.apply_button.setStyleSheet("background-color: #28a745; color: white; padding: 10px; font-weight: bold;")
        self.apply_button.clicked.connect(self.apply_time_shift)
        
        self.cancel_button = QPushButton("❌ Cancel")
        self.cancel_button.clicked.connect(self.reject)
        
        button_layout.addWidget(self.apply_button)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)
    
    def load_sample_times(self):
        """Load current timestamps from first 10 files"""
        from ..exif_processor import get_exiftool_metadata_shared
        
        sample_files = self.files[:10]
        
        for file_path in sample_files:
            try:
                # Get current EXIF time
                meta = get_exiftool_metadata_shared(file_path, self.exiftool_path)
                
                current_time = "No EXIF time found"
                if meta:
                    for field in ['EXIF:DateTimeOriginal', 'EXIF:CreateDate', 'QuickTime:CreateDate']:
                        if field in meta:
                            current_time = meta[field]
                            break
                
                # Add to table (will be updated by update_preview)
                row = self.preview_table.rowCount()
                self.preview_table.insertRow(row)
                
                self.preview_table.setItem(row, 0, QTableWidgetItem(os.path.basename(file_path)))
                self.preview_table.setItem(row, 1, QTableWidgetItem(current_time))
                self.preview_table.setItem(row, 2, QTableWidgetItem(""))
                
            except Exception as e:
                log.warning(f"Error loading time for {file_path}: {e}")
        
        # Initial preview update
        self.update_preview()
    
    def update_preview(self):
        """Update the preview with new times"""
        hours = self.hours_spin.value()
        minutes = self.minutes_spin.value()
        is_forward = self.radio_forward.isChecked()
        
        # Calculate delta
        delta = timedelta(hours=hours, minutes=minutes)
        if not is_forward:
            delta = -delta
        
        # Update each row
        for row in range(self.preview_table.rowCount()):
            current_time_str = self.preview_table.item(row, 1).text()
            
            if current_time_str == "No EXIF time found":
                self.preview_table.setItem(row, 2, QTableWidgetItem("No change"))
                continue
            
            try:
                # Parse current time: "2024:01:15 10:30:45"
                current_time_clean = current_time_str.replace(':', '-', 2)
                current_dt = datetime.strptime(current_time_clean, "%Y-%m-%d %H:%M:%S")
                
                # Apply delta
                new_dt = current_dt + delta
                
                # Format back to EXIF format
                new_time_str = new_dt.strftime("%Y:%m:%d %H:%M:%S")
                
                # Update table with color coding
                item = QTableWidgetItem(new_time_str)
                # Light tints with explicit dark text: readable in every theme
                item.setBackground(QColor("#c8f7c5") if is_forward else QColor("#fff3b0"))
                item.setForeground(QColor("#000000"))
                
                self.preview_table.setItem(row, 2, item)
                
            except Exception as e:
                self.preview_table.setItem(row, 2, QTableWidgetItem(f"Error: {e}"))
    
    def apply_time_shift(self):
        """Apply the time shift to all files"""
        # Confirm action
        hours = self.hours_spin.value()
        minutes = self.minutes_spin.value()
        is_forward = self.radio_forward.isChecked()
        
        direction_text = "forward" if is_forward else "backward"
        
        reply = QMessageBox.question(
            self,
            "Confirm Time Shift",
            f"Shift EXIF timestamps {direction_text} by {hours}h {minutes}m for {len(self.files)} files?\n\n"
            "💡 You can undo this change using the 'Restore Original Names' button.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        # Create progress dialog
        self.progress = QProgressDialog("Applying time shift...", "Cancel", 0, 100, self)
        self.progress.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress.setAutoClose(True)
        self.progress.setMinimumDuration(0)
        
        # Start worker thread
        direction = 'forward' if is_forward else 'backward'
        self.worker = TimeShiftWorker(
            self.files,
            hours,
            minutes,
            direction,
            self.exiftool_path
        )
        self.worker.setParent(self)
        
        self.worker.progress_update.connect(self.progress.setLabelText)
        self.worker.progress_value.connect(self.progress.setValue)
        self.worker.finished_signal.connect(self.on_shift_complete)
        # Cancel stops after the file currently being processed
        self.progress.canceled.connect(self.worker.requestInterruption)
        
        self.worker.start()
        
        # Disable buttons during processing
        self.apply_button.setEnabled(False)
        self.cancel_button.setEnabled(False)
    
    def on_shift_complete(self, success_count, errors, exif_backup):
        """Handle completion of time shift operation"""
        self.progress.close()
        # The thread emits this signal just before run() returns
        self.worker.wait()
        
        # Store EXIF backup for undo functionality
        self.exif_backup = exif_backup
        
        # Show results
        if errors:
            error_msg = "Time shift completed with errors:\n\n"
            error_msg += f"✅ Successfully updated: {success_count} files\n"
            error_msg += f"❌ Failed: {len(errors)} files\n\n"
            error_msg += "First 5 errors:\n"
            for file_path, error in errors[:5]:
                error_msg += f"• {os.path.basename(file_path)}: {error}\n"
            
            QMessageBox.warning(self, "Time Shift Complete (with errors)", error_msg)
        else:
            QMessageBox.information(
                self,
                "Time Shift Complete",
                f"✅ Successfully shifted timestamps for {success_count} files!\n\n"
                f"💡 Tip: You can undo this change using 'Restore Original Names' button."
            )
        
        self.accept()
