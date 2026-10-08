"""Website-specific storage metadata; no host controls or user data."""
from pathlib import Path
from typing import Dict, Optional


def storage_status(database_path: Optional[str]) -> Dict[str, object]:
    """Return storage sizes only, without exposing paths or database contents."""
    if not database_path or database_path == ":memory:":
        return {"available": False, "database_bytes": None, "wal_bytes": None}
    database = Path(database_path)
    try:
        size = database.stat().st_size
        wal = Path(str(database) + "-wal")
        return {"available": True, "database_bytes": size, "wal_bytes": wal.stat().st_size if wal.exists() else 0}
    except OSError:
        return {"available": False, "database_bytes": None, "wal_bytes": None}
