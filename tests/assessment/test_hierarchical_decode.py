import numpy as np
import pytest
from ml.rgb_segmentation.hierarchy import decode_hierarchical


def test_split_skin_mass_can_recover_lesion_without_gold():
    p=np.array([[.40,.25,.35,0,0]])
    assert p.argmax(axis=-1).item()==0
    assert decode_hierarchical(p).item()==2


def test_occlusion_unreadable_and_ties_are_not_promoted():
    p=np.array([[.05,.10,.25,.60,0],[.05,.10,.25,0,.60],[.50,.25,.25,0,0],[.1,.45,.45,0,0]])
    assert decode_hierarchical(p).tolist()==[3,4,0,1]


@pytest.mark.parametrize("p", [np.array([[.2,.2,.2,.2,np.nan]]),np.ones((2,5)),np.zeros((2,4)),np.array([[-.1,.2,.3,.3,.3]])])
def test_invalid_probabilities_fail_closed(p):
    with pytest.raises(ValueError):decode_hierarchical(p)


def test_multidimensional_input_preserves_grid_and_input():
    p=np.full((3,4,5),.2);before=p.copy()
    result=decode_hierarchical(p)
    assert result.shape==(3,4) and result.dtype==np.uint8
    assert np.array_equal(p,before)
