"""Generated-arm mask, ignored-boundary and metrics accounting tests."""
import importlib.util
from pathlib import Path
import unittest
import numpy as np
import torch
HERE=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('r8',HERE/'round8.py');r8=importlib.util.module_from_spec(s);s.loader.exec_module(r8)
class TestRound8(unittest.TestCase):
 def test_masks_and_sources(self):
  paths=[HERE/'generated'/x for x in ('train8-arm.png','test8b-arm.png')]
  self.assertEqual(len({r8.r3.digest(p) for p in paths}),2)
  for p in paths:
   rgb,skin=r8.source(p);self.assertGreater(skin.mean(),.1);self.assertLess(skin.mean(),.9)
   a,b=r8.make(rgb,skin,960000);c,d=r8.make(rgb,skin,960000)
   self.assertTrue(np.array_equal(a,c) and np.array_equal(b,d));self.assertTrue(np.isin(b,[0,1,2,3,4,255]).all())
   self.assertTrue(np.isfinite(a).all() and np.isin(b,[1,2]).any())
 def test_ignore_mask_does_not_count_as_error(self):
  truth=torch.tensor([[[0,1],[2,255]]]);pred=np.array([[[0,1],[2,4]]]);m=r8.metrics(pred,truth)
  self.assertAlmostEqual(m['pixel_accuracy_valid'],1);self.assertAlmostEqual(m['ignored_pixel_pct'],25);self.assertAlmostEqual(m['area_share_mae_pp'],0)
if __name__=='__main__':unittest.main()
