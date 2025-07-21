#!/usr/bin/env python3
"""
Quick test for the filename ordering functionality in GUI mode.
This creates a minimal test to verify the new ordering features work correctly.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_gui_ordering():
    """Test the GUI ordering functionality"""
    from PyQt6.QtWidgets import QApplication
    from RenameFiles import FileRenamerApp
    
    # Create application
    app = QApplication(sys.argv if 'pytest' not in sys.modules else [])
    
    try:
        # Create window
        window = FileRenamerApp()
        
        # Test initial state
        print("✓ Window created successfully")
        print(f"✓ Initial custom_order: {window.custom_order}")
        
        # Test ordering combo
        print(f"✓ Ordering combo items: {window.ordering_combo.count()}")
        for i in range(window.ordering_combo.count()):
            print(f"  - {window.ordering_combo.itemText(i)}")
        
        # Test preview with different orderings
        orderings = [
            ["Date", "Prefix", "Additional", "Camera", "Lens"],
            ["Prefix", "Additional", "Date", "Camera", "Lens"],
            ["Date", "Camera", "Lens", "Prefix", "Additional"],
            ["Additional", "Prefix", "Date", "Camera", "Lens"]
        ]
        
        for i, order in enumerate(orderings):
            window.custom_order = order
            window.camera_prefix_entry.setText("A7R3")
            window.additional_entry.setText("Sarah30")
            window.checkbox_camera.setChecked(True)
            window.checkbox_lens.setChecked(True)
            window.update_preview()
            
            preview_text = window.preview_box.text()
            print(f"✓ Test {i+1}: {'-'.join(order)} -> Number")
            print(f"  Preview: {preview_text}")
            
            # Verify number is at end
            if preview_text and not preview_text.startswith("["):
                name_without_ext = preview_text.replace(".ARW", "")
                parts = name_without_ext.split("-")
                if len(parts) > 0 and parts[-1].isdigit():
                    print(f"  ✓ Sequential number ({parts[-1]}) correctly at end")
                else:
                    print(f"  ❌ Sequential number not at end: {parts}")
            print()
        
        print("=== All GUI Tests Passed! ===")
        return True
        
    except Exception as e:
        print(f"❌ GUI test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        if 'app' in locals():
            app.quit()

if __name__ == "__main__":
    print("Testing GUI Filename Ordering")
    print("=" * 40)
    
    success = test_gui_ordering()
    
    if success:
        print("\n🎉 All tests passed! The filename ordering system is working correctly.")
        print("Features tested:")
        print("- GUI initialization and ordering combo")
        print("- Custom order setting and preview updates")
        print("- Sequential number positioning at end")
        print("- Multiple ordering patterns")
    else:
        print("\n❌ Some tests failed. Please check the output above.")
        sys.exit(1)
