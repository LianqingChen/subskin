"""Configuration settings for SubSkin (backward compatibility wrapper).

This file is maintained for backward compatibility.
New code should import from `src.settings` instead.
"""

from src.settings.settings import Settings, settings, ValidationError

__all__ = ["Settings", "ValidationError", "settings"]
