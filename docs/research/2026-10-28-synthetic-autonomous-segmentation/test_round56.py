import importlib.util
from pathlib import Path
import sys
import numpy as np
sys.path.insert(0,str(Path(__file__).parent))
s=importlib.util.spec_from_file_location('r56',Path(__file__).with_name('round56.py'));r=importlib.util.module_from_spec(s);s.loader.exec_module(r)

def test_score_preserves_small_miss_and_precision():
    big=np.array([[1,0,0]],bool);small=np.array([[0,1,0]],bool);pred=np.array([[1,0,1]],bool);v=np.ones((1,3),bool);m=r.score(pred,big,small,v)
    assert m['big_recall']==1 and m['small_recall']==0 and m['precision']==.5

def test_selection_requires_all_cases_and_thresholds():
    one={'method':'raw','success':True,'control_right_fp_pct':0,'metrics':{'precision':1,'big_recall':1,'small_recall':1}}
    assert r.choose([one]*23) is None and r.choose([one]*24)=='raw'
    bad=dict(one,metrics={'precision':1,'big_recall':1,'small_recall':0})
    assert r.choose([one]*23+[bad]) is None


def test_equal_worst_recall_uses_predeclared_ecc_priority():
    common={"success":True,"control_right_fp_pct":0,"metrics":{"precision":1,"big_recall":1,"small_recall":1}}
    rows=[dict(common,method=m) for m in ("raw","ecc","dense") for _ in range(24)]
    assert r.choose(rows)=="ecc"
