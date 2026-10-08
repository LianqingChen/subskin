"""Presentation guards for current and archived photographic reports."""
from copy import deepcopy
from typing import Any, Dict


def safe_report_metrics(metrics: Dict[str, Any]) -> Dict[str, Any]:
    result = deepcopy(metrics)
    current = result.get("measurement_version") == "common-roi-v1"
    pm = result.get("pair_metrics") or {}
    if not current:
        result.update({"measurement_version": "legacy", "comparison_status": "legacy",
                       "trend": "历史记录，暂不可直接比较", "headline": "历史观察记录", "pair_align": None,
                       "change_summary": ["历史测量口径未验证，原始记录保留，不再推断病情变化"]})
        for key in ("size_change_percent", "melanin_change", "melanin_score_a", "melanin_score_b", "color_change", "border_change"):
            pm[key] = None
        pm.update({"comparison_status": "legacy", "low_confidence": True, "trend": "无法可靠比较", "trend_en": "unknown", "capture_note": "历史测量口径未验证"})
    result["pair_metrics"] = pm or None
    result["has_vasi"] = False
    for key in ("vasi_change", "vasi_change_percent", "area_change"):
        result[key] = None
    for section in result.get("sites") or []:
        section["vasi_change"] = None
        section["vasi_points"] = []
        pair = section.get("pair_metrics") or {}
        if pair.get("measurement_version") != "common-roi-v1":
            section["pair_metrics"] = None
            section["trend"] = "无法可靠比较"
    if not current:
        result["max_change_pair"] = None
        result["melanin_sites"] = []
        summary = result.get("sites_summary")
        if summary:
            summary.update({"improving": 0, "stable": 0, "worsening": 0, "pending": summary.get("total", 0)})
    return result
