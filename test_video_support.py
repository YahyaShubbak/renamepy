#!/usr/bin/env python3
"""
Test script for video support in RenameFiles.py

This script demonstrates the new video support functionality.
"""

from RenameFiles import is_video_file, is_media_file, VIDEO_EXTENSIONS, MEDIA_EXTENSIONS

def test_video_support():
    print("=== Video Support Test ===\n")
    
    print("Supported video extensions:")
    print(", ".join(VIDEO_EXTENSIONS))
    print(f"Total: {len(VIDEO_EXTENSIONS)} formats\n")
    
    print("Supported media extensions (images + videos):")
    print(f"Total: {len(MEDIA_EXTENSIONS)} formats\n")
    
    # Test some sample files
    test_files = [
        "IMG_001.jpg",
        "DSC_002.arw", 
        "video_001.mp4",
        "movie.mov",
        "clip.avi",
        "recording.mkv",
        "document.pdf",
        "audio.mp3"
    ]
    
    print("File type detection test:")
    for file in test_files:
        is_img = "✓" if file.endswith(('.jpg', '.arw')) else "✗"
        is_vid = "✓" if is_video_file(file) else "✗"
        is_med = "✓" if is_media_file(file) else "✗"
        
        print(f"{file:15} | Image: {is_img} | Video: {is_vid} | Media: {is_med}")
    
    print("\n=== Video metadata support ===")
    print("ExifTool can extract metadata from videos including:")
    print("• Creation date/time")
    print("• Camera model (for camera-recorded videos)")
    print("• Video duration")
    print("• Frame rate")
    print("• Resolution")
    print("• GPS coordinates (if available)")
    print("• Lens information (for compatible cameras)")

if __name__ == "__main__":
    test_video_support()
