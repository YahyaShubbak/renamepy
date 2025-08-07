#!/usr/bin/env python3
"""
Core rename engine with original RenameWorkerThread implementation
"""

import os
import re
import datetime
from collections import defaultdict
from PyQt6.QtCore import QThread, pyqtSignal

# Import functions that exist in the original file but may be missing in modules
try:
    from .file_utils import is_media_file, get_safe_filename, sanitize_final_filename, get_safe_target_path, validate_path_length
except ImportError:
    # Fallback implementations
    def is_media_file(filename):
        IMAGE_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.gif', 
                           '.cr2', '.nef', '.arw', '.orf', '.rw2', '.dng', '.raw', '.sr2', '.pef', '.raf', '.3fr', '.erf', '.kdc', '.mos', '.nrw', '.srw', '.x3f']
        VIDEO_EXTENSIONS = ['.mp4', '.mov', '.avi', '.mkv', '.m4v', '.3gp', '.wmv', '.flv', '.webm', '.mpg', '.mpeg', '.m2v', '.mts', '.m2ts', '.ts', '.vob', '.asf', '.rm', '.rmvb', '.f4v', '.ogv']
        MEDIA_EXTENSIONS = IMAGE_EXTENSIONS + VIDEO_EXTENSIONS
        return os.path.splitext(filename)[1].lower() in MEDIA_EXTENSIONS
    
    def sanitize_final_filename(filename):
        safe_name = re.sub(r'[<>:"/\\|?*]', '_', filename)
        safe_name = re.sub(r'_{2,}', '_', safe_name)
        return safe_name.strip('_')
    
    def get_safe_target_path(original_file, new_filename):
        directory = os.path.dirname(original_file)
        return os.path.join(directory, new_filename)
    
    def validate_path_length(path):
        return len(path) <= 260

# Import exif_processor module (not individual functions to avoid scope conflicts)
import exif_processor

def get_filename_components_static(date_taken, camera_prefix, additional, camera_model, lens_model, 
                                 use_camera, use_lens, num, custom_order, date_format="YYYY-MM-DD", use_date=True, selected_metadata=None):
    """
    Static version of get_filename_components for use in worker threads.
    Build filename components according to the selected order.
    Sequential number can now be positioned flexibly.
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
    
    # Check if camera/lens are in selected_metadata to avoid duplicates
    has_camera_in_metadata = selected_metadata and 'camera' in selected_metadata
    has_lens_in_metadata = selected_metadata and 'lens' in selected_metadata
    
    # Define all possible components
    components = {
        "Date": formatted_date if (use_date and formatted_date) else None,
        "Prefix": camera_prefix if camera_prefix else None,
        "Additional": additional if additional else None,
        "Camera": camera_model if (use_camera and camera_model and not has_camera_in_metadata) else None,
        "Lens": lens_model if (use_lens and lens_model and not has_lens_in_metadata) else None,
        "Number": f"{num:03d}"  # FLEXIBLE: Make number a regular component
    }
    
    # Build ordered list based on custom order - INCLUDING metadata components
    ordered_parts = []
    
    # Format metadata for filename (safe characters, consistent format)
    def format_metadata_for_filename(key, value):
        """Format EXIF metadata for safe filename usage"""
        if not value or value == "(not detected)":
            return None
        
        # SIMPLIFIED FIX: Skip boolean flags (these indicate extraction needed)
        if isinstance(value, bool):
            return None  # This is a flag, not actual data
            
        # CRITICAL FIX: Skip placeholder values (these indicate type selection only)
        if isinstance(value, str) and value.startswith('<') and value.endswith('>'):
            return None  # This is a placeholder, not actual data
        
        # Clean and format the value
        formatted = str(value).strip()
        
        # Handle specific metadata types
        if key in ['camera']:
            # Camera: "SONY ILCE-7CM2" -> "SONY-ILCE-7CM2"
            formatted = formatted.replace(' ', '-').replace('/', '-')
        elif key in ['lens']:
            # Lens: "FE 20-70mm F4 G" -> "FE-20-70mm-F4-G"
            formatted = formatted.replace(' ', '-').replace('/', '-')
        elif key in ['FocalLength', 'Focal Length', 'focal_length']:
            # Convert focal length to simple format: "70mm" -> "70mm"
            formatted = re.sub(r'(\d+(?:\.\d+)?)\s*mm.*', r'\1mm', formatted)
        elif key in ['FNumber', 'F-Number', 'Aperture', 'aperture']:
            # Convert f-number to simple format: "f/5.6" -> "f5.6"
            formatted = re.sub(r'f[/\\]?(\d+(?:\.\d+)?)', r'f\1', formatted)
        elif key in ['ISO', 'ISO Speed', 'iso']:
            # Handle ISO format: "100" -> "ISO100"
            if formatted.isdigit():
                formatted = f"ISO{formatted}"
            else:
                formatted = re.sub(r'ISO\s*(\d+)', r'ISO\1', formatted)
        elif key in ['ShutterSpeed', 'Shutter Speed', 'shutter', 'shutter_speed']:
            # Convert shutter speed: "1/800s" -> "1-800s" (safe for filename)
            # CRITICAL FIX: Handle cases where 's' might already be present
            # First remove any existing 's' at the end to avoid double 's'
            formatted = re.sub(r's$', '', formatted)  # Remove trailing 's' if present
            # Then convert fraction and add single 's'
            formatted = re.sub(r'(\d+)/(\d+)', r'\1-\2s', formatted)
            # Clean up any remaining spaces
            formatted = re.sub(r'\s+', '', formatted)
        elif key in ['date']:
            # Date formatting: "2025:04:20 10:12:06" -> "2025-04-20"
            formatted = formatted.split(' ')[0].replace(':', '-')
        
        # Replace problematic characters with safe alternatives
        formatted = re.sub(r'[<>:"/\\|?*]', '', formatted)  # Remove forbidden chars
        formatted = re.sub(r'\s+', '_', formatted)  # Replace spaces with underscores
        formatted = re.sub(r'[^\w\-_.]', '', formatted)  # Keep only safe characters
        
        return formatted if formatted else None
    
    # Process components in the order specified by custom_order
    for component_name in custom_order:
        component_value = None
        
        # Check if it's a basic component
        if component_name in components:
            component_value = components[component_name]
        # Check if it's a metadata component (Meta_*)
        elif component_name.startswith('Meta_') and selected_metadata:
            metadata_key = component_name[5:]  # Remove "Meta_" prefix
            if metadata_key in selected_metadata:
                raw_value = selected_metadata[metadata_key]
                component_value = format_metadata_for_filename(metadata_key, raw_value)
        
        # Add component if it has a value
        if component_value:
            ordered_parts.append(component_value)
            
    # Add any remaining metadata that wasn't in custom_order (fallback)
    # BUT ONLY if no metadata components were specified in custom_order
    if selected_metadata:
        # Check if any Meta_ components are in custom_order
        has_meta_in_order = any(comp.startswith('Meta_') for comp in custom_order)
        
        # Only add fallback metadata if no Meta_ components were explicitly ordered
        if not has_meta_in_order:
            for key, value in selected_metadata.items():
                meta_component_name = f"Meta_{key}"
                if value:
                    formatted_value = format_metadata_for_filename(key, value)
                    if formatted_value:
                        ordered_parts.append(formatted_value)
    
    # FLEXIBLE: Only add number at end if it wasn't in custom_order
    if "Number" not in custom_order:
        ordered_parts.append(f"{num:03d}")
    
    return ordered_parts

class RenameWorkerThread(QThread):
    """
    Worker thread for file renaming to prevent UI freezing
    """
    progress_update = pyqtSignal(str)
    finished = pyqtSignal(list, list, dict)  # EXTENDED: renamed_files, errors, timestamp_backup
    error = pyqtSignal(str)
    
    def __init__(self, files, camera_prefix, additional, use_camera, use_lens, 
                 exif_method, devider, exiftool_path, custom_order, date_format="YYYY-MM-DD", use_date=True, continuous_counter=False, selected_metadata=None, sync_exif_date=False):
        super().__init__()
        self.files = files
        self.camera_prefix = camera_prefix
        self.additional = additional
        self.use_camera = use_camera
        self.use_lens = use_lens
        self.exif_method = exif_method
        self.devider = devider
        self.exiftool_path = exiftool_path
        self.custom_order = custom_order
        self.date_format = date_format
        self.use_date = use_date
        self.continuous_counter = continuous_counter
        self.selected_metadata = selected_metadata or {}
        self.sync_exif_date = sync_exif_date  # NEW: EXIF date synchronization flag
    
    def run(self):
        """Run the rename operation in background thread"""
        try:
            self.progress_update.emit("Starting rename operation...")
            
            # Use optimized rename function
            renamed_files, errors, timestamp_backup = self.optimized_rename_files()
            
            # IMPORTANT: Clean up global ExifTool instance after batch processing
            exif_processor.cleanup_global_exiftool()
            
            self.finished.emit(renamed_files, errors, timestamp_backup)
        except Exception as e:
            # Clean up ExifTool instance even if there's an error
            exif_processor.cleanup_global_exiftool()
            self.error.emit(str(e))
    
    def _create_continuous_counter_map(self):
        """
        CONTINUOUS COUNTER: Create a master mapping of all files to their continuous counter numbers.
        This is done once for all files across all directories.
        IMPORTANT: File pairs (JPG+RAW) share the same counter number!
        """
        if hasattr(self, '_continuous_counter_map'):
            return  # Already created
            
        self._continuous_counter_map = {}
        date_group_pairs = []
        
        self.progress_update.emit("Creating continuous counter map...")
        
        # Step 1: Group files by basename AND directory (CRITICAL FIX for identical filenames in different folders)
        basename_groups = defaultdict(list)
        for file in self.files:
            if is_media_file(file):
                # CRITICAL FIX: Include directory path to prevent grouping identical filenames from different folders
                directory = os.path.dirname(file)
                base = os.path.splitext(os.path.basename(file))[0]
                # Create unique key combining directory and basename
                unique_key = f"{directory}#{base}"
                basename_groups[unique_key].append(file)
        
        # Step 2: Create file groups (same logic as main processing)
        file_groups = []
        orphaned_files = []
        for base, file_list in basename_groups.items():
            if len(file_list) > 1:
                file_groups.append(file_list)  # JPG+RAW pairs
            else:
                orphaned_files.extend(file_list)  # Single files
        
        # Add orphans as individual groups
        for file in orphaned_files:
            file_groups.append([file])
        
        # Step 3: Get date for each group and create (date, group) pairs
        for group in file_groups:
            first_file = group[0]  # Use first file to determine group date
            file_date = None
            
            try:
                if self.exif_method:
                    d, _, _ = exif_processor.get_selective_cached_exif_data(
                        first_file, self.exif_method, self.exiftool_path,
                        need_date=True, need_camera=False, need_lens=False
                    )
                    if d:
                        file_date = d
                
                # Fallback to filename pattern
                if not file_date:
                    m = re.search(r'(20\d{2})(\d{2})(\d{2})', os.path.basename(first_file))
                    if m:
                        file_date = f"{m.group(1)}{m.group(2)}{m.group(3)}"
                
                # Fallback to file date
                if not file_date:
                    mtime = os.path.getmtime(first_file)
                    dt = datetime.datetime.fromtimestamp(mtime)
                    file_date = dt.strftime('%Y%m%d')
                    
                if file_date:
                    date_group_pairs.append((file_date, group))
            except:
                # Ultimate fallback
                try:
                    mtime = os.path.getmtime(first_file)
                    dt = datetime.datetime.fromtimestamp(mtime)
                    file_date = dt.strftime('%Y%m%d')
                    date_group_pairs.append((file_date, group))
                except:
                    pass
        
        # Step 4: Sort by date, then by original file order (using file modification time as fallback)
        def get_sort_key(date_group):
            date, group = date_group
            first_file = group[0]
            try:
                # Try to extract number from filename for natural sorting
                basename = os.path.basename(first_file)
                # Look for numbers in filename (like DSC0001, IMG_1234, etc.)
                # Use ALL digits to maintain original order
                match = re.search(r'(\d+)', basename)
                if match:
                    # Keep the original string with leading zeros for proper sorting
                    file_number_str = match.group(1)
                    file_number = int(file_number_str)
                    # Use file modification time as primary sort after date to maintain chronological order
                    try:
                        mtime = os.path.getmtime(first_file)
                        return (date, mtime, file_number, first_file)
                    except:
                        return (date, file_number, first_file)
                else:
                    # Fallback to modification time then filename
                    try:
                        mtime = os.path.getmtime(first_file)
                        return (date, mtime, first_file)
                    except:
                        return (date, 0, first_file)
            except:
                # Ultimate fallback to filename
                return (date, 0, first_file)
        
        date_group_pairs.sort(key=get_sort_key)
        
        # Step 5: Assign continuous counter numbers to GROUPS (not individual files)
        counter = 1
        for date, group in date_group_pairs:
            # All files in the same group get the same counter number
            for file in group:
                self._continuous_counter_map[file] = counter
            counter += 1  # Increment only once per group
    
    def optimized_rename_files(self):
        """
        SUPER OPTIMIZED rename function with selective EXIF processing
        Only extracts the metadata fields that are actually needed
        """
        self.progress_update.emit("Starting optimized batch processing...")
        
        # CONTINUOUS COUNTER: Pre-process ALL files to create master counter map
        if self.use_date and self.continuous_counter:
            self._create_continuous_counter_map()
        
        # Clear cache for fresh processing
        exif_processor.clear_global_exif_cache()
        
        # Determine what EXIF fields we actually need
        need_date = self.use_date
        need_camera = self.use_camera
        need_lens = self.use_lens
        
        # Early exit message for user
        fields_needed = []
        if need_date:
            fields_needed.append("date")
        if need_camera:
            fields_needed.append("camera")
        if need_lens:
            fields_needed.append("lens")
        
        if fields_needed:
            self.progress_update.emit(f"Extracting only: {', '.join(fields_needed)}")
        else:
            self.progress_update.emit("No EXIF extraction needed - using file names only")
        
        # EXIF DATE SYNC: Process file date synchronization if requested
        timestamp_backup = {}
        
        # Debug: Check EXIF sync status
        print(f"🔍 EXIF Sync Debug:")
        print(f"   sync_exif_date: {self.sync_exif_date}")
        print(f"   exiftool_path: {self.exiftool_path}")
        print(f"   EXIFTOOL_AVAILABLE: {getattr(exif_processor, 'EXIFTOOL_AVAILABLE', 'Unknown')}")
        
        if self.sync_exif_date:
            self.progress_update.emit("Synchronizing EXIF dates to file timestamps...")
            print("🔧 Starting EXIF date synchronization...")
            
            media_files = [f for f in self.files if is_media_file(f)]
            print(f"🔍 Media files for sync: {len(media_files)}")
            
            # Use exiftool_path if available, otherwise let sync function handle it
            effective_exiftool_path = self.exiftool_path if self.exiftool_path else None
            
            successes, sync_errors, timestamp_backup = exif_processor.batch_sync_exif_dates(
                media_files, 
                effective_exiftool_path, 
                lambda msg: self.progress_update.emit(f"Date sync: {msg}")
            )
            
            print(f"📊 EXIF sync results: {len(successes)} successes, {len(sync_errors)} errors")
            
            if successes:
                self.progress_update.emit(f"Successfully synced dates for {len(successes)} files")
                for file_path, message in successes:
                    print(f"   ✅ {os.path.basename(file_path)}: {message}")
            if sync_errors:
                self.progress_update.emit(f"Failed to sync dates for {len(sync_errors)} files")
                for file_path, error in sync_errors:
                    print(f"   ❌ {os.path.basename(file_path)}: {error}")
        else:
            print("🔍 EXIF date sync not requested or not available")
        
        # Step 1: Group files by basename AND directory (CRITICAL FIX for identical filenames in different folders)
        file_groups = []
        basename_groups = defaultdict(list)
        for file in self.files:
            if is_media_file(file):
                # CRITICAL FIX: Include directory path to prevent grouping identical filenames from different folders
                directory = os.path.dirname(file)
                base = os.path.splitext(os.path.basename(file))[0]
                # Create unique key combining directory and basename
                unique_key = f"{directory}#{base}"
                basename_groups[unique_key].append(file)
        
        # Separate grouped and orphaned files
        orphaned_files = []
        for base, file_list in basename_groups.items():
            if len(file_list) > 1:
                file_groups.append(file_list)
            else:
                orphaned_files.extend(file_list)
        
        # Add orphans as individual groups
        for file in orphaned_files:
            file_groups.append([file])
        
        self.progress_update.emit(f"Processing {len(file_groups)} file groups...")
        
        # If date is not included in filename, sort groups chronologically for consistent numbering
        if not self.use_date:
            def get_earliest_timestamp(group):
                """Get the earliest timestamp from a group of files for sorting"""
                earliest = None
                for file in group:
                    try:
                        # Only extract date if we have EXIF method available
                        if self.exif_method and need_date:
                            date_taken, _, _ = exif_processor.get_selective_cached_exif_data(
                                file, self.exif_method, self.exiftool_path,
                                need_date=True, need_camera=False, need_lens=False
                            )
                            if date_taken:
                                timestamp = datetime.datetime.strptime(date_taken, '%Y%m%d')
                                if earliest is None or timestamp < earliest:
                                    earliest = timestamp
                                continue
                        
                        # Fallback to file modification time
                        mtime = os.path.getmtime(file)
                        timestamp = datetime.datetime.fromtimestamp(mtime)
                        if earliest is None or timestamp < earliest:
                            earliest = timestamp
                    except:
                        # Fallback to file modification time
                        mtime = os.path.getmtime(file)
                        timestamp = datetime.datetime.fromtimestamp(mtime)
                        if earliest is None or timestamp < earliest:
                            earliest = timestamp
                return earliest or datetime.datetime.now()
            
            # Sort file groups by earliest timestamp
            file_groups.sort(key=get_earliest_timestamp)
        
        # Step 2: Process each group with SELECTIVE EXIF reads
        renamed_files = []
        errors = []
        date_counter = {}
        
        for i, group_files in enumerate(file_groups):
            if i % 100 == 0:  # Update progress every 100 groups for better performance
                self.progress_update.emit(f"Processing group {i+1}/{len(file_groups)}")
            
            # Check file access (fast check only)
            accessible_files = [f for f in group_files if os.path.exists(f)]
            if not accessible_files:
                continue
            
            # OPTIMIZED: Extract ONLY the EXIF data we actually need
            date_taken = None
            camera_model = None
            lens_model = None
            
            # Strategy: Try to get all needed data from the first file if possible
            first_file = accessible_files[0]
            
            if self.exif_method and any([need_date, need_camera, need_lens]):
                # Single optimized call to get only what we need
                date_taken, camera_model, lens_model = exif_processor.get_selective_cached_exif_data(
                    first_file, self.exif_method, self.exiftool_path,
                    need_date=need_date, need_camera=need_camera, need_lens=need_lens
                )
                
                # If we didn't get everything we need from the first file, try others
                if ((need_date and not date_taken) or 
                    (need_camera and not camera_model) or 
                    (need_lens and not lens_model)):
                    
                    for file in accessible_files[1:]:
                        # Only request fields we still need
                        still_need_date = need_date and not date_taken
                        still_need_camera = need_camera and not camera_model
                        still_need_lens = need_lens and not lens_model
                        
                        if not any([still_need_date, still_need_camera, still_need_lens]):
                            break  # We have everything we need
                        
                        d, c, l = exif_processor.get_selective_cached_exif_data(
                            file, self.exif_method, self.exiftool_path,
                            need_date=still_need_date, 
                            need_camera=still_need_camera, 
                            need_lens=still_need_lens
                        )
                        
                        if still_need_date and d:
                            date_taken = d
                        if still_need_camera and c:
                            camera_model = c
                        if still_need_lens and l:
                            lens_model = l
            
            # Fallback date extraction (only if we need date but didn't get it)
            if need_date and not date_taken:
                # Try filename pattern first
                for file in accessible_files:
                    m = re.search(r'(20\d{2})(\d{2})(\d{2})', os.path.basename(file))
                    if m:
                        date_taken = f"{m.group(1)}{m.group(2)}{m.group(3)}"
                        break
                
                # Use file modification time as last resort
                if not date_taken:
                    mtime = os.path.getmtime(accessible_files[0])
                    dt = datetime.datetime.fromtimestamp(mtime)
                    date_taken = dt.strftime('%Y%m%d')
            
            # CRITICAL FIX: Add fallback values for camera and lens when enabled but not detected
            # This ensures consistency between preview and actual rename operation
            if need_camera and not camera_model:
                # Use fallback camera model when checkbox is enabled but no EXIF data found
                camera_model = "ILCE-7CM2"  # Same fallback as in preview
            
            if need_lens and not lens_model:
                # Use fallback lens model when checkbox is enabled but no EXIF data found  
                lens_model = "FE-20-70mm-F4-G"  # Same fallback as in preview
            
            # Counter logic - depends on whether date is included in filename and continuous counter setting
            if self.use_date and not self.continuous_counter:
                # Standard mode: counter per date (resets each day)
                counter_key = date_taken or "unknown"
                if counter_key not in date_counter:
                    date_counter[counter_key] = 1
                else:
                    date_counter[counter_key] += 1
                num = date_counter[counter_key]
            elif not self.use_date:
                # When date is NOT included: continuous counter across all files
                global_key = "all_files"
                if global_key not in date_counter:
                    date_counter[global_key] = 1
                else:
                    date_counter[global_key] += 1
                num = date_counter[global_key]
            elif self.use_date and self.continuous_counter:
                # CONTINUOUS COUNTER: Get the counter for this file group
                # All files in the same group (JPG+RAW pairs) get the same number
                if hasattr(self, '_continuous_counter_map'):
                    # Use the first file in the group to determine the counter
                    first_file = accessible_files[0]
                    num = self._continuous_counter_map.get(first_file, 1)
                else:
                    # Fallback to simple counter if map wasn't created
                    global_key = "all_files"
                    if global_key not in date_counter:
                        date_counter[global_key] = 1
                    else:
                        date_counter[global_key] += 1
                    num = date_counter[global_key]
            
            # Rename files in group
            for file in accessible_files:
                try:
                    # CRITICAL FIX: Extract EXIF data for EACH individual file
                    # This ensures each file gets its own metadata (aperture, ISO, etc.)
                    file_date_taken = date_taken  # Group date as fallback
                    file_camera_model = camera_model  # Group camera as fallback  
                    file_lens_model = lens_model  # Group lens as fallback
                    
                    # Extract individual EXIF data for this specific file
                    if self.exif_method and any([need_date, need_camera, need_lens]):
                        try:
                            d, c, l = exif_processor.get_selective_cached_exif_data(
                                file, self.exif_method, self.exiftool_path,
                                need_date=need_date, need_camera=need_camera, need_lens=need_lens
                            )
                            # Use individual file data if available, otherwise fall back to group data
                            if need_date and d:
                                file_date_taken = d
                            if need_camera and c:
                                file_camera_model = c
                            if need_lens and l:
                                file_lens_model = l
                        except Exception as e:
                            # Silently continue if individual EXIF extraction fails
                            pass
                    
                    # All files in the group use the same counter (num)
                    # This ensures JPG+RAW pairs get identical numbers
                    current_num = num
                    
                    ext = os.path.splitext(file)[1]
                    
                    # SIMPLIFIED FIX: Extract individual metadata for each file
                    individual_metadata = self.selected_metadata.copy() if self.selected_metadata else {}
                    
                    if self.selected_metadata and self.exif_method:
                        # Check if we need individual file metadata (Boolean flags)
                        needs_individual_metadata = any(
                            key in self.selected_metadata and 
                            self.selected_metadata[key] is True
                            for key in ['aperture', 'iso', 'focal_length', 'shutter_speed', 'exposure_bias']
                        )
                        
                        if needs_individual_metadata:
                            # Extract metadata for this specific file and update only relevant fields
                            try:
                                # CRITICAL FIX: Use the same method as preview (which works!)
                                date_taken, camera_model, lens_model = exif_processor.get_selective_cached_exif_data(
                                    file, self.exif_method, self.exiftool_path,
                                    need_date=False, need_camera=False, need_lens=False
                                )
                                
                                # Also try get_all_metadata for comparison
                                file_metadata = exif_processor.get_all_metadata(file, self.exif_method, self.exiftool_path)
                                
                                # If get_all_metadata is empty, use alternative method
                                if not file_metadata:
                                    # Use ExifTool directly for these specific tags
                                    try:
                                        raw_meta = exif_processor.get_exiftool_metadata_shared(file, self.exiftool_path)
                                        
                                        if raw_meta:
                                            # Extract the metadata we need manually
                                            file_metadata = {}
                                            
                                            # Aperture
                                            aperture = raw_meta.get('EXIF:FNumber') or raw_meta.get('FNumber')
                                            if aperture:
                                                try:
                                                    if isinstance(aperture, str) and '/' in aperture:
                                                        num, den = aperture.split('/')
                                                        aperture_val = float(num) / float(den)
                                                    else:
                                                        aperture_val = float(aperture)
                                                    file_metadata['aperture'] = f"f{aperture_val:.1f}".replace('.0', '')
                                                except:
                                                    pass
                                            
                                            # ISO
                                            iso = raw_meta.get('EXIF:ISO') or raw_meta.get('ISO')
                                            if iso:
                                                file_metadata['iso'] = str(iso)
                                            
                                            # Focal Length
                                            focal_length = raw_meta.get('EXIF:FocalLength') or raw_meta.get('FocalLength')
                                            if focal_length:
                                                try:
                                                    if isinstance(focal_length, str) and '/' in focal_length:
                                                        num, den = focal_length.split('/')
                                                        fl_val = float(num) / float(den)
                                                    else:
                                                        fl_val = float(focal_length)
                                                    file_metadata['focal_length'] = f"{fl_val:.0f}mm"
                                                except:
                                                    pass
                                            
                                            # Shutter Speed
                                            shutter = raw_meta.get('EXIF:ShutterSpeedValue') or raw_meta.get('EXIF:ExposureTime')
                                            if shutter:
                                                file_metadata['shutter_speed'] = str(shutter)
                                    
                                    except Exception as e2:
                                        # Alternative method failed, continue with empty metadata
                                        pass
                                
                                # Only update the metadata keys that are marked as True
                                for key in ['aperture', 'iso', 'focal_length', 'shutter', 'shutter_speed', 'exposure_bias']:
                                    if key in self.selected_metadata and self.selected_metadata[key] is True:
                                        # CRITICAL FIX: Add key mapping for shutter -> shutter_speed (same as main_application.py)
                                        exif_key = key
                                        if key == 'shutter' and 'shutter_speed' in file_metadata:
                                            exif_key = 'shutter_speed'
                                        
                                        if exif_key in file_metadata:
                                            individual_metadata[key] = file_metadata[exif_key]
                                        
                            except Exception as e:
                                # Silently continue if metadata extraction fails
                                # Keep the original selected_metadata values as fallback
                                pass
                    
                    # Use get_filename_components_static for ordered naming
                    name_parts = get_filename_components_static(
                        file_date_taken, self.camera_prefix, self.additional, 
                        file_camera_model, file_lens_model, self.use_camera, self.use_lens, 
                        current_num, self.custom_order, self.date_format, self.use_date, individual_metadata
                    )
                    
                    sep = "" if self.devider == "None" else self.devider
                    new_name = sep.join(name_parts) + ext
                    new_name = sanitize_final_filename(new_name)
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
        
        # Return results including timestamp backup for potential undo operations
        return renamed_files, errors, timestamp_backup

# Export classes and functions
__all__ = ['RenameWorkerThread']
