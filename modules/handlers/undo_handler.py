#!/usr/bin/env python3
"""
Undo handler for the file renamer application.

Manages undo operations including filename restoration, file timestamp
restoration, and EXIF timestamp restoration. Extracted from
main_application.py to reduce the God Object size.
"""

from __future__ import annotations

import os
import shutil
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QLabel, QMessageBox, QPlainTextEdit, QPushButton, QVBoxLayout,
)

from ..exif_processor import batch_restore_timestamps

if TYPE_CHECKING:
    from ..main_application import FileRenamerApp


class UndoHandler:
    """Handles all undo/restore operations for the file renamer.

    Args:
        app: The main FileRenamerApp instance to operate on.
    """

    def __init__(self, app: FileRenamerApp) -> None:
        self.app = app

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def undo_rename_action(self) -> None:
        """Restore files to their original names and EXIF timestamps.

        Simplified version after Phase 2 refactoring — delegates to helper
        functions.
        """
        app = self.app

        # Check what can be undone
        files_to_undo, timestamp_backup_exists, exif_backup_exists = (
            self._check_undo_availability()
        )

        # Nothing to undo?
        if not files_to_undo and not timestamp_backup_exists and not exif_backup_exists:
            QMessageBox.information(
                app,
                "No Undo Available",
                "Nothing to restore.\n\nThe undo function becomes available when either:\n"
                "• Files have been renamed in this session, or\n"
                "• File timestamps were synchronized (and a backup exists), or\n"
                "• EXIF timestamps were shifted (and a backup exists).",
            )
            return

        # Only timestamps to restore (no filename changes)?
        if not files_to_undo and (timestamp_backup_exists or exif_backup_exists):
            restore_msg = "File names are unchanged. Restore original "
            restore_items = []
            if timestamp_backup_exists:
                restore_items.append("file timestamps")
            if exif_backup_exists:
                restore_items.append("EXIF timestamps")
            restore_msg += " and ".join(restore_items) + "?"

            reply = QMessageBox.question(
                app,
                "Restore Original Timestamps",
                restore_msg,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

            # Restore only timestamps
            errors = self._restore_timestamps_only()

            if errors:
                QMessageBox.warning(
                    app,
                    "Timestamp Restore",
                    "Some timestamp restores failed:\n" + "\n".join(errors[:10]),
                )
            else:
                QMessageBox.information(
                    app,
                    "Timestamp Restore",
                    "Original timestamps restored successfully.",
                )

            app.status.showMessage("Timestamps restored", 4000)
            app.update_preview()
            return

        # Confirm filename restore
        reply = QMessageBox.question(
            app,
            "Confirm Undo",
            f"Restore {len(files_to_undo)} files to their original names?\n\n"
            "This will undo all rename operations performed in this session.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        # Disable UI during processing
        self._set_ui_enabled(False)

        # Restore filenames
        restored_files, errors = self._restore_filenames(files_to_undo)

        # Restore timestamps
        timestamp_errors = self._restore_all_timestamps()
        errors.extend(timestamp_errors)

        # Clear original_filenames tracking
        app.original_filenames = {}

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
        self._set_ui_enabled(True)
        app.undo_button.setEnabled(False)

        # Update preview
        app.update_preview()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _set_ui_enabled(self, enabled: bool) -> None:
        """Enable or disable UI controls during undo processing."""
        app = self.app
        if enabled:
            app.undo_button.setText("↶ Restore Original Names")
            app.rename_button.setEnabled(True)
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

        Uses only in-memory data and cached async EXIF check results to
        avoid blocking the GUI thread with synchronous ExifTool calls.

        Returns:
            Tuple of (files_to_undo, timestamp_backup_exists, exif_backup_exists).
        """
        app = self.app
        timestamp_backup_exists = hasattr(app, "timestamp_backup") and bool(
            getattr(app, "timestamp_backup")
        )
        exif_backup_exists = hasattr(app, "exif_backup") and bool(
            getattr(app, "exif_backup")
        )

        # Check which files need to be undone
        files_to_undo: list[tuple[str, str]] = []

        # Check in-memory tracking (current session — fast)
        if hasattr(app, "original_filenames") and app.original_filenames:
            for current_file, original_filename in app.original_filenames.items():
                current_filename = os.path.basename(current_file)
                if current_filename != original_filename and current_file in app.files:
                    files_to_undo.append((current_file, original_filename))

        # Check cached EXIF undo results (populated by _start_async_exif_undo_check)
        if not files_to_undo and getattr(app, "_exif_undo_available", False):
            if app.exiftool_path and hasattr(app, "files") and app.files:
                from ..exif_undo_manager import batch_get_original_filenames

                exif_results = batch_get_original_filenames(
                    app.files, app.exiftool_path
                )
                for file_path, original_filename in exif_results.items():
                    if original_filename:
                        current_filename = os.path.basename(file_path)
                        if original_filename != current_filename:
                            files_to_undo.append((file_path, original_filename))
                            # Cache in memory for future calls
                            if not hasattr(app, "original_filenames"):
                                app.original_filenames = {}
                            app.original_filenames[file_path] = original_filename

        return files_to_undo, timestamp_backup_exists, exif_backup_exists

    def _restore_timestamps_only(self) -> list[str]:
        """Restore only timestamps (file and EXIF) without renaming files.

        Returns:
            List of error messages.
        """
        app = self.app
        errors: list[str] = []

        # Disable UI
        self._set_ui_enabled(False)

        # Restore file timestamps
        if hasattr(app, "timestamp_backup") and app.timestamp_backup:
            try:
                ts_success, ts_errors = batch_restore_timestamps(
                    app.timestamp_backup,
                    progress_callback=lambda msg: app.status.showMessage(msg, 1000),
                )
                if ts_success:
                    app.log(f"✅ Restored file timestamps for {len(ts_success)} files")
                if ts_errors:
                    for file_path, err in ts_errors:
                        errors.append(
                            f"File timestamp restore failed for {os.path.basename(file_path)}: {err}"
                        )
                app.timestamp_backup = {}
            except Exception as e:
                errors.append(f"File timestamp restore error: {e}")

        # Restore EXIF timestamps
        if hasattr(app, "exif_backup") and app.exif_backup:
            try:
                from ..exif_processor import batch_restore_exif_timestamps

                exif_success, exif_errors = batch_restore_exif_timestamps(
                    app.exif_backup,
                    app.exiftool_path,
                    progress_callback=lambda msg: app.status.showMessage(msg, 1000),
                )
                if exif_success:
                    app.log(
                        f"✅ Restored EXIF timestamps for {len(exif_success)} files"
                    )
                    app.exif_service.clear_cache()
                if exif_errors:
                    for file_path, err in exif_errors:
                        errors.append(
                            f"EXIF timestamp restore failed for {os.path.basename(file_path)}: {err}"
                        )
                app.exif_backup = {}
            except Exception as e:
                errors.append(f"EXIF timestamp restore error: {e}")

        # Re-enable UI
        self._set_ui_enabled(True)

        return errors

    def _restore_filenames(
        self, files_to_undo: list[tuple[str, str]]
    ) -> tuple[list[str], list[str]]:
        """Restore files to their original filenames.

        Args:
            files_to_undo: List of (current_file, original_filename) tuples.

        Returns:
            Tuple of (restored_files, errors).
        """
        app = self.app
        restored_files: list[str] = []
        errors: list[str] = []

        # Create a mapping of old paths to new paths for batch update
        path_mapping: dict[str, str] = {}

        for current_file, original_filename in files_to_undo:
            try:
                if os.path.exists(current_file):
                    # Only restore filename, never move between directories
                    current_directory = os.path.dirname(current_file)
                    target_path = os.path.join(current_directory, original_filename)

                    # Check if target already exists
                    if os.path.exists(target_path) and os.path.normpath(
                        target_path
                    ) != os.path.normpath(current_file):
                        errors.append(
                            f"Cannot restore {os.path.basename(current_file)}: "
                            "Target name already exists"
                        )
                        continue

                    # Perform the rename
                    shutil.move(current_file, target_path)
                    restored_files.append(target_path)
                    path_mapping[os.path.normpath(current_file)] = target_path

                else:
                    errors.append(
                        f"File not found: {os.path.basename(current_file)}"
                    )
            except Exception as e:
                errors.append(
                    f"Failed to restore {os.path.basename(current_file)}: {e}"
                )

        # Update all file references in self.files and UI
        if path_mapping:
            # Update app.files list
            for i, file_path in enumerate(app.files):
                normalized_path = os.path.normpath(file_path)
                if normalized_path in path_mapping:
                    app.files[i] = path_mapping[normalized_path]

            # Update UI list
            for i in range(app.file_list.count()):
                item = app.file_list.item(i)
                if item:
                    item_path = item.data(Qt.ItemDataRole.UserRole)
                    if item_path:
                        normalized_path = os.path.normpath(item_path)
                        if normalized_path in path_mapping:
                            new_path = path_mapping[normalized_path]
                            item.setText(os.path.basename(new_path))
                            item.setData(Qt.ItemDataRole.UserRole, new_path)

        return restored_files, errors

    def _restore_all_timestamps(self) -> list[str]:
        """Restore file and EXIF timestamps after filename restore.

        Returns:
            List of error messages.
        """
        app = self.app
        errors: list[str] = []

        # Restore file timestamps
        if hasattr(app, "timestamp_backup") and app.timestamp_backup:
            app.log("🔄 Restoring original file timestamps...")
            try:
                timestamp_successes, timestamp_errors = batch_restore_timestamps(
                    app.timestamp_backup,
                    progress_callback=lambda msg: app.status.showMessage(msg, 1000),
                )
                if timestamp_successes:
                    app.log(
                        f"✅ Restored file timestamps for {len(timestamp_successes)} files"
                    )
                if timestamp_errors:
                    app.log(
                        f"❌ Failed to restore file timestamps for {len(timestamp_errors)} files"
                    )
                    for file_path, error_msg in timestamp_errors:
                        errors.append(
                            f"File timestamp restore failed for "
                            f"{os.path.basename(file_path)}: {error_msg}"
                        )
                app.timestamp_backup = {}
            except Exception as e:
                app.log(f"❌ Error during file timestamp restore: {e}")
                errors.append(f"File timestamp restore error: {e}")

        # Restore EXIF timestamps
        if hasattr(app, "exif_backup") and app.exif_backup:
            app.log("🔄 Restoring original EXIF timestamps...")
            try:
                from ..exif_processor import batch_restore_exif_timestamps

                exif_successes, exif_errors = batch_restore_exif_timestamps(
                    app.exif_backup,
                    app.exiftool_path,
                    progress_callback=lambda msg: app.status.showMessage(msg, 1000),
                )
                if exif_successes:
                    app.log(
                        f"✅ Restored EXIF timestamps for {len(exif_successes)} files"
                    )
                    app.exif_service.clear_cache()
                if exif_errors:
                    app.log(
                        f"❌ Failed to restore EXIF timestamps for {len(exif_errors)} files"
                    )
                    for file_path, error_msg in exif_errors:
                        errors.append(
                            f"EXIF timestamp restore failed for "
                            f"{os.path.basename(file_path)}: {error_msg}"
                        )
                app.exif_backup = {}
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
            error_label = QLabel(f"Errors encountered: {len(errors)}")
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
