#!/usr/bin/env python3
"""Unified filename component builder.

Provides a single source of truth for assembling ordered filename parts
(including flexible position of the sequential number and EXIF-derived metadata components).
"""
from __future__ import annotations
import re
from typing import List, Dict, Optional, Tuple

# Public API
__all__ = [
    "build_named_components", "build_ordered_components",
    "resolve_metadata_flags", "compose_filename",
]

FORBIDDEN_CHARS_PATTERN = re.compile(r'[<>:"/\\|?*]')
WHITESPACE_PATTERN = re.compile(r'\s+')

# Metadata keys that can appear as boolean flags meaning: value must be resolved later
BOOLEAN_META_KEYS = {"iso", "aperture", "focal_length", "shutter", "shutter_speed", "resolution"}


def _format_date(raw: Optional[str], fmt: str) -> Optional[str]:
    if not raw or len(raw) < 8:
        return None
    y, m, d = raw[:4], raw[4:6], raw[6:8]
    return {
        "YYYY-MM-DD": f"{y}-{m}-{d}",
        "YYYY_MM_DD": f"{y}_{m}_{d}",
        "DD-MM-YYYY": f"{d}-{m}-{y}",
        "DD_MM_YYYY": f"{d}_{m}_{y}",
        "YYYYMMDD": f"{y}{m}{d}",
        "MM-DD-YYYY": f"{m}-{d}-{y}",
        "MM_DD_YYYY": f"{m}_{d}_{y}",
    }.get(fmt, f"{y}-{m}-{d}")


def _sanitize_component(value: str) -> str:
    # Remove forbidden chars, collapse whitespace, keep safe set
    value = FORBIDDEN_CHARS_PATTERN.sub('', value)
    value = WHITESPACE_PATTERN.sub('_', value.strip())
    return value


def _format_metadata(key: str, value) -> Optional[str]:
    if value is None or value == '' or value == 'Unknown':
        return None
    if isinstance(value, bool):  # unresolved flag
        return None
    s = str(value)
    if key == 'camera':
        s = s.replace(' ', '-').replace('/', '-')
    elif key == 'lens':
        s = s.replace(' ', '-').replace('/', '-')
    elif key == 'date':
        s = s.split(' ')[0].replace(':', '-')
    elif key == 'iso':
        s = f"ISO{s}" if s.isdigit() else s.replace(' ', '')
    elif key == 'aperture':
        if s.startswith('f/'):
            s = s.replace('f/', 'f')
        elif not s.startswith('f'):
            s = f"f{s}"
    elif key in ('shutter', 'shutter_speed'):
        s = s.replace('/', '_').replace(' ', '')
        if s.endswith('ss') and not s.endswith('sss'):
            s = s[:-1]
    elif key == 'focal_length':
        m = re.search(r'(\d+)mm', s)
        if m:
            s = f"{m.group(1)}mm"
        s = s.replace(' ', '-')
    elif key == 'resolution':
        if 'MP' in s and '(' in s:
            inner = s.split('(')[1].split(')')[0]
            s = inner.replace(' ', '').replace('.', '-')
        else:
            s = s.replace(' ', '-')
    else:
        s = s.replace(' ', '-').replace('/', '-').replace(':', '-')
    return _sanitize_component(s)


def resolve_metadata_flags(
    selected_metadata: Optional[Dict[str, object]],
    all_metadata: Optional[Dict[str, object]],
) -> Dict[str, object]:
    """Replace ``True`` flags ("read this field from the file") with the file's values.

    ``selected_metadata`` holds ``True`` for per-file fields such as ISO or
    aperture; ``all_metadata`` is ``ExifService.parse_all_metadata_from_raw``
    of one file. Flags the file has no value for are dropped. Shared by the
    rename engine and the preview so both produce the same names.
    """
    resolved: Dict[str, object] = {}
    for key, value in (selected_metadata or {}).items():
        if value is True:
            source_key = 'shutter_speed' if key == 'shutter' else key
            file_value = (all_metadata or {}).get(source_key)
            if file_value:
                resolved[key] = file_value
        else:
            resolved[key] = value
    return resolved


def build_named_components(
    *,
    date_taken: Optional[str],
    camera_prefix: Optional[str],
    additional: Optional[str],
    camera_model: Optional[str],
    lens_model: Optional[str],
    use_camera: bool,
    use_lens: bool,
    number: int,
    custom_order: List[str],
    date_format: str = "YYYY-MM-DD",
    use_date: bool = True,
    selected_metadata: Optional[Dict[str, object]] = None,
) -> List[Tuple[str, str]]:
    """Return ordered, sanitized ``(component_id, text)`` pairs.

    Component ids are the names used in ``custom_order``: Date, Prefix,
    Additional, Camera, Lens, Number and ``Meta_<key>`` for metadata fields.
    Metadata flags (True) are ignored until resolved (see
    ``resolve_metadata_flags``).
    """
    formatted_date = _format_date(date_taken, date_format) if (use_date and date_taken) else None

    has_cam_meta = selected_metadata and 'camera' in selected_metadata
    has_lens_meta = selected_metadata and 'lens' in selected_metadata

    base = {
        'Date': formatted_date,
        'Prefix': camera_prefix or None,
        'Additional': additional or None,
        'Camera': camera_model if (use_camera and camera_model and not has_cam_meta) else None,
        'Lens': lens_model if (use_lens and lens_model and not has_lens_meta) else None,
        'Number': f"{number:03d}",
    }

    parts: List[Tuple[str, str]] = []

    def add(component_id: str, value: Optional[str]):
        if value:
            text = _sanitize_component(value)
            if text:
                parts.append((component_id, text))

    for name in custom_order:
        if name in base:
            add(name, base[name])
        elif name.startswith('Meta_') and selected_metadata:
            raw_key = name[5:]
            if raw_key in selected_metadata:
                add(name, _format_metadata(raw_key, selected_metadata[raw_key]))

    # Fallback: append any metadata not explicitly ordered (only if no Meta_ present)
    if selected_metadata:
        has_explicit = any(c.startswith('Meta_') for c in custom_order)
        if not has_explicit:
            for k, v in selected_metadata.items():
                add(f"Meta_{k}", _format_metadata(k, v))

    # If Number not explicitly ordered, append at end
    if 'Number' not in custom_order:
        add('Number', base['Number'])
    return parts


def build_ordered_components(**kwargs) -> List[str]:
    """Return ordered, sanitized components (without joining / separator).

    Same arguments as :func:`build_named_components`, without the ids.
    """
    return [text for _component_id, text in build_named_components(**kwargs)]


def compose_filename(parts: List[str], separator: str, extension: str) -> str:
    """Join components with the separator ("None" = no separator) and sanitize."""
    from .file_utilities import sanitize_final_filename

    sep = '' if separator in (None, 'None') else separator
    return sanitize_final_filename(sep.join(parts) + extension)
