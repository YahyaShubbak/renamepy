#!/usr/bin/env python3
"""
Info dialog functions for the file renamer application.

Provides help dialogs explaining various filename components and features.
Extracted from main_application.py to reduce the God Object size.
"""

from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QWidget


def show_camera_prefix_info(parent: QWidget) -> None:
    """Show camera prefix help dialog.

    Args:
        parent: Parent widget for the dialog.
    """
    dialog = QDialog(parent)
    dialog.setWindowTitle("Camera Prefix Help")
    dialog.setModal(True)
    dialog.resize(400, 300)
    layout = QVBoxLayout(dialog)

    info_text = QLabel("""
Camera Prefix allows you to add a custom identifier for your camera:

Examples:
• A7R3 (for Sony A7R III)
• D850 (for Nikon D850)
• R5 (for Canon EOS R5)

This appears in your filename like:
2025-04-20-A7R3-vacation-001.jpg
    """)
    info_text.setWordWrap(True)
    layout.addWidget(info_text)

    close_btn = QPushButton("Close")
    close_btn.clicked.connect(dialog.accept)
    layout.addWidget(close_btn)
    dialog.exec()


def show_additional_info(parent: QWidget) -> None:
    """Show additional field help dialog.

    Args:
        parent: Parent widget for the dialog.
    """
    dialog = QDialog(parent)
    dialog.setWindowTitle("Additional Field Help")
    dialog.setModal(True)
    dialog.resize(400, 300)
    layout = QVBoxLayout(dialog)

    info_text = QLabel("""
Additional field for custom text in your filename:

Examples:
• vacation
• wedding
• portrait
• landscape

This appears in your filename like:
2025-04-20-A7R3-vacation-001.jpg
    """)
    info_text.setWordWrap(True)
    layout.addWidget(info_text)

    close_btn = QPushButton("Close")
    close_btn.clicked.connect(dialog.accept)
    layout.addWidget(close_btn)
    dialog.exec()


def show_separator_info(parent: QWidget) -> None:
    """Show separator help dialog.

    Args:
        parent: Parent widget for the dialog.
    """
    dialog = QDialog(parent)
    dialog.setWindowTitle("Separator Help")
    dialog.setModal(True)
    dialog.resize(400, 300)
    layout = QVBoxLayout(dialog)

    info_text = QLabel("""
Choose how to separate filename components:

Options:
• - (dash): 2025-04-20-A7R3-vacation-001.jpg
• _ (underscore): 2025_04_20_A7R3_vacation_001.jpg
• (none): 20250420A7R3vacation001.jpg
    """)
    info_text.setWordWrap(True)
    layout.addWidget(info_text)

    close_btn = QPushButton("Close")
    close_btn.clicked.connect(dialog.accept)
    layout.addWidget(close_btn)
    dialog.exec()


def show_exif_sync_info(parent: QWidget) -> None:
    """Show EXIF date synchronization help dialog.

    Args:
        parent: Parent widget for the dialog.
    """
    dialog = QDialog(parent)
    dialog.setWindowTitle("⚠️ EXIF Date Synchronization")
    dialog.setModal(True)
    dialog.resize(500, 400)
    layout = QVBoxLayout(dialog)

    # Warning header
    warning_label = QLabel("⚠️ WARNING: This feature modifies file metadata!")
    warning_label.setStyleSheet("color: #ff6b35; font-weight: bold; font-size: 14px;")
    layout.addWidget(warning_label)

    info_text = QLabel("""
<b>What this feature does:</b>
• Extracts DateTimeOriginal from EXIF metadata
• Sets it as the file's creation and modification date
• Helps cloud services show correct photo dates

<b>Why you might need this:</b>
Many cloud storage services (Google Photos, iCloud, OneDrive) use the file's \
creation date instead of the EXIF DateTimeOriginal for photo organization and \
timeline display.

<b>Requirements:</b>
• ExifTool must be installed and detected
• Files must contain valid EXIF DateTimeOriginal data

<b>Safety features:</b>
• Original file timestamps are backed up
• Can be reversed using the "Restore Original Names" function
• Only processes files with valid EXIF dates
• Skips files that already have matching dates

<b>Supported formats:</b>
JPG, TIFF, RAW files (CR2, NEF, ARW, etc.)
    """)
    info_text.setWordWrap(True)
    layout.addWidget(info_text)

    close_btn = QPushButton("I Understand")
    close_btn.clicked.connect(dialog.accept)
    layout.addWidget(close_btn)
    dialog.exec()
