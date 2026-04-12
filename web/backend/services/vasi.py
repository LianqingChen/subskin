"""
VASI评估服务
"""

import os
import json
import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime
from sqlalchemy.orm import Session

from web.backend.models.vasi import VASIAssessment
from web.backend.database.database import get_db


class VASIAssessmentError(Exception):
    """VASI评估错误"""

    pass


class VASIService:
    """VASI评估服务

    提供VASI（白癜风面积严重程度指数）评估功能
    """

    # 支持的身体部位
    VALID_BODY_SITES = ["面部", "颈部", "躯干", "上肢", "下肢", "其他"]

    # 支持的图片格式
    ALLOWED_IMAGE_TYPES = ["image/jpeg", "image/png", "image/jpg"]

    # 最大图片大小（5MB）
    MAX_IMAGE_SIZE = 5 * 1024 * 1024

    def __init__(self, db: Session):
        self.db = db

    async def assess_vasi(
        self,
        user_id: int,
        image_file: bytes,
        body_site: str,
        image_type: str,
        image_filename: str,
    ) -> VASIAssessment:
        """执行VASI评估

        Args:
            user_id: 用户ID
            image_file: 图片二进制数据
            body_site: 评估部位
            image_type: 图片MIME类型
            image_filename: 图片文件名

        Returns:
            VASIAssessment: 评估记录

        Raises:
            VASIAssessmentError: 评估失败
        """
        # 验证输入
        self._validate_input(image_file, body_site, image_type)

        # 上传图片到对象存储（TODO：实现实际的OSS上传）
        image_url, image_key = await self._upload_image(
            user_id, image_file, image_filename
        )

        # 调用VASI识别API（TODO：等方案确定后实现）
        vasi_result = await self._call_vasi_api(image_file)

        # 创建评估记录
        assessment = VASIAssessment(
            user_id=user_id,
            image_url=image_url,
            image_key=image_key,
            vasi_score=vasi_result["vasi_score"],
            body_site=body_site,
            area_percentage=vasi_result["area_percentage"],
            classification=vasi_result["classification"],
            stage=vasi_result["stage"],
            details=json.dumps(vasi_result.get("details", {})),
            raw_api_response=json.dumps(vasi_result["raw_response"]),
            assessment_source=vasi_result.get("source", "mock"),
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
            raise VASIAssessmentError(
                f"无效的身体部位，支持: {', '.join(self.VALID_BODY_SITES)}"
            )

    async def _upload_image(
        self, user_id: int, image_file: bytes, filename: str
    ) -> tuple[str, str]:
        """上传图片到对象存储

        TODO: 实现实际的OSS/云存储上传

        Args:
            user_id: 用户ID
            image_file: 图片二进制数据
            filename: 文件名

        Returns:
            tuple: (image_url, image_key)
        """
        import hashlib
        import time

        # 生成唯一key
        file_hash = hashlib.md5(image_file).hexdigest()
        timestamp = int(time.time())
        image_key = f"vasi/{user_id}/{timestamp}_{file_hash}.jpg"

        # TODO: 实际上传到OSS/COS等
        # 临时返回mock URL
        image_url = f"https://cdn.subskin.org/{image_key}"

        return image_url, image_key

    async def _call_vasi_api(self, image_file: bytes) -> Dict[str, Any]:
        """调用VASI识别API

        TODO: 等方案确定后对接实际的VASI识别API

        Args:
            image_file: 图片二进制数据

        Returns:
            dict: VASI评估结果
        """
        import random

        # TODO: 调用实际的VASI识别API（百度AI、腾讯云等）
        # 临时返回mock数据

        mock_vasi_score = round(random.uniform(10, 60), 1)
        mock_area_percentage = round(random.uniform(5, 30), 1)

        # 根据VASI评分判断病情阶段
        if mock_vasi_score < 20:
            mock_stage = "好转"
        elif mock_vasi_score < 40:
            mock_stage = "稳定"
        else:
            mock_stage = "扩散"

        return {
            "vasi_score": mock_vasi_score,
            "area_percentage": mock_area_percentage,
            "classification": "非节段型",  # TODO: 实际识别
            "stage": mock_stage,
            "details": {"detected_areas": 3, "confidence": 0.92},
            "raw_response": {"mock": True, "timestamp": datetime.utcnow().isoformat()},
            "source": "mock",
        }
