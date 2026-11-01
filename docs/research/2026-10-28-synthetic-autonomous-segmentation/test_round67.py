import numpy as np
import torch
import round67

class Constant(torch.nn.Module):
    def forward(self,x):
        z=torch.zeros((x.shape[0],5,x.shape[2],x.shape[3]));z[:,2]=2;return z

def test_tiles_cover_and_constant_result():
    torch.set_num_threads(2);r=round67.tiled_predict(Constant(),np.zeros((512,512,3),np.uint8))
    assert r.shape==(512,512) and np.all(r==2)

def test_reject_wrong_size():
    try:round67.tiled_predict(Constant(),np.zeros((128,128,3),np.uint8))
    except ValueError:return
    assert False
