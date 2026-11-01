import numpy as np
import round70

def test_exposure_clamps_and_preserves_shape():
    x=np.array([[[100,200,250]]],dtype=np.uint8)
    assert round70.expose(x,1.2).tolist()==[[[120,240,255]]]

def test_signal_loss_is_reported():
    x=np.zeros((2,2,3),np.uint8);core=np.ones((2,2),bool);big=np.zeros((2,2),np.float32);big[0,0]=1;small=np.zeros_like(big);small[1,1]=1
    result=round70.imaging_stats(x,x,core,big,small)
    assert result['core_no_rgb_change_pct']==100 and result['skin_channel_saturation_pct']==0
