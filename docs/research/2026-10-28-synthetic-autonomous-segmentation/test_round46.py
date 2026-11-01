import importlib.util
from pathlib import Path
import numpy as np
s=importlib.util.spec_from_file_location('r46',Path(__file__).with_name('round46.py'));r=importlib.util.module_from_spec(s);s.loader.exec_module(r)

def test_component_filter_preserves_8_connected_and_other_classes():
    a=np.zeros((6,6),np.uint8);a[0,0]=2;a[1,1]=2;a[4,4]=2;a[5,0]=3
    b=r.filter_components(a,2)
    assert b[0,0]==b[1,1]==2 and b[4,4]==1 and b[5,0]==3
    assert np.array_equal(r.filter_components(a,1),a)

def test_choice_prefers_dice_then_smaller_components():
    x=[{'min_area':4,'mean_positive_dice':.5,'passed':True},{'min_area':16,'mean_positive_dice':.5,'passed':True},{'min_area':256,'mean_positive_dice':.9,'passed':False}]
    assert r.choose(x)==4 and r.choose(x[-1:]) is None
