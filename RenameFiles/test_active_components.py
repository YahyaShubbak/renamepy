#!/usr/bin/env python3
"""
Test für die verbesserte Interactive Preview - zeigt nur aktive Komponenten
"""

import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QLabel, QCheckBox, QLineEdit, QComboBox
from PyQt6.QtCore import Qt

# Import from RenameFiles
from RenameFiles import InteractivePreviewWidget

class TestActiveComponentsWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Test: Nur aktive Komponenten in Preview")
        self.setGeometry(100, 100, 900, 500)
        
        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # Add title
        title = QLabel("🎯 Interactive Preview - Nur aktive Komponenten Test")
        title.setStyleSheet("font-size: 16px; font-weight: bold; margin: 10px;")
        layout.addWidget(title)
        
        # Add controls to simulate main app
        controls_layout = QVBoxLayout()
        
        # Camera Prefix
        prefix_label = QLabel("Kamera Präfix:")
        self.prefix_input = QLineEdit()
        self.prefix_input.setPlaceholderText("z.B. A7R3, D850")
        self.prefix_input.textChanged.connect(self.update_preview)
        controls_layout.addWidget(prefix_label)
        controls_layout.addWidget(self.prefix_input)
        
        # Additional
        additional_label = QLabel("Additional:")
        self.additional_input = QLineEdit()
        self.additional_input.setPlaceholderText("z.B. Birthday, Wedding")
        self.additional_input.textChanged.connect(self.update_preview)
        controls_layout.addWidget(additional_label)
        controls_layout.addWidget(self.additional_input)
        
        # Camera checkbox
        self.camera_checkbox = QCheckBox("Kameramodell in Dateiname einbeziehen")
        self.camera_checkbox.stateChanged.connect(self.update_preview)
        controls_layout.addWidget(self.camera_checkbox)
        
        # Lens checkbox
        self.lens_checkbox = QCheckBox("Objektiv in Dateiname einbeziehen")
        self.lens_checkbox.stateChanged.connect(self.update_preview)
        controls_layout.addWidget(self.lens_checkbox)
        
        # Separator
        sep_label = QLabel("Trennzeichen:")
        self.separator_combo = QComboBox()
        self.separator_combo.addItems(["-", "_", "None"])
        self.separator_combo.currentTextChanged.connect(self.update_preview)
        controls_layout.addWidget(sep_label)
        controls_layout.addWidget(self.separator_combo)
        
        layout.addLayout(controls_layout)
        
        # Add the interactive preview widget
        preview_label = QLabel("📋 Interactive Preview (nur aktive Komponenten):")
        layout.addWidget(preview_label)
        
        self.interactive_preview = InteractivePreviewWidget()
        self.interactive_preview.order_changed.connect(self.on_order_changed)
        layout.addWidget(self.interactive_preview)
        
        # Add status label
        self.status_label = QLabel("Status: Ready")
        self.status_label.setStyleSheet("color: green; margin: 10px;")
        layout.addWidget(self.status_label)
        
        # Add test instructions
        instructions = QLabel("""
📖 Test Szenarien:
1. Nur Datum → Preview zeigt nur: 2025-07-21-01.ARW
2. Präfix eingeben → Preview zeigt: 2025-07-21-A7R3-01.ARW
3. Kamera aktivieren → Preview zeigt: 2025-07-21-A7R3-ILCE-7RM3-01.ARW
4. Additional eingeben → Preview zeigt: 2025-07-21-A7R3-Birthday-ILCE-7RM3-01.ARW
5. Objektiv aktivieren → Preview zeigt: 2025-07-21-A7R3-Birthday-ILCE-7RM3-FE24-70-01.ARW
        """)
        instructions.setStyleSheet("color: #666; font-size: 12px; margin: 10px; background-color: #f0f0f0; padding: 10px; border-radius: 5px;")
        layout.addWidget(instructions)
        
        # Initialize with empty state
        self.update_preview()
    
    def update_preview(self):
        """Update preview based on current control states"""
        # Simulate the real application logic
        camera_prefix = self.prefix_input.text().strip()
        additional = self.additional_input.text().strip()
        use_camera = self.camera_checkbox.isChecked()
        use_lens = self.lens_checkbox.isChecked()
        separator = self.separator_combo.currentText()
        
        # Simulate EXIF data
        formatted_date = "2025-07-21"
        camera_model = "ILCE-7RM3"  # Simulated
        lens_model = "FE24-70"     # Simulated
        
        # Build component list - only include active components (like in real app)
        display_components = []
        component_mapping = {
            "Date": formatted_date,  # Date is always included
            "Prefix": camera_prefix if camera_prefix else None,  # Only if text entered
            "Additional": additional if additional else None,  # Only if text entered
            "Camera": camera_model if (use_camera and camera_model) else None,  # Only if checkbox checked AND value exists
            "Lens": lens_model if (use_lens and lens_model) else None  # Only if checkbox checked AND value exists
        }
        
        # Default order for testing
        custom_order = ["Date", "Prefix", "Additional", "Camera", "Lens"]
        
        # Add components in order, but only if they have values and are active
        for component_name in custom_order:
            value = component_mapping.get(component_name)
            if value:  # Only add non-empty and active components
                display_components.append(value)
        
        # Update the interactive preview
        self.interactive_preview.set_separator(separator)
        self.interactive_preview.set_components(display_components, "01")
        
        # Update status
        preview_text = self.interactive_preview.get_preview_text()
        self.status_label.setText(f"Preview: {preview_text}")
        
        # Debug output
        print(f"Active components: {display_components}")
        print(f"Generated filename: {preview_text}")
    
    def on_order_changed(self, new_order):
        """Handle order changes from drag & drop"""
        preview_text = self.interactive_preview.get_preview_text()
        self.status_label.setText(f"✅ Reihenfolge geändert! Preview: {preview_text}")

def main():
    app = QApplication(sys.argv)
    
    print("🧪 Test: Nur aktive Komponenten in Interactive Preview")
    print("=" * 60)
    print("Dieser Test zeigt, dass nur aktive Komponenten angezeigt werden:")
    print("• Kamera/Objektiv nur wenn Checkbox aktiviert")
    print("• Präfix/Additional nur wenn Text eingegeben")
    print("• Datum immer enthalten")
    print("=" * 60)
    
    window = TestActiveComponentsWindow()
    window.show()
    
    print("✅ Test gestartet!")
    print("👆 Probieren Sie verschiedene Kombinationen aus")
    
    return app.exec()

if __name__ == "__main__":
    sys.exit(main())
