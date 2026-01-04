from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox, QPushButton, QDateTimeEdit, QGroupBox
)
from PyQt6.QtCore import Qt, QDateTime


class TimestampSyncOptionsDialog(QDialog):
    """Dialog to choose which filesystem timestamps to modify and optional custom datetime."""

    def __init__(self, parent=None, default_dt=None):
        super().__init__(parent)
        self.setWindowTitle("Timestamp Synchronization Options")
        self.setModal(True)
        self.resize(420, 260)

        layout = QVBoxLayout(self)

        info = QLabel(
            "Select which filesystem timestamps should be set to the capture date.\n"
            "Optionally specify a custom date/time (overrides EXIF)."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        # Checkboxes for which timestamps
        box = QGroupBox("Fields to Modify")
        box_layout = QVBoxLayout()
        self.cb_creation = QCheckBox("Created (Creation Time)")
        self.cb_modification = QCheckBox("Modified (Modification Time)")
        self.cb_access = QCheckBox("Last Access (Access Time)")
        for cb in (self.cb_creation, self.cb_modification, self.cb_access):
            cb.setChecked(True)
            box_layout.addWidget(cb)
        box.setLayout(box_layout)
        layout.addWidget(box)

        # Custom datetime option
        self.cb_custom = QCheckBox("Use Custom Date/Time")
        layout.addWidget(self.cb_custom)

        dt_row = QHBoxLayout()
        self.dt_edit = QDateTimeEdit()
        self.dt_edit.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        self.dt_edit.setCalendarPopup(True)
        if default_dt is None:
            self.dt_edit.setDateTime(QDateTime.currentDateTime())
        else:
            self.dt_edit.setDateTime(default_dt)
        self.dt_edit.setEnabled(False)
        dt_row.addWidget(QLabel("Date/Time:"))
        dt_row.addWidget(self.dt_edit)
        layout.addLayout(dt_row)

        self.cb_custom.toggled.connect(self.dt_edit.setEnabled)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.btn_ok = QPushButton("OK")
        self.btn_cancel = QPushButton("Cancel")
        btn_row.addWidget(self.btn_cancel)
        btn_row.addWidget(self.btn_ok)
        layout.addLayout(btn_row)

        self.btn_cancel.clicked.connect(self.reject)
        self.btn_ok.clicked.connect(self._on_accept)

        self._result = None

    def _on_accept(self):
        if not (self.cb_creation.isChecked() or self.cb_modification.isChecked() or self.cb_access.isChecked()):
            # Require at least one selection
            return
        options = {
            'creation': self.cb_creation.isChecked(),
            'modification': self.cb_modification.isChecked(),
            'access': self.cb_access.isChecked(),
            'use_custom': self.cb_custom.isChecked(),
            'custom_dt': self.dt_edit.dateTime().toPyDateTime() if self.cb_custom.isChecked() else None,
        }
        self._result = options
        self.accept()

    def get_result(self):
        return self._result
