"""Regression controls for the audited failure paths; no DB/network/patient data."""
import io
import json
from types import SimpleNamespace

import cv2
import numpy as np
import pytest
from PIL import Image
from web.backend.services import vasi_pixel_refine as vpr
from web.backend.services.annotation_contract import encode_layer
from web.backend.services.assessment_measurement import decode_mask, measure_layers, measurement_for


def square(x,y,size):
    return [[x,y],[x+size,y],[x+size,y+size],[x,y+size]]


def geometry(regions):
    return {'protocol':'skin-outline-v1','status':'candidate','skin_regions':[square(.02,.02,.96)],
            'excluded_regions':[],'lesion_regions':regions,'uncertain_regions':[]}


def photo():
    stream=io.BytesIO();Image.new('RGB',(200,200),(160,120,100)).save(stream,format='PNG');return stream.getvalue()


def disable_engines(monkeypatch):
    monkeypatch.setattr(vpr,'build_skin_mask',lambda rgb:None)
    monkeypatch.setattr(vpr.vasi_promptable,'prepare_image',lambda *args:None)
    monkeypatch.setattr(vpr.vasi_promptable,'predict_by_points',lambda *args,**kwargs:None)
    monkeypatch.setattr(vpr,'segment_lesions_edge_aware',lambda rgb,**kwargs:{'lesion_mask':np.zeros(rgb.shape[:2],bool)})


def test_concave_prompt_is_inside_not_in_centroid_hole():
    mask=np.zeros((200,200),bool);mask[20:180,20:50]=1;mask[20:50,20:180]=1;mask[150:180,20:180]=1
    points=vpr._sam_points(mask,200,200)
    assert points
    for x,y,label in points:
        assert bool(mask[min(199,round(y*200)),min(199,round(x*200))]) == bool(label)


def test_rectangle_has_noncontradictory_negative_prompts():
    mask=np.zeros((200,200),bool);mask[50:140,60:150]=1
    points=vpr._sam_points(mask,200,200)
    assert any(label==0 for x,y,label in points)
    assert all(not mask[round(y*200),round(x*200)] for x,y,label in points if label==0)


def test_gray_has_zero_real_lab_chroma():
    rgb=np.full((200,200,3),128,np.uint8);mask=np.zeros((200,200),bool);mask[60:140,60:140]=1
    stats=vpr._colour_stats(rgb,mask,np.ones_like(mask))
    assert stats['available'] and stats['lesion_C'] < .1
    assert 0 <= stats['lesion_L'] <= 100


def test_all_five_regions_are_accounted_for_as_unresolved(monkeypatch):
    disable_engines(monkeypatch)
    g=geometry([square(.1,.1,.1),square(.3,.1,.1),square(.5,.1,.1),square(.1,.5,.1),square(.5,.5,.1)])
    out=vpr.refine_annotation_layers(photo(),g,max_lesion_regions=4)
    assert out['provenance']['lesion_regions_total']==5
    assert len(out['provenance']['regions'])==5
    assert not decode_mask(out['lesion_layer_data_url']).any()
    uncertain=decode_mask(out['annotation']['uncertain_layer_data_url'])
    assert cv2.connectedComponents(uncertain.astype(np.uint8))[0]-1==5
    assert out['provenance']['measurement_eligible'] is False


def test_rejected_sam_does_not_survive_failed_cv(monkeypatch):
    disable_engines(monkeypatch)
    mask=np.zeros((200,200),bool);mask[60:121,60:121]=1
    monkeypatch.setattr(vpr.vasi_promptable,'prepare_image',lambda *args:{'cached':True})
    monkeypatch.setattr(vpr.vasi_promptable,'predict_by_points',lambda *args,**kwargs:{'mask_b64_png':encode_layer(mask,(0,170,100)),'score':.99})
    monkeypatch.setattr(vpr,'refine_mask_by_edges',lambda rgb,mask,**kwargs:mask)
    monkeypatch.setattr(vpr,'_colour_stats',lambda *args,**kwargs:{'available':1.,'lesion_L':0.,'skin_L':80.,'lesion_C':10.,'skin_C':10.})
    out=vpr.refine_annotation_layers(photo(),geometry([square(.3,.3,.3)]))
    assert not decode_mask(out['lesion_layer_data_url']).any()
    assert 'sam' not in out['provenance']['engine']['lesion']
    assert decode_mask(out['annotation']['uncertain_layer_data_url']).any()


def test_cv_skin_cannot_expand_selected_scope(monkeypatch):
    disable_engines(monkeypatch)
    full=np.ones((200,200),bool)
    monkeypatch.setattr(vpr,'build_skin_mask',lambda rgb:full)
    monkeypatch.setattr(vpr,'refine_skin_region',lambda *args:full)
    g=geometry([square(.3,.3,.2)]);g['skin_regions']=[square(.1,.1,.7)]
    out=vpr.refine_annotation_layers(photo(),g,time_budget_s=0)
    skin=decode_mask(out['skin_layer_data_url'])
    assert not skin[165:,:].any() and not skin[:,165:].any()


@pytest.mark.parametrize('state',['candidate-only','partial','cv-fallback','refined'])
def test_old_refinement_tags_do_not_prove_measurement_quality(state):
    annotation={'protocol':'skin-outline-v1','review_state':'pending','refine':{'version':'pixel-refine-v1','status':state}}
    a=SimpleNamespace(details=json.dumps({'annotation':annotation,'measurement':{'status':'measured','area_percentage':80.4,'area_cm2':12,'color':{'relative_lightness':8},'border':{'perimeter_pixels':50},'reasons':[]}}))
    m=measurement_for(a)
    assert m['status']=='unavailable' and m['area_percentage'] is None
    assert m['area_cm2'] is None and m['border'] is None and m['color'] is None


def test_user_review_allows_valid_mask_arithmetic():
    a=SimpleNamespace(details=json.dumps({'annotation':{'protocol':'skin-outline-v1','review_state':'user_reviewed','refine':{'status':'candidate-only'}},'measurement':{'status':'measured','area_percentage':20,'reasons':[]}}))
    assert measurement_for(a)['area_percentage']==20


def test_disabled_engine_cannot_promote_original_polygons(monkeypatch):
    monkeypatch.setenv('VASI_PIXEL_REFINE','0')
    assert vpr.refine_annotation_layers(photo(),geometry([square(.3,.3,.2)])) is None
    a=SimpleNamespace(details=json.dumps({'annotation':{'protocol':'skin-outline-v1','review_state':'pending'},'measurement':{'status':'measured','area_percentage':20,'reasons':[]}}))
    assert measurement_for(a)['status']=='unavailable'

def test_real_image_boundary_required_even_for_high_sam_score(monkeypatch):
    disable_engines(monkeypatch)
    full=np.ones((200,200),bool)
    monkeypatch.setattr(vpr,'build_skin_mask',lambda rgb:full)
    monkeypatch.setattr(vpr,'refine_skin_region',lambda *args:full)
    monkeypatch.setattr(vpr.vasi_promptable,'prepare_image',lambda *args:{'cached':True})
    mask=np.zeros((200,200),bool);mask[60:121,60:121]=1
    monkeypatch.setattr(vpr.vasi_promptable,'predict_by_points',lambda *args,**kwargs:{'mask_b64_png':encode_layer(mask,(0,170,100)),'score':.999})
    out=vpr.refine_annotation_layers(photo(),geometry([square(.3,.3,.3)]))
    assert not decode_mask(out['lesion_layer_data_url']).any()
    assert 'lesion:boundary-unsupported' in out['provenance']['fallback_reasons']


def test_model_refusal_is_not_retried_until_a_result_appears(monkeypatch):
    import asyncio,sys
    from web.backend.services import annotation_provider as provider
    calls=[]
    class Client:
        def __init__(self,**kwargs):self.chat=SimpleNamespace(completions=self)
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        async def create(self,**kwargs):
            calls.append(kwargs)
            return SimpleNamespace(choices=[SimpleNamespace(finish_reason='stop',message=SimpleNamespace(content=json.dumps(dict(geometry([]),status='not_assessable'))))])
    monkeypatch.setitem(sys.modules,'openai',SimpleNamespace(AsyncOpenAI=Client))
    monkeypatch.setattr(provider,'get_llm_config',lambda module:{'vision_model':'synthetic-model','api_key':'synthetic','base_url':'https://invalid.example'})  # pragma: allowlist secret
    monkeypatch.setenv('VASI_ANNOTATION_RETRIES','100')
    from web.backend.services.annotation_contract import AnnotationContractError
    with pytest.raises(AnnotationContractError):asyncio.run(provider.propose_annotation(photo(),'面部'))
    assert len(calls)==1


def test_review_of_legacy_cv_fallback_is_reachable():
    from web.backend.services.annotation_review import apply_review
    from web.backend.services.annotation_contract import render_annotation
    layers=render_annotation(geometry([square(.3,.3,.2)]),200,200)
    a=SimpleNamespace(user_id=1,details=json.dumps({'annotation':{'protocol':None,'review_state':'pending','refine':{'status':'cv-fallback'}}}))
    result=apply_review(a,layers['skin_layer_data_url'],layers['lesion_layer_data_url'],True,photo())
    assert result['status']=='measured'
    assert json.loads(a.details)['annotation']['protocol']=='skin-outline-v1'

def test_genuine_rectangular_colour_boundary_is_not_banned(monkeypatch):
    disable_engines(monkeypatch)
    rgb=np.full((200,200,3),(160,120,100),np.uint8);rgb[60:121,60:121]=(242,232,224)
    stream=io.BytesIO();Image.fromarray(rgb).save(stream,format='PNG')
    mask=np.zeros((200,200),bool);mask[60:121,60:121]=1
    monkeypatch.setattr(vpr.vasi_promptable,'prepare_image',lambda *args:{'cached':True})
    monkeypatch.setattr(vpr.vasi_promptable,'predict_by_points',lambda *args,**kwargs:{'mask_b64_png':encode_layer(mask,(0,170,100)),'score':.99})
    out=vpr.refine_annotation_layers(stream.getvalue(),geometry([square(.3,.3,.3)]))
    assert decode_mask(out['lesion_layer_data_url']).any()
    assert out['provenance']['regions'][0]['status']=='accepted'
