import importlib.util
from pathlib import Path
import torch
spec=importlib.util.spec_from_file_location('r30',Path(__file__).with_name('round30.py'));r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)

def test_consistency_only_identical_normal_skin_has_gradient():
    logits=torch.zeros(2,5,1,4,requires_grad=True)
    with torch.no_grad(): logits[0,2,0,:]=1
    images=torch.zeros(2,3,1,4);images[1,:,0,1]=1
    labels=torch.tensor([[[1,1,2,255]],[[1,1,1,1]]])
    c=r.consistency(logits,images,labels);assert c>0
    g=torch.autograd.grad(c,logits)[0]
    assert g[:,:,:,0].abs().sum()>0 and torch.count_nonzero(g[:,:,:,1:])==0

def test_equal_predictions_and_empty_mask_are_zero():
    logits=torch.zeros(2,5,2,2,requires_grad=True);images=torch.zeros(2,3,2,2);labels=torch.ones(2,2,2,dtype=torch.long)
    assert r.consistency(logits,images,labels).item()==0
    labels[:]=255;c=r.consistency(logits,images,labels);c.backward();assert c.item()==0 and torch.isfinite(logits.grad).all()
