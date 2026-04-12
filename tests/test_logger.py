"""Tests for logger utility."""

import logging
from src.utils.logger import get_logger


class TestLogger:
    """Test the logger getter."""

    def test_get_logger_returns_logger_instance(self):
        """Test that get_logger returns a logging.Logger instance."""
        logger = get_logger(__name__)
        assert isinstance(logger, logging.Logger)

    def test_get_logger_named_correctly(self):
        """Test that logger gets the correct name."""
        logger = get_logger("test.module")
        assert logger.name == "test.module"

    def test_get_logger_reuses_same_instance(self):
        """Test that repeated calls return the same logger."""
        logger1 = get_logger("test.same")
        logger2 = get_logger("test.same")
        assert logger1 is logger2
