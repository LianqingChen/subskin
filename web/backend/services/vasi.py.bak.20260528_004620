"""
VASI评估服务
"""

import os
import json
import asyncio
import base64
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
from sqlalchemy.orm import Session

from web.backend.models.vasi import VASIAssessment
from web.backend.database.database import get_db
from web.backend.services.vasi_segmentation import segment_vitiligo, segment_vitiligo_guided, _segment_with_tiling

logger = logging.getLogger(__name__)


class VASIAssessmentError(Exception):
    """VASI评估错误"""

    pass


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

    BODY_SITE_LABELS = {
        "face": "面部",
        "neck": "颈部",
        "hands": "手部",
        "abdomen": "腹部",
        "back": "背部",
        "arms": "上肢",
        "legs": "下肢",
        "feet": "足部",
        "other": "其他",
        # Sided variants
        "chest": "胸部",
        "upper_back": "上背部",
        "lower_back": "下背部",
        "left_arm": "左臂",
        "right_arm": "右臂",
        "left_hand": "左手",
        "right_hand": "右手",
        "left_leg": "左腿",
        "right_leg": "右腿",
        "left_foot": "左脚",
        "right_foot": "右脚",
    }

    ALLOWED_IMAGE_TYPES = ["image/jpeg", "image/png", "image/jpg"]

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

        # 上传图片到对象存储（TODO：实现实际的OSS上传）
        image_url, image_key = await self._upload_image(
            user_id, image_file, image_filename
        )

        # 调用VASI识别API（TODO：等方案确定后实现）
        vasi_result = await self._call_vasi_api(image_file, precision)

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

        assessment = VASIAssessment(
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
            ai_skin_layer=details_data.get("skin_layer_data_url"),
            ai_lesion_layer=details_data.get("lesion_layer_data_url"),
            visual_features_json=json.dumps(vasi_result.get("visual_features")) if vasi_result.get("visual_features") else None,
        )

        self.db.add(assessment)
        self.db.commit()
        self.db.refresh(assessment)

        return assessment

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
        query = self.db.query(VASIAssessment).filter(VASIAssessment.user_id == user_id)

        # 筛选条件
        if body_site:
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

        for aid in assessment_ids:
            link = self.db.query(ImageLabel).filter(
                ImageLabel.assessment_id == aid,
            ).first()
            if link:
                link.is_user_deleted = True
            else:
                assessment = (
                    self.db.query(VASIAssessment)
                    .filter(VASIAssessment.id == aid, VASIAssessment.user_id == user_id)
                    .first()
                )
                if assessment:
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
            .filter(VASIAssessment.id.in_(assessment_ids), VASIAssessment.user_id == user_id)
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
        )

        if body_site:
            query = query.filter(VASIAssessment.body_site == body_site)

        assessments = query.order_by(VASIAssessment.assessment_date.asc()).all()

        if not assessments:
            return {
                "body_site": body_site or "全部",
                "period": {
                    "start": start_date.isoformat(),
                    "end": end_date.isoformat(),
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

        # 构建趋势数据
        data = [
            {
                "date": a.assessment_date.isoformat(),
                "vasi_score": a.vasi_score,
                "stage": a.stage,
            }
            for a in assessments
        ]

        # 计算趋势总结
        first_score = assessments[0].vasi_score
        last_score = assessments[-1].vasi_score
        change = last_score - first_score

        if first_score > 0:
            change_percent = (change / first_score) * 100
        else:
            change_percent = 0

        # 判断趋势
        if abs(change_percent) < 5:
            trend = "稳定"
        elif change_percent < 0:
            trend = "好转"
        else:
            trend = "恶化"

        return {
            "body_site": body_site or "全部",
            "period": {"start": start_date.isoformat(), "end": end_date.isoformat()},
            "data": data,
            "summary": {
                "first_score": first_score,
                "last_score": last_score,
                "change": round(change, 2),
                "change_percent": round(change_percent, 1),
                "trend": trend,
            },
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
        image_key = f"vasi/{user_id}/{timestamp}_{file_hash[:8]}{ext}"

        upload_dir = Path("data/uploads/vasi")
        upload_dir.mkdir(parents=True, exist_ok=True)

        stored_name = f"{timestamp}_{uuid.uuid4().hex[:8]}{ext}"
        file_path = upload_dir / stored_name
        file_path.write_bytes(image_file)

        image_url = f"/api/files/serve/vasi/{stored_name}"

        return image_url, image_key

    async def _call_vasi_api(self, image_file: bytes, precision: str = "quick") -> Dict[str, Any]:
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

        processed_image = image_file
        if self.preprocessor and self.preprocessor.available:
            processed_image = self.preprocessor.preprocess(image_file)

        # Step 3: VLM first — get classification + localization guidance
        vlm_result = await self._call_vision_model(processed_image)

        # Extract VLM localization for SAM
        skin_bbox: Optional[List[float]] = None
        lesion_centers: Optional[List[List[float]]] = None
        lesion_sizes: Optional[List[float]] = None
        if vlm_result:
            skin_region = vlm_result.get("skin_region", {})
            if skin_region and skin_region.get("bbox"):
                bbox = skin_region["bbox"]
                if len(bbox) == 4 and all(0 <= v <= 1.5 for v in bbox):
                    skin_bbox = [float(v) for v in bbox]
            lesions = vlm_result.get("suspected_lesions", [])
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

        # Step 4: SAM with VLM guidance (or auto if no guidance)
        has_guidance = bool(skin_bbox or lesion_centers)
        if has_guidance:
            logger.info(
                "Using VLM-guided SAM: skin_bbox=%s, lesion_centers=%d",
                skin_bbox, len(lesion_centers) if lesion_centers else 0,
            )
            seg_result = await asyncio.to_thread(
                segment_vitiligo_guided, processed_image, skin_bbox, lesion_centers, precision,
                lesion_sizes if lesion_sizes else None,
            )
        else:
            logger.info("No VLM guidance available, using auto SAM")
            seg_result = await asyncio.to_thread(
                segment_vitiligo, processed_image, 0.005, 5, precision
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
            # If guided SAM found <2 patches, try tiling for small lesions
            if len(seg_contours) < 2 and precision == "quick":
                logger.info("Few contours (%d), trying tiling for small lesions", len(seg_contours))
                tile_result = await asyncio.to_thread(
                    _segment_with_tiling, processed_image, 0.3, precision
                )
                if tile_result["success"] and tile_result["contours"]:
                    # Merge: deduplicate with existing contours
                    existing_areas = {c.get("label", ""): c.get("area_percent", 0) for c in seg_contours}
                    for tc in tile_result["contours"]:
                        if tc["area_percent"] > 0.3:
                            seg_contours.append(tc)
                    seg_area = sum(c["area_percent"] for c in seg_contours)
                    seg_source += "+tiled"
                    logger.info(
                        "Tiling added %d patches, total now %d",
                        len(tile_result["contours"]), len(seg_contours),
                    )
        elif has_guidance:
            # Guided SAM failed — retry with auto SAM
            logger.warning("VLM-guided SAM failed (%s), retrying with auto SAM", seg_result.get("error"))
            seg_result = await asyncio.to_thread(
                segment_vitiligo, processed_image, 0.005, 5, precision
            )
            if seg_result["success"]:
                seg_contours = seg_result["contours"]
                seg_area = seg_result["total_area_percent"]
                seg_source = seg_result["source"]
                skin_layer_data_url = seg_result.get("skin_layer_data_url")
                lesion_layer_data_url = seg_result.get("lesion_layer_data_url")
            else:
                # Auto SAM also failed — try tiling as last resort
                logger.warning("Auto SAM failed (%s), trying tiling", seg_result.get("error"))
                tile_result = await asyncio.to_thread(
                    _segment_with_tiling, processed_image, 0.3, precision
                )
                if tile_result["success"]:
                    seg_contours = tile_result["contours"]
                    seg_area = tile_result["total_area_percent"]
                    seg_source = tile_result["source"]
                    logger.info("Tiling fallback: %d patches", len(seg_contours))
        else:
            # No guidance — auto SAM failed, try tiling
            logger.warning("Auto SAM failed (%s), trying tiling", seg_result.get("error"))
            tile_result = await asyncio.to_thread(
                _segment_with_tiling, processed_image, 0.3, precision
            )
            if tile_result["success"]:
                seg_contours = tile_result["contours"]
                seg_area = tile_result["total_area_percent"]
                seg_source = tile_result["source"]
                logger.info("No-guidance tiling: %d patches", len(seg_contours))
            else:
                logger.warning("All segmentation methods failed")

        if vlm_result is not None:
            if seg_area is not None:
                vlm_result["area_percentage"] = seg_area
                vlm_result["contours"] = seg_contours
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
            return vlm_result

        # Step 5: VLM failed but SAM succeeded → construct result from SAM
        if seg_contours:
            estimated_vasi = min(seg_area * 2.5, 100) if seg_area else 0
            return {
                "vasi_score": round(estimated_vasi, 1),
                "area_percentage": round(seg_area, 1) if seg_area else 0,
                "classification": "未确定",
                "stage": "稳定",
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
                    "skin_region_ratio": skin_region_ratio,
                    "denominator": denominator,
                    "skin_layer_data_url": skin_layer_data_url,
                    "lesion_layer_data_url": lesion_layer_data_url,
                },
                "raw_response": {"sam_result": seg_result},
                "source": f"sam-only-{seg_source}",
            }

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
        """Generate mock VASI data when all AI services are unavailable."""
        import random

        mock_vasi_score = round(random.uniform(10, 60), 1)
        mock_area_percentage = round(random.uniform(5, 30), 1)

        if mock_vasi_score < 20:
            mock_stage = "好转"
        elif mock_vasi_score < 40:
            mock_stage = "稳定"
        else:
            mock_stage = "扩散"

        return {
            "vasi_score": mock_vasi_score,
            "area_percentage": mock_area_percentage,
            "classification": "非节段型",
            "stage": mock_stage,
            "contours": [
                {
                    "label": "白斑1",
                    "polygon": [
                        [0.3, 0.2], [0.5, 0.15], [0.65, 0.25],
                        [0.7, 0.45], [0.6, 0.6], [0.4, 0.65],
                        [0.25, 0.5], [0.2, 0.35],
                    ],
                    "area_percent": mock_area_percentage,
                }
            ],
            "visual_features": {
                "visibility": {"level": "visible", "description": "照片中可见色素减退区域，与周围正常皮肤有一定色差"},
                "color": {"level": "milky_white", "description": "呈现乳白色调，色素脱失程度中等"},
                "border": {"level": "partial", "description": "白斑边界部分清晰，部分区域边缘模糊"},
                "shape": {"description": "呈不规则形，可见散在分布的小片状白斑"},
                "surface": {"texture": "smooth", "description": "白斑区域表面光滑，未见明显鳞屑或萎缩"},
                "distribution": {"pattern": "localized", "description": "白斑局限于照片所示区域，呈局部散在分布"},
                "similarity_note": "需与白色糠疹、花斑癣、炎症后色素减退等鉴别，建议皮肤科确诊。",
                "recommendation": "建议皮肤科就诊"
            },
            "details": {"detected_areas": 1, "confidence": 0.75, "description": "mock数据-请手动调整轮廓"},
            "raw_response": {"mock": True, "timestamp": datetime.utcnow().isoformat()},
            "source": "mock",
        }

    async def _call_vision_model(self, image_file: bytes) -> Optional[Dict[str, Any]]:
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

            vision_model = config.get("vision_model", "qwen3-vl-plus")
            client = openai.OpenAI(
                api_key=config["api_key"],
                base_url=config["base_url"],
            )

            b64_image = base64.b64encode(image_file).decode("utf-8")

            mime_type = "image/jpeg"
            if image_file[:8] == b"\x89PNG\r\n\x1a\n":
                mime_type = "image/png"
            elif image_file[:4] == b"RIFF" and image_file[8:12] == b"WEBP":
                mime_type = "image/webp"

            prompt = """你是一位皮肤科AI助手。请仔细分析这张皮肤照片。

重要声明：你不是医生，不能进行医疗诊断。你的分析仅基于照片中肉眼可见的视觉特征，供用户参考。请在所有描述中使用"观察到"、"可见"等客观措辞，避免使用"诊断为"、"确诊"等医疗术语。

返回 JSON（只返回 JSON，不要其他文字）：

{
  "visual_features": {
    "visibility": {
      "level": "visible|faint|subtle",
      "description": "用一句话描述白斑的肉眼可见程度"
    },
    "color": {
      "level": "pale_white|milky_white|porcelain_white|pure_white",
      "description": "描述白斑的颜色表现和色素脱失程度"
    },
    "border": {
      "level": "clear|partial|unclear",
      "description": "描述白斑与正常皮肤交界处的特征"
    },
    "shape": {
      "description": "描述白斑的形状、数量和大体分布"
    },
    "surface": {
      "texture": "smooth|scaly|atrophic|other",
      "description": "描述白斑表面的纹理特征"
    },
    "distribution": {
      "pattern": "localized|segmental|bilateral|generalized",
      "description": "描述白斑的分布模式"
    },
    "similarity_note": "列举至少2种其他可能出现类似特征的皮肤状况（用于鉴别诊断，无需重复上述特征）",
    "recommendation": "一句话就医建议（10字以内）"
  },
  "skin_region": {
    "bbox": [x1, y1, x2, y2],
    "confidence": 0.0-1.0,
    "notes": "皮肤区域描述（如：右手背掌侧）"
  },
  "suspected_lesions": [
    {
      "label": "白斑1",
      "center": [x, y],
      "estimated_size_percent": 数值,
      "confidence": 0.0-1.0
    }
  ],
  "vasi_score": 0-100,
  "area_percentage_estimate": 0-100,
  "classification": "节段型|非节段型|未确定",
  "stage": "进展期|稳定期|好转期",
  "body_site_confirmed": "面部|颈部|手部|腹部|背部|上肢|下肢|足部|其他",
  "confidence": 0.0-1.0,
  "details": {
    "patch_count_estimate": 数量,
    "color_type": "纯白|乳白|灰白|淡白",
    "border_clarity": "清晰|模糊|部分清晰",
    "description": "80字以内的白斑特征描述"
  }
}

坐标说明:
- skin_region.bbox 是皮肤区域边界框，归一化坐标 (0-1)，[左, 上, 右, 下]
- suspected_lesions[].center 是白斑中心点，归一化坐标 (0-1)
- 确保 bbox 坐标在 0-1 范围内

注意:
1. 基于照片中的可见内容给出你的最佳分析判断，不要返回 error
2. VASI评分保守估计，宁低勿高
3. area_percentage_estimate 是粗略估计（精确面积由分割算法计算）
4. 尽可能找到所有白斑区域，包括小的斑点
5. visual_features 中 similarity_note 仅列举鉴别诊断（其他皮肤状况），不重复特征描述
6. recommendation 需简短（10字以内）
7. 只返回JSON"""

            logger.info(
                "Calling vision model: provider=%s, model=%s, image_size=%d bytes",
                config["provider"],
                vision_model,
                len(image_file),
            )

            response = client.chat.completions.create(
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
                temperature=0.1,
                max_tokens=2000,
                timeout=90,
            )

            content = (response.choices[0].message.content or "").strip()

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
                # Try extracting JSON block: find { ... } boundaries
                start = content.find("{")
                end = content.rfind("}") + 1
                if start >= 0 and end > start:
                    json_str = content[start:end]
                    # VLM models often add trailing commas — strip them
                    import re
                    json_str = re.sub(r',\s*}', '}', json_str)
                    json_str = re.sub(r',\s*]', ']', json_str)
                    try:
                        parsed = json.loads(json_str)
                        logger.info("Extracted JSON from position %d-%d (with trailing comma fix)", start, end)
                    except json.JSONDecodeError:
                        pass

            if parsed is None:
                logger.warning("Vision model returned invalid JSON: %s", content[:300])
                return None

            if "error" in parsed:
                logger.warning(
                    "Vision model returned error but continuing with partial data: %s", parsed["error"]
                )
                # Don't return None — use whatever else is in the response

            vasi_score = float(parsed.get("vasi_score", 0))
            area_percentage = float(parsed.get("area_percentage_estimate", parsed.get("area_percentage", 0)))

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

            return {
                "vasi_score": round(vasi_score, 1),
                "area_percentage": round(area_percentage, 1),
                "classification": parsed.get("classification", "未确定"),
                "stage": stage,
                "body_site": body_site,
                "contours": contours,
                "details": details,
                "raw_response": parsed,
                "source": f"vision-{config['provider']}",
                "skin_region": skin_region,
                "suspected_lesions": suspected_lesions,
                "visual_features": parsed.get("visual_features"),
            }

        except json.JSONDecodeError as e:
            logger.warning("Vision model returned invalid JSON: %s", str(e))
            return None
        except Exception as e:
            logger.error("Vision model call failed: %s", str(e), exc_info=True)
            return None
