#!/usr/bin/env python3
"""
Main entry point for the modular RenameFiles application.
"""

import sys
import os

# Add the modules directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'modules'))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QCoreApplication

# Import the main application class
from original_ui_complete import FileRenamerApp

def main():
    """Main entry point for the application"""
    # Set application properties
    QCoreApplication.setApplicationName("File Renamer")
    QCoreApplication.setApplicationVersion("3.2")
    QCoreApplication.setOrganizationName("RenamePy")
    
    # Create the application
    app = QApplication(sys.argv)
    
    # Create and show the main window
    window = FileRenamerApp()
    window.show()
    
    # Run the application
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
