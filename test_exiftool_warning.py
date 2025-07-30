#!/usr/bin/env python3
"""
Test script to show the ExifTool Warning Dialog without running the full application.
This simulates the case where ExifTool is not installed but Pillow is available.
"""

import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget
from PyQt6.QtCore import QSettings

# Import the dialog class from your main file
# Note: In actual usage, you would import this from RenameFiles
# For testing, we'll copy the dialog class here

from PyQt6.QtWidgets import QDialog, QLabel, QVBoxLayout, QHBoxLayout, QPushButton, QCheckBox
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QStyle

class ExifToolWarningDialog(QDialog):
    """Warning dialog shown when ExifTool is not installed"""
    
    def __init__(self, parent=None, current_method=None):
        super().__init__(parent)
        self.setWindowTitle("ExifTool Not Found - Installation Recommended")
        self.setModal(True)
        self.resize(600, 450)
        
        layout = QVBoxLayout(self)
        
        # Header with warning icon
        header_layout = QHBoxLayout()
        warning_icon = QLabel()
        warning_icon.setPixmap(self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxWarning).pixmap(48, 48))
        
        header_text = QLabel("ExifTool Not Found")
        header_text.setStyleSheet("font-size: 18px; font-weight: bold; color: #d83b01;")
        
        header_layout.addWidget(warning_icon)
        header_layout.addWidget(header_text)
        header_layout.addStretch()
        layout.addLayout(header_layout)
        
        # Dynamic fallback text based on current method
        if current_method == "pillow":
            fallback_text = "<b>Current fallback:</b> Using Pillow (limited RAW support, may miss some metadata)"
            continue_button_text = "Continue with Pillow"
        else:
            fallback_text = "<b>Current status:</b> No EXIF support available (basic file operations only)"
            continue_button_text = "Continue without EXIF"
        
        # Main explanation text
        info_text = QLabel(f"""
<b>What is ExifTool?</b><br>
ExifTool is a powerful library for reading and writing metadata in image files. It provides the most comprehensive and reliable EXIF data extraction available.

<b>Why ExifTool is recommended:</b><br>
• <b>Complete RAW support:</b> Works with all camera RAW formats (ARW, CR2, NEF, DNG, etc.)<br>
• <b>More metadata:</b> Extracts camera, lens, and date information more reliably<br>
• <b>Professional grade:</b> Used by photographers and software worldwide<br>
• <b>Always up-to-date:</b> Supports the latest camera models<br>

{fallback_text}

<b>How to install ExifTool:</b><br>
1. Download from: <a href="https://exiftool.org/install.html">https://exiftool.org/install.html</a><br>
2. Extract the downloaded ZIP file<br>
3. Copy <b>exiftool.exe</b> to your program folder or system PATH<br>
4. Restart this application<br>

<i>You can continue using the application now, but ExifTool is strongly recommended for best results.</i>
        """)
        info_text.setWordWrap(True)
        info_text.setOpenExternalLinks(True)
        info_text.setStyleSheet("font-size: 11px; line-height: 1.4;")
        
        layout.addWidget(info_text)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.dont_show_again = QCheckBox("Don't show this warning again")
        button_layout.addWidget(self.dont_show_again)
        button_layout.addStretch()
        
        install_button = QPushButton("Open Download Page")
        install_button.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 6px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #106ebe;
            }
        """)
        install_button.clicked.connect(self.open_download_page)
        
        continue_button = QPushButton(continue_button_text)
        continue_button.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 6px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #5a6268;
            }
        """)
        continue_button.clicked.connect(self.accept)
        
        button_layout.addWidget(install_button)
        button_layout.addWidget(continue_button)
        layout.addLayout(button_layout)
    
    def open_download_page(self):
        """Open the ExifTool download page in default browser"""
        import webbrowser
        webbrowser.open("https://exiftool.org/install.html")
        self.accept()
    
    def should_show_again(self):
        """Return False if user checked 'don't show again'"""
        return not self.dont_show_again.isChecked()

class TestWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ExifTool Warning Dialog Test")
        self.setGeometry(300, 300, 300, 100)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        test_button = QPushButton("Show ExifTool Warning Dialog")
        test_button.clicked.connect(self.show_warning)
        layout.addWidget(test_button)
    
    def show_warning(self):
        dialog = ExifToolWarningDialog(self, None)  # Test with None (no EXIF support)
        result = dialog.exec()
        print(f"Dialog result: {result}")
        print(f"Show again: {dialog.should_show_again()}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TestWindow()
    window.show()
    sys.exit(app.exec())
