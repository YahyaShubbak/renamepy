"""
File List Manager - Handles file selection, drag & drop, and file list UI
Extracted from main_application.py to improve code organization
"""

import os
from PyQt6.QtWidgets import QFileDialog, QMessageBox, QListWidgetItem
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QDragEnterEvent, QDropEvent, QDragMoveEvent

from ..file_utilities import is_media_file, scan_directory_recursive
from ..logger_util import get_logger

log = get_logger()


class FileListManager:
    """
    Manages file list operations including:
    - File/folder selection
    - Drag & drop handling
    - File list UI updates
    - File statistics
    """
    
    def __init__(self, parent):
        """
        Initialize FileListManager
        
        Args:
            parent: The parent FileRenamerApp instance
        """
        self.parent = parent
    
    def select_files(self):
        """Select individual media files"""
        files, _ = QFileDialog.getOpenFileNames(
            self.parent, "Select Media Files", "", 
            "Media Files (*.jpg *.jpeg *.png *.cr2 *.nef *.arw *.mp4 *.mov);;All Files (*)"
        )
        if files:
            # Filter to only media files
            media_files = [f for f in files if is_media_file(f)]
            self.parent.files.extend(media_files)
            self.update_file_list()
            
            # Clear EXIF cache when loading new files
            from ..exif_processor import clear_global_exif_cache
            clear_global_exif_cache()
            
            # Reset EXIF undo check cache
            if hasattr(self.parent, '_exif_undo_checked'):
                del self.parent._exif_undo_checked
            
            self.parent.extract_camera_info()
            
            # Update buttons to check for EXIF undo data
            if hasattr(self.parent, '_update_buttons'):
                self.parent._update_buttons()
            
            # Start background benchmark with loaded files
            self._start_background_benchmark()
    
    def select_folder(self):
        """Select folder and scan for media files"""
        folder = QFileDialog.getExistingDirectory(self.parent, "Select Folder")
        if folder:
            media_files = scan_directory_recursive(folder)
            self.parent.files.extend(media_files)
            self.update_file_list()
            
            # Clear EXIF cache when loading new folder
            from ..exif_processor import clear_global_exif_cache
            clear_global_exif_cache()
            
            # Reset EXIF undo check cache
            if hasattr(self.parent, '_exif_undo_checked'):
                del self.parent._exif_undo_checked
            
            self.parent.extract_camera_info()
            
            # Update buttons to check for EXIF undo data
            if hasattr(self.parent, '_update_buttons'):
                self.parent._update_buttons()
            
            # Start background benchmark with loaded files
            self._start_background_benchmark()
    
    def clear_file_list(self):
        """Clear the file list"""
        # Use state model to clear data
        self.parent.state.clear_files()
        
        self.parent.file_list.clear()
        self.parent.status.showMessage("Ready")
        self.parent.rename_button.setEnabled(False)
        
        self.parent.camera_model_label.setText("(no files selected)")
        self.parent.lens_model_label.setText("(no files selected)")
        
        # Clear EXIF cache when clearing files
        from ..exif_processor import clear_global_exif_cache
        clear_global_exif_cache()
        
        self.update_file_list_placeholder()
        self.update_file_statistics()
    
    def update_file_list(self):
        """Update the file list display"""
        self.parent.file_list.clear()
        for file_path in self.parent.files:
            item = QListWidgetItem(os.path.basename(file_path))
            item.setData(Qt.ItemDataRole.UserRole, file_path)
            self.parent.file_list.addItem(item)
        
        self.parent.rename_button.setEnabled(len(self.parent.files) > 0)
        self.update_file_statistics()
        self.update_file_list_placeholder()
    
    def update_file_list_placeholder(self):
        """Add placeholder text when file list is empty"""
        if self.parent.file_list.count() == 0:
            placeholder_item = QListWidgetItem(
                "📁 Drag and drop folders/files here or use buttons below\n"
                "📄 Supports images (JPG, RAW) and videos (MP4, MOV, etc.)"
            )
            placeholder_item.setFlags(Qt.ItemFlag.NoItemFlags)  # Make it non-selectable
            placeholder_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.parent.file_list.addItem(placeholder_item)
    
    def update_file_statistics(self):
        """Update file statistics display"""
        from ..utils.ui_helpers import calculate_stats
        
        if not self.parent.files:
            self.parent.file_stats_label.setText("")
            self.parent.file_stats_label.hide()
            return
        
        stats = calculate_stats(self.parent.files)
        
        self.parent.file_stats_label.setText(
            f"📊 Total: {stats['total_files']} files ({stats['total_images']} images)\n"
            f"📷 JPEG: {stats['jpeg_count']} | 📸 RAW: {stats['raw_count']}"
        )
        self.parent.file_stats_label.show()
    
    def add_files_to_list(self, files):
        """Add files to the file list"""
        # Clear existing files when adding new ones
        if files and self.parent.files:
            self.clear_file_list()
        
        # Remove placeholder if present
        if self.parent.file_list.count() == 1:
            item = self.parent.file_list.item(0)
            if item and item.text() == "Drop files here or click 'Select Files' to begin":
                self.parent.file_list.clear()
        
        # Clear EXIF cache when adding new files
        from ..exif_processor import clear_global_exif_cache
        clear_global_exif_cache()
        
        # Validate and add files
        added_count = 0
        inaccessible_files = []
        
        for file in files:
            if is_media_file(file) and os.path.exists(file):
                if file not in self.parent.files:
                    self.parent.files.append(file)
                    item = QListWidgetItem(os.path.basename(file))
                    item.setData(Qt.ItemDataRole.UserRole, file)
                    self.parent.file_list.addItem(item)
                    added_count += 1
            else:
                inaccessible_files.append(file)
        
        # Show warning for inaccessible files
        if inaccessible_files:
            QMessageBox.warning(
                self.parent, 
                "Inaccessible Files", 
                f"Some files could not be accessed:\n" + "\n".join(inaccessible_files[:5])
            )
        
        # Update status
        if added_count > 0:
            self.parent.status.showMessage(f"Added {added_count} files", 3000)
        
        # Update preview and extract camera info when files are added
        self.parent.update_preview()
        self.parent.extract_camera_info()
        self.update_file_statistics()
        
        # CRITICAL FIX: Enable rename button when files are present
        self.parent.rename_button.setEnabled(len(self.parent.files) > 0)
        
        # Reset EXIF undo check cache
        if hasattr(self.parent, '_exif_undo_checked'):
            del self.parent._exif_undo_checked
        
        # Update buttons to check for EXIF undo data
        if hasattr(self.parent, '_update_buttons'):
            self.parent._update_buttons()
        
        # Start background benchmark with loaded files
        if added_count > 0:
            self._start_background_benchmark()
    
    def _start_background_benchmark(self):
        """Start background benchmark with currently loaded files"""
        log.debug(f"Starting background benchmark with {len(self.parent.files)} files")
        
        if not self.parent.files:
            log.debug("No files - skipping benchmark")
            return
        
        # Only benchmark if we have at least a few files
        if len(self.parent.files) < 3:
            log.debug(f"Only {len(self.parent.files)} files - need at least 3")
            return
        
        # Don't start a new benchmark if one is already running
        if hasattr(self.parent, 'benchmark_thread') and self.parent.benchmark_thread and self.parent.benchmark_thread.isRunning():
            log.debug("Benchmark already running - skipping")
            return
        
        # Check if benchmark_manager exists
        if not hasattr(self.parent, 'benchmark_manager'):
            log.error("benchmark_manager does not exist on parent!")
            return
        
        # Import here to avoid circular imports
        from ..performance_benchmark import BenchmarkThread
        
        sample_count = min(20, len(self.parent.files))  # Use up to 20 samples
        log.info(f"Starting background benchmark with {len(self.parent.files)} files, {sample_count} samples")
        self.parent.status.showMessage(f"⏳ Starting performance benchmark with {sample_count} samples...", 0)
        
        # Start benchmark thread
        self.parent.benchmark_thread = BenchmarkThread(
            sample_files=self.parent.files,
            exiftool_path=self.parent.exiftool_path,
            max_samples=sample_count
        )
        
        # Connect signals
        self.parent.benchmark_thread.benchmark_complete.connect(self._on_benchmark_complete)
        self.parent.benchmark_thread.progress_update.connect(self._on_benchmark_progress)
        
        # Start thread
        self.parent.benchmark_thread.start()
        log.debug(f"Benchmark thread started, isRunning={self.parent.benchmark_thread.isRunning()}")
    
    def _on_benchmark_progress(self, message: str, percentage: int):
        """Handle benchmark progress updates"""
        log.debug(f"Benchmark progress: {message} ({percentage}%)")
        self.parent.status.showMessage(f"⏱ Benchmark: {message} ({percentage}%)", 0)
    
    def _on_benchmark_complete(self, results: dict):
        """Handle benchmark completion"""
        log.info(f"Benchmark complete: {len(results)} scenarios")
        
        if results:
            # Update benchmark manager with results
            self.parent.benchmark_manager.benchmark_results = results
            self.parent.benchmark_manager._benchmark_complete = True
            
            # Log detailed results
            for key, result in results.items():
                log.debug(f"  {key}: {result.per_file_time*1000:.1f}ms per file")
            
            log.debug(f"benchmark_manager.is_ready() = {self.parent.benchmark_manager.is_ready()}")
            self.parent.status.showMessage(f"✓ Performance benchmark completed ({len(results)} scenarios tested)", 5000)
        else:
            log.warning("Benchmark completed with no results")
            self.parent.status.showMessage("⚠ Benchmark failed - using default estimates", 5000)
    
    # Drag & Drop Event Handlers
    def handle_drag_enter(self, event: QDragEnterEvent):
        """Handle drag enter events"""
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()
    
    def handle_drag_move(self, event: QDragMoveEvent):
        """Handle drag move events"""
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()
    
    def handle_drop(self, event: QDropEvent):
        """Handle drop events"""
        files = []
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            if os.path.isfile(file_path) and is_media_file(file_path):
                files.append(file_path)
            elif os.path.isdir(file_path):
                # Scan directory for media files
                media_files = scan_directory_recursive(file_path)
                files.extend(media_files)
        
        if files:
            self.add_files_to_list(files)
        event.accept()
