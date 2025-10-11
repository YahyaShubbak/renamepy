#!/usr/bin/env python3
"""
EXIF Handler - Simple EXIF handler using original extraction functions
"""

import os
import glob
from ..exif_processor import (
    get_cached_exif_data, get_exiftool_metadata_shared,
    EXIFTOOL_AVAILABLE, PIL_AVAILABLE
)
from ..logger_util import get_logger

log = get_logger()


class SimpleExifHandler:
    """Simple EXIF handler using original extraction functions."""
    
    def __init__(self):
        self.current_method = "exiftool" if EXIFTOOL_AVAILABLE else ("pillow" if PIL_AVAILABLE else None)
        self.exiftool_path = self._find_exiftool_path()

    def _find_exiftool_path(self):
        if not EXIFTOOL_AVAILABLE:
            return None
        script_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        candidates = [
            os.path.join(script_dir, "exiftool-13.33_64", "exiftool.exe"),
            os.path.join(script_dir, "exiftool-13.33_64", "exiftool(-k).exe"),
            os.path.join(script_dir, "exiftool-13.32_64", "exiftool.exe"),
            os.path.join(script_dir, "exiftool-13.32_64", "exiftool(-k).exe"),
        ]
        for filename in ("exiftool.exe", "exiftool(-k).exe"):
            candidates.extend(glob.glob(os.path.join(script_dir, "*exiftool*", filename)))
        for path in candidates:
            if os.path.exists(path):
                log.debug(f"Found ExifTool at: {path}")
                return path
        log.info("ExifTool not found locally; relying on system path if available")
        return None

    def extract_exif(self, file_path):
        return get_cached_exif_data(file_path, self.current_method, self.exiftool_path)

    def extract_raw_exif(self, file_path):
        try:
            if self.current_method == "exiftool":
                return get_exiftool_metadata_shared(file_path, self.exiftool_path)
            date, camera, lens = get_cached_exif_data(file_path, self.current_method, self.exiftool_path)
            return {'DateTimeOriginal': date, 'Model': camera, 'LensModel': lens}
        except Exception as e:
            log.debug(f"Error extracting raw EXIF from {file_path}: {e}")
            return {}

    def is_exiftool_available(self):
        return EXIFTOOL_AVAILABLE


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
        log.debug(f"Error extracting image number from {image_path}: {e}")
        return None
