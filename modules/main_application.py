#!/usr/bin/env python3
"""
Complete original UI implementation with all features from RenameFiles.py
"""

import os
import sys
from pathlib import Path

# Add the parent directory to the Python path to allow module imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QPushButton, QLineEdit, QCheckBox, QComboBox, QListWidget,
    QFileDialog, QStatusBar, QListWidgetItem, QMessageBox, QDialog,
    QStyle, QPlainTextEdit, QScrollArea
)
from PyQt6.QtCore import Qt, QSettings, QThread, pyqtSignal, QMimeData, QPoint
from PyQt6.QtGui import QIcon, QDragEnterEvent, QDropEvent, QDragMoveEvent, QFont

# Import the modular components
from file_utilities import (
    is_media_file, scan_directory_recursive, get_filename_components_static,
    rename_files, FileConstants, MEDIA_EXTENSIONS, IMAGE_EXTENSIONS, VIDEO_EXTENSIONS,
    is_image_file, is_video_file
)
from exif_processor import (
    get_cached_exif_data, get_selective_cached_exif_data,
    extract_exif_fields, get_exiftool_metadata_shared, 
    cleanup_global_exiftool, clear_global_exif_cache,
    SimpleExifHandler, EXIFTOOL_AVAILABLE, PIL_AVAILABLE,
    extract_exif_fields_with_retry
)
from rename_engine import RenameWorkerThread
from ui_components import InteractivePreviewWidget
from theme_manager import ThemeManager

class ExifToolWarningDialog(QDialog):
    """Warning dialog shown when ExifTool is not installed"""
    
    def __init__(self, parent=None, current_method=None):
        super().__init__(parent)
        self.setWindowTitle("ExifTool Not Found - Installation Recommended")
        self.setModal(True)
        self.resize(600, 450)
        
        layout = QVBoxLayout(self)
        
        # Header with warning icon
        header_layout = QHBoxLayout()
        warning_icon = QLabel()
        warning_icon.setPixmap(self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxWarning).pixmap(48, 48))
        
        header_text = QLabel("ExifTool Not Found")
        header_text.setStyleSheet("font-size: 18px; font-weight: bold; color: #d83b01;")
        
        header_layout.addWidget(warning_icon)
        header_layout.addWidget(header_text)
        header_layout.addStretch()
        layout.addLayout(header_layout)
        
        # Dynamic fallback text based on current method
        if current_method == "pillow":
            fallback_text = "<b>Current fallback:</b> Using Pillow (limited RAW support, may miss some metadata)"
            continue_button_text = "Continue with Pillow"
        else:
            fallback_text = "<b>Current status:</b> No EXIF support available (basic file operations only)"
            continue_button_text = "Continue without EXIF"
        
        # Main explanation text
        info_text = QLabel(f"""
<b>What is ExifTool?</b><br>
ExifTool is a powerful library for reading and writing metadata in image and video files.

<b>Why ExifTool is recommended:</b><br>
• <b>Complete RAW support:</b> Works with all camera RAW formats<br>
• <b>Video metadata:</b> Extracts date, camera, and technical data from videos<br>
• <b>More metadata:</b> Extracts camera, lens, and date information more reliably<br>

{fallback_text}

<b>How to install ExifTool:</b><br>
1. Download from: <a href="https://exiftool.org/install.html">https://exiftool.org/install.html</a><br>
2. Extract the COMPLETE ZIP archive to your program folder<br>
3. Restart this application<br>
        """)
        info_text.setWordWrap(True)
        info_text.setOpenExternalLinks(True)
        info_text.setStyleSheet("font-size: 11px; line-height: 1.4;")
        
        layout.addWidget(info_text)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.dont_show_again = QCheckBox("Don't show this warning again")
        button_layout.addWidget(self.dont_show_again)
        button_layout.addStretch()
        
        install_button = QPushButton("Open Download Page")
        install_button.clicked.connect(self.open_download_page)
        
        continue_button = QPushButton(continue_button_text)
        continue_button.clicked.connect(self.accept)
        
        button_layout.addWidget(install_button)
        button_layout.addWidget(continue_button)
        layout.addLayout(button_layout)
    
    def open_download_page(self):
        """Open the ExifTool download page in default browser"""
        import webbrowser
        webbrowser.open("https://exiftool.org/install.html")
        self.accept()

# Simple replacement functions for missing dependencies
def calculate_stats(files):
    """Calculate simple file statistics"""
    total = len(files)
    
    # Count different file types
    jpeg_count = sum(1 for f in files if f.lower().endswith(('.jpg', '.jpeg')))
    raw_count = sum(1 for f in files if any(f.lower().endswith(ext) for ext in ['.cr2', '.nef', '.arw', '.orf', '.rw2', '.dng', '.raw', '.sr2', '.pef', '.raf', '.3fr', '.erf', '.kdc', '.mos', '.nrw', '.srw', '.x3f']))
    other_images = sum(1 for f in files if any(f.lower().endswith(ext) for ext in ['.png', '.bmp', '.tiff', '.tif', '.gif']))
    total_images = jpeg_count + raw_count + other_images
    videos = total - total_images
    
    return {
        'total_files': total,
        'total_images': total_images,
        'jpeg_count': jpeg_count,
        'raw_count': raw_count,
        'video_count': videos,
        'total': total,
        'images': total_images, 
        'videos': videos
    }

class SimpleExifHandler:
    """Simple EXIF handler using the original functions"""
    def __init__(self):
        self.current_method = "exiftool" if EXIFTOOL_AVAILABLE else ("pillow" if PIL_AVAILABLE else None)
        self.exiftool_path = self._find_exiftool_path()
    
    def _find_exiftool_path(self):
        """Find ExifTool installation path"""
        import glob
        
        if not EXIFTOOL_AVAILABLE:
            return None
            
        # Check common ExifTool installation paths
        script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        # Search for exiftool in project directory
        exiftool_candidates = [
            os.path.join(script_dir, "exiftool-13.33_64", "exiftool.exe"),
            os.path.join(script_dir, "exiftool-13.33_64", "exiftool(-k).exe"),
            os.path.join(script_dir, "exiftool-13.32_64", "exiftool.exe"),
            os.path.join(script_dir, "exiftool-13.32_64", "exiftool(-k).exe"),
        ]
        
        # Also search for any exiftool folder pattern
        for filename in ["exiftool.exe", "exiftool(-k).exe"]:
            exiftool_pattern = os.path.join(script_dir, "*exiftool*", filename)
            exiftool_matches = glob.glob(exiftool_pattern)
            exiftool_candidates.extend(exiftool_matches)
        
        for path in exiftool_candidates:
            if os.path.exists(path):
                print(f"Found ExifTool at: {path}")
                return path
        
        print("ExifTool not found, using system installation")
        return None
    
    def extract_exif(self, file_path):
        return get_cached_exif_data(file_path, self.current_method, self.exiftool_path)
    
    def extract_raw_exif(self, file_path):
        """Extract raw EXIF metadata using ExifTool"""
        try:
            if self.current_method == "exiftool":
                # Use the shared ExifTool instance for raw metadata
                return get_exiftool_metadata_shared(file_path, self.exiftool_path)
            else:
                # Fallback for Pillow - return basic metadata
                date, camera, lens = get_cached_exif_data(file_path, self.current_method, self.exiftool_path)
                return {
                    'DateTimeOriginal': date,
                    'Model': camera,
                    'LensModel': lens
                }
        except Exception as e:
            print(f"Error extracting raw EXIF from {file_path}: {e}")
            return {}
    
    def is_exiftool_available(self):
        return EXIFTOOL_AVAILABLE

class SimpleFilenameGenerator:
    """Simple filename generator using original functions"""
    def __init__(self):
        pass
    
    def generate_filename(self, date_taken, camera_prefix, additional, camera_model, lens_model, use_camera, use_lens, num, custom_order, date_format="YYYY-MM-DD", use_date=True):
        components = get_filename_components_static(date_taken, camera_prefix, additional, camera_model, lens_model, use_camera, use_lens, num, custom_order, date_format, use_date)
        return components

def extract_image_number(image_path, exif_method, exiftool_path):
    """Extract image number/shutter count from image file"""
    try:
        # Get raw EXIF data for detailed extraction
        if exif_method == "exiftool" and exiftool_path:
            exif_data = get_exiftool_metadata_shared(image_path, exiftool_path)
        else:
            return None
            
        if not exif_data:
            return None
        
        # List of possible fields for image/shutter count in priority order
        image_number_fields = [
            'EXIF:ShutterCount',
            'Canon:ShutterCount', 
            'Nikon:ShutterCount',
            'Sony:ShutterCount',
            'Olympus:ShutterCount',
            'Panasonic:ShutterCount',
            'Fujifilm:ShutterCount',
            'EXIF:ImageNumber',
            'Canon:ImageNumber',
            'Nikon:ImageNumber', 
            'Sony:ImageNumber',
            'MakerNotes:ShutterCount',
            'MakerNotes:ImageNumber',
            'File:FileNumber'
        ]
        
        # Try each field to find image number
        for field in image_number_fields:
            if field in exif_data:
                value = exif_data[field]
                if value and str(value).isdigit():
                    return str(value)
                elif value and isinstance(value, (int, float)):
                    return str(int(value))
        
        # If no specific image number field found, try sequential numbering fields
        sequence_fields = [
            'EXIF:SequenceNumber',
            'Canon:SequenceNumber',
            'File:SequenceNumber'
        ]
        
        for field in sequence_fields:
            if field in exif_data:
                value = exif_data[field]
                if value and str(value).isdigit():
                    return str(value)
                elif value and isinstance(value, (int, float)):
                    return str(int(value))
        
        return None
        
    except Exception as e:
        print(f"Error extracting image number from {image_path}: {e}")
        return None

def is_video_file(file_path):
    """Check if file is a video file"""
    video_extensions = ['.mp4', '.mov', '.avi', '.mkv', '.m4v', '.3gp', '.wmv', 
                       '.flv', '.webm', '.mpg', '.mpeg', '.m2v', '.mts', '.m2ts']
    return os.path.splitext(file_path)[1].lower() in video_extensions

class FileRenamerApp(QMainWindow):
    def __init__(self):
        super().__init__()
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
        
        if EXIFTOOL_AVAILABLE and self.exiftool_path:
            self.exif_method = "exiftool"
        elif PIL_AVAILABLE:
            self.exif_method = "pillow"
        else:
            self.exif_method = None
        
        # Initialize theme manager
        self.theme_manager = ThemeManager()
        
        # State variables
        self.files = []
        self.current_order = ["Date", "Prefix", "Additional", "Camera", "Lens"]
        self.camera_models = {}
        self.lens_models = {}
        self.original_filenames = {}  # Track original filenames for undo
        self.selected_metadata = {}  # Store metadata selected from EXIF dialog
        
        self.setup_ui()
        
        # Initialize EXIF cache
        self._preview_exif_cache = {}
        self._preview_exif_file = None
        
        # Check for ExifTool availability and show warning if needed
        self.check_exiftool_warning()
    
    def setup_ui(self):
        """Setup the complete original UI design"""
        
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
        # Remove custom styling to match other checkboxes
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
        camera_row = QHBoxLayout()
        camera_label = QLabel("Camera Prefix:")
        camera_info = QLabel()
        camera_info.setPixmap(self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxInformation).pixmap(16, 16))
        camera_info.setToolTip("Click for detailed info about camera prefix")
        camera_info.setCursor(Qt.CursorShape.PointingHandCursor)
        camera_info.mousePressEvent = lambda event: self.show_camera_prefix_info()
        camera_row.addWidget(camera_label)
        camera_row.addWidget(camera_info)
        camera_row.addStretch()
        self.layout.addLayout(camera_row)
        
        self.camera_prefix_entry = QLineEdit()
        self.camera_prefix_entry.setPlaceholderText("e.g. A7R3, D850")
        self.camera_prefix_entry.textChanged.connect(self.validate_and_update_preview)
        self.layout.addWidget(self.camera_prefix_entry)

        # Additional with clickable info icon
        additional_row = QHBoxLayout()
        additional_label = QLabel("Additional:")
        additional_info = QLabel()
        additional_info.setPixmap(self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxInformation).pixmap(16, 16))
        additional_info.setToolTip("Click for detailed info about additional field")
        additional_info.setCursor(Qt.CursorShape.PointingHandCursor)
        additional_info.mousePressEvent = lambda event: self.show_additional_info()
        additional_row.addWidget(additional_label)
        additional_row.addWidget(additional_info)
        additional_row.addStretch()
        self.layout.addLayout(additional_row)
        
        self.additional_entry = QLineEdit()
        self.additional_entry.setPlaceholderText("e.g. vacation, wedding")
        self.additional_entry.textChanged.connect(self.validate_and_update_preview)
        self.layout.addWidget(self.additional_entry)

        # Separator with clickable info icon
        separator_row = QHBoxLayout()
        separator_label = QLabel("Devider:")
        separator_info = QLabel()
        separator_info.setPixmap(self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxInformation).pixmap(16, 16))
        separator_info.setToolTip("Click for detailed info about separators")
        separator_info.setCursor(Qt.CursorShape.PointingHandCursor)
        separator_info.mousePressEvent = lambda event: self.show_separator_info()
        separator_row.addWidget(separator_label)
        separator_row.addWidget(separator_info)
        separator_row.addStretch()
        self.layout.addLayout(separator_row)
        
        self.devider_combo = QComboBox()
        self.devider_combo.addItems(["-", "_", ""])
        self.devider_combo.setCurrentText("-")
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
        self.checkbox_camera.stateChanged.connect(self.on_camera_checkbox_changed)
        
        # Lens checkbox with model display
        lens_checkbox_layout = QHBoxLayout()
        self.checkbox_lens = QCheckBox("Include lens in filename")
        self.lens_model_label = QLabel("(detecting...)")
        self.lens_model_label.setStyleSheet("color: gray; font-style: italic;")
        lens_checkbox_layout.addWidget(self.checkbox_lens)
        lens_checkbox_layout.addWidget(self.lens_model_label)
        lens_checkbox_layout.addStretch()
        self.layout.addLayout(lens_checkbox_layout)
        self.checkbox_lens.stateChanged.connect(self.on_lens_checkbox_changed)

        # Drag & Drop File List with dashed border and info text
        self.file_list = QListWidget()
        self.file_list.setStyleSheet("""
            QListWidget {
                border: 2px dashed #cccccc;
                border-radius: 8px;
                background-color: #fafafa;
                padding: 20px;
                min-height: 120px;
            }
            QListWidget::item {
                padding: 4px;
                border-bottom: 1px solid #eeeeee;
                background-color: white;
                border-radius: 3px;
                margin: 1px;
            }
            QListWidget::item:selected {
                background-color: #0078d4;
                color: white;
            }
            QListWidget::item:hover {
                background-color: #f0f6ff;
            }
        """)
        
        # Add placeholder text when empty
        self.update_file_list_placeholder()
        
        self.layout.addWidget(self.file_list)
        self.file_list.itemDoubleClicked.connect(self.show_selected_exif)
        self.file_list.itemClicked.connect(self.show_media_info)
        
        # File Statistics Info Panel
        self.file_stats_label = QLabel()
        self.file_stats_label.setStyleSheet("""
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
        self.file_stats_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.file_stats_label.setWordWrap(True)
        self.update_file_statistics()
        self.layout.addWidget(self.file_stats_label)
        
        # Enhanced info for media clicking with visual indicator
        file_list_info = QLabel("💡Single click = Media info in status bar | Double click = Essential metadata dialog")
        file_list_info.setStyleSheet("""
            QLabel {
                border: 1px solid palette(mid);
                border-radius: 4px;
                padding: 6px;
                color: palette(text);
                background-color: palette(base);
                font-size: 11px;
                font-weight: normal;
            }
        """)
        file_list_info.setWordWrap(True)
        file_list_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(file_list_info)
        
        self.file_list.setToolTip("Single click: Media info | Double click: Essential metadata")
        self.file_list.installEventFilter(self)

        self.setAcceptDrops(True)

        # Prominenter Rename Button
        self.rename_button = QPushButton("🚀 Rename Files")
        self.rename_button.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                border: none;
                padding: 12px 24px;
                border-radius: 8px;
                font-weight: bold;
                font-size: 14px;
                min-height: 20px;
            }
            QPushButton:hover {
                background-color: #218838;
            }
            QPushButton:pressed {
                background-color: #1e7e34;
            }
            QPushButton:disabled {
                background-color: #6c757d;
                color: #ffffff;
            }
        """)
        self.rename_button.clicked.connect(self.rename_files_action)
        self.layout.addWidget(self.rename_button)

        # Undo Button - weniger prominent aber sichtbar
        self.undo_button = QPushButton("↶ Restore Original Names")
        self.undo_button.setStyleSheet("""
            QPushButton {
                background-color: #ffc107;
                color: #212529;
                border: none;
                padding: 8px 16px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 12px;
                min-height: 16px;
            }
            QPushButton:hover {
                background-color: #e0a800;
            }
            QPushButton:pressed {
                background-color: #d39e00;
            }
            QPushButton:disabled {
                background-color: #6c757d;
                color: #ffffff;
            }
        """)
        self.undo_button.clicked.connect(self.undo_rename_action)
        self.undo_button.setEnabled(False)  # Initially disabled
        self.undo_button.setToolTip("Restore all files to their original names (only available after renaming)")
        self.layout.addWidget(self.undo_button)
        
        # Statusbar für Info unten rechts
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        # Label für Methode und ggf. Info-Icon
        self.exif_status_label = QLabel()
        self.status.addPermanentWidget(self.exif_status_label)
        
        # Initialize custom ordering BEFORE calling update_preview
        self.custom_order = ["Date", "Camera", "Lens", "Prefix", "Additional", "Number"]  # FLEXIBLE: Number is now draggable
        
        self.update_exif_status()
        self.update_preview()
        self.update_file_list_placeholder()  # Add initial placeholder
        self.update_file_statistics()  # Initialize file statistics display

        # Update camera and lens labels initially
        self.update_camera_lens_labels()
        
        # CRITICAL FIX: Ensure rename button starts disabled (no files initially)
        self.rename_button.setEnabled(False)
        
        # Show ExifTool warning if needed (after UI is fully initialized)
        QApplication.processEvents()  # Ensure UI is rendered first

    def check_exiftool_warning(self):
        """Check if ExifTool warning should be shown"""
        if not (EXIFTOOL_AVAILABLE and self.exiftool_path):
            settings = QSettings("FileRenamer", "Settings")
            show_warning = settings.value("show_exiftool_warning", True, type=bool)
            
            if show_warning:
                dialog = ExifToolWarningDialog(self, self.exif_method)
                dialog.exec()
                
                if not dialog.should_show_again():
                    settings.setValue("show_exiftool_warning", False)
    
    def get_exiftool_path(self):
        """Simple ExifTool path detection for the modular version"""
        script_dir = os.path.dirname(os.path.dirname(__file__))  # Go up from modules to main dir
        
        # Check for exiftool-13.33_64 directory
        exiftool_path = os.path.join(script_dir, "exiftool-13.33_64", "exiftool(-k).exe")
        if os.path.exists(exiftool_path):
            return exiftool_path
            
        # Fallback: check for older version
        exiftool_path = os.path.join(script_dir, "exiftool-13.32_64", "exiftool.exe")
        if os.path.exists(exiftool_path):
            return exiftool_path
            
        return None
    
    # Event handlers implementation
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
            media_files = scan_directory_recursive(folder)
            self.files.extend(media_files)
            self.update_file_list()
            self.extract_camera_info()
    
    def clear_file_list(self):
        """Clear the file list"""
        self.files = []
        self.file_list.clear()
        self.status.showMessage("Ready")
        self.rename_button.setEnabled(False)
        
        # Clear camera and lens data
        self.camera_models = {}
        self.lens_models = {}
        self.camera_model_label.setText("(no files selected)")
        self.lens_model_label.setText("(no files selected)")
        
        self.update_file_list_placeholder()
        self.update_file_statistics()
    
    def update_file_list(self):
        """Update the file list display"""
        self.file_list.clear()
        for file_path in self.files:
            item = QListWidgetItem(os.path.basename(file_path))
            item.setData(Qt.ItemDataRole.UserRole, file_path)
            self.file_list.addItem(item)
        
        self.rename_button.setEnabled(len(self.files) > 0)
        self.update_file_statistics()
        self.update_file_list_placeholder()
    
    def update_file_list_placeholder(self):
        """Add placeholder text when file list is empty"""
        if self.file_list.count() == 0:
            placeholder_item = QListWidgetItem("📁 Drag and drop folders/files here or use buttons below\n📄 Supports images (JPG, RAW) and videos (MP4, MOV, etc.)")
            placeholder_item.setFlags(Qt.ItemFlag.NoItemFlags)  # Make it non-selectable
            placeholder_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.file_list.addItem(placeholder_item)
    
    def update_file_statistics(self):
        """Update file statistics display"""
        if not self.files:
            self.file_stats_label.setText("")
            self.file_stats_label.hide()
            return
        
        stats = calculate_stats(self.files)
        
        self.file_stats_label.setText(
            f"📊 Total: {stats['total_files']} files ({stats['total_images']} images)\n"
            f"📷 JPEG: {stats['jpeg_count']} | 📸 RAW: {stats['raw_count']}"
        )
        self.file_stats_label.show()
    
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
                print(f"show_media_info: File not found: {normalized_path}")
                return
            
            if is_video_file(file_path):
                # For videos, try to extract duration info
                if EXIFTOOL_AVAILABLE and self.exiftool_path:
                    raw_exif_data = get_exiftool_metadata_shared(normalized_path, self.exiftool_path)
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
                print(f"show_exif_info: File not found: {normalized_file}")
                self.show_exif_dialog(file_path, "File not found.")
                return
            
            # Extract raw EXIF data using direct function
            if self.exif_method == "exiftool" and self.exiftool_path:
                raw_exif_data = get_exiftool_metadata_shared(normalized_file, self.exiftool_path)
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
            print(f"Error in show_exif_info: {e}")
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
                except:
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
            except:
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
            except:
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
            except:
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
                except:
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
            except:
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
            except:
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
            except:
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
            # Use the original extract_exif_fields function
            date, camera, lens = extract_exif_fields(first_media, self.exif_method, self.exiftool_path)
            
            # Store results for label update
            self.detected_camera = camera
            self.detected_lens = lens
            
        except Exception as e:
            print(f"Error extracting camera info from {first_media}: {e}")
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
        """Update the interactive preview widget with current settings"""
        # Get current settings
        camera_prefix = self.camera_prefix_entry.text().strip()
        additional = self.additional_entry.text().strip()
        use_camera = self.checkbox_camera.isChecked()
        use_lens = self.checkbox_lens.isChecked()
        use_date = self.checkbox_date.isChecked()
        date_format = self.date_format_combo.currentText()
        devider = self.devider_combo.currentText()
        
        # Choose first JPG file, else first media file, else dummy
        preview_file = next((f for f in self.files if os.path.splitext(f)[1].lower() in [".jpg", ".jpeg"]), None)
        if not preview_file:
            preview_file = next((f for f in self.files if is_media_file(f)), None)
        if not preview_file and self.files:
            preview_file = self.files[0]
        if not preview_file:
            # Default example with video extension to show video support
            preview_file = "20250725_DSC0001.MP4"

        date_taken = None
        camera_model = None
        lens_model = None
        
        if not self.exif_method:
            # No EXIF support - use fallback values
            date_taken = "20250725"
            camera_model = "ILCE-7CM2" if use_camera else None
            lens_model = "FE-20-70mm-F4-G" if use_lens else None
        else:
            # EXIF cache: only extract if file changed
            cache_key = (preview_file, self.exif_method, self.exiftool_path)
            if os.path.exists(preview_file):
                if not hasattr(self, '_preview_exif_file') or self._preview_exif_file != cache_key:
                    try:
                        from exif_processor import get_selective_cached_exif_data
                        date_taken, camera_model, lens_model = get_selective_cached_exif_data(
                            preview_file, self.exif_method, self.exiftool_path,
                            need_date=use_date, need_camera=use_camera, need_lens=use_lens
                        )
                        self._preview_exif_cache = {
                            'date': date_taken,
                            'camera': camera_model,
                            'lens': lens_model,
                        }
                        self._preview_exif_file = cache_key
                    except Exception as e:
                        # Fallback on error
                        self._preview_exif_cache = {'date': None, 'camera': None, 'lens': None}
                else:
                    # Use cached values
                    date_taken = self._preview_exif_cache.get('date')
                    camera_model = self._preview_exif_cache.get('camera')
                    lens_model = self._preview_exif_cache.get('lens')
            
            # Fallback date extraction
            if not date_taken:
                import re
                m = re.search(r'(20\d{2})(\d{2})(\d{2})', os.path.basename(preview_file))
                if m:
                    date_taken = f"{m.group(1)}{m.group(2)}{m.group(3)}"
            
            if not date_taken:
                if os.path.exists(preview_file):
                    import datetime
                    mtime = os.path.getmtime(preview_file)
                    dt = datetime.datetime.fromtimestamp(mtime)
                    date_taken = dt.strftime('%Y%m%d')
                else:
                    date_taken = "20250725"
            
            # Use fallback values for preview if not detected AND checkbox is enabled
            if use_camera and not camera_model:
                camera_model = "ILCE-7CM2"
            if use_lens and not lens_model:
                lens_model = "FE-20-70mm-F4-G"
            
            # Clear values if checkboxes are disabled
            if not use_camera:
                camera_model = None
            if not use_lens:
                lens_model = None
        
        # Format date for display using the selected format
        if date_taken and use_date:
            year = date_taken[:4]
            month = date_taken[4:6]
            day = date_taken[6:8]
            
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
        else:
            formatted_date = None
        
        # Check if camera/lens are in selected_metadata to avoid duplicates
        has_camera_in_metadata = hasattr(self, 'selected_metadata') and self.selected_metadata and 'camera' in self.selected_metadata
        has_lens_in_metadata = hasattr(self, 'selected_metadata') and self.selected_metadata and 'lens' in self.selected_metadata
        
        # Build component list for display - only include active components
        display_components = []
        component_mapping = {
            "Date": formatted_date if use_date else None,  # Only if date checkbox is checked
            "Prefix": camera_prefix if camera_prefix else None,  # Only if text entered
            "Additional": additional if additional else None,  # Only if text entered
            "Camera": camera_model if (use_camera and camera_model and not has_camera_in_metadata) else None,  # Only if checkbox checked AND value exists AND not in metadata
            "Lens": lens_model if (use_lens and lens_model and not has_lens_in_metadata) else None,  # Only if checkbox checked AND value exists AND not in metadata
            "Number": "001"  # FLEXIBLE: Add number as draggable component
        }
        
        # Add selected metadata from metadata dialog
        if hasattr(self, 'selected_metadata') and self.selected_metadata:
            # For preview: extract real metadata from preview file if placeholders are used
            preview_metadata = self.selected_metadata.copy()
            
            # Check if we need to extract real metadata for Boolean flags
            if self.exif_method and preview_file and os.path.exists(preview_file):
                needs_real_metadata = any(
                    value is True for value in self.selected_metadata.values()
                )
                
                if needs_real_metadata:
                    try:
                        from .exif_processor import get_all_metadata
                        print(f"🔍 Preview: Extracting real metadata from {os.path.basename(preview_file)}")
                        real_metadata = get_all_metadata(preview_file, self.exif_method, self.exiftool_path)
                        print(f"  Preview metadata: {real_metadata}")
                        
                        # Replace Boolean flags with real values for preview
                        for key, value in self.selected_metadata.items():
                            if value is True:
                                # Handle key mapping for shutter/shutter_speed
                                exif_key = key
                                if key == 'shutter' and 'shutter_speed' in real_metadata:
                                    exif_key = 'shutter_speed'
                                
                                if exif_key in real_metadata:
                                    old_value = preview_metadata[key]
                                    preview_metadata[key] = real_metadata[exif_key]
                                    print(f"  Preview: {key} {old_value} -> {real_metadata[exif_key]}")
                    except Exception as e:
                        print(f"❌ Warning: Could not extract real metadata for preview: {e}")
                        import traceback
                        traceback.print_exc()
            
            # Add selected metadata components using preview metadata
            for metadata_key, metadata_value in preview_metadata.items():
                # SAFETY CHECK: Don't add camera/lens metadata if their checkboxes are unchecked
                if metadata_key == 'camera' and not use_camera:
                    continue
                if metadata_key == 'lens' and not use_lens:
                    continue
                    
                # Format metadata for display
                display_value = self.format_metadata_for_filename(metadata_key, metadata_value)
                if display_value:
                    component_mapping[f"Meta_{metadata_key}"] = display_value
        
        # Build a unified list of all active components for the preview
        display_components = []
        
        # Create a dynamic, full order list for this preview update
        # This ensures that newly selected metadata items are included and become draggable
        active_components_order = list(self.custom_order)
        if hasattr(self, 'selected_metadata') and self.selected_metadata:
            for meta_key, is_selected in self.selected_metadata.items():
                if is_selected:
                    meta_name = f"Meta_{meta_key}"
                    if meta_name not in active_components_order:
                        active_components_order.append(meta_name)

        # Add components in the current, full order
        print(f"🔍 Debug: Full component order for display: {active_components_order}")
        for component_name in active_components_order:
            value = component_mapping.get(component_name)
            if value:  # Only add non-empty and active components
                display_components.append(value)
        
        # Update the interactive preview
        print(f"🖼️ Debug: Setting preview components: {display_components}")
        print(f"🖼️ Debug: Selected metadata: {getattr(self, 'selected_metadata', {})}")
        print(f"🖼️ Debug: Component mapping: {component_mapping}")
        self.interactive_preview.set_separator(devider)
        self.interactive_preview.set_components(display_components, "001")
    
    def format_metadata_for_filename(self, metadata_key, metadata_value):
        """Format metadata values for use in filenames"""
        if not metadata_value or metadata_value == 'Unknown':
            return None
        
        # CRITICAL FIX: Skip boolean flags (these indicate extraction needed)
        if isinstance(metadata_value, bool):
            return None  # This is a flag, not actual data
        
        # Clean and format different metadata types
        if metadata_key == 'camera':
            # Remove spaces and special characters from camera name
            return metadata_value.replace(' ', '-').replace('/', '-')
        elif metadata_key == 'lens':
            # Simplify lens name for filename
            return metadata_value.replace(' ', '-').replace('/', '-')
        elif metadata_key == 'date':
            # Keep only date part, format as YYYY-MM-DD
            date_part = metadata_value.split(' ')[0] if ' ' in metadata_value else metadata_value
            return date_part.replace(':', '-')
        elif metadata_key == 'iso':
            # Handle ISO format: "100" -> "ISO100" or "ISO 100" -> "ISO100"
            if str(metadata_value).isdigit():
                return f"ISO{metadata_value}"
            else:
                # Remove spaces if already formatted
                return str(metadata_value).replace(' ', '')
        elif metadata_key == 'aperture':
            # Clean up aperture value (remove 'f/' if present, but keep single 'f')
            if metadata_value.startswith('f/'):
                # Case: "f/9" -> "f9"
                return metadata_value.replace('f/', 'f')
            elif metadata_value.startswith('f'):
                # Case: "f9" -> "f9" (already correct)
                return metadata_value
            else:
                # Case: "9" -> "f9"
                return f"f{metadata_value}"
        elif metadata_key in ['shutter', 'shutter_speed']:
            # Keep shutter speed format but replace problematic characters for filename
            # Convert 1/800s to 1_800s for filename safety while keeping it readable
            # Also ensure we don't get double 's' (1/800s -> 1_800s, not 1_800ss)
            result = metadata_value.replace('/', '_').replace(' ', '')
            # Clean up any double 's' that might occur
            if result.endswith('ss') and not result.endswith('sss'):
                result = result[:-1]  # Remove one 's' if double
            print(f"🔧 Debug: Formatted shutter '{metadata_value}' -> '{result}'")
            return result
        elif metadata_key == 'focal_length':
            # Extract just the number part
            import re
            match = re.search(r'(\d+)mm', metadata_value)
            if match:
                return f"{match.group(1)}mm"
            return metadata_value.replace(' ', '-')
        elif metadata_key == 'resolution':
            # Simplify resolution display
            if 'MP' in metadata_value:
                mp_part = metadata_value.split('(')[1].split(')')[0] if '(' in metadata_value else metadata_value
                return mp_part.replace(' ', '').replace('.', '-')
            return metadata_value.replace(' ', '-').replace('x', 'x')
        else:
            # General cleanup for other metadata
            return metadata_value.replace(' ', '-').replace('/', '-').replace(':', '-')
    
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
                    date_taken = "20250805"  # Use current date as fallback
            
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
                print(f"🔄 Debug: Mapped Date '{formatted_date}' -> 'Date'")
            
        # Map camera and lens components
        if use_camera:
            camera_value = None
            if hasattr(self, '_preview_exif_cache') and self._preview_exif_cache:
                camera_value = self._preview_exif_cache.get('camera')
            if not camera_value:
                camera_value = "ILCE-7CM2"  # Fallback
            value_to_component[camera_value] = "Camera"
            
        if use_lens:
            lens_value = None
            if hasattr(self, '_preview_exif_cache') and self._preview_exif_cache:
                lens_value = self._preview_exif_cache.get('lens')
            if not lens_value:
                lens_value = "FE-20-70mm-F4-G"  # Fallback
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
                        from .exif_processor import get_all_metadata
                        real_metadata = get_all_metadata(preview_file, self.exif_method, self.exiftool_path)
                        
                        # Replace Boolean flags with real values for preview
                        for key, value in self.selected_metadata.items():
                            if value is True:
                                # CRITICAL FIX: Add key mapping for shutter -> shutter_speed
                                exif_key = key
                                if key == 'shutter' and 'shutter_speed' in real_metadata:
                                    exif_key = 'shutter_speed'
                                
                                if exif_key in real_metadata:
                                    preview_metadata[key] = real_metadata[exif_key]
                                    print(f"🔄 Debug: Mapped preview {key} True -> {real_metadata[exif_key]}")
                    except Exception as e:
                        print(f"❌ Warning: Could not extract real metadata for preview mapping: {e}")
            
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
                    print(f"🔄 Debug: Mapped EXIF '{display_value}' -> '{meta_component_name}'")
        
        # Convert display order to internal order
        new_internal_order = []
        for display_value in new_order:
            if display_value in value_to_component:
                component_name = value_to_component[display_value]
                if component_name not in new_internal_order:  # Prevent duplicates
                    new_internal_order.append(component_name)
        
        # Add any missing basic components that weren't in the display
        basic_components = ["Date", "Prefix", "Additional", "Camera", "Lens", "Number"]  # FLEXIBLE: Include Number
        for component in basic_components:
            if component not in new_internal_order:
                new_internal_order.append(component)
        
        # Update custom order
        self.custom_order = new_internal_order
        
        # Update preview to reflect the change
        self.update_preview()
    
    def on_continuous_counter_changed(self):
        """Handle continuous counter checkbox change"""
        self.update_preview()
    
    def on_devider_changed(self):
        """Handle separator change"""
        self.update_preview()
    
    def validate_and_update_preview(self):
        """Validate input and update preview"""
        self.update_preview()
    
    def on_theme_changed(self, theme_name):
        """Handle theme changes using ThemeManager"""
        self.theme_manager.apply_theme(theme_name, self)
    
    def update_exif_status(self):
        """Update EXIF method status in status bar"""
        if EXIFTOOL_AVAILABLE and self.exiftool_path:
            self.exif_status_label.setText("EXIF method: ExifTool v13.33 (recommended) ✓")
            self.exif_status_label.setStyleSheet("color: green; font-weight: bold;")
        else:
            self.exif_status_label.setText("EXIF method: Pillow (limited) ⚠")
            self.exif_status_label.setStyleSheet("color: orange; font-weight: bold;")
    
    def rename_files_action(self):
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
        devider = self.devider_combo.currentText()
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
        self.rename_button.setEnabled(False)
        self.rename_button.setText("⏳ Processing...")
        self.select_files_menu_button.setEnabled(False)
        self.select_folder_menu_button.setEnabled(False)
        self.clear_files_menu_button.setEnabled(False)
        
        # Start worker thread for background processing
        self.worker = RenameWorkerThread(
            media_files, camera_prefix, additional, use_camera, use_lens, 
            self.exif_method, devider, self.exiftool_path, self.custom_order,
            date_format, use_date, continuous_counter, self.selected_metadata
        )
        self.worker.progress_update.connect(self.update_status)
        self.worker.finished.connect(self.on_rename_finished)
        self.worker.error.connect(self.on_rename_error)
        self.worker.start()
    
    def update_status(self, message):
        """Update status bar with progress message"""
        self.status.showMessage(message)
        QApplication.processEvents()  # Update UI
    
    def on_rename_finished(self, renamed_files, errors):
        """Handle completion of rename operation"""
        # Update the file list with the new file names
        original_non_media = [f for f in self.files if not is_media_file(f)]
        old_media_files = [f for f in self.files if is_media_file(f)]
        
        # CRITICAL FIX: Only create original mapping if it doesn't exist yet
        # This preserves the FIRST original filenames, not subsequent renames
        if not hasattr(self, 'original_filenames') or not self.original_filenames:
            # First rename operation - create mapping from current names to original names
            new_original_filenames = {}
            
            # Group old files by directory for proper mapping
            old_files_by_dir = {}
            for old_file in old_media_files:
                directory = os.path.dirname(old_file)
                if directory not in old_files_by_dir:
                    old_files_by_dir[directory] = []
                old_files_by_dir[directory].append(old_file)
            
            # Group renamed files by directory  
            renamed_files_by_dir = {}
            for renamed_file in renamed_files:
                directory = os.path.dirname(renamed_file)
                if directory not in renamed_files_by_dir:
                    renamed_files_by_dir[directory] = []
                renamed_files_by_dir[directory].append(renamed_file)
            
            # Create safe mapping based on directory and order preservation
            # CRITICAL FIX: Use index mapping instead of sorting to avoid order issues
            for directory in old_files_by_dir:
                old_files_in_dir = old_files_by_dir[directory]
                renamed_files_in_dir = renamed_files_by_dir.get(directory, [])
                
                # SAFETY CHECK: Ensure we have the same number of files
                if len(old_files_in_dir) != len(renamed_files_in_dir):
                    print(f"WARNING: File count mismatch in {directory}")
                    print(f"  Original: {len(old_files_in_dir)}, Renamed: {len(renamed_files_in_dir)}")
                    # Use minimum count to avoid index errors
                    min_count = min(len(old_files_in_dir), len(renamed_files_in_dir))
                    old_files_in_dir = old_files_in_dir[:min_count]
                    renamed_files_in_dir = renamed_files_in_dir[:min_count]
                
                # Map files based on their original position in self.files list
                # This preserves the exact order relationship
                for old_file in old_files_in_dir:
                    try:
                        # Find the position of this old file in the original self.files list
                        old_index = old_media_files.index(old_file)
                        
                        # Find the corresponding renamed file at the same position
                        if old_index < len(renamed_files):
                            renamed_file = renamed_files[old_index]
                            original_filename = os.path.basename(old_file)
                            new_original_filenames[renamed_file] = original_filename
                            print(f"Mapping: {os.path.basename(renamed_file)} -> {original_filename}")
                    except (ValueError, IndexError) as e:
                        print(f"WARNING: Could not map {os.path.basename(old_file)}: {e}")
            
            # Set original_filenames for the first time
            self.original_filenames = new_original_filenames
        else:
            # Subsequent rename operations - update paths but keep original filenames
            updated_original_filenames = {}
            
            # Map old paths to new paths but preserve original filenames
            old_to_new_path_mapping = {}
            for i, old_file in enumerate(old_media_files):
                if i < len(renamed_files):
                    old_to_new_path_mapping[old_file] = renamed_files[i]
            
            # Update paths in original_filenames dictionary
            for old_path, original_filename in self.original_filenames.items():
                if old_path in old_to_new_path_mapping:
                    new_path = old_to_new_path_mapping[old_path]
                    updated_original_filenames[new_path] = original_filename
                else:
                    # Keep unchanged entries
                    updated_original_filenames[old_path] = original_filename
            
            self.original_filenames = updated_original_filenames
        
        # Clear and rebuild the file list
        self.files.clear()
        self.file_list.clear()
        
        # Add renamed media files with proper item data
        for renamed_file in renamed_files:
            self.files.append(renamed_file)
            item = QListWidgetItem(os.path.basename(renamed_file))
            item.setData(Qt.ItemDataRole.UserRole, renamed_file)
            self.file_list.addItem(item)
        
        # Add back any non-media files (they weren't renamed) with proper item data
        for non_media in original_non_media:
            self.files.append(non_media)
            item = QListWidgetItem(os.path.basename(non_media))
            item.setData(Qt.ItemDataRole.UserRole, non_media)
            self.file_list.addItem(item)
            # Preserve original tracking for non-media files too
            if non_media not in self.original_filenames:
                self.original_filenames[non_media] = os.path.basename(non_media)
        
        # Enable undo button if we have any rename tracking
        # Enable undo button if there are files that can be restored to different names
        if renamed_files and any(os.path.basename(current) != original for current, original in self.original_filenames.items()):
            self.undo_button.setEnabled(True)
        
        # Show results
        if errors:
            # Show detailed error report
            error_dialog = QDialog(self)
            error_dialog.setWindowTitle("Rename Results")
            error_layout = QVBoxLayout(error_dialog)
            
            success_label = QLabel(f"Successfully renamed: {len(renamed_files)} files")
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
            QMessageBox.information(self, "Success", f"All files renamed successfully!\n{len(renamed_files)} files processed.")
        
        # Update preview and status
        self.update_preview()
        self.status.showMessage(f"Completed: {len(renamed_files)} files renamed", 5000)
        
        # Re-enable UI
        self.rename_button.setEnabled(True)
        self.rename_button.setText("🚀 Rename Files")
        self.select_files_menu_button.setEnabled(True)
        self.select_folder_menu_button.setEnabled(True)
        self.clear_files_menu_button.setEnabled(True)
    
    def on_rename_error(self, error_message):
        """Handle critical error during rename operation"""
        QMessageBox.critical(self, "Critical Error", f"Unexpected error during renaming:\n{error_message}")
        self.status.showMessage("Rename operation failed", 3000)
        
        # Re-enable UI
        self.rename_button.setEnabled(True)
        self.rename_button.setText("🚀 Rename Files")
    
    def undo_rename_action(self):
        """Restore files to their original names"""
        if not self.original_filenames:
            QMessageBox.information(
                self, 
                "No Undo Available", 
                "No rename operations to undo.\n\nThe undo function is only available when:\n"
                "• Files have been renamed in this session\n"
                "• The file list hasn't been cleared\n"
                "• No new files have been loaded"
            )
            return
        
        # Check which files actually need to be undone (current name != original name)
        files_to_undo = []
        for current_file, original_filename in self.original_filenames.items():
            current_filename = os.path.basename(current_file)
            if current_filename != original_filename and current_file in self.files:
                files_to_undo.append((current_file, original_filename))
        
        if not files_to_undo:
            QMessageBox.information(
                self, 
                "No Changes to Undo", 
                "All files are already using their original names."
            )
            return
        
        # Confirm undo operation
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
        
        # Perform undo operation
        restored_files = []
        errors = []
        
        for current_file, original_filename in files_to_undo:
            try:
                if os.path.exists(current_file):
                    # CRITICAL FIX: Only restore filename, never move between directories
                    current_directory = os.path.dirname(current_file)
                    target_path = os.path.join(current_directory, original_filename)
                    
                    # Check if target name already exists
                    if os.path.exists(target_path) and target_path != current_file:
                        errors.append(f"Cannot restore {os.path.basename(current_file)}: Target name already exists")
                        continue
                    
                    os.rename(current_file, target_path)
                    restored_files.append(target_path)
                    
                    # Update our file list
                    if current_file in self.files:
                        index = self.files.index(current_file)
                        self.files[index] = target_path
                        # Update the list item with proper data
                        item = self.file_list.item(index)
                        item.setText(os.path.basename(target_path))
                        item.setData(Qt.ItemDataRole.UserRole, target_path)
                    
                else:
                    errors.append(f"File not found: {os.path.basename(current_file)}")
                    
            except Exception as e:
                errors.append(f"Failed to restore {os.path.basename(current_file)}: {e}")
        
        # CRITICAL FIX: Clear original_filenames tracking after successful undo
        # This allows a fresh start for the next rename operation
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
        
        # Update status and disable undo button after successful undo
        self.status.showMessage(f"Restored {len(restored_files)} files to original names", 5000)
        
        # Re-enable UI
        self.undo_button.setText("↶ Restore Original Names")
        self.undo_button.setEnabled(False)  # Disable after successful undo
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
        """Show interactive preview help dialog"""
        dialog = QDialog(self)
        dialog.setWindowTitle("Interactive Preview Help")
        dialog.setModal(True)
        dialog.resize(400, 300)
        layout = QVBoxLayout(dialog)
        
        info_text = QLabel("""
Interactive Preview shows how your filenames will look.

You can:
• Drag and drop components to reorder them
• See real-time preview of your filename format
• Components are separated by your chosen divider

The number (001) is always at the end and auto-increments.
        """)
        info_text.setWordWrap(True)
        layout.addWidget(info_text)
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)
        dialog.exec()

    # Drag and drop implementation
    def dragEnterEvent(self, event: QDragEnterEvent):
        """Handle drag enter events"""
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dragMoveEvent(self, event: QDragMoveEvent):
        """Handle drag move events"""
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent):
        """Handle drop events"""
        files = []
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            if os.path.isfile(file_path) and is_media_file(file_path):
                files.append(file_path)
            elif os.path.isdir(file_path):
                # Scan directory for media files
                media_files = scan_directory_recursive(file_path)
                files.extend(media_files)
        
        if files:
            self.add_files_to_list(files)
        event.accept()
    
    def add_files_to_list(self, files):
        """Add files to the file list"""
        # Clear existing files when adding new ones
        if files and self.files:
            self.clear_file_list()
        
        # Remove placeholder if present
        if self.file_list.count() == 1:
            item = self.file_list.item(0)
            if item and item.text() == "Drop files here or click 'Select Files' to begin":
                self.file_list.clear()
        
        # Validate and add files
        added_count = 0
        inaccessible_files = []
        
        for file in files:
            if is_media_file(file) and os.path.exists(file):
                if file not in self.files:
                    self.files.append(file)
                    item = QListWidgetItem(file)
                    item.setData(Qt.ItemDataRole.UserRole, file)
                    self.file_list.addItem(item)
                    added_count += 1
            else:
                inaccessible_files.append(file)
        
        # Show warning for inaccessible files
        if inaccessible_files:
            QMessageBox.warning(
                self, 
                "Inaccessible Files", 
                f"Some files could not be accessed:\n" + "\n".join(inaccessible_files[:5])
            )
        
        # Update status
        if added_count > 0:
            self.status.showMessage(f"Added {added_count} files", 3000)
        
        # Update preview and extract camera info when files are added
        self.update_preview()
        self.extract_camera_info()  # This will call update_camera_lens_labels() at the end
        self.update_file_statistics()
        
        # CRITICAL FIX: Enable rename button when files are present
        # This ensures the button is properly enabled after clearing and adding new files
        self.rename_button.setEnabled(len(self.files) > 0)
    
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
    
    def check_and_show_exiftool_warning(self):
        """Check if ExifTool warning should be shown and display it"""
        # Show warning if ExifTool is not available (regardless of Pillow status)
        exiftool_available = EXIFTOOL_AVAILABLE and self.exiftool_path
        
        if not exiftool_available:
            settings = QSettings()
            show_warning = settings.value("show_exiftool_warning", True, type=bool)
            
            if show_warning:
                dialog = ExifToolWarningDialog(self, self.exif_method)
                dialog.exec()
                
                if not dialog.should_show_again():
                    settings.setValue("show_exiftool_warning", False)


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
