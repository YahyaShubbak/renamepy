#!/usr/bin/env python3
"""
EXIF data extraction and handling for the RenameFiles application.
This module provides the exact same functionality as the original RenameFiles.py
"""
from __future__ import annotations

import os
import re
import subprocess
import glob
import shutil
from typing import TYPE_CHECKING

from .logger_util import get_logger
log = get_logger()

# EXIF processing imports - exact same as original
import importlib.util

# PyExifTool (pip install PyExifTool) is used through exif_service_new;
# here only its availability matters.
EXIFTOOL_AVAILABLE = importlib.util.find_spec("exiftool") is not None

# ---------------------------------------------------------------------------
# Module-level ExifService reference for backward-compatible delegate functions.
# Call set_default_exif_service() once during application startup.
# ---------------------------------------------------------------------------

if TYPE_CHECKING:
    from .exif_service_new import ExifService as _ExifServiceType

_default_exif_service: _ExifServiceType | None = None


def set_default_exif_service(service: _ExifServiceType) -> None:
    """Register the application's ExifService for backward-compatible functions.

    Must be called once during startup so that legacy delegate functions
    (``get_exiftool_metadata_shared``, ``cleanup_global_exiftool``, etc.)
    can route calls to the canonical ExifService instance.
    """
    global _default_exif_service
    _default_exif_service = service


# Windows FILETIME constants and structure (defined once at module level)
EPOCH_AS_FILETIME = 116444736000000000  # January 1, 1970 as Windows FILETIME
HUNDREDS_OF_NANOSECONDS = 10000000

if os.name == 'nt':
    import ctypes
    from ctypes import wintypes

    class FILETIME(ctypes.Structure):
        """Windows FILETIME structure for file timestamp operations."""
        _fields_ = [("dwLowDateTime", wintypes.DWORD),
                     ("dwHighDateTime", wintypes.DWORD)]

    # A private kernel32 handle with explicit prototypes. Without restype,
    # ctypes returns CreateFileW's HANDLE as a 32-bit int, so a failure (-1)
    # never compared equal to INVALID_HANDLE_VALUE and was silently used as
    # a handle. A private WinDLL instance avoids changing the prototypes
    # other libraries see through ctypes.windll.kernel32.
    _kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    _kernel32.CreateFileW.restype = wintypes.HANDLE
    _kernel32.CreateFileW.argtypes = [
        wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
        wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE,
    ]
    _PFILETIME = ctypes.POINTER(FILETIME)
    _kernel32.GetFileTime.restype = wintypes.BOOL
    _kernel32.GetFileTime.argtypes = [wintypes.HANDLE, _PFILETIME, _PFILETIME, _PFILETIME]
    _kernel32.SetFileTime.restype = wintypes.BOOL
    _kernel32.SetFileTime.argtypes = [wintypes.HANDLE, _PFILETIME, _PFILETIME, _PFILETIME]
    _kernel32.CloseHandle.restype = wintypes.BOOL
    _kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    INVALID_HANDLE_VALUE = wintypes.HANDLE(-1).value

    _GENERIC_READ = 0x80000000
    _FILE_WRITE_ATTRIBUTES = 0x0100
    _FILE_SHARE_READ_WRITE = 0x00000001 | 0x00000002
    _OPEN_EXISTING = 3
    _FILE_ATTRIBUTE_NORMAL = 0x80

    def _open_file_handle(file_path, access):
        handle = _kernel32.CreateFileW(
            file_path, access, _FILE_SHARE_READ_WRITE, None,
            _OPEN_EXISTING, _FILE_ATTRIBUTE_NORMAL, None,
        )
        if handle is None or handle == INVALID_HANDLE_VALUE:
            return None
        return handle

    def _timestamp_to_filetime(timestamp):
        value = int((timestamp * HUNDREDS_OF_NANOSECONDS) + EPOCH_AS_FILETIME)
        ft = FILETIME()
        ft.dwLowDateTime = value & 0xFFFFFFFF
        ft.dwHighDateTime = value >> 32
        return ft


# ---------------------------------------------------------------------------
# Thin delegates — route to the registered ExifService instance.
#
# These exist so that modules which import from exif_processor (handlers,
# dialogs, file_list_manager, tests) continue to
# work without changing their import statements.
# ---------------------------------------------------------------------------

def get_exiftool_metadata_shared(image_path: str, exiftool_path: str | None = None) -> dict:
    """Read raw EXIF metadata via the shared ExifService.

    Falls back to a one-shot ExifTool subprocess if no service is registered
    (e.g. during early startup or standalone testing).
    """
    if _default_exif_service:
        return _default_exif_service.extract_raw_exif(image_path)
    # Fallback: one-shot subprocess (slower but always works)
    try:
        normalized = os.path.normpath(image_path)
        if not os.path.exists(normalized):
            return {}
        if not exiftool_path:
            exiftool_path = find_exiftool_path()
        from .exif_service_new import new_exiftool_helper
        with new_exiftool_helper(exiftool_path) as et:
            return et.get_metadata([normalized])[0]
    except Exception as e:
        log.warning(f"get_exiftool_metadata_shared fallback failed: {e}")
        return {}


def get_exiftool_metadata_batch(file_paths: list[str], exiftool_path: str | None = None) -> dict:
    """Read raw metadata of many files ({path: metadata}, {} for unreadable ones).

    Uses the shared ExifService (one IPC call per chunk) or, if none is
    registered, a one-shot ExifTool process.
    """
    if not file_paths:
        return {}
    if _default_exif_service:
        return _default_exif_service.batch_get_raw_metadata(list(file_paths))
    from .exif_service_new import new_exiftool_helper
    results = {path: {} for path in file_paths}
    existing = [p for p in file_paths if os.path.exists(p)]
    by_norm = {os.path.normpath(p): p for p in existing}
    try:
        if not exiftool_path:
            exiftool_path = find_exiftool_path()
        with new_exiftool_helper(exiftool_path) as et:
            for start in range(0, len(existing), 50):
                try:
                    metas = et.get_metadata(existing[start:start + 50])
                except Exception as e:
                    log.warning(f"Batch metadata read failed: {e}")
                    continue
                for meta in metas:
                    path = by_norm.get(os.path.normpath(str(meta.get('SourceFile', ''))))
                    if path:
                        results[path] = meta
    except Exception as e:
        log.warning(f"get_exiftool_metadata_batch failed: {e}")
    return results


def cleanup_global_exiftool() -> None:
    """Clean up the ExifService's ExifTool process."""
    if _default_exif_service:
        _default_exif_service.cleanup()

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
            # Generous timeout: the first start of exiftool.exe on Windows
            # (Perl runtime unpacking, virus scanner) can take several seconds.
            proc = subprocess.run(
                [executable_path, "-ver"],
                capture_output=True, text=True, timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
            )
            if proc.returncode == 0 and proc.stdout:
                ver = proc.stdout.strip().splitlines()[0].strip()
                log.debug(f"verify_exiftool: found version {ver} at {executable_path}")
                return ver
            return None
        except Exception as e:
            log.debug(f"verify_exiftool failed for {executable_path}: {e}")
            return None

    def _auto_rename_exiftool_k(directory: str) -> str | None:
        """Rename exiftool(-k).exe to exiftool.exe if needed.

        The Windows distribution ships as ``exiftool(-k).exe`` which causes
        the process to pause for a keypress after every invocation — unusable
        for programmatic access.  If only the ``(-k)`` variant exists in
        *directory*, rename it to ``exiftool.exe`` so the application can
        use it normally.

        Returns:
            Path to ``exiftool.exe`` after a successful rename, or *None*
            if no rename was performed.
        """
        k_exe = os.path.join(directory, "exiftool(-k).exe")
        target = os.path.join(directory, "exiftool.exe")
        if os.path.exists(k_exe) and not os.path.exists(target):
            try:
                os.rename(k_exe, target)
                log.info(
                    "Automatically renamed exiftool(-k).exe → exiftool.exe "
                    f"in {directory}"
                )
                return target
            except OSError as exc:
                log.warning(
                    f"Could not rename exiftool(-k).exe → exiftool.exe: {exc}"
                )
        return None

    # 1) Search for project-local exiftool folders with flexible names (exiftool-*)
    for d in glob.glob(os.path.join(script_dir, "exiftool*")):
        if os.path.isdir(d):
            # Auto-rename exiftool(-k).exe → exiftool.exe (Windows ZIP default)
            _auto_rename_exiftool_k(d)

            for fname in ("exiftool.exe", "exiftool"):
                candidate = os.path.join(d, fname)
                if os.path.exists(candidate):
                    if verify_exiftool(candidate):
                        log.debug(f"ExifTool located at: {candidate}")
                        return candidate

    # 2) Check a few legacy project paths explicitly (backwards compatibility)
    legacy_paths = [
        os.path.join(script_dir, "exiftool-13.33_64", "exiftool.exe"),
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

    # 4) Common Windows locations (only checked on Windows)
    if os.name == 'nt':
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

def _parse_target_datetime(value):
    """Accept a datetime or an EXIF date string; return a datetime or None."""
    import datetime as _dt
    if isinstance(value, _dt.datetime):
        return value
    from .exif_service_new import parse_exif_datetime
    return parse_exif_datetime(value)


def _read_capture_datetime(file_path, exiftool_path):
    """Read the capture date/time of one file via the shared ExifTool process."""
    from .exif_service_new import ExifService
    meta = get_exiftool_metadata_shared(file_path, exiftool_path)
    return ExifService.parse_datetime_from_raw(meta)


def _capture_original_times(file_path):
    """Snapshot the filesystem timestamps of *file_path* for undo."""
    stat_info = os.stat(file_path)
    original_times = {
        'atime': stat_info.st_atime,    # Access time
        'mtime': stat_info.st_mtime,    # Modification time
        'ctime': getattr(stat_info, 'st_birthtime', stat_info.st_ctime),  # Creation time (macOS/Windows) or status change time (Linux)
    }

    # On Windows, get the real creation time using Windows API
    if os.name == 'nt':
        try:
            handle = _open_file_handle(file_path, _GENERIC_READ)
            if handle is not None:
                try:
                    creation_time = FILETIME()
                    access_time = FILETIME()
                    write_time = FILETIME()
                    if _kernel32.GetFileTime(handle, ctypes.byref(creation_time),
                                             ctypes.byref(access_time), ctypes.byref(write_time)):
                        creation_100ns = (creation_time.dwHighDateTime << 32) + creation_time.dwLowDateTime
                        original_times['windows_creation_time'] = (
                            (creation_100ns - EPOCH_AS_FILETIME) / HUNDREDS_OF_NANOSECONDS
                        )
                finally:
                    _kernel32.CloseHandle(handle)
        except Exception as e:
            # If Windows API fails, we still have the basic timestamps
            log.debug(f"Could not get Windows creation time: {e}")
    return original_times


def _set_windows_file_times(file_path, creation=None, access=None, write=None):
    """Set Windows file times (each argument a POSIX timestamp or None)."""
    handle = _open_file_handle(file_path, _FILE_WRITE_ATTRIBUTES)
    if handle is None:
        return False
    try:
        c = _timestamp_to_filetime(creation) if creation is not None else None
        a = _timestamp_to_filetime(access) if access is not None else None
        w = _timestamp_to_filetime(write) if write is not None else None
        return bool(_kernel32.SetFileTime(
            handle,
            ctypes.byref(c) if c is not None else None,
            ctypes.byref(a) if a is not None else None,
            ctypes.byref(w) if w is not None else None,
        ))
    finally:
        _kernel32.CloseHandle(handle)


def sync_exif_date_to_file_date(file_path, exiftool_path=None, backup_timestamps=None, options=None, preexif_dt=None):
    """
    Synchronize EXIF DateTimeOriginal to file creation/modification date.
    
    Args:
        file_path: Path to the media file
        exiftool_path: Path to ExifTool executable
        backup_timestamps: Dictionary to store original timestamps for undo.
            An existing entry for *file_path* is never replaced, so repeated
            syncs keep the backup of the file's original timestamps.
        options: Dict from TimestampSyncOptionsDialog (which fields, custom date)
        preexif_dt: Pre-fetched capture date (datetime or EXIF date string)
        
    Returns:
        tuple: (success: bool, message: str, original_times: dict or None)
    """
    use_custom = bool(options and options.get('use_custom') and options.get('custom_dt'))
    if not EXIFTOOL_AVAILABLE and not use_custom and preexif_dt is None:
        # Allow custom date OR externally provided EXIF datetime without local ExifTool
        return False, "ExifTool not available", None
    
    if not os.path.exists(file_path):
        return False, f"File not found: {file_path}", None
    
    # Auto-detect ExifTool path if not provided
    if not exiftool_path and not use_custom and preexif_dt is None:
        exiftool_path = find_exiftool_path()
        if not exiftool_path:
            return False, "ExifTool executable not found", None
    
    try:
        original_times = _capture_original_times(file_path)
        
        # Store in backup if provided (before anything is modified)
        if backup_timestamps is not None and file_path not in backup_timestamps:
            backup_timestamps[file_path] = original_times
        
        # Determine target datetime
        if use_custom:
            dt = options['custom_dt']
        elif preexif_dt is not None:
            dt = _parse_target_datetime(preexif_dt)
            if dt is None:
                return False, "Invalid pre-extracted EXIF date", original_times
        else:
            try:
                dt = _read_capture_datetime(file_path, exiftool_path)
            except Exception as e:
                return False, f"Error accessing EXIF data: {e}", original_times
            if dt is None:
                return False, "No EXIF date found in file", original_times

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
            # Creation time can only be set on Windows
            creation_set = False
            if set_creation and os.name == 'nt':
                try:
                    creation_set = _set_windows_file_times(
                        file_path,
                        creation=new_timestamp,
                        access=new_timestamp if set_access else None,
                        write=new_timestamp if set_mod else None,
                    )
                except Exception as e:
                    log.debug(f"Creation time set failed: {e}")
                if not creation_set:
                    log.debug(f"Could not set creation time for {file_path}")
            fields = f"{'C' if creation_set else ''}{'M' if set_mod else ''}{'A' if set_access else ''}"
            return True, f"Timestamps updated ({fields}) -> {dt.strftime('%Y-%m-%d %H:%M:%S')}", original_times
        except Exception as e:
            return False, f"Failed to set timestamps: {e}", original_times
                
    except Exception as e:
        return False, f"Error syncing date: {e}", None

def _restore_windows_creation_time(file_path, creation_timestamp):
    """Restore Windows creation time using Windows API."""
    try:
        return _set_windows_file_times(file_path, creation=creation_timestamp)
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
    from .backup_journal import PersistedBackupDict

    successes = []
    errors = []
    # PersistedBackupDict writes each entry to the on-disk undo journal the
    # instant it's captured - i.e. before sync_exif_date_to_file_date() below
    # performs the actual (destructive) timestamp write for that file. This
    # means a crash mid-batch never loses the backup for files already done.
    backup_data = PersistedBackupDict("timestamp_backup")

    # Fast path: prefetch all capture datetimes via the registered ExifService
    # (reuses the shared ExifTool process) or fall back to a one-shot helper.
    from .exif_service_new import ExifService, new_exiftool_helper

    prefetch_map = {}
    use_custom = options and options.get('use_custom')
    can_prefetch = EXIFTOOL_AVAILABLE and not use_custom and file_paths
    if can_prefetch:
        try:
            if _default_exif_service:
                # Reuse the shared ExifService — no extra process needed
                raw_batch = _default_exif_service.batch_get_raw_metadata(file_paths, chunk_size=100)
            else:
                # Fallback: one-shot ExifTool helper (slower)
                raw_batch = {}
                by_norm = {os.path.normpath(p): p for p in file_paths}
                with new_exiftool_helper(exiftool_path) as et:
                    CHUNK = 100
                    for start in range(0, len(file_paths), CHUNK):
                        for meta in et.get_metadata(file_paths[start:start + CHUNK]):
                            source = meta.get('SourceFile')
                            if source:
                                raw_batch[by_norm.get(os.path.normpath(source), source)] = meta
            for fpath, meta in raw_batch.items():
                dt_value = ExifService.parse_datetime_from_raw(meta)
                if dt_value is not None:
                    prefetch_map[fpath] = dt_value
            if progress_callback:
                progress_callback(f"Prefetched EXIF datetimes for {len(prefetch_map)} files")
        except Exception as e:
            if progress_callback:
                progress_callback(f"Prefetch failed, falling back: {e}")
            prefetch_map = {}

    # Back up a whole chunk with one journal write before modifying any file
    # of it (one write per file would make large batches quadratic).
    SYNC_CHUNK = 200
    for start in range(0, len(file_paths), SYNC_CHUNK):
        chunk = file_paths[start:start + SYNC_CHUNK]
        originals = {}
        for file_path in chunk:
            if file_path in backup_data or not os.path.exists(file_path):
                continue
            try:
                originals[file_path] = _capture_original_times(file_path)
            except OSError as e:
                log.debug(f"Could not read timestamps of {file_path}: {e}")
        backup_data.record_originals(originals)

        for i, file_path in enumerate(chunk, start=start):
            if progress_callback:
                progress_callback(f"Processing {i+1}/{len(file_paths)}: {os.path.basename(file_path)}")
            if file_path not in backup_data and os.path.exists(file_path):
                errors.append((file_path, "Could not back up the original timestamps - skipped"))
                continue

            pre_dt = prefetch_map.get(file_path)
            success, message, _original_times = sync_exif_date_to_file_date(
                file_path, exiftool_path, None, options=options, preexif_dt=pre_dt
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


# Date tags that the EXIF time shift backs up (see TimeShiftWorker) and that
# restore_exif_timestamps() is therefore allowed to write back.
RESTORABLE_DATE_TAGS = frozenset({
    'EXIF:DateTimeOriginal',
    'EXIF:CreateDate',
    'EXIF:ModifyDate',
    'QuickTime:CreateDate',
    'QuickTime:ModifyDate',
    'QuickTime:TrackCreateDate',
    'QuickTime:TrackModifyDate',
    'QuickTime:MediaCreateDate',
    'QuickTime:MediaModifyDate',
})

_EXIF_VALUE_RE = re.compile(r'^[\w\s:./+\-]+$')


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
    try:
        if not os.path.exists(file_path):
            return False, f"File not found: {file_path}"
        
        if not original_exif:
            return False, "No backup EXIF data available"
        
        if not exiftool_path:
            exiftool_path = find_exiftool_path()
            if not exiftool_path:
                return False, "ExifTool executable not found"
        
        from .exif_service_new import run_exiftool_on_file

        # Add each backed-up field. The backup comes from a JSON file on
        # disk, so both the tag name (it becomes "-TAG=...", i.e. an ExifTool
        # option) and the value are validated before use.
        options = ["-overwrite_original"]
        for field, value in original_exif.items():
            if field not in RESTORABLE_DATE_TAGS:
                log.warning(f"Skipping unexpected EXIF restore field: {field!r}")
                continue
            str_value = str(value)
            if not _EXIF_VALUE_RE.match(str_value):
                log.warning(f"Skipping suspicious EXIF restore value for {field}: {str_value!r}")
                continue
            options.append(f'-{field}={str_value}')

        if len(options) == 1:
            return False, "No restorable EXIF fields in backup"

        result = run_exiftool_on_file(exiftool_path, options, file_path, timeout=60)
        
        if result.returncode == 0:
            return True, "EXIF timestamps restored successfully"
        else:
            return False, f"ExifTool error: {result.stderr.strip()}"
        
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

