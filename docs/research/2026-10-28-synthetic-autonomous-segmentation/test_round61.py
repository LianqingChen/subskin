import importlib.util
from pathlib import Path
import sys
import numpy as np
from PIL import Image
sys.path.insert(0,str(Path(__file__).parent));s=importlib.util.spec_from_file_location('r61',Path(__file__).with_name('round61.py'));r=importlib.util.module_from_spec(s);s.loader.exec_module(r)

def test_letterbox_preserves_ratio_and_rejects_drift(tmp_path):
    p=tmp_path/'x.png';Image.fromarray(np.zeros((100,200,3),np.uint8)).save(p);canvas,info=r.read_letterbox(p)
    assert canvas.shape==(512,512,3) and info['resized']==[512,256] and info['offset']==[0,128]
    assert r.acceptable_aspect(2,2.01) and not r.acceptable_aspect(2,2.1)

def test_skin_gate_rejects_all_background():
    x=np.empty((512,512,3),np.uint8);x[:]=[0,180,250]
    try:r.skin_core(x)
    except ValueError:return
    assert False,'empty skin must be rejected'


def test_native_corner_check_not_hidden_by_padding(tmp_path):
    p=tmp_path/"bad.png";Image.fromarray(np.zeros((100,200,3),np.uint8)).save(p)
    assert not r.native_corners_cyan(p)
