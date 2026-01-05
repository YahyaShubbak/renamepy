#!/usr/bin/env python3
"""
EXIF Undo Manager - Persistent undo functionality via EXIF metadata.

This module provides functionality to store original filenames in EXIF metadata,
enabling undo operations even after closing the application. Uses standard EXIF
UserComment field to store the original filename in a simple format.

Format: "OriginalName: <filename> | RenameDate: <timestamp>"
Example: "OriginalName: _DSC8166.ARW | RenameDate: 2026:01:04 22:00:00"
"""

import os
import subprocess
from typing import Optional, Tuple, List
from .logger_util import get_logger

log = get_logger()

# EXIF field for storing original filename (using standard UserComment field)
EXIF_USER_COMMENT_FIELD = "EXIF:UserComment"
ORIGINAL_NAME_PREFIX = "OriginalName: "
RENAME_DATE_PREFIX = " | RenameDate: "


def write_original_filename_to_exif(
    file_path: str,
    original_filename: str,
    exiftool_path: str,
    add_timestamp: bool = True
) -> Tuple[bool, str]:
    """
    Write original filename to EXIF UserComment field using ExifTool.
    
    Stores data in format: "OriginalName: <filename> | RenameDate: <timestamp>"
    
    Args:
        file_path: Path to the file to update
        original_filename: Original filename (basename only, without path)
        exiftool_path: Path to ExifTool executable
        add_timestamp: Whether to also add a rename timestamp
        
    Returns:
        Tuple of (success: bool, message: str)
        
    Raises:
        FileNotFoundError: If ExifTool executable not found
    """
    try:
        # Validate inputs
        if not os.path.exists(file_path):
            return False, f"File not found: {file_path}"
        
        if not exiftool_path or not os.path.exists(exiftool_path):
            return False, "ExifTool executable not found"
        
        # Build the UserComment value
        user_comment = f"{ORIGINAL_NAME_PREFIX}{original_filename}"
        
        if add_timestamp:
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y:%m:%d %H:%M:%S")
            user_comment += f"{RENAME_DATE_PREFIX}{timestamp}"
        
        # Build ExifTool command
        cmd = [
            exiftool_path,
            "-overwrite_original",  # Don't create backup files
            f"-{EXIF_USER_COMMENT_FIELD}={user_comment}",
            file_path
        ]
        
        # Execute ExifTool
        log.debug(f"Writing original filename to EXIF: {original_filename} -> {file_path}")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
            timeout=30
        )
        
        if result.returncode == 0:
            log.debug(f"Successfully wrote original filename to EXIF: {file_path}")
            return True, "Original filename written to metadata"
        else:
            error_msg = result.stderr.strip() or result.stdout.strip()
            log.warning(f"ExifTool failed to write metadata: {error_msg}")
            return False, f"ExifTool error: {error_msg}"
            
    except subprocess.TimeoutExpired:
        error_msg = "ExifTool operation timed out"
        log.error(f"{error_msg}: {file_path}")
        return False, error_msg
    except Exception as e:
        error_msg = f"Error writing original filename to EXIF: {e}"
        log.error(error_msg)
        return False, error_msg


def get_original_filename_from_exif(
    file_path: str,
    exiftool_path: str
) -> Optional[str]:
    """
    Read original filename from EXIF UserComment field using ExifTool.
    
    Parses format: "OriginalName: <filename> | RenameDate: <timestamp>"
    
    Args:
        file_path: Path to the file to read
        exiftool_path: Path to ExifTool executable
        
    Returns:
        Original filename (basename) if found, None otherwise
    """
    try:
        # Validate inputs
        if not os.path.exists(file_path):
            log.warning(f"File not found: {file_path}")
            return None
        
        if not exiftool_path or not os.path.exists(exiftool_path):
            log.warning("ExifTool executable not found")
            return None
        
        # Build ExifTool command to read UserComment field
        cmd = [
            exiftool_path,
            "-s3",  # Short output format (value only, no field name)
            f"-{EXIF_USER_COMMENT_FIELD}",
            file_path
        ]
        
        # Execute ExifTool
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
            timeout=10
        )
        
        if result.returncode == 0:
            user_comment = result.stdout.strip()
            
            # Check if field exists and contains our marker
            if user_comment and ORIGINAL_NAME_PREFIX in user_comment:
                # Parse the original filename from the UserComment
                # Format: "OriginalName: <filename> | RenameDate: <timestamp>"
                original_filename = user_comment.split(ORIGINAL_NAME_PREFIX)[1]
                
                # Remove the rename date part if present
                if RENAME_DATE_PREFIX.strip() in original_filename:
                    original_filename = original_filename.split(RENAME_DATE_PREFIX.strip())[0]
                
                original_filename = original_filename.strip()
                
                if original_filename:
                    log.debug(f"Found original filename in EXIF: {original_filename}")
                    return original_filename
            else:
                log.debug(f"No original filename found in EXIF: {file_path}")
                return None
        else:
            log.warning(f"ExifTool failed to read metadata: {result.stderr}")
            return None
            
    except subprocess.TimeoutExpired:
        log.error(f"ExifTool read operation timed out: {file_path}")
        return None
    except Exception as e:
        log.error(f"Error reading original filename from EXIF: {e}")
        return None


def batch_write_original_filenames(
    files: List[Tuple[str, str]],
    exiftool_path: str,
    progress_callback=None
) -> Tuple[List[str], List[Tuple[str, str]]]:
    """
    Write original filenames to multiple files in batch.
    
    Args:
        files: List of (file_path, original_filename) tuples
        exiftool_path: Path to ExifTool executable
        progress_callback: Optional callback function(current, total, filename)
        
    Returns:
        Tuple of (successes: List[str], errors: List[Tuple[str, str]])
    """
    successes = []
    errors = []
    
    total = len(files)
    for idx, (file_path, original_filename) in enumerate(files):
        # Report progress
        if progress_callback:
            progress_callback(idx + 1, total, os.path.basename(file_path))
        
        # Write to EXIF
        success, message = write_original_filename_to_exif(
            file_path,
            original_filename,
            exiftool_path
        )
        
        if success:
            successes.append(file_path)
        else:
            errors.append((file_path, message))
    
    return successes, errors


def batch_get_original_filenames(
    file_paths: List[str],
    exiftool_path: str
) -> dict[str, Optional[str]]:
    """
    Read original filenames from multiple files efficiently.
    
    Uses a single ExifTool invocation for better performance.
    
    Args:
        file_paths: List of file paths to read
        exiftool_path: Path to ExifTool executable
        
    Returns:
        Dictionary mapping file_path -> original_filename (or None if not found)
    """
    result_map = {}
    
    try:
        if not exiftool_path or not os.path.exists(exiftool_path):
            log.warning("ExifTool executable not found")
            return {path: None for path in file_paths}
        
        # Filter out non-existent files
        valid_files = [f for f in file_paths if os.path.exists(f)]
        if not valid_files:
            return {path: None for path in file_paths}
        
        # Build ExifTool command for batch reading
        cmd = [
            exiftool_path,
            "-s3",  # Short output format
            "-n",   # No print conversion
            f"-{EXIF_USER_COMMENT_FIELD}",
            "-FileName",  # Also get current filename for mapping
        ] + valid_files
        
        # Execute ExifTool
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
            timeout=60
        )
        
        if result.returncode == 0:
            # Parse output (ExifTool returns one value per line for each file)
            lines = result.stdout.strip().split('\n')
            
            # Each file produces 2 lines: UserComment, FileName
            for i in range(0, len(lines), 2):
                if i + 1 < len(lines):
                    user_comment = lines[i].strip()
                    current = lines[i + 1].strip()
                    
                    # Parse original filename from UserComment
                    original = None
                    if user_comment and ORIGINAL_NAME_PREFIX in user_comment:
                        original = user_comment.split(ORIGINAL_NAME_PREFIX)[1]
                        if RENAME_DATE_PREFIX.strip() in original:
                            original = original.split(RENAME_DATE_PREFIX.strip())[0]
                        original = original.strip() if original else None
                    
                    # Find matching file path
                    matching_path = None
                    for path in valid_files:
                        if os.path.basename(path) == current:
                            matching_path = path
                            break
                    
                    if matching_path:
                        result_map[matching_path] = original if original else None
        
        # Fill in None for any files we couldn't process
        for path in file_paths:
            if path not in result_map:
                result_map[path] = None
                
    except Exception as e:
        log.error(f"Error in batch_get_original_filenames: {e}")
        result_map = {path: None for path in file_paths}
    
    return result_map


def clear_original_filename_from_exif(
    file_path: str,
    exiftool_path: str
) -> Tuple[bool, str]:
    """
    Clear/remove the original filename from EXIF metadata.
    
    Useful for cleaning up metadata or when exporting files.
    
    Args:
        file_path: Path to the file to update
        exiftool_path: Path to ExifTool executable
        
    Returns:
        Tuple of (success: bool, message: str)
    """
    try:
        if not os.path.exists(file_path):
            return False, f"File not found: {file_path}"
        
        if not exiftool_path or not os.path.exists(exiftool_path):
            return False, "ExifTool executable not found"
        
        # Build ExifTool command to delete field
        cmd = [
            exiftool_path,
            "-overwrite_original",
            f"-{EXIF_USER_COMMENT_FIELD}=",  # Empty value deletes the field
            file_path
        ]
        
        # Execute ExifTool
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
            timeout=30
        )
        
        if result.returncode == 0:
            log.debug(f"Cleared original filename from EXIF: {file_path}")
            return True, "Original filename cleared from metadata"
        else:
            error_msg = result.stderr.strip() or result.stdout.strip()
            return False, f"ExifTool error: {error_msg}"
            
    except Exception as e:
        error_msg = f"Error clearing original filename from EXIF: {e}"
        log.error(error_msg)
        return False, error_msg


# Removed _supports_xmp_metadata function - no longer needed with EXIF:UserComment


def has_original_filename(file_path: str, exiftool_path: str) -> bool:
    """
    Quick check if file has original filename in EXIF metadata.
    
    Args:
        file_path: Path to the file
        exiftool_path: Path to ExifTool executable
        
    Returns:
        True if original filename exists in metadata, False otherwise
    """
    original = get_original_filename_from_exif(file_path, exiftool_path)
    return original is not None and original != ""


def get_rename_info(file_path: str, exiftool_path: str) -> dict:
    """
    Get all rename-related information from EXIF metadata.
    
    Args:
        file_path: Path to the file
        exiftool_path: Path to ExifTool executable
        
    Returns:
        Dictionary with 'original_filename' and 'rename_date' keys
    """
    info = {
        'original_filename': None,
        'rename_date': None
    }
    
    try:
        if not os.path.exists(file_path) or not exiftool_path:
            return info
        
        # Build ExifTool command to read UserComment field
        cmd = [
            exiftool_path,
            "-s3",
            f"-{EXIF_USER_COMMENT_FIELD}",
            file_path
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
            timeout=10
        )
        
        if result.returncode == 0:
            user_comment = result.stdout.strip()
            
            # Parse UserComment format: "OriginalName: <filename> | RenameDate: <timestamp>"
            if user_comment and ORIGINAL_NAME_PREFIX in user_comment:
                # Extract original filename
                parts = user_comment.split(ORIGINAL_NAME_PREFIX)[1]
                
                # Check for rename date
                if RENAME_DATE_PREFIX.strip() in parts:
                    filename_part, date_part = parts.split(RENAME_DATE_PREFIX.strip(), 1)
                    info['original_filename'] = filename_part.strip()
                    info['rename_date'] = date_part.strip()
                else:
                    info['original_filename'] = parts.strip()
                
    except Exception as e:
        log.error(f"Error getting rename info: {e}")
    
    return info
