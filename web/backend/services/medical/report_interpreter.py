import base64
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, cast

import openai

from web.backend.services.medical.indicator_normalizer import normalize_indicator_name
from web.backend.services.medical.knowledge_base import knowledge_base
from web.backend.utils.llm_config import get_llm_config

logger = logging.getLogger(__name__)

DISCLAIMER = "以上解读由AI生成，仅供参考，不构成医疗诊断。请咨询医生获取专业意见。"


class ReportInterpreter:
    def interpret(
        self,
        indicators: List[Dict[str, Any]],
        raw_text: str = "",
        user_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        clean_text = (raw_text or "").strip()
        if not indicators and not clean_text:
            return self._empty_result(raw_text)

        if len(clean_text) >= 500:
            return self.interpret_full_text(clean_text[:30000], user_context)

        flagged = [i for i in indicators if i.get("status") not in ("normal", "unknown")]
        if not flagged and not indicators:
            return self._empty_result(raw_text)

        prompt = self._build_prompt(flagged, indicators, clean_text[:30000], user_context)
        result, model_name = self._call_llm_with_metadata(prompt, max_tokens=8192)

        if result is None:
            return self._fallback_result(flagged, indicators, model_name=model_name)

        return self._post_process(result, indicators, model_name=model_name)

    def interpret_full_text(
        self,
        full_text: str,
        user_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if not full_text or not full_text.strip():
            return self._empty_result(full_text)

        user_info = self._build_user_info(user_context)
        prompt = self._build_section_prompt(full_text[:30000], user_info)
        result, model_name = self._call_llm_with_metadata(prompt, max_tokens=8192)

        if result is None:
            return self._fallback_section_result(full_text, model_name=model_name)

        return self._post_process_sections(result, model_name=model_name)

    def interpret_for_comparison(
        self,
        report_data: Dict[str, Any],
        indicators: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        abnormal_items = report_data.get("abnormal_items", [])
        if not abnormal_items and isinstance(report_data.get("sections"), list):
            abnormal_items = self._flatten_section_abnormal_items(report_data.get("sections", []))

        compact_abnormal_items: List[Dict[str, Any]] = []
        for item in abnormal_items[:8]:
            normalized_item = self._normalize_abnormal_item(item)
            if normalized_item is not None:
                compact_abnormal_items.append({
                    "indicator_name": normalized_item.get("indicator_name"),
                    "status": normalized_item.get("status"),
                    "interpretation": normalized_item.get("interpretation"),
                    "confidence": normalized_item.get("confidence"),
                })

        compact_indicators: List[Dict[str, Any]] = []
        for indicator in indicators:
            normalized_indicator = self._normalize_parsed_indicator(indicator)
            if normalized_indicator is not None:
                compact_indicators.append({
                    "indicator_name": normalized_indicator.get("indicator_name"),
                    "canonical_name": normalized_indicator.get("canonical_name"),
                    "value": normalized_indicator.get("value"),
                    "status": normalized_indicator.get("status"),
                    "ref_range": normalized_indicator.get("ref_range"),
                    "unit_family": normalized_indicator.get("unit_family"),
                })

        return {
            "schema_version": "2.0",
            "risk_level": report_data.get("risk_level", "medium"),
            "summary": str(report_data.get("summary", "")).strip(),
            "abnormal_items": compact_abnormal_items,
            "normalized_indicators": compact_indicators,
            "extracted_patient_info": self._normalize_extracted_patient_info(
                report_data.get("extracted_patient_info")
            ),
        }

    def generate_comparison_narrative(
        self,
        comparison_data: Dict[str, Any],
        report_summaries: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        prompt = self._build_comparison_prompt(comparison_data, report_summaries)
        result, model_name = self._call_llm_with_metadata(prompt, max_tokens=4096)
        if result is None:
            return self._fallback_comparison_narrative(comparison_data, model_name=model_name)
        return self._post_process_comparison(result, comparison_data, model_name=model_name)

    def interpret_vision(
        self,
        image_data_list: List[bytes],
        user_context: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        config = get_llm_config()
        if config["provider"] == "none":
            logger.warning("LLM provider not configured, cannot use vision model")
            return None

        vision_model = config.get("vision_model", "qwen-vl-plus")
        client = openai.OpenAI(api_key=config["api_key"], base_url=config["base_url"])
        user_info = self._build_user_info(user_context)

        content: List[Dict[str, Any]] = []
        for img_bytes in image_data_list:
            b64 = base64.b64encode(img_bytes).decode("utf-8")
            mime = "image/jpeg"
            if img_bytes[:8] == b"\x89PNG\r\n\x1a\n":
                mime = "image/png"
            elif img_bytes[:4] == b"RIFF" and img_bytes[8:12] == b"WEBP":
                mime = "image/webp"
            content.append({
                "type": "image_url",
                "image_url": {"url": "data:%s;base64,%s" % (mime, b64)},
            })

        prompt = (
            "你是一位面向白癜风白友的体检报告解读助手。请仔细阅读这份体检报告图片，提取所有检验指标并给出解读。"
            "用户信息: %s\n\n"
            "请输出JSON，格式如下：\n"
            "{\n"
            '  "risk_level": "low" | "medium" | "high" | "critical",\n'
            '  "summary": "200字以内白友易懂总结",\n'
            '  "parsed_indicators": [\n'
            '    {"indicator_name": "指标名", "value": "检测值+单位", "status": "normal"/"high"/"low", "ref_range": "参考范围"}\n'
            "  ],\n"
            '  "abnormal_items": [\n'
            "    {\n"
            '      "indicator_name": "指标名",\n'
            '      "value": "检测值+单位",\n'
            '      "status": "high"/"low"/"critical",\n'
            '      "interpretation": "通俗解释这个指标异常意味着什么",\n'
            '      "possible_causes": ["可能原因1", "可能原因2"],\n'
            '      "suggestions": ["建议1", "建议2"]\n'
            "    }\n"
            "  ],\n"
            '  "recommendations": [\n'
            '    {"content": "具体可执行建议"}\n'
            "  ],\n"
            '  "disclaimer": "%s"\n'
            "}\n\n"
            "注意事项：\n"
            "1. 请尽可能提取图片中所有可见的检验指标，包括指标名称、检测值、单位、参考范围\n"
            "2. status判断：检测值在参考范围内为normal，偏高为high，偏低为low，严重偏离为critical\n"
            "3. 特别关注与白癜风相关的指标（甲状腺功能、免疫指标、肝功能、微量元素等）\n"
            "4. 如果图片不是体检报告或无法识别，返回包含空指标和上传建议的JSON\n"
            "5. 严格输出JSON，不要输出Markdown代码块或JSON以外的文字"
        ) % (user_info, DISCLAIMER)
        content.append({"type": "text", "text": prompt})

        try:
            logger.info(
                "Calling vision model for report interpretation: model=%s, images=%d",
                vision_model,
                len(image_data_list),
            )
            response = client.chat.completions.create(
                model=vision_model,
                messages=cast(Any, [{"role": "user", "content": content}]),
                temperature=0.1,
                max_tokens=4096,
            )
            resp_text = (response.choices[0].message.content or "").strip()
            if resp_text.startswith("```"):
                resp_text = resp_text.strip("`")
                if resp_text.startswith("json"):
                    resp_text = resp_text[4:].strip()

            result = json.loads(resp_text)
            if not isinstance(result, dict):
                logger.warning("Vision model returned non-dict: %s", type(result))
                return None

            return self._post_process(result, [], model_name=vision_model)
        except Exception as exc:
            logger.error("Vision model call failed in ReportInterpreter: %s", str(exc), exc_info=True)
            return None

    def _build_prompt(
        self,
        flagged: List[Dict[str, Any]],
        all_indicators: List[Dict[str, Any]],
        raw_text: str,
        user_context: Optional[Dict[str, Any]] = None,
    ) -> str:
        indicators_text = "\n".join(
            "- %s(%s): %s %s [参考: %s-%s, 状态: %s]" % (
                i.get("name", ""),
                i.get("raw_name", i.get("name", "")),
                i.get("value", ""),
                i.get("unit", ""),
                i.get("ref_min", "?"),
                i.get("ref_max", "?"),
                i.get("status", "unknown"),
            )
            for i in all_indicators
        )
        flagged_text = "\n".join(
            "- %s: %s %s (%s)" % (
                i.get("name", ""),
                i.get("value", ""),
                i.get("unit", ""),
                i.get("status", "unknown"),
            )
            for i in flagged
        )
        user_info = self._build_user_info(user_context)

        return (
            "请基于以下体检报告数据进行解读。\n\n"
            "用户信息: %s\n\n"
            "全部解析指标:\n%s\n\n"
            "异常/需关注指标:\n%s\n\n"
            "原始报告文本（部分）:\n%s\n\n"
            "请输出JSON，格式如下：\n"
            "{\n"
            '  "risk_level": "low" | "medium" | "high" | "critical",\n'
            '  "summary": "200字以内白友易懂总结",\n'
            '  "parsed_indicators": [\n'
            '    {"indicator_name": "指标名", "value": "检测值+单位", "status": "normal"/"high"/"low", "ref_range": "参考范围"}\n'
            "  ],\n"
            '  "abnormal_items": [\n'
            "    {\n"
            '      "indicator_name": "指标名",\n'
            '      "value": "检测值+单位",\n'
            '      "status": "high"/"low"/"critical",\n'
            '      "interpretation": "通俗解释这个指标异常意味着什么",\n'
            '      "possible_causes": ["可能原因1", "可能原因2"],\n'
            '      "suggestions": ["建议1", "建议2"]\n'
            "    }\n"
            "  ],\n"
            '  "recommendations": [\n'
            '    {"content": "具体可执行建议"}\n'
            "  ],\n"
            '  "disclaimer": "%s"\n'
            "}"
        ) % (
            user_info,
            indicators_text,
            flagged_text or "所有指标在参考范围内",
            raw_text[:2000],
            DISCLAIMER,
        )

    def _build_section_prompt(self, full_text: str, user_info: str) -> str:
        return (
            "你是一位专业的体检报告解读助手。请仔细阅读以下体检报告的完整内容，按检查项目分类进行解读。\n\n"
            "用户信息: %s\n\n"
            "报告完整内容:\n---\n%s\n---\n\n"
            "请按以下格式输出JSON（严格JSON，不要Markdown代码块）：\n\n"
            "{\n"
            '  "risk_level": "low|medium|high|critical",\n'
            '  "summary": "200字以内的总体总结",\n'
            '  "extracted_patient_info": {\n'
            '    "name": "张三",\n'
            '    "gender": "男",\n'
            '    "age": 35,\n'
            '    "confidence": 0.9\n'
            '  } | null,\n'
            '  "sections": [\n'
            "    {\n"
            '      "section_name": "血常规",\n'
            '      "risk": "green|yellow|red",\n'
            '      "indicator_count": 10,\n'
            '      "abnormal_count": 2,\n'
            '      "section_summary": "该部分总体情况简述",\n'
            '      "indicators": [\n'
            '        {"name": "白细胞计数", "value": "6.5", "unit": "10⁹/L", "ref_range": "3.5-9.5", "status": "normal"}\n'
            "      ],\n"
            '      "abnormal_items": [\n'
            "        {\n"
            '          "name": "血红蛋白",\n'
            '          "value": "105",\n'
            '          "unit": "g/L",\n'
            '          "ref_range": "115-150",\n'
            '          "status": "low",\n'
            '          "interpretation": "轻度贫血。血红蛋白偏低可能提示缺铁性贫血，在白癜风患者中需关注自身免疫因素。",\n'
            '          "possible_causes": ["缺铁性贫血", "慢性炎症", "自身免疫相关"],\n'
            '          "suggestions": ["建议检查血清铁蛋白", "增加富含铁的食物摄入", "3个月后复查血常规"],\n'
            '          "source_indicators": [\n'
            '            {"indicator_name": "血红蛋白", "value": "105 g/L", "ref_range": "115-150"}\n'
            '          ],\n'
            '          "source_text_excerpt": "血红蛋白 105 g/L 参考范围 115-150",\n'
            '          "confidence": 0.86\n'
            "        }\n"
            "      ]\n"
            "    }\n"
            "  ],\n"
            '  "all_indicators": [\n'
            '    {"name": "指标名", "value": "检测值", "unit": "单位", "ref_range": "参考范围", "status": "normal|high|low|critical"}\n'
            "  ],\n"
            '  "recommendations": [\n'
            '    {"content": "全局性建议1"},\n'
            '    {"content": "全局性建议2"}\n'
            "  ],\n"
            '  "disclaimer": "%s"\n'
            "}\n\n"
            "⚠️ 关键要求：\n"
            "1. 必须覆盖报告中出现的每一个检查项目；报告中的完整文本可使用到30000字符。\n"
            "2. 风险判定：red=危急值或多项严重异常；yellow=轻度异常或临界值；green=全部正常。\n"
            "3. 每个section的indicators必须包含该检查项目的所有指标（包括正常的）。\n"
            "4. 异常指标需要深度解读。对每个异常指标的解读，必须标注：(1) 支撑该结论的具体源指标 (2) 引用原文中的相关片段 (3) 置信度评分 (0-1)。\n"
            "5. extracted_patient_info 需要尽量从原始报告中提取姓名、性别、年龄，并给出置信度；若未发现则返回 null。\n"
            "6. 特别关注与白癜风相关的指标：甲状腺功能、免疫指标、肝功能、微量元素（铜、锌）、维生素D等。\n"
            "7. 如果某指标在参考范围边界附近，也应在section_summary中标记提醒。\n"
            "8. 严格输出JSON，不要输出任何Markdown标记或JSON之外的文字。"
        ) % (user_info, full_text[:30000], DISCLAIMER)

    def _build_comparison_prompt(
        self,
        comparison_data: Dict[str, Any],
        report_summaries: List[Dict[str, Any]],
    ) -> str:
        payload = json.dumps(
            {
                "comparison": comparison_data,
                "report_summaries": report_summaries,
            },
            ensure_ascii=False,
        )
        return (
            "请根据以下已经完成的体检指标变化计算结果，生成多份报告对比总结。\n"
            "不要重新解读原始指标，只能基于给定的变化计算结果输出。\n\n"
            "输入JSON:\n%s\n\n"
            "请输出JSON：\n"
            "{\n"
            '  "summary": "150字以内总结",\n'
            '  "key_changes": [\n'
            '    {"indicator_name": "指标名", "change_type": "newly_abnormal", "interpretation": "变化意义"}\n'
            "  ],\n"
            '  "recommendations": [\n'
            '    {"content": "后续建议"}\n'
            "  ]\n"
            "}\n\n"
            "要求：重点解释 newly_abnormal、resolved_abnormal、persistent_abnormal、large_delta 这几类变化。"
        ) % payload

    def _build_user_info(self, user_context: Optional[Dict[str, Any]]) -> str:
        context_parts: List[str] = []
        if user_context:
            if user_context.get("age"):
                context_parts.append("年龄: %s岁" % user_context["age"])
            if user_context.get("gender"):
                context_parts.append("性别: %s" % user_context["gender"])
        return "，".join(context_parts) if context_parts else "未提供"

    def _call_llm(self, prompt: str, max_tokens: int = 8192) -> Optional[Dict[str, Any]]:
        result, _model_name = self._call_llm_with_metadata(prompt, max_tokens=max_tokens)
        return result

    def _call_llm_with_metadata(
        self, prompt: str, max_tokens: int = 8192
    ) -> Tuple[Optional[Dict[str, Any]], str]:
        config = get_llm_config()
        model_name = config.get("chat_model", "unknown")
        if config["provider"] == "none":
            logger.warning("LLM provider not configured")
            return None, model_name

        client = openai.OpenAI(api_key=config["api_key"], base_url=config["base_url"])

        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "你是一位面向白癜风白友的体检报告解读助手。"
                            "请用通俗易懂的中文解读体检报告，按检查项目分类（血常规/尿常规/肝功能等），"
                            "每个分类标注风险等级（红/黄/绿）。"
                            "特别关注与白癜风相关的指标（甲状腺、免疫、肝功能）。"
                            "必须列出所有指标（包括正常的），不要只列异常指标。"
                            "严格输出JSON，不要输出Markdown代码块或JSON以外的文字。"
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                max_tokens=max_tokens,
            )
            content = (response.choices[0].message.content or "").strip()
            if content.startswith("```"):
                content = content.strip("`")
                if content.startswith("json"):
                    content = content[4:].strip()
            result = json.loads(content)
            if not isinstance(result, dict):
                return None, model_name
            return result, model_name
        except Exception as exc:
            logger.error("LLM call failed in ReportInterpreter: %s", str(exc), exc_info=True)
            return None, model_name

    def _post_process(
        self,
        result: Dict[str, Any],
        indicators: List[Dict[str, Any]],
        model_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        risk_level = self._normalize_risk_level(result.get("risk_level"))
        summary = str(result.get("summary", "")).strip() or "报告已解读，请查看详细指标分析。"

        parsed_source = result.get("parsed_indicators", [])
        if not isinstance(parsed_source, list):
            parsed_source = []
        parsed_indicators = self._normalize_parsed_indicators(parsed_source, indicators)

        abnormal_source = result.get("abnormal_items", [])
        if not isinstance(abnormal_source, list):
            abnormal_source = []
        abnormal_items = self._normalize_abnormal_items(abnormal_source)

        recommendations = self._normalize_recommendations(result.get("recommendations"))
        extracted_patient_info = self._normalize_extracted_patient_info(
            result.get("extracted_patient_info")
        )

        payload = {
            "risk_level": risk_level,
            "summary": summary,
            "parsed_indicators": parsed_indicators,
            "abnormal_items": abnormal_items,
            "recommendations": recommendations,
            "disclaimer": DISCLAIMER,
            "sections": result.get("sections") if isinstance(result.get("sections"), list) else [],
            "extracted_patient_info": extracted_patient_info,
        }
        payload.update(self._build_output_metadata(model_name))
        return payload

    def _post_process_sections(
        self, result: Dict[str, Any], model_name: Optional[str] = None
    ) -> Dict[str, Any]:
        risk_level = self._normalize_risk_level(result.get("risk_level"))
        summary = str(result.get("summary", "")).strip() or "报告已解读，请查看各分类详细分析。"

        sections = result.get("sections", [])
        if not isinstance(sections, list):
            sections = []

        norm_sections: List[Dict[str, Any]] = []
        for section in sections:
            if not isinstance(section, dict):
                continue
            section_indicators = self._normalize_section_indicators(section.get("indicators", []))
            section_abnormal_items = self._normalize_abnormal_items(section.get("abnormal_items", []))
            norm_sections.append({
                "section_name": str(section.get("section_name", "")).strip(),
                "risk": self._normalize_section_risk(section.get("risk")),
                "indicator_count": int(section.get("indicator_count", len(section_indicators))),
                "abnormal_count": int(section.get("abnormal_count", len(section_abnormal_items))),
                "section_summary": str(section.get("section_summary", "")).strip(),
                "indicators": section_indicators,
                "abnormal_items": section_abnormal_items,
            })

        all_indicators = result.get("all_indicators", [])
        if not isinstance(all_indicators, list):
            all_indicators = []
        parsed_indicators = self._normalize_parsed_indicators(all_indicators)
        if not parsed_indicators:
            flattened_indicators: List[Dict[str, Any]] = []
            for section in norm_sections:
                for indicator in section.get("indicators", []):
                    flattened_indicators.append(indicator)
            parsed_indicators = self._normalize_parsed_indicators(flattened_indicators)

        abnormal_items = self._flatten_section_abnormal_items(norm_sections)
        recommendations = self._normalize_recommendations(result.get("recommendations"))
        extracted_patient_info = self._normalize_extracted_patient_info(
            result.get("extracted_patient_info")
        )

        payload = {
            "risk_level": risk_level,
            "summary": summary,
            "sections": norm_sections,
            "parsed_indicators": parsed_indicators,
            "abnormal_items": abnormal_items,
            "recommendations": recommendations,
            "disclaimer": DISCLAIMER,
            "extracted_patient_info": extracted_patient_info,
        }
        payload.update(self._build_output_metadata(model_name))
        return payload

    def _post_process_comparison(
        self,
        result: Dict[str, Any],
        comparison_data: Dict[str, Any],
        model_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        summary = str(result.get("summary", "")).strip()
        if not summary:
            summary = "已生成多份体检报告对比总结。"

        key_changes = result.get("key_changes", [])
        if not isinstance(key_changes, list):
            key_changes = []
        normalized_changes: List[Dict[str, Any]] = []
        for item in key_changes:
            if not isinstance(item, dict):
                continue
            normalized_changes.append({
                "indicator_name": str(item.get("indicator_name", "")).strip(),
                "change_type": str(item.get("change_type", "")).strip(),
                "interpretation": str(item.get("interpretation", "")).strip(),
            })

        payload = {
            "summary": summary,
            "key_changes": normalized_changes,
            "recommendations": self._normalize_recommendations(result.get("recommendations")),
            "change_summary": comparison_data.get("change_summary", {}),
        }
        payload.update(self._build_output_metadata(model_name))
        return payload

    def _normalize_risk_level(self, risk_level: Any) -> str:
        risk = str(risk_level or "medium").strip().lower()
        if risk not in ("low", "medium", "high", "critical"):
            return "medium"
        return risk

    def _normalize_section_risk(self, risk: Any) -> str:
        risk_text = str(risk or "yellow").strip().lower()
        if risk_text not in ("green", "yellow", "red"):
            return "yellow"
        return risk_text

    def _normalize_parsed_indicators(
        self,
        parsed_source: List[Dict[str, Any]],
        fallback_indicators: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        normalized_items: List[Dict[str, Any]] = []
        seen_keys: set[str] = set()
        for indicator in parsed_source:
            normalized_indicator = self._normalize_parsed_indicator(indicator)
            if normalized_indicator is None:
                continue
            key = (
                normalized_indicator.get("canonical_name")
                or normalized_indicator.get("indicator_name")
                or normalized_indicator.get("value")
            )
            if not key:
                continue
            if key in seen_keys:
                continue
            seen_keys.add(str(key))
            normalized_items.append(normalized_indicator)

        if not normalized_items and fallback_indicators:
            for indicator in fallback_indicators:
                normalized_indicator = self._normalize_parsed_indicator(indicator)
                if normalized_indicator is not None:
                    normalized_items.append(normalized_indicator)
        return normalized_items

    def _normalize_parsed_indicator(
        self, indicator: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        if not isinstance(indicator, dict):
            return None
        indicator_name = str(
            indicator.get("indicator_name")
            or indicator.get("name")
            or indicator.get("raw_name")
            or ""
        ).strip()
        if not indicator_name:
            return None

        value = self._format_value(indicator.get("value"), indicator.get("unit"))
        ref_range = self._build_ref_range(indicator)
        status = str(indicator.get("status") or "unknown").strip().lower()
        if status not in ("normal", "high", "low", "critical", "unknown"):
            status = "unknown"
        normalized = normalize_indicator_name(indicator_name)

        payload = {
            "indicator_name": indicator_name,
            "value": value,
            "status": status,
            "ref_range": ref_range,
            "canonical_name": normalized.get("canonical_name") if normalized else None,
            "unit_family": normalized.get("unit_family") if normalized else None,
        }
        if indicator.get("unit") not in (None, ""):
            payload["unit"] = str(indicator.get("unit"))
        return payload

    def _normalize_section_indicators(
        self, indicators: Any
    ) -> List[Dict[str, Any]]:
        if not isinstance(indicators, list):
            return []

        normalized_items: List[Dict[str, Any]] = []
        for indicator in indicators:
            if not isinstance(indicator, dict):
                continue
            indicator_name = str(
                indicator.get("name")
                or indicator.get("indicator_name")
                or indicator.get("raw_name")
                or ""
            ).strip()
            if not indicator_name:
                continue
            normalized = normalize_indicator_name(indicator_name)
            normalized_items.append({
                "name": indicator_name,
                "value": self._format_value(indicator.get("value")),
                "unit": str(indicator.get("unit") or "").strip(),
                "ref_range": self._build_ref_range(indicator),
                "status": str(indicator.get("status") or "unknown").strip().lower(),
                "canonical_name": normalized.get("canonical_name") if normalized else None,
                "unit_family": normalized.get("unit_family") if normalized else None,
            })
        return normalized_items

    def _normalize_abnormal_items(self, abnormal_items: Any) -> List[Dict[str, Any]]:
        if not isinstance(abnormal_items, list):
            return []
        normalized_items: List[Dict[str, Any]] = []
        for item in abnormal_items:
            normalized_item = self._normalize_abnormal_item(item)
            if normalized_item is not None:
                normalized_items.append(normalized_item)
        return normalized_items

    def _normalize_abnormal_item(
        self, item: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        if not isinstance(item, dict):
            return None
        indicator_name = str(
            item.get("indicator_name") or item.get("name") or ""
        ).strip()
        if not indicator_name:
            return None
        normalized = normalize_indicator_name(indicator_name)
        status = str(item.get("status") or "unknown").strip().lower()
        if status not in ("high", "low", "critical", "normal", "unknown"):
            status = "unknown"

        possible_causes = self._normalize_string_list(item.get("possible_causes"))
        suggestions = self._normalize_string_list(item.get("suggestions"))

        source_indicators = item.get("source_indicators", [])
        normalized_sources: List[Dict[str, Any]] = []
        if isinstance(source_indicators, list):
            for source in source_indicators:
                normalized_source = self._normalize_source_indicator(source)
                if normalized_source is not None:
                    normalized_sources.append(normalized_source)

        confidence = self._normalize_confidence(item.get("confidence"))
        return {
            "indicator_name": indicator_name,
            "value": self._format_value(item.get("value"), item.get("unit")),
            "status": status,
            "interpretation": str(item.get("interpretation", "")).strip(),
            "possible_causes": possible_causes,
            "suggestions": suggestions,
            "source_indicators": normalized_sources,
            "source_text_excerpt": str(item.get("source_text_excerpt", "")).strip(),
            "confidence": confidence,
            "ref_range": self._build_ref_range(item),
            "canonical_name": normalized.get("canonical_name") if normalized else None,
        }

    def _normalize_source_indicator(
        self, source: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        if not isinstance(source, dict):
            return None
        indicator_name = str(
            source.get("indicator_name") or source.get("name") or ""
        ).strip()
        if not indicator_name:
            return None
        return {
            "indicator_name": indicator_name,
            "value": self._format_value(source.get("value"), source.get("unit")),
            "ref_range": self._build_ref_range(source),
        }

    def _normalize_string_list(self, values: Any) -> List[str]:
        if not isinstance(values, list):
            return []
        normalized_values: List[str] = []
        for value in values:
            text = str(value or "").strip()
            if text:
                normalized_values.append(text)
        return normalized_values

    def _normalize_recommendations(self, recommendations: Any) -> List[Dict[str, Any]]:
        if not isinstance(recommendations, list):
            return [{"content": "若存在异常指标，请咨询医生进一步判断。"}]

        normalized_items: List[Dict[str, Any]] = []
        for recommendation in recommendations:
            if isinstance(recommendation, dict) and recommendation.get("content"):
                normalized_items.append({"content": str(recommendation["content"]).strip()})
            elif isinstance(recommendation, str) and recommendation.strip():
                normalized_items.append({"content": recommendation.strip()})
        if not normalized_items:
            return [{"content": "若存在异常指标，请咨询医生进一步判断。"}]
        return normalized_items

    def _normalize_extracted_patient_info(
        self, extracted_patient_info: Any
    ) -> Optional[Dict[str, Any]]:
        if not isinstance(extracted_patient_info, dict):
            return None

        name = str(extracted_patient_info.get("name") or "").strip()
        gender = str(extracted_patient_info.get("gender") or "").strip()
        age_value = extracted_patient_info.get("age")
        age: Optional[int] = None
        try:
            if age_value not in (None, ""):
                age = int(age_value)
        except (TypeError, ValueError):
            age = None

        confidence = self._normalize_confidence(extracted_patient_info.get("confidence"))
        if not name and not gender and age is None:
            return None
        return {
            "name": name or None,
            "gender": gender or None,
            "age": age,
            "confidence": confidence,
        }

    def _normalize_confidence(self, confidence: Any) -> float:
        try:
            normalized = float(confidence)
        except (TypeError, ValueError):
            return 0.0
        if normalized < 0:
            return 0.0
        if normalized > 1:
            return 1.0
        return normalized

    def _format_value(self, value: Any, unit: Any = None) -> str:
        if value is None:
            return ""
        value_text = str(value).strip()
        unit_text = str(unit or "").strip()
        if unit_text and unit_text not in value_text:
            return ("%s %s" % (value_text, unit_text)).strip()
        return value_text

    def _build_ref_range(self, indicator: Dict[str, Any]) -> str:
        ref_range = indicator.get("ref_range")
        if ref_range not in (None, ""):
            return str(ref_range).strip()
        ref_min = indicator.get("ref_min")
        ref_max = indicator.get("ref_max")
        if ref_min is None and ref_max is None:
            return ""
        if ref_min is None:
            return "<=%s" % ref_max
        if ref_max is None:
            return ">=%s" % ref_min
        return "%s-%s" % (ref_min, ref_max)

    def _flatten_section_abnormal_items(
        self, sections: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        abnormal_items: List[Dict[str, Any]] = []
        for section in sections:
            for item in section.get("abnormal_items", []):
                normalized_item = self._normalize_abnormal_item(item)
                if normalized_item is not None:
                    abnormal_items.append(normalized_item)
        return abnormal_items

    def _build_output_metadata(self, model_name: Optional[str] = None) -> Dict[str, Any]:
        config = get_llm_config()
        return {
            "schema_version": "2.0",
            "parser_version": "1.0",
            "llm_model": model_name or config.get("chat_model", "unknown"),
            "generated_at": datetime.utcnow().isoformat() + "Z",
        }

    def _empty_result(self, raw_text: str) -> Dict[str, Any]:
        payload = {
            "risk_level": "low",
            "summary": "未能从报告中提取到有效指标。请确认上传的是包含数值指标的体检报告。",
            "parsed_indicators": [],
            "abnormal_items": [],
            "sections": [],
            "recommendations": [{"content": "建议重新上传清晰的体检报告图片或PDF。"}],
            "disclaimer": DISCLAIMER,
            "extracted_patient_info": None,
        }
        payload.update(self._build_output_metadata())
        return payload

    def _fallback_result(
        self,
        flagged: List[Dict[str, Any]],
        all_indicators: List[Dict[str, Any]],
        model_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        abnormal: List[Dict[str, Any]] = []
        for indicator in flagged:
            clinical = knowledge_base.get_clinical_info(indicator.get("name", ""))
            interpretation = ""
            possible_causes: List[str] = []
            if clinical:
                if indicator.get("status") == "high":
                    interpretation = clinical.get("clinical_high", "")
                elif indicator.get("status") == "low":
                    interpretation = clinical.get("clinical_low", "")
                if clinical.get("vitiligo_relevance"):
                    possible_causes = [str(clinical.get("vitiligo_relevance"))]

            abnormal.append({
                "indicator_name": indicator.get("name", ""),
                "value": self._format_value(indicator.get("value"), indicator.get("unit")),
                "status": indicator.get("status", "unknown"),
                "interpretation": interpretation or self._build_fallback_interpretation(indicator),
                "possible_causes": possible_causes,
                "suggestions": ["请咨询医生进一步判断。"],
                "source_indicators": [self._build_fallback_source_indicator(indicator)],
                "source_text_excerpt": "",
                "confidence": 0.35,
                "ref_range": self._build_ref_range(indicator),
            })

        risk = "low"
        if len(flagged) >= 3:
            risk = "high"
        elif len(flagged) >= 1:
            risk = "medium"

        payload = {
            "risk_level": risk,
            "summary": "共解析%s项指标，其中%s项异常。AI深度解读暂不可用，以下为基础参考分析。" % (
                len(all_indicators),
                len(flagged),
            ),
            "parsed_indicators": self._normalize_parsed_indicators([], all_indicators),
            "abnormal_items": self._normalize_abnormal_items(abnormal),
            "sections": [],
            "recommendations": [{"content": "若存在异常指标，请咨询医生进一步判断。"}],
            "disclaimer": DISCLAIMER,
            "extracted_patient_info": None,
        }
        payload.update(self._build_output_metadata(model_name))
        return payload

    def _fallback_section_result(
        self, full_text: str, model_name: Optional[str] = None
    ) -> Dict[str, Any]:
        from web.backend.services.medical.report_parser import report_parser

        indicators = report_parser._extract_indicators_from_text(full_text)
        if not indicators:
            return self._empty_result(full_text)

        flagged = [i for i in indicators if i.get("status") not in ("normal", "unknown")]
        risk_level = "low"
        section_risk = "green"
        if len(flagged) >= 5:
            risk_level = "high"
            section_risk = "red"
        elif len(flagged) >= 2:
            risk_level = "medium"
            section_risk = "yellow"

        section = {
            "section_name": "全部指标",
            "risk": section_risk,
            "indicator_count": len(indicators),
            "abnormal_count": len(flagged),
            "section_summary": "%s项指标，%s项异常" % (len(indicators), len(flagged)),
            "indicators": [
                {
                    "name": indicator.get("name", ""),
                    "value": indicator.get("value", ""),
                    "unit": indicator.get("unit", ""),
                    "ref_range": self._build_ref_range(indicator),
                    "status": indicator.get("status", "unknown"),
                }
                for indicator in indicators
            ],
            "abnormal_items": [
                {
                    "name": indicator.get("name", ""),
                    "value": indicator.get("value", ""),
                    "unit": indicator.get("unit", ""),
                    "ref_range": self._build_ref_range(indicator),
                    "status": indicator.get("status", "unknown"),
                    "interpretation": self._build_fallback_interpretation(indicator),
                    "possible_causes": [],
                    "suggestions": ["建议结合临床表现咨询医生。"],
                    "source_indicators": [self._build_fallback_source_indicator(indicator)],
                    "source_text_excerpt": "",
                    "confidence": 0.3,
                }
                for indicator in flagged
            ],
        }
        payload = self._post_process_sections(
            {
                "risk_level": risk_level,
                "summary": "共解析%s项指标，%s项异常。AI深度解读暂不可用，以下是基础分析。" % (
                    len(indicators),
                    len(flagged),
                ),
                "sections": [section],
                "all_indicators": section["indicators"],
                "recommendations": [{"content": "AI深度解读暂时不可用，以上为基础数据解析。请稍后重试或联系支持。"}],
                "extracted_patient_info": None,
            },
            model_name=model_name,
        )
        return payload

    def _build_fallback_interpretation(self, indicator: Dict[str, Any]) -> str:
        status = indicator.get("status")
        if status == "high":
            return "该指标偏高，建议结合症状和既往病史进一步评估。"
        if status == "low":
            return "该指标偏低，建议结合饮食、药物和临床表现进一步评估。"
        return "该指标需要结合临床情况综合判断。"

    def _build_fallback_source_indicator(
        self, indicator: Dict[str, Any]
    ) -> Dict[str, Any]:
        return {
            "indicator_name": str(indicator.get("name") or "").strip(),
            "value": self._format_value(indicator.get("value"), indicator.get("unit")),
            "ref_range": self._build_ref_range(indicator),
        }

    def _fallback_comparison_narrative(
        self, comparison_data: Dict[str, Any], model_name: Optional[str] = None
    ) -> Dict[str, Any]:
        highlights = comparison_data.get("highlights", [])
        highlight_names = [item.get("display_name") for item in highlights[:5] if item.get("display_name")]
        summary = "已完成%s份报告对比。重点变化：%s。" % (
            comparison_data.get("report_count", 0),
            "、".join(highlight_names) if highlight_names else "暂无显著变化",
        )
        payload = {
            "summary": summary,
            "key_changes": [
                {
                    "indicator_name": item.get("display_name"),
                    "change_type": item.get("change_type"),
                    "interpretation": "请结合对应趋势与临床表现继续跟踪。",
                }
                for item in highlights[:5]
            ],
            "recommendations": [{"content": "建议结合异常持续性和复查时间点，与医生讨论后续处理方案。"}],
            "change_summary": comparison_data.get("change_summary", {}),
        }
        payload.update(self._build_output_metadata(model_name))
        return payload


report_interpreter = ReportInterpreter()
