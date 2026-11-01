import importlib.util
from pathlib import Path
import torch
import pytest

spec = importlib.util.spec_from_file_location('round26', Path(__file__).with_name('round26.py'))
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)

def test_gate_stats_ignores_unknown_and_counts_negative_images():
    pairs=[]
    for _ in range(25): pairs.append((torch.tensor([[2, 1, 2]]),torch.tensor([[2, 2, 255]])))
    for i in range(7): pairs.append((torch.tensor([[2 if i<2 else 1, 2]]),torch.tensor([[1, 255]])))
    s=r.validation_stats(pairs)
    assert s=={'positive':25,'negative':7,'recall':.5,'false_positives':2}

def test_gate_rejects_missing_or_unreadable_validation():
    with pytest.raises(ValueError): r.validation_stats([(torch.tensor([[1]]),torch.tensor([[255]]))])
    with pytest.raises(ValueError): r.validation_stats([])
