"""Knowledge seed file (``web/shared/knowledge/seed.json``): git-reviewed draft content."""

import json
from pathlib import Path
from typing import Dict, Optional

SEED_PATH = Path(__file__).resolve().parents[2] / "shared" / "knowledge" / "seed.json"
DEFAULT_TOPICS = {
    "basics": "认识白癜风",
    "causes": "为什么会得",
    "daily_care": "日常照护",
    "treatment": "治疗与就医",
    "mind": "心理与生活",
    "children": "儿童与家庭",
    "frontier": "前沿进展",
}


def read_seed(path: Path = SEED_PATH) -> Optional[dict]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def topic_labels() -> Dict[str, str]:
    labels = dict(DEFAULT_TOPICS)
    data = read_seed() or {}
    for topic in data.get("topics", []):
        if isinstance(topic, dict) and topic.get("key") and topic.get("label"):
            labels[topic["key"]] = topic["label"]
    return labels
