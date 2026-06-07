import json
import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))),
    "data",
    "medical_knowledge",
)


class MedicalKnowledgeBase:
    def __init__(self) -> None:
        self._indicators: List[Dict[str, Any]] = []
        self._name_map: Dict[str, Dict[str, Any]] = {}
        self._loaded = False

    def load(self) -> None:
        if self._loaded:
            return
        json_path = os.path.join(_DATA_DIR, "reference_ranges.json")
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                self._indicators = json.load(f)
        except Exception as exc:
            logger.error("Failed to load reference_ranges.json: %s", exc)
            self._indicators = []

        for indicator in self._indicators:
            names = [indicator["name"], indicator.get("chinese_name", "")]
            aliases: List[str] = indicator.get("aliases", [])
            for n in names + aliases:
                key = n.strip().lower()
                if key:
                    self._name_map[key] = indicator
        self._loaded = True

    def normalize_name(self, name: str) -> str:
        self.load()
        key = name.strip().lower()
        indicator = self._name_map.get(key)
        if indicator:
            return indicator["name"]
        return name

    def get_reference(self, name: str) -> Optional[Dict[str, Any]]:
        self.load()
        key = name.strip().lower()
        return self._name_map.get(key)

    def get_clinical_info(self, name: str) -> Optional[Dict[str, Any]]:
        ref = self.get_reference(name)
        if not ref:
            return None
        return {
            "name": ref["name"],
            "chinese_name": ref.get("chinese_name", ""),
            "unit": ref.get("unit", ""),
            "ref_min": ref.get("ref_min"),
            "ref_max": ref.get("ref_max"),
            "clinical_low": ref.get("clinical_low", ""),
            "clinical_high": ref.get("clinical_high", ""),
            "vitiligo_relevance": ref.get("vitiligo_relevance", ""),
        }


knowledge_base = MedicalKnowledgeBase()
