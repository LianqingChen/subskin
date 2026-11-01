import importlib.util
from pathlib import Path
import numpy as np
spec=importlib.util.spec_from_file_location('r28',Path(__file__).with_name('round28.py'));r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)

def test_filter_preserves_nonlesion_and_threshold_equality():
    p=np.array([[[.1,.1,.7]],[[.2,.3,.1]],[[.7,.6,.1]],[[0,0,.1]],[[0,0,0]]])
    assert r.filter_lesion(p,.7).tolist()==[[2,1,0]]

def test_select_requires_all_validation_and_breaks_ties_upward():
    base={'total':32,'failures':0,'positives':25,'negatives':7,'false_positives':2,'recall':.3,'dice':.4}
    a=dict(base,threshold=.4);b=dict(base,threshold=.5);c=dict(base,threshold=.9,failures=1,dice=.9)
    assert r.choose([a,b,c])==.5
    assert r.choose([dict(a,false_positives=3),dict(b,recall=.29)]) is None
