#!/usr/bin/env python3
"""
Advanced File Renaming Tool with EXIF Support - Modular Version
Enhanced GUI version with interactive preview and drag-and-drop ordering
Refactored for better maintainability and organization
"""

import sys

if sys.version_info < (3, 10):
    sys.exit(
        f"RenamePy requires Python 3.10 or newer (found {sys.version.split()[0]}).\n"
        "Please install a current Python from https://www.python.org/downloads/"
    )

# Simplified: assume running as script from project root with package modules
try:
    from modules.main_application import main as app_main
except ImportError as e:
    print('Import error starting application:', e)
    raise

if __name__ == '__main__':
    print('Starting GUI...')
    sys.exit(app_main())
