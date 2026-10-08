"""Synthetic records only; all model calls mocked."""
import base64
import io
import json
from unittest.mock import Mock

import pytest
from PIL import Image
from web.backend.exceptions import StoryGenerationError
from web.backend.models.vasi import VASIAssessment
from web.backend.services import assessment_story as service

REVISION = 'a' * 64


def layer():
    out = io.BytesIO()
    image = Image.new('RGBA', (24, 24), (255, 255, 255, 255))
    image.save(out, format='PNG')
    return 'data:image/png;base64,' + base64.b64encode(out.getvalue()).decode()


@pytest.fixture
def record(db_session, test_user):
    item = VASIAssessment(user_id=test_user.id, image_url='/synthetic.png', body_site='left_hand',
        vasi_score=0, area_percentage=25, classification='', stage='', status='active', user_lesion_layer=layer(),
        details=json.dumps({'measurement': {'status':'measured','area_percentage':25,'region_count':1},
                            'annotation': {'protocol':'skin-seg-v2','review_state':'user_reviewed','mask_revision':REVISION}}))
    db_session.add(item); db_session.commit(); db_session.refresh(item)
    return item


@pytest.fixture
def model(monkeypatch):
    fn = Mock(return_value={'theme':'sky','title':'把一片晴空，轻轻握在手心。','source':'ai','art_prompt':'细腻水彩天空与层层舒展的云朵纹理，自然光照，无文字无人像，铺满整个画面。'})
    monkeypatch.setattr(service, 'generate_caption', fn)
    monkeypatch.setattr(service, 'has_active_consent', lambda *args: True)
    return fn


def test_reviewed_story_is_cached_without_changing_measurement(db_session, record, model):
    before = json.loads(record.details)
    result = service.create_story(db_session, record.id, record.user_id, REVISION)
    assert result['source'] == 'ai' and result['revision'] == REVISION
    again = service.create_story(db_session, record.id, record.user_id, REVISION)
    assert again == result and model.call_count == 1
    db_session.refresh(record)
    after = json.loads(record.details)
    assert after['measurement'] == before['measurement'] and after['annotation'] == before['annotation']
    assert record.area_percentage == 25
    assert set(model.call_args.args[0]) == {'shape','arrangement','body_site','silhouette'}


@pytest.mark.parametrize('case', ['owner','revision','pending','draft','empty'])
def test_invalid_or_unreviewed_records_never_call_model(db_session, record, model, case):
    owner, revision = record.user_id, REVISION
    if case == 'owner': owner += 100
    if case == 'revision': revision = 'b'*64
    if case == 'pending':
        details=json.loads(record.details);details['annotation']['review_state']='pending';record.details=json.dumps(details)
    if case == 'draft': record.status='draft'
    if case == 'empty': record.user_lesion_layer=None
    db_session.commit()
    with pytest.raises(StoryGenerationError): service.create_story(db_session, record.id, owner, revision)
    model.assert_not_called()


def test_consent_required_before_external_call(db_session, record, model, monkeypatch):
    monkeypatch.setattr(service, 'has_active_consent', lambda *args: False)
    with pytest.raises(StoryGenerationError) as error: service.create_story(db_session, record.id, record.user_id, REVISION)
    assert error.value.http_status == 403
    model.assert_not_called()


@pytest.mark.parametrize('value', [None, {}, {'theme':'other','title':'天空'}, {'theme':'sky','title':'皮肤一定会治愈'}, {'theme':'sky','title':'今天白斑好转百分之十'}, {'theme':'sky','title':'<script>测试</script>'}, {'theme':'sky','title':'一'*25}])
def test_invalid_model_output_rejected(value):
    with pytest.raises(StoryGenerationError): service.validate_story(value)


def test_changed_record_rejects_late_model_output(db_session, record, model):
    def changed(_):
        item=db_session.get(VASIAssessment, record.id); details=json.loads(item.details)
        details['annotation']['mask_revision']='b'*64;item.details=json.dumps(details);db_session.commit()
        return {'theme':'stars','title':'每一点微光，都值得被看见。','source':'ai'}
    model.side_effect=changed
    with pytest.raises(StoryGenerationError) as error: service.create_story(db_session, record.id, record.user_id, REVISION)
    assert error.value.http_status == 409
    db_session.refresh(record);assert 'creative_story' not in json.loads(record.details)


def test_model_failure_does_not_modify_record_and_releases_slot(db_session, record, model):
    before=record.details;model.side_effect=TimeoutError()
    with pytest.raises(TimeoutError): service.create_story(db_session, record.id, record.user_id, REVISION)
    db_session.refresh(record);assert record.details == before
    model.side_effect=None
    assert service.create_story(db_session, record.id, record.user_id, REVISION)['source']=='ai'


@pytest.fixture
def story_api():
    # Load the route in isolation: api/__init__.py eagerly loads unrelated admin/crypto modules.
    import importlib.util
    import sys
    from pathlib import Path
    name = 'web.backend.api.assessment_story'
    spec = importlib.util.spec_from_file_location(name, Path(__file__).resolve().parents[3] / 'web/backend/api/assessment_story.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_api_uses_owner_and_revision_and_returns_private_cache_headers(db_session, record, model, test_user, story_api):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    router, get_db, get_current_user = story_api.router, story_api.get_db, story_api.get_current_user
    app=FastAPI();app.include_router(router,prefix='/api/vasi')
    app.dependency_overrides[get_db]=lambda:db_session
    app.dependency_overrides[get_current_user]=lambda:test_user
    with TestClient(app) as client:
        url='/api/vasi/assess/%s/story' % record.id
        result=client.post(url,json={'revision':REVISION})
        assert result.status_code==200 and result.headers['cache-control']=='private, no-store'
        assert result.json()['source']=='ai'
        assert client.post(url,json={'revision':'b'*64}).status_code==409
        assert client.post(url,json={'revision':'../anything'}).status_code==422
        assert client.post('/api/vasi/assess/99999/story',json={'revision':REVISION}).status_code==404


def test_api_does_not_expose_provider_errors(db_session, record, model, test_user, story_api):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    router, get_db, get_current_user = story_api.router, story_api.get_db, story_api.get_current_user
    app=FastAPI();app.include_router(router)
    app.dependency_overrides[get_db]=lambda:db_session
    app.dependency_overrides[get_current_user]=lambda:test_user
    model.side_effect=RuntimeError('synthetic-provider-secret')
    with TestClient(app) as client:
        result=client.post('/assess/%s/story' % record.id,json={'revision':REVISION})
        assert result.status_code==503 and 'synthetic-provider-secret' not in result.text


def test_same_record_in_flight_rejected_without_second_model_call(db_session, record, model):
    key=(record.user_id,record.id);service._active.add(key)
    try:
        with pytest.raises(StoryGenerationError) as error:service.create_story(db_session,record.id,record.user_id,REVISION)
        assert error.value.http_status==429;model.assert_not_called()
    finally:service._active.discard(key)
