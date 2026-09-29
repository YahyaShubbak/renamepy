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
"""

from __future__ import annotations

import os
from collections import defaultdict
from typing import TYPE_CHECKING

from PyQt6.QtWidgets import (
    QDialog, QLabel, QMessageBox, QPlainTextEdit, QPushButton, QVBoxLayout,
)

from ..exif_processor import batch_restore_timestamps
from ..backup_journal import update_entries as _update_journal, rekey_entries, rekey_journal
from ..file_utilities import is_safe_restore_name, safe_rename, find_sidecars, sidecar_target

if TYPE_CHECKING:
    from ..main_application import FileRenamerApp


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

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def undo_rename_action(self) -> None:
        """Restore files to their original names and timestamps."""
        app = self.app

        # Check what can be undone
        files_to_undo, timestamp_backup_exists, exif_backup_exists = (
            self._check_undo_availability()
        )

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

        # Only timestamps to restore (no filename changes)?
        if not files_to_undo:
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

            self._set_ui_enabled(False)
            try:
                errors = self._restore_all_timestamps()
            finally:
                self._set_ui_enabled(True)

            if errors:
                QMessageBox.warning(
                    app,
                    "Timestamp Restore",
                    "Some timestamp restores failed (their backups are kept):\n" + "\n".join(errors[:10]),
                )
            else:
                QMessageBox.information(
                    app,
                    "Timestamp Restore",
                    "Original timestamps restored successfully.",
                )

            app.status.showMessage("Timestamps restored", 4000)
            app.update_restore_button_state()
            app.update_preview()
            return

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

        # Disable UI during processing
        self._set_ui_enabled(False)
        try:
            # Contents first (backups are keyed by the current paths) ...
            errors = self._restore_all_timestamps()
            # ... then names
            restored_files, name_errors = self._restore_filenames(files_to_undo)
            errors = name_errors + errors
        finally:
            self._set_ui_enabled(True)

        # Show results
        if errors:
            self._show_error_dialog(restored_files, errors)
        else:
            QMessageBox.information(
                app,
                "Undo Complete",
                f"Successfully restored {len(restored_files)} files to their original names.",
            )

        # Update status and UI
        app.status.showMessage(
            f"Restored {len(restored_files)} files to original names", 5000
        )
        app.update_restore_button_state()
        app.update_preview()

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

    def _check_undo_availability(
        self,
    ) -> tuple[list[tuple[str, str]], bool, bool]:
        """Check if undo operation is available and what can be restored.

        Uses the in-memory/journal mapping and cached async EXIF check
        results to avoid blocking the GUI thread with needless ExifTool
        calls. Entries that are unsafe or ambiguous are collected in
        ``self._rejected`` instead of being restored.

        Returns:
            Tuple of (files_to_undo, timestamp_backup_exists, exif_backup_exists).
        """
        app = self.app
        self._rejected = []
        timestamp_backup_exists = bool(app.timestamp_backup)
        exif_backup_exists = bool(app.exif_backup)

        candidates: list[tuple[str, str]] = []

        # Renames recorded by this application (this session or recovered
        # from the journal). The file must still exist under that name.
        for current_file, original_filename in app.original_filenames.items():
            if (os.path.basename(current_file) != original_filename
                    and os.path.exists(current_file)):
                candidates.append((current_file, original_filename))

        # Original names stored in file metadata (untrusted: any downloaded
        # file can carry such a tag, so everything is validated below).
        if not candidates and getattr(app, "_exif_undo_available", False):
            if app.exiftool_path and app.files:
                from ..exif_undo_manager import batch_get_original_filenames

                exif_results = batch_get_original_filenames(
                    app.files, app.exiftool_path
                )
                for file_path, original_filename in exif_results.items():
                    if original_filename and original_filename != os.path.basename(file_path):
                        candidates.append((file_path, original_filename))

        files_to_undo = self._validate_candidates(candidates)
        return files_to_undo, timestamp_backup_exists, exif_backup_exists

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
        """Restore files to their original filenames.

        Args:
            files_to_undo: List of (current_file, original_filename) tuples,
                already validated by ``_validate_candidates``.

        Returns:
            Tuple of (restored_files, errors).
        """
        app = self.app
        restored_files: list[str] = []
        errors: list[str] = []

        # current path -> restored path
        path_mapping: dict[str, str] = {}
        # Sidecars with their own undo entry are restored through it
        tracked = {os.path.normcase(os.path.abspath(path)) for path, _name in files_to_undo}

        for current_file, original_filename in files_to_undo:
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
                self._restore_sidecars(sidecars, target_path, path_mapping, errors)
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
            # Forget only the entries that were restored
            app.original_filenames = {
                path: name for path, name in app.original_filenames.items()
                if path not in path_mapping
            }
            _update_journal({"original_filenames": {"remove": list(path_mapping)}})

            # Remaining backups (e.g. failed timestamp restores) follow the file
            app.timestamp_backup = rekey_entries(app.timestamp_backup, path_mapping)
            app.exif_backup = rekey_entries(app.exif_backup, path_mapping)
            rekey_journal(path_mapping)

            # Update all file references in app.files and the UI list
            normalized = {os.path.normpath(k): v for k, v in path_mapping.items()}
            new_files = [normalized.get(os.path.normpath(p), p) for p in app.files]
            app.files.clear()
            app.files.extend(new_files)
            app.update_file_list()

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
        """Restore file and EXIF timestamps from their backups.

        Successfully restored entries are removed from memory and from the
        journal; failed ones are kept.

        Returns:
            List of error messages.
        """
        app = self.app
        errors: list[str] = []

        # Restore file timestamps
        if app.timestamp_backup:
            app.log("🔄 Restoring original file timestamps...")
            try:
                timestamp_successes, timestamp_errors = batch_restore_timestamps(
                    dict(app.timestamp_backup),
                    progress_callback=lambda msg: app.status.showMessage(msg, 1000),
                )
                restored = {file_path for file_path, _ in timestamp_successes}
                if restored:
                    app.log(f"✅ Restored file timestamps for {len(restored)} files")
                for file_path, error_msg in timestamp_errors:
                    errors.append(
                        f"File timestamp restore failed for "
                        f"{os.path.basename(file_path)}: {error_msg}"
                    )
                app.timestamp_backup = {
                    k: v for k, v in app.timestamp_backup.items() if k not in restored
                }
                _update_journal({"timestamp_backup": {"remove": list(restored)}})
            except Exception as e:
                app.log(f"❌ Error during file timestamp restore: {e}")
                errors.append(f"File timestamp restore error: {e}")

        # Restore EXIF timestamps
        if app.exif_backup:
            app.log("🔄 Restoring original EXIF timestamps...")
            try:
                from ..exif_processor import batch_restore_exif_timestamps

                exif_successes, exif_errors = batch_restore_exif_timestamps(
                    dict(app.exif_backup),
                    app.exiftool_path,
                    progress_callback=lambda msg: app.status.showMessage(msg, 1000),
                )
                restored = {file_path for file_path, _ in exif_successes}
                if restored:
                    app.log(f"✅ Restored EXIF timestamps for {len(restored)} files")
                    app.exif_service.clear_cache()
                for file_path, error_msg in exif_errors:
                    errors.append(
                        f"EXIF timestamp restore failed for "
                        f"{os.path.basename(file_path)}: {error_msg}"
                    )
                app.exif_backup = {
                    k: v for k, v in app.exif_backup.items() if k not in restored
                }
                _update_journal({"exif_backup": {"remove": list(restored)}})
            except Exception as e:
                app.log(f"❌ Error during EXIF timestamp restore: {e}")
                errors.append(f"EXIF timestamp restore error: {e}")

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
