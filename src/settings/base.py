"""Environment file reading utilities.

This module contains functions for resolving and reading .env files.
"""

from __future__ import annotations

import os
from pathlib import Path

from .paths import PROJECT_ROOT


def _resolve_env_file(env_file: str | None | Path = None) -> Path:
    """Resolve the absolute path to the .env file.

    Args:
        env_file: Optional explicit path to .env file.

    Returns:
        Absolute Path to the .env file.
    """
    candidate = env_file or os.getenv("ENV_FILE") or ".env"
    path = Path(candidate).expanduser()
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path


def _read_env_file(env_path: Path) -> dict[str, str]:
    """Read key-value pairs from .env file.

    If python-dotenv is not available, falls back to simple manual parsing.

    Args:
        env_path: Path to the .env file.

    Returns:
        Dictionary of parsed environment variables.
    """
    if not env_path.exists():
        return {}

    try:
        from dotenv import dotenv_values
        parsed = dotenv_values(dotenv_path=env_path, encoding="utf-8")
        return {key: value for key, value in parsed.items() if value is not None}
    except ImportError:
        values: dict[str, str] = {}
        for line in env_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue

            key, value = stripped.split("=", 1)
            key = key.strip()
            if not key:
                continue

            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
                value = value[1:-1]

            values[key] = value

        return values
