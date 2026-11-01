import importlib.util
from pathlib import Path
import numpy as np
import pytest
import torch
s=importlib.util.spec_from_file_location('r39',Path(__file__).with_name('round39.py'));r=importlib.util.module_from_spec(s);s.loader.exec_module(r)

def test_crop_preserves_pair_alignment_and_categorical_masks():
    image=torch.linspace(0,1,128*128).reshape(1,1,128,128).repeat(2,3,1,1)
    labels=torch.ones((2,128,128),dtype=torch.long);labels[0,3:6,110:113]=2;labels[:,60:70,:]=255
    a,b=r.focused_crop(image,labels,np.random.default_rng(12))
    assert a.shape==(2,3,128,128) and b.shape==(2,128,128)
    assert torch.equal(a[0],a[1]) and (b[0]==2).any() and not (b[1]==2).any()
    assert set(torch.unique(b).tolist())<={1,2,255}

def test_crop_rejects_missing_lesion():
    with pytest.raises(ValueError):r.focused_crop(torch.zeros(2,3,128,128),torch.ones(2,128,128,dtype=torch.long),np.random.default_rng(1))
