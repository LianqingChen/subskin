"""Synthetic protocol and review tests; no DB, private images or provider calls."""
import asyncio
import io
import json
from types import SimpleNamespace

import numpy as np
import pytest
from PIL import Image
from web.backend.services.annotation_contract import (PROTOCOL, AnnotationContractError, parse_annotation, render_annotation)
from web.backend.services.assessment_measurement import decode_mask, measure_layers, measurement_for
from web.backend.services.annotation_review import apply_review


def square(a, b):
    return [[a,a],[b,a],[b,b],[a,b]]


def document():
    return {"protocol":PROTOCOL,"status":"candidate","skin_regions":[square(.1,.9)],
            "excluded_regions":[square(.3,.4)],"lesion_regions":[square(.2,.7)],"uncertain_regions":[square(.6,.8)]}


def test_layers_exclude_background_holes_and_uncertainty():
    result=render_annotation(document(),101,101)
    skin=decode_mask(result['skin_layer_data_url']);lesion=decode_mask(result['lesion_layer_data_url'])
    uncertain=decode_mask(result['annotation']['uncertain_layer_data_url'])
    assert not (lesion & ~skin).any()
    assert not (lesion & uncertain).any()
    assert not skin[35,35] and not lesion[35,35]
    assert not skin[:9,:].any() and not lesion[:9,:].any()
    assert uncertain[65,65] and not lesion[65,65]
    assert result['annotation']['review_state']=='pending'
    assert measure_layers(result['skin_layer_data_url'],result['lesion_layer_data_url'])['area_cm2'] is None


@pytest.mark.parametrize('bad',[-.01,1.01,float('nan'),float('inf'),True,'0.2'])
def test_invalid_units_and_numbers_rejected(bad):
    data=document();data['lesion_regions'][0][0][0]=bad
    with pytest.raises(AnnotationContractError):render_annotation(data,101,101)


def test_self_crossing_polygon_rejected():
    data=document();data['lesion_regions']=[[[.2,.2],[.7,.7],[.2,.7],[.7,.2]]]
    with pytest.raises(AnnotationContractError):render_annotation(data,101,101)


def test_leakage_is_not_fixed_by_expanding_skin():
    data=document();data['lesion_regions']=[square(0,1)]
    with pytest.raises(AnnotationContractError,match='超出'):render_annotation(data,101,101)


def test_no_skin_does_not_fall_back_to_whole_image():
    data=document();data['skin_regions']=[]
    with pytest.raises(AnnotationContractError):render_annotation(data,101,101)


def test_empty_lesion_is_not_no_disease_assertion():
    data=document();data['lesion_regions']=[];data['uncertain_regions']=[]
    result=render_annotation(data,101,101)
    assert result['annotation']['region_count']==0
    assert result['annotation']['review_state']=='pending'


def test_no_output_cannot_be_parsed_as_empty_disease():
    for text in ['', '{}', 'null', json.dumps({'protocol':PROTOCOL,'status':'not_assessable'})]:
        with pytest.raises(AnnotationContractError):
            data=parse_annotation(text);render_annotation(data,101,101)


def test_fenced_json_supported_without_surrounding_prose():
    assert parse_annotation('```json\n'+json.dumps(document())+'\n```')['protocol']==PROTOCOL
    with pytest.raises(AnnotationContractError):parse_annotation('Good news! '+json.dumps(document()))


def assessment_and_layers():
    layers=render_annotation(document(),101,101)
    a=SimpleNamespace(id=1,user_id=1,details=json.dumps({'annotation':layers['annotation']}),
                      ai_skin_layer=layers['skin_layer_data_url'],ai_lesion_layer=layers['lesion_layer_data_url'],visual_features_json='old')
    buf=io.BytesIO();Image.new('RGB',(101,101),(160,120,100)).save(buf,format='PNG')
    return a,layers,buf.getvalue()


def test_review_requires_explicit_acknowledgement_before_mutation():
    a,layers,raw=assessment_and_layers();old=a.details
    with pytest.raises(AnnotationContractError):apply_review(a,a.ai_skin_layer,a.ai_lesion_layer,False,raw)
    assert a.details==old


def test_review_keeps_original_evidence_and_recomputes():
    a,layers,raw=assessment_and_layers();old_mask=a.ai_lesion_layer
    measured=apply_review(a,a.ai_skin_layer,a.ai_lesion_layer,True,raw)
    details=json.loads(a.details)
    assert a.ai_lesion_layer==old_mask
    assert details['raw_annotation']['uncertain_pixels']>0
    assert details['annotation']['review_state']=='user_reviewed'
    assert details['annotation']['uncertain_layer_data_url'] is None
    assert len(details['annotation_reviews'])==1
    assert measured['clinical_vasi'] is None and a.visual_features_json is None
    assert measurement_for(a)['annotation']['review_state']=='user_reviewed'
    assert a.final_area_percentage==measured['area_percentage']


def test_review_dimension_mismatch_rejected():
    a,layers,raw=assessment_and_layers();other=render_annotation(document(),202,202)
    with pytest.raises(AnnotationContractError,match='尺寸'):apply_review(a,a.ai_skin_layer,other['lesion_layer_data_url'],True,raw)


def test_review_cannot_accept_masks_outside_skin():
    a,layers,raw=assessment_and_layers()
    from web.backend.services.annotation_contract import encode_layer
    full=encode_layer(np.ones((101,101),bool),(0,170,100))
    with pytest.raises(AnnotationContractError,match='超出'):apply_review(a,a.ai_skin_layer,full,True,raw)


def test_provider_adapters_share_geometry_not_reported_area(monkeypatch):
    import sys
    from web.backend.services import annotation_provider as provider
    result_document=document();result_document['area_percentage']=99;result_document['confidence']=1
    calls=[]
    class Client:
        def __init__(self,**kwargs):self.chat=SimpleNamespace(completions=self)
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        async def create(self,**kwargs):
            calls.append(kwargs)
            return SimpleNamespace(choices=[SimpleNamespace(finish_reason='stop',message=SimpleNamespace(content=json.dumps(result_document)))])
    monkeypatch.setitem(sys.modules,'openai',SimpleNamespace(AsyncOpenAI=Client))
    a,layers,raw=assessment_and_layers();outputs=[]
    for name in ['provider-a','provider-b']:
        monkeypatch.setattr(provider,'get_llm_config',lambda module,n=name:{'vision_model':n,'api_key':'synthetic','base_url':'https://invalid.example','provider':n})  # pragma: allowlist secret
        outputs.append(asyncio.run(provider.propose_annotation(raw,'面部')))
    assert outputs[0]['details']['lesion_layer_data_url']==outputs[1]['details']['lesion_layer_data_url']
    assert outputs[0]['area_percentage']==0 and outputs[0]['confidence'] is None
    assert all(call['messages'][0]['content'][0]['type']=='image_url' for call in calls)


def test_text_only_configuration_rejected(monkeypatch):
    import sys
    from web.backend.services import annotation_provider as provider
    monkeypatch.setitem(sys.modules,'openai',SimpleNamespace(AsyncOpenAI=object))
    monkeypatch.setattr(provider,'get_llm_config',lambda module:{'vision_model':''})
    with pytest.raises(AnnotationContractError,match='视觉模型'):
        asyncio.run(provider.propose_annotation(b'','面部'))
