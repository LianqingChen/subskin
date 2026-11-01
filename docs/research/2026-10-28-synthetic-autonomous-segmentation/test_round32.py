import importlib.util
from pathlib import Path
import torch
spec=importlib.util.spec_from_file_location('r32',Path(__file__).with_name('round32.py'));r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)

def test_ranking_applies_only_to_matched_lesion_and_drives_correct_sign():
    x=torch.zeros(2,5,1,4,requires_grad=True);y=torch.tensor([[[2,2,255,1]],[[1,255,1,1]]])
    value=r.ranking(x,y);g=torch.autograd.grad(value,x)[0]
    assert g[0,2,0,0]<0 and g[1,2,0,0]>0
    assert torch.count_nonzero(g[:,:,:,1:])==0

def test_ranking_decreases_with_positive_contrast_and_empty_is_safe():
    y=torch.tensor([[[2]],[[1]]]);x=torch.zeros(2,5,1,1,requires_grad=True);a=r.ranking(x,y)
    z=x.detach().clone();z[0,2]=2;assert r.ranking(z,y)<a
    y[:]=255;b=r.ranking(x,y);b.backward();assert b.item()==0 and torch.isfinite(x.grad).all()
