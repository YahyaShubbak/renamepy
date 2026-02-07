#!/usr/bin/env python3
"""
ExifTool Warning Dialog — shown when ExifTool is not installed or not found.

Provides platform-aware installation instructions and a direct download
link.  The user can suppress this dialog for future sessions.
"""
from __future__ import annotations

import os
import sys
import webbrowser
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QCheckBox, QStyle,
)
from PyQt6.QtCore import Qt


class ExifToolWarningDialog(QDialog):
    """Warning dialog shown when ExifTool is not available."""

    DOWNLOAD_URL = "https://exiftool.org/install.html"

    def __init__(self, parent: "QWidget | None" = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("ExifTool Not Found — Installation Recommended")
        self.setModal(True)
        self.resize(620, 480)

        layout = QVBoxLayout(self)

        # --- Header with warning icon ---
        header_layout = QHBoxLayout()
        warning_icon = QLabel()
        warning_icon.setPixmap(
            self.style()
            .standardIcon(QStyle.StandardPixmap.SP_MessageBoxWarning)
            .pixmap(48, 48)
        )
        header_text = QLabel("ExifTool Not Found")
        header_text.setStyleSheet(
            "font-size: 18px; font-weight: bold; color: #d83b01;"
        )
        header_layout.addWidget(warning_icon)
        header_layout.addWidget(header_text)
        header_layout.addStretch()
        layout.addLayout(header_layout)

        # --- Status ---
        status_label = QLabel(
            "<b>Current status:</b> No EXIF support available. "
            "File renaming will use file timestamps only."
        )
        status_label.setWordWrap(True)
        status_label.setStyleSheet("font-size: 11px; margin-top: 6px;")
        layout.addWidget(status_label)

        # --- Explanation ---
        info_text = QLabel(
            "<b>What is ExifTool?</b><br>"
            "ExifTool is a powerful library for reading and writing metadata "
            "in image and video files.<br><br>"
            "<b>Why ExifTool is recommended:</b><br>"
            "• <b>Complete RAW support:</b> Works with all camera RAW formats<br>"
            "• <b>Video metadata:</b> Extracts date, camera, and technical data from videos<br>"
            "• <b>More metadata:</b> Extracts camera, lens, and date information more reliably<br>"
        )
        info_text.setWordWrap(True)
        info_text.setStyleSheet("font-size: 11px; line-height: 1.4;")
        layout.addWidget(info_text)

        # --- Platform-specific install instructions ---
        install_html = self._build_install_instructions()
        install_label = QLabel(install_html)
        install_label.setWordWrap(True)
        install_label.setOpenExternalLinks(True)
        install_label.setStyleSheet("font-size: 11px; line-height: 1.4;")
        layout.addWidget(install_label)

        layout.addStretch()

        # --- Buttons ---
        button_layout = QHBoxLayout()

        self._dont_show_again = QCheckBox("Don't show this warning again")
        button_layout.addWidget(self._dont_show_again)
        button_layout.addStretch()

        download_button = QPushButton("Open Download Page")
        download_button.clicked.connect(self._open_download_page)

        continue_button = QPushButton("Continue without EXIF")
        continue_button.setDefault(True)
        continue_button.clicked.connect(self.accept)

        button_layout.addWidget(download_button)
        button_layout.addWidget(continue_button)
        layout.addLayout(button_layout)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def should_show_again(self) -> bool:
        """Return True if the user wants to see this dialog next time."""
        return not self._dont_show_again.isChecked()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_install_instructions() -> str:
        """Return platform-aware HTML installation instructions."""
        lines: list[str] = ["<b>How to install ExifTool:</b><br>"]

        if sys.platform == "win32":
            lines.append(
                "<b>Option A — Automatic setup:</b> "
                "Run <code>setup_exiftool.bat</code> from the project folder.<br><br>"
            )
            lines.append(
                "<b>Option B — Manual install:</b><br>"
                "1. Download from "
                '<a href="https://exiftool.org/install.html">exiftool.org</a><br>'
                "2. Extract the ZIP into the project folder "
                "(e.g. <code>exiftool-13.xx_64/</code>)<br>"
                "3. Restart this application<br><br>"
            )
            lines.append(
                "<b>Option C — Package manager:</b><br>"
                "<code>winget install OliverBetz.ExifTool</code> or "
                "<code>choco install exiftool</code><br>"
            )
        elif sys.platform == "darwin":
            lines.append(
                "<code>brew install exiftool</code><br>"
                "Then restart this application.<br>"
            )
        else:  # Linux
            lines.append(
                "<code>sudo apt install libimage-exiftool-perl</code> "
                "(Debian/Ubuntu) or<br>"
                "<code>sudo dnf install perl-Image-ExifTool</code> (Fedora)<br>"
                "Then restart this application.<br>"
            )

        return "".join(lines)

    def _open_download_page(self) -> None:
        """Open the ExifTool download page in the default browser."""
        webbrowser.open(self.DOWNLOAD_URL)
        self.accept()
