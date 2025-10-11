"""
UI Helper Utilities - Common utility functions for UI operations
Extracted from main_application.py to reduce clutter
"""

import os


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


def is_video_file(file_path):
    """
    Check if file is a video file
    
    Args:
        file_path: Path to the file
        
    Returns:
        bool: True if file is a video, False otherwise
    """
    video_extensions = [
        '.mp4', '.mov', '.avi', '.mkv', '.m4v', '.3gp', '.wmv', 
        '.flv', '.webm', '.mpg', '.mpeg', '.m2v', '.mts', '.m2ts'
    ]
    return os.path.splitext(file_path)[1].lower() in video_extensions
