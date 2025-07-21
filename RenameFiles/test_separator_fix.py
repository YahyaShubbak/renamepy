#!/usr/bin/env python3
"""
Test für die korrigierte Separator-Logik
"""

import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QLabel, QCheckBox, QLineEdit, QComboBox, QPushButton
from PyQt6.QtCore import Qt

# Import from RenameFiles
from RenameFiles import InteractivePreviewWidget

class TestSeparatorWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Test: Separator Korrektur")
        self.setGeometry(100, 100, 900, 400)
        
        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # Add title
        title = QLabel("🔧 Test: Separator Korrektur - Kein zusätzlicher '-' am Anfang")
        title.setStyleSheet("font-size: 16px; font-weight: bold; margin: 10px;")
        layout.addWidget(title)
        
        # Add controls
        controls_layout = QVBoxLayout()
        
        # Test buttons for different scenarios
        button_layout = QVBoxLayout()
        
        btn1 = QPushButton("Test 1: Nur Datum")
        btn1.clicked.connect(lambda: self.test_scenario("only_date"))
        button_layout.addWidget(btn1)
        
        btn2 = QPushButton("Test 2: Datum + Präfix")
        btn2.clicked.connect(lambda: self.test_scenario("date_prefix"))
        button_layout.addWidget(btn2)
        
        btn3 = QPushButton("Test 3: Datum + Präfix + Additional")
        btn3.clicked.connect(lambda: self.test_scenario("date_prefix_additional"))
        button_layout.addWidget(btn3)
        
        btn4 = QPushButton("Test 4: Vollständig (alle Komponenten)")
        btn4.clicked.connect(lambda: self.test_scenario("full"))
        button_layout.addWidget(btn4)
        
        btn5 = QPushButton("Test 5: Ohne Separator")
        btn5.clicked.connect(lambda: self.test_scenario("no_separator"))
        button_layout.addWidget(btn5)
        
        layout.addLayout(button_layout)
        
        # Separator selector
        sep_label = QLabel("Trennzeichen:")
        self.separator_combo = QComboBox()
        self.separator_combo.addItems(["-", "_", "None"])
        self.separator_combo.currentTextChanged.connect(self.update_current_test)
        layout.addWidget(sep_label)
        layout.addWidget(self.separator_combo)
        
        # Add the interactive preview widget
        preview_label = QLabel("📋 Interactive Preview:")
        layout.addWidget(preview_label)
        
        self.interactive_preview = InteractivePreviewWidget()
        self.interactive_preview.order_changed.connect(self.on_order_changed)
        layout.addWidget(self.interactive_preview)
        
        # Add status label
        self.status_label = QLabel("Status: Wählen Sie einen Test")
        self.status_label.setStyleSheet("color: blue; margin: 10px;")
        layout.addWidget(self.status_label)
        
        # Expected results
        self.expected_label = QLabel("")
        self.expected_label.setStyleSheet("color: green; margin: 10px; font-family: monospace;")
        layout.addWidget(self.expected_label)
        
        # Current test scenario
        self.current_scenario = None
        
    def test_scenario(self, scenario):
        """Test different component scenarios"""
        self.current_scenario = scenario
        separator = self.separator_combo.currentText()
        
        if scenario == "only_date":
            components = ["2025-07-21"]
            expected = "2025-07-21-01.ARW" if separator == "-" else ("2025-07-21_01.ARW" if separator == "_" else "2025-07-2101.ARW")
            
        elif scenario == "date_prefix":
            components = ["2025-07-21", "A7R3"]
            expected = "2025-07-21-A7R3-01.ARW" if separator == "-" else ("2025-07-21_A7R3_01.ARW" if separator == "_" else "2025-07-21A7R301.ARW")
            
        elif scenario == "date_prefix_additional":
            components = ["2025-07-21", "A7R3", "Birthday"]
            expected = "2025-07-21-A7R3-Birthday-01.ARW" if separator == "-" else ("2025-07-21_A7R3_Birthday_01.ARW" if separator == "_" else "2025-07-21A7R3Birthday01.ARW")
            
        elif scenario == "full":
            components = ["2025-07-21", "A7R3", "Birthday", "ILCE-7RM3", "FE24-70"]
            expected = "2025-07-21-A7R3-Birthday-ILCE-7RM3-FE24-70-01.ARW" if separator == "-" else ("2025-07-21_A7R3_Birthday_ILCE-7RM3_FE24-70_01.ARW" if separator == "_" else "2025-07-21A7R3BirthdayILCE-7RM3FE24-7001.ARW")
            
        elif scenario == "no_separator":
            components = ["2025-07-21", "A7R3", "Birthday"]
            separator = "None"
            self.separator_combo.setCurrentText("None")
            expected = "2025-07-21A7R3Birthday01.ARW"
        
        # Update the preview
        self.interactive_preview.set_separator(separator)
        self.interactive_preview.set_components(components, "01")
        
        # Show results
        actual = self.interactive_preview.get_preview_text()
        self.status_label.setText(f"Test: {scenario}")
        self.expected_label.setText(f"Erwartet: {expected}\nTatsächlich: {actual}\n{'✅ KORREKT' if actual == expected else '❌ FEHLER'}")
        
        print(f"\n=== Test: {scenario} ===")
        print(f"Komponenten: {components}")
        print(f"Separator: '{separator}'")
        print(f"Erwartet: {expected}")
        print(f"Tatsächlich: {actual}")
        print(f"Status: {'✅ KORREKT' if actual == expected else '❌ FEHLER'}")
    
    def update_current_test(self):
        """Update current test when separator changes"""
        if self.current_scenario:
            self.test_scenario(self.current_scenario)
    
    def on_order_changed(self, new_order):
        """Handle order changes from drag & drop"""
        preview_text = self.interactive_preview.get_preview_text()
        self.status_label.setText(f"✅ Reihenfolge geändert! Preview: {preview_text}")

def main():
    app = QApplication(sys.argv)
    
    print("🔧 Test: Separator Korrektur")
    print("=" * 50)
    print("Überprüfung der korrigierten Separator-Logik:")
    print("• Kein zusätzlicher '-' am Anfang")
    print("• Korrekte Separator zwischen Komponenten")
    print("• Separator vor der Sequenznummer")
    print("=" * 50)
    
    window = TestSeparatorWindow()
    window.show()
    
    print("✅ Test gestartet!")
    print("👆 Klicken Sie auf die Test-Buttons")
    
    return app.exec()

if __name__ == "__main__":
    sys.exit(main())
