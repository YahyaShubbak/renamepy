"""
Preview Generator - Handles filename preview generation and updates
Extracted from main_application.py to improve code organization

The example name is computed by the same RenamePlanner that performs the
real rename, so the preview always matches the result (including sanitizing,
fallbacks like "Unknown-Camera" and per-file shooting settings).
"""
from __future__ import annotations

import os

from ..file_utilities import is_media_file
from ..rename_engine import RenamePlanner


# Shown before any files are loaded, so every component has an example value
SAMPLE_FILE = "20250725_DSC0001.JPG"
SAMPLE_METADATA = {
    "EXIF:DateTimeOriginal": "2025:07:25 10:30:00",
    "EXIF:Model": "Camera",
    "EXIF:LensModel": "Lens",
    "EXIF:ISO": 100,
    "EXIF:FNumber": 2.8,
    "EXIF:ExposureTime": 0.004,
    "EXIF:FocalLength": 50.0,
}


class PreviewGenerator:
    """
    Manages preview generation and display including:
    - Preview updates based on settings
    - Raw metadata caching for the preview file
    - Component order management
    """

    def __init__(self, parent):
        """
        Initialize PreviewGenerator

        Args:
            parent: The parent FileRenamerApp instance
        """
        self.parent = parent
        # path -> (mtime, raw metadata) of files shown in the preview
        self._raw_cache: dict[str, tuple[float, dict]] = {}

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------

    def planner_settings(self) -> dict:
        """The naming settings currently selected in the UI."""
        p = self.parent
        return dict(
            camera_prefix=p.camera_prefix_entry.text().strip(),
            additional=p.additional_entry.text().strip(),
            use_camera=p.checkbox_camera.isChecked(),
            use_lens=p.checkbox_lens.isChecked(),
            use_date=p.checkbox_date.isChecked(),
            date_format=p.date_format_combo.currentText(),
            separator=p.separator_combo.currentText(),
            custom_order=list(p.custom_order),
            continuous_counter=p.checkbox_continuous_counter.isChecked(),
            selected_metadata=dict(p.selected_metadata),
        )

    def _active_components(self, settings: dict) -> list[str]:
        active = []
        if settings["use_date"]:
            active.append("Date")
        if settings["camera_prefix"]:
            active.append("Prefix")
        if settings["additional"]:
            active.append("Additional")
        if settings["use_camera"]:
            active.append("Camera")
        if settings["use_lens"]:
            active.append("Lens")
        active.append("Number")  # Always present
        active.extend(f"Meta_{key}" for key in settings["selected_metadata"])
        return active

    def _sync_custom_order(self, settings: dict) -> None:
        """Keep custom_order in line with the activated components.

        Newly activated components are inserted before "Number",
        deactivated ones are removed.
        """
        active = self._active_components(settings)
        order = list(self.parent.custom_order)
        for component in active:
            if component not in order:
                if "Number" in order:
                    order.insert(order.index("Number"), component)
                else:
                    order.append(component)
        self.parent.custom_order = [c for c in order if c in active]

    # ------------------------------------------------------------------
    # Preview
    # ------------------------------------------------------------------

    def _preview_file(self) -> str | None:
        files = self.parent.files
        return (
            next((f for f in files if os.path.splitext(f)[1].lower() in (".jpg", ".jpeg")), None)
            or next((f for f in files if is_media_file(f)), None)
        )

    def _raw_metadata(self, path: str) -> dict:
        """Raw ExifTool metadata of *path*, cached by modification time."""
        if not self.parent.exif_method or not os.path.exists(path):
            return {}
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            return {}
        cached = self._raw_cache.get(path)
        if cached and cached[0] == mtime:
            return cached[1]
        try:
            meta = self.parent.exif_service.batch_get_raw_metadata([path]).get(path) or {}
        except Exception as e:
            self.parent.log(f"Preview: could not read metadata of {path}: {e}")
            meta = {}
        if len(self._raw_cache) > 50:
            self._raw_cache.clear()
        self._raw_cache[path] = (mtime, meta)
        return meta

    def clear_cache(self) -> None:
        self._raw_cache.clear()

    def build_preview(self) -> tuple[list[tuple[str, str]], str]:
        """(component_id, text) pairs and the full example file name."""
        settings = self.planner_settings()
        path = self._preview_file()
        if path is None:
            path, raw_meta, exif_method = SAMPLE_FILE, SAMPLE_METADATA, "exiftool"
        else:
            raw_meta, exif_method = self._raw_metadata(path), self.parent.exif_method
        planner = RenamePlanner([path], exif_method=exif_method, exif_service=None, **settings)
        return planner.preview(path, raw_meta)

    def update_preview(self):
        """Update the interactive preview widget with current settings"""
        self._sync_custom_order(self.planner_settings())
        components, new_name = self.build_preview()
        self.parent.log(f"🖼️ Debug: Preview {new_name} from {components}")
        self.parent.interactive_preview.set_separator(self.parent.separator_combo.currentText())
        self.parent.interactive_preview.set_components(components)
        self.parent.interactive_preview.setToolTip(f"Example: {new_name}")

    def apply_order(self, new_ids: list[str]) -> None:
        """Take over the order the user dragged in the preview.

        Only the displayed components are reordered; active components that
        are not shown (e.g. ISO for a file without ISO) keep their place.
        """
        displayed = list(new_ids)
        remaining = iter(displayed)
        order = [next(remaining) if c in displayed else c for c in self.parent.custom_order]
        order.extend(c for c in displayed if c not in order)
        self.parent.custom_order = order
        self.update_preview()

    def validate_and_update_preview(self):
        """Validate input and update preview"""
        self.update_preview()

    def show_preview_info(self):
        """Show interactive preview help dialog"""
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton

        dialog = QDialog(self.parent)
        dialog.setWindowTitle("Interactive Preview Help")
        dialog.setModal(True)
        dialog.resize(400, 300)
        layout = QVBoxLayout(dialog)

        info_text = QLabel("""
Interactive Preview shows how your filenames will look,
using the first loaded file as the example.

You can:
• Drag and drop components to reorder them
• See real-time preview of your filename format
• Components are separated by your chosen separator

The number (001) counts up per file (per day, or across all days
with the continuous counter). Before renaming, the full list of
old and new names is shown for confirmation.
        """)
        info_text.setWordWrap(True)
        layout.addWidget(info_text)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)
        dialog.exec()
