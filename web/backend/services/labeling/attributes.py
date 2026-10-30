"""Image-level attributes per the annotator guideline (T-Q/T-S/T-V), validated.

Every field accepts "unknown"; nothing is auto-filled. Diagnosis, type, stage
and clinical scores are deliberately absent — those are clinician-only.
"""

from typing import Any, Dict, List

from web.backend.exceptions import RGBSegmentationError
from web.backend.utils.body_sites import normalize

GUIDELINE_VERSION = "v0.1"

QUALITY_ISSUES = ("blur", "exposure", "glare", "occlusion", "angle", "site_mismatch")
REJECT_REASONS = QUALITY_ISSUES + ("identifiable", "out_of_scope", "not_skin", "duplicate", "other")
SHOT_TYPES = ("overall", "medium", "close", "unknown")
IMAGING = ("rgb_phone", "wood_lamp", "dermoscopy", "unknown")
LIGHTING = ("indoor", "outdoor", "flash", "mixed", "unknown")
SIGNS = (
    "confetti",
    "hypochromic_border",
    "inflammatory_border",
    "leukotrichia",
    "linear",
    "cosmetic_or_sunburn",
)
TRISTATE = ("yes", "no", "unknown")


def _choice(value: Any, allowed: tuple, field: str) -> str:
    value = value or "unknown"
    if value not in allowed:
        raise RGBSegmentationError("INVALID_REQUEST", "字段 %s 取值无效" % field)
    return value


def normalize_attributes(raw: Dict[str, Any]) -> Dict[str, Any]:
    raw = raw or {}
    issues = raw.get("quality_issues") or []
    if not isinstance(issues, list) or any(i not in QUALITY_ISSUES for i in issues):
        raise RGBSegmentationError("INVALID_REQUEST", "质量问题取值无效")
    tone = raw.get("monk_skin_tone")
    if tone is not None and (not isinstance(tone, int) or not 1 <= tone <= 10):
        raise RGBSegmentationError("INVALID_REQUEST", "Monk 肤色需为 1~10 或不确定")
    signs = raw.get("signs") or {}
    if not isinstance(signs, dict) or any(k not in SIGNS for k in signs):
        raise RGBSegmentationError("INVALID_REQUEST", "可见体征字段无效")
    site = raw.get("body_site")
    code = normalize(site) if site else None
    if site and code is None:
        raise RGBSegmentationError("INVALID_REQUEST", "身体部位无效")
    notes = (raw.get("notes") or "").strip()
    if len(notes) > 500:
        raise RGBSegmentationError("INVALID_REQUEST", "备注不超过 500 字")
    return {
        "quality_issues": sorted(set(issues)),
        "shot_type": _choice(raw.get("shot_type"), SHOT_TYPES, "shot_type"),
        "imaging": _choice(raw.get("imaging"), IMAGING, "imaging"),
        "lighting": _choice(raw.get("lighting"), LIGHTING, "lighting"),
        "monk_skin_tone": tone,
        "body_site": code,
        "signs": {k: _choice(signs.get(k), TRISTATE, k) for k in SIGNS},
        "escalate": bool(raw.get("escalate")),
        "notes": notes,
    }


def normalize_reasons(reasons: List[str]) -> List[str]:
    if not reasons or any(r not in REJECT_REASONS for r in reasons):
        raise RGBSegmentationError("INVALID_REQUEST", "请选择不可用原因")
    return sorted(set(reasons))


def choices() -> Dict[str, Any]:
    return {
        "guideline_version": GUIDELINE_VERSION,
        "quality_issues": list(QUALITY_ISSUES),
        "reject_reasons": list(REJECT_REASONS),
        "shot_types": list(SHOT_TYPES),
        "imaging": list(IMAGING),
        "lighting": list(LIGHTING),
        "signs": list(SIGNS),
    }
