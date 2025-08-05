#!/usr/bin/env python3
"""
Original FileRenamerApp with modular backend - maintains exact original UI design
"""

import os
import sys
import webbrowser
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QWidget, QLabel, QLineEdit, 
    QPushButton, QListWidget, QFileDialog, QMessageBox, QCheckBox, QDialog, 
    QPlainTextEdit, QHBoxLayout, QStyle, QComboBox, QStatusBar, QListWidgetItem
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QMimeData, QSize, QSettings
from PyQt6.QtGui import QIcon, QFont

# Import our modules
from modules.file_utils import FileConstants, scan_directory, is_media_file
from modules.exif_handler import ExifHandler
from modules.filename_generator import FilenameGenerator  
from modules.rename_engine import RenameWorker
from modules.gui_widgets import ExifToolWarningDialog, InteractivePreviewWidget

class FileRenamerApp(QMainWindow):
    """Original FileRenamer design with modular backend"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("File Renamer")
        
        # Initialize modular components
        self.exif_handler = ExifHandler()
        self.filename_generator = FilenameGenerator()
        
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

        # State variables
        self.files = []
        self.current_order = ["Date", "Prefix", "Additional", "Camera", "Lens"]
        self.camera_models = {}
        self.lens_models = {}
        
        self.setup_ui()
        
        # Check for ExifTool availability and show warning if needed
        self.check_exiftool_warning()
    
    def setup_ui(self):
        """Setup the original UI design"""
        
        # Theme Switch - ganz oben
        theme_row = QHBoxLayout()
        theme_label = QLabel("Theme:")
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["System", "Light", "Dark"])
        self.theme_combo.setCurrentText("System")
        self.theme_combo.currentTextChanged.connect(self.on_theme_changed)
        theme_row.addWidget(theme_label)
        theme_row.addWidget(self.theme_combo)
        theme_row.addStretch()
        self.layout.addLayout(theme_row)

        # File Selection Menu Bar
        file_menu_row = QHBoxLayout()
        file_menu_row.setSpacing(10)
        
        # File selection buttons styled as menu bar
        self.select_files_menu_button = QPushButton("📄 Select Media Files")
        self.select_files_menu_button.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 6px;
                font-weight: bold;
                min-width: 120px;
            }
            QPushButton:hover {
                background-color: #106ebe;
            }
            QPushButton:pressed {
                background-color: #005a9e;
            }
        """)
        self.select_files_menu_button.clicked.connect(self.select_files)
        
        self.select_folder_menu_button = QPushButton("📁 Select Folder")
        self.select_folder_menu_button.setStyleSheet("""
            QPushButton {
                background-color: #107c10;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 6px;
                font-weight: bold;
                min-width: 120px;
            }
            QPushButton:hover {
                background-color: #0e6e0e;
            }
            QPushButton:pressed {
                background-color: #0c5a0c;
            }
        """)
        self.select_folder_menu_button.clicked.connect(self.select_folder)
        
        self.clear_files_menu_button = QPushButton("🗑️ Clear Files")
        self.clear_files_menu_button.setStyleSheet("""
            QPushButton {
                background-color: #d83b01;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 6px;
                font-weight: bold;
                min-width: 120px;
            }
            QPushButton:hover {
                background-color: #c73401;
            }
            QPushButton:pressed {
                background-color: #a72d01;
            }
        """)
        self.clear_files_menu_button.clicked.connect(self.clear_file_list)
        
        file_menu_row.addWidget(self.select_files_menu_button)
        file_menu_row.addWidget(self.select_folder_menu_button)
        file_menu_row.addWidget(self.clear_files_menu_button)
        file_menu_row.addStretch()
        self.layout.addLayout(file_menu_row)

        # Date options
        date_options_row = QHBoxLayout()
        self.checkbox_date = QCheckBox("Include date in filename")
        self.checkbox_date.setChecked(True)  # Default: aktiviert
        self.checkbox_date.stateChanged.connect(self.update_preview)
        
        date_format_label = QLabel("Date Format:")
        self.date_format_combo = QComboBox()
        self.date_format_combo.addItems([
            "YYYY-MM-DD", "YYYY_MM_DD", "DD-MM-YYYY", "DD_MM_YYYY", 
            "YYYYMMDD", "MM-DD-YYYY", "MM_DD_YYYY"
        ])
        self.date_format_combo.setCurrentText("YYYY-MM-DD")  # Default
        self.date_format_combo.currentTextChanged.connect(self.update_preview)
        
        date_options_row.addWidget(self.checkbox_date)
        date_options_row.addWidget(date_format_label)
        date_options_row.addWidget(self.date_format_combo)
        date_options_row.addStretch()
        self.layout.addLayout(date_options_row)

        # Continuous Counter Checkbox (vacation scenario)
        continuous_counter_row = QHBoxLayout()
        self.checkbox_continuous_counter = QCheckBox("Continuous counter for vacation/multi-day shoots")
        self.checkbox_continuous_counter.setChecked(False)  # Default: disabled
        self.checkbox_continuous_counter.setStyleSheet("""
            QCheckBox {
                color: #0066cc;
                font-weight: bold;
            }
            QCheckBox::indicator:checked {
                background-color: #0066cc;
                border: 2px solid #004499;
            }
        """)
        self.checkbox_continuous_counter.setToolTip(
            "Enable for vacation scenarios where you want continuous numbering across dates:\n"
            "• Day 1: 2025-07-20_001, 2025-07-20_002, 2025-07-20_003\n"
            "• Day 2: 2025-07-21_004, 2025-07-21_005, 2025-07-21_006\n"
            "Instead of restarting at 001 each day"
        )
        self.checkbox_continuous_counter.stateChanged.connect(self.on_continuous_counter_changed)
        
        continuous_counter_row.addWidget(self.checkbox_continuous_counter)
        continuous_counter_row.addStretch()
        self.layout.addLayout(continuous_counter_row)

        # Camera Prefix with clickable info icon
        camera_label = QLabel("Camera Prefix:")
        camera_info = QLabel()
        camera_info.setPixmap(self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxInformation).pixmap(16, 16))
        camera_info.setToolTip("Click for detailed info about camera prefix")
        camera_info.setCursor(Qt.CursorShape.PointingHandCursor)
        camera_info.mousePressEvent = lambda event: self.show_camera_prefix_info()
        camera_row = QHBoxLayout()
        camera_row.addWidget(camera_label)
        camera_row.addWidget(camera_info)
        camera_row.addStretch()
        self.layout.addLayout(camera_row)
        self.camera_prefix_entry = QLineEdit()
        self.camera_prefix_entry.setPlaceholderText("e.g. A7R3, D850")
        self.camera_prefix_entry.textChanged.connect(self.validate_and_update_preview)
        self.layout.addWidget(self.camera_prefix_entry)
        
        # Additional with clickable info icon
        additional_label = QLabel("Additional:")
        additional_info = QLabel()
        additional_info.setPixmap(self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxInformation).pixmap(16, 16))
        additional_info.setToolTip("Click for detailed info about additional field")
        additional_info.setCursor(Qt.CursorShape.PointingHandCursor)
        additional_info.mousePressEvent = lambda event: self.show_additional_info()
        additional_row = QHBoxLayout()
        additional_row.addWidget(additional_label)
        additional_row.addWidget(additional_info)
        additional_row.addStretch()
        self.layout.addLayout(additional_row)
        self.additional_entry = QLineEdit()
        self.additional_entry.setPlaceholderText("e.g. vacation, wedding")
        self.additional_entry.textChanged.connect(self.validate_and_update_preview)
        self.layout.addWidget(self.additional_entry)

        # Devider selection with clickable info icon
        devider_row = QHBoxLayout()
        devider_label = QLabel("Devider:")
        devider_info = QLabel()
        devider_info.setPixmap(self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxInformation).pixmap(16, 16))
        devider_info.setToolTip("Click for detailed info about separators")
        devider_info.setCursor(Qt.CursorShape.PointingHandCursor)
        devider_info.mousePressEvent = lambda event: self.show_devider_info()
        devider_row.addWidget(devider_label)
        devider_row.addWidget(devider_info)
        devider_row.addStretch()
        self.layout.addLayout(devider_row)
        self.devider_combo = QComboBox()
        self.devider_combo.addItems(["None", "_", "-"])
        self.devider_combo.setCurrentText("-")  # Set default to dash for better readability
        self.layout.addWidget(self.devider_combo)
        self.devider_combo.currentIndexChanged.connect(self.update_preview)
        self.devider_combo.currentIndexChanged.connect(self.on_devider_changed)

        # Interactive Preview section with clickable info icon
        preview_row = QHBoxLayout()
        preview_label = QLabel("Interactive Preview:")
        preview_info = QLabel()
        preview_info.setPixmap(self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxInformation).pixmap(16, 16))
        preview_info.setToolTip("Click for detailed info about interactive preview")
        preview_info.setCursor(Qt.CursorShape.PointingHandCursor)
        preview_info.mousePressEvent = lambda event: self.show_preview_info()
        preview_row.addWidget(preview_label)
        preview_row.addWidget(preview_info)
        preview_row.addStretch()
        self.layout.addLayout(preview_row)
        
        self.interactive_preview = InteractivePreviewWidget()
        self.interactive_preview.order_changed.connect(self.on_preview_order_changed)
        self.layout.addWidget(self.interactive_preview)

        # Camera checkbox with model display
        camera_checkbox_layout = QHBoxLayout()
        self.checkbox_camera = QCheckBox("Include camera model in filename")
        self.camera_model_label = QLabel("(detecting...)")
        self.camera_model_label.setStyleSheet("color: gray; font-style: italic;")
        camera_checkbox_layout.addWidget(self.checkbox_camera)
        camera_checkbox_layout.addWidget(self.camera_model_label)
        camera_checkbox_layout.addStretch()
        self.layout.addLayout(camera_checkbox_layout)
        self.checkbox_camera.stateChanged.connect(self.update_preview)
        
        # Lens checkbox with model display
        lens_checkbox_layout = QHBoxLayout()
        self.checkbox_lens = QCheckBox("Include lens in filename")
        self.lens_model_label = QLabel("(detecting...)")
        self.lens_model_label.setStyleSheet("color: gray; font-style: italic;")
        lens_checkbox_layout.addWidget(self.checkbox_lens)
        lens_checkbox_layout.addWidget(self.lens_model_label)
        lens_checkbox_layout.addStretch()
        self.layout.addLayout(lens_checkbox_layout)
        self.checkbox_lens.stateChanged.connect(self.update_preview)

        # Drag & Drop File List with dashed border and info text
        self.file_list = QListWidget()
        self.file_list.setStyleSheet("""
            QListWidget {
                border: 2px dashed #cccccc;
                border-radius: 8px;
                background-color: #fafafa;
                padding: 20px;
                min-height: 120px;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 10pt;
            }
            QListWidget::item {
                border: none;
                padding: 4px;
                border-radius: 4px;
                margin: 1px;
            }
            QListWidget::item:selected {
                background-color: #e3f2fd;
                color: #1976d2;
            }
            QListWidget::item:hover {
                background-color: #f5f5f5;
            }
        """)
        self.file_list.setAcceptDrops(True)
        self.file_list.setDragDropMode(QListWidget.DragDropMode.DropOnly)
        self.layout.addWidget(self.file_list)
        
        # Status bar and rename button
        bottom_layout = QHBoxLayout()
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: gray; font-style: italic;")
        self.rename_button = QPushButton("Start Renaming")
        self.rename_button.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 11pt;
            }
            QPushButton:hover {
                background-color: #218838;
            }
            QPushButton:pressed {
                background-color: #1e7e34;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        self.rename_button.clicked.connect(self.start_renaming)
        self.rename_button.setEnabled(False)
        
        bottom_layout.addWidget(self.status_label)
        bottom_layout.addStretch()
        bottom_layout.addWidget(self.rename_button)
        self.layout.addLayout(bottom_layout)
        
        # Connect drag and drop
        self.file_list.dragEnterEvent = self.dragEnterEvent
        self.file_list.dropEvent = self.dropEvent
    
    def check_exiftool_warning(self):
        """Check if ExifTool warning should be shown"""
        if not self.exif_handler.is_exiftool_available():
            settings = QSettings("FileRenamer", "Settings")
            show_warning = settings.value("show_exiftool_warning", True, type=bool)
            
            if show_warning:
                dialog = ExifToolWarningDialog(self, self.exif_handler.current_method)
                dialog.exec()
                
                if not dialog.should_show_again():
                    settings.setValue("show_exiftool_warning", False)
    
    # Event handlers - simplified versions that use modular backend
    def select_files(self):
        """Select individual media files"""
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select Media Files", "", 
            "Media Files (*.jpg *.jpeg *.png *.cr2 *.nef *.arw *.mp4 *.mov);;All Files (*)"
        )
        if files:
            # Filter to only media files
            media_files = [f for f in files if is_media_file(f)]
            self.files.extend(media_files)
            self.update_file_list()
            self.extract_camera_info()
    
    def select_folder(self):
        """Select folder and scan for media files"""
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder:
            media_files = scan_directory(folder, include_subdirs=True)
            self.files.extend(media_files)
            self.update_file_list()
            self.extract_camera_info()
    
    def clear_file_list(self):
        """Clear the file list"""
        self.files = []
        self.file_list.clear()
        self.status_label.setText("Ready")
        self.rename_button.setEnabled(False)
        self.camera_model_label.setText("(detecting...)")
        self.lens_model_label.setText("(detecting...)")
    
    def update_file_list(self):
        """Update the file list display"""
        self.file_list.clear()
        for file_path in self.files:
            self.file_list.addItem(os.path.basename(file_path))
        
        self.status_label.setText(f"{len(self.files)} files loaded")
        self.rename_button.setEnabled(len(self.files) > 0)
        self.update_preview()
    
    def extract_camera_info(self):
        """Extract camera and lens info from the first few files"""
        if not self.files:
            return
        
        # Extract from first file (representative)
        first_file = self.files[0]
        exif_data = self.exif_handler.extract_exif(first_file)
        
        camera_model = exif_data.get('camera_model', '')
        lens_model = exif_data.get('lens_model', '')
        
        if camera_model:
            self.camera_model_label.setText(f"({camera_model})")
            self.camera_model_label.setStyleSheet("color: green; font-style: italic;")
        else:
            self.camera_model_label.setText("(not detected)")
            self.camera_model_label.setStyleSheet("color: orange; font-style: italic;")
        
        if lens_model:
            self.lens_model_label.setText(f"({lens_model})")
            self.lens_model_label.setStyleSheet("color: green; font-style: italic;")
        else:
            self.lens_model_label.setText("(not detected)")
            self.lens_model_label.setStyleSheet("color: orange; font-style: italic;")
    
    def update_preview(self):
        """Update the interactive preview using modular backend"""
        if not hasattr(self, 'interactive_preview'):
            return
        
        # Get selected components based on checkboxes
        components = []
        if self.checkbox_date.isChecked():
            components.append("Date")
        if self.camera_prefix_entry.text().strip():
            components.append("Prefix")
        if self.additional_entry.text().strip():
            components.append("Additional")
        if self.checkbox_camera.isChecked():
            components.append("Camera")
        if self.checkbox_lens.isChecked():
            components.append("Lens")
        
        # Update interactive preview
        separator = self.devider_combo.currentText()
        if separator == "None":
            separator = ""
        
        self.interactive_preview.set_separator(separator)
        self.interactive_preview.set_components(components, "001")
    
    def start_renaming(self):
        """Start the renaming process using modular backend"""
        if not self.files:
            QMessageBox.warning(self, "Warning", "No files selected.")
            return
        
        # Confirm with user
        reply = QMessageBox.question(
            self, "Confirm Rename", 
            f"Are you sure you want to rename {len(self.files)} files?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        try:
            # Create configuration
            config = {
                'components': {
                    'date': self.checkbox_date.isChecked(),
                    'camera': self.checkbox_camera.isChecked(),
                    'lens': self.checkbox_lens.isChecked(),
                    'custom': self.additional_entry.text().strip()
                },
                'component_order': self.current_order,
                'date_format': self.date_format_combo.currentText(),
                'separator': self.devider_combo.currentText() if self.devider_combo.currentText() != "None" else "",
                'use_numbering': True,
                'start_number': 1,
                'camera_prefix': self.camera_prefix_entry.text().strip(),
                'additional': self.additional_entry.text().strip()
            }
            
            # Use modular rename engine
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
            self.status_label.setText("Renaming files...")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to start renaming: {str(e)}")
    
    # Event handler stubs - implement basic functionality
    def on_theme_changed(self, theme): pass
    def on_continuous_counter_changed(self): pass
    def on_devider_changed(self): pass
    def on_preview_order_changed(self, new_order): 
        self.current_order = new_order
        self.update_preview()
    def validate_and_update_preview(self): self.update_preview()
    def show_camera_prefix_info(self): pass
    def show_additional_info(self): pass
    def show_devider_info(self): pass
    def show_preview_info(self): pass
    
    def on_rename_progress(self, current, total, message):
        self.status_label.setText(f"Renaming: {current}/{total}")
    
    def on_rename_finished(self, operations):
        self.status_label.setText(f"Renamed {len(operations)} files successfully!")
        self.rename_button.setEnabled(True)
        QMessageBox.information(self, "Success", f"Successfully renamed {len(operations)} files!")
    
    def on_rename_error(self, error_message):
        self.status_label.setText("Rename failed!")
        self.rename_button.setEnabled(True)
        QMessageBox.critical(self, "Error", f"Rename failed:\n{error_message}")
    
    # Drag and drop support
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()
    
    def dropEvent(self, event):
        files = [u.toLocalFile() for u in event.mimeData().urls()]
        media_files = [f for f in files if os.path.isfile(f) and is_media_file(f)]
        
        if media_files:
            self.files.extend(media_files)
            self.update_file_list()
            self.extract_camera_info()

def main():
    """Main entry point"""
    app = QApplication(sys.argv)
    app.setApplicationName("File Renamer")
    
    # Set application icon if available
    icon_path = os.path.join(os.path.dirname(__file__), "icon.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    
    # Create and show main window
    window = FileRenamerApp()
    window.show()
    
    # Run application
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
