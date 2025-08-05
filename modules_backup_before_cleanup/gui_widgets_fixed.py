#!/usr/bin/env python3
"""
Custom GUI widgets for the RenameFiles application.
"""

import os
import webbrowser
from PyQt6.QtWidgets import (
    QListWidget, QDialog, QVBoxLayout, QLabel, QPushButton, QPlainTextEdit,
    QCheckBox, QHBoxLayout, QListWidgetItem, QStyledItemDelegate, QStyle, QApplication
)
from PyQt6.QtCore import Qt, QMimeData, pyqtSignal, QSize
from PyQt6.QtGui import QDrag, QPainter, QFont, QFontMetrics

class CustomItemDelegate(QStyledItemDelegate):
    """Custom delegate for separators in interactive preview"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
    
    def paint(self, painter, option, index):
        """Custom painting for separators"""
        item_type = index.data(Qt.ItemDataRole.UserRole)
        
        if item_type == "separator":
            # Custom painting for separators - no background box
            painter.save()
            painter.setFont(QFont("Arial", 10))
            painter.drawText(option.rect, Qt.AlignmentFlag.AlignCenter, index.data())
            painter.restore()
        else:
            # Use default painting for other items
            super().paint(painter, option, index)

class InteractivePreviewWidget(QListWidget):
    """
    Interactive preview widget that allows drag & drop reordering of filename components.
    The sequential number is always shown at the end and cannot be moved.
    """
    order_changed = pyqtSignal(list)  # Signal emitted when order changes
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.setMaximumHeight(80)  # Höherer Bereich für bessere Sichtbarkeit
        self.setMinimumHeight(65)  # Höherer Bereich für bessere Sichtbarkeit
        self.setFlow(QListWidget.Flow.LeftToRight)
        self.setWrapping(False)
        self.setSpacing(2)  # Zurück auf 2px für besseren Abstand zwischen Items
        
        # Set custom item delegate for separator handling
        self.setItemDelegate(CustomItemDelegate(self))
        
        # Style the widget - kompaktere Version
        self.setStyleSheet("""
            QListWidget {
                border: 2px solid #cccccc;
                border-radius: 6px;
                background-color: #f9f9f9;
                padding: 8px;  /* Zurück auf 8px damit Items vollständig sichtbar sind */
                font-size: 11px;  /* Reduziert von 12px */
            }
            QListWidget::item {
                background-color: #e6f3ff;
                border: 1px solid #b3d9ff;
                border-radius: 2px;  /* Kleinerer border-radius */
                padding: 1px 3px;  /* Etwas mehr Padding für bessere Proportionen */
                margin: 0px;  /* Kein Margin */
                font-weight: bold;
                text-align: center;
                font-size: 8px;  /* Erhöht von 7px auf 8px für bessere Sichtbarkeit */
                /* Keine feste min-width - lässt die Box sich an den Text anpassen */
            }
            QListWidget::item:selected {
                background-color: #cce7ff;
                border: 2px solid #0078d4;
            }
            QListWidget::item:hover {
                background-color: #d9ecff;
                border: 1px solid #66c2ff;
            }
            /* Separatoren erhalten keine Box-Styling */
        """)
        
        # Add drag & drop visual feedback
        self.setAcceptDrops(True)
        self.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        
        # Connect signals
        self.itemChanged.connect(self._on_item_changed)
        
        # Store separator
        self.separator = "-"
        
        # Initialize with empty state
        self.components = []
        self.fixed_number = "001"
        
    def set_separator(self, separator):
        """Set the separator character"""
        self.separator = "" if separator == "None" else separator
        self.update_display()
    
    def set_components(self, components, number="001"):
        """Set the filename components to display"""
        self.components = components.copy()
        self.fixed_number = number
        self.update_display()
    
    def update_display(self):
        """Update the visual display of components"""
        self.clear()
        
        # If no components, show helpful placeholder
        if not self.components:
            placeholder_item = QListWidgetItem("Drop files or enter text above to see preview")
            placeholder_item.setFlags(Qt.ItemFlag.NoItemFlags)
            placeholder_item.setData(Qt.ItemDataRole.UserRole, "placeholder")
            placeholder_item.setForeground(Qt.GlobalColor.gray)
            placeholder_item.setFont(QFont("Arial", 10, QFont.Weight.Normal))
            placeholder_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.addItem(placeholder_item)
            return
        
        # Add components and separators in the correct order
        for i, component in enumerate(self.components):
            # Add the component
            item = QListWidgetItem(component)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsDragEnabled)
            item.setData(Qt.ItemDataRole.UserRole, "component")
            item.setToolTip("Drag to swap position with another component")
            
            # Calculate optimal size for the component based on text
            # Use QFont to measure the text size
            font = QFont("Arial", 8)  # Same font as in CSS
            font.setBold(True)
            metrics = QFontMetrics(font)
            text_width = metrics.horizontalAdvance(component)
            text_height = metrics.height()
            
            # Add 10% padding around the text (3px horizontal, 1px vertical padding from CSS)
            optimal_width = text_width + 17  # 3px padding on each side
            optimal_height = text_height   # 1px padding top and bottom
            
            # Set the size hint to fit the text perfectly
            item.setSizeHint(QSize(optimal_width, optimal_height))
            item.setFont(font)  # Ensure consistent font
            
            self.addItem(item)
            
            # Add separator after each component (except the last one)
            if self.separator and i < len(self.components) - 1:
                sep_item = QListWidgetItem(self.separator)
                sep_item.setFlags(Qt.ItemFlag.NoItemFlags)  # Not selectable or draggable
                sep_item.setData(Qt.ItemDataRole.UserRole, "separator")
                # Separator should be just big enough for the separator character
                sep_item.setSizeHint(QSize(8, 20))  # Kompakte Separator-Größe
                self.addItem(sep_item)
        
        # Add final separator before number (only if we have components)
        if self.separator and self.components:
            sep_item = QListWidgetItem(self.separator)
            sep_item.setFlags(Qt.ItemFlag.NoItemFlags)
            sep_item.setData(Qt.ItemDataRole.UserRole, "separator")
            sep_item.setToolTip("Separator character")
            # Kompakte Separator-Größe
            sep_item.setSizeHint(QSize(8, 20))  # Kleinere, angemessene Separator-Größe
            self.addItem(sep_item)
        
        # Add fixed number at the end (not draggable)
        number_item = QListWidgetItem(self.fixed_number)
        number_item.setFlags(Qt.ItemFlag.NoItemFlags)  # Not selectable or draggable
        number_item.setData(Qt.ItemDataRole.UserRole, "number")
        number_item.setBackground(Qt.GlobalColor.yellow)
        number_item.setToolTip("Sequential number (fixed position)")
        
        # Calculate optimal size for the number based on text - use same font size as components
        font = QFont("Arial", 8)  # Same as components
        font.setBold(True)
        number_item.setFont(font)
        
        metrics = QFontMetrics(font)
        text_width = metrics.horizontalAdvance(self.fixed_number)
        text_height = metrics.height()
        
        # Add proper padding around the text (same as components)
        optimal_width = text_width + 17  # 3px padding on each side + margin
        optimal_height = text_height   # 1px padding top and bottom
        
        # Set the size hint to fit the text perfectly
        number_item.setSizeHint(QSize(optimal_width, optimal_height))
        
        self.addItem(number_item)
    
    def get_component_order(self):
        """Get the current order of components (excluding separators and number)"""
        order = []
        for i in range(self.count()):
            item = self.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == "component":
                order.append(item.text())
        return order
    
    def dropEvent(self, event):
        """Handle drop events to swap positions of components"""
        if event.source() == self:
            # Get the dragged item
            dragged_items = self.selectedItems()
            if not dragged_items:
                return
            
            dragged_item = dragged_items[0]
            
            # Only allow moving component items, not separators or numbers
            if dragged_item.data(Qt.ItemDataRole.UserRole) != "component":
                event.ignore()
                return
            
            # Get drop position
            drop_item = self.itemAt(event.position().toPoint())
            
            # Special case: if dropping on number or empty space, move to last position
            if not drop_item or drop_item.data(Qt.ItemDataRole.UserRole) == "number":
                dragged_text = dragged_item.text()
                if dragged_text in self.components:
                    # Move component to last position
                    dragged_index = self.components.index(dragged_text)
                    component = self.components.pop(dragged_index)
                    self.components.append(component)
                    
                    # Update display and emit signal
                    self.update_display()
                    self.order_changed.emit(self.get_component_order())
                event.accept()
                return
            
            # If dropping on separator, find nearest valid component position
            if drop_item and drop_item.data(Qt.ItemDataRole.UserRole) != "component":
                # Find the nearest component position
                drop_row = self.row(drop_item)
                # Look for previous component
                for i in range(drop_row - 1, -1, -1):
                    if self.item(i).data(Qt.ItemDataRole.UserRole) == "component":
                        drop_item = self.item(i)
                        break
                else:
                    # Look for next component
                    for i in range(drop_row + 1, self.count()):
                        if self.item(i).data(Qt.ItemDataRole.UserRole) == "component":
                            drop_item = self.item(i)
                            break
                    else:
                        # No components found, move to last position
                        dragged_text = dragged_item.text()
                        if dragged_text in self.components:
                            dragged_index = self.components.index(dragged_text)
                            component = self.components.pop(dragged_index)
                            self.components.append(component)
                            
                            self.update_display()
                            self.order_changed.emit(self.get_component_order())
                        event.accept()
                        return
            
            # Perform position swap in components list
            dragged_text = dragged_item.text()
            if dragged_text in self.components and drop_item and drop_item.data(Qt.ItemDataRole.UserRole) == "component":
                drop_text = drop_item.text()
                if drop_text in self.components and dragged_text != drop_text:
                    # Find indices of both components
                    dragged_index = self.components.index(dragged_text)
                    drop_index = self.components.index(drop_text)
                    
                    # Swap the positions
                    self.components[dragged_index], self.components[drop_index] = self.components[drop_index], self.components[dragged_index]
                    
                    # Update display and emit signal
                    self.update_display()
                    self.order_changed.emit(self.get_component_order())
        
        event.accept()
    
    def _on_item_changed(self, item):
        """Handle item changes"""
        pass  # We don't allow editing items directly


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("About File Renamer")
        self.setFixedSize(500, 400)
        self.setModal(True)
        
        layout = QVBoxLayout(self)
        
        # Title
        title = QLabel("📸 Advanced File Renaming Tool")
        title.setStyleSheet("font-size: 18px; font-weight: bold; margin: 10px; color: #0066cc;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # Version info
        version = QLabel("Version 3.0.0 - Enhanced GUI Edition")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version.setStyleSheet("font-size: 12px; color: #666; margin-bottom: 20px;")
        layout.addWidget(version)
        
        # Description
        description = QLabel("""
This powerful file renaming tool helps you organize your photos and videos 
with EXIF metadata integration and customizable naming patterns.

🎯 Key Features:
• Batch rename photos and videos
• EXIF metadata extraction (camera, lens, date)
• Customizable filename components and order
• Interactive drag-and-drop preview
• Safety features with undo functionality
• Dark/Light theme support
• Multiple date formats
• Continuous numbering for multi-day shoots

📊 Technical Details:
• Supports ExifTool and Pillow for metadata
• Handles RAW and standard image formats
• Qt6-based modern interface
• Optimized for large file collections
        """)
        description.setWordWrap(True)
        description.setStyleSheet("font-size: 11px; line-height: 1.4; margin: 10px;")
        layout.addWidget(description)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        github_button = QPushButton("🌐 View on GitHub")
        github_button.clicked.connect(lambda: webbrowser.open("https://github.com/YourUsername/file-renamer"))
        github_button.setStyleSheet("QPushButton { padding: 8px 16px; background-color: #0066cc; color: white; border: none; border-radius: 4px; }")
        
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        close_button.setStyleSheet("QPushButton { padding: 8px 16px; }")
        
        button_layout.addWidget(github_button)
        button_layout.addStretch()
        button_layout.addWidget(close_button)
        
        layout.addLayout(button_layout)


class ExifDataDialog(QDialog):
    def __init__(self, file_path, exif_data, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"EXIF Data - {os.path.basename(file_path)}")
        self.setModal(True)
        self.resize(600, 500)
        
        layout = QVBoxLayout(self)
        
        # File info header
        file_info = QLabel(f"📸 File: {os.path.basename(file_path)}")
        file_info.setStyleSheet("font-weight: bold; font-size: 14px; padding: 10px; background-color: #f0f0f0; border-radius: 5px;")
        layout.addWidget(file_info)
        
        # EXIF data display
        exif_text = QPlainTextEdit()
        exif_text.setReadOnly(True)
        exif_text.setFont(QFont("Consolas", 10))
        
        if exif_data:
            # Format EXIF data nicely
            formatted_data = ""
            for key, value in sorted(exif_data.items()):
                if value:  # Only show non-empty values
                    formatted_data += f"{key:<30} : {value}\n"
            exif_text.setPlainText(formatted_data)
        else:
            exif_text.setPlainText("No EXIF data available for this file.")
        
        layout.addWidget(exif_text)
        
        # Action buttons
        button_layout = QHBoxLayout()
        
        copy_button = QPushButton("📋 Copy to Clipboard")
        copy_button.clicked.connect(lambda: QApplication.clipboard().setText(exif_text.toPlainText()))
        
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        
        button_layout.addWidget(copy_button)
        button_layout.addStretch()
        button_layout.addWidget(close_button)
        
        layout.addLayout(button_layout)


class InteractivePreviewInfoDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Interactive Preview - Help")
        self.setModal(True)
        self.resize(550, 450)
        
        layout = QVBoxLayout(self)
        
        # Title
        title = QLabel("🎯 Interactive Preview Guide")
        title.setStyleSheet("font-size: 16px; font-weight: bold; margin: 10px; color: #0066cc;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # Help content
        help_text = QLabel("""
<b>What is the Interactive Preview?</b><br>
The interactive preview shows you exactly how your files will be renamed, with all components in the correct order and with the chosen separator.

<b>🔄 Drag & Drop Reordering:</b><br>
• <b>Drag any component</b> to change the order of filename parts<br>
• <b>Blue boxes</b> = Draggable components (Date, Camera, Lens, etc.)<br>
• <b>Yellow box</b> = Sequential number (always stays at the end)<br>
• <b>Gray separators</b> = Cannot be moved<br>

<b>📝 Component Types:</b><br>
• <b>Date:</b> Photo date from EXIF (format configurable)<br>
• <b>Camera:</b> Camera model from EXIF metadata<br>
• <b>Lens:</b> Lens information from EXIF metadata<br>
• <b>Prefix:</b> Custom text you enter (e.g., "Sony")<br>
• <b>Additional:</b> Extra custom text (e.g., "Forest", "Wedding")<br>
• <b>Number:</b> Sequential counter (001, 002, 003...)<br>

<b>⚙️ How to Use:</b><br>
1. Enter your custom text in the Prefix/Additional fields<br>
2. Check/uncheck components you want to include<br>
3. Drag components in the preview to reorder them<br>
4. Choose your separator character<br>
5. Click "Rename Files" when you're happy with the preview<br>

<b>💡 Tips:</b><br>
• The preview updates automatically as you make changes<br>
• Only enabled components appear in the preview<br>
• EXIF data is extracted from your first selected file<br>
• Separators appear between all components automatically
        """)
        help_text.setWordWrap(True)
        help_text.setTextFormat(Qt.TextFormat.RichText)
        help_text.setStyleSheet("font-size: 11px; line-height: 1.5; margin: 15px;")
        layout.addWidget(help_text)
        
        # Close button
        close_button = QPushButton("Got it!")
        close_button.clicked.connect(self.accept)
        close_button.setStyleSheet("QPushButton { padding: 10px 20px; background-color: #0066cc; color: white; border: none; border-radius: 5px; font-weight: bold; }")
        close_button.setDefault(True)
        
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(close_button)
        button_layout.addStretch()
        
        layout.addLayout(button_layout)
