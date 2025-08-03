#!/usr/bin/env python3
"""
Simplified CI test that focuses on core functionality without complex ExifTool validation
"""

import sys
import os

# Add current directory to path
sys.path.insert(0, '.')

def test_basic_imports():
    """Test if core modules can be imported"""
    try:
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
        import traceback
        traceback.print_exc()
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
        import traceback
        traceback.print_exc()
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
        import traceback
        traceback.print_exc()
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
        import traceback
        traceback.print_exc()
        return False

def test_exiftool_detection_ci_safe():
    """Test ExifTool detection without complex validation (CI-safe)"""
    try:
        import shutil
        
        # Simple check for system exiftool (Ubuntu CI)
        system_exiftool = shutil.which("exiftool")
        if system_exiftool:
            print(f"✅ System ExifTool found: {system_exiftool}")
            
            # Try to run exiftool version check
            try:
                import subprocess
                result = subprocess.run([system_exiftool, "-ver"], capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    version = result.stdout.strip()
                    print(f"✅ ExifTool version: {version}")
                else:
                    print(f"⚠️ ExifTool found but version check failed: {result.stderr}")
            except Exception as e:
                print(f"⚠️ ExifTool found but cannot run version check: {e}")
        else:
            print("ℹ️ No system ExifTool found (this is OK for basic tests)")
        
        return True
    except Exception as e:
        print(f"❌ ExifTool detection failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_syntax_validation():
    """Test that the main file compiles without syntax errors"""
    try:
        import py_compile
        py_compile.compile('RenameFiles.py', doraise=True)
        print("✅ Python syntax validation passed")
        return True
    except Exception as e:
        print(f"❌ Syntax validation failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all CI-safe tests"""
    print("🔬 Running GitHub Actions CI tests...")
    print(f"🐍 Python version: {sys.version}")
    print(f"📁 Working directory: {os.getcwd()}")
    print(f"📂 Python path: {sys.path[:3]}...")  # First 3 entries
    
    tests = [
        ("Syntax Validation", test_syntax_validation),
        ("Basic Imports", test_basic_imports),
        ("Media File Detection", test_media_file_detection),
        ("Filename Sanitization", test_filename_sanitization),
        ("Filename Components", test_filename_components),
        ("ExifTool Detection", test_exiftool_detection_ci_safe)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n🧪 Running {test_name}...")
        try:
            if test_func():
                passed += 1
                print(f"✅ {test_name} PASSED")
            else:
                print(f"❌ {test_name} FAILED")
        except Exception as e:
            print(f"💥 {test_name} CRASHED: {e}")
            import traceback
            traceback.print_exc()
    
    print(f"\n📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed!")
        return 0
    else:
        print("❌ Some tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())
