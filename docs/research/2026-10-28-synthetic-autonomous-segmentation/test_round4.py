"""Contract tests for fourth-round synthetic evaluation only."""
import importlib.util
from pathlib import Path
import unittest
import numpy as np
from PIL import Image

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('r4',HERE/'round4.py');r4=importlib.util.module_from_spec(spec);spec.loader.exec_module(r4)

class TestRound4(unittest.TestCase):
    def test_sources_disjoint(self):
        paths=[HERE/'generated'/x for x in ('train-medium.png','val-light.png','test-dark.png','test4-light.png','test4-dark.png')]
        self.assertEqual(len(set(r4.r3.digest(p) for p in paths)),5)
    def test_cases_labels_and_repeatability(self):
        for index,name in enumerate(('test4-light.png','test4-dark.png')):
            with Image.open(HERE/'generated'/name) as im:base=np.asarray(im.convert('RGB'))
            all_seeds=[]
            for j,kind in enumerate(('standard','weak','glare')):
                for seed in range(600000+index*10000+j*1000,600032+index*10000+j*1000):
                    a,y,m=r4.make_case(base,seed,kind);b,z,n=r4.make_case(base,seed,kind)
                    self.assertTrue(np.array_equal(a,b) and np.array_equal(y,z));self.assertEqual(m,n)
                    self.assertTrue(np.isfinite(a).all() and np.isin(y,(0,1)).all());self.assertEqual(bool(y.any()),kind!='glare')
                    all_seeds.append(seed)
            self.assertEqual(len(set(all_seeds)),len(all_seeds))
if __name__=='__main__':unittest.main()
