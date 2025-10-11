#!/usr/bin/env python3
"""
ExifTool Warning Dialog - shown when ExifTool is not installed
"""

import webbrowser
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QCheckBox, QStyle
from PyQt6.QtCore import Qt


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
ExifTool is a powerful library for reading and writing metadata in image and video files.

<b>Why ExifTool is recommended:</b><br>
• <b>Complete RAW support:</b> Works with all camera RAW formats<br>
• <b>Video metadata:</b> Extracts date, camera, and technical data from videos<br>
• <b>More metadata:</b> Extracts camera, lens, and date information more reliably<br>

{fallback_text}

<b>How to install ExifTool:</b><br>
1. Download from: <a href="https://exiftool.org/install.html">https://exiftool.org/install.html</a><br>
2. Extract the COMPLETE ZIP archive to your program folder<br>
3. Restart this application<br>
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
        install_button.clicked.connect(self.open_download_page)
        
        continue_button = QPushButton(continue_button_text)
        continue_button.clicked.connect(self.accept)
        
        button_layout.addWidget(install_button)
        button_layout.addWidget(continue_button)
        layout.addLayout(button_layout)
    
    def open_download_page(self):
        """Open the ExifTool download page in default browser"""
        webbrowser.open("https://exiftool.org/install.html")
        self.accept()
