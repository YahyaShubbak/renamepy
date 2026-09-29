#!/usr/bin/env python3
"""
EXIF Undo Manager - Persistent undo functionality via file metadata.

Stores each file's original filename inside the file itself, enabling undo
operations even after closing the application.

The name is written to ``XMP-xmpMM:PreservedFileName`` - the standard XMP
tag for exactly this purpose (Adobe Lightroom/Bridge use it too). It is only
created if it doesn't exist yet, so renaming a file a second time keeps the
name it had *before the first* rename, and the user's own EXIF comments are
never touched.

Older versions of this application stored the name in ``EXIF:UserComment``
as ``"OriginalName: <filename> | RenameDate: <timestamp>"``; that format is
still read for backward compatibility.
"""
from __future__ import annotations

import os
import json
import tempfile
import subprocess
from typing import Optional, Tuple, List
from .logger_util import get_logger

log = get_logger()

# Tag the original filename is stored in
PRESERVED_FILENAME_TAG = "XMP-xmpMM:PreservedFileName"

# Legacy format (read-only)
EXIF_USER_COMMENT_FIELD = "EXIF:UserComment"
ORIGINAL_NAME_PREFIX = "OriginalName: "
RENAME_DATE_PREFIX = " | RenameDate: "

# UTF-8 file names on every platform (see exif_service_new.EXIFTOOL_CHARSET_ARGS)
_CHARSET_ARGS = ["-charset", "filename=utf8"]

# Files per ExifTool invocation. File names go through an argument file,
# so this only bounds the work per subprocess, not the command-line length.
CHUNK_SIZE = 200


def _run_exiftool(cmd: List[str], timeout: int) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        timeout=timeout,
    )


def _write_argfile(lines: List[str]) -> str:
    """Write ExifTool arguments (one per line, UTF-8) to a temporary file.

    Passing file names via ``-@ ARGFILE`` avoids the Windows command-line
    length limit (~32k characters) for large batches.
    """
    fd, path = tempfile.mkstemp(prefix="renamepy_", suffix=".args")
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines))
        f.write("\n")
    return path


def _parse_legacy_user_comment(comment) -> Tuple[Optional[str], Optional[str]]:
    """Parse ``"OriginalName: <name> | RenameDate: <date>"``."""
    if not comment:
        return None, None
    comment = str(comment)
    if ORIGINAL_NAME_PREFIX not in comment:
        return None, None
    rest = comment.split(ORIGINAL_NAME_PREFIX, 1)[1]
    rename_date = None
    marker = RENAME_DATE_PREFIX.strip()
    if marker in rest:
        rest, rename_date = rest.split(marker, 1)
        rename_date = rename_date.strip() or None
    name = rest.strip()
    return (name or None), rename_date


def _read_rename_info(file_paths: List[str], exiftool_path: str) -> dict:
    """Read the stored original name (and legacy rename date) of many files.

    Returns:
        ``{path: {"original_filename": str|None, "rename_date": str|None,
        "legacy_marker": bool}}`` for every path in *file_paths*;
        ``legacy_marker`` tells whether EXIF:UserComment holds this
        application's old-format marker.
    """
    empty = {"original_filename": None, "rename_date": None, "legacy_marker": False}
    result = {path: dict(empty) for path in file_paths}

    if not exiftool_path or not os.path.exists(exiftool_path):
        log.warning("ExifTool executable not found")
        return result

    valid_files = [f for f in file_paths if os.path.exists(f)]
    if not valid_files:
        return result
    by_norm = {os.path.normpath(p): p for p in valid_files}

    for start in range(0, len(valid_files), CHUNK_SIZE):
        chunk = valid_files[start:start + CHUNK_SIZE]
        argfile = _write_argfile(chunk)
        try:
            cmd = [
                exiftool_path, "-json", *_CHARSET_ARGS,
                f"-{PRESERVED_FILENAME_TAG}", f"-{EXIF_USER_COMMENT_FIELD}",
                "-@", argfile,
            ]
            proc = _run_exiftool(cmd, timeout=120)
            # ExifTool exits with 1 if *any* file could not be read, but still
            # prints JSON for all the others - so parse stdout regardless.
            if not proc.stdout.strip():
                if proc.returncode != 0:
                    log.warning(f"ExifTool failed to read metadata: {proc.stderr.strip()}")
                continue
            try:
                entries = json.loads(proc.stdout)
            except json.JSONDecodeError as e:
                log.error(f"Failed to parse ExifTool JSON output: {e}")
                continue
            for entry in entries:
                path = by_norm.get(os.path.normpath(str(entry.get("SourceFile", ""))))
                if not path:
                    continue
                preserved = entry.get("PreservedFileName")
                legacy_name, legacy_date = _parse_legacy_user_comment(entry.get("UserComment"))
                if preserved:
                    result[path] = {"original_filename": str(preserved).strip() or None,
                                    "rename_date": None,
                                    "legacy_marker": bool(legacy_name)}
                elif legacy_name:
                    result[path] = {"original_filename": legacy_name,
                                    "rename_date": legacy_date,
                                    "legacy_marker": True}
        except subprocess.TimeoutExpired:
            log.error("ExifTool read operation timed out")
        except Exception as e:
            log.error(f"Error reading original filenames from metadata: {e}")
        finally:
            try:
                os.remove(argfile)
            except OSError:
                pass

    return result


def write_original_filename_to_exif(
    file_path: str,
    original_filename: str,
    exiftool_path: str,
    add_timestamp: bool = True
) -> Tuple[bool, str]:
    """
    Store the original filename in the file's metadata using ExifTool.

    The tag is only created if absent, so an older original name is kept.

    Args:
        file_path: Path to the file to update
        original_filename: Original filename (basename only, without path)
        exiftool_path: Path to ExifTool executable
        add_timestamp: Ignored; kept for backward compatibility (the legacy
            UserComment format carried a rename date).

    Returns:
        Tuple of (success: bool, message: str)
    """
    successes, errors = batch_write_original_filenames(
        [(file_path, original_filename)], exiftool_path
    )
    if successes:
        return True, "Original filename written to metadata"
    return False, errors[0][1] if errors else "Unknown error"


def get_original_filename_from_exif(
    file_path: str,
    exiftool_path: str
) -> Optional[str]:
    """
    Read the stored original filename of one file.

    Args:
        file_path: Path to the file to read
        exiftool_path: Path to ExifTool executable

    Returns:
        Original filename (basename) if found, None otherwise
    """
    if not os.path.exists(file_path):
        log.warning(f"File not found: {file_path}")
        return None
    return _read_rename_info([file_path], exiftool_path)[file_path]["original_filename"]


def batch_write_original_filenames(
    files: List[Tuple[str, str]],
    exiftool_path: str,
    progress_callback=None
) -> Tuple[List[str], List[Tuple[str, str]]]:
    """
    Store original filenames for many files.

    ExifTool applies every ``-TAG=VALUE`` of one command to *all* files of
    that command, so per-file values need one ``-execute`` block per file.
    The blocks go into an argument file and run in a single ExifTool
    process per chunk. Afterwards the tag is read back to confirm each file.

    Args:
        files: List of (file_path, original_filename) tuples
        exiftool_path: Path to ExifTool executable
        progress_callback: Optional callback function(current, total, message)

    Returns:
        Tuple of (successes: List[str], errors: List[Tuple[str, str]])
    """
    if not files:
        return [], []

    if not exiftool_path or not os.path.exists(exiftool_path):
        return [], [(f, "ExifTool executable not found") for f, _ in files]

    successes: List[str] = []
    errors: List[Tuple[str, str]] = []

    existing = []
    for file_path, original_filename in files:
        if os.path.exists(file_path):
            existing.append((file_path, original_filename))
        else:
            errors.append((file_path, f"File not found: {file_path}"))

    for chunk_start in range(0, len(existing), CHUNK_SIZE):
        chunk = existing[chunk_start:chunk_start + CHUNK_SIZE]
        lines: List[str] = []
        for i, (file_path, original_filename) in enumerate(chunk):
            if i:
                lines.append("-execute")
            # "-TAG-=" + "-TAG=VALUE": create the tag only if it doesn't exist.
            lines.append(f"-{PRESERVED_FILENAME_TAG}-=")
            lines.append(f"-{PRESERVED_FILENAME_TAG}={original_filename}")
            lines.append(file_path)

        if progress_callback:
            progress_callback(
                min(chunk_start + CHUNK_SIZE, len(existing)),
                len(existing),
                f"Batch {chunk_start // CHUNK_SIZE + 1}"
            )

        argfile = _write_argfile(lines)
        stderr = ""
        try:
            cmd = [exiftool_path, "-@", argfile,
                   "-common_args", "-overwrite_original", *_CHARSET_ARGS]
            proc = _run_exiftool(cmd, timeout=max(60, 2 * len(chunk)))
            stderr = proc.stderr.strip()
            if proc.returncode != 0:
                log.warning(f"ExifTool reported errors while writing original filenames: {stderr}")
        except subprocess.TimeoutExpired:
            stderr = "ExifTool operation timed out"
            log.error(stderr)
        except Exception as e:
            stderr = str(e)
            log.error(f"Batch metadata write error: {e}")
        finally:
            try:
                os.remove(argfile)
            except OSError:
                pass

        # Confirm per file: the tag must now be present (either our value or
        # an older original name that was deliberately kept).
        written = _read_rename_info([p for p, _ in chunk], exiftool_path)
        for file_path, _ in chunk:
            if written[file_path]["original_filename"]:
                successes.append(file_path)
            else:
                errors.append((file_path, f"Original filename not stored: {stderr or 'unsupported file type'}"))

    return successes, errors


def batch_get_original_filenames(
    file_paths: List[str],
    exiftool_path: str
) -> dict[str, Optional[str]]:
    """
    Read original filenames from multiple files in one ExifTool call per chunk.

    Args:
        file_paths: List of file paths to read
        exiftool_path: Path to ExifTool executable

    Returns:
        Dictionary mapping file_path -> original_filename (or None if not found)
    """
    info = _read_rename_info(list(file_paths), exiftool_path)
    return {path: info[path]["original_filename"] for path in file_paths}


def clear_original_filename_from_exif(
    file_path: str,
    exiftool_path: str
) -> Tuple[bool, str]:
    """
    Remove the stored original filename from the file's metadata.

    Deletes the XMP tag; a legacy ``EXIF:UserComment`` is only cleared if it
    holds this application's marker, never a user's own comment.

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

        cmd = [exiftool_path, "-overwrite_original", *_CHARSET_ARGS,
               f"-{PRESERVED_FILENAME_TAG}="]
        if _read_rename_info([file_path], exiftool_path)[file_path]["legacy_marker"]:
            cmd.append(f"-{EXIF_USER_COMMENT_FIELD}=")
        cmd.append(file_path)

        result = _run_exiftool(cmd, timeout=30)

        if result.returncode == 0:
            log.debug(f"Cleared original filename from metadata: {file_path}")
            return True, "Original filename cleared from metadata"
        else:
            error_msg = result.stderr.strip() or result.stdout.strip()
            return False, f"ExifTool error: {error_msg}"

    except Exception as e:
        error_msg = f"Error clearing original filename from metadata: {e}"
        log.error(error_msg)
        return False, error_msg


def has_original_filename(file_path: str, exiftool_path: str) -> bool:
    """
    Quick check if file has original filename in its metadata.

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
    Get all rename-related information from the file's metadata.

    Args:
        file_path: Path to the file
        exiftool_path: Path to ExifTool executable

    Returns:
        Dictionary with 'original_filename' and 'rename_date' keys
        (the rename date is only known for the legacy UserComment format)
    """
    if not os.path.exists(file_path) or not exiftool_path:
        return {'original_filename': None, 'rename_date': None}
    info = _read_rename_info([file_path], exiftool_path)[file_path]
    return {'original_filename': info['original_filename'], 'rename_date': info['rename_date']}
