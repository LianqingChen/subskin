import importlib.util
from pathlib import Path
import torch
from torch.nn import functional as F

spec = importlib.util.spec_from_file_location('round27', Path(__file__).with_name('round27.py'))
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)

def test_weight_one_preserves_original_loss_and_gradients():
    torch.manual_seed(4)
    x=torch.randn(1,5,2,3,requires_grad=True)
    target=torch.tensor([[[1,2,255],[0,2,1]]])
    base=lambda a,b:F.cross_entropy(a,b,ignore_index=255) + a.square().mean()
    a=r.weighted_training_loss(x,target,base,1.0)
    b=base(x,target)
    assert torch.allclose(a,b)
    assert torch.allclose(torch.autograd.grad(a,x,retain_graph=True)[0],torch.autograd.grad(b,x)[0])

def test_ignore_and_weight_raise_relative_lesion_gradient():
    x=torch.zeros(1,5,1,3,requires_grad=True)
    y=torch.tensor([[[2,1,255]]])
    ce=lambda a,b:F.cross_entropy(a,b,ignore_index=255)
    weighted=r.weighted_training_loss(x,y,ce,3.0)
    grad=torch.autograd.grad(weighted,x)[0]
    assert grad[0,2,0,0].abs()>grad[0,1,0,1].abs()
    assert torch.equal(grad[:,:,:,2],torch.zeros_like(grad[:,:,:,2]))
