#!/usr/bin/env python3
"""
Benchmark: Measure rename performance on the Bilbao test set.

Copies images to a temp directory, runs the rename engine with ISO + Aperture
metadata, and reports wall-clock time. Cleans up afterwards.

Usage:
    python Tests/benchmark_rename.py
"""

import os
import sys
import shutil
import tempfile
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

BILBAO_DIR = r"C:\Users\yshub\Desktop\Bilbao"


def copy_test_files(src_dir: str, dst_dir: str, max_pairs: int = 0) -> list[str]:
    """Copy media files from src_dir to dst_dir. Returns list of copied paths."""
    files = sorted(os.listdir(src_dir))
    media_exts = {'.jpg', '.jpeg', '.arw', '.cr2', '.nef', '.dng', '.raf',
                  '.rw2', '.orf', '.png', '.tiff', '.mp4', '.mov'}
    copied = []
    for f in files:
        ext = os.path.splitext(f)[1].lower()
        if ext in media_exts:
            src = os.path.join(src_dir, f)
            dst = os.path.join(dst_dir, f)
            shutil.copy2(src, dst)
            copied.append(dst)
    if max_pairs > 0:
        # Keep only the first N pairs (a pair = same stem, different ext)
        stems_seen = set()
        filtered = []
        for p in copied:
            stem = os.path.splitext(os.path.basename(p))[0]
            stems_seen.add(stem)
            if len(stems_seen) <= max_pairs:
                filtered.append(p)
        return filtered
    return copied


def run_benchmark(files: list[str], label: str) -> float:
    """Run the rename engine and return elapsed seconds."""
    from modules.exif_processor import find_exiftool_path, cleanup_global_exiftool
    from modules.exif_service_new import ExifService
    from modules.rename_engine import RenameWorkerThread

    exiftool_path = find_exiftool_path()
    if not exiftool_path:
        print("ERROR: ExifTool not found")
        sys.exit(1)

    service = ExifService(exiftool_path=exiftool_path)

    # Configuration matching real-world use: date + prefix + ISO + aperture
    worker = RenameWorkerThread(
        files=files,
        camera_prefix="test",
        additional="",
        use_camera=False,
        use_lens=False,
        exif_method="exiftool",
        separator="-",
        exiftool_path=exiftool_path,
        custom_order=["Date", "Prefix", "Metadata", "Number"],
        date_format="YYYY-MM-DD",
        use_date=True,
        continuous_counter=False,
        selected_metadata={"iso": True, "aperture": True},
        sync_exif_date=False,
        exif_service=service,
        save_original_to_exif=False,
    )

    start = time.perf_counter()
    renamed, errors, ts_backup = worker.optimized_rename_files()
    elapsed = time.perf_counter() - start

    service.cleanup()
    cleanup_global_exiftool()

    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")
    print(f"  Files:        {len(files)}")
    print(f"  Renamed:      {len(renamed)}")
    print(f"  Errors:       {len(errors)}")
    print(f"  Elapsed:      {elapsed:.2f}s")
    print(f"  Per file:     {elapsed/max(len(files),1)*1000:.1f}ms")
    if errors:
        for fp, msg in errors[:5]:
            print(f"    ERR: {os.path.basename(fp)}: {msg}")
    print(f"{'='*60}")

    return elapsed


def main():
    if not os.path.isdir(BILBAO_DIR):
        print(f"Test directory not found: {BILBAO_DIR}")
        sys.exit(1)

    # Count source files
    all_files = [f for f in os.listdir(BILBAO_DIR)
                 if os.path.splitext(f)[1].lower() in {'.jpg', '.arw'}]
    print(f"Source: {BILBAO_DIR}")
    print(f"Total files: {len(all_files)}")

    # --- Full benchmark ---
    with tempfile.TemporaryDirectory(prefix="renamepy_bench_") as tmpdir:
        print(f"\nCopying files to temp dir...")
        t0 = time.perf_counter()
        files = copy_test_files(BILBAO_DIR, tmpdir)
        copy_time = time.perf_counter() - t0
        print(f"Copied {len(files)} files in {copy_time:.1f}s")

        elapsed_full = run_benchmark(files, f"FULL BENCHMARK ({len(files)} files, ISO+Aperture)")

    # --- Small benchmark (20 pairs) for quick iteration ---
    with tempfile.TemporaryDirectory(prefix="renamepy_bench_small_") as tmpdir:
        files = copy_test_files(BILBAO_DIR, tmpdir, max_pairs=20)
        elapsed_small = run_benchmark(files, f"SMALL BENCHMARK ({len(files)} files, ISO+Aperture)")

    print(f"\n{'#'*60}")
    print(f"  SUMMARY")
    print(f"{'#'*60}")
    print(f"  Full:  {elapsed_full:.2f}s  ({len(all_files)} files)")
    print(f"  Small: {elapsed_small:.2f}s  (20 pairs)")
    print(f"{'#'*60}")


if __name__ == "__main__":
    main()
