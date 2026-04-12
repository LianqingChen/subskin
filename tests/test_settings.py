"""Tests for settings modules."""

import os
from pathlib import Path
import pytest
from src.settings.settings import Settings
from src.settings.paths import (
    PROJECT_ROOT,
    DATA_DIR,
    LOGS_DIR,
    ensure_directories,
)
from src.settings.logging import configure_logging


class TestSettingsLoading:
    """Test Settings pydantic model loading."""

    def test_settings_can_load_from_env(self):
        """Test that Settings can be instantiated."""
        # Settings loads from .env automatically via pydantic-settings
        # Just check that it instantiates without throwing
        settings = Settings()
        assert settings is not None
        assert hasattr(settings, "NCBI_API_KEY")
        assert hasattr(settings, "OPENAI_API_KEY")
        assert hasattr(settings, "SCHEDULER_ENABLED")
        assert isinstance(settings.SCHEDULER_ENABLED, bool)


class TestPaths:
    """Test path constants."""

    def test_project_root_is_correct(self):
        """Test that PROJECT_ROOT is correctly detected."""
        assert isinstance(PROJECT_ROOT, Path)
        assert (PROJECT_ROOT / "pyproject.toml").exists()
        assert (PROJECT_ROOT / "README.md").exists()

    def test_data_dir_is_correct(self):
        """Test that DATA_DIR is correct."""
        assert isinstance(DATA_DIR, Path)
        assert DATA_DIR.name == "data"

    def test_logs_dir_is_correct(self):
        """Test that LOGS_DIR is correct."""
        assert isinstance(LOGS_DIR, Path)
        assert LOGS_DIR.name == "logs"

    def test_ensure_directories_does_not_throw(self):
        """Test that ensure_directories runs without error."""
        ensure_directories()
        assert DATA_DIR.exists()
        assert LOGS_DIR.exists()


class TestLoggingConfiguration:
    """Test logging configuration."""

    def test_configure_logging_does_not_throw(self):
        """Test that configure_logging runs without error."""
        # This should just configure logging and not throw
        configure_logging()
        assert True  # If we get here, it worked
