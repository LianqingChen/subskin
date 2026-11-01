import importlib.util
from pathlib import Path
import numpy as np
import pytest
s=importlib.util.spec_from_file_location('r41',Path(__file__).with_name('round41_prepare.py'));r=importlib.util.module_from_spec(s);s.loader.exec_module(r)

def test_interpolation_endpoints_and_nonchanged_region():
    a=np.array([[[20,40,80],[30,30,30]]],np.uint8);b=np.array([[[100,120,160],[30,30,30]]],np.uint8)
    assert np.array_equal(r.weaken(b,a,1),b)
    assert np.array_equal(r.weaken(b,a,.25),np.array([[[40,60,100],[30,30,30]]],np.uint8))
    with pytest.raises(ValueError):r.weaken(b,a,0)
