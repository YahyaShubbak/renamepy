#!/usr/bin/env python3
"""
Test script for compact UI with smaller separators and boxes
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget
from RenameFiles import InteractivePreviewWidget

class TestApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Test: Compact UI")
        self.setGeometry(100, 100, 600, 200)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # Create interactive preview
        self.preview = InteractivePreviewWidget()
        self.preview.set_separator("-")
        
        # Test with sample data
        components = ["2025-07-25", "sony", "summer", "001"]
        self.preview.set_components(components[:-1], components[-1])
        
        layout.addWidget(self.preview)

def main():
    app = QApplication(sys.argv)
    window = TestApp()
    window.show()
    
    print("Testing compact UI:")
    print("- Separatoren sind jetzt kleiner (Font 12 statt 16)")
    print("- Boxes sind 30% niedriger (38px statt 55px)")
    print("- Boxes sind 20% enger (padding 2px 5px statt 3px 6px)")
    print("- Separator-Größe: 12x28 statt 20x40")
    print("- Schriftgröße reduziert auf 9px")
    
    return app.exec()

if __name__ == "__main__":
    main()
