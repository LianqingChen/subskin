import importlib.util
from pathlib import Path
import numpy as np
import pytest
spec=importlib.util.spec_from_file_location('r34',Path(__file__).with_name('round34_weaken.py'));r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)

def test_weaken_endpoints_and_unmodified_pixels():
    a=np.array([[[20,40,80],[130,130,130]]],np.uint8);b=np.array([[[100,120,160],[130,130,130]]],np.uint8)
    assert np.array_equal(r.weaken(b,a,1),b)
    assert np.array_equal(r.weaken(b,a,.25),np.array([[[40,60,100],[130,130,130]]],np.uint8))
    with pytest.raises(ValueError):r.weaken(b,a,0)
