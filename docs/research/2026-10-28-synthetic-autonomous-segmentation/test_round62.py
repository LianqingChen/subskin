import numpy as np
import round62

def test_warp_alpha_matches_inverse_map_translation():
    alpha=np.zeros((512,512),dtype='float32');alpha[100,120]=1
    result=round62.warp_alpha(alpha,[[1,0,5],[0,1,3]])
    assert result[97,115]==1 and result.sum()==1

def test_intervention_is_local():
    img=np.full((3,3,3),100,dtype='uint8');alpha=np.zeros((3,3),dtype='float32');alpha[1,1]=1
    out=round62.synthesize(img,alpha,.2)
    assert np.all(out[0,0]==100) and np.all(out[1,1]>100)
