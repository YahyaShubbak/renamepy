"""
UI Helper Utilities - Common utility functions for UI operations
Extracted from main_application.py to reduce clutter
"""

import os

from ..file_utilities import FileConstants, is_image_file, is_video_file


def calculate_stats(files):
    """
    Calculate simple file statistics
    
    Args:
        files: List of file paths
        
    Returns:
        dict: Statistics including total_files, jpeg_count, raw_count, video_count, etc.
    """
    total = len(files)
    
    # Count different file types (extension lists from FileConstants)
    jpeg_count = sum(1 for f in files if f.lower().endswith(('.jpg', '.jpeg')))
    raw_count = sum(1 for f in files
                    if os.path.splitext(f)[1].lower() in FileConstants.RAW_EXTENSIONS)
    total_images = sum(1 for f in files if is_image_file(f))
    # EDGE 3 fix: count actual video files instead of assuming
    # everything that isn't an image is a video.
    videos = sum(1 for f in files if is_video_file(f))
    
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
