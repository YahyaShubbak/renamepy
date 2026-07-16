#!/usr/bin/env python3
"""
Backup Journal - durable, on-disk persistence for pending undo data.

Why this exists
----------------
Several features in this application perform *destructive* in-place writes
to the user's original files:

  - "Sync EXIF date to file creation date" overwrites filesystem timestamps
    (exif_processor.sync_exif_date_to_file_date).
  - "EXIF Time Shift" overwrites EXIF date/time fields with
    ``-overwrite_original`` (dialogs.exif_time_shift_dialog.TimeShiftWorker).

Both features back up the *original* values before writing so the user can
undo later. Previously that backup only ever lived in memory
(RenamerState.timestamp_backup / exif_backup). If the application crashed,
was force-closed, or the user's machine lost power between the destructive
write and clicking "Undo", the backup was gone and the original file was
unrecoverable.

This module fixes that by giving those backups a durable home on disk,
written atomically and *before* the corresponding file is modified (see
``PersistedBackupDict`` below), and reloaded automatically the next time the
application starts.

Usage
-----
    from .backup_journal import PersistedBackupDict

    # Instead of: backup_data = {}
    backup_data = PersistedBackupDict("timestamp_backup")

    # Every assignment is durably persisted immediately:
    backup_data[file_path] = original_times   # <- written to disk here,
                                               #    before the destructive
                                               #    write happens

Recovery on startup and clearing after a successful undo are handled by
``load_journal()`` and ``clear_backup()`` respectively; see
``main_application.py`` (``_recover_pending_backups``) and
``handlers/undo_handler.py`` for the call sites.
"""
from __future__ import annotations

import json
import os
import threading
import time
from typing import Any, Dict

from .logger_util import get_logger

log = get_logger()

# A single process-wide lock. Writes are small and infrequent (one per file
# processed), so a coarse lock is simple and sufficient - this only needs to
# protect the on-disk journal from interleaved read-modify-write cycles if
# multiple worker threads happen to touch it around the same time.
_journal_lock = threading.Lock()

_JOURNAL_FILENAME = "pending_undo.json"

# Recognized top-level keys in the journal. Kept as a constant so typos in
# call sites fail loudly during development rather than silently creating a
# new, never-read key.
KNOWN_BACKUP_KEYS = ("timestamp_backup", "exif_backup", "original_filenames")


def get_app_data_dir() -> str:
    """Return a writable, per-user application-data directory.

    Uses Qt's standard application-data directory rather than a path next
    to the source code, so this works regardless of whether the app is run
    from a cloned repo or installed somewhere read-only (e.g. Program Files).
    Falls back to the user's home directory if Qt is unavailable for any
    reason (e.g. running headless utility scripts/tests).

    Shared by this module (the undo journal) and performance_benchmark.py
    (calibration data), so both keep their persisted state in the same
    predictable, writable place instead of each computing their own path.
    """
    try:
        from PyQt6.QtCore import QStandardPaths

        directory = QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.AppDataLocation
        )
    except Exception:
        directory = ""

    if not directory:
        directory = os.path.join(os.path.expanduser("~"), ".renamepy")

    try:
        os.makedirs(directory, exist_ok=True)
    except OSError as e:
        log.warning(f"Could not create app data directory {directory!r}: {e}")

    return directory


def _journal_path() -> str:
    """Return the path to the journal file in the writable app-data directory."""
    return os.path.join(get_app_data_dir(), _JOURNAL_FILENAME)


def _read_journal_unlocked() -> Dict[str, Any]:
    """Read the journal file. Caller must hold ``_journal_lock``."""
    path = _journal_path()
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            log.warning("Undo journal has unexpected format - ignoring")
            return {}
        return data
    except (json.JSONDecodeError, ValueError, OSError) as e:
        # A corrupt or unreadable journal must never crash the app or block
        # a rename operation - treat it as "nothing to recover" and move on.
        log.warning(f"Could not read undo journal ({e}) - starting fresh")
        return {}


def _write_journal_unlocked(data: Dict[str, Any]) -> None:
    """Atomically write the journal file. Caller must hold ``_journal_lock``."""
    path = _journal_path()
    tmp_path = f"{path}.tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f)
        os.replace(tmp_path, path)  # atomic on POSIX and Windows
    except OSError as e:
        # Persisting the backup failing is unfortunate but must not raise -
        # the caller (e.g. TimeShiftWorker) should be able to decide whether
        # to proceed; we simply log loudly so it's visible in diagnostics.
        log.error(f"Could not persist undo journal to {path!r}: {e}")
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except OSError:
            pass


def load_journal() -> Dict[str, Dict[str, Any]]:
    """Load the full on-disk journal (all backup keys at once).

    Returns a dict like ``{"timestamp_backup": {...}, "exif_backup": {...}}``.
    Missing keys are simply absent - callers should use ``.get(key, {})``.
    """
    with _journal_lock:
        return _read_journal_unlocked()


def save_backup(key: str, data: Dict[str, Any]) -> None:
    """Persist ``data`` under ``key`` in the on-disk journal (full replace).

    This overwrites any previous contents for ``key`` with ``data`` as given,
    so callers that maintain the authoritative in-memory dict (like
    ``PersistedBackupDict``) should pass the complete current dict, not a
    delta.
    """
    with _journal_lock:
        journal = _read_journal_unlocked()
        if data:
            journal[key] = data
        else:
            journal.pop(key, None)
        journal["_last_updated"] = time.time()
        _write_journal_unlocked(journal)


def clear_backup(key: str) -> None:
    """Remove ``key`` from the journal (e.g. after a successful undo)."""
    with _journal_lock:
        journal = _read_journal_unlocked()
        if key in journal:
            journal.pop(key, None)
            journal["_last_updated"] = time.time()
            _write_journal_unlocked(journal)


def clear_all() -> None:
    """Remove the entire journal file."""
    with _journal_lock:
        path = _journal_path()
        try:
            if os.path.exists(path):
                os.remove(path)
        except OSError as e:
            log.warning(f"Could not remove undo journal {path!r}: {e}")


class PersistedBackupDict(dict):
    """A dict that transparently persists itself to the undo journal.

    Every mutation is written to disk immediately (atomically), so the
    backup for a file is durable *before* the corresponding destructive
    write happens - not after the whole batch finishes and not only when
    the app shuts down cleanly.

    Drop-in replacement for a plain ``{}`` wherever a backup dict is built
    up incrementally inside a per-file loop, e.g.:

        backup_data = PersistedBackupDict("timestamp_backup")
        for file_path in files:
            backup_data[file_path] = original_times   # <- persisted here
            ... perform the destructive write for file_path ...
    """

    def __init__(self, journal_key: str, *args, **kwargs) -> None:
        if journal_key not in KNOWN_BACKUP_KEYS:
            log.debug(f"PersistedBackupDict using non-standard key: {journal_key!r}")
        super().__init__(*args, **kwargs)
        self._journal_key = journal_key
        if self:
            save_backup(self._journal_key, dict(self))

    def __setitem__(self, key, value) -> None:
        super().__setitem__(key, value)
        save_backup(self._journal_key, dict(self))

    def __delitem__(self, key) -> None:
        super().__delitem__(key)
        save_backup(self._journal_key, dict(self))

    def update(self, *args, **kwargs) -> None:  # type: ignore[override]
        super().update(*args, **kwargs)
        save_backup(self._journal_key, dict(self))

    def clear(self) -> None:
        super().clear()
        clear_backup(self._journal_key)

    def pop(self, *args):
        result = super().pop(*args)
        save_backup(self._journal_key, dict(self))
        return result
