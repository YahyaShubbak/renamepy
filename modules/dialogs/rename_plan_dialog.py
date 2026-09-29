"""
Rename Plan Dialog - shows every planned rename (old name -> new name)
before anything is changed on disk.
"""
from __future__ import annotations

import os

from PyQt6.QtCore import Qt, QAbstractTableModel, QModelIndex, QSortFilterProxyModel
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableView,
    QHeaderView, QPlainTextEdit, QCheckBox, QAbstractItemView,
)


class RenamePlanModel(QAbstractTableModel):
    """Table model over a list of rename_engine.PlanEntry objects."""

    HEADERS = ("Current name", "New name", "Folder", "Note")

    def __init__(self, entries, parent=None):
        super().__init__(parent)
        self.entries = list(entries)
        sources = [os.path.dirname(e.source) for e in self.entries]
        try:
            self._base = os.path.commonpath(sources) if sources else ""
        except ValueError:  # e.g. different drives on Windows
            self._base = ""

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.entries)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.HEADERS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return self.HEADERS[section]
        return None

    def _folder(self, entry):
        folder = os.path.dirname(entry.source)
        if self._base:
            rel = os.path.relpath(folder, self._base)
            return "" if rel == "." else rel
        return folder

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        entry = self.entries[index.row()]
        column = index.column()
        if role == Qt.ItemDataRole.DisplayRole:
            if column == 0:
                return os.path.basename(entry.source)
            if column == 1:
                return os.path.basename(entry.target) if entry.changed else "(unchanged)"
            if column == 2:
                return self._folder(entry)
            return entry.note
        if role == Qt.ItemDataRole.ToolTipRole:
            return f"{entry.source}\n→ {entry.target}"
        if role == Qt.ItemDataRole.ForegroundRole:
            if not entry.changed:
                return QColor("gray")
            if entry.note and not entry.sidecar and column in (1, 3):
                return QColor("#d9822b")  # name conflict: a number was added
        if role == Qt.ItemDataRole.FontRole and entry.sidecar:
            font = QFont()
            font.setItalic(True)
            return font
        return None


class _ChangedFilter(QSortFilterProxyModel):
    """Optionally hide files whose name stays the same."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.show_unchanged = True

    def filterAcceptsRow(self, source_row, source_parent):
        if self.show_unchanged:
            return True
        return self.sourceModel().entries[source_row].changed


class RenamePlanDialog(QDialog):
    """Confirm a rename plan.

    Args:
        entries: list of rename_engine.PlanEntry
        errors: list of (path, message) problems found while planning
    """

    def __init__(self, entries, errors, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Review Rename")
        self.resize(900, 560)

        changed = [e for e in entries if e.changed]
        self.photo_count = sum(1 for e in changed if not e.sidecar)
        self.sidecar_count = sum(1 for e in changed if e.sidecar)
        unchanged = len(entries) - len(changed)
        conflicts = sum(1 for e in changed if e.note and not e.sidecar)

        layout = QVBoxLayout(self)

        summary = f"<b>{self.photo_count} files will be renamed</b>"
        if self.sidecar_count:
            summary += f" (plus {self.sidecar_count} sidecar files)"
        details = []
        if unchanged:
            details.append(f"{unchanged} already have the right name")
        if conflicts:
            details.append(f"{conflicts} get a number suffix because the name is taken (orange)")
        if errors:
            details.append(f"{len(errors)} problems (see below)")
        if details:
            summary += "<br>" + "; ".join(details)
        summary_label = QLabel(summary)
        summary_label.setWordWrap(True)
        layout.addWidget(summary_label)

        self.model = RenamePlanModel(entries, self)
        self.proxy = _ChangedFilter(self)
        self.proxy.setSourceModel(self.model)
        self.table = QTableView()
        self.table.setModel(self.proxy)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        header.setStretchLastSection(True)
        self.table.setColumnWidth(0, 260)
        self.table.setColumnWidth(1, 320)
        self.table.setColumnWidth(2, 140)
        # All files in one folder: the folder column would stay empty
        if all(not self.model._folder(e) for e in self.model.entries):
            self.table.setColumnHidden(2, True)
        layout.addWidget(self.table, 1)

        self.show_unchanged = QCheckBox("Show files that keep their name")
        self.show_unchanged.setChecked(True)
        self.show_unchanged.toggled.connect(self._toggle_unchanged)
        layout.addWidget(self.show_unchanged)

        if errors:
            problems_label = QLabel(f"⚠ Problems ({len(errors)}) - these files will be skipped:")
            layout.addWidget(problems_label)
            problems = QPlainTextEdit()
            problems.setReadOnly(True)
            problems.setMaximumHeight(110)
            problems.setPlainText("\n".join(
                f"{os.path.basename(path)}: {message}" if path else str(message)
                for path, message in errors
            ))
            layout.addWidget(problems)

        buttons = QHBoxLayout()
        buttons.addStretch()
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        buttons.addWidget(self.cancel_button)
        if self.photo_count or self.sidecar_count:
            self.rename_button = QPushButton(f"Rename {self.photo_count} files")
        else:
            self.rename_button = QPushButton("Nothing to rename")
            self.rename_button.setEnabled(False)
        self.rename_button.setDefault(True)
        self.rename_button.clicked.connect(self.accept)
        buttons.addWidget(self.rename_button)
        layout.addLayout(buttons)

    def _toggle_unchanged(self, checked):
        self.proxy.show_unchanged = checked
        self.proxy.invalidateFilter()
