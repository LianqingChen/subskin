import pytest
import torch
from ml.rgb_segmentation.partial_labels import nail_auxiliary_loss


def test_non_nail_pixels_never_receive_main_skin_or_background_labels():
    main=torch.zeros(1,5,1,3,requires_grad=True);nail=torch.zeros(1,1,1,3,requires_grad=True)
    target=torch.tensor([[[1,0,255]]]);value=nail_auxiliary_loss(main,nail,target);value.backward()
    assert main.grad[0,3,0,0]<0
    assert torch.equal(main.grad[:,:,:,1:],torch.zeros_like(main.grad[:,:,:,1:]))
    assert nail.grad[0,0,0,0]<0 and nail.grad[0,0,0,1]>0 and nail.grad[0,0,0,2]==0


def test_all_negative_auxiliary_data_does_not_relabel_other_occlusion():
    main=torch.randn(1,5,2,2,requires_grad=True);nail=torch.zeros(1,1,2,2,requires_grad=True)
    value=nail_auxiliary_loss(main,nail,torch.zeros(1,2,2,dtype=torch.long));value.backward()
    assert torch.equal(main.grad,torch.zeros_like(main)) and torch.isfinite(value)


def test_all_ignored_has_zero_finite_gradient():
    main=torch.randn(1,5,2,2,requires_grad=True);nail=torch.randn(1,1,2,2,requires_grad=True)
    value=nail_auxiliary_loss(main,nail,torch.full((1,2,2),255,dtype=torch.long));value.backward()
    assert value==0 and torch.equal(main.grad,torch.zeros_like(main)) and torch.equal(nail.grad,torch.zeros_like(nail))


def test_invalid_partial_labels_fail_closed():
    with pytest.raises(ValueError):nail_auxiliary_loss(torch.zeros(1,5,1,1),torch.zeros(1,1,1,1),torch.tensor([[[3]]]))
