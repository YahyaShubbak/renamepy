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
    # Debug output for console
    print("🚀 File Renamer wird gestartet...")
    print(f"Python Version: {sys.version}")
    print(f"Arbeitsverzeichnis: {os.getcwd()}")
    print(f"Modules Pfad: {modules_dir}")
    
    try:
        print("📦 Importiere Module...")
        from modules.main_application import main
        print("✅ Module erfolgreich importiert")
        print("🖼️ Starte GUI...")
        main()
        print("👋 Anwendung beendet")
    except ImportError as e:
        print(f"❌ Fehler beim Importieren der Module: {e}")
        print("Bitte stellen Sie sicher, dass alle erforderlichen Module installiert sind:")
        print("pip install PyQt6 PyExifTool Pillow")
        input("Drücken Sie Enter zum Beenden...")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Anwendungsfehler: {e}")
        print(f"Fehlerdetails: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        input("Drücken Sie Enter zum Beenden...")
        sys.exit(1)
