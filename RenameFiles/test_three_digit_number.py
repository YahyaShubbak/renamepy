#!/usr/bin/env python3
"""
Test script to verify 3-digit numbering system
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from RenameFiles import get_filename_components_static

def test_three_digit_numbering():
    """Test that the numbering system now uses 3 digits"""
    print("Testing 3-digit numbering system...")
    
    # Test parameters
    date_taken = "20250721"
    camera_prefix = "A7R3"
    additional = "Test"
    camera_model = "ILCE-7RM3"
    lens_model = "FE24-70"
    use_camera = True
    use_lens = True
    custom_order = ["Date", "Prefix", "Additional", "Camera", "Lens"]
    
    # Test different numbers
    test_numbers = [1, 5, 10, 99, 100, 999]
    
    for num in test_numbers:
        components = get_filename_components_static(
            date_taken, camera_prefix, additional, 
            camera_model, lens_model, use_camera, use_lens, 
            num, custom_order
        )
        
        filename = "-".join(components) + ".ARW"
        print(f"Number {num:3d}: {filename}")
        
        # Verify the number is 3 digits
        number_part = components[-1]  # Last component is always the number
        if len(number_part) == 3 and number_part.isdigit():
            print(f"  ✅ Number '{number_part}' is correctly 3 digits")
        else:
            print(f"  ❌ Number '{number_part}' is NOT 3 digits")
    
    print("\n" + "="*50)
    print("3-digit numbering test completed!")

if __name__ == "__main__":
    test_three_digit_numbering()
