import pytest
import torch
from ml.rgb_segmentation.losses import class_weights_from_counts,lesion_aware_loss


def test_unlabeled_batch_has_zero_finite_gradient():
    x=torch.randn(1,5,3,4,requires_grad=True);y=torch.full((1,3,4),255,dtype=torch.long)
    result=lesion_aware_loss(x,y,torch.ones(5));result.backward()
    assert result.item()==0 and torch.equal(x.grad,torch.zeros_like(x))


def test_ignored_pixels_never_change_loss_or_gradient():
    x=torch.zeros(1,5,2,2,requires_grad=True);y=torch.tensor([[[1,2],[255,255]]]);w=torch.ones(5)
    a=lesion_aware_loss(x,y,w);a.backward();assert torch.equal(x.grad[:,:,1],torch.zeros_like(x.grad[:,:,1]))
    changed=x.detach().clone();changed[:,:,1]=torch.tensor([9.,-7.,5.,3.,-4.])[:,None]
    assert torch.allclose(a.detach(),lesion_aware_loss(changed,y,w))


def test_small_lesion_has_nonzero_finite_learning_signal():
    x=torch.zeros(1,5,32,32,requires_grad=True);y=torch.ones(1,32,32,dtype=torch.long);y[0,0,0]=2
    w=class_weights_from_counts(torch.tensor([0,1023,1,0,0]));assert w[2]>w[1] and w.max()<=4
    result=lesion_aware_loss(x,y,w);result.backward()
    assert torch.isfinite(result) and torch.isfinite(x.grad).all() and x.grad[0,2,0,0]<0


@pytest.mark.parametrize('counts', [torch.zeros(5),torch.tensor([1,2,3,4,float('nan')]),torch.tensor([-1,1,1,1,1])])
def test_invalid_class_counts_rejected(counts):
    with pytest.raises(ValueError):class_weights_from_counts(counts)


def test_unseen_weighted_class_is_not_silently_ignored():
    with pytest.raises(ValueError):lesion_aware_loss(torch.zeros(1,5,1,1),torch.tensor([[[2]]]),torch.tensor([1.,1.,0.,1.,1.]))
