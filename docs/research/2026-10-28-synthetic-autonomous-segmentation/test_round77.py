import numpy as np
import round77

def test_boundary_f1_identical_and_empty():
    core=np.ones((32,32),bool);mask=np.zeros((32,32),bool);mask[8:24,8:24]=True
    assert round77.boundary_f1(mask,mask,core)==1
    assert round77.boundary_f1(np.zeros_like(mask),mask,core)==0

def test_boundary_f1_far_apart():
    core=np.ones((64,64),bool);a=np.zeros_like(core);b=np.zeros_like(core);a[3:10,3:10]=1;b[45:52,45:52]=1
    assert round77.boundary_f1(a,b,core)==0
