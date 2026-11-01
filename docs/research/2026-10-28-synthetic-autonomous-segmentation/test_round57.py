import importlib.util
from pathlib import Path
import sys
import numpy as np
sys.path.insert(0,str(Path(__file__).parent))
s=importlib.util.spec_from_file_location('r57',Path(__file__).with_name('round57.py'));r=importlib.util.module_from_spec(s);s.loader.exec_module(r)

def test_dual_control_detects_changed_area_without_false_control():
    a=np.full((4,8,3),100,np.uint8);b=a.copy();edit=a.copy();edit[1:3,5:7]=180;core=np.ones((4,8),bool)
    stats,pred,control=r.dual_measure(a,b,edit,core)
    assert pred[1:3,5:7].all() and pred.sum()==4 and not control.any() and stats['control_right_false_positive_pct']==0

def test_gate_rejects_any_case_and_ties_prefer_single():
    row={'success':True,'control_right_fp_pct':0,'metrics':{'precision':1,'big_recall':1,'small_recall':1}}
    cases=[dict(row,method=m) for m in ('single','dual') for _ in range(24)]
    assert r.choose(cases)=='single'
    assert r.choose([dict(row,method='single')]*23) is None
