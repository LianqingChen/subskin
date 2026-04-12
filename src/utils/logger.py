"""Configured logging utilities for SubSkin project.

This module provides a helper function to create consistently configured
loggers that output to both console and optional file with proper formatting.
Supports log rotation to keep logs manageable.
"""

from __future__ import annotations

import logging
import logging.handlers
import sys
from pathlib import Path 

_LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def get_logger(
    name: str,
    log_file: str | Path | None = None,
    level: int = logging.INFO,
    rotate_days: int = 7,
) -> logging.Logger:
    """Return a configured logger with optional log rotation.
    
    Args:
        name: Logger name.
        log_file: Optional file path for file logging.
        level: Logging level. Defaults to ``logging.INFO``.
        rotate_days: Number of days to keep log files. Defaults to 7.
    
    Returns:
        A configured logger instance.
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.propagate = False
    
    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)
    
    # Console handler (always added)
    if not any(isinstance(handler, logging.StreamHandler) for handler in logger.handlers):
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    
    # File handler with rotation (if log_file is provided)
    if log_file is not None:
        log_path = Path(log_file)
        file_path = log_path.resolve()
        
        # Check if file handler already exists for this path
        file_handler_exists = any(
            isinstance(handler, logging.handlers.RotatingFileHandler)
            and Path(getattr(handler, "baseFilename", "")).resolve() == file_path
            for handler in logger.handlers
        )
        
        if not file_handler_exists:
            # Use TimedRotatingFileHandler for time-based rotation
            # Rotate daily, keep files for the specified number of days
            file_handler = logging.handlers.TimedRotatingFileHandler(
                filename=file_path,
                when="midnight",  # Rotate at midnight
                interval=1,  # Every day
                backupCount=rotate_days,  # Keep N backup files
                encoding="utf-8"
            )
            file_handler.setLevel(level)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
    
    # Set level and formatter for all handlers
    for handler in logger.handlers:
        handler.setLevel(level)
        handler.setFormatter(formatter)
    
    return logger
