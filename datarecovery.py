import os
import re
import shutil
from tqdm import tqdm  # Fortschrittsbalken


# Konfiguration
ROOT_DIR = r'F:\Backup'
ZIEL_DIR = r'F:\test'


PATTERNS = [
    (
        # 1: NH2/COOH, 2: 2mT/8mT/..., 3: Zeitangabe, 4: 1000fps, 5: Nummer
        re.compile(r'^(NH2|COOH)_DestH2O_PMMA700nm_(\d+mT)_(\w+)_1000fps_(\d+)\.bmp$', re.IGNORECASE),
        lambda m: f"{m.group(1)}_DestH2O_PMMA700nm_{m.group(2)}_{m.group(3)}_1000fps"
    ),
    (
        re.compile(r'^(NH2|COOH)_DestH2O_PMMA700nm_(\d+mT)_(\d+ms)_(\w*)\.bmp$', re.IGNORECASE),
        lambda m: f"{m.group(1)}_DestH2O_PMMA700nm_{m.group(2)}_{m.group(3)}"
    ),
    # Weitere Patterns und Ordnerfunktionen hier ergänzen
]
def match_any_pattern(fname):
    """
    Gibt (Match-Objekt, Ordnerbau-Funktion) zurück, wenn fname zu einem Pattern passt, sonst (None, None).
    """
    for pattern, ordner_func in PATTERNS:
        match = pattern.match(fname)
        if match:
            return match, ordner_func
    return None, None

def collect_files(root_dir):
    files = []
    for dirpath, _, filenames in os.walk(root_dir):
        for fname in filenames:
            match, _ = match_any_pattern(fname)
            if match:
                files.append((dirpath, fname))
    return files

def move_file(src, dst):
    try:
        shutil.move(src, dst)
    except shutil.Error:
        pass  # Datei existiert schon am Ziel

def sortiere_und_verschiebe_dateien(files, ziel_dir):
    for dirpath, fname in tqdm(files, desc="Dateien werden verschoben"):
        match, ordner_func = match_any_pattern(fname)
        if match:
            ordnername = ordner_func(match)
            zielbasis = os.path.join(ziel_dir, ordnername)
            os.makedirs(zielbasis, exist_ok=True)

            pfad = os.path.join(dirpath, fname)
            zielpfad = os.path.join(zielbasis, fname)

            if os.path.exists(zielpfad):
                dublikate_ordner = os.path.join(zielbasis, "dublikate")
                os.makedirs(dublikate_ordner, exist_ok=True)
                zielpfad = os.path.join(dublikate_ordner, fname)

            move_file(pfad, zielpfad)

def main():
    print("Sammle alle passenden Dateien...")
    files = collect_files(ROOT_DIR)
    print(f"{len(files)} Dateien gefunden. Starte das Verschieben...")
    sortiere_und_verschiebe_dateien(files, ZIEL_DIR)
    print("Fertig! Dateien wurden verschoben. Bei Duplikaten wurde ein Unterordner 'dublikate' angelegt.")

if __name__ == "__main__":
    main()