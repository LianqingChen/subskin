"""Settings module for SubSkin configuration.

This module contains typed application settings loaded from environment variables.
"""

from .paths import (
    PROJECT_ROOT,
    DATA_DIR,
    DATA_RAW_DIR,
    DATA_PROCESSED_DIR,
    DATA_EXPORTS_DIR,
    CONFIGS_DIR,
    LOGS_DIR,
    TESTS_DIR,
    ensure_directories,
)
from .logging import configure_logging, get_logger
from .settings import Settings, settings
from .base import _resolve_env_file, _read_env_file

__all__ = [
    # Paths
    "PROJECT_ROOT",
    "DATA_DIR",
    "DATA_RAW_DIR",
    "DATA_PROCESSED_DIR",
    "DATA_EXPORTS_DIR",
    "CONFIGS_DIR",
    "LOGS_DIR",
    "TESTS_DIR",
    "ensure_directories",
    # Logging
    "configure_logging",
    "get_logger",
    # Settings
    "Settings",
    "settings",
    # Internal utilities
    "_resolve_env_file",
    "_read_env_file",
]
