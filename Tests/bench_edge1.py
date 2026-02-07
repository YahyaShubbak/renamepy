#!/usr/bin/env python3
"""
Benchmark script for EDGE 1: Measure rename performance.

Tests renaming 596 files from Bilbao with:
- Custom text: "Vacations"
- 2 EXIF fields: ISO and Shutter
"""

import os
import sys
import time
import shutil
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.exif_processor import find_exiftool_path, set_default_exif_service
from modules.exif_service_new import ExifService
from modules.file_utilities import is_media_file, scan_directory_recursive
from modules.rename_engine import RenameWorkerThread


SOURCE_DIR = r"C:\Users\yshub\Desktop\Bilbao"
EXIFTOOL_PATH = find_exiftool_path()


def collect_files() -> list[str]:
    """Scan source directory for media files."""
    files = scan_directory_recursive(SOURCE_DIR)
    print(f"Found {len(files)} media files in {SOURCE_DIR}")
    return files


def copy_to_temp(files: list[str]) -> tuple[str, list[str]]:
    """Copy all files to a temp directory (so we don't modify originals)."""
    temp_dir = tempfile.mkdtemp(prefix="edge1_bench_")
    new_files = []
    for f in files:
        dst = os.path.join(temp_dir, os.path.basename(f))
        # Handle duplicate basenames by adding a suffix
        if os.path.exists(dst):
            base, ext = os.path.splitext(os.path.basename(f))
            i = 1
            while os.path.exists(dst):
                dst = os.path.join(temp_dir, f"{base}_{i}{ext}")
                i += 1
        try:
            os.link(f, dst)  # Hard link — instant, no I/O
        except (OSError, NotImplementedError):
            shutil.copy2(f, dst)
        new_files.append(dst)
    print(f"Prepared {len(new_files)} files in temp dir")
    return temp_dir, new_files


def run_rename(files: list[str], exif_service: ExifService) -> tuple[float, int, int]:
    """Run rename and return (elapsed_seconds, renamed_count, error_count)."""
    worker = RenameWorkerThread(
        files=files,
        camera_prefix="",
        additional="Vacations",
        use_camera=False,
        use_lens=False,
        exif_method="exiftool",
        separator="-",
        exiftool_path=EXIFTOOL_PATH,
        custom_order=["Date", "Prefix", "Additional", "Camera", "Lens"],
        date_format="YYYY-MM-DD",
        use_date=True,
        continuous_counter=True,
        selected_metadata={"iso": True, "shutter": True},
        sync_exif_date=False,
        exif_service=exif_service,
        save_original_to_exif=False,
    )

    start = time.perf_counter()
    renamed, errors, _ts_backup, _mapping = worker.optimized_rename_files()
    elapsed = time.perf_counter() - start

    return elapsed, len(renamed), len(errors)


def main() -> None:
    if not os.path.isdir(SOURCE_DIR):
        print(f"ERROR: Source directory not found: {SOURCE_DIR}")
        sys.exit(1)
    if not EXIFTOOL_PATH:
        print("ERROR: ExifTool not found")
        sys.exit(1)

    print(f"ExifTool: {EXIFTOOL_PATH}")
    files = collect_files()

    # Run 3 iterations for stable timing
    times = []
    for i in range(3):
        exif_service = ExifService(EXIFTOOL_PATH)
        set_default_exif_service(exif_service)

        temp_dir, temp_files = copy_to_temp(files)
        try:
            elapsed, renamed, errs = run_rename(temp_files, exif_service)
            times.append(elapsed)
            print(f"  Run {i+1}: {elapsed:.3f}s  ({renamed} renamed, {errs} errors)")
        finally:
            exif_service.cleanup()
            shutil.rmtree(temp_dir, ignore_errors=True)

    avg = sum(times) / len(times)
    best = min(times)
    print(f"\nResults ({len(files)} files, 3 runs):")
    print(f"  Average: {avg:.3f}s")
    print(f"  Best:    {best:.3f}s")
    print(f"  Per-file (avg): {avg / len(files) * 1000:.2f}ms")


if __name__ == "__main__":
    main()
