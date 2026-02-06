#!/usr/bin/env python3
"""
EXIF data extraction and handling for the RenameFiles application.
This module provides the exact same functionality as the original RenameFiles.py
"""

import os
import time
import threading
import subprocess
import glob
import shutil
# Pre-import commonly used modules (performance optimization)
try:
    import ctypes
    from ctypes import wintypes
    CTYPES_AVAILABLE = True
except ImportError:
    CTYPES_AVAILABLE = False
    
from .logger_util import get_logger
log = get_logger()

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

# Import ExifService from the new dedicated module
from .exif_service_new import ExifService

# Global variables for backward compatibility with legacy code
# These are kept for functions that are still called from outside the ExifService
_global_exiftool_instance = None
_global_exiftool_path = None


# Legacy wrapper functions for backward compatibility
def get_cached_exif_data(file_path, method, exiftool_path=None):
    """
    Legacy wrapper - calls extract_exif_fields_with_retry which uses shared ExifTool instance.
    OPTIMIZATION: No ExifService instance created, uses global ExifTool directly.
    """
    return extract_exif_fields_with_retry(file_path, method, exiftool_path, max_retries=2)

def get_selective_cached_exif_data(file_path, method, exiftool_path=None, need_date=True, need_camera=False, need_lens=False):
    """
    Legacy wrapper - calls extract_selective_exif_fields which uses shared ExifTool instance.
    OPTIMIZATION: No ExifService instance created, uses global ExifTool directly.
    """
    return extract_selective_exif_fields(
        file_path, method, exiftool_path,
        need_date=need_date, need_camera=need_camera, need_lens=need_lens
    )

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
        log.warning(f"extract_selective_exif_fields: File not found: {normalized_path}")
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
        log.warning(f"get_exiftool_metadata_shared: File not found: {normalized_path}")
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
                except Exception:
                    pass
            
            # Create new instance
            if exiftool_path and os.path.exists(exiftool_path):
                _global_exiftool_instance = exiftool.ExifToolHelper(executable=exiftool_path)
                log.info(f"Created ExifTool instance with: {exiftool_path}")
            else:
                _global_exiftool_instance = exiftool.ExifToolHelper()
                log.info("Created default ExifTool instance")
            
            _global_exiftool_path = exiftool_path
            
            # Start the instance
            _global_exiftool_instance.__enter__()
        
        # Get metadata using the shared instance with normalized path
        meta = _global_exiftool_instance.get_metadata([normalized_path])[0]
        return meta
        
    except Exception as e:
        # If the shared instance fails, fall back to a temporary instance
        log.warning(f"Shared ExifTool instance failed, using temporary instance: {e}")
        try:
            if exiftool_path and os.path.exists(exiftool_path):
                with exiftool.ExifToolHelper(executable=exiftool_path) as et:
                    return et.get_metadata([normalized_path])[0]
            else:
                with exiftool.ExifToolHelper() as et:
                    return et.get_metadata([normalized_path])[0]
        except Exception as e2:
            log.error(f"Temporary ExifTool instance also failed: {e2}")
            return {}

def clear_global_exif_cache() -> None:
    """Clear any global EXIF state.

    For backward compatibility only. The global ``get_exiftool_metadata_shared``
    function is stateless (no result cache), so there is nothing to evict here.
    New code should use :class:`ExifService` instead.
    """
    # The legacy global path does not maintain a result cache, but we
    # reset the global instance so a fresh connection is established on
    # the next call.
    global _global_exiftool_instance
    if _global_exiftool_instance is not None:
        try:
            _global_exiftool_instance.__exit__(None, None, None)
        except Exception:
            pass
        _global_exiftool_instance = None

def cleanup_global_exiftool() -> None:
    """Clean up the global ExifTool instance when done with batch processing."""
    global _global_exiftool_instance
    
    if _global_exiftool_instance is not None:
        try:
            _global_exiftool_instance.__exit__(None, None, None)
        except Exception:
            pass
        _global_exiftool_instance = None

def extract_exif_fields_with_retry(image_path, method, exiftool_path=None, max_retries=3):
    """
    Extracts EXIF fields with retry mechanism for reliability.
    OPTIMIZATION: Now uses shared ExifTool instance for better performance!
    """
    # CRITICAL FIX: Normalize path to prevent double backslashes
    normalized_path = os.path.normpath(image_path)
    
    # Verify file exists
    if not os.path.exists(normalized_path):
        log.warning(f"extract_exif_fields_with_retry: File not found: {normalized_path}")
        return None, None, None
    
    for attempt in range(max_retries):
        try:
            if method == "exiftool":
                # PERFORMANCE OPTIMIZATION: Use shared ExifTool instance instead of creating new process
                meta = get_exiftool_metadata_shared(normalized_path, exiftool_path)
                
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
                log.error(f"EXIF extraction failed after {max_retries} attempts: {e}")
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
        log.debug(f"Failed to extract image number: {e}")
    
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
        log.debug(f"Failed to get file timestamp: {e}")
        return None

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
                    except (ValueError, TypeError, ZeroDivisionError):
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
                    except (ValueError, TypeError, ZeroDivisionError):
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
                    except (ValueError, TypeError, ZeroDivisionError):
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
        log.error(f"Error extracting metadata from {file_path}: {e}")
        return {}

def find_exiftool_path():
    """
    Find the ExifTool executable path automatically
    
    Returns:
        str: Path to ExifTool executable or None if not found
    """
    script_dir = os.path.dirname(os.path.dirname(__file__))

    def verify_exiftool(executable_path):
        """Quick smoke test to verify exiftool executable works and returns a version string.

        Returns version string on success, None on failure.
        """
        try:
            if not os.path.exists(executable_path):
                return None
            # Try to run the binary with -ver (short, safe)
            proc = subprocess.run([executable_path, "-ver"], capture_output=True, text=True, timeout=2)
            if proc.returncode == 0 and proc.stdout:
                ver = proc.stdout.strip().splitlines()[0].strip()
                log.debug(f"verify_exiftool: found version {ver} at {executable_path}")
                return ver
            return None
        except Exception as e:
            log.debug(f"verify_exiftool failed for {executable_path}: {e}")
            return None

    # 1) Search for project-local exiftool folders with flexible names (exiftool-*)
    for d in glob.glob(os.path.join(script_dir, "exiftool*")):
        if os.path.isdir(d):
            for fname in ("exiftool(-k).exe", "exiftool.exe", "exiftool"):
                candidate = os.path.join(d, fname)
                if os.path.exists(candidate):
                    if verify_exiftool(candidate):
                        log.debug(f"ExifTool located at: {candidate}")
                        return candidate

    # 2) Check a few legacy project paths explicitly (backwards compatibility)
    legacy_paths = [
        os.path.join(script_dir, "exiftool-13.33_64", "exiftool(-k).exe"),
        os.path.join(script_dir, "exiftool-13.32_64", "exiftool.exe"),
    ]
    for path in legacy_paths:
        if os.path.exists(path) and verify_exiftool(path):
            log.debug(f"ExifTool located at: {path}")
            return path

    # 3) Check system PATH using shutil.which
    for name in ("exiftool.exe", "exiftool"):
        which_path = shutil.which(name)
        if which_path and verify_exiftool(which_path):
            log.debug(f"ExifTool located on PATH: {which_path}")
            return which_path

    # 4) Common Windows locations
    common_windows = [
        "C:\\exiftool\\exiftool.exe",
        "C:\\Program Files\\exiftool\\exiftool.exe",
        "C:\\Program Files (x86)\\exiftool\\exiftool.exe",
    ]
    for path in common_windows:
        if os.path.exists(path) and verify_exiftool(path):
            log.debug(f"ExifTool located at: {path}")
            return path

    log.warning("ExifTool not found in expected locations")
    return None

def sync_exif_date_to_file_date(file_path, exiftool_path=None, backup_timestamps=None, options=None, preexif_dt=None):
    """
    Synchronize EXIF DateTimeOriginal to file creation/modification date.
    
    Args:
        file_path: Path to the media file
        exiftool_path: Path to ExifTool executable
        backup_timestamps: Dictionary to store original timestamps for undo
        
    Returns:
        tuple: (success: bool, message: str, original_times: dict or None)
    """
    if not EXIFTOOL_AVAILABLE and not (options and options.get('use_custom')) and preexif_dt is None:
        # Allow custom date OR externally provided EXIF datetime without local ExifTool
        return False, "ExifTool not available", None
    
    if not os.path.exists(file_path):
        return False, f"File not found: {file_path}", None
    
    # Auto-detect ExifTool path if not provided
    if not exiftool_path:
        exiftool_path = find_exiftool_path()
        if not exiftool_path:
            return False, "ExifTool executable not found", None
    
    log.info(f"Using ExifTool executable: {exiftool_path}")
    
    try:
        # Get original file timestamps for backup
        stat_info = os.stat(file_path)
        original_times = {
            'atime': stat_info.st_atime,    # Access time
            'mtime': stat_info.st_mtime,    # Modification time
            'ctime': getattr(stat_info, 'st_birthtime', stat_info.st_ctime),  # Creation time (macOS/Windows) or status change time (Linux)
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
            log.debug(f"Could not get Windows creation time: {e}")
        
        # Store in backup if provided
        if backup_timestamps is not None:
            backup_timestamps[file_path] = original_times
        
        # Determine target datetime
        dt = None
        if options and options.get('use_custom') and options.get('custom_dt'):
            dt = options['custom_dt']
        elif preexif_dt is not None:
            # Pre-fetched raw EXIF datetime string (already from allowed fields)
            try:
                import datetime as _dt
                value = str(preexif_dt)
                if ' ' in value:
                    dt = _dt.datetime.strptime(value, '%Y:%m:%d %H:%M:%S')
                else:
                    dt = _dt.datetime.strptime(value, '%Y:%m:%d')
            except Exception:
                return False, "Invalid pre-extracted EXIF date", original_times
        else:
            # Extract EXIF DateTimeOriginal using ExifTool (fallback path)
            try:
                if not EXIFTOOL_AVAILABLE:
                    return False, "EXIF extraction not available", original_times
                helper_exec = exiftool_path if exiftool_path else None
                with exiftool.ExifToolHelper(executable=helper_exec) as et:
                    meta = et.get_metadata(file_path)[0]
                exif_date = None
                for field in ['EXIF:DateTimeOriginal','EXIF:DateTime','EXIF:CreateDate','DateTimeOriginal','DateTime','CreateDate']:
                    if field in meta and meta[field]:
                        exif_date = meta[field]
                        break
                if not exif_date:
                    return False, "No EXIF date found in file", original_times
                import datetime as _dt
                value = str(exif_date)
                if ' ' in value:
                    dt = _dt.datetime.strptime(value, '%Y:%m:%d %H:%M:%S')
                else:
                    dt = _dt.datetime.strptime(value, '%Y:%m:%d')
            except Exception as e:
                return False, f"Error accessing EXIF data: {e}", original_times
        if not dt:
            return False, "No target date/time determined", original_times
        new_timestamp = dt.timestamp()
        # Selective update logic
        set_creation = True
        set_mod = True
        set_access = True
        if options:
            set_creation = options.get('creation', True)
            set_mod = options.get('modification', True)
            set_access = options.get('access', True)
        try:
            # Always backup performed above. Now update selected fields.
            # Basic: use os.utime for access/modification
            atime = original_times['atime'] if not set_access else new_timestamp
            mtime = original_times['mtime'] if not set_mod else new_timestamp
            os.utime(file_path, (atime, mtime))
            # Creation time (Windows) via API only if requested
            creation_ok = True
            if set_creation and os.name == 'nt':
                try:
                    import ctypes
                    from ctypes import wintypes
                    EPOCH_AS_FILETIME = 116444736000000000
                    ts_100ns = int((new_timestamp * 10000000) + EPOCH_AS_FILETIME)
                    class FILETIME(ctypes.Structure):
                        _fields_ = [("dwLowDateTime", wintypes.DWORD),("dwHighDateTime", wintypes.DWORD)]
                    ft = FILETIME()
                    ft.dwLowDateTime = ts_100ns & 0xFFFFFFFF
                    ft.dwHighDateTime = ts_100ns >> 32
                    k32 = ctypes.windll.kernel32
                    handle = k32.CreateFileW(
                        file_path,0x40000000,0x00000001|0x00000002,None,3,0x80,None
                    )
                    if handle != -1:
                        if not k32.SetFileTime(handle, ctypes.byref(ft), None if not set_access else ctypes.byref(ft), None if not set_mod else ctypes.byref(ft)):
                            creation_ok = False
                        k32.CloseHandle(handle)
                    else:
                        creation_ok = False
                except Exception as e:
                    log.debug(f"Creation time set failed: {e}")
                    creation_ok = False
            return True, f"Timestamps updated ({'C' if set_creation else ''}{'M' if set_mod else ''}{'A' if set_access else ''}) -> {dt.strftime('%Y-%m-%d %H:%M:%S')}", original_times
        except Exception as e:
            return False, f"Failed to set timestamps: {e}", original_times
                
    except Exception as e:
        return False, f"Error syncing date: {e}", None

def _set_file_timestamp_method1(file_path, timestamp):
    """Method 1: Standard os.utime"""
    try:
        os.utime(file_path, (timestamp, timestamp))
        log.debug("Method 1 (os.utime) successful")
        return True
    except Exception as e:
        log.debug(f"Method 1 (os.utime) failed: {e}")
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
                log.debug("Method 2 (SetFileTime) successful")
                return True
            else:
                error_code = kernel32.GetLastError()
                log.debug(f"Method 2 (SetFileTime) failed, Error: {error_code}")
                return False
        else:
            error_code = kernel32.GetLastError()
            log.debug(f"Method 2 file open failed, Error: {error_code}")
            return False
    
    except Exception as e:
        log.debug(f"Method 2 (Windows API) exception: {e}")
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
            log.debug("Method 3 (PowerShell) successful")
            return True
        else:
            log.debug(f"Method 3 (PowerShell) failed: {result.stderr.strip()}")
            return False
    
    except Exception as e:
        log.debug(f"Method 3 (PowerShell) exception: {e}")
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
    log.info(f"Ultimate timestamp sync for: {os.path.basename(file_path)}")
    log.debug(f"Target date: {dt.strftime('%Y-%m-%d %H:%M:%S')}")
    
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
            log.debug("Method 4 (FlushFileBuffers) successful")
    except Exception:
        pass
    
    log.info(f"Timestamp sync result: {success_count}/3 methods succeeded")
    return success_count

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
                    log.debug(f"Could not restore creation time for {file_path}")
        
        return True, "File timestamps restored successfully"
        
    except Exception as e:
        return False, f"Error restoring timestamps: {e}"

def batch_sync_exif_dates(file_paths, exiftool_path=None, progress_callback=None, options=None):
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

    # Fast path: prefetch all EXIF datetimes in one ExifTool invocation if possible
    prefetch_map = {}
    use_custom = options and options.get('use_custom')
    can_prefetch = EXIFTOOL_AVAILABLE and not use_custom and file_paths
    if can_prefetch:
        try:
            helper_exec = exiftool_path if exiftool_path else None
            with exiftool.ExifToolHelper(executable=helper_exec) as et:
                # Chunk to avoid extremely long command lines (safety)
                CHUNK = 100
                for start in range(0, len(file_paths), CHUNK):
                    subset = file_paths[start:start+CHUNK]
                    metas = et.get_metadata(subset)
                    for meta in metas:
                        # meta['SourceFile'] usually contains absolute path
                        fpath = meta.get('SourceFile')
                        if not fpath:
                            continue
                        dt_value = None
                        for field in ['EXIF:DateTimeOriginal','EXIF:DateTime','EXIF:CreateDate','DateTimeOriginal','DateTime','CreateDate']:
                            if field in meta and meta[field]:
                                dt_value = meta[field]
                                break
                        if dt_value:
                            prefetch_map[fpath] = dt_value
            if progress_callback:
                progress_callback(f"Prefetched EXIF datetimes for {len(prefetch_map)} files")
        except Exception as e:
            if progress_callback:
                progress_callback(f"Prefetch failed, falling back: {e}")
            prefetch_map = {}

    for i, file_path in enumerate(file_paths):
        if progress_callback:
            progress_callback(f"Processing {i+1}/{len(file_paths)}: {os.path.basename(file_path)}")

        pre_dt = prefetch_map.get(file_path)
        success, message, original_times = sync_exif_date_to_file_date(
            file_path, exiftool_path, backup_data, options=options, preexif_dt=pre_dt
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


def restore_exif_timestamps(file_path, original_exif, exiftool_path):
    """
    Restore original EXIF timestamps from backup.
    
    Args:
        file_path: Path to the file
        original_exif: Dictionary with original EXIF date fields
        exiftool_path: Path to ExifTool executable
        
    Returns:
        tuple: (success: bool, message: str)
    """
    import subprocess
    
    try:
        if not os.path.exists(file_path):
            return False, f"File not found: {file_path}"
        
        if not original_exif:
            return False, "No backup EXIF data available"
        
        if not exiftool_path:
            exiftool_path = find_exiftool_path()
            if not exiftool_path:
                return False, "ExifTool executable not found"
        
        # Build ExifTool command to restore all backed-up fields
        cmd = [exiftool_path, "-overwrite_original"]
        
        # Add each backed-up field
        for field, value in original_exif.items():
            # Format: -EXIF:DateTimeOriginal="2024:01:15 10:30:45"
            cmd.append(f'-{field}={value}')
        
        cmd.append(file_path)
        
        # Execute ExifTool
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        
        if result.returncode == 0:
            return True, "EXIF timestamps restored successfully"
        else:
            return False, f"ExifTool error: {result.stderr}"
        
    except Exception as e:
        return False, f"Error restoring EXIF timestamps: {e}"


def batch_restore_exif_timestamps(backup_data, exiftool_path, progress_callback=None):
    """
    Batch restore original EXIF timestamps for multiple files.
    
    Args:
        backup_data: Dictionary mapping file paths to original EXIF data
        exiftool_path: Path to ExifTool executable
        progress_callback: Optional callback function for progress updates
        
    Returns:
        tuple: (successes: list, errors: list)
    """
    successes = []
    errors = []
    
    file_paths = list(backup_data.keys())
    
    for i, file_path in enumerate(file_paths):
        if progress_callback:
            progress_callback(f"Restoring EXIF {i+1}/{len(file_paths)}: {os.path.basename(file_path)}")
        
        original_exif = backup_data[file_path]
        success, message = restore_exif_timestamps(file_path, original_exif, exiftool_path)
        
        if success:
            successes.append((file_path, message))
        else:
            errors.append((file_path, message))
    
    return successes, errors

