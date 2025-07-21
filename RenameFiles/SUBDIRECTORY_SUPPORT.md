# Unterordner-Behandlung in RenameFiles

## 📁 **Neue Unterordner-Funktionalität**

Die RenameFiles-Anwendung unterstützt jetzt **vollständige rekursive Unterordner-Scans**!

### 🔄 **Was wurde verbessert:**

#### **Vorher (❌ Alt):**
- Nur Dateien im **Hauptordner** wurden erfasst
- Unterordner wurden **ignoriert**
- Manuelle Auswahl aus jedem Unterordner nötig

#### **Jetzt (✅ Neu):**
- **Rekursive Suche** in allen Unterordnern
- **Beliebige Tiefe** wird unterstützt
- **Automatische Erfassung** aller Bilder

---

## 🛠️ **Funktionsweise**

### 1. **📁 "Select Folder" Button**
```
Verhalten:
1. Ordner auswählen
2. Scanning-Nachricht: "Scanning folder and subfolders for images..."
3. Rekursive Suche in ALLEN Unterordnern
4. Ergebnis: "Found X images in folder hierarchy"
```

### 2. **🖱️ Drag & Drop von Ordnern**
```
Verhalten:
1. Ordner in die Anwendung ziehen
2. Scanning-Nachricht: "Scanning dropped folders for images..."
3. Automatische rekursive Suche
4. Ergebnis: "Found X images in dropped folder(s)"
```

### 3. **📂 Beispiel-Ordnerstruktur**
```
📁 Meine_Fotos/
├── 📷 IMG_001.jpg          ← ✅ Gefunden
├── 📷 IMG_002.CR2          ← ✅ Gefunden
├── 📄 readme.txt           ← ❌ Ignoriert (kein Bild)
├── 📁 Urlaub_2024/
│   ├── 📷 strand_01.jpg    ← ✅ Gefunden
│   ├── 📷 strand_02.ARW    ← ✅ Gefunden
│   └── 📁 Tag_1/
│       ├── 📷 morgen.NEF   ← ✅ Gefunden
│       └── 📷 abend.CR2    ← ✅ Gefunden
├── 📁 Arbeit/
│   ├── 📷 meeting.jpg      ← ✅ Gefunden
│   └── 📁 Konferenz/
│       └── 📷 event.DNG    ← ✅ Gefunden
└── 📁 Leer_Ordner/         ← ❌ Leer, ignoriert
```

**Ergebnis:** Alle 8 Bilder werden automatisch gefunden! 🎉

---

## ⚡ **Vorteile**

### **Für den Benutzer:**
- ✅ **Ein Klick** erfasst alle Bilder
- ✅ **Keine manuelle Ordner-Navigation** nötig
- ✅ **Komplexe Strukturen** automatisch verarbeitet
- ✅ **Zeitersparnis** bei großen Fotosammlungen

### **Technische Verbesserungen:**
- ✅ **os.walk()** für effiziente rekursive Suche
- ✅ **Progress-Feedback** für Benutzer
- ✅ **Error-Handling** für nicht-zugängliche Ordner
- ✅ **Speicher-effizient** auch bei vielen Dateien

---

## 🎯 **Anwendungsfälle**

### **1. Foto-Import von Kamera/SD-Karte**
```
SD-Karte/
├── DCIM/
│   ├── 100CANON/
│   │   ├── IMG_001.CR2
│   │   └── IMG_002.CR2
│   └── 101CANON/
│       ├── IMG_003.CR2
│       └── IMG_004.CR2
└── MISC/
    └── backup_001.jpg

→ Alle Bilder werden automatisch gefunden!
```

### **2. Organisierte Foto-Bibliothek**
```
Fotos/
├── 2024/
│   ├── Januar/
│   ├── Februar/
│   └── März/
├── 2023/
│   └── Dezember/
└── RAW/
    ├── Bearbeitet/
    └── Original/

→ Komplette Bibliothek mit einem Klick!
```

### **3. Projekt-Ordner**
```
Hochzeit_Mueller/
├── Zeremonie/
├── Feier/
├── Portraits/
│   ├── Braut/
│   ├── Bräutigam/
│   └── Familie/
└── Details/

→ Alle Event-Bilder automatisch erfasst!
```

---

## 🔧 **Technische Details**

### **Implementierung:**
```python
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
```

### **Unterstützte Formate:**
- **Standard:** JPG, JPEG, PNG, BMP, TIFF, GIF
- **RAW:** CR2, NEF, ARW, ORF, RW2, DNG, RAW, SR2, PEF, RAF, 3FR, ERF, KDC, MOS, NRW, SRW, X3F

### **Performance:**
- **Effizient:** Nutzt `os.walk()` für optimale Performance
- **Skalierbar:** Funktioniert mit tausenden von Dateien
- **Responsiv:** UI-Updates während des Scannens

---

## 🚀 **Verwendung**

### **Schritt-für-Schritt:**

1. **Anwendung starten:**
   ```bash
   python RenameFiles.py
   ```

2. **Ordner wählen:**
   - **Option A:** "Select Folder" Button klicken
   - **Option B:** Ordner per Drag & Drop

3. **Automatisches Scanning:**
   - Status-Bar zeigt Progress
   - Alle Unterordner werden durchsucht
   - Ergebnis wird angezeigt

4. **Normale Verarbeitung:**
   - Alle gefundenen Bilder in der Liste
   - Standard-Rename-Funktionen verwenden
   - Dateien bleiben in ursprünglichen Ordnern

### **Beispiel-Workflow:**
```
1. Ordner "Meine_Fotos" auswählen
   → "Scanning folder and subfolders for images..."

2. Scan abgeschlossen
   → "Found 247 images in folder hierarchy"

3. Rename-Parameter einstellen
   → Kamera-Prefix, Zusatzinfo, etc.

4. "Rename" klicken
   → Alle 247 Bilder werden umbenannt
   → Jede Datei bleibt in ihrem Original-Ordner
```

---

## 🎉 **Zusammenfassung**

**Unterordner werden jetzt vollständig unterstützt!**

- ✅ **Rekursive Suche** in beliebiger Tiefe
- ✅ **Automatische Erfassung** aller Bilder
- ✅ **Progress-Feedback** für den Benutzer
- ✅ **Drag & Drop** Unterstützung
- ✅ **Beibehaltung** der Ordnerstruktur beim Umbenennen

**Die Anwendung ist jetzt perfekt für:**
- 📷 Große Fotosammlungen
- 🗂️ Organisierte Bibliotheken  
- 💼 Professionelle Workflows
- 🎯 Batch-Processing ganzer Archive

**Ein Klick genügt - alle Bilder in allen Unterordnern werden gefunden! 🚀**
