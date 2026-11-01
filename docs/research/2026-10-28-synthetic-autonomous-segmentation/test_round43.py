import importlib.util
from pathlib import Path
import pytest
import torch
s=importlib.util.spec_from_file_location('r43',Path(__file__).with_name('round43_train.py'));r=importlib.util.module_from_spec(s);s.loader.exec_module(r)

def test_loss_gradients_only_hardest_valid_negative_pixel():
    x=torch.zeros(2,5,1,4,requires_grad=True)
    with torch.no_grad():x[1,2,0,1]=3;x[1,2,0,3]=9
    y=torch.tensor([[[2,2,1,255]],[[1,1,1,255]]])
    value=r.hard_negative_loss(x,y);g=torch.autograd.grad(value,x)[0]
    assert value>0 and torch.count_nonzero(g[0])==0 and g[1,2,0,1]>0
    assert torch.count_nonzero(g[1,:,:,0])==0 and torch.count_nonzero(g[1,:,:,2:])==0

def test_rejects_negative_with_lesion_or_no_valid_pixels():
    x=torch.zeros(2,5,1,2);y=torch.tensor([[[1,1]],[[2,1]]])
    with pytest.raises(ValueError):r.hard_negative_loss(x,y)
    y[1]=255
    with pytest.raises(ValueError):r.hard_negative_loss(x,y)
