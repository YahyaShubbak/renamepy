#!/usr/bin/env python3
"""
Test script to verify the application icon
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication, QMainWindow, QLabel, QVBoxLayout, QWidget
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap

def test_icon():
    """Test the application icon"""
    app = QApplication(sys.argv)
    
    # Create a simple test window
    window = QMainWindow()
    window.setWindowTitle("Icon Test - File Renamer")
    
    # Set the same icon as in the main app
    from PyQt6.QtWidgets import QStyle
    window.setWindowIcon(window.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView))
    
    # Add some content
    central_widget = QWidget()
    window.setCentralWidget(central_widget)
    layout = QVBoxLayout(central_widget)
    
    label = QLabel("✅ Icon Test erfolgreich!\n\nDas Fenster sollte ein Datei-Icon haben.")
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    label.setStyleSheet("""
        QLabel {
            font-size: 16px;
            padding: 20px;
            background-color: #f0f0f0;
            border: 2px solid #4CAF50;
            border-radius: 10px;
            color: #2E7D32;
        }
    """)
    layout.addWidget(label)
    
    window.setGeometry(300, 300, 400, 200)
    window.show()
    
    print("✅ Icon-Test Fenster geöffnet!")
    print("Das Fenster sollte ein Datei-Icon in der Titelleiste und Taskleiste haben.")
    print("Schließe das Fenster um den Test zu beenden.")
    
    app.exec()

if __name__ == "__main__":
    test_icon()
