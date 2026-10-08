"""Request/response integration on an isolated in-memory database."""
import base64
import io
import json
import os
import secrets
from datetime import datetime
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import AsyncMock

os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
os.environ.setdefault('SECRET_KEY', secrets.token_urlsafe(32))

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from PIL import Image

from web.backend.api.vasi import router, get_db, get_current_user
from web.backend.services.vasi import VASIService, VASIAssessmentError
from web.backend.database.database import Base
from web.backend.models.vasi import VASIAssessment
ORIGINAL_ASSESS = VASIService.assess_vasi


@pytest.fixture
def client(monkeypatch):
    engine = create_engine('sqlite:///:memory:', connect_args={'check_same_thread':False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    app = FastAPI(); app.include_router(router)
    app.dependency_overrides[get_db] = lambda: session
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=123, is_admin=False)
    async def assess(self, **kwargs):
        row = VASIAssessment(user_id=123, image_url='/api/files/serve/vasi/synthetic.png', body_site='左手',
             vasi_score=1, area_percentage=10, classification='未确定', stage='未知', status='draft',
             details=json.dumps({'measurement': {'version':'photo-mask-v1','status':'measured','area_percentage':10,'reasons':[]}}))
        session.add(row);session.commit();session.refresh(row)
        return row
    monkeypatch.setattr(VASIService,'assess_vasi',assess)
    with TestClient(app) as http: yield http, session
    session.close();engine.dispose()


def upload(client, **fields):
    out=io.BytesIO();Image.new('RGB',(800,800),(180,140,120)).save(out,format='PNG')
    return client.post('/assess',data={'body_site':'left_hand','view':'背面','intent':'tracking','capture_date':'2026-09-01',**fields},files={'image':('synthetic.png',out.getvalue(),'image/png')})


def test_context_round_trip_and_repeat_position(client):
    http, session = client
    first=upload(http, observation_label='位置A')
    assert first.status_code==200,first.text
    data=first.json(); assert data['measurement']['version']=='photo-mask-v1'
    aid=data['id'];root=data['observation']['id']
    assert http.post(f'/assess/{aid}/finalize').status_code==200
    second=upload(http,baseline_id=str(aid),capture_date='2026-09-02')
    assert second.status_code==200,second.text
    assert second.json()['observation']['id']==root
    hist=http.get('/history').json()
    assert hist['items'][0]['observation']['label']=='位置A'
    assert hist['items'][0]['measurement']['area_percentage']==10
    detail=http.get(f'/assess/{aid}').json()
    assert detail['observation']['capture_date']=='2026-09-01'


def test_bad_context_rejected_without_record(client):
    http,session=client
    assert upload(http,capture_date='invalid').status_code==400
    assert upload(http,baseline_id='987').status_code==400
    assert session.query(VASIAssessment).count()==0


def test_poor_photo_cannot_be_finalized(client):
    http,session=client
    row=VASIAssessment(user_id=123,image_url='synthetic',body_site='左手',vasi_score=0,area_percentage=0,classification='未知',stage='未知',status='draft',details=json.dumps({'quality_reject':True}))
    session.add(row);session.commit()
    with pytest.raises(VASIAssessmentError): VASIService(session).finalize_assessment(row.id,123)
    assert row.status=='draft'
    assert http.post(f'/assess/{row.id}/finalize').status_code==400


def test_generated_preview_keeps_owner_scoped_filename(tmp_path, monkeypatch):
    import numpy as np
    from web.backend.services import assessment_comparison as comp, spot_compare
    from test_measurement import photo, overlay
    mask=np.zeros((200,200),bool);mask[50:110,50:110]=True
    rgb,skin,lesion=photo(mask)
    buf=io.BytesIO();Image.fromarray(rgb).save(buf,format='PNG')
    info={'user_id':123,'image_url':'synthetic','skin_layer':overlay(skin),'ai_lesion_layer':overlay(lesion)}
    monkeypatch.setattr(spot_compare,'load_photo_ref',lambda *a:info)
    monkeypatch.setattr(spot_compare,'resolve_image_bytes',lambda *a:buf.getvalue())
    monkeypatch.chdir(tmp_path)
    pair={'ref_a':'va:1','ref_b':'va:2','merged':{'comparison_status':'measured','evidence':{'transform':[[1,0,0],[0,1,0]],'alignment_error_px':0}}}
    result=comp.save_comparison_preview(None,123,pair)
    assert result['aligned']
    assert Path(result['heatmap_url']).name.startswith('123_')


def test_full_orchestration_preserves_large_patch_and_submitted_site(client, monkeypatch, tmp_path):
    import numpy as np
    from web.backend.services import vasi as service_module
    from test_measurement import overlay
    _, session=client
    skin=np.ones((800,800),bool);mask=np.zeros_like(skin);mask[40:760,40:760]=True
    image=io.BytesIO();Image.new('RGB',(800,800),(180,140,120)).save(image,format='PNG')
    model={'vasi_score':99,'area_percentage':99,'body_site':'legs','depigmentation_level':2,
      'classification':'非节段型','stage':'稳定','confidence':0.9,'details':{},'raw_response':{},
      'skin_region':{'bbox':[0,0,1,1]},'suspected_lesions':[{'center':[0.5,0.5],'bbox':[0.05,0.05,0.95,0.95],
        'confidence':0.9,'depigmentation_level':2,'estimated_size_percent':81}]}
    # Undo fixture stub, then test actual service orchestration without network/weights.
    original_method = ORIGINAL_ASSESS
    svc=VASIService(session)
    svc.quality_checker=SimpleNamespace(available=True,check_all=lambda b:SimpleNamespace(overall='good',suggestions=[],blur_score=200))
    monkeypatch.setattr(svc,'_call_vision_model',AsyncMock(return_value=model))
    seen=[]
    def segmentation(image, bbox, centers, precision, sizes, bboxes, *args):
        seen.extend(bboxes or [])
        return {'success':True,'source':'synthetic','contours':[],'total_area_percent':81,
           'skin_layer_data_url':overlay(skin),'lesion_layer_data_url':overlay(mask)}
    monkeypatch.setattr(service_module,'segment_vitiligo_guided',segmentation)
    monkeypatch.setattr(service_module,'_run_patient_consensus_sync',lambda *a:None)
    monkeypatch.chdir(tmp_path)
    import asyncio
    row=asyncio.run(original_method(svc,123,image.getvalue(),'left_hand','image/png','synthetic.png'))
    measurement=json.loads(row.details)['measurement']
    assert seen==[[0.05,0.05,0.95,0.95]]
    assert row.body_site=='左手'
    assert row.stage=='未知'
    assert row.area_percentage==81
    assert measurement['area_percentage']==81
    assert measurement['clinical_vasi'] is None


def test_exact_duplicate_is_not_a_longitudinal_stability_claim(monkeypatch):
    from datetime import date
    from web.backend.services import spot_compare
    def info(db,ref,**kwargs):
        return {'ref':ref,'user_id':123,'body_site':'left_hand','body_site_label':'左手','image_url':'synthetic',
                'date':date(2026,9,1) if ref=='va:1' else date(2026,9,2)}
    monkeypatch.setattr(spot_compare,'load_photo_ref',info)
    monkeypatch.setattr(spot_compare,'resolve_image_bytes',lambda *a:b'identical synthetic bytes')
    monkeypatch.setattr(spot_compare,'_quality_factor',lambda *a:(1.0,'good'))
    monkeypatch.setattr(spot_compare,'_save_comparison_cache',lambda *a,**k:None)
    pair=spot_compare.compare_pair(None,123,'va:1','va:2',force=True)
    assert pair['merged']['comparison_status']=='not_comparable'
    assert pair['merged']['size_change_percent'] is None
    assert pair['merged']['evidence']['duplicate'] is True
