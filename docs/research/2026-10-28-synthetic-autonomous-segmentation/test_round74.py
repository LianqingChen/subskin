import numpy as np
from PIL import Image
import round74_prepare as r

def test_core_and_cyan_corners(tmp_path):
    a=np.empty((160,240,3),np.uint8);a[:]=[80,220,240];a[25:135,40:200]=[190,110,80];p=tmp_path/'a.png';Image.fromarray(a).save(p)
    _,core,meta=r.core_from_image(p);assert .1<meta['core_fraction']<.9 and core[256,256] and not core[0,0]

def test_noncyan_corners_rejected(tmp_path):
    p=tmp_path/'bad.png';Image.fromarray(np.zeros((100,200,3),np.uint8)).save(p)
    try:r.core_from_image(p)
    except ValueError:return
    assert False
