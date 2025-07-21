#!/usr/bin/env python3
"""
Test für die verbesserte Drag & Drop Funktionalität
Jetzt sollte das Ziehen auf ein Element es NACH diesem Element einfügen
"""

import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QLabel, QPushButton
from PyQt6.QtCore import Qt

# Import from RenameFiles
from RenameFiles import InteractivePreviewWidget

class TestIntuitiveDropWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Test: Intuitive Drag & Drop")
        self.setGeometry(100, 100, 900, 500)
        
        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # Add title
        title = QLabel("🎯 Test: Intuitive Drag & Drop - Element auf Element ziehen")
        title.setStyleSheet("font-size: 16px; font-weight: bold; margin: 10px;")
        layout.addWidget(title)
        
        # Test setup buttons
        button_layout = QVBoxLayout()
        
        btn1 = QPushButton("Test 1: Einfache Reihenfolge [A, B, C]")
        btn1.clicked.connect(lambda: self.setup_test("simple"))
        button_layout.addWidget(btn1)
        
        btn2 = QPushButton("Test 2: Komplexe Reihenfolge [Datum, Kamera, Event, Objektiv]")
        btn2.clicked.connect(lambda: self.setup_test("complex"))
        button_layout.addWidget(btn2)
        
        btn3 = QPushButton("Test 3: Viele Elemente [A, B, C, D, E, F]")
        btn3.clicked.connect(lambda: self.setup_test("many"))
        button_layout.addWidget(btn3)
        
        layout.addLayout(button_layout)
        
        # Add the interactive preview widget
        preview_label = QLabel("📋 Interactive Preview - Ziehen Sie Elemente direkt auf andere Elemente:")
        layout.addWidget(preview_label)
        
        self.interactive_preview = InteractivePreviewWidget()
        self.interactive_preview.order_changed.connect(self.on_order_changed)
        layout.addWidget(self.interactive_preview)
        
        # Add status label
        self.status_label = QLabel("Status: Wählen Sie einen Test")
        self.status_label.setStyleSheet("color: blue; margin: 10px;")
        layout.addWidget(self.status_label)
        
        # Add test instructions
        instructions = QLabel("""
📖 Test der intuitiven Drag & Drop Funktionalität:

✅ SOLL FUNKTIONIEREN:
• Element A auf Element B ziehen → A wird NACH B eingefügt
• Element B auf Element A ziehen → B wird NACH A eingefügt
• Erstes Element auf zweites ziehen → Erstes wird nach zweitem eingefügt

❌ VORHER (Problem):
• Man musste genau auf den Separator ziehen
• Ziehen auf Element hatte keine Wirkung

🎯 JETZT (Lösung):
• Ziehen direkt auf Element funktioniert intuitiv
• Element wird automatisch NACH dem Ziel-Element eingefügt
        """)
        instructions.setStyleSheet("color: #666; font-size: 11px; margin: 10px; background-color: #f0f0f0; padding: 10px; border-radius: 5px;")
        layout.addWidget(instructions)
        
    def setup_test(self, test_type):
        """Setup different test scenarios"""
        if test_type == "simple":
            components = ["A", "B", "C"]
            self.status_label.setText("Test 1: Einfache Reihenfolge - Probieren Sie: A auf B ziehen")
            
        elif test_type == "complex":
            components = ["2025-07-21", "A7R3", "Wedding", "FE24-70"]
            self.status_label.setText("Test 2: Komplexe Reihenfolge - Probieren Sie: A7R3 auf Wedding ziehen")
            
        elif test_type == "many":
            components = ["A", "B", "C", "D", "E", "F"]
            self.status_label.setText("Test 3: Viele Elemente - Probieren Sie verschiedene Kombinationen")
        
        # Update the preview
        self.interactive_preview.set_separator("-")
        self.interactive_preview.set_components(components, "01")
        
        print(f"\n=== {test_type.upper()} TEST ===")
        print(f"Start-Reihenfolge: {components}")
        print("Versuchen Sie jetzt Drag & Drop!")
    
    def on_order_changed(self, new_order):
        """Handle order changes from drag & drop"""
        try:
            preview_text = self.interactive_preview.get_preview_text()
            self.status_label.setText(f"✅ Neue Reihenfolge: {' → '.join(new_order)}")
            
            print(f"✅ Drag & Drop erfolgreich!")
            print(f"   Neue Reihenfolge: {new_order}")
            print(f"   Preview: {preview_text}")
            
        except Exception as e:
            self.status_label.setText(f"❌ Fehler beim Drag & Drop: {e}")
            print(f"❌ Fehler: {e}")

def main():
    app = QApplication(sys.argv)
    
    print("🎯 Test: Intuitive Drag & Drop Funktionalität")
    print("=" * 60)
    print("Dieser Test überprüft die verbesserte Drag & Drop Logik:")
    print("• Element auf Element ziehen sollte es NACH dem Ziel einfügen")
    print("• Kein Ziehen auf Separatoren mehr nötig")
    print("• Intuitive Bedienung")
    print("=" * 60)
    
    window = TestIntuitiveDropWindow()
    window.show()
    
    print("✅ Test gestartet!")
    print("👆 Wählen Sie einen Test und probieren Sie Drag & Drop")
    print("🎯 Besonders testen: Erstes Element auf zweites Element ziehen")
    
    return app.exec()

if __name__ == "__main__":
    sys.exit(main())
