import os
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QWidget, QLabel, QLineEdit, QPushButton, QListWidget, QFileDialog, QMessageBox, QCheckBox
)
from PyQt6.QtCore import Qt
from PIL import Image
from PIL.ExifTags import TAGS

IMAGE_EXTENSIONS = [
    '.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.gif',
    '.cr2', '.nef', '.arw', '.orf', '.rw2', '.dng', '.raw', '.sr2', '.pef', '.raf', '.3fr', '.erf', '.kdc', '.mos', '.nrw', '.srw', '.x3f'
]

def is_image_file(filename):
    return os.path.splitext(filename)[1].lower() in IMAGE_EXTENSIONS

def extract_date_taken(image_path):
    try:
        image = Image.open(image_path)
        exif_data = image._getexif()
        if exif_data:
            for tag, value in exif_data.items():
                decoded_tag = TAGS.get(tag, tag)
                if decoded_tag == "DateTimeOriginal":
                    return value.split(" ")[0].replace(":", "")
        return None
    except Exception as e:
        print(f"Error extracting date: {e}")
        return None

def extract_camera_model(image_path):
    try:
        image = Image.open(image_path)
        exif_data = image._getexif()
        if exif_data:
            for tag, value in exif_data.items():
                decoded_tag = TAGS.get(tag, tag)
                if decoded_tag == "Model":
                    return str(value).replace(" ", "-")
        return None
    except Exception:
        return None

def extract_lens_model(image_path):
    try:
        image = Image.open(image_path)
        exif_data = image._getexif()
        if exif_data:
            for tag, value in exif_data.items():
                decoded_tag = TAGS.get(tag, tag)
                if decoded_tag == "LensModel":
                    return str(value).replace(" ", "-")
        return None
    except Exception:
        return None

def rename_files(files, camera_prefix, additional, use_camera, use_lens):
    # Gruppiere nach Basename (ohne Endung), damit gleiche Bilder mit verschiedenen Endungen gleich behandelt werden
    from collections import defaultdict
    import re
    grouped = defaultdict(list)
    for file in files:
        base = os.path.splitext(os.path.basename(file))[0]
        grouped[base].append(file)

    renamed_files = []
    date_counter = {}
    for group_files in grouped.values():
        # Finde das Bild mit EXIF-Datum, falls möglich
        date_taken = None
        camera_model = None
        lens_model = None
        for file in group_files:
            if use_camera and not camera_model:
                camera_model = extract_camera_model(file)
            if use_lens and not lens_model:
                lens_model = extract_lens_model(file)
            if not date_taken:
                date_taken = extract_date_taken(file)
            if date_taken and (not use_camera or camera_model) and (not use_lens or lens_model):
                break
        if not date_taken:
            # Fallback: Dateiname nach Muster JJJJMMTT extrahieren
            for file in group_files:
                m = re.search(r'(20\d{2})(\d{2})(\d{2})', os.path.basename(file))
                if m:
                    date_taken = f"{m.group(1)}{m.group(2)}{m.group(3)}"
                    break
        if not date_taken:
            # Fallback: Änderungsdatum der Datei
            file = group_files[0]
            mtime = os.path.getmtime(file)
            import datetime
            dt = datetime.datetime.fromtimestamp(mtime)
            date_taken = dt.strftime('%Y%m%d')
        # Zähle fortlaufende Nummer pro Datum
        if date_taken not in date_counter:
            date_counter[date_taken] = 1
        else:
            date_counter[date_taken] += 1
        num = date_counter[date_taken]
        # Format: Jahr_Monat_Tag_Fortlaufendenummer_Kamerakürzel
        year = date_taken[:4]
        month = date_taken[4:6]
        day = date_taken[6:8]
        for file in group_files:
            ext = os.path.splitext(file)[1]
            name_parts = [year, month, day, f"{num:02d}"]
            if camera_prefix:
                name_parts.append(camera_prefix)
            if additional:
                name_parts.append(additional)
            if use_camera and camera_model:
                name_parts.append(camera_model)
            if use_lens and lens_model:
                name_parts.append(lens_model)
            new_name = "_".join(name_parts) + ext
            new_path = os.path.join(os.path.dirname(file), new_name)
            os.rename(file, new_path)
            renamed_files.append(new_path)
    return renamed_files

class FileRenamerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("File Renamer")
        self.setGeometry(100, 100, 600, 400)

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        self.layout = QVBoxLayout(self.central_widget)

        self.label = QLabel("Kamera Präfix:")
        self.layout.addWidget(self.label)
        self.camera_prefix_entry = QLineEdit()
        self.layout.addWidget(self.camera_prefix_entry)

        self.label_additional = QLabel("Weitere:")
        self.layout.addWidget(self.label_additional)
        self.additional_entry = QLineEdit()
        self.layout.addWidget(self.additional_entry)

        self.checkbox_camera = QCheckBox("Kameramodell in Dateiname")
        self.layout.addWidget(self.checkbox_camera)
        self.checkbox_lens = QCheckBox("Objektiv in Dateiname")
        self.layout.addWidget(self.checkbox_lens)

        self.file_list = QListWidget()
        self.layout.addWidget(self.file_list)
        self.file_list.itemDoubleClicked.connect(self.show_selected_exif)

        self.select_files_button = QPushButton("Select Files")
        self.select_files_button.clicked.connect(self.select_files)
        self.layout.addWidget(self.select_files_button)

        self.select_folder_button = QPushButton("Select Folder")
        self.select_folder_button.clicked.connect(self.select_folder)
        self.layout.addWidget(self.select_folder_button)

        self.setAcceptDrops(True)

        self.rename_button = QPushButton("Rename")
        self.rename_button.clicked.connect(self.rename_files_action)
        self.layout.addWidget(self.rename_button)

        self.files = []

    def show_exif_info(self, file):
        try:
            image = Image.open(file)
            exif_data = image._getexif()
            if not exif_data:
                QMessageBox.information(self, "EXIF Info", f"Keine EXIF-Daten gefunden für {file}.")
                return
            info = []
            for tag, value in exif_data.items():
                decoded_tag = TAGS.get(tag, tag)
                info.append(f"{decoded_tag}: {value}")
            info_str = "\n".join(info)
            QMessageBox.information(self, "EXIF Info", f"{file}\n\n{info_str}")
        except Exception as e:
            QMessageBox.information(self, "EXIF Info", f"{file}\nFehler beim Auslesen: {e}")

    def add_files_to_list(self, files):
        # Verhindere doppelte Einträge
        for file in files:
            if file not in self.files:
                self.files.append(file)
                self.file_list.addItem(file)

        # Entferne EXIF-Anzeige beim Einladen

    def show_selected_exif(self, item):
        file = item.text()
        if is_image_file(file):
            self.show_exif_info(file)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            files = []
            for url in event.mimeData().urls():
                path = url.toLocalFile()
                if os.path.isdir(path):
                    files.extend([os.path.join(path, f) for f in os.listdir(path) if is_image_file(f)])
                elif is_image_file(path):
                    files.append(path)
            self.add_files_to_list(files)

    def select_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Select Files", "", "Image Files (*.jpg *.jpeg *.png *.arw *.cr2 *.nef *.dng *.tif *.tiff *.bmp *.gif)")
        if files:
            self.add_files_to_list(files)

    def select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder:
            files = [os.path.join(folder, f) for f in os.listdir(folder) if is_image_file(f)]
            self.add_files_to_list(files)

    def rename_files_action(self):
        if not self.files:
            QMessageBox.warning(self, "Warnung", "Keine Dateien zum Umbenennen ausgewählt.")
            return
        camera_prefix = self.camera_prefix_entry.text().strip()
        additional = self.additional_entry.text().strip()
        use_camera = self.checkbox_camera.isChecked()
        use_lens = self.checkbox_lens.isChecked()
        # Kamerakürzel darf leer bleiben, keine Warnung mehr
        # Prüfe, ob alle Dateien Bilddateien sind
        non_images = [f for f in self.files if not is_image_file(f)]
        if non_images:
            reply = QMessageBox.question(
                self,
                "Nicht-Bilddateien gefunden",
                "Die eingeladenen Dateien sind keine Bilder. Weiterhin umbenennen?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                return
        # Nur Bilddateien umbenennen
        image_files = [f for f in self.files if is_image_file(f)]
        if not image_files:
            QMessageBox.warning(self, "Warnung", "Keine Bilddateien zum Umbenennen gefunden.")
            return
        try:
            rename_files(image_files, camera_prefix, additional, use_camera, use_lens)
            QMessageBox.information(self, "Fertig", "Dateien wurden umbenannt.")
            self.file_list.clear()
            self.files = []
        except Exception as e:
            QMessageBox.critical(self, "Fehler", f"Fehler beim Umbenennen: {e}")

if __name__ == "__main__":
    app = QApplication([])
    window = FileRenamerApp()
    window.show()
    app.exec()