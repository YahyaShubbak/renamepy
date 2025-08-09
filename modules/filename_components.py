#!/usr/bin/env python3
"""Unified filename component builder.

Provides a single source of truth for assembling ordered filename parts
(including flexible position of the sequential number and EXIF-derived metadata components).
"""
from __future__ import annotations
import re
from typing import List, Dict, Optional

# Public API
__all__ = ["build_ordered_components"]

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


def build_ordered_components(
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
) -> List[str]:
    """Return ordered, sanitized components (without joining / separator).
    custom_order may include base names (Date, Prefix, Additional, Camera, Lens, Number)
    and dynamic metadata entries (Meta_<key>). Metadata flags (True) are ignored until resolved.
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

    parts: List[str] = []

    def add(value: Optional[str]):
        if value:
            parts.append(_sanitize_component(value))

    for name in custom_order:
        if name in base:
            add(base[name])
        elif name.startswith('Meta_') and selected_metadata:
            raw_key = name[5:]
            if raw_key in selected_metadata:
                formatted = _format_metadata(raw_key, selected_metadata[raw_key])
                if formatted:
                    add(formatted)

    # Fallback: append any metadata not explicitly ordered (only if no Meta_ present)
    if selected_metadata:
        has_explicit = any(c.startswith('Meta_') for c in custom_order)
        if not has_explicit:
            for k, v in selected_metadata.items():
                formatted = _format_metadata(k, v)
                if formatted:
                    add(formatted)

    # If Number not explicitly ordered, append at end
    if 'Number' not in custom_order:
        add(base['Number'])
    return parts
