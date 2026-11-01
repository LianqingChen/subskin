import importlib.util
from pathlib import Path
import numpy as np
import pytest
s=importlib.util.spec_from_file_location('r55',Path(__file__).with_name('round55_prepare.py'));r=importlib.util.module_from_spec(s);s.loader.exec_module(r)

def test_safe_selection_preserves_outside_and_constraints_when_matched():
    neg=np.full((16,16,3),[70,90,110],dtype=np.uint8);pos=neg.copy();pos[4:12,4:12]=[100,120,140];mask=np.ones((16,16),np.uint8);mask[4:12,4:12]=2
    out,m=r.select_image(pos,neg,mask);assert np.array_equal(out[mask!=2],neg[mask!=2])
    if m['matched']:assert m['absolute_error']<=.5 and m['fallback_core_pct']<=20 and m['new_saturated_core_pct']<=1 and m['distinct_core_pct']>=10
    else:assert np.array_equal(out,pos)

def test_empty_core_rejected():
    x=np.zeros((4,4,3),np.uint8)
    with pytest.raises(ValueError):r.select_image(x,x,np.ones((4,4),np.uint8))
