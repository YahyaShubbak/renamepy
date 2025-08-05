#!/usr/bin/env python3
"""
Simple CI Test Suite
"""

import sys
import os

def main():
    print("🚀 Starting CI Test Suite")
    print("=" * 40)
    
    # Add modules to path
    sys.path.insert(0, "modules")
    
    try:
        # Test basic import
        from rename_engine import get_filename_components_static
        print("✅ rename_engine imported successfully")
        
        # Test basic functionality
        result = get_filename_components_static(
            date_taken="20240101",
            camera_prefix="",
            additional="",
            camera_model="Test Camera",
            lens_model="Test Lens",
            use_camera=True,
            use_lens=True,
            num=1,
            custom_order=["Date", "Camera", "Lens"],
            date_format="YYYY-MM-DD",
            use_date=True,
            selected_metadata={}
        )
        
        if result:
            print(f"✅ Basic functionality test passed: {result}")
            print("✅ All tests passed!")
            return 0
        else:
            print("❌ Basic functionality test failed")
            return 1
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
