#!/usr/bin/env python3
"""
Test script to verify the custom icon.ico is loaded correctly
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication, QMainWindow, QLabel, QVBoxLayout, QWidget
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon

def test_custom_icon():
    """Test loading the custom icon.ico file"""
    app = QApplication(sys.argv)
    
    # Create a simple test window
    window = QMainWindow()
    window.setWindowTitle("Custom Icon Test - File Renamer")
    
    # Load the same icon as in the main app
    icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.ico")
    
    if os.path.exists(icon_path):
        window.setWindowIcon(QIcon(icon_path))
        icon_status = f"✅ Custom Icon gefunden und geladen!\nPfad: {icon_path}"
        status_color = "#2E7D32"
        border_color = "#4CAF50"
    else:
        # Fallback
        from PyQt6.QtWidgets import QStyle
        window.setWindowIcon(window.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView))
        icon_status = f"❌ Custom Icon nicht gefunden!\nErwartet: {icon_path}\nFallback verwendet."
        status_color = "#D32F2F"
        border_color = "#F44336"
    
    # Add some content
    central_widget = QWidget()
    window.setCentralWidget(central_widget)
    layout = QVBoxLayout(central_widget)
    
    label = QLabel(icon_status)
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    label.setStyleSheet(f"""
        QLabel {{
            font-size: 14px;
            padding: 20px;
            background-color: #f0f0f0;
            border: 2px solid {border_color};
            border-radius: 10px;
            color: {status_color};
        }}
    """)
    layout.addWidget(label)
    
    # Check icon file info
    if os.path.exists(icon_path):
        file_size = os.path.getsize(icon_path)
        info_label = QLabel(f"Icon-Datei Info:\nGröße: {file_size} Bytes\nPfad: {icon_path}")
        info_label.setStyleSheet("""
            QLabel {
                font-size: 10px;
                padding: 10px;
                background-color: #e8f5e8;
                border: 1px solid #c8e6c9;
                border-radius: 5px;
                color: #1b5e20;
            }
        """)
        layout.addWidget(info_label)
    
    window.setGeometry(300, 300, 450, 250)
    window.show()
    
    print("✅ Custom Icon Test gestartet!")
    print(f"Icon-Pfad: {icon_path}")
    print(f"Icon existiert: {os.path.exists(icon_path)}")
    if os.path.exists(icon_path):
        print(f"Icon-Größe: {os.path.getsize(icon_path)} Bytes")
    
    app.exec()

if __name__ == "__main__":
    test_custom_icon()
