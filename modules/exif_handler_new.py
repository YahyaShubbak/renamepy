#!/usr/bin/env python3
"""
EXIF data extraction and handling for the RenameFiles application.
"""

import os
import threading
import logging
from typing import Dict, Optional, Any

# EXIF processing imports
try:
    import pyexiftools as pyexiftool
    EXIFTOOL_AVAILABLE = True
except ImportError:
    try:
        import exiftool as pyexiftool
        EXIFTOOL_AVAILABLE = True
    except ImportError:
        EXIFTOOL_AVAILABLE = False
        pyexiftool = None

try:
    from PIL import Image
    from PIL.ExifTags import TAGS
    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False
    Image = None
    TAGS = None

class ExifHandler:
    """Handles EXIF data extraction with caching and multiple backends"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.cache = {}
        self.cache_lock = threading.Lock()
        
        # Determine the best available method
        self.current_method = self._determine_method()
        self.exiftool_instance = None
        
        # Initialize ExifTool if available
        if self.current_method == "exiftool":
            self._initialize_exiftool()
    
    def _determine_method(self):
        """Determine the best available EXIF extraction method"""
        if EXIFTOOL_AVAILABLE:
            return "exiftool"
        elif PILLOW_AVAILABLE:
            return "pillow"
        else:
            return None
    
    def _initialize_exiftool(self):
        """Initialize ExifTool instance"""
        try:
            # Check for local ExifTool installation
            exiftool_paths = [
                os.path.join(os.path.dirname(os.path.dirname(__file__)), "exiftool-13.32_64", "exiftool.exe"),
                "exiftool.exe",
                "exiftool"
            ]
            
            exiftool_path = None
            for path in exiftool_paths:
                if os.path.exists(path):
                    exiftool_path = path
                    break
            
            if exiftool_path:
                self.exiftool_instance = pyexiftool.ExifTool(executable=exiftool_path)
                self.exiftool_instance.start()
                self.logger.info(f"ExifTool initialized with: {exiftool_path}")
            else:
                self.exiftool_instance = pyexiftool.ExifTool()
                self.exiftool_instance.start()
                self.logger.info("ExifTool initialized with system installation")
                
        except Exception as e:
            self.logger.warning(f"Failed to initialize ExifTool: {e}")
            self.current_method = "pillow" if PILLOW_AVAILABLE else None
    
    def is_exiftool_available(self):
        """Check if ExifTool is available and working"""
        return self.current_method == "exiftool" and self.exiftool_instance is not None
    
    def extract_exif(self, file_path: str) -> Dict[str, Any]:
        """Extract EXIF data from a file with caching"""
        # Check cache first
        with self.cache_lock:
            if file_path in self.cache:
                return self.cache[file_path]
        
        # Extract EXIF data
        exif_data = {}
        
        if self.current_method == "exiftool":
            exif_data = self._extract_with_exiftool(file_path)
        elif self.current_method == "pillow":
            exif_data = self._extract_with_pillow(file_path)
        
        # Normalize the data
        normalized_data = self._normalize_exif_data(exif_data, file_path)
        
        # Cache the result
        with self.cache_lock:
            self.cache[file_path] = normalized_data
        
        return normalized_data
    
    def _extract_with_exiftool(self, file_path: str) -> Dict[str, Any]:
        """Extract EXIF data using ExifTool"""
        if not self.exiftool_instance:
            return {}
        
        try:
            metadata = self.exiftool_instance.get_metadata(file_path)
            return metadata or {}
        except Exception as e:
            self.logger.warning(f"ExifTool extraction failed for {file_path}: {e}")
            return {}
    
    def _extract_with_pillow(self, file_path: str) -> Dict[str, Any]:
        """Extract EXIF data using Pillow"""
        if not PILLOW_AVAILABLE:
            return {}
        
        try:
            with Image.open(file_path) as img:
                exif_dict = img._getexif() or {}
                
                # Convert numeric tags to readable names
                readable_exif = {}
                for tag_id, value in exif_dict.items():
                    tag_name = TAGS.get(tag_id, tag_id)
                    readable_exif[tag_name] = value
                
                return readable_exif
                
        except Exception as e:
            self.logger.warning(f"Pillow extraction failed for {file_path}: {e}")
            return {}
    
    def _normalize_exif_data(self, raw_exif: Dict[str, Any], file_path: str = "") -> Dict[str, Any]:
        """Normalize EXIF data to a common format"""
        normalized = {
            'date_taken': None,
            'camera_make': None,
            'camera_model': None,
            'lens_model': None,
            'original_datetime': None
        }
        
        if self.current_method == "exiftool":
            # ExifTool field mapping
            field_mapping = {
                'EXIF:DateTimeOriginal': 'original_datetime',
                'EXIF:CreateDate': 'date_taken',
                'EXIF:Make': 'camera_make',
                'EXIF:Model': 'camera_model',
                'EXIF:LensModel': 'lens_model',
                'XMP:LensModel': 'lens_model'
            }
            
            for exif_key, norm_key in field_mapping.items():
                if exif_key in raw_exif and raw_exif[exif_key]:
                    normalized[norm_key] = str(raw_exif[exif_key]).strip()
        
        elif self.current_method == "pillow":
            # Pillow field mapping
            field_mapping = {
                'DateTimeOriginal': 'original_datetime',
                'DateTime': 'date_taken',
                'Make': 'camera_make',
                'Model': 'camera_model',
                'LensModel': 'lens_model'
            }
            
            for exif_key, norm_key in field_mapping.items():
                if exif_key in raw_exif and raw_exif[exif_key]:
                    normalized[norm_key] = str(raw_exif[exif_key]).strip()
        
        # Format date for filename use
        if normalized['original_datetime'] or normalized['date_taken']:
            date_str = normalized['original_datetime'] or normalized['date_taken']
            formatted_date = self._format_date_for_filename(date_str)
            if formatted_date:
                normalized['date_taken'] = formatted_date
        
        # If no EXIF date, use file modification time or filename
        if not normalized['date_taken']:
            if file_path:
                normalized['date_taken'] = self._get_file_date_fallback(file_path)
            else:
                normalized['date_taken'] = self._get_current_date()
        
        return normalized
    
    def _format_date_for_filename(self, date_str: str) -> Optional[str]:
        """Convert various date formats to YYYYMMDD format"""
        if not date_str:
            return None
        
        import re
        
        # Common date patterns
        patterns = [
            r'(\d{4}):(\d{2}):(\d{2})\s+(\d{2}):(\d{2}):(\d{2})',  # YYYY:MM:DD HH:MM:SS
            r'(\d{4})-(\d{2})-(\d{2})\s+(\d{2}):(\d{2}):(\d{2})',  # YYYY-MM-DD HH:MM:SS
            r'(\d{4}):(\d{2}):(\d{2})',  # YYYY:MM:DD
            r'(\d{4})-(\d{2})-(\d{2})',  # YYYY-MM-DD
        ]
        
        for pattern in patterns:
            match = re.match(pattern, date_str)
            if match:
                year, month, day = match.groups()[:3]
                return f"{year}{month}{day}"
        
        return None
    
    def _get_file_date_fallback(self, file_path: str) -> str:
        """Extract date from filename or use file modification time as fallback"""
        import re
        from datetime import datetime
        
        filename = os.path.basename(file_path)
        
        # Try to extract date from filename
        date_patterns = [
            r'(\d{4})(\d{2})(\d{2})',  # YYYYMMDD
            r'(\d{4})-(\d{2})-(\d{2})',  # YYYY-MM-DD
            r'(\d{4})_(\d{2})_(\d{2})',  # YYYY_MM_DD
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, filename)
            if match:
                year, month, day = match.groups()
                return f"{year}{month}{day}"
        
        # Use file modification time
        try:
            if os.path.exists(file_path):
                mtime = os.path.getmtime(file_path)
                return datetime.fromtimestamp(mtime).strftime("%Y%m%d")
        except:
            pass
        
        # Final fallback to current date
        return self._get_current_date()
    
    def _get_current_date(self) -> str:
        """Get current date in YYYYMMDD format"""
        from datetime import datetime
        return datetime.now().strftime("%Y%m%d")
    
    def clear_cache(self):
        """Clear the EXIF cache"""
        with self.cache_lock:
            self.cache.clear()
    
    def close(self):
        """Clean up resources"""
        if self.exiftool_instance:
            try:
                self.exiftool_instance.terminate()
            except:
                pass
        self.clear_cache()
