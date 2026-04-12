"""Logging configuration for SubSkin project.

This module contains logging-related settings and utilities.
"""

from __future__ import annotations

import logging
from typing import Optional

from .settings import settings


def configure_logging(
    name: Optional[str] = None,
    level: Optional[str] = None,
) -> logging.Logger:
    """Configure and return a logger with the given name.

    Args:
        name: Logger name (defaults to root logger if None)
        level: Log level (defaults to LOG_LEVEL from settings)

    Returns:
        Configured logger instance
    """
    log_level = level or settings.LOG_LEVEL
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    logger = logging.getLogger(name)
    logger.setLevel(numeric_level)

    # If no handlers configured yet, add a default stream handler
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setLevel(numeric_level)
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger


def get_logger(name: str) -> logging.Logger:
    """Get a configured logger with the given name.

    Shortcut for `configure_logging(name)` using default settings.

    Args:
        name: Logger name

    Returns:
        Configured logger instance
    """
    return configure_logging(name)
