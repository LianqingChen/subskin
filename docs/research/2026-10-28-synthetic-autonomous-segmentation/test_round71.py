import numpy as np
import round71_shapes as s

def test_narrow_region_places_and_preserves_boundary():
    core=np.zeros((256,256),bool);core[60:165,30:220]=True
    (big,small),meta=s.shape_fields(core,np.random.default_rng(7005))
    assert np.square(np.array(meta['big_yx'])-meta['small_yx']).sum()>=3600
    assert not np.any((np.maximum(big,small)>.2)&~core)

def test_impossible_area_rejected():
    core=np.zeros((128,128),bool);core[30:75,30:75]=True
    try:s.shape_fields(core,np.random.default_rng(7005))
    except ValueError:return
    assert False
