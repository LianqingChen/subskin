import importlib.util
from pathlib import Path
import numpy as np
s=importlib.util.spec_from_file_location('r44',Path(__file__).with_name('round44.py'));r=importlib.util.module_from_spec(s);s.loader.exec_module(r)

def test_half_matches_argmax_and_non_skin_never_changes():
    p=np.array([[[.05,.05,.8,.01]],[[.6,.2,.05,.01]],[[.3,.7,.05,.01]],[[.04,.04,.05,.96]],[[.01,.01,.05,.01]]])
    assert np.array_equal(r.conditional_decode(p,.5),p.argmax(0))
    assert r.conditional_decode(p,.2).tolist()==[[2,2,0,3]]
    assert r.conditional_decode(p,.9).tolist()==[[1,1,0,3]]

def test_select_prefers_dice_then_higher_threshold():
    rows=[{'threshold':.3,'mean_positive_dice':.4,'passed':True},{'threshold':.7,'mean_positive_dice':.4,'passed':True},{'threshold':.9,'mean_positive_dice':.9,'passed':False}]
    assert r.select(rows)==.7 and r.select([rows[-1]]) is None
