import numpy as np
import round65

def test_full_region_counts_edge_and_false_positive():
    a=np.array([[1,.5,.49,0]],dtype='float32');core=np.ones((1,4),bool);p=np.array([[1,1,1,0]],bool)
    m=round65.full_metrics(p,a,core)
    assert m['reference_area_pixels']==2 and m['confirmed_area_pixels']==3 and m['dice']==.8 and m['relative_area_error']==.5

def test_zero_reference_rejected():
    try:round65.full_metrics(np.zeros((1,2),bool),np.zeros((1,2)),np.ones((1,2),bool))
    except ValueError:return
    assert False
