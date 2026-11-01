import importlib.util
from pathlib import Path
import sys
import numpy as np
sys.path.insert(0,str(Path(__file__).parent))
s=importlib.util.spec_from_file_location('r58',Path(__file__).with_name('round58.py'));r=importlib.util.module_from_spec(s);s.loader.exec_module(r)

def test_partition_confident_unknown_are_disjoint():
    neg=np.zeros((4,8),np.float32);pos=neg.copy();pos[1,5]=4;pos[2,6]=2.5;core=np.ones((4,8),bool)
    strong,unknown,info=r.partition(neg,pos,core)
    assert strong[1,5] and unknown[2,6] and not (strong&unknown).any() and info['control_confirmed_pct']==0

def test_coverage_cannot_hide_missing_confirmed_or_excess_unknown():
    big=np.array([[1,0,0]],bool);small=np.array([[0,1,0]],bool);valid=np.ones((1,3),bool);strong=np.array([[1,0,0]],bool);unknown=np.array([[0,1,0]],bool);m=r.metrics(strong,unknown,big,small,valid,valid)
    assert m['confirmed_small_recall']==0 and m['covered_small_recall']==1 and m['unknown_skin_pct']>10
    row={'method':'single','success':True,'thresholds':{'control_confirmed_pct':0,'control_union_pct':0},'metrics':m}
    assert r.choose([row]*24) is None
