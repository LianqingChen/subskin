import numpy as np
import round78

def test_one_pixel_reference_rejected():
    core=np.ones((32,32),bool);big=np.zeros((32,32),np.float32);big[2:6,2:6]=1;small=np.zeros_like(big);small[20,20]=1
    assert not round78.reference_valid(big,small,core)

def test_minimum_valid_and_edge_rejection():
    core=np.ones((32,32),bool);big=np.zeros((32,32),np.float32);big[2:6,2:6]=1;small=np.zeros_like(big);small[20:24,20:24]=1
    assert round78.reference_valid(big,small,core)
    core[20,20]=False;assert not round78.reference_valid(big,small,core)
