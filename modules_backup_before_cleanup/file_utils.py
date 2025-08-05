#!/usr/bin/env python3
"""
Constants and utility functions for the RenameFiles application.
"""

import os
import re

def get_filename_components_static(date_taken, camera_prefix, additional, camera_model, lens_model, use_camera, use_lens, num, custom_order, date_format="YYYY-MM-DD", use_date=True):
    """
    Static version of get_filename_components for use in worker threads.
    Build filename components according to the selected order.
    Sequential number is always added at the end.
    """
    year = date_taken[:4]
    month = date_taken[4:6]
    day = date_taken[6:8]
    
    # Format date according to selected format
    formatted_date = None
    if use_date and date_taken:
        if date_format == "YYYY-MM-DD":
            formatted_date = f"{year}-{month}-{day}"
        elif date_format == "YYYY_MM_DD":
            formatted_date = f"{year}_{month}_{day}"
        elif date_format == "DD-MM-YYYY":
            formatted_date = f"{day}-{month}-{year}"
        elif date_format == "DD_MM_YYYY":
            formatted_date = f"{day}_{month}_{year}"
        elif date_format == "YYYYMMDD":
            formatted_date = f"{year}{month}{day}"
        elif date_format == "MM-DD-YYYY":
            formatted_date = f"{month}-{day}-{year}"
        elif date_format == "MM_DD_YYYY":
            formatted_date = f"{month}_{day}_{year}"
        else:
            formatted_date = f"{year}-{month}-{day}"  # Default fallback
    
    # Define all possible components
    components = {
        "Date": formatted_date if (use_date and formatted_date) else None,
        "Prefix": camera_prefix if camera_prefix else None,
        "Additional": additional if additional else None,
        "Camera": camera_model if (use_camera and camera_model) else None,
        "Lens": lens_model if (use_lens and lens_model) else None
    }
    
    # Build ordered list based on custom order
    ordered_parts = []
    for component_name in custom_order:
        component_value = components.get(component_name)
        if component_value:  # Only add non-empty components
            ordered_parts.append(component_value)
    
    # Always add sequential number at the end
    ordered_parts.append(f"{num:03d}")
    
    return ordered_parts

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

def is_image_file(filename):
    """
    Returns True if the file is an image or RAW file based on its extension.
    """
    return os.path.splitext(filename)[1].lower() in IMAGE_EXTENSIONS

def is_video_file(filename):
    """
    Returns True if the file is a video file based on its extension.
    """
    return os.path.splitext(filename)[1].lower() in VIDEO_EXTENSIONS

def is_media_file(filename):
    """
    Returns True if the file is a media file (image, RAW, or video) based on its extension.
    """
    return os.path.splitext(filename)[1].lower() in MEDIA_EXTENSIONS

def scan_directory_recursive(directory):
    """
    Recursively scan directory for media files (images and videos) in all subdirectories.
    Returns a list of all media file paths found.
    """
    media_files = []
    try:
        for root, dirs, files in os.walk(directory):
            for file in files:
                if is_media_file(file):
                    full_path = os.path.join(root, file)
                    media_files.append(full_path)
    except Exception as e:
        print(f"Error scanning directory {directory}: {e}")
    
    return media_files

def is_video_file(filename):
    """
    Returns True if the file is a video file based on its extension.
    """
    return os.path.splitext(filename)[1].lower() in VIDEO_EXTENSIONS

def is_media_file(filename):
    """
    Returns True if the file is a media file (image, RAW, or video) based on its extension.
    """
    return os.path.splitext(filename)[1].lower() in MEDIA_EXTENSIONS

def sanitize_filename(filename):
    """
    Sanitize filename by removing/replacing invalid characters and ensuring compatibility.
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

def validate_path_length(file_path):
    """
    Validate that the file path is not too long for the filesystem.
    Returns True if valid, False if too long.
    """
    # Windows has a 260 character limit, leave buffer
    max_length = 250
    return len(file_path) <= max_length

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
            print(f"Error scanning directory {directory}: {e}")
        
        return sorted(media_files)

def scan_directory_recursive(directory):
    """
    Recursively scan directory for media files (images and videos) in all subdirectories.
    Returns a list of all media file paths found.
    """
    media_files = []
    try:
        for root, dirs, files in os.walk(directory):
            for file in files:
                if is_media_file(file):
                    full_path = os.path.join(root, file)
                    media_files.append(full_path)
    except Exception as e:
        print(f"Error scanning directory {directory}: {e}")
    
    return media_files

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

def validate_path(file_path):
    """
    Validate a file path for various criteria.
    
    Args:
        file_path: Path to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not file_path:
        return False, "Path is empty"
    
    if not os.path.exists(file_path):
        return False, "Path does not exist"
    
    # Check path length
    is_valid_length, length_error = validate_path_length(file_path)
    if not is_valid_length:
        return False, length_error
    
    # Check if it's a file
    if not os.path.isfile(file_path):
        return False, "Path is not a file"
    
    # Check if it's a media file
    if not is_media_file(file_path):
        return False, "File is not a supported media type"
    
    return True, "Valid"

def rename_files(files, camera_prefix, additional, use_camera, use_lens, exif_method, devider="_", exiftool_path=None, custom_order=None, date_format="YYYY-MM-DD", use_date=True):
    """
    Optimized batch rename function using cached EXIF processing.
    Simply delegates to the optimized_rename_files function for better performance.
    
    Counter behavior:
    - When use_date=True: Counter resets per date (001, 002, 003... per day)
    - When use_date=False: Counter runs continuously across all files (001, 002, 003... regardless of date)
    
    Returns a list of new file paths and any errors encountered.
    """
    from .rename_engine_fixed import RenameWorkerThread
    
    # Create a temporary worker thread instance to use its optimized function
    worker = RenameWorkerThread(files, camera_prefix, additional, use_camera, use_lens, 
                               exif_method, devider, exiftool_path, custom_order, date_format, use_date)
    
    # Use the optimized rename function directly
    return worker.optimized_rename_files()
