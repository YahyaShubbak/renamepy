import os
import shutil
import re
import datetime
import time
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QWidget, QLabel, QLineEdit, QPushButton, QListWidget, QFileDialog, QMessageBox, QCheckBox, QDialog, QPlainTextEdit, QHBoxLayout, QStyle, QToolTip, QComboBox, QStatusBar, QListWidgetItem, QStyledItemDelegate
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QMimeData, QSize
from PyQt6.QtGui import QIcon, QTextCursor, QDrag, QPainter, QFont

try:
    import exiftool #### pip install PyExifTool
    EXIFTOOL_AVAILABLE = True
except ImportError:
    EXIFTOOL_AVAILABLE = False

try:
    from PIL import Image
    from PIL.ExifTags import TAGS
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

# Global EXIF cache for performance
_exif_cache = {}
_cache_lock = None

def clear_global_exif_cache():
    """Clear the global EXIF cache for fresh processing"""
    global _exif_cache
    _exif_cache.clear()

def get_filename_components_static(date_taken, camera_prefix, additional, camera_model, lens_model, use_camera, use_lens, num, custom_order, date_format="YYYY-MM-DD", use_date=True):
    """
    Static version of get_filename_components for use in worker threads.
    Build filename components according to the selected order.
    Sequential number is always added at the end.
    """
    year = date_taken[:4]
    month = date_taken[4:6]
    day = date_taken[6:8]
    
    # Format date according to selected format
    formatted_date = None
    if use_date and date_taken:
        if date_format == "YYYY-MM-DD":
            formatted_date = f"{year}-{month}-{day}"
        elif date_format == "YYYY_MM_DD":
            formatted_date = f"{year}_{month}_{day}"
        elif date_format == "DD-MM-YYYY":
            formatted_date = f"{day}-{month}-{year}"
        elif date_format == "DD_MM_YYYY":
            formatted_date = f"{day}_{month}_{year}"
        elif date_format == "YYYYMMDD":
            formatted_date = f"{year}{month}{day}"
        elif date_format == "MM-DD-YYYY":
            formatted_date = f"{month}-{day}-{year}"
        elif date_format == "MM_DD_YYYY":
            formatted_date = f"{month}_{day}_{year}"
        else:
            formatted_date = f"{year}-{month}-{day}"  # Default fallback
    
    # Define all possible components
    components = {
        "Date": formatted_date if (use_date and formatted_date) else None,
        "Prefix": camera_prefix if camera_prefix else None,
        "Additional": additional if additional else None,
        "Camera": camera_model if (use_camera and camera_model) else None,
        "Lens": lens_model if (use_lens and lens_model) else None
    }
    
    # Build ordered list based on custom order
    ordered_parts = []
    for component_name in custom_order:
        component_value = components.get(component_name)
        if component_value:  # Only add non-empty components
            ordered_parts.append(component_value)
    
    # Always add sequential number at the end
    ordered_parts.append(f"{num:03d}")
    
    return ordered_parts

class CustomItemDelegate(QStyledItemDelegate):
    """Custom item delegate to handle separator styling"""
    
    def paint(self, painter, option, index):
        # Check if this is a separator item
        item_data = index.data(Qt.ItemDataRole.UserRole)
        if item_data == "separator":
            # Custom painting for separators - no background, just text
            painter.save()
            
            # Get the text to paint
            text = index.data(Qt.ItemDataRole.DisplayRole)
            
            # Set font - kleiner für kompaktere Darstellung
            font = QFont("Arial", 12, QFont.Weight.Bold)  # Reduziert von 16 auf 12
            painter.setFont(font)
            
            # Set text color
            from PyQt6.QtGui import QColor
            painter.setPen(QColor(0, 0, 0))  # Black text
            
            # Calculate text position (centered)
            rect = option.rect
            text_rect = painter.fontMetrics().boundingRect(text)
            x = rect.x() + (rect.width() - text_rect.width()) // 2
            y = rect.y() + (rect.height() + text_rect.height()) // 2
            
            # Draw the text
            painter.drawText(x, y, text)
            
            painter.restore()
        else:
            # Use default painting for other items
            super().paint(painter, option, index)

class InteractivePreviewWidget(QListWidget):
    """
    Interactive preview widget that allows drag & drop reordering of filename components.
    The sequential number is always shown at the end and cannot be moved.
    """
    order_changed = pyqtSignal(list)  # Signal emitted when order changes
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.setMaximumHeight(80)  # Höherer Bereich für bessere Sichtbarkeit
        self.setMinimumHeight(65)  # Höherer Bereich für bessere Sichtbarkeit
        self.setFlow(QListWidget.Flow.LeftToRight)
        self.setWrapping(False)
        self.setSpacing(2)  # Zurück auf 2px für besseren Abstand zwischen Items
        
        # Set custom item delegate for separator handling
        self.setItemDelegate(CustomItemDelegate(self))
        
        # Style the widget - kompaktere Version
        self.setStyleSheet("""
            QListWidget {
                border: 2px solid #cccccc;
                border-radius: 6px;
                background-color: #f9f9f9;
                padding: 8px;  /* Zurück auf 8px damit Items vollständig sichtbar sind */
                font-size: 11px;  /* Reduziert von 12px */
            }
            QListWidget::item {
                background-color: #e6f3ff;
                border: 1px solid #b3d9ff;
                border-radius: 2px;  /* Kleinerer border-radius */
                padding: 1px 3px;  /* Etwas mehr Padding für bessere Proportionen */
                margin: 0px;  /* Kein Margin */
                font-weight: bold;
                text-align: center;
                font-size: 8px;  /* Erhöht von 7px auf 8px für bessere Sichtbarkeit */
                /* Keine feste min-width - lässt die Box sich an den Text anpassen */
            }
            QListWidget::item:selected {
                background-color: #cce7ff;
                border: 2px solid #0078d4;
            }
            QListWidget::item:hover {
                background-color: #d9ecff;
                border: 1px solid #66c2ff;
            }
            /* Separatoren erhalten keine Box-Styling */
        """)
        
        # Add drag & drop visual feedback
        self.setAcceptDrops(True)
        self.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        
        # Connect signals
        self.itemChanged.connect(self._on_item_changed)
        
        # Store separator
        self.separator = "-"
        
        # Initialize with empty state
        self.components = []
        self.fixed_number = "001"
        
    def set_separator(self, separator):
        """Set the separator character"""
        self.separator = "" if separator == "None" else separator
        self.update_display()
    
    def set_components(self, components, number="001"):
        """Set the filename components to display"""
        self.components = components.copy()
        self.fixed_number = number
        self.update_display()
    
    def update_display(self):
        """Update the visual display of components"""
        self.clear()
        
        # If no components, show helpful placeholder
        if not self.components:
            placeholder_item = QListWidgetItem("Drop files or enter text above to see preview")
            placeholder_item.setFlags(Qt.ItemFlag.NoItemFlags)
            placeholder_item.setData(Qt.ItemDataRole.UserRole, "placeholder")
            placeholder_item.setForeground(Qt.GlobalColor.gray)
            placeholder_item.setFont(QFont("Arial", 10, QFont.Weight.Normal))
            placeholder_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.addItem(placeholder_item)
            return
        
        # Add components and separators in the correct order
        for i, component in enumerate(self.components):
            # Add the component
            item = QListWidgetItem(component)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsDragEnabled)
            item.setData(Qt.ItemDataRole.UserRole, "component")
            item.setToolTip("Drag to swap position with another component")
            
            # Calculate optimal size for the component based on text
            # Use QFont to measure the text size
            font = QFont("Arial", 8)  # Same font as in CSS
            font.setBold(True)
            from PyQt6.QtGui import QFontMetrics
            metrics = QFontMetrics(font)
            text_width = metrics.horizontalAdvance(component)
            text_height = metrics.height()
            
            # Add 10% padding around the text (3px horizontal, 1px vertical padding from CSS)
            optimal_width = text_width + 17  # 3px padding on each side
            optimal_height = text_height   # 1px padding top and bottom
            
            # Set the size hint to fit the text perfectly
            item.setSizeHint(QSize(optimal_width, optimal_height))
            item.setFont(font)  # Ensure consistent font
            
            self.addItem(item)
            
            # Add separator after each component (except the last one)
            if self.separator and i < len(self.components) - 1:
                sep_item = QListWidgetItem(self.separator)
                sep_item.setFlags(Qt.ItemFlag.NoItemFlags)  # Not selectable or draggable
                sep_item.setData(Qt.ItemDataRole.UserRole, "separator")
                # Separator should be just big enough for the separator character
                sep_item.setSizeHint(QSize(8, 20))  # Kompakte Separator-Größe
                self.addItem(sep_item)
        
        # Add final separator before number (only if we have components)
        if self.separator and self.components:
            sep_item = QListWidgetItem(self.separator)
            sep_item.setFlags(Qt.ItemFlag.NoItemFlags)
            sep_item.setData(Qt.ItemDataRole.UserRole, "separator")
            sep_item.setToolTip("Separator character")
            # Kompakte Separator-Größe
            sep_item.setSizeHint(QSize(8, 20))  # Kleinere, angemessene Separator-Größe
            self.addItem(sep_item)
        
        # Add fixed number at the end (not draggable)
        number_item = QListWidgetItem(self.fixed_number)
        number_item.setFlags(Qt.ItemFlag.NoItemFlags)  # Not selectable or draggable
        number_item.setData(Qt.ItemDataRole.UserRole, "number")
        number_item.setBackground(Qt.GlobalColor.yellow)
        number_item.setToolTip("Sequential number (fixed position)")
        
        # Calculate optimal size for the number based on text - use same font size as components
        font = QFont("Arial", 8)  # Same as components
        font.setBold(True)
        number_item.setFont(font)
        
        from PyQt6.QtGui import QFontMetrics
        metrics = QFontMetrics(font)
        text_width = metrics.horizontalAdvance(self.fixed_number)
        text_height = metrics.height()
        
        # Add proper padding around the text (same as components)
        optimal_width = text_width + 17  # 3px padding on each side + margin
        optimal_height = text_height   # 1px padding top and bottom
        
        # Set the size hint to fit the text perfectly
        number_item.setSizeHint(QSize(optimal_width, optimal_height))
        
        self.addItem(number_item)
    
    def get_component_order(self):
        """Get the current order of components (excluding separators and number)"""
        order = []
        for i in range(self.count()):
            item = self.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == "component":
                order.append(item.text())
        return order
    
    def dropEvent(self, event):
        """Handle drop events to swap positions of components"""
        if event.source() == self:
            # Get the dragged item
            dragged_items = self.selectedItems()
            if not dragged_items:
                return
            
            dragged_item = dragged_items[0]
            
            # Only allow moving component items, not separators or numbers
            if dragged_item.data(Qt.ItemDataRole.UserRole) != "component":
                event.ignore()
                return
            
            # Get drop position
            drop_item = self.itemAt(event.position().toPoint())
            
            # Special case: if dropping on number or empty space, move to last position
            if not drop_item or drop_item.data(Qt.ItemDataRole.UserRole) == "number":
                dragged_text = dragged_item.text()
                if dragged_text in self.components:
                    # Move component to last position
                    dragged_index = self.components.index(dragged_text)
                    component = self.components.pop(dragged_index)
                    self.components.append(component)
                    
                    # Update display and emit signal
                    self.update_display()
                    self.order_changed.emit(self.get_component_order())
                event.accept()
                return
            
            # If dropping on separator, find nearest valid component position
            if drop_item and drop_item.data(Qt.ItemDataRole.UserRole) != "component":
                # Find the nearest component position
                drop_row = self.row(drop_item)
                # Look for previous component
                for i in range(drop_row - 1, -1, -1):
                    if self.item(i).data(Qt.ItemDataRole.UserRole) == "component":
                        drop_item = self.item(i)
                        break
                else:
                    # Look for next component
                    for i in range(drop_row + 1, self.count()):
                        if self.item(i).data(Qt.ItemDataRole.UserRole) == "component":
                            drop_item = self.item(i)
                            break
                    else:
                        # No components found, move to last position
                        dragged_text = dragged_item.text()
                        if dragged_text in self.components:
                            dragged_index = self.components.index(dragged_text)
                            component = self.components.pop(dragged_index)
                            self.components.append(component)
                            
                            self.update_display()
                            self.order_changed.emit(self.get_component_order())
                        event.accept()
                        return
            
            # Perform position swap in components list
            dragged_text = dragged_item.text()
            if dragged_text in self.components and drop_item and drop_item.data(Qt.ItemDataRole.UserRole) == "component":
                drop_text = drop_item.text()
                if drop_text in self.components and dragged_text != drop_text:
                    # Find indices of both components
                    dragged_index = self.components.index(dragged_text)
                    drop_index = self.components.index(drop_text)
                    
                    # Swap the positions
                    self.components[dragged_index], self.components[drop_index] = self.components[drop_index], self.components[dragged_index]
                    
                    # Update display and emit signal
                    self.update_display()
                    self.order_changed.emit(self.get_component_order())
        
        event.accept()
    
    def _on_item_changed(self, item):
        """Handle item changes"""
        pass  # We don't allow editing items directly
    
    def get_preview_text(self):
        """Get the complete preview text as it would appear in filename"""
        if not self.components:
            return f"{self.fixed_number}.ARW"
        
        if self.separator:
            return self.separator.join(self.components + [self.fixed_number]) + ".ARW"
        else:
            return "".join(self.components + [self.fixed_number]) + ".ARW"

def get_cached_exif_data(file_path, method, exiftool_path=None):
    """
    Get EXIF data with intelligent caching based on file modification time
    """
    try:
        # Create cache key based on file path and modification time
        mtime = os.path.getmtime(file_path)
        cache_key = (file_path, mtime, method)
        
        # Check cache first
        if cache_key in _exif_cache:
            return _exif_cache[cache_key]
        
        # Extract EXIF data (not cached)
        result = extract_exif_fields_with_retry(file_path, method, exiftool_path, max_retries=2)
        
        # Cache the result
        _exif_cache[cache_key] = result
        
        return result
    except Exception as e:
        print(f"Cached EXIF extraction failed for {file_path}: {e}")
        return None, None, None

class RenameWorkerThread(QThread):
    """
    Worker thread for file renaming to prevent UI freezing
    """
    progress_update = pyqtSignal(str)
    finished = pyqtSignal(list, list)
    error = pyqtSignal(str)
    
    def __init__(self, files, camera_prefix, additional, use_camera, use_lens, 
                 exif_method, devider, exiftool_path, custom_order, date_format="YYYY-MM-DD", use_date=True):
        super().__init__()
        self.files = files
        self.camera_prefix = camera_prefix
        self.additional = additional
        self.use_camera = use_camera
        self.use_lens = use_lens
        self.exif_method = exif_method
        self.devider = devider
        self.exiftool_path = exiftool_path
        self.custom_order = custom_order
        self.date_format = date_format
        self.use_date = use_date
    
    def run(self):
        """Run the rename operation in background thread"""
        try:
            self.progress_update.emit("Starting rename operation...")
            
            # Use optimized rename function
            renamed_files, errors = self.optimized_rename_files()
            
            self.finished.emit(renamed_files, errors)
        except Exception as e:
            self.error.emit(str(e))
    
    def optimized_rename_files(self):
        """
        Optimized rename function with batch EXIF processing
        """
        import re
        from collections import defaultdict
        
        self.progress_update.emit("Grouping files...")
        
        # Clear cache for fresh processing
        clear_global_exif_cache()
        
        # Step 1: Group files by basename (fast)
        file_groups = []
        basename_groups = defaultdict(list)
        for file in self.files:
            if is_image_file(file):
                base = os.path.splitext(os.path.basename(file))[0]
                basename_groups[base].append(file)
        
        # Separate grouped and orphaned files
        orphaned_files = []
        for base, file_list in basename_groups.items():
            if len(file_list) > 1:
                file_groups.append(file_list)
            else:
                orphaned_files.extend(file_list)
        
        # Add orphans as individual groups (simple approach for now)
        for file in orphaned_files:
            file_groups.append([file])
        
        self.progress_update.emit(f"Processing {len(file_groups)} file groups...")
        
        # Step 2: Process each group with cached EXIF reads
        renamed_files = []
        errors = []
        date_counter = {}
        
        for i, group_files in enumerate(file_groups):
            if i % 10 == 0:  # Update progress every 10 groups
                self.progress_update.emit(f"Processing group {i+1}/{len(file_groups)}")
            
            # Check file access
            accessible_files = [f for f in group_files if check_file_access(f)]
            if not accessible_files:
                continue
            
            # Extract EXIF data using cache
            date_taken = None
            camera_model = None
            lens_model = None
            
            for file in accessible_files:
                if self.use_camera and not camera_model:
                    _, camera_model, _ = get_cached_exif_data(file, self.exif_method, self.exiftool_path)
                if self.use_lens and not lens_model:
                    _, _, lens_model = get_cached_exif_data(file, self.exif_method, self.exiftool_path)
                if not date_taken:
                    date_taken, _, _ = get_cached_exif_data(file, self.exif_method, self.exiftool_path)
                
                if date_taken and (not self.use_camera or camera_model) and (not self.use_lens or lens_model):
                    break
            
            # Fallback date extraction
            if not date_taken:
                for file in accessible_files:
                    m = re.search(r'(20\d{2})(\d{2})(\d{2})', os.path.basename(file))
                    if m:
                        date_taken = f"{m.group(1)}{m.group(2)}{m.group(3)}"
                        break
            
            if not date_taken:
                file = accessible_files[0]
                mtime = os.path.getmtime(file)
                dt = datetime.datetime.fromtimestamp(mtime)
                date_taken = dt.strftime('%Y%m%d')
            
            # Counter logic
            if date_taken not in date_counter:
                date_counter[date_taken] = 1
            else:
                date_counter[date_taken] += 1
            num = date_counter[date_taken]
            year = date_taken[:4]
            month = date_taken[4:6]
            day = date_taken[6:8]
            
            # Rename files in group
            for file in accessible_files:
                try:
                    ext = os.path.splitext(file)[1]
                    
                    # Use get_filename_components_static for ordered naming
                    name_parts = get_filename_components_static(
                        date_taken, self.camera_prefix, self.additional, 
                        camera_model, lens_model, self.use_camera, self.use_lens, 
                        num, self.custom_order, self.date_format, self.use_date
                    )
                    
                    sep = "" if self.devider == "None" else self.devider
                    new_name = sep.join(name_parts) + ext
                    new_name = sanitize_final_filename(new_name)
                    new_path = get_safe_target_path(file, new_name)
                    
                    if not validate_path_length(new_path):
                        directory = os.path.dirname(file)
                        base, ext = os.path.splitext(new_name)
                        max_name_len = 200 - len(directory)
                        if max_name_len > 10:
                            shortened_base = base[:max_name_len - len(ext)]
                            new_name = shortened_base + ext
                            new_path = os.path.join(directory, new_name)
                        else:
                            errors.append(f"Path too long: {file}")
                            continue
                    
                    os.rename(file, new_path)
                    renamed_files.append(new_path)
                    
                except Exception as e:
                    errors.append(f"Failed to rename {os.path.basename(file)}: {e}")
        
        return renamed_files, errors

IMAGE_EXTENSIONS = [
    '.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.gif', 
    '.cr2', '.nef', '.arw', '.orf', '.rw2', '.dng', '.raw', '.sr2', '.pef', '.raf', '.3fr', '.erf', '.kdc', '.mos', '.nrw', '.srw', '.x3f'
]

def is_image_file(filename):
    """
    Returns True if the file is an image or RAW file based on its extension.
    """
    return os.path.splitext(filename)[1].lower() in IMAGE_EXTENSIONS

def scan_directory_recursive(directory):
    """
    Recursively scan directory for image files in all subdirectories.
    Returns a list of all image file paths found.
    """
    image_files = []
    try:
        for root, dirs, files in os.walk(directory):
            for file in files:
                if is_image_file(file):
                    full_path = os.path.join(root, file)
                    image_files.append(full_path)
    except Exception as e:
        print(f"Error scanning directory {directory}: {e}")
    
    return image_files

def is_exiftool_installed():
    """
    Check for exiftool installation in multiple locations.
    Returns the absolute path to exiftool.exe if found, None otherwise.
    """
    # Test 1: System PATH
    exe = shutil.which("exiftool")
    if exe:
        return exe
    
    # Test 2: Current directory
    local = os.path.join(os.getcwd(), "exiftool.exe")
    if os.path.exists(local):
        return local
    
    # Test 3: exiftool-13.32_64 subdirectory (relative to script)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    custom = os.path.join(script_dir, "exiftool-13.32_64", "exiftool.exe")
    if os.path.exists(custom):
        return custom
    
    # Test 4: Direct check in common locations
    possible_paths = [
        os.path.join(script_dir, "exiftool.exe"),
        os.path.join(script_dir, "exiftool", "exiftool.exe"),
        "C:\\exiftool\\exiftool.exe"
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            return path
    
    return None

# Dynamische EXIF-Auslese

def extract_exif_fields(image_path, method, exiftool_path=None):
    """
    Extracts date, camera model, and lens model from an image using the specified method.
    Returns (date, camera, lens) or (None, None, None) if not found.
    """
    return extract_exif_fields_with_retry(image_path, method, exiftool_path, max_retries=3)

def extract_exif_fields_with_retry(image_path, method, exiftool_path=None, max_retries=3):
    """
    Extracts EXIF fields with retry mechanism for reliability.
    """
    import time
    
    for attempt in range(max_retries):
        try:
            if method == "exiftool":
                # Use exiftool with or without explicit path
                if exiftool_path and os.path.exists(exiftool_path):
                    with exiftool.ExifToolHelper(executable=exiftool_path) as et:
                        meta = et.get_metadata([image_path])[0]
                else:
                    # Try to use system exiftool or let exiftool package find it
                    with exiftool.ExifToolHelper() as et:
                        meta = et.get_metadata([image_path])[0]
                
                # Extract date
                date = meta.get('EXIF:DateTimeOriginal')
                if date:
                    date = date.split(' ')[0].replace(':', '')
                
                # Extract camera model
                camera = meta.get('EXIF:Model')
                if camera:
                    camera = str(camera).replace(' ', '-')
                
                # Extract lens model
                lens = meta.get('EXIF:LensModel')
                if lens:
                    lens = str(lens).replace(' ', '-')
                
                return date, camera, lens
                
            elif method == "pillow":
                image = Image.open(image_path)
                exif_data = image._getexif()
                date = None
                camera = None
                lens = None
                if exif_data:
                    for tag, value in exif_data.items():
                        decoded_tag = TAGS.get(tag, tag)
                        if decoded_tag == "DateTimeOriginal" and not date:
                            date = value.split(" ")[0].replace(":", "")
                        if decoded_tag == "Model" and not camera:
                            camera = str(value).replace(" ", "-")
                        if decoded_tag == "LensModel" and not lens:
                            lens = str(value).replace(" ", "-")
                return date, camera, lens
            else:
                return None, None, None
                
        except Exception as e:
            if attempt == max_retries - 1:
                print(f"Failed to extract EXIF after {max_retries} attempts from {image_path}: {e}")
                return None, None, None
            else:
                print(f"EXIF extraction attempt {attempt + 1} failed, retrying... ({e})")
                time.sleep(0.1)  # Brief pause before retry

def extract_date_taken(image_path, method, exiftool_path=None):
    """
    Extracts only the date from an image using the specified method.
    """
    date, _, _ = extract_exif_fields(image_path, method, exiftool_path)
    return date

def extract_camera_model(image_path, method, exiftool_path=None):
    """
    Extracts only the camera model from an image using the specified method.
    """
    _, camera, _ = extract_exif_fields(image_path, method, exiftool_path)
    return camera

def extract_lens_model(image_path, method, exiftool_path=None):
    """
    Extracts only the lens model from an image using the specified method.
    """
    _, _, lens = extract_exif_fields(image_path, method, exiftool_path)
    return lens

def extract_image_number(image_path, method, exiftool_path=None):
    """
    Extracts the image number/shutter count from an image using the specified method.
    Returns the image number as a string or None if not found.
    """
    if method == "exiftool":
        try:
            # Use exiftool with or without explicit path
            if exiftool_path and os.path.exists(exiftool_path):
                with exiftool.ExifToolHelper(executable=exiftool_path) as et:
                    meta = et.get_metadata([image_path])[0]
            else:
                # Try to use system exiftool or let exiftool package find it
                with exiftool.ExifToolHelper() as et:
                    meta = et.get_metadata([image_path])[0]
            
            # Try different possible fields for image number/shutter count
            possible_fields = [
                'EXIF:ImageNumber',
                'EXIF:ShutterCount', 
                'MakerNotes:ShutterCount',
                'MakerNotes:ImageNumber',
                'Canon:ImageNumber',
                'Nikon:ShutterCount',
                'Sony:ShotNumberSincePowerUp',
                'Sony:ImageNumber',
                'File:FileNumber'
            ]
            
            for field in possible_fields:
                if field in meta and meta[field] is not None:
                    return str(meta[field])
            
            return None
            
        except Exception as e:
            print(f"ExifTool error for image number in {image_path}: {e}")
            return None
    elif method == "pillow":
        try:
            image = Image.open(image_path)
            exif_data = image._getexif()
            if exif_data:
                for tag, value in exif_data.items():
                    decoded_tag = TAGS.get(tag, tag)
                    if decoded_tag in ["ImageNumber", "ShutterCount"]:
                        return str(value)
            return None
        except Exception as e:
            print(f"Pillow error for image number in {image_path}: {e}")
            return None
    else:
        return None


def get_file_timestamp(image_path, method, exiftool_path=None):
    """
    Extracts the file timestamp from an image using the specified method.
    Returns the timestamp as a string or None if not found.
    """
    if method == "exiftool":
        try:
            # Use exiftool with or without explicit path
            if exiftool_path and os.path.exists(exiftool_path):
                with exiftool.ExifToolHelper(executable=exiftool_path) as et:
                    meta = et.get_metadata([image_path])[0]
            else:
                # Try to use system exiftool or let exiftool package find it
                with exiftool.ExifToolHelper() as et:
                    meta = et.get_metadata([image_path])[0]
            
            # Try different possible timestamp fields
            possible_fields = [
                'EXIF:DateTimeOriginal',
                'EXIF:CreateDate', 
                'File:FileModifyDate',
                'File:FileCreateDate',
                'EXIF:DateTime'
            ]
            
            for field in possible_fields:
                if field in meta and meta[field] is not None:
                    return str(meta[field])
            
            return None
            
        except Exception as e:
            print(f"ExifTool error for timestamp in {image_path}: {e}")
            return None
    elif method == "pillow":
        try:
            image = Image.open(image_path)
            exif_data = image._getexif()
            if exif_data:
                for tag, value in exif_data.items():
                    decoded_tag = TAGS.get(tag, tag)
                    if decoded_tag in ["DateTimeOriginal", "DateTime"]:
                        return str(value)
            return None
        except Exception as e:
            print(f"Pillow error for timestamp in {image_path}: {e}")
            return None
    else:
        return None

def sanitize_filename(filename):
    """
    Sanitize filename by removing/replacing invalid characters and ensuring compatibility.
    """
    # First check if filename is only whitespace - return empty string instead of 'unnamed_file'
    if not filename or filename.isspace():
        return ""
    
    # Remove/replace invalid characters for Windows/Unix
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    
    # Remove control characters (ASCII 0-31) and replace with underscore
    filename = ''.join(char if ord(char) >= 32 else '_' for char in filename)
    
    # Remove trailing and leading dots and spaces (Windows issue)
    filename = filename.strip('. ')
    
    # Remove multiple consecutive underscores and spaces
    import re
    filename = re.sub(r'_+', '_', filename)
    filename = re.sub(r'\s+', ' ', filename)  # Collapse multiple spaces
    filename = filename.strip()  # Remove leading/trailing spaces again
    
    # Only use 'unnamed_file' for actual file names, not for components
    # Return empty string if sanitization resulted in empty content
    if not filename or filename == '_':
        return ""
    
    # Limit length to prevent filesystem issues (keep extension)
    if len(filename) > 200:
        base, ext = os.path.splitext(filename)
        filename = base[:200-len(ext)] + ext
    
    return filename

def sanitize_final_filename(filename):
    """
    Sanitize a complete filename, ensuring it's not empty for file operations.
    This is different from sanitize_filename which is used for components.
    """
    # First use the regular sanitization
    sanitized = sanitize_filename(filename)
    
    # If the result is empty, use a fallback name
    if not sanitized:
        return "unnamed_file"
    
    return sanitized

def check_file_access(file_path):
    """
    Check if file can be accessed and renamed.
    Returns True if accessible, False otherwise.
    """
    try:
        # Test if file exists and is accessible
        if not os.path.exists(file_path):
            return False
        
        # Test read access
        with open(file_path, 'rb') as f:
            f.read(1)
        
        # Test if file is locked by checking if we can open it for writing
        with open(file_path, 'r+b') as f:
            pass
            
        return True
    except (PermissionError, OSError, IOError):
        return False

def get_safe_target_path(original_path, new_name):
    """
    Generate a safe target path, avoiding conflicts with existing files.
    """
    directory = os.path.dirname(original_path)
    new_path = os.path.join(directory, new_name)
    
    # Check if target already exists
    if not os.path.exists(new_path):
        return new_path
    
    # Generate alternative name if conflict exists
    base, ext = os.path.splitext(new_name)
    attempt = 1
    
    while os.path.exists(new_path) and attempt <= 999:
        alternative_name = f"{base}_conflict_{attempt:03d}{ext}"
        new_path = os.path.join(directory, alternative_name)
        attempt += 1
    
    if attempt > 999:
        # Fallback: add timestamp
        import time
        timestamp = int(time.time())
        alternative_name = f"{base}_conflict_{timestamp}{ext}"
        new_path = os.path.join(directory, alternative_name)
    
    return new_path

def validate_path_length(file_path):
    """
    Validate that the file path is not too long for the filesystem.
    Returns True if valid, False if too long.
    """
    # Windows has a 260 character limit, leave buffer
    max_length = 250
    return len(file_path) <= max_length

def group_files_with_failsafe(files, exif_method, exiftool_path=None):
    """
    Groups files by basename first, then tries to group orphaned files by timestamp.
    Returns a list of file groups (each group is a list of files that belong together).
    """
    from collections import defaultdict
    import re
    from datetime import datetime
    
    # Step 1: Group by basename (normal case)
    basename_groups = defaultdict(list)
    for file in files:
        base = os.path.splitext(os.path.basename(file))[0]
        basename_groups[base].append(file)
    
    # Step 2: Find orphaned files (groups with only one file)
    final_groups = []
    orphaned_files = []
    
    for base, file_list in basename_groups.items():
        if len(file_list) > 1:
            # Multiple files with same basename - they belong together
            final_groups.append(file_list)
        else:
            # Single file - potential orphan
            orphaned_files.append(file_list[0])
    
    # Step 3: Try to match orphaned files by timestamp
    if len(orphaned_files) > 1 and exif_method:
        print(f"Found {len(orphaned_files)} orphaned files, trying timestamp matching...")
        
        # Extract timestamps for orphaned files
        file_timestamps = {}
        for file in orphaned_files:
            timestamp = get_file_timestamp(file, exif_method, exiftool_path)
            if timestamp:
                # Parse timestamp to compare (remove timezone info for comparison)
                try:
                    # Handle different timestamp formats
                    clean_timestamp = timestamp.split('+')[0].split('-')[0]  # Remove timezone
                    parsed_time = datetime.strptime(clean_timestamp, '%Y:%m:%d %H:%M:%S')
                    file_timestamps[file] = parsed_time
                except:
                    try:
                        # Try alternative format
                        parsed_time = datetime.strptime(clean_timestamp, '%Y-%m-%d %H:%M:%S')
                        file_timestamps[file] = parsed_time
                    except:
                        print(f"Could not parse timestamp for {file}: {timestamp}")
        
        # Group files with timestamps within 2 seconds of each other
        used_files = set()
        for file1 in orphaned_files:
            if file1 in used_files or file1 not in file_timestamps:
                continue
                
            group = [file1]
            used_files.add(file1)
            
            for file2 in orphaned_files:
                if file2 in used_files or file2 not in file_timestamps:
                    continue
                
                # Check if timestamps are within 2 seconds
                time_diff = abs((file_timestamps[file1] - file_timestamps[file2]).total_seconds())
                if time_diff <= 2:
                    group.append(file2)
                    used_files.add(file2)
            
            final_groups.append(group)
        
        # Add remaining orphaned files as individual groups
        for file in orphaned_files:
            if file not in used_files:
                final_groups.append([file])
    else:
        # No timestamp matching possible, add orphans as individual groups
        for file in orphaned_files:
            final_groups.append([file])
    
    return final_groups

def verify_group_consistency(group, exif_method, exiftool_path=None):
    """
    Verify that grouped files have consistent EXIF data (same camera, similar timestamps).
    Returns True if consistent, False if suspicious grouping detected.
    """
    if len(group) < 2:
        return True
    
    # Extract EXIF data from all files in group
    exif_data = []
    for file in group:
        date, camera, lens = extract_exif_fields(file, exif_method, exiftool_path)
        timestamp = get_file_timestamp(file, exif_method, exiftool_path)
        exif_data.append({
            'file': file,
            'date': date,
            'camera': camera,
            'lens': lens,
            'timestamp': timestamp
        })
    
    # Check camera consistency
    cameras = [data['camera'] for data in exif_data if data['camera']]
    if len(set(cameras)) > 1:
        print(f"Warning: Different cameras in group: {set(cameras)}")
        print(f"Files: {[os.path.basename(data['file']) for data in exif_data]}")
        return False
    
    # Check timestamp consistency (should be very close)
    timestamps = []
    for data in exif_data:
        if data['timestamp']:
            try:
                from datetime import datetime
                clean_timestamp = data['timestamp'].split('+')[0].split('-')[0]
                parsed_time = datetime.strptime(clean_timestamp, '%Y:%m:%d %H:%M:%S')
                timestamps.append(parsed_time)
            except:
                continue
    
    if len(timestamps) >= 2:
        # Check if all timestamps are within 5 seconds of each other
        min_time = min(timestamps)
        max_time = max(timestamps)
        time_diff = (max_time - min_time).total_seconds()
        
        if time_diff > 5:
            print(f"Warning: Large time difference in group: {time_diff} seconds")
            print(f"Files: {[os.path.basename(data['file']) for data in exif_data]}")
            return False
    
    return True

def rename_files(files, camera_prefix, additional, use_camera, use_lens, exif_method, devider="_", exiftool_path=None, custom_order=None):
    """
    Batch rename files based on EXIF data and user options.
    Groups files by base name with failsafe timestamp matching, extracts EXIF only once per group, and applies a running counter per date.
    Returns a list of new file paths and any errors encountered.
    """
    import re
    
    # Default order if not provided
    if custom_order is None:
        custom_order = ["Date", "Prefix", "Additional", "Camera", "Lens"]
    
    # Use improved grouping with failsafe
    file_groups = group_files_with_failsafe(files, exif_method, exiftool_path)

    renamed_files = []
    errors = []
    skipped_files = []
    date_counter = {}
    
    for group_files in file_groups:
        # Verify group consistency
        if not verify_group_consistency(group_files, exif_method, exiftool_path):
            print(f"Warning: Inconsistent group detected, but proceeding with rename...")
        
        # Check file access for all files in group
        accessible_files = []
        for file in group_files:
            if not check_file_access(file):
                error_msg = f"Cannot access file (locked/permission denied): {os.path.basename(file)}"
                errors.append(error_msg)
                print(error_msg)
                skipped_files.append(file)
            else:
                accessible_files.append(file)
        
        if not accessible_files:
            continue  # Skip this group entirely if no files are accessible
        
        # Extract EXIF data
        date_taken = None
        camera_model = None
        lens_model = None
        for file in accessible_files:
            if use_camera and not camera_model:
                camera_model = extract_camera_model(file, exif_method, exiftool_path)
            if use_lens and not lens_model:
                lens_model = extract_lens_model(file, exif_method, exiftool_path)
            if not date_taken:
                date_taken = extract_date_taken(file, exif_method, exiftool_path)
            if date_taken and (not use_camera or camera_model) and (not use_lens or lens_model):
                break
        
        # Fallback date extraction
        if not date_taken:
            for file in accessible_files:
                m = re.search(r'(20\d{2})(\d{2})(\d{2})', os.path.basename(file))
                if m:
                    date_taken = f"{m.group(1)}{m.group(2)}{m.group(3)}"
                    break
        if not date_taken:
            # Fallback: use file modification date
            file = accessible_files[0]
            mtime = os.path.getmtime(file)
            dt = datetime.datetime.fromtimestamp(mtime)
            date_taken = dt.strftime('%Y%m%d')
        
        # Running counter per date
        if date_taken not in date_counter:
            date_counter[date_taken] = 1
        else:
            date_counter[date_taken] += 1
        num = date_counter[date_taken]
        year = date_taken[:4]
        month = date_taken[4:6]
        day = date_taken[6:8]
        
        # Rename each accessible file in the group
        for file in accessible_files:
            try:
                ext = os.path.splitext(file)[1]
                
                # Use get_filename_components_static for ordered naming
                name_parts = get_filename_components_static(
                    date_taken, camera_prefix, additional, 
                    camera_model, lens_model, use_camera, use_lens, 
                    num, custom_order
                )
                
                sep = "" if devider == "None" else devider
                new_name = sep.join(name_parts) + ext
                
                # Sanitize filename
                new_name = sanitize_final_filename(new_name)
                
                # Get safe target path (handles conflicts)
                new_path = get_safe_target_path(file, new_name)
                
                # Validate path length
                if not validate_path_length(new_path):
                    # Shorten filename if path too long
                    directory = os.path.dirname(file)
                    base, ext = os.path.splitext(new_name)
                    max_name_len = 200 - len(directory)
                    if max_name_len > 10:  # Ensure minimum filename length
                        shortened_base = base[:max_name_len - len(ext)]
                        new_name = shortened_base + ext
                        new_path = os.path.join(directory, new_name)
                    else:
                        error_msg = f"Path too long, cannot shorten further: {file}"
                        errors.append(error_msg)
                        print(error_msg)
                        continue
                
                # Perform the rename
                os.rename(file, new_path)
                renamed_files.append(new_path)
                print(f"Renamed: {os.path.basename(file)} → {os.path.basename(new_path)}")
                
            except Exception as e:
                error_msg = f"Failed to rename {os.path.basename(file)}: {e}"
                errors.append(error_msg)
                print(error_msg)
                skipped_files.append(file)
    
    # Print summary
    print(f"\nRename Summary:")
    print(f"Successfully renamed: {len(renamed_files)} files")
    if errors:
        print(f"Errors encountered: {len(errors)}")
        print(f"Skipped files: {len(skipped_files)}")
    
    return renamed_files, errors

class FileRenamerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("File Renamer")
        
        # Set application icon using custom icon.ico file
        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        else:
            # Fallback to standard icon if icon.ico is not found
            self.setWindowIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView))
        
        self.setGeometry(100, 100, 600, 400)
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)

        # Theme Switch - ganz oben
        theme_row = QHBoxLayout()
        theme_label = QLabel("Theme:")
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["System", "Light", "Dark"])
        self.theme_combo.setCurrentText("System")
        self.theme_combo.currentTextChanged.connect(self.on_theme_changed)
        theme_row.addWidget(theme_label)
        theme_row.addWidget(self.theme_combo)
        theme_row.addStretch()
        self.layout.addLayout(theme_row)

        # File Selection Menu Bar
        file_menu_row = QHBoxLayout()
        file_menu_row.setSpacing(10)
        
        # File selection buttons styled as menu bar
        self.select_files_menu_button = QPushButton("📄 Select Files")
        self.select_files_menu_button.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 6px;
                font-weight: bold;
                min-width: 120px;
            }
            QPushButton:hover {
                background-color: #106ebe;
            }
            QPushButton:pressed {
                background-color: #005a9e;
            }
        """)
        self.select_files_menu_button.clicked.connect(self.select_files)
        
        self.select_folder_menu_button = QPushButton("📁 Select Folder")
        self.select_folder_menu_button.setStyleSheet("""
            QPushButton {
                background-color: #107c10;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 6px;
                font-weight: bold;
                min-width: 120px;
            }
            QPushButton:hover {
                background-color: #0e6e0e;
            }
            QPushButton:pressed {
                background-color: #0c5a0c;
            }
        """)
        self.select_folder_menu_button.clicked.connect(self.select_folder)
        
        self.clear_files_menu_button = QPushButton("🗑️ Clear Files")
        self.clear_files_menu_button.setStyleSheet("""
            QPushButton {
                background-color: #d83b01;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 6px;
                font-weight: bold;
                min-width: 120px;
            }
            QPushButton:hover {
                background-color: #c73401;
            }
            QPushButton:pressed {
                background-color: #a72d01;
            }
        """)
        self.clear_files_menu_button.clicked.connect(self.clear_file_list)
        
        file_menu_row.addWidget(self.select_files_menu_button)
        file_menu_row.addWidget(self.select_folder_menu_button)
        file_menu_row.addWidget(self.clear_files_menu_button)
        file_menu_row.addStretch()
        self.layout.addLayout(file_menu_row)

        # Date options
        date_options_row = QHBoxLayout()
        self.checkbox_date = QCheckBox("Include date in filename")
        self.checkbox_date.setChecked(True)  # Default: aktiviert
        self.checkbox_date.stateChanged.connect(self.update_preview)
        
        date_format_label = QLabel("Date Format:")
        self.date_format_combo = QComboBox()
        self.date_format_combo.addItems([
            "YYYY-MM-DD", "YYYY_MM_DD", "DD-MM-YYYY", "DD_MM_YYYY", 
            "YYYYMMDD", "MM-DD-YYYY", "MM_DD_YYYY"
        ])
        self.date_format_combo.setCurrentText("YYYY-MM-DD")  # Default
        self.date_format_combo.currentTextChanged.connect(self.update_preview)
        
        date_options_row.addWidget(self.checkbox_date)
        date_options_row.addWidget(date_format_label)
        date_options_row.addWidget(self.date_format_combo)
        date_options_row.addStretch()
        self.layout.addLayout(date_options_row)

        # Camera Prefix with clickable info icon
        camera_layout = QVBoxLayout()
        camera_label = QLabel("Camera Prefix:")
        camera_info = QLabel()
        camera_info.setPixmap(self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxInformation).pixmap(16, 16))
        camera_info.setToolTip("Click for detailed info about camera prefix")
        camera_info.setCursor(Qt.CursorShape.PointingHandCursor)
        camera_info.mousePressEvent = lambda event: self.show_camera_prefix_info()
        camera_row = QHBoxLayout()
        camera_row.addWidget(camera_label)
        camera_row.addWidget(camera_info)
        camera_row.addStretch()
        self.layout.addLayout(camera_row)
        self.camera_prefix_entry = QLineEdit()
        self.camera_prefix_entry.setPlaceholderText("e.g. A7R3, D850")
        self.camera_prefix_entry.textChanged.connect(self.validate_and_update_preview)
        self.layout.addWidget(self.camera_prefix_entry)
        # Additional with clickable info icon
        additional_label = QLabel("Additional:")
        additional_info = QLabel()
        additional_info.setPixmap(self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxInformation).pixmap(16, 16))
        additional_info.setToolTip("Click for detailed info about additional field")
        additional_info.setCursor(Qt.CursorShape.PointingHandCursor)
        additional_info.mousePressEvent = lambda event: self.show_additional_info()
        additional_row = QHBoxLayout()
        additional_row.addWidget(additional_label)
        additional_row.addWidget(additional_info)
        additional_row.addStretch()
        self.layout.addLayout(additional_row)
        self.additional_entry = QLineEdit()
        self.additional_entry.setPlaceholderText("e.g. vacation, wedding")
        self.additional_entry.textChanged.connect(self.validate_and_update_preview)
        self.layout.addWidget(self.additional_entry)

        # Devider selection with clickable info icon
        devider_row = QHBoxLayout()
        devider_label = QLabel("Devider:")
        devider_info = QLabel()
        devider_info.setPixmap(self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxInformation).pixmap(16, 16))
        devider_info.setToolTip("Click for detailed info about separators")
        devider_info.setCursor(Qt.CursorShape.PointingHandCursor)
        devider_info.mousePressEvent = lambda event: self.show_devider_info()
        devider_row.addWidget(devider_label)
        devider_row.addWidget(devider_info)
        devider_row.addStretch()
        self.layout.addLayout(devider_row)
        self.devider_combo = QComboBox()
        self.devider_combo.addItems(["None", "_", "-"])
        self.devider_combo.setCurrentText("-")  # Set default to dash for better readability
        self.layout.addWidget(self.devider_combo)
        self.devider_combo.currentIndexChanged.connect(self.update_preview)
        self.devider_combo.currentIndexChanged.connect(self.on_devider_changed)

        # Interactive Preview section with clickable info icon
        preview_row = QHBoxLayout()
        preview_label = QLabel("Interactive Preview:")
        preview_info = QLabel()
        preview_info.setPixmap(self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxInformation).pixmap(16, 16))
        preview_info.setToolTip("Click for detailed info about interactive preview")
        preview_info.setCursor(Qt.CursorShape.PointingHandCursor)
        preview_info.mousePressEvent = lambda event: self.show_preview_info()
        preview_row.addWidget(preview_label)
        preview_row.addWidget(preview_info)
        preview_row.addStretch()
        self.layout.addLayout(preview_row)
        
        self.interactive_preview = InteractivePreviewWidget()
        self.interactive_preview.order_changed.connect(self.on_preview_order_changed)
        self.layout.addWidget(self.interactive_preview)

        # Camera checkbox with model display
        camera_checkbox_layout = QHBoxLayout()
        self.checkbox_camera = QCheckBox("Include camera model in filename")
        self.camera_model_label = QLabel("(detecting...)")
        self.camera_model_label.setStyleSheet("color: gray; font-style: italic;")
        camera_checkbox_layout.addWidget(self.checkbox_camera)
        camera_checkbox_layout.addWidget(self.camera_model_label)
        camera_checkbox_layout.addStretch()
        self.layout.addLayout(camera_checkbox_layout)
        self.checkbox_camera.stateChanged.connect(self.update_preview)
        
        # Lens checkbox with model display
        lens_checkbox_layout = QHBoxLayout()
        self.checkbox_lens = QCheckBox("Include lens in filename")
        self.lens_model_label = QLabel("(detecting...)")
        self.lens_model_label.setStyleSheet("color: gray; font-style: italic;")
        lens_checkbox_layout.addWidget(self.checkbox_lens)
        lens_checkbox_layout.addWidget(self.lens_model_label)
        lens_checkbox_layout.addStretch()
        self.layout.addLayout(lens_checkbox_layout)
        self.checkbox_lens.stateChanged.connect(self.update_preview)

        # Drag & Drop File List with dashed border and info text
        self.file_list = QListWidget()
        self.file_list.setStyleSheet("""
            QListWidget {
                border: 2px dashed #cccccc;
                border-radius: 8px;
                background-color: #fafafa;
                padding: 20px;
                min-height: 120px;
            }
            QListWidget::item {
                padding: 4px;
                border-bottom: 1px solid #eeeeee;
                background-color: white;
                border-radius: 3px;
                margin: 1px;
            }
            QListWidget::item:selected {
                background-color: #0078d4;
                color: white;
            }
            QListWidget::item:hover {
                background-color: #f0f6ff;
            }
        """)
        
        # Add placeholder text when empty
        self.update_file_list_placeholder()
        
        self.layout.addWidget(self.file_list)
        self.file_list.itemDoubleClicked.connect(self.show_selected_exif)
        self.file_list.itemClicked.connect(self.show_image_info)
        
        # Enhanced info for image clicking with visual indicator - zurückhaltender gestaltet
        file_list_info = QLabel("💡Single click = Image info in status bar | Double click = Full EXIF data dialog")
        file_list_info.setStyleSheet("""
            QLabel {
                background-color: #f8f9fa;
                border: 2px solid #dee2e6;
                border-radius: 4px;
                padding: 6px;
                color: #6c757d;
                font-size: 11px;
                font-weight: normal;
            }
        """)
        file_list_info.setWordWrap(True)
        file_list_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(file_list_info)
        
        self.file_list.setToolTip("Single click: Image info | Double click: Full EXIF data")
        self.file_list.installEventFilter(self)

        self.setAcceptDrops(True)

        # Prominenter Rename Button
        self.rename_button = QPushButton("🚀 Rename Files")
        self.rename_button.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                border: none;
                padding: 12px 24px;
                border-radius: 8px;
                font-weight: bold;
                font-size: 14px;
                min-height: 20px;
            }
            QPushButton:hover {
                background-color: #218838;
                transform: translateY(-1px);
            }
            QPushButton:pressed {
                background-color: #1e7e34;
            }
            QPushButton:disabled {
                background-color: #6c757d;
                color: #ffffff;
            }
        """)
        self.rename_button.clicked.connect(self.rename_files_action)
        self.layout.addWidget(self.rename_button)

        self.files = []
        self.exiftool_path = is_exiftool_installed()
        
        if EXIFTOOL_AVAILABLE and self.exiftool_path:
            self.exif_method = "exiftool"
        elif PIL_AVAILABLE:
            self.exif_method = "pillow"
        else:
            self.exif_method = None
        
        # Statusbar für Info unten rechts
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        # Label für Methode und ggf. Info-Icon
        self.exif_status_label = QLabel()
        self.status.addPermanentWidget(self.exif_status_label)
        
        # Initialize custom ordering BEFORE calling update_preview
        self.custom_order = ["Date", "Prefix", "Additional", "Camera", "Lens"]  # Number always at end
        
        self.update_exif_status()
        self.update_preview()
        self.update_file_list_placeholder()  # Add initial placeholder

        # EXIF cache for preview file
        self._preview_exif_cache = {}
        self._preview_exif_file = None
        
        # Update camera and lens labels initially
        self.update_camera_lens_labels()

    def on_preview_order_changed(self, new_order):
        """Handle changes from the interactive preview widget"""
        # Map display names back to internal names
        display_to_internal = {
            "2025-07-21": "Date",
            "A7R3": "Prefix", 
            "Sarah30": "Additional",
            "ILCE-7RM3": "Camera",
            "FE24-70": "Lens"
        }
        
        # Convert display order to internal order
        internal_order = []
        for display_name in new_order:
            # Try exact match first
            if display_name in display_to_internal:
                internal_order.append(display_to_internal[display_name])
            else:
                # Try to guess based on content
                if re.match(r'\d{4}-\d{2}-\d{2}', display_name):
                    internal_order.append("Date")
                elif display_name in ["A7R3", "D850"]:  # Common prefixes
                    internal_order.append("Prefix")
                elif display_name in ["ILCE-7RM3", "D850"]:  # Camera models
                    internal_order.append("Camera")
                elif "FE" in display_name or "mm" in display_name:  # Lens patterns
                    internal_order.append("Lens")
                else:
                    internal_order.append("Additional")  # Default fallback
        
        # Add missing components that weren't in the display
        all_components = ["Date", "Prefix", "Additional", "Camera", "Lens"]
        for component in all_components:
            if component not in internal_order:
                internal_order.append(component)
        
        self.custom_order = internal_order

    def on_theme_changed(self, theme_name):
        """Handle theme changes"""
        app = QApplication.instance()
        if theme_name == "Dark":
            # Dark theme stylesheet
            dark_style = """
            QMainWindow {
                background-color: #2b2b2b;
                color: #ffffff;
            }
            QWidget {
                background-color: #2b2b2b;
                color: #ffffff;
            }
            QLineEdit {
                background-color: #3c3c3c;
                border: 1px solid #5a5a5a;
                border-radius: 3px;
                padding: 5px;
                color: #ffffff;
            }
            QLineEdit:focus {
                border: 2px solid #0078d4;
            }
            QPushButton {
                background-color: #404040;
                border: 1px solid #5a5a5a;
                border-radius: 3px;
                padding: 8px;
                color: #ffffff;
            }
            QPushButton:hover {
                background-color: #4a4a4a;
                border: 1px solid #0078d4;
            }
            QPushButton:pressed {
                background-color: #0078d4;
            }
            QComboBox {
                background-color: #3c3c3c;
                border: 1px solid #5a5a5a;
                border-radius: 3px;
                padding: 5px;
                color: #ffffff;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid #ffffff;
            }
            QListWidget {
                background-color: #3c3c3c;
                border: 1px solid #5a5a5a;
                color: #ffffff;
            }
            QListWidget::item:selected {
                background-color: #0078d4;
            }
            QCheckBox {
                color: #ffffff;
            }
            QLabel {
                color: #ffffff;
            }
            QStatusBar {
                background-color: #404040;
                color: #ffffff;
            }
            /* Interactive Preview Widget - Dark Theme */
            InteractivePreviewWidget {
                background-color: #3c3c3c;
                border: 2px solid #5a5a5a;
                color: #ffffff;
            }
            InteractivePreviewWidget::item {
                background-color: #404040;
                border: 1px solid #6a6a6a;
                color: #ffffff;
            }
            InteractivePreviewWidget::item:selected {
                background-color: #0078d4;
                border: 2px solid #66c2ff;
            }
            InteractivePreviewWidget::item:hover {
                background-color: #4a4a4a;
                border: 1px solid #0078d4;
            }
            """
            app.setStyleSheet(dark_style)
            
            # Apply dark theme to specific widgets with custom stylesheets
            # Interactive Preview Widget
            self.interactive_preview.setStyleSheet("""
                QListWidget {
                    border: 2px solid #5a5a5a;
                    border-radius: 6px;
                    background-color: #3c3c3c;
                    padding: 8px;
                    font-size: 11px;
                    color: #ffffff;
                }
                QListWidget::item {
                    background-color: #404040;
                    border: 1px solid #6a6a6a;
                    border-radius: 2px;
                    padding: 1px 3px;
                    margin: 0px;
                    font-weight: bold;
                    text-align: center;
                    font-size: 8px;
                    color: #ffffff;
                }
                QListWidget::item:selected {
                    background-color: #0078d4;
                    border: 2px solid #66c2ff;
                }
                QListWidget::item:hover {
                    background-color: #4a4a4a;
                    border: 1px solid #0078d4;
                }
            """)
            
            # Info label under file list
            for child in self.findChildren(QLabel):
                if "Single click" in child.text():
                    child.setStyleSheet("""
                        QLabel {
                            background-color: #404040;
                            border: 2px solid #5a5a5a;
                            border-radius: 4px;
                            padding: 6px;
                            color: #cccccc;
                            font-size: 11px;
                            font-weight: normal;
                        }
                    """)
                    break
            
            # File List Dark Theme
            self.file_list.setStyleSheet("""
                QListWidget {
                    border: 2px dashed #5a5a5a;
                    border-radius: 8px;
                    background-color: #3c3c3c;
                    padding: 20px;
                    min-height: 120px;
                    color: #ffffff;
                }
                QListWidget::item {
                    padding: 4px;
                    border-bottom: 1px solid #5a5a5a;
                    background-color: #404040;
                    border-radius: 3px;
                    margin: 1px;
                    color: #ffffff;
                }
                QListWidget::item:selected {
                    background-color: #0078d4;
                    color: white;
                }
                QListWidget::item:hover {
                    background-color: #4a4a4a;
                }
            """)
        elif theme_name == "Light":
            # Light theme (default Qt)
            app.setStyleSheet("")
            
            # Restore original light theme styles for specific widgets
            # Interactive Preview Widget
            self.interactive_preview.setStyleSheet("""
                QListWidget {
                    border: 2px solid #cccccc;
                    border-radius: 6px;
                    background-color: #f9f9f9;
                    padding: 8px;
                    font-size: 11px;
                }
                QListWidget::item {
                    background-color: #e6f3ff;
                    border: 1px solid #b3d9ff;
                    border-radius: 2px;
                    padding: 1px 3px;
                    margin: 0px;
                    font-weight: bold;
                    text-align: center;
                    font-size: 8px;
                }
                QListWidget::item:selected {
                    background-color: #cce7ff;
                    border: 2px solid #0078d4;
                }
                QListWidget::item:hover {
                    background-color: #d9ecff;
                    border: 1px solid #66c2ff;
                }
            """)
            
            # Info label under file list
            for child in self.findChildren(QLabel):
                if "Single click" in child.text():
                    child.setStyleSheet("""
                        QLabel {
                            background-color: #f8f9fa;
                            border: 2px solid #dee2e6;
                            border-radius: 4px;
                            padding: 6px;
                            color: #6c757d;
                            font-size: 11px;
                            font-weight: normal;
                        }
                    """)
                    break
            
            # File List Light Theme
            self.file_list.setStyleSheet("""
                QListWidget {
                    border: 2px dashed #cccccc;
                    border-radius: 8px;
                    background-color: #fafafa;
                    padding: 20px;
                    min-height: 120px;
                }
                QListWidget::item {
                    padding: 4px;
                    border-bottom: 1px solid #eeeeee;
                    background-color: white;
                    border-radius: 3px;
                    margin: 1px;
                }
                QListWidget::item:selected {
                    background-color: #0078d4;
                    color: white;
                }
                QListWidget::item:hover {
                    background-color: #f0f6ff;
                }
            """)
        else:  # System
            # Let Qt detect system theme
            app.setStyleSheet("")
            
            # Restore original styles for specific widgets
            # Interactive Preview Widget
            self.interactive_preview.setStyleSheet("""
                QListWidget {
                    border: 2px solid #cccccc;
                    border-radius: 6px;
                    background-color: #f9f9f9;
                    padding: 8px;
                    font-size: 11px;
                }
                QListWidget::item {
                    background-color: #e6f3ff;
                    border: 1px solid #b3d9ff;
                    border-radius: 2px;
                    padding: 1px 3px;
                    margin: 0px;
                    font-weight: bold;
                    text-align: center;
                    font-size: 8px;
                }
                QListWidget::item:selected {
                    background-color: #cce7ff;
                    border: 2px solid #0078d4;
                }
                QListWidget::item:hover {
                    background-color: #d9ecff;
                    border: 1px solid #66c2ff;
                }
            """)
            
            # Info label under file list
            for child in self.findChildren(QLabel):
                if "Single click" in child.text():
                    child.setStyleSheet("""
                        QLabel {
                            background-color: #f8f9fa;
                            border: 2px solid #dee2e6;
                            border-radius: 4px;
                            padding: 6px;
                            color: #6c757d;
                            font-size: 11px;
                            font-weight: normal;
                        }
                    """)
                    break
            
            # File List System Theme
            self.file_list.setStyleSheet("""
                QListWidget {
                    border: 2px dashed #cccccc;
                    border-radius: 8px;
                    background-color: #fafafa;
                    padding: 20px;
                    min-height: 120px;
                }
                QListWidget::item {
                    padding: 4px;
                    border-bottom: 1px solid #eeeeee;
                    background-color: white;
                    border-radius: 3px;
                    margin: 1px;
                }
                QListWidget::item:selected {
                    background-color: #0078d4;
                    color: white;
                }
                QListWidget::item:hover {
                    background-color: #f0f6ff;
                }
            """)

    def on_devider_changed(self):
        """Handle devider combo box changes"""
        devider = self.devider_combo.currentText()
        self.interactive_preview.set_separator(devider)

    def validate_and_update_preview(self):
        # Get current text
        camera_text = self.camera_prefix_entry.text()
        additional_text = self.additional_entry.text()
        
        # Validate and sanitize camera prefix
        if camera_text:
            sanitized_camera = sanitize_filename(camera_text)
            if sanitized_camera != camera_text:
                # Update field with sanitized version
                cursor_pos = self.camera_prefix_entry.cursorPosition()
                self.camera_prefix_entry.setText(sanitized_camera)
                self.camera_prefix_entry.setCursorPosition(min(cursor_pos, len(sanitized_camera)))
        
        # Validate and sanitize additional field
        if additional_text:
            sanitized_additional = sanitize_filename(additional_text)
            if sanitized_additional != additional_text:
                # Update field with sanitized version
                cursor_pos = self.additional_entry.cursorPosition()
                self.additional_entry.setText(sanitized_additional)
                self.additional_entry.setCursorPosition(min(cursor_pos, len(sanitized_additional)))
        
        # Update preview
        self.update_preview()

    def update_file_list_placeholder(self):
        """Update the file list with placeholder text when empty"""
        if self.file_list.count() == 0:
            # Add placeholder item when list is empty
            placeholder = QListWidgetItem("📁 Drag and drop folders/files here or use buttons below")
            placeholder.setFlags(Qt.ItemFlag.NoItemFlags)  # Not selectable
            placeholder.setForeground(Qt.GlobalColor.gray)
            placeholder.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            
            font = QFont()
            font.setPointSize(12)
            # font.setItalic(True)  # Make the whole text italic (simplest solution)
            placeholder.setFont(font)
            self.file_list.addItem(placeholder)
            self.file_list.setStyleSheet(self.file_list.styleSheet() + """
                QListWidget::item:first {
                    border: none;
                    background-color: transparent;
                    text-align: center;
                    padding: 40px;
                }
            """)

    def update_camera_lens_labels(self):
        """Update the camera and lens model labels based on the first selected file"""
        if not self.files or not self.exif_method:
            self.camera_model_label.setText("(no files selected)")
            self.lens_model_label.setText("(no files selected)")
            return
        
        # Use first image file for detection
        first_image = next((f for f in self.files if is_image_file(f)), None)
        if not first_image:
            self.camera_model_label.setText("(no image files)")
            self.lens_model_label.setText("(no image files)")
            return
        
        try:
            date, camera, lens = extract_exif_fields(first_image, self.exif_method, self.exiftool_path)
            
            if camera:
                self.camera_model_label.setText(f"({camera})")
                self.camera_model_label.setStyleSheet("color: green; font-style: italic;")
            else:
                self.camera_model_label.setText("(not detected)")
                self.camera_model_label.setStyleSheet("color: orange; font-style: italic;")
            
            if lens:
                self.lens_model_label.setText(f"({lens})")
                self.lens_model_label.setStyleSheet("color: green; font-style: italic;")
            else:
                self.lens_model_label.setText("(not detected)")
                self.lens_model_label.setStyleSheet("color: orange; font-style: italic;")
                
        except Exception as e:
            self.camera_model_label.setText("(error)")
            self.lens_model_label.setText("(error)")
            self.camera_model_label.setStyleSheet("color: red; font-style: italic;")
            self.lens_model_label.setStyleSheet("color: red; font-style: italic;")

    def show_image_info(self, item):
        """Show image information when a file is clicked (single click)"""
        file_path = item.text()
        if not is_image_file(file_path) or not self.exif_method:
            return
        
        try:
            # Extract image number
            image_number = extract_image_number(file_path, self.exif_method, self.exiftool_path)
            
            if image_number:
                # Update status bar with image number
                self.status.showMessage(f"Image Number/Shutter Count: {image_number}", 5000)  # Show for 5 seconds
            else:
                self.status.showMessage("Image number not found in EXIF data", 3000)
                
        except Exception as e:
            self.status.showMessage(f"Error reading image number: {e}", 3000)

    def update_exif_status(self):
        if self.exif_method == "exiftool":
            self.exif_status_label.setText(f"EXIF method: exiftool v13.32 (recommended) ✓")
            self.exif_status_label.setStyleSheet("color: green;")
            self.exif_status_label.setToolTip(f"Using ExifTool at: {self.exiftool_path}")
        elif self.exif_method == "pillow":
            self.exif_status_label.setText("EXIF method: Pillow ⚠")
            self.exif_status_label.setStyleSheet("color: orange;")
            info_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxInformation).pixmap(16, 16)
            self.exif_status_label.setPixmap(info_icon)
            self.exif_status_label.setToolTip("To make use of the great exiftool, go to https://exiftool.org to download it, place exiftool.exe in your program folder or PATH, then restart. RAW support is limited with Pillow.")
        else:
            self.exif_status_label.setText("No EXIF support available ❌")
            self.exif_status_label.setStyleSheet("color: red;")
            info_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxInformation).pixmap(16, 16)
            self.exif_status_label.setPixmap(info_icon)
            self.exif_status_label.setToolTip("Please install exiftool (https://exiftool.org) or Pillow for EXIF support.")

    def update_preview(self):
        """Update the interactive preview widget with current settings"""
        # Get current settings
        camera_prefix = self.camera_prefix_entry.text().strip()
        additional = self.additional_entry.text().strip()
        use_camera = self.checkbox_camera.isChecked()
        use_lens = self.checkbox_lens.isChecked()
        use_date = self.checkbox_date.isChecked()
        date_format = self.date_format_combo.currentText()
        devider = self.devider_combo.currentText()
        
        # Choose first JPG file, else first file, else dummy
        preview_file = next((f for f in self.files if os.path.splitext(f)[1].lower() in [".jpg", ".jpeg"]), None)
        if not preview_file and self.files:
            preview_file = self.files[0]
        if not preview_file:
            preview_file = "20250725_DSC0001.ARW"

        date_taken = None
        camera_model = None
        lens_model = None
        
        if not self.exif_method:
            # No EXIF support - use fallback values
            date_taken = "20250725"
            camera_model = "A7R3" if use_camera else None
            lens_model = "FE24-70" if use_lens else None
        else:
            # EXIF cache: only extract if file changed
            cache_key = (preview_file, self.exif_method, self.exiftool_path)
            if os.path.exists(preview_file):
                if self._preview_exif_file != cache_key:
                    try:
                        exif_data = extract_exif_fields(preview_file, self.exif_method, self.exiftool_path)
                        self._preview_exif_cache = {
                            'date': exif_data[0],
                            'camera': exif_data[1],
                            'lens': exif_data[2],
                        }
                        self._preview_exif_file = cache_key
                    except Exception as e:
                        # Fallback on error
                        self._preview_exif_cache = {'date': None, 'camera': None, 'lens': None}
                
                date_taken = self._preview_exif_cache.get('date')
                camera_model = self._preview_exif_cache.get('camera')
                lens_model = self._preview_exif_cache.get('lens')
            
            # Fallback date extraction
            if not date_taken:
                m = re.search(r'(20\d{2})(\d{2})(\d{2})', os.path.basename(preview_file))
                if m:
                    date_taken = f"{m.group(1)}{m.group(2)}{m.group(3)}"
            
            if not date_taken:
                if os.path.exists(preview_file):
                    mtime = os.path.getmtime(preview_file)
                    dt = datetime.datetime.fromtimestamp(mtime)
                    date_taken = dt.strftime('%Y%m%d')
                else:
                    date_taken = "20250725"
            
            # Use fallback values for preview if not detected
            if use_camera and not camera_model:
                camera_model = "A7R3"
            if use_lens and not lens_model:
                lens_model = "FE24-70"
        
        # Format date for display using the selected format
        if date_taken and use_date:
            year = date_taken[:4]
            month = date_taken[4:6]
            day = date_taken[6:8]
            
            if date_format == "YYYY-MM-DD":
                formatted_date = f"{year}-{month}-{day}"
            elif date_format == "YYYY_MM_DD":
                formatted_date = f"{year}_{month}_{day}"
            elif date_format == "DD-MM-YYYY":
                formatted_date = f"{day}-{month}-{year}"
            elif date_format == "DD_MM_YYYY":
                formatted_date = f"{day}_{month}_{year}"
            elif date_format == "YYYYMMDD":
                formatted_date = f"{year}{month}{day}"
            elif date_format == "MM-DD-YYYY":
                formatted_date = f"{month}-{day}-{year}"
            elif date_format == "MM_DD_YYYY":
                formatted_date = f"{month}_{day}_{year}"
            else:
                formatted_date = f"{year}-{month}-{day}"  # Default fallback
        else:
            formatted_date = None
        
        # Build component list for display - only include active components
        display_components = []
        component_mapping = {
            "Date": formatted_date if use_date else None,  # Only if date checkbox is checked
            "Prefix": camera_prefix if camera_prefix else None,  # Only if text entered
            "Additional": additional if additional else None,  # Only if text entered
            "Camera": camera_model if (use_camera and camera_model) else None,  # Only if checkbox checked AND value exists
            "Lens": lens_model if (use_lens and lens_model) else None  # Only if checkbox checked AND value exists
        }
        
        # Add components in current order, but only if they have values and are active
        for component_name in self.custom_order:
            value = component_mapping.get(component_name)
            if value:  # Only add non-empty and active components
                display_components.append(value)
        
        # Update the interactive preview
        self.interactive_preview.set_separator(devider)
        self.interactive_preview.set_components(display_components, "001")

    def eventFilter(self, obj, event):
        if obj == self.file_list and event.type() == event.Type.ToolTip:
            item = self.file_list.itemAt(event.pos())
            if item:
                QToolTip.showText(event.globalPos(), 
                    "💡 Single click: Quick image info in status bar\n🔍 Double click: Full EXIF data dialog", 
                    self.file_list)
                return True
        return super().eventFilter(obj, event)

    def show_exif_info(self, file):
        if not self.exif_method:
            self.show_exif_dialog(file, "No EXIF support available.")
            return
        try:
            if self.exif_method == "exiftool":
                if self.exiftool_path:
                    with exiftool.ExifToolHelper(executable=self.exiftool_path) as et:
                        meta = et.get_metadata([file])[0]
                else:
                    with exiftool.ExifToolHelper() as et:
                        meta = et.get_metadata([file])[0]
                if not meta:
                    self.show_exif_dialog(file, "No EXIF data found.")
                    return
                info = []
                for k, v in meta.items():
                    info.append(f"{k}: {v}")
                info_str = "\n".join(info)
                self.show_exif_dialog(file, info_str)
            elif self.exif_method == "pillow":
                image = Image.open(file)
                exif_data = image._getexif()
                if not exif_data:
                    self.show_exif_dialog(file, "No EXIF data found.")
                    return
                info = []
                for tag, value in exif_data.items():
                    decoded_tag = TAGS.get(tag, tag)
                    info.append(f"{decoded_tag}: {value}")
                info_str = "\n".join(info)
                self.show_exif_dialog(file, info_str)
        except Exception as e:
            self.show_exif_dialog(file, f"Error reading EXIF: {e}")

    def show_exif_dialog(self, file, info_str):
        dialog = QDialog(self)
        dialog.setWindowTitle(f"EXIF Info: {os.path.basename(file)}")
        layout = QVBoxLayout(dialog)
        text_edit = QPlainTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setPlainText(info_str)
        layout.addWidget(text_edit)
        dialog.resize(500, 400)
        dialog.exec()

    def add_files_to_list(self, files):
        # Clear existing files when adding new ones
        if files and self.files:
            self.clear_file_list()
        
        # Remove placeholder if present
        if self.file_list.count() == 1:
            first_item = self.file_list.item(0)
            if first_item and first_item.flags() == Qt.ItemFlag.NoItemFlags:
                self.file_list.clear()
        
        # Validate and add files
        added_count = 0
        inaccessible_files = []
        
        for file in files:
            if file not in self.files:
                # Check if file is accessible
                if not check_file_access(file):
                    inaccessible_files.append(os.path.basename(file))
                    continue
                
                self.files.append(file)
                self.file_list.addItem(file)
                added_count += 1
        
        # Show warning for inaccessible files
        if inaccessible_files:
            QMessageBox.warning(
                self,
                "File Access Warning",
                f"The following files could not be accessed (locked/permission denied):\n\n" +
                "\n".join(inaccessible_files[:10]) +  # Show max 10 files
                (f"\n... and {len(inaccessible_files) - 10} more" if len(inaccessible_files) > 10 else "")
            )
        
        # Update status
        if added_count > 0:
            self.status.showMessage(f"Added {added_count} files", 3000)
        
        # Update preview and camera/lens labels when files are added
        self.update_preview()
        self.update_camera_lens_labels()

    def clear_file_list(self):
        """Clear the file list and reset the GUI"""
        self.files.clear()
        self.file_list.clear()
        self._preview_exif_cache = {}
        self._preview_exif_file = None
        self.update_file_list_placeholder()  # Add placeholder back
        self.update_preview()
        self.update_camera_lens_labels()

    def show_selected_exif(self, item):
        file = item.text()
        if is_image_file(file):
            self.show_exif_info(file)

    def show_camera_prefix_info(self):
        """Show detailed info about camera prefix when info icon is clicked"""
        info_text = """Camera Prefix Information

The Camera Prefix is a short code that identifies your camera model in the filename.

Examples:
• A7R3 (for Sony Alpha 7R III)
• D850 (for Nikon D850) 
• R5 (for Canon EOS R5)
• GFX100S (for Fujifilm GFX 100S)

Benefits:
• Quickly identify which camera took the photo
• Useful when using multiple cameras
• Helps organize photos by equipment

This field is optional - leave empty if you don't want camera info in filenames.

The camera model can also be automatically detected from EXIF data if you enable the "Include camera model" checkbox below."""
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Camera Prefix Help")
        layout = QVBoxLayout(dialog)
        
        text_edit = QPlainTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setPlainText(info_text)
        text_edit.setFont(QFont("Arial", 10))
        layout.addWidget(text_edit)
        
        close_button = QPushButton("Close")
        close_button.clicked.connect(dialog.close)
        layout.addWidget(close_button)
        
        dialog.resize(500, 400)
        dialog.exec()

    def show_additional_info(self):
        """Show detailed info about additional field when info icon is clicked"""
        info_text = """Additional Information Field

This field allows you to add extra context or information to your filenames.

Examples:
• vacation (for vacation photos)
• wedding (for wedding photography)
• portrait (for portrait sessions)
• landscape (for landscape photography)
• macro (for macro photography)
• studio (for studio work)
• event-name (for specific events)

Benefits:
• Add context to your photos
• Organize by project or theme
• Make files easier to find later

This field is optional - leave empty if you don't need additional information in filenames.

The text will be included in the filename according to your chosen order in the Interactive Preview below."""
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Additional Field Help")
        layout = QVBoxLayout(dialog)
        
        text_edit = QPlainTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setPlainText(info_text)
        text_edit.setFont(QFont("Arial", 10))
        layout.addWidget(text_edit)
        
        close_button = QPushButton("Close")
        close_button.clicked.connect(dialog.close)
        layout.addWidget(close_button)
        
        dialog.resize(500, 400)
        dialog.exec()

    def show_devider_info(self):
        """Show detailed info about separators when info icon is clicked"""
        info_text = """Separator (Devider) Information

Separators are characters used to separate different parts of your filename.

Available Options:
• None: No separator (components joined directly)
  Example: 2025-01-15A7R3vacation001.jpg

• _ (Underscore): Uses underscore as separator
  Example: 2025-01-15_A7R3_vacation_001.jpg

• - (Dash/Hyphen): Uses dash as separator  
  Example: 2025-01-15-A7R3-vacation-001.jpg

Recommendations:
• Dash (-): Most readable, works well with most systems
• Underscore (_): Good compatibility, slightly less readable
• None: Most compact but harder to read

Note: Some characters like spaces, slashes, or special symbols are not allowed in filenames and will be automatically replaced with underscores for safety."""
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Separator Help")
        layout = QVBoxLayout(dialog)
        
        text_edit = QPlainTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setPlainText(info_text)
        text_edit.setFont(QFont("Arial", 10))
        layout.addWidget(text_edit)
        
        close_button = QPushButton("Close")
        close_button.clicked.connect(dialog.close)
        layout.addWidget(close_button)
        
        dialog.resize(500, 350)
        dialog.exec()

    def show_preview_info(self):
        """Show detailed info about interactive preview when info icon is clicked"""
        info_text = """Interactive Preview Help

The Interactive Preview shows how your filenames will look and allows you to customize the order of components.

Features:
• Drag & Drop: Click and drag any blue component to reorder them
• Live Preview: See filename changes in real-time
• Sequential Number: Always appears at the end (cannot be moved)

How to Use:
1. Click and hold any blue component (Date, Prefix, Additional, etc.)
2. Drag it to a new position
3. Release to place it in the new order
4. The preview updates immediately

Components Shown:
• Date: Based on EXIF or file date
• Prefix: Your custom camera code
• Additional: Extra information you entered
• Camera: Detected camera model (if enabled)
• Lens: Detected lens model (if enabled)
• Number: Sequential number (always last)

Only active components with values are shown in the preview.

The yellow box shows the sequential number which always stays at the end."""
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Interactive Preview Help")
        layout = QVBoxLayout(dialog)
        
        text_edit = QPlainTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setPlainText(info_text)
        text_edit.setFont(QFont("Arial", 10))
        layout.addWidget(text_edit)
        
        close_button = QPushButton("Close")
        close_button.clicked.connect(dialog.close)
        layout.addWidget(close_button)
        
        dialog.resize(550, 450)
        dialog.exec()

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            files = []
            total_dirs = sum(1 for url in event.mimeData().urls() if os.path.isdir(url.toLocalFile()))
            
            if total_dirs > 0:
                self.status.showMessage("Scanning dropped folders for images...")
                QApplication.processEvents()  # Update UI
            
            for url in event.mimeData().urls():
                path = url.toLocalFile()
                if os.path.isdir(path):
                    # Recursively scan subdirectories
                    dir_files = scan_directory_recursive(path)
                    files.extend(dir_files)
                elif is_image_file(path):
                    files.append(path)
            
            if files:
                if total_dirs > 0:
                    self.status.showMessage(f"Found {len(files)} images in dropped folder(s)", 3000)
                self.add_files_to_list(files)
            elif total_dirs > 0:
                self.status.showMessage("No images found in dropped folder(s)", 3000)

    def select_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Select Files", "", "Image Files (*.jpg *.jpeg *.png *.arw *.cr2 *.nef *.dng *.tif *.tiff *.bmp *.gif)")
        if files:
            self.add_files_to_list(files)

    def select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder:
            # Show progress while scanning
            self.status.showMessage("Scanning folder and subfolders for images...")
            QApplication.processEvents()  # Update UI
            
            # Recursively scan all subdirectories
            files = scan_directory_recursive(folder)
            
            if files:
                self.status.showMessage(f"Found {len(files)} images in folder hierarchy", 3000)
                self.add_files_to_list(files)
            else:
                self.status.showMessage("No image files found in folder hierarchy", 3000)
                QMessageBox.information(
                    self, 
                    "No Images Found", 
                    f"No image files were found in:\n{folder}\n\nSupported formats: JPG, PNG, RAW files (CR2, NEF, ARW, etc.)"
                )

    def rename_files_action(self):
        if not self.files:
            QMessageBox.warning(self, "Warning", "No files selected for renaming.")
            return
        camera_prefix = self.camera_prefix_entry.text().strip()
        additional = self.additional_entry.text().strip()
        use_camera = self.checkbox_camera.isChecked()
        use_lens = self.checkbox_lens.isChecked()
        use_date = self.checkbox_date.isChecked()
        date_format = self.date_format_combo.currentText()
        devider = self.devider_combo.currentText()
        non_images = [f for f in self.files if not is_image_file(f)]
        if non_images:
            reply = QMessageBox.question(
                self,
                "Non-image files found",
                "Some selected files are not images. Continue renaming?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                return
        image_files = [f for f in self.files if is_image_file(f)]
        if not image_files:
            QMessageBox.warning(self, "Warning", "No image files found for renaming.")
            return
        
        # Disable UI during processing
        self.rename_button.setEnabled(False)
        self.rename_button.setText("⏳ Processing...")
        self.select_files_menu_button.setEnabled(False)
        self.select_folder_menu_button.setEnabled(False)
        self.clear_files_menu_button.setEnabled(False)
        
        # Start worker thread for background processing
        self.worker = RenameWorkerThread(
            image_files, camera_prefix, additional, use_camera, use_lens, 
            self.exif_method, devider, self.exiftool_path, self.custom_order,
            date_format, use_date
        )
        self.worker.progress_update.connect(self.update_status)
        self.worker.finished.connect(self.on_rename_finished)
        self.worker.error.connect(self.on_rename_error)
        self.worker.start()
    
    def update_status(self, message):
        """Update status bar with progress message"""
        self.status.showMessage(message)
        QApplication.processEvents()  # Update UI
    
    def on_rename_finished(self, renamed_files, errors):
        """Handle completion of rename operation"""
        # Update the file list with the new file names
        original_non_images = [f for f in self.files if not is_image_file(f)]
        
        # Clear and rebuild the file list
        self.files.clear()
        self.file_list.clear()
        
        # Add renamed image files
        for renamed_file in renamed_files:
            self.files.append(renamed_file)
            self.file_list.addItem(renamed_file)
        
        # Add back any non-image files (they weren't renamed)
        for non_image in original_non_images:
            self.files.append(non_image)
            self.file_list.addItem(non_image)
        
        # Show results
        if errors:
            # Show detailed error report
            error_dialog = QDialog(self)
            error_dialog.setWindowTitle("Rename Results")
            error_layout = QVBoxLayout(error_dialog)
            
            success_label = QLabel(f"Successfully renamed: {len(renamed_files)} files")
            success_label.setStyleSheet("color: green; font-weight: bold;")
            error_layout.addWidget(success_label)
            
            if errors:
                error_label = QLabel(f"Errors encountered: {len(errors)}")
                error_label.setStyleSheet("color: red; font-weight: bold;")
                error_layout.addWidget(error_label)
                
                error_text = QPlainTextEdit()
                error_text.setReadOnly(True)
                error_text.setPlainText("\n".join(errors))
                error_layout.addWidget(error_text)
            
            close_button = QPushButton("Close")
            close_button.clicked.connect(error_dialog.accept)
            error_layout.addWidget(close_button)
            
            error_dialog.resize(500, 300)
            error_dialog.exec()
        else:
            QMessageBox.information(self, "Success", f"All files renamed successfully!\n{len(renamed_files)} files processed.")
        
        # Update preview and status
        self.update_preview()
        self.status.showMessage(f"Completed: {len(renamed_files)} files renamed", 5000)
        
        # Re-enable UI
        self.rename_button.setEnabled(True)
        self.rename_button.setText("🚀 Rename Files")
        self.select_files_menu_button.setEnabled(True)
        self.select_folder_menu_button.setEnabled(True)
        self.clear_files_menu_button.setEnabled(True)
    
    def on_rename_error(self, error_message):
        """Handle critical error during rename operation"""
        QMessageBox.critical(self, "Critical Error", f"Unexpected error during renaming:\n{error_message}")
        self.status.showMessage("Rename operation failed", 3000)
        
        # Re-enable UI
        self.rename_button.setEnabled(True)
        self.rename_button.setText("🚀 Rename Files")
        self.select_files_menu_button.setEnabled(True)
        self.select_folder_menu_button.setEnabled(True)
        self.clear_files_menu_button.setEnabled(True)

if __name__ == "__main__":
    app = QApplication([])
    window = FileRenamerApp()
    window.show()
    app.exec()