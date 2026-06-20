"""
VASI 数据飞轮 — 反馈收集与训练样本管理 (Phase 1)

实现自我进化闭环的第一步：从用户行为中收集高质量反馈信号，
标准化为训练样本，为后续的 Prompt 进化、参数优化、模型训练提供数据基础。

核心功能:
  1. 显式反馈: 用户主动评分、手动修正轮廓
  2. 隐式信号: 停留时间、重新上传、分享等无感行为
  3. 主动询问: 低置信度时弹窗请求用户确认
  4. 样本导出: 从 contour_diff + user_mask → 标准化 TrainingSample
"""

import json
import logging
import hashlib
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field

from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from web.backend.models.vasi import (
    VASIAssessment,
    VasiFeedbackSignal,
    VasiTrainingSample,
    VasiModelVersion,
)

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# Data Classes
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class ImplicitFeedback:
    """隐式反馈信号汇总"""
    stay_duration_ok: bool = False       # 用户停留 > 10s
    reupload_detected: bool = False      # 短时间内重新上传同部位
    shared: bool = False                 # 用户分享了结果
    corrected_again: bool = False        # 修正后又再次修正
    overall_positive: Optional[bool] = None  # None = 信号不足判断


@dataclass
class FeedbackPrompt:
    """主动询问弹窗的内容"""
    assessment_id: int
    confidence: float
    should_ask: bool                    # 是否应该弹窗
    title: str = ""
    question: str = ""
    options: List[str] = field(default_factory=list)
    reason: str = ""                    # 为什么需要询问


@dataclass
class TrainingSampleExport:
    """标准化的训练样本"""
    image_hash: str
    image_key: str
    body_site: str
    fitzpatrick_type: Optional[str]
    quality_level: Optional[str]
    ai_mask_b64: Optional[str]
    ai_contours_json: Optional[str]
    user_mask_b64: Optional[str]
    user_contours_json: Optional[str]
    contour_diff_json: Optional[str]
    dice_score: Optional[float]
    area_error_pct: Optional[float]
    confidence: Optional[float]
    assessment_source: Optional[str]


# ══════════════════════════════════════════════════════════════════════════════
# FeedbackCollector — 主服务
# ══════════════════════════════════════════════════════════════════════════════

class VasiFeedbackCollector:
    """VASI 反馈收集服务

    收集多维度反馈信号，建立训练数据集。
    """

    # ── 阈值常量 ──
    STAY_DURATION_THRESHOLD = 10      # 停留 > 10s = 认真看了
    REUPLOAD_WINDOW_MINUTES = 5       # 5分钟内重新上传同部位 = 不满意
    LOW_CONFIDENCE_THRESHOLD = 0.5    # confidence < 0.5 = 主动询问
    UNCERTAIN_CONFIDENCE_THRESHOLD = 0.7  # 0.5-0.7 = 显示"不太确定"

    def __init__(self, db: Session):
        self.db = db

    # ── 1. 显式反馈 ──

    def record_explicit_rating(
        self,
        assessment_id: int,
        user_id: int,
        rating: int,
        comment: Optional[str] = None,
        issues: Optional[List[str]] = None,
    ) -> VasiFeedbackSignal:
        """记录用户主动评分 (1-5星)"""
        signal = VasiFeedbackSignal(
            assessment_id=assessment_id,
            user_id=user_id,
            signal_type="explicit_rating",
            signal_value=json.dumps({
                "rating": max(1, min(5, rating)),
                "comment": comment or "",
                "issues": issues or [],
            }),
        )
        self.db.add(signal)
        self.db.commit()
        logger.info("Explicit rating recorded: assessment=%d rating=%d", assessment_id, rating)
        return signal

    def record_explicit_correction(
        self,
        assessment_id: int,
        user_id: int,
        contour_diff_json: str,
        user_mask_b64: Optional[str] = None,
    ) -> VasiFeedbackSignal:
        """记录用户手动修正轮廓"""
        signal = VasiFeedbackSignal(
            assessment_id=assessment_id,
            user_id=user_id,
            signal_type="explicit_correction",
            signal_value=json.dumps({
                "has_user_mask": bool(user_mask_b64),
                "diff_size_bytes": len(contour_diff_json),
            }),
        )
        self.db.add(signal)
        self.db.commit()

        # 同时触发训练样本导出
        assessment = self.db.query(VASIAssessment).filter(
            VASIAssessment.id == assessment_id
        ).first()
        if assessment:
            self._upsert_training_sample(assessment, user_mask_b64)

        return signal

    # ── 2. 隐式信号 ──

    def record_implicit_stay(
        self, assessment_id: int, user_id: int, duration_seconds: float
    ) -> Optional[VasiFeedbackSignal]:
        """记录用户在结果页的停留时间"""
        ok = duration_seconds >= self.STAY_DURATION_THRESHOLD
        if not ok:
            return None  # 停留太短，不记录（不是有效信号）

        signal = VasiFeedbackSignal(
            assessment_id=assessment_id,
            user_id=user_id,
            signal_type="implicit_stay",
            signal_value=json.dumps({"duration_seconds": round(duration_seconds, 1)}),
        )
        self.db.add(signal)
        self.db.commit()
        logger.debug("Implicit stay: assessment=%d duration=%.1fs", assessment_id, duration_seconds)
        return signal

    def record_implicit_reupload(
        self, assessment_id: int, user_id: int, previous_assessment_id: int
    ) -> VasiFeedbackSignal:
        """记录用户短时间内重新上传同部位"""
        signal = VasiFeedbackSignal(
            assessment_id=assessment_id,
            user_id=user_id,
            signal_type="implicit_reupload",
            signal_value=json.dumps({
                "previous_assessment_id": previous_assessment_id,
                "reason": "user_reuploaded_same_site",
            }),
        )
        self.db.add(signal)
        self.db.commit()
        logger.info("Implicit reupload: %d → %d", previous_assessment_id, assessment_id)
        return signal

    def record_implicit_share(
        self, assessment_id: int, user_id: int
    ) -> VasiFeedbackSignal:
        """记录用户分享结果（认可准确度）"""
        signal = VasiFeedbackSignal(
            assessment_id=assessment_id,
            user_id=user_id,
            signal_type="implicit_share",
            signal_value=json.dumps({"shared": True}),
        )
        self.db.add(signal)
        self.db.commit()
        return signal

    def detect_reupload(
        self, user_id: int, body_site: str, current_time: datetime
    ) -> Optional[int]:
        """检测用户在 REUPLOAD_WINDOW_MINUTES 内是否上传过同部位。

        Returns:
            最近的同部位评估ID，如果没有则返回None
        """
        window_start = current_time - timedelta(minutes=self.REUPLOAD_WINDOW_MINUTES)
        recent = (
            self.db.query(VASIAssessment)
            .filter(
                VASIAssessment.user_id == user_id,
                VASIAssessment.body_site == body_site,
                VASIAssessment.assessment_date >= window_start,
                VASIAssessment.id != None,
            )
            .order_by(VASIAssessment.assessment_date.desc())
            .first()
        )
        return recent.id if recent else None

    # ── 3. 主动询问 ──

    def should_request_feedback(self, assessment_id: int) -> FeedbackPrompt:
        """判断是否应该主动向用户请求反馈。

        触发条件:
        - confidence < 0.5: 必须询问
        - 0.5 <= confidence < 0.7: 显示"不太确定"提示（轻量询问）
        - confidence >= 0.7: 不询问
        """
        assessment = self.db.query(VASIAssessment).filter(
            VASIAssessment.id == assessment_id
        ).first()

        if not assessment:
            return FeedbackPrompt(
                assessment_id=assessment_id,
                confidence=0.0,
                should_ask=False,
                reason="assessment not found",
            )

        confidence = assessment.confidence or 0.5

        if confidence < self.LOW_CONFIDENCE_THRESHOLD:
            return FeedbackPrompt(
                assessment_id=assessment_id,
                confidence=confidence,
                should_ask=True,
                title="AI 对这次识别不太有把握",
                question="AI 对白斑的识别准确吗？",
                options=["基本准确", "有漏检", "误判了正常皮肤"],
                reason="low_confidence",
            )

        if confidence < self.UNCERTAIN_CONFIDENCE_THRESHOLD:
            return FeedbackPrompt(
                assessment_id=assessment_id,
                confidence=confidence,
                should_ask=True,
                title="需要你帮忙确认一下",
                question="白斑范围识别得怎么样？",
                options=["准确 ✓", "需要微调"],
                reason="uncertain_confidence",
            )

        return FeedbackPrompt(
            assessment_id=assessment_id,
            confidence=confidence,
            should_ask=False,
            reason="high_confidence",
        )

    def record_active_query_response(
        self,
        assessment_id: int,
        user_id: int,
        selected_option: str,
        comment: Optional[str] = None,
    ) -> VasiFeedbackSignal:
        """记录用户对主动询问的回复"""
        signal = VasiFeedbackSignal(
            assessment_id=assessment_id,
            user_id=user_id,
            signal_type="active_query",
            signal_value=json.dumps({
                "selected_option": selected_option,
                "comment": comment or "",
            }),
        )
        self.db.add(signal)
        self.db.commit()
        return signal

    # ── 4. 综合信号分析 ──

    def analyze_implicit_signals(self, assessment_id: int) -> ImplicitFeedback:
        """综合分析一个评估的所有隐式信号"""
        signals = (
            self.db.query(VasiFeedbackSignal)
            .filter(VasiFeedbackSignal.assessment_id == assessment_id)
            .all()
        )

        fb = ImplicitFeedback()
        for s in signals:
            if s.signal_type == "implicit_stay":
                fb.stay_duration_ok = True
            elif s.signal_type == "implicit_reupload":
                fb.reupload_detected = True
            elif s.signal_type == "implicit_share":
                fb.shared = True
            elif s.signal_type == "implicit_correction_again":
                fb.corrected_again = True

        # 综合判断: 有正向信号且无负向信号 = positive
        positive_signals = sum([fb.stay_duration_ok, fb.shared])
        negative_signals = sum([fb.reupload_detected, fb.corrected_again])
        if positive_signals > 0 and negative_signals == 0:
            fb.overall_positive = True
        elif negative_signals > 0 and positive_signals == 0:
            fb.overall_positive = False

        return fb

    # ── 5. 训练样本导出 ──

    def _upsert_training_sample(
        self,
        assessment: VASIAssessment,
        user_mask_b64: Optional[str] = None,
        pipeline_params: Optional[dict] = None,
    ) -> Optional[VasiTrainingSample]:
        """从 VASIAssessment + 用户修正 → 标准化的 TrainingSample

        去重策略: 按 image_hash 去重，如果已存在则更新

        Args:
            assessment: VASI评估记录
            user_mask_b64: 用户修正后的mask（可选，从assessment.user_lesion_layer fallback）
            pipeline_params: RL管线参数快照（可选）
        """
        # 必须有图片和用户修正才能生成训练样本
        if not assessment.image_key:
            return None

        image_hash = assessment.image_hash or self._compute_image_hash(assessment)
        if not image_hash:
            return None

        # 解析 contour_diff 计算 dice 和 area_error
        dice_score = None
        area_error_pct = None
        contour_diff_json = assessment.contour_diff

        if contour_diff_json:
            try:
                diff_data = json.loads(contour_diff_json)
                dice_score = diff_data.get("dice_score")
                area_error_pct = diff_data.get("area_error_pct")
            except (json.JSONDecodeError, TypeError):
                pass

        # 解析 quality_report 获取 quality_level
        quality_level = None
        if assessment.quality_report_json:
            try:
                qr = json.loads(assessment.quality_report_json)
                quality_level = qr.get("overall")
            except (json.JSONDecodeError, TypeError):
                pass

        # ── Phase 1A: Extract richer metadata from VLM output ──
        fitzpatrick_type = None
        vitiligo_type = None
        vitiligo_stage = None

        # Try raw_api_response first (most complete VLM output)
        source_data = assessment.raw_api_response or assessment.details
        if source_data:
            try:
                sd = json.loads(source_data) if isinstance(source_data, str) else source_data
                # Fitzpatrick skin type (I-VI)
                fitz = sd.get("fitzpatrick_type") or sd.get("fitzpatrick") or sd.get("skin_type")
                if fitz and isinstance(fitz, str):
                    # Normalize: "3" → "III", "III" stays "III"
                    fitz_clean = fitz.strip()
                    if fitz_clean.isdigit():
                        roman_map = {"1": "I", "2": "II", "3": "III", "4": "IV", "5": "V", "6": "VI"}
                        fitzpatrick_type = roman_map.get(fitz_clean, fitz_clean)
                    else:
                        fitzpatrick_type = fitz_clean
                # Vitiligo classification
                classifications = sd.get("classifications") or sd.get("detailed_classification") or {}
                if isinstance(classifications, dict):
                    vitiligo_type = classifications.get("type") or classifications.get("vitiligo_type")
                    vitiligo_stage = classifications.get("stage")
                if not vitiligo_type:
                    vitiligo_type = sd.get("vitiligo_type") or sd.get("type")
                if not vitiligo_stage:
                    vitiligo_stage = sd.get("stage")
                # Fallback to assessment record fields
                if not vitiligo_type:
                    vitiligo_type = assessment.classification
                if not vitiligo_stage:
                    vitiligo_stage = assessment.stage
            except (json.JSONDecodeError, TypeError):
                pass

        # AI 轮廓从 details 中提取
        ai_contours_json = None
        if assessment.details:
            try:
                details = json.loads(assessment.details)
                contours = details.get("contours")
                if contours:
                    ai_contours_json = json.dumps(contours)
            except (json.JSONDecodeError, TypeError):
                pass

        # 用户轮廓
        user_contours_json = assessment.user_contours

        # 用户 mask: 优先用参数，然后 user_lesion_layer，最后 user_mask_image
        final_user_mask = user_mask_b64 or assessment.user_lesion_layer or assessment.user_mask_image

        # AI mask
        ai_mask_b64 = assessment.ai_lesion_layer

        # Pipeline params snapshot
        pipeline_params_json = json.dumps(pipeline_params) if pipeline_params else None

        # Upsert: 先查是否存在
        existing = (
            self.db.query(VasiTrainingSample)
            .filter(VasiTrainingSample.image_hash == image_hash)
            .first()
        )

        if existing:
            # 更新现有记录
            if final_user_mask:
                existing.user_mask_b64 = final_user_mask
            if user_contours_json:
                existing.user_contours_json = user_contours_json
            if contour_diff_json:
                existing.contour_diff_json = contour_diff_json
            if dice_score is not None:
                existing.dice_score = dice_score
            if area_error_pct is not None:
                existing.area_error_pct = area_error_pct
            if assessment.confidence is not None:
                existing.confidence = assessment.confidence
            # Phase 1A: enrich metadata on update
            if fitzpatrick_type:
                existing.fitzpatrick_type = fitzpatrick_type
            if vitiligo_type:
                existing.vitiligo_type = vitiligo_type
            if vitiligo_stage:
                existing.stage = vitiligo_stage
            if quality_level:
                existing.quality_level = quality_level
            if pipeline_params_json:
                existing.pipeline_params_json = pipeline_params_json
            # sample_source: only set if not already admin_labeling
            if not existing.sample_source or existing.sample_source == "user_correction":
                existing.sample_source = "user_correction"
            self.db.commit()
            logger.info("Updated training sample: hash=%s dice=%.3f", image_hash[:8], dice_score or 0)
            return existing

        # 创建新记录
        sample = VasiTrainingSample(
            image_hash=image_hash,
            image_key=assessment.image_key,
            body_site=assessment.body_site,
            fitzpatrick_type=fitzpatrick_type,
            quality_level=quality_level,
            sample_source="user_correction",
            vitiligo_type=vitiligo_type,
            stage=vitiligo_stage,
            ai_mask_b64=ai_mask_b64,
            ai_contours_json=ai_contours_json,
            user_mask_b64=final_user_mask,
            user_contours_json=user_contours_json,
            contour_diff_json=contour_diff_json,
            dice_score=dice_score,
            area_error_pct=area_error_pct,
            confidence=assessment.confidence,
            assessment_source=assessment.assessment_source,
            pipeline_params_json=pipeline_params_json,
        )
        self.db.add(sample)
        self.db.commit()
        logger.info(
            "Created training sample: hash=%s site=%s source=%s dice=%.3f",
            image_hash[:8], assessment.body_site, "user_correction", dice_score or 0,
        )
        return sample

    def _compute_image_hash(self, assessment: VASIAssessment) -> Optional[str]:
        """从已有字段计算 image_hash"""
        if assessment.image_key:
            return hashlib.md5(assessment.image_key.encode()).hexdigest()
        return None

    # ── Admin labeling integration ──────────────────────────────────

    def upsert_from_admin_label(
        self,
        label: Any,  # ImageLabel instance
    ) -> Optional[VasiTrainingSample]:
        """从管理员打标记录 → 创建/更新高质量训练样本 (gold standard)

        管理员标注被视为 ground truth，具有最高优先级。
        每次管理员完成标注后调用此方法，将结果同步到训练样本中心。

        Args:
            label: ImageLabel 实例（需已加载 annotations）
        Returns:
            VasiTrainingSample 或 None（无有效数据时）
        """
        from web.backend.models.image_label import ImageLabel

        if not hasattr(label, "image_hash") or not label.image_hash:
            logger.warning("Admin label %s has no image_hash, skipping training export", label.id)
            return None

        # Only export labeled items (not pending/skipped/rejected)
        if label.label_status != "labeled":
            logger.debug("Admin label %s status=%s, skipping", label.id, label.label_status)
            return None

        # Must be training-eligible
        if not label.training_eligible:
            logger.debug("Admin label %s not training_eligible, skipping", label.id)
            return None

        # Collect admin annotations as ground truth
        admin_annotations = []
        if hasattr(label, "annotations") and label.annotations:
            admin_annotations = [
                a for a in label.annotations
                if a.source == "admin" and a.mask_data
            ]

        # Use ImageLabel's top-level admin fields as fallback
        admin_mask = None
        admin_contours = []
        admin_label_id = None

        if admin_annotations:
            # Use the first admin annotation's mask
            admin_mask = admin_annotations[0].mask_data
            admin_label_id = admin_annotations[0].id
            contours = []
            for ann in admin_annotations:
                if ann.region_contour:
                    try:
                        c = json.loads(ann.region_contour)
                        if isinstance(c, list):
                            contours.extend(c)
                        elif isinstance(c, dict):
                            contours.append(c)
                    except (json.JSONDecodeError, TypeError):
                        pass
            admin_contours = contours

        if not admin_mask:
            logger.debug("Admin label %s has no admin mask data", label.id)
            return None

        # Collect metadata
        body_site = label.admin_body_site or label.ai_body_site or "unknown"
        vitiligo_type = label.admin_vitiligo_type or label.ai_vitiligo_type
        vitiligo_stage = label.admin_vitiligo_stage or label.ai_vitiligo_stage

        # AI mask — from assessment if available, otherwise from AI pre-annotation
        ai_mask = None
        ai_contours_json = None
        if hasattr(label, "assessment") and label.assessment:
            ai_mask = label.assessment.ai_lesion_layer
            if label.assessment.details:
                try:
                    details = json.loads(label.assessment.details)
                    contours = details.get("contours")
                    if contours:
                        ai_contours_json = json.dumps(contours)
                except (json.JSONDecodeError, TypeError):
                    pass
        # Fallback: AI annotations from labeling module
        if not ai_mask:
            ai_anns = [a for a in label.annotations if a.source == "ai" and a.mask_data] if hasattr(label, "annotations") and label.annotations else []
            if ai_anns:
                ai_mask = ai_anns[0].mask_data

        # Compute Dice between AI and admin (if both available)
        dice_score = None
        area_error_pct = None
        if ai_mask and admin_mask:
            # Defer to the mask comparison utility
            try:
                from web.backend.api.vasi import _compute_mask_dice_and_area
                mask_metrics = _compute_mask_dice_and_area(ai_mask, admin_mask)
                if mask_metrics:
                    dice_score = mask_metrics.get("dice_score")
                    area_error_pct = mask_metrics.get("area_error_pct")
            except ImportError:
                pass

        # Upsert by image_hash
        existing = (
            self.db.query(VasiTrainingSample)
            .filter(VasiTrainingSample.image_hash == label.image_hash)
            .first()
        )

        if existing:
            # Admin labels are gold standard — overwrite
            existing.sample_source = "admin_labeling"
            existing.admin_mask_b64 = admin_mask
            existing.admin_label_id = admin_label_id
            existing.body_site = body_site
            if vitiligo_type:
                existing.vitiligo_type = vitiligo_type
            if vitiligo_stage:
                existing.stage = vitiligo_stage
            if ai_mask:
                existing.ai_mask_b64 = ai_mask
            if ai_contours_json:
                existing.ai_contours_json = ai_contours_json
            if dice_score is not None:
                existing.dice_score = dice_score
            if area_error_pct is not None:
                existing.area_error_pct = area_error_pct
            existing.quality_level = "good"  # admin label = gold
            self.db.commit()
            logger.info(
                "Updated training sample from admin label %s: hash=%s dice=%.3f",
                label.id, label.image_hash[:8], dice_score or 0,
            )
            return existing

        # Create new
        sample = VasiTrainingSample(
            image_hash=label.image_hash,
            image_key=label.image_key or "",
            body_site=body_site,
            sample_source="admin_labeling",
            vitiligo_type=vitiligo_type,
            stage=vitiligo_stage,
            quality_level="good",
            admin_mask_b64=admin_mask,
            admin_label_id=admin_label_id,
            ai_mask_b64=ai_mask,
            ai_contours_json=ai_contours_json,
            dice_score=dice_score,
            area_error_pct=area_error_pct,
            confidence=getattr(label, "ai_confidence", None),
        )
        self.db.add(sample)
        self.db.commit()
        logger.info(
            "Created training sample from admin label %s: hash=%s site=%s dice=%.3f",
            label.id, label.image_hash[:8], body_site, dice_score or 0,
        )
        return sample

    def export_training_samples(
        self,
        body_site: Optional[str] = None,
        quality_level: Optional[str] = None,
        min_dice: Optional[float] = None,
        limit: int = 100,
    ) -> List[VasiTrainingSample]:
        """导出训练样本（支持筛选）"""
        query = self.db.query(VasiTrainingSample).filter(
            VasiTrainingSample.is_active == True
        )

        if body_site:
            query = query.filter(VasiTrainingSample.body_site == body_site)
        if quality_level:
            query = query.filter(VasiTrainingSample.quality_level == quality_level)
        if min_dice is not None:
            query = query.filter(VasiTrainingSample.dice_score >= min_dice)

        return query.order_by(VasiTrainingSample.created_at.desc()).limit(limit).all()

    def count_training_samples(
        self,
        quality_level: Optional[str] = "good",
        min_dice: float = 0.5,
    ) -> int:
        """统计高质量训练样本数量"""
        query = self.db.query(func.count(VasiTrainingSample.id)).filter(
            VasiTrainingSample.is_active == True,
            VasiTrainingSample.user_mask_b64 != None,  # 必须有用户修正
        )
        if quality_level:
            query = query.filter(VasiTrainingSample.quality_level == quality_level)
        if min_dice:
            query = query.filter(VasiTrainingSample.dice_score >= min_dice)
        return query.scalar() or 0

    def get_recent_samples(self, days: int = 7, limit: int = 10) -> List[VasiTrainingSample]:
        """获取最近的训练样本"""
        cutoff = datetime.utcnow() - timedelta(days=days)
        return (
            self.db.query(VasiTrainingSample)
            .filter(
                VasiTrainingSample.created_at >= cutoff,
                VasiTrainingSample.is_active == True,
            )
            .order_by(VasiTrainingSample.created_at.desc())
            .limit(limit)
            .all()
        )

    # ── 6. 统计查询 ──

    def get_feedback_stats(
        self,
        days: int = 30,
    ) -> Dict[str, Any]:
        """获取反馈统计信息"""
        cutoff = datetime.utcnow() - timedelta(days=days)

        total_corrections = (
            self.db.query(func.count(VasiFeedbackSignal.id))
            .filter(
                VasiFeedbackSignal.signal_type == "explicit_correction",
                VasiFeedbackSignal.created_at >= cutoff,
            )
            .scalar() or 0
        )

        total_ratings = (
            self.db.query(func.count(VasiFeedbackSignal.id))
            .filter(
                VasiFeedbackSignal.signal_type == "explicit_rating",
                VasiFeedbackSignal.created_at >= cutoff,
            )
            .scalar() or 0
        )

        training_samples = self.count_training_samples()

        return {
            "period_days": days,
            "total_corrections": total_corrections,
            "total_ratings": total_ratings,
            "training_samples": training_samples,
            "ready_for_prompt_evo": training_samples >= 20,
            "ready_for_param_evo": training_samples >= 50,
            "ready_for_nnunet": training_samples >= 200,
        }


# ══════════════════════════════════════════════════════════════════════════════
# Module-level convenience
# ══════════════════════════════════════════════════════════════════════════════

# ═══ SELF-EVOLVING DISABLED (2026-06-13) — data insufficient for effective RL ═══
def get_feedback_collector(db: Session) -> VasiFeedbackCollector:
    return None  # DISABLED — insufficient training data

    """获取 VasiFeedbackCollector 实例"""
    return VasiFeedbackCollector(db)
