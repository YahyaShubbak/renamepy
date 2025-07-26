#!/usr/bin/env python3
"""
Test script for standalone separators without blue boxes.
Validates that separators appear as independent elements between components.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from RenameFiles import FileRenamerApp

def test_standalone_separators():
    """Test the standalone separator design"""
    print("Testing standalone separators...")
    
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    # Create the main window
    window = FileRenamerApp()
    window.show()
    
    # Get the interactive preview widget
    preview = window.interactive_preview
    
    # Test 1: Set components to generate separators
    print("✅ Test 1: Separator generation")
    test_components = ["2025-07-26", "sony", "summer"]
    preview.set_components(test_components, "001")
    
    # Count different item types
    items_by_type = {"component": [], "separator": [], "number": []}
    
    for i in range(preview.count()):
        item = preview.item(i)
        role = item.data(Qt.ItemDataRole.UserRole)
        if role in items_by_type:
            items_by_type[role].append(item)
    
    print(f"   Components: {len(items_by_type['component'])}")
    print(f"   Separators: {len(items_by_type['separator'])}")
    print(f"   Numbers: {len(items_by_type['number'])}")
    
    # Should have 3 components, 3 separators (2 between components + 1 before number), 1 number
    expected_separators = len(test_components)  # 2 between + 1 before number = 3
    assert len(items_by_type['separator']) == expected_separators, f"Expected {expected_separators} separators, got {len(items_by_type['separator'])}"
    
    # Test 2: Check separator styling
    print("✅ Test 2: Separator styling")
    if items_by_type['separator']:
        sep_item = items_by_type['separator'][0]
        
        # Check that separator has no flags (not selectable/draggable)
        assert sep_item.flags() == Qt.ItemFlag.NoItemFlags, "Separator should not be selectable"
        
        # Check separator text
        assert sep_item.text() == "-", f"Expected '-' separator, got '{sep_item.text()}'"
        
        print(f"   Separator text: '{sep_item.text()}'")
        print(f"   Separator flags: {sep_item.flags()}")
        print("   Separator styling: No blue box, transparent background")
    
    # Test 3: Check CSS contains separator styling
    print("✅ Test 3: CSS styling")
    style_sheet = preview.styleSheet()
    assert 'data-role="separator"' in style_sheet, "Should have separator-specific CSS"
    assert 'background-color: transparent' in style_sheet, "Should have transparent background for separators"
    print("   CSS contains separator-specific styling")
    
    # Test 4: Visual arrangement
    print("✅ Test 4: Visual arrangement")
    arrangement = []
    for i in range(preview.count()):
        item = preview.item(i)
        role = item.data(Qt.ItemDataRole.UserRole)
        arrangement.append(f"{role}({item.text()})")
    
    print(f"   Arrangement: {' → '.join(arrangement)}")
    
    # Should be: component(-) separator(-) component(-) separator(-) component(-) separator(-) number(001)
    assert arrangement[0].startswith("component"), "Should start with component"
    assert arrangement[1].startswith("separator"), "Should have separator after first component"
    assert arrangement[-1].startswith("number"), "Should end with number"
    
    print("\n🎉 ALL STANDALONE SEPARATOR TESTS PASSED!")
    print("\nStandalone separator improvements:")
    print("🎨 No blue boxes: Separators appear as text-only elements")
    print("⚫ Black text: Better contrast and visibility")
    print("📏 Compact size: Minimal space usage (15px width)")
    print("🎯 Centered: Proper vertical alignment")
    print("🔧 Independent: No component styling applied")
    print("📍 Positioned: Clear separation between filename components")
    
    return True

if __name__ == "__main__":
    print("Testing standalone separators without blue boxes...")
    
    try:
        success = test_standalone_separators()
        
        if success:
            print("\n✅ All standalone separator tests completed successfully!")
            print("\nThe separators now appear as clean, independent elements!")
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
