import importlib.util
from pathlib import Path
import sys
import cv2
import numpy as np
sys.path.insert(0,str(Path(__file__).parent))
s=importlib.util.spec_from_file_location('r51',Path(__file__).with_name('round51_prepare.py'));r=importlib.util.module_from_spec(s);s.loader.exec_module(r)

def test_lab_intervention_preserves_outside_and_increases_lightness():
    clean=np.full((8,8,3),(.2,.3,.4),np.float32);positive=clean.copy();positive[2:6,2:6]+=0.2*(1-positive[2:6,2:6]);out=r.alternate_lab(clean,positive)
    assert np.array_equal(out[0],clean[0]) and np.isfinite(out).all()
    before=cv2.cvtColor(clean,cv2.COLOR_RGB2LAB);after=cv2.cvtColor(out,cv2.COLOR_RGB2LAB)
    assert after[3,3,0]>before[3,3,0]

def test_identical_input_stays_identical():
    clean=np.full((4,4,3),.4,np.float32);assert np.array_equal(r.alternate_lab(clean,clean),clean)
