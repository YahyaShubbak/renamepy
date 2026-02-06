#!/usr/bin/env python3
"""
Core rename engine with original RenameWorkerThread implementation.

This module provides the RenameWorkerThread class for batch file renaming
with EXIF metadata extraction and optional timestamp synchronization.
"""

import os
import re
import datetime
from collections import defaultdict
from typing import List, Tuple, Dict, Optional, Any, Callable
from PyQt6.QtCore import QThread, pyqtSignal

# Import unified utilities from file_utilities module
from .file_utilities import is_media_file, sanitize_final_filename, get_safe_target_path, validate_path_length

# Import exif_processor module (relative only to work inside package)
from . import exif_processor
from .filename_components import build_ordered_components
from .exif_undo_manager import write_original_filename_to_exif

class RenameWorkerThread(QThread):
    """Worker thread for file renaming & optional EXIF timestamp sync."""
    progress_update = pyqtSignal(str)
    finished = pyqtSignal(list, list, dict)  # renamed_files, errors, timestamp_backup
    error = pyqtSignal(str)

    def __init__(
        self,
        files: List[str],
        camera_prefix: str,
        additional: str,
        use_camera: bool,
        use_lens: bool,
        exif_method: str,
        separator: str,
        exiftool_path: Optional[str],
        custom_order: List[str],
        date_format: str,
        use_date: bool,
        continuous_counter: bool,
        selected_metadata: Dict[str, Any],
        sync_exif_date: bool,
        parent: Optional[QThread] = None,
        log_callable: Optional[Callable] = None,
        exif_service: Optional[Any] = None,
        save_original_to_exif: bool = False,
        **kwargs: Any,
    ) -> None:
            super().__init__(parent)
            self.files = files
            self.camera_prefix = camera_prefix
            self.additional = additional
            self.use_camera = use_camera
            self.use_lens = use_lens
            self.exif_method = exif_method
            self.separator = separator
            self.exiftool_path = exiftool_path
            self.custom_order = custom_order or []
            self.date_format = date_format
            self.use_date = use_date
            self.continuous_counter = continuous_counter
            self.selected_metadata = selected_metadata or {}
            self.sync_exif_date = sync_exif_date
            self._log = log_callable or (lambda *a, **k: None)
            self.exif_service = exif_service  # NEW: Store service instance
            self.save_original_to_exif = save_original_to_exif  # NEW: Persistent undo feature
            self.timestamp_options = kwargs.get('timestamp_options') or kwargs.get('timestamp_options'.lower()) or kwargs.get('TIMESTAMP_OPTIONS') or kwargs.get('timestamp_options'.upper()) or kwargs.get('timestamp_options', None)
            self.leave_names = kwargs.get('leave_names', False)
            # (Dry-run feature removed)

    def _debug(self, msg: str) -> None:
        """Log debug message safely.
        
        Args:
            msg: Debug message to log
        """
        try:
            self._log(msg)
        except Exception:
            pass
    
    # ------------------------------------------------------------------
    # Phase 2 Refactoring: Helper functions for optimized_rename_files
    # ------------------------------------------------------------------
    
    def _sync_exif_timestamps(self) -> Tuple[List[str], List[Tuple[str, str]], Dict[str, Any]]:
        """
        Sync EXIF timestamps to file timestamps (optional first step).
        
        Returns:
            Tuple containing:
                - success_list: List of successfully synced file paths
                - error_list: List of (file_path, error_message) tuples
                - timestamp_backup_dict: Backup of original timestamps for undo
        """
        if not self.sync_exif_date:
            return [], [], {}
        
        self.progress_update.emit("Synchronizing EXIF dates to file timestamps...")
        media_files = [f for f in self.files if is_media_file(f)]
        
        successes, sync_errors, timestamp_backup = exif_processor.batch_sync_exif_dates(
            media_files,
            self.exiftool_path if self.exiftool_path else None,
            lambda msg: self.progress_update.emit(f"Date sync: {msg}"),
            options=self.timestamp_options,
        )
        
        if successes:
            self.progress_update.emit(f"Successfully synced dates for {len(successes)} files")
        if sync_errors:
            self.progress_update.emit(f"Failed to sync dates for {len(sync_errors)} files")
        
        return successes, sync_errors, timestamp_backup
    
    def _create_file_groups(self) -> List[List[str]]:
        """
        Group RAW/JPEG siblings (same basename in same directory).
        
        Files with the same basename but different extensions (e.g., IMG_001.JPG 
        and IMG_001.ARW) are grouped together for synchronized renaming.
        
        Returns:
            List of file groups, where each group is a list of related file paths
        """
        basename_groups = defaultdict(list)
        for path in self.files:
            if is_media_file(path):
                directory = os.path.dirname(path)
                stem = os.path.splitext(os.path.basename(path))[0]
                basename_groups[f"{directory}#{stem}"].append(path)
        
        file_groups = []
        orphans = []
        for _k, group in basename_groups.items():
            if len(group) > 1:
                file_groups.append(group)
            else:
                orphans.extend(group)
        
        for f in orphans:
            file_groups.append([f])
        
        return file_groups
    
    def _pre_extract_exif_cache(self, file_groups: List[List[str]]) -> Dict[str, Optional[Dict[str, Any]]]:
        """
        Pre-extract EXIF data for all files once (performance optimization).
        
        This eliminates duplicate EXIF reads during sorting and renaming,
        providing 40-50% speedup for large batches.
        
        Args:
            file_groups: List of file groups to process
            
        Returns:
            Cache dictionary mapping file_path to EXIF data:
            {
                'date_str': Date string (YYYYMMDD format),
                'camera': Camera model name,
                'lens': Lens model name,
                'raw_meta': Raw EXIF metadata dictionary
            }
            Returns None for files that fail EXIF extraction.
        """
        exif_cache = {}
        
        if not self.exif_method:
            return exif_cache
        
        self.progress_update.emit("Pre-extracting EXIF data for all files...")
        
        for idx, group in enumerate(file_groups):
            if idx % 50 == 0:
                self.progress_update.emit(f"Extracting EXIF: {idx+1}/{len(file_groups)} groups")
            
            first_file = group[0]
            if first_file not in exif_cache:
                try:
                    # Extract full EXIF metadata once
                    if self.exif_service:
                        date_str, camera, lens = self.exif_service.get_selective_cached_exif_data(
                            first_file, self.exif_method, self.exiftool_path,
                            need_date=True, need_camera=True, need_lens=True
                        )
                        raw_meta = self.exif_service.extract_raw_exif(first_file)
                    else:
                        date_str, camera, lens = exif_processor.get_selective_cached_exif_data(
                            first_file, self.exif_method, self.exiftool_path,
                            need_date=True, need_camera=True, need_lens=True
                        )
                        raw_meta = exif_processor.get_exiftool_metadata_shared(first_file, self.exiftool_path)
                    
                    exif_cache[first_file] = {
                        'date_str': date_str,
                        'camera': camera,
                        'lens': lens,
                        'raw_meta': raw_meta
                    }
                except Exception as e:
                    self._debug(f"EXIF pre-extraction failed for {first_file}: {e}")
                    exif_cache[first_file] = None
        
        self.progress_update.emit("EXIF pre-extraction complete")
        return exif_cache
    
    def _get_exif_sort_key(self, group: List[str], exif_cache: Dict[str, Optional[Dict[str, Any]]]) -> Tuple[datetime.datetime, int, str]:
        """
        Generate sort key for chronological ordering based on EXIF timestamp.
        
        Uses EXIF DateTimeOriginal field when available, falls back to file
        modification time, then filename number as tiebreaker.
        
        Args:
            group: File group (list of file paths)
            exif_cache: Pre-extracted EXIF cache from _pre_extract_exif_cache
            
        Returns:
            Tuple of (datetime, file_number, filename) for stable sorting
        """
        first_file = group[0]
        exif_datetime = None
        
        # Use pre-extracted EXIF cache (PERFORMANCE OPTIMIZATION)
        if first_file in exif_cache and exif_cache[first_file]:
            cached_exif = exif_cache[first_file]
            date_str = cached_exif.get('date_str')
            raw_meta = cached_exif.get('raw_meta')
            
            if date_str and raw_meta:
                # Look for DateTimeOriginal with time
                datetime_fields = [
                    'EXIF:DateTimeOriginal',
                    'EXIF:CreateDate', 
                    'QuickTime:CreateDate',
                    'QuickTime:CreationDate'
                ]
                for field in datetime_fields:
                    if field in raw_meta:
                        dt_str = raw_meta[field]
                        try:
                            import datetime as dt_module
                            if ':' in dt_str:
                                dt_str_clean = dt_str.replace(':', '-', 2)
                                exif_datetime = dt_module.datetime.strptime(dt_str_clean, "%Y-%m-%d %H:%M:%S")
                                break
                        except Exception:
                            pass
        
        # Fallback to file modification time
        if not exif_datetime:
            try:
                import datetime as dt_module
                mtime = os.path.getmtime(first_file)
                exif_datetime = dt_module.datetime.fromtimestamp(mtime)
            except Exception:
                import datetime as dt_module
                exif_datetime = dt_module.datetime(1970, 1, 1)
        
        # Extract LAST number from filename as tiebreaker
        # Use the last number to get the actual sequence number (e.g., '003')
        # instead of the first number which is often the year (e.g., '2025')
        basename = os.path.basename(first_file)
        all_numbers = re.findall(r'(\d+)', basename)
        file_number = int(all_numbers[-1]) if all_numbers else 0
        
        return (exif_datetime, file_number, first_file)
    
    def _process_file_group(
        self, 
        group: List[str], 
        date_counter: Dict[str, int], 
        exif_cache: Dict[str, Optional[Dict[str, Any]]]
    ) -> Tuple[List[str], List[Tuple[str, str]]]:
        """
        Process a single file group and rename all files within it.
        
        Extracts metadata, builds new filenames, and performs the rename operation.
        Uses pre-extracted EXIF cache for performance.
        
        Args:
            group: List of file paths in this group (RAW+JPEG siblings)
            date_counter: Counter dictionary for per-date numbering {date: count}
            exif_cache: Pre-extracted EXIF cache from _pre_extract_exif_cache
            
        Returns:
            Tuple of:
                - renamed_files_list: List of successfully renamed file paths
                - errors_list: List of (file_path, error_message) tuples
        """
        renamed_files = []
        errors = []
        
        need_date = self.use_date
        need_camera = self.use_camera
        need_lens = self.use_lens
        
        group_existing = [p for p in group if os.path.exists(p)]
        if not group_existing:
            return renamed_files, errors

        date_taken = None
        camera_model = None
        lens_model = None
        first_file = group_existing[0]

        # ============================================================
        # PERFORMANCE OPTIMIZATION: Use pre-extracted EXIF cache
        # ============================================================
        if first_file in exif_cache and exif_cache[first_file]:
            cached_exif = exif_cache[first_file]
            date_taken = cached_exif.get('date_str') if need_date else None
            camera_model = cached_exif.get('camera') if need_camera else None
            lens_model = cached_exif.get('lens') if need_lens else None
            
            # Best-effort look through rest of group if anything missing
            if ((need_date and not date_taken) or (need_camera and not camera_model) or (need_lens and not lens_model)):
                for other in group_existing[1:]:
                    if other in exif_cache and exif_cache[other]:
                        other_exif = exif_cache[other]
                        if need_date and not date_taken: 
                            date_taken = other_exif.get('date_str')
                        if need_camera and not camera_model: 
                            camera_model = other_exif.get('camera')
                        if need_lens and not lens_model: 
                            lens_model = other_exif.get('lens')
                        if date_taken and camera_model and lens_model:
                            break
        # Fallback to old method if not in cache
        elif self.exif_method and any([need_date, need_camera, need_lens]):
            if self.exif_service:
                date_taken, camera_model, lens_model = self.exif_service.get_selective_cached_exif_data(
                    first_file, self.exif_method, self.exiftool_path,
                    need_date=need_date, need_camera=need_camera, need_lens=need_lens
                )
            else:
                date_taken, camera_model, lens_model = exif_processor.get_selective_cached_exif_data(
                    first_file, self.exif_method, self.exiftool_path,
                    need_date=need_date, need_camera=need_camera, need_lens=need_lens
                )

        # Fallbacks
        if need_date and not date_taken:
            for p in group_existing:
                m = re.search(r'(20\d{2})(\d{2})(\d{2})', os.path.basename(p))
                if m:
                    date_taken = f"{m.group(1)}{m.group(2)}{m.group(3)}"
                    break
            if not date_taken:
                try:
                    dt = datetime.datetime.fromtimestamp(os.path.getmtime(first_file))
                    date_taken = dt.strftime('%Y%m%d')
                except Exception:
                    date_taken = '19700101'
        if need_camera and not camera_model:
            camera_model = 'Unknown-Camera'
        if need_lens and not lens_model:
            lens_model = 'Unknown-Lens'

        # Counter logic
        if self.use_date and not self.continuous_counter:
            key = date_taken or 'unknown'
            date_counter[key] = date_counter.get(key, 0) + 1
            group_number = date_counter[key]
        elif not self.use_date:
            key = 'all_files'
            date_counter[key] = date_counter.get(key, 0) + 1
            group_number = date_counter[key]
        else:  # self.use_date and continuous_counter
            if hasattr(self, '_continuous_counter_map'):
                group_number = self._continuous_counter_map.get(first_file, 1)
            else:
                key = 'all_files'
                date_counter[key] = date_counter.get(key, 0) + 1
                group_number = date_counter[key]

        # Process each file in group
        for path in group_existing:
            try:
                file_date = date_taken
                file_cam = camera_model
                file_lens = lens_model
                if self.exif_method and any([need_date, need_camera, need_lens]):
                    try:
                        if self.exif_service:
                            d, c, l = self.exif_service.get_selective_cached_exif_data(
                                path, self.exif_method, self.exiftool_path,
                                need_date=need_date, need_camera=need_camera, need_lens=need_lens
                            )
                        else:
                            d, c, l = exif_processor.get_selective_cached_exif_data(
                                path, self.exif_method, self.exiftool_path,
                                need_date=need_date, need_camera=need_camera, need_lens=need_lens
                            )
                        if need_date and d: file_date = d
                        if need_camera and c: file_cam = c
                        if need_lens and l: file_lens = l
                    except Exception:
                        pass

                # Individual selected metadata (aperture, iso, etc.)
                individual_metadata = self.selected_metadata.copy() if self.selected_metadata else {}
                if self.selected_metadata and self.exif_method:
                    wants_extra = any(individual_metadata.get(k) is True for k in ['aperture','iso','focal_length','shutter','shutter_speed','exposure_bias'])
                    if wants_extra:
                        try:
                            if self.exif_service:
                                meta = self.exif_service.get_all_metadata(path, self.exif_method, self.exiftool_path) or {}
                            else:
                                meta = exif_processor.get_all_metadata(path, self.exif_method, self.exiftool_path) or {}
                            if meta:
                                if 'shutter' in individual_metadata and 'shutter_speed' in meta:
                                    individual_metadata['shutter'] = meta.get('shutter_speed')
                                for k in ['aperture','iso','focal_length','shutter_speed','exposure_bias']:
                                    if individual_metadata.get(k) is True and k in meta:
                                        individual_metadata[k] = meta[k]
                        except Exception:
                            pass

                parts = build_ordered_components(
                    date_taken=file_date,
                    camera_prefix=self.camera_prefix,
                    additional=self.additional,
                    camera_model=file_cam,
                    lens_model=file_lens,
                    use_camera=self.use_camera,
                    use_lens=self.use_lens,
                    number=group_number,
                    custom_order=self.custom_order,
                    date_format=self.date_format,
                    use_date=self.use_date,
                    selected_metadata=individual_metadata,
                )
                sep = '' if self.separator == 'None' else self.separator
                new_name = sanitize_final_filename(sep.join(parts) + os.path.splitext(path)[1])

                # CRITICAL FIX: Pass original file path, not directory!
                target_path = get_safe_target_path(path, new_name)

                if not validate_path_length(target_path):
                    errors.append((path, f"Target path too long: {len(target_path)} chars"))
                    continue

                if os.path.normpath(path) != os.path.normpath(target_path):
                    try:
                        # Write original filename to EXIF before renaming (if enabled)
                        if self.save_original_to_exif and self.exiftool_path:
                            original_filename = os.path.basename(path)
                            success, message = write_original_filename_to_exif(
                                path, original_filename, self.exiftool_path
                            )
                            if not success:
                                self._debug(f"Warning: Could not write original filename to EXIF: {message}")
                                # Continue with rename anyway - this is not a critical error
                        
                        os.rename(path, target_path)
                        renamed_files.append(target_path)
                    except Exception as e:
                        errors.append((path, str(e)))
                else:
                    renamed_files.append(path)
            except Exception as e:
                errors.append((path, str(e)))
        
        return renamed_files, errors
    
    # ------------------------------------------------------------------
    # End of Phase 2 helper functions
    # ------------------------------------------------------------------
    
    def run(self) -> None:
        """Run the rename operation in background thread.
        
        Emits progress_update signals during processing and finished signal
        when complete. Keeps ExifTool instance alive for performance.
        """
        self._debug(f"Starting rename thread with {len(self.files)} files. Continuous={self.continuous_counter} SyncTS={self.sync_exif_date}")
        try:
            self.progress_update.emit("Starting rename operation...")
            
            # Use optimized rename function
            renamed_files, errors, timestamp_backup = self.optimized_rename_files()
            
            # OPTIMIZATION: Keep ExifTool instance alive for better performance
            # Only cleanup on app close, not after each operation
            # Cache is preserved between operations for maximum speed
            
            self.finished.emit(renamed_files, errors, timestamp_backup)
        except Exception as e:
            # OPTIMIZATION: Even on error, keep ExifTool instance alive
            # It will be cleaned up when app closes
            self.error.emit(str(e))
    
    def _create_continuous_counter_map(self) -> None:
        """
        Create continuous counter mapping for all files.
        
        Maps each file to a sequential counter number based on chronological order.
        File pairs (JPG+RAW) share the same counter number to maintain consistency.
        
        Sets:
            self._continuous_counter_map: Dict[str, int] mapping file paths to counter numbers
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
                    if self.exif_service:
                        d, _, _ = self.exif_service.get_selective_cached_exif_data(
                            first_file, self.exif_method, self.exiftool_path,
                            need_date=True, need_camera=False, need_lens=False
                        )
                    else:
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
            except Exception:
                # Ultimate fallback
                try:
                    mtime = os.path.getmtime(first_file)
                    dt = datetime.datetime.fromtimestamp(mtime)
                    file_date = dt.strftime('%Y%m%d')
                    date_group_pairs.append((file_date, group))
                except Exception:
                    pass
        # Step 4: Sort by date, then by original file order (using file modification time as fallback)
        def get_sort_key(date_group):
            date, group = date_group
            first_file = group[0]
            try:
                basename = os.path.basename(first_file)
                all_numbers = re.findall(r'(\d+)', basename)
                if all_numbers:
                    # Use the last number as tiebreaker (actual sequence number)
                    # instead of the first (often the year)
                    file_number = int(all_numbers[-1])
                    try:
                        mtime = os.path.getmtime(first_file)
                        return (date, mtime, file_number, first_file)
                    except Exception:
                        return (date, file_number, first_file)
                else:
                    try:
                        mtime = os.path.getmtime(first_file)
                        return (date, mtime, first_file)
                    except Exception:
                        return (date, 0, first_file)
            except Exception:
                return (date, 0, first_file)
        date_group_pairs.sort(key=get_sort_key)
        # Step 5: Assign continuous counter numbers to GROUPS
        counter = 1
        for date, group in date_group_pairs:
            for file in group:
                self._continuous_counter_map[file] = counter
            counter += 1
    
    def optimized_rename_files(self) -> Tuple[List[str], List[Tuple[str, str]], Dict[str, Any]]:
        """
        Main worker implementation - simplified with helper functions.
        
        Steps:
        1. Optional EXIF->filesystem timestamp sync
        2. Early exit for metadata-only mode (leave_names)
        3. Group RAW/JPG siblings
        4. Pre-extract EXIF data once (performance optimization)
        5. Sort files chronologically
        6. Process each file group with counter logic
        
        Returns:
            Tuple containing:
                - renamed_files: List of successfully renamed file paths
                - errors: List of (file_path, error_message) tuples
                - timestamp_backup: Dictionary of original timestamps for undo
        """
        self.progress_update.emit("Starting optimized batch processing...")

        # Prepare continuous counter map once if needed
        if self.use_date and self.continuous_counter:
            self._create_continuous_counter_map()

        # Clear cache for fresh processing
        if self.exif_service:
            self.exif_service.clear_cache()
        else:
            exif_processor.clear_global_exif_cache()

        # Report what EXIF fields are needed
        need_date = self.use_date
        need_camera = self.use_camera
        need_lens = self.use_lens
        needed_labels = [lbl for lbl, flag in [("date", need_date), ("camera", need_camera), ("lens", need_lens)] if flag]
        
        if needed_labels:
            self.progress_update.emit(f"Extracting only: {', '.join(needed_labels)}")
        else:
            self.progress_update.emit("No EXIF extraction needed - using file names only")

        # Step 1: Optional EXIF timestamp sync
        successes, sync_errors, timestamp_backup = self._sync_exif_timestamps()
        
        if self.leave_names:
            # Only syncing timestamps - early exit
            error_messages = [msg for _file, msg in sync_errors]
            return [], error_messages, timestamp_backup

        # Step 2: Group RAW/JPEG siblings
        file_groups = self._create_file_groups()
        self.progress_update.emit(f"Processing {len(file_groups)} file groups...")

        # Step 3: Pre-extract EXIF data (PERFORMANCE OPTIMIZATION)
        exif_cache = self._pre_extract_exif_cache(file_groups)

        # Step 4: Sort files chronologically
        self.progress_update.emit("Sorting files by capture time...")
        file_groups.sort(key=lambda g: self._get_exif_sort_key(g, exif_cache))
        self.progress_update.emit("Files sorted chronologically")

        # Step 5: Process each file group
        renamed_files = []
        errors = []
        date_counter = {}

        for idx, group in enumerate(file_groups):
            self.progress_update.emit(f"Processing group {idx+1}/{len(file_groups)}")
            
            group_renamed, group_errors = self._process_file_group(group, date_counter, exif_cache)
            renamed_files.extend(group_renamed)
            errors.extend(group_errors)

        return renamed_files, errors, timestamp_backup
    
    def generate_new_filename(self, file, camera_model, lens_model, exif_data, timestamp_backup):
        """
        Generate a new filename based on the selected metadata and custom order
        """
        # Initialize components
        components = {
            'camera': camera_model,
            'lens': lens_model,
            'date': None,
            'counter': None,
            'ext': os.path.splitext(file)[1],
            **self.selected_metadata
        }
        
        # Step 1: Date handling
        if self.use_date:
            date_component = components.get('date')
            if date_component is None:
                # Try to get date from EXIF data
                date_component = exif_data.get('DateTimeOriginal') or exif_data.get('CreateDate')
            
            if date_component:
                try:
                    # Parse the date using the specified format
                    dt = datetime.datetime.strptime(date_component, '%Y:%m:%d %H:%M:%S')
                    components['date'] = dt.strftime(self.date_format)
                except Exception as e:
                    components['date'] = None  # Parsing failed, fallback to None
        
        # Step 2: Continuous counter
        if self.continuous_counter:
            counter_number = self._continuous_counter_map.get(file)
            if counter_number is not None:
                components['counter'] = str(counter_number).zfill(4)  # Zero-pad to 4 digits
        
        # Step 3: Build the new filename using the custom order
        try:
            new_filename = self.separator.join(
                str(components[key]) for key in self.custom_order if key in components and components[key] is not None
            )
        except Exception as e:
            new_filename = os.path.basename(file)  # Fallback to original filename in case of error
        
        # Step 4: Final sanitization
        final_sanitized_name = sanitize_final_filename(new_filename)
        
        return final_sanitized_name + components['ext']  # Restore original extension
