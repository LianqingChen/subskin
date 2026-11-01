"""Stress transforms do not change image size or dtype."""
import importlib.util
from pathlib import Path
import unittest
import numpy as np
HERE=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('stress',HERE/'round14-stress.py');stress=importlib.util.module_from_spec(s);s.loader.exec_module(stress)
class TestStress(unittest.TestCase):
 def test_photometric_transforms_preserve_geometry(self):
  rng=np.random.default_rng(10);image=rng.integers(0,256,(256,512,3),dtype=np.uint8)
  for kind in ('blur_1_5','blur_3','jpeg_15','gamma_2'):
   transformed=stress.degrade(image,kind);self.assertEqual(transformed.shape,image.shape);self.assertEqual(transformed.dtype,np.uint8)
if __name__=='__main__':unittest.main()
