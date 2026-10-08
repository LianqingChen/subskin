"""账户注销（被遗忘权）服务 — 2026-08-30 隐私合规新增。

PIPL 第 47 条：用户有权要求删除其个人信息。本服务在用户通过
强身份验证（密码或 OTP，由 API 层校验）后执行：

1. 匿名化 users 行（username/uid/email/phone/wechat/alipay 置
   deleted_* 或 NULL，is_active=False，token_version+1）；
2. 级联删除 L2/L3 个人数据：帖子及图片（含磁盘文件）、评论、日记
   （含图片）、VASI 测评（行、掩膜、RGB 任务产物与图片均删除；打标记录
   匿名化为墓碑并清除载荷；由其生成的训练样本删除）、体检
   报告（含文件与页面图）、病情档案、白斑报告、用药提醒、治疗事件、
   聊天会话与消息、IM 消息、事件埋点、凭证、刷新令牌、通知、
   关注/屏蔽/收藏/书签；
3. AuditLog 骨架保留（合规审计要求），不含明文联系方式。

服务层不依赖 FastAPI；文件清理失败不阻断主流程（记日志）。
"""

import logging
import uuid
from pathlib import Path
from typing import List

from sqlalchemy.orm import Session

from web.backend.database import models as m
from web.backend.database.models import User

logger = logging.getLogger(__name__)


def _delete_files(paths: List[str]) -> int:
    """按 /uploads/... URL 列表删除磁盘文件，返回成功数。"""
    deleted = 0
    uploads_root = Path("data/uploads").resolve()
    for url in paths:
        if not url:
            continue
        try:
            local = (Path("data") / str(url).lstrip("/")).resolve()
            if uploads_root not in local.parents:
                continue
            local.unlink(missing_ok=True)
            deleted += 1
        except OSError as exc:
            logger.warning("account deletion: remove %s failed: %s", url, exc)
    return deleted


def _erase_vasi_data(db: Session, user_id: int, vasis, rgb_jobs, labels) -> None:
    """删除用户的白斑测评及其衍生数据（调用方负责 commit）。

    - RGB 任务：私有产物目录、任务行；
    - ImageLabel：保留为匿名墓碑（不再可关联到本人、不参与训练），清除图像路径、
      详情、备注、掩膜标注与合成图；
    - 训练样本：删除由这些图像/标注生成的样本（已训练过的权重不在此回收，见方案文档）；
    - 测评行及其质量标签、反馈信号。
    """
    import shutil

    from web.backend.models.image_label import ImageLabelAnnotation
    from web.backend.models.vasi import (
        ImageQualityTag,
        VasiFeedbackSignal,
        VasiTrainingSample,
        VASIAssessment,
    )
    from web.backend.services.rgb_segmentation import artifacts

    vasi_ids = [v.id for v in vasis]
    label_ids = [lb.id for lb in labels]
    hashes = {v.image_hash for v in vasis if v.image_hash}
    hashes |= {lb.image_hash for lb in labels if lb.image_hash}

    for job in rgb_jobs:
        try:
            shutil.rmtree(artifacts.job_directory(job.id), ignore_errors=True)
        except Exception as exc:  # 非法任务号等：不阻断注销
            logger.warning("account deletion: job dir %s: %s", job.id, exc)
        db.delete(job)

    annotated_dir = Path("data/uploads/vasi/annotated")
    for label in labels:
        shutil.rmtree(artifacts.ROOT / "admin_labels" / str(label.id), ignore_errors=True)
        for prefix in (f"admin_{label.id}_", f"user_{label.id}_"):
            for f in annotated_dir.glob(prefix + "*"):
                if f.is_file():
                    f.unlink(missing_ok=True)
        label.is_user_deleted = True
        label.training_eligible = False
        label.training_set_split = None
        label.original_user_id = None
        label.assessment_id = None
        label.image_key = None
        label.image_hash = None
        label.image_url = "deleted"
        label.ai_details = None
        label.user_notes = None
        label.admin_notes = None
        label.annotated_image_path = None
        label.annotated_image_url = None
        label.annotated_layers_path = None
        db.add(label)

    if label_ids:
        db.query(ImageLabelAnnotation).filter(
            ImageLabelAnnotation.image_label_id.in_(label_ids)
        ).delete(synchronize_session=False)
        db.query(VasiTrainingSample).filter(
            VasiTrainingSample.image_label_id.in_(label_ids)
        ).delete(synchronize_session=False)
    if hashes:
        db.query(VasiTrainingSample).filter(
            VasiTrainingSample.image_hash.in_(hashes)
        ).delete(synchronize_session=False)
    if vasi_ids:
        db.query(ImageQualityTag).filter(
            ImageQualityTag.assessment_id.in_(vasi_ids)
        ).delete(synchronize_session=False)
        db.query(VasiFeedbackSignal).filter(
            VasiFeedbackSignal.assessment_id.in_(vasi_ids)
        ).delete(synchronize_session=False)
    db.flush()  # 先落标签/任务的解绑，再删测评行
    if vasi_ids:
        db.query(VASIAssessment).filter(VASIAssessment.id.in_(vasi_ids)).delete(
            synchronize_session=False
        )


def delete_user_account(db: Session, user: User) -> dict:
    """执行账户匿名化+数据删除。调用方负责身份验证与审计。"""
    user_id = int(user.id or 0)
    detail: dict = {"user_id": user_id}

    # ── 收集需要删除的磁盘文件 ──
    file_urls: List[str] = []

    posts = db.query(m.Post).filter(m.Post.user_id == user_id).all()
    post_ids = [p.id for p in posts]
    if post_ids:
        imgs = (
            db.query(m.PostImage)
            .filter(m.PostImage.post_id.in_(post_ids))
            .all()
        )
        file_urls.extend([i.image_url for i in imgs if i.image_url])
        auds = (
            db.query(m.PostAudio)
            .filter(m.PostAudio.post_id.in_(post_ids))
            .all()
        )
        file_urls.extend([a.audio_url for a in auds if a.audio_url])
        atts = (
            db.query(m.PostAttachment)
            .filter(m.PostAttachment.post_id.in_(post_ids))
            .all()
        )
        file_urls.extend([a.file_url for a in atts if a.file_url])
        detail["posts"] = len(post_ids)

    if user.avatar_url:
        file_urls.append(user.avatar_url)

    reports = (
        db.query(m.MedicalReport)
        .filter(m.MedicalReport.user_id == user_id)
        .all()
    )
    report_ids = [r.id for r in reports]
    page_file_ids: List[int] = []
    if report_ids:
        rfiles = (
            db.query(m.MedicalReportFile)
            .filter(m.MedicalReportFile.report_id.in_(report_ids))
            .all()
        )
        file_urls.extend([f.file_url for f in rfiles if f.file_url])
        page_file_ids = [f.id for f in rfiles]
        detail["medical_reports"] = len(report_ids)

    diary_ids = [
        d.id
        for d in db.query(m.DiaryEntry)
        .filter(m.DiaryEntry.user_id == user_id)
        .all()
    ]
    if diary_ids:
        dimgs = (
            db.query(m.DiaryImage)
            .filter(m.DiaryImage.diary_entry_id.in_(diary_ids))
            .all()
        )
        file_urls.extend([i.image_url for i in dimgs if i.image_url])
        detail["diaries"] = len(diary_ids)

    from web.backend.models.vasi import VASIAssessment
    from web.backend.models.image_label import ImageLabel
    from web.backend.models.rgb_segmentation import RGBSegmentationJob

    vasis = (
        db.query(VASIAssessment)
        .filter(VASIAssessment.user_id == user_id)
        .all()
    )
    vasi_ids = [v.id for v in vasis]
    rgb_jobs = (
        db.query(RGBSegmentationJob)
        .filter(RGBSegmentationJob.user_id == user_id)
        .all()
    )
    vasi_files: List[str] = []
    for v in vasis:
        key = getattr(v, "image_key", None)
        if key:
            vasi_files.append(f"/uploads/{key}" if not str(key).startswith("/") else str(key))
        if str(getattr(v, "image_url", "") or "").startswith("/uploads/"):
            vasi_files.append(v.image_url)
    # RGB 路径的可见图固定存为 uploads/vasi/rgb_<job>.png（image_key 为 rgb_<job>，
    # 上面按 key 拼出的路径对不上），逐任务显式回收。
    for job in rgb_jobs:
        vasi_files.append(f"/uploads/vasi/rgb_{job.id}.png")
    file_urls.extend(vasi_files)
    detail["vasi_assessments"] = len(vasis)

    # 用户的打标记录：按测评或原始用户关联；用于清除其图像/掩膜载荷。
    label_filter = ImageLabel.original_user_id == user_id
    if vasi_ids:
        label_filter = label_filter | ImageLabel.assessment_id.in_(vasi_ids)
    labels = db.query(ImageLabel).filter(label_filter).all()
    for label in labels:
        if label.annotated_image_url:
            file_urls.append(label.annotated_image_url)

    # ── 磁盘文件清理（先删文件再删行，失败不阻断） ──
    detail["files_deleted"] = _delete_files(file_urls)
    for fid in page_file_ids:
        try:
            import shutil

            shutil.rmtree(Path("data/uploads/pages") / str(fid), ignore_errors=True)
        except Exception:
            pass
    # IM 图片目录
    try:
        import shutil

        shutil.rmtree(Path("data/uploads/im") / str(user_id), ignore_errors=True)
    except Exception:
        pass

    # ── 贡献授权：先撤回全部有效授权（系统事件），再删除自报事实与微询问日志 ──
    # 授权与事件、回收工单保留为不含个人内容的审计骨架（只含用途、时间、哈希）。
    from web.backend.models.self_report import MicroAskLog, SelfReportFact
    from web.backend.models.contribution import ContributionCredit
    from web.backend.services import data_consent as _consent

    detail["grants_withdrawn"] = _consent.withdraw_all(db, user_id, reason="account_deletion")
    db.query(SelfReportFact).filter(SelfReportFact.user_id == user_id).delete(synchronize_session=False)
    db.query(MicroAskLog).filter(MicroAskLog.user_id == user_id).delete(synchronize_session=False)
    detail["contribution_credits_deleted"] = db.query(ContributionCredit).filter(
        ContributionCredit.user_id == user_id
    ).delete(synchronize_session=False)

    # ── VASI 数据回收：RGB 任务产物 → 打标载荷 → 训练样本 → 测评行 ──
    _erase_vasi_data(db, user_id, vasis, rgb_jobs, labels)

    # ── 级联删除数据库行 ──
    def _del(query) -> int:
        n = query.delete(synchronize_session=False)
        return int(n)

    if post_ids:
        _del(db.query(m.PostImage).filter(m.PostImage.post_id.in_(post_ids)))
        _del(db.query(m.PostAudio).filter(m.PostAudio.post_id.in_(post_ids)))
        _del(db.query(m.PostAttachment).filter(m.PostAttachment.post_id.in_(post_ids)))
        _del(db.query(m.PostLike).filter(m.PostLike.post_id.in_(post_ids)))
        _del(db.query(m.PostTag).filter(m.PostTag.post_id.in_(post_ids)))
        _del(db.query(m.PostVersion).filter(m.PostVersion.post_id.in_(post_ids)))
        _del(db.query(m.PostComment).filter(m.PostComment.post_id.in_(post_ids)))
        _del(db.query(m.Bookmark).filter(m.Bookmark.post_id.in_(post_ids)))
        _del(db.query(m.UserInteractionLog).filter(m.UserInteractionLog.post_id.in_(post_ids)))
    _del(db.query(m.Post).filter(m.Post.user_id == user_id))
    _del(db.query(m.PostComment).filter(m.PostComment.user_id == user_id))

    if diary_ids:
        _del(db.query(m.DiaryImage).filter(m.DiaryImage.diary_entry_id.in_(diary_ids)))
    _del(db.query(m.DiaryEntry).filter(m.DiaryEntry.user_id == user_id))
    _del(db.query(m.TreatmentEvent).filter(m.TreatmentEvent.user_id == user_id))
    _del(db.query(m.MedicationReminder).filter(m.MedicationReminder.user_id == user_id))

    if report_ids:
        _del(db.query(m.MedicalReportFile).filter(m.MedicalReportFile.report_id.in_(report_ids)))
    _del(db.query(m.MedicalReport).filter(m.MedicalReport.user_id == user_id))

    _del(db.query(m.SkinReport).filter(m.SkinReport.user_id == user_id))
    _del(db.query(m.PatientProfile).filter(m.PatientProfile.user_id == user_id))

    _del(db.query(m.Message).filter(m.Message.conversation_id.in_(
        [c.id for c in db.query(m.Conversation).filter(m.Conversation.user_id == user_id).all()]
    )))
    _del(db.query(m.Conversation).filter(m.Conversation.user_id == user_id))

    _del(db.query(m.ImMessage).filter(m.ImMessage.sender_id == user_id))
    member_convs = [
        c.conversation_id
        for c in db.query(m.ImConversationMember)
        .filter(m.ImConversationMember.user_id == user_id)
        .all()
    ]
    if member_convs:
        _del(db.query(m.ImMessage).filter(m.ImMessage.conversation_id.in_(member_convs)))
        _del(db.query(m.ImConversationMember).filter(m.ImConversationMember.conversation_id.in_(member_convs)))
        _del(db.query(m.ImConversation).filter(m.ImConversation.id.in_(member_convs)))
    _del(db.query(m.ImFriendRequest).filter(
        (m.ImFriendRequest.from_user_id == user_id) | (m.ImFriendRequest.to_user_id == user_id)
    ))

    # user_events 以埋点 uid（非 user_id）关联
    _user_uid = getattr(user, "uid", None)
    if _user_uid:
        _del(db.query(m.UserEvent).filter(m.UserEvent.uid == _user_uid))
    _del(db.query(m.UserCredential).filter(m.UserCredential.user_id == user_id))
    _del(db.query(m.RefreshToken).filter(m.RefreshToken.user_id == user_id))
    _del(db.query(m.UserNotification).filter(m.UserNotification.user_id == user_id))
    _del(db.query(m.UserFollow).filter(
        (m.UserFollow.follower_id == user_id) | (m.UserFollow.followee_id == user_id)
    ))
    _del(db.query(m.UserBlock).filter(
        (m.UserBlock.blocker_id == user_id) | (m.UserBlock.blocked_id == user_id)
    ))
    own_collections = [
        c.id for c in db.query(m.Collection).filter(m.Collection.user_id == user_id).all()
    ]
    if own_collections:
        _del(db.query(m.CollectionItem).filter(m.CollectionItem.collection_id.in_(own_collections)))
    _del(db.query(m.Collection).filter(m.Collection.user_id == user_id))
    _del(db.query(m.Bookmark).filter(m.Bookmark.user_id == user_id))
    _del(db.query(m.UserAssistantPreference).filter(m.UserAssistantPreference.user_id == user_id))

    # ── 匿名化用户行（保留骨架用于外键完整性 + 审计关联） ──
    anon = f"deleted_{user_id}_{uuid.uuid4().hex[:8]}"
    user.username = anon
    user.uid = None
    user.email = None
    user.phone = None
    user.wechat_id = None
    user.alipay_id = None
    user.avatar_url = None
    user.hashed_password = None
    user.is_active = False
    user.token_version = int(getattr(user, "token_version", 0) or 0) + 1
    user.user_status = "banned"  # 拒绝后续登录路径
    user.ban_reason = "账户已注销"
    db.add(user)

    db.commit()
    logger.info("Account deleted (anonymized): user_id=%s detail=%s", user_id, detail)
    return detail
