import numpy as np
import round69_prepare as p

def test_pair_no_change_outside_and_unknown_edges():
    rgb=np.full((5,5,3),100,np.uint8);core=np.ones((5,5),bool);big=np.zeros((5,5),np.float32);small=np.zeros_like(big);big[1,1]=1;big[1,2]=.5;small[3,3]=1
    edited,pos,neg=p.build_pair(rgb,core,big,small,.2)
    assert np.array_equal(edited[big+small==0],rgb[big+small==0])
    assert pos[1,1]==2 and pos[1,2]==255 and pos[3,3]==2 and np.all(neg==1)

def test_positions_keep_shape_inside():
    core=np.ones((512,512),bool);(big,small),meta=p.shape_fields(core,np.random.default_rng(6905))
    assert np.any(big>=.8) and np.any(small>=.8) and np.square(np.array(meta['big_yx'])-meta['small_yx']).sum()>=3600
