#!/usr/bin/env python3
"""Central logging utility for the renamepy application.

Provides a single get_logger() function returning a configured root logger
for the application so that all modules share consistent formatting and levels.

Usage:
    from .logger_util import get_logger
    log = get_logger()
    log.info("message")

A helper set_level() is provided for dynamic level changes from the UI
(e.g. toggling debug verbosity without recreating handlers).
"""
from __future__ import annotations
import logging
import os
from typing import Optional

_LOGGER: Optional[logging.Logger] = None
_DEFAULT_NAME = "renamepy"

def get_logger(name: str = _DEFAULT_NAME) -> logging.Logger:
    global _LOGGER
    if _LOGGER is not None:
        return _LOGGER

    logger = logging.getLogger(name)
    # Only configure once (avoid duplicate handlers if reloaded)
    if not logger.handlers:
        level_name = os.environ.get("RENAMEPY_LOG_LEVEL", "INFO").upper()
        level = getattr(logging, level_name, logging.INFO)
        logger.setLevel(level)
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%H:%M:%S"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    # Prevent propagation to root to avoid duplicate output if root also configured
    logger.propagate = False
    _LOGGER = logger
    return logger

def set_level(level: int | str) -> None:
    """Dynamically adjust log level for all existing handlers.

    Args:
        level: logging level (int or name). Examples: logging.DEBUG, "DEBUG".
    """
    logger = get_logger()
    if isinstance(level, str):
        level = getattr(logging, level.upper(), logging.INFO)
    logger.setLevel(level)
    for handler in logger.handlers:
        handler.setLevel(level)

__all__ = ["get_logger", "set_level"]
