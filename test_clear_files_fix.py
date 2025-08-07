#!/usr/bin/env python3
"""
Test script to verify the Clear Files button fix
This test simulates the workflow that was causing the issue
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'modules'))

from PyQt6.QtWidgets import QApplication
from modules.main_application import FileRenamerApp

def test_clear_files_workflow():
    """
    Test the problematic workflow:
    1. Load files
    2. Click Clear Files
    3. Load new files
    4. Check if Rename button is enabled
    """
    print("🧪 Testing Clear Files fix...")
    
    app = QApplication(sys.argv)
    window = FileRenamerApp()
    
    # Simulate initial state
    print("✅ Initial state: rename_button.isEnabled() =", window.rename_button.isEnabled())
    assert not window.rename_button.isEnabled(), "Button should be disabled initially"
    
    # Simulate adding files (like drag & drop)
    test_files = [
        "test_image1.jpg",  # These don't need to exist for this UI test
        "test_image2.jpg"
    ]
    
    print("\n📁 Simulating file addition...")
    # Mock the file existence check temporarily
    old_is_media_file = __import__('modules.file_utils', fromlist=['is_media_file']).is_media_file
    old_exists = os.path.exists
    
    def mock_is_media_file(filename):
        return filename.endswith('.jpg')
    
    def mock_exists(path):
        return path.endswith('.jpg')
    
    # Apply mocks
    import modules.file_utils
    modules.file_utils.is_media_file = mock_is_media_file
    os.path.exists = mock_exists
    
    try:
        # Add files through the normal workflow
        window.add_files_to_list(test_files)
        print("✅ After adding files: rename_button.isEnabled() =", window.rename_button.isEnabled())
        print(f"✅ Files count: {len(window.files)}")
        assert window.rename_button.isEnabled(), "Button should be enabled after adding files"
        
        # Clear files
        print("\n🗑️ Clearing files...")
        window.clear_file_list()
        print("✅ After clearing: rename_button.isEnabled() =", window.rename_button.isEnabled())
        print(f"✅ Files count: {len(window.files)}")
        assert not window.rename_button.isEnabled(), "Button should be disabled after clearing"
        
        # Add files again (this was the problematic step)
        print("\n📁 Adding files again...")
        window.add_files_to_list(test_files)
        print("✅ After re-adding files: rename_button.isEnabled() =", window.rename_button.isEnabled())
        print(f"✅ Files count: {len(window.files)}")
        assert window.rename_button.isEnabled(), "🎯 CRITICAL: Button should be enabled after re-adding files!"
        
        print("\n🎉 All tests passed! The Clear Files fix is working correctly.")
        
    finally:
        # Restore original functions
        modules.file_utils.is_media_file = old_is_media_file
        os.path.exists = old_exists
    
    app.quit()

if __name__ == "__main__":
    test_clear_files_workflow()
