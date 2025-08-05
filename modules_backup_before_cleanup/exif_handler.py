#!/usr/bin/env python3
"""
EXIF data extraction and handling for the RenameFiles application.
This module provides the exact same functionality as the original RenameFiles.py
"""

import os
import time
import threading

# EXIF processing imports - exact same as original
try:
    import exiftool #### pip install PyExifTool
    EXIFTOOL_AVAILABLE = True
except ImportError:
    EXIFTOOL_AVAILABLE = False

try:
    from PIL import Image
    from PIL.ExifTags import TAGS
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

# Global EXIF cache for performance - exact same as original
_exif_cache = {}
_cache_lock = None

# Global ExifTool instance for batch processing - exact same as original
_global_exiftool_instance = None
_global_exiftool_path = None

def clear_global_exif_cache():
    """Clear the global EXIF cache for fresh processing"""
    global _exif_cache
    _exif_cache.clear()

def get_cached_exif_data(file_path, method, exiftool_path=None):
    """
    Get EXIF data with intelligent caching based on file modification time
    """
    try:
        # Create cache key based on file path and modification time
        mtime = os.path.getmtime(file_path)
        cache_key = (file_path, mtime, method)
        
        # Check cache first
        if cache_key in _exif_cache:
            return _exif_cache[cache_key]
        
        # Extract EXIF data (not cached)
        result = extract_exif_fields_with_retry(file_path, method, exiftool_path, max_retries=2)
        
        # Cache the result
        _exif_cache[cache_key] = result
        
        return result
    except Exception as e:
        print(f"Cached EXIF extraction failed for {file_path}: {e}")
        return None, None, None

def get_selective_cached_exif_data(file_path, method, exiftool_path=None, need_date=True, need_camera=False, need_lens=False):
    """
    OPTIMIZED: Get only requested EXIF data with intelligent caching.
    This function only extracts and caches the fields that are actually needed.
    
    Args:
        file_path: Path to the image file
        method: 'exiftool' or 'pillow'
        exiftool_path: Path to exiftool executable
        need_date: Whether to extract date information
        need_camera: Whether to extract camera model
        need_lens: Whether to extract lens model
    
    Returns:
        (date, camera, lens) - only requested fields are extracted and cached
    """
    try:
        # CRITICAL FIX: Normalize path to prevent double backslashes
        normalized_path = os.path.normpath(file_path)
        
        # Verify file exists before processing
        if not os.path.exists(normalized_path):
            print(f"File not found: {normalized_path}")
            return None, None, None
        
        # Create cache key based on file path, modification time, method AND requested fields
        mtime = os.path.getmtime(normalized_path)
        field_signature = (need_date, need_camera, need_lens)
        cache_key = (normalized_path, mtime, method, field_signature)
        
        # Check cache first
        if cache_key in _exif_cache:
            return _exif_cache[cache_key]
        
        # Extract only requested EXIF fields
        result = extract_selective_exif_fields(
            normalized_path, method, exiftool_path, 
            need_date=need_date, need_camera=need_camera, need_lens=need_lens
        )
        
        # Cache the result
        _exif_cache[cache_key] = result
        
        return result
    except Exception as e:
        print(f"Error in get_selective_cached_exif_data for {file_path}: {e}")
        return None, None, None

def extract_exif_fields(image_path, method, exiftool_path=None):
    """
    Extracts date, camera model, and lens model from an image using the specified method.
    Returns (date, camera, lens) or (None, None, None) if not found.
    """
    return extract_exif_fields_with_retry(image_path, method, exiftool_path, max_retries=3)

def extract_selective_exif_fields(image_path, method, exiftool_path=None, need_date=True, need_camera=False, need_lens=False):
    """
    OPTIMIZED: Extracts only the requested EXIF fields from an image.
    This dramatically improves performance by only reading what's needed.
    
    Args:
        image_path: Path to the image file
        method: 'exiftool' or 'pillow'
        exiftool_path: Path to exiftool executable (if using exiftool)
        need_date: Whether to extract date information
        need_camera: Whether to extract camera model
        need_lens: Whether to extract lens model
    
    Returns:
        (date, camera, lens) - only requested fields are extracted, others are None
    """
    # If nothing is needed, return early
    if not any([need_date, need_camera, need_lens]):
        return None, None, None
    
    # CRITICAL FIX: Normalize path to prevent double backslashes
    normalized_path = os.path.normpath(image_path)
    
    # Verify file exists
    if not os.path.exists(normalized_path):
        print(f"extract_selective_exif_fields: File not found: {normalized_path}")
        return None, None, None
    
    max_retries = 2  # Reduced retries for batch processing
    
    for attempt in range(max_retries):
        try:
            if method == "exiftool":
                # Use shared ExifTool instance for better performance
                meta = get_exiftool_metadata_shared(normalized_path, exiftool_path)
                
                # Extract only requested fields
                date = None
                camera = None  
                lens = None
                
                if need_date:
                    date = meta.get('EXIF:DateTimeOriginal') or meta.get('CreateDate') or meta.get('DateTimeOriginal')
                    if date:
                        date = date.split(' ')[0].replace(':', '')
                
                if need_camera:
                    # Use the same simple approach as the working old application
                    camera = meta.get('EXIF:Model') or meta.get('Model')
                    if camera:
                        camera = str(camera).replace(' ', '-')
                
                if need_lens:
                    # Use the same simple approach as the working old application
                    lens = meta.get('EXIF:LensModel') or meta.get('LensModel') or meta.get('LensInfo')
                    if lens:
                        lens = str(lens).replace(' ', '-')
                
                return date, camera, lens
                
            elif method == "pillow":
                image = Image.open(image_path)
                exif_data = image._getexif()
                date = None
                camera = None
                lens = None
                
                if exif_data:
                    # Only process tags we actually need
                    for tag, value in exif_data.items():
                        decoded_tag = TAGS.get(tag, tag)
                        
                        if need_date and decoded_tag == "DateTimeOriginal" and not date:
                            date = value.split(" ")[0].replace(":", "")
                        
                        if need_camera and decoded_tag == "Model" and not camera:
                            camera = str(value).replace(" ", "-")
                        
                        if need_lens and decoded_tag == "LensModel" and not lens:
                            lens = str(value).replace(" ", "-")
                        
                        # Early exit if we have everything we need
                        if ((not need_date or date) and 
                            (not need_camera or camera) and 
                            (not need_lens or lens)):
                            break
                
                return date, camera, lens
            else:
                return None, None, None
                
        except Exception as e:
            if attempt == max_retries - 1:
                return None, None, None
            else:
                time.sleep(0.05)  # Shorter pause for batch processing

def get_exiftool_metadata_shared(image_path, exiftool_path=None):
    """
    PERFORMANCE OPTIMIZATION: Use a shared ExifTool instance to avoid 
    the overhead of starting/stopping ExifTool for each file.
    """
    global _global_exiftool_instance, _global_exiftool_path
    
    # CRITICAL FIX: Normalize path to prevent double backslashes
    normalized_path = os.path.normpath(image_path)
    
    # Verify file exists
    if not os.path.exists(normalized_path):
        print(f"get_exiftool_metadata_shared: File not found: {normalized_path}")
        return {}
    
    try:
        # Check if we need to create/recreate the instance
        if (_global_exiftool_instance is None or 
            _global_exiftool_path != exiftool_path):
            
            # Close existing instance if needed
            if _global_exiftool_instance is not None:
                try:
                    _global_exiftool_instance.terminate()
                except:
                    pass
            
            # Create new instance
            if exiftool_path and os.path.exists(exiftool_path):
                _global_exiftool_instance = exiftool.ExifToolHelper(executable=exiftool_path)
            else:
                _global_exiftool_instance = exiftool.ExifToolHelper()
            
            _global_exiftool_path = exiftool_path
            
            # Start the instance
            _global_exiftool_instance.__enter__()
        
        # Get metadata using the shared instance with normalized path
        meta = _global_exiftool_instance.get_metadata([normalized_path])[0]
        return meta
        
    except Exception as e:
        # If the shared instance fails, fall back to a temporary instance
        print(f"Shared ExifTool instance failed, using temporary instance: {e}")
        try:
            if exiftool_path and os.path.exists(exiftool_path):
                with exiftool.ExifToolHelper(executable=exiftool_path) as et:
                    return et.get_metadata([normalized_path])[0]
            else:
                with exiftool.ExifToolHelper() as et:
                    return et.get_metadata([normalized_path])[0]
        except Exception as e2:
            print(f"Temporary ExifTool instance also failed: {e2}")
            return {}

def cleanup_global_exiftool():
    """
    Clean up the global ExifTool instance when done with batch processing
    """
    global _global_exiftool_instance
    if _global_exiftool_instance is not None:
        try:
            _global_exiftool_instance.__exit__(None, None, None)
        except:
            pass
        _global_exiftool_instance = None

def extract_exif_fields_with_retry(image_path, method, exiftool_path=None, max_retries=3):
    """
    Extracts EXIF fields with retry mechanism for reliability.
    """
    # CRITICAL FIX: Normalize path to prevent double backslashes
    normalized_path = os.path.normpath(image_path)
    
    # Verify file exists
    if not os.path.exists(normalized_path):
        print(f"extract_exif_fields_with_retry: File not found: {normalized_path}")
        return None, None, None
    
    for attempt in range(max_retries):
        try:
            if method == "exiftool":
                # Use exiftool with or without explicit path
                if exiftool_path and os.path.exists(exiftool_path):
                    with exiftool.ExifToolHelper(executable=exiftool_path) as et:
                        meta = et.get_metadata([normalized_path])[0]
                else:
                    # Try to use system exiftool or let exiftool package find it
                    with exiftool.ExifToolHelper() as et:
                        meta = et.get_metadata([normalized_path])[0]
                
                # Extract date
                date = meta.get('EXIF:DateTimeOriginal')
                if date:
                    date = date.split(' ')[0].replace(':', '')
                
                # Extract camera model
                camera = meta.get('EXIF:Model')
                if camera:
                    camera = str(camera).replace(' ', '-')
                
                # Extract lens model
                lens = meta.get('EXIF:LensModel') or meta.get('LensInfo')
                if lens:
                    lens = str(lens).replace(' ', '-')
                
                return date, camera, lens
                
            elif method == "pillow":
                image = Image.open(normalized_path)
                exif_data = image._getexif()
                date = None
                camera = None
                lens = None
                
                if exif_data:
                    for tag, value in exif_data.items():
                        decoded_tag = TAGS.get(tag, tag)
                        if decoded_tag == "DateTimeOriginal":
                            date = value.split(" ")[0].replace(":", "")
                        elif decoded_tag == "Model":
                            camera = str(value).replace(" ", "-")
                        elif decoded_tag == "LensModel":
                            lens = str(value).replace(" ", "-")
                
                return date, camera, lens
            else:
                return None, None, None
                
        except Exception as e:
            if attempt == max_retries - 1:
                print(f"EXIF extraction failed after {max_retries} attempts: {e}")
                return None, None, None
            else:
                time.sleep(0.1)

def extract_date_taken(image_path, method, exiftool_path=None):
    """Extract only the date taken from an image"""
    date, _, _ = extract_exif_fields(image_path, method, exiftool_path)
    return date

def extract_camera_model(image_path, method, exiftool_path=None):
    """Extract only the camera model from an image"""
    _, camera, _ = extract_exif_fields(image_path, method, exiftool_path)
    return camera

def extract_lens_model(image_path, method, exiftool_path=None):
    """Extract only the lens model from an image"""
    _, _, lens = extract_exif_fields(image_path, method, exiftool_path)
    return lens

def extract_image_number(image_path, method, exiftool_path=None):
    """Extract image number from EXIF data if available"""
    try:
        if method == "exiftool":
            if exiftool_path and os.path.exists(exiftool_path):
                with exiftool.ExifToolHelper(executable=exiftool_path) as et:
                    meta = et.get_metadata([image_path])[0]
            else:
                with exiftool.ExifToolHelper() as et:
                    meta = et.get_metadata([image_path])[0]
            
            # Try various fields for image number
            image_number = (meta.get('EXIF:ImageNumber') or 
                          meta.get('ImageNumber') or 
                          meta.get('FileNumber'))
            
            if image_number:
                return str(image_number).zfill(3)
    except Exception as e:
        print(f"Failed to extract image number: {e}")
    
    return None

def get_file_timestamp(image_path, method, exiftool_path=None):
    """
    Get file timestamp using EXIF DateTimeOriginal or file system date
    Returns timestamp string or None
    """
    try:
        # First try to get EXIF date
        date = extract_date_taken(image_path, method, exiftool_path)
        if date:
            return date
        
        # Fall back to file system modification time
        mtime = os.path.getmtime(image_path)
        return time.strftime("%Y%m%d", time.localtime(mtime))
        
    except Exception as e:
        print(f"Failed to get file timestamp: {e}")
        return None

def get_safe_target_path(original_path, new_name):
    """
    Generate a safe target path, avoiding conflicts with existing files.
    """
    directory = os.path.dirname(original_path)
    new_path = os.path.join(directory, new_name)
    
    # Check if target already exists
    if not os.path.exists(new_path):
        return new_path
    
    # Generate alternative name if conflict exists
    base, ext = os.path.splitext(new_name)
    attempt = 1
    
    while os.path.exists(new_path) and attempt <= 999:
        alternative_name = f"{base}_conflict_{attempt:03d}{ext}"
        new_path = os.path.join(directory, alternative_name)
        attempt += 1
    
    if attempt > 999:
        # Fallback: add timestamp
        timestamp = int(time.time())
        alternative_name = f"{base}_conflict_{timestamp}{ext}"
        new_path = os.path.join(directory, alternative_name)
    
    return new_path

def validate_path_length(file_path):
    """
    Validate that the file path is not too long for the filesystem.
    Returns True if valid, False if too long.
    """
    # Windows has a 260 character limit, leave buffer
    max_length = 250
    return len(file_path) <= max_length

# Legacy class for backward compatibility
class ExifHandler:
    """Legacy class for backward compatibility"""
    
    def __init__(self):
        pass
    
    def extract_exif(self, file_path):
        """Extract EXIF data using the original functions"""
        return get_cached_exif_data(file_path, "exiftool")
    
    def is_exiftool_available(self):
        """Check if ExifTool is available"""
        return EXIFTOOL_AVAILABLE

# Simple EXIF Handler for UI compatibility
class SimpleExifHandler:
    """Simple EXIF handler for UI compatibility"""
    
    def __init__(self):
        self.current_method = "exiftool" if EXIFTOOL_AVAILABLE else ("pillow" if PIL_AVAILABLE else None)
        # Correct path to ExifTool in the project (updated to version 13.33)
        self.exiftool_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "exiftool-13.33_64", "exiftool(-k).exe")
        # Check if ExifTool exists at the specified path
        if not os.path.exists(self.exiftool_path):
            self.exiftool_path = None
    
    def extract_raw_exif(self, file_path):
        """Extract raw EXIF data"""
        if self.current_method == "exiftool":
            return get_exiftool_metadata_shared(file_path, self.exiftool_path)
        return {}
    
    def is_exiftool_available(self):
        """Check if ExifTool is available"""
        return EXIFTOOL_AVAILABLE and self.current_method == "exiftool"

# Backward compatibility functions
def get_exif_data(file_path: str, 
                  method: str = "exiftool",
                  exiftool_path: str = None,
                  fields: list = None) -> dict:
    """Get EXIF data (backward compatibility function)"""
    date, camera, lens = get_cached_exif_data(file_path, method, exiftool_path)
    return {
        'date': date,
        'camera': camera,
        'lens': lens
    }

def get_selective_exif_data(file_path: str,
                          method: str = "exiftool", 
                          exiftool_path: str = None,
                          fields: list = None) -> dict:
    """Get selective EXIF data with caching (backward compatibility function)"""
    date, camera, lens = get_cached_exif_data(file_path, method, exiftool_path)
    return {
        'date': date,
        'camera': camera,
        'lens': lens
    }
