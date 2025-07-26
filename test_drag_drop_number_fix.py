#!/usr/bin/env python3
"""
Test script for the drag & drop number field fix.
Tests that components don't disappear when dragged to the sequential number field.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtTest import QTest
from RenameFiles import InteractivePreviewWidget

def test_drag_to_number_field():
    """Test dragging a component to the number field"""
    print("Testing drag & drop to number field...")
    
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    # Create the interactive preview widget
    widget = InteractivePreviewWidget()
    widget.set_separator("-")
    
    # Set up test components
    test_components = ["2025-07-26", "A7R3", "Sarah30", "ILCE-7RM3"]
    widget.set_components(test_components, "001")
    
    print(f"Initial components: {widget.components}")
    print(f"Initial order: {widget.get_component_order()}")
    
    # Find the position of the first component and the number field
    widget.show()  # Widget needs to be shown for itemAt to work
    QTest.qWaitForWindowExposed(widget)
    
    # Find items
    first_component_item = None
    number_item = None
    
    for i in range(widget.count()):
        item = widget.item(i)
        if item.data(Qt.ItemDataRole.UserRole) == "component" and not first_component_item:
            first_component_item = item
        elif item.data(Qt.ItemDataRole.UserRole) == "number":
            number_item = item
    
    if not first_component_item or not number_item:
        print("ERROR: Could not find required items")
        return False
    
    print(f"Found component: {first_component_item.text()}")
    print(f"Found number: {number_item.text()}")
    
    # Simulate drag from first component to number field
    widget.setCurrentItem(first_component_item)
    
    # Get positions
    first_rect = widget.visualItemRect(first_component_item)
    number_rect = widget.visualItemRect(number_item)
    
    start_pos = first_rect.center()
    end_pos = number_rect.center()
    
    print(f"Dragging from {start_pos} to {end_pos}")
    
    # Simulate the drag & drop
    QTest.mousePress(widget, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, start_pos)
    QTest.mouseMove(widget, end_pos)
    QTest.mouseRelease(widget, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, end_pos)
    
    # Check results
    final_components = widget.components
    final_order = widget.get_component_order()
    
    print(f"Final components: {final_components}")
    print(f"Final order: {final_order}")
    
    # Verify that the component didn't disappear
    if len(final_components) != len(test_components):
        print(f"ERROR: Component count changed from {len(test_components)} to {len(final_components)}")
        return False
    
    # Verify that the dragged component is now at the last position
    if final_components[-1] != "2025-07-26":
        print(f"ERROR: Expected '2025-07-26' at last position, got '{final_components[-1]}'")
        return False
    
    print("✅ SUCCESS: Component moved to last position without disappearing")
    return True

def test_drag_to_empty_space():
    """Test dragging a component to empty space"""
    print("\nTesting drag & drop to empty space...")
    
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    widget = InteractivePreviewWidget()
    widget.set_separator("-")
    
    test_components = ["2025-07-26", "A7R3", "Sarah30"]
    widget.set_components(test_components, "001")
    
    print(f"Initial components: {widget.components}")
    
    widget.show()
    QTest.qWaitForWindowExposed(widget)
    
    # Find the first component
    first_component_item = None
    for i in range(widget.count()):
        item = widget.item(i)
        if item.data(Qt.ItemDataRole.UserRole) == "component":
            first_component_item = item
            break
    
    if not first_component_item:
        print("ERROR: Could not find component item")
        return False
    
    widget.setCurrentItem(first_component_item)
    
    # Get component position and simulate drop to empty space
    component_rect = widget.visualItemRect(first_component_item)
    start_pos = component_rect.center()
    
    # Drop at far right (empty space)
    widget_rect = widget.rect()
    end_pos = QPoint(widget_rect.width() - 10, widget_rect.height() // 2)
    
    print(f"Dragging from {start_pos} to empty space at {end_pos}")
    
    QTest.mousePress(widget, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, start_pos)
    QTest.mouseMove(widget, end_pos)
    QTest.mouseRelease(widget, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, end_pos)
    
    final_components = widget.components
    print(f"Final components: {final_components}")
    
    # Verify component moved to last position
    if len(final_components) != len(test_components):
        print(f"ERROR: Component count changed")
        return False
    
    if final_components[-1] != "2025-07-26":
        print(f"ERROR: Expected '2025-07-26' at last position, got '{final_components[-1]}'")
        return False
    
    print("✅ SUCCESS: Component moved to last position when dropped on empty space")
    return True

def test_normal_component_swap():
    """Test normal component to component swapping still works"""
    print("\nTesting normal component swapping...")
    
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    widget = InteractivePreviewWidget()
    widget.set_separator("-")
    
    test_components = ["2025-07-26", "A7R3", "Sarah30"]
    widget.set_components(test_components, "001")
    
    print(f"Initial components: {widget.components}")
    
    widget.show()
    QTest.qWaitForWindowExposed(widget)
    
    # Find first and second components
    components = []
    for i in range(widget.count()):
        item = widget.item(i)
        if item.data(Qt.ItemDataRole.UserRole) == "component":
            components.append(item)
    
    if len(components) < 2:
        print("ERROR: Need at least 2 components for swap test")
        return False
    
    first_item = components[0]
    second_item = components[1]
    
    print(f"Swapping '{first_item.text()}' with '{second_item.text()}'")
    
    widget.setCurrentItem(first_item)
    
    first_rect = widget.visualItemRect(first_item)
    second_rect = widget.visualItemRect(second_item)
    
    start_pos = first_rect.center()
    end_pos = second_rect.center()
    
    QTest.mousePress(widget, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, start_pos)
    QTest.mouseMove(widget, end_pos)
    QTest.mouseRelease(widget, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, end_pos)
    
    final_components = widget.components
    print(f"Final components: {final_components}")
    
    # Verify swap occurred
    if final_components[0] != "A7R3" or final_components[1] != "2025-07-26":
        print(f"ERROR: Swap failed. Expected ['A7R3', '2025-07-26', ...], got {final_components}")
        return False
    
    print("✅ SUCCESS: Component swap working correctly")
    return True

if __name__ == "__main__":
    print("Running drag & drop tests for number field fix...")
    
    success = True
    
    try:
        success &= test_drag_to_number_field()
        success &= test_drag_to_empty_space()
        success &= test_normal_component_swap()
        
        if success:
            print("\n🎉 ALL TESTS PASSED! The drag & drop fix is working correctly.")
        else:
            print("\n❌ SOME TESTS FAILED!")
            
    except Exception as e:
        print(f"\n💥 TEST ERROR: {e}")
        import traceback
        traceback.print_exc()
        success = False
    
    sys.exit(0 if success else 1)
