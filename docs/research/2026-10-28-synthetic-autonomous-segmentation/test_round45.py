import importlib.util
from pathlib import Path
import numpy as np
s=importlib.util.spec_from_file_location('r45',Path(__file__).with_name('round45.py'));r=importlib.util.module_from_spec(s);s.loader.exec_module(r)

def test_intersection_requires_both_skin_and_thresholds():
    prior=np.array([[[.05,.05,.8,.05]],[[.2,.2,.05,.7]],[[.7,.7,.05,.2]],[[.04,.04,.05,.04]],[[.01,.01,.05,.01]]])
    hard=np.array([[[.05,.8,.05,.05]],[[.2,.05,.2,.2]],[[.7,.05,.7,.7]],[[.04,.05,.04,.04]],[[.01,.05,.01,.01]]])
    assert r.joint_decode(prior,hard,.2,.5).tolist()==[[2,1,0,2]]
    assert r.joint_decode(prior,hard,.9,.9).tolist()==[[1,1,0,1]]

def test_select_uses_all_tie_breakers_and_rejects_failures():
    rows=[{'prior_threshold':.3,'hard_threshold':.3,'mean_positive_dice':.5,'passed':True},{'prior_threshold':.1,'hard_threshold':.7,'mean_positive_dice':.5,'passed':True},{'prior_threshold':.9,'hard_threshold':.9,'mean_positive_dice':.9,'passed':False}]
    assert r.choose(rows)==rows[1] and r.choose(rows[-1:]) is None
