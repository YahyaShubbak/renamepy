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
    
    # Auto-detect ExifTool path if not provided
    if not exiftool_path:
        exiftool_path = find_exiftool_path()
    
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
                print(f"🔧 Created ExifTool instance with: {exiftool_path}")
            else:
                _global_exiftool_instance = exiftool.ExifToolHelper()
                print("🔧 Created default ExifTool instance")
            
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

def get_all_metadata(file_path, method, exiftool_path=None):
    """
    Extract all relevant metadata for filename generation
    Returns dict with aperture, iso, focal_length, shutter_speed, etc.
    """
    try:
        normalized_path = os.path.normpath(file_path)
        
        if not os.path.exists(normalized_path):
            return {}
        
        metadata = {}
        
        if method == "exiftool" and EXIFTOOL_AVAILABLE:
            meta = get_exiftool_metadata_shared(normalized_path, exiftool_path)
            
            # Extract all relevant metadata
            if meta:
                # Aperture (f-number)
                aperture = meta.get('EXIF:FNumber') or meta.get('FNumber') or meta.get('EXIF:ApertureValue')
                if aperture:
                    try:
                        # Convert to f/x format
                        if isinstance(aperture, str) and '/' in aperture:
                            num, den = aperture.split('/')
                            aperture_val = float(num) / float(den)
                        else:
                            aperture_val = float(aperture)
                        metadata['aperture'] = f"f{aperture_val:.1f}".replace('.0', '')
                    except:
                        pass
                
                # ISO
                iso = meta.get('EXIF:ISO') or meta.get('ISO')
                if iso:
                    metadata['iso'] = str(iso)
                
                # Focal Length
                focal = meta.get('EXIF:FocalLength') or meta.get('FocalLength')
                if focal:
                    try:
                        if isinstance(focal, str) and '/' in focal:
                            num, den = focal.split('/')
                            focal_val = float(num) / float(den)
                        else:
                            focal_val = float(focal)
                        metadata['focal_length'] = f"{focal_val:.0f}mm"
                    except:
                        pass
                
                # Shutter Speed
                shutter = meta.get('EXIF:ExposureTime') or meta.get('ExposureTime')
                if shutter:
                    try:
                        if isinstance(shutter, str) and '/' in shutter:
                            num, den = shutter.split('/')
                            shutter_val = float(num) / float(den)
                            if shutter_val >= 1:
                                metadata['shutter_speed'] = f"{shutter_val:.0f}s"
                            else:
                                metadata['shutter_speed'] = f"1/{int(1/shutter_val)}s"
                        else:
                            shutter_val = float(shutter)
                            if shutter_val >= 1:
                                metadata['shutter_speed'] = f"{shutter_val:.0f}s"
                            else:
                                metadata['shutter_speed'] = f"1/{int(1/shutter_val)}s"
                    except:
                        pass
                
                # Camera model
                camera = meta.get('EXIF:Model') or meta.get('Model')
                if camera:
                    metadata['camera'] = str(camera).replace(' ', '-')
                
                # Lens model
                lens = meta.get('EXIF:LensModel') or meta.get('LensModel')
                if lens:
                    metadata['lens'] = str(lens).replace(' ', '-')
        
        return metadata
    except Exception as e:
        print(f"Error extracting metadata from {file_path}: {e}")
        return {}

def find_exiftool_path():
    """
    Find the ExifTool executable path automatically
    
    Returns:
        str: Path to ExifTool executable or None if not found
    """
    # Possible ExifTool locations
    possible_paths = [
        # Local project ExifTool
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "exiftool-13.33_64", "exiftool(-k).exe"),
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "exiftool-13.32_64", "exiftool.exe"),
        # System ExifTool
        "exiftool.exe",
        "exiftool",
        # Common Windows locations
        "C:\\exiftool\\exiftool.exe",
        "C:\\Program Files\\exiftool\\exiftool.exe",
        "C:\\Program Files (x86)\\exiftool\\exiftool.exe"
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            print(f"🔍 ExifTool found at: {path}")
            return path
    
    print("⚠️  ExifTool not found in any expected location")
    return None

def sync_exif_date_to_file_date(file_path, exiftool_path=None, backup_timestamps=None):
    """
    Synchronize EXIF DateTimeOriginal to file creation/modification date.
    
    Args:
        file_path: Path to the media file
        exiftool_path: Path to ExifTool executable
        backup_timestamps: Dictionary to store original timestamps for undo
        
    Returns:
        tuple: (success: bool, message: str, original_times: dict or None)
    """
    if not EXIFTOOL_AVAILABLE:
        return False, "ExifTool not available", None
    
    if not os.path.exists(file_path):
        return False, f"File not found: {file_path}", None
    
    # Auto-detect ExifTool path if not provided
    if not exiftool_path:
        exiftool_path = find_exiftool_path()
        if not exiftool_path:
            return False, "ExifTool executable not found", None
    
    print(f"🔧 Using ExifTool: {exiftool_path}")
    
    try:
        # Get original file timestamps for backup
        stat_info = os.stat(file_path)
        original_times = {
            'atime': stat_info.st_atime,    # Access time
            'mtime': stat_info.st_mtime,    # Modification time
            'ctime': stat_info.st_birthtime      # Creation time (Windows) / Status change time (Unix)
        }
        
        # On Windows, get the real creation time using Windows API
        try:
            if os.name == 'nt':  # Windows
                import ctypes
                from ctypes import wintypes
                
                # Create FILETIME structure
                class FILETIME(ctypes.Structure):
                    _fields_ = [("dwLowDateTime", wintypes.DWORD),
                               ("dwHighDateTime", wintypes.DWORD)]
                
                # Open file to get creation time
                kernel32 = ctypes.windll.kernel32
                handle = kernel32.CreateFileW(
                    file_path,
                    0x80000000,  # GENERIC_READ
                    0x00000001 | 0x00000002,  # FILE_SHARE_READ | FILE_SHARE_WRITE
                    None,
                    3,  # OPEN_EXISTING
                    0x80,  # FILE_ATTRIBUTE_NORMAL
                    None
                )
                
                if handle != -1:  # INVALID_HANDLE_VALUE
                    creation_time = FILETIME()
                    access_time = FILETIME()
                    write_time = FILETIME()
                    
                    # Get file times
                    if kernel32.GetFileTime(handle, ctypes.byref(creation_time), 
                                          ctypes.byref(access_time), ctypes.byref(write_time)):
                        # Convert Windows FILETIME to Unix timestamp
                        EPOCH_AS_FILETIME = 116444736000000000
                        creation_100ns = (creation_time.dwHighDateTime << 32) + creation_time.dwLowDateTime
                        creation_timestamp = (creation_100ns - EPOCH_AS_FILETIME) / 10000000.0
                        
                        # Store the real Windows creation time
                        original_times['windows_creation_time'] = creation_timestamp
                    
                    kernel32.CloseHandle(handle)
        
        except Exception as e:
            # If Windows API fails, we still have the basic timestamps
            print(f"Warning: Could not get Windows creation time: {e}")
        
        # Store in backup if provided
        if backup_timestamps is not None:
            backup_timestamps[file_path] = original_times
        
        # Extract EXIF DateTimeOriginal using ExifTool
        try:
            # Use ExifTool to get metadata
            if exiftool_path:
                with exiftool.ExifToolHelper(executable=exiftool_path) as et:
                    meta = et.get_metadata(file_path)[0]
            else:
                with exiftool.ExifToolHelper() as et:
                    meta = et.get_metadata(file_path)[0]
            
            # Try multiple possible EXIF date fields
            exif_date = None
            date_fields = [
                'EXIF:DateTimeOriginal',
                'EXIF:DateTime', 
                'EXIF:CreateDate',
                'DateTimeOriginal',
                'DateTime',
                'CreateDate'
            ]
            
            for field in date_fields:
                if field in meta and meta[field]:
                    exif_date = meta[field]
                    break
            
            if not exif_date:
                return False, "No EXIF date found in file", original_times
            
            # Parse EXIF date (format: "YYYY:MM:DD HH:MM:SS")
            try:
                import datetime
                # Handle both with and without time component
                if ' ' in str(exif_date):
                    dt = datetime.datetime.strptime(str(exif_date), '%Y:%m:%d %H:%M:%S')
                else:
                    dt = datetime.datetime.strptime(str(exif_date), '%Y:%m:%d')
                
                # Convert to timestamp
                new_timestamp = dt.timestamp()
                
                # FORCE SYNC - Always update timestamps to ensure File:FileCreateDate is correct
                print(f"🔧 Force syncing timestamps to EXIF date...")
                print(f"📊 Current mtime: {datetime.datetime.fromtimestamp(original_times['mtime'])}")
                print(f"📊 Target EXIF date: {dt}")
                print(f"📊 Time difference: {abs(original_times['mtime'] - new_timestamp):.2f} seconds")
                
                # Apply Ultimate Windows Timestamp Sync
                success_count = _apply_ultimate_timestamp_sync(file_path, new_timestamp, dt)
                
                if success_count > 0:
                    return True, f"Successfully synced date from EXIF using {success_count} methods: {dt.strftime('%Y-%m-%d %H:%M:%S')}", original_times
                else:
                    return False, "All timestamp sync methods failed", original_times
                
            except ValueError as e:
                return False, f"Could not parse EXIF date '{exif_date}': {e}", original_times
        
        except Exception as e:
            return False, f"Error accessing EXIF data: {e}", original_times
                
    except Exception as e:
        return False, f"Error syncing date: {e}", None

def _set_file_timestamp_method1(file_path, timestamp):
    """Method 1: Standard os.utime"""
    try:
        os.utime(file_path, (timestamp, timestamp))
        print("   ✅ Method 1: os.utime successful")
        return True
    except Exception as e:
        print(f"   ❌ Method 1: os.utime failed: {e}")
        return False

def _set_file_timestamp_method2(file_path, timestamp):
    """Method 2: Windows API with SetFileTime"""
    try:
        if os.name != 'nt':  # Not Windows
            return False
            
        import ctypes
        from ctypes import wintypes
        
        # Convert to Windows FILETIME
        EPOCH_AS_FILETIME = 116444736000000000
        timestamp_100ns = int((timestamp * 10000000) + EPOCH_AS_FILETIME)
        
        # FILETIME structure
        class FILETIME(ctypes.Structure):
            _fields_ = [("dwLowDateTime", wintypes.DWORD),
                       ("dwHighDateTime", wintypes.DWORD)]
        
        ft = FILETIME()
        ft.dwLowDateTime = timestamp_100ns & 0xFFFFFFFF
        ft.dwHighDateTime = timestamp_100ns >> 32
        
        # Open file with proper flags
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.CreateFileW(
            file_path,
            0x40000000,  # GENERIC_WRITE
            0x00000001 | 0x00000002,  # FILE_SHARE_READ | FILE_SHARE_WRITE
            None,
            3,  # OPEN_EXISTING
            0x00000080,  # FILE_ATTRIBUTE_NORMAL
            None
        )
        
        if handle != -1:
            # Set ALL file timestamps to ensure File:FileCreateDate is updated
            result = kernel32.SetFileTime(
                handle,
                ctypes.byref(ft),  # Creation time (File:FileCreateDate)
                ctypes.byref(ft),  # Last access time
                ctypes.byref(ft)   # Last write time (File:FileModifyDate)
            )
            
            kernel32.CloseHandle(handle)
            
            if result:
                print("   ✅ Method 2: Windows SetFileTime successful")
                return True
            else:
                error_code = kernel32.GetLastError()
                print(f"   ❌ Method 2: SetFileTime failed, Error: {error_code}")
                return False
        else:
            error_code = kernel32.GetLastError()
            print(f"   ❌ Method 2: File open failed, Error: {error_code}")
            return False
    
    except Exception as e:
        print(f"   ❌ Method 2: Windows API failed: {e}")
        return False

def _set_file_timestamp_method3(file_path, dt):
    """Method 3: PowerShell for extra robustness"""
    try:
        if os.name != 'nt':  # Not Windows
            return False
            
        import subprocess
        
        # Format date for PowerShell (ISO 8601)
        ps_date = dt.strftime('%Y-%m-%dT%H:%M:%S')
        
        # PowerShell script for robust timestamp setting
        ps_script = f'''
        $file = Get-Item -LiteralPath "{file_path}"
        $date = [DateTime]::Parse("{ps_date}")
        $file.CreationTime = $date
        $file.LastWriteTime = $date
        $file.LastAccessTime = $date
        Write-Host "PowerShell timestamp sync completed"
        '''
        
        # Execute PowerShell command
        result = subprocess.run([
            'powershell', '-Command', ps_script
        ], capture_output=True, text=True, timeout=15)
        
        if result.returncode == 0:
            print("   ✅ Method 3: PowerShell successful")
            return True
        else:
            print(f"   ❌ Method 3: PowerShell failed: {result.stderr.strip()}")
            return False
    
    except Exception as e:
        print(f"   ❌ Method 3: PowerShell failed: {e}")
        return False

def _apply_ultimate_timestamp_sync(file_path, new_timestamp, dt):
    """
    Apply Ultimate Windows Timestamp Sync using multiple methods
    
    Args:
        file_path: Path to the file
        new_timestamp: Unix timestamp to set
        dt: datetime object for PowerShell method
        
    Returns:
        int: Number of successful methods
    """
    success_count = 0
    print(f"🔧 Ultimate timestamp sync for: {os.path.basename(file_path)}")
    print(f"📅 Target date: {dt.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Method 1: Standard os.utime
    if _set_file_timestamp_method1(file_path, new_timestamp):
        success_count += 1
    
    # Method 2: Windows API with SetFileTime 
    if _set_file_timestamp_method2(file_path, new_timestamp):
        success_count += 1
    
    # Method 3: PowerShell
    if _set_file_timestamp_method3(file_path, dt):
        success_count += 1
    
    # Method 4: System flush to ensure changes are written
    try:
        if os.name == 'nt' and success_count > 0:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            kernel32.FlushFileBuffers(-1)  # Flush all system buffers
            print("   ✅ Method 4: System flush completed")
    except:
        pass
    
    print(f"📊 Result: {success_count}/3 methods successful")
    return success_count

def sync_exif_date_to_file_date(file_path, exiftool_path=None, backup_timestamps=None):
    """
    Synchronize EXIF DateTimeOriginal to file creation/modification date.
    
    Args:
        file_path: Path to the media file
        exiftool_path: Path to ExifTool executable
        backup_timestamps: Dictionary to store original timestamps for undo
        
    Returns:
        tuple: (success: bool, message: str, original_times: dict or None)
    """
    if not EXIFTOOL_AVAILABLE:
        return False, "ExifTool not available", None
    
    if not os.path.exists(file_path):
        return False, f"File not found: {file_path}", None
    
    # Auto-detect ExifTool path if not provided
    if not exiftool_path:
        exiftool_path = find_exiftool_path()
        if not exiftool_path:
            return False, "ExifTool executable not found", None
    
    print(f"🔧 Using ExifTool: {exiftool_path}")
    
    try:
        # Get original file timestamps for backup
        stat_info = os.stat(file_path)
        original_times = {
            'atime': stat_info.st_atime,    # Access time
            'mtime': stat_info.st_mtime,    # Modification time
            'ctime': stat_info.st_ctime     # Creation time (Windows) / Status change time (Unix)
        }
        
        # On Windows, get the real creation time using Windows API
        try:
            if os.name == 'nt':  # Windows
                import ctypes
                from ctypes import wintypes
                
                # Create FILETIME structure
                class FILETIME(ctypes.Structure):
                    _fields_ = [("dwLowDateTime", wintypes.DWORD),
                               ("dwHighDateTime", wintypes.DWORD)]
                
                # Open file to get creation time
                kernel32 = ctypes.windll.kernel32
                handle = kernel32.CreateFileW(
                    file_path,
                    0x80000000,  # GENERIC_READ
                    0x00000001 | 0x00000002,  # FILE_SHARE_READ | FILE_SHARE_WRITE
                    None,
                    3,  # OPEN_EXISTING
                    0x80,  # FILE_ATTRIBUTE_NORMAL
                    None
                )
                
                if handle != -1:  # INVALID_HANDLE_VALUE
                    creation_time = FILETIME()
                    access_time = FILETIME()
                    write_time = FILETIME()
                    
                    # Get file times
                    if kernel32.GetFileTime(handle, ctypes.byref(creation_time), 
                                          ctypes.byref(access_time), ctypes.byref(write_time)):
                        # Convert Windows FILETIME to Unix timestamp
                        EPOCH_AS_FILETIME = 116444736000000000
                        creation_100ns = (creation_time.dwHighDateTime << 32) + creation_time.dwLowDateTime
                        creation_timestamp = (creation_100ns - EPOCH_AS_FILETIME) / 10000000.0
                        
                        # Store the real Windows creation time
                        original_times['windows_creation_time'] = creation_timestamp
                    
                    kernel32.CloseHandle(handle)
        
        except Exception as e:
            # If Windows API fails, we still have the basic timestamps
            print(f"Warning: Could not get Windows creation time: {e}")
        
        # Store in backup if provided
        if backup_timestamps is not None:
            backup_timestamps[file_path] = original_times
        
        # Extract EXIF DateTimeOriginal using ExifTool
        try:
            # Use ExifTool to get metadata
            if exiftool_path:
                with exiftool.ExifToolHelper(executable=exiftool_path) as et:
                    meta = et.get_metadata(file_path)[0]
            else:
                with exiftool.ExifToolHelper() as et:
                    meta = et.get_metadata(file_path)[0]
            
            # Try multiple possible EXIF date fields
            exif_date = None
            date_fields = [
                'EXIF:DateTimeOriginal',
                'EXIF:DateTime', 
                'EXIF:CreateDate',
                'DateTimeOriginal',
                'DateTime',
                'CreateDate'
            ]
            
            for field in date_fields:
                if field in meta and meta[field]:
                    exif_date = meta[field]
                    break
            
            if not exif_date:
                return False, "No EXIF date found in file", original_times
            
            # Parse EXIF date (format: "YYYY:MM:DD HH:MM:SS")
            try:
                import datetime
                # Handle both with and without time component
                if ' ' in str(exif_date):
                    dt = datetime.datetime.strptime(str(exif_date), '%Y:%m:%d %H:%M:%S')
                else:
                    dt = datetime.datetime.strptime(str(exif_date), '%Y:%m:%d')
                
                # Convert to timestamp
                new_timestamp = dt.timestamp()
                
                # FORCE SYNC - Always update timestamps to ensure File:FileCreateDate is correct
                print(f"🔧 Force syncing timestamps to EXIF date...")
                print(f"📊 Current mtime: {datetime.datetime.fromtimestamp(original_times['mtime'])}")
                print(f"📊 Target EXIF date: {dt}")
                print(f"📊 Time difference: {abs(original_times['mtime'] - new_timestamp):.2f} seconds")
                
                # Apply Ultimate Windows Timestamp Sync
                success_count = _apply_ultimate_timestamp_sync(file_path, new_timestamp, dt)
                
                if success_count > 0:
                    return True, f"Successfully synced date from EXIF using {success_count} methods: {dt.strftime('%Y-%m-%d %H:%M:%S')}", original_times
                else:
                    return False, "All timestamp sync methods failed", original_times
                
            except ValueError as e:
                return False, f"Could not parse EXIF date '{exif_date}': {e}", original_times
        
        except Exception as e:
            return False, f"Error accessing EXIF data: {e}", original_times
                
    except Exception as e:
        return False, f"Error syncing date: {e}", None

def _restore_windows_creation_time(file_path, creation_timestamp):
    """Restore Windows creation time using Windows API"""
    try:
        import ctypes
        from ctypes import wintypes
        
        # Convert timestamp to Windows FILETIME format
        EPOCH_AS_FILETIME = 116444736000000000  # January 1, 1970 as FILETIME
        timestamp_100ns = int((creation_timestamp * 10000000) + EPOCH_AS_FILETIME)
        
        # Create FILETIME structure
        class FILETIME(ctypes.Structure):
            _fields_ = [("dwLowDateTime", wintypes.DWORD),
                       ("dwHighDateTime", wintypes.DWORD)]
        
        ft = FILETIME()
        ft.dwLowDateTime = timestamp_100ns & 0xFFFFFFFF
        ft.dwHighDateTime = timestamp_100ns >> 32
        
        # Open file handle with write access
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.CreateFileW(
            file_path,
            0x40000000,  # GENERIC_WRITE
            0x00000001 | 0x00000002,  # FILE_SHARE_READ | FILE_SHARE_WRITE
            None,
            3,  # OPEN_EXISTING
            0x80,  # FILE_ATTRIBUTE_NORMAL
            None
        )
        
        if handle != -1:  # INVALID_HANDLE_VALUE
            # Restore original creation time
            kernel32.SetFileTime(handle, ctypes.byref(ft), None, None)
            kernel32.CloseHandle(handle)
            return True
        
        return False
    except Exception:
        return False

def restore_file_timestamps(file_path, original_times):
    """
    Restore original file timestamps from backup.
    
    Args:
        file_path: Path to the file
        original_times: Dictionary with original timestamps
        
    Returns:
        tuple: (success: bool, message: str)
    """
    try:
        if not os.path.exists(file_path):
            return False, f"File not found: {file_path}"
        
        if not original_times:
            return False, "No backup timestamps available"
        
        # Restore access and modification times
        os.utime(file_path, (original_times['atime'], original_times['mtime']))
        
        # On Windows, also restore creation time using Windows API
        if os.name == 'nt':  # Windows
            # Use the real Windows creation time if available, otherwise fall back to ctime
            creation_timestamp = original_times.get('windows_creation_time', original_times.get('ctime'))
            
            if creation_timestamp:
                success = _restore_windows_creation_time(file_path, creation_timestamp)
                if not success:
                    print(f"Warning: Could not restore creation time for {file_path}")
        
        return True, "File timestamps restored successfully"
        
    except Exception as e:
        return False, f"Error restoring timestamps: {e}"

def batch_sync_exif_dates(file_paths, exiftool_path=None, progress_callback=None):
    """
    Batch synchronize EXIF dates to file dates for multiple files.
    
    Args:
        file_paths: List of file paths to process
        exiftool_path: Path to ExifTool executable
        progress_callback: Optional callback function for progress updates
        
    Returns:
        tuple: (successes: list, errors: list, backup_data: dict)
    """
    successes = []
    errors = []
    backup_data = {}
    
    for i, file_path in enumerate(file_paths):
        if progress_callback:
            progress_callback(f"Processing {i+1}/{len(file_paths)}: {os.path.basename(file_path)}")
        
        success, message, original_times = sync_exif_date_to_file_date(
            file_path, exiftool_path, backup_data
        )
        
        if success:
            successes.append((file_path, message))
        else:
            errors.append((file_path, message))
    
    return successes, errors, backup_data

def batch_restore_timestamps(backup_data, progress_callback=None):
    """
    Batch restore original timestamps for multiple files.
    
    Args:
        backup_data: Dictionary mapping file paths to original timestamps
        progress_callback: Optional callback function for progress updates
        
    Returns:
        tuple: (successes: list, errors: list)
    """
    successes = []
    errors = []
    
    file_paths = list(backup_data.keys())
    
    for i, file_path in enumerate(file_paths):
        if progress_callback:
            progress_callback(f"Restoring {i+1}/{len(file_paths)}: {os.path.basename(file_path)}")
        
        original_times = backup_data[file_path]
        success, message = restore_file_timestamps(file_path, original_times)
        
        if success:
            successes.append((file_path, message))
        else:
            errors.append((file_path, message))
    
    return successes, errors
