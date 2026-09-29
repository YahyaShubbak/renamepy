# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Security
- **Undo restore validates original names from file metadata**: a crafted `OriginalName`/`PreservedFileName` (e.g. `..\..\Startup\x.bat`) could move a file anywhere when clicking Restore. Only plain file names in the same folder with the same extension are accepted now; ambiguous claims (several files, one name) are skipped, and the full list is shown before restoring.
- Removed the unused PowerShell timestamp helper, whose file-name argument was injectable (`powershell -Command` appends arguments to the script text).
- EXIF restore only writes allow-listed date tags from the on-disk journal.

### Fixed
- **Crash on any rename error**: errors are `(path, message)` tuples; the result dialog called `str.startswith` on them, and PyQt6 aborted the app (losing the in-memory undo data). A global exception hook now reports unexpected errors instead of aborting.
- **"Save original filename to metadata" wrote the same name into every file of a batch**: ExifTool applies all tag assignments of one command to all its files. Each file now gets its own `-execute` block; the name is stored in `XMP-xmpMM:PreservedFileName` (created only if absent, user comments are no longer overwritten; the old `EXIF:UserComment` format is still read).
- **Camera/lens of the first file were used for every file** once the checkbox was ticked; they are now read per file. Metadata-dialog checkboxes only offer fields that are resolved per file.
- **Undo data loss**: a second timestamp sync or EXIF time shift replaced the backup of the original values; undo discarded backups even when restoring failed; the EXIF time shift modified files it could not back up.
- **Renames are journaled before files are moved** and recovered on the next start, so a crash or kill mid-rename can be undone. Timestamp/EXIF backups follow renamed files.
- Renames never overwrite a file that appeared after planning; case-only renames work on macOS.
- Loading the same folder twice no longer duplicates files (which made the rename fail); drag & drop appends like the buttons; the list placeholder no longer stays after a drop; the preview refreshes after loading.
- Closing the window during a rename, time shift or benchmark no longer aborts the process mid-operation; the time shift can be cancelled.
- Exposure time rounding (1/60 s was shown and named as `1/59`), video capture dates (QuickTime tags were never read), sub-second/time-zone EXIF dates, sort keys that could raise `TypeError`, continuous counter ordered by capture time instead of mtime, timestamp-sync errors being dropped, Windows creation-time API errors going undetected.
- Non-ASCII file names on Windows (UTF-8 for ExifTool file names and the PyExifTool pipe; single-file commands pass names via argument files).
- Python 3.9 crashed on import (`str | None` annotation); a clear message is shown for Python < 3.10.

### Installation
- **Windows**: `install.ps1` installed the packages into the system Python instead of the venv (the app then failed to start); validation now imports the packages; "recreate" deletes the Conda env; the ExifTool download URL (exiftool.org now links to SourceForge, the old URL returns 404) is fixed; `start.bat` handles user names with spaces, calls `conda activate` correctly and starts the app without a console window; batch files are CRLF-only via `.gitattributes`.
- **Linux/macOS**: pressing Enter at "Recreate? [y/N]" deleted the environment; `python3-venv` added for Debian/Ubuntu; Fedora (dnf) and openSUSE (zypper) supported; Python ≥ 3.10 is located automatically; ExifTool via Homebrew on macOS; menu entry in `~/.local/share/applications` with a PNG icon.
- **CI**: the workflow file was invalid YAML; it now runs the test suite on Linux (Python 3.10–3.13), Windows and macOS with a real ExifTool, plus ShellCheck and PowerShell parsing.

### Added
- **Tools → Forget Undo Data…** to discard pending undo information.
- CR3, HEIC/HEIF, AVIF and WebP support; folder scans skip hidden/NAS thumbnail folders and `._*` files.
- Regression tests (`Tests/test_data_integrity.py`) and tests against a real ExifTool (`Tests/test_exiftool_integration.py`); tests no longer touch the user's undo journal.
- **Type Hints**: Comprehensive type hints added to all core functions for better IDE support and code safety
- **Improved Docstrings**: Enhanced documentation with detailed parameter and return value descriptions

### Changed
- **Code Refactoring Phase 2**: Split large functions into focused helper functions for better maintainability
  - `on_rename_finished`: 198→40 lines (3 helpers)
  - `undo_rename_action`: 270→120 lines (4 helpers)
  - `optimized_rename_files`: 318→65 lines (5 helpers)
- **Code Quality**: Eliminated ~550 lines of complex nested code, replaced with clean, documented helpers
- **Documentation Cleanup**: Removed obsolete test outputs and debug scripts

### Fixed
- **Critical Bug**: Fixed `get_safe_target_path` parameter error that caused files to be renamed to wrong locations
  - Issue: Directory path passed instead of file path
  - Impact: Files moved to Desktop instead of original location
  - Fix: Corrected parameter in line 397 of rename_engine.py

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
- EXIF data extraction using ExifTool
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
- **EXIF Methods**: ExifTool (required)
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
