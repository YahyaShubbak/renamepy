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
from PyQt6.QtGui import QFont
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
        """Apply time shift to all files and create EXIF backup"""
        from ..exif_processor import get_exiftool_metadata_shared
        from ..backup_journal import PersistedBackupDict
        from ..exif_service_new import run_exiftool_on_file
        
        success_count = 0
        errors = []
        # PersistedBackupDict writes each file's backup to the on-disk undo
        # journal immediately - before the -overwrite_original ExifTool call
        # below runs for that file - so a crash mid-batch can't lose backups
        # for files already processed. It starts with the backups still
        # pending from earlier shifts: a file shifted twice keeps the backup
        # of its original dates.
        exif_backup = PersistedBackupDict("exif_backup")
        total_files = len(self.files)
        
        # Calculate time delta
        delta_minutes = self.hours * 60 + self.minutes
        if self.direction == 'backward':
            delta_minutes = -delta_minutes

        # ExifTool accepts: -AllDates+=HH:MM:SS or -AllDates-=HH:MM:SS
        hours_shift = abs(delta_minutes) // 60
        minutes_shift = abs(delta_minutes) % 60
        time_shift = f"{hours_shift}:{minutes_shift:02d}:00"
        operator = "+=" if delta_minutes >= 0 else "-="
        
        for idx, file_path in enumerate(self.files):
            if self.isInterruptionRequested():
                errors.append((file_path, f"Cancelled - {total_files - idx} files not processed"))
                break
            backup_created = False
            try:
                self.progress_update.emit(f"Processing {os.path.basename(file_path)}...")
                self.progress_value.emit(int((idx / total_files) * 100))
                
                # Backup original EXIF timestamps BEFORE modifying. Without a
                # backup the change could not be undone, so the file is
                # skipped instead.
                if file_path not in exif_backup:
                    exif_data = get_exiftool_metadata_shared(file_path, self.exiftool_path)
                    if not exif_data:
                        errors.append((file_path, "Could not read metadata - skipped (no backup possible)"))
                        continue
                    backup_fields = {
                        field: exif_data[field] for field in BACKUP_DATE_FIELDS if field in exif_data
                    }
                    if not backup_fields:
                        errors.append((file_path, "No date tags found - skipped"))
                        continue
                    exif_backup[file_path] = backup_fields
                    backup_created = True
                
                result = run_exiftool_on_file(
                    self.exiftool_path,
                    [f"-AllDates{operator}{time_shift}", "-overwrite_original"],
                    file_path,
                    timeout=60,
                )
                
                if result.returncode == 0:
                    success_count += 1
                else:
                    errors.append((file_path, result.stderr.strip() or "ExifTool error"))
                    # Remove the backup created for this (unchanged) file
                    if backup_created:
                        del exif_backup[file_path]
                    
            except Exception as e:
                errors.append((file_path, str(e)))
                # Remove the backup created for this (unchanged) file
                if backup_created and file_path in exif_backup:
                    del exif_backup[file_path]
        
        self.progress_value.emit(100)
        self.finished_signal.emit(success_count, errors, dict(exif_backup))


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
        desc.setStyleSheet("color: #555; padding: 10px; background-color: #f0f0f0; border-radius: 5px;")
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
        self.info_label.setStyleSheet("color: #555; font-weight: bold;")
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
                if is_forward:
                    item.setBackground(Qt.GlobalColor.green)
                else:
                    item.setBackground(Qt.GlobalColor.yellow)
                
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
            error_msg = f"Time shift completed with errors:\n\n"
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
