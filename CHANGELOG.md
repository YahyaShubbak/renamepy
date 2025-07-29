# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2025-07-29

### Added
- Initial release of RenameFiles application
- PyQt6-based GUI with drag & drop functionality
- EXIF data extraction using ExifTool and Pillow
- Interactive preview with drag & drop component reordering
- Support for multiple date formats
- Custom camera prefix and additional information fields
- Automatic camera and lens model detection
- Sequential file numbering with collision detection
- Subdirectory scanning support
- Dark and Light theme support
- Undo functionality to restore original filenames
- Comprehensive error handling and user feedback
- Support for RAW files (CR2, NEF, ARW, DNG, etc.)
- File access validation and safety checks
- Batch processing with background threading
- Detailed tooltips and help system

### Features
- **File Formats**: Support for JPEG, RAW, TIFF, PNG, BMP
- **EXIF Methods**: ExifTool (recommended) and Pillow (fallback)
- **Naming Options**: Date, camera prefix, additional info, camera model, lens model
- **Date Formats**: YYYY-MM-DD, YYYYMMDD, DD-MM-YYYY, MM_DD_YYYY, etc.
- **Separators**: Dash, underscore, or none
- **UI Themes**: Dark and Light mode
- **Safety**: Undo functionality, file validation, error reporting

### Technical
- Built with PyQt6 for cross-platform compatibility
- Threaded file processing to prevent UI freezing
- EXIF caching for improved performance
- Recursive directory scanning
- Path length validation for Windows compatibility

## [Unreleased]

### Planned Features
- Standalone executable builds
- Custom naming templates
- Batch configuration presets
- Image thumbnail preview
- Metadata editing capabilities
- Plugin system for extensions
