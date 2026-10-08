"""Durable per-revision artwork tasks; refreshes resume rather than resubmit."""
import hashlib
import json
import time
from typing import Any, Dict, Optional
from uuid import uuid4

from sqlalchemy.orm import Session
from web.backend.exceptions import StoryGenerationError, ArtAdmissionRejected
from web.backend.models.vasi import VASIAssessment
from web.backend.services.assessment_measurement import read_details
from web.backend.services.assessment_story import create_story, owned_snapshot, geometry, validate_theme
from web.backend.services.consent import has_active_consent, CONSENT_TYPE_AI_DATA, CONSENT_TYPE_MEDICAL_PHOTO
from web.backend.services import assessment_art_provider as provider

ART_VERSION = 'contour-guide-v1'
STYLES = {'sky': '柔和云朵与天空，浅蓝、米白色，光线轻盈。',
          'island': '海岛与海岸的微缩自然风景，青绿海水、沙滩与植被。',
          'stars': '星光与宇宙星云，深蓝、暖金色，细腻微光。'}


def require_consent(db: Session, owner: int) -> None:
    if not (has_active_consent(db, owner, CONSENT_TYPE_AI_DATA) or has_active_consent(db, owner, CONSENT_TYPE_MEDICAL_PHOTO)):
        raise StoryGenerationError('开启AI数据授权后可生成艺术画面', 403)


def public_state(value: Dict[str, Any]) -> Dict[str, Any]:
    result = {'status': value['status'], 'revision': value['revision'], 'model': provider.MODEL}
    if value.get('theme'): result['theme'] = value['theme']
    if value['status'] == 'ready': result['image_data_url'] = value['image_data_url']
    if value['status'] == 'failed': result['message'] = '艺术画面暂未生成，已保留基础创意'
    return result


def write_state(db: Session, record: VASIAssessment, state: Dict[str, Any]) -> None:
    original = record.details
    details = read_details(original)
    if state.get('selected_theme'): details.setdefault('creative_arts', {})[state['selected_theme']] = state
    else: details['creative_art'] = state
    changed = db.query(VASIAssessment).filter_by(id=record.id, user_id=record.user_id, status='active', details=original).update(
        {VASIAssessment.details: json.dumps(details, ensure_ascii=False)}, synchronize_session=False)
    if changed != 1:
        db.rollback()
        raise StoryGenerationError('记录正在更新，请稍后重试', 409)
    db.commit()


def art_state(record: VASIAssessment, theme: Optional[str]) -> Dict[str, Any]:
    details = read_details(record.details)
    return (details.get('creative_arts') or {}).get(theme, {}) if theme else details.get('creative_art') or {}


def start_art(db: Session, assessment_id: int, owner: int, revision: str, retry: bool = False, theme: Optional[str] = None) -> Dict[str, Any]:
    validate_theme(theme)
    record = owned_snapshot(db, assessment_id, owner, revision)
    existing = art_state(record, theme)
    def reusable(value):
        return value.get('revision') == revision and value.get('version') == ART_VERSION and not (retry and value.get('status') == 'failed' and value.get('retryable') and value.get('attempt', 1) < 2 and time.time() - value.get('started', 0) >= 30)
    if reusable(existing): return public_state(existing)
    require_consent(db, owner)
    plan = create_story(db, assessment_id, owner, revision, theme=theme)
    prompt = plan.get('art_prompt')
    if not prompt: raise StoryGenerationError('请先生成创意构思', 409)
    record = owned_snapshot(db, assessment_id, owner, revision)
    existing = art_state(record, theme)
    if reusable(existing): return public_state(existing)
    # This committed reservation prevents repeated admission, even across process restarts.
    guide = geometry(record)['silhouette']
    state = {'revision': revision, 'selected_theme': theme, 'theme': plan['theme'], 'version': ART_VERSION, 'status': 'pending', 'token': uuid4().hex, 'task_id': None,
             'started': time.time(), 'attempt': existing.get('attempt', 0) + 1 if existing.get('revision') == revision else 1, 'last_checked': 0, 'prompt_hash': hashlib.sha256(prompt.encode()).hexdigest()}
    write_state(db, record, state)
    full_prompt = STYLES[plan['theme']] + '参考图深色区域是各艺术主体，浅色区域是留白。严格保持每个主体在正方形中的位置、外形和孔洞，必须让每一小块也有对应主体细节。不要移动、缩放或新增主体，不要在浅色孔洞中放置主体。' + prompt + '仅创作对应深色区域内的自然风景肌理，背景纯色干净。不要文字、数字、标志、水印、人物、人体或医学图表。'
    try:
        task = provider.submit(full_prompt, guide)
    except Exception as exc:
        # A timeout may have created a paid provider task; do not automatically resubmit.
        record = owned_snapshot(db, assessment_id, owner, revision)
        current = art_state(record, theme)
        if current.get('token') == state['token']:
            write_state(db, record, dict(state, status='failed', retryable=isinstance(exc, ArtAdmissionRejected)))
        raise StoryGenerationError('艺术任务暂未确认，已保留基础创意', 503)
    record = owned_snapshot(db, assessment_id, owner, revision)
    current = art_state(record, theme)
    if current.get('token') != state['token']: raise StoryGenerationError('创意版本已更新', 409)
    state['task_id'] = task
    write_state(db, record, state)
    return public_state(state)


def read_art(db: Session, assessment_id: int, owner: int, revision: str, theme: Optional[str] = None) -> Dict[str, Any]:
    validate_theme(theme)
    record = owned_snapshot(db, assessment_id, owner, revision)
    state = art_state(record, theme)
    if state.get('revision') != revision: raise StoryGenerationError('当前记录尚未开始创作', 404)
    if state['status'] != 'pending': return public_state(state)
    if not state.get('task_id'):
        if time.time() - state['started'] > 90:
            state['status'] = 'failed'; write_state(db, record, state)
        return public_state(state)
    require_consent(db, owner)
    if time.time() - state.get('last_checked', 0) < 2: return public_state(state)
    state['last_checked'] = time.time()
    write_state(db, record, state)
    # No database lock/transaction is held across network or image decode operations.
    result = provider.poll(state['task_id'])
    record = owned_snapshot(db, assessment_id, owner, revision)
    current = art_state(record, theme)
    if current.get('token') != state['token']: raise StoryGenerationError('创意版本已更新', 409)
    if current['status'] != 'pending': return public_state(current)
    if result['status'] in ('ready', 'failed'):
        state.update(result); write_state(db, record, state)
    return public_state(state)
