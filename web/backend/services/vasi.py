"""
VASI评估服务
"""
from web.backend.utils.timeutils import iso_utc

import os
import json
import asyncio
import base64
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
from sqlalchemy.orm import Session

from web.backend.models.vasi import VASIAssessment
from web.backend.utils.assessment_body_sites import BODY_SITE_LABELS as SHARED_BODY_SITE_LABELS
from web.backend.database.database import get_db
from web.backend.services.vasi_segmentation import segment_vitiligo, segment_vitiligo_guided, consolidate_segmentation
from web.backend.services.vasi_formula import compute_vasi_v2
from web.backend.services.assessment_measurement import (decode_mask, measure_layers, normalize_capture, read_details)

logger = logging.getLogger(__name__)

# ── Feature toggle: VLM ensemble (two independent calls + lesion intersection) ──
# Doubles API cost. Enables stability when VLM stochasticity is problematic.
# Set to True in _call_vasi_api for production-critical assessments.
ENABLE_VLM_ENSEMBLE = False


class VASIAssessmentError(Exception):
    """VASI评估错误"""

    pass


# ── Image magic-byte signatures ──
# Verifies the actual bytes of an uploaded image match its declared type, so a
# polyglot or malicious file renamed to .jpg is rejected before reaching VLM/SAM.
_IMAGE_MAGIC = (
    (b"\xff\xd8\xff", "image/jpeg"),         # JPEG (SOI + marker)
    (b"\x89PNG\r\n\x1a\n", "image/png"),     # PNG
    (b"RIFF", "image/webp"),                 # WebP (RIFF....WEBP)
)


def _has_valid_image_magic(data: bytes) -> bool:
    if not data:
        return False
    for sig, _kind in _IMAGE_MAGIC:
        if data.startswith(sig):
            # WebP needs the WEBP chunk at offset 8
            if sig == b"RIFF":
                return len(data) >= 12 and data[8:12] == b"WEBP"
            return True
    return False


def _data_url_to_mask(data_url: Optional[str], target_shape) -> Optional[Any]:
    """data URL PNG → 二值掩膜（目标尺寸）。失败返回 None。"""
    return decode_mask(data_url, target_shape)


def _run_patient_consensus_sync(db: Session, user_id: int, body_site: str,
                                image_file: bytes,
                                vasi_result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """评估时执行患者级画布管线 + 共识（同步，供 asyncio.to_thread 调用）。

    SAM 掩膜在预处理图坐标（最长边 1024），需映射回原图坐标后参与共识。
    分歧时自动排入 LLM 裁判队列（后台限速处理）。
    """
    import cv2
    import numpy as np

    from web.backend.services.vasi_consensus import run_patient_consensus
    from web.backend.services.vasi_autoloop import queue_judge

    orig = cv2.imdecode(np.frombuffer(image_file, np.uint8), cv2.IMREAD_COLOR)
    if orig is None:
        return None
    details = vasi_result.get("details") or {}
    sam_lesion = _data_url_to_mask(details.get("lesion_layer_data_url"), orig.shape)
    sam_skin = _data_url_to_mask(details.get("skin_layer_data_url"), orig.shape)

    consensus_data = run_patient_consensus(
        db, user_id, body_site, image_file, None,
        sam_lesion_mask_orig=sam_lesion, sam_skin_mask_orig=sam_skin,
    )

    if not consensus_data or not consensus_data.get("participated"):
        return consensus_data

    cons = consensus_data.get("consensus") or {}
    if cons.get("verdict") == "disputed_needs_judge":
        # 分歧区 = SAM 与患者掩膜并集 bbox（原图坐标，归一化）
        masks = [m for m in (sam_lesion, consensus_data.get("patient_mask_orig"))
                 if m is not None and m.any()]
        try:
            union = np.zeros(orig.shape[:2], dtype=bool)
            for m in masks:
                union |= m
            if union.any():
                ys, xs = np.where(union)
                h, w = orig.shape[:2]
                bbox = [float(xs.min()) / w, float(ys.min()) / h,
                        float(xs.max()) / w, float(ys.max()) / h]
                # 找到评估 id 后入队（评估记录尚未创建，此处先挂到共识 JSON，
                # assess_vasi 落库后由 queue_judge_for_assessment 处理）
                consensus_data["_judge_bbox"] = bbox
        except Exception:
            pass
    return consensus_data


def queue_judge_for_assessment(db: Session, assessment_id: int,
                               consensus_data: Dict[str, Any]) -> bool:
    """评估落库后：分歧区排入 LLM 裁判队列。"""
    bbox = consensus_data.get("_judge_bbox")
    if not bbox:
        return False
    try:
        from web.backend.services.vasi_autoloop import queue_judge
        return queue_judge(db, assessment_id, {"bbox": bbox})
    except Exception:
        return False


class VASIService:
    """VASI评估服务

    提供VASI（白癜风面积严重程度指数）评估功能
    """

    VALID_BODY_SITES = [
        # Standard (non-sided)
        "face",
        "neck",
        "hands",
        "abdomen",
        "back",
        "arms",
        "legs",
        "feet",
        "other",
        "面部",
        "颈部",
        "手部",
        "腹部",
        "背部",
        "上肢",
        "下肢",
        "足部",
        "其他",
        # Sided variants (frontend bodySites.ts)
        "chest",
        "upper_back",
        "lower_back",
        "left_arm",
        "right_arm",
        "left_hand",
        "right_hand",
        "left_leg",
        "right_leg",
        "left_foot",
        "right_foot",
    ]

    BODY_SITE_LABELS = SHARED_BODY_SITE_LABELS

    ALLOWED_IMAGE_TYPES = ["image/jpeg", "image/png", "image/jpg", "image/webp"]

    # 最大图片大小（10MB）
    MAX_IMAGE_SIZE = 10 * 1024 * 1024

    def __init__(self, db: Session):
        self.db = db
        # Initialize optional services with graceful fallback
        self.preprocessor = self._init_preprocessor()
        self.quality_checker = self._init_quality_checker()
        self.segmentation = self._init_segmentation()

    @staticmethod
    def _init_preprocessor():
        try:
            from web.backend.services.vasi_preprocess import VasiImagePreprocessor
            return VasiImagePreprocessor()
        except Exception as e:
            logger.warning("VasiImagePreprocessor not available: %s", e)
            return None

    @staticmethod
    def _init_quality_checker():
        try:
            from web.backend.services.vasi_quality import VasiQualityChecker
            return VasiQualityChecker()
        except Exception as e:
            logger.warning("VasiQualityChecker not available: %s", e)
            return None

    @staticmethod
    def _init_segmentation():
        try:
            from web.backend.services.vasi_segmentation import nnUNetSegmentationService
            return nnUNetSegmentationService()
        except Exception as e:
            logger.warning("nnUNetSegmentationService not available: %s", e)
            return None

    async def assess_vasi(
        self,
        user_id: int,
        image_file: bytes,
        body_site: str,
        image_type: str,
        image_filename: str,
        precision: str = "quick",
        annotation_protocol: str = "",
    ) -> VASIAssessment:
        """执行VASI评估

        Args:
            user_id: 用户ID
            image_file: 图片二进制数据
            body_site: 评估部位
            image_type: 图片MIME类型
            image_filename: 图片文件名
            precision: "quick" (~10s) 或 "precise" (~70s)

        Returns:
            VASIAssessment: 评估记录

        Raises:
            VASIAssessmentError: 评估失败
        """
        self._validate_input(image_file, body_site, image_type)

        body_site = self.BODY_SITE_LABELS.get(body_site, body_site)
        normalized_image = normalize_capture(image_file)
        if self.quality_checker and self.quality_checker.available:
            quality = self.quality_checker.check_all(normalized_image)
            if quality.overall == "poor":
                raise VASIAssessmentError("照片暂不适合分析：" + "；".join(quality.suggestions))

        # 上传图片到对象存储（TODO：实现实际的OSS上传）
        image_url, image_key = await self._upload_image(
            user_id, image_file, image_filename
        )

        # 调用VASI识别API（TODO：等方案确定后实现）
        if annotation_protocol:
            from web.backend.services.annotation_contract import PROTOCOL, AnnotationContractError
            from web.backend.services.annotation_provider import propose_annotation
            from web.backend.services.vasi_pixel_refine import (
                cv_only_layers,
                refine_annotation_layers,
            )
            if annotation_protocol != PROTOCOL:
                raise VASIAssessmentError("不支持的标注协议")
            try:
                vasi_result = await propose_annotation(normalized_image, body_site)
            except AnnotationContractError as exc:
                # 视觉模型拒答/不可用：降级为纯 CV 逐像素，仍交付逐像素结果而不是报错。
                # 设计见 docs/specs/2026-09-12-pixel-level-vitiligo-refine-design.md §3.4
                degraded = await asyncio.to_thread(cv_only_layers, normalized_image)
                if not degraded:
                    raise VASIAssessmentError(str(exc)) from exc
                logger.info(
                    "annotation model unavailable (%s); degraded to cv-only pixel layers",
                    type(exc).__name__,
                )
                vasi_result = {
                    "vasi_score": 0.0, "area_percentage": 0.0,
                    "classification": "未确定", "stage": "未知",
                    "confidence": None, "contours": [], "source": "cv-pixel-fallback",
                    "details": degraded,
                    "raw_response": {
                        "source": "cv-pixel-fallback",
                        "reason": "annotation model unavailable",
                    },
                    "visual_features": None,
                }
            else:
                # 逐像素精修：大模型只给候选，SAM/边缘感知决定最终边界。
                geometry = (vasi_result.get("raw_response") or {}).get("geometry") or {}
                refined = await asyncio.to_thread(
                    refine_annotation_layers, normalized_image, geometry
                )
                if refined:
                    prior_annotation = dict(vasi_result.get("details", {}).get("annotation") or {})
                    vasi_result.setdefault("details", {}).update(refined)
                    vasi_result["details"]["annotation"] = {**prior_annotation, **refined["annotation"]}
                    if (refined.get("provenance") or {}).get("status") != "candidate-only":
                        vasi_result["source"] = "vision-outline-v1+refine"
        else:
            vasi_result = await self._call_vasi_api(normalized_image, precision, body_site)

        measurement = measure_layers(
            vasi_result.get("details", {}).get("skin_layer_data_url"),
            vasi_result.get("details", {}).get("lesion_layer_data_url"), normalized_image,
        )
        from web.backend.services.annotation_measurement_policy import guard_annotation_measurement
        measurement = guard_annotation_measurement(measurement, vasi_result.get("details", {}).get("annotation"))
        vasi_result.setdefault("details", {})["measurement"] = measurement
        # Legacy numeric fields are retained for API compatibility only.
        vasi_result["stage"] = "未知"
        vasi_result["classification"] = "未确定"
        if measurement["area_percentage"] is not None:
            vasi_result["area_percentage"] = measurement["area_percentage"]

        # ── 患者级画布管线 + 共识（全自动自循环，2026-08-27）──
        # SAM 掩膜（预处理图坐标）与患者像素分类器掩膜（统一画布坐标）共识；
        # 共识达标 + 质检门禁通过 → 自动终审 active，无需用户确认。
        consensus_data: Optional[Dict[str, Any]] = None
        try:
            if not annotation_protocol:
                consensus_data = await asyncio.to_thread(
                    _run_patient_consensus_sync,
                    self.db, user_id, body_site, normalized_image, vasi_result,
                )
        except Exception as e:
            logger.info("patient consensus skipped (%s)", e)

        # 创建评估记录
        details_data = vasi_result.get("details", {})
        details_data["contours"] = vasi_result.get("contours", [])

        confidence = vasi_result.get("confidence")
        if confidence is None and isinstance(details_data, dict):
            confidence = details_data.get("confidence")

        quality_report_json = None
        if isinstance(details_data, dict) and details_data.get("quality_reject"):
            quality_report_json = json.dumps(vasi_result["raw_response"].get("quality_report", {}))

        preprocessed = self.preprocessor is not None and self.preprocessor.available

        assessment_source = vasi_result.get("source", "mock")
        logger.info(
            "VASI assessment source=%s, confidence=%s, preprocessed=%s",
            assessment_source,
            confidence,
            preprocessed,
        )

        # ── 共识结果与自动终审判定 ──
        auto_finalized = False
        patient_model_version: Optional[str] = None
        consensus_json: Optional[str] = None
        canvas_json: Optional[str] = None
        if consensus_data:
            canvas_json = json.dumps(consensus_data["snapshot"], ensure_ascii=False) \
                if consensus_data.get("snapshot") else None
            patient_model_version = consensus_data.get("patient_model_version")
            consensus_json = json.dumps(consensus_data.get("consensus") or {},
                                        ensure_ascii=False)
            quality_overall = None
            if isinstance(details_data, dict) and details_data.get("quality"):
                quality_overall = details_data["quality"].get("overall")
            if (consensus_data.get("auto_finalize") and quality_overall in ("good", "acceptable")
                    and measurement["status"] == "measured"):
                auto_finalized = True

        assessment = VASIAssessment(
            status="active" if auto_finalized else "draft",
            user_id=user_id,
            image_url=image_url,
            image_key=image_key,
            vasi_score=vasi_result["vasi_score"],
            body_site=body_site,
            area_percentage=vasi_result["area_percentage"],
            classification=vasi_result["classification"],
            stage=vasi_result["stage"],
            details=json.dumps(details_data),
            raw_api_response=json.dumps(vasi_result["raw_response"]),
            assessment_source=assessment_source,
            confidence=confidence,
            quality_report_json=quality_report_json,
            preprocessed=preprocessed,
            image_hash=__import__("hashlib").sha256(image_file).hexdigest(),
            ai_skin_layer=details_data.get("skin_layer_data_url"),
            ai_lesion_layer=details_data.get("lesion_layer_data_url"),
            visual_features_json=json.dumps(vasi_result.get("visual_features")) if vasi_result.get("visual_features") else None,
            canvas_json=canvas_json,
            patient_model_version=patient_model_version,
            consensus_json=consensus_json,
            auto_finalized=auto_finalized,
        )

        self.db.add(assessment)
        self.db.commit()
        self.db.refresh(assessment)

        # 分歧评估 → LLM 裁判队列（后台限速复核，无需用户参与）
        if consensus_data and consensus_data.get("_judge_bbox"):
            try:
                queue_judge_for_assessment(self.db, assessment.id, consensus_data)
            except Exception as e:
                logger.info("queue judge skipped: %s", e)

        if auto_finalized:
            logger.info(
                "VASI assessment %d auto-finalized (consensus=%s, model=%s)",
                assessment.id,
                (json.loads(consensus_json) if consensus_json else {}).get("verdict"),
                patient_model_version,
            )

        return assessment


    def finalize_assessment(self, assessment_id: int, user_id: int) -> bool:
        """确认草稿测评，将其状态从draft改为active。
        
        如果用户没有走完完整流程，草稿不会被确认，
        后续可以被清理任务删除。
        """
        assessment = (
            self.db.query(VASIAssessment)
            .filter(VASIAssessment.id == assessment_id, VASIAssessment.user_id == user_id)
            .first()
        )
        if not assessment:
            return False
        if read_details(assessment.details).get("quality_reject"):
            raise VASIAssessmentError("照片质检未通过，请重新拍摄")
        details = read_details(assessment.details)
        annotation = details.get("annotation") or {}
        if annotation and annotation.get("review_state") != "user_reviewed":
            raise VASIAssessmentError("请先核对皮肤、浅色范围和不确定区域后保存")
        if assessment.status == "active":
            return True  # already finalized
        assessment.status = "active"
        assessment.updated_at = datetime.utcnow()
        self.db.commit()
        logger.info("VASI assessment %d finalized by user %d", assessment_id, user_id)
        return True

    def abandon_assessment(self, assessment_id: int, user_id: int) -> bool:
        """放弃草稿测评，标记为abandoned。"""
        assessment = (
            self.db.query(VASIAssessment)
            .filter(VASIAssessment.id == assessment_id, VASIAssessment.user_id == user_id)
            .first()
        )
        if not assessment:
            return False
        assessment.status = "abandoned"
        assessment.updated_at = datetime.utcnow()
        self.db.commit()
        logger.info("VASI assessment %d abandoned by user %d", assessment_id, user_id)
        return True

    def get_user_history(
        self,
        user_id: int,
        limit: int = 10,
        offset: int = 0,
        body_site: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> tuple[int, List[VASIAssessment]]:
        """获取用户评估历史

        Args:
            user_id: 用户ID
            limit: 返回数量限制
            offset: 偏移量
            body_site: 筛选部位
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            tuple: (总数, 评估记录列表)
        """
        # History should only contain finalized (active) assessments — drafts
        # and abandoned assessments do not represent confirmed clinical state
        # and would pollute the history list / trend chart.
        query = self.db.query(VASIAssessment).filter(
            VASIAssessment.user_id == user_id,
            VASIAssessment.status == "active",
        )

        # 筛选条件：body_site 可能是前端传来的英文 key，需要翻译成中文 label
        if body_site:
            body_site = self.BODY_SITE_LABELS.get(body_site, body_site)
            query = query.filter(VASIAssessment.body_site == body_site)

        if start_date:
            query = query.filter(VASIAssessment.assessment_date >= start_date)

        if end_date:
            query = query.filter(VASIAssessment.assessment_date <= end_date)

        # 获取总数
        total = query.count()

        # 分页查询
        assessments = (
            query.order_by(VASIAssessment.assessment_date.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

        return total, assessments

    def get_assessment_by_id(
        self, assessment_id: int, user_id: int
    ) -> Optional[VASIAssessment]:
        """获取单条评估详情

        Args:
            assessment_id: 评估ID
            user_id: 用户ID（用于权限验证）

        Returns:
            VASIAssessment: 评估记录，如果不存在返回None
        """
        return (
            self.db.query(VASIAssessment)
            .filter(
                VASIAssessment.id == assessment_id, VASIAssessment.user_id == user_id
            )
            .first()
        )

    def delete_assessment(self, assessment_id: int, user_id: int) -> bool:
        assessment = (
            self.db.query(VASIAssessment)
            .filter(VASIAssessment.id == assessment_id, VASIAssessment.user_id == user_id)
            .first()
        )
        if not assessment:
            return False

        from web.backend.models.image_label import ImageLabel
        link = self.db.query(ImageLabel).filter(
            ImageLabel.assessment_id == assessment_id,
        ).first()
        if link:
            link.is_user_deleted = True
        else:
            link = ImageLabel(
                assessment_id=assessment_id,
                original_user_id=user_id,
                image_url=assessment.image_url,
                image_key=assessment.image_key,
                image_hash=assessment.image_hash,
                ai_body_site=assessment.body_site,
                ai_vitiligo_type=assessment.classification,
                ai_vitiligo_stage=assessment.stage,
                ai_area_percentage=assessment.final_area_percentage or assessment.area_percentage,
                ai_vasi_score=assessment.final_vasi_score or assessment.vasi_score,
                ai_confidence=assessment.confidence,
                ai_details=assessment.details,
                is_user_deleted=True,
            )
            self.db.add(link)

        self.db.delete(assessment)
        self.db.commit()
        return True

    def delete_assessments_batch(self, assessment_ids: List[int], user_id: int) -> int:
        from web.backend.models.image_label import ImageLabel

        # Only operate on assessments actually owned by this user. Without this
        # scope check, a caller could pass another user's assessment_id and, when
        # an ImageLabel row already exists for it, flip is_user_deleted on
        # another user's label metadata (cross-user IDOR).
        owned = {
            a.id: a
            for a in self.db.query(VASIAssessment)
            .filter(VASIAssessment.id.in_(assessment_ids), VASIAssessment.user_id == user_id)
            .all()
        }

        for aid in assessment_ids:
            if aid not in owned:
                # Not owned by this user — skip to prevent cross-user mutation.
                continue
            assessment = owned[aid]
            link = self.db.query(ImageLabel).filter(
                ImageLabel.assessment_id == aid,
            ).first()
            if link:
                link.is_user_deleted = True
            else:
                link = ImageLabel(
                    assessment_id=aid,
                    original_user_id=user_id,
                    image_url=assessment.image_url,
                    image_key=assessment.image_key,
                    image_hash=assessment.image_hash,
                    ai_body_site=assessment.body_site,
                    ai_vitiligo_type=assessment.classification,
                    ai_vitiligo_stage=assessment.stage,
                    ai_area_percentage=assessment.final_area_percentage or assessment.area_percentage,
                    ai_vasi_score=assessment.final_vasi_score or assessment.vasi_score,
                    ai_confidence=assessment.confidence,
                    ai_details=assessment.details,
                    is_user_deleted=True,
                )
                self.db.add(link)

        deleted = (
            self.db.query(VASIAssessment)
            .filter(VASIAssessment.id.in_(list(owned.keys())), VASIAssessment.user_id == user_id)
            .delete(synchronize_session=False)
        )
        self.db.commit()
        return deleted

    def get_trend_data(
        self, user_id: int, body_site: Optional[str] = None, days: int = 30
    ) -> Dict[str, Any]:
        """获取趋势数据（用于曲线图）

        Args:
            user_id: 用户ID
            body_site: 筛选部位
            days: 天数

        Returns:
            dict: 趋势数据
        """
        from datetime import timedelta

        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)

        query = self.db.query(VASIAssessment).filter(
            VASIAssessment.user_id == user_id,
            VASIAssessment.assessment_date >= start_date,
            VASIAssessment.assessment_date <= end_date,
            # Trend must reflect confirmed clinical state only — exclude drafts
            # and abandoned assessments so the curve isn't distorted by
            # unconfirmed or discarded evaluations.
            VASIAssessment.status == "active",
        )

        if body_site:
            body_site = self.BODY_SITE_LABELS.get(body_site, body_site)
            query = query.filter(VASIAssessment.body_site == body_site)

        assessments = query.order_by(VASIAssessment.assessment_date.asc()).all()

        if not assessments:
            return {
                "body_site": body_site or "全部",
                "period": {
                    "start": iso_utc(start_date),
                    "end": iso_utc(end_date),
                },
                "data": [],
                "summary": {
                    "first_score": None,
                    "last_score": None,
                    "change": None,
                    "change_percent": None,
                    "trend": "无数据",
                },
            }

        # Photographic scores have changing ROIs/versions and cannot form a
        # clinical time series. Use the verified pair-comparison endpoint.
        return {
            "body_site": body_site or "全部",
            "period": {"start": iso_utc(start_date), "end": iso_utc(end_date)},
            "data": [],
            "summary": {"first_score": None, "last_score": None, "change": None,
                        "change_percent": None, "trend": "无法可靠比较"},
        }

    def _validate_input(
        self, image_file: bytes, body_site: str, image_type: str
    ) -> None:
        """验证输入参数

        Raises:
            VASIAssessmentError: 验证失败
        """
        # 验证图片大小
        if len(image_file) > self.MAX_IMAGE_SIZE:
            raise VASIAssessmentError(
                f"图片过大，最大支持{self.MAX_IMAGE_SIZE / 1024 / 1024}MB"
            )

        # 验证图片格式
        if image_type not in self.ALLOWED_IMAGE_TYPES:
            raise VASIAssessmentError(
                f"不支持的图片格式，支持: {', '.join(self.ALLOWED_IMAGE_TYPES)}"
            )

        # Magic-byte verification: Content-Type can be spoofed, so verify the
        # actual file signature to reject polyglot / mis-labeled uploads before
        # they reach the VLM/SAM pipeline. WebP is accepted here too even though
        # ALLOWED_IMAGE_TYPES is JPEG/PNG-focused, because the VLM path supports it.
        if not _has_valid_image_magic(image_file):
            raise VASIAssessmentError(
                "图片内容与声明格式不符（magic byte 校验失败），请上传真实的 JPG/PNG/WebP 图片"
            )

        # 验证身体部位
        if body_site not in self.VALID_BODY_SITES:
            supported = ", ".join(sorted(set(self.BODY_SITE_LABELS.values())))
            raise VASIAssessmentError(f"无效的身体部位，支持: {supported}")

    async def _upload_image(
        self, user_id: int, image_file: bytes, filename: str
    ) -> tuple[str, str]:
        import hashlib
        import time
        from pathlib import Path
        import uuid

        file_hash = hashlib.md5(image_file).hexdigest()
        timestamp = int(time.time())
        ext = Path(filename).suffix or ".jpg"

        upload_dir = Path("data/uploads/vasi")
        upload_dir.mkdir(parents=True, exist_ok=True)

        stored_name = f"{timestamp}_{uuid.uuid4().hex[:8]}{ext}"
        file_path = upload_dir / stored_name
        file_path.write_bytes(image_file)

        image_url = f"/api/files/serve/vasi/{stored_name}"
        # image_key MUST match the actual on-disk relative path so downstream
        # RL/training pipelines can locate the file. Previously this used a
        # {user_id}/{timestamp}_{file_hash[:8]} key that never corresponded to a
        # real file, so RL training could never load the image. The hash is
        # preserved as a separate field for dedup/audit.
        image_key = f"vasi/{stored_name}"

        return image_url, image_key

    async def _call_vasi_api(self, image_file: bytes, precision: str = "quick", body_site: str = "面部") -> Dict[str, Any]:
        """Call AI services for VASI assessment.

        Flow (v2): quality check → preprocess → VLM classification +
        localization → SAM guided by VLM → combine → nnU-Net fallback → mock.

        Args:
            image_file: Raw image bytes.

        Returns:
            dict: VASI assessment result.
        """
        quality_summary = None
        if self.quality_checker and self.quality_checker.available:
            quality = self.quality_checker.check_all(image_file)
            quality_summary = {
                "overall": quality.overall,
                "suggestions": quality.suggestions,
                "blur_score": quality.blur_score,
            }
            # Reject poor-quality photos up front: return structured quality
            # feedback with improvement suggestions instead of running AI on
            # an unusable image (which previously fabricated low-confidence
            # scores or wasted LLM/VLM budget). The caller/UI must surface the
            # suggestions; no clinical score is persisted for poor photos.
            if quality.overall == "poor":
                logger.info("VASI quality reject (overall=poor, blur=%.1f)", quality.blur_score)
                raise VASIAssessmentError("照片暂不适合分析：" + "；".join(quality.suggestions))

        # 质检摘要随结果带出（自动终审门禁用，additive）
        def _attach_quality(result: Dict[str, Any]) -> None:
            if quality_summary and isinstance(result, dict):
                details = result.get("details")
                if isinstance(details, dict):
                    details["quality"] = quality_summary

        # Keep color/edge evidence unenhanced. Segmentation handles its own resizing.
        processed_image = image_file

        # Step 3: VLM first — get classification + localization guidance
        # Enable ensemble (run twice, intersect) only in precise mode for stability
        use_ensemble = ENABLE_VLM_ENSEMBLE or precision == "precise"
        if use_ensemble:
            vlm_result = await self._call_vision_model_ensemble(processed_image, body_site)
        else:
            vlm_result = await self._call_vision_model(processed_image, body_site)

        # Extract VLM localization for SAM
        skin_bbox: Optional[List[float]] = None
        lesion_centers: Optional[List[List[float]]] = None
        lesion_sizes: Optional[List[float]] = None
        lesion_bboxes: Optional[List[List[float]]] = None
        lesion_edge_points: Optional[List[List[List[float]]]] = None
        depigmentation_level = None
        if vlm_result:
            depigmentation_level = vlm_result.get("depigmentation_level")
            skin_region = vlm_result.get("skin_region", {})
            if skin_region and skin_region.get("bbox"):
                bbox = skin_region["bbox"]
                if len(bbox) == 4 and all(0 <= v <= 1.5 for v in bbox):
                    skin_bbox = [float(v) for v in bbox]
            lesions = vlm_result.get("suspected_lesions", [])
            raw_lesion_count = len(lesions)
            
            # ── Confidence filtering: tiered approach ──
            # v2: lowered threshold from 0.85 → 0.7 to reduce false negatives.
            # Lesions with 0.7-0.85 confidence are kept but flagged for user verification.
            CONFIDENCE_THRESHOLD_MIN = 0.7
            CONFIDENCE_THRESHOLD_HIGH = 0.85
            filtered_count = 0
            verified_count = 0
            kept_lesions = []
            for l in lesions:
                conf = float(l.get("confidence", 0.5))
                if conf < CONFIDENCE_THRESHOLD_MIN:
                    filtered_count += 1
                    continue
                if conf < CONFIDENCE_THRESHOLD_HIGH:
                    l["needs_verification"] = True
                    verified_count += 1
                kept_lesions.append(l)
            lesions = kept_lesions
            if filtered_count > 0 or verified_count > 0:
                logger.info(
                    "Confidence filter: dropped %d, flagged %d for verification, kept %d/%d",
                    filtered_count, verified_count, len(lesions), raw_lesion_count,
                )

            # Size alone is not evidence against a lesion. Preserve large patches;
            # reject only invalid geometry, including non-finite/out-of-frame boxes.
            import math
            lesions = [l for l in lesions if not l.get("bbox") or (
                len(l["bbox"]) == 4
                and all(isinstance(v, (float, int)) and math.isfinite(v) and 0 <= v <= 1 for v in l["bbox"])
                and l["bbox"][2] > l["bbox"][0] and l["bbox"][3] > l["bbox"][1]
            )]

            # Write the filtered lesion list back into vlm_result so downstream
            # enrichment (per-lesion depig/contrast/confidence matching) uses the
            # SAME filtered set that guided SAM — otherwise metadata is matched
            # against unfiltered lesions and the weighted VASI score is wrong.
            vlm_result["suspected_lesions"] = lesions

            if lesions:
                lesion_centers = [
                    [float(l["center"][0]), float(l["center"][1])]
                    for l in lesions
                    if l.get("center") and len(l["center"]) == 2
                ]
                # Also pass VLM's size estimates for box-prompt inference
                lesion_sizes = [
                    float(l.get("estimated_size_percent", 5.0))
                    for l in lesions
                    if l.get("center") and len(l["center"]) == 2
                ]
                # Rebuild lesion_bboxes from filtered lesions (sync with confidence/bbox filtering)
                lesion_bboxes = []
                for l in lesions:
                    bbox = l.get("bbox")
                    if bbox and len(bbox) == 4:
                        valid = all(isinstance(v, (int, float)) and 0 <= v <= 1.5 for v in bbox)
                        if valid and bbox[2] > bbox[0] and bbox[3] > bbox[1]:
                            lesion_bboxes.append([float(v) for v in bbox])

                # Rebuild lesion_edge_points aligned with lesion_centers (same
                # filter: center present) so SAM can index them in lockstep.
                # Each entry is a list of [x,y] boundary points (possibly empty).
                lesion_edge_points = []
                for l in lesions:
                    if not (l.get("center") and len(l["center"]) == 2):
                        continue
                    pts: List[List[float]] = []
                    for pt in (l.get("edge_points") or []):
                        if (isinstance(pt, (list, tuple)) and len(pt) == 2
                                and isinstance(pt[0], (int, float))
                                and isinstance(pt[1], (int, float))):
                            pts.append([float(pt[0]), float(pt[1])])
                    lesion_edge_points.append(pts)

            # Per-lesion metadata for adaptive SAM (contrast, confidence, depig)
            lesion_metas: Optional[List[Dict[str, Any]]] = None
            if lesions:
                lesion_metas = [
                    {
                        "contrast": float(l.get("contrast_to_skin", 0.5)),
                        "confidence": float(l.get("confidence", 0.5)),
                        "depigmentation": l.get("depigmentation_level"),
                    }
                    for l in lesions
                    if l.get("center") and len(l["center"]) == 2
                ]

        # Step 4: SAM with VLM guidance (or auto if no guidance)
        has_guidance = bool(skin_bbox or lesion_centers)
        if has_guidance:
            bbox_count = len(lesion_bboxes) if lesion_bboxes else 0
            edge_count = sum(1 for pts in (lesion_edge_points or []) if pts)
            is_vlm_ensemble = bool(vlm_result.get("_ensemble")) if vlm_result else False
            logger.info(
                "Using VLM-guided SAM: skin_bbox=%s, lesion_centers=%d, lesion_bboxes=%d, lesion_edge_pts=%d, ensemble=%s",
                skin_bbox, len(lesion_centers) if lesion_centers else 0, bbox_count, edge_count, is_vlm_ensemble,
            )
            seg_result = await asyncio.to_thread(
                segment_vitiligo_guided,
                processed_image, skin_bbox, lesion_centers, precision,
                lesion_sizes if lesion_sizes else None,
                lesion_bboxes if lesion_bboxes else None,
                lesion_metas if lesion_metas else None,
                is_vlm_ensemble,
                lesion_edge_points if lesion_edge_points else None,
            )
        else:
            logger.info("No VLM guidance available, using auto SAM")
            seg_result = await asyncio.to_thread(
                segment_vitiligo, processed_image, 0.005, 100, precision
            )

        seg_contours: List[Dict[str, Any]] = []
        seg_area: Optional[float] = None
        seg_source = "none"
        skin_region_ratio: Optional[float] = seg_result.get("skin_region_ratio")
        denominator = seg_result.get("denominator", "image")
        skin_layer_data_url = seg_result.get("skin_layer_data_url")
        lesion_layer_data_url = seg_result.get("lesion_layer_data_url")

        if seg_result["success"]:
            seg_contours = seg_result["contours"]
            seg_area = seg_result["total_area_percent"]
            seg_source = seg_result["source"]
            logger.info(
                "SAM segmentation: %d patches, %.1f%% of skin (skin=%.1f%% of image, source=%s)",
                len(seg_contours), seg_area or 0,
                skin_region_ratio or 0, seg_source,
            )
        elif has_guidance:
            seg_result = await asyncio.to_thread(segment_vitiligo, processed_image, 0.005, 100, precision)
        # A single canonical binary mask supplies both overlays and numeric area.
        # Do not append unclassified tile masks or add overlapping polygon areas.
        seg_result = consolidate_segmentation(processed_image, seg_result)
        seg_contours = seg_result.get("contours", [])
        seg_area = seg_result.get("total_area_percent") if seg_result.get("success") else None
        seg_source = seg_result.get("source", "none")
        skin_layer_data_url = seg_result.get("skin_layer_data_url")
        lesion_layer_data_url = seg_result.get("lesion_layer_data_url")
        skin_region_ratio = seg_result.get("skin_region_ratio")
        denominator = seg_result.get("denominator", "unknown")

        if vlm_result is not None:
            if seg_area is not None:
                # ── Per-lesion metadata enrichment ──
                # Enrich each SAM contour with VLM per-lesion metadata
                # (depigmentation, contrast, confidence) for clinical accuracy.
                lesions = vlm_result.get("suspected_lesions", [])
                enriched_contours: List[Dict[str, Any]] = []
                weighted_depig_sum = 0.0
                weighted_area_sum = 0.0
                contrast_adjusted_area = 0.0

                for i, c in enumerate(seg_contours):
                    area_i = float(c.get("area_percent", 0))
                    area_img = float(c.get("area_percent_in_image", 0))
                    # Match VLM lesion by index (1:1 via per-lesion bbox)
                    vlm_lesion = lesions[i] if i < len(lesions) else {}
                    depig_raw = vlm_lesion.get("depigmentation_level")
                    contrast = float(vlm_lesion.get("contrast_to_skin", 0.5))
                    confidence = float(vlm_lesion.get("confidence", 0.5))

                    # ── Post-SAM contour sanity check ──
                    # v2: adaptive threshold based on estimated lesion size.
                    # Large lesions naturally fill more of the VLM bbox, so we
                    # use higher thresholds before applying penalties.
                    vlm_bbox = vlm_lesion.get("bbox")
                    if vlm_bbox and len(vlm_bbox) == 4:
                        bbox_area_pct = (float(vlm_bbox[2]) - float(vlm_bbox[0])) * \
                                       (float(vlm_bbox[3]) - float(vlm_bbox[1])) * 100
                        if bbox_area_pct > 0 and area_img > 0:
                            fill_ratio = area_img / bbox_area_pct
                            # Adaptive threshold: larger lesions allow higher fill ratio
                            estimated_size = float(vlm_lesion.get("estimated_size_percent", 5.0))
                            if estimated_size > 10:
                                fill_threshold, fill_penalty = 0.8, 0.6
                            elif estimated_size > 5:
                                fill_threshold, fill_penalty = 0.7, 0.5
                            else:
                                fill_threshold, fill_penalty = 0.6, 0.4
                            if fill_ratio > fill_threshold:
                                logger.warning(
                                    "Contour %s overfills bbox (%.1f%% fill > %.0f%% threshold), bbox=%.1f%%, contour=%.1f%%",
                                    c.get("label"), fill_ratio * 100, fill_threshold * 100, bbox_area_pct, area_img,
                                )
                                confidence = confidence * 0.3
                                area_i = area_i * fill_penalty
                                area_img = area_img * fill_penalty

                    # Per-lesion depig: 1-3 → normalized 0-1
                    depig_i = float(depig_raw) / 3.0 if depig_raw else 0.67
                    weighted_depig_sum += area_i * depig_i
                    weighted_area_sum += area_i

                    # Contrast-adjusted area: low contrast (< 0.5) → down-weight
                    # Reduces noise amplification from hard-to-see lesions
                    contrast_factor = min(1.0, contrast / 0.5) if contrast > 0 else 0.2
                    contrast_adjusted_area += area_i * contrast_factor

                    # Enrich contour
                    enriched_c = dict(c)
                    enriched_c["depigmentation_level"] = depig_raw
                    enriched_c["depigmentation_norm"] = round(depig_i, 2)
                    enriched_c["contrast_to_skin"] = contrast
                    enriched_c["contrast_factor"] = round(contrast_factor, 2)
                    enriched_c["confidence"] = confidence
                    enriched_contours.append(enriched_c)

                # Area-weighted depigmentation
                area_weighted_depig = weighted_depig_sum / max(weighted_area_sum, 1e-6)

                # Replace VLM's rough area estimate with SAM-measured area
                raw_area = seg_area
                # Scale contrast_adjusted_area to avoid double-counting from
                # overlapping contours (sum of individual areas can exceed 100%).
                scale_factor = raw_area / max(weighted_area_sum, 1e-6)
                contrast_adjusted_area = contrast_adjusted_area * scale_factor
                contrast_adjusted_area = min(contrast_adjusted_area, 100.0)

                vlm_result["area_percentage"] = raw_area
                vlm_result["area_percentage_contrast_adjusted"] = round(contrast_adjusted_area, 1)

                # Recompute VASI score from SAM-measured area + area-weighted depigmentation.
                # Use the user-submitted body_site (the method parameter) for BSA weighting —
                # the VLM-returned body_site can drift (e.g. default "hands"), which would
                # mis-weight region area (face 4.5% vs legs 18%).
                try:
                    # The validated submitted site remains authoritative.
                    formula_score = compute_vasi_v2(
                        body_site=body_site,
                        area_pct_in_region=raw_area,
                        depigmentation_level=area_weighted_depig,
                    )
                    vlm_result["vasi_score"] = formula_score
                    vlm_result["details"]["vasi_score_source"] = "sam-area + weighted-depig formula"
                    vlm_result["details"]["vasi_score_depig"] = round(area_weighted_depig, 2)
                    vlm_result["details"]["vasi_score_depig_method"] = "area-weighted per-lesion"
                    vlm_result["weighted_depigmentation"] = round(area_weighted_depig, 2)
                    vlm_result["details"]["contrast_adjusted_area"] = round(contrast_adjusted_area, 1)
                    vlm_result["details"]["num_lesions_evaluated"] = len(enriched_contours)
                    logger.info(
                        "VASI formula: %.1f (body=%s, area=%.1f%%, depig=%.2f weighted, contrast_adj_area=%.1f%%, %d lesions)",
                        formula_score, body_site, raw_area, area_weighted_depig,
                        contrast_adjusted_area, len(enriched_contours),
                    )
                except Exception as e:
                    logger.warning("VASI formula computation failed: %s", e)
                if depigmentation_level is not None:
                    vlm_result["depigmentation_level"] = depigmentation_level
                vlm_result["contours"] = enriched_contours
                vlm_result["details"]["segmentation_source"] = seg_source
                vlm_result["details"]["skin_region_ratio"] = skin_region_ratio
                vlm_result["details"]["denominator"] = denominator
                vlm_result["source"] = f"sam-{seg_source}"
            else:
                vlm_result["source"] = "vlm-fallback"
            if skin_layer_data_url:
                vlm_result["details"]["skin_layer_data_url"] = skin_layer_data_url
            if lesion_layer_data_url:
                vlm_result["details"]["lesion_layer_data_url"] = lesion_layer_data_url
            _attach_quality(vlm_result)
            return vlm_result

        # Step 5: VLM failed but SAM succeeded → construct result from SAM
        if seg_contours:
            # Use VASI formula with conservative defaults.
            # Use the user-submitted body_site (method param) rather than a
            # hardcoded "hands" so BSA region weighting is correct.
            try:
                depig = float(depigmentation_level) / 3.0 if depigmentation_level else 0.67
                formula_score = compute_vasi_v2(
                    body_site=body_site,
                    area_pct_in_region=seg_area if seg_area else 0,
                    depigmentation_level=depig,
                )
            except Exception:
                formula_score = min((seg_area or 0) * 2.5, 100)
            sam_only_result = {
                "vasi_score": round(formula_score, 1),
                "area_percentage": round(seg_area, 1) if seg_area else 0,
                "classification": "未确定",
                "stage": "未知",
                "contours": seg_contours,
                "visual_features": {
                    "visibility": {"level": "visible", "description": "照片中可见色素减退区域"},
                    "color": {"description": "请参考照片自行观察白斑颜色表现"},
                    "border": {"description": "请参考照片自行观察白斑边缘特征"},
                    "shape": {"description": f"AI识别到{len(seg_contours)}处白斑区域，呈散在分布"},
                    "surface": {"description": "请参考照片自行观察白斑表面纹理"},
                    "distribution": {"pattern": "localized", "description": f"白斑局限在照片所示区域内，共{len(seg_contours)}处"},
                    "similarity_note": "AI特征分析未完成，建议重新拍摄清晰照片或前往皮肤科检查。",
                    "recommendation": "建议皮肤科就诊"
                },
                "details": {
                    "description": (
                        f"AI识别到{len(seg_contours)}处白斑区域，"
                        f"占该部位皮肤区域的{seg_area:.1f}%。请手动调整轮廓以修正评估。"
                    ),
                    "confidence": 0.6,
                    "detected_areas": len(seg_contours),
                    "segmentation_source": seg_source,
                                    "depigmentation_level": depigmentation_level,
                "skin_region_ratio": skin_region_ratio,
                    "denominator": denominator,
                    "skin_layer_data_url": skin_layer_data_url,
                    "lesion_layer_data_url": lesion_layer_data_url,
                },
                "raw_response": {"sam_result": seg_result},
                                "depigmentation_level": 1.0,
                "source": f"sam-only-{seg_source}",
            }
            _attach_quality(sam_only_result)
            return sam_only_result

        # Step 6: nnU-Net fallback (remote API)
        if self.segmentation and self.segmentation.available:
            result = await self.segmentation.segment(processed_image)
            if result is not None:
                return result

        # Step 7: Mock fallback (last resort)
        return self._mock_result()

    def _quality_reject_response(self, quality) -> Dict[str, Any]:
        """Return a structured response for poor-quality images.

        Does not call any AI service; the user receives Chinese-language
        suggestions to improve their photo.
        """
        return {
            "vasi_score": 0,
            "area_percentage": 0,
            "classification": "未确定",
            "stage": "未知",
            "contours": [],
            "details": {
                "quality_reject": True,
                "blur_score": quality.blur_score,
                "skin_ratio": quality.skin_ratio,
                "brightness_mean": quality.brightness_mean,
                "suggestions": quality.suggestions,
            },
            "raw_response": {"quality_report": {
                "overall": quality.overall,
                "blur_ok": quality.blur_ok,
                "skin_ok": quality.skin_ok,
                "lighting_ok": quality.lighting_ok,
                "size_ok": quality.size_ok,
            }},
            "source": "quality-reject",
        }

    def _mock_result(self) -> Dict[str, Any]:
        """Fail closed when all AI services are unavailable.

        Previously this returned random VASI scores (10–60) and area percentages
        (5–30), which were persisted as real clinical assessments. That risks
        users trusting fabricated scores. We now raise so the caller surfaces a
        clear error and no assessment row is created.
        """
        raise VASIAssessmentError(
            "AI 评估服务暂时不可用，无法生成评估结果。请稍后重试或使用「手动勾勒」模式自行标注白斑区域。"
        )

    async def _call_vision_model(self, image_file: bytes, body_site: str = "面部") -> Optional[Dict[str, Any]]:
        """调用百炼 DashScope 视觉大模型进行白斑图像分析

        Args:
            image_file: 图片二进制数据

        Returns:
            dict: 结构化评估结果，如果调用失败返回 None
        """
        try:
            import openai

            from web.backend.utils.llm_config import get_llm_config

            config = get_llm_config("vasi")

            if config["provider"] == "none":
                logger.warning("No LLM provider configured, cannot call vision model")
                return None

            vision_model = config.get("vision_model", "qwen-vl-max")
            # max_retries=0 is critical: the SDK defaults to 2 retries, and each
            # attempt can block up to `timeout` (120s). A slow/unresponsive VLM
            # endpoint would otherwise retry 3×120s = 360s, blowing past the
            # frontend 180s timeout and nginx 300s proxy timeout. Fail fast once
            # and let the caller fall back to CV segmentation instead.
            client = openai.OpenAI(
                api_key=config["api_key"],
                base_url=config["base_url"],
                max_retries=0,
            )

            b64_image = base64.b64encode(image_file).decode("utf-8")

            mime_type = "image/jpeg"
            if image_file[:8] == b"\x89PNG\r\n\x1a\n":
                mime_type = "image/png"
            elif image_file[:4] == b"RIFF" and image_file[8:12] == b"WEBP":
                mime_type = "image/webp"

            # Phase 2: Dynamic prompt — 优先 DB 可编辑提示词（管理后台可持续迭代），
            # 其次自进化引擎（当前已停用），最后回退内置默认模板。
            prompt = None
            try:
                from web.backend.experiments.vasi_prompt_evolver import get_prompt_evolver
                evolver = get_prompt_evolver(self.db)
                if evolver is not None:
                    prompt = evolver.get_current_prompt()
                    logger.info("Using evolved prompt (%d chars)", len(prompt))
            except Exception as e:
                logger.info("Prompt evolver unavailable (%s), will load DB prompt", e)

            if not prompt:
                try:
                    from web.backend.services.llm_prompt_service import (
                        LLMPromptService,
                        VASI_VISION_PROMPT,
                    )
                    prompt = LLMPromptService.get_prompt(self.db, "vasi", "vision_analysis")
                    logger.info("Using DB prompt (%d chars)", len(prompt))
                except Exception as e2:
                    logger.warning("Prompt service unavailable (%s), using builtin default", e2)
                    prompt = VASI_VISION_PROMPT

            logger.info(
                "Calling vision model: provider=%s, model=%s, image_size=%d bytes",
                config["provider"],
                vision_model,
                len(image_file),
            )

            # VLM sampling parameters — tunable via env for lesion-edge precision.
            # Edge/boundary localization benefits from near-deterministic sampling,
            # and multi-lesion large images need headroom beyond 4k tokens.
            vlm_temperature = float(os.getenv("VASI_VLM_TEMPERATURE", "0.0"))
            vlm_max_tokens = int(os.getenv("VASI_VLM_MAX_TOKENS", "8192"))
            vlm_timeout = int(os.getenv("VASI_VLM_TIMEOUT", "120"))

            # Offload the synchronous (blocking) OpenAI SDK call to a worker
            # thread. Running it directly in the event loop would freeze the
            # entire single-worker backend for the full VLM latency (~76-120s),
            # stalling every other request (health checks, notifications, file
            # serving) for all users during each assessment.
            request_kwargs = dict(
                model=vision_model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{mime_type};base64,{b64_image}"
                                },
                            },
                            {"type": "text", "text": prompt},
                        ],
                    }
                ],
                temperature=vlm_temperature,
                max_tokens=vlm_max_tokens,
                timeout=vlm_timeout,
            )

            # deepseek 推理视觉模型偶发「推理耗尽 token、内容为空」，重试一次
            response = None
            content = ""
            for attempt in range(2):
                response = await asyncio.to_thread(
                    client.chat.completions.create, **request_kwargs
                )
                content = (response.choices[0].message.content or "").strip()
                if content:
                    break
                logger.warning(
                    "vasi: VLM 返回空内容（第 %s 次，finish=%s），重试",
                    attempt + 1,
                    response.choices[0].finish_reason,
                )
                await asyncio.sleep(1.0)

            # Strip markdown code fences
            if content.startswith("```"):
                content = content.strip("`")
                if content.startswith("json"):
                    content = content[4:].strip()

            logger.info("Vision model raw response: %s", content[:500])

            # Try to extract JSON from response (handle extra text around JSON)
            parsed = None
            try:
                parsed = json.loads(content)
            except json.JSONDecodeError:
                # Remove markdown code fences more thoroughly
                cleaned = content
                for fence in ["```json", "```", "'''json", "'''"]:
                    if fence in cleaned:
                        idx = cleaned.find(fence)
                        cleaned = cleaned[idx + len(fence):]
                        end_fence = cleaned.rfind("```")
                        if end_fence == -1:
                            end_fence = cleaned.rfind("'''")
                        if end_fence > 0:
                            cleaned = cleaned[:end_fence]
                        break

                # Try extracting JSON block: find { ... } boundaries
                start = cleaned.find("{")
                end = cleaned.rfind("}") + 1
                if start >= 0 and end > start:
                    json_str = cleaned[start:end]
                    # VLM models often add trailing commas — strip them
                    import re
                    json_str = re.sub(r',\s*}', '}', json_str)
                    json_str = re.sub(r',\s*]', ']', json_str)
                    # Strip line comments
                    json_str = re.sub(r'//.*$', '', json_str, flags=re.MULTILINE)
                    try:
                        parsed = json.loads(json_str)
                        logger.info("Extracted JSON from position %d-%d (with trailing comma fix)", start, end)
                    except json.JSONDecodeError as je:
                        # If truncated, try to auto-close
                        open_braces = json_str.count('{') - json_str.count('}')
                        open_brackets = json_str.count('[') - json_str.count(']')
                        if open_braces > 0 or open_brackets > 0:
                            json_str += ']' * open_brackets
                            json_str += '}' * open_braces
                            json_str = re.sub(r',\s*}', '}', json_str)
                            json_str = re.sub(r',\s*]', ']', json_str)
                            try:
                                parsed = json.loads(json_str)
                                logger.info("Auto-closed truncated JSON: +%d braces, +%d brackets",
                                           open_braces, open_brackets)
                            except json.JSONDecodeError:
                                pass

            if parsed is None:
                logger.warning("Vision model returned invalid JSON: %s", content[:500])
                return None

            if "error" in parsed:
                logger.warning(
                    "Vision model returned error but continuing with partial data: %s", parsed["error"]
                )
                # Don't return None — use whatever else is in the response

            # Robust numeric parsing — VLMs sometimes append % or return strings
            def _safe_float(val, default=0.0):
                if val is None:
                    return default
                if isinstance(val, (int, float)):
                    return float(val)
                if isinstance(val, str):
                    val = val.strip().rstrip('%').replace(',', '')
                    try:
                        return float(val)
                    except ValueError:
                        return default
                return default

            vasi_score = _safe_float(parsed.get("vasi_score", 0))
            area_percentage = _safe_float(parsed.get("area_percentage_estimate", parsed.get("area_percentage", 0)))
            estimated_total_area_cm2 = _safe_float(parsed.get("estimated_total_area_cm2", 0), 0)
            if estimated_total_area_cm2 == 0:
                estimated_total_area_cm2 = None

            # Extract depigmentation level from VLM (0-3 scale → 0.0-1.0 for formula)
            overall_depig = parsed.get("overall_depigmentation")
            if overall_depig is not None:
                depigmentation_level = _safe_float(overall_depig, 1.0) / 3.0
            else:
                depigmentation_level = 1.0

            raw_stage = parsed.get("stage", "未知")
            stage_map = {
                "进展期": "扩散",
                "稳定期": "稳定",
                "好转期": "好转",
                "扩散": "扩散",
                "稳定": "稳定",
                "好转": "好转",
            }
            stage = stage_map.get(raw_stage, "稳定")

            details = parsed.get("details", {})
            if isinstance(details, str):
                details = {"description": details}

            body_site = parsed.get(
                "body_site_confirmed",
                parsed.get("body_site", "其他"),
            )

            # Extract VLM localization guidance for SAM
            skin_region = parsed.get("skin_region", {})
            suspected_lesions = parsed.get("suspected_lesions", [])
            reference_objects = parsed.get("reference_objects", [])

            # Normalize numeric fields in suspected_lesions (VLMs may return strings)
            for lesion in suspected_lesions:
                if isinstance(lesion.get("estimated_size_percent"), str):
                    lesion["estimated_size_percent"] = _safe_float(lesion["estimated_size_percent"])
                if isinstance(lesion.get("confidence"), str):
                    lesion["confidence"] = _safe_float(lesion["confidence"])
                if isinstance(lesion.get("depigmentation_level"), str):
                    lesion["depigmentation_level"] = _safe_float(lesion["depigmentation_level"])

            # Extract per-lesion bboxes from VLM v4.0+ prompt
            lesion_bboxes = []
            for lesion in suspected_lesions:
                bbox = lesion.get("bbox")
                if bbox and len(bbox) == 4:
                    valid = all(isinstance(v, (int, float)) and 0 <= v <= 1.5 for v in bbox)
                    if valid and bbox[2] > bbox[0] and bbox[3] > bbox[1]:
                        lesion_bboxes.append([float(v) for v in bbox])

            # Extract per-lesion edge points for finer SAM guidance
            lesion_edge_points = []
            for lesion in suspected_lesions:
                edge_pts = lesion.get("edge_points")
                if edge_pts and isinstance(edge_pts, list) and len(edge_pts) >= 2:
                    valid_pts = []
                    for pt in edge_pts:
                        if isinstance(pt, (list, tuple)) and len(pt) == 2:
                            if isinstance(pt[0], (int, float)) and isinstance(pt[1], (int, float)):
                                valid_pts.append([float(pt[0]), float(pt[1])])
                    if valid_pts:
                        lesion_edge_points.append(valid_pts)
                    else:
                        lesion_edge_points.append([])
                else:
                    lesion_edge_points.append([])

            # VLM no longer generates contours — SAM handles that.
            # If VLM still returns contours, validate them as a fallback.
            contours: List[Dict[str, Any]] = []
            raw_contours = parsed.get("contours", [])
            for c in raw_contours:
                if isinstance(c, dict) and "polygon" in c:
                    polygon = c["polygon"]
                    if isinstance(polygon, list) and len(polygon) >= 3:
                        valid_points = []
                        for pt in polygon:
                            if (isinstance(pt, (list, tuple)) and len(pt) == 2
                                    and isinstance(pt[0], (int, float))
                                    and isinstance(pt[1], (int, float))):
                                valid_points.append([
                                    round(max(0.0, min(1.0, float(pt[0]))), 3),
                                    round(max(0.0, min(1.0, float(pt[1]))), 3),
                                ])
                        if len(valid_points) >= 3:
                            contours.append({
                                "label": c.get("label", f"白斑{len(contours)+1}"),
                                "polygon": valid_points[:40],
                                "area_percent": float(c.get("area_percent", 0)),
                            })

            # Build default visual features if VLM didn't provide them
            vf = parsed.get("visual_features")
            if not vf or not isinstance(vf, dict):
                vf = {
                    "visibility": {"level": "unassessed", "description": "需要人工评估"},
                    "color": {"level": "unassessed", "description": "需要人工评估"},
                    "border": {"level": "unassessed", "description": "需要人工评估"},
                    "shape": {"pattern": "unassessed", "description": "需要人工评估"},
                    "surface": {"texture": "unassessed", "description": "需要人工评估"},
                    "distribution": {"pattern": "unassessed", "description": "需要人工评估"},
                    "similarity_note": "建议线下就医进行详细皮肤科检查",
                    "recommendation": "请咨询皮肤科医生获取专业诊断"
                }

            return {
                "vasi_score": round(vasi_score, 1),
                "area_percentage": round(area_percentage, 1),
                "depigmentation_level": depigmentation_level,
                "classification": parsed.get("classification", "未确定"),
                "stage": stage,
                "body_site": body_site,
                "contours": contours,
                "details": details,
                "raw_response": parsed,
                "source": f"vision-{config['provider']}",
                "estimated_total_area_cm2": estimated_total_area_cm2,
                "reference_objects": reference_objects,
                "skin_region": skin_region,
                "suspected_lesions": suspected_lesions,
                "lesion_bboxes": lesion_bboxes,
                "lesion_edge_points": lesion_edge_points,
                "visual_features": vf,
            }

        except json.JSONDecodeError as e:
            logger.warning("Vision model returned invalid JSON: %s", str(e))
            return None
        except Exception as e:
            logger.error("Vision model call failed: %s", str(e), exc_info=True)
            return None

    async def _call_vision_model_ensemble(self, image_file: bytes, body_site: str = "面部") -> Optional[Dict[str, Any]]:
        """Make two VLM calls and intersect results for stability.

        VLM stochasticity is the fundamental bottleneck. Running twice
        and keeping only lesions found in BOTH calls dramatically reduces
        random variation while preserving real lesions.

        Cost: 2x API calls (only enable when stability matters).
        """
        logger.info("VLM ensemble: starting two independent calls")

        result1, result2 = await asyncio.gather(
            self._call_vision_model(image_file, body_site),
            self._call_vision_model(image_file, body_site),
        )

        if not result1 or not result2:
            logger.warning("VLM ensemble: one call failed, using available result")
            return result1 or result2

        lesions1 = result1.get("suspected_lesions", [])
        lesions2 = result2.get("suspected_lesions", [])

        if not lesions1 or not lesions2:
            # Union fallback: if one ensemble call found 0 lesions, do NOT force
            # the intersection to empty (that would be a false negative). Use the
            # non-empty call's lesions, flagged so callers know ensemble didn't
            # intersect. Only when BOTH find 0 do we legitimately return [].
            non_empty = result1 if lesions1 and not lesions2 else (result2 if lesions2 and not lesions1 else result1)
            logger.info(
                "VLM ensemble: one call found 0 lesions (n1=%d, n2=%d), using union fallback",
                len(lesions1), len(lesions2),
            )
            non_empty["_ensemble"] = True
            non_empty["_ensemble_fallback"] = "single_nonempty"
            return non_empty

        # Intersect: keep lesions where bbox IoU > 0.3 with some lesion in other call
        IOU_THRESHOLD = 0.2
        matched = []
        matched_indices_2: set = set()

        for l1 in lesions1:
            bbox1 = l1.get("bbox")
            if not bbox1 or len(bbox1) != 4:
                continue

            best_iou = 0.0
            best_idx = -1
            for j, l2 in enumerate(lesions2):
                if j in matched_indices_2:
                    continue
                bbox2 = l2.get("bbox")
                if not bbox2 or len(bbox2) != 4:
                    continue
                iou = _bbox_iou(bbox1, bbox2)
                if iou > best_iou:
                    best_iou = iou
                    best_idx = j

            if best_iou >= IOU_THRESHOLD and best_idx >= 0:
                l2 = lesions2[best_idx]
                matched_indices_2.add(best_idx)

                avg_bbox = [
                    (float(bbox1[i]) + float(l2.get("bbox", bbox1)[i])) / 2
                    for i in range(4)
                ]

                merged = dict(l1)
                merged["bbox"] = avg_bbox
                merged["confidence"] = (
                    float(l1.get("confidence", 0.5)) + float(l2.get("confidence", 0.5))
                ) / 2
                merged["depigmentation_level"] = max(
                    l1.get("depigmentation_level", 0),
                    l2.get("depigmentation_level", 0),
                )
                merged["_ensemble_matched"] = True
                matched.append(merged)

        logger.info(
            "VLM ensemble: %d/%d lesions from call1 matched → %d consensus",
            len(matched), len(lesions1), len(matched),
        )

        # Rebuild lesion_bboxes from consensus
        rebuilt_bboxes = []
        for l in matched:
            bbox = l.get("bbox")
            if bbox and len(bbox) == 4:
                rebuilt_bboxes.append([float(v) for v in bbox])

        result1["suspected_lesions"] = matched
        result1["lesion_bboxes"] = rebuilt_bboxes
        result1["_ensemble"] = True
        return result1


def _bbox_iou(box1: list, box2: list) -> float:
    """Compute IoU between two bboxes [x1, y1, x2, y2] in normalized coords."""
    x1 = max(box1[0], box2[0])
    y1 = max(box1[1], box2[1])
    x2 = min(box1[2], box2[2])
    y2 = min(box1[3], box2[3])
    if x1 >= x2 or y1 >= y2:
        return 0.0
    intersection = (x2 - x1) * (y2 - y1)
    area1 = (box1[2] - box1[0]) * (box1[3] - box1[1])
    area2 = (box2[2] - box2[0]) * (box2[3] - box2[1])
    union = area1 + area2 - intersection
    return intersection / union if union > 0 else 0.0
