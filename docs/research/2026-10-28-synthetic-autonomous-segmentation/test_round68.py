import torch
import round68_train as r

def test_ranking_gradients_and_mask():
    logits=torch.zeros((2,5,2,2),requires_grad=True);targets=torch.ones((2,2,2),dtype=torch.long);targets[0,0,0]=2
    value=r.paired_ranking(logits,targets);value.backward()
    assert logits.grad[0,2,0,0]<0 and logits.grad[1,2,0,0]>0
    assert torch.count_nonzero(logits.grad)==4 and torch.count_nonzero(logits.grad[:,:,1,1])==0

def test_empty_mask_gives_zero_and_grad():
    logits=torch.zeros((2,5,2,2),requires_grad=True);targets=torch.ones((2,2,2),dtype=torch.long);loss=r.paired_ranking(logits,targets);loss.backward()
    assert loss.item()==0 and torch.count_nonzero(logits.grad)==0
