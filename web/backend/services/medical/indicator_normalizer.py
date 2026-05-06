import re
from datetime import datetime
from typing import Any, Dict, List, Optional


CANONICAL_INDICATORS = {
    "ALT": {
        "display_name": "谷丙转氨酶",
        "aliases": ["谷丙转氨酶", "丙氨酸氨基转移酶", "Alanine Aminotransferase", "ALT", "GPT"],
        "unit_family": "U/L",
        "panel": "liver",
    },
    "AST": {
        "display_name": "谷草转氨酶",
        "aliases": ["谷草转氨酶", "天门冬氨酸氨基转移酶", "Aspartate Aminotransferase", "AST", "GOT"],
        "unit_family": "U/L",
        "panel": "liver",
    },
    "WBC": {
        "display_name": "白细胞计数",
        "aliases": ["白细胞计数", "白细胞", "White Blood Cell", "WBC", "LEU"],
        "unit_family": "10^9/L",
        "panel": "cbc",
    },
    "RBC": {
        "display_name": "红细胞计数",
        "aliases": ["红细胞计数", "红细胞", "Red Blood Cell", "RBC"],
        "unit_family": "10^12/L",
        "panel": "cbc",
    },
    "HGB": {
        "display_name": "血红蛋白",
        "aliases": ["血红蛋白", "Hemoglobin", "HGB"],
        "unit_family": "g/L",
        "panel": "cbc",
    },
    "PLT": {
        "display_name": "血小板计数",
        "aliases": ["血小板计数", "血小板", "Platelet", "PLT"],
        "unit_family": "10^9/L",
        "panel": "cbc",
    },
    "GLU": {
        "display_name": "血糖",
        "aliases": ["血糖", "葡萄糖", "Glucose", "GLU"],
        "unit_family": "mmol/L",
        "panel": "glucose",
    },
    "TC": {
        "display_name": "总胆固醇",
        "aliases": ["总胆固醇", "Total Cholesterol", "TC", "CHOL"],
        "unit_family": "mmol/L",
        "panel": "lipid",
    },
    "TG": {
        "display_name": "甘油三酯",
        "aliases": ["甘油三酯", "Triglyceride", "TG"],
        "unit_family": "mmol/L",
        "panel": "lipid",
    },
    "HDL": {
        "display_name": "高密度脂蛋白",
        "aliases": ["高密度脂蛋白胆固醇", "HDL-C", "HDL"],
        "unit_family": "mmol/L",
        "panel": "lipid",
    },
    "LDL": {
        "display_name": "低密度脂蛋白",
        "aliases": ["低密度脂蛋白胆固醇", "LDL-C", "LDL"],
        "unit_family": "mmol/L",
        "panel": "lipid",
    },
    "UA": {
        "display_name": "尿酸",
        "aliases": ["尿酸", "Uric Acid", "UA"],
        "unit_family": "μmol/L",
        "panel": "renal",
    },
    "CREA": {
        "display_name": "肌酐",
        "aliases": ["肌酐", "Creatinine", "CREA", "CR"],
        "unit_family": "μmol/L",
        "panel": "renal",
    },
    "BUN": {
        "display_name": "尿素氮",
        "aliases": ["尿素氮", "尿素", "BUN", "UREA"],
        "unit_family": "mmol/L",
        "panel": "renal",
    },
    "TSH": {
        "display_name": "促甲状腺激素",
        "aliases": ["促甲状腺激素", "TSH", "Thyroid Stimulating Hormone"],
        "unit_family": "mIU/L",
        "panel": "thyroid",
    },
    "FT3": {
        "display_name": "游离T3",
        "aliases": ["游离T3", "FT3", "Free T3"],
        "unit_family": "pmol/L",
        "panel": "thyroid",
    },
    "FT4": {
        "display_name": "游离T4",
        "aliases": ["游离T4", "FT4", "Free T4"],
        "unit_family": "pmol/L",
        "panel": "thyroid",
    },
    "TP": {
        "display_name": "总蛋白",
        "aliases": ["总蛋白", "Total Protein", "TP"],
        "unit_family": "g/L",
        "panel": "liver",
    },
    "ALB": {
        "display_name": "白蛋白",
        "aliases": ["白蛋白", "Albumin", "ALB"],
        "unit_family": "g/L",
        "panel": "liver",
    },
    "TBIL": {
        "display_name": "总胆红素",
        "aliases": ["总胆红素", "Total Bilirubin", "TBIL"],
        "unit_family": "μmol/L",
        "panel": "liver",
    },
    "DBIL": {
        "display_name": "直接胆红素",
        "aliases": ["直接胆红素", "Direct Bilirubin", "DBIL"],
        "unit_family": "μmol/L",
        "panel": "liver",
    },
    "GGT": {
        "display_name": "γ-谷氨酰转移酶",
        "aliases": ["γ-谷氨酰转移酶", "谷氨酰转移酶", "GGT", "γ-GT"],
        "unit_family": "U/L",
        "panel": "liver",
    },
    "ALP": {
        "display_name": "碱性磷酸酶",
        "aliases": ["碱性磷酸酶", "Alkaline Phosphatase", "ALP"],
        "unit_family": "U/L",
        "panel": "liver",
    },
    "NEUT": {
        "display_name": "中性粒细胞计数",
        "aliases": ["中性粒细胞计数", "中性粒细胞", "NEUT"],
        "unit_family": "10^9/L",
        "panel": "cbc",
    },
    "LYMPH": {
        "display_name": "淋巴细胞计数",
        "aliases": ["淋巴细胞计数", "淋巴细胞", "LYMPH"],
        "unit_family": "10^9/L",
        "panel": "cbc",
    },
    "HCT": {
        "display_name": "红细胞比积",
        "aliases": ["红细胞比积", "红细胞压积", "Hematocrit", "HCT"],
        "unit_family": "%",
        "panel": "cbc",
    },
    "MCV": {
        "display_name": "平均红细胞体积",
        "aliases": ["平均红细胞体积", "Mean Corpuscular Volume", "MCV"],
        "unit_family": "fL",
        "panel": "cbc",
    },
    "CRP": {
        "display_name": "C反应蛋白",
        "aliases": ["C反应蛋白", "C-Reactive Protein", "CRP"],
        "unit_family": "mg/L",
        "panel": "inflammation",
    },
    "HbA1c": {
        "display_name": "糖化血红蛋白",
        "aliases": ["糖化血红蛋白", "HbA1c", "Glycated Hemoglobin"],
        "unit_family": "%",
        "panel": "glucose",
    },
    "VITD": {
        "display_name": "维生素D",
        "aliases": ["维生素D", "25-羟维生素D", "Vitamin D", "25(OH)D", "VITD"],
        "unit_family": "ng/mL",
        "panel": "vitamin",
    },
}


def _normalize_text(value: str) -> str:
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", value.lower())


EXACT_ALIAS_MAP = {}
NORMALIZED_ALIAS_MAP = {}
for canonical_name, info in CANONICAL_INDICATORS.items():
    all_aliases = list(info.get("aliases", [])) + [canonical_name, info.get("display_name", canonical_name)]
    for alias in all_aliases:
        EXACT_ALIAS_MAP[str(alias)] = canonical_name
        NORMALIZED_ALIAS_MAP[_normalize_text(str(alias))] = canonical_name


def normalize_indicator_name(name: str) -> Optional[Dict[str, Any]]:
    indicator_name = str(name or "").strip()
    if not indicator_name:
        return None

    canonical_name = EXACT_ALIAS_MAP.get(indicator_name)
    if canonical_name is None:
        canonical_name = NORMALIZED_ALIAS_MAP.get(_normalize_text(indicator_name))
    if canonical_name is None:
        return None

    info = dict(CANONICAL_INDICATORS[canonical_name])
    info["canonical_name"] = canonical_name
    return info


def _extract_numeric_value(value: Any) -> Optional[float]:
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value or "").strip()
    if not text:
        return None
    match = re.search(r"[-+]?\d+(?:\.\d+)?", text)
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None


def _build_ref_range(indicator: Dict[str, Any]) -> str:
    ref_range = indicator.get("ref_range")
    if ref_range not in (None, ""):
        return str(ref_range)

    ref_min = indicator.get("ref_min")
    ref_max = indicator.get("ref_max")
    if ref_min is None and ref_max is None:
        return ""
    if ref_min is None:
        return "<=%s" % ref_max
    if ref_max is None:
        return ">=%s" % ref_min
    return "%s-%s" % (ref_min, ref_max)


def _normalize_status(status: Any) -> str:
    text = str(status or "unknown").strip().lower()
    if text in ("normal", "high", "low", "critical"):
        return text
    return "unknown"


def _stringify_value(indicator: Dict[str, Any]) -> str:
    value = indicator.get("value")
    unit = str(indicator.get("unit") or "").strip()
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        value_text = str(int(value))
    else:
        value_text = str(value)
    return ("%s %s" % (value_text, unit)).strip()


def _normalize_indicator_record(
    indicator: Dict[str, Any], report_id: Optional[int] = None
) -> Dict[str, Any]:
    indicator_name = str(
        indicator.get("indicator_name")
        or indicator.get("name")
        or indicator.get("raw_name")
        or ""
    ).strip()
    canonical = normalize_indicator_name(indicator_name)
    numeric_value = _extract_numeric_value(indicator.get("value"))
    measured = bool(indicator_name or indicator.get("value") not in (None, ""))

    return {
        "report_id": report_id,
        "indicator_name": indicator_name,
        "canonical_name": canonical.get("canonical_name") if canonical else None,
        "display_name": canonical.get("display_name") if canonical else indicator_name,
        "panel": canonical.get("panel") if canonical else "other",
        "unit_family": canonical.get("unit_family") if canonical else str(indicator.get("unit") or "").strip() or None,
        "value": _stringify_value(indicator),
        "numeric_value": numeric_value,
        "status": _normalize_status(indicator.get("status")),
        "ref_range": _build_ref_range(indicator),
        "measured": measured,
    }


def _placeholder_value(report_id: Optional[int]) -> Dict[str, Any]:
    return {
        "report_id": report_id,
        "indicator_name": "",
        "canonical_name": None,
        "display_name": "",
        "panel": "other",
        "unit_family": None,
        "value": "",
        "numeric_value": None,
        "status": "unknown",
        "ref_range": "",
        "measured": False,
    }


def align_indicators(report_indicators: List[List[Dict[str, Any]]]) -> Dict[str, Any]:
    report_count = len(report_indicators)
    aligned_map: Dict[str, Dict[str, Any]] = {}

    for report_index, indicators in enumerate(report_indicators):
        for indicator in indicators:
            if not isinstance(indicator, dict):
                continue
            normalized = _normalize_indicator_record(indicator)
            key = normalized.get("canonical_name") or _normalize_text(normalized.get("indicator_name") or "")
            if not key:
                continue

            if key not in aligned_map:
                aligned_map[key] = {
                    "canonical_name": normalized.get("canonical_name"),
                    "display_name": normalized.get("display_name") or normalized.get("indicator_name"),
                    "panel": normalized.get("panel") or "other",
                    "unit_family": normalized.get("unit_family"),
                    "values": [_placeholder_value(None) for _ in range(report_count)],
                }
            if aligned_map[key]["values"][report_index].get("measured"):
                continue
            aligned_map[key]["values"][report_index] = normalized

    aligned_items: List[Dict[str, Any]] = []
    for item in aligned_map.values():
        for idx in range(report_count):
            value = item["values"][idx]
            if value.get("report_id") is None:
                placeholder = _placeholder_value(None)
                placeholder["canonical_name"] = item.get("canonical_name")
                placeholder["display_name"] = item.get("display_name")
                placeholder["panel"] = item.get("panel")
                placeholder["unit_family"] = item.get("unit_family")
                item["values"][idx] = placeholder
        aligned_items.append(item)

    aligned_items.sort(key=lambda item: (str(item.get("panel") or "other"), str(item.get("display_name") or "")))
    return {
        "report_count": report_count,
        "aligned_indicators": aligned_items,
    }


def _is_abnormal(value: Dict[str, Any]) -> bool:
    return str(value.get("status") or "").lower() in ("high", "low", "critical")


def _has_large_delta(first: Dict[str, Any], last: Dict[str, Any]) -> bool:
    first_value = first.get("numeric_value")
    last_value = last.get("numeric_value")
    if first_value is None or last_value is None:
        return False

    delta = abs(last_value - first_value)
    baseline = abs(first_value)
    if baseline > 0 and (delta / baseline) >= 0.2:
        return True

    ref_range = str(last.get("ref_range") or first.get("ref_range") or "")
    range_match = re.search(r"([-+]?\d+(?:\.\d+)?)\s*[-–—~～]\s*([-+]?\d+(?:\.\d+)?)", ref_range)
    if range_match:
        try:
            range_width = abs(float(range_match.group(2)) - float(range_match.group(1)))
            if range_width > 0 and delta >= (range_width * 0.5):
                return True
        except ValueError:
            return False
    return False


def classify_change(values: List[Dict[str, Any]]) -> str:
    measured_values = [value for value in values if value.get("measured")]
    if len(measured_values) < 2:
        return "not_measured"

    first = measured_values[0]
    last = measured_values[-1]
    first_abnormal = _is_abnormal(first)
    last_abnormal = _is_abnormal(last)

    if not first_abnormal and last_abnormal:
        return "newly_abnormal"
    if first_abnormal and not last_abnormal:
        return "resolved_abnormal"
    if first_abnormal and last_abnormal:
        return "persistent_abnormal"
    if _has_large_delta(first, last):
        return "large_delta"
    return "unchanged_stable"


def compute_comparison(
    report_ids: List[int], report_indicators_map: Dict[int, List[Dict[str, Any]]]
) -> Dict[str, Any]:
    ordered_indicators = [report_indicators_map.get(report_id, []) for report_id in report_ids]
    aligned = align_indicators(ordered_indicators)

    change_summary = {
        "newly_abnormal": 0,
        "resolved_abnormal": 0,
        "persistent_abnormal": 0,
        "large_delta": 0,
        "unchanged_stable": 0,
        "not_measured": 0,
    }
    aligned_indicators: List[Dict[str, Any]] = []
    highlights: List[Dict[str, Any]] = []

    for item in aligned.get("aligned_indicators", []):
        values: List[Dict[str, Any]] = []
        for index, value in enumerate(item.get("values", [])):
            normalized_value = dict(value)
            normalized_value["report_id"] = report_ids[index] if index < len(report_ids) else None
            values.append(normalized_value)

        change_type = classify_change(values)
        change_summary[change_type] += 1

        aligned_item = {
            "canonical_name": item.get("canonical_name"),
            "display_name": item.get("display_name"),
            "panel": item.get("panel"),
            "unit_family": item.get("unit_family"),
            "change_type": change_type,
            "values": values,
        }
        aligned_indicators.append(aligned_item)

        if change_type not in ("unchanged_stable", "not_measured"):
            highlights.append({
                "canonical_name": item.get("canonical_name"),
                "display_name": item.get("display_name"),
                "panel": item.get("panel"),
                "change_type": change_type,
            })

    return {
        "schema_version": "1.0",
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "report_ids": report_ids,
        "report_count": len(report_ids),
        "change_summary": change_summary,
        "aligned_indicators": aligned_indicators,
        "highlights": highlights,
    }
