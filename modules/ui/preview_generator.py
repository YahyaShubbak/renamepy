"""
Preview Generator - Handles filename preview generation and updates
Extracted from main_application.py to improve code organization

This module manages the interactive preview widget and generates 
filename previews based on current settings.
"""

import os
import re
import datetime
from ..file_utilities import is_media_file, is_video_file
from ..exif_processor import get_selective_cached_exif_data, get_all_metadata


class PreviewGenerator:
    """
    Manages preview generation and display including:
    - Preview updates based on settings
    - EXIF data caching for preview
    - Metadata formatting for filenames
    - Component order management
    """
    
    def __init__(self, parent):
        """
        Initialize PreviewGenerator
        
        Args:
            parent: The parent FileRenamerApp instance
        """
        self.parent = parent
        # Initialize preview EXIF cache
        self._preview_exif_cache = {}
        self._preview_exif_file = None
    
    def update_preview(self):
        """Update the interactive preview widget with current settings"""
        # Get current settings
        camera_prefix = self.parent.camera_prefix_entry.text().strip()
        additional = self.parent.additional_entry.text().strip()
        use_camera = self.parent.checkbox_camera.isChecked()
        use_lens = self.parent.checkbox_lens.isChecked()
        use_date = self.parent.checkbox_date.isChecked()
        date_format = self.parent.date_format_combo.currentText()
        separator = self.parent.separator_combo.currentText()
        
        # Component management: Ensure custom_order reflects currently active components
        # This handles components being activated/deactivated
        active_components = []
        if use_date:
            active_components.append("Date")
        if camera_prefix:
            active_components.append("Prefix")
        if additional:
            active_components.append("Additional")
        if use_camera:
            active_components.append("Camera")
        if use_lens:
            active_components.append("Lens")
        active_components.append("Number")  # Always present
        
        # Add active metadata components
        if hasattr(self.parent, 'selected_metadata') and self.parent.selected_metadata:
            for meta_key in self.parent.selected_metadata.keys():
                active_components.append(f"Meta_{meta_key}")
        
        # Update custom_order: Add missing active components before "Number"
        for component in active_components:
            if component not in self.parent.custom_order:
                # Insert before Number for logical ordering
                if "Number" in self.parent.custom_order:
                    idx = self.parent.custom_order.index("Number")
                    self.parent.custom_order.insert(idx, component)
                else:
                    self.parent.custom_order.append(component)
        
        # Remove inactive components from custom_order
        self.parent.custom_order = [
            c for c in self.parent.custom_order 
            if c in active_components
        ]
        
        # Choose first JPG file, else first media file, else dummy
        preview_file = next((f for f in self.parent.files if os.path.splitext(f)[1].lower() in [".jpg", ".jpeg"]), None)
        if not preview_file:
            preview_file = next((f for f in self.parent.files if is_media_file(f)), None)
        if not preview_file and self.parent.files:
            preview_file = self.parent.files[0]
        if not preview_file:
            # Default example with video extension to show video support
            preview_file = "20250725_DSC0001.MP4"

        date_taken, camera_model, lens_model = self._extract_preview_metadata(
            preview_file, use_date, use_camera, use_lens
        )
        
        # Format date for display
        formatted_date = self._format_date(date_taken, date_format) if use_date and date_taken else None
        
        # Check if camera/lens are in selected_metadata to avoid duplicates
        has_camera_in_metadata = hasattr(self.parent, 'selected_metadata') and self.parent.selected_metadata and 'camera' in self.parent.selected_metadata
        has_lens_in_metadata = hasattr(self.parent, 'selected_metadata') and self.parent.selected_metadata and 'lens' in self.parent.selected_metadata
        
        # Build component mapping
        component_mapping = {
            "Date": formatted_date if use_date else None,
            "Prefix": camera_prefix if camera_prefix else None,
            "Additional": additional if additional else None,
            "Camera": camera_model if (use_camera and camera_model and not has_camera_in_metadata) else None,
            "Lens": lens_model if (use_lens and lens_model and not has_lens_in_metadata) else None,
            "Number": "001"
        }
        
        # Add selected metadata from metadata dialog
        if hasattr(self.parent, 'selected_metadata') and self.parent.selected_metadata:
            preview_metadata = self._get_preview_metadata(preview_file)
            
            for metadata_key, metadata_value in preview_metadata.items():
                # Skip if this metadata conflicts with main checkboxes
                if metadata_key == 'camera' and not use_camera:
                    continue
                if metadata_key == 'lens' and not use_lens:
                    continue
                
                display_value = self.format_metadata_for_filename(metadata_key, metadata_value)
                if display_value:
                    component_mapping[f"Meta_{metadata_key}"] = display_value
        
        # Build display components list
        display_components = self._build_display_components(component_mapping)
        
        # Update the interactive preview
        self.parent.log(f"🖼️ Debug: Setting preview components: {display_components}")
        self.parent.interactive_preview.set_separator(separator)
        self.parent.interactive_preview.set_components(display_components, "001")
    
    def _extract_preview_metadata(self, preview_file, use_date, use_camera, use_lens):
        """Extract metadata for preview file with caching"""
        date_taken = None
        camera_model = None
        lens_model = None
        
        if not self.parent.exif_method:
            # No EXIF support - use fallback values
            date_taken = "20250725"
            camera_model = "Camera" if use_camera else None
            lens_model = "Lens" if use_lens else None
        else:
            # EXIF cache: only extract if file changed
            cache_key = (preview_file, self.parent.exif_method, self.parent.exiftool_path)
            if os.path.exists(preview_file):
                if not hasattr(self, '_preview_exif_file') or self._preview_exif_file != cache_key:
                    try:
                        date_taken, camera_model, lens_model = get_selective_cached_exif_data(
                            preview_file, self.parent.exif_method, self.parent.exiftool_path,
                            need_date=use_date, need_camera=use_camera, need_lens=use_lens
                        )
                        self._preview_exif_cache = {
                            'date': date_taken,
                            'camera': camera_model,
                            'lens': lens_model,
                        }
                        self._preview_exif_file = cache_key
                    except Exception as e:
                        self._preview_exif_cache = {'date': None, 'camera': None, 'lens': None}
                else:
                    # Use cached values
                    date_taken = self._preview_exif_cache.get('date')
                    camera_model = self._preview_exif_cache.get('camera')
                    lens_model = self._preview_exif_cache.get('lens')
            
            # Fallback date extraction
            if not date_taken:
                date_taken = self._extract_fallback_date(preview_file)
            
            # Use fallback values for preview if not detected AND checkbox is enabled
            if use_camera and not camera_model:
                camera_model = "Camera"
            if use_lens and not lens_model:
                lens_model = "Lens"
            
            # Clear values if checkboxes are disabled
            if not use_camera:
                camera_model = None
            if not use_lens:
                lens_model = None
        
        return date_taken, camera_model, lens_model
    
    def _extract_fallback_date(self, preview_file):
        """Extract date from filename or file modification time"""
        m = re.search(r'(20\d{2})(\d{2})(\d{2})', os.path.basename(preview_file))
        if m:
            return f"{m.group(1)}{m.group(2)}{m.group(3)}"
        
        if os.path.exists(preview_file):
            mtime = os.path.getmtime(preview_file)
            dt = datetime.datetime.fromtimestamp(mtime)
            return dt.strftime('%Y%m%d')
        
        return "20250725"
    
    def _format_date(self, date_taken, date_format):
        """Format date for display using the selected format"""
        if not date_taken:
            return None
        
        year = date_taken[:4]
        month = date_taken[4:6]
        day = date_taken[6:8]
        
        format_map = {
            "YYYY-MM-DD": f"{year}-{month}-{day}",
            "YYYY_MM_DD": f"{year}_{month}_{day}",
            "DD-MM-YYYY": f"{day}-{month}-{year}",
            "DD_MM_YYYY": f"{day}_{month}_{year}",
            "YYYYMMDD": f"{year}{month}{day}",
            "MM-DD-YYYY": f"{month}-{day}-{year}",
            "MM_DD_YYYY": f"{month}_{day}_{year}",
        }
        
        return format_map.get(date_format, f"{year}-{month}-{day}")
    
    def _get_preview_metadata(self, preview_file):
        """Get metadata for preview file, extracting real values if needed"""
        preview_metadata = self.parent.selected_metadata.copy()
        
        if self.parent.exif_method and preview_file and os.path.exists(preview_file):
            needs_real_metadata = any(
                value is True for value in self.parent.selected_metadata.values()
            )
            
            if needs_real_metadata:
                try:
                    self.parent.log(f"🔍 Preview: Extracting real metadata from {os.path.basename(preview_file)}")
                    real_metadata = get_all_metadata(preview_file, self.parent.exif_method, self.parent.exiftool_path)
                    
                    # Replace Boolean flags with real values for preview
                    for key, value in self.parent.selected_metadata.items():
                        if value is True:
                            exif_key = key
                            if key == 'shutter' and 'shutter_speed' in real_metadata:
                                exif_key = 'shutter_speed'
                            
                            if exif_key in real_metadata:
                                preview_metadata[key] = real_metadata[exif_key]
                except Exception as e:
                    self.parent.log(f"❌ Warning: Could not extract real metadata for preview: {e}")
        
        return preview_metadata
    
    def _build_display_components(self, component_mapping):
        """Build ordered list of display components - follows custom_order exactly"""
        display_components = []
        
        # Simply iterate through custom_order and add components with values
        # No manipulation of order here - that's handled in update_preview()
        for component_name in self.parent.custom_order:
            value = component_mapping.get(component_name)
            if value:  # Only add non-empty and active components
                display_components.append(value)
        
        return display_components
    
    def format_metadata_for_filename(self, metadata_key, metadata_value):
        """Format metadata values for use in filenames"""
        if not metadata_value or metadata_value == 'Unknown':
            return None
        
        # Skip boolean flags
        if isinstance(metadata_value, bool):
            return None
        
        # Clean and format different metadata types
        formatters = {
            'camera': lambda v: v.replace(' ', '-').replace('/', '-'),
            'lens': lambda v: v.replace(' ', '-').replace('/', '-'),
            'date': lambda v: v.split(' ')[0].replace(':', '-') if ' ' in v else v.replace(':', '-'),
            'iso': lambda v: f"ISO{v}" if str(v).isdigit() else str(v).replace(' ', ''),
            'aperture': self._format_aperture,
            'shutter': self._format_shutter,
            'shutter_speed': self._format_shutter,
            'focal_length': self._format_focal_length,
            'resolution': self._format_resolution,
        }
        
        formatter = formatters.get(metadata_key)
        if formatter:
            return formatter(metadata_value)
        
        # General cleanup for other metadata
        return str(metadata_value).replace(' ', '-').replace('/', '-').replace(':', '-')
    
    def _format_aperture(self, value):
        """Format aperture value"""
        value = str(value)
        if value.startswith('f/'):
            return value.replace('f/', 'f')
        elif value.startswith('f'):
            return value
        else:
            return f"f{value}"
    
    def _format_shutter(self, value):
        """Format shutter speed value"""
        value = str(value)
        result = value.replace('/', '_').replace(' ', '')
        # Clean up double 's' if present
        if result.endswith('ss') and not result.endswith('sss'):
            result = result[:-1]
        return result
    
    def _format_focal_length(self, value):
        """Format focal length value"""
        value = str(value)
        match = re.search(r'(\d+)mm', value)
        if match:
            return f"{match.group(1)}mm"
        return value.replace(' ', '-')
    
    def _format_resolution(self, value):
        """Format resolution value"""
        value = str(value)
        if 'MP' in value:
            mp_part = value.split('(')[1].split(')')[0] if '(' in value else value
            return mp_part.replace(' ', '').replace('.', '-')
        return value.replace(' ', '-').replace('x', 'x')
    
    def validate_and_update_preview(self):
        """Validate input and update preview"""
        self.update_preview()
    
    def show_preview_info(self):
        """Show interactive preview help dialog"""
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton
        
        dialog = QDialog(self.parent)
        dialog.setWindowTitle("Interactive Preview Help")
        dialog.setModal(True)
        dialog.resize(400, 300)
        layout = QVBoxLayout(dialog)
        
        info_text = QLabel("""
Interactive Preview shows how your filenames will look.

You can:
• Drag and drop components to reorder them
• See real-time preview of your filename format
• Components are separated by your chosen separator

The number (001) is always at the end and auto-increments.
        """)
        info_text.setWordWrap(True)
        layout.addWidget(info_text)
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)
        dialog.exec()
