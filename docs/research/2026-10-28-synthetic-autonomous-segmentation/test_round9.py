"""Generated hand masks, data split and explicit ignored-region checks."""
import importlib.util
from pathlib import Path
import unittest
import numpy as np
import torch
HERE=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('r9',HERE/'round9.py');r9=importlib.util.module_from_spec(s);s.loader.exec_module(r9)
class TestRound9(unittest.TestCase):
 def test_data_source_and_labels(self):
  paths=[HERE/'generated'/x for x in ('train8-arm.png','test8b-arm.png','train9-hand.png','test9-hand.png')]
  self.assertEqual(len({r9.r3.digest(p) for p in paths}),4)
  for i,path in enumerate(paths):
   rgb,skin=(r9.r8.source(path) if i<2 else r9.hand_source(path));a,b=r9.r8.make(rgb,skin,980000+i);c,d=r9.r8.make(rgb,skin,980000+i)
   self.assertTrue(np.array_equal(a,c) and np.array_equal(b,d));self.assertTrue(np.isin(b,[0,1,2,3,4,255]).all())
 def test_rejected_pixels_do_not_count_as_correct(self):
  truth=torch.tensor([[[0,1],[2,255]]]);pred=np.array([[[0,1],[0,2]]]);m=r9.r8.metrics(pred,truth)
  self.assertAlmostEqual(m['ignored_pixel_pct'],25);self.assertAlmostEqual(m['pixel_accuracy_valid'],2/3)
if __name__=='__main__':unittest.main()
