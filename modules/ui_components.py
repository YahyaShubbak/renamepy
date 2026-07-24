#!/usr/bin/env python3
"""
Custom GUI widgets for the RenameFiles application.

Provides interactive preview, drag-and-drop reordering, about/help dialogs,
and EXIF data display components.
"""

import os
import webbrowser
from PyQt6.QtWidgets import (
    QListWidget, QDialog, QVBoxLayout, QLabel, QPushButton, QPlainTextEdit,
    QCheckBox, QHBoxLayout, QListWidgetItem, QStyledItemDelegate, QStyle, QApplication,
    QWidget
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
        self.setMaximumHeight(80)  # Increased height for better component visibility
        self.setMinimumHeight(65)  # Minimum height to prevent component clipping
        self.setFlow(QListWidget.Flow.LeftToRight)
        self.setWrapping(False)
        self.setSpacing(2)  # 2px spacing provides optimal visual separation between items
        
        # Set custom item delegate for separator handling
        self.setItemDelegate(CustomItemDelegate(self))
        
        # Style the widget with compact, optimized layout
        self.setStyleSheet("""
            QListWidget {
                border: 2px solid #cccccc;
                border-radius: 6px;
                background-color: #f9f9f9;
                padding: 8px;  /* 8px padding ensures items are fully visible */
                font-size: 11px;  /* Reduced from 12px for more compact display */
            }
            QListWidget::item {
                background-color: #e6f3ff;
                border: 1px solid #b3d9ff;
                border-radius: 2px;  /* Smaller radius for compact appearance */
                padding: 1px 3px;  /* Balanced padding for optimal proportions */
                margin: 0px;  /* No margin for tight spacing */
                font-weight: bold;
                text-align: center;
                font-size: 8px;  /* Increased from 7px for better readability */
                /* No fixed min-width - allows box to adapt to text length */
            }
            QListWidget::item:selected {
                background-color: #cce7ff;
                border: 2px solid #0078d4;
            }
            QListWidget::item:hover {
                background-color: #d9ecff;
                border: 1px solid #66c2ff;
            }
            /* Separators receive no box styling to maintain visual distinction */
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
        self.fixed_number = number  # Keep for backward compatibility but not used anymore
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
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsDragEnabled | Qt.ItemFlag.ItemIsDropEnabled)
            item.setData(Qt.ItemDataRole.UserRole, "component")
            
            # FLEXIBLE: Highlight number component but make it draggable
            if component == "001" or component.isdigit():
                item.setBackground(Qt.GlobalColor.yellow)
                item.setToolTip("Sequential number (draggable)")
            else:
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
                # Separator sized to fit character while maintaining compact layout
                sep_item.setSizeHint(QSize(8, 20))  # Compact separator size (8px width)
                self.addItem(sep_item)
                
        # FLEXIBLE: No more fixed number - it's now part of components
    
    def get_component_order(self):
        """Get the current order of components (excluding separators and number)"""
        order = []
        for i in range(self.count()):
            item = self.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == "component":
                order.append(item.text())
        return order
        
    def startDrag(self, supportedActions):
        """Override startDrag to ensure drag operations work correctly"""
        item = self.currentItem()
        if item and item.data(Qt.ItemDataRole.UserRole) == "component":
            super().startDrag(supportedActions)
        
    def mousePressEvent(self, event):
        """Handle mouse press events"""
        if event.button() == Qt.MouseButton.LeftButton:
            try:
                pos = event.position().toPoint()
            except AttributeError:
                pos = event.pos()
            item = self.itemAt(pos)
            if item and item.data(Qt.ItemDataRole.UserRole) == "component":
                self.setCurrentItem(item)
        super().mousePressEvent(event)
    
    def dropEvent(self, event):
        """Handle drop events to swap positions of components"""
        if event.source() != self:
            event.ignore()
            return
            
        # Get the dragged item
        dragged_items = self.selectedItems()
        if not dragged_items:
            event.ignore()
            return
            
        dragged_item = dragged_items[0]
        
        # Only allow moving component items, not separators or numbers
        if dragged_item.data(Qt.ItemDataRole.UserRole) != "component":
            event.ignore()
            return
        
        # Get drop position
        try:
            # PyQt6 uses position()
            drop_point = event.position().toPoint()
        except AttributeError:
            # PyQt5 uses pos()
            drop_point = event.pos()
        
        drop_item = self.itemAt(drop_point)
        
        # Get component texts
        dragged_text = dragged_item.text()
        
        # If no drop target or dropping on non-component, move to end
        if not drop_item or drop_item.data(Qt.ItemDataRole.UserRole) != "component":
            if dragged_text in self.components:
                # Move to last position
                self.components.remove(dragged_text)
                self.components.append(dragged_text)
                self.update_display()
                self.order_changed.emit(self.get_component_order())
            event.accept()
            return
        
        # Get drop target text
        drop_text = drop_item.text()
        
        # Swap positions in the components list
        if dragged_text in self.components and drop_text in self.components and dragged_text != drop_text:
            dragged_index = self.components.index(dragged_text)
            drop_index = self.components.index(drop_text)
            
            # Swap positions
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
• Powered by ExifTool for professional metadata extraction
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
        github_button.clicked.connect(lambda: webbrowser.open("https://github.com/YahyaShubbak/renamepy"))
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


class CollapsibleSection(QWidget):
    """A collapsible section with a toggle-button header.

    Used to move less-frequently-used options (continuous counter, EXIF
    date sync, time-shift-related toggles) out of the always-visible
    surface, so the primary naming controls aren't visually competing with
    things most people touch far less often. Collapsed by default.

    Exposes addLayout()/addWidget() so existing UI-setup code that already
    calls those on a plain layout can target this section with a one-line
    change, without needing to restructure how each row itself is built.
    """

    def __init__(self, title, parent=None):
        super().__init__(parent)
        self._title = title

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 4, 0, 0)
        outer.setSpacing(4)

        self.toggle_button = QPushButton()
        self.toggle_button.setCheckable(True)
        self.toggle_button.setChecked(False)
        self.toggle_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_button.setStyleSheet("""
            QPushButton {
                text-align: left;
                padding: 6px 10px;
                border: 1px solid palette(mid);
                border-radius: 4px;
                background-color: palette(button);
            }
            QPushButton:hover {
                background-color: palette(light);
            }
        """)
        self.toggle_button.clicked.connect(self._on_toggled)
        outer.addWidget(self.toggle_button)

        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(6, 6, 0, 2)
        self.content_layout.setSpacing(6)
        outer.addWidget(self.content_widget)

        self.content_widget.setVisible(False)
        self._update_title()

    def _on_toggled(self):
        self.content_widget.setVisible(self.toggle_button.isChecked())
        self._update_title()

    def _update_title(self):
        arrow = "\u25be" if self.toggle_button.isChecked() else "\u25b8"
        self.toggle_button.setText(f"{arrow} {self._title}")

    def addLayout(self, layout):
        self.content_layout.addLayout(layout)

    def addWidget(self, widget):
        self.content_layout.addWidget(widget)
