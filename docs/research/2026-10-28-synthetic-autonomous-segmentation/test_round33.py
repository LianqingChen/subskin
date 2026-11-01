import importlib.util
from pathlib import Path
import numpy as np
import pytest
s=importlib.util.spec_from_file_location('r33',Path(__file__).with_name('round33_prepare.py'));r=importlib.util.module_from_spec(s);s.loader.exec_module(r)

def test_interpolation_has_exact_endpoints_and_valid_midpoint():
    clean=np.zeros((2,2,3),np.float32);positive=np.ones_like(clean)
    assert np.array_equal(r.interpolate(clean,positive,0),clean)
    assert np.array_equal(r.interpolate(clean,positive,1),positive)
    assert np.allclose(r.interpolate(clean,positive,.25),.25)
    with pytest.raises(ValueError):r.interpolate(clean,positive,1.1)

def test_delta_e_zero_for_identical_images_and_rejects_empty_core():
    rgb=np.full((4,4,3),128,np.uint8);m=np.full((4,4),2,np.uint8)
    assert r.delta_e(rgb,rgb,m)==0
    with pytest.raises(ValueError):r.delta_e(rgb,rgb,np.zeros((4,4),np.uint8))
