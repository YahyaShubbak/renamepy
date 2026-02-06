"""
UI Helper Utilities - Common utility functions for UI operations
Extracted from main_application.py to reduce clutter
"""

import os
from ..file_utilities import is_video_file as _is_video_file_canonical


def calculate_stats(files):
    """
    Calculate simple file statistics
    
    Args:
        files: List of file paths
        
    Returns:
        dict: Statistics including total_files, jpeg_count, raw_count, video_count, etc.
    """
    total = len(files)
    
    # Count different file types
    jpeg_count = sum(1 for f in files if f.lower().endswith(('.jpg', '.jpeg')))
    raw_count = sum(1 for f in files if any(
        f.lower().endswith(ext) for ext in [
            '.cr2', '.nef', '.arw', '.orf', '.rw2', '.dng', '.raw', 
            '.sr2', '.pef', '.raf', '.3fr', '.erf', '.kdc', '.mos', 
            '.nrw', '.srw', '.x3f'
        ]
    ))
    other_images = sum(1 for f in files if any(
        f.lower().endswith(ext) for ext in ['.png', '.bmp', '.tiff', '.tif', '.gif']
    ))
    total_images = jpeg_count + raw_count + other_images
    videos = total - total_images
    
    return {
        'total_files': total,
        'total_images': total_images,
        'jpeg_count': jpeg_count,
        'raw_count': raw_count,
        'video_count': videos,
        'total': total,
        'images': total_images, 
        'videos': videos
    }


def is_video_file(file_path: str) -> bool:
    """Check if file is a video file.

    Delegates to the canonical implementation in file_utilities to avoid
    maintaining a duplicate extension list.
    """
    return _is_video_file_canonical(file_path)
