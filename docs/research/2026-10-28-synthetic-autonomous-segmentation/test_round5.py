"""Synthetic-only validation of source split and held-out masks."""
import importlib.util
from pathlib import Path
import unittest
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('r5',ROOT/'round5.py');r5=importlib.util.module_from_spec(s);s.loader.exec_module(r5)

class TestRound5(unittest.TestCase):
    def test_sources_differ(self):
        paths=[ROOT/'generated'/x for x in ('train-medium.png','val-light.png','test5-medium.png')]
        self.assertEqual(len({r5.r3.digest(p) for p in paths}),len(paths))
    def test_test_masks_and_seeds(self):
        with Image.open(ROOT/'generated'/'test5-medium.png') as im:full=np.asarray(im.convert('RGB'))
        h,w=full.shape[:2];base=full[int(h*.25):int(h*.75),int(w*.10):int(w*.90)]
        seeds=[]
        for j,kind in enumerate(('standard','weak','glare')):
            for seed in range(920000+j*1000,920032+j*1000):
                x,y,m=r5.independent_case(base,seed,kind);x2,y2,m2=r5.independent_case(base,seed,kind)
                self.assertTrue(np.array_equal(x,x2) and np.array_equal(y,y2));self.assertEqual(m,m2)
                self.assertTrue(np.isfinite(x).all() and np.isin(y,[0,1]).all());self.assertEqual(bool(y.any()),kind!='glare')
                seeds.append(seed)
        self.assertEqual(len(seeds),len(set(seeds)))
if __name__=='__main__':unittest.main()
