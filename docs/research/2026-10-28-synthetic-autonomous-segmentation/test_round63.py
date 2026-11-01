import numpy as np
import round63

def test_difference_preserves_float_mean():
    a=np.array([2],dtype='float32');b=np.array([3],dtype='float32');observed=np.array([5],dtype='float32')
    assert round63.difference(a,b,observed,'single')[0]==3
    assert round63.difference(a,b,observed,'mean')[0]==2.5

def test_reference_moves_with_matrix():
    core=np.ones((512,512),bool);identity=[[1,0,0],[0,1,0]];translation=[[1,0,5],[0,1,3]]
    b,s,_=round63.reference(core,'original',identity);b2,s2,_=round63.reference(core,'original',translation)
    assert np.array_equal(b[3:,5:],b2[:-3,:-5])
    assert np.array_equal(s[3:,5:],s2[:-3,:-5])
