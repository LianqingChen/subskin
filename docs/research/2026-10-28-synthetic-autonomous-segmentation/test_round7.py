"""Five-class synthetic label and area accounting checks."""
import importlib.util
from pathlib import Path
import unittest
import numpy as np
import torch
from PIL import Image
HERE=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('r7',HERE/'round7.py');r7=importlib.util.module_from_spec(s);s.loader.exec_module(r7)
class TestRound7(unittest.TestCase):
 def test_generated_sources_and_labels(self):
  paths=[HERE/'generated'/x for x in ('train-medium.png','val-light.png','test7-medium.png')]
  self.assertEqual(len({r7.r3.digest(x) for x in paths}),3)
  with Image.open(paths[-1]) as im:base=np.asarray(im.convert('RGB'))
  pixels=np.zeros(5,dtype=np.int64);positive=negative=0
  for seed in range(850000,850064):
   a,y=r7.make(base,seed);b,z=r7.make(base,seed)
   self.assertTrue(np.array_equal(a,b) and np.array_equal(y,z))
   self.assertTrue(np.isfinite(a).all() and np.isin(y,[0,1,2,3,4]).all());self.assertTrue(np.isin(y,[1,2]).any())
   pixels+=np.bincount(y.ravel(),minlength=5);positive+=bool((y==2).any());negative+=not bool((y==2).any())
  self.assertTrue((pixels>0).all());self.assertGreater(positive,0);self.assertGreater(negative,0)
 def test_area_and_skin_measurement(self):
  truth=torch.tensor([[[0,1],[2,3]]]);perfect=r7.metrics(truth.numpy(),truth)
  self.assertEqual(perfect['pixel_accuracy'],1);self.assertAlmostEqual(perfect['area_share_mae_pp'],0)
  empty=r7.metrics(np.array([[[0,0],[0,3]]]),truth)
  self.assertEqual(empty['predicted_empty_skin_images'],1);self.assertAlmostEqual(empty['area_share_mae_pp'],50)
if __name__=='__main__':unittest.main()
