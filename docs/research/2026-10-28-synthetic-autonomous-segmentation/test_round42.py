import importlib.util
from pathlib import Path
import torch
import pytest
s=importlib.util.spec_from_file_location('r42',Path(__file__).with_name('round42_validation.py'));r=importlib.util.module_from_spec(s);s.loader.exec_module(r)

def samples():
    return [(torch.tensor([[2]]),torch.tensor([[2]])) if j%2==0 else (torch.tensor([[1]]),torch.tensor([[1]])) for _ in range(10) for j in range(16)]

def test_per_source_gate_rejects_concentrated_false_positives():
    data=samples();assert r.passes_validation(r.validation_stats(data))
    for i in range(1,16,2):data[i]=(torch.tensor([[2]]),torch.tensor([[1]]))
    stats=r.validation_stats(data);assert stats['false_positives']==8 and not r.passes_validation(stats)

def test_missing_and_ignored_validation_are_rejected():
    with pytest.raises(ValueError):r.validation_stats(samples()[:-1])
    data=samples();data[0]=(torch.tensor([[1]]),torch.tensor([[255]]))
    with pytest.raises(ValueError):r.validation_stats(data)
