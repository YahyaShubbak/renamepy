#!/usr/bin/env python3
"""
Custoclass InteractivePreviewWidget(QListWidget):
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
            from PyQt6.QtGui import QFontMetrics
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
        
        from PyQt6.QtGui import QFontMetrics
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
        pass  # We don't allow editing items directlyr the RenameFiles application.
"""

import os
import webbrowser
from PyQt6.QtWidgets import (
    QListWidget, QDialog, QVBoxLayout, QLabel, QPushButton, QPlainTextEdit,
    QCheckBox, QHBoxLayout, QListWidgetItem, QStyledItemDelegate, QStyle
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
    
    def get_preview_text(self):
        """Get the complete preview text as it would appear in filename"""
        if not self.components:
            return f"{self.fixed_number}.ARW"
        
        if self.separator:
            return self.separator.join(self.components + [self.fixed_number]) + ".ARW"
        else:
            return "".join(self.components + [self.fixed_number]) + ".ARW"
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
                    self.items_reordered.emit()
                event.accept()
                return
            
            # If dropping on separator, find the adjacent component
            if drop_item.data(Qt.ItemDataRole.UserRole) == "separator":
                drop_index = self.row(drop_item)
                # Find the next component item
                for next_index in range(drop_index + 1, self.count()):
                    next_item = self.item(next_index)
                    if next_item.data(Qt.ItemDataRole.UserRole) == "component":
                        drop_item = next_item
                        break
                else:
                    # No component found after separator, move to end
                    dragged_text = dragged_item.text()
                    if dragged_text in self.components:
                        dragged_index = self.components.index(dragged_text)
                        component = self.components.pop(dragged_index)
                        self.components.append(component)
                        
                        self.update_display()
                        self.order_changed.emit(self.get_component_order())
                        self.items_reordered.emit()
                    event.accept()
                    return
            
            # Handle component-to-component drops
            if drop_item.data(Qt.ItemDataRole.UserRole) == "component":
                dragged_text = dragged_item.text()
                drop_text = drop_item.text()
                
                if dragged_text in self.components and drop_text in self.components:
                    # Swap positions
                    dragged_index = self.components.index(dragged_text)
                    drop_index = self.components.index(drop_text)
                    
                    # Remove dragged component
                    component = self.components.pop(dragged_index)
                    
                    # Insert at drop position (adjust index if necessary)
                    if dragged_index < drop_index:
                        drop_index -= 1
                    
                    self.components.insert(drop_index, component)
                    
                    # Update display and emit signal
                    self.update_display()
                    self.order_changed.emit(self.get_component_order())
                    self.items_reordered.emit()
            
            event.accept()
        else:
            super().dropEvent(event)
    
    def _on_item_changed(self, item):
        """Handle item changes"""
        # This could be used for inline editing if needed
        pass
    
    def get_preview_text(self):
        """Get the complete preview text with separator"""
        if not self.components:
            return "No components selected"
        
        all_components = self.components + [self.fixed_number]
        if self.separator:
            return self.separator.join(all_components)
        else:
            return "".join(all_components)
    
    def add_separator(self):
        """Add a separator to the preview (placeholder method)"""
        # In the original implementation, separators are handled differently
        # This is a compatibility method
        pass

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
ExifTool is a powerful library for reading and writing metadata in image and video files. It provides the most comprehensive and reliable EXIF/metadata extraction available.

<b>Why ExifTool is recommended:</b><br>
• <b>Complete RAW support:</b> Works with all camera RAW formats (ARW, CR2, NEF, DNG, etc.)<br>
• <b>Video metadata:</b> Extracts date, camera, and technical data from videos<br>
• <b>More metadata:</b> Extracts camera, lens, and date information more reliably<br>
• <b>Professional grade:</b> Used by photographers and software worldwide<br>
• <b>Always up-to-date:</b> Supports the latest camera models<br>

{fallback_text}

<b>CRITICAL: How to install ExifTool correctly:</b><br>
1. Download from: <a href="https://exiftool.org/install.html">https://exiftool.org/install.html</a><br>
2. <b>Extract the COMPLETE ZIP archive</b> to your program folder<br>
3. <b>Do NOT copy just the exiftool.exe file!</b> The complete folder with all dependencies is required<br>
4. Required folder structure:<br>
   &nbsp;&nbsp;&nbsp;📁 exiftool-13.32_64/<br>
   &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;⚙️ exiftool.exe<br>
   &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;⚙️ perl.exe<br>
   &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;⚙️ perl532.dll<br>
   &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;📁 lib/ (with Perl modules)<br>
   &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;📁 exiftool_files/<br>
5. Restart this application<br>

<b style="color: #d83b01;">⚠️ WARNING:</b> Copying only the exiftool.exe file will cause the application to crash!<br>
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
