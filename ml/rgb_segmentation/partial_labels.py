"""Opt-in partial-label supervision; never invent full masks from auxiliary labels."""
import torch
from torch.nn import functional as F


def nail_auxiliary_loss(main_logits: torch.Tensor,nail_logits: torch.Tensor,target: torch.Tensor) -> torch.Tensor:
    """0=not-nail, 1=nail, 255=unknown. Non-nail may still be other occlusion.

    A separate binary head learns both signs. Only nail-positive pixels supervise
    class 3 of the five-class head. No five-class negative or healthy label is inferred.
    """
    if (main_logits.ndim!=4 or main_logits.shape[1]!=5
            or nail_logits.shape!=(main_logits.shape[0],1,*main_logits.shape[2:])
            or target.shape!=(main_logits.shape[0],*main_logits.shape[2:])):
        raise ValueError("Aligned main, auxiliary and partial-label grids required")
    if not torch.isfinite(main_logits).all() or not torch.isfinite(nail_logits).all():
        raise ValueError("Nonfinite logits")
    valid=target!=255
    if ((target[valid]!=0)&(target[valid]!=1)).any():raise ValueError("Partial nail labels must be 0, 1 or 255")
    zero=main_logits.sum()*0+nail_logits.sum()*0
    if not valid.any():return zero
    auxiliary=F.binary_cross_entropy_with_logits(nail_logits[:,0][valid],target[valid].to(nail_logits.dtype))
    positive=target==1
    if not positive.any():return auxiliary+zero
    main_target=torch.full_like(target,255);main_target[positive]=3
    return auxiliary+.25*F.cross_entropy(main_logits,main_target,ignore_index=255)
