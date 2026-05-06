import logging
import os
import re
from typing import Any, Dict, List, Optional

from web.backend.services.medical.knowledge_base import knowledge_base

logger = logging.getLogger(__name__)

SUPERSCRIPT_MAP = str.maketrans(
    {
        "⁰": "0",
        "¹": "1",
        "²": "2",
        "³": "3",
        "⁴": "4",
        "⁵": "5",
        "⁶": "6",
        "⁷": "7",
        "⁸": "8",
        "⁹": "9",
    }
)

CANONICAL_INDICATORS: Dict[str, Dict[str, Any]] = {
    "ALT": {
        "canonical_name": "ALT",
        "aliases": ["谷丙转氨酶", "丙氨酸氨基转移酶", "GPT", "ALT"],
        "unit_family": "enzyme_u_l",
        "panel": "liver",
    },
    "AST": {
        "canonical_name": "AST",
        "aliases": ["谷草转氨酶", "天门冬氨酸氨基转移酶", "GOT", "AST"],
        "unit_family": "enzyme_u_l",
        "panel": "liver",
    },
    "WBC": {
        "canonical_name": "WBC",
        "aliases": ["白细胞计数", "白细胞", "WBC"],
        "unit_family": "count_10e9_l",
        "panel": "cbc",
    },
    "RBC": {
        "canonical_name": "RBC",
        "aliases": ["红细胞计数", "红细胞", "RBC"],
        "unit_family": "count_10e12_l",
        "panel": "cbc",
    },
    "HGB": {
        "canonical_name": "HGB",
        "aliases": ["血红蛋白", "血红蛋白浓度", "HGB", "Hb"],
        "unit_family": "mass_g_l",
        "panel": "cbc",
    },
    "PLT": {
        "canonical_name": "PLT",
        "aliases": ["血小板计数", "血小板", "PLT"],
        "unit_family": "count_10e9_l",
        "panel": "cbc",
    },
    "GLU": {
        "canonical_name": "GLU",
        "aliases": ["血糖", "葡萄糖", "GLU", "GLUCOSE"],
        "unit_family": "mmol_l",
        "panel": "glucose",
    },
    "TC": {
        "canonical_name": "TC",
        "aliases": ["总胆固醇", "TC", "CHO"],
        "unit_family": "mmol_l",
        "panel": "lipid",
    },
    "TG": {
        "canonical_name": "TG",
        "aliases": ["甘油三酯", "TG"],
        "unit_family": "mmol_l",
        "panel": "lipid",
    },
    "UA": {
        "canonical_name": "UA",
        "aliases": ["尿酸", "UA"],
        "unit_family": "umol_l",
        "panel": "renal",
    },
    "CREA": {
        "canonical_name": "CREA",
        "aliases": ["肌酐", "CREA", "CRE", "Cr"],
        "unit_family": "umol_l",
        "panel": "renal",
    },
    "BUN": {
        "canonical_name": "BUN",
        "aliases": ["尿素氮", "尿素", "BUN", "UREA"],
        "unit_family": "mmol_l",
        "panel": "renal",
    },
    "TSH": {
        "canonical_name": "TSH",
        "aliases": ["促甲状腺激素", "TSH"],
        "unit_family": "miu_l",
        "panel": "thyroid",
    },
    "FT3": {
        "canonical_name": "FT3",
        "aliases": ["游离T3", "游离三碘甲状腺原氨酸", "FT3"],
        "unit_family": "pmol_l",
        "panel": "thyroid",
    },
    "FT4": {
        "canonical_name": "FT4",
        "aliases": ["游离T4", "游离甲状腺素", "FT4"],
        "unit_family": "pmol_l",
        "panel": "thyroid",
    },
    "TP": {
        "canonical_name": "TP",
        "aliases": ["总蛋白", "TP"],
        "unit_family": "mass_g_l",
        "panel": "liver",
    },
    "ALB": {
        "canonical_name": "ALB",
        "aliases": ["白蛋白", "ALB"],
        "unit_family": "mass_g_l",
        "panel": "liver",
    },
    "TBIL": {
        "canonical_name": "TBIL",
        "aliases": ["总胆红素", "TBIL", "TB"],
        "unit_family": "umol_l",
        "panel": "liver",
    },
    "DBIL": {
        "canonical_name": "DBIL",
        "aliases": ["直接胆红素", "DBIL", "DB"],
        "unit_family": "umol_l",
        "panel": "liver",
    },
}

SECTION_DEFINITIONS: List[Dict[str, Any]] = [
    {"section_name": "血常规", "panel": "cbc", "aliases": ["血常规", "血液分析", "血细胞分析"]},
    {"section_name": "尿常规", "panel": "urinalysis", "aliases": ["尿常规", "尿液分析", "尿沉渣"]},
    {"section_name": "肝功能", "panel": "liver", "aliases": ["肝功能", "肝功", "肝功能检查"]},
    {"section_name": "肾功能", "panel": "renal", "aliases": ["肾功能", "肾功", "肾功能检查"]},
    {"section_name": "血脂", "panel": "lipid", "aliases": ["血脂", "血脂检查", "血脂分析"]},
    {"section_name": "血糖", "panel": "glucose", "aliases": ["血糖", "葡萄糖", "糖代谢"]},
    {"section_name": "甲状腺功能", "panel": "thyroid", "aliases": ["甲状腺功能", "甲功", "甲状腺功能检查"]},
    {"section_name": "彩超", "panel": "ultrasound", "aliases": ["彩超", "超声", "超声检查", "B超"]},
]

SECTION_LOOKUP: Dict[str, Dict[str, Any]] = {}
for section_info in SECTION_DEFINITIONS:
    for alias in section_info["aliases"]:
        SECTION_LOOKUP[alias.lower()] = section_info

INDICATOR_LOOKUP: Dict[str, Dict[str, Any]] = {}
for indicator_info in CANONICAL_INDICATORS.values():
    for alias in indicator_info["aliases"]:
        INDICATOR_LOOKUP[alias.lower()] = indicator_info


class ReportParser:
    def detect_sections(self, text: str) -> List[Dict[str, Any]]:
        lines = [self._normalize_line(line) for line in text.split("\n")]
        sections: List[Dict[str, Any]] = []
        current: Optional[Dict[str, Any]] = None

        for index, line in enumerate(lines):
            header_info = self._match_section_header(line)
            if header_info:
                if current is not None:
                    current["end_line"] = index - 1
                    current["text"] = "\n".join(current.pop("_lines"))
                    sections.append(current)

                current = {
                    "section_name": header_info["section_name"],
                    "panel": header_info["panel"],
                    "start_line": index,
                    "end_line": index,
                    "_lines": [line],
                }
                continue

            if current is not None:
                current["_lines"].append(line)

        if current is not None:
            current["end_line"] = len(lines) - 1
            current["text"] = "\n".join(current.pop("_lines"))
            sections.append(current)

        return sections

    def normalize_indicator(self, name: str) -> Optional[Dict[str, Any]]:
        normalized_name = self._normalize_indicator_key(name)
        indicator = INDICATOR_LOOKUP.get(normalized_name.lower())
        if not indicator:
            return None
        return {
            "canonical_name": indicator["canonical_name"],
            "aliases": list(indicator["aliases"]),
            "unit_family": indicator["unit_family"],
            "panel": indicator["panel"],
        }

    def parse(self, file_path: str) -> List[Dict[str, Any]]:
        ext = os.path.splitext(file_path)[1].lower()
        if ext == ".pdf":
            return self._parse_pdf(file_path)
        if ext in (".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp"):
            return self._parse_image(file_path)
        logger.warning("Unsupported file type: %s", ext)
        return []

    def _parse_pdf(self, file_path: str) -> List[Dict[str, Any]]:
        text = self._extract_pdf_text(file_path)
        if text.strip():
            return self._extract_indicators_from_text(text)

        table_text = self._extract_pdf_tables(file_path)
        if table_text.strip():
            return self._extract_indicators_from_text(table_text)

        logger.warning("No text extracted from PDF: %s", file_path)
        return []

    def _extract_pdf_text(self, file_path: str) -> str:
        try:
            import fitz

            doc = fitz.open(file_path)
            text_parts: List[str] = []
            for page in doc:
                get_text = getattr(page, "get_text", None)
                if callable(get_text):
                    text_parts.append(str(get_text()))
            doc.close()
            return "\n".join(text_parts)
        except Exception as exc:
            logger.warning("PyMuPDF extraction failed: %s", exc)
            return ""

    def _extract_pdf_tables(self, file_path: str) -> str:
        try:
            import pdfplumber

            text_parts: List[str] = []
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    tables = page.extract_tables()
                    for table in tables:
                        for row in table:
                            if row:
                                text_parts.append("\t".join(str(c or "") for c in row))
            return "\n".join(text_parts)
        except Exception as exc:
            logger.warning("pdfplumber table extraction failed: %s", exc)
            return ""

    def _parse_image(self, file_path: str) -> List[Dict[str, Any]]:
        ocr_text = self._ocr_image(file_path)
        if ocr_text.strip():
            return self._extract_indicators_from_text(ocr_text)
        return []

    def _ocr_image(self, file_path: str) -> str:
        try:
            from paddleocr import PaddleOCR

            ocr = PaddleOCR(use_angle_cls=True, lang="ch", show_log=False)
            result = ocr.ocr(file_path, cls=True)
            text_parts: List[str] = []
            if result and result[0]:
                for line in result[0]:
                    if line and len(line) >= 2:
                        text_parts.append(str(line[1][0]))
            return "\n".join(text_parts)
        except Exception as exc:
            logger.warning("PaddleOCR failed (image OCR unavailable): %s", exc)
            return ""

    def _extract_indicators_from_text(self, text: str) -> List[Dict[str, Any]]:
        indicators: List[Dict[str, Any]] = []
        seen_names: set[str] = set()

        current_section: Optional[Dict[str, Any]] = None
        section_by_line: Dict[int, Dict[str, Any]] = {}
        for section in self.detect_sections(text):
            for line_index in range(section["start_line"], section["end_line"] + 1):
                section_by_line[line_index] = section

        lines = text.split("\n")
        for index, line in enumerate(lines):
            current_section = section_by_line.get(index, current_section)
            parsed_items = self._extract_indicators_from_line(line, current_section)
            for parsed in parsed_items:
                key = parsed.get("canonical_name") or parsed["name"]
                if key in seen_names:
                    continue
                seen_names.add(key)
                indicators.append(parsed)

        return indicators

    def _extract_indicators_from_line(
        self,
        line: str,
        section: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        raw_normalized_line = self._normalize_line(line, preserve_delimiters=True)
        normalized_line = self._normalize_line(line)
        if not normalized_line or self._match_section_header(normalized_line):
            return []

        parsed_items = self._parse_multi_indicator_line(raw_normalized_line, section)
        if parsed_items:
            return parsed_items

        single_item = self._parse_indicator_line(normalized_line, section)
        if single_item:
            return [single_item]

        return []

    def _parse_indicator_line(
        self,
        line: str,
        section: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        line = self._normalize_line(line)
        if not line or len(line) < 3:
            return None

        colon_parts = re.split(r"[:：]", line, maxsplit=1)
        if len(colon_parts) == 2 and not re.search(r"\d", colon_parts[0]):
            return None

        # Strategy: find the first numeric value, everything before is name, after is unit+range
        value_match = re.search(
            r"([<>↓↑]?\s*[\d.]+(?:[eE][+-]?\d+)?)",
            line,
        )
        if not value_match:
            return None

        raw_name = line[:value_match.start()].strip()
        raw_value = value_match.group(1).strip()
        rest = line[value_match.end():].strip()

        if not raw_name:
            return None

        raw_name = raw_name.strip("|：: ")
        raw_name = re.sub(r"\b(结果|单位|参考范围|参考值|项目名称|项目)\b", "", raw_name).strip()
        if not raw_name:
            return None

        # Clean name: remove trailing parentheses content like (HGB)
        clean_name = raw_name
        paren_match = re.search(r"\(([A-Za-z]+)\)$", raw_name)
        if paren_match:
            clean_name = raw_name[:paren_match.start()].strip()
            alias = paren_match.group(1)
            normalized = knowledge_base.normalize_name(alias)
            if normalized != alias:
                clean_name = alias

        normalized_name = knowledge_base.normalize_name(clean_name)
        if normalized_name == clean_name and raw_name != clean_name:
            normalized_name = knowledge_base.normalize_name(raw_name)

        value = self._normalize_value(raw_value)
        if value is None:
            return None

        canonical_info = self.normalize_indicator(raw_name)
        if canonical_info is None and clean_name != raw_name:
            canonical_info = self.normalize_indicator(clean_name)
        if canonical_info is None and normalized_name != raw_name:
            canonical_info = self.normalize_indicator(normalized_name)

        ref = knowledge_base.get_reference(normalized_name)
        ref_min: Optional[float] = None
        ref_max: Optional[float] = None
        unit: str = ""
        if ref:
            ref_min = ref.get("ref_min")
            ref_max = ref.get("ref_max")
            unit = ref.get("unit", "")

        # Try to extract unit from rest of line
        unit_from_line = self._extract_unit(rest)
        if unit_from_line:
            unit = unit_from_line

        # Try to extract reference range from rest of line
        range_match = re.search(r"([\d.]+)\s*[-–—~～]\s*([\d.]+)", rest)
        if range_match:
            try:
                ref_min = float(range_match.group(1))
                ref_max = float(range_match.group(2))
            except ValueError:
                pass

        status = self._determine_status(value, ref_min, ref_max)

        indicator: Dict[str, Any] = {
            "name": normalized_name,
            "raw_name": raw_name,
            "value": value,
            "raw_value": raw_value,
            "unit": unit,
            "ref_min": ref_min,
            "ref_max": ref_max,
            "status": status,
        }

        if section is not None:
            indicator["section_name"] = section["section_name"]
            indicator["section_panel"] = section["panel"]

        if canonical_info is not None:
            indicator["canonical_name"] = canonical_info["canonical_name"]
            indicator["aliases"] = canonical_info["aliases"]
            indicator["unit_family"] = canonical_info["unit_family"]
            indicator["panel"] = canonical_info["panel"]
        elif section is not None:
            indicator["panel"] = section["panel"]

        return indicator

    def _parse_multi_indicator_line(
        self,
        line: str,
        section: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        parsed_items: List[Dict[str, Any]] = []
        tokens = [token.strip() for token in re.split(r"\t+|\s{2,}", line) if token.strip()]

        if len(tokens) >= 2:
            index = 0
            while index < len(tokens) - 1:
                name_token = tokens[index]
                if self._looks_like_header_token(name_token):
                    index += 1
                    continue

                value_token = tokens[index + 1] if index + 1 < len(tokens) else ""
                if self._contains_numeric_value(value_token):
                    combined_parts = [name_token, value_token]
                    consumed = 2
                    if index + 2 < len(tokens) and not self._looks_like_name_token(tokens[index + 2]):
                        combined_parts.append(tokens[index + 2])
                        consumed += 1
                    if index + 3 < len(tokens) and self._looks_like_range_token(tokens[index + 3]):
                        combined_parts.append(tokens[index + 3])
                        consumed += 1
                    parsed = self._parse_indicator_line(" ".join(combined_parts), section)
                    if parsed is not None:
                        parsed_items.append(parsed)
                        index += consumed
                        continue

                index += 1

        if parsed_items:
            return parsed_items

        colon_matches = re.finditer(
            r"([A-Za-z\u4e00-\u9fff()（）/·+-]{2,})\s*[:：]\s*([<>↓↑]?\s*[\d.]+(?:[eE][+-]?\d+)?)\s*([^\s]+)?",
            line,
        )
        for match in colon_matches:
            parsed = self._parse_indicator_line(
                "{0} {1} {2}".format(
                    match.group(1),
                    match.group(2),
                    match.group(3) or "",
                ).strip(),
                section,
            )
            if parsed is not None:
                parsed_items.append(parsed)

        return parsed_items

    def _normalize_value(self, raw: str) -> Optional[float]:
        cleaned = raw.strip()
        cleaned = re.sub(r"^[<>↓↑]\s*", "", cleaned)
        cleaned = cleaned.replace(",", "")
        try:
            return float(cleaned)
        except ValueError:
            return None

    def _determine_status(
        self, value: float, ref_min: Optional[float], ref_max: Optional[float]
    ) -> str:
        if ref_min is None and ref_max is None:
            return "unknown"
        if ref_min is not None and value < ref_min:
            return "low"
        if ref_max is not None and value > ref_max:
            return "high"
        return "normal"

    def _extract_unit(self, text: str) -> str:
        patterns = [
            r"([x×]\s*10\^?\d+/L|10\^?\d+/L)",
            r"(μ?mol/L|mmol/L|g/L|mg/L|U/L|pmol/L|nmol/L|mIU/L|%)",
            r"(fL|pg)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1)
        return ""

    def _normalize_line(self, line: str, preserve_delimiters: bool = False) -> str:
        normalized = line.translate(SUPERSCRIPT_MAP)
        normalized = normalized.replace("×", "x")
        normalized = normalized.replace("＊", "*")
        normalized = normalized.replace("（", "(").replace("）", ")")
        normalized = normalized.replace("／", "/")
        normalized = normalized.replace("\u3000", " ")
        if preserve_delimiters:
            normalized = re.sub(r"\r", "", normalized)
        else:
            normalized = re.sub(r"\s+", " ", normalized)
        return normalized.strip()

    def _normalize_indicator_key(self, name: str) -> str:
        normalized = self._normalize_line(name)
        normalized = re.sub(r"\([^)]*\)", "", normalized).strip()
        return normalized

    def _match_section_header(self, line: str) -> Optional[Dict[str, Any]]:
        candidate = self._normalize_line(line)
        if not candidate or len(candidate) > 30:
            return None

        candidate = re.sub(r"[:：].*$", "", candidate).strip()
        candidate = re.sub(r"[一二三四五六七八九十0-9]+[、.)）-]?", "", candidate).strip()
        candidate = candidate.replace("检查结果", "").replace("检验结果", "").strip()

        for alias, section in SECTION_LOOKUP.items():
            if candidate.lower() == alias or candidate.lower().startswith(alias):
                return {
                    "section_name": section["section_name"],
                    "panel": section["panel"],
                }

        return None

    def _contains_numeric_value(self, token: str) -> bool:
        return re.search(r"[<>↓↑]?\s*[\d.]+(?:[eE][+-]?\d+)?", token) is not None

    def _looks_like_header_token(self, token: str) -> bool:
        cleaned = self._normalize_line(token).lower()
        return cleaned in {
            "项目名称",
            "项目",
            "结果",
            "单位",
            "参考范围",
            "参考值",
            "检测项目",
        }

    def _looks_like_name_token(self, token: str) -> bool:
        cleaned = self._normalize_line(token)
        return bool(cleaned) and not self._contains_numeric_value(cleaned)

    def _looks_like_range_token(self, token: str) -> bool:
        cleaned = self._normalize_line(token)
        return re.search(r"[\d.]+\s*[-–—~～]\s*[\d.]+", cleaned) is not None


report_parser = ReportParser()
