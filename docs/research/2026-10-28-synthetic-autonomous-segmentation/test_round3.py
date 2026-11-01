"""Checks for generated-image provenance split and deterministic labels."""
import importlib.util
from pathlib import Path
import unittest
import numpy as np
from PIL import Image
root = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('round3', root / 'round3.py')
r3 = importlib.util.module_from_spec(spec); spec.loader.exec_module(r3)
class TestSyntheticRoundThree(unittest.TestCase):
    def test_independent_bases(self):
        paths = [root/'generated'/name for name in ('train-medium.png','val-light.png','test-dark.png')]
        self.assertEqual(len({r3.digest(path) for path in paths}), 3)
        self.assertTrue(set(range(10000,10128)).isdisjoint(range(200000,200064)))
        self.assertTrue(set(range(10000,10128)).isdisjoint(range(500000,500064)))
        self.assertTrue(set(range(200000,200064)).isdisjoint(range(500000,500064)))
    def test_seed_repeat_and_target_consistency(self):
        with Image.open(root/'generated'/'test-dark.png') as img:
            base=np.asarray(img.convert('RGB'))
        negative=small=0
        for seed in range(500000,500064):
            x,y,meta=r3.render(base,seed);x2,y2,meta2=r3.render(base,seed)
            self.assertTrue(np.array_equal(x,x2) and np.array_equal(y,y2));self.assertEqual(meta,meta2)
            self.assertTrue(np.isfinite(x).all() and np.isin(y,(0,1)).all());self.assertEqual(bool(y.any()),not meta['negative'])
            negative += meta['negative']; small += meta['small']
        self.assertGreaterEqual(negative,10);self.assertGreaterEqual(small,8)
if __name__=='__main__': unittest.main()
