"""Opt-in research losses; the default trainer is unchanged."""
import torch
from torch.nn import functional as F


def class_weights_from_counts(counts: torch.Tensor) -> torch.Tensor:
    counts=torch.as_tensor(counts,dtype=torch.float32)
    if counts.shape!=(5,) or not torch.isfinite(counts).all() or (counts<0).any() or not (counts>0).any():
        raise ValueError("Expected nonempty finite five-class training counts")
    present=counts>0
    weights=torch.zeros_like(counts)
    weights[present]=(counts[present].mean()/counts[present]).sqrt().clamp(.25,4)
    return weights


def lesion_aware_loss(logits: torch.Tensor,target: torch.Tensor,weights: torch.Tensor) -> torch.Tensor:
    if logits.ndim!=4 or logits.shape[1]!=5 or target.shape!=(logits.shape[0],logits.shape[2],logits.shape[3]):
        raise ValueError("Expected Bx5xHxW logits and aligned labels")
    if not torch.isfinite(logits).all():raise ValueError("Nonfinite logits")
    valid=target!=255
    if not valid.any():return logits.sum()*0
    if (target[valid]<0).any() or (target[valid]>4).any():raise ValueError("Invalid labels")
    weights=weights.to(device=logits.device,dtype=logits.dtype)
    if weights.shape!=(5,) or not torch.isfinite(weights).all() or (weights<0).any() or (weights[target[valid]]<=0).any():
        raise ValueError("Every observed class requires a finite positive weight")
    ce=F.cross_entropy(logits,target,weight=weights,ignore_index=255)
    safe=target.masked_fill(~valid,0)
    truth=F.one_hot(safe,5).permute(0,3,1,2).to(logits.dtype)*valid[:,None]
    probability=logits.softmax(1)*valid[:,None]
    count=truth.sum((0,2,3));present=count>0
    dice=(2*(probability*truth).sum((0,2,3))+1e-6)/(probability.sum((0,2,3))+count+1e-6)
    importance=torch.ones(5,device=logits.device,dtype=logits.dtype);importance[2]=2
    return ce+((1-dice[present])*importance[present]).sum()/importance[present].sum()
