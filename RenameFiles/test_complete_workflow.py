#!/usr/bin/env python3
"""
Complete workflow test for the Interactive Preview System
This demonstrates the full drag & drop functionality in action.
"""

import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QLabel, QComboBox
from PyQt6.QtCore import Qt

# Import the InteractivePreviewWidget from RenameFiles
from RenameFiles import InteractivePreviewWidget

class TestMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Interactive Preview - Complete Workflow Test")
        self.setGeometry(100, 100, 800, 400)
        
        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # Add title
        title = QLabel("🎯 Interactive Filename Preview - Drag & Drop Test")
        title.setStyleSheet("font-size: 16px; font-weight: bold; margin: 10px;")
        layout.addWidget(title)
        
        # Add separator selector
        sep_layout = QVBoxLayout()
        sep_label = QLabel("Separator:")
        self.separator_combo = QComboBox()
        self.separator_combo.addItems(["-", "_", "None"])
        self.separator_combo.currentTextChanged.connect(self.update_separator)
        
        sep_layout.addWidget(sep_label)
        sep_layout.addWidget(self.separator_combo)
        layout.addLayout(sep_layout)
        
        # Add the interactive preview widget
        preview_label = QLabel("📋 Preview (Drag components to reorder):")
        layout.addWidget(preview_label)
        
        self.interactive_preview = InteractivePreviewWidget()
        self.interactive_preview.order_changed.connect(self.on_order_changed)
        layout.addWidget(self.interactive_preview)
        
        # Add status label
        self.status_label = QLabel("Status: Ready - Drag components to change filename order")
        self.status_label.setStyleSheet("color: green; margin: 10px;")
        layout.addWidget(self.status_label)
        
        # Add instructions
        instructions = QLabel("""
📖 Instructions:
• Blue items = Draggable components (date, camera, etc.)
• Gray items = Separators (-, _, or no separator)
• Yellow item = Sequential number (always stays at end)
• Drag blue components to reorder them
• Sequential number automatically stays at the end
        """)
        instructions.setStyleSheet("color: #666; font-size: 12px; margin: 10px;")
        layout.addWidget(instructions)
        
        # Initialize with sample data
        self.setup_sample_data()
    
    def setup_sample_data(self):
        """Setup sample filename data for testing"""
        components = ["2025-07-21", "Wedding", "A7R3", "ILCE-7RM3", "FE24-70"]
        separator = "-"
        number = 42
        
        # Populate the preview widget
        self.interactive_preview.populate(components, separator, number)
        self.status_label.setText(f"Preview: {self.interactive_preview.get_preview_text()}")
    
    def update_separator(self, separator):
        """Update separator when combo box changes"""
        if separator == "None":
            separator = None
        
        # Get current state
        current_order = self.interactive_preview.get_component_order()
        
        # Repopulate with new separator
        self.interactive_preview.populate(current_order, separator, 42)
        self.status_label.setText(f"Preview: {self.interactive_preview.get_preview_text()}")
    
    def on_order_changed(self, new_order):
        """Handle order changes from drag & drop"""
        preview_text = self.interactive_preview.get_preview_text()
        self.status_label.setText(f"✅ Order changed! Preview: {preview_text}")
        print(f"New component order: {new_order}")
        print(f"Generated filename: {preview_text}")

def main():
    app = QApplication(sys.argv)
    
    print("🚀 Starting Interactive Preview Complete Workflow Test")
    print("=" * 60)
    print("This test demonstrates the full drag & drop functionality:")
    print("1. Visual component separation (blue=draggable, gray=separator, yellow=number)")
    print("2. Drag & drop reordering of filename components")
    print("3. Sequential number always stays at end")
    print("4. Real-time preview text generation")
    print("5. Multiple separator support")
    print("=" * 60)
    
    window = TestMainWindow()
    window.show()
    
    print("✅ Application started successfully!")
    print("👆 Try dragging the blue components to reorder them")
    print("📝 The yellow sequential number will always stay at the end")
    
    return app.exec()

if __name__ == "__main__":
    sys.exit(main())
