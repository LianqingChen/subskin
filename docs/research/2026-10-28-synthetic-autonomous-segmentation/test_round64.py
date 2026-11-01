import numpy as np
import round64

def test_smoothing_spreads_signal_without_changing_uniform_field():
    a=np.zeros((40,40),dtype='float32');b=a.copy();o=a.copy();o[20,20]=10
    d=round64.difference(a,b,o,'smooth')
    assert 0<d[20,20]<10 and d[20,21]>0 and np.isclose(d.sum(),10,atol=.001)
    assert np.allclose(round64.difference(a,b,np.ones_like(a)*4,'smooth'),4)
