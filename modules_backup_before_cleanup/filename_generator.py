#!/usr/bin/env python3
"""
Filename generation and component handling for the RenameFiles application.
"""

import os
import re
from datetime import datetime
from typing import Dict, List, Optional, Any

def calculate_stats(files: List[str]) -> Dict[str, int]:
    """Calculate statistics for a list of files"""
    stats = {
        'total_files': len(files),
        'total_images': 0,
        'jpeg_count': 0,
        'raw_count': 0
    }
    
    for file_path in files:
        ext = os.path.splitext(file_path)[1].lower()
        if ext in ['.jpg', '.jpeg']:
            stats['jpeg_count'] += 1
            stats['total_images'] += 1
        elif ext in ['.cr2', '.nef', '.arw', '.dng', '.raf', '.orf']:
            stats['raw_count'] += 1
            stats['total_images'] += 1
        elif ext in ['.png', '.tiff', '.tif']:
            stats['total_images'] += 1
    
    return stats

class FilenameGenerator:
    """Handles filename generation with various components and formatting options"""
    
    def __init__(self):
        self.component_cache = {}
    
    def generate_filename(self, file_path: str, config: Dict[str, Any], 
                         exif_data: Optional[Dict[str, Any]] = None, 
                         sequential_number: int = 1) -> str:
        """Generate a filename based on configuration and EXIF data"""
        
        # Extract components based on configuration
        components = []
        component_order = config.get('component_order', [])
        separator = config.get('separator', '_')
        
        # Process each component in the specified order
        for component_name in component_order:
            component_value = self._get_component_value(
                component_name, file_path, config, exif_data
            )
            if component_value:
                components.append(component_value)
        
        # Add sequential number if enabled
        if config.get('use_numbering', True):
            start_num = config.get('start_number', 1)
            number = start_num + sequential_number - 1
            components.append(f"{number:03d}")
        
        # Get file extension
        _, ext = os.path.splitext(file_path)
        
        # Join components and add extension
        if components:
            if separator == "None" or not separator:
                filename = "".join(components) + ext
            else:
                filename = separator.join(components) + ext
        else:
            # Fallback to original filename if no components
            filename = os.path.basename(file_path)
        
        return filename
    
    def _get_component_value(self, component_name: str, file_path: str, 
                           config: Dict[str, Any], 
                           exif_data: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """Get the value for a specific component"""
        
        component_name_upper = component_name.upper()
        
        if component_name_upper == "DATE":
            return self._get_date_component(file_path, config, exif_data)
        elif component_name_upper == "CAMERA":
            return self._get_camera_component(file_path, exif_data)
        elif component_name_upper == "LENS":
            return self._get_lens_component(file_path, exif_data)
        elif component_name_upper == "ORIGINAL":
            return self._get_original_filename_component(file_path)
        elif component_name_upper == "FOLDER":
            return self._get_folder_component(file_path)
        elif component_name in config.get('components', {}):
            # Custom text component
            return config['components'].get(component_name, "")
        else:
            # Handle custom text directly
            return component_name if component_name else None
    
    def _get_date_component(self, file_path: str, config: Dict[str, Any], 
                           exif_data: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """Get formatted date component"""
        
        if not exif_data:
            # Fallback to file modification time if no EXIF data
            try:
                mtime = os.path.getmtime(file_path)
                date_taken = datetime.fromtimestamp(mtime).strftime("%Y%m%d")
            except:
                date_taken = datetime.now().strftime("%Y%m%d")
        else:
            date_taken = exif_data.get('date_taken')
            if not date_taken:
                try:
                    mtime = os.path.getmtime(file_path)
                    date_taken = datetime.fromtimestamp(mtime).strftime("%Y%m%d")
                except:
                    date_taken = datetime.now().strftime("%Y%m%d")
        
        # Format date according to configuration
        date_format = config.get('date_format', 'YYYY-MM-DD')
        return self._format_date(date_taken, date_format)
    
    def _format_date(self, date_str: str, format_type: str) -> str:
        """Format date string according to the specified format"""
        
        if not date_str or len(date_str) < 8:
            return date_str
        
        # Extract date components (assuming YYYYMMDD format)
        year = date_str[:4]
        month = date_str[4:6] if len(date_str) >= 6 else "01"
        day = date_str[6:8] if len(date_str) >= 8 else "01"
        
        if format_type == "YYYY-MM-DD":
            return f"{year}-{month}-{day}"
        elif format_type == "YYYY-MM-DD_HH-MM-SS":
            # For now, just add 00-00-00 for time
            return f"{year}-{month}-{day}_00-00-00"
        elif format_type == "YYYYMMDD":
            return f"{year}{month}{day}"
        elif format_type == "YYYYMMDD_HHMMSS":
            return f"{year}{month}{day}_000000"
        elif format_type == "DD-MM-YYYY":
            return f"{day}-{month}-{year}"
        elif format_type == "MM-DD-YYYY":
            return f"{month}-{day}-{year}"
        else:
            return date_str
    
    def _get_camera_component(self, file_path: str, 
                            exif_data: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """Get camera model component"""
        
        if not exif_data:
            return None
        
        camera_make = exif_data.get('camera_make', '')
        camera_model = exif_data.get('camera_model', '')
        
        if camera_model:
            # Clean up camera model string
            camera_model = re.sub(r'[^\w\-]', '', camera_model)
            if camera_make and camera_make.lower() not in camera_model.lower():
                return f"{camera_make}_{camera_model}"
            return camera_model
        
        return None
    
    def _get_lens_component(self, file_path: str, 
                          exif_data: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """Get lens model component"""
        
        if not exif_data:
            return None
        
        lens_model = exif_data.get('lens_model', '')
        
        if lens_model:
            # Clean up lens model string
            lens_model = re.sub(r'[^\w\-]', '', lens_model)
            return lens_model
        
        return None
    
    def _get_original_filename_component(self, file_path: str) -> str:
        """Get original filename (without extension) component"""
        filename = os.path.basename(file_path)
        name, _ = os.path.splitext(filename)
        return name
    
    def _get_folder_component(self, file_path: str) -> str:
        """Get parent folder name component"""
        parent_dir = os.path.dirname(file_path)
        return os.path.basename(parent_dir) if parent_dir else ""
    
    def generate_preview(self, files: List[str], config: Dict[str, Any]) -> List[tuple]:
        """Generate preview of renamed files"""
        preview_data = []
        
        for i, file_path in enumerate(files):
            original_name = os.path.basename(file_path)
            
            try:
                new_name = self.generate_filename(file_path, config, None, i + 1)
                preview_data.append((original_name, new_name))
            except Exception as e:
                preview_data.append((original_name, f"Error: {str(e)}"))
        
        return preview_data
    
    def validate_config(self, config: Dict[str, Any]) -> List[str]:
        """Validate the configuration and return any errors"""
        errors = []
        
        # Check if at least one component is selected
        components = config.get('components', {})
        if not any(components.values()) and not config.get('use_numbering', True):
            errors.append("At least one component must be selected or numbering enabled")
        
        # Check date format
        date_format = config.get('date_format', '')
        valid_formats = [
            "YYYY-MM-DD", "YYYY-MM-DD_HH-MM-SS", "YYYYMMDD", 
            "YYYYMMDD_HHMMSS", "DD-MM-YYYY", "MM-DD-YYYY"
        ]
        if date_format and date_format not in valid_formats:
            errors.append(f"Invalid date format: {date_format}")
        
        return errors

# Backward compatibility functions
def get_filename_components_static(date_taken, camera_prefix, additional, camera_model, 
                                 lens_model, use_camera, use_lens, num, custom_order, 
                                 date_format="YYYY-MM-DD", use_date=True):
    """Static version for backward compatibility"""
    generator = FilenameGenerator()
    
    # Convert old parameters to new config format
    config = {
        'components': {
            'date': use_date,
            'camera': use_camera,
            'lens': use_lens,
            'custom': bool(additional)
        },
        'component_order': custom_order or ['DATE', 'CAMERA', 'LENS'],
        'date_format': date_format,
        'separator': '_',
        'use_numbering': True,
        'start_number': num,
        'custom_text': additional or ''
    }
    
    exif_data = {
        'date_taken': date_taken,
        'camera_model': camera_model,
        'lens_model': lens_model
    }
    
    # Generate filename for a dummy file
    return generator.generate_filename("dummy.jpg", config, exif_data, num)

# Additional backward compatibility functions
def group_files_with_failsafe(files, max_group_size=50):
    """Group files with failsafe (backward compatibility)"""
    groups = []
    for i in range(0, len(files), max_group_size):
        groups.append(files[i:i + max_group_size])
    return groups

def create_continuous_counter_map(files, start_counter=1):
    """Create continuous counter map (backward compatibility)"""
    counter_map = {}
    current_counter = start_counter
    
    for file_path in files:
        counter_map[file_path] = current_counter
        current_counter += 1
    
    return counter_map

def extract_date_from_file(file_path, exif_handler=None):
    """Extract date from file (backward compatibility)"""
    if exif_handler:
        exif_data = exif_handler.extract_exif(file_path)
        return exif_data.get('date_taken')
    else:
        # Fallback to file modification time
        try:
            mtime = os.path.getmtime(file_path)
            return datetime.fromtimestamp(mtime).strftime("%Y%m%d")
        except:
            return datetime.now().strftime("%Y%m%d")
