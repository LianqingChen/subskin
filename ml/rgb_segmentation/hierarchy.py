"""Research decoding policies; these functions do not grant measurement eligibility."""
import numpy as np


def decode_hierarchical(probabilities: np.ndarray, lesion_threshold: float = .5) -> np.ndarray:
    """Compare total skin mass against background/occlusion/unreadable first."""
    p=np.asarray(probabilities)
    if (p.ndim < 2 or p.shape[-1] != 5 or not np.isfinite(p).all()
            or np.any(p < 0) or np.any(p > 1)
            or not np.allclose(p.sum(axis=-1),1,atol=1e-5)
            or not 0 < lesion_threshold < 1):
        raise ValueError("Expected normalized finite five-class probabilities")
    other=p[...,[0,3,4]]
    result=np.array([0,3,4],dtype=np.uint8)[other.argmax(axis=-1)]
    skin=p[...,1]+p[...,2]
    inside=skin > other.max(axis=-1)
    result[inside]=1
    lesion=inside & (p[...,2] > lesion_threshold * skin)
    result[lesion]=2
    return result
