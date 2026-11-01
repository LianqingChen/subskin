import importlib.util
from pathlib import Path
import numpy as np
import pytest
s=importlib.util.spec_from_file_location('r54',Path(__file__).with_name('round54_prepare.py'));r=importlib.util.module_from_spec(s);s.loader.exec_module(r)

def test_guarded_matching_and_no_new_saturation():
    neg=np.full((16,16,3),[70,90,110],dtype=np.uint8);pos=neg.copy();pos[4:12,4:12]=[100,120,140];mask=np.ones((16,16),np.uint8);mask[4:12,4:12]=2
    out,m=r.match_delta_e(pos,neg,mask);assert m['matched'] and m['absolute_error']<=.5 and m['new_saturated_core_pct']<=1
    assert np.array_equal(out[mask!=2],neg[mask!=2])

def test_empty_core_is_rejected():
    x=np.zeros((4,4,3),np.uint8)
    with pytest.raises(ValueError):r.match_delta_e(x,x,np.ones((4,4),np.uint8))
