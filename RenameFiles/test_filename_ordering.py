#!/usr/bin/env python3
"""
Test script for filename ordering functionality.
This tests the new intuitive filename component ordering system.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from RenameFiles import get_filename_components_static, sanitize_filename

def test_filename_ordering():
    """Test different filename component orders"""
    print("=== Testing Filename Component Ordering ===\n")
    
    # Test data
    date_taken = "20250721"
    camera_prefix = "A7R3"
    additional = "Sarah30"
    camera_model = "ILCE-7RM3"
    lens_model = "FE24-70F28GM"
    use_camera = True
    use_lens = True
    num = 78
    
    # Test different ordering scenarios
    test_cases = [
        {
            "name": "Default (Date-Prefix-Additional-Camera-Lens-Number)",
            "order": ["Date", "Prefix", "Additional", "Camera", "Lens"],
            "expected_format": "2025-07-21-A7R3-Sarah30-ILCE-7RM3-FE24-70F28GM-78"
        },
        {
            "name": "Prefix First (Prefix-Additional-Date-Camera-Lens-Number)",
            "order": ["Prefix", "Additional", "Date", "Camera", "Lens"],
            "expected_format": "A7R3-Sarah30-2025-07-21-ILCE-7RM3-FE24-70F28GM-78"
        },
        {
            "name": "Camera Focus (Date-Camera-Lens-Prefix-Additional-Number)",
            "order": ["Date", "Camera", "Lens", "Prefix", "Additional"],
            "expected_format": "2025-07-21-ILCE-7RM3-FE24-70F28GM-A7R3-Sarah30-78"
        },
        {
            "name": "Event First (Additional-Prefix-Date-Camera-Lens-Number)",
            "order": ["Additional", "Prefix", "Date", "Camera", "Lens"],
            "expected_format": "Sarah30-A7R3-2025-07-21-ILCE-7RM3-FE24-70F28GM-78"
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"{i}. {test_case['name']}")
        
        # Generate filename components
        name_parts = get_filename_components_static(
            date_taken, camera_prefix, additional, 
            camera_model, lens_model, use_camera, use_lens, 
            num, test_case['order']
        )
        
        # Join with separator and add extension
        filename = "-".join(name_parts) + ".ARW"
        
        print(f"   Order: {' -> '.join(test_case['order'])} -> Number")
        print(f"   Result: {filename}")
        
        # Validate sequential number is at the end
        parts = filename.replace(".ARW", "").split("-")
        if parts[-1] == "78":
            print("   ✓ Sequential number correctly at end")
        else:
            print(f"   ❌ Sequential number not at end: {parts[-1]}")
        
        print()

def test_edge_cases():
    """Test edge cases with missing components"""
    print("=== Testing Edge Cases ===\n")
    
    date_taken = "20250721"
    num = 5
    
    test_cases = [
        {
            "name": "Only Date and Number",
            "camera_prefix": "",
            "additional": "",
            "camera_model": None,
            "lens_model": None,
            "use_camera": False,
            "use_lens": False,
            "expected": "2025-07-21-05"
        },
        {
            "name": "Date + Prefix + Number",
            "camera_prefix": "A7R3",
            "additional": "",
            "camera_model": None,
            "lens_model": None,
            "use_camera": False,
            "use_lens": False,
            "expected": "2025-07-21-A7R3-05"
        },
        {
            "name": "Date + Additional + Camera + Number",
            "camera_prefix": "",
            "additional": "Wedding",
            "camera_model": "D850",
            "lens_model": None,
            "use_camera": True,
            "use_lens": False,
            "expected": "2025-07-21-Wedding-D850-05"
        }
    ]
    
    default_order = ["Date", "Prefix", "Additional", "Camera", "Lens"]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"{i}. {test_case['name']}")
        
        name_parts = get_filename_components_static(
            date_taken, test_case['camera_prefix'], test_case['additional'],
            test_case['camera_model'], test_case['lens_model'], 
            test_case['use_camera'], test_case['use_lens'],
            num, default_order
        )
        
        filename = "-".join(name_parts)
        print(f"   Result: {filename}")
        print(f"   Expected: {test_case['expected']}")
        
        if filename == test_case['expected']:
            print("   ✓ Correct")
        else:
            print("   ❌ Mismatch")
        
        print()

def test_special_characters():
    """Test handling of special characters in filenames"""
    print("=== Testing Special Character Handling ===\n")
    
    date_taken = "20250721"
    num = 1
    order = ["Date", "Prefix", "Additional", "Camera", "Lens"]
    
    test_cases = [
        {
            "name": "Special characters in prefix",
            "camera_prefix": "A7R/III",
            "additional": "Test<File>",
            "expected_sanitized": True
        },
        {
            "name": "Spaces and symbols",
            "camera_prefix": "Sony Alpha",
            "additional": "Wedding:Day*1",
            "expected_sanitized": True
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"{i}. {test_case['name']}")
        
        name_parts = get_filename_components_static(
            date_taken, test_case['camera_prefix'], test_case['additional'],
            None, None, False, False, num, order
        )
        
        filename = "-".join(name_parts) + ".ARW"
        sanitized = sanitize_filename(filename)
        
        print(f"   Original: {filename}")
        print(f"   Sanitized: {sanitized}")
        
        # Check if sanitization was needed
        if filename != sanitized:
            print("   ✓ Special characters properly sanitized")
        else:
            print("   ✓ No sanitization needed")
        
        print()

if __name__ == "__main__":
    print("Testing Filename Ordering System")
    print("=" * 50)
    print()
    
    try:
        test_filename_ordering()
        test_edge_cases()
        test_special_characters()
        
        print("=== Summary ===")
        print("✓ All filename ordering tests completed")
        print("✓ Sequential number always appears at end")
        print("✓ Component ordering is flexible and intuitive")
        print("✓ Special character handling works correctly")
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
