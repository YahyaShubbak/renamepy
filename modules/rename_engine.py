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
    from .file_utilities import is_media_file, sanitize_final_filename, get_safe_target_path, validate_path_length
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

# Import exif_processor module (relative only to work inside package)
from . import exif_processor
from .filename_components import build_ordered_components

class RenameWorkerThread(QThread):
    """Worker thread for file renaming & optional EXIF timestamp sync."""
    progress_update = pyqtSignal(str)
    finished = pyqtSignal(list, list, dict)  # renamed_files, errors, timestamp_backup
    error = pyqtSignal(str)

    def __init__(
        self,
        files,
        camera_prefix,
        additional,
        use_camera,
        use_lens,
        exif_method,
        devider,
        exiftool_path,
        custom_order,
        date_format,
        use_date,
        continuous_counter,
        selected_metadata,
        sync_exif_date,
        parent=None,
        log_callable=None,
        **kwargs,
    ):
            super().__init__(parent)
            self.files = files
            self.camera_prefix = camera_prefix
            self.additional = additional
            self.use_camera = use_camera
            self.use_lens = use_lens
            self.exif_method = exif_method
            self.devider = devider
            self.exiftool_path = exiftool_path
            self.custom_order = custom_order or []
            self.date_format = date_format
            self.use_date = use_date
            self.continuous_counter = continuous_counter
            self.selected_metadata = selected_metadata or {}
            self.sync_exif_date = sync_exif_date
            self._log = log_callable or (lambda *a, **k: None)
            self.timestamp_options = kwargs.get('timestamp_options') or kwargs.get('timestamp_options'.lower()) or kwargs.get('TIMESTAMP_OPTIONS') or kwargs.get('timestamp_options'.upper()) or kwargs.get('timestamp_options', None)
            self.leave_names = kwargs.get('leave_names', False)
            # (Dry-run feature removed)

    def _debug(self, msg):
        try:
            self._log(msg)
        except Exception:
            pass
    
    def run(self):
        self._debug(f"Starting rename thread with {len(self.files)} files. Continuous={self.continuous_counter} SyncTS={self.sync_exif_date}")
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
                match = re.search(r'(\d+)', basename)
                if match:
                    file_number_str = match.group(1)
                    file_number = int(file_number_str)
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
    
    def optimized_rename_files(self):
        """Main worker implementation.

        1. Optional EXIF->filesystem timestamp sync (with selective fields / custom date)
        2. Early exit path when user chose metadata-only (leave_names)
        3. Fast grouping of RAW/JPG siblings
        4. Minimal EXIF extraction (only needed fields)
        """
        self.progress_update.emit("Starting optimized batch processing...")

        # Prepare continuous counter map once if needed
        if self.use_date and self.continuous_counter:
            self._create_continuous_counter_map()

        exif_processor.clear_global_exif_cache()

        need_date = self.use_date
        need_camera = self.use_camera
        need_lens = self.use_lens

        needed_labels = [lbl for lbl, flag in [("date", need_date), ("camera", need_camera), ("lens", need_lens)] if flag]
        if needed_labels:
            self.progress_update.emit(f"Extracting only: {', '.join(needed_labels)}")
        else:
            self.progress_update.emit("No EXIF extraction needed - using file names only")

        timestamp_backup = {}
        if self.sync_exif_date:
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
            if self.leave_names:
                # Only syncing timestamps; convert sync_errors to simple messages
                error_messages = [msg for _file, msg in sync_errors]
                return [], error_messages, timestamp_backup

        # Group RAW/JPEG siblings (same basename in same directory)
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

        self.progress_update.emit(f"Processing {len(file_groups)} file groups...")

        # When not ordering by date, provide deterministic ordering via earliest timestamp
        if not self.use_date:
            def earliest(group):
                try:
                    mtimes = [os.path.getmtime(p) for p in group]
                    return min(mtimes)
                except Exception:
                    return 0
            file_groups.sort(key=earliest)

        renamed_files = []
        errors = []
        date_counter = {}

        for idx, group in enumerate(file_groups):
            self.progress_update.emit(f"Processing group {idx+1}/{len(file_groups)}")
            group_existing = [p for p in group if os.path.exists(p)]
            if not group_existing:
                continue

            date_taken = None
            camera_model = None
            lens_model = None
            first_file = group_existing[0]

            if self.exif_method and any([need_date, need_camera, need_lens]):
                date_taken, camera_model, lens_model = exif_processor.get_selective_cached_exif_data(
                    first_file, self.exif_method, self.exiftool_path,
                    need_date=need_date, need_camera=need_camera, need_lens=need_lens
                )
                # Best-effort look through rest if anything missing
                if ((need_date and not date_taken) or (need_camera and not camera_model) or (need_lens and not lens_model)):
                    for other in group_existing[1:]:
                        still_date = need_date and not date_taken
                        still_cam = need_camera and not camera_model
                        still_lens = need_lens and not lens_model
                        if not any([still_date, still_cam, still_lens]):
                            break
                        d, c, l = exif_processor.get_selective_cached_exif_data(
                            other, self.exif_method, self.exiftool_path,
                            need_date=still_date, need_camera=still_cam, need_lens=still_lens
                        )
                        if still_date and d: date_taken = d
                        if still_cam and c: camera_model = c
                        if still_lens and l: lens_model = l

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
                camera_model = 'ILCE-7CM2'
            if need_lens and not lens_model:
                lens_model = 'FE-20-70mm-F4-G'

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
                    sep = '' if self.devider == 'None' else self.devider
                    new_name = sanitize_final_filename(sep.join(parts) + os.path.splitext(path)[1])
                    target = get_safe_target_path(path, new_name)
                    if not validate_path_length(target):
                        # Attempt shorten
                        directory = os.path.dirname(path)
                        base, ext = os.path.splitext(new_name)
                        max_len = 200 - len(directory)
                        if max_len > 10:
                            new_name = base[:max_len - len(ext)] + ext
                            target = os.path.join(directory, new_name)
                        else:
                            errors.append(f"Path too long: {path}")
                            continue
                    os.rename(path, target)
                    renamed_files.append(target)
                except Exception as e:
                    errors.append(f"Failed to rename {os.path.basename(path)}: {e}")

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
            new_filename = self.devider.join(
                str(components[key]) for key in self.custom_order if key in components and components[key] is not None
            )
        except Exception as e:
            new_filename = os.path.basename(file)  # Fallback to original filename in case of error
        
        # Step 4: Final sanitization
        final_sanitized_name = sanitize_final_filename(new_filename)
        
        return final_sanitized_name + components['ext']  # Restore original extension
