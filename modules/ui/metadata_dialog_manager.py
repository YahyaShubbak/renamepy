#!/usr/bin/env python3
"""
Metadata Dialog Manager - the single-click status-bar media info, and the
double-click "Essential Metadata" dialog (with camera/lens/EXIF checkboxes
for filename inclusion, and the full-metadata toggle view).

Extracted from main_application.py, which previously implemented this
~600-line, fully self-contained feature directly as instance methods
(FileRenamerApp had grown to nearly 2000 lines). This follows the exact
same parent-delegation pattern already established by FileListManager,
PreviewGenerator, and UndoHandler: FileRenamerApp still exposes every one
of these method names (now as one-line delegates), so nothing that wires
Qt signals to them (see main_window_ui.py) needed to change.

Scratch state that's local to a single open dialog (show_full_button,
full_metadata_widget, dialog_layout) lives on this manager instance rather
than on FileRenamerApp - verified via a full-codebase search that nothing
outside this cluster ever read those attributes directly.
"""
from __future__ import annotations

import os

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QCheckBox,
    QDialog, QPlainTextEdit, QScrollArea, QMenu,
)
from PyQt6.QtCore import Qt

from ..file_utilities import is_media_file, is_video_file
from ..exif_service_new import EXIFTOOL_AVAILABLE
from ..handlers import extract_image_number
from ..exif_undo_manager import get_rename_info


class MetadataDialogManager:
    """Handles media-info display: status-bar summary on single click, and
    the full EXIF metadata dialog on double click, including the
    essential-metadata view with filename-inclusion checkboxes.
    """

    def __init__(self, parent):
        self.parent = parent
        # Per-dialog scratch state (see module docstring for why this
        # lives here rather than on FileRenamerApp).
        self.show_full_button = None
        self.full_metadata_widget = None
        self.dialog_layout = None

    def show_context_menu(self, position):
        """Right-click menu on a file list item.

        Single-click (status bar info) and double-click (full metadata
        dialog) are the primary gestures, but neither has a strong visual
        affordance - a person has to already know they exist, or read the
        small hint label under the list, to find them. A right-click menu
        is a much more standard, discoverable way to expose the same
        actions explicitly.
        """
        item = self.parent.file_list.itemAt(position)
        if item is None:
            return
        file_path = item.data(Qt.ItemDataRole.UserRole)
        if not file_path:
            return

        menu = QMenu(self.parent)
        view_action = menu.addAction("🔍 View Full Metadata...")
        info_action = menu.addAction("ℹ Show Quick Info")
        chosen = menu.exec(self.parent.file_list.mapToGlobal(position))

        if chosen == view_action:
            self.show_selected_exif(item)
        elif chosen == info_action:
            self.show_media_info(item)

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
                self.parent.log(f"show_media_info: File not found: {normalized_path}")
                return
            
            if is_video_file(file_path):
                # For videos, try to extract duration info
                if EXIFTOOL_AVAILABLE and self.parent.exiftool_path:
                    raw_exif_data = self.parent.exif_service.extract_raw_exif(normalized_path)
                    if raw_exif_data:
                        # Try to get video duration or frame count
                        duration_fields = ['QuickTime:Duration', 'Track1:MediaDuration', 'Duration', 'EXIF:Duration']
                        frame_fields = ['VideoFrameCount', 'FrameCount', 'TotalFrames']
                        
                        found_info = False
                        for field in duration_fields:
                            if field in raw_exif_data and raw_exif_data[field]:
                                duration = raw_exif_data[field]
                                self.parent.status.showMessage(f"Video Duration: {duration}", 5000)
                                found_info = True
                                break
                        
                        if not found_info:
                            for field in frame_fields:
                                if field in raw_exif_data and raw_exif_data[field]:
                                    frame_count = raw_exif_data[field]
                                    self.parent.status.showMessage(f"Video Frame Count: {frame_count}", 5000)
                                    found_info = True
                                    break
                        
                        if not found_info:
                            self.parent.status.showMessage("Video metadata available - double click for details", 3000)
                    else:
                        self.parent.status.showMessage("No video metadata found", 3000)
                else:
                    self.parent.status.showMessage("Video files require ExifTool for metadata extraction", 3000)
            else:
                # For images, extract image number
                image_number = extract_image_number(file_path, self.parent.exif_method, self.parent.exiftool_path)
                
                if image_number:
                    self.parent.status.showMessage(f"Image Number/Shutter Count: {image_number}", 5000)
                else:
                    self.parent.status.showMessage("Image number not found in EXIF data", 3000)
                
        except Exception as e:
            self.parent.status.showMessage(f"Error reading media metadata: {e}", 3000)
    
    def show_selected_exif(self, item):
        """Show EXIF data dialog on double click"""
        file_path = item.data(Qt.ItemDataRole.UserRole)
        if file_path and is_media_file(file_path):
            self.show_exif_info(file_path)
    
    def show_exif_info(self, file_path):
        """Show complete EXIF information in a dialog"""
        if not self.parent.exif_method:
            file_type = "Video" if is_video_file(file_path) else "Image"
            self.show_exif_dialog(file_path, f"No metadata support available for {file_type.lower()} files.")
            return
        
        try:
            # Normalize path to prevent double backslashes
            normalized_file = os.path.normpath(file_path)
            
            # Verify file exists
            if not os.path.exists(normalized_file):
                self.parent.log(f"show_exif_info: File not found: {normalized_file}")
                self.show_exif_dialog(file_path, "File not found.")
                return
            
            # Extract raw EXIF data using direct function
            if self.parent.exif_method == "exiftool" and self.parent.exiftool_path:
                raw_exif_data = self.parent.exif_service.extract_raw_exif(normalized_file)
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
            self.parent.log(f"Error in show_exif_info: {e}")
            file_type = "Video" if is_video_file(file_path) else "Image"
            self.show_exif_dialog(file_path, f"Error reading {file_type.lower()} metadata: {e}")
    
    def show_exif_dialog(self, file_path, info_str):
        """Show detailed EXIF metadata dialog with two-stage display and checkboxes for filename inclusion"""
        file_type = "Video" if is_video_file(file_path) else "Image"
        
        # Parse the full metadata to extract essential information
        essential_info = self.extract_essential_metadata(info_str, file_path)
        
        dialog = QDialog(self.parent)
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
                if metadata_key:
                    is_selected = metadata_key in self.parent.selected_metadata
                    
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
        if self.parent.exiftool_path:
            rename_info = get_rename_info(file_path, self.parent.exiftool_path)
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
        camera_checked = self.parent.checkbox_camera.isChecked() or ('camera' in self.parent.selected_metadata)
        lens_checked = self.parent.checkbox_lens.isChecked() or ('lens' in self.parent.selected_metadata)
        
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
        if checked:
            # SIMPLIFIED FIX: Store boolean flags instead of placeholders
            # This tells the rename engine which metadata types to extract
            if metadata_key in ['aperture', 'iso', 'focal_length', 'shutter', 'shutter_speed', 'exposure_bias']:
                # For EXIF metadata, store True to indicate extraction needed
                self.parent.selected_metadata[metadata_key] = True
            else:
                # For camera/lens, store the actual value (these are typically the same for all files)
                self.parent.selected_metadata[metadata_key] = value
        else:
            self.parent.selected_metadata.pop(metadata_key, None)
        
        # Only synchronize with main window checkboxes if this is a user action
        # This prevents automatic sync when dialog is reopened with existing selected_metadata
        if user_action:
            if metadata_key == 'camera':
                self.parent.checkbox_camera.setChecked(checked)
            elif metadata_key == 'lens':
                self.parent.checkbox_lens.setChecked(checked)
        
        # Update preview to show new filename format immediately
        self.parent.update_preview()
    
    def on_camera_checkbox_changed(self):
        """Handle camera checkbox changes and sync with metadata"""
        checked = self.parent.checkbox_camera.isChecked()
        
        # Update selected_metadata first - BEFORE updating preview
        if checked:
            # Only add if we have valid camera info and it's not already there
            camera_info = self.parent.camera_model_label.text()
            # Remove parentheses if present (e.g., "(ILCE-7CM2)" -> "ILCE-7CM2")
            if camera_info.startswith('(') and camera_info.endswith(')'):
                camera_info = camera_info[1:-1]
            
            if camera_info and camera_info not in ["detecting...", "not detected", "no files selected"] and 'camera' not in self.parent.selected_metadata:
                self.parent.selected_metadata['camera'] = camera_info
        else:
            # Remove camera from selected metadata when checkbox is unchecked
            if 'camera' in self.parent.selected_metadata:
                self.parent.selected_metadata.pop('camera', None)
        
        # Now update preview with the corrected metadata
        self.parent.update_preview()
    
    def on_lens_checkbox_changed(self):
        """Handle lens checkbox changes and sync with metadata"""
        checked = self.parent.checkbox_lens.isChecked()
        
        # Update selected_metadata first - BEFORE updating preview
        if checked:
            # Only add if we have valid lens info and it's not already there
            lens_info = self.parent.lens_model_label.text()
            # Remove parentheses if present (e.g., "(FE-20-70mm-F4-G)" -> "FE-20-70mm-F4-G")
            if lens_info.startswith('(') and lens_info.endswith(')'):
                lens_info = lens_info[1:-1]
            
            if lens_info and lens_info not in ["detecting...", "not detected", "no files selected"] and 'lens' not in self.parent.selected_metadata:
                self.parent.selected_metadata['lens'] = lens_info
        else:
            # Remove lens from selected metadata when checkbox is unchecked
            if 'lens' in self.parent.selected_metadata:
                self.parent.selected_metadata.pop('lens', None)
        
        # Now update preview with the corrected metadata
        self.parent.update_preview()
    
    def on_shooting_setting_checkbox_changed(self, key):
        """Handle ISO/Aperture/Shutter/Focal Length checkbox changes.

        Unlike camera/lens (a single value shared across the batch), these
        vary shot to shot, so we store a boolean flag rather than a fixed
        value - the actual value is resolved per file at rename time (see
        BOOLEAN_META_KEYS in filename_components.py, which already handles
        'iso', 'aperture', 'shutter', 'focal_length' this way).
        """
        checkbox = self.parent.shooting_setting_checkboxes[key]
        checked = checkbox.isChecked()
        self.on_metadata_checkbox_changed(key, True, checked, user_action=True)
    
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
    
