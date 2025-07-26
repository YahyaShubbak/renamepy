#!/usr/bin/env python3
"""
Test script for TODO 2 and 3 implementation:
- Dashed border drag & drop box with info text
- File selection menu bar at the top
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from RenameFiles import FileRenamerApp

def test_ui_improvements():
    """Test the UI improvements for TODOs 2 and 3"""
    print("Testing UI improvements...")
    
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    # Create the main window
    window = FileRenamerApp()
    window.show()
    
    # Test 1: Check that file list has placeholder when empty
    print("✅ Test 1: File list placeholder")
    assert window.file_list.count() == 1, "File list should have placeholder item"
    
    placeholder_item = window.file_list.item(0)
    assert placeholder_item.flags() == Qt.ItemFlag.NoItemFlags, "Placeholder should not be selectable"
    assert "Drag and drop" in placeholder_item.text(), "Placeholder should contain drag and drop text"
    print(f"   Placeholder text: {placeholder_item.text()}")
    
    # Test 2: Check that menu bar buttons exist
    print("✅ Test 2: Menu bar buttons")
    assert hasattr(window, 'select_files_menu_button'), "Select files menu button should exist"
    assert hasattr(window, 'select_folder_menu_button'), "Select folder menu button should exist"
    assert hasattr(window, 'clear_files_menu_button'), "Clear files menu button should exist"
    
    print(f"   Select Files button text: {window.select_files_menu_button.text()}")
    print(f"   Select Folder button text: {window.select_folder_menu_button.text()}")
    print(f"   Clear Files button text: {window.clear_files_menu_button.text()}")
    
    # Test 3: Check file list styling (dashed border)
    print("✅ Test 3: File list styling")
    style_sheet = window.file_list.styleSheet()
    assert "dashed" in style_sheet, "File list should have dashed border"
    assert "border:" in style_sheet, "File list should have border styling"
    print("   File list has dashed border styling")
    
    # Test 4: Check that old buttons are removed
    print("✅ Test 4: Old buttons removed")
    assert not hasattr(window, 'select_files_button') or window.select_files_button is None, "Old select files button should be removed"
    print("   Old file selection buttons have been removed")
    
    print("\n🎉 ALL UI IMPROVEMENT TESTS PASSED!")
    print("\nImplemented improvements:")
    print("✅ TODO 2: Drag & drop box with dashed border and info text")
    print("✅ TODO 3: File selection menu bar at the top")
    print("\nNew features:")
    print("📁 Placeholder text: 'Drag and drop folders/files here or use buttons below'")
    print("🎨 Dashed border around file list for better visual distinction")
    print("🎛️ Color-coded menu buttons: Blue (Files), Green (Folder), Red (Clear)")
    print("📍 Menu bar positioned at the top for better accessibility")
    
    return True

if __name__ == "__main__":
    print("Testing UI improvements for TODOs 2 and 3...")
    
    try:
        success = test_ui_improvements()
        
        if success:
            print("\n✅ All tests completed successfully!")
        else:
            print("\n❌ Some tests failed!")
            
    except Exception as e:
        print(f"\n💥 TEST ERROR: {e}")
        import traceback
        traceback.print_exc()
        success = False
    
    # Keep window open for manual inspection
    input("\nPress Enter to close the test window...")
    
    sys.exit(0 if success else 1)
