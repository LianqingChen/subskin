import numpy as np
import round75_shapes as s

def test_small_shapes_separated_and_inside_core():
    core=np.zeros((256,256),bool);core[60:150,20:230]=True
    (big,small),meta=s.shape_fields(core,np.random.default_rng(7505));assert np.square(np.array(meta['big_yx'])-meta['small_yx']).sum()>=2500;assert not np.any((np.maximum(big,small)>.2)&~core)
    assert np.any(big>=.8) and np.any(small>=.8)

def test_empty_region_refused():
    try:s.shape_fields(np.zeros((128,128),bool),np.random.default_rng(7505))
    except ValueError:return
    assert False
