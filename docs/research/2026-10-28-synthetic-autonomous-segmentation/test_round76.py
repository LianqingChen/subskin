import numpy as np
from PIL import Image
import round76_prepare as r

def test_template_is_extracted_and_placed(tmp_path):
    a=np.zeros((100,100),np.uint8);a[20:80,30:70]=255;p=tmp_path/'x.png';Image.fromarray(a).save(p);mask,meta=r.template_mask(p);assert .05<meta['component_fraction']<.6
    placed=r.at_location(mask,[50,50],10,1.2,(100,100));assert placed[50,50]>.8 and placed[0,0]==0

def test_template_touching_boundary_rejected(tmp_path):
    a=np.zeros((100,100),np.uint8);a[:60,30:70]=255;p=tmp_path/'x.png';Image.fromarray(a).save(p)
    try:r.template_mask(p)
    except ValueError:return
    assert False
