import os
import re
import shutil
from tqdm import tqdm  # Fortschrittsbalken
from datetime import datetime
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from sklearn.cluster import KMeans
import numpy as np


# Konfiguration
# ROOT_DIR = r'F:\Backup'
# ZIEL_DIR = r'F:\Backup_sortiert'
# ROOT_DIR = r'F:\Backup'
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
    (
        re.compile(r'^(NH2|COOH)_DestH2O_PMMA700nm_(\d+mT)_(\d+s)_(\w*)\.bmp$', re.IGNORECASE),
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
    andere_files = []
    for dirpath, _, filenames in os.walk(root_dir):
        for fname in filenames:
            match, _ = match_any_pattern(fname)
            if match:
                files.append((dirpath, fname))
            else:
                andere_files.append((dirpath, fname))
    return files, andere_files

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
            # Prüfen, ob der Ursprungsordner jetzt leer ist und ggf. löschen
            try:
                if not os.listdir(dirpath):
                    os.rmdir(dirpath)
            except Exception as e:
                print(f"Ordner {dirpath} konnte nicht gelöscht werden: {e}")

def verschiebe_andere_dateien(andere_files, ziel_dir):
    andere_dir = os.path.join(ziel_dir, "Andere")
    os.makedirs(andere_dir, exist_ok=True)
    for dirpath, fname in tqdm(andere_files, desc="Andere Dateien werden verschoben"):
        pfad = os.path.join(dirpath, fname)
        zielpfad = os.path.join(andere_dir, fname)
        if os.path.exists(zielpfad):
            # Bei Namenskonflikt Zähler anhängen
            base, ext = os.path.splitext(fname)
            i = 1
            while os.path.exists(os.path.join(andere_dir, f"{base}_{i}{ext}")):
                i += 1
            zielpfad = os.path.join(andere_dir, f"{base}_{i}{ext}")
        move_file(pfad, zielpfad)
        # Prüfen, ob der Ursprungsordner jetzt leer ist und ggf. löschen
        try:
            if not os.listdir(dirpath):
                os.rmdir(dirpath)
        except Exception as e:
            print(f"Ordner {dirpath} konnte nicht gelöscht werden: {e}")

def finde_fraktionen(sekunden_liste, n_fraktionen=2, min_diff_sec=600):
    """
    Cluster die sekunden_liste in n_fraktionen, aber gibt nur mehrere Fraktionen zurück,
    wenn die Clusterzentren mindestens min_diff_sec auseinander liegen.
    """
    if len(sekunden_liste) < n_fraktionen:
        return [sekunden_liste]  # nicht genug Daten
    X = np.array(sekunden_liste).reshape(-1, 1)
    kmeans = KMeans(n_clusters=n_fraktionen, n_init=10, random_state=0)
    labels = kmeans.fit_predict(X)
    centers = sorted([c[0] for c in kmeans.cluster_centers_])
    # Prüfe, ob die Clusterzentren weit genug auseinander liegen
    if n_fraktionen == 2 and abs(centers[1] - centers[0]) < min_diff_sec:
        return [sekunden_liste]  # nur eine Fraktion, da zu nah beieinander
    fraktionen = []
    for i in range(n_fraktionen):
        fraktion = [sekunden_liste[j] for j in range(len(sekunden_liste)) if labels[j] == i]
        if fraktion:
            fraktionen.append(fraktion)
    return fraktionen

def plot_histogramme_fuer_dublikate_ordner(ziel_dir):
    ordnernamen = [o for o in os.listdir(ziel_dir) if os.path.isdir(os.path.join(ziel_dir, o))]
    for ordnername in tqdm(ordnernamen, desc="Histogramme werden erstellt"):
        ordnerpfad = os.path.join(ziel_dir, ordnername)
        dublikate_ordner = os.path.join(ordnerpfad, "dublikate")
        haupt_aenderungsdaten = []
        for fname in os.listdir(ordnerpfad):
            fpath = os.path.join(ordnerpfad, fname)
            if os.path.isfile(fpath):
                ts = os.path.getmtime(fpath)
                haupt_aenderungsdaten.append(datetime.fromtimestamp(ts).time())
        dublikate_aenderungsdaten = []
        if os.path.isdir(dublikate_ordner):
            for fname in os.listdir(dublikate_ordner):
                fpath = os.path.join(dublikate_ordner, fname)
                if os.path.isfile(fpath):
                    ts = os.path.getmtime(fpath)
                    dublikate_aenderungsdaten.append(datetime.fromtimestamp(ts).time())
        if haupt_aenderungsdaten or dublikate_aenderungsdaten:
            haupt_secs = [t.hour * 3600 + t.minute * 60 + t.second for t in haupt_aenderungsdaten]
            dubl_secs = [t.hour * 3600 + t.minute * 60 + t.second for t in dublikate_aenderungsdaten]
            all_secs = haupt_secs + dubl_secs
            if not all_secs:
                continue
            # --- Fraktionen finden ---
            fraktionen = finde_fraktionen(all_secs, n_fraktionen=2)
            # Anzahl der Fraktionen für den Plot-Titel
            anzahl_fraktionen = sum(1 for f in fraktionen if f)
            min_sec = min(all_secs)
            max_sec = max(all_secs)
            xlim_min = max(0, min_sec - 600)
            xlim_max = min(24 * 3600, max_sec + 600)
            xticks = list(range(xlim_min, xlim_max + 1, 60))
            xticklabels = [f"{s//3600:02d}:{(s%3600)//60:02d}" for s in xticks]
            bins = (xlim_max - xlim_min) // 60  # 1-Minuten-Bins
            plt.hist(
                haupt_secs,
                bins=bins,
                range=(xlim_min, xlim_max),
                color='tab:blue',
                alpha=0.7,
                label='Original',
                edgecolor='black'
            )
            if dubl_secs:
                plt.hist(
                    dubl_secs,
                    bins=bins,
                    range=(xlim_min, xlim_max),
                    color='tab:orange',
                    alpha=0.7,
                    label='Dublikate',
                    edgecolor='black'
                )
            plt.xticks(xticks[::10], xticklabels[::10], rotation=45)  # alle 10 Minuten ein Label
            plt.xlim(xlim_min, xlim_max)
            plt.title(f'Änderungszeit Histogramm: {ordnername} (Original & Dublikate)\nAnzahl Fraktionen: {anzahl_fraktionen}')
            plt.xlabel('Uhrzeit')
            plt.ylabel('Anzahl Dateien')
            plt.show()

def sortiere_fraktionen_mit_zwischenordner(ordnerpfad):
    dublikate_ordner = os.path.join(ordnerpfad, "dublikate")
    zwischenordner = os.path.join(ordnerpfad, "zwischenordner")
    os.makedirs(zwischenordner, exist_ok=True)

    # Alle Dateien und Änderungszeiten sammeln
    dateien = []
    for fname in os.listdir(ordnerpfad):
        fpath = os.path.join(ordnerpfad, fname)
        if os.path.isfile(fpath):
            ts = os.path.getmtime(fpath)
            dateien.append((fpath, fname, ts, "haupt"))
    if os.path.isdir(dublikate_ordner):
        for fname in os.listdir(dublikate_ordner):
            fpath = os.path.join(dublikate_ordner, fname)
            if os.path.isfile(fpath):
                ts = os.path.getmtime(fpath)
                dateien.append((fpath, fname, ts, "dublikate"))
    if not dateien:
        return

    # Fraktionen bestimmen
    sekunden_liste = [datetime.fromtimestamp(ts).hour * 3600 + datetime.fromtimestamp(ts).minute * 60 + datetime.fromtimestamp(ts).second for _, _, ts, _ in dateien]
    fraktionen = finde_fraktionen(sekunden_liste, n_fraktionen=2)
    if len(fraktionen) < 2:
        # Nur eine Fraktion gefunden: alles bleibt wie es ist, keine Sortierung nötig
        return

    idx_groß = 0 if len(fraktionen[0]) >= len(fraktionen[1]) else 1
    große_fraktion = set(fraktionen[idx_groß])
    kleine_fraktion = set(fraktionen[1-idx_groß])

    # 1. Dateien im dublikate-Ordner, die zur großen Fraktion gehören, in zwischenordner verschieben
    for fpath, fname, ts, location in dateien:
        sek = datetime.fromtimestamp(ts).hour * 3600 + datetime.fromtimestamp(ts).minute * 60 + datetime.fromtimestamp(ts).second
        if location == "dublikate" and sek in große_fraktion:
            zielpfad = os.path.join(zwischenordner, fname)
            base, ext = os.path.splitext(fname)
            count = 1
            while os.path.exists(zielpfad):
                zielpfad = os.path.join(zwischenordner, f"{base}_fr1_{count}{ext}")
                count += 1
            shutil.move(fpath, zielpfad)

    # 2. Dateien der kleinen Fraktion in dublikate-Ordner verschieben
    os.makedirs(dublikate_ordner, exist_ok=True)
    for fpath, fname, ts, location in dateien:
        sek = datetime.fromtimestamp(ts).hour * 3600 + datetime.fromtimestamp(ts).minute * 60 + datetime.fromtimestamp(ts).second
        if sek in kleine_fraktion:
            zielpfad = os.path.join(dublikate_ordner, fname)
            base, ext = os.path.splitext(fname)
            count = 1
            while os.path.exists(zielpfad):
                zielpfad = os.path.join(dublikate_ordner, f"{base}_fr2_{count}{ext}")
                count += 1
            shutil.move(fpath, zielpfad)

    # 3. Dateien aus zwischenordner zurück in Hauptordner verschieben
    for fname in os.listdir(zwischenordner):
        fpath = os.path.join(zwischenordner, fname)
        if os.path.isfile(fpath):
            zielpfad = os.path.join(ordnerpfad, fname)
            base, ext = os.path.splitext(fname)
            count = 1
            while os.path.exists(zielpfad):
                zielpfad = os.path.join(ordnerpfad, f"{base}_fr1_{count}{ext}")
                count += 1
            shutil.move(fpath, zielpfad)
    try:
        if not os.listdir(zwischenordner):
            os.rmdir(zwischenordner)
    except Exception:
        pass

# Beispielaufruf für alle Ordner:
def sortiere_alle_ordner_nach_fraktion_mit_zwischenordner(ziel_dir):
    ordnernamen = [o for o in os.listdir(ziel_dir) if os.path.isdir(os.path.join(ziel_dir, o))]
    for ordnername in tqdm(ordnernamen, desc="Fraktionssortierung"):
        ordnerpfad = os.path.join(ziel_dir, ordnername)
        sortiere_fraktionen_mit_zwischenordner(ordnerpfad)


def main():
    # print("Sammle alle passenden Dateien...")
    # files, andere_files = collect_files(ROOT_DIR)
    # print(f"{len(files)} passende Dateien gefunden. Starte das Verschieben...")
    # sortiere_und_verschiebe_dateien(files, ZIEL_DIR)
    # print(f"{len(andere_files)} andere Dateien gefunden. Verschiebe diese nach 'Andere'...")
    # verschiebe_andere_dateien(andere_files, ZIEL_DIR)
    # print("Fertig! Dateien wurden verschoben. Bei Duplikaten wurde ein Unterordner 'dublikate' angelegt.")
    
    # ZIEL_DIR = r'F:\Backup_sortiert\vermutlich in paper'
    plot_histogramme_fuer_dublikate_ordner(ZIEL_DIR)
    plt.show()
    sortiere_alle_ordner_nach_fraktion_mit_zwischenordner(ZIEL_DIR)
    plot_histogramme_fuer_dublikate_ordner(ZIEL_DIR)
    plt.show()

if __name__ == "__main__":
    main()
