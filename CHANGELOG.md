# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Changed
- Improved code documentation with English-only comments
- Consolidated development documentation
- Enhanced inline code clarity

---

## [1.1.0] - 2026-01-04

### Fixed
- **Interactive Preview Order Bug**: Fixed critical bug where preview showed different component order than actual renamed files. Preview now matches final filename exactly (WYSIWYG principle).
- **Component Ordering**: Removed automatic component insertion that broke user's drag & drop order
- Component activation/deactivation now maintains proper order in preview

### Changed
- Simplified preview generation logic for better maintainability
- Component management now handled before rendering for cleaner code flow
- Improved "What You See Is What You Get" experience in interactive preview

### Technical
- Refactored `on_preview_order_changed()` to respect exact preview order without manipulation
- Simplified `_build_display_components()` to follow custom_order without modifications
- Enhanced `update_preview()` with intelligent component management for activation/deactivation

---

## [1.0.1] - 2025-10-11

### Performance
- **EXIF Processing**: Achieved 13.1x performance improvement using persistent ExifTool instance
  - Before: 153.11s for 596 files (3.9 files/sec)
  - After: 11.67s for 596 files (51.1 files/sec)
  - Per-file average: 250ms → 19.5ms (12.8x faster)
- **Directory Scanning**: 17.7% throughput improvement
  - Before: 78,003 files/sec
  - After: 91,801 files/sec
  - Duration: 132ms → 112ms (15% faster)

### Fixed
- **Dark Theme**: Complete dark theme coverage for all UI elements including scrollbars, combo boxes, and checkboxes
- **System Theme**: Fixed interactive preview maintaining yellow highlight when switching to system theme
- **Click Handlers**: Fixed single/double click functionality after rename by properly setting UserRole data on list items
- **Undo Functionality**: Completely reworked original filename tracking
  - Original filenames now preserved correctly across multiple renames
  - Undo operation properly restores initial filenames instead of previous rename state
- **Camera/Lens Display**: Fixed inconsistency between preview fallback values and actual rename operation
  - Added fallback logic to rename engine matching preview behavior
  - Ensured consistency between preview and actual filenames
- **ExifTool Warning**: Improved ExifTool availability warning implementation

### Technical
- Implemented shared ExifTool process for metadata extraction
- Enhanced theme manager with extended dark theme styles
- Improved file list item creation with proper metadata attachment
- Selective optimization approach focusing on critical bottlenecks

---

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
- **Custom Filename Ordering**: Drag and drop components to create custom filename patterns
  - Date → Camera Prefix → Additional → Camera Model → Lens → Sequential Number (default)
  - Full flexibility with visual preview
  - Sequential number always maintained at end for proper sorting
- **Chronological Sorting**: Files automatically sorted by EXIF capture time
  - Ensures correct chronological order even with mixed equipment
  - Continuous or date-based counter modes
  - Supports multi-day shoots and vacation mode
- **Video Support**: Full support for video file formats
  - MP4, MOV, AVI, MKV, and more
  - EXIF extraction from video files
  - Consistent naming across photo and video files
- **EXIF Time Shifting**: Adjust EXIF timestamps for timezone corrections
  - Forward and backward time shifts
  - Undo capability for time shift operations
  - Preserves original EXIF data integrity
- **Advanced Metadata Selection**: Include additional EXIF data in filenames
  - ISO, aperture, shutter speed, focal length
  - Resolution and exposure compensation
  - Flexible positioning within filename
- **File Formats**: Support for JPEG, RAW (CR2, NEF, ARW, DNG, RAF, etc.), TIFF, PNG, BMP
- **EXIF Methods**: ExifTool (recommended) and Pillow (fallback)
- **Naming Options**: Date, camera prefix, additional info, camera model, lens model, metadata
- **Date Formats**: YYYY-MM-DD, YYYYMMDD, DD-MM-YYYY, DD_MM_YYYY, MM-DD-YYYY, MM_DD_YYYY
- **Separators**: Dash (-), underscore (_), or none
- **UI Themes**: Dark, Light, and System theme modes
- **Safety**: Undo functionality, file validation, error reporting

### Technical
- Built with PyQt6 for cross-platform compatibility (Windows, macOS, Linux)
- Threaded file processing to prevent UI freezing
- EXIF caching for improved performance
- Recursive directory scanning with followlinks control
- Path length validation for Windows compatibility
- Modular architecture with separated concerns:
  - UI components in dedicated modules
  - Separated file processing logic
  - Centralized state management
  - Theme management system
- Unified filename component builder for consistency
- Comprehensive logging system for debugging

---

## [Unreleased] - Future Plans

### Planned Features
- Standalone executable builds (.exe for Windows, .app for macOS)
- Custom naming templates with saved presets
- Batch configuration profiles
- Image thumbnail preview in file list
- Extended metadata editing capabilities
- Plugin system for custom extensions
- Multi-language support
- Cloud storage integration
- Automated backup before rename operations
