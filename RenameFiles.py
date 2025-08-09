#!/usr/bin/env python3
"""
Advanced File Renaming Tool with EXIF Support - Modular Version
Enhanced GUI version with interactive preview and drag-and-drop ordering
Refactored for better maintainability and organization
"""

# Simplified: assume running as script from project root with package modules
try:
    from modules.main_application import main as app_main
except ImportError as e:
    print('Import error starting application:', e)
    raise

if __name__ == '__main__':
    print('🖼️ Starte GUI...')
    app_main()
