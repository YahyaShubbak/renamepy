#!/usr/bin/env python3
"""
Main Window UI Setup.
Separates the UI construction from the main application logic.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QLineEdit, QCheckBox, QComboBox, QListWidget, QStyle
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon, QAction

from ..ui_components import InteractivePreviewWidget, CollapsibleSection

class MainWindowUI:
    """
    Handles the setup of the Main Window UI.
    """
    
    def setup_ui(self, window):
        """
        Constructs the UI for the given window.
        
        Args:
            window: The FileRenamerApp instance.
        """
        # Set basic window properties
        window.setWindowTitle("File Renamer")
        window.setGeometry(100, 100, 940, 760)
        
        # Set application icon
        # (Logic moved from main_application.py)
        # ...
        
        # Central Widget
        window.central_widget = QWidget()
        window.setCentralWidget(window.central_widget)
        window.layout = QVBoxLayout(window.central_widget)
        # A modest inset rather than content running edge-to-edge. Kept
        # small deliberately: the menu bar above is a native QMainWindow
        # menu bar and always spans the full window width regardless of
        # this margin (that's fixed Qt/OS behavior, same as any desktop
        # app) - a large margin here creates a visible, disconnected-
        # looking gap directly under it.
        window.layout.setContentsMargins(14, 8, 14, 10)
        
        # Top bar (theme selector) - full width, stays compact at the top
        window.top_layout = QVBoxLayout()
        window.layout.addLayout(window.top_layout)
        
        # Workspace: file area (left, grows to fill space) + naming options
        # panel (right, fixed width). Splitting these into separate columns
        # is what stops the file list from either overflowing or leaving a
        # huge empty box - each column only takes the space its own content
        # actually needs.
        workspace_layout = QHBoxLayout()
        window.layout.addLayout(workspace_layout, 1)
        
        window.left_layout = QVBoxLayout()
        workspace_layout.addLayout(window.left_layout, 1)
        
        right_container = QWidget()
        right_container.setMaximumWidth(360)
        window.right_layout = QVBoxLayout(right_container)
        window.right_layout.setContentsMargins(0, 0, 0, 0)
        workspace_layout.addWidget(right_container, 0, Qt.AlignmentFlag.AlignTop)
        
        # Advanced options: continuous counter, EXIF date sync, leave-names-
        # as-is, save-original-to-metadata. These are used far less often
        # than date/prefix/separator but previously sat visually equal to
        # them - collapsing them here cuts the always-visible surface
        # roughly in half without removing any capability. Created here so
        # _setup_options/_setup_checkboxes (called below) can populate it;
        # it's only inserted into right_layout after all the "basic" right-
        # column content below, so it appears last regardless of when its
        # own content is added.
        window.advanced_section = CollapsibleSection("Advanced options")
        
        # Bottom bar (Rename/Restore) - full width, sticky at the bottom
        window.bottom_layout = QVBoxLayout()
        window.layout.addLayout(window.bottom_layout)
        
        # Setup Menu Bar
        self._setup_menu_bar(window)
        
        # Setup Theme Selector
        self._setup_theme_selector(window)
        
        # Setup File Selection Buttons
        self._setup_file_selection_buttons(window)
        
        # Setup Options (Date, Counter, etc.)
        self._setup_options(window)
        
        # Setup Input Fields (Prefix, Additional, Separator)
        self._setup_input_fields(window)
        
        # Setup Preview
        self._setup_preview(window)
        
        # Setup Checkboxes (Camera, Lens, Sync)
        self._setup_checkboxes(window)
        
        # Advanced options section goes last in the right column
        window.right_layout.addWidget(window.advanced_section)
        window.right_layout.addStretch()
        
        # Setup File List
        self._setup_file_list(window)
        
        # Setup Action Buttons (Rename, Undo)
        self._setup_action_buttons(window)
        
        # Setup Status Bar
        window.status = window.statusBar()
        window.exif_status_label = QLabel()
        window.status.addPermanentWidget(window.exif_status_label)

    def _setup_menu_bar(self, window):
        if not hasattr(window, 'menuBar'):
            return
            
        mb = window.menuBar()
        if mb:
            tools_menu = None
            for a in mb.actions():
                if a.text() == '&Tools':
                    tools_menu = a.menu()
                    break
            if tools_menu is None:
                tools_menu = mb.addMenu('&Tools')

            # Debug logging toggle
            window.action_toggle_debug = QAction('Enable Debug Logging', window, checkable=True)
            window.action_toggle_debug.setStatusTip('Toggle verbose debug log output')
            window.action_toggle_debug.toggled.connect(window._on_toggle_debug_logging)
            tools_menu.addAction(window.action_toggle_debug)
            
            # EXIF Time Shift
            tools_menu.addSeparator()
            window.action_time_shift = QAction('⏰ EXIF Time Shift...', window)
            window.action_time_shift.setStatusTip('Adjust EXIF timestamps when camera clock was set incorrectly')
            window.action_time_shift.triggered.connect(window.show_time_shift_dialog)
            tools_menu.addAction(window.action_time_shift)

    def _setup_theme_selector(self, window):
        theme_row = QHBoxLayout()
        theme_label = QLabel("Theme:")
        window.theme_combo = QComboBox()
        window.theme_combo.addItems(["System", "Light", "Dark"])
        window.theme_combo.setCurrentText("System")
        window.theme_combo.currentTextChanged.connect(window.on_theme_changed)
        theme_row.addWidget(theme_label)
        theme_row.addWidget(window.theme_combo)
        theme_row.addStretch()
        window.top_layout.addLayout(theme_row)

    def _setup_file_selection_buttons(self, window):
        file_menu_row = QHBoxLayout()
        file_menu_row.setSpacing(10)
        
        # Select Files
        window.select_files_menu_button = QPushButton("📄 Select Media Files")
        window.select_files_menu_button.setStyleSheet("""
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
        # Callback connected later in main_application.py
        
        # Select Folder
        window.select_folder_menu_button = QPushButton("📁 Select Folder")
        window.select_folder_menu_button.setStyleSheet("""
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
        # Callback connected later in main_application.py
        
        # Clear Files
        window.clear_files_menu_button = QPushButton("🗑️ Clear Files")
        window.clear_files_menu_button.setStyleSheet("""
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
        # Callback connected later in main_application.py
        
        file_menu_row.addWidget(window.select_files_menu_button)
        file_menu_row.addWidget(window.select_folder_menu_button)
        file_menu_row.addWidget(window.clear_files_menu_button)
        file_menu_row.addStretch()
        window.left_layout.addLayout(file_menu_row)

    def _setup_options(self, window):
        # Date options
        date_options_row = QHBoxLayout()
        window.checkbox_date = QCheckBox("Include date in filename")
        window.checkbox_date.setChecked(True)
        window.checkbox_date.stateChanged.connect(window.update_preview)
        
        date_format_label = QLabel("Date Format:")
        window.date_format_combo = QComboBox()
        window.date_format_combo.addItems([
            "YYYY-MM-DD", "YYYY_MM_DD", "DD-MM-YYYY", "DD_MM_YYYY", 
            "YYYYMMDD", "MM-DD-YYYY", "MM_DD_YYYY"
        ])
        window.date_format_combo.setCurrentText("YYYY-MM-DD")
        window.date_format_combo.currentTextChanged.connect(window.update_preview)
        
        date_options_row.addWidget(window.checkbox_date)
        date_options_row.addWidget(date_format_label)
        date_options_row.addWidget(window.date_format_combo)
        date_options_row.addStretch()
        window.right_layout.addLayout(date_options_row)

        # Continuous Counter
        continuous_counter_row = QHBoxLayout()
        window.checkbox_continuous_counter = QCheckBox("Continuous counter for vacation/multi-day shoots")
        window.checkbox_continuous_counter.setChecked(False)
        window.checkbox_continuous_counter.setToolTip(
            "Enable for vacation scenarios where you want continuous numbering across dates:\n"
            "• Day 1: 2025-07-20_001, 2025-07-20_002, 2025-07-20_003\n"
            "• Day 2: 2025-07-21_004, 2025-07-21_005, 2025-07-21_006\n"
            "Instead of restarting at 001 each day"
        )
        window.checkbox_continuous_counter.stateChanged.connect(window.on_continuous_counter_changed)
        
        continuous_counter_row.addWidget(window.checkbox_continuous_counter)
        continuous_counter_row.addStretch()
        window.advanced_section.addLayout(continuous_counter_row)

    def _setup_input_fields(self, window):
        # Camera Prefix
        camera_row = QHBoxLayout()
        camera_label = QLabel("Camera Prefix:")
        camera_info = QLabel()
        camera_info.setPixmap(window.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxInformation).pixmap(16, 16))
        camera_info.setToolTip("Click for detailed info about camera prefix")
        camera_info.setCursor(Qt.CursorShape.PointingHandCursor)
        camera_info.mousePressEvent = lambda event: window.show_camera_prefix_info()
        camera_row.addWidget(camera_label)
        camera_row.addWidget(camera_info)
        camera_row.addStretch()
        window.right_layout.addLayout(camera_row)
        
        window.camera_prefix_entry = QLineEdit()
        window.camera_prefix_entry.setPlaceholderText("e.g. A7R3, D850")
        window.camera_prefix_entry.textChanged.connect(window.validate_and_update_preview)
        window.right_layout.addWidget(window.camera_prefix_entry)

        # Additional
        additional_row = QHBoxLayout()
        additional_label = QLabel("Additional:")
        additional_info = QLabel()
        additional_info.setPixmap(window.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxInformation).pixmap(16, 16))
        additional_info.setToolTip("Click for detailed info about additional field")
        additional_info.setCursor(Qt.CursorShape.PointingHandCursor)
        additional_info.mousePressEvent = lambda event: window.show_additional_info()
        additional_row.addWidget(additional_label)
        additional_row.addWidget(additional_info)
        additional_row.addStretch()
        window.right_layout.addLayout(additional_row)
        
        window.additional_entry = QLineEdit()
        window.additional_entry.setPlaceholderText("e.g. vacation, wedding")
        window.additional_entry.textChanged.connect(window.validate_and_update_preview)
        window.right_layout.addWidget(window.additional_entry)

        # Separator
        separator_row = QHBoxLayout()
        separator_label = QLabel("Separator:")
        separator_info = QLabel()
        separator_info.setPixmap(window.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxInformation).pixmap(16, 16))
        separator_info.setToolTip("Click for detailed info about separators")
        separator_info.setCursor(Qt.CursorShape.PointingHandCursor)
        separator_info.mousePressEvent = lambda event: window.show_separator_info()
        separator_row.addWidget(separator_label)
        separator_row.addWidget(separator_info)
        separator_row.addStretch()
        window.right_layout.addLayout(separator_row)
        
        window.separator_combo = QComboBox()
        window.separator_combo.addItems(["-", "_", ""])
        window.separator_combo.setCurrentText("-")
        window.right_layout.addWidget(window.separator_combo)
        window.separator_combo.currentIndexChanged.connect(window.update_preview)
        window.separator_combo.currentIndexChanged.connect(window.on_separator_changed)

    def _setup_preview(self, window):
        preview_row = QHBoxLayout()
        preview_label = QLabel("Interactive Preview:")
        preview_info = QLabel()
        preview_info.setPixmap(window.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxInformation).pixmap(16, 16))
        preview_info.setToolTip("Click for detailed info about interactive preview")
        preview_info.setCursor(Qt.CursorShape.PointingHandCursor)
        preview_info.mousePressEvent = lambda event: window.show_preview_info()
        preview_row.addWidget(preview_label)
        preview_row.addWidget(preview_info)
        preview_row.addStretch()
        window.bottom_layout.addLayout(preview_row)
        
        window.interactive_preview = InteractivePreviewWidget()
        window.interactive_preview.order_changed.connect(window.on_preview_order_changed)
        window.bottom_layout.addWidget(window.interactive_preview)

    def _setup_checkboxes(self, window):
        # Camera
        camera_checkbox_layout = QHBoxLayout()
        window.checkbox_camera = QCheckBox("Include camera model in filename")
        window.camera_model_label = QLabel("(detecting...)")
        window.camera_model_label.setStyleSheet("color: gray; font-style: italic;")
        camera_checkbox_layout.addWidget(window.checkbox_camera)
        camera_checkbox_layout.addWidget(window.camera_model_label)
        camera_checkbox_layout.addStretch()
        window.right_layout.addLayout(camera_checkbox_layout)
        window.checkbox_camera.stateChanged.connect(window.on_camera_checkbox_changed)
        
        # Lens
        lens_checkbox_layout = QHBoxLayout()
        window.checkbox_lens = QCheckBox("Include lens in filename")
        window.lens_model_label = QLabel("(detecting...)")
        window.lens_model_label.setStyleSheet("color: gray; font-style: italic;")
        lens_checkbox_layout.addWidget(window.checkbox_lens)
        lens_checkbox_layout.addWidget(window.lens_model_label)
        lens_checkbox_layout.addStretch()
        window.right_layout.addLayout(lens_checkbox_layout)
        window.checkbox_lens.stateChanged.connect(window.on_lens_checkbox_changed)

        # Shooting settings (ISO, Aperture, Shutter, Focal Length) - resolved
        # per-file at rename time rather than from a single detected value,
        # since these vary shot to shot (see BOOLEAN_META_KEYS in
        # filename_components.py). Disabled until we know the field is
        # actually present in the loaded files' EXIF data - see
        # FileRenamerApp.extract_camera_info()/update_shooting_settings_labels().
        window.shooting_setting_checkboxes = {}
        window.shooting_setting_labels = {}
        shooting_settings = [
            ("iso", "Include ISO in filename"),
            ("aperture", "Include aperture in filename"),
            ("shutter", "Include shutter speed in filename"),
            ("focal_length", "Include focal length in filename"),
        ]
        for key, label_text in shooting_settings:
            row = QHBoxLayout()
            checkbox = QCheckBox(label_text)
            checkbox.setEnabled(False)
            value_label = QLabel("(no files selected)")
            value_label.setStyleSheet("color: gray; font-style: italic;")
            row.addWidget(checkbox)
            row.addWidget(value_label)
            row.addStretch()
            window.right_layout.addLayout(row)
            checkbox.stateChanged.connect(
                lambda _state, k=key: window.on_shooting_setting_checkbox_changed(k)
            )
            window.shooting_setting_checkboxes[key] = checkbox
            window.shooting_setting_labels[key] = value_label

        # EXIF Sync
        sync_date_layout = QHBoxLayout()
        window.checkbox_sync_exif_date = QCheckBox("Sync EXIF date to file creation date")
        window.checkbox_sync_exif_date.setStyleSheet("""
            QCheckBox {
                color: #ff6b35;
                font-weight: bold;
            }
            QCheckBox::indicator:checked {
                background-color: #ff6b35;
                border: 2px solid #e55a2b;
            }
        """)
        window.checkbox_sync_exif_date.setToolTip(
            "⚠️ WARNING: This will modify file metadata!\n\n"
            "• Extracts DateTimeOriginal from EXIF\n"
            "• Sets it as file creation/modification date\n"
            "• Useful for cloud services that use file dates\n"
            "• Can be undone with restore function\n\n"
            "Only works if ExifTool is available."
        )
        sync_date_layout.addWidget(window.checkbox_sync_exif_date)
        
        sync_info_icon = QLabel()
        sync_info_icon.setPixmap(window.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxWarning).pixmap(16, 16))
        sync_info_icon.setToolTip("Click for detailed info about EXIF date synchronization")
        sync_info_icon.setCursor(Qt.CursorShape.PointingHandCursor)
        sync_info_icon.mousePressEvent = lambda event: window.show_exif_sync_info()
        sync_date_layout.addWidget(sync_info_icon)
        
        window.checkbox_leave_names = QCheckBox("Leave file names as-is")
        window.checkbox_leave_names.setToolTip(
            "Skip renaming and only perform timestamp (and future metadata) operations.\n"
            "Useful when you only want to normalize filesystem dates without changing filenames."
        )
        sync_date_layout.addWidget(window.checkbox_leave_names)
        
        window.checkbox_save_original_to_exif = QCheckBox("Save original filename to metadata")
        window.checkbox_save_original_to_exif.setStyleSheet("""
            QCheckBox {
                color: #4CAF50;
                font-weight: bold;
            }
            QCheckBox::indicator:checked {
                background-color: #4CAF50;
                border: 2px solid #45a049;
            }
        """)
        window.checkbox_save_original_to_exif.setToolTip(
            "💾 Persistent Undo Feature\n\n"
            "Saves the original filename in EXIF metadata before renaming.\n\n"
            "Benefits:\n"
            "• Undo renames even after closing the application\n"
            "• Each file carries its own rename history\n"
            "• View original filename in EXIF info dialog\n"
            "• Works with all image formats (JPEG, RAW, etc.)\n\n"
            "⚠️ Performance Note:\n"
            "Adds ~50-200ms per file to rename time.\n"
            "With 100+ files, this can add 5-20 seconds.\n\n"
            "Note: Requires ExifTool. Original filename is stored in\n"
            "EXIF UserComment field."
        )
        sync_date_layout.addWidget(window.checkbox_save_original_to_exif)
        
        sync_date_layout.addStretch()
        window.advanced_section.addLayout(sync_date_layout)

    def _setup_file_list(self, window):
        window.file_list = QListWidget()
        window.file_list.setStyleSheet("""
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
        
        window.left_layout.addWidget(window.file_list)
        window.file_list.itemDoubleClicked.connect(window.show_selected_exif)
        window.file_list.itemClicked.connect(window.show_media_info)
        
        # Right-click menu as a discoverable alternative to the single/
        # double-click gestures below, which aren't obvious without the
        # hint label or tooltip being read first.
        window.file_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        window.file_list.customContextMenuRequested.connect(window.show_file_list_context_menu)
        
        # File Statistics
        window.file_stats_label = QLabel()
        window.file_stats_label.setStyleSheet("""
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
        window.file_stats_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        window.file_stats_label.setWordWrap(True)
        window.left_layout.addWidget(window.file_stats_label)
        
        # Info Label
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
        window.left_layout.addWidget(file_list_info)
        
        window.file_list.setToolTip("Single click: Media info | Double click: Essential metadata")
        window.file_list.installEventFilter(window)
        window.setAcceptDrops(True)

    def _setup_action_buttons(self, window):
        # Rename Button
        window.rename_button = QPushButton("🚀 Rename Files")
        window.rename_button.setStyleSheet("""
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
                background-color: #cccccc;
                color: #666666;
            }
        """)
        window.rename_button.clicked.connect(window.rename_files_action)
        window.rename_button.setEnabled(False)
        window.bottom_layout.addWidget(window.rename_button)
        
        # Undo Button
        window.undo_button = QPushButton("↶ Restore Original Names")
        window.undo_button.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 6px;
                font-weight: bold;
                margin-top: 5px;
            }
            QPushButton:hover {
                background-color: #5a6268;
            }
            QPushButton:pressed {
                background-color: #545b62;
            }
            QPushButton:disabled {
                background-color: #e2e6ea;
                color: #adb5bd;
            }
        """)
        window.undo_button.clicked.connect(window.undo_rename_action)
        window.undo_button.setEnabled(False)
        window.bottom_layout.addWidget(window.undo_button)
