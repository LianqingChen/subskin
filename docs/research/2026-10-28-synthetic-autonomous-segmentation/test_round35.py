import importlib.util
from pathlib import Path
import numpy as np
spec=importlib.util.spec_from_file_location('r35',Path(__file__).with_name('round35_prepare.py'));r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)

def test_ignore_only_weak_lesion_and_preserve_other_classes():
    a=np.full((1,4,3),100,np.uint8);b=a.copy();a[0,1]=180
    mask=np.array([[2,2,1,255]],np.uint8);out=r.ignore_low_signal(a,b,mask)
    assert out.tolist()==[[255,2,1,255]] and mask.tolist()==[[2,2,1,255]]

def test_threshold_zero_leaves_all_unchanged():
    rgb=np.full((2,2,3),100,np.uint8);mask=np.array([[2,1],[3,255]],np.uint8)
    assert np.array_equal(r.ignore_low_signal(rgb,rgb,mask,0),mask)
