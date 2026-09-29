#!/usr/bin/env python3
"""
Rename engine: planning and execution of batch renames.

- :class:`RenamePlanner` computes the complete rename plan (new names for all
  files and their sidecars) without touching anything. It has no Qt
  dependency, and the interactive preview uses the very same code for its
  example name, so the preview always matches the real result.
- :class:`RenameWorkerThread` runs planning and/or execution in a background
  thread: optional EXIF-to-file timestamp sync, journaling of the plan,
  collision-safe renames, and writing original names into the files.
"""
from __future__ import annotations

import os
import re
import datetime
from collections import defaultdict
from dataclasses import dataclass
from typing import List, Tuple, Dict, Optional, Any, Callable
from PyQt6.QtCore import QThread, pyqtSignal

from .logger_util import get_logger
log = get_logger()

# Import unified utilities from file_utilities module
from .file_utilities import (
    is_media_file, get_safe_target_path, validate_path_length, safe_rename, is_case_variant,
    SIDECAR_EXTENSIONS, find_sidecars, sidecar_target,
)

# Import timestamp operations from exif_processor (the only remaining use)
from .exif_processor import batch_sync_exif_dates
from .filename_components import build_named_components, compose_filename, resolve_metadata_flags
from .exif_undo_manager import batch_write_original_filenames
from .exif_service_new import ExifService
from . import backup_journal

# SIDECAR_EXTENSIONS is re-exported for callers of this module
__all__ = ["RenamePlanner", "RenameWorkerThread", "PlanEntry", "PlanningCancelled", "SIDECAR_EXTENSIONS"]


def _last_number(path: str) -> int:
    """Last number in the file name (the camera's sequence number, not the year)."""
    numbers = re.findall(r'(\d+)', os.path.basename(path))
    return int(numbers[-1]) if numbers else 0


def _mtime_or_zero(path: str) -> float:
    try:
        return os.path.getmtime(path)
    except OSError:
        return 0.0


def _date_from_filename(path: str) -> Optional[str]:
    m = re.search(r'(20\d{2})(\d{2})(\d{2})', os.path.basename(path))
    return f"{m.group(1)}{m.group(2)}{m.group(3)}" if m else None


def _date_from_mtime(path: str) -> Optional[str]:
    try:
        return datetime.datetime.fromtimestamp(os.path.getmtime(path)).strftime('%Y%m%d')
    except (OSError, OverflowError, ValueError):
        return None


class PlanningCancelled(Exception):
    """Raised by the planner when the user cancels."""


@dataclass
class PlanEntry:
    """One planned rename."""
    source: str
    target: str
    sidecar: bool = False
    main_source: str = ""  # for sidecars: the photo they belong to
    note: str = ""         # e.g. why the name differs from the pattern

    @property
    def changed(self) -> bool:
        return os.path.normpath(self.source) != os.path.normpath(self.target)


def cache_entry_from_raw(meta: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Parse the fields the planner needs from one file's raw ExifTool metadata."""
    if not meta:
        return None
    return {
        'date_str': ExifService.parse_date_from_raw(meta),
        'camera': ExifService.parse_camera_from_raw(meta),
        'lens': ExifService.parse_lens_from_raw(meta),
        'raw_meta': meta,
        'all_metadata': ExifService.parse_all_metadata_from_raw(meta),
    }


class RenamePlanner:
    """Compute new file names for a batch without modifying anything."""

    def __init__(
        self,
        files: List[str],
        *,
        camera_prefix: str = "",
        additional: str = "",
        use_camera: bool = False,
        use_lens: bool = False,
        use_date: bool = True,
        date_format: str = "YYYY-MM-DD",
        separator: str = "-",
        custom_order: Optional[List[str]] = None,
        continuous_counter: bool = False,
        selected_metadata: Optional[Dict[str, Any]] = None,
        exif_method: Optional[str] = None,
        exif_service: Optional[Any] = None,
        exiftool_path: Optional[str] = None,
        rename_sidecars: bool = False,
        progress: Optional[Callable[[str], None]] = None,
        progress_value: Optional[Callable[[int, int], None]] = None,
        is_cancelled: Optional[Callable[[], bool]] = None,
    ) -> None:
        self.files = files
        self.camera_prefix = camera_prefix
        self.additional = additional
        self.use_camera = use_camera
        self.use_lens = use_lens
        self.use_date = use_date
        self.date_format = date_format
        self.separator = separator
        self.custom_order = custom_order or []
        self.continuous_counter = continuous_counter
        self.selected_metadata = selected_metadata or {}
        self.exif_method = exif_method
        self.exif_service = exif_service
        self.exiftool_path = exiftool_path
        self.rename_sidecars = rename_sidecars
        self._progress = progress or (lambda msg: None)
        self._progress_value = progress_value or (lambda done, total: None)
        self._is_cancelled = is_cancelled or (lambda: False)
        self.continuous_counter_map: Optional[Dict[str, int]] = None
        self._continuous_raw_cache: Dict[str, Dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # Grouping and metadata
    # ------------------------------------------------------------------

    def create_file_groups(self) -> List[List[str]]:
        """
        Group RAW/JPEG siblings (same basename in same directory).

        Files with the same basename but different extensions (e.g., IMG_001.JPG
        and IMG_001.ARW) are grouped together for synchronized renaming.

        Returns:
            List of file groups, where each group is a list of related file paths
        """
        basename_groups = defaultdict(list)
        for path in self.files:
            if is_media_file(path):
                directory = os.path.dirname(path)
                stem = os.path.splitext(os.path.basename(path))[0]
                basename_groups[f"{directory}#{stem}"].append(path)

        file_groups = []
        orphans = []
        for group in basename_groups.values():
            if len(group) > 1:
                file_groups.append(group)
            else:
                orphans.extend(group)

        for f in orphans:
            file_groups.append([f])

        return file_groups

    def pre_extract_exif_cache(self, file_groups: List[List[str]]) -> Dict[str, Optional[Dict[str, Any]]]:
        """
        Pre-extract EXIF data for all files in batched ExifTool calls.

        Uses ExifService.batch_get_raw_metadata() to issue a single ExifTool
        IPC call per chunk of ~50 files instead of one call per file.

        Returns:
            Cache dictionary mapping file_path to the dict of
            :func:`cache_entry_from_raw` (or None if nothing could be read).
        """
        exif_cache: Dict[str, Optional[Dict[str, Any]]] = {}
        if not self.exif_method or not self.exif_service:
            return exif_cache

        paths = [path for group in file_groups for path in group]
        if not paths:
            return exif_cache

        self._progress("Reading metadata...")
        # Reuse the raw metadata the continuous counter map already fetched
        raw = dict(self._continuous_raw_cache)
        remaining = [p for p in paths if p not in raw]
        if remaining:
            self._progress(f"Batch-extracting EXIF for {len(remaining)} files...")
            raw.update(self.exif_service.batch_get_raw_metadata(remaining, chunk_size=50))

        for path in paths:
            exif_cache[path] = cache_entry_from_raw(raw.get(path))
        return exif_cache

    @staticmethod
    def capture_timestamp(path: str, raw_meta: Optional[Dict[str, Any]]) -> float:
        """Capture time as a POSIX timestamp (EXIF/QuickTime, else mtime).

        A float rather than a datetime: naive (EXIF) and zone-aware
        (QuickTime) datetimes cannot be compared with each other.
        """
        dt = ExifService.parse_datetime_from_raw(raw_meta) if raw_meta else None
        if dt is not None:
            try:
                return dt.timestamp()
            except (OverflowError, OSError, ValueError):
                pass
        return _mtime_or_zero(path)

    def exif_sort_key(self, group: List[str], exif_cache: Dict[str, Optional[Dict[str, Any]]]) -> Tuple[float, int, str]:
        """Sort key for chronological order: capture time, sequence number, path."""
        first_file = group[0]
        raw_meta = (exif_cache.get(first_file) or {}).get('raw_meta')
        return (self.capture_timestamp(first_file, raw_meta), _last_number(first_file), first_file)

    def _selective_exif(self, path, need_date, need_camera, need_lens):
        """Per-file fallback when a file is missing from the batch cache."""
        if not (self.exif_method and self.exif_service):
            return None, None, None
        try:
            return self.exif_service.get_selective_cached_exif_data(
                path, self.exif_method, self.exiftool_path,
                need_date=need_date, need_camera=need_camera, need_lens=need_lens,
            )
        except Exception as e:
            log.debug(f"Per-file EXIF fallback failed for {path}: {e}")
            return None, None, None

    def create_continuous_counter_map(self) -> Dict[str, int]:
        """
        Map each file to a continuous counter number in chronological order.

        File pairs (JPG+RAW) share the same number.
        """
        if self.continuous_counter_map is not None:
            return self.continuous_counter_map

        self._progress("Creating continuous counter map...")
        file_groups = self.create_file_groups()
        first_files = [group[0] for group in file_groups]

        date_by_file: Dict[str, Optional[str]] = {}
        raw_batch: Dict[str, Dict[str, Any]] = {}
        if self.exif_service and self.exif_method and first_files:
            raw_batch = self.exif_service.batch_get_raw_metadata(first_files, chunk_size=50)
            # Save raw metadata for reuse by pre_extract_exif_cache
            self._continuous_raw_cache = raw_batch
            for fp, meta in raw_batch.items():
                date_by_file[fp] = ExifService.parse_date_from_raw(meta) if meta else None

        date_group_pairs = []
        for group in file_groups:
            first_file = group[0]
            file_date = date_by_file.get(first_file)
            # Per-file fallback when the batch didn't run or returned nothing
            if file_date is None and first_file not in date_by_file:
                file_date = self._selective_exif(first_file, True, False, False)[0]
            file_date = (file_date or _date_from_filename(first_file)
                         or _date_from_mtime(first_file) or '19700101')
            date_group_pairs.append((file_date, group))

        # Sort by date, then capture time (mtime fallback), then the camera's
        # sequence number. Every key has the same element types, so equal
        # dates and times never end up comparing an int with a str.
        date_group_pairs.sort(key=lambda pair: (
            pair[0],
            self.capture_timestamp(pair[1][0], raw_batch.get(pair[1][0])),
            _last_number(pair[1][0]),
            pair[1][0],
        ))
        counter_map: Dict[str, int] = {}
        for number, (_date, group) in enumerate(date_group_pairs, start=1):
            for file in group:
                counter_map[file] = number
        self.continuous_counter_map = counter_map
        return counter_map

    # ------------------------------------------------------------------
    # Names
    # ------------------------------------------------------------------

    def resolve_safe_target(self, original_path: str, new_name: str, reserved_targets: set[str]) -> str:
        """Resolve a conflict-free target considering disk and already planned targets.

        Wraps :func:`get_safe_target_path` (which performs security checks) and
        additionally checks against *reserved_targets* — paths planned for an
        earlier file but not yet on disk.
        """
        target = get_safe_target_path(original_path, new_name)

        # If target is the source file itself, no conflict is possible
        if os.path.normcase(target) == os.path.normcase(original_path):
            return target

        # If not reserved by another planned rename, we're good
        if os.path.normcase(target) not in reserved_targets:
            return target

        # Conflict with a reserved (but not yet on-disk) target — find alternative
        directory = os.path.dirname(target)
        name, ext = os.path.splitext(os.path.basename(target))
        for attempt in range(1, 1000):
            alt_path = os.path.join(directory, f"{name}({attempt}){ext}")
            if not os.path.exists(alt_path) and os.path.normcase(alt_path) not in reserved_targets:
                return alt_path
        raise RuntimeError(f"Cannot generate unique filename for {new_name}")

    def group_values(
        self, group: List[str], exif_cache: Dict[str, Optional[Dict[str, Any]]]
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Date (YYYYMMDD), camera and lens shared by a group, with fallbacks."""
        need_date, need_camera, need_lens = self.use_date, self.use_camera, self.use_lens
        date_taken = camera_model = lens_model = None
        first_file = group[0]

        if exif_cache.get(first_file):
            for path in group:
                entry = exif_cache.get(path)
                if not entry:
                    continue
                if need_date and not date_taken:
                    date_taken = entry.get('date_str')
                if need_camera and not camera_model:
                    camera_model = entry.get('camera')
                if need_lens and not lens_model:
                    lens_model = entry.get('lens')
        elif any([need_date, need_camera, need_lens]):
            date_taken, camera_model, lens_model = self._selective_exif(
                first_file, need_date, need_camera, need_lens
            )

        if need_date and not date_taken:
            for p in group:
                date_taken = _date_from_filename(p)
                if date_taken:
                    break
            date_taken = date_taken or _date_from_mtime(first_file) or '19700101'
        if need_camera and not camera_model:
            camera_model = 'Unknown-Camera'
        if need_lens and not lens_model:
            lens_model = 'Unknown-Lens'
        return date_taken, camera_model, lens_model

    def _group_number(self, first_file: str, date_taken: Optional[str], date_counter: Dict[str, int]) -> int:
        if self.use_date and self.continuous_counter and self.continuous_counter_map is not None:
            return self.continuous_counter_map.get(first_file, 1)
        key = (date_taken or 'unknown') if (self.use_date and not self.continuous_counter) else 'all_files'
        date_counter[key] = date_counter.get(key, 0) + 1
        return date_counter[key]

    def file_components(
        self,
        path: str,
        first_file: str,
        exif_cache: Dict[str, Optional[Dict[str, Any]]],
        group_date: Optional[str],
        group_camera: Optional[str],
        group_lens: Optional[str],
        number: int,
    ) -> List[Tuple[str, str]]:
        """Ordered ``(component_id, text)`` pairs of one file's new name."""
        need_date, need_camera, need_lens = self.use_date, self.use_camera, self.use_lens
        file_date, file_cam, file_lens = group_date, group_camera, group_lens

        # Per-file values (e.g. a RAW and a JPG with slightly different data)
        entry = exif_cache.get(path)
        if entry:
            if need_date and entry.get('date_str'):
                file_date = entry['date_str']
            if need_camera and entry.get('camera'):
                file_cam = entry['camera']
            if need_lens and entry.get('lens'):
                file_lens = entry['lens']
        elif path != first_file and any([need_date, need_camera, need_lens]):
            # Secondary file missing from the batch cache: ask ExifTool directly
            d, c, l = self._selective_exif(path, need_date, need_camera, need_lens)
            file_date = d if (need_date and d) else file_date
            file_cam = c if (need_camera and c) else file_cam
            file_lens = l if (need_lens and l) else file_lens

        # Shooting settings flagged in selected_metadata are read per file
        metadata = dict(self.selected_metadata)
        if any(value is True for value in metadata.values()):
            all_meta = None
            if self.exif_method:
                source = exif_cache.get(path) or exif_cache.get(first_file)
                if source:
                    all_meta = source.get('all_metadata') or ExifService.parse_all_metadata_from_raw(
                        source.get('raw_meta') or {}
                    )
                elif self.exif_service:
                    try:
                        all_meta = self.exif_service.get_all_metadata(path, self.exif_method, self.exiftool_path)
                    except Exception:
                        all_meta = None
            metadata = resolve_metadata_flags(metadata, all_meta)

        return build_named_components(
            date_taken=file_date,
            camera_prefix=self.camera_prefix,
            additional=self.additional,
            camera_model=file_cam,
            lens_model=file_lens,
            use_camera=self.use_camera,
            use_lens=self.use_lens,
            number=number,
            custom_order=self.custom_order,
            date_format=self.date_format,
            use_date=self.use_date,
            selected_metadata=metadata,
        )

    def new_name_for(self, path: str, components: List[Tuple[str, str]]) -> str:
        return compose_filename([text for _id, text in components], self.separator, os.path.splitext(path)[1])

    def plan_file_group(
        self,
        group: List[str],
        date_counter: Dict[str, int],
        exif_cache: Dict[str, Optional[Dict[str, Any]]],
        reserved_targets: set[str],
    ) -> Tuple[List[PlanEntry], List[Tuple[str, str]]]:
        """
        Compute the rename plan for one file group **without** moving files.

        Conflict resolution accounts for both on-disk files and targets
        already reserved by earlier groups.

        Returns:
            (plan entries, list of (file_path, error_message))
        """
        plan_entries: List[PlanEntry] = []
        errors: List[Tuple[str, str]] = []

        group_existing = [p for p in group if os.path.exists(p)]
        if not group_existing:
            return plan_entries, errors

        first_file = group_existing[0]
        date_taken, camera_model, lens_model = self.group_values(group_existing, exif_cache)
        number = self._group_number(first_file, date_taken, date_counter)

        for path in group_existing:
            try:
                components = self.file_components(
                    path, first_file, exif_cache, date_taken, camera_model, lens_model, number
                )
                new_name = self.new_name_for(path, components)
                target_path = self.resolve_safe_target(path, new_name, reserved_targets)

                if not validate_path_length(target_path):
                    errors.append((path, f"Target path too long: {len(target_path)} chars"))
                    continue

                note = ""
                if os.path.basename(target_path) != new_name:
                    note = f"'{new_name}' already exists - number added"
                plan_entries.append(PlanEntry(path, target_path, note=note))
                reserved_targets.add(os.path.normcase(target_path))
            except Exception as e:
                errors.append((path, str(e)))

        return plan_entries, errors

    def plan_sidecars(
        self, entries: List[PlanEntry], reserved_targets: set[str]
    ) -> Tuple[List[PlanEntry], List[Tuple[str, str]]]:
        """Plan renames of sidecar files that belong to the planned photos.

        Supports ``<name>.<ext>.xmp`` (darktable, RawTherapee, DxO) and
        ``<stem>.xmp`` (Lightroom, Apple .aae, Canon .thm) naming. A sidecar
        whose new name is taken is left alone (with a warning) - a "(1)"
        suffix would detach it from its photo.
        """
        sidecars: List[PlanEntry] = []
        errors: List[Tuple[str, str]] = []
        loaded = {os.path.normcase(os.path.abspath(p)) for p in self.files}
        listings: Dict[str, Dict[str, str]] = {}
        claimed: set[str] = set()

        def listing(directory):
            if directory not in listings:
                try:
                    listings[directory] = {name.lower(): name for name in os.listdir(directory or '.')}
                except OSError:
                    listings[directory] = {}
            return listings[directory]

        for entry in entries:
            if not entry.changed:
                continue
            directory = os.path.dirname(entry.source)
            source_name = os.path.basename(entry.source)
            for sidecar_path, kind, suffix in find_sidecars(entry.source, listing(directory)):
                key = os.path.normcase(os.path.abspath(sidecar_path))
                if key in claimed or key in loaded:
                    continue
                claimed.add(key)
                new_path = sidecar_target(entry.target, kind, suffix)
                taken = (
                    os.path.normcase(new_path) in reserved_targets
                    or (os.path.lexists(new_path) and not is_case_variant(sidecar_path, new_path)
                        and os.path.normcase(new_path) != os.path.normcase(sidecar_path))
                )
                if taken:
                    errors.append((sidecar_path,
                                   f"Sidecar not renamed: '{os.path.basename(new_path)}' already exists"))
                    continue
                reserved_targets.add(os.path.normcase(new_path))
                sidecars.append(PlanEntry(
                    sidecar_path, new_path, sidecar=True, main_source=entry.source,
                    note=f"sidecar of {source_name}",
                ))
        return sidecars, errors

    def build_plan(self) -> Tuple[List[PlanEntry], List[Tuple[str, str]]]:
        """Compute the complete rename plan.

        Raises:
            PlanningCancelled: if ``is_cancelled`` returns True.
        """
        if self.use_date and self.continuous_counter:
            self.create_continuous_counter_map()

        file_groups = self.create_file_groups()
        self._progress(f"Processing {len(file_groups)} file groups...")
        exif_cache = self.pre_extract_exif_cache(file_groups)

        self._progress("Sorting files by capture time...")
        file_groups.sort(key=lambda g: self.exif_sort_key(g, exif_cache))

        entries: List[PlanEntry] = []
        errors: List[Tuple[str, str]] = []
        date_counter: Dict[str, int] = {}
        reserved_targets: set[str] = set()
        total = len(file_groups)
        for idx, group in enumerate(file_groups):
            if self._is_cancelled():
                raise PlanningCancelled()
            if idx % 50 == 0:
                self._progress(f"Planning group {idx + 1}/{total}")
                self._progress_value(idx, total)
            group_plan, group_errors = self.plan_file_group(group, date_counter, exif_cache, reserved_targets)
            entries.extend(group_plan)
            errors.extend(group_errors)
        self._progress_value(total, total)

        if self.rename_sidecars:
            sidecar_entries, sidecar_errors = self.plan_sidecars(entries, reserved_targets)
            entries.extend(sidecar_entries)
            errors.extend(sidecar_errors)

        self._progress(f"Plan complete: {len(entries)} files, {len(errors)} problems")
        return entries, errors

    def preview(self, path: str, raw_meta: Optional[Dict[str, Any]]) -> Tuple[List[Tuple[str, str]], str]:
        """Components and new name of *path* as the first file of a batch.

        Used by the interactive preview; *path* doesn't have to exist (the
        sample shown before files are loaded).
        """
        exif_cache = {path: cache_entry_from_raw(raw_meta)} if self.exif_method else {}
        date_taken, camera_model, lens_model = self.group_values([path], exif_cache)
        components = self.file_components(path, path, exif_cache, date_taken, camera_model, lens_model, 1)
        return components, self.new_name_for(path, components)


class RenameWorkerThread(QThread):
    """Worker thread for file renaming & optional EXIF timestamp sync.

    ``mode``:
        ``"plan"``    - only compute the plan, emit ``plan_ready``
        ``"execute"`` - run the sync and execute ``plan``, emit ``finished``
        ``"full"``    - plan and execute in one go (default)
    """
    progress_update = pyqtSignal(str)
    progress_value = pyqtSignal(int, int)  # done, total
    plan_ready = pyqtSignal(list, list)  # plan entries, errors
    finished = pyqtSignal(list, list, dict, dict)  # renamed_files, errors, timestamp_backup, rename_mapping
    error = pyqtSignal(str)

    def __init__(
        self,
        files: List[str],
        camera_prefix: str,
        additional: str,
        use_camera: bool,
        use_lens: bool,
        exif_method: str,
        separator: str,
        exiftool_path: Optional[str],
        custom_order: List[str],
        date_format: str,
        use_date: bool,
        continuous_counter: bool,
        selected_metadata: Dict[str, Any],
        sync_exif_date: bool,
        parent: Optional[QThread] = None,
        log_callable: Optional[Callable] = None,
        exif_service: Optional[Any] = None,
        save_original_to_exif: bool = False,
        **kwargs: Any,
    ) -> None:
        super().__init__(parent)
        self.files = files
        self.exif_method = exif_method
        self.exiftool_path = exiftool_path
        self.exif_service = exif_service
        self.sync_exif_date = sync_exif_date
        self._log = log_callable or (lambda *a, **k: None)
        self.save_original_to_exif = save_original_to_exif  # Persistent undo feature
        self.timestamp_options = kwargs.get('timestamp_options') or kwargs.get('TIMESTAMP_OPTIONS')
        self.leave_names = kwargs.get('leave_names', False)
        # {current_path: original_basename} from earlier renames, so a
        # second rename still remembers the name before the first one.
        self.prior_originals: Dict[str, str] = dict(kwargs.get('prior_originals') or {})
        self.mode: str = kwargs.get('mode', 'full')
        self.plan: List[PlanEntry] = list(kwargs.get('plan') or [])
        self.plan_errors: List[Tuple[str, str]] = list(kwargs.get('plan_errors') or [])
        self.was_cancelled = False
        self.planner = RenamePlanner(
            files,
            camera_prefix=camera_prefix,
            additional=additional,
            use_camera=use_camera,
            use_lens=use_lens,
            use_date=use_date,
            date_format=date_format,
            separator=separator,
            custom_order=custom_order,
            continuous_counter=continuous_counter,
            selected_metadata=selected_metadata,
            exif_method=exif_method,
            exif_service=exif_service,
            exiftool_path=exiftool_path,
            rename_sidecars=kwargs.get('rename_sidecars', False),
            progress=self.progress_update.emit,
            progress_value=self.progress_value.emit,
            is_cancelled=self.isInterruptionRequested,
        )

    def _original_name_of(self, path: str) -> str:
        return self.prior_originals.get(path, os.path.basename(path))

    def _debug(self, msg: str) -> None:
        try:
            self._log(msg)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Steps
    # ------------------------------------------------------------------

    def _sync_exif_timestamps(self) -> Tuple[List[Any], List[Tuple[str, str]], Dict[str, Any]]:
        """Sync EXIF capture dates to file timestamps (optional first step).

        Returns:
            (successes, errors as (file_path, message), timestamp backup)
        """
        if not self.sync_exif_date:
            return [], [], {}

        self.progress_update.emit("Synchronizing EXIF dates to file timestamps...")
        media_files = [f for f in self.files if is_media_file(f)]

        successes, sync_errors, timestamp_backup = batch_sync_exif_dates(
            media_files,
            self.exiftool_path if self.exiftool_path else None,
            lambda msg: self.progress_update.emit(f"Date sync: {msg}"),
            options=self.timestamp_options,
        )

        if successes:
            self.progress_update.emit(f"Successfully synced dates for {len(successes)} files")
        if sync_errors:
            self.progress_update.emit(f"Failed to sync dates for {len(sync_errors)} files")

        return successes, sync_errors, timestamp_backup

    def build_plan(self) -> Tuple[List[PlanEntry], List[Tuple[str, str]]]:
        return self.planner.build_plan()

    def execute_plan(self, entries: List[PlanEntry]) -> Tuple[List[str], List[Tuple[str, str]], Dict[str, str]]:
        """Execute a rename plan.

        The plan is journaled *before* any file is touched, so a crash or
        kill mid-way still leaves enough on disk to undo every rename that
        did happen. Stops between files if interruption is requested.

        Returns:
            (renamed photo paths, errors, {new_path: old_path} incl. sidecars)
        """
        renamed_files: List[str] = []
        errors: List[Tuple[str, str]] = []
        rename_mapping: Dict[str, str] = {}

        planned_moves = [e for e in entries if e.changed]
        if planned_moves:
            backup_journal.update_entries({
                "original_filenames": {
                    "set": {e.target: self._original_name_of(e.source) for e in planned_moves},
                },
            })

        moved: Dict[str, str] = {}
        total = len(entries)
        for idx, entry in enumerate(entries):
            if self.isInterruptionRequested():
                remaining = sum(1 for e in entries[idx:] if e.changed and not e.sidecar)
                errors.append(("", f"Cancelled - {remaining} file(s) not renamed"))
                self.was_cancelled = True
                break
            if idx % 20 == 0:
                self.progress_value.emit(idx, total)
                self.progress_update.emit(f"Renaming {idx + 1}/{total}")

            if entry.sidecar and entry.main_source not in moved:
                errors.append((entry.source, "Sidecar not renamed because its photo was not renamed"))
                continue
            if not entry.changed:
                if not entry.sidecar:
                    renamed_files.append(entry.source)
                    rename_mapping[entry.source] = entry.source
                continue
            try:
                safe_rename(entry.source, entry.target)
                moved[entry.source] = entry.target
                rename_mapping[entry.target] = entry.source
                if not entry.sidecar:
                    renamed_files.append(entry.target)
            except Exception as e:
                errors.append((entry.source, str(e)))
        self.progress_value.emit(total, total)

        # Settle the journal: renamed files are tracked under their new path
        # only, planned-but-not-done renames are dropped, and backups of
        # timestamps/EXIF follow the file.
        if planned_moves:
            not_done = [e.target for e in planned_moves if e.source not in moved]
            backup_journal.update_entries({
                "original_filenames": {"remove": list(moved) + not_done},
            })
            backup_journal.rekey_journal(moved)

        # Write original filenames into the renamed photos (one batched
        # ExifTool process per chunk, after all renames are complete).
        main_moves = [e for e in planned_moves if not e.sidecar and e.source in moved]
        if self.save_original_to_exif and self.exiftool_path and main_moves:
            exif_write_pairs = [(e.target, self._original_name_of(e.source)) for e in main_moves]
            self.progress_update.emit(f"Writing original filenames to metadata for {len(exif_write_pairs)} files...")
            successes_exif, errors_exif = batch_write_original_filenames(
                exif_write_pairs,
                self.exiftool_path,
                progress_callback=lambda cur, tot, msg: self.progress_update.emit(
                    f"Metadata write: {cur}/{tot}"
                ),
            )
            for fp, msg in errors_exif:
                errors.append((fp, f"Renamed, but original name not saved to metadata: {msg}"))
            if successes_exif:
                self.progress_update.emit(f"Wrote original filenames to {len(successes_exif)} files")

        return renamed_files, errors, rename_mapping

    def _sync_then_execute(self, entries: List[PlanEntry], plan_errors: List[Tuple[str, str]]):
        _successes, sync_errors, timestamp_backup = self._sync_exif_timestamps()
        if self.leave_names:
            # Only syncing timestamps
            return [], list(sync_errors), timestamp_backup, {}
        renamed_files, exec_errors, rename_mapping = self.execute_plan(entries)
        errors = [(path, f"Timestamp sync: {msg}") for path, msg in sync_errors]
        errors += list(plan_errors) + exec_errors
        return renamed_files, errors, timestamp_backup, rename_mapping

    def optimized_rename_files(self) -> Tuple[List[str], List[Tuple[str, str]], Dict[str, Any], Dict[str, str]]:
        """
        Plan and execute in one go (optional timestamp sync first).

        Returns:
            Tuple containing:
                - renamed_files: List of successfully renamed file paths
                - errors: List of (file_path, error_message) tuples
                - timestamp_backup: Dictionary of original timestamps for undo
                - rename_mapping: Dict of {new_path: old_path} for reliable undo
        """
        _successes, sync_errors, timestamp_backup = self._sync_exif_timestamps()
        if self.leave_names:
            return [], list(sync_errors), timestamp_backup, {}
        entries, plan_errors = self.build_plan()
        renamed_files, exec_errors, rename_mapping = self.execute_plan(entries)
        errors = [(path, f"Timestamp sync: {msg}") for path, msg in sync_errors]
        errors += plan_errors + exec_errors
        return renamed_files, errors, timestamp_backup, rename_mapping

    def run(self) -> None:
        """Run the selected mode in the background thread."""
        self._debug(f"Rename thread ({self.mode}) with {len(self.files)} files")
        try:
            if self.mode == 'plan':
                try:
                    entries, errors = self.build_plan()
                except PlanningCancelled:
                    self.was_cancelled = True
                    entries, errors = [], []
                self.plan_ready.emit(entries, errors)
            elif self.mode == 'execute':
                self.finished.emit(*self._sync_then_execute(self.plan, self.plan_errors))
            else:
                self.finished.emit(*self.optimized_rename_files())
        except Exception as e:
            self.error.emit(str(e))
