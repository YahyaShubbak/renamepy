# GitHub Copilot Persona - renamepy Project

## 🎯 Project Overview

**renamepy** is an advanced batch file renaming tool specifically designed for photographers who need to organize and rename their image files using EXIF metadata. The application provides a powerful PyQt6 GUI with interactive preview, drag-and-drop ordering, and comprehensive EXIF data integration.

### Project Characteristics
- **Target Audience**: Photographers and media professionals
- **Distribution Goal**: Broad audience release once stable and bug-free
- **Current Status**: Maintenance mode with active feature implementation when needed
- **Tech Stack**: Python 3.12+, PyQt6, ExifTool, cross-platform (Windows, Linux, macOS)

---

## 🛠️ Development Environment

### Virtual Environment
- **Environment Name**: `renamepy` (Conda) or `.venv` / `renamepy` (venv), created by `install.sh` / `install.ps1`
- **Action Required**: Always activate the environment when opening a terminal or running commands
- **Python Version**: 3.10 or newer is supported (CI tests 3.10–3.13); `RenameFiles.py` refuses older versions
- **Modern Features**: Python 3.10 features are fine; modules use `from __future__ import annotations` so `X | None` annotations never break

### Initial Setup Check
When starting work:
1. Verify the environment is active
2. Confirm Python version is 3.10+
3. Install dependencies with `pip install -r requirements-dev.txt`

---

## 🏗️ Architecture Invariants

These protect users' files - keep them when changing code:

- **Plan, confirm, execute.** `rename_engine.RenamePlanner` computes every new name without touching files; the UI shows the plan (`dialogs/rename_plan_dialog.py`) and only then `RenameWorkerThread(mode="execute")` renames. The interactive preview calls `RenamePlanner.preview()`, i.e. the same code, so preview and result can't diverge.
- **Journal before destructive writes.** Renames, timestamp syncs and EXIF time shifts write their undo data to `backup_journal` *before* modifying files. Backups are keyed by the file's current path and follow renames (`rekey_journal`).
- **First backup wins.** Never overwrite an existing backup (`PersistedBackupDict.record_original(s)`) - it holds the original values. Undo removes only successfully restored entries.
- **Never overwrite files.** Use `file_utilities.safe_rename`, never `shutil.move`/`os.rename` on user files.
- **File metadata is untrusted.** Names read from metadata (`PreservedFileName`, legacy `UserComment`) must pass `is_safe_restore_name` before use.
- **ExifTool file names go through argument files** (`-@`, UTF-8, `-charset filename=utf8`) - Windows mangles non-ANSI command-line arguments. Per-file tag values need one `-execute` block per file.
- **Background threads** must not be destroyed while running (`closeEvent` refuses to close during a rename).
- **Only the main thread starts the shared ExifTool process** (`ExifService._ensure_exiftool_running`). On Linux PyExifTool uses `PR_SET_PDEATHSIG`: a process started by a worker thread dies with that thread and a read in progress hangs forever.
- **Real-image tests**: put camera files into `Tests/Testbilder` (git-ignored) or point `RENAMEPY_TEST_IMAGES` at a folder; tests only read them - anything that writes works on copies.

---

## 📝 Code Quality Standards

### Language & Naming
- **ALL code, comments, documentation, and variable names MUST be in English**
- **Never mix languages** - this is considered outdated practice
- Translate existing German documentation to English when encountered
- Variable/function names: Clear, descriptive, English-only

### Code Style
- **PEP 8 Compliant**: Follow Python style guide strictly
- **Type Hints**: Required for all functions, methods, and complex variables
- **Docstrings**: Use Google style format for all modules, classes, and functions
- **Comments**: Required for complex logic - explain the "why", not just the "what"
- **Architecture**: Avoid spaghetti code - maintain clean, modular structure

### Code Quality Principles
```python
# Example of expected code quality:
def process_exif_data(file_path: str, options: dict[str, Any]) -> ExifData | None:
    """
    Extract and process EXIF data from an image file.
    
    Args:
        file_path: Absolute path to the image file
        options: Configuration options for EXIF processing
        
    Returns:
        ExifData object if successful, None if file has no EXIF data
        
    Raises:
        FileNotFoundError: If the specified file doesn't exist
        ExifProcessingError: If EXIF data is corrupted
    """
    # Implementation with clear logic and error handling
```

---

## 🔄 Development Workflow

### Analysis-First Approach
When receiving a task (bug fix, feature request, refactoring):

1. **Deep Analysis Phase**
   - Understand the entire codebase context
   - Identify all dependencies and affected modules
   - Analyze performance implications
   - Check for potential side effects
   - Review existing tests

2. **Iterative Review**
   - Make multiple passes through the code
   - Look for improvement opportunities in each pass
   - Consider edge cases and error scenarios
   - Evaluate alternative approaches

3. **Proposal Before Implementation**
   - Present concept/pseudocode first
   - Show multiple alternatives with pros/cons
   - Discuss performance implications
   - Wait for approval before implementing

4. **Implementation Phase**
   - Write clean, well-documented code
   - Follow established patterns in the codebase
   - Update or create tests
   - Update relevant documentation

### Git Workflow
- **Request commit before major changes**: Ask user to commit current state before implementing significant modifications
- This allows easy rollback if needed and keeps history clean

---

## 🧪 Testing Requirements

### Testing Philosophy
Testing is a critical part of development - always prioritize test quality.

### When to Test
- ✅ Before implementing new features
- ✅ After bug fixes
- ✅ During refactoring
- ✅ When modifying core functionality
- ✅ After dependency updates

### Testing Actions
1. **Run existing tests first** to establish baseline
2. **Write new tests** for new features or bug fixes
3. **Update existing tests** when behavior changes
4. **Remove obsolete tests** when functionality is removed
5. **Review test coverage** - aim for comprehensive coverage of critical paths

### Test Framework
- **Primary**: pytest
- **Location**: Tests/ directory
- **Naming**: `test_*.py` pattern

---

## 🚨 Error Handling Strategy

### Error Philosophy
Errors should never be silently ignored - address them directly and appropriately.

### Error Handling Approach

#### 1. Fail Fast (Developer Errors)
```python
# Use for programming errors that should never happen
if not isinstance(file_path, str):
    raise TypeError(f"file_path must be str, got {type(file_path)}")
```

#### 2. Graceful Degradation (User Errors)
```python
# Use for user-facing errors with helpful messages
try:
    exif_data = extract_exif(file_path)
except FileNotFoundError:
    show_user_message("The selected file could not be found. Please try again.")
    return None
```

#### 3. Logging Levels
- **DEBUG**: Detailed diagnostic information for developers
- **INFO**: General informational messages for normal operation
- **WARNING**: Warning messages for recoverable issues
- **ERROR**: Error messages for serious problems
- **CRITICAL**: Critical issues that prevent operation

---

## ⚡ Performance & Optimization

### Performance Mindset
- **Proactively suggest optimizations** when you identify opportunities
- **Always mention performance implications** of proposed changes
- **No specific performance targets**, but efficiency matters for user experience
- **Consider batch operations** for file processing
- **Profile before optimizing** - don't guess at bottlenecks

### Performance Considerations
- EXIF processing can be expensive - consider caching
- File I/O should be minimized
- GUI operations should be non-blocking (use QThread)
- Large file lists need efficient data structures

---

## 📚 Documentation Requirements

### Documentation Cleanup
The project has accumulated many markdown files that need consolidation:
- **Consolidate multiple MD files** into single, cohesive documents
- **Delete obsolete documentation** when content is outdated
- **Organize documentation** logically (user docs, dev docs, changelogs)

### Documentation Standards
1. **README Updates**: Update for all new user-facing features
2. **Inline Comments**: Required for complex algorithms or business logic
3. **API Documentation**: Google-style docstrings for all public APIs
4. **Change Documentation**: Maintain changelog for significant changes
5. **English Only**: Translate all German documentation to English

---

## 🔗 Critical Dependencies

### Core Dependencies
1. **PyQt6** (>= 6.5, < 7)
   - GUI framework
   - Used throughout the application
   - Cross-platform compatibility required

2. **PyExifTool** (>= 0.5.5, < 0.6)
   - Python wrapper for ExifTool
   - Primary EXIF data extraction
   - Must handle ExifTool binary path correctly

3. **ExifTool Binary**
   - External command-line tool
   - Platform-specific installation
   - Check availability and version

### Dependency Management
- **Support the ranges in `requirements.txt`** - CI tests both the lower bounds and the newest releases
- **Cross-platform support mandatory** - test on Windows, Linux, macOS
- **Handle missing dependencies gracefully** with user-friendly error messages

---

## 🌍 Cross-Platform Support

### Platform Requirements
- **Windows**: Primary development platform
- **Linux**: Full support required
- **macOS**: Full support required

### Platform-Specific Considerations
- **File Paths**: Use `pathlib.Path` for cross-platform compatibility
- **Line Endings**: Respect platform conventions
- **External Tools**: Handle platform-specific ExifTool locations
- **GUI**: Ensure PyQt6 renders correctly on all platforms
- **Commands**: Test terminal commands work on all target platforms

---

## 🎨 GUI Development

### Framework
- **PyQt6**: Primary GUI framework (verified in use)
- **Modernization**: GUI improvements are welcome
- **Focus**: Primary focus on backend, but GUI quality matters

### GUI Best Practices
- **Non-blocking operations**: Use QThread for long-running tasks
- **User feedback**: Provide progress indicators and status messages
- **Responsive design**: Application should remain responsive during operations
- **Error messages**: Clear, actionable user-facing error messages

---

## 💡 Communication & Collaboration

### Response Style
When working with the user:
1. **Analysis First**: Present thorough analysis before proposing solutions
2. **Clear Communication**: Explain what you're doing and why
3. **Options**: Present alternatives with trade-offs
4. **Questions**: Ask clarifying questions when requirements are unclear
5. **Transparency**: Be honest about limitations or uncertainties

### Code Review Mindset
- Look at code with fresh eyes each time
- Question existing patterns if they seem suboptimal
- Suggest improvements even in working code
- Consider maintainability and readability

---

## 🚀 Quick Reference Commands

### Environment Activation
```bash
# Conda
conda activate renamepy
# or venv
source .venv/bin/activate
```

### Testing
```bash
# Run all tests (headless; tests against a real ExifTool run if one is installed)
QT_QPA_PLATFORM=offscreen python -m pytest Tests

# Run specific test file
QT_QPA_PLATFORM=offscreen python -m pytest Tests/test_rename_plan.py
```
Tests never touch the user's real undo journal (`Tests/conftest.py` redirects it to a temp dir).

### Code Quality
```bash
# Format code (if black is installed)
black .

# Lint code (if flake8 is installed)
flake8 modules/
```

---

## 🎯 Success Criteria

You are performing well when:
- ✅ Code is clean, maintainable, and well-documented
- ✅ All code and comments are in English
- ✅ Tests are written and passing
- ✅ Performance implications are considered and communicated
- ✅ Cross-platform compatibility is maintained
- ✅ User experience is prioritized
- ✅ Errors are handled appropriately
- ✅ Documentation is up-to-date
- ✅ The `renamepy` environment is properly activated
- ✅ Proposals are presented before implementation

---

**Remember**: Quality over speed. Take time to understand the full context, propose thoughtful solutions, and implement with care. This project aims for broad distribution - every detail matters.
