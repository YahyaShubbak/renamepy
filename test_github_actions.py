#!/usr/bin/env python3
"""
Simple test script to verify core functionality for GitHub Actions
"""

import sys
import os

# Add current directory to path
sys.path.insert(0, '.')

def test_basic_imports():
    """Test if core modules can be imported"""
    try:
        # Test basic function imports
        from RenameFiles import (
            is_media_file, 
            is_image_file, 
            is_video_file,
            sanitize_filename,
            get_filename_components_static
        )
        print("✅ Core functions imported successfully")
        return True
    except Exception as e:
        print(f"❌ Import error: {e}")
        return False

def test_media_file_detection():
    """Test media file detection functions"""
    try:
        from RenameFiles import is_media_file, is_image_file, is_video_file
        
        # Test image files
        assert is_media_file('test.jpg') == True
        assert is_media_file('test.CR2') == True
        assert is_media_file('test.arw') == True
        assert is_image_file('test.jpg') == True
        assert is_image_file('test.mp4') == False
        
        # Test video files
        assert is_media_file('test.mp4') == True
        assert is_media_file('test.mov') == True
        assert is_video_file('test.mp4') == True
        assert is_video_file('test.jpg') == False
        
        # Test non-media files
        assert is_media_file('test.txt') == False
        assert is_media_file('test.doc') == False
        
        print("✅ Media file detection tests passed")
        return True
    except Exception as e:
        print(f"❌ Media file detection failed: {e}")
        return False

def test_filename_sanitization():
    """Test filename sanitization"""
    try:
        from RenameFiles import sanitize_filename
        
        # Test basic sanitization
        result = sanitize_filename('test/file:name<>')
        assert '/' not in result
        assert ':' not in result
        assert '<' not in result
        assert '>' not in result
        
        # Test normal filename
        result = sanitize_filename('normal_filename')
        assert result == 'normal_filename'
        
        print("✅ Filename sanitization tests passed")
        return True
    except Exception as e:
        print(f"❌ Filename sanitization failed: {e}")
        return False

def test_filename_components():
    """Test filename component generation"""
    try:
        from RenameFiles import get_filename_components_static
        
        # Test basic component generation
        components = get_filename_components_static(
            '20250725', 'A7R3', 'vacation', 'ILCE-7RM3', 'FE24-70',
            True, True, 1, ['Date', 'Prefix', 'Additional', 'Camera', 'Lens'],
            'YYYY-MM-DD', True
        )
        
        assert isinstance(components, list)
        assert len(components) > 0
        assert '001' in components  # Sequential number should be present
        
        print(f"✅ Filename components generated: {components}")
        return True
    except Exception as e:
        print(f"❌ Filename component generation failed: {e}")
        return False

def main():
    """Run all tests"""
    print("🔬 Running GitHub Actions compatibility tests...")
    
    tests = [
        test_basic_imports,
        test_media_file_detection,
        test_filename_sanitization,
        test_filename_components
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        else:
            print(f"❌ Test {test.__name__} failed")
    
    print(f"\n📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed!")
        return 0
    else:
        print("❌ Some tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())
