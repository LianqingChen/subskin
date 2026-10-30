"""Body-site taxonomy derived from ``web/shared/body-sites.json`` (single source)."""

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

_PATH = Path(__file__).resolve().parents[2] / "shared" / "body-sites.json"


@lru_cache(maxsize=1)
def taxonomy() -> Dict[str, Any]:
    return json.loads(_PATH.read_text(encoding="utf-8"))


def sites() -> List[Dict[str, Any]]:
    return list(taxonomy()["sites"])


def site_labels() -> Dict[str, str]:
    """code → stored Chinese label (what assessments persist)."""
    return {site["code"]: site["label"] for site in sites()}


def normalize(value: Optional[str]) -> Optional[str]:
    """Map a code, stored label or legacy alias to a canonical code; None if unknown."""
    if not value:
        return None
    text = value.strip()
    by_code = {site["code"]: site["code"] for site in sites()}
    if text in by_code:
        return text
    for site in sites():
        if site["label"] == text:
            return site["code"]
    return taxonomy()["aliases"].get(text)


def group_of(value: Optional[str]) -> str:
    """Coarse training/evaluation group (head/torso/arm/hand/leg/foot/other) or unknown."""
    code = normalize(value)
    for site in sites():
        if site["code"] == code:
            return site["group"]
    return "unknown"


def label_of(value: Optional[str]) -> Optional[str]:
    code = normalize(value)
    return site_labels().get(code) if code else None
