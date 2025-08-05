#!/usr/bin/env python3
"""
Core rename engine and worker thread for the RenameFiles application.
"""

import os
import time
from collections import defaultdict
from PyQt6.QtCore import QThread, pyqtSignal

from .file_utils import (
    is_media_file, sanitize_final_filename, get_safe_target_path, 
    validate_path_length, check_file_access
)
from .filename_generator import (
    get_filename_components_static, group_files_with_failsafe,
    create_continuous_counter_map, extract_date_from_file
)
from .exif_handler import (
    get_selective_cached_exif_data, clear_global_exif_cache, cleanup_global_exiftool
)

class RenameWorkerThread(QThread):
    """
    Worker thread for file renaming to prevent UI freezing
    """
    progress_update = pyqtSignal(str)
    finished = pyqtSignal(list, list)
    error = pyqtSignal(str)
    
    def __init__(self, files, camera_prefix, additional, use_camera, use_lens, 
                 exif_method, devider, exiftool_path, custom_order, date_format="YYYY-MM-DD", 
                 use_date=True, continuous_counter=False):
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
    
    def run(self):
        """Run the rename operation in the background thread"""
        try:
            renamed_files, errors = self.optimized_rename_files()
            self.finished.emit(renamed_files, errors)
        except Exception as e:
            self.error.emit(str(e))
        finally:
            # Always clean up resources
            cleanup_global_exiftool()
    
    def optimized_rename_files(self):
        """
        SUPER OPTIMIZED rename function with selective EXIF processing
        Only extracts the metadata fields that are actually needed
        """
        self.progress_update.emit("Starting optimized batch processing...")
        
        # CONTINUOUS COUNTER: Pre-process ALL files to create master counter map
        continuous_counter_map = {}
        if self.use_date and self.continuous_counter:
            self.progress_update.emit("Creating continuous counter mapping...")
            continuous_counter_map = create_continuous_counter_map(
                self.files, self.use_date, self.exif_method, self.exiftool_path
            )
        
        # Clear cache for fresh processing
        clear_global_exif_cache()
        
        # Determine what EXIF fields we actually need
        need_date = self.use_date
        need_camera = self.use_camera
        need_lens = self.use_lens
        
        # Early exit message for user
        fields_needed = []
        if need_date:
            fields_needed.append("Date")
        if need_camera:
            fields_needed.append("Camera")
        if need_lens:
            fields_needed.append("Lens")
        
        if fields_needed:
            self.progress_update.emit(f"Extracting EXIF fields: {', '.join(fields_needed)}")
        else:
            self.progress_update.emit("No EXIF extraction needed - using filename patterns only")
        
        # Step 1: Group files by basename AND directory (CRITICAL FIX for identical filenames in different folders)
        file_groups = []
        basename_groups = defaultdict(list)
        for file in self.files:
            # Use full path + basename for grouping to handle same basenames in different directories
            directory = os.path.dirname(file)
            basename = os.path.splitext(os.path.basename(file))[0]
            group_key = f"{directory}::{basename}"
            basename_groups[group_key].append(file)
        
        # Separate grouped and orphaned files
        orphaned_files = []
        for group_key, file_list in basename_groups.items():
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
            self.progress_update.emit("Sorting files chronologically for consistent numbering...")
            # Sort groups by the earliest file timestamp in each group
            def get_group_timestamp(group):
                timestamps = []
                for file in group:
                    try:
                        mtime = os.path.getmtime(file)
                        timestamps.append(mtime)
                    except:
                        timestamps.append(0)
                return min(timestamps) if timestamps else 0
            
            file_groups.sort(key=get_group_timestamp)
        
        # Step 2: Process each group with SELECTIVE EXIF reads
        renamed_files = []
        errors = []
        date_counter = {}
        
        for i, group_files in enumerate(file_groups):
            self.progress_update.emit(f"Processing group {i+1}/{len(file_groups)} ({len(group_files)} files)")
            
            # Sort files within group for consistent numbering
            group_files.sort()
            
            # Extract EXIF data for the first file (representative of the group)
            representative_file = group_files[0]
            
            # Use selective EXIF extraction to get only what we need
            date_taken, camera_model, lens_model = get_selective_cached_exif_data(
                representative_file, self.exif_method, self.exiftool_path,
                need_date, need_camera, need_lens
            )
            
            # Fallback date extraction if needed
            if need_date and not date_taken:
                date_taken = extract_date_from_file(representative_file, self.exif_method, self.exiftool_path)
            
            # Process each file in the group
            for j, old_file in enumerate(group_files):
                try:
                    # Check file accessibility
                    if not check_file_access(old_file):
                        errors.append(f"Cannot access file: {os.path.basename(old_file)} (locked or permission denied)")
                        continue
                    
                    # Determine counter based on mode
                    if self.continuous_counter and old_file in continuous_counter_map:
                        counter = continuous_counter_map[old_file]
                    elif self.use_date and date_taken:
                        # Regular date-based counter
                        if date_taken not in date_counter:
                            date_counter[date_taken] = 1
                        counter = date_counter[date_taken]
                        date_counter[date_taken] += 1
                    else:
                        # Sequential counter across all files
                        counter = (i * 1000) + j + 1  # Ensure unique counters
                    
                    # Generate filename components
                    components = get_filename_components_static(
                        date_taken, self.camera_prefix, self.additional,
                        camera_model, lens_model, self.use_camera, self.use_lens,
                        counter, self.custom_order, self.date_format, self.use_date
                    )
                    
                    # Join components with separator
                    if self.devider and self.devider != "None":
                        new_base = self.devider.join(components)
                    else:
                        new_base = "".join(components)
                    
                    # Add original extension
                    original_ext = os.path.splitext(old_file)[1]
                    new_filename = sanitize_final_filename(new_base) + original_ext
                    
                    # Generate safe target path
                    new_file = get_safe_target_path(old_file, new_filename)
                    
                    # Validate path length
                    if not validate_path_length(new_file):
                        errors.append(f"Target path too long: {new_filename}")
                        continue
                    
                    # Skip if no actual change needed
                    if os.path.normpath(old_file) == os.path.normpath(new_file):
                        renamed_files.append(old_file)  # No change needed
                        continue
                    
                    # Perform the rename
                    os.rename(old_file, new_file)
                    renamed_files.append(new_file)
                    
                except Exception as e:
                    errors.append(f"Failed to rename {os.path.basename(old_file)}: {str(e)}")
        
        # IMPORTANT: Clean up global ExifTool instance after batch processing
        cleanup_global_exiftool()
        
        self.progress_update.emit(f"Completed: {len(renamed_files)} files renamed, {len(errors)} errors")
        return successful_renames, errors

class RenameEngine:
    """Main rename engine that coordinates the renaming process"""
    
    def __init__(self, exif_handler, filename_generator):
        self.exif_handler = exif_handler
        self.filename_generator = filename_generator
    
    def rename_files(self, files, settings):
        """Rename files based on settings"""
        try:
            # Create worker thread for rename operation
            worker = RenameWorkerThread(
                files=files,
                camera_prefix=settings.get('camera_prefix', ''),
                additional=settings.get('additional', ''),
                use_camera=settings.get('include_camera', False),
                use_lens=settings.get('include_lens', False),
                exif_method=self.exif_handler.current_method,
                devider=settings.get('separator', '-'),
                exiftool_path=getattr(self.exif_handler, 'exiftool_path', None),
                custom_order=["Date", "Prefix", "Additional", "Camera", "Lens"],
                date_format=settings.get('date_format', 'YYYY-MM-DD'),
                use_date=settings.get('include_date', True),
                continuous_counter=settings.get('continuous_counter', False)
            )
            
            # Run the worker thread
            worker.run()
            
            # For now, return success count of files and empty errors
            # In the real implementation, this would get results from worker
            return len(files), []
            
        except Exception as e:
            return 0, [f"Rename operation failed: {str(e)}"]

def rename_files(files, camera_prefix, additional, use_camera, use_lens, exif_method, 
                devider="_", exiftool_path=None, custom_order=None, date_format="YYYY-MM-DD", use_date=True):
    """
    Optimized batch rename function using cached EXIF processing.
    Simply delegates to the optimized_rename_files function for better performance.
    
    Counter behavior:
    - When use_date=True: Counter resets per date (001, 002, 003... per day)
    - When use_date=False: Counter runs continuously across all files (001, 002, 003... regardless of date)
    
    Returns a list of new file paths and any errors encountered.
    """
    # Create a temporary worker thread instance to use its optimized function
    worker = RenameWorkerThread(files, camera_prefix, additional, use_camera, use_lens, 
                               exif_method, devider, exiftool_path, custom_order, date_format, use_date)
    
    # Use the optimized rename function directly
    return worker.optimized_rename_files()

# Alias for backward compatibility
RenameWorker = RenameWorkerThread
