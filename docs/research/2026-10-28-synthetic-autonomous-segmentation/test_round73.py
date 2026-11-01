import torch
import round48_train as r

def test_hard_loss_gradient_targets_only_negative_valid():
    logits=torch.zeros((2,5,4,4),requires_grad=True);targets=torch.ones((2,4,4),dtype=torch.long);targets[1,0,0]=255
    with torch.no_grad():logits[1,2,2,2]=3
    loss=r.hard_negative_loss(logits,targets);loss.backward()
    assert logits.grad[1,2,2,2]>0 and torch.count_nonzero(logits.grad[0])==0 and torch.count_nonzero(logits.grad[1,:,0,0])==0

def test_reject_invalid_negative():
    logits=torch.zeros((2,5,2,2));targets=torch.ones((2,2,2),dtype=torch.long);targets[1,0,0]=2
    try:r.hard_negative_loss(logits,targets)
    except ValueError:return
    assert False
