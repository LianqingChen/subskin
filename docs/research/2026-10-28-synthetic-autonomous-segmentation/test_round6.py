"""Synthetic mask and rejected-case accounting tests."""
import importlib.util
from pathlib import Path
import unittest
import numpy as np
from PIL import Image
HERE=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('r6',HERE/'round6.py');r6=importlib.util.module_from_spec(s);s.loader.exec_module(r6)
class TestRound6(unittest.TestCase):
 def test_holdout_hash_and_synthetic_masks(self):
  names=('train-medium.png','val-light.png','test4-light.png','test4-dark.png','test5-medium.png','test6-medium.png')
  paths=[HERE/'generated'/x for x in names];self.assertEqual(len({r6.r3.digest(p) for p in paths}),len(paths))
  with Image.open(paths[-1]) as im:base=np.asarray(im.convert('RGB'))
  for kind,(x,y,meta) in r6.make_test(base).items():
   self.assertEqual(len(meta),32)
   for i,m in enumerate(meta):self.assertEqual(bool(y[i].any()),kind!='glare')
 def test_rejected_cases_remain_in_denominator(self):
  truth=np.ones((2,4,4),bool);pred=truth.copy();accepted=np.array([True,False])
  result=r6.group_metrics(pred,truth,accepted,False)
  self.assertAlmostEqual(result['accepted_pixel_recall'],1);self.assertAlmostEqual(result['all_cases_effective_pixel_recall'],.5)
  result=r6.group_metrics(pred,np.zeros_like(truth),accepted,True)
  self.assertEqual(result['accepted_fp_image_gt_1pct'],100);self.assertEqual(result['all_cases_auto_fp_gt_1pct'],50)
if __name__=='__main__':unittest.main()
