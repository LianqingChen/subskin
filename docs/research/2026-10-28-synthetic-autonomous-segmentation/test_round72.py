import numpy as np
import round72

def test_threshold_never_adds_and_uses_next_best():
    p=np.array([[[.1,.4]],[[.3,.1]],[[.4,.2]],[[.1,.2]],[[.1,.1]]],dtype='float32')
    assert round72.classify(p,0).tolist()==[[2,0]]
    assert round72.classify(p,.5).tolist()==[[1,0]]

def test_threshold_equality_is_retained():
    p=np.array([[[.1]],[[.2]],[[.5]],[[.1]],[[.1]]],dtype='float32')
    assert round72.classify(p,.5).item()==2
