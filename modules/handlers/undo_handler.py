#!/usr/bin/env python3
"""
Undo handler for the file renamer application.

Manages undo operations including filename restoration, file timestamp
restoration, and EXIF timestamp restoration. Extracted from
main_application.py to reduce the God Object size.

Every backup is keyed by the file's *current* path (renames re-key them,
see FileRenamerApp.on_rename_finished), so file contents - timestamps and
EXIF dates - are restored first and file names last. Only entries that were
restored successfully are removed; failed ones stay available for another
attempt (or can be discarded via Tools > Forget Undo Data).

The work itself (metadata scan, restores, renames) runs in an
``UndoWorker`` thread so the window stays responsive. The functions that
run there (``_do_restore_timestamps``, ``_do_restore_filenames``,
``_scan_metadata_candidates``) take plain data and touch only the files and
the journal; the application state is updated afterwards on the GUI thread.
"""

from __future__ import annotations

import os
from collections import defaultdict
from typing import TYPE_CHECKING, Callable

from PyQt6.QtCore import QThread, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog, QLabel, QMessageBox, QPlainTextEdit, QProgressDialog, QPushButton, QVBoxLayout,
)

from ..exif_processor import batch_restore_timestamps
from ..backup_journal import update_entries as _update_journal, rekey_entries, rekey_journal
from ..file_utilities import (
    is_safe_restore_name, safe_rename, find_sidecars, sidecar_target, rename_order, path_key,
)
from ..logger_util import get_logger

if TYPE_CHECKING:
    from ..main_application import FileRenamerApp

log = get_logger()

Progress = Callable[[str], None]


# ----------------------------------------------------------------------
# Work that may run on any thread (no access to the application window)
# ----------------------------------------------------------------------

def _do_restore_timestamps(
    timestamp_backup: dict, exif_backup: dict, exiftool_path, progress: Progress,
) -> tuple[set[str], set[str], list[str]]:
    """Restore EXIF dates, then file timestamps, from their backups.

    EXIF dates come first: writing metadata rewrites the file, so file
    timestamps are restored last and end up correct even where ExifTool
    cannot preserve a time. Restored entries are removed from the journal.

    Returns:
        (restored timestamp paths, restored EXIF paths, error messages)
    """
    errors: list[str] = []
    restored_exif: set[str] = set()
    restored_ts: set[str] = set()

    if exif_backup:
        progress("🔄 Restoring original EXIF timestamps...")
        try:
            from ..exif_processor import batch_restore_exif_timestamps

            exif_successes, exif_errors = batch_restore_exif_timestamps(
                dict(exif_backup), exiftool_path, progress_callback=progress,
            )
            restored_exif = {file_path for file_path, _ in exif_successes}
            for file_path, error_msg in exif_errors:
                errors.append(
                    f"EXIF timestamp restore failed for "
                    f"{os.path.basename(file_path)}: {error_msg}"
                )
            _update_journal({"exif_backup": {"remove": list(restored_exif)}})
        except Exception as e:
            log.warning(f"Error during EXIF timestamp restore: {e}")
            errors.append(f"EXIF timestamp restore error: {e}")

    if timestamp_backup:
        progress("🔄 Restoring original file timestamps...")
        try:
            timestamp_successes, timestamp_errors = batch_restore_timestamps(
                dict(timestamp_backup), progress_callback=progress,
            )
            restored_ts = {file_path for file_path, _ in timestamp_successes}
            for file_path, error_msg in timestamp_errors:
                errors.append(
                    f"File timestamp restore failed for "
                    f"{os.path.basename(file_path)}: {error_msg}"
                )
            _update_journal({"timestamp_backup": {"remove": list(restored_ts)}})
        except Exception as e:
            log.warning(f"Error during file timestamp restore: {e}")
            errors.append(f"File timestamp restore error: {e}")

    return restored_ts, restored_exif, errors


def _do_restore_filenames(
    files_to_undo: list[tuple[str, str]], progress: Progress,
) -> tuple[list[str], list[str], dict[str, str]]:
    """Rename files back to their original names (sidecars follow).

    Args:
        files_to_undo: (current_file, original_filename) pairs, already
            validated by ``UndoHandler._validate_candidates``.

    Returns:
        (restored files, error messages, {old path: restored path})
    """
    restored_files: list[str] = []
    errors: list[str] = []

    # current path -> restored path
    path_mapping: dict[str, str] = {}
    # Sidecars with their own undo entry are restored through it
    tracked = {os.path.normcase(os.path.abspath(path)) for path, _name in files_to_undo}

    # A chain of renames (A->B while B->C) is undone in dependency order,
    # otherwise a name is still taken when its file is restored.
    pairs = [(path, os.path.join(os.path.dirname(path), str(name))) for path, name in files_to_undo]
    files_to_undo = [files_to_undo[i] for i in rename_order(pairs)]
    # Backups of files whose path another restored file takes over follow
    # them right away (a crash must not leave them on the other file's path)
    sources = {path_key(path) for path, _target in pairs}
    targets = {path_key(target) for _path, target in pairs}
    stepwise = {path_key(path) for path, target in pairs
                if path_key(target) in sources or path_key(path) in targets}

    total = len(files_to_undo)
    for idx, (current_file, original_filename) in enumerate(files_to_undo):
        if idx % 20 == 0:
            progress(f"Restoring file names {idx + 1}/{total}...")
        try:
            if not is_safe_restore_name(original_filename, current_file):
                errors.append(f"Refusing unsafe original name for {os.path.basename(current_file)}")
                continue
            if not os.path.exists(current_file):
                errors.append(f"File not found: {os.path.basename(current_file)}")
                continue

            # Only restore filename, never move between directories
            target_path = os.path.join(os.path.dirname(current_file), original_filename)
            sidecars = [
                sidecar for sidecar in find_sidecars(current_file)
                if os.path.normcase(os.path.abspath(sidecar[0])) not in tracked
            ]
            safe_rename(current_file, target_path)
            restored_files.append(target_path)
            path_mapping[current_file] = target_path
            if path_key(current_file) in stepwise:
                rekey_journal({current_file: target_path})
            UndoHandler._restore_sidecars(sidecars, target_path, path_mapping, errors)
        except FileExistsError:
            errors.append(
                f"Cannot restore {os.path.basename(current_file)}: "
                f"'{original_filename}' already exists"
            )
        except Exception as e:
            errors.append(
                f"Failed to restore {os.path.basename(current_file)}: {e}"
            )

    if path_mapping:
        # Forget only the entries that were restored; remaining backups
        # (e.g. failed timestamp restores) follow the file.
        _update_journal({"original_filenames": {"remove": list(path_mapping)}})
        rekey_journal({old: new for old, new in path_mapping.items() if path_key(old) not in stepwise})

    return restored_files, errors, path_mapping


def _scan_metadata_candidates(files: list[str], exiftool_path) -> list[tuple[str, str]]:
    """(path, original name) pairs stored in the files' metadata.

    Untrusted: any downloaded file can carry such a tag, so the caller
    validates every entry before restoring it.
    """
    from ..exif_undo_manager import batch_get_original_filenames

    candidates: list[tuple[str, str]] = []
    for file_path, original_filename in batch_get_original_filenames(files, exiftool_path).items():
        if original_filename and original_filename != os.path.basename(file_path):
            candidates.append((file_path, original_filename))
    return candidates


class UndoWorker(QThread):
    """Runs one undo phase off the GUI thread.

    *job* receives a progress callback and returns the phase's result. It
    must only touch files and the journal, never the application window.
    ``done`` carries the result, or the exception the job raised.
    """

    progress = pyqtSignal(str)
    done = pyqtSignal(object)

    def __init__(self, job: Callable[[Progress], object], parent=None) -> None:
        super().__init__(parent)
        self._job = job

    def run(self) -> None:
        try:
            result = self._job(self.progress.emit)
        except Exception as e:
            log.exception("Undo worker failed")
            result = e
        self.done.emit(result)


class UndoHandler:
    """Handles all undo/restore operations for the file renamer.

    Args:
        app: The main FileRenamerApp instance to operate on.
    """

    def __init__(self, app: FileRenamerApp) -> None:
        self.app = app
        # (current_path, original_name, reason) of entries that were found
        # but will not be restored - shown to the user for transparency.
        self._rejected: list[tuple[str, str, str]] = []
        # The running undo phase (FileRenamerApp.closeEvent checks it)
        self.worker: UndoWorker | None = None
        self._progress: QProgressDialog | None = None

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def undo_rename_action(self) -> None:
        """Restore files to their original names and timestamps.

        Returns immediately; the work runs in an ``UndoWorker``. If no
        rename is recorded, the original names are first read from the
        files' metadata (also in the worker).
        """
        app = self.app
        if self.worker is not None:
            return
        self._rejected = []

        candidates = self._journal_candidates()
        if not candidates and self._metadata_scan_needed():
            files = list(app.files)
            exiftool_path = app.exiftool_path
            self._start_worker(
                "Reading original names from file metadata...",
                lambda progress: _scan_metadata_candidates(files, exiftool_path),
                self._on_scan_done,
            )
            return
        self._confirm_and_restore(candidates)

    # ------------------------------------------------------------------
    # Worker flow (GUI thread)
    # ------------------------------------------------------------------

    def _start_worker(self, text: str, job: Callable[[Progress], object], on_done) -> None:
        app = self.app
        app._ui_set_busy(True)

        progress = QProgressDialog(text, "", 0, 0, app)
        progress.setCancelButton(None)  # a restore is never left half done
        progress.setWindowTitle("RenamePy")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(300)
        progress.setAutoClose(False)
        progress.setAutoReset(False)
        self._progress = progress

        worker = UndoWorker(job, app)
        worker.progress.connect(progress.setLabelText)
        worker.done.connect(on_done)
        self.worker = worker
        worker.start()

    def _finish_worker(self) -> None:
        """Release the finished worker and close the progress dialog."""
        worker = self.worker
        if worker is not None:
            worker.wait()  # done is emitted as the last statement of run()
            worker.deleteLater()
            self.worker = None
        if self._progress is not None:
            self._progress.close()
            self._progress.deleteLater()
            self._progress = None

    def _on_scan_done(self, result) -> None:
        self._finish_worker()
        self.app._ui_set_busy(False)
        if isinstance(result, Exception):
            log.warning(f"Could not read original names from metadata: {result}")
            result = []
        self._confirm_and_restore(result)

    def _confirm_and_restore(self, candidates: list[tuple[str, str]]) -> None:
        """Ask for confirmation, then restore in the worker."""
        app = self.app
        files_to_undo = self._validate_candidates(candidates)
        timestamp_backup_exists = bool(app.timestamp_backup)
        exif_backup_exists = bool(app.exif_backup)

        # Nothing to undo?
        if not files_to_undo and not timestamp_backup_exists and not exif_backup_exists:
            message = (
                "Nothing to restore.\n\nThe undo function becomes available when either:\n"
                "• Files have been renamed (in this or an earlier session), or\n"
                "• File timestamps were synchronized (and a backup exists), or\n"
                "• EXIF timestamps were shifted (and a backup exists)."
            )
            if self._rejected:
                message += "\n\n" + self._format_rejected()
            QMessageBox.information(app, "No Undo Available", message)
            return

        if not files_to_undo:
            # Only timestamps to restore (no filename changes)
            restore_items = []
            if timestamp_backup_exists:
                restore_items.append("file timestamps")
            if exif_backup_exists:
                restore_items.append("EXIF timestamps")
            restore_msg = "File names are unchanged. Restore original " + " and ".join(restore_items) + "?"

            reply = QMessageBox.question(
                app,
                "Restore Original Timestamps",
                restore_msg,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        else:
            # Confirm filename restore, listing exactly what will happen
            box = QMessageBox(app)
            box.setIcon(QMessageBox.Icon.Question)
            box.setWindowTitle("Confirm Undo")
            text = f"Restore {len(files_to_undo)} files to their original names?"
            if timestamp_backup_exists or exif_backup_exists:
                text += "\n\nBacked-up timestamps will be restored as well."
            if self._rejected:
                text += f"\n\n{len(self._rejected)} entries will be skipped (see details)."
            box.setText(text)
            details = [f"{os.path.basename(cur)}  →  {orig}" for cur, orig in files_to_undo]
            if self._rejected:
                details.append("")
                details.append(self._format_rejected())
            box.setDetailedText("\n".join(details))
            box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            box.setDefaultButton(QMessageBox.StandardButton.No)
            if box.exec() != QMessageBox.StandardButton.Yes:
                return

        timestamp_backup = dict(app.timestamp_backup)
        exif_backup = dict(app.exif_backup)
        exiftool_path = app.exiftool_path

        def job(progress: Progress):
            # Contents first (backups are keyed by the current paths) ...
            timestamps = _do_restore_timestamps(timestamp_backup, exif_backup, exiftool_path, progress)
            # ... then names
            names = _do_restore_filenames(files_to_undo, progress) if files_to_undo else ([], [], {})
            return timestamps, names

        names_requested = bool(files_to_undo)
        self._start_worker(
            "Restoring...", job,
            lambda result: self._on_restore_done(result, names_requested),
        )

    def _on_restore_done(self, result, names_requested: bool) -> None:
        app = self.app
        self._finish_worker()

        if isinstance(result, Exception):
            app._ui_set_busy(False)
            QMessageBox.critical(app, "Undo Failed", f"Unexpected error during undo:\n{result}")
            app.update_restore_button_state()
            app.update_preview()
            return

        (restored_ts, restored_exif, timestamp_errors), (restored_files, name_errors, path_mapping) = result
        self._apply_timestamp_result(restored_ts, restored_exif)
        self._apply_filename_result(path_mapping)
        app._ui_set_busy(False)

        if not names_requested:
            if timestamp_errors:
                QMessageBox.warning(
                    app,
                    "Timestamp Restore",
                    "Some timestamp restores failed (their backups are kept):\n"
                    + "\n".join(timestamp_errors[:10]),
                )
            else:
                QMessageBox.information(
                    app,
                    "Timestamp Restore",
                    "Original timestamps restored successfully.",
                )
            app.status.showMessage("Timestamps restored", 4000)
        else:
            errors = name_errors + timestamp_errors
            if errors:
                self._show_error_dialog(restored_files, errors)
            else:
                QMessageBox.information(
                    app,
                    "Undo Complete",
                    f"Successfully restored {len(restored_files)} files to their original names.",
                )
            app.status.showMessage(
                f"Restored {len(restored_files)} files to original names", 5000
            )

        app.update_restore_button_state()
        app.update_preview()

    # ------------------------------------------------------------------
    # Applying results to the application state (GUI thread)
    # ------------------------------------------------------------------

    def _apply_timestamp_result(self, restored_ts: set[str], restored_exif: set[str]) -> None:
        app = self.app
        if restored_exif:
            app.log(f"✅ Restored EXIF timestamps for {len(restored_exif)} files")
            app.exif_service.clear_cache()
            app.preview_generator.clear_cache()
            app.exif_backup = {
                k: v for k, v in app.exif_backup.items() if k not in restored_exif
            }
        if restored_ts:
            app.log(f"✅ Restored file timestamps for {len(restored_ts)} files")
            app.timestamp_backup = {
                k: v for k, v in app.timestamp_backup.items() if k not in restored_ts
            }

    def _apply_filename_result(self, path_mapping: dict[str, str]) -> None:
        if not path_mapping:
            return
        app = self.app
        # Forget only the entries that were restored
        app.original_filenames = {
            path: name for path, name in app.original_filenames.items()
            if path not in path_mapping
        }
        # Remaining backups (e.g. failed timestamp restores) follow the file
        app.timestamp_backup = rekey_entries(app.timestamp_backup, path_mapping)
        app.exif_backup = rekey_entries(app.exif_backup, path_mapping)

        # Update all file references in app.files and the UI list
        normalized = {os.path.normpath(k): v for k, v in path_mapping.items()}
        new_files = [normalized.get(os.path.normpath(p), p) for p in app.files]
        app.files.clear()
        app.files.extend(new_files)
        app.update_file_list()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _format_rejected(self) -> str:
        lines = ["Skipped:"]
        for current, original, reason in self._rejected:
            lines.append(f"• {os.path.basename(current)} → {original!r}: {reason}")
        return "\n".join(lines)

    def _set_ui_enabled(self, enabled: bool) -> None:
        """Enable or disable UI controls during undo processing."""
        app = self.app
        if enabled:
            app.undo_button.setText("↶ Restore Original Names")
            app.rename_button.setEnabled(bool(app.files))
            app.select_files_menu_button.setEnabled(True)
            app.select_folder_menu_button.setEnabled(True)
            app.clear_files_menu_button.setEnabled(True)
        else:
            app.undo_button.setEnabled(False)
            app.undo_button.setText("⏳ Restoring...")
            app.rename_button.setEnabled(False)
            app.select_files_menu_button.setEnabled(False)
            app.select_folder_menu_button.setEnabled(False)
            app.clear_files_menu_button.setEnabled(False)

    def _journal_candidates(self) -> list[tuple[str, str]]:
        """Renames recorded by this application (this session or recovered
        from the journal). The file must still exist under that name."""
        candidates: list[tuple[str, str]] = []
        for current_file, original_filename in self.app.original_filenames.items():
            if (os.path.basename(current_file) != original_filename
                    and os.path.exists(current_file)):
                candidates.append((current_file, original_filename))
        return candidates

    def _metadata_scan_needed(self) -> bool:
        app = self.app
        return bool(getattr(app, "_exif_undo_available", False) and app.exiftool_path and app.files)

    def _check_undo_availability(
        self,
    ) -> tuple[list[tuple[str, str]], bool, bool]:
        """Check if undo operation is available and what can be restored.

        Synchronous variant (the metadata scan runs on the calling thread);
        ``undo_rename_action`` does the same in an ``UndoWorker``. Entries
        that are unsafe or ambiguous are collected in ``self._rejected``
        instead of being restored.

        Returns:
            Tuple of (files_to_undo, timestamp_backup_exists, exif_backup_exists).
        """
        app = self.app
        self._rejected = []
        candidates = self._journal_candidates()
        if not candidates and self._metadata_scan_needed():
            candidates = _scan_metadata_candidates(app.files, app.exiftool_path)
        files_to_undo = self._validate_candidates(candidates)
        return files_to_undo, bool(app.timestamp_backup), bool(app.exif_backup)

    def _validate_candidates(
        self, candidates: list[tuple[str, str]]
    ) -> list[tuple[str, str]]:
        """Drop unsafe names and names claimed by several files in one folder."""
        safe: list[tuple[str, str]] = []
        for current_file, original_filename in candidates:
            if is_safe_restore_name(original_filename, current_file):
                safe.append((current_file, original_filename))
            else:
                self._rejected.append((
                    current_file, str(original_filename),
                    "not a plain file name with the same extension",
                ))

        claims: dict[tuple[str, str], list[tuple[str, str]]] = defaultdict(list)
        for current_file, original_filename in safe:
            key = (os.path.normcase(os.path.dirname(current_file)), original_filename.lower())
            claims[key].append((current_file, original_filename))

        result: list[tuple[str, str]] = []
        for entries in claims.values():
            if len(entries) == 1:
                result.extend(entries)
            else:
                for current_file, original_filename in entries:
                    self._rejected.append((
                        current_file, original_filename,
                        f"{len(entries)} files claim this original name",
                    ))
        return result

    def _restore_timestamps_only(self) -> list[str]:
        """Restore only timestamps (file and EXIF) without renaming files.

        Returns:
            List of error messages.
        """
        self._set_ui_enabled(False)
        try:
            return self._restore_all_timestamps()
        finally:
            self._set_ui_enabled(True)

    def _restore_filenames(
        self, files_to_undo: list[tuple[str, str]]
    ) -> tuple[list[str], list[str]]:
        """Restore files to their original filenames (synchronously).

        Args:
            files_to_undo: List of (current_file, original_filename) tuples,
                already validated by ``_validate_candidates``.

        Returns:
            Tuple of (restored_files, errors).
        """
        restored_files, errors, path_mapping = _do_restore_filenames(files_to_undo, lambda msg: None)
        self._apply_filename_result(path_mapping)
        return restored_files, errors

    @staticmethod
    def _restore_sidecars(sidecars, photo_target, path_mapping, errors) -> None:
        """Keep sidecars that follow a photo's current name attached to it.

        Covers sidecars without an undo entry of their own - e.g. when the
        original name comes from the photo's metadata, or the sidecar was
        created after the rename.
        """
        for sidecar_path, kind, suffix in sidecars:
            if not os.path.exists(sidecar_path):
                continue  # e.g. a stem sidecar already moved with the pair's other photo
            new_path = sidecar_target(photo_target, kind, suffix)
            if os.path.normcase(new_path) == os.path.normcase(sidecar_path):
                continue
            try:
                safe_rename(sidecar_path, new_path)
                path_mapping[sidecar_path] = new_path
            except FileExistsError:
                errors.append(
                    f"Sidecar {os.path.basename(sidecar_path)} not restored: "
                    f"'{os.path.basename(new_path)}' already exists"
                )
            except OSError as e:
                errors.append(f"Sidecar {os.path.basename(sidecar_path)} not restored: {e}")

    def _restore_all_timestamps(self) -> list[str]:
        """Restore file and EXIF timestamps from their backups (synchronously).

        Successfully restored entries are removed from memory and from the
        journal; failed ones are kept.

        Returns:
            List of error messages.
        """
        app = self.app
        restored_ts, restored_exif, errors = _do_restore_timestamps(
            dict(app.timestamp_backup), dict(app.exif_backup), app.exiftool_path,
            lambda msg: app.status.showMessage(msg, 1000),
        )
        self._apply_timestamp_result(restored_ts, restored_exif)
        return errors

    def _show_error_dialog(
        self, restored_files: list[str], errors: list[str]
    ) -> None:
        """Display a dialog summarizing undo results with errors.

        Args:
            restored_files: List of successfully restored file paths.
            errors: List of error message strings.
        """
        app = self.app
        error_dialog = QDialog(app)
        error_dialog.setWindowTitle("Undo Results")
        error_layout = QVBoxLayout(error_dialog)

        if restored_files:
            success_label = QLabel(
                f"Successfully restored: {len(restored_files)} files"
            )
            success_label.setStyleSheet("color: green; font-weight: bold;")
            error_layout.addWidget(success_label)

        if errors:
            error_label = QLabel(f"Errors encountered: {len(errors)} (the undo data for these is kept)")
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
