import importlib.util
from pathlib import Path
import numpy as np
import pytest
spec=importlib.util.spec_from_file_location('r31',Path(__file__).with_name('round31_prepare.py'));r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)

def test_pair_illumination_is_deterministic_and_preserves_shared_pixels():
    a=np.full((40,40,3),80,dtype=np.uint8);b=a.copy();b[15:20,15:20]=110
    ma=np.ones((40,40),dtype=np.uint8);mb=ma.copy();mb[15:20,15:20]=2
    output,meta=r.apply_illumination([a,b],[ma,mb],123);again,meta2=r.apply_illumination([a,b],[ma,mb],123)
    assert meta==meta2 and all(np.array_equal(x,y) for x,y in zip(output,again))
    same=(a==b).all(axis=2);assert np.array_equal(output[0][same],output[1][same]);assert np.any(output[0]>a)
    y,x=meta['center'];assert ma[y,x]==mb[y,x]==1

def test_no_shared_normal_skin_is_rejected():
    image=np.zeros((4,4,3),dtype=np.uint8);mask=np.full((4,4),255,dtype=np.uint8)
    with pytest.raises(ValueError):r.apply_illumination([image,image],[mask,mask],1)
