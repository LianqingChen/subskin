"""Durable artwork tests on synthetic in-memory records; no external requests."""
import base64
import io
import json
from unittest.mock import Mock

import pytest
from PIL import Image
from web.backend.exceptions import StoryGenerationError
from web.backend.services import assessment_art as art, assessment_art_provider as provider
from tests.backend.services.test_assessment_story import record, model, story_api, REVISION


@pytest.fixture
def images(monkeypatch, model):
    model.return_value['art_prompt']='细腻水彩云朵自然风景，纯净天空中充满光线与柔软纹理，无文字无人像。'
    monkeypatch.setattr(art, 'has_active_consent', lambda *args: True)
    submit=Mock(return_value='synthetic-task-id');poll=Mock(return_value={'status':'ready','image_data_url':'data:image/jpeg;base64,synthetic'})
    monkeypatch.setattr(provider,'submit',submit);monkeypatch.setattr(provider,'poll',poll)
    return submit,poll


def test_refresh_and_poll_reuse_one_task_and_cache_art_without_changing_masks(db_session, record, images):
    before=json.loads(record.details);mask=record.user_lesion_layer
    first=art.start_art(db_session,record.id,record.user_id,REVISION)
    assert first['status']=='pending' and 'task_id' not in first
    again=art.start_art(db_session,record.id,record.user_id,REVISION);assert first==again
    result=art.read_art(db_session,record.id,record.user_id,REVISION);assert result['status']=='ready'
    assert art.start_art(db_session,record.id,record.user_id,REVISION)==result
    assert art.read_art(db_session,record.id,record.user_id,REVISION)==result
    assert images[0].call_count==1 and images[1].call_count==1
    db_session.refresh(record);after=json.loads(record.details)
    assert before['measurement']==after['measurement'] and before['annotation']==after['annotation'] and mask==record.user_lesion_layer


def test_unknown_admission_is_not_submitted_again(db_session,record,images):
    images[0].side_effect=TimeoutError()
    with pytest.raises(StoryGenerationError):art.start_art(db_session,record.id,record.user_id,REVISION)
    assert art.start_art(db_session,record.id,record.user_id,REVISION)['status']=='failed'
    assert images[0].call_count==1


def test_late_art_cannot_replace_new_revision(db_session,record,images):
    art.start_art(db_session,record.id,record.user_id,REVISION)
    def late(_):
        item=db_session.get(type(record),record.id);details=json.loads(item.details);details['annotation']['mask_revision']='b'*64
        item.details=json.dumps(details);db_session.commit()
        return {'status':'ready','image_data_url':'data:image/jpeg;base64,late'}
    images[1].side_effect=late
    with pytest.raises(StoryGenerationError):art.read_art(db_session,record.id,record.user_id,REVISION)
    db_session.refresh(record);assert json.loads(record.details)['creative_art']['status']=='pending'


def test_ownership_consent_and_review_guard_paid_calls(db_session,record,images,monkeypatch):
    with pytest.raises(StoryGenerationError):art.start_art(db_session,record.id,record.user_id+1,REVISION)
    with pytest.raises(StoryGenerationError):art.start_art(db_session,record.id,record.user_id,'wrong-revision')
    monkeypatch.setattr(art,'has_active_consent',lambda *args:False)
    with pytest.raises(StoryGenerationError) as exc:art.start_art(db_session,record.id,record.user_id,REVISION)
    assert exc.value.http_status==403;images[0].assert_not_called()


def test_pending_poll_is_throttled_and_refresh_preserves_task(db_session,record,images):
    images[1].return_value={'status':'pending'}
    art.start_art(db_session,record.id,record.user_id,REVISION)
    assert art.read_art(db_session,record.id,record.user_id,REVISION)['status']=='pending'
    assert art.read_art(db_session,record.id,record.user_id,REVISION)['status']=='pending'
    assert images[1].call_count==1 and images[0].call_count==1


@pytest.mark.parametrize('url',['http://127.0.0.1/a','https://evil.example/a','https://dashscope-a.oss-accelerate.aliyuncs.com.evil.example/a','https://user:pass@dashscope-a.oss-accelerate.aliyuncs.com/a'])  # pragma: allowlist secret
def test_art_download_rejects_untrusted_hosts(url):
    with pytest.raises(StoryGenerationError):provider.download_image(url)


def test_signed_provider_image_is_bounded_and_normalized(monkeypatch):
    raw=io.BytesIO();Image.new('RGB',(64,64),(120,150,180)).save(raw,format='PNG')
    response=Mock(status_code=200);response.__enter__=Mock(return_value=response);response.__exit__=Mock(return_value=False)
    response.iter_content.return_value=[raw.getvalue()]
    get=Mock(return_value=response);monkeypatch.setattr(provider.requests,'get',get)
    image=provider.download_image('https://dashscope-a.oss-accelerate.aliyuncs.com/synthetic.png')
    assert image.startswith('data:image/jpeg;base64,')
    assert Image.open(io.BytesIO(base64.b64decode(image.split(',')[1]))).size==(64,64)
    assert get.call_args.kwargs['allow_redirects'] is False and 'headers' not in get.call_args.kwargs


def test_terminal_failure_retries_only_on_explicit_request_and_at_most_once(db_session,record,images,monkeypatch):
    clock=[1000.0];monkeypatch.setattr(art.time,'time',lambda:clock[0])
    images[1].return_value={'status':'failed','retryable':True}
    art.start_art(db_session,record.id,record.user_id,REVISION)
    art.read_art(db_session,record.id,record.user_id,REVISION)
    assert art.start_art(db_session,record.id,record.user_id,REVISION)['status']=='failed'
    clock[0]+=31
    assert art.start_art(db_session,record.id,record.user_id,REVISION,retry=True)['status']=='pending'
    art.read_art(db_session,record.id,record.user_id,REVISION);clock[0]+=31
    assert art.start_art(db_session,record.id,record.user_id,REVISION,retry=True)['status']=='failed'
    assert images[0].call_count==2


def test_actual_route_resumes_private_art(db_session,record,images,test_user,story_api):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    app=FastAPI();app.include_router(story_api.router)
    app.dependency_overrides[story_api.get_db]=lambda:db_session
    app.dependency_overrides[story_api.get_current_user]=lambda:test_user
    with TestClient(app) as client:
        url='/assess/%s/story/art'%record.id
        first=client.post(url,json={'revision':REVISION});assert first.status_code==200
        ready=client.get(url,params={'revision':REVISION});assert ready.status_code==200 and ready.json()['status']=='ready'
        assert ready.headers['cache-control']=='private, no-store'
        assert client.get(url,params={'revision':'wrong'}).status_code==409


def test_provider_uses_dedicated_async_endpoint_and_single_image(monkeypatch):
    monkeypatch.setattr(provider,'get_llm_config',lambda _: {'api_key':'synthetic-key','base_url':'https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1'})  # pragma: allowlist secret
    response=Mock(ok=True);response.json.return_value={'output':{'task_id':'synthetic-task'}}
    post=Mock(return_value=response);monkeypatch.setattr(provider.requests,'post',post)
    assert provider.submit('synthetic prompt')=='synthetic-task'
    assert post.call_args.args[0].endswith('/api/v1/services/aigc/image-generation/generation')
    assert post.call_args.kwargs['headers']['X-DashScope-Async']=='enable'
    body=post.call_args.kwargs['json'];assert body['model']=='qwen-image-3.0-pro' and body['parameters']['n']==1
    assert body['input']['messages'][0]['content']==[{'text':'synthetic prompt'}]


@pytest.mark.parametrize('state,expected',[('PENDING','pending'),('RUNNING','pending'),('FAILED','failed'),('CANCELED','failed'),('UNKNOWN','failed'),('SUCCEEDED','ready')])
def test_provider_polls_real_response_shape(monkeypatch,state,expected):
    monkeypatch.setattr(provider,'connection',lambda:{'root':'https://synthetic.aliyuncs.com','key':'synthetic'})
    response=Mock(ok=True);response.json.return_value={'output':{'task_status':state,'choices':[{'message':{'content':[{'image':'https://synthetic-image'}]}}]}}
    monkeypatch.setattr(provider.requests,'get',Mock(return_value=response));monkeypatch.setattr(provider,'download_image',lambda _: 'data:image/jpeg;base64,synthetic')
    assert provider.poll('synthetic-task')['status']==expected


def test_three_styles_cache_plans_and_art_independently(db_session,record,images,model):
    from web.backend.services.assessment_story import create_story
    def planned(description):
        return {'theme':description['theme'],'title':'这片风景也有自己的光。','source':'ai','art_prompt':'细腻的自然风景铺满轮廓，以用户选定主题展现具体纹理，无文字无人像。'}
    model.side_effect=planned
    for theme in ['sky','island','stars']:
        assert create_story(db_session,record.id,record.user_id,REVISION,theme)['theme']==theme
        assert art.start_art(db_session,record.id,record.user_id,REVISION,theme=theme)['status']=='pending'
        assert art.read_art(db_session,record.id,record.user_id,REVISION,theme=theme)['status']=='ready'
    for theme in ['stars','sky','island']:
        assert create_story(db_session,record.id,record.user_id,REVISION,theme)['theme']==theme
        assert art.start_art(db_session,record.id,record.user_id,REVISION,theme=theme)['theme']==theme
    assert model.call_count==3 and images[0].call_count==3
    db_session.refresh(record);details=json.loads(record.details)
    assert set(details['creative_arts'])=={'sky','island','stars'}
    assert set(details['creative_stories'])=={'sky','island','stars'}
    with pytest.raises(StoryGenerationError):art.start_art(db_session,record.id,record.user_id,REVISION,theme='invalid')


def test_style_parameter_reaches_real_api_and_invalid_styles_are_rejected(db_session,record,images,test_user,story_api):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    app=FastAPI();app.include_router(story_api.router)
    app.dependency_overrides[story_api.get_db]=lambda:db_session
    app.dependency_overrides[story_api.get_current_user]=lambda:test_user
    with TestClient(app) as client:
        url='/assess/%s/story'%record.id
        plan=client.post(url,json={'revision':REVISION,'theme':'sky'})
        assert plan.status_code==200 and plan.json()['theme']=='sky'
        started=client.post(url+'/art',json={'revision':REVISION,'theme':'sky'})
        assert started.status_code==200 and started.json()['theme']=='sky'
        image=client.get(url+'/art',params={'revision':REVISION,'theme':'sky'})
        assert image.status_code==200 and image.json()['theme']=='sky'
        assert client.get(url+'/art',params={'revision':REVISION,'theme':'stars'}).status_code==404
        assert client.post(url,json={'revision':REVISION,'theme':'invalid'}).status_code==422
