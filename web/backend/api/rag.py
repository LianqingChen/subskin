# pyright: reportAny=false, reportArgumentType=false, reportAttributeAccessIssue=false, reportCallInDefaultInitializer=false, reportGeneralTypeIssues=false, reportIndexIssue=false, reportMissingTypeArgument=false, reportPrivateUsage=false, reportReturnType=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportUnknownVariableType=false, reportUnusedCallResult=false, reportUnusedVariable=false

import hashlib
import json
import logging
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import (
    APIRouter,
    Depends,
    File as FastAPIFile,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from web.backend.database.database import get_db, SessionLocal
from web.backend.database.models import (
    User as DBUser,
    GuestUsage,
    Conversation,
    Message,
)
from web.backend.models.rag import (
    ConfirmActionRequest,
    ConfirmActionResponse,
    QuestionRequest,
    QuestionRequestWithAttachments,
    QuestionResponse,
    TempUploadResponse,
)
from web.backend.services.rag import (
    _analyze_uploaded_image,
    _extract_document_text,
    _generate_diary_draft,
    _interpret_report,
    answer_question,
    answer_question_stream,
    is_site_feature_question,
    is_vitiligo_related,
    is_crisis_message,
    search_documents,
)
from web.backend.services.auth import auth

logger = logging.getLogger(__name__)
router = APIRouter()

GUEST_DAILY_LIMIT = 5
GUEST_MAX_QUESTION_LENGTH = 200
LOGGED_IN_MAX_QUESTION_LENGTH = 2000
ALLOWED_UPLOAD_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "application/pdf",
    "text/plain",
    "text/markdown",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


def _get_client_fingerprint(request: Request) -> str:
    ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "")
    # Include request path prefix for additional entropy
    path_prefix = request.url.path.split("/")[1] if request.url.path.startswith("/") else ""
    raw = f"{ip}:{user_agent}:{path_prefix}"
    return hashlib.sha256(raw.encode()).hexdigest()


def _today_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _temp_upload_dir() -> Path:
    path = Path("data/uploads/temp")
    path.mkdir(parents=True, exist_ok=True)
    return path


def _temp_upload_meta_path(file_path: Path) -> Path:
    return file_path.with_name(f"{file_path.name}.meta")


def _promote_temp_upload(
    file_url: str, subdir: str, user_id: Optional[int] = None
) -> str:
    if not file_url or not file_url.startswith("/uploads/temp/"):
        return file_url

    source = Path("data") / file_url.lstrip("/")
    if not source.exists():
        return file_url

    meta_path = _temp_upload_meta_path(source)
    if user_id is not None:
        if not meta_path.exists():
            logger.warning(
                "Missing upload metadata for temp file promotion: %s", file_url
            )
            return file_url

        owner_id = meta_path.read_text(encoding="utf-8").strip()
        if owner_id != str(user_id):
            logger.warning(
                "Rejected temp file promotion for user %s: %s", user_id, file_url
            )
            return file_url

    target_dir = Path("data/uploads") / subdir
    target_dir.mkdir(parents=True, exist_ok=True)

    suffix = source.suffix or ".bin"
    target_name = f"{uuid.uuid4().hex[:16]}{suffix}"
    target = target_dir / target_name
    shutil.move(str(source), str(target))
    if meta_path.exists():
        meta_path.unlink()
    return f"/uploads/{subdir}/{target_name}"


def _check_guest_limit(db: Session, fingerprint: str) -> int:
    today = _today_str()
    usage = (
        db.query(GuestUsage)
        .filter(GuestUsage.client_fingerprint == fingerprint)
        .filter(GuestUsage.date == today)
        .first()
    )
    if not usage:
        return 0
    return usage.question_count


def _increment_guest_usage(db: Session, fingerprint: str) -> int:
    today = _today_str()
    usage = (
        db.query(GuestUsage)
        .filter(GuestUsage.client_fingerprint == fingerprint)
        .filter(GuestUsage.date == today)
        .first()
    )
    if not usage:
        usage = GuestUsage(client_fingerprint=fingerprint, question_count=1, date=today)
        db.add(usage)
    else:
        usage.question_count += 1
    db.commit()
    return usage.question_count


def _refund_guest_usage(db: Session, fingerprint: str) -> None:
    """Refund one guest question count (clamped at 0).

    Called when a guest stream fails before producing a useful answer, so the
    user's daily quota is not consumed by an error. Best-effort: any DB failure
    is swallowed so it never masks the original error.
    """
    try:
        today = _today_str()
        usage = (
            db.query(GuestUsage)
            .filter(GuestUsage.client_fingerprint == fingerprint)
            .filter(GuestUsage.date == today)
            .first()
        )
        if usage and usage.question_count > 0:
            usage.question_count -= 1
            db.commit()
    except Exception:
        db.rollback()


def _assert_conversation_ownership(
    db: Session, conversation_id: Optional[str], user_id: Optional[int]
) -> None:
    """Ensure ``user_id`` may append to ``conversation_id``.

    Prevents cross-user reads/injections: a logged-in user may only use a
    conversation whose owner is themselves (or an unclaimed guest conversation,
    which is adopted on first logged-in use). Guests are blocked from any
    conversation already claimed by a user.
    """
    if not conversation_id:
        return
    conv = (
        db.query(Conversation)
        .filter(Conversation.conversation_id == conversation_id)
        .first()
    )
    if conv is None:
        return  # created later with the correct user_id
    # Soft-deleted conversations must not be readable or appendable — otherwise
    # a user (or a leaked conversation_id) could continue reading/injecting into
    # a conversation the user explicitly deleted.
    if getattr(conv, "is_deleted", False):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="该会话已被删除",
        )
    owner = conv.user_id
    if owner is None:
        if user_id is not None:
            conv.user_id = user_id
            db.commit()
        return
    if user_id is None or owner != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问该会话",
        )


def _enforce_chat_rate_limit(user_id: Optional[int]) -> None:
    """Per-user rate limit for logged-in chat endpoints.

    Guests are rate-limited via the daily GUEST_DAILY_LIMIT quota; logged-in
    users previously had no limit, making the LLM-backed endpoints a cost/DoS
    abuse vector. Keyed by user_id (falls back to a shared anonymous bucket).
    """
    from web.backend.app.middleware.rate_limit import chat_limiter

    key = f"chat:user:{user_id}" if user_id else "chat:anon"
    if not chat_limiter.is_allowed(key):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="提问过于频繁，请稍后再试",
        )
    chat_limiter.hit(key)


@router.post("/ask", response_model=QuestionResponse)
def ask_question(
    request: QuestionRequest,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(auth),
):
    """已登录用户提问（按用户限速，防止 LLM 成本滥用）"""
    if len(request.question) > LOGGED_IN_MAX_QUESTION_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"问题长度不能超过{LOGGED_IN_MAX_QUESTION_LENGTH}个字符",
        )

    user_id = current_user.id if current_user else None
    _assert_conversation_ownership(db, request.conversation_id, user_id)
    # Per-user chat rate limit (guests are separately capped by daily quota).
    _enforce_chat_rate_limit(user_id)

    return answer_question(
        db=db,
        question=request.question,
        conversation_id=request.conversation_id,
        user_id=user_id,
        mode=request.mode,
    )


@router.post("/ask-public", response_model=QuestionResponse)
def ask_question_public(
    request: QuestionRequest,
    http_request: Request,
    db: Session = Depends(get_db),
):
    """访客免费提问，每日3次，限白癜风/皮肤健康话题"""
    question = request.question.strip()

    if not question:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="请输入你的问题"
        )

    if len(question) > GUEST_MAX_QUESTION_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"访客问题长度不能超过{GUEST_MAX_QUESTION_LENGTH}个字符，登录后可提问更长的内容",
        )

    # 1. 话题相关性校验（网站功能问题也放行，只有完全不相关的才拒绝）
    # Crisis / suicidal-ideation messages bypass the vitiligo-only topic gate.
    # A guest typing "我不想活了" must reach the assistant so it can respond
    # with support resources — blocking it with a 400 "off-topic" is a safety
    # regression.
    if (
        not is_crisis_message(question)
        and not is_vitiligo_related(question)
        and not is_site_feature_question(question)
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="抱歉，当前AI助手专注于白癜风及皮肤健康相关问题。如有其他问题，建议咨询相关领域的专业人士。",
        )

    # 2. 访客次数限制
    fingerprint = _get_client_fingerprint(http_request)
    used = _check_guest_limit(db, fingerprint)

    if used >= GUEST_DAILY_LIMIT:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"今日免费体验次数（{GUEST_DAILY_LIMIT}次）已用完，请登录后继续使用AI助手，解锁更多功能。",
        )

    # 3. 执行问答
    result = answer_question(
        db=db, question=question, conversation_id=None, user_id=None, mode=request.mode
    )

    # 4. 记录使用次数
    new_count = _increment_guest_usage(db, fingerprint)

    # 5. 在响应中附加剩余次数信息
    result.remaining_quota = GUEST_DAILY_LIMIT - new_count
    result.is_guest = True

    return result


@router.get("/guest-quota")
def get_guest_quota(http_request: Request, db: Session = Depends(get_db)):
    """获取访客剩余免费次数"""
    fingerprint = _get_client_fingerprint(http_request)
    used = _check_guest_limit(db, fingerprint)
    return {
        "used": used,
        "limit": GUEST_DAILY_LIMIT,
        "remaining": max(0, GUEST_DAILY_LIMIT - used),
    }


@router.post("/upload-temp", response_model=TempUploadResponse)
async def upload_temp_file(
    file: UploadFile = FastAPIFile(...),
    current_user: DBUser = Depends(auth),
):
    """Upload a temporary file for chat analysis."""
    if not current_user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="请登录")

    if file.content_type not in ALLOWED_UPLOAD_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的文件类型: {file.content_type}",
        )

    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="文件大小不能超过10MB",
        )

    temp_id = f"tmp_{uuid.uuid4().hex[:12]}"
    ext = Path(file.filename or "file").suffix or ".bin"
    filename = f"{temp_id}{ext}"
    filepath = _temp_upload_dir() / filename
    filepath.write_bytes(content)
    meta_path = _temp_upload_meta_path(filepath)
    pending_meta_path = meta_path.with_suffix(f"{meta_path.suffix}.tmp")
    pending_meta_path.write_text(str(current_user.id), encoding="utf-8")
    pending_meta_path.replace(meta_path)

    return TempUploadResponse(
        temp_url=f"/uploads/temp/{filename}",
        temp_id=temp_id,
        mime_type=file.content_type or "application/octet-stream",
        size=len(content),
    )


@router.post("/confirm-action", response_model=ConfirmActionResponse)
def confirm_action(
    request: ConfirmActionRequest,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(auth),
):
    """Confirm saving an action card to the appropriate module."""
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="请登录后操作"
        )

    if request.action == "discard":
        return ConfirmActionResponse(success=True, message="已跳过")

    if request.card_type == "vasi" and request.action == "save":
        from web.backend.models.vasi import VASIAssessment

        card = request.card_data
        image_url = _promote_temp_upload(
            card.get("imageUrl", ""), "vasi", current_user.id
        )
        assessment = VASIAssessment(
            user_id=current_user.id,
            image_url=image_url,
            image_key=image_url,
            image_hash="",
            vasi_score=card.get("vasiScore", 0),
            body_site=card.get("bodySite", "其他"),
            area_percentage=card.get("areaPercentage", 0),
            classification=card.get("classification", "未分类"),
            stage=card.get("stage", "未知"),
            details=json.dumps(card, ensure_ascii=False),
            assessment_source="ai_chat",
        )
        db.add(assessment)
        db.commit()
        db.refresh(assessment)
        return ConfirmActionResponse(
            success=True, message="已保存到测评", resource_id=assessment.id
        )

    if request.card_type == "report" and request.action == "save":
        from web.backend.database.models import MedicalReport, MedicalReportFile

        card = request.card_data
        findings = card.get("keyFindings", [])
        report_tags = []
        if isinstance(findings, list):
            for item in findings[:3]:
                if isinstance(item, dict):
                    name = str(item.get("name", "")).strip()
                    if name:
                        report_tags.append(name)
                else:
                    text = str(item).strip()
                    if text:
                        report_tags.append(text)
        report = MedicalReport(
            user_id=current_user.id,
            title=card.get("title", "体检报告"),
            tags=",".join(report_tags),
        )
        db.add(report)
        db.commit()
        db.refresh(report)

        file_url = card.get("fileUrl", "")
        if file_url:
            persisted_url = _promote_temp_upload(
                file_url, "medical-reports", current_user.id
            )
            db.add(
                MedicalReportFile(
                    report_id=report.id,
                    file_url=persisted_url,
                    file_name=card.get("fileName") or Path(persisted_url).name,
                    file_size=int(card.get("size", 0) or 0),
                    file_type=card.get("mimeType") or "",
                )
            )
            db.commit()

        return ConfirmActionResponse(
            success=True, message="已保存到体检报告", resource_id=report.id
        )

    if request.card_type == "diary":
        from datetime import date

        from web.backend.database.models import AuditLog, CommunityCategory, Post

        card = request.card_data
        is_public = request.action == "share" or card.get("privacy") == "public"
        diary_category = (
            db.query(CommunityCategory)
            .filter(CommunityCategory.name == "白白日记")
            .first()
        )
        if diary_category is None:
            diary_category = CommunityCategory(
                name="白白日记", description="AI日记草稿"
            )
            db.add(diary_category)
            db.commit()
            db.refresh(diary_category)

        post = Post(
            user_id=current_user.id,
            title=card.get("title", f"{date.today().isoformat()} 病情日记"),
            content=card.get("content", ""),
            content_json=None,
            category_id=diary_category.id,
            is_private=not is_public,
            diary_date=date.today(),
        )
        db.add(post)
        db.commit()
        db.refresh(post)

        if is_public:
            db.add(
                AuditLog(
                    user_id=current_user.id,
                    action="share",
                    target_type="post",
                    target_id=post.id,
                    scope="public",
                    detail=json.dumps(
                        {
                            "conversation_id": request.conversation_id,
                            "card_type": request.card_type,
                        },
                        ensure_ascii=False,
                    ),
                    revokeable=True,
                )
            )
            db.commit()

        return ConfirmActionResponse(
            success=True,
            message="已分享到社区" if is_public else "已存档（仅自己可见）",
            resource_id=post.id,
        )

    return ConfirmActionResponse(success=False, message="未知操作")


@router.post("/ask-stream")
def ask_question_stream(
    request: QuestionRequestWithAttachments,
    current_user: DBUser = Depends(auth),
    db: Session = Depends(get_db),
):
    if len(request.question) > LOGGED_IN_MAX_QUESTION_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"问题长度不能超过{LOGGED_IN_MAX_QUESTION_LENGTH}个字符",
        )
    user_id = current_user.id if current_user else None
    _assert_conversation_ownership(db, request.conversation_id, user_id)
    _enforce_chat_rate_limit(user_id)
    db = SessionLocal()
    try:
        return StreamingResponse(
            _stream_rag_response(
                db=db,
                question=request.question,
                conversation_id=request.conversation_id,
                attachment_ids=request.attachment_ids,
                user_id=user_id,
                is_guest=False,
                mode=request.mode,
            ),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
    except Exception:
        db.close()
        raise


@router.post("/ask-public-stream")
def ask_question_public_stream(
    request: QuestionRequestWithAttachments,
    http_request: Request,
):
    question = request.question.strip()
    if not question:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="请输入你的问题"
        )
    if len(question) > GUEST_MAX_QUESTION_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"访客问题长度不能超过{GUEST_MAX_QUESTION_LENGTH}个字符，登录后可提问更长的内容",
        )
    # Crisis / suicidal-ideation messages bypass the vitiligo-only topic gate.
    # A guest typing "我不想活了" must reach the assistant so it can respond
    # with support resources — blocking it with a 400 "off-topic" is a safety
    # regression.
    if (
        not is_crisis_message(question)
        and not is_vitiligo_related(question)
        and not is_site_feature_question(question)
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="抱歉，当前AI助手专注于白癜风及皮肤健康相关问题。如有其他问题，建议咨询相关领域的专业人士。",
        )

    db = SessionLocal()
    try:
        fingerprint = _get_client_fingerprint(http_request)
        used = _check_guest_limit(db, fingerprint)
        if used >= GUEST_DAILY_LIMIT:
            db.close()
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"今日免费体验次数（{GUEST_DAILY_LIMIT}次）已用完，请登录后继续使用AI助手，解锁更多功能。",
            )
        new_count = _increment_guest_usage(db, fingerprint)
        remaining = GUEST_DAILY_LIMIT - new_count
        return StreamingResponse(
            _stream_rag_response(
                db=db,
                question=question,
                conversation_id=None,
                attachment_ids=request.attachment_ids,
                user_id=None,
                is_guest=True,
                remaining_quota=remaining,
                mode=request.mode,
                guest_fingerprint=fingerprint,
            ),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
    except HTTPException:
        db.close()
        raise
    except Exception:
        db.close()
        raise


def _stream_rag_response(
    db: Session,
    question: str,
    conversation_id: Optional[str],
    attachment_ids: Optional[list[str]],
    user_id: Optional[int],
    is_guest: bool,
    remaining_quota: Optional[int] = None,
    mode: Optional[str] = None,
    guest_fingerprint: Optional[str] = None,
):
    def event(data: dict) -> str:
        return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

    try:
        yield event(
            {
                "type": "thinking",
                "stage": "searching",
                "message": "正在搜索知识库...",
            }
        )

        results = search_documents(db, question)
        docs = [doc for doc, score in results if score > 0.5]
        if not docs:
            docs = [doc for doc, score in results[:3]]

        sources = [
            {
                "title": doc.title,
                "url": doc.source_url or "",
                "snippet": doc.content[:200],
            }
            for doc in docs
        ]

        yield event(
            {
                "type": "thinking",
                "stage": "analyzing",
                "message": "📚 正在分析相关文献...",
            }
        )

        action_cards = []
        if attachment_ids:
            for attachment_id in attachment_ids:
                matches = sorted(_temp_upload_dir().glob(f"{attachment_id}*"))
                if not matches:
                    continue

                filepath = matches[0]

                # Owner check: temp files carry a sidecar .meta with owner_id.
                # Logged-in users may only analyze their own temp uploads; guests
                # are blocked from attachment analysis entirely.
                if is_guest:
                    yield event(
                        {
                            "type": "error",
                            "message": "访客暂不支持附件分析，请登录后使用。",
                        }
                    )
                    continue
                meta_path = _temp_upload_meta_path(filepath)
                if meta_path.exists():
                    owner_id = meta_path.read_text(encoding="utf-8").strip()
                    if owner_id != str(user_id):
                        logger.warning(
                            "Rejected temp attachment access by user %s: %s",
                            user_id,
                            filepath.name,
                        )
                        continue
                else:
                    logger.warning(
                        "Temp attachment without metadata rejected: %s",
                        filepath.name,
                    )
                    continue

                suffix = filepath.suffix.lower()

                if suffix in {".jpg", ".jpeg", ".png", ".webp"}:
                    yield event(
                        {
                            "type": "thinking",
                            "stage": "analyzing_image",
                            "message": "正在分析白斑图片...",
                        }
                    )
                    try:
                        result = _analyze_uploaded_image(filepath)
                        card = {
                            "type": "vasi",
                            "vasiScore": result.get("vasi_score", 0),
                            "bodySite": result.get("body_site", "其他"),
                            "classification": result.get("classification", "未分类"),
                            "stage": result.get("stage", "未知"),
                            "riskLevel": "red"
                            if "进展" in result.get("stage", "")
                            else "green",
                            "areaPercentage": result.get("area_percentage", 0),
                            "imageUrl": f"/uploads/temp/{filepath.name}",
                            "saved": False,
                        }
                        action_cards.append(card)
                        yield event({"type": "action_card", "card": card})
                    except Exception as exc:
                        logger.warning("VASI analysis failed: %s", str(exc))

                elif suffix in {".pdf", ".doc", ".docx", ".txt", ".md"}:
                    yield event(
                        {
                            "type": "thinking",
                            "stage": "reading_document",
                            "message": "正在解读文档...",
                        }
                    )
                    try:
                        doc_text = _extract_document_text(filepath)
                        interpretation = _interpret_report(doc_text, question)
                        card = {
                            "type": "report",
                            "title": filepath.stem,
                            "reportType": interpretation.get("report_type", "general"),
                            "riskLevel": interpretation.get("risk_level", "green"),
                            "summary": interpretation.get("summary", ""),
                            "keyFindings": interpretation.get("key_findings", []),
                            "recommendations": interpretation.get(
                                "recommendations", []
                            ),
                            "disclaimer": interpretation.get("disclaimer", ""),
                            "fileUrl": f"/uploads/temp/{filepath.name}",
                            "fileName": filepath.name,
                            "saved": False,
                        }
                        action_cards.append(card)
                        yield event({"type": "action_card", "card": card})
                    except Exception as exc:
                        logger.warning("Document interpretation failed: %s", str(exc))

        conversation_history = None
        if conversation_id:
            history = (
                db.query(Message)
                .filter(Message.conversation_id == conversation_id)
                .order_by(Message.created_at)
                .all()
            )
            conversation_history = [
                {"role": msg.role, "content": msg.content} for msg in history
            ]
            conv = (
                db.query(Conversation)
                .filter(Conversation.conversation_id == conversation_id)
                .first()
            )
            if not conv:
                conv = Conversation(conversation_id=conversation_id, user_id=user_id)
                db.add(conv)
                db.commit()

        yield event(
            {
                "type": "thinking",
                "stage": "generating",
                "message": "✨ 正在生成回答...",
            }
        )

        full_answer = ""
        for token in answer_question_stream(
            query=question,
            docs=docs,
            conversation_history=conversation_history,
            has_attachments=bool(attachment_ids),
            mode=mode,
        ):
            full_answer += token
            yield event({"type": "token", "content": token})

        if conversation_id:
            db.add(
                Message(conversation_id=conversation_id, role="user", content=question)
            )
            db.add(
                Message(
                    conversation_id=conversation_id,
                    role="assistant",
                    content=full_answer,
                )
            )
            db.commit()

        if action_cards:
            yield event(
                {
                    "type": "thinking",
                    "stage": "generating_diary",
                    "message": "正在生成白白日记草稿...",
                }
            )
            try:
                diary_card = _generate_diary_draft(question, full_answer, action_cards)
                action_cards.append(diary_card)
                yield event({"type": "action_card", "card": diary_card})
            except Exception as exc:
                logger.warning("Diary generation failed: %s", str(exc))

        done_data: dict = {"type": "done", "sources": sources}
        if remaining_quota is not None:
            done_data["remaining_quota"] = remaining_quota
        if is_guest:
            done_data["is_guest"] = True
        yield event(done_data)
    except Exception:
        # Stream failed before completing the answer. For guest users the daily
        # quota was incremented up-front; refund it so an error doesn't burn a
        # guest's limited free attempts. Logged for diagnosis, then re-raised so
        # the client still sees the failure.
        logger.exception("RAG stream failed before completion")
        if is_guest and guest_fingerprint:
            _refund_guest_usage(db, guest_fingerprint)
        raise
    finally:
        db.close()


@router.get("/conversations")
def list_conversations(
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(auth),
):
    if not current_user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="请登录")
    convs = (
        db.query(Conversation)
        .filter(
            Conversation.user_id == current_user.id, Conversation.is_deleted == False
        )
        .order_by(Conversation.updated_at.desc())
        .all()
    )
    result = []
    for conv in convs:
        first_msg = (
            db.query(Message)
            .filter(
                Message.conversation_id == conv.conversation_id, Message.role == "user"
            )
            .order_by(Message.created_at)
            .first()
        )
        title = first_msg.content[:50] if first_msg else "新对话"
        result.append(
            {
                "id": conv.conversation_id,
                "title": title,
                "date": conv.updated_at.isoformat()
                if conv.updated_at
                else conv.created_at.isoformat(),
                "created_at": conv.created_at.isoformat(),
            }
        )
    return result


@router.get("/conversations/{conversation_id}/messages")
def get_conversation_messages(
    conversation_id: str,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(auth),
):
    if not current_user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="请登录")
    conv = (
        db.query(Conversation)
        .filter(
            Conversation.conversation_id == conversation_id,
            Conversation.user_id == current_user.id,
        )
        .first()
    )
    if not conv or getattr(conv, "is_deleted", False):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="对话不存在")
    messages = (
        db.query(Message)
        .filter(Message.conversation_id == conversation_id)
        .order_by(Message.created_at)
        .all()
    )
    return [
        {
            "id": msg.id,
            "role": msg.role,
            "content": msg.content,
            "created_at": msg.created_at.isoformat(),
        }
        for msg in messages
    ]


@router.delete("/conversations/{conversation_id}")
def delete_conversation(
    conversation_id: str,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(auth),
):
    if not current_user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="请登录")
    conv = (
        db.query(Conversation)
        .filter(
            Conversation.conversation_id == conversation_id,
            Conversation.user_id == current_user.id,
        )
        .first()
    )
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="对话不存在")
    conv.is_deleted = True
    db.commit()
    return {"status": "ok"}
