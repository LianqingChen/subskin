"""
日记图片轻量视觉分析服务

针对图文日记中上传的照片，调用视觉大模型（qwen3-vl-plus）做一次"看图说话"，
返回白斑的定性视觉特征（颜色/边界/面积印象/与历史同部位对比印象）。

这是两级智能分析中的「轻量级」：
- 秒级返回、低 API 成本
- 不跑图像分割管线，只给定性描述
- 为白斑变化报告提供基础视觉依据

深度级分析（精准面积/轮廓/分型/分期）由 VASI 评估管线负责，见 services/vasi.py。
"""

import base64
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# 单张图片轻量分析的最大字节数（超过则跳过，避免视觉模型拒绝）
_MAX_LIGHT_IMAGE_BYTES = 8 * 1024 * 1024


LIGHT_ANALYSIS_PROMPT = """你是 SubSkin 的白癜风病情记录助手。请观察这张皮肤照片，用客观、非诊断的措辞描述白斑（白癜风）的视觉特征。

重要：你不是医生，不做医疗诊断。只用"观察到""可见"等客观描述。

照片部位：{body_site}
{history_hint}

请提取以下定性特征（看不到则对应字段返回 null）：

1. color: 白斑颜色印象，level 取值 pale_white(淡白)/milky_white(乳白)/porcelain_white(瓷白)，附简短描述
2. border: 边界清晰度，level 取值 clear(清晰)/partial(部分清晰)/unclear(模糊)，附简短描述
3. area_impression: 白斑面积主观印象，level 取值 tiny(零星小点)/small(小片)/medium(中等)/large(大片)，附简短描述
4. distribution: 分布形态，pattern 取值 localized(局限)/segmental(节段)/scattered(散在)/generalized(泛发)，附简短描述
5. surface: 表面质地，texture 取值 smooth(光滑)/scaly(脱屑)/atrophic(萎缩)，附简短描述
6. change_note: {change_instruction}
7. confidence: 本次观察置信度 0-1
8. summary: 一句话总结（不超过30字）

请严格以 JSON 返回，不要任何其他文字或 markdown 代码块：
{{"color": {{"level": null, "description": null}}, "border": {{"level": null, "description": null}}, "area_impression": {{"level": null, "description": null}}, "distribution": {{"pattern": null, "description": null}}, "surface": {{"texture": null, "description": null}}, "change_note": null, "confidence": 0, "summary": null}}
"""


def _load_image_bytes(image_url: str) -> Optional[bytes]:
    """从图片 URL/路径加载本地图片 bytes。

    支持：
    - data URL（base64 内联）
    - /uploads/xxx 相对路径 → data/uploads/xxx
    - 绝对文件路径
    """
    if not image_url:
        return None

    # data URL
    if image_url.startswith("data:"):
        try:
            _, b64 = image_url.split(",", 1)
            return base64.b64decode(b64)
        except Exception:
            return None

    # 本地 /uploads/ 相对路径
    if image_url.startswith("/uploads/"):
        local_path = Path("data") / image_url.lstrip("/")
        if local_path.exists():
            try:
                return local_path.read_bytes()
            except Exception:
                return None

    # 绝对路径
    try:
        p = Path(image_url)
        if p.is_absolute() and p.exists():
            return p.read_bytes()
    except Exception:
        return None

    return None


def _detect_mime(image_bytes: bytes) -> str:
    if image_bytes[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if image_bytes[:4] == b"RIFF" and image_bytes[8:12] == b"WEBP":
        return "image/webp"
    return "image/jpeg"


def analyze_light(
    image_url: str,
    body_site: Optional[str] = None,
    history_image_urls: Optional[List[str]] = None,
) -> Optional[Dict[str, Any]]:
    """对单张日记图片做轻量视觉分析。

    Args:
        image_url: 当前照片 URL
        body_site: 照片对应部位（可为空）
        history_image_urls: 同部位历史照片 URL 列表（用于对比印象，最多取最近 1 张）

    Returns:
        结构化视觉特征 dict；调用失败返回 None
    """
    image_bytes = _load_image_bytes(image_url)
    if not image_bytes:
        logger.warning("diary_image: 无法加载图片 %s", image_url)
        return None
    if len(image_bytes) > _MAX_LIGHT_IMAGE_BYTES:
        logger.warning("diary_image: 图片过大(%d bytes)，跳过轻量分析", len(image_bytes))
        return None

    try:
        import openai

        from web.backend.utils.llm_config import get_llm_config

        # 视觉模型复用 vasi 模块配置（已配置 qwen3-vl-plus）
        config = get_llm_config("vasi")
        if config.get("provider") == "none" or not config.get("api_key"):
            logger.info("diary_image: 无可用 LLM provider，跳过轻量分析")
            return None

        vision_model = config.get("vision_model") or "qwen-vl-max"
        client = openai.OpenAI(api_key=config["api_key"], base_url=config["base_url"])

        b64_image = base64.b64encode(image_bytes).decode("utf-8")
        mime = _detect_mime(image_bytes)
        data_url = f"data:{mime};base64,{b64_image}"

        # 历史对比：最多取 1 张最近的同部位照片
        history_hint = ""
        change_instruction = "首次记录，无历史对比"
        history_content = []
        if history_image_urls:
            for hist_url in history_image_urls[:1]:
                hist_bytes = _load_image_bytes(hist_url)
                if hist_bytes and len(hist_bytes) <= _MAX_LIGHT_IMAGE_BYTES:
                    h_b64 = base64.b64encode(hist_bytes).decode("utf-8")
                    h_mime = _detect_mime(hist_bytes)
                    history_content.append(
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{h_mime};base64,{h_b64}"},
                        }
                    )
            if history_content:
                history_hint = "已附上一张同部位的历史照片作为对比参考。"
                change_instruction = "与所附历史照片对比，描述变化印象（如颜色/面积/边界的增减）"

        prompt = LIGHT_ANALYSIS_PROMPT.format(
            body_site=body_site or "未指定",
            history_hint=history_hint,
            change_instruction=change_instruction,
        )

        content: List[Dict[str, Any]] = []
        if history_content:
            content.append({"type": "text", "text": "这是更早的历史照片："})
            content.extend(history_content)
            content.append({"type": "text", "text": "这是当前最新照片："})
        content.append({"type": "image_url", "image_url": {"url": data_url}})
        content.append({"type": "text", "text": prompt})

        response = client.chat.completions.create(
            model=vision_model,
            messages=[{"role": "user", "content": content}],
            temperature=0.2,
            # 推理 token 计入 max_tokens：600 在「带历史对比图」（双图）时会被思考耗尽，
            # 返回空内容 → JSON 解析失败 → 整个轻量分析静默返回 None（2026-09-12 实测）。
            max_tokens=int(os.getenv("DIARY_VISION_MAX_TOKENS", "4000")),
        )

        raw = (response.choices[0].message.content or "").strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0]
        result = json.loads(raw)
        result.setdefault("analyzed_at", _now_iso())
        return result

    except Exception:
        logger.warning("diary_image: 轻量视觉分析失败 %s", image_url, exc_info=True)
        return None


def analyze_diary_images_async(entry_id: int) -> None:
    """后台线程：对某条日记下所有 pending 图片逐张做轻量分析。

    仿 diary_ai.extract_diary_structure 的后台线程模式。
    """
    import threading

    from web.backend.database.database import SessionLocal

    def _run():
        from web.backend.database.models import DiaryEntry, DiaryImage

        db = SessionLocal()
        try:
            entry = db.query(DiaryEntry).filter(DiaryEntry.id == entry_id).first()
            if not entry:
                return

            images = (
                db.query(DiaryImage)
                .filter(
                    DiaryImage.diary_entry_id == entry_id,
                    DiaryImage.analysis_status.in_(["pending", "failed"]),
                )
                .order_by(DiaryImage.order_index.asc())
                .all()
            )
            if not images:
                return

            # 收集该用户同部位的近期历史图，供对比
            for img in images:
                img.analysis_status = "analyzing"
                db.commit()

                history_urls: List[str] = []
                if img.body_site:
                    hist = (
                        db.query(DiaryImage)
                        .filter(
                            DiaryImage.user_id == entry.user_id,
                            DiaryImage.body_site == img.body_site,
                            DiaryImage.id != img.id,
                            DiaryImage.capture_date.isnot(None),
                        )
                        .order_by(DiaryImage.capture_date.desc())
                        .first()
                    )
                    if hist:
                        history_urls = [hist.image_url]

                result = analyze_light(img.image_url, img.body_site, history_urls)
                if result:
                    img.visual_analysis_json = json.dumps(result, ensure_ascii=False)
                    img.analysis_status = "light_done"
                else:
                    img.analysis_status = "failed"
                db.commit()

            logger.info(
                "diary_image: 日记 %s 的 %d 张图片轻量分析完成", entry_id, len(images)
            )
        except Exception:
            logger.exception("diary_image: 日记 %s 图片分析异常", entry_id)
            db.rollback()
        finally:
            db.close()

    t = threading.Thread(target=_run, daemon=True)
    t.start()


def _now_iso() -> str:
    from web.backend.utils.timeutils import iso_utc

    return iso_utc(None)
