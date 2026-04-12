"""Path definitions for SubSkin project.

This module contains constant paths for the project root and common directories.
"""

from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
"""Project root directory (absolute path)."""

DATA_DIR = PROJECT_ROOT / "data"
"""Main data directory."""

DATA_RAW_DIR = DATA_DIR / "raw"
"""Raw scraped data directory."""

DATA_PROCESSED_DIR = DATA_DIR / "processed"
"""AI-processed data directory."""

DATA_EXPORTS_DIR = DATA_DIR / "exports"
"""Final exported datasets directory."""

CONFIGS_DIR = PROJECT_ROOT / "configs"
"""Configuration files directory."""

LOGS_DIR = PROJECT_ROOT / "logs"
"""Log files directory."""

TESTS_DIR = PROJECT_ROOT / "tests"
"""Tests directory."""


def ensure_directories() -> None:
    """Ensure all required data directories exist.

    Creates directories if they don't already exist.
    """
    for directory in [
        DATA_DIR,
        DATA_RAW_DIR,
        DATA_PROCESSED_DIR,
        DATA_EXPORTS_DIR,
        LOGS_DIR,
    ]:
        directory.mkdir(parents=True, exist_ok=True)
