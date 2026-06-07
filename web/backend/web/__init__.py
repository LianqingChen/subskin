"""Import shim so `python -c` works from web/backend."""

from pathlib import Path


__path__ = [str(Path(__file__).resolve().parents[2])]
