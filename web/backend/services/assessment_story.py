"""Short creative captions from reviewed geometry. Never recomputes measurements."""
import hashlib
import base64
import io
import json
import re
import threading
from typing import Any, Dict, Optional

import numpy as np
from PIL import Image
from openai import OpenAI
from sqlalchemy.orm import Session

from web.backend.exceptions import StoryGenerationError
from web.backend.models.vasi import VASIAssessment
from web.backend.services.assessment_measurement import decode_mask, measurement_for, read_details
from web.backend.services.consent import has_active_consent, CONSENT_TYPE_AI_DATA, CONSENT_TYPE_MEDICAL_PHOTO
from web.backend.utils.llm_config import get_llm_config

VERSION = "contour-story-v3"
_slots = threading.BoundedSemaphore(2)
_guard = threading.Lock()
_active = set()


def owned_snapshot(db: Session, assessment_id: int, user_id: int, revision: str) -> VASIAssessment:
    record = db.query(VASIAssessment).filter_by(id=assessment_id, user_id=user_id).populate_existing().first()
    if record is None or record.status != "active":
        raise StoryGenerationError("记录不存在或尚未保存", 404)
    measurement = measurement_for(record)
    annotation = measurement.get("annotation") or {}
    if annotation.get("review_state") != "user_reviewed":
        raise StoryGenerationError("请先核对并保存白斑范围", 409)
    current = annotation.get("mask_revision") or measurement.get("mask_revision")
    if not revision or current != revision:
        raise StoryGenerationError("记录已更新，请重新打开后生成", 409)
    return record


def geometry(record: VASIAssessment) -> Dict[str, Any]:
    mask = decode_mask(record.user_lesion_layer)
    if mask is None or not mask.any():
        raise StoryGenerationError("当前没有可用白斑轮廓，记录仍已保存", 422)
    ys, xs = np.nonzero(mask)
    ratio = float((xs.max() - xs.min() + 1) / (ys.max() - ys.min() + 1))
    measurement = measurement_for(record)
    count = measurement.get("region_count")
    silhouette = Image.fromarray(np.where(mask, 20, 245).astype(np.uint8), mode="L")
    scale = min(1.0, 512 / max(silhouette.size))
    silhouette = silhouette.resize((max(1, int(silhouette.width * scale + .5)), max(1, int(silhouette.height * scale + .5))), Image.Resampling.NEAREST)
    guide = Image.new("L", (512, 512), 245)
    guide.paste(silhouette, ((512 - silhouette.width) // 2, (512 - silhouette.height) // 2))
    encoded = io.BytesIO(); guide.save(encoded, format="PNG")
    return {"silhouette": "data:image/png;base64," + base64.b64encode(encoded.getvalue()).decode(),
            "shape": "纵向舒展" if ratio < .65 else "横向舒展" if ratio > 1.65 else "集中舒展",
            "arrangement": "多块相伴" if isinstance(count, int) and count > 1 else "独立轮廓",
            "body_site": record.body_site}


def validate_story(value: Any) -> Dict[str, str]:
    if not isinstance(value, dict) or value.get("theme") not in ("sky", "island", "stars"):
        raise StoryGenerationError("创意暂未生成，请重试", 503)
    title = value.get("title")
    if not isinstance(title, str):
        raise StoryGenerationError("创意暂未生成，请重试", 503)
    title = title.strip()
    # Restrict output to one short Chinese literary sentence, no markup/numbers/diagnosis.
    if (not 6 <= len(title) <= 24 or not re.fullmatch(r"[\u4e00-\u9fff，。！？、；：‘’“”·—\s]+", title)
            or re.search(r"治愈|痊愈|好转|恶化|疗效|治疗|康复|严重|轻度|重度|消退|消失|扩散|病因|诊断|白癜风|丑|缺陷|残缺|癌|传染|一定|保证|百分", title)):
        raise StoryGenerationError("创意暂未生成，请重试", 503)
    result = {"theme": value["theme"], "title": title.replace("\n", ""), "source": "ai"}
    if "art_prompt" in value:
        prompt = value["art_prompt"]
        if not isinstance(prompt, str) or not 20 <= len(prompt) <= 700 or re.search(r"https?://|<|>|治愈|疗效|病因|诊断|裸露|身份证", prompt):
            raise StoryGenerationError("创意画面构思暂不可用，请重试", 503)
        result["art_prompt"] = prompt.strip()
    return result


def generate_caption(description: Dict[str, Any]) -> Dict[str, str]:
    config = get_llm_config("vasi")
    if not config.get("api_key"):
        raise StoryGenerationError("创意服务暂不可用，请稍后重试", 503)
    prompt = (
        "你为SubSkin的个人轮廓艺术卡构思画面和一句中文短句。附图深色区域是用户确认的真实轮廓，浅色为背景。观察各块具体形状、孔洞、朝向和相对位置。"
        "不要写病情、诊断、分期、疗效、好转或身体缺陷；不要推断年龄、性别、姓名或情绪。"
        "只作云朵、海岛或星光的文学联想，温和自然，不说教，不强行励志。"
        "选择适合轮廓的一种主题。只输出JSON：{\"theme\":\"sky或island或stars\",\"title\":\"6至24字中文短句\"}。"
        "另加art_prompt字段：80至220字中文生图提示词，依据所见轮廓联想具体的自然风景、光线和细节，避免通用套话。"
        "保持三种既定风格sky云朵/island海岛/stars星光，选最贴合轮廓的一种；艺术画面会作为纹理裁入真实轮廓，画满全幅，主体靠中，不要描绘文字、数字、二维码、人物、人体、皮肤或医学图表。"
        "文案title仅6至24字中文；输出仅JSON，不要其他解释。"
    )
    if description.get("theme"):
        prompt += "用户已明确选择风格 " + description["theme"] + "，必须按此风格构思，返回相同theme，不能自行切换。"
    with OpenAI(api_key=config["api_key"], base_url=config["base_url"], timeout=35, max_retries=0) as client:
        result = client.chat.completions.create(
            model=config["chat_model"], temperature=.7, max_tokens=1500,
            response_format={"type": "json_object"},
            messages=[{"role": "system", "content": prompt}, {"role": "user", "content": [
                {"type": "text", "text": json.dumps({k: v for k, v in description.items() if k != "silhouette"}, ensure_ascii=False)},
                {"type": "image_url", "image_url": {"url": description["silhouette"]}},
            ]}],
        )
    try:
        content = validate_story(json.loads(result.choices[0].message.content or ""))
        if description.get("theme") and content["theme"] != description["theme"]:
            raise StoryGenerationError("所选风格的创意暂未生成，请重试", 503)
        if not content.get("art_prompt"):
            raise StoryGenerationError("创意画面构思暂未生成，请重试", 503)
        return content
    except (ValueError, IndexError, AttributeError):
        raise StoryGenerationError("创意暂未生成，请重试", 503)


def validate_theme(theme: Optional[str]) -> None:
    if theme is not None and theme not in ("sky", "island", "stars"):
        raise StoryGenerationError("创意风格无效")


def story_cache(details: Dict[str, Any], theme: Optional[str]) -> Dict[str, Any]:
    return (details.get("creative_stories") or {}).get(theme, {}) if theme else details.get("creative_story") or {}


def story_fingerprint(record: VASIAssessment, revision: str, theme: Optional[str]) -> str:
    return hashlib.sha256((VERSION + revision + (record.user_lesion_layer or "") + record.body_site + (theme or "")).encode()).hexdigest()


def create_story(db: Session, assessment_id: int, user_id: int, revision: str, theme: Optional[str] = None) -> Dict[str, str]:
    validate_theme(theme)
    record = owned_snapshot(db, assessment_id, user_id, revision)
    details = read_details(record.details)
    fingerprint = story_fingerprint(record, revision, theme)
    cached = story_cache(details, theme)
    if cached.get("fingerprint") == fingerprint:
        return dict(validate_story(cached), revision=revision)
    if not (has_active_consent(db, user_id, CONSENT_TYPE_AI_DATA) or has_active_consent(db, user_id, CONSENT_TYPE_MEDICAL_PHOTO)):
        raise StoryGenerationError("开启隐私设置中的AI数据授权后可自动创作", 403)
    description = geometry(record)
    if theme: description["theme"] = theme
    key = (user_id, assessment_id, theme) if theme else (user_id, assessment_id)
    with _guard:
        if key in _active or not _slots.acquire(blocking=False):
            raise StoryGenerationError("创意正在生成，请稍后重试", 429)
        _active.add(key)
    try:
        db.rollback()
        generated = generate_caption(description)
        if theme and generated.get("theme") != theme:
            raise StoryGenerationError("所选风格的创意暂未生成，请重试", 503)
        record = owned_snapshot(db, assessment_id, user_id, revision)
        if story_fingerprint(record, revision, theme) != fingerprint:
            raise StoryGenerationError("记录已更新，请重新生成", 409)
        # Merge independent style/art caches using the latest snapshot; never overwrite a measurement update.
        original = record.details; details = read_details(original)
        cached = story_cache(details, theme)
        if cached.get("fingerprint") == fingerprint:
            return dict(validate_story(cached), revision=revision)
        value = dict(generated, fingerprint=fingerprint, version=VERSION)
        if theme: details.setdefault("creative_stories", {})[theme] = value
        else: details["creative_story"] = value
        changed = db.query(VASIAssessment).filter_by(id=assessment_id, user_id=user_id, status="active", details=original).update(
            {VASIAssessment.details: json.dumps(details, ensure_ascii=False)}, synchronize_session=False)
        if changed != 1:
            db.rollback()
            raise StoryGenerationError("记录正在更新，请重试", 409)
        db.commit()
        return dict(generated, revision=revision)
    finally:
        with _guard:
            _active.discard(key); _slots.release()
