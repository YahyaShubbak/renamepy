import os
import shutil
import re
import datetime
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QWidget, QLabel, QLineEdit, QPushButton, QListWidget, QFileDialog, QMessageBox, QCheckBox, QDialog, QPlainTextEdit, QHBoxLayout, QStyle, QToolTip, QComboBox, QStatusBar
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QIcon, QTextCursor

try:
    import exiftool
    EXIFTOOL_AVAILABLE = True
except ImportError:
    EXIFTOOL_AVAILABLE = False

try:
    from PIL import Image
    from PIL.ExifTags import TAGS
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

# Global EXIF cache for performance
_exif_cache = {}
_cache_lock = None

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

class RenameWorkerThread(QThread):
    """
    Worker thread for file renaming to prevent UI freezing
    """
    progress_update = pyqtSignal(str)
    finished = pyqtSignal(list, list)
    error = pyqtSignal(str)
    
    def __init__(self, files, camera_prefix, additional, use_camera, use_lens, 
                 exif_method, devider, exiftool_path):
        super().__init__()
        self.files = files
        self.camera_prefix = camera_prefix
        self.additional = additional
        self.use_camera = use_camera
        self.use_lens = use_lens
        self.exif_method = exif_method
        self.devider = devider
        self.exiftool_path = exiftool_path
    
    def run(self):
        """Run the rename operation in background thread"""
        try:
            self.progress_update.emit("Starting rename operation...")
            
            # Use optimized rename function
            renamed_files, errors = self.optimized_rename_files()
            
            self.finished.emit(renamed_files, errors)
        except Exception as e:
            self.error.emit(str(e))
    
    def optimized_rename_files(self):
        """
        Optimized rename function with batch EXIF processing
        """
        import re
        from collections import defaultdict
        
        self.progress_update.emit("Grouping files...")
        
        # Clear cache for fresh processing
        clear_global_exif_cache()
        
        # Step 1: Group files by basename (fast)
        file_groups = []
        basename_groups = defaultdict(list)
        for file in self.files:
            if is_image_file(file):
                base = os.path.splitext(os.path.basename(file))[0]
                basename_groups[base].append(file)
        
        # Separate grouped and orphaned files
        orphaned_files = []
        for base, file_list in basename_groups.items():
            if len(file_list) > 1:
                file_groups.append(file_list)
            else:
                orphaned_files.extend(file_list)
        
        # Add orphans as individual groups (simple approach for now)
        for file in orphaned_files:
            file_groups.append([file])
        
        self.progress_update.emit(f"Processing {len(file_groups)} file groups...")
        
        # Step 2: Process each group with cached EXIF reads
        renamed_files = []
        errors = []
        date_counter = {}
        
        for i, group_files in enumerate(file_groups):
            if i % 10 == 0:  # Update progress every 10 groups
                self.progress_update.emit(f"Processing group {i+1}/{len(file_groups)}")
            
            # Check file access
            accessible_files = [f for f in group_files if check_file_access(f)]
            if not accessible_files:
                continue
            
            # Extract EXIF data using cache
            date_taken = None
            camera_model = None
            lens_model = None
            
            for file in accessible_files:
                if self.use_camera and not camera_model:
                    _, camera_model, _ = get_cached_exif_data(file, self.exif_method, self.exiftool_path)
                if self.use_lens and not lens_model:
                    _, _, lens_model = get_cached_exif_data(file, self.exif_method, self.exiftool_path)
                if not date_taken:
                    date_taken, _, _ = get_cached_exif_data(file, self.exif_method, self.exiftool_path)
                
                if date_taken and (not self.use_camera or camera_model) and (not self.use_lens or lens_model):
                    break
            
            # Fallback date extraction
            if not date_taken:
                for file in accessible_files:
                    m = re.search(r'(20\d{2})(\d{2})(\d{2})', os.path.basename(file))
                    if m:
                        date_taken = f"{m.group(1)}{m.group(2)}{m.group(3)}"
                        break
            
            if not date_taken:
                file = accessible_files[0]
                mtime = os.path.getmtime(file)
                dt = datetime.datetime.fromtimestamp(mtime)
                date_taken = dt.strftime('%Y%m%d')
            
            # Counter logic
            if date_taken not in date_counter:
                date_counter[date_taken] = 1
            else:
                date_counter[date_taken] += 1
            num = date_counter[date_taken]
            year = date_taken[:4]
            month = date_taken[4:6]
            day = date_taken[6:8]
            
            # Rename files in group
            for file in accessible_files:
                try:
                    ext = os.path.splitext(file)[1]
                    name_parts = [year, month, day, f"{num:02d}"]
                    if self.camera_prefix:
                        name_parts.append(self.camera_prefix)
                    if self.additional:
                        name_parts.append(self.additional)
                    if self.use_camera and camera_model:
                        name_parts.append(camera_model)
                    if self.use_lens and lens_model:
                        name_parts.append(lens_model)
                    
                    sep = "" if self.devider == "None" else self.devider
                    new_name = sep.join(name_parts) + ext
                    new_name = sanitize_filename(new_name)
                    new_path = get_safe_target_path(file, new_name)
                    
                    if not validate_path_length(new_path):
                        directory = os.path.dirname(file)
                        base, ext = os.path.splitext(new_name)
                        max_name_len = 200 - len(directory)
                        if max_name_len > 10:
                            shortened_base = base[:max_name_len - len(ext)]
                            new_name = shortened_base + ext
                            new_path = os.path.join(directory, new_name)
                        else:
                            errors.append(f"Path too long: {file}")
                            continue
                    
                    os.rename(file, new_path)
                    renamed_files.append(new_path)
                    
                except Exception as e:
                    errors.append(f"Failed to rename {os.path.basename(file)}: {e}")
        
        return renamed_files, errors

IMAGE_EXTENSIONS = [
    '.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.gif', 
    '.cr2', '.nef', '.arw', '.orf', '.rw2', '.dng', '.raw', '.sr2', '.pef', '.raf', '.3fr', '.erf', '.kdc', '.mos', '.nrw', '.srw', '.x3f'
]

def is_image_file(filename):
    """
    Returns True if the file is an image or RAW file based on its extension.
    """
    return os.path.splitext(filename)[1].lower() in IMAGE_EXTENSIONS

def is_exiftool_installed():
    """
    Check for exiftool installation in multiple locations.
    Returns the absolute path to exiftool.exe if found, None otherwise.
    """
    # Test 1: System PATH
    exe = shutil.which("exiftool")
    if exe:
        return exe
    
    # Test 2: Current directory
    local = os.path.join(os.getcwd(), "exiftool.exe")
    if os.path.exists(local):
        return local
    
    # Test 3: exiftool-13.32_64 subdirectory (relative to script)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    custom = os.path.join(script_dir, "exiftool-13.32_64", "exiftool.exe")
    if os.path.exists(custom):
        return custom
    
    # Test 4: Direct check in common locations
    possible_paths = [
        os.path.join(script_dir, "exiftool.exe"),
        os.path.join(script_dir, "exiftool", "exiftool.exe"),
        "C:\\exiftool\\exiftool.exe"
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            return path
    
    return None

# Dynamische EXIF-Auslese

def extract_exif_fields(image_path, method, exiftool_path=None):
    """
    Extracts date, camera model, and lens model from an image using the specified method.
    Returns (date, camera, lens) or (None, None, None) if not found.
    """
    return extract_exif_fields_with_retry(image_path, method, exiftool_path, max_retries=3)

def extract_exif_fields_with_retry(image_path, method, exiftool_path=None, max_retries=3):
    """
    Extracts EXIF fields with retry mechanism for reliability.
    """
    import time
    
    for attempt in range(max_retries):
        try:
            if method == "exiftool":
                # Use exiftool with or without explicit path
                if exiftool_path and os.path.exists(exiftool_path):
                    with exiftool.ExifToolHelper(executable=exiftool_path) as et:
                        meta = et.get_metadata([image_path])[0]
                else:
                    # Try to use system exiftool or let exiftool package find it
                    with exiftool.ExifToolHelper() as et:
                        meta = et.get_metadata([image_path])[0]
                
                # Extract date
                date = meta.get('EXIF:DateTimeOriginal')
                if date:
                    date = date.split(' ')[0].replace(':', '')
                
                # Extract camera model
                camera = meta.get('EXIF:Model')
                if camera:
                    camera = str(camera).replace(' ', '-')
                
                # Extract lens model
                lens = meta.get('EXIF:LensModel')
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
                    for tag, value in exif_data.items():
                        decoded_tag = TAGS.get(tag, tag)
                        if decoded_tag == "DateTimeOriginal" and not date:
                            date = value.split(" ")[0].replace(":", "")
                        if decoded_tag == "Model" and not camera:
                            camera = str(value).replace(" ", "-")
                        if decoded_tag == "LensModel" and not lens:
                            lens = str(value).replace(" ", "-")
                return date, camera, lens
            else:
                return None, None, None
                
        except Exception as e:
            if attempt == max_retries - 1:
                print(f"Failed to extract EXIF after {max_retries} attempts from {image_path}: {e}")
                return None, None, None
            else:
                print(f"EXIF extraction attempt {attempt + 1} failed, retrying... ({e})")
                time.sleep(0.1)  # Brief pause before retry

def extract_date_taken(image_path, method, exiftool_path=None):
    """
    Extracts only the date from an image using the specified method.
    """
    date, _, _ = extract_exif_fields(image_path, method, exiftool_path)
    return date

def extract_camera_model(image_path, method, exiftool_path=None):
    """
    Extracts only the camera model from an image using the specified method.
    """
    _, camera, _ = extract_exif_fields(image_path, method, exiftool_path)
    return camera

def extract_lens_model(image_path, method, exiftool_path=None):
    """
    Extracts only the lens model from an image using the specified method.
    """
    _, _, lens = extract_exif_fields(image_path, method, exiftool_path)
    return lens

def extract_image_number(image_path, method, exiftool_path=None):
    """
    Extracts the image number/shutter count from an image using the specified method.
    Returns the image number as a string or None if not found.
    """
    if method == "exiftool":
        try:
            # Use exiftool with or without explicit path
            if exiftool_path and os.path.exists(exiftool_path):
                with exiftool.ExifToolHelper(executable=exiftool_path) as et:
                    meta = et.get_metadata([image_path])[0]
            else:
                # Try to use system exiftool or let exiftool package find it
                with exiftool.ExifToolHelper() as et:
                    meta = et.get_metadata([image_path])[0]
            
            # Try different possible fields for image number/shutter count
            possible_fields = [
                'EXIF:ImageNumber',
                'EXIF:ShutterCount', 
                'MakerNotes:ShutterCount',
                'MakerNotes:ImageNumber',
                'Canon:ImageNumber',
                'Nikon:ShutterCount',
                'Sony:ShotNumberSincePowerUp',
                'Sony:ImageNumber',
                'File:FileNumber'
            ]
            
            for field in possible_fields:
                if field in meta and meta[field] is not None:
                    return str(meta[field])
            
            return None
            
        except Exception as e:
            print(f"ExifTool error for image number in {image_path}: {e}")
            return None
    elif method == "pillow":
        try:
            image = Image.open(image_path)
            exif_data = image._getexif()
            if exif_data:
                for tag, value in exif_data.items():
                    decoded_tag = TAGS.get(tag, tag)
                    if decoded_tag in ["ImageNumber", "ShutterCount"]:
                        return str(value)
            return None
        except Exception as e:
            print(f"Pillow error for image number in {image_path}: {e}")
            return None
    else:
        return None


def get_file_timestamp(image_path, method, exiftool_path=None):
    """
    Extracts the file timestamp from an image using the specified method.
    Returns the timestamp as a string or None if not found.
    """
    if method == "exiftool":
        try:
            # Use exiftool with or without explicit path
            if exiftool_path and os.path.exists(exiftool_path):
                with exiftool.ExifToolHelper(executable=exiftool_path) as et:
                    meta = et.get_metadata([image_path])[0]
            else:
                # Try to use system exiftool or let exiftool package find it
                with exiftool.ExifToolHelper() as et:
                    meta = et.get_metadata([image_path])[0]
            
            # Try different possible timestamp fields
            possible_fields = [
                'EXIF:DateTimeOriginal',
                'EXIF:CreateDate', 
                'File:FileModifyDate',
                'File:FileCreateDate',
                'EXIF:DateTime'
            ]
            
            for field in possible_fields:
                if field in meta and meta[field] is not None:
                    return str(meta[field])
            
            return None
            
        except Exception as e:
            print(f"ExifTool error for timestamp in {image_path}: {e}")
            return None
    elif method == "pillow":
        try:
            image = Image.open(image_path)
            exif_data = image._getexif()
            if exif_data:
                for tag, value in exif_data.items():
                    decoded_tag = TAGS.get(tag, tag)
                    if decoded_tag in ["DateTimeOriginal", "DateTime"]:
                        return str(value)
            return None
        except Exception as e:
            print(f"Pillow error for timestamp in {image_path}: {e}")
            return None
    else:
        return None

def sanitize_filename(filename):
    """
    Sanitize filename by removing/replacing invalid characters and ensuring compatibility.
    """
    # Remove/replace invalid characters for Windows/Unix
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    
    # Remove control characters (ASCII 0-31) and replace with underscore
    filename = ''.join(char if ord(char) >= 32 else '_' for char in filename)
    
    # Remove trailing and leading dots and spaces (Windows issue)
    filename = filename.strip('. ')
    
    # Remove multiple consecutive underscores and spaces
    import re
    filename = re.sub(r'_+', '_', filename)
    filename = re.sub(r'\s+', ' ', filename)  # Collapse multiple spaces
    filename = filename.strip()  # Remove leading/trailing spaces again
    
    # Ensure filename is not empty
    if not filename or filename == '_':
        filename = 'unnamed_file'
    
    # Limit length to prevent filesystem issues (keep extension)
    if len(filename) > 200:
        base, ext = os.path.splitext(filename)
        filename = base[:200-len(ext)] + ext
    
    return filename

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
            f.read(1)
        
        # Test if file is locked by checking if we can open it for writing
        with open(file_path, 'r+b') as f:
            pass
            
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
        alternative_name = f"{base}_conflict_{attempt:03d}{ext}"
        new_path = os.path.join(directory, alternative_name)
        attempt += 1
    
    if attempt > 999:
        # Fallback: add timestamp
        import time
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

def group_files_with_failsafe(files, exif_method, exiftool_path=None):
    """
    Groups files by basename first, then tries to group orphaned files by timestamp.
    Returns a list of file groups (each group is a list of files that belong together).
    """
    from collections import defaultdict
    import re
    from datetime import datetime
    
    # Step 1: Group by basename (normal case)
    basename_groups = defaultdict(list)
    for file in files:
        base = os.path.splitext(os.path.basename(file))[0]
        basename_groups[base].append(file)
    
    # Step 2: Find orphaned files (groups with only one file)
    final_groups = []
    orphaned_files = []
    
    for base, file_list in basename_groups.items():
        if len(file_list) > 1:
            # Multiple files with same basename - they belong together
            final_groups.append(file_list)
        else:
            # Single file - potential orphan
            orphaned_files.append(file_list[0])
    
    # Step 3: Try to match orphaned files by timestamp
    if len(orphaned_files) > 1 and exif_method:
        print(f"Found {len(orphaned_files)} orphaned files, trying timestamp matching...")
        
        # Extract timestamps for orphaned files
        file_timestamps = {}
        for file in orphaned_files:
            timestamp = get_file_timestamp(file, exif_method, exiftool_path)
            if timestamp:
                # Parse timestamp to compare (remove timezone info for comparison)
                try:
                    # Handle different timestamp formats
                    clean_timestamp = timestamp.split('+')[0].split('-')[0]  # Remove timezone
                    parsed_time = datetime.strptime(clean_timestamp, '%Y:%m:%d %H:%M:%S')
                    file_timestamps[file] = parsed_time
                except:
                    try:
                        # Try alternative format
                        parsed_time = datetime.strptime(clean_timestamp, '%Y-%m-%d %H:%M:%S')
                        file_timestamps[file] = parsed_time
                    except:
                        print(f"Could not parse timestamp for {file}: {timestamp}")
        
        # Group files with timestamps within 2 seconds of each other
        used_files = set()
        for file1 in orphaned_files:
            if file1 in used_files or file1 not in file_timestamps:
                continue
                
            group = [file1]
            used_files.add(file1)
            
            for file2 in orphaned_files:
                if file2 in used_files or file2 not in file_timestamps:
                    continue
                
                # Check if timestamps are within 2 seconds
                time_diff = abs((file_timestamps[file1] - file_timestamps[file2]).total_seconds())
                if time_diff <= 2:
                    group.append(file2)
                    used_files.add(file2)
            
            final_groups.append(group)
        
        # Add remaining orphaned files as individual groups
        for file in orphaned_files:
            if file not in used_files:
                final_groups.append([file])
    else:
        # No timestamp matching possible, add orphans as individual groups
        for file in orphaned_files:
            final_groups.append([file])
    
    return final_groups

def verify_group_consistency(group, exif_method, exiftool_path=None):
    """
    Verify that grouped files have consistent EXIF data (same camera, similar timestamps).
    Returns True if consistent, False if suspicious grouping detected.
    """
    if len(group) < 2:
        return True
    
    # Extract EXIF data from all files in group
    exif_data = []
    for file in group:
        date, camera, lens = extract_exif_fields(file, exif_method, exiftool_path)
        timestamp = get_file_timestamp(file, exif_method, exiftool_path)
        exif_data.append({
            'file': file,
            'date': date,
            'camera': camera,
            'lens': lens,
            'timestamp': timestamp
        })
    
    # Check camera consistency
    cameras = [data['camera'] for data in exif_data if data['camera']]
    if len(set(cameras)) > 1:
        print(f"Warning: Different cameras in group: {set(cameras)}")
        print(f"Files: {[os.path.basename(data['file']) for data in exif_data]}")
        return False
    
    # Check timestamp consistency (should be very close)
    timestamps = []
    for data in exif_data:
        if data['timestamp']:
            try:
                from datetime import datetime
                clean_timestamp = data['timestamp'].split('+')[0].split('-')[0]
                parsed_time = datetime.strptime(clean_timestamp, '%Y:%m:%d %H:%M:%S')
                timestamps.append(parsed_time)
            except:
                continue
    
    if len(timestamps) >= 2:
        # Check if all timestamps are within 5 seconds of each other
        min_time = min(timestamps)
        max_time = max(timestamps)
        time_diff = (max_time - min_time).total_seconds()
        
        if time_diff > 5:
            print(f"Warning: Large time difference in group: {time_diff} seconds")
            print(f"Files: {[os.path.basename(data['file']) for data in exif_data]}")
            return False
    
    return True

def rename_files(files, camera_prefix, additional, use_camera, use_lens, exif_method, devider="_", exiftool_path=None):
    """
    Batch rename files based on EXIF data and user options.
    Groups files by base name with failsafe timestamp matching, extracts EXIF only once per group, and applies a running counter per date.
    Returns a list of new file paths and any errors encountered.
    """
    import re
    
    # Use improved grouping with failsafe
    file_groups = group_files_with_failsafe(files, exif_method, exiftool_path)

    renamed_files = []
    errors = []
    skipped_files = []
    date_counter = {}
    
    for group_files in file_groups:
        # Verify group consistency
        if not verify_group_consistency(group_files, exif_method, exiftool_path):
            print(f"Warning: Inconsistent group detected, but proceeding with rename...")
        
        # Check file access for all files in group
        accessible_files = []
        for file in group_files:
            if not check_file_access(file):
                error_msg = f"Cannot access file (locked/permission denied): {os.path.basename(file)}"
                errors.append(error_msg)
                print(error_msg)
                skipped_files.append(file)
            else:
                accessible_files.append(file)
        
        if not accessible_files:
            continue  # Skip this group entirely if no files are accessible
        
        # Extract EXIF data
        date_taken = None
        camera_model = None
        lens_model = None
        for file in accessible_files:
            if use_camera and not camera_model:
                camera_model = extract_camera_model(file, exif_method, exiftool_path)
            if use_lens and not lens_model:
                lens_model = extract_lens_model(file, exif_method, exiftool_path)
            if not date_taken:
                date_taken = extract_date_taken(file, exif_method, exiftool_path)
            if date_taken and (not use_camera or camera_model) and (not use_lens or lens_model):
                break
        
        # Fallback date extraction
        if not date_taken:
            for file in accessible_files:
                m = re.search(r'(20\d{2})(\d{2})(\d{2})', os.path.basename(file))
                if m:
                    date_taken = f"{m.group(1)}{m.group(2)}{m.group(3)}"
                    break
        if not date_taken:
            # Fallback: use file modification date
            file = accessible_files[0]
            mtime = os.path.getmtime(file)
            dt = datetime.datetime.fromtimestamp(mtime)
            date_taken = dt.strftime('%Y%m%d')
        
        # Running counter per date
        if date_taken not in date_counter:
            date_counter[date_taken] = 1
        else:
            date_counter[date_taken] += 1
        num = date_counter[date_taken]
        year = date_taken[:4]
        month = date_taken[4:6]
        day = date_taken[6:8]
        
        # Rename each accessible file in the group
        for file in accessible_files:
            try:
                ext = os.path.splitext(file)[1]
                name_parts = [year, month, day, f"{num:02d}"]
                if camera_prefix:
                    name_parts.append(camera_prefix)
                if additional:
                    name_parts.append(additional)
                if use_camera and camera_model:
                    name_parts.append(camera_model)
                if use_lens and lens_model:
                    name_parts.append(lens_model)
                
                sep = "" if devider == "None" else devider
                new_name = sep.join(name_parts) + ext
                
                # Sanitize filename
                new_name = sanitize_filename(new_name)
                
                # Get safe target path (handles conflicts)
                new_path = get_safe_target_path(file, new_name)
                
                # Validate path length
                if not validate_path_length(new_path):
                    # Shorten filename if path too long
                    directory = os.path.dirname(file)
                    base, ext = os.path.splitext(new_name)
                    max_name_len = 200 - len(directory)
                    if max_name_len > 10:  # Ensure minimum filename length
                        shortened_base = base[:max_name_len - len(ext)]
                        new_name = shortened_base + ext
                        new_path = os.path.join(directory, new_name)
                    else:
                        error_msg = f"Path too long, cannot shorten further: {file}"
                        errors.append(error_msg)
                        print(error_msg)
                        continue
                
                # Perform the rename
                os.rename(file, new_path)
                renamed_files.append(new_path)
                print(f"Renamed: {os.path.basename(file)} → {os.path.basename(new_path)}")
                
            except Exception as e:
                error_msg = f"Failed to rename {os.path.basename(file)}: {e}"
                errors.append(error_msg)
                print(error_msg)
                skipped_files.append(file)
    
    # Print summary
    print(f"\nRename Summary:")
    print(f"Successfully renamed: {len(renamed_files)} files")
    if errors:
        print(f"Errors encountered: {len(errors)}")
        print(f"Skipped files: {len(skipped_files)}")
    
    return renamed_files, errors

class FileRenamerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("File Renamer")
        self.setGeometry(100, 100, 600, 400)
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)

        # Camera Prefix with info icon
        camera_layout = QVBoxLayout()
        camera_label = QLabel("Camera Prefix:")
        camera_info = QLabel()
        camera_info.setPixmap(self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxInformation).pixmap(16, 16))
        camera_info.setToolTip("Short camera code, e.g. A7R3 or D850. Optional.")
        camera_row = QHBoxLayout()
        camera_row.addWidget(camera_label)
        camera_row.addWidget(camera_info)
        camera_row.addStretch()
        self.layout.addLayout(camera_row)
        self.camera_prefix_entry = QLineEdit()
        self.camera_prefix_entry.setPlaceholderText("e.g. A7R3, D850")
        self.camera_prefix_entry.textChanged.connect(self.validate_and_update_preview)
        self.layout.addWidget(self.camera_prefix_entry)
        # Additional with info icon
        additional_label = QLabel("Additional:")
        additional_info = QLabel()
        additional_info.setPixmap(self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxInformation).pixmap(16, 16))
        additional_info.setToolTip("Any additional info, e.g. location or event. Optional.")
        additional_row = QHBoxLayout()
        additional_row.addWidget(additional_label)
        additional_row.addWidget(additional_info)
        additional_row.addStretch()
        self.layout.addLayout(additional_row)
        self.additional_entry = QLineEdit()
        self.additional_entry.setPlaceholderText("e.g. vacation, wedding")
        self.additional_entry.textChanged.connect(self.validate_and_update_preview)
        self.layout.addWidget(self.additional_entry)

        # Devider selection
        devider_row = QHBoxLayout()
        devider_label = QLabel("Devider:")
        devider_info = QLabel()
        devider_info.setPixmap(self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxInformation).pixmap(16, 16))
        devider_info.setToolTip("Choose how to separate date and info in filename.")
        devider_row.addWidget(devider_label)
        devider_row.addWidget(devider_info)
        devider_row.addStretch()
        self.layout.addLayout(devider_row)
        self.devider_combo = QComboBox()
        self.devider_combo.addItems(["None", "_", "-"])
        self.layout.addWidget(self.devider_combo)
        self.devider_combo.currentIndexChanged.connect(self.update_preview)

        # Camera checkbox with model display
        camera_checkbox_layout = QHBoxLayout()
        self.checkbox_camera = QCheckBox("Include camera model in filename")
        self.camera_model_label = QLabel("(detecting...)")
        self.camera_model_label.setStyleSheet("color: gray; font-style: italic;")
        camera_checkbox_layout.addWidget(self.checkbox_camera)
        camera_checkbox_layout.addWidget(self.camera_model_label)
        camera_checkbox_layout.addStretch()
        self.layout.addLayout(camera_checkbox_layout)
        self.checkbox_camera.stateChanged.connect(self.update_preview)
        
        # Lens checkbox with model display
        lens_checkbox_layout = QHBoxLayout()
        self.checkbox_lens = QCheckBox("Include lens in filename")
        self.lens_model_label = QLabel("(detecting...)")
        self.lens_model_label.setStyleSheet("color: gray; font-style: italic;")
        lens_checkbox_layout.addWidget(self.checkbox_lens)
        lens_checkbox_layout.addWidget(self.lens_model_label)
        lens_checkbox_layout.addStretch()
        self.layout.addLayout(lens_checkbox_layout)
        self.checkbox_lens.stateChanged.connect(self.update_preview)

        self.preview_label = QLabel("Preview:")
        self.layout.addWidget(self.preview_label)
        self.preview_box = QLineEdit()
        self.preview_box.setReadOnly(True)
        self.layout.addWidget(self.preview_box)

        self.file_list = QListWidget()
        self.layout.addWidget(self.file_list)
        self.file_list.itemDoubleClicked.connect(self.show_selected_exif)
        self.file_list.itemClicked.connect(self.show_image_info)
        self.file_list.setToolTip("Click for image info, double click for EXIF")
        self.file_list.installEventFilter(self)

        self.select_files_button = QPushButton("Select Files")
        self.select_files_button.clicked.connect(self.select_files)
        self.layout.addWidget(self.select_files_button)

        self.select_folder_button = QPushButton("Select Folder")
        self.select_folder_button.clicked.connect(self.select_folder)
        self.layout.addWidget(self.select_folder_button)

        self.clear_list_button = QPushButton("Clear List")
        self.clear_list_button.clicked.connect(self.clear_file_list)
        self.layout.addWidget(self.clear_list_button)

        self.setAcceptDrops(True)

        self.rename_button = QPushButton("Rename")
        self.rename_button.clicked.connect(self.rename_files_action)
        self.layout.addWidget(self.rename_button)

        self.files = []
        self.exiftool_path = is_exiftool_installed()
        
        if EXIFTOOL_AVAILABLE and self.exiftool_path:
            self.exif_method = "exiftool"
        elif PIL_AVAILABLE:
            self.exif_method = "pillow"
        else:
            self.exif_method = None
        
        # Statusbar für Info unten rechts
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        # Label für Methode und ggf. Info-Icon
        self.exif_status_label = QLabel()
        self.status.addPermanentWidget(self.exif_status_label)
        self.update_exif_status()
        self.update_preview()

        # EXIF cache for preview file
        self._preview_exif_cache = {}
        self._preview_exif_file = None
        
        # Update camera and lens labels initially
        self.update_camera_lens_labels()

    def validate_and_update_preview(self):
        """Validate input fields and update preview"""
        # Get current text
        camera_text = self.camera_prefix_entry.text()
        additional_text = self.additional_entry.text()
        
        # Validate and sanitize camera prefix
        if camera_text:
            sanitized_camera = sanitize_filename(camera_text)
            if sanitized_camera != camera_text:
                # Update field with sanitized version
                cursor_pos = self.camera_prefix_entry.cursorPosition()
                self.camera_prefix_entry.setText(sanitized_camera)
                self.camera_prefix_entry.setCursorPosition(min(cursor_pos, len(sanitized_camera)))
        
        # Validate and sanitize additional field
        if additional_text:
            sanitized_additional = sanitize_filename(additional_text)
            if sanitized_additional != additional_text:
                # Update field with sanitized version
                cursor_pos = self.additional_entry.cursorPosition()
                self.additional_entry.setText(sanitized_additional)
                self.additional_entry.setCursorPosition(min(cursor_pos, len(sanitized_additional)))
        
        # Update preview
        self.update_preview()

    def update_camera_lens_labels(self):
        """Update the camera and lens model labels based on the first selected file"""
        if not self.files or not self.exif_method:
            self.camera_model_label.setText("(no files selected)")
            self.lens_model_label.setText("(no files selected)")
            return
        
        # Use first image file for detection
        first_image = next((f for f in self.files if is_image_file(f)), None)
        if not first_image:
            self.camera_model_label.setText("(no image files)")
            self.lens_model_label.setText("(no image files)")
            return
        
        try:
            date, camera, lens = extract_exif_fields(first_image, self.exif_method, self.exiftool_path)
            
            if camera:
                self.camera_model_label.setText(f"({camera})")
                self.camera_model_label.setStyleSheet("color: green; font-style: italic;")
            else:
                self.camera_model_label.setText("(not detected)")
                self.camera_model_label.setStyleSheet("color: orange; font-style: italic;")
            
            if lens:
                self.lens_model_label.setText(f"({lens})")
                self.lens_model_label.setStyleSheet("color: green; font-style: italic;")
            else:
                self.lens_model_label.setText("(not detected)")
                self.lens_model_label.setStyleSheet("color: orange; font-style: italic;")
                
        except Exception as e:
            self.camera_model_label.setText("(error)")
            self.lens_model_label.setText("(error)")
            self.camera_model_label.setStyleSheet("color: red; font-style: italic;")
            self.lens_model_label.setStyleSheet("color: red; font-style: italic;")

    def show_image_info(self, item):
        """Show image information when a file is clicked (single click)"""
        file_path = item.text()
        if not is_image_file(file_path) or not self.exif_method:
            return
        
        try:
            # Extract image number
            image_number = extract_image_number(file_path, self.exif_method, self.exiftool_path)
            
            if image_number:
                # Update status bar with image number
                self.status.showMessage(f"Image Number/Shutter Count: {image_number}", 5000)  # Show for 5 seconds
            else:
                self.status.showMessage("Image number not found in EXIF data", 3000)
                
        except Exception as e:
            self.status.showMessage(f"Error reading image number: {e}", 3000)

    def update_exif_status(self):
        if self.exif_method == "exiftool":
            self.exif_status_label.setText(f"EXIF method: exiftool v13.32 (recommended) ✓")
            self.exif_status_label.setStyleSheet("color: green;")
            self.exif_status_label.setToolTip(f"Using ExifTool at: {self.exiftool_path}")
        elif self.exif_method == "pillow":
            self.exif_status_label.setText("EXIF method: Pillow ⚠")
            self.exif_status_label.setStyleSheet("color: orange;")
            info_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxInformation).pixmap(16, 16)
            self.exif_status_label.setPixmap(info_icon)
            self.exif_status_label.setToolTip("To make use of the great exiftool, go to https://exiftool.org to download it, place exiftool.exe in your program folder or PATH, then restart. RAW support is limited with Pillow.")
        else:
            self.exif_status_label.setText("No EXIF support available ❌")
            self.exif_status_label.setStyleSheet("color: red;")
            info_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxInformation).pixmap(16, 16)
            self.exif_status_label.setPixmap(info_icon)
            self.exif_status_label.setToolTip("Please install exiftool (https://exiftool.org) or Pillow for EXIF support.")

    def update_preview(self):
        # Choose first JPG file, else first file, else dummy
        preview_file = next((f for f in self.files if os.path.splitext(f)[1].lower() in [".jpg", ".jpeg"]), None)
        if not preview_file and self.files:
            preview_file = self.files[0]
        if not preview_file:
            preview_file = "20250725_DSC0001.ARW"

        camera_prefix = self.camera_prefix_entry.text().strip()
        additional = self.additional_entry.text().strip()
        use_camera = self.checkbox_camera.isChecked()
        use_lens = self.checkbox_lens.isChecked()
        devider = self.devider_combo.currentText()
        date_taken = None
        camera_model = None
        lens_model = None
        ext = os.path.splitext(preview_file)[1] if preview_file else ".ARW"
        if not self.exif_method:
            self.preview_box.setText("[No EXIF support available]")
            return

        # EXIF cache: only extract if file changed
        cache_key = (preview_file, self.exif_method, self.exiftool_path)
        if os.path.exists(preview_file):
            if self._preview_exif_file != cache_key:
                try:
                    exif_data = extract_exif_fields(preview_file, self.exif_method, self.exiftool_path)
                except Exception as e:
                    self.preview_box.setText(f"[EXIF error: {e}]")
                    return
                self._preview_exif_cache = {
                    'date': exif_data[0],
                    'camera': exif_data[1],
                    'lens': exif_data[2],
                }
                self._preview_exif_file = cache_key
            date_taken = self._preview_exif_cache.get('date')
            camera_model = self._preview_exif_cache.get('camera')
            lens_model = self._preview_exif_cache.get('lens')

        import re
        if not date_taken:
            m = re.search(r'(20\d{2})(\d{2})(\d{2})', os.path.basename(preview_file))
            if m:
                date_taken = f"{m.group(1)}{m.group(2)}{m.group(3)}"
        if not date_taken:
            if os.path.exists(preview_file):
                mtime = os.path.getmtime(preview_file)
                import datetime
                dt = datetime.datetime.fromtimestamp(mtime)
                date_taken = dt.strftime('%Y%m%d')
            else:
                date_taken = "20250725"
        year = date_taken[:4]
        month = date_taken[4:6]
        day = date_taken[6:8]
        num = 1
        sep = "" if devider == "None" else devider
        name_parts = [year, month, day, f"{num:02d}"]
        if camera_prefix:
            name_parts.append(camera_prefix)
        if additional:
            name_parts.append(additional)
        if use_camera and camera_model:
            name_parts.append(camera_model)
        elif use_camera:
            name_parts.append("A7R3")
        if use_lens and lens_model:
            name_parts.append(lens_model)
        elif use_lens:
            name_parts.append("FE24-70")
        preview = sep.join(name_parts) + ext
        self.preview_box.setText(preview)

    def eventFilter(self, obj, event):
        if obj == self.file_list and event.type() == event.Type.ToolTip:
            item = self.file_list.itemAt(event.pos())
            if item:
                QToolTip.showText(event.globalPos(), "Click for image info, double click for EXIF", self.file_list)
                return True
        return super().eventFilter(obj, event)

    def show_exif_info(self, file):
        if not self.exif_method:
            self.show_exif_dialog(file, "No EXIF support available.")
            return
        try:
            if self.exif_method == "exiftool":
                if self.exiftool_path:
                    with exiftool.ExifToolHelper(executable=self.exiftool_path) as et:
                        meta = et.get_metadata([file])[0]
                else:
                    with exiftool.ExifToolHelper() as et:
                        meta = et.get_metadata([file])[0]
                if not meta:
                    self.show_exif_dialog(file, "No EXIF data found.")
                    return
                info = []
                for k, v in meta.items():
                    info.append(f"{k}: {v}")
                info_str = "\n".join(info)
                self.show_exif_dialog(file, info_str)
            elif self.exif_method == "pillow":
                image = Image.open(file)
                exif_data = image._getexif()
                if not exif_data:
                    self.show_exif_dialog(file, "No EXIF data found.")
                    return
                info = []
                for tag, value in exif_data.items():
                    decoded_tag = TAGS.get(tag, tag)
                    info.append(f"{decoded_tag}: {value}")
                info_str = "\n".join(info)
                self.show_exif_dialog(file, info_str)
        except Exception as e:
            self.show_exif_dialog(file, f"Error reading EXIF: {e}")

    def show_exif_dialog(self, file, info_str):
        dialog = QDialog(self)
        dialog.setWindowTitle(f"EXIF Info: {os.path.basename(file)}")
        layout = QVBoxLayout(dialog)
        text_edit = QPlainTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setPlainText(info_str)
        layout.addWidget(text_edit)
        dialog.resize(500, 400)
        dialog.exec()

    def add_files_to_list(self, files):
        # Clear existing files when adding new ones
        if files and self.files:
            self.clear_file_list()
        
        # Validate and add files
        added_count = 0
        inaccessible_files = []
        
        for file in files:
            if file not in self.files:
                # Check if file is accessible
                if not check_file_access(file):
                    inaccessible_files.append(os.path.basename(file))
                    continue
                
                self.files.append(file)
                self.file_list.addItem(file)
                added_count += 1
        
        # Show warning for inaccessible files
        if inaccessible_files:
            QMessageBox.warning(
                self,
                "File Access Warning",
                f"The following files could not be accessed (locked/permission denied):\n\n" +
                "\n".join(inaccessible_files[:10]) +  # Show max 10 files
                (f"\n... and {len(inaccessible_files) - 10} more" if len(inaccessible_files) > 10 else "")
            )
        
        # Update status
        if added_count > 0:
            self.status.showMessage(f"Added {added_count} files", 3000)
        
        # Update preview and camera/lens labels when files are added
        self.update_preview()
        self.update_camera_lens_labels()

    def clear_file_list(self):
        """Clear the file list and reset the GUI"""
        self.files.clear()
        self.file_list.clear()
        self._preview_exif_cache = {}
        self._preview_exif_file = None
        self.update_preview()
        self.update_camera_lens_labels()

    def show_selected_exif(self, item):
        file = item.text()
        if is_image_file(file):
            self.show_exif_info(file)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            files = []
            for url in event.mimeData().urls():
                path = url.toLocalFile()
                if os.path.isdir(path):
                    files.extend([os.path.join(path, f) for f in os.listdir(path) if is_image_file(f)])
                elif is_image_file(path):
                    files.append(path)
            self.add_files_to_list(files)

    def select_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Select Files", "", "Image Files (*.jpg *.jpeg *.png *.arw *.cr2 *.nef *.dng *.tif *.tiff *.bmp *.gif)")
        if files:
            self.add_files_to_list(files)

    def select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder:
            files = [os.path.join(folder, f) for f in os.listdir(folder) if is_image_file(f)]
            self.add_files_to_list(files)

    def rename_files_action(self):
        if not self.files:
            QMessageBox.warning(self, "Warning", "No files selected for renaming.")
            return
        camera_prefix = self.camera_prefix_entry.text().strip()
        additional = self.additional_entry.text().strip()
        use_camera = self.checkbox_camera.isChecked()
        use_lens = self.checkbox_lens.isChecked()
        devider = self.devider_combo.currentText()
        non_images = [f for f in self.files if not is_image_file(f)]
        if non_images:
            reply = QMessageBox.question(
                self,
                "Non-image files found",
                "Some selected files are not images. Continue renaming?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                return
        image_files = [f for f in self.files if is_image_file(f)]
        if not image_files:
            QMessageBox.warning(self, "Warning", "No image files found for renaming.")
            return
        
        # Disable UI during processing
        self.rename_button.setEnabled(False)
        self.rename_button.setText("Processing...")
        self.select_files_button.setEnabled(False)
        self.select_folder_button.setEnabled(False)
        self.clear_list_button.setEnabled(False)
        
        # Start worker thread for background processing
        self.worker = RenameWorkerThread(
            image_files, camera_prefix, additional, use_camera, use_lens, 
            self.exif_method, devider, self.exiftool_path
        )
        self.worker.progress_update.connect(self.update_status)
        self.worker.finished.connect(self.on_rename_finished)
        self.worker.error.connect(self.on_rename_error)
        self.worker.start()
    
    def update_status(self, message):
        """Update status bar with progress message"""
        self.status.showMessage(message)
        QApplication.processEvents()  # Update UI
    
    def on_rename_finished(self, renamed_files, errors):
        """Handle completion of rename operation"""
        # Update the file list with the new file names
        original_non_images = [f for f in self.files if not is_image_file(f)]
        
        # Clear and rebuild the file list
        self.files.clear()
        self.file_list.clear()
        
        # Add renamed image files
        for renamed_file in renamed_files:
            self.files.append(renamed_file)
            self.file_list.addItem(renamed_file)
        
        # Add back any non-image files (they weren't renamed)
        for non_image in original_non_images:
            self.files.append(non_image)
            self.file_list.addItem(non_image)
        
        # Show results
        if errors:
            # Show detailed error report
            error_dialog = QDialog(self)
            error_dialog.setWindowTitle("Rename Results")
            error_layout = QVBoxLayout(error_dialog)
            
            success_label = QLabel(f"Successfully renamed: {len(renamed_files)} files")
            success_label.setStyleSheet("color: green; font-weight: bold;")
            error_layout.addWidget(success_label)
            
            if errors:
                error_label = QLabel(f"Errors encountered: {len(errors)}")
                error_label.setStyleSheet("color: red; font-weight: bold;")
                error_layout.addWidget(error_label)
                
                error_text = QPlainTextEdit()
                error_text.setReadOnly(True)
                error_text.setPlainText("\n".join(errors))
                error_layout.addWidget(error_text)
            
            close_button = QPushButton("Close")
            close_button.clicked.connect(error_dialog.accept)
            error_layout.addWidget(close_button)
            
            error_dialog.resize(500, 300)
            error_dialog.exec()
        else:
            QMessageBox.information(self, "Success", f"All files renamed successfully!\n{len(renamed_files)} files processed.")
        
        # Update preview and status
        self.update_preview()
        self.status.showMessage(f"Completed: {len(renamed_files)} files renamed", 5000)
        
        # Re-enable UI
        self.rename_button.setEnabled(True)
        self.rename_button.setText("Rename")
        self.select_files_button.setEnabled(True)
        self.select_folder_button.setEnabled(True)
        self.clear_list_button.setEnabled(True)
    
    def on_rename_error(self, error_message):
        """Handle critical error during rename operation"""
        QMessageBox.critical(self, "Critical Error", f"Unexpected error during renaming:\n{error_message}")
        self.status.showMessage("Rename operation failed", 3000)
        
        # Re-enable UI
        self.rename_button.setEnabled(True)
        self.rename_button.setText("Rename")
        self.select_files_button.setEnabled(True)
        self.select_folder_button.setEnabled(True)
        self.clear_list_button.setEnabled(True)

if __name__ == "__main__":
    app = QApplication([])
    window = FileRenamerApp()
    window.show()
    app.exec()