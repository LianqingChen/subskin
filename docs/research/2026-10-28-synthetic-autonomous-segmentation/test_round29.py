import importlib.util
from pathlib import Path
import numpy as np
spec=importlib.util.spec_from_file_location('r29',Path(__file__).with_name('round29_prepare.py'));r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)

def test_pair_replays_original_and_preserves_nonlesion_background():
    path=Path(__file__).with_name('generated')/'train8-arm.png'
    rgb,skin=r.r9.r8.source(path)
    positives=0
    for seed in range(2900000,2900012):
        pos,pm,neg,nm,foot=r.paired_make(rgb,skin,seed)
        old,oldm=r.r9.r8.make(rgb,skin,seed)
        assert np.array_equal(pos,old) and np.array_equal(pm,oldm)
        assert np.array_equal(pos[~foot],neg[~foot])
        assert np.array_equal(pm==3,nm==3) and np.array_equal(pm==4,nm==4)
        assert not (nm==2).any()
        positives+=int((pm==2).any())
    assert positives>0
