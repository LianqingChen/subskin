"""Synthetic controls only: no patient data, DB, model APIs or network."""
import ast
import base64
import io
from pathlib import Path
from typing import *

import cv2
import numpy as np
import pytest
from PIL import Image
from web.backend.services.assessment_measurement import decode_mask, measure_layers, comparison_fingerprint
from web.backend.services.assessment_comparison import measure_common_roi, measure_registered, compare_registered_masks
from web.backend.services.vasi_formula import compute_vasi_v2, compute_two_layer_area
from web.backend.services.report_measurements import safe_report_metrics


def overlay(mask, color=(244, 114, 182)):
    rgba = np.zeros((*mask.shape, 4), np.uint8)
    rgba[mask, :3] = color
    rgba[mask, 3] = 180
    out = io.BytesIO(); Image.fromarray(rgba).save(out, format='PNG')
    return 'data:image/png;base64,' + base64.b64encode(out.getvalue()).decode()


def photo(mask, shape=(200, 200)):
    skin = np.ones(shape, dtype=bool)
    rgb = np.full((*shape, 3), (180, 140, 120), np.uint8)
    rgb[mask] = (225, 215, 210)
    return rgb, skin, mask


def extract_function(path, names, namespace):
    tree = ast.parse(Path(path).read_text())
    functions = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    exec(compile(ast.Module(body=functions, type_ignores=[]), path, 'exec'), namespace)
    return namespace


def test_mask_uses_alpha_not_color():
    mask = np.zeros((20, 20), bool); mask[4:15, 5:16] = True
    assert np.array_equal(decode_mask(overlay(mask, (0, 0, 0))), mask)


def test_large_lesion_measures_without_size_rejection():
    skin = np.ones((100, 100), bool); mask = np.zeros_like(skin); mask[5:95, 5:95] = True
    m = measure_layers(overlay(skin), overlay(mask))
    assert m['status'] == 'measured'
    assert m['area_percentage'] == 81
    assert m['clinical_vasi'] is None


def test_partial_lesion_is_explicit():
    skin = np.ones((100, 100), bool); mask = np.zeros_like(skin); mask[:30, :30] = True
    assert measure_layers(overlay(skin), overlay(mask))['status'] == 'partial'


def test_lesion_cannot_expand_denominator():
    skin = np.zeros((100, 100), bool); skin[20:80,20:80] = True
    lesion = np.ones_like(skin)
    assert measure_layers(overlay(skin), overlay(lesion))['status'] == 'unavailable'


def test_standard_hand_units_and_side_aliases():
    assert compute_vasi_v2('left_hand', 100, 1) == 1
    assert compute_vasi_v2('左脚', 100, 1) == compute_vasi_v2('left_foot', 100, 1)
    assert compute_vasi_v2('left_hand', 100, 0) == 0
    with pytest.raises(ValueError): compute_vasi_v2('unknown', 25, 1)
    with pytest.raises(ValueError): compute_vasi_v2('face', float('nan'), 1)


def test_no_model_evidence_cannot_become_stable():
    ns = dict(globals())
    fn = extract_function('web/backend/services/spot_compare.py', {'_merge_results'}, ns)['_merge_results']
    result = fn({'trend':'improving','size_change_percent':-80}, None, (1,'good'), (1,'good'))
    assert result['trend_en'] == 'unknown'
    assert result['size_change_percent'] is None
    assert result['comparison_status'] == 'not_comparable'


def test_shared_roi_rejects_missing_lesion():
    mask = np.zeros((200,200), bool); mask[50:100,50:100] = True
    a = photo(mask)
    b = photo(mask.copy()); b[1][:,:75] = False
    m = measure_common_roi(a,b,np.array([[1,0,0],[0,1,0]],float),0)
    assert m['status'] == 'not_comparable'


def test_same_photo_no_definite_change_and_larger_lesion_detected():
    ma = np.zeros((200,200),bool); ma[60:120,60:120] = True
    mb = ma.copy(); mb[50:130,50:130] = True
    identity=np.array([[1,0,0],[0,1,0]],float)
    same=measure_common_roi(photo(ma), photo(ma),identity,0)
    assert same['size_change_percent'] == 0
    assert same['area_direction'] == 'uncertain'
    changed=measure_common_roi(photo(ma),photo(mb),identity,0)
    assert changed['area_direction'] == 'increasing'
    assert changed['size_change_percent'] > 70
    assert changed['expanded_pixels'] > 0


def test_zero_baseline_never_divides():
    a=np.zeros((200,200),bool);b=a.copy();b[70:100,70:100]=True
    m=measure_common_roi(photo(a),photo(b),np.array([[1,0,0],[0,1,0]],float),0)
    assert m['size_change_percent'] is None
    assert m['area_direction']=='unknown'


def test_no_feature_alignment_refuses_measurement():
    a=np.zeros((200,200),bool);a[60:120,60:120]=True
    assert measure_registered(photo(a),photo(a))['status']=='not_comparable'


def test_context_and_revision_gates():
    assert compare_registered_masks(b'',b'',{}, {})['status']=='not_comparable'
    a={'ref':'va:1','user_lesion_layer':'before'};b={'ref':'va:2'}
    old=comparison_fingerprint(a,b); a['user_lesion_layer']='after'
    assert comparison_fingerprint(a,b)!=old


def test_legacy_reports_preserved_but_not_treated_as_new_measurements():
    original={'trend':'稳定','has_vasi':True,'vasi_change':-10,'pair_metrics':{'size_change_percent':-90}}
    safe=safe_report_metrics(original)
    assert safe['comparison_status']=='legacy'
    assert safe['pair_metrics']['size_change_percent'] is None
    assert original['vasi_change']==-10


def test_all_pending_periodic_report_has_no_stable_fallback():
    from datetime import date
    ns = dict(globals(), date=date)
    fn = extract_function('web/backend/services/skin_report.py', {'_compute_periodic_metrics'}, ns)['_compute_periodic_metrics']
    result=fn([{'trend':'无法可靠比较','pair_metrics':{},'body_site_label':'test','vasi_points':[]}],date(2026,1,1),date(2026,1,3))
    assert result['trend']!='稳定'
    assert result['comparison_status']=='not_comparable'


def test_reference_scale_requires_explicit_planar_confirmation():
    skin=np.ones((100,100),bool);lesion=np.zeros_like(skin);lesion[25:75,25:75]=True
    calibration={'points':[[0.1,0.1],[0.6,0.1]],'length_mm':10,'same_plane':True}
    measured=measure_layers(overlay(skin),overlay(lesion),calibration=calibration)
    assert measured['area_cm2']==1.0
    calibration['same_plane']=False
    assert measure_layers(overlay(skin),overlay(lesion),calibration=calibration)['area_cm2'] is None


def test_benchmark_perfect_mask_and_patient_leakage(tmp_path):
    import importlib.util
    import json
    spec=importlib.util.spec_from_file_location('assessment_benchmark','scripts/assessment_benchmark.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    image=np.zeros((100,100),np.uint8);image[20:80,20:80]=255
    Image.fromarray(image).save(tmp_path/'mask.png')
    samples=[{'patient_id':'synthetic-group','split':'test','ground_truth':'mask.png','prediction':'mask.png','consent':True,'label_source':'clinician'}]
    manifest=tmp_path/'dataset.json';output=tmp_path/'metrics.json'
    manifest.write_text(json.dumps({'samples':samples,'model_version':'synthetic-test'}))
    module.run(manifest,output)
    assert json.loads(output.read_text())['overall']['dice']==1
    samples.append({**samples[0],'split':'train'})
    manifest.write_text(json.dumps({'samples':samples}))
    with pytest.raises(ValueError,match='leakage'):module.run(manifest,output)


def test_registration_removes_camera_translation_without_false_change():
    rng=np.random.default_rng(7)
    rgb=rng.integers(90,190,(500,500,3),dtype=np.uint8)
    skin=np.ones((500,500),bool)
    lesion=np.zeros_like(skin);lesion[190:300,200:310]=True;rgb[lesion]=(230,225,220)
    movement=np.array([[1,0,12],[0,1,8]],float)
    rgb_b=cv2.warpAffine(rgb,movement,(500,500))
    skin_b=cv2.warpAffine(skin.astype(np.uint8),movement,(500,500)).astype(bool)
    lesion_b=cv2.warpAffine(lesion.astype(np.uint8),movement,(500,500)).astype(bool)
    measured=measure_registered((rgb,skin,lesion),(rgb_b,skin_b,lesion_b))
    assert measured['status']=='measured',measured
    assert abs(measured['size_change_percent']) < 1
    assert measured['area_direction']=='uncertain'
