import importlib.util
from pathlib import Path
import pytest
import torch
s=importlib.util.spec_from_file_location('r50',Path(__file__).with_name('round50_train.py'));r=importlib.util.module_from_spec(s);s.loader.exec_module(r)

def test_exposure_preserves_pair_and_marks_only_clipping():
    img=torch.full((2,3,16,16),.3);img[:,:,2,2]=.9;labels=torch.ones(2,16,16,dtype=torch.long);labels[:,3,3]=255
    out,mask,n=r.exposure_augment(img,labels,1.2)
    assert torch.equal(out[0],out[1]) and mask[:,2,2].tolist()==[255,255] and n==2
    assert mask[:,3,3].tolist()==[255,255] and torch.all(mask[:,0,0]==1)

def test_rejects_unusable_full_clipping():
    with pytest.raises(ValueError):r.exposure_augment(torch.ones(2,3,16,16),torch.ones(2,16,16,dtype=torch.long),1.2)
