#!/usr/bin/env python3
"""
ExifService - Modern EXIF data extraction service with instance-based caching.
Replaces global variables with instance variables for better thread safety and testability.
"""

import os
import time
import threading
import subprocess
import glob
import shutil
from collections import OrderedDict
from functools import lru_cache

from .logger_util import get_logger
log = get_logger()

# EXIF processing imports
try:
    import exiftool
    EXIFTOOL_AVAILABLE = True
except ImportError:
    EXIFTOOL_AVAILABLE = False

# Pillow dependency removed — ExifTool is the sole EXIF backend


class ExifService:
    """
    Service class for EXIF data extraction and caching.
    Replaces global variables with instance variables for better thread safety and testability.
    """
    
    def __init__(self, exiftool_path=None):
        """
        Initialize the EXIF service with optional exiftool path
        
        Args:
            exiftool_path: Path to exiftool executable. If None, will auto-detect.
        """
        # Instance variables instead of globals
        self._cache: OrderedDict = OrderedDict()
        self._cache_lock = threading.Lock()
        self._cache_max_size = 10000  # Prevent unbounded memory growth
        self._exiftool_instance = None
        self._exiftool_lock = threading.Lock()  # Thread safety for ExifTool instance
        self._exiftool_path = exiftool_path or self._find_exiftool_path()
        
        # Set default method based on availability
        self.current_method = "exiftool" if EXIFTOOL_AVAILABLE else None
    
    @staticmethod
    @lru_cache(maxsize=1)
    def _find_exiftool_path_cached():
        """Find ExifTool executable in project directory (cached for performance)"""
        try:
            # Check project directory
            project_root = os.path.dirname(os.path.dirname(__file__))
            exiftool_dirs = glob.glob(os.path.join(project_root, "exiftool-*_64"))
            
            if exiftool_dirs:
                exiftool_exe = os.path.join(exiftool_dirs[0], "exiftool(-k).exe")
                if os.path.exists(exiftool_exe):
                    return exiftool_exe
            
            # Check if exiftool is in PATH
            if shutil.which("exiftool"):
                return "exiftool"
        except Exception as e:
            # Can't use log here since this is a static method
            pass
        
        return None
    
    def _find_exiftool_path(self):
        """Find ExifTool executable (uses cached static method)"""
        return self._find_exiftool_path_cached()
    
    def clear_cache(self) -> None:
        """Clear the EXIF cache for fresh processing."""
        with self._cache_lock:
            self._cache.clear()

    # ------------------------------------------------------------------
    # Batch extraction — reduces N ExifTool IPC calls to ceil(N/chunk)
    # ------------------------------------------------------------------

    def batch_get_raw_metadata(
        self, file_paths: list[str], chunk_size: int = 50
    ) -> dict[str, dict]:
        """Batch-extract raw EXIF metadata for many files at once.

        Instead of one ExifTool IPC round-trip per file, this sends
        *chunk_size* file paths in a single ``get_metadata()`` call.
        For 300 files with chunk_size=50 this is 6 calls instead of 300.

        Args:
            file_paths: List of file paths to extract metadata from.
            chunk_size: Files per ExifTool batch call (default 50).

        Returns:
            Dict mapping each input file path to its raw metadata dict.
            Files that fail return an empty dict.
        """
        results: dict[str, dict] = {}
        if not file_paths:
            return results

        # Normalize paths and filter to existing files
        path_pairs: list[tuple[str, str]] = []
        for fp in file_paths:
            norm = os.path.normpath(fp)
            if os.path.exists(norm):
                path_pairs.append((norm, fp))
            else:
                results[fp] = {}

        exiftool_path = self._exiftool_path

        for i in range(0, len(path_pairs), chunk_size):
            chunk = path_pairs[i : i + chunk_size]
            chunk_norms = [norm for norm, _orig in chunk]

            try:
                with self._exiftool_lock:
                    self._ensure_exiftool_running(exiftool_path)
                    batch_meta = self._exiftool_instance.get_metadata(chunk_norms)

                for (norm, orig), meta in zip(chunk, batch_meta):
                    results[orig] = meta
            except Exception as e:
                log.warning(f"Batch ExifTool failed for chunk, falling back to per-file: {e}")
                # Rebuild instance for next attempt
                with self._exiftool_lock:
                    self._kill_exiftool_instance()
                for norm, orig in chunk:
                    if orig not in results:
                        try:
                            results[orig] = self._get_exiftool_metadata_shared(norm, exiftool_path)
                        except Exception:
                            results[orig] = {}

        return results

    # ------------------------------------------------------------------
    # Static helpers — parse fields from an already-fetched raw dict
    # ------------------------------------------------------------------

    @staticmethod
    def parse_date_from_raw(meta: dict) -> str | None:
        """Extract date string (YYYYMMDD) from raw EXIF metadata."""
        date = (
            meta.get("EXIF:DateTimeOriginal")
            or meta.get("CreateDate")
            or meta.get("DateTimeOriginal")
        )
        if date:
            return date.split(" ")[0].replace(":", "")
        return None

    @staticmethod
    def parse_camera_from_raw(meta: dict) -> str | None:
        """Extract camera model from raw EXIF metadata."""
        camera = meta.get("EXIF:Model") or meta.get("Model")
        if camera:
            return str(camera).replace(" ", "-")
        return None

    @staticmethod
    def parse_lens_from_raw(meta: dict) -> str | None:
        """Extract lens model from raw EXIF metadata."""
        lens = (
            meta.get("EXIF:LensModel")
            or meta.get("LensModel")
            or meta.get("LensInfo")
        )
        if lens:
            return str(lens).replace(" ", "-")
        return None

    @staticmethod
    def parse_all_metadata_from_raw(meta: dict) -> dict:
        """Extract all relevant metadata fields from raw EXIF dict.

        Returns dict with keys: aperture, iso, focal_length, shutter_speed,
        camera, lens — same format as ``get_all_metadata()``.
        """
        metadata: dict = {}
        if not meta:
            return metadata

        # Aperture
        aperture = meta.get("EXIF:FNumber") or meta.get("FNumber") or meta.get("EXIF:ApertureValue")
        if aperture:
            try:
                if isinstance(aperture, str) and "/" in aperture:
                    num, den = aperture.split("/")
                    aperture_val = float(num) / float(den)
                else:
                    aperture_val = float(aperture)
                metadata["aperture"] = f"f{aperture_val:.1f}".replace(".0", "")
            except (ValueError, TypeError, ZeroDivisionError):
                pass

        # ISO
        iso = meta.get("EXIF:ISO") or meta.get("ISO")
        if iso:
            metadata["iso"] = str(iso)

        # Focal length
        focal = meta.get("EXIF:FocalLength") or meta.get("FocalLength")
        if focal:
            try:
                if isinstance(focal, str) and "/" in focal:
                    num, den = focal.split("/")
                    focal_val = float(num) / float(den)
                else:
                    focal_val = float(focal)
                metadata["focal_length"] = f"{focal_val:.0f}mm"
            except (ValueError, TypeError, ZeroDivisionError):
                pass

        # Shutter speed
        shutter = meta.get("EXIF:ExposureTime") or meta.get("ExposureTime")
        if shutter:
            try:
                if isinstance(shutter, str) and "/" in shutter:
                    num, den = shutter.split("/")
                    shutter_val = float(num) / float(den)
                else:
                    shutter_val = float(shutter)
                if shutter_val >= 1:
                    metadata["shutter_speed"] = f"{shutter_val:.0f}s"
                else:
                    metadata["shutter_speed"] = f"1/{int(1/shutter_val)}s"
            except (ValueError, TypeError, ZeroDivisionError):
                pass

        # Camera
        camera = meta.get("EXIF:Model") or meta.get("Model")
        if camera:
            metadata["camera"] = str(camera).replace(" ", "-")

        # Lens
        lens = meta.get("EXIF:LensModel") or meta.get("LensModel")
        if lens:
            metadata["lens"] = str(lens).replace(" ", "-")

        return metadata

    def _evict_cache_if_needed(self) -> None:
        """Evict oldest cache entries if cache exceeds max size.

        Must be called while holding ``_cache_lock``.
        """
        if len(self._cache) > self._cache_max_size:
            # Remove oldest 20% of entries
            evict_count = self._cache_max_size // 5
            keys_to_remove = list(self._cache.keys())[:evict_count]
            for key in keys_to_remove:
                del self._cache[key]
    
    def cleanup(self) -> None:
        """Clean up the ExifTool instance when done with batch processing.

        OPTIMIZATION: Only call this when app closes, not after each operation!
        """
        with self._exiftool_lock:
            if self._exiftool_instance is not None:
                try:
                    self._exiftool_instance.__exit__(None, None, None)
                    log.info("ExifTool instance cleaned up successfully")
                except Exception as e:
                    log.warning(f"Error during ExifTool cleanup: {e}")
                finally:
                    self._exiftool_instance = None
    
    def get_cached_exif_data(self, file_path, method=None, exiftool_path=None):
        """
        Get EXIF data with intelligent caching based on file modification time
        
        Args:
            file_path: Path to the image file
            method: 'exiftool' (only supported method, defaults to self.current_method)
            exiftool_path: Path to exiftool (defaults to self._exiftool_path)
        
        Returns:
            (date, camera, lens) tuple
        """
        method = method or self.current_method
        exiftool_path = exiftool_path or self._exiftool_path
        
        try:
            # Create cache key based on file path and modification time
            mtime = os.path.getmtime(file_path)
            cache_key = (file_path, mtime, method)
            
            # Check cache first
            with self._cache_lock:
                if cache_key in self._cache:
                    self._cache.move_to_end(cache_key)  # LRU: mark as recently used
                    return self._cache[cache_key]
            
            # Extract EXIF data (not cached)
            result = self._extract_exif_fields_with_retry(file_path, method, exiftool_path, max_retries=2)
            
            # Cache the result
            with self._cache_lock:
                self._evict_cache_if_needed()
                self._cache[cache_key] = result
            
            return result
        except Exception as e:
            log.debug(f"Cached EXIF extraction failed for {file_path}: {e}")
            return None, None, None
    
    def get_selective_cached_exif_data(self, file_path, method=None, exiftool_path=None,
                                      need_date=True, need_camera=False, need_lens=False):
        """
        OPTIMIZED: Get only requested EXIF data with intelligent caching.
        This function only extracts and caches the fields that are actually needed.
        
        Args:
            file_path: Path to the image file
            method: 'exiftool' (only supported method, defaults to self.current_method)
            exiftool_path: Path to exiftool executable (defaults to self._exiftool_path)
            need_date: Whether to extract date information
            need_camera: Whether to extract camera model
            need_lens: Whether to extract lens model
        
        Returns:
            (date, camera, lens) - only requested fields are extracted and cached
        """
        method = method or self.current_method
        exiftool_path = exiftool_path or self._exiftool_path
        
        try:
            # CRITICAL FIX: Normalize path to prevent double backslashes
            normalized_path = os.path.normpath(file_path)
            
            # Verify file exists before processing
            if not os.path.exists(normalized_path):
                log.warning(f"File not found: {normalized_path}")
                return None, None, None
            
            # Create cache key based on file path, modification time, method AND requested fields
            mtime = os.path.getmtime(normalized_path)
            field_signature = (need_date, need_camera, need_lens)
            cache_key = (normalized_path, mtime, method, field_signature)
            
            # Check cache first
            with self._cache_lock:
                if cache_key in self._cache:
                    self._cache.move_to_end(cache_key)  # LRU: mark as recently used
                    return self._cache[cache_key]
            
            # Extract only requested EXIF fields
            result = self._extract_selective_exif_fields(
                normalized_path, method, exiftool_path,
                need_date=need_date, need_camera=need_camera, need_lens=need_lens
            )
            
            # Cache the result
            with self._cache_lock:
                self._evict_cache_if_needed()
                self._cache[cache_key] = result
            
            return result
        except Exception as e:
            log.debug(f"Error in get_selective_cached_exif_data for {file_path}: {e}")
            return None, None, None
    
    def _get_exiftool_metadata_shared(self, image_path, exiftool_path=None):
        """
        PERFORMANCE OPTIMIZATION: Use a shared ExifTool instance to avoid
        the overhead of starting/stopping ExifTool for each file.
        """
        # CRITICAL FIX: Normalize path to prevent double backslashes
        normalized_path = os.path.normpath(image_path)
        
        # Verify file exists
        if not os.path.exists(normalized_path):
            log.warning(f"get_exiftool_metadata_shared: File not found: {normalized_path}")
            return {}
        
        # Use instance exiftool path if not provided
        exiftool_path = exiftool_path or self._exiftool_path
        
        try:
            with self._exiftool_lock:
                self._ensure_exiftool_running(exiftool_path)
                meta = self._exiftool_instance.get_metadata([normalized_path])[0]
                return meta
            
        except Exception as e:
            # If the shared instance fails, rebuild and fall back to a temporary instance
            log.warning(f"Shared ExifTool instance failed, using temporary instance: {e}")
            with self._exiftool_lock:
                self._kill_exiftool_instance()
            try:
                if exiftool_path and os.path.exists(exiftool_path):
                    with exiftool.ExifToolHelper(executable=exiftool_path) as et:
                        return et.get_metadata([normalized_path])[0]
                else:
                    with exiftool.ExifToolHelper() as et:
                        return et.get_metadata([normalized_path])[0]
            except Exception as e2:
                log.error(f"Temporary ExifTool instance also failed: {e2}")
                return {}

    def _ensure_exiftool_running(self, exiftool_path: str | None = None) -> None:
        """Start or restart the shared ExifTool process if needed.

        MUST be called while holding ``_exiftool_lock``.
        """
        exiftool_path = exiftool_path or self._exiftool_path

        if self._exiftool_instance is not None and self._exiftool_path == exiftool_path:
            return  # Already running with correct path

        # Close stale instance
        if self._exiftool_instance is not None:
            try:
                self._exiftool_instance.terminate()
            except Exception:
                pass

        # Create & start new instance
        if exiftool_path and os.path.exists(exiftool_path):
            self._exiftool_instance = exiftool.ExifToolHelper(executable=exiftool_path)
            log.info(f"Created ExifTool instance with: {exiftool_path}")
        else:
            self._exiftool_instance = exiftool.ExifToolHelper()
            log.info("Created default ExifTool instance")

        self._exiftool_path = exiftool_path
        self._exiftool_instance.__enter__()

    def _kill_exiftool_instance(self) -> None:
        """Terminate the shared ExifTool process.

        MUST be called while holding ``_exiftool_lock``.
        """
        if self._exiftool_instance is not None:
            try:
                self._exiftool_instance.terminate()
            except Exception:
                pass
            self._exiftool_instance = None
    
    def _extract_exif_fields_with_retry(self, image_path, method, exiftool_path=None, max_retries=3):
        """
        Extracts EXIF fields with retry mechanism for reliability.
        OPTIMIZATION: Now uses shared ExifTool instance for better performance!
        """
        # CRITICAL FIX: Normalize path to prevent double backslashes
        normalized_path = os.path.normpath(image_path)
        
        # Verify file exists
        if not os.path.exists(normalized_path):
            log.warning(f"extract_exif_fields_with_retry: File not found: {normalized_path}")
            return None, None, None
        
        for attempt in range(max_retries):
            try:
                if method == "exiftool":
                    # PERFORMANCE OPTIMIZATION: Use shared ExifTool instance instead of creating new process
                    meta = self._get_exiftool_metadata_shared(normalized_path, exiftool_path)
                    
                    # Extract date
                    date = meta.get('EXIF:DateTimeOriginal')
                    if date:
                        date = date.split(' ')[0].replace(':', '')
                    
                    # Extract camera model
                    camera = meta.get('EXIF:Model')
                    if camera:
                        camera = str(camera).replace(' ', '-')
                    
                    # Extract lens model
                    lens = meta.get('EXIF:LensModel') or meta.get('LensInfo')
                    if lens:
                        lens = str(lens).replace(' ', '-')
                    
                    return date, camera, lens
                else:
                    log.warning(f"Unsupported EXIF method: {method}")
                    return None, None, None
                    
            except Exception as e:
                if attempt == max_retries - 1:
                    log.error(f"EXIF extraction failed after {max_retries} attempts: {e}")
                    return None, None, None
                else:
                    time.sleep(0.1)
    
    def _extract_selective_exif_fields(self, image_path, method, exiftool_path=None,
                                      need_date=True, need_camera=False, need_lens=False):
        """
        OPTIMIZED: Extracts only the requested EXIF fields from an image.
        This dramatically improves performance by only reading what's needed.
        
        Args:
            image_path: Path to the image file
            method: 'exiftool' (only supported method)
            exiftool_path: Path to exiftool executable
            need_date: Whether to extract date information
            need_camera: Whether to extract camera model
            need_lens: Whether to extract lens model
        
        Returns:
            (date, camera, lens) - only requested fields are extracted, others are None
        """
        # If nothing is needed, return early
        if not any([need_date, need_camera, need_lens]):
            return None, None, None
        
        # CRITICAL FIX: Normalize path to prevent double backslashes
        normalized_path = os.path.normpath(image_path)
        
        # Verify file exists
        if not os.path.exists(normalized_path):
            log.warning(f"extract_selective_exif_fields: File not found: {normalized_path}")
            return None, None, None
        
        max_retries = 2  # Reduced retries for batch processing
        
        for attempt in range(max_retries):
            try:
                if method == "exiftool":
                    # Use shared ExifTool instance for better performance
                    meta = self._get_exiftool_metadata_shared(normalized_path, exiftool_path)
                    
                    # Extract only requested fields
                    date = None
                    camera = None
                    lens = None
                    
                    if need_date:
                        date = meta.get('EXIF:DateTimeOriginal') or meta.get('CreateDate') or meta.get('DateTimeOriginal')
                        if date:
                            date = date.split(' ')[0].replace(':', '')
                    
                    if need_camera:
                        # Use the same simple approach as the working old application
                        camera = meta.get('EXIF:Model') or meta.get('Model')
                        if camera:
                            camera = str(camera).replace(' ', '-')
                    
                    if need_lens:
                        # Use the same simple approach as the working old application
                        lens = meta.get('EXIF:LensModel') or meta.get('LensModel') or meta.get('LensInfo')
                        if lens:
                            lens = str(lens).replace(' ', '-')
                    
                    return date, camera, lens
                else:
                    log.warning(f"Unsupported EXIF method: {method}")
                    return None, None, None
                    
            except Exception as e:
                if attempt == max_retries - 1:
                    return None, None, None
                else:
                    time.sleep(0.05)  # Shorter pause for batch processing
    
    def get_all_metadata(self, file_path, method=None, exiftool_path=None):
        """
        Extract all relevant metadata for filename generation
        Returns dict with aperture, iso, focal_length, shutter_speed, etc.
        """
        method = method or self.current_method
        exiftool_path = exiftool_path or self._exiftool_path
        
        try:
            normalized_path = os.path.normpath(file_path)
            
            if not os.path.exists(normalized_path):
                return {}
            
            metadata = {}
            
            if method == "exiftool" and EXIFTOOL_AVAILABLE:
                meta = self._get_exiftool_metadata_shared(normalized_path, exiftool_path)
                
                # Extract all relevant metadata
                if meta:
                    # Aperture (f-number)
                    aperture = meta.get('EXIF:FNumber') or meta.get('FNumber') or meta.get('EXIF:ApertureValue')
                    if aperture:
                        try:
                            # Convert to f/x format
                            if isinstance(aperture, str) and '/' in aperture:
                                num, den = aperture.split('/')
                                aperture_val = float(num) / float(den)
                            else:
                                aperture_val = float(aperture)
                            metadata['aperture'] = f"f{aperture_val:.1f}".replace('.0', '')
                        except (ValueError, TypeError, ZeroDivisionError):
                            pass
                    
                    # ISO
                    iso = meta.get('EXIF:ISO') or meta.get('ISO')
                    if iso:
                        metadata['iso'] = str(iso)
                    
                    # Focal Length
                    focal = meta.get('EXIF:FocalLength') or meta.get('FocalLength')
                    if focal:
                        try:
                            if isinstance(focal, str) and '/' in focal:
                                num, den = focal.split('/')
                                focal_val = float(num) / float(den)
                            else:
                                focal_val = float(focal)
                            metadata['focal_length'] = f"{focal_val:.0f}mm"
                        except (ValueError, TypeError, ZeroDivisionError):
                            pass
                    
                    # Shutter Speed
                    shutter = meta.get('EXIF:ExposureTime') or meta.get('ExposureTime')
                    if shutter:
                        try:
                            if isinstance(shutter, str) and '/' in shutter:
                                num, den = shutter.split('/')
                                shutter_val = float(num) / float(den)
                                if shutter_val >= 1:
                                    metadata['shutter_speed'] = f"{shutter_val:.0f}s"
                                else:
                                    metadata['shutter_speed'] = f"1/{int(1/shutter_val)}s"
                            else:
                                shutter_val = float(shutter)
                                if shutter_val >= 1:
                                    metadata['shutter_speed'] = f"{shutter_val:.0f}s"
                                else:
                                    metadata['shutter_speed'] = f"1/{int(1/shutter_val)}s"
                        except (ValueError, TypeError, ZeroDivisionError):
                            pass
                    
                    # Camera model
                    camera = meta.get('EXIF:Model') or meta.get('Model')
                    if camera:
                        metadata['camera'] = str(camera).replace(' ', '-')
                    
                    # Lens model
                    lens = meta.get('EXIF:LensModel') or meta.get('LensModel')
                    if lens:
                        metadata['lens'] = str(lens).replace(' ', '-')
            
            return metadata
        except Exception as e:
            log.error(f"Error extracting metadata from {file_path}: {e}")
            return {}
    
    def extract_raw_exif(self, file_path):
        """Extract raw EXIF data dictionary"""
        if self.current_method == "exiftool":
            return self._get_exiftool_metadata_shared(file_path, self._exiftool_path)
        return {}
    
    def is_exiftool_available(self):
        """Check if ExifTool is available"""
        return EXIFTOOL_AVAILABLE and self.current_method == "exiftool"
