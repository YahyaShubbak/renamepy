#!/usr/bin/env python3
"""
Custom GUI widgets for the RenameFiles application.

Provides the interactive (drag-and-drop) filename preview and a collapsible
options section.
"""

from PyQt6.QtWidgets import (
    QListWidget, QVBoxLayout, QPushButton, QListWidgetItem, QStyledItemDelegate, QWidget
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QFont, QFontMetrics

class CustomItemDelegate(QStyledItemDelegate):
    """Custom delegate for separators in interactive preview"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
    
    def paint(self, painter, option, index):
        """Custom painting for separators"""
        item_type = index.data(Qt.ItemDataRole.UserRole)  # ITEM_TYPE_ROLE
        
        if item_type == "separator":
            # Custom painting for separators - no background box
            painter.save()
            painter.setFont(QFont("Arial", 10))
            painter.drawText(option.rect, Qt.AlignmentFlag.AlignCenter, index.data())
            painter.restore()
        else:
            # Use default painting for other items
            super().paint(painter, option, index)

# Item data roles of the interactive preview
ITEM_TYPE_ROLE = Qt.ItemDataRole.UserRole          # "component" / "separator" / "placeholder"
COMPONENT_ID_ROLE = Qt.ItemDataRole.UserRole + 1   # e.g. "Date", "Number", "Meta_iso"


class InteractivePreviewWidget(QListWidget):
    """
    Interactive preview widget that allows drag & drop reordering of filename components.

    Each box carries its component id (Date, Prefix, Camera, Number,
    Meta_iso, ...), so reordering never depends on the displayed text - two
    components may well show the same text.
    """
    order_changed = pyqtSignal(list)  # new order of component ids
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.setMaximumHeight(80)
        self.setMinimumHeight(65)
        self.setFlow(QListWidget.Flow.LeftToRight)
        self.setWrapping(False)
        self.setSpacing(2)
        self.setAcceptDrops(True)
        
        # Custom item delegate for separator handling
        self.setItemDelegate(CustomItemDelegate(self))
        # Colours come from ThemeManager (applied at startup)

        self.separator = "-"
        self.components: list[tuple[str, str]] = []  # (component_id, text)
        
    def set_separator(self, separator):
        """Set the separator character"""
        self.separator = "" if separator == "None" else separator
        self.update_display()
    
    def set_components(self, components):
        """Set the filename components to display as (component_id, text) pairs."""
        self.components = list(components)
        self.update_display()
    
    def update_display(self):
        """Update the visual display of components"""
        self.clear()
        
        # If no components, show helpful placeholder
        if not self.components:
            placeholder_item = QListWidgetItem("Drop files or enter text above to see preview")
            placeholder_item.setFlags(Qt.ItemFlag.NoItemFlags)
            placeholder_item.setData(ITEM_TYPE_ROLE, "placeholder")
            placeholder_item.setForeground(Qt.GlobalColor.gray)
            placeholder_item.setFont(QFont("Arial", 10, QFont.Weight.Normal))
            placeholder_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.addItem(placeholder_item)
            return
        
        font = QFont("Arial", 8)
        font.setBold(True)
        metrics = QFontMetrics(font)

        for i, (component_id, text) in enumerate(self.components):
            item = QListWidgetItem(text)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsDragEnabled | Qt.ItemFlag.ItemIsDropEnabled)
            item.setData(ITEM_TYPE_ROLE, "component")
            item.setData(COMPONENT_ID_ROLE, component_id)
            
            if component_id == "Number":
                item.setBackground(Qt.GlobalColor.yellow)
                item.setForeground(Qt.GlobalColor.black)
                item.setToolTip("Sequential number (draggable)")
            else:
                item.setToolTip(f"{component_id.replace('Meta_', '')} - drag to swap position")
            
            # Size the box to fit its text
            item.setSizeHint(QSize(metrics.horizontalAdvance(text) + 17, metrics.height()))
            item.setFont(font)
            self.addItem(item)
            
            # Add separator after each component (except the last one)
            if self.separator and i < len(self.components) - 1:
                sep_item = QListWidgetItem(self.separator)
                sep_item.setFlags(Qt.ItemFlag.NoItemFlags)  # Not selectable or draggable
                sep_item.setData(ITEM_TYPE_ROLE, "separator")
                sep_item.setSizeHint(QSize(8, 20))
                self.addItem(sep_item)
    
    def get_component_order(self):
        """Current order of component ids (separators excluded)."""
        return [component_id for component_id, _text in self.components]
        
    def startDrag(self, supportedActions):
        """Only components can be dragged"""
        item = self.currentItem()
        if item and item.data(ITEM_TYPE_ROLE) == "component":
            super().startDrag(supportedActions)
        
    def mousePressEvent(self, event):
        """Handle mouse press events"""
        if event.button() == Qt.MouseButton.LeftButton:
            item = self.itemAt(event.position().toPoint())
            if item and item.data(ITEM_TYPE_ROLE) == "component":
                self.setCurrentItem(item)
        super().mousePressEvent(event)
    
    def move_component(self, dragged_id, drop_id=None):
        """Swap *dragged_id* with *drop_id*, or move it to the end if None."""
        ids = self.get_component_order()
        if dragged_id not in ids:
            return
        if drop_id is None:
            index = ids.index(dragged_id)
            self.components.append(self.components.pop(index))
        elif drop_id in ids and drop_id != dragged_id:
            a, b = ids.index(dragged_id), ids.index(drop_id)
            self.components[a], self.components[b] = self.components[b], self.components[a]
        else:
            return
        self.update_display()
        self.order_changed.emit(self.get_component_order())

    def dropEvent(self, event):
        """Handle drop events to swap positions of components"""
        if event.source() != self:
            event.ignore()
            return
            
        dragged_items = self.selectedItems()
        if not dragged_items or dragged_items[0].data(ITEM_TYPE_ROLE) != "component":
            event.ignore()
            return
        dragged_id = dragged_items[0].data(COMPONENT_ID_ROLE)

        drop_item = self.itemAt(event.position().toPoint())
        if drop_item is not None and drop_item.data(ITEM_TYPE_ROLE) == "component":
            self.move_component(dragged_id, drop_item.data(COMPONENT_ID_ROLE))
        else:
            # Dropped on a separator or empty space: move to the end
            self.move_component(dragged_id, None)
        event.accept()


class CollapsibleSection(QWidget):
    """A collapsible section with a toggle-button header.

    Used to move less-frequently-used options (EXIF date sync, metadata
    and sidecar toggles) out of the always-visible
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
