#!/usr/bin/env python3
"""
EXIF data extraction and handling for the RenameFiles application.
This module provides the exact same functionality as the original RenameFiles.py
"""
from __future__ import annotations

import os
import time
import subprocess
import glob
import shutil
from typing import TYPE_CHECKING

from .logger_util import get_logger
log = get_logger()

# EXIF processing imports - exact same as original
try:
    import exiftool #### pip install PyExifTool
    EXIFTOOL_AVAILABLE = True
except ImportError:
    EXIFTOOL_AVAILABLE = False

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


# ---------------------------------------------------------------------------
# Thin delegates — route to the registered ExifService instance.
#
# These exist so that modules which import from exif_processor (handlers,
# dialogs, file_list_manager, performance_benchmark, tests) continue to
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
        if exiftool_path and os.path.exists(exiftool_path):
            with exiftool.ExifToolHelper(executable=exiftool_path) as et:
                return et.get_metadata([normalized])[0]
        else:
            with exiftool.ExifToolHelper() as et:
                return et.get_metadata([normalized])[0]
    except Exception as e:
        log.warning(f"get_exiftool_metadata_shared fallback failed: {e}")
        return {}


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
                        creation_100ns = (creation_time.dwHighDateTime << 32) + creation_time.dwLowDateTime
                        creation_timestamp = (creation_100ns - EPOCH_AS_FILETIME) / HUNDREDS_OF_NANOSECONDS
                        
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
                    ts_100ns = int((new_timestamp * HUNDREDS_OF_NANOSECONDS) + EPOCH_AS_FILETIME)
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

def _set_file_timestamp_method3(file_path, dt):
    """Method 3: PowerShell for extra robustness.
    
    Uses parameterized script block to avoid command injection
    via file paths containing special characters.
    """
    try:
        if os.name != 'nt':  # Not Windows
            return False
            
        import subprocess
        
        # Format date for PowerShell (ISO 8601)
        ps_date = dt.strftime('%Y-%m-%dT%H:%M:%S')
        
        # SECURITY FIX: Use parameterized ScriptBlock via -File or
        # pass the path as an encoded argument to avoid injection.
        # The path and date are passed as separate arguments to
        # a script block, never interpolated into the script string.
        ps_script = (
            'param($FilePath, $DateStr); '
            '$file = Get-Item -LiteralPath $FilePath; '
            '$date = [DateTime]::Parse($DateStr); '
            '$file.CreationTime = $date; '
            '$file.LastWriteTime = $date; '
            '$file.LastAccessTime = $date; '
            'Write-Host "PowerShell timestamp sync completed"'
        )
        
        # Execute PowerShell command with path as a safe argument
        result = subprocess.run([
            'powershell', '-NoProfile', '-Command',
            '&{' + ps_script + '}',
            '-FilePath', str(file_path),
            '-DateStr', ps_date
        ], capture_output=True, text=True, timeout=15,
           encoding='utf-8', errors='replace')
        
        if result.returncode == 0:
            log.debug("Method 3 (PowerShell) successful")
            return True
        else:
            log.debug(f"Method 3 (PowerShell) failed: {result.stderr.strip()}")
            return False
    
    except Exception as e:
        log.debug(f"Method 3 (PowerShell) exception: {e}")
        return False

def _restore_windows_creation_time(file_path, creation_timestamp):
    """Restore Windows creation time using Windows API."""
    try:
        # Convert timestamp to Windows FILETIME format
        timestamp_100ns = int((creation_timestamp * HUNDREDS_OF_NANOSECONDS) + EPOCH_AS_FILETIME)
        
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

