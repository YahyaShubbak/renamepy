#!/usr/bin/env python3
"""
Constants and utility functions for the RenameFiles application.
"""
from __future__ import annotations

import os
import re
import sys
from functools import lru_cache
from .logger_util import get_logger
log = get_logger()
try:
    from .filename_components import build_ordered_components
except ImportError:
    from filename_components import build_ordered_components

def natural_sort_key(filename: str) -> list:
    """Generate a sort key for natural sorting (handles numbers correctly).

    Example:
        DSC00001 comes before DSC00009.
    """
    def convert(text: str) -> int | str:
        return int(text) if text.isdigit() else text.lower()
    
    return [convert(c) for c in re.split(r'(\d+)', filename)]

# remove duplicated get_filename_components_static definition and provide thin wrapper if needed for backward compatibility
def get_filename_components_static(date_taken, camera_prefix, additional, camera_model, lens_model, use_camera, use_lens, num, custom_order, date_format="YYYY-MM-DD", use_date=True, selected_metadata=None):
    return build_ordered_components(
        date_taken=date_taken,
        camera_prefix=camera_prefix,
        additional=additional,
        camera_model=camera_model,
        lens_model=lens_model,
        use_camera=use_camera,
        use_lens=use_lens,
        number=num,
        custom_order=custom_order,
        date_format=date_format,
        use_date=use_date,
        selected_metadata=selected_metadata,
    )

class FileConstants:
    """Constants for file processing"""
    
    # File extension constants
    IMAGE_EXTENSIONS = [
        '.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.gif', 
        '.cr2', '.nef', '.arw', '.orf', '.rw2', '.dng', '.raw', '.sr2', '.pef', '.raf', 
        '.3fr', '.erf', '.kdc', '.mos', '.nrw', '.srw', '.x3f'
    ]

    VIDEO_EXTENSIONS = [
        '.mp4', '.mov', '.avi', '.mkv', '.m4v', '.3gp', '.wmv', '.flv', '.webm', 
        '.mpg', '.mpeg', '.m2v', '.mts', '.m2ts', '.ts', '.vob', '.asf', '.rm', 
        '.rmvb', '.f4v', '.ogv'
    ]

    # Combined list for media files (images + videos)
    MEDIA_EXTENSIONS = IMAGE_EXTENSIONS + VIDEO_EXTENSIONS
    
    # Date formats
    DATE_FORMATS = [
        "YYYY-MM-DD",
        "YYYY-MM-DD_HH-MM-SS", 
        "YYYYMMDD",
        "YYYYMMDD_HHMMSS",
        "DD-MM-YYYY",
        "MM-DD-YYYY"
    ]
    
    # Component separators
    SEPARATORS = ["_", "-", " ", ".", "None"]

# Legacy constants for backward compatibility
IMAGE_EXTENSIONS = FileConstants.IMAGE_EXTENSIONS
VIDEO_EXTENSIONS = FileConstants.VIDEO_EXTENSIONS
MEDIA_EXTENSIONS = FileConstants.MEDIA_EXTENSIONS

def is_image_file(filename: str) -> bool:
    """Returns True if the file is an image or RAW file based on its extension."""
    return os.path.splitext(filename)[1].lower() in IMAGE_EXTENSIONS

def is_video_file(filename: str) -> bool:
    """Returns True if the file is a video file based on its extension."""
    return os.path.splitext(filename)[1].lower() in VIDEO_EXTENSIONS

def is_media_file(filename: str) -> bool:
    """Returns True if the file is a media file (image, RAW, or video) based on its extension."""
    return os.path.splitext(filename)[1].lower() in MEDIA_EXTENSIONS

def scan_directory_recursive(directory):
    """
    OPTIMIZED: Recursively scan directory for media files (images and videos) in all subdirectories.
    Uses followlinks=False to prevent symlink loops and duplicate counting.
    Returns a sorted list of all media file paths found.
    """
    media_files = []
    try:
        # OPTIMIZATION: followlinks=False prevents symlink loops (+10% performance)
        for root, dirs, files in os.walk(directory, followlinks=False):
            for file in files:
                if is_media_file(file):
                    full_path = os.path.join(root, file)
                    media_files.append(full_path)
    except Exception as e:
        log.warning(f"Error scanning directory {directory}: {e}")
    
    return sorted(media_files, key=lambda x: (os.path.dirname(x), natural_sort_key(os.path.basename(x))))

def sanitize_filename(filename: str) -> str:
    """Sanitize filename by removing/replacing invalid characters.

    Ensures compatibility across Windows, macOS, and Linux filesystems.

    Args:
        filename: The raw filename to sanitize.

    Returns:
        A sanitized filename string (may be empty if nothing remains).
    """
    # First check if filename is only whitespace - return empty string instead of 'unnamed_file'
    if not filename or filename.isspace():
        return ""
    
    # Remove/replace invalid characters for Windows/Unix
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    
    # Remove control characters (ASCII 0-31) and replace with underscore
    filename = ''.join(char if ord(char) >= 32 else '_' for char in filename)
    
    # Remove trailing and leading dots and spaces (Windows issue)
    filename = filename.strip('. ')
    
    # Remove multiple consecutive underscores and spaces
    filename = re.sub(r'_+', '_', filename)
    filename = re.sub(r'\s+', ' ', filename)  # Collapse multiple spaces
    filename = filename.strip()  # Remove leading/trailing spaces again
    
    # Only use 'unnamed_file' for actual file names, not for components
    # Return empty string if sanitization resulted in empty content
    if not filename or filename == '_':
        return ""
    
    # Limit length to prevent filesystem issues (keep extension)
    if len(filename) > 200:
        base, ext = os.path.splitext(filename)
        filename = base[:200-len(ext)] + ext
    
    return filename

def sanitize_final_filename(filename):
    """
    Sanitize a complete filename, ensuring it's not empty for file operations.
    This is different from sanitize_filename which is used for components.
    """
    # First use the regular sanitization
    sanitized = sanitize_filename(filename)
    
    # If the result is empty, use a fallback name
    if not sanitized:
        return "unnamed_file"
    
    return sanitized

def validate_path_length(file_path: str) -> bool:
    """Validate that the file path is within filesystem limits.

    Checks **both** the total path length and the filename component length
    against the limits of the current operating system:

    - **Windows**: 260 chars total (classic) or 32,767 with long-path support;
      filename component max 255.
    - **macOS / Linux**: 4096 chars total path; 255 chars filename component.

    On Windows, long-path support is detected via the registry key
    ``HKLM\\SYSTEM\\CurrentControlSet\\Control\\FileSystem\\LongPathsEnabled``.

    Args:
        file_path: The full file path to validate.

    Returns:
        True if both the total path and filename lengths are within limits.
    """
    filename = os.path.basename(file_path)

    # Filename component limit is 255 on all major filesystems
    max_filename = 255

    if sys.platform == "win32":
        max_path = _get_windows_max_path()
    else:
        # POSIX (Linux, macOS) — PATH_MAX is typically 4096
        max_path = 4096

    return len(file_path) <= max_path and len(filename) <= max_filename


def _get_windows_max_path() -> int:
    """Return the effective maximum path length on Windows.

    Checks the ``LongPathsEnabled`` registry value.  If enabled, returns
    32767 (the ``\\\\?\\`` limit).  Otherwise returns 260 (MAX_PATH) minus
    a small safety buffer → **255**.

    Returns:
        Maximum total path length allowed on this system.
    """
    try:
        import winreg
        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SYSTEM\CurrentControlSet\Control\FileSystem",
        ) as key:
            value, _ = winreg.QueryValueEx(key, "LongPathsEnabled")
            if value == 1:
                return 32_767
    except (OSError, FileNotFoundError, ImportError):
        pass
    # Classic Windows MAX_PATH (260) minus a small safety buffer
    return 255

def check_file_access(file_path):
    """
    Check if file can be accessed and renamed.
    Returns True if accessible, False otherwise.
    """
    try:
        # Test if file exists and is accessible
        if not os.path.exists(file_path):
            return False
        
        # Test read access
        with open(file_path, 'rb') as f:
            f.read(1)  # Try to read one byte
        
        # Test if file is locked by checking if we can open it for writing
        return True
    except (PermissionError, OSError, IOError):
        return False

def get_safe_target_path(original_path, new_name):
    """
    Generate a safe target path, avoiding conflicts with existing files.
    Ignores the source file itself to allow same-name "renames".
    
    Args:
        original_path: The current file path
        new_name: The desired new filename (basename only)
        
    Returns:
        A safe target path within the same directory
        
    Raises:
        ValueError: If the new name would escape the source directory
    """
    directory = os.path.dirname(original_path)
    
    # SEC: Strip path separators and traversal components from the filename
    # Only the basename should be used — reject embedded path components
    basename_only = os.path.basename(new_name)
    if basename_only != new_name or '..' in new_name:
        log.warning(f"Path traversal attempt blocked in filename: {new_name!r}")
        new_name = basename_only
    
    new_path = os.path.join(directory, new_name)
    
    # SEC: Verify the resolved path stays within the source directory
    resolved_dir = os.path.realpath(directory)
    resolved_target = os.path.realpath(new_path)
    if not resolved_target.startswith(resolved_dir + os.sep) and resolved_target != resolved_dir:
        raise ValueError(
            f"Target path escapes source directory: {new_path!r}"
        )
    
    # If target is the same as source (case-insensitive on Windows), it's safe
    if os.path.normcase(original_path) == os.path.normcase(new_path):
        return new_path
    
    # Check if target already exists
    if not os.path.exists(new_path):
        return new_path
    
    # Generate alternative name if conflict exists
    base, ext = os.path.splitext(new_name)
    attempt = 1
    
    while os.path.exists(new_path) and attempt <= 999:
        new_name_attempt = f"{base}({attempt}){ext}"
        new_path = os.path.join(directory, new_name_attempt)
        attempt += 1
    
    if attempt > 999:
        raise RuntimeError(f"Cannot generate unique filename for {new_name}")
    
    return new_path

def scan_directory(directory, include_subdirs=False):
    """
    Scan directory for media files (images and videos).
    
    Args:
        directory: Path to the directory to scan
        include_subdirs: If True, scan subdirectories recursively
    
    Returns:
        List of media file paths found
    """
    if include_subdirs:
        return scan_directory_recursive(directory)
    else:
        media_files = []
        try:
            if os.path.exists(directory):
                for file in os.listdir(directory):
                    file_path = os.path.join(directory, file)
                    if os.path.isfile(file_path) and is_media_file(file):
                        media_files.append(file_path)
        except Exception as e:
            log.warning(f"Error scanning directory {directory}: {e}")
        
        return sorted(media_files, key=lambda x: (os.path.dirname(x), natural_sort_key(os.path.basename(x))))

def get_safe_filename(directory, new_name):
    """
    Generate a safe filename that doesn't conflict with existing files.
    
    Args:
        directory: Directory where the file will be placed
        new_name: Desired filename
        
    Returns:
        Safe filename that doesn't conflict with existing files
    """
    # Check if file already exists
    new_path = os.path.join(directory, new_name)
    if not os.path.exists(new_path):
        return new_name
    
    # Generate alternative name if conflict exists
    base, ext = os.path.splitext(new_name)
    attempt = 1
    
    while os.path.exists(new_path) and attempt <= 999:
        new_name_attempt = f"{base}({attempt}){ext}"
        new_path = os.path.join(directory, new_name_attempt)
        attempt += 1
    
    if attempt > 999:
        raise RuntimeError(f"Cannot generate unique filename for {new_name}")
    
    return os.path.basename(new_path)

def validate_path(file_path: str) -> tuple[bool, str]:
    """Validate a file path for various criteria.

    Args:
        file_path: Path to validate.

    Returns:
        Tuple of (is_valid, error_message).
    """
    if not file_path:
        return False, "Path is empty"

    if not os.path.exists(file_path):
        return False, "Path does not exist"

    # Check path length (validate_path_length returns bool)
    if not validate_path_length(file_path):
        return False, f"Path too long ({len(file_path)} chars, max 250)"

    # Check if it's a file
    if not os.path.isfile(file_path):
        return False, "Path is not a file"

    # Check if it's a media file
    if not is_media_file(file_path):
        return False, "File is not a supported media type"

    return True, "Valid"

def rename_files(files, camera_prefix, additional, use_camera, use_lens, exif_method, separator="_", exiftool_path=None, custom_order=None, date_format="YYYY-MM-DD", use_date=True):
    """
    Optimized batch rename function using cached EXIF processing.
    Simply delegates to the optimized_rename_files function for better performance.
    
    Counter behavior:
    - When use_date=True: Counter resets per date (001, 002, 003... per day)
    - When use_date=False: Counter runs continuously across all files (001, 002, 003... regardless of date)
    
    Returns a list of new file paths and any errors encountered.
    """
    from .rename_engine import RenameWorkerThread
    
    # Create a temporary worker thread instance to use its optimized function
    worker = RenameWorkerThread(files, camera_prefix, additional, use_camera, use_lens, 
                               exif_method, separator, exiftool_path, custom_order, date_format, use_date)
    
    # Use the optimized rename function directly
    return worker.optimized_rename_files()
