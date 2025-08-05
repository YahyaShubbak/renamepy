#!/usr/bin/env python3
"""
Main application class for RenameFiles - integrates all modules.
"""

import sys
import os
import logging
from pathlib import Path
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QPushButton, QLabel, QComboBox, QLineEdit, QProgressBar, QTextEdit,
    QGroupBox, QCheckBox, QFileDialog, QMessageBox, QListWidget,
    QSplitter, QFrame, QGridLayout, QScrollArea, QSpinBox, QDialog
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QSettings
from PyQt6.QtGui import QFont, QIcon, QPixmap

# Import our modules
from modules.file_utils import (
    FileConstants, scan_directory, is_media_file, sanitize_filename,
    get_safe_filename, validate_path
)
from modules.exif_handler import ExifHandler
from modules.filename_generator import FilenameGenerator
from modules.rename_engine import RenameWorker
from modules.gui_widgets import ExifToolWarningDialog, InteractivePreviewWidget

class RenameFilesApp(QMainWindow):
    """Main application window for RenameFiles"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("RenameFiles - EXIF-Based File Renaming Tool")
        self.setGeometry(100, 100, 1200, 800)
        
        # Initialize core components
        self.exif_handler = ExifHandler()
        self.filename_generator = FilenameGenerator()
        self.settings = QSettings("RenameFiles", "FileRenamer")
        
        # State variables
        self.files = []
        self.selected_folder = ""
        self.rename_worker = None
        self.last_operation = None
        
        # Setup logging
        self.setup_logging()
        
        # Setup UI
        self.setup_ui()
        self.setup_connections()
        self.load_settings()
        
        # Check ExifTool availability
        self.check_exiftool_availability()
    
    def setup_logging(self):
        """Setup logging configuration"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('renamepy.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def setup_ui(self):
        """Setup the main user interface"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QVBoxLayout(central_widget)
        
        # Top section - Folder selection
        folder_group = QGroupBox("Folder Selection")
        folder_layout = QHBoxLayout(folder_group)
        
        self.folder_label = QLabel("No folder selected")
        self.folder_label.setStyleSheet("padding: 5px; border: 1px solid #ccc; background: #f9f9f9;")
        folder_layout.addWidget(self.folder_label)
        
        self.browse_button = QPushButton("Browse...")
        self.browse_button.clicked.connect(self.browse_folder)
        folder_layout.addWidget(self.browse_button)
        
        self.include_subdirs_checkbox = QCheckBox("Include subdirectories")
        folder_layout.addWidget(self.include_subdirs_checkbox)
        
        main_layout.addWidget(folder_group)
        
        # Middle section - Splitter with options and preview
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left side - Options
        options_widget = self.create_options_widget()
        splitter.addWidget(options_widget)
        
        # Right side - File list and preview
        files_widget = self.create_files_widget()
        splitter.addWidget(files_widget)
        
        splitter.setSizes([400, 800])
        main_layout.addWidget(splitter)
        
        # Bottom section - Progress and actions
        progress_group = QGroupBox("Progress")
        progress_layout = QVBoxLayout(progress_group)
        
        self.progress_bar = QProgressBar()
        progress_layout.addWidget(self.progress_bar)
        
        self.status_label = QLabel("Ready")
        progress_layout.addWidget(self.status_label)
        
        # Action buttons
        button_layout = QHBoxLayout()
        
        self.preview_button = QPushButton("Generate Preview")
        self.preview_button.clicked.connect(self.generate_preview)
        button_layout.addWidget(self.preview_button)
        
        self.rename_button = QPushButton("Start Renaming")
        self.rename_button.clicked.connect(self.start_renaming)
        self.rename_button.setEnabled(False)
        self.rename_button.setStyleSheet("""
            QPushButton:enabled {
                background-color: #28a745;
                color: white;
                font-weight: bold;
                padding: 8px;
            }
            QPushButton:enabled:hover {
                background-color: #218838;
            }
        """)
        button_layout.addWidget(self.rename_button)
        
        self.undo_button = QPushButton("Undo Last Operation")
        self.undo_button.clicked.connect(self.undo_last_operation)
        self.undo_button.setEnabled(False)
        button_layout.addWidget(self.undo_button)
        
        progress_layout.addLayout(button_layout)
        main_layout.addWidget(progress_group)
        
        # Log output
        log_group = QGroupBox("Log Output")
        log_layout = QVBoxLayout(log_group)
        
        self.log_text = QTextEdit()
        self.log_text.setMaximumHeight(120)
        self.log_text.setFont(QFont("Consolas", 9))
        log_layout.addWidget(self.log_text)
        
        main_layout.addWidget(log_group)
    
    def create_options_widget(self):
        """Create the options panel"""
        scroll_area = QScrollArea()
        scroll_widget = QWidget()
        layout = QVBoxLayout(scroll_widget)
        
        # Component selection
        components_group = QGroupBox("Components to Include")
        components_layout = QGridLayout(components_group)
        
        self.components_checkboxes = {}
        available_components = [
            ("date", "Date (EXIF/File)"),
            ("camera", "Camera Model"),
            ("lens", "Lens Model"),
            ("custom", "Custom Text"),
            ("original", "Original Filename"),
            ("folder", "Parent Folder Name")
        ]
        
        for i, (key, label) in enumerate(available_components):
            checkbox = QCheckBox(label)
            checkbox.stateChanged.connect(self.update_preview)
            self.components_checkboxes[key] = checkbox
            components_layout.addWidget(checkbox, i // 2, i % 2)
        
        layout.addWidget(components_group)
        
        # Date format options
        date_group = QGroupBox("Date Format")
        date_layout = QVBoxLayout(date_group)
        
        self.date_format_combo = QComboBox()
        self.date_format_combo.addItems([
            "YYYY-MM-DD",
            "YYYY-MM-DD_HH-MM-SS",
            "YYYYMMDD",
            "YYYYMMDD_HHMMSS",
            "DD-MM-YYYY",
            "MM-DD-YYYY"
        ])
        self.date_format_combo.currentTextChanged.connect(self.update_preview)
        date_layout.addWidget(self.date_format_combo)
        
        layout.addWidget(date_group)
        
        # Custom text
        custom_group = QGroupBox("Custom Text")
        custom_layout = QVBoxLayout(custom_group)
        
        self.custom_text_input = QLineEdit()
        self.custom_text_input.setPlaceholderText("Enter custom text...")
        self.custom_text_input.textChanged.connect(self.update_preview)
        custom_layout.addWidget(self.custom_text_input)
        
        layout.addWidget(custom_group)
        
        # Separator
        separator_group = QGroupBox("Component Separator")
        separator_layout = QVBoxLayout(separator_group)
        
        self.separator_combo = QComboBox()
        self.separator_combo.addItems(["_", "-", " ", ".", "None"])
        self.separator_combo.currentTextChanged.connect(self.update_preview)
        separator_layout.addWidget(self.separator_combo)
        
        layout.addWidget(separator_group)
        
        # Numbering
        numbering_group = QGroupBox("Sequential Numbering")
        numbering_layout = QVBoxLayout(numbering_group)
        
        self.numbering_checkbox = QCheckBox("Add sequential numbers")
        self.numbering_checkbox.setChecked(True)
        self.numbering_checkbox.stateChanged.connect(self.update_preview)
        numbering_layout.addWidget(self.numbering_checkbox)
        
        number_layout = QHBoxLayout()
        number_layout.addWidget(QLabel("Start from:"))
        self.start_number_input = QSpinBox()
        self.start_number_input.setMinimum(1)
        self.start_number_input.setMaximum(9999)
        self.start_number_input.setValue(1)
        self.start_number_input.valueChanged.connect(self.update_preview)
        number_layout.addWidget(self.start_number_input)
        numbering_layout.addLayout(number_layout)
        
        layout.addWidget(numbering_group)
        
        # Interactive preview
        preview_group = QGroupBox("Component Order (Drag to Reorder)")
        preview_layout = QVBoxLayout(preview_group)
        
        self.interactive_preview = InteractivePreviewWidget()
        self.interactive_preview.order_changed.connect(self.on_order_changed)
        preview_layout.addWidget(self.interactive_preview)
        
        layout.addWidget(preview_group)
        
        # Add stretch to push everything to the top
        layout.addStretch()
        
        scroll_area.setWidget(scroll_widget)
        scroll_area.setWidgetResizable(True)
        scroll_area.setMinimumWidth(380)
        scroll_area.setMaximumWidth(420)
        
        return scroll_area
    
    def create_files_widget(self):
        """Create the files list and preview widget"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # File list
        files_group = QGroupBox("Files Found")
        files_layout = QVBoxLayout(files_group)
        
        self.files_list = QListWidget()
        self.files_list.setFont(QFont("Consolas", 9))
        files_layout.addWidget(self.files_list)
        
        layout.addWidget(files_group)
        
        # Preview
        preview_group = QGroupBox("Rename Preview")
        preview_layout = QVBoxLayout(preview_group)
        
        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setFont(QFont("Consolas", 9))
        self.preview_text.setMaximumHeight(200)
        preview_layout.addWidget(self.preview_text)
        
        layout.addWidget(preview_group)
        
        return widget
    
    def setup_connections(self):
        """Setup signal connections"""
        self.include_subdirs_checkbox.stateChanged.connect(self.scan_current_folder)
        
        # Connect all component checkboxes
        for checkbox in self.components_checkboxes.values():
            checkbox.stateChanged.connect(self.update_preview)
    
    def load_settings(self):
        """Load settings from QSettings"""
        # Load component selections
        for key, checkbox in self.components_checkboxes.items():
            value = self.settings.value(f"component_{key}", False, type=bool)
            checkbox.setChecked(value)
        
        # Load other settings
        date_format = self.settings.value("date_format", "YYYY-MM-DD", type=str)
        separator = self.settings.value("separator", "_", type=str)
        custom_text = self.settings.value("custom_text", "", type=str)
        include_subdirs = self.settings.value("include_subdirs", False, type=bool)
        numbering = self.settings.value("numbering", True, type=bool)
        start_number = self.settings.value("start_number", 1, type=int)
        
        # Set UI values
        index = self.date_format_combo.findText(date_format)
        if index >= 0:
            self.date_format_combo.setCurrentIndex(index)
        
        index = self.separator_combo.findText(separator)
        if index >= 0:
            self.separator_combo.setCurrentIndex(index)
        
        self.custom_text_input.setText(custom_text)
        self.include_subdirs_checkbox.setChecked(include_subdirs)
        self.numbering_checkbox.setChecked(numbering)
        self.start_number_input.setValue(start_number)
    
    def save_settings(self):
        """Save settings to QSettings"""
        # Save component selections
        for key, checkbox in self.components_checkboxes.items():
            self.settings.setValue(f"component_{key}", checkbox.isChecked())
        
        # Save other settings
        self.settings.setValue("date_format", self.date_format_combo.currentText())
        self.settings.setValue("separator", self.separator_combo.currentText())
        self.settings.setValue("custom_text", self.custom_text_input.text())
        self.settings.setValue("include_subdirs", self.include_subdirs_checkbox.isChecked())
        self.settings.setValue("numbering", self.numbering_checkbox.isChecked())
        self.settings.setValue("start_number", self.start_number_input.value())
    
    def check_exiftool_availability(self):
        """Check if ExifTool is available and show warning if not"""
        if not self.exif_handler.is_exiftool_available():
            # Check if user has disabled this warning
            show_warning = self.settings.value("show_exiftool_warning", True, type=bool)
            
            if show_warning:
                dialog = ExifToolWarningDialog(self, self.exif_handler.current_method)
                dialog.exec()
                
                if not dialog.should_show_again():
                    self.settings.setValue("show_exiftool_warning", False)
    
    def browse_folder(self):
        """Open folder browser dialog"""
        folder = QFileDialog.getExistingDirectory(
            self, "Select Folder", self.selected_folder
        )
        
        if folder:
            self.selected_folder = folder
            self.folder_label.setText(folder)
            self.scan_current_folder()
    
    def scan_current_folder(self):
        """Scan the current folder for media files"""
        if not self.selected_folder:
            return
        
        try:
            self.status_label.setText("Scanning folder...")
            self.progress_bar.setRange(0, 0)  # Indeterminate progress
            
            include_subdirs = self.include_subdirs_checkbox.isChecked()
            self.files = scan_directory(self.selected_folder, include_subdirs)
            
            # Update file list
            self.files_list.clear()
            for file_path in self.files:
                self.files_list.addItem(os.path.basename(file_path))
            
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(100)
            self.status_label.setText(f"Found {len(self.files)} files")
            
            self.log_message(f"Scanned folder: {self.selected_folder}")
            self.log_message(f"Found {len(self.files)} media files")
            
            # Enable preview button if files found
            self.preview_button.setEnabled(len(self.files) > 0)
            
        except Exception as e:
            self.log_message(f"Error scanning folder: {str(e)}", "ERROR")
            self.status_label.setText("Error scanning folder")
    
    def update_preview(self):
        """Update the interactive preview and main preview"""
        if not hasattr(self, 'interactive_preview'):
            return
        
        # Get selected components
        selected_components = []
        for key, checkbox in self.components_checkboxes.items():
            if checkbox.isChecked():
                if key == "custom" and self.custom_text_input.text():
                    selected_components.append(self.custom_text_input.text())
                else:
                    selected_components.append(key.upper())
        
        # Update interactive preview
        separator = self.separator_combo.currentText()
        if separator == "None":
            separator = ""
        
        start_num = self.start_number_input.value()
        sequential_num = f"{start_num:03d}" if self.numbering_checkbox.isChecked() else ""
        
        self.interactive_preview.set_separator(separator)
        self.interactive_preview.set_components(selected_components, sequential_num)
    
    def on_order_changed(self, new_order):
        """Handle when component order is changed in interactive preview"""
        self.log_message(f"Component order changed: {' -> '.join(new_order)}")
        # Trigger preview generation if files are loaded
        if self.files:
            QTimer.singleShot(100, self.generate_preview)  # Slight delay to avoid rapid updates
    
    def generate_preview(self):
        """Generate rename preview for all files"""
        if not self.files:
            QMessageBox.warning(self, "Warning", "No files loaded. Please select a folder first.")
            return
        
        try:
            self.status_label.setText("Generating preview...")
            self.progress_bar.setRange(0, len(self.files))
            
            # Get configuration
            config = self.get_rename_config()
            
            # Clear preview
            self.preview_text.clear()
            
            preview_lines = []
            for i, file_path in enumerate(self.files):
                # Update progress
                self.progress_bar.setValue(i + 1)
                QApplication.processEvents()
                
                # Generate new filename
                old_name = os.path.basename(file_path)
                
                # Get EXIF data
                exif_data = self.exif_handler.extract_exif(file_path)
                
                # Generate filename
                new_name = self.filename_generator.generate_filename(
                    file_path, config, exif_data, i + 1
                )
                
                # Add to preview
                preview_lines.append(f"{old_name} → {new_name}")
            
            # Display preview
            self.preview_text.setPlainText('\n'.join(preview_lines))
            
            # Enable rename button
            self.rename_button.setEnabled(True)
            
            self.status_label.setText(f"Preview generated for {len(self.files)} files")
            self.log_message(f"Generated preview for {len(self.files)} files")
            
        except Exception as e:
            self.log_message(f"Error generating preview: {str(e)}", "ERROR")
            self.status_label.setText("Error generating preview")
    
    def get_rename_config(self):
        """Get current rename configuration"""
        # Get component order from interactive preview
        component_order = self.interactive_preview.get_component_order()
        
        # Create component mapping
        component_mapping = {}
        for key, checkbox in self.components_checkboxes.items():
            if checkbox.isChecked():
                if key == "custom":
                    component_mapping["custom"] = self.custom_text_input.text()
                else:
                    component_mapping[key] = True
        
        config = {
            'components': component_mapping,
            'component_order': component_order,
            'date_format': self.date_format_combo.currentText(),
            'separator': self.separator_combo.currentText() if self.separator_combo.currentText() != "None" else "",
            'start_number': self.start_number_input.value(),
            'use_numbering': self.numbering_checkbox.isChecked(),
            'custom_text': self.custom_text_input.text()
        }
        
        return config
    
    def start_renaming(self):
        """Start the renaming process"""
        if not self.files:
            QMessageBox.warning(self, "Warning", "No files to rename.")
            return
        
        # Confirm with user
        reply = QMessageBox.question(
            self, "Confirm Rename",
            f"Are you sure you want to rename {len(self.files)} files?\n\n"
            "This action can be undone, but it's recommended to backup your files first.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        try:
            # Get configuration
            config = self.get_rename_config()
            
            # Create and start worker thread
            self.rename_worker = RenameWorker(
                self.files, config, self.exif_handler, self.filename_generator
            )
            
            # Connect signals
            self.rename_worker.progress.connect(self.on_rename_progress)
            self.rename_worker.finished.connect(self.on_rename_finished)
            self.rename_worker.error.connect(self.on_rename_error)
            
            # Start worker
            self.rename_worker.start()
            
            # Update UI
            self.rename_button.setEnabled(False)
            self.preview_button.setEnabled(False)
            self.status_label.setText("Renaming files...")
            
            self.log_message("Started renaming process")
            
        except Exception as e:
            self.log_message(f"Error starting rename: {str(e)}", "ERROR")
    
    def on_rename_progress(self, current, total, message):
        """Handle rename progress updates"""
        self.progress_bar.setRange(0, total)
        self.progress_bar.setValue(current)
        self.status_label.setText(f"Renaming: {current}/{total} - {message}")
        self.log_message(message)
    
    def on_rename_finished(self, operations):
        """Handle rename completion"""
        self.last_operation = operations
        
        self.progress_bar.setValue(self.progress_bar.maximum())
        self.status_label.setText(f"Renamed {len(operations)} files successfully!")
        
        # Re-enable buttons
        self.rename_button.setEnabled(True)
        self.preview_button.setEnabled(True)
        self.undo_button.setEnabled(True)
        
        # Save settings
        self.save_settings()
        
        # Rescan folder to update file list
        self.scan_current_folder()
        
        self.log_message(f"Rename operation completed: {len(operations)} files")
        
        QMessageBox.information(
            self, "Success",
            f"Successfully renamed {len(operations)} files!"
        )
    
    def on_rename_error(self, error_message):
        """Handle rename errors"""
        self.status_label.setText("Rename failed!")
        self.rename_button.setEnabled(True)
        self.preview_button.setEnabled(True)
        
        self.log_message(f"Rename error: {error_message}", "ERROR")
        
        QMessageBox.critical(self, "Error", f"Rename failed:\n{error_message}")
    
    def undo_last_operation(self):
        """Undo the last rename operation"""
        if not self.last_operation:
            QMessageBox.warning(self, "Warning", "No operation to undo.")
            return
        
        # Confirm with user
        reply = QMessageBox.question(
            self, "Confirm Undo",
            f"Are you sure you want to undo the last operation?\n"
            f"This will rename {len(self.last_operation)} files back to their original names.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        try:
            self.status_label.setText("Undoing operation...")
            self.progress_bar.setRange(0, len(self.last_operation))
            
            failed_operations = []
            
            for i, (old_path, new_path) in enumerate(self.last_operation):
                self.progress_bar.setValue(i + 1)
                QApplication.processEvents()
                
                try:
                    if os.path.exists(new_path):
                        os.rename(new_path, old_path)
                        self.log_message(f"Reverted: {os.path.basename(new_path)} → {os.path.basename(old_path)}")
                    else:
                        failed_operations.append((old_path, new_path))
                        self.log_message(f"Could not revert: {new_path} (file not found)", "WARNING")
                        
                except Exception as e:
                    failed_operations.append((old_path, new_path))
                    self.log_message(f"Failed to revert {new_path}: {str(e)}", "ERROR")
            
            # Clear last operation
            self.last_operation = None
            self.undo_button.setEnabled(False)
            
            # Rescan folder
            self.scan_current_folder()
            
            success_count = len(self.last_operation or []) - len(failed_operations)
            
            if failed_operations:
                QMessageBox.warning(
                    self, "Partial Success",
                    f"Reverted {success_count} files successfully.\n"
                    f"{len(failed_operations)} files could not be reverted."
                )
            else:
                QMessageBox.information(
                    self, "Success",
                    f"Successfully reverted {success_count} files!"
                )
            
            self.status_label.setText("Undo completed")
            
        except Exception as e:
            self.log_message(f"Error during undo: {str(e)}", "ERROR")
            QMessageBox.critical(self, "Error", f"Undo failed:\n{str(e)}")
    
    def log_message(self, message, level="INFO"):
        """Add a message to the log"""
        import datetime
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {level}: {message}"
        
        self.log_text.append(formatted_message)
        
        # Also log to file
        if level == "ERROR":
            self.logger.error(message)
        elif level == "WARNING":
            self.logger.warning(message)
        else:
            self.logger.info(message)
    
    def closeEvent(self, event):
        """Handle application close event"""
        # Save settings
        self.save_settings()
        
        # Stop any running worker
        if self.rename_worker and self.rename_worker.isRunning():
            self.rename_worker.terminate()
            self.rename_worker.wait()
        
        # Close EXIF handler
        self.exif_handler.close()
        
        event.accept()

def main():
    """Main entry point"""
    app = QApplication(sys.argv)
    app.setApplicationName("RenameFiles")
    app.setApplicationVersion("2.0")
    
    # Set application icon if available
    icon_path = os.path.join(os.path.dirname(__file__), "icon.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    
    # Create and show main window
    window = RenameFilesApp()
    window.show()
    
    # Run application
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
