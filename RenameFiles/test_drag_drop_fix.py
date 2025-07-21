#!/usr/bin/env python3
"""
Test für die korrigierte Drag & Drop Funktionalität
Behebt den ValueError: 'FE-50mm-F1.8' is not in list
"""

import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QLabel, QPushButton
from PyQt6.QtCore import Qt

# Import from RenameFiles
from RenameFiles import InteractivePreviewWidget

class TestDragDropWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Test: Drag & Drop Korrektur")
        self.setGeometry(100, 100, 900, 400)
        
        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # Add title
        title = QLabel("🔧 Test: Drag & Drop Korrektur - ValueError Fix")
        title.setStyleSheet("font-size: 16px; font-weight: bold; margin: 10px;")
        layout.addWidget(title)
        
        # Test setup buttons
        button_layout = QVBoxLayout()
        
        btn1 = QPushButton("Test 1: Problematische Kombination (FE-50mm-F1.8)")
        btn1.clicked.connect(lambda: self.test_problematic_case())
        button_layout.addWidget(btn1)
        
        btn2 = QPushButton("Test 2: Standard Kombination")
        btn2.clicked.connect(lambda: self.test_standard_case())
        button_layout.addWidget(btn2)
        
        btn3 = QPushButton("Test 3: Viele Komponenten")
        btn3.clicked.connect(lambda: self.test_many_components())
        button_layout.addWidget(btn3)
        
        layout.addLayout(button_layout)
        
        # Add the interactive preview widget
        preview_label = QLabel("📋 Interactive Preview - Testen Sie Drag & Drop:")
        layout.addWidget(preview_label)
        
        self.interactive_preview = InteractivePreviewWidget()
        self.interactive_preview.order_changed.connect(self.on_order_changed)
        layout.addWidget(self.interactive_preview)
        
        # Add status label
        self.status_label = QLabel("Status: Wählen Sie einen Test und probieren Sie Drag & Drop")
        self.status_label.setStyleSheet("color: blue; margin: 10px;")
        layout.addWidget(self.status_label)
        
        # Instructions
        instructions = QLabel("""
📖 Testanweisungen:
1. Klicken Sie auf einen Test-Button
2. Ziehen Sie die blauen Komponenten per Drag & Drop
3. Überprüfen Sie, dass kein ValueError auftritt
4. Die gelbe Nummer sollte immer am Ende bleiben
        """)
        instructions.setStyleSheet("color: #666; font-size: 12px; margin: 10px; background-color: #f0f0f0; padding: 10px; border-radius: 5px;")
        layout.addWidget(instructions)
        
    def test_problematic_case(self):
        """Test the case that was causing the ValueError"""
        components = ["2025-07-21", "A7R3", "ILCE-7RM3", "FE-50mm-F1.8"]
        separator = "-"
        
        self.interactive_preview.set_separator(separator)
        self.interactive_preview.set_components(components, "78")
        
        self.status_label.setText("Test 1 geladen: Problematische Kombination mit FE-50mm-F1.8")
        print("\n=== Test 1: Problematische Kombination ===")
        print(f"Komponenten: {components}")
        print("Versuchen Sie jetzt Drag & Drop!")
    
    def test_standard_case(self):
        """Test a standard case"""
        components = ["2025-07-21", "Birthday", "A7R3"]
        separator = "-"
        
        self.interactive_preview.set_separator(separator)
        self.interactive_preview.set_components(components, "05")
        
        self.status_label.setText("Test 2 geladen: Standard Kombination")
        print("\n=== Test 2: Standard Kombination ===")
        print(f"Komponenten: {components}")
    
    def test_many_components(self):
        """Test with many components"""
        components = ["2025-07-21", "A7R3", "Wedding", "ILCE-7RM3", "FE24-70", "Church"]
        separator = "_"
        
        self.interactive_preview.set_separator(separator)
        self.interactive_preview.set_components(components, "123")
        
        self.status_label.setText("Test 3 geladen: Viele Komponenten mit Underscore")
        print("\n=== Test 3: Viele Komponenten ===")
        print(f"Komponenten: {components}")
    
    def on_order_changed(self, new_order):
        """Handle order changes from drag & drop"""
        try:
            preview_text = self.interactive_preview.get_preview_text()
            self.status_label.setText(f"✅ Drag & Drop erfolgreich! Neue Reihenfolge: {' → '.join(new_order)}")
            print(f"✅ Neue Reihenfolge: {new_order}")
            print(f"✅ Preview: {preview_text}")
        except Exception as e:
            self.status_label.setText(f"❌ Fehler beim Drag & Drop: {e}")
            print(f"❌ Fehler: {e}")

def main():
    app = QApplication(sys.argv)
    
    print("🔧 Test: Drag & Drop Korrektur")
    print("=" * 50)
    print("Dieser Test überprüft die Behebung des ValueError:")
    print("'FE-50mm-F1.8' is not in list")
    print("=" * 50)
    
    window = TestDragDropWindow()
    window.show()
    
    print("✅ Test gestartet!")
    print("👆 Klicken Sie auf Test-Buttons und probieren Sie Drag & Drop")
    
    return app.exec()

if __name__ == "__main__":
    sys.exit(main())
