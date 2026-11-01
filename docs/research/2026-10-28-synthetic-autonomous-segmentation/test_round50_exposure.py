import importlib.util
from pathlib import Path
import numpy as np
s=importlib.util.spec_from_file_location('r50e',Path(__file__).with_name('round50_exposure_eval.py'));r=importlib.util.module_from_spec(s);s.loader.exec_module(r)

def test_common_reference_excludes_saturation_equally_and_preserves_other_labels():
    rgb=np.full((10,10,3),100,np.uint8);rgb[1,1]=250;truth=np.ones((10,10),np.uint8);truth[2,2]=2
    mask,n,ok=r.common_reference(rgb,truth)
    assert ok and n==1 and mask[1,1]==255 and mask[2,2]==2 and truth[1,1]==1
    assert r.scale_srgb(rgb,.8)[1,1,0]==200 and r.scale_srgb(rgb,1.2)[1,1,0]==255

def test_positive_with_only_clipped_lesion_is_unassessable():
    rgb=np.full((10,10,3),100,np.uint8);rgb[1,1]=250;truth=np.ones((10,10),np.uint8);truth[1,1]=2
    _,_,ok=r.common_reference(rgb,truth);assert not ok
