import importlib.util
from pathlib import Path
import torch
from torch.nn import functional as F
s=importlib.util.spec_from_file_location('r38',Path(__file__).with_name('round38_train.py'));r=importlib.util.module_from_spec(s);s.loader.exec_module(r)

def test_weighted_loss_changes_gradient_only_on_valid_examples():
    x=torch.zeros(1,5,1,3,requires_grad=True);y=torch.tensor([[[2,1,255]]]);orig=lambda a,b:F.cross_entropy(a,b,ignore_index=255)+a[:,:,:,:2].square().mean()
    value=r.weighted_training_loss(x,y,orig);g=torch.autograd.grad(value,x)[0]
    assert g[0,2,0,0].abs()>g[0,1,0,1].abs()
    assert torch.count_nonzero(g[:,:,:,2])==0
