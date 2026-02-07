#!/usr/bin/env python3
"""
EXIF Handler - Image number/shutter count extraction using shared ExifTool instance.
"""

from ..exif_processor import get_exiftool_metadata_shared
from ..logger_util import get_logger

log = get_logger()


def extract_image_number(image_path, exif_method, exiftool_path):
    """Extract image number/shutter count from image file.
    
    Uses the shared ExifTool instance for performance.
    """
    try:
        # Get raw EXIF data using shared instance for performance
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
