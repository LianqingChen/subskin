"""Allowlisted Bailian assessment authorization and provider configuration."""

import hashlib
import json
import os

from web.backend.database.models import AuditLog
from web.backend.exceptions import RGBSegmentationError
from web.backend.services.rgb_segmentation import artifacts

MODEL = "qwen3.8-max"
PROVIDER = "aliyun-bailian"
BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
LEGACY_NOTICE = "bailian-diary-preview-v1"
NOTICE = "bailian-diary-fusion-v2"
QUEUE = "bailian_queued"
HEARTBEAT = artifacts.ROOT / "bailian-preview-heartbeat.json"
TIMEOUT_SECONDS = 6 * 60 * 60
PRIVACY_URL = "https://help.aliyun.com/zh/model-studio/privacy-notice"


def allowed(user_id):
    return str(user_id) in os.getenv("SUBSKIN_BAILIAN_PREVIEW_USERS", "").split()


def provider_key():
    key = os.getenv("SUBSKIN_BAILIAN_PREVIEW_API_KEY", "").strip()
    return key if key.startswith("sk-") and not key.startswith("sk-sp-") else ""


def authorization(source, notice=NOTICE):
    return {
        "notice": notice,
        "purpose": "diary_white_patch_assessment",
        "provider": PROVIDER,
        "model": MODEL,
        "source_sha256": hashlib.sha256(source).hexdigest(),
    }


def authorization_record(job, grant):
    return AuditLog(
        user_id=job.user_id, action="diary_external_analysis_authorized",
        target_type="rgb_segmentation_job", scope="private", revokeable=False,
        detail=json.dumps({"job_id": job.id, **grant}, sort_keys=True),
    )


def verify_job(db, job, source):
    supplied = json.loads(job.context_json).get("external_analysis") or {}
    notice = supplied.get("notice")
    grant = authorization(source, notice)
    if not allowed(job.user_id) or notice not in (NOTICE, LEGACY_NOTICE) or supplied != grant:
        raise RGBSegmentationError("BAILIAN_CONSENT_REQUIRED", "请重新确认本次百炼照片分析", 403)
    expected = authorization_record(job, grant)
    exists = db.query(AuditLog.id).filter_by(
        user_id=job.user_id, action=expected.action, target_type=expected.target_type,
        detail=expected.detail,
    ).first()
    if exists is None:
        raise RGBSegmentationError("BAILIAN_CONSENT_REQUIRED", "本次照片分析授权不可用", 403)
    return grant
