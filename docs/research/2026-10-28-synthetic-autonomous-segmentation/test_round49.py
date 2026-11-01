import importlib.util
from pathlib import Path
import sys
import torch
root=Path(__file__).resolve().parents[3];sys.path.insert(0,str(root))
from ml.rgb_segmentation.network import RGBUNet
s=importlib.util.spec_from_file_location('r49',Path(__file__).with_name('round49_model.py'));r=importlib.util.module_from_spec(s);s.loader.exec_module(r)

def test_constant_is_neutral_and_local_brightening_increases_feature():
    x=torch.full((1,3,64,64),.3);assert torch.allclose(r.local_contrast(x),torch.full((1,1,64,64),.5),atol=1e-6)
    x[:,:,32,32]=.6;assert r.local_contrast(x)[0,0,32,32]>.5

def test_initial_output_and_rng_match_original_model():
    torch.set_num_threads(2);x=torch.linspace(0,1,3*32*32).reshape(1,3,32,32)
    torch.manual_seed(123);a=RGBUNet().eval();rng_a=torch.get_rng_state()
    torch.manual_seed(123);b=r.LocalContrastUNet().eval();rng_b=torch.get_rng_state()
    with torch.inference_mode():assert torch.allclose(a(x),b(x),atol=1e-6,rtol=1e-6)
    assert torch.equal(rng_a,rng_b)
