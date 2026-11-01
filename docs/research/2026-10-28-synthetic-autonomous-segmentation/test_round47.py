import importlib.util
from pathlib import Path
import sys
import pytest
import torch
sys.path.insert(0,str(Path(__file__).parent))
s=importlib.util.spec_from_file_location('r47',Path(__file__).with_name('round47_validation.py'));r=importlib.util.module_from_spec(s);s.loader.exec_module(r)

def make_perfect():
    return [(torch.tensor([[2]]),torch.tensor([[2]])) if j%2==0 else (torch.tensor([[1]]),torch.tensor([[1]])) for _ in range(20) for j in range(16)]

def test_rejects_source_with_many_complete_misses():
    data=make_perfect();assert r.passes_validation(r.validation_stats(data))
    for j in range(0,10,2):data[160+j]=(torch.tensor([[1]]),torch.tensor([[2]]))
    assert not r.passes_validation(r.validation_stats(data))

def test_high_recall_low_dice_and_missing_are_rejected():
    data=make_perfect()
    for i in range(160,320,2):
        truth=torch.ones((1,128),dtype=torch.long);truth[0,0]=2;data[i]=(torch.full((1,128),2,dtype=torch.long),truth)
    stats=r.validation_stats(data);assert stats['small']['recall']==1 and stats['small_mean_dice']<.2 and not r.passes_validation(stats)
    with pytest.raises(ValueError):r.validation_stats(data[:-1])
