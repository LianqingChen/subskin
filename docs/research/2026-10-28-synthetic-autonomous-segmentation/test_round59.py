import importlib.util
from pathlib import Path
import sys
import numpy as np
sys.path.insert(0,str(Path(__file__).parent));s=importlib.util.spec_from_file_location('r59',Path(__file__).with_name('round59.py'));r=importlib.util.module_from_spec(s);s.loader.exec_module(r)

def test_guard_moves_confirmation_to_unknown_without_changing_union():
    core=np.ones((40,80),bool);cal=np.full((40,80),4,np.float32);obs=np.full((40,80),6,np.float32)
    a,b,_=r.labels(cal,obs,core,False);c,d,_=r.labels(cal,obs,core,True)
    assert a.all() and not c.any() and d.all() and np.array_equal(a|b,c|d)

def test_independent_control_detects_false_positive():
    core=np.ones((4,8),bool);cal=np.zeros((4,8),np.float32);negative=np.zeros_like(cal);negative[1,6]=4
    c,u,_=r.labels(cal,negative,core,False);stats=r.control_stats(c,u,core)
    assert stats['control_confirmed_pct']>0 and stats['control_union_pct']>0
