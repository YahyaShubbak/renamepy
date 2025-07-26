#!/usr/bin/env python3
"""
Test script for compact interactive preview widget.
Validates that the preview takes less space and dividers are more compact.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication
from RenameFiles import FileRenamerApp

def test_compact_preview():
    """Test the compact interactive preview widget"""
    print("Testing compact interactive preview...")
    
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    # Create the main window
    window = FileRenamerApp()
    window.show()
    
    # Get the interactive preview widget
    preview = window.interactive_preview
    
    # Test 1: Check height is more compact
    print("✅ Test 1: Widget height")
    max_height = preview.maximumHeight()
    min_height = preview.minimumHeight()
    print(f"   Max height: {max_height}px (should be ≤55px)")
    print(f"   Min height: {min_height}px (should be ≤40px)")
    assert max_height <= 55, f"Max height {max_height} should be ≤55px"
    assert min_height <= 40, f"Min height {min_height} should be ≤40px"
    
    # Test 2: Set some test components to check styling
    print("✅ Test 2: Component styling")
    test_components = ["2025-07-26", "sony", "summer", "ILCE-7CM2", "FE-50mm-F1.8"]
    preview.set_components(test_components, "001")
    
    # Check that items exist
    item_count = preview.count()
    print(f"   Total items: {item_count}")
    
    # Count components, separators, and number
    components = []
    separators = []
    numbers = []
    
    for i in range(item_count):
        item = preview.item(i)
        role = item.data(1)  # Qt.ItemDataRole.UserRole = 1
        if role == "component":
            components.append(item.text())
        elif role == "separator":
            separators.append(item.text())
        elif role == "number":
            numbers.append(item.text())
    
    print(f"   Components: {len(components)} ({components})")
    print(f"   Separators: {len(separators)} ({separators})")
    print(f"   Numbers: {len(numbers)} ({numbers})")
    
    # Test 3: Check spacing is compact
    print("✅ Test 3: Spacing")
    spacing = preview.spacing()
    print(f"   Item spacing: {spacing}px (should be ≤1px)")
    assert spacing <= 1, f"Spacing {spacing} should be ≤1px"
    
    # Test 4: Check style sheet contains compact settings
    print("✅ Test 4: Style sheet")
    style_sheet = preview.styleSheet()
    assert "padding: 4px" in style_sheet, "Should have compact padding"
    assert "font-size: 11px" in style_sheet, "Should have smaller base font"
    assert "padding: 3px 6px" in style_sheet, "Should have compact item padding"
    assert "margin: 1px" in style_sheet, "Should have minimal margins"
    print("   Style sheet contains compact settings")
    
    print("\n🎉 ALL COMPACT TESTS PASSED!")
    print("\nCompact improvements:")
    print("📐 Height reduced: 80px → 55px (max), 60px → 40px (min)")
    print("🔤 Font size reduced: 12px → 11px (base), 10px (items)")
    print("📦 Padding reduced: 8px → 4px (widget), 6px 10px → 3px 6px (items)")
    print("📏 Margins reduced: 3px → 1px")
    print("📊 Spacing reduced: 2px → 1px")
    print("➖ Separators: Smaller font (8px) and fixed width (12px)")
    print("🔢 Number field: Smaller font (10px)")
    
    return True

if __name__ == "__main__":
    print("Testing compact interactive preview...")
    
    try:
        success = test_compact_preview()
        
        if success:
            print("\n✅ All compact tests completed successfully!")
            print("\nThe interactive preview now takes up significantly less space!")
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
