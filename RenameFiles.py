#!/usr/bin/env python3
"""
Advanced File Renaming Tool with EXIF Support - Modular Version
Enhanced GUI version with interactive preview and drag-and-drop ordering
Refactored for better maintainability and organization
"""

import sys
import os
from pathlib import Path

# Add modules directory to path
current_dir = os.path.dirname(__file__)
modules_dir = os.path.join(current_dir, 'modules')
if modules_dir not in sys.path:
    sys.path.insert(0, modules_dir)

# Import and run the main application
if __name__ == "__main__":
    try:
        from modules.main_application import main
        main()
    except ImportError as e:
        print(f"Error importing modules: {e}")
        print("Please ensure all required modules are installed:")
        print("pip install PyQt6 PyExifTool Pillow")
        sys.exit(1)
    except Exception as e:
        print(f"Application error: {e}")
        sys.exit(1)
